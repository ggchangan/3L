#!/usr/bin/env python3
"""生成 3L 结构/阶段 P0-structure 验证图。

用途：

    PYTHONPATH=server:core python server/scripts/render_structure_validation.py

该脚本只用于人工校准结构层，不输出买卖点。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2] if len(SCRIPT_PATH.parents) > 2 else Path.cwd()
SERVER = ROOT / 'server'
CORE = ROOT / 'core'
for p in (SERVER, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.core.ema_utils import ema_list, get_stage, get_structure, _reg_slope  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


MIN_BARS = 25

DEFAULT_SAMPLES = [
    {'name': '科创50', 'asset_type': 'market', 'table': 'index_daily', 'code': '000688.SH'},
    {'name': '中证全指', 'asset_type': 'market', 'table': 'index_daily', 'code': '000985.CSI'},
    {'name': '元件', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '881270.TI'},
    {'name': '共封装光学(CPO)', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886033.TI'},
    {'name': '存储芯片', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886042.TI'},
    {'name': '圣邦股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300661.SZ'},
    {'name': '美年健康', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '002044.SZ'},
    {'name': '绿的谐波', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688017.SH'},
    {'name': '太辰光', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300570.SZ'},
    {'name': '中际旭创', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300308.SZ'},
    {'name': '胜宏科技', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300476.SZ'},
    {'name': '永鼎股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '600105.SH'},
    {'name': '长川科技', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300604.SZ'},
]

STRUCTURE_COLORS = {
    '上涨趋势': '#7f1d1d',
    '区间震荡': '#1e3a8a',
    '下降趋势': '#14532d',
    '--': '#374151',
}

STAGE_MARKERS = {
    '上行': '上',
    '加速': '速',
    '缩量整理': '整',
    '转弱': '弱',
    '下行': '下',
    '加速跌': '跌',
    '转强': '强',
    '区间顶部': '顶',
    '区间中段': '中',
    '区间底部': '底',
    '放量滞涨': '滞',
    '缩量滞涨': '缩滞',
}


def _fixture_date(offset: int) -> str:
    from datetime import date, timedelta

    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows() -> List[Dict]:
    rows = []
    close = 100.0
    for idx in range(35):
        close += 1.2
        rows.append({
            'date': _fixture_date(idx),
            'open': close - 0.4,
            'high': close + 1.0,
            'low': close - 1.0,
            'close': close,
            'volume': 100000 + idx * 1000,
        })
    for idx in range(35, 55):
        close += (-1) ** idx * 1.5
        rows.append({
            'date': _fixture_date(idx),
            'open': close - 0.2,
            'high': close + 1.4,
            'low': close - 1.4,
            'close': close,
            'volume': 120000,
        })
    for idx in range(55, 80):
        close -= 1.1
        rows.append({
            'date': _fixture_date(idx),
            'open': close + 0.4,
            'high': close + 1.0,
            'low': close - 1.0,
            'close': close,
            'volume': 110000,
        })
    return rows


def collect_fixture_samples() -> List[Dict]:
    return [{
        'name': 'fixture-P0-structure',
        'asset_type': 'stock',
        'table': 'fixture',
        'code': 'fixture-P0-structure',
        'source': 'offline-fixture',
        'data_quality': 'ok',
        'quality_issues': [],
        'rows': _fixture_rows(),
    }]


def filter_samples(samples: List[Dict], selected_names: List[str]) -> List[Dict]:
    if not selected_names:
        return samples
    selected = set(selected_names)
    return [
        sample for sample in samples
        if sample['name'] in selected or sample['code'] in selected
    ]


def _query_rows(db: TushareDB, table: str, code: str, limit: int) -> List[Dict]:
    rows = db.execute_raw(
        f'SELECT trade_date, open, high, low, close, vol FROM {table} '
        'WHERE ts_code=%s ORDER BY trade_date DESC LIMIT %s',
        [code, limit],
    )
    return list(reversed(rows))


def _normalize(rows: Iterable[Dict]) -> List[Dict]:
    result = []
    for row in rows:
        result.append({
            'date': str(row['trade_date']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('vol') or 0),
        })
    return result


def _normalize_qfq_rows(rows: Iterable[Dict]) -> List[Dict]:
    result = []
    for row in rows:
        result.append({
            'date': str(row['date']),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close']),
            'volume': float(row.get('volume') or row.get('vol') or 0),
            'adjustment_status': row.get('adjustment_status', ''),
        })
    result.sort(key=lambda r: r['date'])
    return result


def validate_price_continuity(rows: List[Dict], *, max_close_gap_pct: float = 35.0,
                              max_open_gap_pct: float = 30.0) -> Tuple[str, List[Dict]]:
    issues: List[Dict] = []
    for index in range(1, len(rows)):
        previous = rows[index - 1]
        current = rows[index]
        prev_close = float(previous.get('close') or 0)
        if prev_close <= 0:
            continue
        open_gap = (float(current.get('open') or 0) / prev_close - 1) * 100
        close_gap = (float(current.get('close') or 0) / prev_close - 1) * 100
        if abs(open_gap) > max_open_gap_pct or abs(close_gap) > max_close_gap_pct:
            issues.append({
                'date': current.get('date'),
                'prev_date': previous.get('date'),
                'prev_close': round(prev_close, 4),
                'open': current.get('open'),
                'close': current.get('close'),
                'open_gap_pct': round(open_gap, 2),
                'close_gap_pct': round(close_gap, 2),
            })
    return ('ok' if not issues else 'suspicious_price_gap'), issues


def collect_samples(limit: int) -> List[Dict]:
    db = TushareDB()
    samples = []
    for spec in DEFAULT_SAMPLES:
        if spec['table'] == 'stock_daily':
            rows = _normalize_qfq_rows(db.query_stock_daily(spec['code'], limit=limit, adj='qfq'))
            source = f"{spec['table']}:{spec['code']}:qfq"
            data_quality, quality_issues = validate_price_continuity(rows)
        else:
            rows = _normalize(_query_rows(db, spec['table'], spec['code'], limit))
            source = f"{spec['table']}:{spec['code']}"
            data_quality, quality_issues = 'ok', []
        samples.append({
            **spec,
            'source': source,
            'rows': rows,
            'data_quality': data_quality,
            'quality_issues': quality_issues,
        })
    return samples


def _round(value: float, digits: int = 4):
    return round(value, digits) if value is not None else None


def structure_metrics(rows: List[Dict], idx: int) -> Dict:
    scoped = rows[:idx + 1]
    closes = [float(row['close']) for row in scoped]
    highs = [float(row['high']) for row in scoped]
    lows = [float(row['low']) for row in scoped]
    volumes = [float(row.get('volume') or 0) for row in scoped]
    opens = [float(row['open']) for row in scoped]

    if len(closes) < MIN_BARS:
        return {
            'date': rows[idx]['date'],
            'structure': '--',
            'stage': '--',
            'metrics': {},
            'reason': f'不足 {MIN_BARS} 根 K 线',
        }

    structure = get_structure(closes)
    stage = get_stage(
        closes,
        structure=structure,
        highs=highs,
        lows=lows,
        volumes=volumes,
        opens_p=opens,
    )

    ema5 = ema_list(closes, 5)
    ema10 = ema_list(closes, 10)
    ema12 = ema_list(closes, 12)
    ema20 = ema_list(closes, 20)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    ema12_slope_pct = None
    bias_ema12_pct = None
    if len(e12_recent) >= 5 and e12_recent[0]:
        ema12_slope = _reg_slope(e12_recent)
        ema12_slope_pct = ema12_slope / e12_recent[0] * 100
        bias_ema12_pct = (closes[-1] - e12_recent[-1]) / e12_recent[-1] * 100 if e12_recent[-1] else None

    e5_recent = [v for v in ema5[-5:] if v is not None]
    ema5_slope_pct = None
    if len(e5_recent) >= 3 and e5_recent[0]:
        ema5_slope_pct = _reg_slope(e5_recent) / e5_recent[0] * 100

    close3_slope_pct = None
    close3 = closes[-3:]
    if len(close3) >= 3 and close3[0]:
        close3_slope_pct = _reg_slope(close3) / close3[0] * 100

    bull_arrange = bool(ema5[-1] and ema10[-1] and ema20[-1] and ema5[-1] > ema10[-1] > ema20[-1])
    bear_arrange = bool(ema5[-1] and ema10[-1] and ema20[-1] and ema5[-1] < ema10[-1] < ema20[-1])
    range_position_15_pct = None
    if len(highs) >= 15 and len(lows) >= 15:
        lo = min(lows[-15:])
        hi = max(highs[-15:])
        if hi > lo:
            range_position_15_pct = (closes[-1] - lo) / (hi - lo) * 100

    reason = []
    if structure == '上涨趋势':
        reason.append('EMA12斜率、BIAS、多头排列和短期动量均满足上涨趋势')
    elif structure == '下降趋势':
        reason.append('EMA12斜率、BIAS和短期动量满足下降趋势')
    elif structure == '区间震荡':
        reason.append('趋势条件不完整或短期动量与长周期方向冲突，按旧算法归为区间震荡')
    else:
        reason.append('结构待确认')
    if stage and stage != '--':
        reason.append(f'阶段={stage}')

    return {
        'date': rows[idx]['date'],
        'idx': idx,
        'structure': structure,
        'stage': stage,
        'metrics': {
            'ema5': _round(ema5[-1]),
            'ema10': _round(ema10[-1]),
            'ema12': _round(ema12[-1]),
            'ema20': _round(ema20[-1]),
            'ema12_slope_pct': _round(ema12_slope_pct),
            'bias_ema12_pct': _round(bias_ema12_pct),
            'ema5_slope_pct': _round(ema5_slope_pct),
            'close3_slope_pct': _round(close3_slope_pct),
            'bull_arrange': bull_arrange,
            'bear_arrange': bear_arrange,
            'range_position_15_pct': _round(range_position_15_pct, 2),
        },
        'reason': '；'.join(reason),
    }


def detect_all_structure_states(rows: List[Dict]) -> List[Dict]:
    return [structure_metrics(rows, idx) for idx in range(len(rows))]


def _segments(states: List[Dict]) -> List[Tuple[int, int, str]]:
    if not states:
        return []
    result = []
    start = 0
    current = states[0]['structure']
    for idx, state in enumerate(states[1:], start=1):
        if state['structure'] != current:
            result.append((start, idx - 1, current))
            start = idx
            current = state['structure']
    result.append((start, len(states) - 1, current))
    return result


def render(samples: List[Dict], output: Path) -> None:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import Rectangle

    font_path = next((
        path for path in (
            '/System/Library/Fonts/PingFang.ttc',
            '/System/Library/Fonts/STHeiti Medium.ttc',
            '/System/Library/Fonts/Hiragino Sans GB.ttc',
            '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
            '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf',
        )
        if os.path.exists(path)
    ), None)
    font = FontProperties(fname=font_path) if font_path else None
    plt.rcParams['axes.unicode_minus'] = False

    rows_count = max(1, (len(samples) + 1) // 2)
    fig, axes = plt.subplots(rows_count, 2, figsize=(20, rows_count * 5.6), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    for ax, sample in zip(axes_list, samples):
        rows = sample.get('rows') or []
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            continue
        states = detect_all_structure_states(rows)
        y_min = min(row['low'] for row in rows)
        y_max = max(row['high'] for row in rows)
        y_range = y_max - y_min

        for start, end, structure in _segments(states):
            ax.axvspan(
                start - 0.5,
                end + 0.5,
                color=STRUCTURE_COLORS.get(structure, '#374151'),
                alpha=0.16,
                linewidth=0,
            )

        for i, k in enumerate(rows):
            color = '#ef4444' if k['close'] >= k['open'] else '#22c55e'
            ax.vlines(i, k['low'], k['high'], color=color, linewidth=0.8, alpha=0.8)
            lower = min(k['open'], k['close'])
            height = max(abs(k['close'] - k['open']), y_range * 0.002)
            ax.add_patch(Rectangle(
                (i - 0.28, lower), 0.56, height,
                facecolor=color, edgecolor=color, alpha=0.72,
            ))

        last_stage_idx = {}
        for state in states:
            stage = state.get('stage') or '--'
            label = STAGE_MARKERS.get(stage)
            if not label:
                continue
            idx = state['idx']
            # 同一阶段密集出现时每 5 根标一次，避免图面糊掉。
            if stage in last_stage_idx and idx - last_stage_idx[stage] < 5:
                continue
            last_stage_idx[stage] = idx
            ax.text(
                idx, y_max + y_range * 0.035, label,
                color='#e5e7eb', fontsize=7.5, ha='center', va='bottom',
                fontproperties=font, zorder=7,
            )

        counts = {}
        for state in states:
            counts[state['structure']] = counts.get(state['structure'], 0) + 1
        compact_counts = ' '.join(f'{key}{value}' for key, value in counts.items())
        quality_label = ''
        if sample.get('data_quality') and sample.get('data_quality') != 'ok':
            quality_label = f" | ⚠ {sample['data_quality']}({len(sample.get('quality_issues') or [])})"
        title = (
            f"{sample['name']} · {sample['asset_type']}\n"
            f"{rows[0]['date']}~{rows[-1]['date']} | {compact_counts}{quality_label}"
        )
        ax.set_title(title, color='#e5e7eb', fontsize=10.5, fontproperties=font)
        ax.set_facecolor('#10131f')
        ax.grid(color='#283044', linestyle='--', linewidth=0.45, alpha=0.55)
        ax.set_ylim(y_min - y_range * 0.08, y_max + y_range * 0.12)
        for spine in ax.spines.values():
            spine.set_color('#374151')
        ax.tick_params(colors='#cbd5e1', labelsize=8)
        step = max(1, len(rows) // 6)
        ticks = list(range(0, len(rows), step))
        labels = [datetime.strptime(rows[i]['date'], '%Y%m%d').strftime('%m-%d') for i in ticks]
        ax.set_xticks(ticks)
        ax.set_xticklabels(labels, fontproperties=font)

    for ax in axes_list[len(samples):]:
        ax.axis('off')

    handles = [
        plt.Rectangle((0, 0), 1, 1, color=color, alpha=0.35, label=label)
        for label, color in STRUCTURE_COLORS.items()
    ]
    leg = fig.legend(handles=handles, loc='upper center', ncol=4,
                     bbox_to_anchor=(0.5, 0.995), facecolor='#111827',
                     edgecolor='#374151', prop=font)
    for text in leg.get_texts():
        text.set_color('#e5e7eb')
    fig.suptitle(
        '3L 结构/阶段 P0-structure 验证总览：只验证结构，不输出买卖点',
        color='#e5e7eb', fontsize=16, y=1.012, fontproperties=font,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())


def build_summary(samples: List[Dict]) -> List[Dict]:
    summary = []
    for sample in samples:
        rows = sample.get('rows') or []
        states = detect_all_structure_states(rows) if rows else []
        summary.append({
            'name': sample['name'],
            'asset_type': sample['asset_type'],
            'source': sample['source'],
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'data_quality': sample.get('data_quality', 'ok'),
            'quality_issues': sample.get('quality_issues', []),
            'states': states,
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=90)
    parser.add_argument('--output', default='/tmp/structure_validation_overview.png')
    parser.add_argument('--summary', default='/tmp/structure_validation_summary.json')
    parser.add_argument(
        '--sample',
        action='append',
        default=[],
        help='只渲染指定样本名或代码；可重复传入。不传则渲染全部默认样本。',
    )
    parser.add_argument(
        '--fixture',
        action='store_true',
        help='使用内置离线 fixture 生成验证图，适合本地没有 MySQL 时跑结构回归。',
    )
    args = parser.parse_args()

    samples = collect_fixture_samples() if args.fixture else collect_samples(args.limit)
    samples = filter_samples(samples, args.sample)
    output = Path(args.output)
    render(samples, output)

    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(build_summary(samples), ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    print(output)
    print(summary_path)


if __name__ == '__main__':
    main()
