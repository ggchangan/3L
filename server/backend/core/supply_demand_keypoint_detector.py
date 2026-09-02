"""3L 供需格局转换关键点识别器。

本模块是 P0.2：消费 P0.1 纯关键点，并结合结构、位置和当日量价行为，
识别突破、跌破、反转、中继、恐慌滞跌、高潮滞涨等供需格局点。

注意：供需格局点不是买卖点。本模块永远不输出正式 buy_point，也不做仓位建议。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from backend.core.ema_utils import ema_list, get_stage, get_structure
from backend.core.pure_keypoint_detector import detect_pure_keypoints
from backend.core.structure_position_context import detect_structure_position_context
from backend.core.wave_structure_detector import judge_wave_structure


VERSION = 'supply-demand-keypoint-v1'
MIN_BARS = 20


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


def _volume(row: Dict) -> float:
    return _safe_float(row.get('volume', row.get('vol', 0)))


def _avg(values: List[float]) -> Optional[float]:
    values = [v for v in values if v > 0]
    if not values:
        return None
    return sum(values) / len(values)


def _pct_change(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _percentile_rank(value: float, values: List[float]) -> Optional[float]:
    clean = sorted(v for v in values if v > 0)
    if not clean:
        return None
    less = sum(1 for v in clean if v < value)
    equal = sum(1 for v in clean if v == value)
    return (less + equal * 0.5) / len(clean) * 100


def _round(value: Optional[float], digits: int = 2):
    return round(value, digits) if value is not None else None


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


def _bar_metrics(rows: List[Dict], end: int) -> Dict:
    row = rows[end]
    previous = rows[end - 1] if end > 0 else row
    open_ = _safe_float(row.get('open'), _safe_float(row.get('close')))
    high = _safe_float(row.get('high'), _safe_float(row.get('close')))
    low = _safe_float(row.get('low'), _safe_float(row.get('close')))
    close = _safe_float(row.get('close'))
    prev_close = _safe_float(previous.get('close'), close)
    volume = _volume(row)
    prev_volume = _volume(previous)
    previous_volumes = [_volume(r) for r in rows[:end]]
    volume_ma5 = _avg(previous_volumes[-5:])
    volume_ma20 = _avg(previous_volumes[-20:])
    volume_pct = _percentile_rank(volume, [_volume(r) for r in rows[max(0, end - 119):end + 1]])
    day_volume_ratio = volume / prev_volume if prev_volume > 0 else None
    volume_ma5_ratio = volume / volume_ma5 if volume_ma5 else None
    volume_ma20_ratio = volume / volume_ma20 if volume_ma20 else None
    bar_range = high - low
    body = close - open_
    body_pct = _pct_change(close, open_)
    price_change_pct = _pct_change(close, prev_close)
    close_location = (close - low) / bar_range if bar_range > 0 else 0.5
    upper_shadow_ratio = (high - max(open_, close)) / bar_range if bar_range > 0 else 0
    lower_shadow_ratio = (min(open_, close) - low) / bar_range if bar_range > 0 else 0

    return {
        'date': str(row.get('date', '')),
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'prev_close': prev_close,
        'volume': volume,
        'price_change_pct': price_change_pct,
        'body_pct': body_pct,
        'body_value': body,
        'close_location': close_location,
        'upper_shadow_ratio': upper_shadow_ratio,
        'lower_shadow_ratio': lower_shadow_ratio,
        'day_volume_ratio': day_volume_ratio,
        'volume_ma5_ratio': volume_ma5_ratio,
        'volume_ma20_ratio': volume_ma20_ratio,
        'volume_percentile': volume_pct,
    }


def _detect_current_zone(rows: List[Dict], end: int, structure: str,
                         stage: str, points: List[Dict]) -> Dict:
    row = rows[end]
    close = _safe_float(row.get('close'))
    highs = [_safe_float(r.get('high')) for r in rows[max(0, end - 20):end]]
    lows = [_safe_float(r.get('low')) for r in rows[max(0, end - 20):end]]
    resistance = _nearest_anchor(points, close, 'resistance')
    support = _nearest_anchor(points, close, 'support')

    if structure == '区间震荡' and highs and lows:
        range_high = max(highs)
        range_low = min(lows)
        range_span = range_high - range_low
        pos = (close - range_low) / range_span * 100 if range_span > 0 else 50
        if pos >= 70:
            anchor = resistance or {
                'type': 'range_high',
                'date': str(row.get('date', '')),
                'price': range_high,
                'status': 'candidate',
                'role': 'resistance',
            }
            return {
                'type': 'near_resistance',
                'range_position_pct': round(pos, 2),
                'anchor': _anchor_payload(anchor, close),
                'reason': '区间震荡接近上沿/压力位',
            }
        if pos <= 30:
            anchor = support or {
                'type': 'range_low',
                'date': str(row.get('date', '')),
                'price': range_low,
                'status': 'candidate',
                'role': 'support',
            }
            return {
                'type': 'near_support',
                'range_position_pct': round(pos, 2),
                'anchor': _anchor_payload(anchor, close),
                'reason': '区间震荡接近下沿/支撑位',
            }
        return {
            'type': 'mid_range',
            'range_position_pct': round(pos, 2),
            'anchor': None,
            'reason': '区间中部，供需方向未到关键位置',
        }

    if structure == '上涨趋势':
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
        if anchors:
            anchor = anchors[0]
            distance = _pct_change(close, float(anchor['price']))
            if -4.0 <= distance <= 4.0 and stage not in ('加速', '放量滞涨'):
                return {
                    'type': 'trend_pullback',
                    'anchor': _anchor_payload(anchor, close),
                    'reason': '上涨趋势中回踩到均线或支撑附近',
                }
        return {'type': 'trend_body', 'anchor': None, 'reason': '上涨趋势中但未回踩到关键支撑'}

    if structure == '下降趋势':
        return {'type': 'downtrend', 'anchor': support and _anchor_payload(support, close), 'reason': '下降趋势中'}

    return {'type': 'unknown', 'anchor': None, 'reason': '结构未确认'}


def _anchor_payload(anchor: Dict, close: float) -> Dict:
    price = _safe_float(anchor.get('price'))
    return {
        'type': anchor.get('type'),
        'date': anchor.get('date'),
        'price': _round(price, 4),
        'status': anchor.get('status'),
        'distance_pct': _round(_pct_change(close, price), 2) if price else None,
    }


def _detect_volume_price_action(metrics: Dict, pure_points: List[Dict], end: int) -> Dict:
    price_change = metrics['price_change_pct']
    day_ratio = metrics['day_volume_ratio'] or 1.0
    ma5_ratio = metrics['volume_ma5_ratio'] or 1.0
    ma20_ratio = metrics['volume_ma20_ratio'] or 1.0
    volume_pct = metrics['volume_percentile'] or 50.0
    close_location = metrics['close_location']

    has_volume_peak = any(
        p for p in pure_points
        if p.get('idx') == end and p.get('type') == 'volume_peak'
    )
    has_volume_trough = any(
        p for p in pure_points
        if p.get('idx') == end and p.get('type') == 'volume_trough'
    )

    is_volume_up = day_ratio >= 1.25 or ma5_ratio >= 1.20 or ma20_ratio >= 1.25
    is_huge_volume = has_volume_peak or ma20_ratio >= 1.8 or volume_pct >= 90
    is_shrink = day_ratio <= 0.85 and ma5_ratio <= 0.9 and ma20_ratio <= 0.95

    action_type = 'neutral'
    reason = '量价行为不突出'
    if (
        is_huge_volume
        and price_change <= 0.5
        and close_location >= 0.45
        and metrics['lower_shadow_ratio'] >= 0.20
    ):
        action_type = 'panic_stagnation'
        reason = '天量滞跌：供应强烈释放但价格没有有效收在低位'
    elif is_huge_volume and price_change >= 0 and close_location <= 0.55:
        action_type = 'climax_stagnation'
        reason = '天量滞涨：需求努力较大但价格推进效率下降'
    elif is_volume_up and price_change <= -2.0:
        action_type = 'volume_down'
        reason = '放量下跌，供应进入或需求承接不足'
    elif is_volume_up and price_change >= 2.0:
        action_type = 'volume_up'
        reason = '放量上涨，需求主动推进'
    elif is_shrink and price_change <= 1.0:
        action_type = 'shrink_pullback'
        reason = '缩量回踩或窄幅整理，需结合结构判断'
    elif is_shrink:
        action_type = 'shrink'
        reason = '缩量，需结合结构判断供应/需求含义'
    elif has_volume_trough:
        action_type = 'dry_volume'
        reason = '局部量谷，参与意愿收缩'

    return {
        'type': action_type,
        'date': metrics['date'],
        'price_change_pct': _round(price_change, 2),
        'day_volume_ratio': _round(metrics['day_volume_ratio'], 2),
        'volume_ma5_ratio': _round(metrics['volume_ma5_ratio'], 2),
        'volume_ma20_ratio': _round(metrics['volume_ma20_ratio'], 2),
        'volume_percentile': _round(metrics['volume_percentile'], 1),
        'close_location': _round(close_location, 2),
        'upper_shadow_ratio': _round(metrics['upper_shadow_ratio'], 2),
        'lower_shadow_ratio': _round(metrics['lower_shadow_ratio'], 2),
        'local_volume_role': 'volume_peak' if has_volume_peak else 'volume_trough' if has_volume_trough else 'normal',
        'reason': reason,
    }


def _score_evidence(structure: str, zone: Dict, vpa: Dict, metrics: Dict) -> Dict:
    price_change = metrics['price_change_pct']
    close_location = metrics['close_location']
    volume_strength = max(
        min(((metrics['volume_ma20_ratio'] or 1) - 1) / 1.2 * 100, 100),
        min(((metrics['volume_percentile'] or 50) - 50) / 45 * 100, 100),
        0,
    )
    bearish_result = max(
        min(max(-price_change, 0) / 5 * 100, 100),
        min(max(0.5 - close_location, 0) / 0.5 * 100, 100),
    )
    bullish_result = max(
        min(max(price_change, 0) / 5 * 100, 100),
        min(max(close_location - 0.5, 0) / 0.5 * 100, 100),
    )

    supply_entry = 0.7 * bearish_result + 0.3 * volume_strength
    demand_entry = 0.7 * bullish_result + 0.3 * volume_strength
    supply_absorption = (
        0.45 * volume_strength
        + 0.35 * min(max(close_location - 0.35, 0) / 0.45 * 100, 100)
        + 0.20 * min(max(metrics['lower_shadow_ratio'], 0) / 0.45 * 100, 100)
    )
    distribution = (
        0.45 * volume_strength
        + 0.35 * min(max(0.65 - close_location, 0) / 0.45 * 100, 100)
        + 0.20 * min(max(metrics['upper_shadow_ratio'], 0) / 0.45 * 100, 100)
    )
    no_supply = 100 - min(max((metrics['volume_ma20_ratio'] or 1) - 0.65, 0) / 0.7 * 100, 100)
    no_demand = no_supply

    if structure == '上涨趋势' and zone.get('type') == 'trend_pullback':
        no_supply = max(no_supply, 65 if vpa['type'] == 'shrink_pullback' else 0)
    if structure == '下降趋势':
        no_demand = max(no_demand, 60 if vpa['type'] in ('shrink', 'shrink_pullback') else 0)

    return {
        'supply_entry': round(min(max(supply_entry, 0), 100), 1),
        'demand_entry': round(min(max(demand_entry, 0), 100), 1),
        'supply_absorption': round(min(max(supply_absorption, 0), 100), 1),
        'distribution': round(min(max(distribution, 0), 100), 1),
        'no_supply': round(min(max(no_supply, 0), 100), 1),
        'no_demand': round(min(max(no_demand, 0), 100), 1),
    }


def _status_for_idx(end: int, total: int) -> str:
    # 纯函数只能确定当日正在发生；最后一根默认候选，历史点可作为 confirmed。
    return 'candidate' if end >= total - 1 else 'confirmed'


def _is_low_or_decline_context(structure: str, stage: str, zone: Dict) -> bool:
    """恐慌滞跌只能在低位、下降或支撑附近解释为 bullish 供需候选。"""
    stage_text = stage or ''
    if zone.get('type') == 'near_resistance':
        return False
    if structure == '下降趋势' or zone.get('type') == 'near_support':
        return True
    return any(token in stage_text for token in ('底', '低位', '末端', '超跌', '调整'))


def _is_high_or_up_context(structure: str, stage: str, zone: Dict) -> bool:
    """高潮滞涨只在高位、上涨或压力附近解释为 bearish 供需候选。"""
    stage_text = stage or ''
    if zone.get('type') == 'near_support':
        return False
    if structure == '上涨趋势' or zone.get('type') == 'near_resistance':
        return True
    return any(token in stage_text for token in ('顶', '高位', '加速', '波峰'))


def _trading_direction(wave_context: Dict) -> str:
    trading_wave = (wave_context or {}).get('trading_wave') or {}
    return str(trading_wave.get('direction') or '')


def _trading_state(wave_context: Dict) -> str:
    return str((wave_context or {}).get('trading_state') or '')


def _is_up_trading_wave(wave_context: Dict) -> bool:
    return _trading_direction(wave_context) == 'up'


def _is_down_trading_wave(wave_context: Dict) -> bool:
    return _trading_direction(wave_context) == 'down'


def _is_pullback_trading_state(wave_context: Dict) -> bool:
    state = _trading_state(wave_context)
    return '下降波段/回调' in state or '回调' in state


def _is_countertrend_bounce(wave_context: Dict) -> bool:
    state = _trading_state(wave_context)
    return '反弹波' in state


def _point_priority(point_type: str, direction: str, confidence: float,
                    zone: Dict, vpa: Dict, wave_context: Optional[Dict]) -> Dict:
    """给供需转换点做展示分层。

    P0.2 仍然只输出供需点，不输出买卖点。这里的分层只解决展示/后续消费的
    噪音问题：

    - core：核心供需点，位置、量价和当前交易波段较匹配；
    - watch：需要关注，但证据或波段上下文不完整；
    - weak：背景提示，默认不应在复盘页抢占注意力。
    """
    # confidence 是供需证据强弱；priority_score 是展示优先级，不能简单等同。
    # 否则历史图上所有高置信点都会变成 core，无法帮助复盘页排序注意力。
    score = float(confidence or 0) * 0.62
    reasons: List[str] = []
    zone_type = zone.get('type')
    vpa_type = vpa.get('type')
    trading_direction = _trading_direction(wave_context or {})

    if point_type in ('failed_breakout', 'failed_breakdown', 'panic_stagnation', 'climax_stagnation'):
        score += 12
        reasons.append('关键供需转换类型')
    elif point_type in ('upward_breakout', 'downward_breakdown'):
        score += 8
        reasons.append('突破/跌破类型')
    elif point_type in ('bullish_continuation', 'bearish_continuation'):
        score += 4
        reasons.append('中继类型')

    if zone_type in ('near_resistance', 'near_support', 'trend_pullback'):
        score += 8
        reasons.append('处在关键位置')
    elif zone_type in ('trend_body', 'downtrend'):
        score -= 4
        reasons.append('位置证据较弱')
    elif zone_type in ('mid_range', 'unknown'):
        score -= 10
        reasons.append('未到清晰关键位置')

    if vpa_type in ('panic_stagnation', 'climax_stagnation', 'volume_down', 'volume_up'):
        score += 8
        reasons.append('量价行为突出')
    elif vpa_type in ('shrink_pullback', 'shrink', 'dry_volume'):
        score += 3
        reasons.append('量能行为可参考')
    else:
        score -= 8
        reasons.append('量价行为不突出')

    continuation_types = {'bullish_continuation', 'bearish_continuation'}
    breakout_types = {'upward_breakout', 'downward_breakdown'}
    reversal_types = {
        'failed_breakout',
        'failed_breakdown',
        'panic_stagnation',
        'climax_stagnation',
        'bullish_reversal',
        'bearish_reversal',
    }
    point_direction = 'up' if direction == 'bullish' else 'down' if direction == 'bearish' else ''
    if trading_direction in ('up', 'down') and point_direction:
        is_same_direction = trading_direction == point_direction
        if point_type in continuation_types or point_type in breakout_types:
            if is_same_direction:
                score += 6
                reasons.append('当前交易波段顺向')
            else:
                score -= 10
                reasons.append('当前交易波段逆向')
        elif point_type in reversal_types:
            if is_same_direction:
                score += 2
                reasons.append('当前交易波段延续验证')
            else:
                score += 8
                reasons.append('当前交易波段转折/衰竭候选')

    score = round(max(0, min(score, 100)), 1)
    if score >= 78:
        tier = 'core'
        display_level = 'primary'
    elif score >= 62:
        tier = 'watch'
        display_level = 'secondary'
    else:
        tier = 'weak'
        display_level = 'muted'

    return {
        'priority_score': score,
        'tier': tier,
        'display_level': display_level,
        'priority_reasons': reasons,
    }


def _point(point_type: str, direction: str, *, rows: List[Dict], end: int,
           structure: str, stage: str, zone: Dict, vpa: Dict, evidence: Dict,
           confidence: float, reason: str, invalidations: Optional[List[str]] = None,
           wave_context: Optional[Dict] = None) -> Dict:
    confidence = round(max(0, min(confidence, 100)), 1)
    priority = _point_priority(point_type, direction, confidence, zone, vpa, wave_context)
    return {
        'idx': end,
        'date': str(rows[end].get('date', '')),
        'type': point_type,
        'direction': direction,
        'status': _status_for_idx(end, len(rows)),
        'confidence': confidence,
        **priority,
        'structure': structure,
        'stage': stage,
        'trading_wave': (wave_context or {}).get('trading_wave'),
        'trading_state': (wave_context or {}).get('trading_state'),
        'anchor': zone.get('anchor'),
        'evidence': {
            'volume_price_action': vpa.get('type'),
            'price_change_pct': vpa.get('price_change_pct'),
            'day_volume_ratio': vpa.get('day_volume_ratio'),
            'volume_ma5_ratio': vpa.get('volume_ma5_ratio'),
            'volume_ma20_ratio': vpa.get('volume_ma20_ratio'),
            'volume_percentile': vpa.get('volume_percentile'),
            'close_location': vpa.get('close_location'),
            **evidence,
        },
        'invalidations': invalidations or [],
        'reason': reason,
        'is_trade_decision': False,
    }


def _resolve_conflicts(points: List[Dict]) -> List[Dict]:
    if len(points) <= 1:
        return points
    bearish = [p for p in points if p['direction'] == 'bearish']
    bullish = [p for p in points if p['direction'] == 'bullish']
    if bearish and bullish:
        best_bear = max(bearish, key=lambda p: p.get('priority_score', p['confidence']))
        best_bull = max(bullish, key=lambda p: p.get('priority_score', p['confidence']))
        # bearish 风险证据明显时优先阻断看多供需点。
        if best_bear.get('priority_score', best_bear['confidence']) >= best_bull.get('priority_score', best_bull['confidence']) - 10:
            return [best_bear]
    return [max(points, key=lambda p: p.get('priority_score', p['confidence']))]


def _tier_counts(points: List[Dict]) -> Dict[str, int]:
    return {
        'core': sum(1 for point in points if point.get('tier') == 'core'),
        'watch': sum(1 for point in points if point.get('tier') == 'watch'),
        'weak': sum(1 for point in points if point.get('tier') == 'weak'),
        'total': len(points),
    }


def detect_supply_demand_keypoints(
    klines: Iterable[Dict],
    *,
    asset_type: str = 'stock',
    end_idx: int = -1,
    structure: str = '',
    stage: str = '',
    pure_keypoints: Optional[Dict] = None,
    wave_context: Optional[Dict] = None,
) -> Dict:
    """识别 3L 供需格局转换关键点。

    Returns:
        {
          "version": "supply-demand-keypoint-v1",
          "transition_points": [...],
          "is_trade_decision": false
        }
    """
    rows = _normalize_klines(klines)
    if len(rows) < MIN_BARS:
        return {
            'version': VERSION,
            'asset_type': asset_type,
            'status': 'unavailable',
            'reason': f'至少需要 {MIN_BARS} 根 K 线',
            'transition_points': [],
            'is_trade_decision': False,
        }

    end = end_idx if end_idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    closes = [_safe_float(r.get('close')) for r in rows[:end + 1]]
    highs = [_safe_float(r.get('high')) for r in rows[:end + 1]]
    lows = [_safe_float(r.get('low')) for r in rows[:end + 1]]
    volumes = [_volume(r) for r in rows[:end + 1]]
    opens = [_safe_float(r.get('open'), _safe_float(r.get('close'))) for r in rows[:end + 1]]
    resolved_structure = structure or get_structure(closes)
    resolved_stage = stage or get_stage(
        closes,
        structure=resolved_structure,
        highs=highs,
        lows=lows,
        volumes=volumes,
        opens_p=opens,
    )
    resolved_wave_context = wave_context or judge_wave_structure(rows[:end + 1], asset_type=asset_type)
    pure = pure_keypoints or detect_pure_keypoints(rows, asset_type=asset_type, end_idx=end)
    pure_points = pure.get('points') or []
    position_context = detect_structure_position_context(
        rows,
        idx=end,
        structure=resolved_structure,
        stage=resolved_stage,
        reference_points=pure_points,
    )
    resolved_stage = position_context.get('stage') or resolved_stage
    zone = position_context.get('current_zone') or {'type': 'unknown', 'anchor': None}
    metrics = _bar_metrics(rows, end)
    vpa = _detect_volume_price_action(metrics, pure_points, end)
    evidence = _score_evidence(resolved_structure, zone, vpa, metrics)

    points: List[Dict] = []
    zone_type = zone.get('type')
    vpa_type = vpa.get('type')
    price_change = metrics['price_change_pct']
    close_location = metrics['close_location']

    if zone_type == 'near_resistance':
        if vpa_type == 'volume_up' and close_location >= 0.58:
            points.append(_point(
                'upward_breakout', 'bullish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=55 + min(evidence['demand_entry'], 35),
                reason='压力位附近放量上涨并收在相对高位，需求尝试打破供应区',
                invalidations=['后续跌回压力位下方且放量转弱，则突破失效'],
                wave_context=resolved_wave_context,
            ))
        elif vpa_type in ('volume_down', 'climax_stagnation', 'panic_stagnation') or price_change <= -2:
            points.append(_point(
                'failed_breakout', 'bearish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=55 + min(evidence['supply_entry'], 35),
                reason='区间顶部或压力位附近放量转弱，需求突破失败；高位巨量长下影也不能按恐慌低吸解释',
                invalidations=['后续放量收复压力位，则突破失败失效'],
                wave_context=resolved_wave_context,
            ))

    if zone_type == 'near_support':
        if price_change <= -1.5 and close_location <= 0.45:
            points.append(_point(
                'downward_breakdown', 'bearish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=50 + min(evidence['supply_entry'], 40),
                reason='支撑位附近收弱并跌破倾向明显，供应占优或需求撤退',
                invalidations=['后续快速收回支撑并放量承接，则跌破失效'],
                wave_context=resolved_wave_context,
            ))
        elif vpa_type == 'panic_stagnation' or (price_change < 0 and close_location >= 0.55):
            points.append(_point(
                'failed_breakdown', 'bullish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=50 + min(evidence['supply_absorption'], 40),
                reason='支撑位附近下探后收回，供应跌破失败并出现承接',
                invalidations=['后续再度放量跌破支撑，则承接失败'],
                wave_context=resolved_wave_context,
            ))

    if resolved_structure == '上涨趋势':
        if (
            zone_type == 'trend_pullback'
            and vpa_type == 'shrink_pullback'
            and evidence['no_supply'] >= 55
            and not _is_down_trading_wave(resolved_wave_context)
        ):
            points.append(_point(
                'bullish_continuation', 'bullish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=55 + min(evidence['no_supply'], 35),
                reason='上涨趋势中缩量回踩且未破坏关键支撑，供应不足，原上升格局延续',
                invalidations=['后续放量跌破回踩支撑，则中继失效'],
                wave_context=resolved_wave_context,
            ))
        elif vpa_type in ('climax_stagnation', 'volume_down') and zone_type in ('trend_body', 'near_resistance'):
            points.append(_point(
                'bearish_reversal', 'bearish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=50 + min(max(evidence['distribution'], evidence['supply_entry']), 40),
                reason='上涨趋势中出现放量滞涨或放量转弱，需求衰竭后供应进入',
                invalidations=['后续放量新高并收强，则转弱失效'],
                wave_context=resolved_wave_context,
            ))

    if resolved_structure == '下降趋势':
        if (
            vpa_type in ('shrink', 'shrink_pullback')
            and evidence['no_demand'] >= 55
            and not _is_up_trading_wave(resolved_wave_context)
        ):
            points.append(_point(
                'bearish_continuation', 'bearish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=55 + min(evidence['no_demand'], 35),
                reason='下降趋势中缩量反弹或弱整理，需求不足，原下降格局延续',
                invalidations=['后续放量收复关键压力并形成需求进入，则下跌中继失效'],
                wave_context=resolved_wave_context,
            ))
        if vpa_type == 'panic_stagnation' and evidence['supply_absorption'] >= 50:
            points.append(_point(
                'panic_stagnation', 'bullish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=55 + min(evidence['supply_absorption'], 35),
                reason='下降或调整末端出现天量滞跌，供应集中释放并被需求承接',
                invalidations=['后续继续放量有效创新低，则恐慌滞跌失效'],
                wave_context=resolved_wave_context,
            ))
        elif (
            price_change >= 2
            and close_location >= 0.65
            and evidence['demand_entry'] >= 55
            and not _is_down_trading_wave(resolved_wave_context)
        ):
            points.append(_point(
                'bullish_reversal', 'bullish',
                rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
                zone=zone, vpa=vpa, evidence=evidence,
                confidence=50 + min(evidence['demand_entry'], 40),
                reason='下降趋势中出现需求进入并收强，原供应占优格局开始改变',
                invalidations=['后续跌回反转 K 线低点，则反转失效'],
                wave_context=resolved_wave_context,
            ))

    if (
        vpa_type == 'panic_stagnation'
        and _is_low_or_decline_context(resolved_structure, resolved_stage, zone)
        and not _is_up_trading_wave(resolved_wave_context)
    ):
        points.append(_point(
            'panic_stagnation', 'bullish',
            rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
            zone=zone, vpa=vpa, evidence=evidence,
            confidence=50 + min(evidence['supply_absorption'], 40),
            reason='低位或调整中出现天量滞跌，供应释放但下跌推进效率下降',
            invalidations=['后续继续放量有效创新低，则恐慌滞跌失效'],
            wave_context=resolved_wave_context,
        ))

    if vpa_type == 'climax_stagnation' and _is_high_or_up_context(resolved_structure, resolved_stage, zone):
        points.append(_point(
            'climax_stagnation', 'bearish',
            rows=rows, end=end, structure=resolved_structure, stage=resolved_stage,
            zone=zone, vpa=vpa, evidence=evidence,
            confidence=50 + min(evidence['distribution'], 40),
            reason='高位或上涨中出现天量滞涨，需求推进效率下降并有派发风险',
            invalidations=['后续继续放量有效突破并站稳，则高潮滞涨失效'],
            wave_context=resolved_wave_context,
        ))

    points = _resolve_conflicts(points)
    return {
        'version': VERSION,
        'asset_type': asset_type,
        'status': 'ok',
        'date': str(rows[end].get('date', '')),
        'structure': resolved_structure,
        'stage': resolved_stage,
        'raw_stage': position_context.get('raw_stage'),
        'stage_position_normalization': position_context.get('normalization'),
        'wave_context': {
            'structure': resolved_wave_context.get('structure'),
            'phase': resolved_wave_context.get('phase'),
            'trading_wave': resolved_wave_context.get('trading_wave'),
            'trading_state': resolved_wave_context.get('trading_state'),
            'thresholds': resolved_wave_context.get('thresholds'),
        },
        'current_zone': zone,
        'volume_price_action': vpa,
        'transition_points': points,
        'transition_point_tiers': _tier_counts(points),
        'is_trade_decision': False,
        'definitions': {
            'transition_points': '突破、跌破、反转、中继、恐慌滞跌、高潮滞涨等供需格局点；不直接等于买卖点',
            'confidence': '供需证据强弱，不等于胜率',
        },
    }
