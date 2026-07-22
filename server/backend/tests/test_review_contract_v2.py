"""复盘 API v3 契约：统一接口语义、行业字段和数据时效。"""
import threading
import time

import backend.services.review_service as review_service
from backend.services.review_compute_service import apply_trading_plan_actions, generate_trading_plan
from backend.services.review_service import normalize_review_response


def test_cached_review_contract_is_completed_without_losing_legacy_sector():
    review = normalize_review_response({
        'date': '2026-07-15',
        'holdings_review': [{'code': '000001', 'sector': '银行'}],
    })

    assert review['holdings_review'][0]['industry'] == '银行'
    assert review['holdings_review'][0]['sector'] == '银行'
    assert review['data_status']['overall'] == 'stale'
    assert review['response_meta'] == {
        'source': 'cache',
        'computed_live': False,
        'contract_version': 3,
        'deprecated_fields': ['holdings', 'buy_signals', 'data_dates', 'data_freshness', 'data_stale'],
    }


def test_live_review_contract_marks_computation_source():
    review = normalize_review_response({}, source='live')

    assert review['response_meta']['source'] == 'live'
    assert review['response_meta']['computed_live'] is True
    assert review['holdings_review'] == []
    assert review['buy_signals_review'] == []


def test_estimated_sector_status_is_ready_without_pretending_to_be_confirmed():
    review = normalize_review_response({
        'date': '2026-07-22',
        'data_dates': {
            'requested': '2026-07-22', 'index': '20260722',
            'stocks': '20260722', 'sectors': '20260721',
        },
        'mainline': {
            'ranking_status': 'estimated', 'ranking_date': '20260722',
            'base_date': '20260721', 'estimate_coverage': 0.9781,
            'concept_mainline': {
                'ranking_status': 'estimated', 'ranking_date': '20260722',
                'base_date': '20260721', 'estimate_coverage': 0.8533,
            },
        },
    })

    assert review['data_status']['overall'] == 'ready'
    assert review['data_status']['industry']['status'] == 'estimated'
    assert review['data_status']['industry']['confirmed_date'] == '20260721'
    assert review['data_status']['concept']['coverage'] == 0.8533
    assert review['data_stale'] is False


def test_archive_review_contract_marks_archive_source():
    review = normalize_review_response({'date': '2026-07-15'}, source='archive')

    assert review['response_meta']['source'] == 'archive'
    assert review['response_meta']['computed_live'] is False


def test_background_refresh_is_single_flight(monkeypatch):
    entered = threading.Event()
    release = threading.Event()
    saved = []

    def fake_compute(date_str):
        assert date_str == '2026-07-21'
        entered.set()
        assert release.wait(timeout=2)
        return {'date': '2026-07-21'}

    monkeypatch.setattr(review_service, 'compute_review_real_time', fake_compute)
    monkeypatch.setattr(review_service, 'get_completed_review_date', lambda: '2026-07-21')
    monkeypatch.setattr(review_service, 'save_review_data', saved.append)
    with review_service._review_refresh_lock:
        review_service._review_refresh_state.update({
            'status': 'idle', 'started_at': '', 'completed_at': '', 'error': '',
        })

    first = review_service.request_review_refresh(force=True)
    assert entered.wait(timeout=1)
    second = review_service.request_review_refresh(force=True)
    assert first['started'] is True
    assert second['started'] is False

    release.set()
    for _ in range(50):
        if review_service.get_review_refresh_status()['status'] == 'completed':
            break
        time.sleep(0.01)
    assert review_service.get_review_refresh_status()['status'] == 'completed'
    assert saved[0]['date'] == '2026-07-21'
    assert saved[0]['cache_generated_at']


def test_completed_review_date_uses_last_completed_trading_day(monkeypatch):
    monkeypatch.setattr(
        'backend.data_access.data_source.get_last_completed_trading_day',
        lambda: '20260720',
    )

    assert review_service.get_completed_review_date() == '2026-07-20'


def test_trading_plan_joins_opportunity_by_canonical_industry():
    plan = generate_trading_plan(
        market_cycle={'position': '波中'},
        mainline_data={'lines': []},
        signals_data={},
        existing_holdings=[],
        buy_signals_review=[{
            'code': '603986',
            'name': '兆易创新',
            'industry': '数字芯片设计',
            'sector': '半导体产品与设备Ⅱ(A股)',
            'action_type': '买入',
        }],
        opportunity_map={'数字芯片设计': '主线回调'},
    )

    item = plan['buy_priority'][0]
    assert item['industry'] == '数字芯片设计'
    assert item['sector'] == '数字芯片设计'
    assert item['opportunity'] == '主线回调'
    assert item['opp_reason'] == ''
    assert item['decision_status'] == 'executable'
    assert item['data_quality'] == 'ready'


def test_trading_plan_blocks_buy_when_estimated_snapshot_misses_industry():
    plan = generate_trading_plan(
        market_cycle={'position': '波中'},
        mainline_data={'ranking_status': 'estimated', 'lines': []},
        signals_data={},
        existing_holdings=[],
        buy_signals_review=[{
            'code': '000001',
            'name': '测试股票',
            'industry': '未覆盖行业',
            'action_type': '买入',
            'action_priority': '高',
        }],
        opportunity_map={'已覆盖行业': '--'},
    )

    item = plan['buy_priority'][0]
    assert item['action_type'] == '待确认'
    assert item['priority'] == '低'
    assert item['decision_status'] == 'blocked'
    assert item['data_quality'] == 'sector_unavailable'
    assert item['opp_reason'] == '未覆盖行业·当日板块快照未覆盖'


def test_trading_plan_keeps_buy_action_when_covered_industry_has_no_opportunity_label():
    plan = generate_trading_plan(
        market_cycle={'position': '波中'},
        mainline_data={'ranking_status': 'estimated', 'lines': []},
        signals_data={},
        existing_holdings=[],
        buy_signals_review=[{
            'code': '000002',
            'name': '测试股票',
            'industry': '已覆盖行业',
            'action_type': '买入',
        }],
        opportunity_map={'已覆盖行业': '--'},
    )

    item = plan['buy_priority'][0]
    assert item['action_type'] == '买入'
    assert item['decision_status'] == 'executable'
    assert item['data_quality'] == 'ready'


def test_trading_plan_action_is_synchronized_to_buy_signal_card():
    signals = [{'code': '000001.SZ', 'action_type': '买入'}]
    plan = {
        'buy_priority': [{
            'code': '000001',
            'action_type': '待确认',
            'decision_status': 'blocked',
            'data_quality': 'sector_unavailable',
            'opp_reason': '板块当日数据待补齐',
        }],
    }

    apply_trading_plan_actions(signals, plan)

    assert signals[0]['action_type'] == '待确认'
    assert signals[0]['decision_status'] == 'blocked'
    assert signals[0]['action_reason'] == '板块当日数据待补齐'
