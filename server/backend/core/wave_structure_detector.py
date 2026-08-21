"""3L 波段结构识别实验函数。

这是 P0-structure 的旁路实验：先识别主导波段，再派生结构。
它不替换 `get_structure()`，也不接入生产页面。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


VERSION = 'wave-structure-v1'
MIN_BARS = 20


@dataclass(frozen=True)
class WaveProfile:
    name: str
    min_reversal_pct: float
    atr_multiplier: float
    min_impulse_pct: float


PROFILES = {
    'market': WaveProfile('market', min_reversal_pct=3.0, atr_multiplier=1.8, min_impulse_pct=4.0),
    'sector': WaveProfile('sector', min_reversal_pct=4.0, atr_multiplier=2.0, min_impulse_pct=5.0),
    'stock': WaveProfile('stock', min_reversal_pct=5.0, atr_multiplier=2.2, min_impulse_pct=6.0),
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_klines(klines: Iterable[Dict]) -> List[Dict]:
    rows = [dict(row) for row in klines or []]
    rows.sort(key=lambda row: str(row.get('date', row.get('trade_date', ''))))
    normalized = []
    for row in rows:
        date = str(row.get('date', row.get('trade_date', '')))
        open_ = _safe_float(row.get('open'))
        high = _safe_float(row.get('high'))
        low = _safe_float(row.get('low'))
        close = _safe_float(row.get('close'))
        volume = _safe_float(row.get('volume', row.get('vol', 0)))
        if not date or min(open_, high, low, close) <= 0:
            continue
        normalized.append({
            'date': date,
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume,
        })
    return normalized


def _pct_change(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _true_ranges(rows: List[Dict]) -> List[float]:
    result = []
    for idx, row in enumerate(rows):
        prev_close = rows[idx - 1]['close'] if idx else row['close']
        result.append(max(
            row['high'] - row['low'],
            abs(row['high'] - prev_close),
            abs(row['low'] - prev_close),
        ))
    return result


def _avg(values: List[float]) -> Optional[float]:
    values = [value for value in values if value > 0]
    if not values:
        return None
    return sum(values) / len(values)


def _atr_pct(rows: List[Dict], period: int = 14) -> float:
    if len(rows) < 2:
        return 0.0
    trs = _true_ranges(rows)
    atr = _avg(trs[-period:]) or 0.0
    close = rows[-1]['close']
    return atr / close * 100 if close else 0.0


def get_wave_profile(asset_type: str = 'stock') -> WaveProfile:
    return PROFILES.get(asset_type, PROFILES['stock'])


def _threshold(rows: List[Dict], profile: WaveProfile) -> Dict:
    atr = _atr_pct(rows)
    reversal = max(profile.min_reversal_pct, atr * profile.atr_multiplier)
    return {
        'atr_pct': round(atr, 4),
        'reversal_pct': round(reversal, 4),
        'min_impulse_pct': profile.min_impulse_pct,
    }


def detect_wave_pivots(rows: List[Dict], reversal_pct: float) -> List[Dict]:
    """使用动态 ZigZag 思路识别确认波段拐点。

    返回 confirmed pivot。最新形成中的极值不一定进入 pivots。
    """
    if len(rows) < 2:
        return []

    pivots: List[Dict] = []
    direction: Optional[str] = None
    extreme_idx = 0
    extreme_price = rows[0]['close']
    init_high_idx = 0
    init_high = rows[0]['high']
    init_low_idx = 0
    init_low = rows[0]['low']

    for idx in range(1, len(rows)):
        high = rows[idx]['high']
        low = rows[idx]['low']

        if direction is None:
            if high > init_high:
                init_high_idx, init_high = idx, high
            if low < init_low:
                init_low_idx, init_low = idx, low

            up_pct = _pct_change(init_high, init_low)
            down_pct = _pct_change(init_low, init_high)
            if up_pct >= reversal_pct and init_low_idx < init_high_idx:
                pivots.append(_pivot(rows, init_low_idx, 'low', init_low))
                direction = 'up'
                extreme_idx = init_high_idx
                extreme_price = init_high
            elif down_pct <= -reversal_pct and init_high_idx < init_low_idx:
                pivots.append(_pivot(rows, init_high_idx, 'high', init_high))
                direction = 'down'
                extreme_idx = init_low_idx
                extreme_price = init_low
            continue

        if direction == 'up':
            if high >= extreme_price:
                extreme_idx, extreme_price = idx, high
                continue
            drawdown = _pct_change(low, extreme_price)
            if drawdown <= -reversal_pct:
                pivots.append(_pivot(rows, extreme_idx, 'high', extreme_price))
                direction = 'down'
                extreme_idx, extreme_price = idx, low
        else:
            if low <= extreme_price:
                extreme_idx, extreme_price = idx, low
                continue
            rebound = _pct_change(high, extreme_price)
            if rebound >= reversal_pct:
                pivots.append(_pivot(rows, extreme_idx, 'low', extreme_price))
                direction = 'up'
                extreme_idx, extreme_price = idx, high

    return _dedupe_pivots(pivots)


def _pivot(rows: List[Dict], idx: int, pivot_type: str, price: float) -> Dict:
    return {
        'idx': idx,
        'date': rows[idx]['date'],
        'type': pivot_type,
        'price': round(price, 4),
    }


def _dedupe_pivots(pivots: List[Dict]) -> List[Dict]:
    result: List[Dict] = []
    for pivot in pivots:
        if result and result[-1]['idx'] == pivot['idx'] and result[-1]['type'] == pivot['type']:
            result[-1] = pivot
            continue
        if result and result[-1]['type'] == pivot['type']:
            # 同类型连续 pivot 只保留更极端的一个。
            previous = result[-1]
            if pivot['type'] == 'high' and pivot['price'] > previous['price']:
                result[-1] = pivot
            elif pivot['type'] == 'low' and pivot['price'] < previous['price']:
                result[-1] = pivot
            continue
        result.append(pivot)
    return result


def _active_wave(rows: List[Dict], pivots: List[Dict]) -> Dict:
    current = rows[-1]
    if not pivots:
        start = rows[0]
        change = _pct_change(current['close'], start['close'])
        direction = 'up' if change > 0 else 'down' if change < 0 else 'flat'
        return {
            'direction': direction,
            'start_idx': 0,
            'start_date': start['date'],
            'start_price': round(start['close'], 4),
            'extreme_idx': len(rows) - 1,
            'extreme_date': current['date'],
            'extreme_price': round(current['close'], 4),
            'change_pct': round(change, 2),
            'counter_move_pct': 0.0,
            'confirmed': False,
        }

    last = pivots[-1]
    scoped = rows[last['idx']:]
    if last['type'] == 'low':
        extreme_rel_idx, extreme = max(enumerate(scoped), key=lambda item: item[1]['high'])
        extreme_idx = last['idx'] + extreme_rel_idx
        direction = 'up'
        change = _pct_change(extreme['high'], last['price'])
        counter = max(0.0, -_pct_change(current['close'], extreme['high']))
        extreme_price = extreme['high']
    else:
        extreme_rel_idx, extreme = min(enumerate(scoped), key=lambda item: item[1]['low'])
        extreme_idx = last['idx'] + extreme_rel_idx
        direction = 'down'
        change = _pct_change(extreme['low'], last['price'])
        counter = max(0.0, _pct_change(current['close'], extreme['low']))
        extreme_price = extreme['low']

    return {
        'direction': direction,
        'start_idx': last['idx'],
        'start_date': last['date'],
        'start_price': round(float(last['price']), 4),
        'extreme_idx': extreme_idx,
        'extreme_date': rows[extreme_idx]['date'],
        'extreme_price': round(float(extreme_price), 4),
        'change_pct': round(change, 2),
        'counter_move_pct': round(counter, 2),
        'confirmed': True,
    }


def judge_wave_structure(klines: Iterable[Dict], *, asset_type: str = 'stock') -> Dict:
    """基于主导波段判断结构。

    这是实验函数，不影响生产 `get_structure()`。
    """
    rows = _normalize_klines(klines)
    if len(rows) < MIN_BARS:
        return {
            'version': VERSION,
            'status': 'unavailable',
            'reason': f'至少需要 {MIN_BARS} 根有效 K 线',
            'structure': '--',
            'phase': '--',
            'pivots': [],
            'active_wave': {},
        }

    profile = get_wave_profile(asset_type)
    thresholds = _threshold(rows, profile)
    pivots = detect_wave_pivots(rows, thresholds['reversal_pct'])
    active = _active_wave(rows, pivots)
    previous = _previous_wave(pivots)
    structure, phase, reason = _classify(active, thresholds, previous)

    return {
        'version': VERSION,
        'status': 'ok',
        'date': rows[-1]['date'],
        'asset_type': asset_type,
        'structure': structure,
        'phase': phase,
        'active_wave': active,
        'previous_wave': previous,
        'thresholds': thresholds,
        'pivots': pivots,
        'reason': reason,
    }


def _previous_wave(pivots: List[Dict]) -> Dict:
    if len(pivots) < 2:
        return {}
    start = pivots[-2]
    end = pivots[-1]
    direction = 'up' if start['type'] == 'low' and end['type'] == 'high' else 'down'
    return {
        'direction': direction,
        'start_date': start['date'],
        'start_price': start['price'],
        'end_date': end['date'],
        'end_price': end['price'],
        'change_pct': round(_pct_change(end['price'], start['price']), 2),
    }


def _classify(active: Dict, thresholds: Dict, previous: Optional[Dict] = None) -> tuple[str, str, str]:
    direction = active.get('direction')
    change = abs(float(active.get('change_pct') or 0))
    counter = float(active.get('counter_move_pct') or 0)
    min_impulse = float(thresholds['min_impulse_pct'])
    reversal = float(thresholds['reversal_pct'])
    previous = previous or {}
    previous_direction = previous.get('direction')
    previous_change = abs(float(previous.get('change_pct') or 0))

    if (
        direction == 'up'
        and previous_direction == 'down'
        and previous_change >= min_impulse
        and change < previous_change * 0.50
    ):
        return (
            '下降趋势',
            'countertrend_bounce',
            '新上涨波段相对前一主跌波幅度不足，先视为下降趋势中的反弹',
        )

    if (
        direction == 'down'
        and previous_direction == 'up'
        and previous_change >= min_impulse
        and change < previous_change * 0.50
    ):
        return (
            '上涨趋势',
            'pullback',
            '新下跌波段相对前一主升波幅度不足，先视为上涨趋势中的回踩',
        )

    if direction == 'up' and change >= min_impulse:
        if counter >= reversal * 0.65:
            return (
                '上涨趋势',
                'pullback',
                '主导上涨波段仍成立，但出现较明显回撤；未达到反转阈值前保持上涨结构',
            )
        return '上涨趋势', 'impulse', '主导上涨波段涨幅超过阈值，结构判为上涨趋势'

    if direction == 'down' and change >= min_impulse:
        if counter >= reversal * 0.65:
            return (
                '下降趋势',
                'countertrend_bounce',
                '主导下降波段仍成立，但出现反向反弹；未达到反转阈值前保持下降结构',
            )
        return '下降趋势', 'impulse', '主导下降波段跌幅超过阈值，结构判为下降趋势'

    return '区间震荡', 'range', '尚未形成超过波段阈值的主导上涨或下降波段'
