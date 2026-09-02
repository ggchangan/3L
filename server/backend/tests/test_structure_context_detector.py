from backend.core.structure_context_detector import detect_3l_structure_context


def _row(date, open_, high, low, close, volume=100000):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _trend_rows(direction='up', count=40):
    rows = []
    close = 100.0 if direction == 'up' else 160.0
    for idx in range(count):
        close += 1.2 if direction == 'up' else -1.2
        rows.append(_row(
            f'202607{idx + 1:02d}',
            close - 0.5 if direction == 'up' else close + 0.5,
            close + 1.0,
            close - 1.0,
            close,
            100000 + idx * 1000,
        ))
    return rows


def test_structure_context_keeps_sidecar_boundary_for_uptrend():
    result = detect_3l_structure_context(
        _trend_rows('up'),
        asset_type='stock',
        wave_structure_result={
            'status': 'ok',
            'date': '20260740',
            'structure': '上涨趋势',
            'phase': 'impulse',
            'active_wave': {
                'direction': 'up',
                'start_idx': 0,
                'start_date': '20260701',
                'start_price': 100,
                'extreme_idx': 39,
                'extreme_date': '20260740',
                'extreme_price': 148,
                'change_pct': 48,
                'counter_move_pct': 0,
                'confirmed': True,
            },
            'trading_wave': {'direction': 'up', 'label': '上涨波段', 'confirmed': True},
            'trading_state': '上涨趋势中的上涨推动波',
            'thresholds': {'min_impulse_pct': 6, 'reversal_pct': 5},
            'pivots': [
                {'idx': 0, 'date': '20260701', 'type': 'low', 'price': 100},
                {'idx': 15, 'date': '20260716', 'type': 'high', 'price': 120},
                {'idx': 20, 'date': '20260721', 'type': 'low', 'price': 112},
                {'idx': 39, 'date': '20260740', 'type': 'high', 'price': 148},
            ],
            'reason': 'fixture uptrend',
        },
        supply_demand_events_result={'status': 'ok', 'events': [], 'is_trade_decision': False},
    )

    assert result['status'] == 'ok'
    assert result['market_structure']['structure'] == '上涨趋势'
    assert result['market_structure']['supply_demand_regime'] == 'demand_dominant'
    assert result['wave_position']['position'] in ('rising_middle', 'peak_left')
    assert result['major_decline_risk']['level'] in ('none', 'watch')
    assert result['is_trade_decision'] is False


def test_structure_context_marks_downtrend_development_as_high_decline_risk():
    result = detect_3l_structure_context(
        _trend_rows('down'),
        asset_type='stock',
        wave_structure_result={
            'status': 'ok',
            'date': '20260740',
            'structure': '下降趋势',
            'phase': 'impulse',
            'active_wave': {
                'direction': 'down',
                'start_idx': 0,
                'start_date': '20260701',
                'start_price': 160,
                'extreme_idx': 39,
                'extreme_date': '20260740',
                'extreme_price': 112,
                'change_pct': -30,
                'counter_move_pct': 0,
                'confirmed': True,
            },
            'trading_wave': {'direction': 'down', 'label': '下降波段', 'confirmed': True},
            'trading_state': '下降趋势中的下降推动波',
            'thresholds': {'min_impulse_pct': 6, 'reversal_pct': 5},
            'pivots': [
                {'idx': 0, 'date': '20260701', 'type': 'high', 'price': 160},
                {'idx': 15, 'date': '20260716', 'type': 'low', 'price': 138},
                {'idx': 20, 'date': '20260721', 'type': 'high', 'price': 145},
                {'idx': 39, 'date': '20260740', 'type': 'low', 'price': 112},
            ],
            'reason': 'fixture downtrend',
        },
        supply_demand_events_result={'status': 'ok', 'events': [], 'is_trade_decision': False},
    )

    assert result['market_structure']['structure'] == '下降趋势'
    assert result['market_structure']['stage'] == '发展'
    assert result['wave_position']['position'] == 'falling_middle'
    assert result['major_decline_risk']['level'] == 'high'


def test_panic_exhaustion_overrides_mechanical_high_decline_risk():
    result = detect_3l_structure_context(
        _trend_rows('down'),
        asset_type='stock',
        wave_structure_result={
            'status': 'ok',
            'date': '20260740',
            'structure': '下降趋势',
            'phase': 'impulse',
            'active_wave': {'direction': 'down', 'change_pct': -25, 'confirmed': True},
            'trading_wave': {'direction': 'down', 'label': '下降波段', 'confirmed': True},
            'trading_state': '下降趋势中的下降推动波',
            'thresholds': {'min_impulse_pct': 6, 'reversal_pct': 5},
            'pivots': [],
            'reason': 'fixture panic',
        },
        supply_demand_events_result={
            'status': 'ok',
            'is_trade_decision': False,
            'events': [{
                'event_type': 'exhaustion',
                'subtype': 'panic_stagnation',
                'direction': 'bullish',
                'dominant_force': 'supply_exhaustion',
                'is_trade_decision': False,
            }],
        },
    )

    assert result['market_structure']['stage'] == '恐慌/供应衰竭'
    assert result['wave_position']['position'] == 'valley_left'
    assert result['major_decline_risk']['level'] == 'none'
    assert '不能机械继续判为主跌' in result['major_decline_risk']['reason']


def test_range_top_uses_position_context_as_stage():
    rows = []
    for idx in range(24):
        close = 100 + idx * 0.5
        rows.append(_row(f'202608{idx + 1:02d}', close - 0.5, close + 2, close - 2, close))

    result = detect_3l_structure_context(
        rows,
        asset_type='stock',
        wave_structure_result={
            'status': 'ok',
            'date': rows[-1]['date'],
            'structure': '区间震荡',
            'phase': 'range',
            'active_wave': {'direction': 'up', 'change_pct': 8, 'confirmed': False},
            'trading_wave': {'direction': 'up', 'label': '上涨波段', 'confirmed': False},
            'trading_state': '区间震荡中的上行波段',
            'thresholds': {'min_impulse_pct': 6, 'reversal_pct': 5},
            'pivots': [],
            'reason': 'fixture range',
        },
        supply_demand_events_result={'status': 'ok', 'events': [], 'is_trade_decision': False},
    )

    assert result['market_structure']['structure'] == '区间震荡'
    assert result['market_structure']['stage'] in ('区间顶部', '区间中段', '区间底部')
    assert result['position_context']['zone_type'] in ('near_resistance', 'mid_range', 'near_support')
    assert result['is_trade_decision'] is False


def test_range_support_breakdown_is_not_labeled_as_peak_confirmation():
    rows = []
    for idx in range(24):
        rows.append(_row(f'202608{idx + 1:02d}', 100, 110, 90, 92))

    result = detect_3l_structure_context(
        rows,
        asset_type='stock',
        wave_structure_result={
            'status': 'ok',
            'date': rows[-1]['date'],
            'structure': '区间震荡',
            'phase': 'range',
            'active_wave': {'direction': 'down', 'change_pct': -8, 'confirmed': False},
            'trading_wave': {'direction': 'down', 'label': '下降波段', 'confirmed': False},
            'trading_state': '区间震荡中的下行波段',
            'thresholds': {'min_impulse_pct': 6, 'reversal_pct': 5},
            'pivots': [],
            'reason': 'fixture range support',
        },
        supply_demand_events_result={
            'status': 'ok',
            'is_trade_decision': False,
            'events': [{
                'event_type': 'breakout',
                'subtype': 'downward_breakdown',
                'direction': 'bearish',
                'dominant_force': 'supply',
                'is_trade_decision': False,
            }],
        },
    )

    assert result['market_structure']['stage'] == '区间底部'
    assert result['position_context']['zone_type'] == 'near_support'
    assert result['wave_position']['position'] == 'falling_middle'
    assert result['wave_position']['label'] == '区间底部跌破风险'
    assert result['major_decline_risk']['level'] == 'watch'


def test_unavailable_when_not_enough_bars():
    result = detect_3l_structure_context([_row('20260701', 1, 1, 1, 1)], asset_type='stock')

    assert result['status'] == 'unavailable'
    assert result['is_trade_decision'] is False
