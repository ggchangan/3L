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
    assert result['trading_wave']['label'] == '上涨波段'
    assert result['trading_state'] == '上涨趋势中的上涨推动波'
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
    assert result['trading_wave']['label'] == '上涨波段'
    assert result['trading_state'] == '下降趋势中的反弹波'
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
    assert result['trading_state'] in ('区间震荡中的上行波段', '区间震荡中的下行波段', '区间震荡')


def test_wave_structure_exposes_down_wave_inside_uptrend_pullback():
    rows = []
    price = 100.0
    # 明确主升波。
    for idx in range(1, 23):
        price += 1.5
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.6, price))
    # 回撤已经构成当前下降波段，但相对前一主升波仍不足以反转主结构。
    for idx in range(23, 29):
        price -= 1.4
        rows.append(_row(_date(idx), price + 0.3, price + 0.7, price - 0.8, price))

    result = judge_wave_structure(rows, asset_type='market')

    assert result['structure'] == '上涨趋势'
    assert result['phase'] == 'pullback'
    assert result['active_wave']['direction'] == 'down'
    assert result['trading_wave']['label'] == '下降波段'
    assert result['trading_state'] == '上涨趋势中的下降波段/回调'


def test_wave_structure_uses_candidate_down_wave_before_confirmed_pivot_changes_structure():
    rows = []
    price = 100.0
    # 先形成一段主升。日内振幅偏大，使 confirmed pivot 阈值较保守。
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))
    # 高位回撤：交易上已经是下降波段，但还不必要求主结构立即翻空。
    price -= 12.0
    rows.append(_row(_date(25), price + 1.0, price + 3.0, price - 2.0, price))

    result = judge_wave_structure(rows, asset_type='stock')

    assert result['structure'] == '上涨趋势'
    assert result['active_wave']['direction'] == 'up'
    assert result['trading_wave']['direction'] == 'down'
    assert result['trading_wave']['source'] == 'candidate_counter_wave'
    assert result['trading_state'] == '上涨趋势中的下降波段/回调'


def test_wave_structure_does_not_flip_trading_wave_on_intraday_dip_that_closes_back():
    rows = []
    price = 100.0
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))

    # 盘中深踩超过 candidate 阈值，但收盘基本收回；交易波段不应仅因影线翻成下降。
    rows.append(_row(_date(25), price - 1.0, price + 2.0, price - 18.0, price - 2.0))

    result = judge_wave_structure(rows, asset_type='stock')

    assert result['structure'] == '上涨趋势'
    assert result['trading_wave']['direction'] == 'up'
    assert result['trading_wave']['source'] == 'confirmed_active_wave'
    assert result['trading_state'] == '上涨趋势中的上涨推动波'
