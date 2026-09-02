"""3L 结构上下文识别器。

P0 实验旁路：聚合波段、结构/位置、供需事件，输出统一的 3L 结构上下文。
本模块不输出买卖点，不改变生产 `get_structure()` / `get_stage()`。
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

from backend.core.pure_keypoint_detector import detect_pure_keypoints
from backend.core.structure_position_context import detect_structure_position_context
from backend.core.supply_demand_event_detector import detect_supply_demand_events
from backend.core.wave_structure_detector import MIN_BARS, judge_wave_structure


VERSION = '3l-structure-context-v1'


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
    result: List[Dict] = []
    for row in rows:
        date = str(row.get('date', row.get('trade_date', '')))
        close = _safe_float(row.get('close'))
        high = _safe_float(row.get('high'), close)
        low = _safe_float(row.get('low'), close)
        open_ = _safe_float(row.get('open'), close)
        if not date or min(open_, high, low, close) <= 0:
            continue
        result.append({
            'date': date,
            'open': open_,
            'high': high,
            'low': low,
            'close': close,
            'volume': _safe_float(row.get('volume', row.get('vol', 0))),
        })
    return result


def _pct_change(current: float, base: float) -> float:
    return (current / base - 1) * 100 if base else 0.0


def _round(value: Optional[float], digits: int = 2):
    return round(value, digits) if value is not None else None


def _pivot_sequence_structure(pivots: List[Dict]) -> Dict:
    highs = [p for p in pivots if p.get('type') == 'high']
    lows = [p for p in pivots if p.get('type') == 'low']
    evidence: List[str] = []
    if len(highs) >= 2:
        previous, current = highs[-2], highs[-1]
        evidence.append(
            f"高点序列：{previous.get('date')} {previous.get('price')} → "
            f"{current.get('date')} {current.get('price')}"
        )
    if len(lows) >= 2:
        previous, current = lows[-2], lows[-1]
        evidence.append(
            f"低点序列：{previous.get('date')} {previous.get('price')} → "
            f"{current.get('date')} {current.get('price')}"
        )
    if len(highs) < 2 or len(lows) < 2:
        return {'structure': '', 'confidence': 0, 'evidence': evidence}

    high_rising = float(highs[-1]['price']) > float(highs[-2]['price'])
    low_rising = float(lows[-1]['price']) > float(lows[-2]['price'])
    high_falling = float(highs[-1]['price']) < float(highs[-2]['price'])
    low_falling = float(lows[-1]['price']) < float(lows[-2]['price'])

    if high_rising and low_rising:
        return {'structure': '上涨趋势', 'confidence': 78, 'evidence': evidence + ['高点抬高、低点抬高']}
    if high_falling and low_falling:
        return {'structure': '下降趋势', 'confidence': 78, 'evidence': evidence + ['高点降低、低点降低']}
    if low_rising and not high_rising:
        return {'structure': '区间震荡', 'confidence': 56, 'evidence': evidence + ['低点抬高但高点未突破，区间偏强']}
    if high_falling and not low_falling:
        return {'structure': '区间震荡', 'confidence': 56, 'evidence': evidence + ['高点降低但低点未跌破，区间偏弱']}
    return {'structure': '区间震荡', 'confidence': 52, 'evidence': evidence + ['高低点未形成同向趋势序列']}


def _resolve_structure(wave_result: Dict) -> Dict:
    pivot_view = _pivot_sequence_structure(wave_result.get('pivots') or [])
    if pivot_view.get('structure'):
        return {
            'structure': pivot_view['structure'],
            'confidence': pivot_view['confidence'],
            'evidence': pivot_view['evidence'],
            'source': 'pivot_sequence',
        }
    structure = wave_result.get('structure') or '未识别'
    confidence = 62 if structure in ('上涨趋势', '下降趋势') else 45
    return {
        'structure': structure if structure != '--' else '未识别',
        'confidence': confidence,
        'evidence': [wave_result.get('reason') or '波段结构结果作为首版兜底'],
        'source': 'wave_structure_fallback',
    }


def _event_types(events: List[Dict]) -> set[str]:
    return {str(event.get('subtype') or '') for event in events}


def _event_groups(events: List[Dict]) -> set[str]:
    return {str(event.get('event_type') or '') for event in events}


def _stage_for_context(structure: str, wave_result: Dict, events: List[Dict], position_context: Dict) -> Dict:
    trading_wave = wave_result.get('trading_wave') or {}
    trading_direction = trading_wave.get('direction')
    phase = wave_result.get('phase')
    active = wave_result.get('active_wave') or {}
    thresholds = wave_result.get('thresholds') or {}
    event_types = _event_types(events)
    event_groups = _event_groups(events)
    evidence: List[str] = []

    if structure == '区间震荡':
        stage = (position_context.get('stage') or '区间中段')
        return {
            'stage': stage,
            'confidence': 70 if stage in ('区间顶部', '区间底部') else 55,
            'evidence': [f"区间位置：{position_context.get('current_zone', {}).get('reason', '区间位置')}"],
        }

    if structure == '上涨趋势':
        if {'climax_stagnation', 'bearish_reversal', 'failed_breakout'} & event_types:
            return {'stage': '逆转候选', 'confidence': 72, 'evidence': ['上涨结构中出现需求衰竭/供应进入事件']}
        if 'exhaustion' in event_groups and 'climax_stagnation' in event_types:
            return {'stage': '加速/高潮', 'confidence': 70, 'evidence': ['上涨结构中出现高潮衰竭']}
        change = abs(float(active.get('change_pct') or 0))
        min_impulse = float(thresholds.get('min_impulse_pct') or 0)
        if trading_direction == 'down' or phase == 'pullback':
            return {'stage': '回调', 'confidence': 68, 'evidence': ['上涨结构中的下降交易波段/回调']}
        if min_impulse and change >= min_impulse * 2.5:
            evidence.append(f"主导上涨波段涨幅 {round(change, 2)}%，显著超过最小波段阈值")
            return {'stage': '加速', 'confidence': 66, 'evidence': evidence}
        if phase == 'impulse':
            return {'stage': '发展', 'confidence': 68, 'evidence': ['主导上涨波段仍在推进']}
        return {'stage': '形成', 'confidence': 58, 'evidence': ['上涨结构形成中']}

    if structure == '下降趋势':
        if 'panic_stagnation' in event_types:
            return {'stage': '恐慌/供应衰竭', 'confidence': 75, 'evidence': ['下降末端出现恐慌滞跌/供应衰竭事件']}
        if {'bullish_reversal', 'failed_breakdown'} & event_types:
            return {'stage': '逆转候选', 'confidence': 70, 'evidence': ['下降结构中出现需求进入或跌破失败']}
        if trading_direction == 'up' or phase == 'countertrend_bounce':
            return {'stage': '反弹', 'confidence': 64, 'evidence': ['下降结构中的上涨交易波段/反弹']}
        change = abs(float(active.get('change_pct') or 0))
        min_impulse = float(thresholds.get('min_impulse_pct') or 0)
        if min_impulse and change >= min_impulse * 1.5:
            return {'stage': '发展', 'confidence': 70, 'evidence': ['下降推动波幅度充分，供应占优延续']}
        return {'stage': '形成', 'confidence': 60, 'evidence': ['下降结构形成中']}

    return {'stage': '未识别', 'confidence': 0, 'evidence': ['结构未识别，无法判定阶段']}


def _regime(structure: str) -> str:
    if structure == '上涨趋势':
        return 'demand_dominant'
    if structure == '下降趋势':
        return 'supply_dominant'
    if structure == '区间震荡':
        return 'balance'
    return 'unknown'


def _wave_position(structure: str, stage: str, wave_result: Dict, events: List[Dict],
                   position_context: Dict) -> Dict:
    event_types = _event_types(events)
    trading_wave = wave_result.get('trading_wave') or {}
    direction = trading_wave.get('direction')
    zone_type = (position_context.get('current_zone') or {}).get('type')
    evidence: List[str] = []

    if 'panic_stagnation' in event_types:
        return {
            'position': 'valley_left',
            'label': '波谷左侧',
            'confidence': 76,
            'evidence': ['天量滞跌/恐慌表示供应快速释放，但仍需需求确认'],
        }
    if {'bullish_reversal', 'failed_breakdown'} & event_types:
        return {
            'position': 'valley_confirmed',
            'label': '波谷确认',
            'confidence': 72,
            'evidence': ['需求进入或跌破失败，下降段结束概率提高'],
        }
    if 'climax_stagnation' in event_types:
        return {
            'position': 'peak_left',
            'label': '波峰左侧',
            'confidence': 74,
            'evidence': ['放量滞涨/高潮表示需求可能被透支'],
        }
    if 'downward_breakdown' in event_types and zone_type == 'near_support':
        return {
            'position': 'falling_middle',
            'label': '区间底部跌破风险',
            'confidence': 70,
            'evidence': ['支撑附近被供应跌破，属于下行风险，不是波峰确认'],
        }
    if {'bearish_reversal', 'failed_breakout'} & event_types:
        return {
            'position': 'peak_confirmed',
            'label': '波峰确认/转弱',
            'confidence': 72,
            'evidence': ['供应进入、突破失败或关键位跌破'],
        }

    if structure == '上涨趋势':
        if direction == 'up':
            return {'position': 'rising_middle', 'label': '上升波中', 'confidence': 64, 'evidence': ['需求占优的上涨交易波段']}
        if direction == 'down':
            return {'position': 'falling_middle', 'label': '上涨结构中的回调段', 'confidence': 58, 'evidence': ['主结构未破坏，但当前交易波段向下']}
    if structure == '下降趋势':
        if direction == 'down':
            return {'position': 'falling_middle', 'label': '下降波中', 'confidence': 66, 'evidence': ['供应占优的下降交易波段']}
        if direction == 'up':
            return {'position': 'rising_middle', 'label': '下降结构中的反弹段', 'confidence': 56, 'evidence': ['主结构未扭转，只是反弹波']}
    if structure == '区间震荡':
        if direction == 'up':
            evidence.append('区间震荡中的上行波段')
        elif direction == 'down':
            evidence.append('区间震荡中的下行波段')
        else:
            evidence.append('区间中部或横向波段')
        return {'position': 'range_middle', 'label': stage or '区间震荡', 'confidence': 52, 'evidence': evidence}

    return {'position': 'unknown', 'label': '未识别', 'confidence': 0, 'evidence': ['波段位置未识别']}


def _major_decline_risk(structure: str, stage: str, wave_position: Dict, events: List[Dict]) -> Dict:
    event_types = _event_types(events)
    evidence: List[str] = []

    if wave_position.get('position') in ('valley_left', 'valley_confirmed') or 'panic_stagnation' in event_types:
        return {
            'level': 'none',
            'reason': '供应衰竭/波谷候选出现，不能机械继续判为主跌 high',
            'evidence': wave_position.get('evidence', []),
        }

    if structure == '下降趋势' and stage in ('形成', '发展'):
        return {
            'level': 'high',
            'reason': '下降趋势形成/发展段是 3L 仓位控制最应回避的主跌风险区',
            'evidence': ['供应占优结构', f'阶段={stage}'],
        }

    if 'downward_breakdown' in event_types:
        return {
            'level': 'watch',
            'reason': '关键支撑/区间下沿出现跌破，需要观察是否演化为主跌',
            'evidence': ['供应尝试打破支撑或区间平衡'],
        }

    if wave_position.get('position') in ('peak_left', 'peak_confirmed') or stage in ('加速', '加速/高潮', '逆转候选'):
        evidence.extend(wave_position.get('evidence', []))
        return {
            'level': 'watch',
            'reason': '上升段后出现需求透支、供应进入或波峰候选，需要防主跌',
            'evidence': evidence or [f'阶段={stage}'],
        }

    if structure == '上涨趋势' and stage == '回调':
        return {
            'level': 'watch',
            'reason': '上涨结构仍在，但当前交易波段向下，需要观察是否演化为主跌',
            'evidence': ['上涨趋势中的下降交易波段/回调'],
        }

    return {
        'level': 'none',
        'reason': '未识别到主跌高风险条件',
        'evidence': [],
    }


def _compact_wave(wave: Dict) -> Dict:
    return {
        'direction': wave.get('direction') or 'flat',
        'label': wave.get('label'),
        'start_idx': wave.get('start_idx'),
        'start_date': wave.get('start_date'),
        'start_price': wave.get('start_price'),
        'extreme_idx': wave.get('extreme_idx'),
        'extreme_date': wave.get('extreme_date'),
        'extreme_price': wave.get('extreme_price'),
        'change_pct': wave.get('change_pct'),
        'counter_move_pct': wave.get('counter_move_pct'),
        'status': 'confirmed' if wave.get('confirmed') else 'candidate',
        'source': wave.get('source'),
    }


def detect_3l_structure_context(
    klines: Iterable[Dict],
    *,
    asset_type: str = 'stock',
    end_idx: int = -1,
    wave_structure_result: Optional[Dict] = None,
    supply_demand_events_result: Optional[Dict] = None,
) -> Dict:
    """识别 3L 结构上下文。

    首版是旁路聚合器：先把输出合同稳定下来，再用验证图和人工样本优化算法。
    """
    rows = _normalize_klines(klines)
    if len(rows) < MIN_BARS:
        return {
            'version': VERSION,
            'status': 'unavailable',
            'reason': f'至少需要 {MIN_BARS} 根有效 K 线',
            'asset_type': asset_type,
            'is_trade_decision': False,
        }

    end = end_idx if end_idx >= 0 else len(rows) - 1
    end = min(end, len(rows) - 1)
    scoped_rows = rows[:end + 1]
    wave_result = wave_structure_result or judge_wave_structure(scoped_rows, asset_type=asset_type)
    if wave_result.get('status') != 'ok':
        return {
            'version': VERSION,
            'status': wave_result.get('status', 'unavailable'),
            'reason': wave_result.get('reason', '波段结构不可用'),
            'asset_type': asset_type,
            'is_trade_decision': False,
        }

    structure_view = _resolve_structure(wave_result)
    structure = structure_view['structure']
    pure = detect_pure_keypoints(scoped_rows, asset_type=asset_type, end_idx=end)
    position_context = detect_structure_position_context(
        scoped_rows,
        idx=end,
        structure=structure,
        stage='',
        reference_points=pure.get('points') or [],
    )
    events_result = supply_demand_events_result or detect_supply_demand_events(
        scoped_rows,
        asset_type=asset_type,
        end_idx=end,
        structure=structure,
        stage=position_context.get('stage') or '',
        pure_keypoints=pure,
        wave_context=wave_result,
    )
    events = events_result.get('events') or []
    stage_view = _stage_for_context(structure, wave_result, events, position_context)
    stage = stage_view['stage']
    wave_position = _wave_position(structure, stage, wave_result, events, position_context)
    risk = _major_decline_risk(structure, stage, wave_position, events)
    warnings: List[str] = []
    if structure == '区间震荡' and position_context.get('stage') not in ('区间顶部', '区间底部', '区间中段'):
        warnings.append('区间震荡缺少明确区间位置')
    if events_result.get('is_trade_decision') is not False:
        warnings.append('供需事件层不应输出交易决策')

    return {
        'version': VERSION,
        'status': 'ok',
        'asset_type': asset_type,
        'date': scoped_rows[-1]['date'],
        'market_structure': {
            'structure': structure,
            'stage': stage,
            'supply_demand_regime': _regime(structure),
            'confidence': min(100, round((structure_view['confidence'] + stage_view['confidence']) / 2, 1)),
            'evidence': structure_view.get('evidence', []) + stage_view.get('evidence', []),
            'source': structure_view.get('source'),
        },
        'wave_context': {
            'primary_wave': _compact_wave(wave_result.get('active_wave') or {}),
            'trading_wave': {
                **_compact_wave(wave_result.get('trading_wave') or {}),
                'state': wave_result.get('trading_state'),
            },
            'pivots': wave_result.get('pivots') or [],
            'thresholds': wave_result.get('thresholds') or {},
        },
        'wave_position': wave_position,
        'major_decline_risk': risk,
        'position_context': {
            'zone_type': (position_context.get('current_zone') or {}).get('type'),
            'range_position_pct': (position_context.get('current_zone') or {}).get('range_position_pct'),
            'anchor': (position_context.get('current_zone') or {}).get('anchor'),
            'reason': (position_context.get('current_zone') or {}).get('reason'),
        },
        'supply_demand_events': events,
        'warnings': warnings,
        'is_trade_decision': False,
        'definitions': {
            'structure_context': '3L 结构上下文：只描述结构、阶段、波段位置和主跌风险，不直接输出买卖点',
            'major_decline_risk': '主跌风险用于仓位/节奏过滤，不等于机械清仓指令',
        },
    }
