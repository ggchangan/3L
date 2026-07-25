"""3L 供需证据驱动的峰谷判定 V3。

先识别结构和可解释的供需证据，再通过状态机输出峰谷阶段。
所有特征只使用当前及历史K线，不使用未来数据。
"""

from __future__ import annotations

import math
from statistics import mean
from typing import Dict, List, Optional, Sequence, Tuple


MIN_BARS = 80
PHASE_SCORE = {'none': 0, 'left': 1, 'forming': 2, 'biased': 3, 'confirmed': 4}


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _scale(value: float, low: float, high: float) -> float:
    """把数值在 low~high 之间线性映射到 0~100。"""
    if high <= low:
        return 0.0
    return _clamp((value - low) / (high - low) * 100)


def _avg(values: Sequence[float]) -> float:
    return mean(values) if values else 0.0


def _pct_change(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _ma(values: Sequence[float], period: int) -> float:
    return _avg(values[-period:]) if len(values) >= period else _avg(values)


def _percentile_rank(value: float, values: Sequence[float]) -> float:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return 0.5
    return sum(1 for v in clean if v <= value) / len(clean)


def normalize_market_klines(klines: List[Dict]) -> List[Dict]:
    """按生产判定口径清洗、排序并按交易日去重。"""
    by_date = {}
    for raw in sorted(klines, key=lambda row: str(row.get('date', ''))):
        try:
            bar = {
                'date': str(raw.get('date', '')),
                'open': float(raw.get('open', 0) or 0),
                'high': float(raw.get('high', 0) or 0),
                'low': float(raw.get('low', 0) or 0),
                'close': float(raw.get('close', 0) or 0),
                'volume': float(raw.get('volume', raw.get('vol', 0)) or 0),
            }
        except (TypeError, ValueError):
            continue
        prices = (bar['open'], bar['high'], bar['low'], bar['close'])
        if not all(math.isfinite(v) and v > 0 for v in prices):
            continue
        if bar['high'] < max(bar['open'], bar['close']) or bar['low'] > min(bar['open'], bar['close']):
            continue
        if not math.isfinite(bar['volume']) or bar['volume'] < 0:
            continue
        if not bar['date']:
            continue
        by_date[bar['date']] = bar
    return [by_date[date] for date in sorted(by_date)]


def _true_ranges(bars: List[Dict]) -> List[float]:
    ranges = []
    for index, bar in enumerate(bars):
        previous_close = bars[index - 1]['close'] if index else bar['close']
        ranges.append(max(
            bar['high'] - bar['low'],
            abs(bar['high'] - previous_close),
            abs(bar['low'] - previous_close),
        ))
    return ranges


def _classify_structure(features: Dict) -> str:
    price = features['close']
    ma20 = features['ma20']
    ma60 = features['ma60']
    slope = features['ma20_slope_5d']
    if price >= ma20 >= ma60 and slope >= 0:
        return '上涨趋势'
    if price < ma20 < ma60 and slope <= 0:
        return '下降趋势'
    return '区间震荡'


def _compute_features(bars: List[Dict]) -> Dict:
    closes = [bar['close'] for bar in bars]
    highs = [bar['high'] for bar in bars]
    lows = [bar['low'] for bar in bars]
    volumes = [bar['volume'] for bar in bars]
    true_ranges = _true_ranges(bars)
    current = bars[-1]
    previous = bars[-2]

    atr14 = _avg(true_ranges[-14:]) or current['close'] * 0.01
    atr_pct = atr14 / current['close'] * 100
    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    ma20_5d_ago = _avg(closes[-25:-5]) if len(closes) >= 25 else ma20
    ma20_slope = _pct_change(ma20, ma20_5d_ago)
    volume_base = _avg(volumes[-21:-1])
    volume_ratio = current['volume'] / volume_base if volume_base > 0 else 1.0
    volume_percentile = _percentile_rank(current['volume'], volumes[-120:])
    bar_range = current['high'] - current['low']
    close_location = (current['close'] - current['low']) / bar_range if bar_range > 0 else 0.5
    body_pct = _pct_change(current['close'], current['open'])
    body_atr = (current['close'] - current['open']) / atr14
    range_atr = bar_range / atr14 if atr14 else 1.0
    lower_shadow = min(current['open'], current['close']) - current['low']
    upper_shadow = current['high'] - max(current['open'], current['close'])
    lower_shadow_ratio = lower_shadow / bar_range if bar_range > 0 else 0
    upper_shadow_ratio = upper_shadow / bar_range if bar_range > 0 else 0

    low60, high60 = min(lows[-60:]), max(highs[-60:])
    range_position60 = (
        (current['close'] - low60) / (high60 - low60)
        if high60 > low60 else 0.5
    )
    prior_low20 = min(lows[-21:-1])
    prior_high20 = max(highs[-21:-1])
    new_low_atr = max(0.0, (prior_low20 - current['low']) / atr14)
    new_high_atr = max(0.0, (current['high'] - prior_high20) / atr14)

    return_3d = _pct_change(closes[-1], closes[-4])
    return_5d = _pct_change(closes[-1], closes[-6])
    return_10d = _pct_change(closes[-1], closes[-11])
    return_20d = _pct_change(closes[-1], closes[-21])
    prior_7d_return = _pct_change(closes[-4], closes[-11])
    current_down_speed = max(0.0, -return_3d) / 3
    prior_down_speed = max(0.0, -prior_7d_return) / 7
    current_up_speed = max(0.0, return_3d) / 3
    prior_up_speed = max(0.0, prior_7d_return) / 7

    recent_range_ratio = _avg(true_ranges[-3:]) / (_avg(true_ranges[-13:-3]) or atr14)
    recent_volume_ratio = _avg(volumes[-3:]) / (_avg(volumes[-13:-3]) or volume_base or 1)
    no_new_low_3d = min(lows[-3:]) >= min(lows[-6:-3]) * 0.998
    no_new_high_3d = max(highs[-3:]) <= max(highs[-6:-3]) * 1.002
    lows_rising = lows[-1] >= lows[-2] and lows[-2] >= lows[-3]
    highs_falling = highs[-1] <= highs[-2] and highs[-2] <= highs[-3]
    bullish_follow_through_count = sum((
        return_3d >= atr_pct * .5,
        current['close'] > max(highs[-4:-1]),
        lows_rising,
        current['close'] >= ma5 and previous['close'] < _avg(closes[-6:-1]),
    ))
    bearish_follow_through_count = sum((
        return_3d <= -atr_pct * .5,
        current['close'] < min(lows[-4:-1]),
        highs_falling,
        current['close'] < ma5 and previous['close'] >= _avg(closes[-6:-1]),
    ))

    down_result = max(0.0, -_pct_change(current['close'], previous['close'])) / max(atr_pct, 0.1) + new_low_atr
    up_result = max(0.0, _pct_change(current['close'], previous['close'])) / max(atr_pct, 0.1) + new_high_atr
    effort = max(volume_ratio * max(range_atr, 0.25), 0.1)

    return {
        'date': current['date'], 'close': current['close'],
        'ma5': ma5, 'ma20': ma20, 'ma60': ma60, 'ma20_slope_5d': ma20_slope,
        'atr14': atr14, 'atr_pct': atr_pct,
        'bias20': _pct_change(current['close'], ma20),
        'return_1d': _pct_change(current['close'], previous['close']),
        'return_3d': return_3d, 'return_5d': return_5d,
        'return_10d': return_10d, 'return_20d': return_20d,
        'prior_7d_return': prior_7d_return,
        'current_down_speed': current_down_speed, 'prior_down_speed': prior_down_speed,
        'current_up_speed': current_up_speed, 'prior_up_speed': prior_up_speed,
        'volume_ratio20': volume_ratio, 'volume_percentile120': volume_percentile,
        'range_atr': range_atr, 'close_location': close_location,
        'body_pct': body_pct, 'body_atr': body_atr,
        'lower_shadow_ratio': lower_shadow_ratio, 'upper_shadow_ratio': upper_shadow_ratio,
        'range_position60': range_position60,
        'drawdown20': _pct_change(current['close'], max(highs[-20:])),
        'drawdown60': _pct_change(current['close'], max(highs[-60:])),
        'rise20': _pct_change(current['close'], min(lows[-20:])),
        'rise60': _pct_change(current['close'], min(lows[-60:])),
        'prior_low20': prior_low20, 'prior_high20': prior_high20,
        'new_low_atr': new_low_atr, 'new_high_atr': new_high_atr,
        'recent_range_ratio': recent_range_ratio,
        'recent_volume_ratio': recent_volume_ratio,
        'no_new_low_3d': no_new_low_3d, 'no_new_high_3d': no_new_high_3d,
        'lows_rising': lows_rising, 'highs_falling': highs_falling,
        'bullish_follow_through_count': bullish_follow_through_count,
        'bearish_follow_through_count': bearish_follow_through_count,
        'down_efficiency': down_result / effort,
        'up_efficiency': up_result / effort,
        'reclaim_ma5': current['close'] >= ma5,
        'break_ma5': current['close'] < ma5,
        'break_prior_high': current['close'] > max(highs[-4:-1]),
        'break_prior_low': current['close'] < min(lows[-4:-1]),
    }


def _score_context(features: Dict, structure: str) -> Dict[str, float]:
    atr_pct = max(features['atr_pct'], 0.5)
    low_range = _scale(0.50 - features['range_position60'], 0, 0.50)
    high_range = _scale(features['range_position60'] - 0.50, 0, 0.50)
    low_bias = _scale(-features['bias20'] / atr_pct, 0.8, 4.0)
    high_bias = _scale(features['bias20'] / atr_pct, 0.8, 4.0)
    low_drawdown = _scale(-features['drawdown20'] / atr_pct, 1.5, 7.0)
    high_rise = _scale(features['rise20'] / atr_pct, 1.5, 7.0)
    low_location = .4 * low_range + .3 * low_bias + .3 * low_drawdown
    high_location = .4 * high_range + .3 * high_bias + .3 * high_rise

    trend_down = 100 if structure == '下降趋势' else 40 if structure == '区间震荡' else 0
    trend_up = 100 if structure == '上涨趋势' else 40 if structure == '区间震荡' else 0
    pullback_depth = _scale(-features['drawdown20'] / atr_pct, 1.0, 5.0)
    rally_height = _scale(features['rise20'] / atr_pct, 1.0, 5.0)
    decline_context = (
        .25 * trend_down
        + .25 * _scale(-features['return_5d'] / atr_pct, .5, 4)
        + .20 * _scale(-features['return_10d'] / atr_pct, 1, 6)
        + .15 * _scale(-features['prior_7d_return'] / atr_pct, .5, 4)
        + .15 * pullback_depth
    )
    advance_context = (
        .25 * trend_up
        + .25 * _scale(features['return_5d'] / atr_pct, .5, 4)
        + .20 * _scale(features['return_10d'] / atr_pct, 1, 6)
        + .15 * _scale(features['prior_7d_return'] / atr_pct, .5, 4)
        + .15 * rally_height
    )
    distance_ma20_atr = abs(features['close'] - features['ma20']) / features['atr14']
    ma_proximity = 100 - _scale(distance_ma20_atr, 0.5, 3.0)
    if structure == '上涨趋势':
        support_context = .35 * 100 + .35 * ma_proximity + .30 * pullback_depth
        resistance_context = .25 * high_range + .25 * ma_proximity + .50 * rally_height
    elif structure == '下降趋势':
        support_context = .25 * low_range + .25 * ma_proximity + .50 * pullback_depth
        resistance_context = .35 * 100 + .35 * ma_proximity + .30 * rally_height
    else:
        support_context = .50 * low_range + .25 * ma_proximity + .25 * pullback_depth
        resistance_context = .50 * high_range + .25 * ma_proximity + .25 * rally_height
    return {key: round(_clamp(value), 1) for key, value in {
        'low_location': low_location, 'high_location': high_location,
        'decline_context': decline_context, 'advance_context': advance_context,
        'support_context': support_context, 'resistance_context': resistance_context,
    }.items()}


def _score_evidence(features: Dict, context: Dict) -> Dict[str, float]:
    volume_effort = max(
        _scale(features['volume_ratio20'], 1.1, 2.2),
        _scale(features['volume_percentile120'], .70, .97),
    )
    range_effort = _scale(features['range_atr'], 1.0, 2.2)
    sell_result = max(
        _scale(-features['body_atr'], .35, 1.4),
        _scale(features['new_low_atr'], .1, 1.2),
    )
    buy_result = max(
        _scale(features['body_atr'], .35, 1.4),
        _scale(features['new_high_atr'], .1, 1.2),
    )
    panic_release = (
        (.35 * volume_effort + .25 * range_effort + .40 * sell_result)
        if context['decline_context'] >= 45 and sell_result >= 30 else 0
    )
    buying_climax = (
        (.35 * volume_effort + .25 * range_effort + .40 * buy_result)
        if context['advance_context'] >= 45 and buy_result >= 30 else 0
    )

    down_slowdown = (
        _scale(
            (features['prior_down_speed'] - features['current_down_speed'])
            / max(features['prior_down_speed'], features['atr_pct'] * .05, .05),
            0, .9,
        )
        if features['prior_down_speed'] > 0 else 0
    )
    up_slowdown = (
        _scale(
            (features['prior_up_speed'] - features['current_up_speed'])
            / max(features['prior_up_speed'], features['atr_pct'] * .05, .05),
            0, .9,
        )
        if features['prior_up_speed'] > 0 else 0
    )
    no_down_progress = max(
        100 if features['no_new_low_3d'] else 0,
        100 - _scale(features['new_low_atr'], .05, .8),
    )
    no_up_progress = max(
        100 if features['no_new_high_3d'] else 0,
        100 - _scale(features['new_high_atr'], .05, .8),
    )
    range_contract = 100 - _scale(features['recent_range_ratio'], .55, 1.05)
    volume_contract = 100 - _scale(features['recent_volume_ratio'], .45, 1.0)
    supply_exhaustion = (
        .35 * down_slowdown + .30 * no_down_progress
        + .20 * range_contract + .15 * volume_contract
    ) if context['decline_context'] >= 30 else 0
    demand_exhaustion = (
        .35 * up_slowdown + .30 * no_up_progress
        + .20 * range_contract + .15 * volume_contract
    ) if context['advance_context'] >= 30 else 0

    high_effort = .6 * volume_effort + .4 * range_effort
    poor_down_result = 100 - _scale(features['down_efficiency'], .35, 1.3)
    poor_up_result = 100 - _scale(features['up_efficiency'], .35, 1.3)
    recovery = max(
        _scale(features['close_location'], .35, .80),
        _scale(features['lower_shadow_ratio'], .20, .65),
    )
    rejection = max(
        _scale(.65 - features['close_location'], 0, .55),
        _scale(features['upper_shadow_ratio'], .20, .65),
    )
    absorption = (
        .4 * high_effort + .3 * poor_down_result + .3 * recovery
        if high_effort >= 30 and context['decline_context'] >= 35 else 0
    )
    distribution = (
        .4 * high_effort + .3 * poor_up_result + .3 * rejection
        if high_effort >= 30 and context['advance_context'] >= 35 else 0
    )

    bullish_result = (
        .45 * _scale(features['body_atr'], .05, .9)
        + .25 * _scale(features['close_location'], .50, .90)
        + .15 * (100 if features['reclaim_ma5'] else 0)
        + .15 * (100 if features['break_prior_high'] or features['lows_rising'] else 0)
    )
    demand_entry = .8 * bullish_result + .2 * max(volume_effort, 35 if supply_exhaustion >= 60 else 0)
    bearish_result = (
        .45 * _scale(-features['body_atr'], .05, .9)
        + .25 * _scale(.50 - features['close_location'], 0, .45)
        + .15 * (100 if features['break_ma5'] else 0)
        + .15 * (100 if features['break_prior_low'] or features['highs_falling'] else 0)
    )
    # 下降不一定需要放量，因此供应进入只给量能10%权重。
    supply_entry = .9 * bearish_result + .1 * volume_effort

    values = {
        'panic_release': panic_release, 'supply_exhaustion': supply_exhaustion,
        'absorption': absorption, 'demand_entry': demand_entry,
        'buying_climax': buying_climax, 'demand_exhaustion': demand_exhaustion,
        'distribution': distribution, 'supply_entry': supply_entry,
    }
    return {key: round(_clamp(value), 1) for key, value in values.items()}


def _combine_valley(structure: str, context: Dict, evidence: Dict, features: Dict) -> Tuple[str, List[str]]:
    low = context['low_location']
    decline = context['decline_context']
    support = context['support_context']
    supply_event = max(evidence['panic_release'], evidence['supply_exhaustion'], evidence['absorption'])
    phase = 'none'
    gates = []

    if structure == '上涨趋势':
        pullback = features['return_3d'] < 0 or features['drawdown20'] < -features['atr_pct'] * 1.5
        if pullback and decline >= 30 and support >= 45:
            phase = 'left'
        if phase != 'none' and support >= 50 and evidence['supply_exhaustion'] >= 45:
            phase = 'forming'
        if (
            phase == 'forming' and support >= 55
            and evidence['supply_exhaustion'] >= 60
            and evidence['demand_entry'] >= 50
            and features['bullish_follow_through_count'] >= 1
        ):
            phase = 'biased'
        if (
            phase == 'biased' and evidence['demand_entry'] >= 75
            and features['bullish_follow_through_count'] >= 2
            and features['reclaim_ma5']
        ):
            phase = 'confirmed'
    elif structure == '区间震荡':
        if low >= 55:
            phase = 'left'
        if phase != 'none' and supply_event >= 55:
            phase = 'forming'
        if phase == 'forming' and max(evidence['supply_exhaustion'], evidence['absorption']) >= 55 and evidence['demand_entry'] >= 45:
            phase = 'biased'
        if (
            phase == 'biased' and evidence['demand_entry'] >= 75
            and features['bullish_follow_through_count'] >= 2
            and features['range_position60'] > .12
        ):
            phase = 'confirmed'
    else:
        # 反转日价格会迅速离开最低点、降低低位/下降背景分，门槛需保留
        # 对刚发生的供需反转的识别空间；后续仍由吸收与需求进入硬约束。
        if decline >= 45 and low >= 45:
            phase = 'left'
        if phase != 'none' and supply_event >= 55:
            phase = 'forming'
        if (
            phase == 'forming'
            and max(evidence['panic_release'], evidence['supply_exhaustion']) >= 60
            and (
                (evidence['absorption'] >= 45 and evidence['demand_entry'] >= 50)
                or (
                    evidence['supply_exhaustion'] >= 60
                    and evidence['demand_entry'] >= 65
                    and features['bullish_follow_through_count'] >= 2
                )
            )
        ):
            phase = 'biased'
        if (
            phase == 'biased' and evidence['demand_entry'] >= 75
            and features['bullish_follow_through_count'] >= 2
            and features['reclaim_ma5']
        ):
            phase = 'confirmed'
        if phase in ('left', 'forming'):
            if evidence['absorption'] < 45:
                gates.append('下降趋势尚无有效吸收/放量滞跌')
            if evidence['demand_entry'] < 50:
                gates.append('下降趋势尚无需求进入')
    if phase in ('left', 'forming') and features['bias20'] < -8:
        gates.append('极端负乖离只表示低位，不能替代供需确认')
    return phase, gates


def _combine_peak(structure: str, context: Dict, evidence: Dict, features: Dict) -> Tuple[str, List[str]]:
    high = context['high_location']
    advance = context['advance_context']
    resistance = context['resistance_context']
    demand_event = max(evidence['buying_climax'], evidence['demand_exhaustion'], evidence['distribution'])
    phase = 'none'
    gates = []

    if structure == '下降趋势':
        bounce = features['return_5d'] > features['atr_pct'] * 1.5
        if bounce and resistance >= 45:
            phase = 'left'
        if phase != 'none' and max(evidence['demand_exhaustion'], evidence['distribution']) >= 50:
            phase = 'forming'
        if (
            phase == 'forming' and evidence['supply_entry'] >= 50
            and features['bearish_follow_through_count'] >= 1
        ):
            phase = 'biased'
        if (
            phase == 'biased' and evidence['supply_entry'] >= 75
            and features['bearish_follow_through_count'] >= 2
            and features['break_ma5']
        ):
            phase = 'confirmed'
    elif structure == '区间震荡':
        if high >= 55:
            phase = 'left'
        if phase != 'none' and demand_event >= 55:
            phase = 'forming'
        if (
            phase == 'forming'
            and max(evidence['demand_exhaustion'], evidence['distribution']) >= 55
            and evidence['supply_entry'] >= 45
            and features['bearish_follow_through_count'] >= 1
        ):
            phase = 'biased'
        if (
            phase == 'biased' and evidence['supply_entry'] >= 75
            and features['bearish_follow_through_count'] >= 2
        ):
            phase = 'confirmed'
    else:
        if advance >= 55 and high >= 55:
            phase = 'left'
        if phase != 'none' and demand_event >= 55:
            phase = 'forming'
        if (
            phase == 'forming'
            and max(evidence['demand_exhaustion'], evidence['distribution']) >= 55
            and evidence['supply_entry'] >= 45
            and features['bearish_follow_through_count'] >= 1
        ):
            phase = 'biased'
        if (
            phase == 'biased' and evidence['supply_entry'] >= 75
            and features['bearish_follow_through_count'] >= 2
            and features['break_ma5']
        ):
            phase = 'confirmed'
    if phase in ('left', 'forming') and features['bias20'] > 8:
        gates.append('极端正乖离只表示高位，不能替代供需确认')
    return phase, gates


def _resolve_side(valley_phase: str, peak_phase: str, context: Dict, evidence: Dict) -> Tuple[str, str]:
    valley_level = PHASE_SCORE[valley_phase]
    peak_level = PHASE_SCORE[peak_phase]
    if valley_level > peak_level:
        return 'valley', valley_phase
    if peak_level > valley_level:
        return 'peak', peak_phase
    if valley_level == 0:
        return 'none', 'none'
    valley_strength = context['low_location'] + evidence['absorption'] + evidence['demand_entry']
    peak_strength = context['high_location'] + evidence['distribution'] + evidence['supply_entry']
    return ('valley', valley_phase) if valley_strength >= peak_strength else ('peak', peak_phase)


def _labels(side: str, phase: str) -> Tuple[str, str, str]:
    if side == 'valley':
        label = {
            'left': '波谷左侧', 'forming': '波谷形成中',
            'biased': '偏波谷', 'confirmed': '波谷确认',
        }.get(phase, '波中')
        position = '偏波谷' if phase in ('biased', 'confirmed') else '波中偏下'
        state = '需求开始占优' if phase == 'confirmed' else '供需趋于平衡' if phase == 'biased' else '供应衰减观察' if phase == 'forming' else '供应仍占优'
        return label, position, state
    if side == 'peak':
        label = {
            'left': '波峰左侧', 'forming': '波峰形成中',
            'biased': '偏波峰', 'confirmed': '波峰确认',
        }.get(phase, '波中')
        position = '偏波峰' if phase in ('biased', 'confirmed') else '波中偏上'
        state = '供应开始占优' if phase == 'confirmed' else '供需趋于平衡' if phase == 'biased' else '需求衰减观察' if phase == 'forming' else '需求仍占优'
        return label, position, state
    return '波中', '波中', '供需未出现明确转折'


def _explain(side: str, phase: str, structure: str, context: Dict, evidence: Dict) -> List[str]:
    messages = [f'市场结构：{structure}']
    if side == 'valley':
        if context['low_location'] >= 55:
            messages.append('价格已进入低位区域')
        best_name, best_score = max(
            ((name, evidence[name]) for name in ('panic_release', 'supply_exhaustion', 'absorption', 'demand_entry')),
            key=lambda item: item[1],
        )
        name_map = {
            'panic_release': '恐慌释放', 'supply_exhaustion': '供应衰竭',
            'absorption': '放量吸收/滞跌', 'demand_entry': '需求进入',
        }
        messages.append(f'最强波谷证据：{name_map[best_name]} {best_score:g}')
        if phase in ('left', 'forming') and evidence['demand_entry'] < 50:
            messages.append('需求尚未形成有效反转')
    elif side == 'peak':
        if context['high_location'] >= 55:
            messages.append('价格已进入高位区域')
        best_name, best_score = max(
            ((name, evidence[name]) for name in ('buying_climax', 'demand_exhaustion', 'distribution', 'supply_entry')),
            key=lambda item: item[1],
        )
        name_map = {
            'buying_climax': '需求高潮', 'demand_exhaustion': '需求衰竭',
            'distribution': '派发/滞涨', 'supply_entry': '供应进入',
        }
        messages.append(f'最强波峰证据：{name_map[best_name]} {best_score:g}')
    else:
        messages.append('未形成足够的峰谷供需证据')
    return messages


def judge_peak_valley_v3(klines: List[Dict], structure: Optional[str] = None) -> Dict:
    """返回供需证据、峰谷阶段和兼容的五档位置。"""
    bars = normalize_market_klines(klines)
    if len(bars) < MIN_BARS:
        return {
            'position': '波中', 'wave_side': 'none', 'wave_phase': 'none',
            'wave_label': '数据不足', 'structure': '待确认',
            'supply_demand_state': '待确认', 'pk_score': 0, 'vl_score': 0,
            'evidence': {}, 'context': {}, 'hard_gates': ['至少需要80根有效K线'],
            'explanation': ['数据不足'], 'algorithm_version': 'supply_demand_v3',
        }
    features = _compute_features(bars)
    structure = structure or _classify_structure(features)
    if structure == '上升趋势':
        structure = '上涨趋势'
    elif structure == '下跌趋势':
        structure = '下降趋势'
    context = _score_context(features, structure)
    evidence = _score_evidence(features, context)
    valley_phase, valley_gates = _combine_valley(structure, context, evidence, features)
    peak_phase, peak_gates = _combine_peak(structure, context, evidence, features)
    side, phase = _resolve_side(valley_phase, peak_phase, context, evidence)
    label, position, supply_demand_state = _labels(side, phase)
    return {
        'position': position,
        'wave_side': side,
        'wave_phase': phase,
        'wave_label': label,
        'structure': structure,
        'supply_demand_state': supply_demand_state,
        'pk_score': PHASE_SCORE[phase] if side == 'peak' else 0,
        'vl_score': PHASE_SCORE[phase] if side == 'valley' else 0,
        'peak_phase': peak_phase,
        'valley_phase': valley_phase,
        'context': context,
        'evidence': evidence,
        'hard_gates': valley_gates if side == 'valley' else peak_gates if side == 'peak' else [],
        'valley_gates': valley_gates,
        'peak_gates': peak_gates,
        'explanation': _explain(side, phase, structure, context, evidence),
        'features': {key: round(value, 4) if isinstance(value, float) else value for key, value in features.items()},
        'algorithm_version': 'supply_demand_v3',
    }
