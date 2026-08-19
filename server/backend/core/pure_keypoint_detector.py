"""纯关键点识别器。

本模块只回答一个问题：K 线图上哪些点本身值得被标记？

它不判断买卖点，也不解释供需含义。按照 3L 原文，第一阶段只识别两类
客观关键点：

- 价格关键点：局部前高、局部前低；
- 成交量关键点：局部量峰、局部量谷。

供需格局转换点（突破、跌破、反转、中继、恐慌）需要在本模块输出之上，
再结合结构、位置和量价结果单独识别。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional


@dataclass(frozen=True)
class KeypointProfile:
    """不同对象类型的关键点识别参数。

    定义保持一致，参数允许随对象类型微调：

    - market：指数噪音较少，关键点应更少、更稳；
    - sector：板块轮动更快，敏感度介于指数和个股之间；
    - stock：个股噪音最大，价格窗口更短，但量峰/量谷强度要求更高。
    """

    name: str
    price_left: int
    price_right: int
    volume_left: int
    volume_right: int
    lookback: int
    min_spacing: int
    volume_ma_period: int
    volume_peak_ma_ratio: float
    volume_peak_percentile: float
    volume_trough_ma_ratio: float
    volume_trough_percentile: float


PROFILES: Dict[str, KeypointProfile] = {
    'market': KeypointProfile(
        name='market',
        price_left=5,
        price_right=5,
        volume_left=5,
        volume_right=5,
        lookback=60,
        min_spacing=3,
        volume_ma_period=20,
        volume_peak_ma_ratio=1.25,
        volume_peak_percentile=85,
        volume_trough_ma_ratio=0.75,
        volume_trough_percentile=20,
    ),
    'sector': KeypointProfile(
        name='sector',
        price_left=4,
        price_right=4,
        volume_left=4,
        volume_right=4,
        lookback=60,
        min_spacing=3,
        volume_ma_period=20,
        volume_peak_ma_ratio=1.35,
        volume_peak_percentile=85,
        volume_trough_ma_ratio=0.70,
        volume_trough_percentile=18,
    ),
    'stock': KeypointProfile(
        name='stock',
        price_left=3,
        price_right=3,
        volume_left=3,
        volume_right=3,
        lookback=60,
        min_spacing=3,
        volume_ma_period=20,
        volume_peak_ma_ratio=1.50,
        volume_peak_percentile=90,
        volume_trough_ma_ratio=0.65,
        volume_trough_percentile=15,
    ),
}


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_klines(klines: Iterable[Dict]) -> List[Dict]:
    rows = [dict(k) for k in klines or []]
    rows.sort(key=lambda k: str(k.get('date', '')))
    return rows


def _avg(values: List[float]) -> Optional[float]:
    values = [v for v in values if v > 0]
    if not values:
        return None
    return sum(values) / len(values)


def _percentile_rank(value: float, values: List[float]) -> Optional[float]:
    values = sorted(v for v in values if v > 0)
    if not values:
        return None
    less = sum(1 for v in values if v < value)
    equal = sum(1 for v in values if v == value)
    return (less + equal * 0.5) / len(values) * 100


def _window(rows: List[Dict], idx: int, left: int, right: int,
            field: str, end: int) -> tuple[List[float], List[float]]:
    lvals = [_safe_float(r.get(field)) for r in rows[max(0, idx - left):idx]]
    rvals = [_safe_float(r.get(field)) for r in rows[idx + 1:min(end + 1, idx + right + 1)]]
    return lvals, rvals


def _volume_window(rows: List[Dict], idx: int, left: int, right: int,
                   end: int) -> tuple[List[float], List[float]]:
    def vol(row: Dict) -> float:
        return _safe_float(row.get('volume', row.get('vol', 0)))

    lvals = [vol(r) for r in rows[max(0, idx - left):idx]]
    rvals = [vol(r) for r in rows[idx + 1:min(end + 1, idx + right + 1)]]
    return lvals, rvals


def _is_local_high(value: float, left_values: List[float], right_values: List[float]) -> bool:
    if len(left_values) < 2:
        return False
    return value > max(left_values) and (not right_values or value >= max(right_values))


def _is_local_low(value: float, left_values: List[float], right_values: List[float]) -> bool:
    if len(left_values) < 2:
        return False
    return value < min(left_values) and (not right_values or value <= min(right_values))


def _status(idx: int, end: int, right_window: int) -> str:
    return 'confirmed' if idx + right_window <= end else 'candidate'


def _strength_from_percentile(percentile: Optional[float], *, high: bool) -> str:
    if percentile is None:
        return 'normal'
    if high:
        if percentile >= 95:
            return 'major'
        if percentile >= 85:
            return 'strong'
    else:
        if percentile <= 5:
            return 'major'
        if percentile <= 20:
            return 'strong'
    return 'normal'


def _point(*, idx: int, row: Dict, point_type: str, label: str, status: str,
           price: Optional[float] = None, volume: Optional[float] = None,
           role: str = '', profile: KeypointProfile,
           strength: str = 'normal', metrics: Optional[Dict] = None) -> Dict:
    result = {
        'idx': idx,
        'date': str(row.get('date', '')),
        'type': point_type,
        'label': label,
        'status': status,
        'asset_profile': profile.name,
        'window_left': profile.price_left if point_type.startswith('price_') else profile.volume_left,
        'window_right': profile.price_right if point_type.startswith('price_') else profile.volume_right,
        'strength': strength,
    }
    if role:
        result['role'] = role
    if price is not None:
        result['price'] = round(float(price), 4)
    if volume is not None:
        result['volume'] = float(volume)
    if metrics:
        result['metrics'] = metrics
    return result


def get_keypoint_profile(asset_type: str = 'stock') -> KeypointProfile:
    return PROFILES.get(asset_type, PROFILES['stock'])


def detect_pure_keypoints(klines: Iterable[Dict], *, asset_type: str = 'stock',
                          end_idx: int = -1, lookback: Optional[int] = None) -> Dict:
    """识别纯关键点。

    Returns:
        {
          "version": "pure-keypoint-v1",
          "asset_type": "market|sector|stock",
          "points": [
            {"type": "price_high", "status": "confirmed|candidate", ...},
            {"type": "volume_peak", "status": "confirmed|candidate", ...}
          ]
        }
    """
    rows = _normalize_klines(klines)
    if not rows:
        return {
            'version': 'pure-keypoint-v1',
            'asset_type': asset_type,
            'status': 'unavailable',
            'reason': '数据不足',
            'points': [],
        }

    profile = get_keypoint_profile(asset_type)
    end = end_idx if end_idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    lb = lookback or profile.lookback
    start = max(0, end - lb + 1)
    points: List[Dict] = []

    for i in range(start, end + 1):
        row = rows[i]
        high = _safe_float(row.get('high'))
        low = _safe_float(row.get('low'))

        left_highs, right_highs = _window(rows, i, profile.price_left, profile.price_right, 'high', end)
        if high > 0 and _is_local_high(high, left_highs, right_highs):
            points.append(_point(
                idx=i,
                row=row,
                point_type='price_high',
                label='局部前高' if _status(i, end, profile.price_right) == 'confirmed' else '候选前高',
                status=_status(i, end, profile.price_right),
                price=high,
                role='resistance',
                profile=profile,
            ))

        left_lows, right_lows = _window(rows, i, profile.price_left, profile.price_right, 'low', end)
        if low > 0 and _is_local_low(low, left_lows, right_lows):
            points.append(_point(
                idx=i,
                row=row,
                point_type='price_low',
                label='局部前低' if _status(i, end, profile.price_right) == 'confirmed' else '候选前低',
                status=_status(i, end, profile.price_right),
                price=low,
                role='support',
                profile=profile,
            ))

        volume = _safe_float(row.get('volume', row.get('vol', 0)))
        if volume <= 0:
            continue
        left_vols, right_vols = _volume_window(rows, i, profile.volume_left, profile.volume_right, end)
        history = [
            _safe_float(r.get('volume', r.get('vol', 0)))
            for r in rows[max(0, i - profile.lookback + 1):i + 1]
        ]
        ma_values = [
            _safe_float(r.get('volume', r.get('vol', 0)))
            for r in rows[max(0, i - profile.volume_ma_period):i]
        ]
        vol_ma = _avg(ma_values)
        ma_ratio = volume / vol_ma if vol_ma else None
        pct = _percentile_rank(volume, history)
        metrics = {
            'volume_ma_ratio': round(ma_ratio, 2) if ma_ratio is not None else None,
            'volume_percentile': round(pct, 1) if pct is not None else None,
        }

        is_peak_shape = _is_local_high(volume, left_vols, right_vols)
        is_peak_strong = (
            (ma_ratio is not None and ma_ratio >= profile.volume_peak_ma_ratio)
            or (pct is not None and pct >= profile.volume_peak_percentile)
        )
        if is_peak_shape and is_peak_strong:
            points.append(_point(
                idx=i,
                row=row,
                point_type='volume_peak',
                label='局部量峰' if _status(i, end, profile.volume_right) == 'confirmed' else '候选量峰',
                status=_status(i, end, profile.volume_right),
                volume=volume,
                role='volume_peak',
                profile=profile,
                strength=_strength_from_percentile(pct, high=True),
                metrics=metrics,
            ))

        is_trough_shape = _is_local_low(volume, left_vols, right_vols)
        is_trough_strong = (
            (ma_ratio is not None and ma_ratio <= profile.volume_trough_ma_ratio)
            or (pct is not None and pct <= profile.volume_trough_percentile)
        )
        if is_trough_shape and is_trough_strong:
            points.append(_point(
                idx=i,
                row=row,
                point_type='volume_trough',
                label='局部量谷' if _status(i, end, profile.volume_right) == 'confirmed' else '候选量谷',
                status=_status(i, end, profile.volume_right),
                volume=volume,
                role='volume_trough',
                profile=profile,
                strength=_strength_from_percentile(pct, high=False),
                metrics=metrics,
            ))

    return {
        'version': 'pure-keypoint-v1',
        'asset_type': asset_type,
        'status': 'ok',
        'date': str(rows[end].get('date', '')),
        'profile': profile.__dict__,
        'points': _dedupe_points(points, profile),
    }


def _dedupe_points(points: List[Dict], profile: KeypointProfile) -> List[Dict]:
    """同类型点过近时保留更强的那个，避免图上密集噪音。"""
    def score(point: Dict) -> float:
        metrics = point.get('metrics') or {}
        percentile = metrics.get('volume_percentile')
        if point['type'] == 'volume_peak' and percentile is not None:
            return float(percentile)
        if point['type'] == 'volume_trough' and percentile is not None:
            return 100 - float(percentile)
        return float(point.get('price') or point.get('volume') or 0)

    kept: List[Dict] = []
    for point in sorted(points, key=lambda p: (p['type'], p['idx'])):
        same_near = [
            existing for existing in kept
            if existing['type'] == point['type']
            and abs(existing['idx'] - point['idx']) < profile.min_spacing
        ]
        if not same_near:
            kept.append(point)
            continue
        old = same_near[0]
        if score(point) > score(old):
            kept.remove(old)
            kept.append(point)
    kept.sort(key=lambda p: (p['idx'], p['type']))
    return kept
