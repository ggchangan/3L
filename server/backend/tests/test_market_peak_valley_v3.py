"""3L供需峰谷V3的知识库硬约束测试。"""

from datetime import date, timedelta

from backend.core.market_peak_valley import _combine_peak, _resolve_side, judge_peak_valley_v3


def _bars(closes, volumes=None, shapes=None):
    volumes = volumes or [1_000_000] * len(closes)
    shapes = shapes or {}
    start = date(2025, 1, 1)
    result = []
    for index, close in enumerate(closes):
        previous = closes[index - 1] if index else close
        open_price = shapes.get(index, {}).get('open', previous)
        high = shapes.get(index, {}).get('high', max(open_price, close) * 1.006)
        low = shapes.get(index, {}).get('low', min(open_price, close) * 0.994)
        result.append({
            'date': (start + timedelta(days=index)).isoformat(),
            'open': open_price, 'high': high, 'low': low, 'close': close,
            'volume': volumes[index],
        })
    return result


def _downtrend(length=100, daily_loss=.008):
    closes = [200]
    for _ in range(length - 1):
        closes.append(closes[-1] * (1 - daily_loss))
    return closes


def test_downtrend_shrinking_volume_is_not_a_tradeable_valley():
    closes = _downtrend()
    volumes = [1_500_000 - index * 8_000 for index in range(len(closes))]
    result = judge_peak_valley_v3(_bars(closes, volumes))

    assert result['structure'] == '下降趋势'
    assert result['wave_phase'] in ('left', 'forming')
    assert result['position'] == '波中偏下'
    assert result['wave_phase'] not in ('biased', 'confirmed')
    if result['wave_side'] == 'valley':
        assert result['hard_gates'] == result['valley_gates']
        assert not set(result['peak_gates']) & set(result['hard_gates'])
    assert '下降趋势尚无需求进入' in result['hard_gates']


def test_extreme_negative_bias_never_skips_supply_demand_confirmation():
    closes = _downtrend(daily_loss=.012)
    result = judge_peak_valley_v3(_bars(closes))

    assert result['features']['bias20'] < -8
    assert result['wave_phase'] in ('left', 'forming')
    assert result['vl_score'] <= 2
    assert any('极端负乖离' in gate for gate in result['hard_gates'])


def test_panic_close_at_low_is_supply_release_not_confirmed_valley():
    closes = _downtrend()
    closes[-1] = closes[-2] * .94
    volumes = [1_000_000] * len(closes)
    volumes[-1] = 3_000_000
    last = len(closes) - 1
    shapes = {
        last: {
            'open': closes[-2] * .995,
            'high': closes[-2],
            'low': closes[-1] * .998,
        },
    }
    result = judge_peak_valley_v3(_bars(closes, volumes, shapes))

    assert result['evidence']['panic_release'] >= 60
    assert result['wave_phase'] in ('left', 'forming')
    assert result['wave_phase'] != 'confirmed'


def test_demand_reversal_after_decline_can_upgrade_valley():
    closes = _downtrend(96)
    # 先放缓并停止创新低，最后以放量阳线收复短期高点/MA5。
    closes.extend([
        closes[-1] * .995,
        closes[-1] * .994,
        closes[-1] * 1.004,
        closes[-1] * 1.035,
    ])
    volumes = [1_000_000] * 96 + [650_000, 550_000, 600_000, 1_800_000]
    last = len(closes) - 1
    shapes = {
        last: {
            'open': closes[-2] * .995,
            'high': closes[-1] * 1.005,
            'low': closes[-2] * .99,
        },
    }
    result = judge_peak_valley_v3(_bars(closes, volumes, shapes))

    assert result['evidence']['demand_entry'] >= 50
    assert result['wave_phase'] in ('biased', 'confirmed')
    assert result['position'] == '偏波谷'


def test_result_is_independent_of_input_order():
    bars = _bars(_downtrend())
    assert judge_peak_valley_v3(bars) == judge_peak_valley_v3(list(reversed(bars)))


def test_insufficient_data_is_explicit():
    result = judge_peak_valley_v3(_bars(_downtrend(40)))
    assert result['wave_label'] == '数据不足'
    assert result['structure'] == '待确认'


def test_peak_requires_bearish_follow_through_and_can_confirm():
    context = {'high_location': 70, 'advance_context': 70, 'resistance_context': 70}
    evidence = {
        'buying_climax': 20, 'demand_exhaustion': 65,
        'distribution': 60, 'supply_entry': 60,
    }
    features = {'bias20': 3, 'break_ma5': False, 'bearish_follow_through_count': 0}

    phase, _ = _combine_peak('上涨趋势', context, evidence, features)
    assert phase == 'forming'

    evidence['supply_entry'] = 80
    features.update({'break_ma5': True, 'bearish_follow_through_count': 2})
    phase, _ = _combine_peak('上涨趋势', context, evidence, features)
    assert phase == 'confirmed'


def test_competing_states_resolve_to_stronger_evidence():
    side, phase = _resolve_side(
        'biased', 'biased',
        {'low_location': 80, 'high_location': 30},
        {'absorption': 70, 'demand_entry': 80, 'distribution': 20, 'supply_entry': 20},
    )
    assert (side, phase) == ('valley', 'biased')
