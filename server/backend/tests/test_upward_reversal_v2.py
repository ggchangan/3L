from copy import deepcopy

from backend.core.signal_detector.upward_reversal_detector import detect_upward_reversal


def _decline_then_reversal():
    rows = []
    price = 410.0
    for day in range(1, 31):
        close = price - 4.2
        rows.append({
            'date': f'202607{day:02d}', 'open': price, 'high': price + 2,
            'low': close - 3, 'close': close, 'volume': 90_000 + (day % 4) * 5_000,
        })
        price = close
    for row in rows[-7:-2]:
        row['volume'] = 90_000
    for row in rows[:-7]:
        row['volume'] = 130_000
    rows[-2].update({'open': 283.0, 'high': 288.0, 'low': 256.2, 'close': 261.0, 'volume': 121_269})
    rows[-1].update({'open': 287.98, 'high': 312.94, 'low': 287.98, 'close': 303.65, 'volume': 150_735})
    return rows


def test_strong_demand_reversal_can_use_five_day_volume_context():
    result = detect_upward_reversal(_decline_then_reversal())

    assert result['triggered'] is True
    assert result['confidence'] >= 60
    assert result['scores']['volume_ratio_5'] >= 1.3
    assert result['scores']['volume_rule'] in ('5日放量长阳', '强需求长阳且量增')
    assert '20日/5日量比' in result['detail']


def test_large_gain_without_decline_is_not_reversal():
    rows = _decline_then_reversal()
    for i, row in enumerate(rows[:-1]):
        row.update(open=100 + i * .2, high=102 + i * .2, low=99 + i * .2, close=101 + i * .2)
    rows[-1].update(open=108, high=120, low=107, close=119)

    result = detect_upward_reversal(rows)

    assert result['triggered'] is False
    assert '下降背景不足' in result['detail']


def test_close_low_or_weak_demand_does_not_trigger():
    close_low = _decline_then_reversal()
    close_low[-1].update(open=287, high=313, low=280, close=288)
    weak_demand = _decline_then_reversal()
    weak_demand[-1].update(open=288, high=304, low=286, close=293, volume=95_000)

    assert detect_upward_reversal(close_low)['triggered'] is False
    assert detect_upward_reversal(weak_demand)['triggered'] is False


def test_historical_result_is_unchanged_by_future_klines():
    rows = _decline_then_reversal()
    before = detect_upward_reversal(rows, len(rows) - 1)
    extended = deepcopy(rows) + [
        {'date': '20260801', 'open': 300, 'high': 301, 'low': 250, 'close': 255, 'volume': 300_000}
    ]
    after = detect_upward_reversal(extended, len(rows) - 1)

    assert after == before


def test_old_drawdown_followed_by_long_recovery_is_not_a_new_reversal():
    rows = _decline_then_reversal()
    # 低点发生在20日窗口早段，此后已经连续恢复，末日只是普通放量上涨。
    base = 250.0
    for offset, row in enumerate(rows[-20:]):
        close = base + offset * 5
        row.update(open=close - 1, high=close + 2, low=close - 3, close=close, volume=100_000)
    rows[-20].update(open=285, high=288, low=245, close=250, volume=180_000)
    rows[-1].update(open=342, high=354, low=340, close=352, volume=160_000)

    result = detect_upward_reversal(rows)

    assert result['triggered'] is False
    assert '非下降末端' in result['detail']
