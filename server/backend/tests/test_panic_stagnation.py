from copy import deepcopy

from backend.core.signal_detector.panic_stagnation import detect_panic_stagnation


def _slow_decline_with_panic():
    rows = []
    price = 125.0
    for day in range(1, 31):
        close = price - 0.8
        rows.append({
            'date': f'202607{day:02d}', 'open': price, 'high': price + 0.5,
            'low': close - 0.5, 'close': close, 'volume': 100_000,
        })
        price = close
    prev_close = rows[-2]['close']
    rows[-1].update({
        'open': prev_close - 1.0, 'high': prev_close + 0.5,
        'low': prev_close * 0.94, 'close': prev_close - 0.8,
        'volume': 220_000,
    })
    return rows


def test_panic_buy_is_huge_volume_stagnation_at_decline_end():
    result = detect_panic_stagnation(_slow_decline_with_panic())

    assert result['triggered'] is True
    assert result['signal_key'] == 'panic_stagnation'
    assert result['scores']['volume_ratio_20'] >= 1.6
    assert result['scores']['close_position'] >= 0.5
    assert '天量' in result['detail']
    assert '滞跌' in result['detail']


def test_large_drop_without_huge_volume_is_not_panic_buy():
    rows = _slow_decline_with_panic()
    rows[-1]['volume'] = 120_000

    result = detect_panic_stagnation(rows)

    assert result['triggered'] is False
    assert '未达到天量' in result['detail']


def test_huge_volume_close_at_low_is_not_stagnation():
    rows = _slow_decline_with_panic()
    rows[-1].update(open=rows[-2]['close'], high=rows[-2]['close'],
                    low=rows[-2]['close'] * 0.93, close=rows[-2]['close'] * 0.931)

    result = detect_panic_stagnation(rows)

    assert result['triggered'] is False
    assert '未滞跌' in result['detail']


def test_high_level_huge_volume_long_bearish_candle_is_not_panic():
    rows = _slow_decline_with_panic()
    for i, row in enumerate(rows[:-1]):
        close = 100 + i
        row.update(open=close - 0.5, high=close + 1, low=close - 1, close=close)
    rows[-1].update(open=130, high=131, low=123, close=124, volume=250_000)

    result = detect_panic_stagnation(rows)

    assert result['triggered'] is False
    assert '不在下降末端' in result['detail']


def test_panic_detection_has_no_future_function():
    rows = _slow_decline_with_panic()
    before = detect_panic_stagnation(rows, len(rows) - 1)
    extended = deepcopy(rows) + [{
        'date': '20260801', 'open': 100, 'high': 110, 'low': 99,
        'close': 109, 'volume': 300_000,
    }]

    assert detect_panic_stagnation(extended, len(rows) - 1) == before
