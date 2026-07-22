"""复盘 API v2 契约：统一接口语义、行业字段和数据时效。"""
import threading
import time

import backend.services.review_service as review_service
from backend.services.review_compute_service import generate_trading_plan
from backend.services.review_service import normalize_review_response


def test_cached_review_contract_is_completed_without_losing_legacy_sector():
    review = normalize_review_response({
        'date': '2026-07-15',
        'holdings_review': [{'code': '000001', 'sector': '银行'}],
    })

    assert review['holdings_review'][0]['industry'] == '银行'
    assert review['holdings_review'][0]['sector'] == '银行'
    assert review['data_dates'] == {}
    assert review['data_freshness'] == {}
    assert review['response_meta'] == {
        'source': 'cache',
        'computed_live': False,
        'contract_version': 2,
    }


def test_live_review_contract_marks_computation_source():
    review = normalize_review_response({}, source='live')

    assert review['response_meta']['source'] == 'live'
    assert review['response_meta']['computed_live'] is True
    assert review['holdings'] == []
    assert review['buy_signals'] == []


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
