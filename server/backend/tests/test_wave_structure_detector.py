from backend.core.wave_structure_detector import judge_wave_structure


def _row(date, open_, high, low, close, volume=100000):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _date(day):
    return f'202606{day:02d}' if day <= 30 else f'202607{day - 30:02d}'


def test_wave_structure_detects_rising_wave_before_ema_confirmation_style_lag():
    rows = []
    price = 100.0
    # 先下跌，形成低点背景
    for idx in range(1, 16):
        price -= 1.0
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.8, price))
    # 之后强力上行。到第 23 根时，已经从低点反弹超过 market 阈值。
    for idx in range(16, 24):
        price += 2.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.7, price))

    result = judge_wave_structure(rows, asset_type='market')

    assert result['structure'] == '上涨趋势'
    assert result['active_wave']['direction'] == 'up'
    assert result['active_wave']['change_pct'] >= result['thresholds']['min_impulse_pct']
    assert result['phase'] in ('impulse', 'pullback')


def test_wave_structure_keeps_downtrend_during_countertrend_bounce():
    rows = []
    price = 120.0
    # 先上涨形成高点
    for idx in range(1, 18):
        price += 1.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.8, price - 0.8, price))
    # 大波段下跌
    for idx in range(18, 31):
        price -= 2.2
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.9, price))
    # 反弹扰动，但不应该破坏主导下降波段
    for idx in range(31, 34):
        price += 1.2
        rows.append(_row(_date(idx), price - 0.3, price + 0.8, price - 0.5, price))

    result = judge_wave_structure(rows, asset_type='market')

    assert result['structure'] == '下降趋势'
    assert result['phase'] == 'countertrend_bounce'
    assert result['active_wave']['direction'] == 'up'
    assert result['previous_wave']['direction'] == 'down'


def test_wave_structure_returns_range_when_no_dominant_wave():
    rows = []
    price = 100.0
    for idx in range(1, 30):
        price += 0.5 if idx % 2 else -0.45
        rows.append(_row(_date(idx), price - 0.3, price + 0.6, price - 0.6, price))

    result = judge_wave_structure(rows, asset_type='market')

    assert result['structure'] == '区间震荡'
    assert result['phase'] == 'range'
