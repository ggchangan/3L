"""3L 关键点上下文。

本模块把 3L 原文中的三类关键点特征统一成一个只读上下文：

- 明显参考点：前高、前低、天量/地量 K 线高低点；
- 不寻常量价行为：放量、缩量、长阳、长阴、十字星等；
- 供需格局点：突破、跌破、反转、中继。

P0 阶段只负责把上下文算清楚，供股票卡片、复盘信号和关键点图逐步迁移。
它不直接下买卖指令，也不替代后续买点检测器。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from backend.core.ema_utils import ema_list, get_stage, get_structure
from backend.core.structure_position_context import detect_structure_position_context
from backend.core.supply_demand_keypoint_detector import detect_supply_demand_keypoints


REFERENCE_LOOKBACK = 60
PIVOT_SIDE = 5
RANGE_LOOKBACK = 15
NEAR_ANCHOR_PCT = 3.0


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    return numerator / denominator * 100


def _avg(values: List[float]) -> Optional[float]:
    values = [v for v in values if v and v > 0]
    if not values:
        return None
    return sum(values) / len(values)


def _normalize_klines(klines: List[Dict]) -> List[Dict]:
    rows = [dict(k) for k in klines or []]
    rows.sort(key=lambda k: str(k.get('date', '')))
    return rows


def _point(idx: int, row: Dict, point_type: str, role: str, price: float,
           *, source: str, strength: str = 'normal') -> Dict:
    return {
        'idx': idx,
        'date': str(row.get('date', '')),
        'type': point_type,
        'role': role,
        'price': round(float(price), 2),
        'source': source,
        'strength': strength,
    }


def detect_reference_keypoints(klines: List[Dict], idx: int = -1,
                               lookback: int = REFERENCE_LOOKBACK) -> List[Dict]:
    """识别 3L 明显参考点。

    前高/前低使用局部波峰波谷；天量/地量使用回看窗口内显著最高/最低量
    K 线的高低点。这里的输出是参考点，不是交易结论。
    """
    rows = _normalize_klines(klines)
    if not rows:
        return []
    end = idx if idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    start = max(0, end - lookback + 1)
    scoped = rows[start:end + 1]
    points: List[Dict] = []

    for abs_i in range(start, end + 1):
        row = rows[abs_i]
        left = rows[max(start, abs_i - PIVOT_SIDE):abs_i]
        right = rows[abs_i + 1:min(end + 1, abs_i + PIVOT_SIDE + 1)]
        if len(left) < 2:
            continue
        high = _safe_float(row.get('high'))
        low = _safe_float(row.get('low'))
        if high and high >= max(_safe_float(k.get('high')) for k in left) and (
            not right or high >= max(_safe_float(k.get('high')) for k in right)
        ):
            points.append(_point(
                abs_i, row, 'prior_high', 'resistance', high,
                source='visible_reference',
            ))
        if low and low <= min(_safe_float(k.get('low')) for k in left) and (
            not right or low <= min(_safe_float(k.get('low')) for k in right)
        ):
            points.append(_point(
                abs_i, row, 'prior_low', 'support', low,
                source='visible_reference',
            ))

    vols = [_safe_float(k.get('volume', k.get('vol', 0))) for k in scoped]
    positive_vols = [v for v in vols if v > 0]
    if len(positive_vols) >= 10:
        max_vol = max(positive_vols)
        min_vol = min(positive_vols)
        avg_vol = _avg(positive_vols) or 0
        for rel_i, vol in enumerate(vols):
            abs_i = start + rel_i
            row = rows[abs_i]
            if avg_vol and vol == max_vol and vol >= avg_vol * 1.8:
                points.append(_point(
                    abs_i, row, 'climax_volume_high', 'resistance',
                    _safe_float(row.get('high')),
                    source='unusual_volume', strength='climax',
                ))
                points.append(_point(
                    abs_i, row, 'climax_volume_low', 'support',
                    _safe_float(row.get('low')),
                    source='unusual_volume', strength='climax',
                ))
            if avg_vol and vol == min_vol and vol <= avg_vol * 0.45:
                points.append(_point(
                    abs_i, row, 'dry_volume_high', 'resistance',
                    _safe_float(row.get('high')),
                    source='unusual_volume', strength='dry',
                ))
                points.append(_point(
                    abs_i, row, 'dry_volume_low', 'support',
                    _safe_float(row.get('low')),
                    source='unusual_volume', strength='dry',
                ))

    points.sort(key=lambda p: (p['idx'], p['type'], p['price']))
    return points


def _nearest_anchor(points: List[Dict], close: float, role: str) -> Optional[Dict]:
    candidates = [p for p in points if p.get('role') == role and p.get('price')]
    if role == 'support':
        candidates = [p for p in candidates if float(p['price']) <= close]
        candidates.sort(key=lambda p: abs(close - float(p['price'])))
    else:
        candidates = [p for p in candidates if float(p['price']) >= close]
        candidates.sort(key=lambda p: abs(float(p['price']) - close))
    return candidates[0] if candidates else None


def detect_current_zone(klines: List[Dict], idx: int, structure: str, stage: str,
                        reference_points: List[Dict]) -> Dict:
    """判断当前价格处在什么关键区域。"""
    context = detect_structure_position_context(
        klines,
        idx=idx,
        structure=structure,
        stage=stage,
        reference_points=reference_points,
    )
    return context['current_zone']


def detect_volume_price_action(klines: List[Dict], idx: int = -1) -> Dict:
    """识别当前 K 线的量价行为证据。"""
    rows = _normalize_klines(klines)
    if len(rows) < 2:
        return {'type': 'unknown', 'reason': '数据不足'}
    end = idx if idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    row = rows[end]
    prev = rows[end - 1]
    close = _safe_float(row.get('close'))
    prev_close = _safe_float(prev.get('close'))
    open_ = _safe_float(row.get('open'), close)
    high = _safe_float(row.get('high'), close)
    low = _safe_float(row.get('low'), close)
    volume = _safe_float(row.get('volume', row.get('vol', 0)))
    prev_volume = _safe_float(prev.get('volume', prev.get('vol', 0)))
    prev5_avg = _avg([
        _safe_float(k.get('volume', k.get('vol', 0)))
        for k in rows[max(0, end - 5):end]
    ])
    prev20_avg = _avg([
        _safe_float(k.get('volume', k.get('vol', 0)))
        for k in rows[max(0, end - 20):end]
    ])
    price_change_pct = _pct(close - prev_close, prev_close) or 0
    day_volume_ratio = volume / prev_volume if prev_volume > 0 else None
    volume_ratio_5 = volume / prev5_avg if prev5_avg else None
    volume_ratio_20 = volume / prev20_avg if prev20_avg else None
    body_pct = abs(close - open_) / open_ * 100 if open_ else 0
    amplitude_pct = (high - low) / low * 100 if low else 0
    close_position = (close - low) / (high - low) if high > low else 0.5

    is_volume_up = (
        (day_volume_ratio is not None and day_volume_ratio >= 1.25)
        or (volume_ratio_5 is not None and volume_ratio_5 >= 1.2)
    )
    is_shrink = (
        (day_volume_ratio is not None and day_volume_ratio <= 0.8)
        and (volume_ratio_5 is not None and volume_ratio_5 <= 0.85)
    )

    action_type = 'neutral'
    reason = '量价行为不突出'
    if is_volume_up and price_change_pct <= -2:
        action_type = 'volume_down'
        reason = '放量下跌，供应进入或需求承接不足'
    elif is_volume_up and price_change_pct >= 2:
        action_type = 'volume_up'
        reason = '放量上涨，需求主动推进'
    elif is_shrink and price_change_pct <= 1 and amplitude_pct <= 6:
        action_type = 'shrink_pullback'
        reason = '缩量窄幅回踩，需结合结构判断供应是否不足'
    elif is_shrink:
        action_type = 'shrink'
        reason = '缩量，需结合结构判断是供应萎缩还是需求不足'
    elif volume_ratio_20 is not None and volume_ratio_20 >= 2.0 and abs(price_change_pct) <= 1.5:
        action_type = 'climax_stagnation'
        reason = '天量滞涨/滞跌，需要观察供需结果'
    elif body_pct <= 1.0 and amplitude_pct >= 4:
        action_type = 'long_shadow_or_doji'
        reason = '长影线或十字星，体现关键位置分歧'

    return {
        'type': action_type,
        'date': str(row.get('date', '')),
        'price_change_pct': round(price_change_pct, 2),
        'day_volume_ratio': round(day_volume_ratio, 2) if day_volume_ratio is not None else None,
        'volume_ratio_5': round(volume_ratio_5, 2) if volume_ratio_5 is not None else None,
        'volume_ratio_20': round(volume_ratio_20, 2) if volume_ratio_20 is not None else None,
        'body_pct': round(body_pct, 2),
        'amplitude_pct': round(amplitude_pct, 2),
        'close_position': round(close_position, 2),
        'reason': reason,
    }


def detect_supply_demand_keypoint(structure: str, stage: str, current_zone: Dict,
                                  volume_price_action: Dict) -> Dict:
    """基于结构、关键区域和量价行为识别供需格局点。"""
    zone_type = current_zone.get('type')
    action_type = volume_price_action.get('type')
    change = _safe_float(volume_price_action.get('price_change_pct'))

    if structure == '上涨趋势' and zone_type == 'trend_pullback':
        if action_type == 'shrink_pullback':
            return {
                'type': 'continuation',
                'direction': 'bullish',
                'confidence': 70,
                'reason': '上涨趋势中缩量回踩，供应不足，原供不应求格局未被破坏',
            }
        if action_type == 'volume_down':
            return {
                'type': 'pullback_supply_entering',
                'direction': 'bearish',
                'confidence': 65,
                'reason': '上涨趋势回踩处放量下跌，供应显著进入，不能视为中继点',
            }

    if structure == '区间震荡' and zone_type == 'near_resistance':
        if action_type == 'volume_down' or change < -2:
            return {
                'type': 'failed_breakout',
                'direction': 'bearish',
                'confidence': 70,
                'reason': '区间顶部附近放量下跌或明显回落，供应进入，突破失败倾向',
            }
        if action_type == 'volume_up' and change > 2:
            return {
                'type': 'breakout',
                'direction': 'bullish',
                'confidence': 65,
                'reason': '区间顶部放量上涨，需求尝试突破压力',
            }
        return {
            'type': 'near_resistance',
            'direction': 'neutral',
            'confidence': 40,
            'reason': '区间顶部压力位置，等待突破或受阻的量价结果',
        }

    if structure == '区间震荡' and zone_type == 'near_support':
        if action_type == 'volume_down' and change < -2:
            return {
                'type': 'breakdown_pressure',
                'direction': 'bearish',
                'confidence': 65,
                'reason': '区间底部放量下跌，供应尝试跌破支撑',
            }
        if action_type in ('shrink_pullback', 'climax_stagnation', 'long_shadow_or_doji'):
            return {
                'type': 'support_test',
                'direction': 'bullish',
                'confidence': 55,
                'reason': '区间底部出现支撑测试，需要后续需求确认',
            }

    return {
        'type': 'none',
        'direction': 'neutral',
        'confidence': 0,
        'reason': '未识别到明确供需格局点',
    }


def build_keypoint_context(klines: List[Dict], idx: int = -1,
                           structure: str = '', stage: str = '',
                           asset_type: str = 'stock') -> Dict:
    """构建统一关键点上下文。"""
    rows = _normalize_klines(klines)
    if not rows:
        return {
            'version': 'keypoint-context-p0',
            'status': 'unavailable',
            'reason': '数据不足',
        }
    end = idx if idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    closes = [_safe_float(k.get('close')) for k in rows[:end + 1]]
    highs = [_safe_float(k.get('high')) for k in rows[:end + 1]]
    lows = [_safe_float(k.get('low')) for k in rows[:end + 1]]
    volumes = [_safe_float(k.get('volume', k.get('vol', 0))) for k in rows[:end + 1]]
    opens = [_safe_float(k.get('open'), _safe_float(k.get('close'))) for k in rows[:end + 1]]

    resolved_structure = structure or get_structure(closes)
    resolved_stage = stage or get_stage(
        closes,
        structure=resolved_structure,
        highs=highs,
        lows=lows,
        volumes=volumes,
        opens_p=opens,
    )
    refs = detect_reference_keypoints(rows, end)
    position_context = detect_structure_position_context(
        rows,
        idx=end,
        structure=resolved_structure,
        stage=resolved_stage,
        reference_points=refs,
    )
    resolved_stage = position_context.get('stage') or resolved_stage
    zone = position_context.get('current_zone') or {'type': 'unknown', 'anchor': None}
    vpa = detect_volume_price_action(rows, end)
    sd = detect_supply_demand_keypoint(resolved_structure, resolved_stage, zone, vpa)
    transition_context = detect_supply_demand_keypoints(
        rows[:end + 1],
        asset_type=asset_type,
        structure=resolved_structure,
        stage=resolved_stage,
    )
    return {
        'version': 'keypoint-context-p0',
        'status': 'ok',
        'date': str(rows[end].get('date', '')),
        'asset_type': asset_type,
        'structure': resolved_structure,
        'stage': resolved_stage,
        'raw_stage': position_context.get('raw_stage'),
        'stage_position_normalization': position_context.get('normalization'),
        'reference_points': refs,
        'current_zone': zone,
        'volume_price_action': vpa,
        'supply_demand_keypoint': sd,
        'supply_demand_transition_context': transition_context,
        'transition_points': transition_context.get('transition_points', []),
        'definitions': {
            'reference_points': '前高、前低、天量/地量K线高低点等明显参考点；不直接等于买卖点',
            'volume_price_action': '当前关键位置/走势中的放量、缩量、长阳、长阴、十字星等量价证据',
            'supply_demand_keypoint': '旧版兼容字段：突破、跌破、反转、中继等供需格局打破或延续的位置',
            'transition_points': 'P0.2新版字段：供需格局转换关键点；不直接等于买卖点',
        },
    }
