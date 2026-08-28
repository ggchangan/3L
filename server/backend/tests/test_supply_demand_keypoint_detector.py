from backend.core.supply_demand_keypoint_detector import detect_supply_demand_keypoints


def _row(date, open_, high, low, close, volume):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _types(result):
    return [p['type'] for p in result['transition_points']]


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


def test_range_top_volume_down_is_failed_breakout_not_bullish_continuation():
    result = detect_supply_demand_keypoints(
        _range_top_volume_down_rows(),
        asset_type='stock',
        structure='区间震荡',
        stage='区间顶部',
    )

    assert result['current_zone']['type'] == 'near_resistance'
    assert result['volume_price_action']['type'] == 'volume_down'
    assert result['volume_price_action']['day_volume_ratio'] == 1.53
    assert _types(result) == ['failed_breakout']
    point = result['transition_points'][0]
    assert point['direction'] == 'bearish'
    assert point['tier'] in ('core', 'watch')
    assert point['display_level'] in ('primary', 'secondary')
    assert point['priority_reasons']
    assert point['is_trade_decision'] is False
    assert 'buy_point' not in point


def test_uptrend_shrink_pullback_can_be_bullish_continuation():
    rows = []
    close = 100.0
    for i in range(35):
        close += 1.0
        rows.append(_row(f'202607{i + 1:02d}', close - 0.5, close + 1, close - 1, close, 100000 + i * 1000))
    rows.extend([
        _row('20260810', 135.0, 136.0, 132.0, 133.0, 85000),
        _row('20260811', 133.0, 134.0, 131.8, 132.6, 65000),
    ])

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='上涨趋势',
        stage='缩量整理',
    )

    assert result['current_zone']['type'] == 'trend_pullback'
    assert result['volume_price_action']['type'] == 'shrink_pullback'
    assert _types(result) == ['bullish_continuation']
    point = result['transition_points'][0]
    assert point['direction'] == 'bullish'
    assert point['tier'] in ('core', 'watch', 'weak')
    assert point['display_level'] in ('primary', 'secondary', 'muted')
    assert point['priority_reasons']
    assert point['is_trade_decision'] is False
    assert 'buy_point' not in point


def test_down_trading_wave_blocks_bullish_continuation_in_uptrend_context():
    rows = []
    close = 100.0
    for i in range(35):
        close += 1.0
        rows.append(_row(f'202607{i + 1:02d}', close - 0.5, close + 1, close - 1, close, 100000 + i * 1000))
    rows.extend([
        _row('20260810', 135.0, 136.0, 132.0, 133.0, 85000),
        _row('20260811', 133.0, 134.0, 131.8, 132.6, 65000),
    ])

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='上涨趋势',
        stage='缩量整理',
        wave_context={
            'structure': '上涨趋势',
            'phase': 'pullback',
            'trading_wave': {'direction': 'down', 'label': '下降波段'},
            'trading_state': '上涨趋势中的下降波段/回调',
        },
    )

    assert result['wave_context']['trading_state'] == '上涨趋势中的下降波段/回调'
    assert 'bullish_continuation' not in _types(result)
    assert result['transition_point_tiers']['total'] == len(result['transition_points'])


def test_downtrend_shrink_is_bearish_continuation_not_buy_signal():
    rows = []
    close = 130.0
    for i in range(28):
        close -= 1.0
        rows.append(_row(f'202607{i + 1:02d}', close + 0.5, close + 1, close - 1, close, 120000))
    rows.extend([
        _row('20260801', 102, 104, 101, 103, 85000),
        _row('20260802', 103, 104, 101.5, 102.8, 70000),
    ])

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='下降趋势',
        stage='缩量反弹',
    )

    assert _types(result) == ['bearish_continuation']
    point = result['transition_points'][0]
    assert point['direction'] == 'bearish'
    assert point['tier'] in ('core', 'watch', 'weak')
    assert point['priority_reasons']
    assert point['is_trade_decision'] is False
    assert 'buy_point' not in point


def test_up_trading_wave_blocks_bearish_continuation_in_downtrend_context():
    rows = []
    close = 130.0
    for i in range(28):
        close -= 1.0
        rows.append(_row(f'202607{i + 1:02d}', close + 0.5, close + 1, close - 1, close, 120000))
    rows.extend([
        _row('20260801', 102, 104, 101, 103, 85000),
        _row('20260802', 103, 104, 101.5, 102.8, 70000),
    ])

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='下降趋势',
        stage='缩量反弹',
        wave_context={
            'structure': '下降趋势',
            'phase': 'countertrend_bounce',
            'trading_wave': {'direction': 'up', 'label': '上涨波段'},
            'trading_state': '下降趋势中的反弹波',
        },
    )

    assert result['wave_context']['trading_state'] == '下降趋势中的反弹波'
    assert 'bearish_continuation' not in _types(result)


def test_panic_keypoint_requires_huge_volume_stagnation():
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

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='下降趋势',
        stage='主跌末端',
    )

    assert _types(result) == ['panic_stagnation']
    assert result['volume_price_action']['type'] == 'panic_stagnation'
    point = result['transition_points'][0]
    assert point['tier'] == 'core'
    assert point['display_level'] == 'primary'
    assert '天量滞跌' in point['reason']


def test_reversal_style_point_treats_opposite_trading_wave_as_turning_evidence():
    rows = _range_top_volume_down_rows()
    rows[-1].update({
        'open': 122.8,
        'high': 123.5,
        'low': 114.8,
        'close': 122.2,
        'volume': 260000,
    })

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='区间震荡',
        stage='区间顶部',
        wave_context={
            'structure': '上涨趋势',
            'phase': 'impulse',
            'trading_wave': {'direction': 'up', 'label': '上涨波段'},
            'trading_state': '上涨趋势中的上涨推动波',
        },
    )

    assert _types(result) == ['failed_breakout']
    point = result['transition_points'][0]
    assert point['direction'] == 'bearish'
    assert '当前交易波段转折/衰竭候选' in point['priority_reasons']


def test_huge_volume_close_at_low_is_not_panic_stagnation():
    rows = []
    price = 125.0
    for day in range(1, 31):
        close = price - 0.8
        rows.append(_row(f'202607{day:02d}', price, price + 0.5, close - 0.5, close, 100000))
        price = close
    prev_close = rows[-2]['close']
    rows[-1].update({
        'open': prev_close - 0.5,
        'high': prev_close,
        'low': prev_close * 0.93,
        'close': prev_close * 0.931,
        'volume': 260000,
    })

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='下降趋势',
        stage='主跌',
    )

    assert 'panic_stagnation' not in _types(result)


def test_uptrend_huge_volume_small_green_without_lower_shadow_is_not_panic():
    rows = []
    close = 100.0
    for i in range(30):
        close += 1.0
        rows.append(_row(f'202607{i + 1:02d}', close - 0.3, close + 0.7, close - 0.8, close, 100000))
    rows[-1].update({
        'open': rows[-2]['close'],
        'high': rows[-2]['close'] + 1.0,
        'low': rows[-2]['close'] - 0.1,
        'close': rows[-2]['close'] + 0.2,
        'volume': 260000,
    })

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='上涨趋势',
        stage='高位震荡',
    )

    assert result['volume_price_action']['type'] != 'panic_stagnation'
    assert 'panic_stagnation' not in _types(result)


def test_range_top_huge_volume_lower_shadow_is_not_panic_buy_context():
    rows = _range_top_volume_down_rows()
    rows[-1].update({
        'open': 122.8,
        'high': 123.5,
        'low': 114.8,
        'close': 122.2,
        'volume': 260000,
    })

    result = detect_supply_demand_keypoints(
        rows,
        asset_type='stock',
        structure='区间震荡',
        stage='区间顶部',
    )

    assert result['current_zone']['type'] == 'near_resistance'
    assert result['volume_price_action']['type'] == 'panic_stagnation'
    assert _types(result) == ['failed_breakout']
    point = result['transition_points'][0]
    assert point['direction'] == 'bearish'
    assert '不能按恐慌低吸解释' in point['reason']
