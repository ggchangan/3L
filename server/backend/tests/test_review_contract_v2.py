"""复盘 API v3 契约：统一接口语义、行业字段和数据时效。"""
from contextlib import nullcontext
import threading
import time

import backend.services.review_service as review_service
from backend.services.review_compute_service import apply_trading_plan_actions, generate_trading_plan, judge_peak_valley
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


def test_partial_concept_status_keeps_review_partial_and_exposes_counts():
    review = normalize_review_response({
        'date': '2026-07-22',
        'data_dates': {
            'requested': '2026-07-22', 'index': '20260722',
            'stocks': '20260722', 'sectors': '20260722',
        },
        'mainline': {
            'ranking_status': 'confirmed',
            'ranking_date': '20260722',
            'concept_mainline': {
                'ranking_status': 'partial',
                'ranking_date': '20260722',
                'confirmed_date': '20260721',
                'coverage': 175 / 179,
                'coverage_detail': {
                    'covered': 175,
                    'expected': 179,
                    'missing': ['大飞机'],
                },
            },
        },
    })

    assert review['data_status']['overall'] == 'partial'
    assert review['data_status']['concept']['status'] == 'partial'
    assert review['data_status']['concept']['date'] == '20260722'
    assert review['data_status']['concept']['confirmed_date'] == '20260721'
    assert review['data_status']['concept']['coverage_detail']['expected'] == 179
    assert review['data_stale'] is True


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
    # 单飞测试不依赖跨进程文件锁，避免与正在运行的生产服务互相等待。
    monkeypatch.setattr(review_service, 'review_refresh_file_lock', nullcontext)
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
    assert item['sector_context'] == '主线·波谷'
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
    assert item['decision_status'] == 'signal_only'
    assert item['attention_tier'] == 'ordinary'
    assert item['data_quality'] == 'ready'


def test_trading_plan_prioritizes_mainline_before_sector_wave_stage():
    plan = generate_trading_plan(
        market_cycle={'position': '波中'},
        mainline_data={'lines': []},
        signals_data={},
        existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000001', 'name': '非主线波谷股', 'industry': '波谷行业',
                'action_type': '买入', 'mainline_level': '', 'structure': '上涨趋势',
            },
            {
                'code': '000002', 'name': '主线波峰股', 'industry': '波峰行业',
                'action_type': '买入', 'mainline_level': '主线', 'structure': '下降趋势',
            },
        ],
        opportunity_map={'波谷行业': '主线回调', '波峰行业': '见顶风险'},
    )

    assert [item['code'] for item in plan['buy_priority']] == ['000002', '000001']


def test_trading_plan_uses_momentum_rank_within_same_direction_level():
    plan = generate_trading_plan(
        market_cycle={'position': '波中'},
        mainline_data={
            'lines': [],
            'all_ranked': [{'name': '第一方向'}, {'name': '第二方向'}],
        },
        signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000002', 'name': '第二名上涨股', 'industry': '第二方向',
                'action_type': '买入', 'mainline_level': '主线', 'structure': '上涨趋势',
            },
            {
                'code': '000001', 'name': '第一名概念股', 'industry': '普通行业',
                'direction': '人工方向', 'matched_mainline_direction': '第一方向',
                'action_type': '买入', 'mainline_level': '主线', 'structure': '区间震荡',
            },
        ],
        opportunity_map={'普通行业': '--', '第二方向': '趋势延续'},
    )

    assert [item['code'] for item in plan['buy_priority']] == ['000001', '000002']
    assert [item['momentum_rank'] for item in plan['buy_priority']] == [1, 2]
    assert [item['momentum_total'] for item in plan['buy_priority']] == [2, 2]
    assert [item['momentum_source'] for item in plan['buy_priority']] == ['行业', '行业']
    assert [item['momentum_direction'] for item in plan['buy_priority']] == ['第一方向', '第二方向']


def test_trading_plan_explains_concept_momentum_and_rounds_quality_score():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={
            'lines': [],
            'all_ranked': [{'name': '行业方向'}],
            'concept_mainline': {
                'all_ranked': [
                    {'name': '第一概念'}, {'name': '目标概念'}, {'name': '第三概念'},
                ],
            },
        },
        signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '概念买点', 'industry': '普通行业',
            'matched_mainline_direction': '目标概念', 'action_type': '买入',
            'triggered_signals': [{
                'direction': 'bullish', 'confidence': 66.57076461728134,
            }],
        }],
        opportunity_map={'普通行业': '--'},
    )

    item = plan['buy_priority'][0]
    assert item['momentum_rank'] == 2
    assert item['momentum_total'] == 3
    assert item['momentum_source'] == '概念'
    assert item['momentum_direction'] == '目标概念'
    assert item['quality_score'] == 67
    assert item['quality_basis'] == '多信号融合置信度'


def test_trading_plan_separates_focus_watch_and_ordinary_signals_in_weak_market():
    rankings = [{'name': f'方向{index}'} for index in range(1, 52)]
    plan = generate_trading_plan(
        market_cycle={'position': '波中偏下', 'market_regime': 'weak'},
        mainline_data={'lines': [], 'all_ranked': rankings},
        signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000001', 'name': '主线买点', 'industry': '普通行业',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            },
            {
                'code': '000002', 'name': '强动量买点', 'industry': '方向1',
                'score': 3, 'action_type': '买入',
            },
            {
                'code': '000003', 'name': '次级观察', 'industry': '方向30',
                'score': 5, 'action_type': '买入',
            },
            {
                'code': '000004', 'name': '低质量信号', 'industry': '方向2',
                'score': 2, 'action_type': '买入',
            },
            {
                'code': '000005', 'name': '普通方向信号', 'industry': '方向51',
                'score': 4, 'action_type': '买入',
            },
        ],
        opportunity_map={
            '普通行业': '--', '方向1': '--', '方向30': '--',
            '方向2': '--', '方向51': '--',
        },
    )

    assert [item['attention_tier'] for item in plan['buy_priority']] == [
        'focus', 'focus', 'watch', 'ordinary', 'ordinary',
    ]
    assert plan['buy_summary'] == {
        'total': 5,
        'focus': 2,
        'watch': 1,
        'ordinary': 2,
        'market_regime': 'weak',
        'conclusion': '当前为弱势市场，重点买点也需等待确认并控制仓位。',
        'ranking_rule': '市场过滤 → 主线/强动量 → 个股买点质量 → 板块环境 → 止损风险',
    }
    assert plan['buy_priority'][0]['decision_status'] == 'candidate'
    assert plan['buy_priority'][0]['priority'] == '中'
    low_quality = next(item for item in plan['buy_priority'] if item['code'] == '000004')
    assert low_quality['decision_status'] == 'signal_only'
    assert low_quality['quality_score'] == 40
    assert '买点质量40' in low_quality['attention_reason']


def test_trading_plan_reduce_filter_never_marks_focus_as_executable():
    plan = generate_trading_plan(
        market_cycle={
            'position': '偏波峰', 'market_regime': 'strong',
            'pk_score': 5, 'bias20': 12,
        },
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '主线买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['attention_tier'] == 'focus'
    assert item['quality_score'] == 80
    assert item['decision_status'] == 'candidate'
    assert item['priority'] == '中'
    assert '高位或加速阶段' in plan['buy_summary']['conclusion']


def test_trading_plan_rest_filter_never_marks_focus_as_executable():
    plan = generate_trading_plan(
        market_cycle={
            'position': '下降趋势', 'market_regime': 'weak',
            'vl_score': 4, 'bias20': -9,
        },
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '主线买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['attention_tier'] == 'focus'
    assert item['decision_status'] == 'candidate'
    assert item['priority'] == '中'
    assert '只观察' in plan['buy_summary']['conclusion']


def test_trend_fixed_marker_is_not_presented_as_quality_100():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '趋势买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 5, 'trading_system': 'trend',
            'trend_stock': True, 'action_type': '买入',
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['attention_tier'] == 'focus'
    assert item['quality_score'] is None


def test_trading_plan_attention_tier_boundaries_are_explicit():
    rankings = [{'name': f'方向{index}'} for index in range(1, 52)]
    signals = [
        {
            'code': f'0000{index}', 'name': f'第{rank}名', 'industry': f'方向{rank}',
            'score': 4, 'action_type': '买入',
        }
        for index, rank in enumerate((20, 21, 50, 51), start=1)
    ]
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': [], 'all_ranked': rankings},
        signals_data={}, existing_holdings=[], buy_signals_review=signals,
        opportunity_map={f'方向{rank}': '--' for rank in (20, 21, 50, 51)},
    )

    tiers_by_rank = {item['momentum_rank']: item['attention_tier'] for item in plan['buy_priority']}
    assert tiers_by_rank == {20: 'focus', 21: 'watch', 50: 'watch', 51: 'ordinary'}


def test_trading_plan_sorts_same_direction_by_quality_then_stop_loss_risk():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': [], 'all_ranked': [{'name': '强方向'}]},
        signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000003', 'name': '低分宽止损', 'industry': '强方向',
                'score': 3, 'stop_loss_pct': -8, 'action_type': '买入',
            },
            {
                'code': '000002', 'name': '低分窄止损', 'industry': '强方向',
                'score': 3, 'stop_loss_pct': -4, 'action_type': '买入',
            },
            {
                'code': '000001', 'name': '高分信号', 'industry': '强方向',
                'score': 4, 'stop_loss_pct': -9, 'action_type': '买入',
            },
        ],
        opportunity_map={'强方向': '趋势延续'},
    )

    assert [item['code'] for item in plan['buy_priority']] == ['000001', '000002', '000003']


def test_market_regime_is_computed_from_chronological_snapshot():
    chronological = [
        {
            'date': f'2026-04-{index + 1:02d}',
            'open': 100 + index, 'high': 101 + index, 'low': 99 + index,
            'close': 100 + index, 'volume': 1000,
        }
        for index in range(80)
    ]

    result = judge_peak_valley(list(reversed(chronological)))

    assert result['market_regime'] == 'strong'
    assert result['structure'] == '上涨趋势'
    assert result['ma20'] > result['ma60']


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
