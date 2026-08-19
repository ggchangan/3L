#!/usr/bin/env python3
"""生成 3L 纯关键点识别验证图。

用途：

    PYTHONPATH=server:core python server/scripts/render_pure_keypoint_validation.py

脚本只用于人工校准 P0.1 纯关键点识别算法。它读取当前数据库中的指数、
板块和个股 K 线，生成一张大盘/板块/个股总览图，方便人工讨论哪些点
应该进入 must_include / must_exclude 回归样本。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / 'server'
CORE = ROOT / 'core'
for p in (SERVER, CORE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from backend.core.pure_keypoint_detector import detect_pure_keypoints  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


DEFAULT_SAMPLES = [
    {'name': '科创50', 'asset_type': 'market', 'table': 'index_daily', 'code': '000688.SH'},
    {'name': '中证全指', 'asset_type': 'market', 'table': 'index_daily', 'code': '000985.CSI'},
    {'name': 'CPO', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886033.TI'},
    {'name': '元件', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '881270.TI'},
    {'name': '存储', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886042.TI'},
    {'name': '中国巨石', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '600176.SH'},
    {'name': '太辰光', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300570.SZ'},
    {'name': '普冉股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688766.SH'},
]


def _fixture_date(offset: int) -> str:
    from datetime import date, timedelta

    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows(volume_tail: float = 240, price_tail_high: bool = True) -> List[Dict]:
    highs = [
        100, 102, 104, 106, 108, 110, 112, 114, 113, 112,
        111, 109, 107, 105, 103, 101, 99, 98, 100, 102,
        104, 108, 112, 116, 120, 118, 116, 114, 112, 110,
        108, 106, 104, 102, 100, 98, 96, 95, 97, 99,
        101, 103, 105, 107, 109, 111, 113, 115, 117, 119,
        121, 123, 125, 127, 129, 131, 133, 134, 135, 136,
    ]
    if not price_tail_high:
        highs[-1] = highs[-2] - 1
    lows = [h - 5 for h in highs]
    lows[17] = 90
    lows[37] = 88
    volumes = [
        100, 102, 104, 106, 108, 110, 112, 114, 116, 118,
        120, 122, 124, 126, 128, 130, 132, 134, 136, 138,
        140, 230, 150, 145, 142, 140, 138, 136, 134, 132,
        130, 128, 126, 124, 122, 120, 118, 70, 115, 116,
        118, 120, 122, 124, 126, 128, 130, 132, 134, 136,
        138, 140, 142, 144, 146, 148, 150, 152, 154, volume_tail,
    ]
    rows = []
    for i, (high, low, volume) in enumerate(zip(highs, lows, volumes)):
        close = (high + low) / 2
        rows.append({
            'date': _fixture_date(i),
            'open': close,
            'high': float(high),
            'low': float(low),
            'close': close,
            'volume': float(volume),
        })
    return rows


def collect_fixture_samples() -> List[Dict]:
    specs = [
        ('fixture-科创50', 'market', 180, True),
        ('fixture-中证全指', 'market', 170, False),
        ('fixture-CPO', 'sector', 245, False),
        ('fixture-元件', 'sector', 235, True),
        ('fixture-存储', 'sector', 225, False),
        ('fixture-中国巨石', 'stock', 255, False),
        ('fixture-太辰光', 'stock', 265, True),
        ('fixture-普冉股份', 'stock', 275, False),
    ]
    return [
        {
            'name': name,
            'asset_type': asset_type,
            'table': 'fixture',
            'code': name,
            'source': 'offline-fixture',
            'rows': _fixture_rows(volume_tail=volume_tail, price_tail_high=price_tail_high),
        }
        for name, asset_type, volume_tail, price_tail_high in specs
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


def collect_samples(limit: int) -> List[Dict]:
    db = TushareDB()
    samples = []
    for spec in DEFAULT_SAMPLES:
        rows = _query_rows(db, spec['table'], spec['code'], limit)
        samples.append({
            **spec,
            'source': f"{spec['table']}:{spec['code']}",
            'rows': _normalize(rows),
        })
    return samples


def render(samples: List[Dict], output: Path) -> None:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties
    from matplotlib.patches import Rectangle

    font_path = '/System/Library/Fonts/PingFang.ttc'
    if not os.path.exists(font_path):
        font_path = '/System/Library/Fonts/STHeiti Medium.ttc'
    font = FontProperties(fname=font_path) if os.path.exists(font_path) else None
    plt.rcParams['axes.unicode_minus'] = False

    rows_count = max(1, (len(samples) + 1) // 2)
    fig, axes = plt.subplots(rows_count, 2, figsize=(19, rows_count * 5.5), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    for ax, sample in zip(axes_list, samples):
        rows = sample.get('rows') or []
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            continue
        result = detect_pure_keypoints(rows, asset_type=sample['asset_type'])
        points = result['points']
        y_range = max(r['high'] for r in rows) - min(r['low'] for r in rows)

        for i, k in enumerate(rows):
            color = '#ef4444' if k['close'] >= k['open'] else '#22c55e'
            ax.vlines(i, k['low'], k['high'], color=color, linewidth=0.8, alpha=0.8)
            lower = min(k['open'], k['close'])
            height = max(abs(k['close'] - k['open']), y_range * 0.002)
            ax.add_patch(Rectangle(
                (i - 0.28, lower), 0.56, height,
                facecolor=color, edgecolor=color, alpha=0.75,
            ))

        for point in points:
            idx = point['idx']
            alpha = 1.0 if point['status'] == 'confirmed' else 0.50
            edge = 'white' if point['status'] == 'confirmed' else '#9ca3af'
            if point['type'] == 'price_high':
                ax.scatter(idx, point['price'], s=70, marker='^', color='#f97316',
                           edgecolors=edge, linewidths=0.7, alpha=alpha, zorder=5)
            elif point['type'] == 'price_low':
                ax.scatter(idx, point['price'], s=70, marker='v', color='#10b981',
                           edgecolors=edge, linewidths=0.7, alpha=alpha, zorder=5)
            elif point['type'] == 'volume_peak':
                ax.scatter(idx, rows[idx]['high'] + y_range * 0.045, s=58, marker='o',
                           facecolors='none', edgecolors='#e11d48', linewidths=1.4,
                           alpha=alpha, zorder=5)
            elif point['type'] == 'volume_trough':
                ax.scatter(idx, rows[idx]['low'] - y_range * 0.045, s=58, marker='s',
                           facecolors='none', edgecolors='#818cf8', linewidths=1.4,
                           alpha=alpha, zorder=5)

        counts = {
            kind: sum(1 for p in points if p['type'] == kind)
            for kind in ('price_high', 'price_low', 'volume_peak', 'volume_trough')
        }
        candidates = sum(1 for p in points if p['status'] == 'candidate')
        title = (
            f"{sample['name']} · {sample['asset_type']}\n"
            f"{rows[0]['date']}~{rows[-1]['date']} | "
            f"高{counts['price_high']} 低{counts['price_low']} "
            f"量峰{counts['volume_peak']} 量谷{counts['volume_trough']} "
            f"候选{candidates}"
        )
        ax.set_title(title, color='#e5e7eb', fontsize=11, fontproperties=font)
        ax.set_facecolor('#10131f')
        ax.grid(color='#283044', linestyle='--', linewidth=0.45, alpha=0.55)
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
        plt.Line2D([0], [0], marker='^', color='none', markerfacecolor='#f97316',
                   markeredgecolor='#f97316', markersize=8, label='确认/候选前高'),
        plt.Line2D([0], [0], marker='v', color='none', markerfacecolor='#10b981',
                   markeredgecolor='#10b981', markersize=8, label='确认/候选前低'),
        plt.Line2D([0], [0], marker='o', color='none', markerfacecolor='none',
                   markeredgecolor='#e11d48', markersize=8, label='局部量峰'),
        plt.Line2D([0], [0], marker='s', color='none', markerfacecolor='none',
                   markeredgecolor='#818cf8', markersize=8, label='局部量谷'),
    ]
    leg = fig.legend(handles=handles, loc='upper center', ncol=4,
                     bbox_to_anchor=(0.5, 0.995), facecolor='#111827',
                     edgecolor='#374151', prop=font)
    for text in leg.get_texts():
        text.set_color('#e5e7eb')
    fig.suptitle(
        '3L 纯关键点识别 P0.1 验证总览：只标客观关键点，不解释买卖含义',
        color='#e5e7eb', fontsize=16, y=1.012, fontproperties=font,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=65)
    parser.add_argument('--output', default='/tmp/pure_keypoint_validation_overview.png')
    parser.add_argument('--summary', default='/tmp/pure_keypoint_validation_summary.json')
    parser.add_argument(
        '--fixture',
        action='store_true',
        help='使用内置离线 fixture 生成验证图，适合本地没有 MySQL 时跑 P0.1 回归。',
    )
    args = parser.parse_args()

    samples = collect_fixture_samples() if args.fixture else collect_samples(args.limit)
    output = Path(args.output)
    render(samples, output)

    summary = []
    for sample in samples:
        result = detect_pure_keypoints(sample['rows'], asset_type=sample['asset_type'])
        summary.append({
            'name': sample['name'],
            'asset_type': sample['asset_type'],
            'source': sample['source'],
            'date_range': [sample['rows'][0]['date'], sample['rows'][-1]['date']] if sample['rows'] else [],
            'points': result['points'],
        })
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
    print(summary_path)


if __name__ == '__main__':
    main()
