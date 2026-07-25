"""峰谷算法的无未来函数事件回归工具。

这里不把未来涨跌当作峰谷定义，只把它用于诊断当日供需判定的后续表现。
judge 回调在每个交易日只会收到截至当日的 K 线切片。
"""
from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Callable, Dict, Iterable, List, Mapping, Sequence

from backend.core.market_peak_valley import normalize_market_klines


Judge = Callable[[List[Dict]], Dict]
PHASE_LEVEL = {'none': 0, 'left': 1, 'forming': 2, 'biased': 3, 'confirmed': 4}
DEFAULT_HORIZONS = (1, 3, 5, 10, 20)


def adapt_legacy_result(result: Dict) -> Dict:
    """把旧五档结果映射为事件阶段，仅用于新旧算法回归对比。"""
    position = result.get('position', '波中')
    side_phase = {
        '偏波谷': ('valley', 'biased'),
        '波中偏下': ('valley', 'forming'),
        '偏波峰': ('peak', 'biased'),
        '波中偏上': ('peak', 'forming'),
    }
    side, phase = side_phase.get(position, ('none', 'none'))
    return {
        **result,
        'wave_side': side,
        'wave_phase': phase,
        'wave_label': position,
        'algorithm_version': 'legacy_bias20_v5',
    }


def _ordered_bars(klines: Iterable[Dict]) -> List[Dict]:
    return normalize_market_klines(list(klines))


def _forward_outcome(
    bars: Sequence[Dict], index: int, side: str, horizons: Sequence[int], *, end_index: int,
) -> Dict:
    close = float(bars[index]['close'])
    available = end_index - index
    result = {}
    for horizon in horizons:
        key = f'return_{horizon}d'
        if available < horizon:
            result[key] = None
            continue
        future_close = float(bars[index + horizon]['close'])
        result[key] = round((future_close / close - 1) * 100, 4)

    max_horizon = max(horizons)
    if available < max_horizon:
        result.update({'mfe': None, 'mae': None, 'signed_return_10d': None})
    else:
        path_returns = [
            (float(bars[index + offset]['close']) / close - 1) * 100
            for offset in range(1, max_horizon + 1)
        ]
        signed_path = [0.0] + (path_returns if side == 'valley' else [-value for value in path_returns])
        result['mfe'] = round(max(signed_path), 4)
        result['mae'] = round(min(signed_path), 4)
    return_10d = result.get('return_10d')
    result['signed_return_10d'] = (
        None if return_10d is None else round(return_10d if side == 'valley' else -return_10d, 4)
    )
    return result


def collect_events(
    klines: Iterable[Dict],
    judge: Judge,
    *,
    min_bars: int = 80,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    calibration_ratio: float = 0.6,
    same_phase_cooldown: int = 5,
) -> List[Dict]:
    """滚动运行判定器，并把连续同阶段信号合并为一个事件。"""
    bars = _ordered_bars(klines)
    split_index = max(min_bars, int(len(bars) * calibration_ratio))
    events: List[Dict] = []
    active_side = 'none'
    active_phase = 'none'
    last_event_index = {}

    for index in range(min_bars - 1, len(bars)):
        result = judge(bars[:index + 1])
        side = result.get('wave_side', 'none')
        phase = result.get('wave_phase', 'none')
        if side not in ('valley', 'peak') or phase not in PHASE_LEVEL:
            side, phase = 'none', 'none'

        current_level = PHASE_LEVEL[phase]
        previous_level = PHASE_LEVEL.get(active_phase, 0) if side == active_side else 0
        changed_or_upgraded = side != active_side or current_level > previous_level
        same_phase_recent = index - last_event_index.get((side, phase), -10_000) <= same_phase_cooldown
        is_new_event = current_level > 0 and changed_or_upgraded and not same_phase_recent
        if is_new_event:
            event = {
                'date': str(bars[index].get('date', '')),
                'close': float(bars[index]['close']),
                'side': side,
                'phase': phase,
                'label': result.get('wave_label') or result.get('position'),
                'structure': result.get('structure', 'unknown'),
                'supply_demand_state': result.get('supply_demand_state', ''),
                'dataset': 'calibration' if index < split_index else 'validation',
                'context': result.get('context', {}),
                'evidence': result.get('evidence', {}),
                'features': result.get('features', {}),
                **_forward_outcome(
                    bars, index, side, horizons,
                    end_index=split_index - 1 if index < split_index else len(bars) - 1,
                ),
            }
            events.append(event)
            last_event_index[(side, phase)] = index

        active_side, active_phase = side, phase

    return events


def _average(rows: Sequence[Dict], key: str):
    values = [float(row[key]) for row in rows if row.get(key) is not None]
    return round(mean(values), 4) if values else None


def summarize_events(events: Sequence[Dict], horizons: Sequence[int] = DEFAULT_HORIZONS) -> List[Dict]:
    """按数据段、方向和阶段汇总事件表现。"""
    groups = defaultdict(list)
    for event in events:
        groups[(event['dataset'], event['side'], event['phase'])].append(event)

    summaries = []
    for (dataset, side, phase), rows in sorted(groups.items()):
        signed = [row['signed_return_10d'] for row in rows if row.get('signed_return_10d') is not None]
        summary = {
            'dataset': dataset,
            'side': side,
            'phase': phase,
            'count': len(rows),
            'evaluated_10d': len(signed),
            'positive_10d_ratio': round(sum(value > 0 for value in signed) / len(signed), 4) if signed else None,
            'avg_signed_return_10d': round(mean(signed), 4) if signed else None,
            'avg_mfe': _average(rows, 'mfe'),
            'avg_mae': _average(rows, 'mae'),
        }
        for horizon in horizons:
            raw_key = f'return_{horizon}d'
            values = [
                (row[raw_key] if side == 'valley' else -row[raw_key])
                for row in rows if row.get(raw_key) is not None
            ]
            summary[f'avg_signed_return_{horizon}d'] = round(mean(values), 4) if values else None
        summaries.append(summary)
    return summaries


def run_regression(
    indices: Mapping[str, Dict],
    judges: Mapping[str, Judge],
    *,
    min_bars: int = 80,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    calibration_ratio: float = 0.6,
) -> Dict:
    """对多个指数、多个算法执行同口径的滚动回归。"""
    report = {
        'method': 'rolling_no_lookahead_event_study',
        'min_bars': min_bars,
        'horizons': list(horizons),
        'calibration_ratio': calibration_ratio,
        'algorithms': {},
    }
    for algorithm, judge in judges.items():
        algorithm_events = []
        per_index = {}
        for code, info in indices.items():
            events = collect_events(
                info.get('klines', []), judge, min_bars=min_bars,
                horizons=horizons, calibration_ratio=calibration_ratio,
            )
            named_events = [{'index_code': code, 'index_name': info.get('name', code), **row} for row in events]
            algorithm_events.extend(named_events)
            per_index[code] = {
                'name': info.get('name', code),
                'bars': len(info.get('klines', [])),
                'event_count': len(events),
                'summary': summarize_events(events, horizons),
                'events': named_events,
            }
        report['algorithms'][algorithm] = {
            'event_count': len(algorithm_events),
            'summary': summarize_events(algorithm_events, horizons),
            'indices': per_index,
        }
    return report
