"""3L 结构/阶段/位置统一上下文。

本模块解决同一根 K 线被不同模块用两把尺子解释的问题，例如：

- `stage='区间中段'`
- `current_zone.type='near_resistance'`

在 3L 语义里，区间结构下的“阶段”和“位置”本质上都来自同一个区间
百分位：接近上沿是区间顶部，接近下沿是区间底部，中间才是区间中段。

本模块只统一上下文，不输出买卖点。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from backend.core.ema_utils import ema_list


RANGE_LOOKBACK = 20
RANGE_TOP_PCT = 70.0
RANGE_BOTTOM_PCT = 30.0
TREND_ANCHOR_PCT = 4.0


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _pct_change(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _round(value: Optional[float], digits: int = 2):
    return round(value, digits) if value is not None else None


def _normalize_klines(klines: Iterable[Dict]) -> List[Dict]:
    rows = [dict(k) for k in klines or []]
    rows.sort(key=lambda k: str(k.get('date', '')))
    return rows


def _nearest_anchor(points: List[Dict], close: float, role: str) -> Optional[Dict]:
    candidates = [
        p for p in points
        if p.get('role') == role and p.get('price') not in (None, '')
    ]
    if role == 'support':
        candidates = [p for p in candidates if float(p['price']) <= close]
    elif role == 'resistance':
        candidates = [p for p in candidates if float(p['price']) >= close]
    candidates.sort(key=lambda p: abs(close - float(p['price'])))
    return candidates[0] if candidates else None


def anchor_payload(anchor: Dict, close: float) -> Dict:
    price = _safe_float(anchor.get('price'))
    return {
        'type': anchor.get('type'),
        'date': anchor.get('date'),
        'price': _round(price, 4),
        'status': anchor.get('status'),
        'distance_pct': _round(_pct_change(close, price), 2) if price else None,
    }


def _with_anchor_compat(zone: Dict) -> Dict:
    anchor = zone.get('anchor') or {}
    if anchor:
        zone.setdefault('anchor_type', anchor.get('type'))
        zone.setdefault('anchor_price', anchor.get('price'))
        zone.setdefault('distance_pct', anchor.get('distance_pct'))
    return zone


def _range_stage_from_pct(position_pct: Optional[float]) -> str:
    if position_pct is None:
        return '--'
    if position_pct >= RANGE_TOP_PCT:
        return '区间顶部'
    if position_pct <= RANGE_BOTTOM_PCT:
        return '区间底部'
    return '区间中段'


def detect_structure_position_context(
    klines: Iterable[Dict],
    *,
    idx: int = -1,
    structure: str,
    stage: str = '',
    reference_points: Optional[List[Dict]] = None,
) -> Dict:
    """返回统一后的结构/阶段/位置上下文。

    返回字段：

    - `structure`: 原结构；
    - `stage`: 规范化阶段；
    - `raw_stage`: 调用方传入的阶段；
    - `current_zone`: 当前位置；
    - `normalization`: 是否发生口径修正。
    """
    rows = _normalize_klines(klines)
    if not rows:
        return {
            'structure': structure,
            'stage': stage,
            'raw_stage': stage,
            'current_zone': {'type': 'unknown', 'anchor': None, 'reason': '数据不足'},
            'normalization': {'changed': False, 'reason': '数据不足'},
        }

    end = idx if idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    row = rows[end]
    close = _safe_float(row.get('close'))
    refs = reference_points or []
    resistance = _nearest_anchor(refs, close, 'resistance')
    support = _nearest_anchor(refs, close, 'support')

    if structure == '区间震荡':
        prior_rows = rows[max(0, end - RANGE_LOOKBACK):end]
        highs = [_safe_float(r.get('high')) for r in prior_rows]
        lows = [_safe_float(r.get('low')) for r in prior_rows]
        if highs and lows:
            range_high = max(highs)
            range_low = min(lows)
            range_span = range_high - range_low
            position_pct = (close - range_low) / range_span * 100 if range_span > 0 else 50.0
            normalized_stage = _range_stage_from_pct(position_pct)
            changed = bool(stage and normalized_stage != stage)
            if position_pct >= RANGE_TOP_PCT:
                anchor = resistance or {
                    'type': 'range_high',
                    'date': str(row.get('date', '')),
                    'price': range_high,
                    'status': 'candidate',
                    'role': 'resistance',
                }
                zone = _with_anchor_compat({
                    'type': 'near_resistance',
                    'range_position_pct': round(position_pct, 2),
                    'anchor': anchor_payload(anchor, close),
                    'reason': '区间震荡接近上沿/压力位',
                })
            elif position_pct <= RANGE_BOTTOM_PCT:
                anchor = support or {
                    'type': 'range_low',
                    'date': str(row.get('date', '')),
                    'price': range_low,
                    'status': 'candidate',
                    'role': 'support',
                }
                zone = _with_anchor_compat({
                    'type': 'near_support',
                    'range_position_pct': round(position_pct, 2),
                    'anchor': anchor_payload(anchor, close),
                    'reason': '区间震荡接近下沿/支撑位',
                })
            else:
                zone = {
                    'type': 'mid_range',
                    'range_position_pct': round(position_pct, 2),
                    'anchor': None,
                    'reason': '区间中部，供需方向未到关键位置',
                }
            return {
                'structure': structure,
                'stage': normalized_stage,
                'raw_stage': stage,
                'current_zone': zone,
                'normalization': {
                    'changed': changed,
                    'reason': '区间结构下阶段与位置统一使用近20根区间百分位',
                },
            }

    if structure == '上涨趋势':
        if stage in ('加速',):
            zone = {'type': 'extended', 'anchor': None, 'reason': '上涨趋势加速段，非回踩关键区'}
        else:
            closes = [_safe_float(r.get('close')) for r in rows[:end + 1]]
            anchors = []
            if len(closes) >= 10:
                anchors.append({'type': 'ema10', 'price': ema_list(closes, 10)[-1], 'date': str(row.get('date', ''))})
            if len(closes) >= 20:
                anchors.append({'type': 'ema20', 'price': ema_list(closes, 20)[-1], 'date': str(row.get('date', ''))})
            if support:
                anchors.append(support)
            anchors = [a for a in anchors if a.get('price')]
            anchors.sort(key=lambda a: abs(close - float(a['price'])))
            zone = {'type': 'trend_body', 'anchor': None, 'reason': '上涨趋势中但未回踩到关键支撑'}
            if anchors:
                anchor = anchors[0]
                distance = _pct_change(close, float(anchor['price']))
                if -TREND_ANCHOR_PCT <= distance <= TREND_ANCHOR_PCT:
                    zone = _with_anchor_compat({
                        'type': 'trend_pullback',
                        'anchor': anchor_payload(anchor, close),
                        'reason': '上涨趋势中回踩到均线或支撑附近',
                    })
        return {
            'structure': structure,
            'stage': stage,
            'raw_stage': stage,
            'current_zone': zone,
            'normalization': {'changed': False, 'reason': '趋势结构阶段暂由趋势算法定义'},
        }

    if structure == '下降趋势':
        return {
            'structure': structure,
            'stage': stage,
            'raw_stage': stage,
            'current_zone': _with_anchor_compat({
                'type': 'downtrend',
                'anchor': support and anchor_payload(support, close),
                'reason': '下降趋势中',
            }),
            'normalization': {'changed': False, 'reason': '趋势结构阶段暂由趋势算法定义'},
        }

    return {
        'structure': structure,
        'stage': stage,
        'raw_stage': stage,
        'current_zone': {'type': 'unknown', 'anchor': None, 'reason': '结构未确认'},
        'normalization': {'changed': False, 'reason': '结构未确认'},
    }
