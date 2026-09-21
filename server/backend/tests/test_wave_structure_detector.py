import json
from pathlib import Path

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


def _recipe_fall_then_strong_rise():
    rows = []
    price = 100.0
    for idx in range(1, 16):
        price -= 1.0
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.8, price))
    for idx in range(16, 24):
        price += 2.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.7, price))
    return rows


def _recipe_rise_then_downtrend_bounce():
    rows = []
    price = 120.0
    for idx in range(1, 18):
        price += 1.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.8, price - 0.8, price))
    for idx in range(18, 31):
        price -= 2.2
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.9, price))
    for idx in range(31, 34):
        price += 1.2
        rows.append(_row(_date(idx), price - 0.3, price + 0.8, price - 0.5, price))
    return rows


def _recipe_range_oscillation():
    rows = []
    price = 100.0
    for idx in range(1, 30):
        price += 0.5 if idx % 2 else -0.45
        rows.append(_row(_date(idx), price - 0.3, price + 0.6, price - 0.6, price))
    return rows


def _recipe_uptrend_pullback():
    rows = []
    price = 100.0
    for idx in range(1, 23):
        price += 1.5
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.6, price))
    for idx in range(23, 29):
        price -= 1.4
        rows.append(_row(_date(idx), price + 0.3, price + 0.7, price - 0.8, price))
    return rows


def _recipe_stock_candidate_counter_wave():
    rows = []
    price = 100.0
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))
    price -= 12.0
    rows.append(_row(_date(25), price + 1.0, price + 3.0, price - 2.0, price))
    return rows


def _recipe_stock_intraday_dip_close_back():
    rows = []
    price = 100.0
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))
    rows.append(_row(_date(25), price - 1.0, price + 2.0, price - 18.0, price - 2.0))
    return rows


RECIPES = {
    'fall_then_strong_rise': _recipe_fall_then_strong_rise,
    'rise_then_downtrend_bounce': _recipe_rise_then_downtrend_bounce,
    'range_oscillation': _recipe_range_oscillation,
    'uptrend_pullback': _recipe_uptrend_pullback,
    'stock_candidate_counter_wave': _recipe_stock_candidate_counter_wave,
    'stock_intraday_dip_close_back': _recipe_stock_intraday_dip_close_back,
}


def _source_fixture_rows(sample):
    source_fixture = sample.get('source_fixture')
    source_sample = sample.get('source_sample')
    if not source_fixture or not source_sample:
        return None
    fixture_files = {
        'pure-keypoint-benchmark-v1': 'pure_keypoint_benchmark_v1.json',
        'pure-keypoint-benchmark-v2': 'pure_keypoint_benchmark_v2.json',
    }
    fixture_path = Path(__file__).parent / 'fixtures' / fixture_files[source_fixture]
    fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
    source = next(item for item in fixture['samples'] if item['name'] == source_sample)
    return source['rows']


def _sample_rows(sample):
    if sample.get('recipe'):
        return RECIPES[sample['recipe']]()
    rows = _source_fixture_rows(sample)
    if rows is None:
        raise AssertionError(f"无法解析 benchmark 样本数据: {sample.get('name')}")
    return rows


def _assert_expected_wave_result(result, expected, sample_name):
    if 'structure' in expected:
        assert result['structure'] == expected['structure'], sample_name
    if 'phase' in expected:
        assert result['phase'] == expected['phase'], sample_name
    if 'phase_in' in expected:
        assert result['phase'] in expected['phase_in'], sample_name
    if 'trading_state' in expected:
        assert result['trading_state'] == expected['trading_state'], sample_name
    if 'trading_state_in' in expected:
        assert result['trading_state'] in expected['trading_state_in'], sample_name

    trading_wave = result.get('trading_wave') or {}
    if 'trading_wave_direction' in expected:
        assert trading_wave.get('direction') == expected['trading_wave_direction'], sample_name
    if 'trading_wave_label' in expected:
        assert trading_wave.get('label') == expected['trading_wave_label'], sample_name
    if 'trading_wave_source' in expected:
        assert trading_wave.get('source') == expected['trading_wave_source'], sample_name

    active_wave = result.get('active_wave') or {}
    if 'active_wave_direction' in expected:
        assert active_wave.get('direction') == expected['active_wave_direction'], sample_name

    previous_wave = result.get('previous_wave') or {}
    if 'previous_wave_direction' in expected:
        assert previous_wave.get('direction') == expected['previous_wave_direction'], sample_name


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


def test_user_confirmed_wave_structure_benchmarks():
    fixture_paths = sorted((Path(__file__).parent / 'fixtures').glob('wave_structure_benchmark_v*.json'))
    assert [path.name for path in fixture_paths] == [
        'wave_structure_benchmark_v1.json',
        'wave_structure_benchmark_v2.json',
    ]

    sample_count = 0
    for fixture_path in fixture_paths:
        fixture = json.loads(fixture_path.read_text(encoding='utf-8'))
        assert fixture['algorithm_version'] == 'wave-structure-v1'
        assert fixture['samples']

        for sample in fixture['samples']:
            rows = _sample_rows(sample)
            result = judge_wave_structure(rows, asset_type=sample['asset_type'])
            _assert_expected_wave_result(result, sample['expected'], sample['name'])
            assert result['version'] == fixture['algorithm_version']
            assert result['status'] == 'ok'
            sample_count += 1

    assert sample_count == 21
