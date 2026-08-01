"""3L 止损候选与无前视回测纯函数。"""
from __future__ import annotations

import math
import random
import statistics

from .buy_point_detection import calc_stop_loss


STRUCTURE_BUFFERS = (0.0, 0.1, 0.2, 0.3)
ROUND_TRIP_SIDE_COST = 0.001


def calc_recent_atr(klines, period=14):
    """预注册口径：截至信号日最近 period 个 TR 的算术均值。"""
    if len(klines) < period + 1:
        return None
    true_ranges = []
    for index in range(len(klines) - period, len(klines)):
        current = klines[index]
        previous_close = _positive(klines[index - 1].get('close'))
        high = _positive(current.get('high'))
        low = _positive(current.get('low'))
        if None in (previous_close, high, low):
            return None
        true_ranges.append(max(high - low, abs(high - previous_close), abs(low - previous_close)))
    return statistics.fmean(true_ranges)


def validate_adjusted_continuity(rows, tolerance=0.005):
    """用前收盘/除权昨收/复权因子校验相邻日线是否来自同一连续序列。"""
    for index in range(1, len(rows)):
        previous, current = rows[index - 1], rows[index]
        prev_close = _positive(previous.get('close'))
        prev_factor = _positive(previous.get('adj_factor'))
        pre_close = _positive(current.get('pre_close'))
        current_factor = _positive(current.get('adj_factor'))
        if None in (prev_close, prev_factor, pre_close, current_factor):
            return False, {'index': index, 'reason': 'missing_continuity_field'}
        previous_adjusted = prev_close * prev_factor
        current_reference = pre_close * current_factor
        relative_gap = abs(previous_adjusted - current_reference) / max(previous_adjusted, current_reference)
        if relative_gap > tolerance:
            return False, {
                'index': index,
                'date': current.get('trade_date') or current.get('date'),
                'reason': 'adjusted_pre_close_mismatch',
                'relative_gap': round(relative_gap, 6),
            }
    return True, None


def detect_buy_point_without_future(detector, code, klines, signal_idx, **kwargs):
    """只把截止信号日的数据交给生产检测器。"""
    visible = [dict(item) for item in klines[:signal_idx + 1]]
    if not visible:
        return None
    date_str = str(visible[-1].get('date', ''))
    return detector(code, date_str, {'回测样本': {code: visible}}, **kwargs)


def calculate_stop_candidates(klines, signal_idx, buy_type, next_open=None):
    """在信号日可见数据上计算冻结生产基线与结构候选。"""
    visible = klines[:signal_idx + 1]
    if len(visible) < 16:
        return {}
    signal = visible[-1]
    close = _positive(signal.get('close'))
    low = _positive(signal.get('low'))
    atr = calc_recent_atr(visible, 14)
    if close is None or low is None or not atr or atr <= 0:
        return {}

    baseline, _ = calc_stop_loss(
        visible, signal_idx, close_price=close,
        buy_type=buy_type, entry_idx=signal_idx,
    )
    prior_high = max(_positive(k.get('high')) or 0 for k in visible[-16:-1])
    if buy_type in ('突破买点', '区顶突破') and 0 < prior_high < close:
        anchor = max(low, prior_high)
    else:
        anchor = low

    candidates = {'production_baseline': _valid_planned_stop(baseline, close)}
    for buffer in STRUCTURE_BUFFERS:
        name = f'structure_atr_{buffer:.1f}'
        candidates[name] = _valid_planned_stop(round(anchor - buffer * atr, 2), close)
    entry_proxy = _positive(next_open)
    candidates['cost_2atr'] = (
        _valid_planned_stop(round(entry_proxy - 2 * atr, 2), entry_proxy)
        if entry_proxy is not None else None
    )
    return candidates


def simulate_stop_trade(klines, signal_idx, stop, horizon=20, side_cost=ROUND_TRIP_SIDE_COST,
                        terminal_if_short=False):
    """信号次日开盘入场，按日线保守模拟止损或第20根收盘退出。"""
    if stop is None or signal_idx + 1 >= len(klines):
        return {'covered': False}
    future = klines[signal_idx + 1:signal_idx + horizon + 1]
    if not future:
        return {'covered': False}
    entry = _positive(future[0].get('open'))
    if entry is None:
        return {'covered': False}
    if entry <= stop:
        return {
            'covered': True, 'gap_cancelled': True, 'stop_hit': False,
            'net_return_pct': 0.0, 'gross_return_pct': 0.0,
            'initial_risk_pct': 0.0, 'terminal_exit': False,
            'false_stop': False, 'gap_slippage_pct': 0.0,
        }

    entry_cost = entry * (1 + side_cost)
    stop_idx = None
    exit_price = None
    gap_slippage = 0.0
    for offset, bar in enumerate(future):
        low = _positive(bar.get('low'))
        open_price = _positive(bar.get('open'))
        if low is not None and low <= stop:
            stop_idx = offset
            exit_price = min(open_price, stop) if open_price is not None else stop
            gap_slippage = max(0.0, (stop - exit_price) / entry * 100)
            break

    terminal = False
    if exit_price is None:
        exit_price = _positive(future[-1].get('close'))
        if exit_price is None:
            return {'covered': False}
        terminal = len(future) < horizon and terminal_if_short
    proceeds = exit_price * (1 - side_cost)
    gross_return = (exit_price - entry) / entry * 100
    net_return = (proceeds - entry_cost) / entry_cost * 100

    false_stop = False
    if stop_idx is not None:
        false_stop = any(
            (_positive(bar.get('close')) or 0) > entry
            for bar in future[stop_idx:]
        )
    hold_exit = _positive(future[-1].get('close'))
    hold_return = None
    if hold_exit is not None:
        hold_return = ((hold_exit * (1 - side_cost)) - entry_cost) / entry_cost * 100

    return {
        'covered': True,
        'gap_cancelled': False,
        'stop_hit': stop_idx is not None,
        'stop_day': stop_idx + 1 if stop_idx is not None else None,
        'net_return_pct': round(net_return, 4),
        'gross_return_pct': round(gross_return, 4),
        'hold_return_pct': round(hold_return, 4) if hold_return is not None else None,
        'initial_risk_pct': round((entry - stop) / entry * 100, 4),
        'terminal_exit': terminal,
        'false_stop': false_stop,
        'gap_slippage_pct': round(gap_slippage, 4),
    }


def summarize_results(rows, bootstrap_runs=1000, seed=3):
    """汇总一个候选/数据切分/买点类型的结果。"""
    total = len(rows)
    covered = [row for row in rows if row.get('covered')]
    traded = [row for row in covered if not row.get('gap_cancelled')]
    returns = [float(row['net_return_pct']) for row in covered if row.get('net_return_pct') is not None]
    stops = [row for row in traded if row.get('stop_hit')]
    metrics = {
        'signals': total,
        'covered': len(covered),
        'coverage_pct': _pct(len(covered), total),
        'gap_cancel_rate_pct': _pct(sum(bool(r.get('gap_cancelled')) for r in covered), len(covered)),
        'trades': len(traded),
        'stop_5d_rate_pct': _pct(sum((r.get('stop_day') or 999) <= 5 for r in traded), len(traded)),
        'stop_10d_rate_pct': _pct(sum((r.get('stop_day') or 999) <= 10 for r in traded), len(traded)),
        'stop_20d_rate_pct': _pct(len(stops), len(traded)),
        'false_stop_rate_pct': _pct(sum(bool(r.get('false_stop')) for r in stops), len(stops)),
        'terminal_exit_rate_pct': _pct(sum(bool(r.get('terminal_exit')) for r in traded), len(traded)),
        'mean_initial_risk_pct': _mean([r.get('initial_risk_pct') for r in traded]),
        'mean_return_pct': _mean(returns),
        'median_return_pct': round(statistics.median(returns), 4) if returns else None,
        'win_rate_pct': _pct(sum(v > 0 for v in returns), len(returns)),
        'p05_return_pct': _quantile(returns, 0.05),
        'cvar05_return_pct': _cvar(returns, 0.05),
        'max_loss_pct': round(min(returns), 4) if returns else None,
        'mean_hold_return_pct': _mean([r.get('hold_return_pct') for r in traded]),
        'mean_gap_slippage_pct': _mean([r.get('gap_slippage_pct') for r in stops]),
    }
    metrics['bootstrap_95'] = _cluster_bootstrap(rows, bootstrap_runs, seed) if bootstrap_runs and rows else {}
    return metrics


def _cluster_bootstrap(rows, runs, seed):
    groups = {}
    for row in rows:
        groups.setdefault(row.get('code', ''), []).append(row)
    codes = sorted(code for code in groups if code)
    if len(codes) < 2:
        return {}
    rng = random.Random(seed)
    sampled_metrics = {'mean_return_pct': [], 'cvar05_return_pct': [], 'false_stop_rate_pct': []}
    for _ in range(runs):
        sample = []
        for code in rng.choices(codes, k=len(codes)):
            sample.extend(groups[code])
        returns = [float(r['net_return_pct']) for r in sample if r.get('covered') and r.get('net_return_pct') is not None]
        stops = [r for r in sample if r.get('covered') and not r.get('gap_cancelled') and r.get('stop_hit')]
        sampled_metrics['mean_return_pct'].append(_mean(returns))
        sampled_metrics['cvar05_return_pct'].append(_cvar(returns, 0.05))
        sampled_metrics['false_stop_rate_pct'].append(_pct(sum(bool(r.get('false_stop')) for r in stops), len(stops)))
    return {
        key: [_quantile([v for v in values if v is not None], 0.025),
              _quantile([v for v in values if v is not None], 0.975)]
        for key, values in sampled_metrics.items()
    }


def _positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


def _valid_planned_stop(stop, signal_close):
    stop = _positive(stop)
    return round(stop, 2) if stop is not None and stop < signal_close else None


def _pct(numerator, denominator):
    return round(numerator / denominator * 100, 4) if denominator else None


def _mean(values):
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return round(statistics.fmean(clean), 4) if clean else None


def _quantile(values, q):
    clean = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not clean:
        return None
    index = (len(clean) - 1) * q
    low, high = math.floor(index), math.ceil(index)
    if low == high:
        return round(clean[low], 4)
    value = clean[low] * (high - index) + clean[high] * (index - low)
    return round(value, 4)


def _cvar(values, q):
    clean = sorted(float(v) for v in values if v is not None and math.isfinite(float(v)))
    if not clean:
        return None
    count = max(1, math.ceil(len(clean) * q))
    return round(statistics.fmean(clean[:count]), 4)
