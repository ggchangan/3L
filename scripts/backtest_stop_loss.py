#!/usr/bin/env python3
"""在生产 MySQL 历史日线上比较 3L 止损候选，生成 JSON/Markdown 报告。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (os.path.join(ROOT, 'core'), os.path.join(ROOT, 'server')):
    if path not in sys.path:
        sys.path.insert(0, path)

from backend.data_access.tushare_db import TushareDB
from threel_core.buy_point_detection import detect_buy_point
from threel_core.price_adjustment import qfq_ratio
from threel_core.stop_loss_validation import (
    calculate_stop_candidates,
    detect_buy_point_without_future,
    simulate_stop_trade,
    summarize_results,
    validate_adjusted_continuity,
)


def parse_args():
    parser = argparse.ArgumentParser(description='3L止损候选无前视回测')
    parser.add_argument('--start', default='20240401')
    parser.add_argument('--calibration-end', default='20251231')
    parser.add_argument('--end', default='')
    parser.add_argument('--sample-size', type=int, default=0, help='0=全部股票；否则按代码哈希固定抽样')
    parser.add_argument('--bootstrap-runs', type=int, default=1000)
    parser.add_argument('--calendar-buffer', type=int, default=40, help='end后额外加载的全市场交易日数')
    parser.add_argument('--output-dir', default=os.path.join(ROOT, 'docs', 'stop-loss-validation', 'results'))
    parser.add_argument('--progress-every', type=int, default=100)
    return parser.parse_args()


def load_universe(db, sample_size):
    rows = db.execute_raw(
        "SELECT d.ts_code, COUNT(*) AS bars, MAX(d.trade_date) AS last_trade_date, "
        "MAX(s.delist_date) AS delist_date FROM stock_daily d "
        "LEFT JOIN stock_basic s ON s.ts_code=d.ts_code "
        "GROUP BY d.ts_code HAVING COUNT(*) >= 81"
    )
    if sample_size and sample_size < len(rows):
        rows = sorted(rows, key=lambda row: hashlib.sha256(row['ts_code'].encode()).hexdigest())[:sample_size]
    return sorted(rows, key=lambda row: row['ts_code'])


def load_global_dates(db):
    return [row['trade_date'] for row in db.execute_raw(
        'SELECT DISTINCT trade_date FROM stock_daily ORDER BY trade_date'
    )]


def load_adjusted_klines(db, ts_code, cutoff):
    rows = db.execute_raw(
        "SELECT d.trade_date,d.open,d.high,d.low,d.close,d.pre_close,d.vol,a.adj_factor "
        "FROM stock_daily d LEFT JOIN adj_factor a "
        "ON a.ts_code=d.ts_code AND a.trade_date=d.trade_date "
        "WHERE d.ts_code=%s AND d.trade_date<=%s ORDER BY d.trade_date",
        [ts_code, cutoff],
    )
    if not rows:
        return [], 'no_daily'
    base = rows[-1].get('adj_factor')
    ratios = [qfq_ratio(row.get('adj_factor'), base) for row in rows]
    if any(ratio is None for ratio in ratios):
        return [], 'factor_incomplete'
    continuous, _detail = validate_adjusted_continuity(rows)
    if not continuous:
        return [], 'price_discontinuity'
    klines = []
    for row, ratio in zip(rows, ratios):
        prices = {}
        try:
            for field in ('open', 'high', 'low', 'close'):
                prices[field] = round(float(row[field]) * ratio, 2)
        except (TypeError, ValueError):
            return [], 'invalid_price'
        if min(prices.values()) <= 0:
            return [], 'invalid_price'
        klines.append({
            'date': row['trade_date'], **prices,
            'volume': int(row.get('vol') or 0),
            'adjustment_status': 'qfq',
        })
    return klines, 'qfq'


def scan_stock(code, klines, start, end, global_future_count, stock_last_trade, price_cutoff):
    local_code = code.split('.')[0]
    detect_buy_point._ind_map = {local_code: {'ths_industry': '回测统一主线'}}
    outcomes = []
    counters = Counter()
    last_primary_idx = -10_000
    for idx in range(60, len(klines) - 1):
        signal_date = str(klines[idx]['date'])
        if signal_date < start or (end and signal_date > end):
            continue
        result = detect_buy_point_without_future(
            detect_buy_point, local_code, klines, idx,
            market_position='波中', main_lines=['回测统一主线'],
        )
        if not result:
            continue
        counters['raw_signals'] += 1
        primary = idx > last_primary_idx + 20
        if primary:
            last_primary_idx = idx
            counters['primary_signals'] += 1
        if global_future_count.get(signal_date, 0) < 20:
            counters['censored_recent'] += 1
            continue
        available_future = len(klines) - idx - 1
        terminal_if_short = available_future < 20 and stock_last_trade <= price_cutoff
        if available_future < 20 and not terminal_if_short:
            counters['censored_suspension'] += 1
            continue
        next_open = klines[idx + 1].get('open')
        candidates = calculate_stop_candidates(klines, idx, result.get('buy_type', ''), next_open=next_open)
        for candidate, stop in candidates.items():
            outcome = simulate_stop_trade(
                klines, idx, stop, horizon=20,
                terminal_if_short=terminal_if_short,
            )
            outcome.update({
                'code': local_code,
                'ts_code': code,
                'signal_date': signal_date,
                'buy_type': result.get('buy_type', ''),
                'candidate': candidate,
                'stop': stop,
                'primary': primary,
            })
            outcomes.append(outcome)
    return outcomes, counters


def build_report(outcomes, calibration_end, bootstrap_runs, metadata):
    report = {'metadata': metadata, 'summary': {}, 'decisions': {}}
    for scope, scope_rows in (
        ('primary', [row for row in outcomes if row['primary']]),
        ('all_signals_sensitivity', outcomes),
    ):
        report['summary'][scope] = {}
        for split, split_rows in (
            ('calibration', [r for r in scope_rows if r['signal_date'] <= calibration_end]),
            ('validation', [r for r in scope_rows if r['signal_date'] > calibration_end]),
        ):
            report['summary'][scope][split] = {}
            candidates = sorted({row['candidate'] for row in split_rows})
            for candidate in candidates:
                candidate_rows = [row for row in split_rows if row['candidate'] == candidate]
                report['summary'][scope][split][candidate] = {
                    'all': summarize_results(candidate_rows, bootstrap_runs),
                }
                for buy_type in sorted({row['buy_type'] for row in candidate_rows}):
                    rows = [row for row in candidate_rows if row['buy_type'] == buy_type]
                    report['summary'][scope][split][candidate][buy_type] = summarize_results(rows, bootstrap_runs)
    report['decisions'] = evaluate_candidates(report['summary']['primary'].get('validation', {}))
    return report


def evaluate_candidates(validation):
    baseline_groups = validation.get('production_baseline', {})
    decisions = {}
    for candidate, groups in validation.items():
        if candidate in ('production_baseline', 'cost_2atr'):
            continue
        decisions[candidate] = {}
        for group in ('all', '突破买点', '中继买点'):
            current = groups.get(group, {})
            baseline = baseline_groups.get(group, {})
            minimum = 300 if group == 'all' else 100
            reasons = []
            if (current.get('signals') or 0) < minimum:
                reasons.append(f'样本不足<{minimum}')
            if (current.get('coverage_pct') or 0) < 95:
                reasons.append('覆盖率<95%')
            for key, tolerance in (('cvar05_return_pct', 0.5), ('max_loss_pct', 1.0)):
                if _worse(current.get(key), baseline.get(key), tolerance):
                    reasons.append(f'{key}恶化>{tolerance}pp')
            mean_improve = _delta(current.get('mean_return_pct'), baseline.get('mean_return_pct'))
            false_improve = _delta(baseline.get('false_stop_rate_pct'), current.get('false_stop_rate_pct'))
            if (mean_improve is None or mean_improve < 0.2) and (false_improve is None or false_improve < 5):
                reasons.append('平均收益/假止损率未达到改善门槛')
            if mean_improve is not None and mean_improve < -2:
                reasons.append('平均收益恶化>2pp')
            if false_improve is not None and false_improve < -2:
                reasons.append('假止损率恶化>2pp')
            decisions[candidate][group] = {
                'accepted': not reasons,
                'reasons': reasons,
                'mean_return_improvement_pp': mean_improve,
                'false_stop_improvement_pp': false_improve,
            }
    return decisions


def render_markdown(report):
    meta = report['metadata']
    lines = [
        '# 3L 止损算法回测报告', '',
        f"- 代码版本：`{meta['git_commit']}`",
        f"- 数据范围：{meta['data_start']} ～ {meta['data_end']}",
        f"- 股票池：{meta['stocks_used']}/{meta['stocks_selected']}（历史日线构造，固定哈希抽样={meta['sample_size']}）",
        f"- 信号：原始 {meta.get('raw_signals', 0)}，20日冷却后 {meta.get('primary_signals', 0)}，近期删失 {meta.get('censored_recent', 0)}",
        f"- 数据跳过：{json.dumps(meta['skipped'], ensure_ascii=False, sort_keys=True)}",
        '- 检测上下文：波中市场、假设属于主线；每个信号日强制截断 K 线，无未来数据。', '',
    ]
    for split in ('calibration', 'validation'):
        lines.extend([f'## {"校准集" if split == "calibration" else "时间外验证集"}', '',
                      '| 候选 | 样本 | 覆盖率 | 初始风险 | 20日止损 | 假止损 | 平均收益 | CVaR5 | 最大亏损 |',
                      '|---|---:|---:|---:|---:|---:|---:|---:|---:|'])
        for candidate, groups in report['summary']['primary'].get(split, {}).items():
            m = groups['all']
            lines.append(
                f"| {candidate} | {m.get('signals')} | {_fmt(m.get('coverage_pct'))} | "
                f"{_fmt(m.get('mean_initial_risk_pct'))} | {_fmt(m.get('stop_20d_rate_pct'))} | "
                f"{_fmt(m.get('false_stop_rate_pct'))} | {_fmt(m.get('mean_return_pct'))} | "
                f"{_fmt(m.get('cvar05_return_pct'))} | {_fmt(m.get('max_loss_pct'))} |"
            )
        lines.append('')
    lines.extend(['## 自动验收结论', '', '```json', json.dumps(report['decisions'], ensure_ascii=False, indent=2), '```', '',
                  '> 本报告使用结果代理指标，不宣称人工标注意义上的“止损准确率”。'])
    return '\n'.join(lines) + '\n'


def main():
    args = parse_args()
    db = TushareDB()
    global_dates = load_global_dates(db)
    end = args.end or global_dates[-21]
    if end not in global_dates:
        raise SystemExit(f'--end {end} 不是数据库交易日')
    end_index = global_dates.index(end)
    if end_index + args.calendar_buffer >= len(global_dates):
        raise SystemExit('--end 之后不足 calendar-buffer 个全市场交易日')
    price_cutoff = global_dates[end_index + args.calendar_buffer]
    future_count = {date: len(global_dates) - i - 1 for i, date in enumerate(global_dates)}
    universe = load_universe(db, args.sample_size)
    outcomes = []
    skipped = Counter()
    totals = Counter()
    used = 0
    for number, universe_row in enumerate(universe, 1):
        code = universe_row['ts_code']
        klines, status = load_adjusted_klines(db, code, price_cutoff)
        if not klines:
            skipped[status] += 1
            continue
        stock_outcomes, counters = scan_stock(
            code, klines, args.start, end, future_count,
            str(universe_row['last_trade_date']), price_cutoff,
        )
        outcomes.extend(stock_outcomes)
        totals.update(counters)
        used += 1
        if args.progress_every and number % args.progress_every == 0:
            print(f'[{number}/{len(universe)}] used={used} primary={totals["primary_signals"]} rows={len(outcomes)}', flush=True)

    git_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    metadata = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'git_commit': git_commit,
        'data_start': args.start,
        'data_end': end,
        'price_cutoff': price_cutoff,
        'calibration_end': args.calibration_end,
        'sample_size': args.sample_size,
        'stocks_selected': len(universe),
        'stocks_used': used,
        'skipped': dict(skipped),
        **dict(totals),
        'bootstrap_runs': args.bootstrap_runs,
        'signal_context': {'market_position': '波中', 'mainline_assumed': True},
    }
    for key in ('raw_signals', 'primary_signals', 'censored_recent', 'censored_suspension'):
        metadata.setdefault(key, 0)
    report = build_report(outcomes, args.calibration_end, args.bootstrap_runs, metadata)
    os.makedirs(args.output_dir, exist_ok=True)
    suffix = f'sample{args.sample_size}' if args.sample_size else 'full'
    json_path = os.path.join(args.output_dir, f'stop_loss_backtest_{suffix}.json')
    md_path = os.path.join(args.output_dir, f'stop_loss_backtest_{suffix}.md')
    with open(json_path, 'w', encoding='utf-8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
    with open(md_path, 'w', encoding='utf-8') as file:
        file.write(render_markdown(report))
    print(json.dumps({'json': json_path, 'markdown': md_path, 'metadata': metadata}, ensure_ascii=False, indent=2))


def _delta(left, right):
    return round(left - right, 4) if left is not None and right is not None else None


def _worse(current, baseline, tolerance):
    return current is not None and baseline is not None and current < baseline - tolerance


def _fmt(value):
    return '--' if value is None else f'{value:.2f}%'


if __name__ == '__main__':
    main()
