from backend.core.supply_demand_event_detector import detect_supply_demand_events


def _row(date, open_, high, low, close, volume):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _range_top_volume_down_rows():
    return [
        _row('20260720', 100, 104, 99, 103, 120000),
        _row('20260721', 103, 105, 101, 104, 130000),
        _row('20260722', 104, 106, 102, 105, 125000),
        _row('20260723', 105, 108, 103, 107, 150000),
        _row('20260724', 107, 109, 104, 106, 160000),
        _row('20260727', 106, 107, 98, 99, 190000),
        _row('20260728', 99, 101, 94, 96, 175000),
        _row('20260729', 96, 99, 92, 95, 150000),
        _row('20260730', 95, 98, 88.72, 92, 140000),
        _row('20260731', 92, 97, 90, 96, 110000),
        _row('20260803', 96, 101, 95, 100, 130000),
        _row('20260804', 100, 106, 99, 104, 150000),
        _row('20260805', 104, 109, 103, 108, 165000),
        _row('20260806', 108, 112, 106, 110, 170000),
        _row('20260807', 106.87, 113.3, 106.02, 111.68, 131702),
        _row('20260810', 115.13, 115.13, 105.28, 110.27, 161458),
        _row('20260811', 110.84, 118.5, 110.5, 115.49, 193308),
        _row('20260812', 114.36, 118.78, 113.58, 116.02, 106596),
        _row('20260813', 118.37, 122.59, 115.1, 118.7, 156062),
        _row('20260814', 119.0, 123.8, 117.0, 123.0, 198824),
        _row('20260817', 122.45, 123.6, 120.0, 123.24, 148669),
        _row('20260818', 122.22, 122.89, 115.0, 116.92, 227188),
    ]


def test_failed_breakout_becomes_bearish_failure_event_not_trade_decision():
    result = detect_supply_demand_events(
        _range_top_volume_down_rows(),
        asset_type='stock',
        structure='区间震荡',
        stage='区间顶部',
    )

    event = result['events'][0]
    assert event['event_type'] == 'failure'
    assert event['subtype'] == 'failed_breakout'
    assert event['direction'] == 'bearish'
    assert event['dominant_force'] == 'supply'
    assert event['position_context']['zone_type'] == 'near_resistance'
    assert event['trade_implication'] == 'risk_or_sell_context'
    assert event['is_trade_decision'] is False
    assert event['definition_aligned'] is True
    assert result['is_trade_decision'] is False


def test_range_stage_is_normalized_before_event_semantic_check():
    result = detect_supply_demand_events(
        _range_top_volume_down_rows(),
        asset_type='stock',
        structure='区间震荡',
        stage='区间中段',
    )

    event = result['events'][0]
    assert result['structure_context']['stage'] == '区间顶部'
    assert event['structure_context']['stage'] == '区间顶部'
    assert event['position_context']['zone_type'] == 'near_resistance'
    assert event['definition_aligned'] is True
    assert not event['semantic_warnings']


def test_bullish_continuation_keeps_continuation_semantics():
    rows = []
    close = 100.0
    for i in range(35):
        close += 1.0
        rows.append(_row(f'202607{i + 1:02d}', close - 0.5, close + 1, close - 1, close, 100000 + i * 1000))
    rows.extend([
        _row('20260810', 135.0, 136.0, 132.0, 133.0, 85000),
        _row('20260811', 133.0, 134.0, 131.8, 132.6, 65000),
    ])

    result = detect_supply_demand_events(
        rows,
        asset_type='stock',
        structure='上涨趋势',
        stage='缩量整理',
    )

    event = result['events'][0]
    assert event['event_type'] == 'continuation'
    assert event['subtype'] == 'bullish_continuation'
    assert event['dominant_force'] == 'demand'
    assert event['trade_implication'] == 'candidate_continuation_context'
    assert event['meaning'].startswith('回调力量无法改变需求占优格局')
    assert event['definition_aligned'] is True


def test_panic_stagnation_becomes_supply_exhaustion_left_context():
    rows = []
    price = 125.0
    for day in range(1, 31):
        close = price - 0.8
        rows.append(_row(f'202607{day:02d}', price, price + 0.5, close - 0.5, close, 100000))
        price = close
    prev_close = rows[-2]['close']
    rows[-1].update({
        'open': prev_close - 1.0,
        'high': prev_close + 0.5,
        'low': prev_close * 0.94,
        'close': prev_close - 0.8,
        'volume': 260000,
    })

    result = detect_supply_demand_events(
        rows,
        asset_type='stock',
        structure='下降趋势',
        stage='主跌末端',
    )

    event = result['events'][0]
    assert event['event_type'] == 'exhaustion'
    assert event['subtype'] == 'panic_stagnation'
    assert event['direction'] == 'bullish'
    assert event['dominant_force'] == 'supply_exhaustion'
    assert event['trade_implication'] == 'candidate_left_buy_context'
    assert event['volume_price_evidence']['action_type'] == 'panic_stagnation'
    assert event['definition_aligned'] is True


def test_event_exposes_semantic_warning_for_invalid_bullish_continuation_context():
    result = detect_supply_demand_events(
        [],
        supply_demand_result={
            'asset_type': 'stock',
            'status': 'ok',
            'date': '20260828',
            'structure': '下降趋势',
            'stage': '主跌',
            'current_zone': {'type': 'downtrend'},
            'volume_price_action': {'type': 'volume_up'},
            'transition_points': [{
                'idx': 1,
                'date': '20260828',
                'type': 'bullish_continuation',
                'direction': 'bullish',
                'status': 'candidate',
                'confidence': 61,
                'tier': 'watch',
                'evidence': {'volume_price_action': 'volume_up'},
                'reason': '不合规中继样例',
            }],
        },
    )

    event = result['events'][0]
    assert event['definition_aligned'] is False
    assert '看多中继不能出现在下降趋势中' in event['semantic_warnings']


def test_event_warns_when_range_stage_conflicts_with_position_context():
    result = detect_supply_demand_events(
        [],
        supply_demand_result={
            'asset_type': 'stock',
            'status': 'ok',
            'date': '20260828',
            'structure': '区间震荡',
            'stage': '区间中段',
            'current_zone': {'type': 'near_resistance'},
            'volume_price_action': {'type': 'neutral'},
            'transition_points': [{
                'idx': 1,
                'date': '20260828',
                'type': 'failed_breakout',
                'direction': 'bearish',
                'status': 'candidate',
                'confidence': 61,
                'tier': 'watch',
                'evidence': {'volume_price_action': 'neutral'},
                'reason': '阶段位置冲突样例',
            }],
        },
    )

    event = result['events'][0]
    assert event['definition_aligned'] is False
    assert '区间阶段为中段' in event['semantic_warnings'][0]


def test_can_wrap_existing_supply_demand_result_without_klines():
    result = detect_supply_demand_events(
        [],
        supply_demand_result={
            'version': 'supply-demand-keypoint-v1',
            'asset_type': 'market',
            'status': 'ok',
            'date': '20260828',
            'structure': '上涨趋势',
            'stage': '发展',
            'current_zone': {'type': 'trend_pullback', 'reason': '回踩'},
            'wave_context': {'trading_state': '上涨趋势中的下降波段/回调'},
            'transition_points': [{
                'idx': 30,
                'date': '20260828',
                'type': 'bullish_reversal',
                'direction': 'bullish',
                'status': 'candidate',
                'confidence': 70,
                'tier': 'watch',
                'evidence': {'volume_price_action': 'volume_up'},
                'reason': '需求出现',
            }],
        },
    )

    event = result['events'][0]
    assert event['event_type'] == 'reversal'
    assert event['structure_context']['structure'] == '上涨趋势'
    assert event['wave_context']['trading_state'] == '上涨趋势中的下降波段/回调'
    assert event['legacy_point']['reason'] == '需求出现'


def test_unavailable_result_keeps_safe_empty_events():
    result = detect_supply_demand_events(
        [],
        supply_demand_result={
            'status': 'unavailable',
            'reason': '数据不足',
            'transition_points': [],
        },
    )

    assert result['status'] == 'unavailable'
    assert result['events'] == []
    assert result['event_counts']['total'] == 0
    assert result['is_trade_decision'] is False
