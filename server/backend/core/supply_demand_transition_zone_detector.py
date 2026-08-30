"""3L 多日供需转换区间识别器。

P0.3 实验旁路：消费波段结构与单日供需关键点，识别“下降→上升”、
“上升→下降”的多日转换区间。它不输出买卖点，也不接入生产页面。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from backend.core.supply_demand_keypoint_detector import detect_supply_demand_keypoints
from backend.core.wave_structure_detector import judge_wave_structure


VERSION = 'supply-demand-transition-zone-v1'
MIN_BARS = 20


BULLISH_POINT_TYPES = {
    'failed_breakdown',
    'bullish_reversal',
    'bullish_continuation',
    'upward_breakout',
    'panic_stagnation',
}

BEARISH_POINT_TYPES = {
    'failed_breakout',
    'bearish_reversal',
    'bearish_continuation',
    'downward_breakdown',
    'climax_stagnation',
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
    normalized: List[Dict] = []
    for row in rows:
        date = str(row.get('date', row.get('trade_date', '')))
        open_ = _safe_float(row.get('open'), _safe_float(row.get('close')))
        high = _safe_float(row.get('high'), _safe_float(row.get('close')))
        low = _safe_float(row.get('low'), _safe_float(row.get('close')))
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


def _avg(values: List[float]) -> Optional[float]:
    clean = [value for value in values if value > 0]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _round(value: Optional[float], digits: int = 2):
    return round(value, digits) if value is not None else None


def _state_idx(state: Dict) -> int:
    return int(state.get('idx', 0))


def _state_direction(state: Dict) -> str:
    wave = state.get('trading_wave') or {}
    direction = wave.get('direction') or state.get('direction') or 'flat'
    return direction if direction in ('up', 'down', 'flat') else 'flat'


def _rolling_wave_states(rows: List[Dict], asset_type: str, end: int) -> List[Dict]:
    states: List[Dict] = []
    for idx in range(MIN_BARS - 1, end + 1):
        state = judge_wave_structure(rows[:idx + 1], asset_type=asset_type)
        states.append({
            'idx': idx,
            'date': rows[idx]['date'],
            'structure': state.get('structure'),
            'phase': state.get('phase'),
            'trading_wave': state.get('trading_wave') or {},
            'trading_state': state.get('trading_state'),
            'thresholds': state.get('thresholds') or {},
        })
    return states


def _rolling_supply_demand_results(rows: List[Dict], asset_type: str, wave_states: List[Dict]) -> Dict[int, Dict]:
    by_idx: Dict[int, Dict] = {}
    waves_by_idx = {_state_idx(state): state for state in wave_states}
    for idx in range(MIN_BARS - 1, len(rows)):
        if idx not in waves_by_idx:
            continue
        by_idx[idx] = detect_supply_demand_keypoints(
            rows,
            asset_type=asset_type,
            end_idx=idx,
            wave_context=waves_by_idx[idx],
        )
    return by_idx


def _normalize_wave_states(wave_states: List[Dict], rows: List[Dict], end: int) -> List[Dict]:
    normalized: List[Dict] = []
    for order, state in enumerate(wave_states or []):
        idx = int(state.get('idx', order))
        if idx < 0 or idx > end or idx >= len(rows):
            continue
        item = dict(state)
        item['idx'] = idx
        item.setdefault('date', rows[idx]['date'])
        item.setdefault('trading_wave', {'direction': _state_direction(item)})
        normalized.append(item)
    normalized.sort(key=_state_idx)
    return normalized


def _segments(wave_states: List[Dict]) -> List[Dict]:
    result: List[Dict] = []
    active: Optional[Dict] = None
    for state in wave_states:
        direction = _state_direction(state)
        if direction == 'flat':
            continue
        idx = _state_idx(state)
        if active is None or direction != active['direction']:
            if active:
                result.append(active)
            active = {
                'direction': direction,
                'start_idx': idx,
                'end_idx': idx,
                'start_date': state.get('date'),
                'end_date': state.get('date'),
                'states': [state],
            }
        else:
            active['end_idx'] = idx
            active['end_date'] = state.get('date')
            active['states'].append(state)
    if active:
        result.append(active)
    return result


def _segment_change(rows: List[Dict], segment: Dict) -> float:
    start = max(0, int(segment['start_idx']))
    end = min(len(rows) - 1, int(segment['end_idx']))
    if start >= len(rows) or end >= len(rows):
        return 0.0
    return _pct_change(rows[end]['close'], rows[start]['close'])


def _segment_duration(segment: Dict) -> int:
    return int(segment['end_idx']) - int(segment['start_idx']) + 1


def _point_direction_matches(point: Dict, direction: str) -> bool:
    if direction == 'bullish':
        return point.get('direction') == 'bullish' or point.get('type') in BULLISH_POINT_TYPES
    return point.get('direction') == 'bearish' or point.get('type') in BEARISH_POINT_TYPES


def _collect_points(
    supply_demand_results: Dict[int, Dict],
    start_idx: int,
    end_idx: int,
    direction: str,
) -> Tuple[List[Dict], List[Dict]]:
    matched: List[Dict] = []
    counter: List[Dict] = []
    for idx in range(start_idx, end_idx + 1):
        result = supply_demand_results.get(idx) or {}
        for point in result.get('transition_points', []):
            compact = {
                'idx': point.get('idx', idx),
                'date': point.get('date'),
                'type': point.get('type'),
                'direction': point.get('direction'),
                'tier': point.get('tier'),
                'confidence': point.get('confidence'),
                'reason': point.get('reason'),
            }
            if _point_direction_matches(point, direction):
                matched.append(compact)
            else:
                counter.append(compact)
    return matched, counter


def _volume_evidence(rows: List[Dict], start_idx: int, end_idx: int) -> Dict:
    pre_start = max(0, start_idx - 10)
    pre_vol = _avg([rows[idx]['volume'] for idx in range(pre_start, start_idx)])
    zone_vol = _avg([rows[idx]['volume'] for idx in range(start_idx, end_idx + 1)])
    return {
        'avg_volume': _round(zone_vol, 2),
        'pre10_avg_volume': _round(pre_vol, 2),
        'volume_ratio_vs_pre10': _round(zone_vol / pre_vol, 2) if pre_vol and zone_vol else None,
    }


def _build_zone(
    rows: List[Dict],
    prev_segment: Dict,
    curr_segment: Dict,
    next_segment: Optional[Dict],
    supply_demand_results: Dict[int, Dict],
    *,
    pre_bars: int,
    post_bars: int,
) -> Dict:
    transition_idx = int(curr_segment['start_idx'])
    start_idx = max(0, transition_idx - pre_bars)
    end_idx = min(len(rows) - 1, transition_idx + post_bars - 1)
    direction = 'bullish' if prev_segment['direction'] == 'down' and curr_segment['direction'] == 'up' else 'bearish'
    zone_type = 'down_to_up' if direction == 'bullish' else 'up_to_down'
    matched_points, counter_points = _collect_points(supply_demand_results, start_idx, end_idx, direction)
    prior_change = _segment_change(rows, prev_segment)
    new_change = _pct_change(rows[min(end_idx, int(curr_segment['end_idx']))]['close'], rows[transition_idx]['close'])
    zone_change = _pct_change(rows[end_idx]['close'], rows[start_idx]['close'])
    curr_duration = _segment_duration(curr_segment)
    prev_duration = _segment_duration(prev_segment)
    vol = _volume_evidence(rows, start_idx, end_idx)

    confidence = 42
    reasons = ['交易波段方向发生切换']
    if prev_duration >= 3:
        confidence += 10
        reasons.append(f"前一{_label_wave(prev_segment['direction'])}持续 {prev_duration} 天")
    if curr_duration >= 2:
        confidence += 14
        reasons.append(f"新{_label_wave(curr_segment['direction'])}已持续 {curr_duration} 天")
    if matched_points:
        core_count = sum(1 for point in matched_points if point.get('tier') == 'core')
        confidence += 14 + min(core_count * 4, 8)
        reasons.append(f"区间内有 {len(matched_points)} 个同向供需格局点")
    if direction == 'bullish' and zone_change > 0:
        confidence += 8
        reasons.append('区间价格由弱转强')
    if direction == 'bearish' and zone_change < 0:
        confidence += 8
        reasons.append('区间价格由强转弱')
    if vol.get('volume_ratio_vs_pre10') and vol['volume_ratio_vs_pre10'] >= 1.15:
        confidence += 6
        reasons.append('区间量能高于前 10 日均量')
    if counter_points:
        confidence -= min(len(counter_points) * 4, 12)
        reasons.append(f"区间内存在 {len(counter_points)} 个反向供需点，需要降权")

    if prev_duration < 2:
        status = 'failed'
        reasons.append('前一波段不足 2 天，属于噪声反向后的恢复，暂按失败切换过滤')
    elif curr_duration < 2 and next_segment:
        status = 'failed'
        reasons.append('新波段只持续 1 天即反向，暂按切换失败处理')
    elif curr_duration < 2 and not next_segment:
        status = 'forming'
        reasons.append('最新波段刚开始，先标记形成中')
    elif confidence >= 68:
        status = 'confirmed'
    else:
        status = 'forming'
        reasons.append('证据尚不足以确认，只作为形成中区间')

    bounded_confidence = max(0, min(100, round(confidence)))
    if status == 'forming' and not next_segment:
        tier = 'watch'
        display_level = 'secondary'
    elif status == 'failed' or bounded_confidence < 60:
        tier = 'weak'
        display_level = 'muted'
    elif status == 'confirmed' and bounded_confidence >= 78:
        tier = 'core'
        display_level = 'primary'
    else:
        tier = 'watch'
        display_level = 'secondary'

    return {
        'version': VERSION,
        'type': zone_type,
        'direction': direction,
        'status': status,
        'tier': tier,
        'display_level': display_level,
        'start_idx': start_idx,
        'end_idx': end_idx,
        'start_date': rows[start_idx]['date'],
        'end_date': rows[end_idx]['date'],
        'pivot_idx': transition_idx,
        'pivot_date': rows[transition_idx]['date'],
        'from_wave': prev_segment['direction'],
        'to_wave': curr_segment['direction'],
        'confidence': bounded_confidence,
        'is_trade_decision': False,
        'evidence': {
            'previous_wave_duration': prev_duration,
            'current_wave_duration': curr_duration,
            'previous_wave_change_pct': _round(prior_change),
            'early_new_wave_change_pct': _round(new_change),
            'zone_change_pct': _round(zone_change),
            'volume': vol,
            'matched_supply_demand_points': matched_points,
            'counter_supply_demand_points': counter_points,
        },
        'reasons': reasons,
    }


def _label_wave(direction: str) -> str:
    return '上涨波段' if direction == 'up' else '下降波段' if direction == 'down' else '横向波段'


def detect_transition_zones(
    klines: Iterable[Dict],
    *,
    asset_type: str = 'stock',
    end_idx: int = -1,
    wave_states: Optional[List[Dict]] = None,
    supply_demand_results: Optional[Dict[int, Dict]] = None,
    pre_bars: int = 2,
    post_bars: int = 3,
    include_failed: bool = False,
) -> Dict:
    """识别多日供需转换区间。

    返回的 zones 只描述波段供需切换窗口，不是买卖点。
    """
    rows = _normalize_klines(klines)
    if len(rows) < MIN_BARS:
        return {
            'version': VERSION,
            'asset_type': asset_type,
            'status': 'unavailable',
            'reason': f'至少需要 {MIN_BARS} 根有效 K 线',
            'zones': [],
            'latest_zone': None,
            'is_trade_decision': False,
        }

    end = end_idx if end_idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    scoped_rows = rows[:end + 1]
    states = (
        _normalize_wave_states(wave_states or [], scoped_rows, end)
        if wave_states is not None
        else _rolling_wave_states(scoped_rows, asset_type, end)
    )
    if not states:
        return {
            'version': VERSION,
            'asset_type': asset_type,
            'status': 'unavailable',
            'reason': '没有可用波段状态',
            'zones': [],
            'latest_zone': None,
            'is_trade_decision': False,
        }

    sd_results = supply_demand_results if supply_demand_results is not None else _rolling_supply_demand_results(
        scoped_rows,
        asset_type,
        states,
    )
    segments = _segments(states)
    zones: List[Dict] = []
    for pos in range(1, len(segments)):
        prev_segment = segments[pos - 1]
        curr_segment = segments[pos]
        pair = (prev_segment['direction'], curr_segment['direction'])
        if pair not in (('down', 'up'), ('up', 'down')):
            continue
        if (
            _segment_duration(prev_segment) < 2
            and pos >= 2
            and segments[pos - 2]['direction'] == curr_segment['direction']
        ):
            continue
        zone = _build_zone(
            scoped_rows,
            prev_segment,
            curr_segment,
            segments[pos + 1] if pos + 1 < len(segments) else None,
            sd_results,
            pre_bars=max(0, pre_bars),
            post_bars=max(1, post_bars),
        )
        if zone.get('status') == 'failed' and not include_failed:
            continue
        zones.append(zone)

    return {
        'version': VERSION,
        'asset_type': asset_type,
        'status': 'ok',
        'date': scoped_rows[-1]['date'],
        'zones': zones,
        'latest_zone': zones[-1] if zones else None,
        'segments': [
            {
                'direction': segment['direction'],
                'start_idx': segment['start_idx'],
                'end_idx': segment['end_idx'],
                'start_date': segment['start_date'],
                'end_date': segment['end_date'],
            }
            for segment in segments
        ],
        'is_trade_decision': False,
    }
