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
    archived = []

    def fake_compute(date_str):
        assert date_str == '2026-07-21'
        entered.set()
        assert release.wait(timeout=2)
        return {'date': '2026-07-21'}

    monkeypatch.setattr(review_service, 'compute_review_real_time', fake_compute)
    monkeypatch.setattr(review_service, 'get_completed_review_date', lambda: '2026-07-21')
    monkeypatch.setattr(review_service, 'save_review_data', saved.append)
    monkeypatch.setattr(review_service, 'save_review_snapshot', archived.append)
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
    assert archived == saved


def test_completed_review_date_uses_last_completed_trading_day(monkeypatch):
    monkeypatch.setattr(
        'backend.data_access.data_source.get_last_completed_trading_day',
        lambda: '20260720',
    )

    assert review_service.get_completed_review_date() == '2026-07-20'


def test_previous_review_date_uses_trade_calendar(monkeypatch):
    monkeypatch.setattr(
        'backend.data_access.data_source.get_previous_trading_day',
        lambda reference: '20260717',
    )

    assert review_service.get_previous_review_date('2026-07-20') == '2026-07-17'


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
    assert item['decision_status'] == 'candidate'
    assert item['buy_point_category'] == 'unknown'
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
    assert item['action_type'] == '技术信号'
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
        'conclusion': '当前为弱势市场，重点信号需符合恐慌、供应衰竭或明确反转买点后才可执行。',
        'ranking_rule': '市场过滤 → 主线/强动量 → 个股买点质量 → 板块环境 → 止损风险',
    }
    assert plan['buy_priority'][0]['decision_status'] == 'candidate'
    assert plan['buy_priority'][0]['action_type'] == '观察'
    assert plan['buy_priority'][0]['priority'] == '中'
    low_quality = next(item for item in plan['buy_priority'] if item['code'] == '000004')
    assert low_quality['decision_status'] == 'signal_only'
    assert low_quality['action_type'] == '技术信号'
    assert low_quality['quality_score'] == 40
    assert '买点质量40' in low_quality['attention_reason']


def test_trading_plan_peak_risk_blocks_breakout_but_not_every_valid_buy():
    plan = generate_trading_plan(
        market_cycle={
            'position': '偏波峰', 'market_regime': 'strong',
            'pk_score': 5, 'bias20': 12,
        },
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000001', 'name': '突破标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '突破买点',
            },
            {
                'code': '000002', 'name': '回踩标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '缩量回踩', 'structure': '上涨趋势', 'stage': '上行',
                'stop_loss': 9.5,
            },
        ],
        opportunity_map={'主线方向': '趋势延续'},
    )

    items = {item['code']: item for item in plan['buy_priority']}
    assert items['000001']['decision_status'] == 'candidate'
    assert items['000001']['market_compatible'] is False
    assert '波峰风险阶段避免突破追高' in items['000001']['attention_reason']
    assert items['000002']['decision_status'] == 'executable'
    assert items['000002']['market_compatible'] is True
    assert '避免突破追高' in plan['buy_summary']['conclusion']


def test_trading_plan_valley_recovery_allows_focus_to_be_executable():
    plan = generate_trading_plan(
        market_cycle={
            'position': '下降趋势', 'market_regime': 'weak',
            'vl_score': 4, 'bias20': -9,
        },
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '主线买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '明确反转买点', 'structure': '下降趋势', 'stage': '转强',
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['attention_tier'] == 'focus'
    assert item['decision_status'] == 'executable'
    assert item['priority'] == '高'
    assert plan['market_strategy']['risk_phase'] == 'valley_recovery'
    assert '随主线/强动量中的有效买点逐步增加仓位' in plan['market_strategy']['position_action']


def test_dynamic_position_uses_actual_holdings_and_planned_sells_in_main_decline():
    plan = generate_trading_plan(
        market_cycle={
            'position': '波中', 'structure': '下降趋势',
            'market_regime': 'weak', 'vl_score': 2, 'pk_score': 1,
        },
        mainline_data={'lines': []}, signals_data={},
        existing_holdings=[
            {'code': '300604', 'target_ratio': 40},
            {'code': '600584', 'target_ratio': 4},
            {'code': '603986', 'target_ratio': 6},
        ],
        holdings_review=[
            {'code': '300604', 'name': '长川科技', 'action_type': '持有'},
            {'code': '600584', 'name': '长电科技', 'action_type': '卖出'},
            {'code': '603986', 'name': '兆易创新', 'action_type': '卖出'},
        ],
    )

    strategy = plan['market_strategy']
    assert strategy['environment'] == 'weak'
    assert strategy['risk_phase'] == 'main_decline'
    assert strategy['current_position_pct'] == 50
    assert strategy['planned_exit_pct'] == 10
    assert strategy['position_after_exits_pct'] == 40
    assert strategy['executable_buy_count'] == 0
    assert plan['position_level'] == '当前50% → 卖出后约40%'
    assert '七至八成' not in plan['position_detail']
    assert '恐慌买点' in strategy['allowed_buy_points']


def test_dynamic_position_does_not_guess_when_any_holding_ratio_is_missing():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={},
        existing_holdings=[
            {'code': '000001', 'target_ratio': 30},
            {'code': '000002'},
        ],
        holdings_review=[
            {'code': '000001', 'name': '已知比例', 'action_type': '卖出'},
            {'code': '000002', 'name': '缺少比例', 'action_type': '持有'},
        ],
    )

    strategy = plan['market_strategy']
    assert strategy['current_position_pct'] is None
    assert strategy['planned_exit_pct'] is None
    assert strategy['position_after_exits_pct'] is None
    assert plan['position_level'] == '当前仓位未记录'


def test_dynamic_position_counts_switch_as_full_exit():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={},
        existing_holdings=[{'code': '000001', 'target_ratio': 25}],
        holdings_review=[{'code': '000001', 'name': '换股标的', 'action_type': '换股'}],
    )

    strategy = plan['market_strategy']
    assert strategy['planned_exit_pct'] == 25
    assert strategy['position_after_exits_pct'] == 0


def test_dynamic_position_keeps_after_exits_unknown_for_unsized_reduction():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={},
        existing_holdings=[{'code': '000001', 'target_ratio': 25}],
        holdings_review=[{'code': '000001', 'name': '减仓标的', 'action_type': '减仓'}],
    )

    strategy = plan['market_strategy']
    assert strategy['current_position_pct'] == 25
    assert strategy['planned_exit_pct'] == 0
    assert strategy['position_after_exits_pct'] is None


def test_dynamic_position_reports_zero_exit_when_no_exit_is_planned():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={},
        existing_holdings=[{'code': '000001', 'target_ratio': 25}],
        holdings_review=[{'code': '000001', 'name': '持有标的', 'action_type': '持有'}],
    )

    strategy = plan['market_strategy']
    assert strategy['planned_exit_pct'] == 0
    assert strategy['position_after_exits_pct'] == 25


def test_dynamic_position_rejects_invalid_or_impossible_ratios():
    invalid_sets = [
        [{'code': '1', 'target_ratio': -1}],
        [{'code': '1', 'target_ratio': float('nan')}],
        [{'code': '1', 'target_ratio': float('inf')}],
        [{'code': '1', 'target_ratio': 101}],
        [{'code': '1', 'target_ratio': 60}, {'code': '2', 'target_ratio': 50}],
    ]
    for holdings in invalid_sets:
        plan = generate_trading_plan(
            market_cycle={'position': '波中', 'market_regime': 'neutral'},
            mainline_data={'lines': []}, signals_data={}, existing_holdings=holdings,
        )
        strategy = plan['market_strategy']
        assert strategy['current_position_pct'] is None
        assert strategy['planned_exit_pct'] is None
        assert strategy['position_after_exits_pct'] is None


def test_unknown_market_never_marks_focus_buy_as_executable():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'unknown'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '主线买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '明确反转买点',
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'candidate'
    assert item['market_compatible'] is False
    assert '市场强弱尚未确认' in item['attention_reason']


def test_weak_market_does_not_treat_bearish_reversal_or_demand_exhaustion_as_buy_compatible():
    plan = generate_trading_plan(
        market_cycle={'position': '偏波谷', 'market_regime': 'weak', 'vl_score': 4},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '主线买点', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '信号确认',
            'triggered_signals': [
                {'name': '向下反转', 'direction': 'bearish', 'confidence': 80},
                {'name': '需求衰竭', 'direction': 'bearish', 'confidence': 75},
            ],
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'candidate'
    assert item['market_compatible'] is False
    assert '无法将当前信号确认为3L四类买点' in item['attention_reason']


def test_strong_market_executes_breakout_but_not_reversal_buy_point():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000001', 'name': '突破标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '突破买点', 'structure': '上涨趋势', 'stage': '上行',
                'stop_loss': 9.5,
            },
            {
                'code': '000002', 'name': '反转标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '明确反转买点', 'structure': '下降趋势', 'stage': '转强',
            },
        ],
        opportunity_map={'主线方向': '趋势延续'},
    )

    items = {item['code']: item for item in plan['buy_priority']}
    assert items['000001']['decision_status'] == 'executable'
    assert items['000001']['buy_point_category'] == 'breakout'
    assert items['000002']['decision_status'] == 'candidate'
    assert '强势市场不执行反转买点' in items['000002']['attention_reason']


def test_strong_market_does_not_turn_downtrend_breakout_signal_into_execution():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '下降突破信号', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '信号确认', 'structure': '下降趋势', 'stage': '下行',
            'triggered_signals': [{
                'key': 'upward_breakout', 'name': '向上突破',
                'direction': 'bullish', 'confidence': 80,
            }],
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'candidate'
    assert '上涨趋势或区间顶部' in item['attention_reason']


def test_strong_market_treats_real_trend_bias_buy_as_continuation():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '趋势标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 5, 'action_type': '买入',
            'buy_point': 'BIAS5乖离率买入', 'trading_system': 'trend',
            'trend_stock': True, 'structure': '上涨趋势', 'stage': '沿EMA5趋势',
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['buy_point_category'] == 'continuation'
    assert item['decision_status'] == 'executable'


def test_neutral_market_only_executes_buy_points_at_range_edges():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[
            {
                'code': '000001', 'name': '区底标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '中继买点', 'structure': '区间震荡', 'stage': '区间底部',
                'stop_loss': 9.5,
            },
            {
                'code': '000002', 'name': '区中标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '中继买点', 'structure': '区间震荡', 'stage': '区间中段',
                'stop_loss': 9.5,
            },
        ],
        opportunity_map={'主线方向': '趋势延续'},
    )

    items = {item['code']: item for item in plan['buy_priority']}
    assert items['000001']['decision_status'] == 'executable'
    assert items['000002']['decision_status'] == 'candidate'
    assert '只在区间底部成立' in items['000002']['attention_reason']


def test_neutral_market_accepts_display_stage_for_confirmed_range_breakout():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'neutral'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '突破标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '突破买点', 'structure': '区间震荡', 'stage': '突破位',
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    assert plan['buy_priority'][0]['decision_status'] == 'executable'


def test_market_strategy_and_execution_share_the_same_buy_point_policy():
    plan = generate_trading_plan(
        market_cycle={'position': '偏波谷', 'market_regime': 'weak', 'vl_score': 4},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '恐慌标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '信号确认', 'structure': '下降趋势', 'stage': '恐慌',
            'triggered_signals': [{
                'key': 'supply_exhaustion', 'name': '供应衰竭',
                'direction': 'bullish', 'confidence': 80,
            }],
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'executable'
    assert item['buy_point_category'] == 'panic'
    assert '恐慌买点' in plan['market_strategy']['allowed_buy_points']
    assert '供应衰竭买点' in plan['market_strategy']['allowed_buy_points']


def test_executable_breakout_is_upgraded_to_a_complete_condition_plan():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '突破标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '突破买点', 'structure': '上涨趋势', 'stage': '上行',
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'executable'
    assert '放量有效突破关键压力位' in item['trigger_condition']
    assert item['action_when_triggered'] == '按计划买入'
    assert '突破后快速跌回关键位' in item['invalidation_condition']
    assert item['stop_condition'] == '盘中有效跌破 9.50 时止损'
    assert item['valid_for'] == '下一交易日'
    assert item['plan_readiness'] == 'ready'


def test_condition_plan_never_invents_a_missing_stop_price():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '中继标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '中继买点', 'structure': '上涨趋势', 'stage': '上行',
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'candidate'
    assert item['action_type'] == '观察'
    assert item['plan_readiness'] == 'needs_stop'
    assert '止损位尚未设定' in item['stop_condition']
    assert '未补充前不执行买入' in item['stop_condition']


def test_condition_plan_rejects_invalid_stop_prices():
    for invalid_stop in (0, -1, float('nan'), float('inf'), True, 'not-a-price'):
        plan = generate_trading_plan(
            market_cycle={'position': '波中', 'market_regime': 'strong'},
            mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
            buy_signals_review=[{
                'code': '000001', 'name': '中继标的', 'industry': '主线方向',
                'mainline_level': '主线', 'score': 4, 'action_type': '买入',
                'buy_point': '中继买点', 'structure': '上涨趋势', 'stage': '上行',
                'stop_loss': invalid_stop,
            }],
            opportunity_map={'主线方向': '趋势延续'},
        )
        item = plan['buy_priority'][0]
        assert item['stop_loss'] is None
        assert item['plan_readiness'] == 'needs_stop'
        assert item['decision_status'] == 'candidate'


def test_candidate_condition_does_not_upgrade_to_buy_action():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'weak'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        buy_signals_review=[{
            'code': '000001', 'name': '突破标的', 'industry': '主线方向',
            'mainline_level': '主线', 'score': 4, 'action_type': '买入',
            'buy_point': '突破买点', 'structure': '上涨趋势', 'stage': '上行',
            'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['buy_priority'][0]
    assert item['decision_status'] == 'candidate'
    assert item['action_type'] == '观察'
    assert item['action_when_triggered'].startswith('重新评估')


def test_holding_action_has_continue_and_exit_conditions():
    plan = generate_trading_plan(
        market_cycle={'position': '波中', 'market_regime': 'strong'},
        mainline_data={'lines': []}, signals_data={}, existing_holdings=[],
        holdings_review=[{
            'code': '000001', 'name': '持仓标的', 'industry': '主线方向',
            'action_type': '持有', 'signal': 'hold', 'structure': '上涨趋势',
            'stage': '上行', 'stop_loss': 9.5,
        }],
        opportunity_map={'主线方向': '趋势延续'},
    )

    item = plan['holdings_action'][0]
    assert '趋势结构与关键支撑保持有效' in item['trigger_condition']
    assert item['action_when_triggered'] == '继续持有'
    assert '出现明确卖出信号' in item['invalidation_condition']
    assert item['stop_condition'] == '盘中有效跌破 9.50 时止损'


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
    assert result['algorithm_version'] == 'supply_demand_v3'
    assert 'evidence' in result


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


def test_non_executable_actions_are_synchronized_to_buy_signal_cards():
    signals = [
        {'code': '000001', 'action_type': '买入'},
        {'code': '000002', 'action_type': '买入'},
    ]
    plan = {
        'buy_priority': [
            {
                'code': '000001', 'action_type': '买入',
                'decision_status': 'candidate', 'attention_tier': 'watch',
                'attention_reason': '等待市场条件确认',
            },
            {
                'code': '000002', 'action_type': '买入',
                'decision_status': 'signal_only', 'attention_tier': 'ordinary',
                'attention_reason': '非主线且动量靠后',
            },
        ],
    }

    apply_trading_plan_actions(signals, plan)

    assert signals[0]['action_type'] == '观察'
    assert signals[0]['action_reason'] == '等待市场条件确认'
    assert signals[1]['action_type'] == '技术信号'
    assert signals[1]['action_reason'] == '非主线且动量靠后'


def test_executable_market_match_is_synchronized_to_buy_signal_card():
    signals = [{'code': '000001', 'action_type': '买入', 'action_reason': '个股买点成立'}]
    plan = {
        'buy_priority': [{
            'code': '000001', 'action_type': '买入',
            'decision_status': 'executable', 'attention_tier': 'focus',
            'buy_point_category': 'breakout', 'buy_point_category_label': '突破买点',
            'market_compatible': True,
            'market_compatibility_reason': '强势市场与突破买点匹配',
        }],
    }

    apply_trading_plan_actions(signals, plan)

    assert signals[0]['action_type'] == '买入'
    assert signals[0]['buy_point_category'] == 'breakout'
    assert signals[0]['market_compatible'] is True
    assert signals[0]['action_reason'] == '个股买点成立；强势市场与突破买点匹配'
