"""3L 结构化供需事件检测器。

P0.4-B 实验旁路：把 P0.2 `transition_points` 规范化为
`SupplyDemandEvent`。事件只描述供需行为，不输出买卖点。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from backend.core.supply_demand_keypoint_detector import detect_supply_demand_keypoints


VERSION = 'supply-demand-event-v1'
MIN_BARS = 20


EVENT_DEFINITIONS: Dict[str, Dict] = {
    'upward_breakout': {
        'event_type': 'breakout',
        'event_label': '向上突破',
        'direction': 'bullish',
        'dominant_force': 'demand',
        'trade_implication': 'candidate_right_buy_context',
        'meaning': '需求放量打破压力或平台，原供需平衡/供应压制被需求尝试改变',
        'source_definition': '突破点是趋势形成点；突破买点需要放量突破平台。',
    },
    'downward_breakdown': {
        'event_type': 'breakout',
        'event_label': '向下跌破',
        'direction': 'bearish',
        'dominant_force': 'supply',
        'trade_implication': 'risk_or_sell_context',
        'meaning': '供应打破支撑或平台，原供需平衡/需求承接被供应尝试改变',
        'source_definition': '向下突破前低或支撑，说明供应开始占优。',
    },
    'failed_breakout': {
        'event_type': 'failure',
        'event_label': '突破失败',
        'direction': 'bearish',
        'dominant_force': 'supply',
        'trade_implication': 'risk_or_sell_context',
        'meaning': '压力/区间顶部附近需求突破失败，供应重新占优或需求不足',
        'source_definition': '关键位突破只有成功或失败；失败后容易反向。',
    },
    'failed_breakdown': {
        'event_type': 'failure',
        'event_label': '跌破失败',
        'direction': 'bullish',
        'dominant_force': 'demand',
        'trade_implication': 'candidate_support_context',
        'meaning': '支撑/区间底部附近供应跌破失败，需求出现承接',
        'source_definition': '关键位跌破失败常体现支撑和承接。',
    },
    'bullish_continuation': {
        'event_type': 'continuation',
        'event_label': '上涨中继',
        'direction': 'bullish',
        'dominant_force': 'demand',
        'trade_implication': 'candidate_continuation_context',
        'meaning': '回调力量无法改变需求占优格局，属于顺大势逆小势的中继位置',
        'source_definition': '中继点是无法改变原有趋势的量价行为，上涨中继常见于缩量回踩。',
    },
    'bearish_continuation': {
        'event_type': 'continuation',
        'event_label': '下跌中继',
        'direction': 'bearish',
        'dominant_force': 'supply',
        'trade_implication': 'avoid_or_sell_context',
        'meaning': '反弹力量无法改变供应占优格局，属于下跌趋势延续位置',
        'source_definition': '下跌中继是需求无法压倒供应，不是买点。',
    },
    'bullish_reversal': {
        'event_type': 'reversal',
        'event_label': '向上反转',
        'direction': 'bullish',
        'dominant_force': 'demand',
        'trade_implication': 'candidate_right_buy_context',
        'meaning': '需求出现并尝试压倒供应，原调整/下降走势出现弱转强',
        'source_definition': '转折点是右侧，需求出现压倒供应是弱转强转折点。',
    },
    'bearish_reversal': {
        'event_type': 'reversal',
        'event_label': '向下反转',
        'direction': 'bearish',
        'dominant_force': 'supply',
        'trade_implication': 'risk_or_sell_context',
        'meaning': '供应出现并尝试压倒需求，原上涨走势出现强转弱',
        'source_definition': '转折点是右侧，供应出现压倒需求是强转弱转折点。',
    },
    'panic_stagnation': {
        'event_type': 'exhaustion',
        'event_label': '恐慌滞跌',
        'direction': 'bullish',
        'dominant_force': 'supply_exhaustion',
        'trade_implication': 'candidate_left_buy_context',
        'meaning': '下跌末端天量滞跌，供应快速释放后趋于衰竭',
        'source_definition': '恐慌是快速衰竭；衰竭点是左侧，仍需需求确认。',
    },
    'climax_stagnation': {
        'event_type': 'exhaustion',
        'event_label': '高潮滞涨',
        'direction': 'bearish',
        'dominant_force': 'demand_exhaustion',
        'trade_implication': 'candidate_left_sell_context',
        'meaning': '上涨末端天量滞涨，需求透支后趋于衰竭',
        'source_definition': '高潮/放量滞涨常代表需求衰竭，是左侧风险点。',
    },
}


def _event_id(point: Dict) -> str:
    return f"{point.get('date', '')}:{point.get('type', 'unknown')}:{point.get('idx', '')}"


def _copy_context(value) -> Dict:
    return dict(value) if isinstance(value, dict) else {}


def _structure_context(result: Dict, point: Dict) -> Dict:
    return {
        'structure': point.get('structure') or result.get('structure'),
        'stage': point.get('stage') or result.get('stage'),
    }


def _position_context(result: Dict, point: Dict) -> Dict:
    zone = _copy_context(result.get('current_zone'))
    return {
        'zone_type': zone.get('type'),
        'zone_reason': zone.get('reason'),
        'range_position_pct': zone.get('range_position_pct'),
        'anchor': point.get('anchor') or zone.get('anchor'),
    }


def _wave_context(result: Dict, point: Dict) -> Dict:
    wave = _copy_context(result.get('wave_context'))
    return {
        'structure': wave.get('structure'),
        'phase': wave.get('phase'),
        'trading_wave': point.get('trading_wave') or wave.get('trading_wave'),
        'trading_state': point.get('trading_state') or wave.get('trading_state'),
        'thresholds': wave.get('thresholds'),
    }


def _volume_price_evidence(result: Dict, point: Dict) -> Dict:
    evidence = _copy_context(point.get('evidence'))
    vpa = _copy_context(result.get('volume_price_action'))
    return {
        'action_type': evidence.get('volume_price_action') or vpa.get('type'),
        'price_change_pct': evidence.get('price_change_pct') or vpa.get('price_change_pct'),
        'day_volume_ratio': evidence.get('day_volume_ratio') or vpa.get('day_volume_ratio'),
        'volume_ma5_ratio': evidence.get('volume_ma5_ratio') or vpa.get('volume_ma5_ratio'),
        'volume_ma20_ratio': evidence.get('volume_ma20_ratio') or vpa.get('volume_ma20_ratio'),
        'volume_percentile': evidence.get('volume_percentile') or vpa.get('volume_percentile'),
        'close_location': evidence.get('close_location') or vpa.get('close_location'),
        'upper_shadow_ratio': evidence.get('upper_shadow_ratio') or vpa.get('upper_shadow_ratio'),
        'lower_shadow_ratio': evidence.get('lower_shadow_ratio') or vpa.get('lower_shadow_ratio'),
    }


def _semantic_warnings(event: Dict) -> List[str]:
    warnings: List[str] = []
    subtype = event.get('subtype')
    structure = (event.get('structure_context') or {}).get('structure') or ''
    stage = (event.get('structure_context') or {}).get('stage') or ''
    zone_type = (event.get('position_context') or {}).get('zone_type')
    vpa = (event.get('volume_price_evidence') or {}).get('action_type')

    if structure == '区间震荡' and any(token in stage for token in ('中段', '中部')) and zone_type in ('near_resistance', 'near_support'):
        warnings.append('区间阶段为中段，但位置上下文接近支撑/压力，需统一阶段与位置口径')

    if subtype == 'bullish_continuation':
        if structure == '下降趋势':
            warnings.append('看多中继不能出现在下降趋势中')
        if zone_type not in ('trend_pullback', 'near_support'):
            warnings.append('看多中继需要回踩关键支撑/均线或区间底部')
        if vpa not in ('shrink_pullback', 'shrink', 'dry_volume'):
            warnings.append('看多中继需要缩量/量能收缩证据')
    elif subtype == 'bearish_continuation':
        if structure != '下降趋势':
            warnings.append('看空中继通常应在下降趋势或明确供应占优背景中解释')
        if vpa not in ('shrink_pullback', 'shrink', 'dry_volume'):
            warnings.append('看空中继需要无量反弹/需求不足证据')

    if subtype == 'panic_stagnation':
        low_or_decline = structure == '下降趋势' or any(token in stage for token in ('低', '底', '恐慌', '主跌', '调整'))
        if not low_or_decline:
            warnings.append('恐慌滞跌必须绑定低位/下跌末端/调整末端')
        if vpa != 'panic_stagnation':
            warnings.append('恐慌事件需要天量滞跌量价行为')
    elif subtype == 'climax_stagnation':
        high_or_up = structure == '上涨趋势' or any(token in stage for token in ('高', '顶', '加速', '波峰'))
        if not high_or_up:
            warnings.append('高潮滞涨必须绑定高位/上涨末端/加速段')
        if vpa != 'climax_stagnation':
            warnings.append('高潮事件需要天量滞涨量价行为')

    if subtype == 'failed_breakout' and zone_type not in ('near_resistance', 'trend_body'):
        warnings.append('突破失败应发生在压力/区间顶部附近')
    if subtype == 'failed_breakdown' and zone_type != 'near_support':
        warnings.append('跌破失败应发生在支撑/区间底部附近')
    return warnings


def _point_to_event(result: Dict, point: Dict) -> Dict:
    subtype = point.get('type') or 'unknown'
    definition = EVENT_DEFINITIONS.get(subtype, {})
    direction = definition.get('direction') or point.get('direction') or 'neutral'
    event = {
        'version': VERSION,
        'id': _event_id(point),
        'idx': point.get('idx'),
        'date': point.get('date') or result.get('date'),
        'event_type': definition.get('event_type', 'unknown'),
        'event_label': definition.get('event_label', subtype),
        'subtype': subtype,
        'direction': direction,
        'dominant_force': definition.get('dominant_force', 'unknown'),
        'status': point.get('status', 'candidate'),
        'confidence': point.get('confidence', 0),
        'tier': point.get('tier', 'weak'),
        'display_level': point.get('display_level', 'muted'),
        'priority_score': point.get('priority_score'),
        'priority_reasons': point.get('priority_reasons', []),
        'structure_context': _structure_context(result, point),
        'position_context': _position_context(result, point),
        'wave_context': _wave_context(result, point),
        'volume_price_evidence': _volume_price_evidence(result, point),
        'meaning': definition.get('meaning', point.get('reason', '')),
        'source_definition': definition.get('source_definition', ''),
        'invalidations': point.get('invalidations', []),
        'trade_implication': definition.get('trade_implication', 'observe'),
        'is_trade_decision': False,
        'legacy_point': {
            'type': point.get('type'),
            'direction': point.get('direction'),
            'reason': point.get('reason'),
        },
    }
    event['semantic_warnings'] = _semantic_warnings(event)
    event['definition_aligned'] = not event['semantic_warnings']
    return event


def _event_counts(events: List[Dict]) -> Dict:
    counts = {'total': len(events), 'core': 0, 'watch': 0, 'weak': 0}
    by_type: Dict[str, int] = {}
    for event in events:
        tier = event.get('tier') or 'weak'
        counts[tier] = counts.get(tier, 0) + 1
        event_type = event.get('event_type') or 'unknown'
        by_type[event_type] = by_type.get(event_type, 0) + 1
    counts['by_event_type'] = by_type
    return counts


def detect_supply_demand_events(
    klines: Iterable[Dict],
    *,
    asset_type: str = 'stock',
    end_idx: int = -1,
    structure: str = '',
    stage: str = '',
    supply_demand_result: Optional[Dict] = None,
    pure_keypoints: Optional[Dict] = None,
    wave_context: Optional[Dict] = None,
) -> Dict:
    """识别结构化供需事件。

    本函数是 P0.4-B 旁路适配层：默认调用 P0.2，再把旧点转换为事件。
    """
    result = supply_demand_result or detect_supply_demand_keypoints(
        klines,
        asset_type=asset_type,
        end_idx=end_idx,
        structure=structure,
        stage=stage,
        pure_keypoints=pure_keypoints,
        wave_context=wave_context,
    )
    if result.get('status') != 'ok':
        return {
            'version': VERSION,
            'asset_type': asset_type,
            'status': result.get('status', 'unavailable'),
            'reason': result.get('reason', '供需关键点不可用'),
            'events': [],
            'event_counts': _event_counts([]),
            'legacy_transition_points': result.get('transition_points', []),
            'is_trade_decision': False,
        }

    events = [_point_to_event(result, point) for point in result.get('transition_points', [])]
    return {
        'version': VERSION,
        'asset_type': result.get('asset_type', asset_type),
        'status': 'ok',
        'date': result.get('date'),
        'structure_context': {
            'structure': result.get('structure'),
            'stage': result.get('stage'),
        },
        'events': events,
        'event_counts': _event_counts(events),
        'legacy_transition_points': result.get('transition_points', []),
        'is_trade_decision': False,
        'definitions': {
            'events': '结构化供需事件：衰竭、转折、突破/跌破、失败、中继；不直接等于买卖点',
            'trade_implication': '交易含义只描述上下文，不能作为可执行买卖指令',
        },
    }
