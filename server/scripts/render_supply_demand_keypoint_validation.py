#!/usr/bin/env python3
"""生成 3L 供需格局转换关键点 P0.2 验证图。

用途：

    PYTHONPATH=server:core python server/scripts/render_supply_demand_keypoint_validation.py

该脚本只用于人工校准 P0.2 定义。它把供需转换点画到真实 K 线上：

- 突破 / 跌破；
- 突破失败 / 跌破失败；
- 上涨中继 / 下跌中继；
- 向上反转 / 向下反转；
- 恐慌滞跌 / 高潮滞涨。

注意：这些点不是买卖点，图上也不输出买卖建议。
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

from backend.core.supply_demand_keypoint_detector import (  # noqa: E402
    MIN_BARS,
    detect_supply_demand_keypoints,
)
from backend.core.wave_structure_detector import judge_wave_structure  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


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


POINT_STYLES = {
    'upward_breakout': {'label': '突↑', 'color': '#ef4444', 'marker': '^', 'offset': 0.055},
    'downward_breakdown': {'label': '破↓', 'color': '#22c55e', 'marker': 'v', 'offset': -0.055},
    'failed_breakout': {'label': '突败', 'color': '#f97316', 'marker': 'X', 'offset': 0.08},
    'failed_breakdown': {'label': '破败', 'color': '#38bdf8', 'marker': 'X', 'offset': -0.08},
    'bullish_continuation': {'label': '继↑', 'color': '#facc15', 'marker': 'P', 'offset': 0.045},
    'bearish_continuation': {'label': '继↓', 'color': '#a3e635', 'marker': 'P', 'offset': -0.045},
    'bullish_reversal': {'label': '反↑', 'color': '#fb7185', 'marker': '*', 'offset': 0.07},
    'bearish_reversal': {'label': '反↓', 'color': '#34d399', 'marker': '*', 'offset': -0.07},
    'panic_stagnation': {'label': '恐慌', 'color': '#f43f5e', 'marker': 'D', 'offset': -0.10},
    'climax_stagnation': {'label': '高潮', 'color': '#c084fc', 'marker': 'D', 'offset': 0.10},
}


WAVE_BAND_COLORS = {
    'up': '#ef4444',
    'down': '#22c55e',
    'flat': '#64748b',
    None: '#64748b',
}


def _fixture_date(offset: int) -> str:
    from datetime import date, timedelta

    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows() -> List[Dict]:
    rows = []
    close = 100.0
    for i in range(25):
        close += 1
        rows.append({
            'date': _fixture_date(i),
            'open': close - 0.5,
            'high': close + 1,
            'low': close - 1,
            'close': close,
            'volume': 100000 + i * 1200,
        })
    rows.extend([
        {'date': _fixture_date(25), 'open': 125, 'high': 126, 'low': 122, 'close': 123, 'volume': 85000},
        {'date': _fixture_date(26), 'open': 123, 'high': 124, 'low': 121.5, 'close': 122.8, 'volume': 65000},
        {'date': _fixture_date(27), 'open': 123, 'high': 130, 'low': 122, 'close': 129, 'volume': 180000},
        {'date': _fixture_date(28), 'open': 129, 'high': 130, 'low': 121, 'close': 122, 'volume': 240000},
        {'date': _fixture_date(29), 'open': 121, 'high': 123, 'low': 114, 'close': 120.5, 'volume': 260000},
    ])
    return rows


def collect_fixture_samples() -> List[Dict]:
    return [{
        'name': 'fixture-P0.2',
        'asset_type': 'stock',
        'table': 'fixture',
        'code': 'fixture-P0.2',
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


def detect_all_transition_points(rows: List[Dict], asset_type: str) -> List[Dict]:
    points = []
    for idx in range(MIN_BARS - 1, len(rows)):
        result = detect_supply_demand_keypoints(rows, asset_type=asset_type, end_idx=idx)
        for point in result.get('transition_points', []):
            enriched = dict(point)
            enriched['structure'] = result.get('structure')
            enriched['stage'] = result.get('stage')
            enriched['volume_price_action'] = result.get('volume_price_action', {})
            enriched['current_zone'] = result.get('current_zone', {})
            points.append(enriched)
    return points


def detect_all_wave_states(rows: List[Dict], asset_type: str) -> List[Dict]:
    states = []
    for idx in range(MIN_BARS - 1, len(rows)):
        state = judge_wave_structure(rows[:idx + 1], asset_type=asset_type)
        states.append({
            'idx': idx,
            'date': rows[idx]['date'],
            'structure': state.get('structure'),
            'phase': state.get('phase'),
            'trading_wave': state.get('trading_wave') or {},
            'trading_state': state.get('trading_state'),
        })
    return states


def _wave_segments(states: List[Dict]) -> List[Tuple[int, int, str]]:
    if not states:
        return []
    result = []
    start = states[0]['idx']
    end = start
    current = (states[0].get('trading_wave') or {}).get('direction')
    for state in states[1:]:
        direction = (state.get('trading_wave') or {}).get('direction')
        if direction != current:
            result.append((start, end, current))
            start = state['idx']
            current = direction
        end = state['idx']
    result.append((start, end, current))
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
    fig, axes = plt.subplots(rows_count, 2, figsize=(20, rows_count * 5.8), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    for ax, sample in zip(axes_list, samples):
        rows = sample.get('rows') or []
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            continue
        points = detect_all_transition_points(rows, sample['asset_type'])
        wave_states = detect_all_wave_states(rows, sample['asset_type'])
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

        for start, end, direction in _wave_segments(wave_states):
            ax.axvspan(
                start - 0.5,
                end + 0.5,
                ymin=0.0,
                ymax=0.045,
                color=WAVE_BAND_COLORS.get(direction, '#64748b'),
                alpha=0.38,
                linewidth=0,
            )
        if rows:
            ax.text(
                0,
                min(r['low'] for r in rows) - y_range * 0.07,
                '底部色带：交易波段 红=上涨 绿=下降 灰=横向',
                color='#cbd5e1',
                fontsize=7.2,
                va='top',
                fontproperties=font,
            )

        for point in points:
            style = POINT_STYLES.get(point['type'])
            if not style:
                continue
            idx = point['idx']
            if idx < 0 or idx >= len(rows):
                continue
            y = rows[idx]['high'] + y_range * style['offset'] if style['offset'] > 0 else rows[idx]['low'] + y_range * style['offset']
            tier = point.get('tier') or 'watch'
            display_level = point.get('display_level') or 'secondary'
            alpha = {'primary': 1.0, 'secondary': 0.72, 'muted': 0.28}.get(display_level, 0.72)
            if point.get('status') != 'confirmed':
                alpha *= 0.78
            size = {'core': 90, 'watch': 70, 'weak': 40}.get(tier, 70)
            ax.scatter(
                idx, y, s=size, marker=style['marker'], color=style['color'],
                edgecolors='white', linewidths=0.6, alpha=alpha, zorder=6,
            )
            if tier == 'core':
                ax.text(
                    idx, y + y_range * 0.012, style['label'],
                    color=style['color'], fontsize=7.5, ha='center', va='bottom',
                    fontproperties=font, zorder=7,
                )

        counts = {kind: sum(1 for p in points if p['type'] == kind) for kind in POINT_STYLES}
        compact_counts = ' '.join(
            f"{POINT_STYLES[k]['label']}{v}" for k, v in counts.items() if v
        ) or '无供需点'
        tier_counts = {
            'core': sum(1 for p in points if p.get('tier') == 'core'),
            'watch': sum(1 for p in points if p.get('tier') == 'watch'),
            'weak': sum(1 for p in points if p.get('tier') == 'weak'),
        }
        tier_label = f"核心{tier_counts['core']} 关注{tier_counts['watch']} 弱提示{tier_counts['weak']}"
        quality_label = ''
        if sample.get('data_quality') and sample.get('data_quality') != 'ok':
            quality_label = f" | ⚠ {sample['data_quality']}({len(sample.get('quality_issues') or [])})"
        final_state = wave_states[-1].get('trading_state') if wave_states else '--'
        title = (
            f"{sample['name']} · {sample['asset_type']}\n"
            f"{rows[0]['date']}~{rows[-1]['date']} | {tier_label} | {compact_counts}{quality_label} | {final_state}"
        )
        ax.set_title(title, color='#e5e7eb', fontsize=10.5, fontproperties=font)
        ax.set_ylim(
            min(r['low'] for r in rows) - y_range * 0.10,
            max(r['high'] for r in rows) + y_range * 0.13,
        )
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
        plt.Line2D([0], [0], marker=style['marker'], color='none',
                   markerfacecolor=style['color'], markeredgecolor='white',
                   markersize=8, label=style['label'])
        for style in POINT_STYLES.values()
    ]
    leg = fig.legend(handles=handles, loc='upper center', ncol=10,
                     bbox_to_anchor=(0.5, 0.995), facecolor='#111827',
                     edgecolor='#374151', prop=font)
    for text in leg.get_texts():
        text.set_color('#e5e7eb')
    fig.suptitle(
        '3L 供需格局转换关键点 P0.2 验证总览：只验证定义，不输出买卖点',
        color='#e5e7eb', fontsize=16, y=1.012, fontproperties=font,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())


def build_summary(samples: List[Dict]) -> List[Dict]:
    summary = []
    for sample in samples:
        rows = sample.get('rows') or []
        points = detect_all_transition_points(rows, sample['asset_type']) if rows else []
        wave_states = detect_all_wave_states(rows, sample['asset_type']) if rows else []
        summary.append({
            'name': sample['name'],
            'asset_type': sample['asset_type'],
            'source': sample['source'],
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'data_quality': sample.get('data_quality', 'ok'),
            'quality_issues': sample.get('quality_issues', []),
            'wave_states_tail': wave_states[-10:],
            'transition_points': points,
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=90)
    parser.add_argument('--output', default='/tmp/supply_demand_keypoint_validation_overview.png')
    parser.add_argument('--summary', default='/tmp/supply_demand_keypoint_validation_summary.json')
    parser.add_argument(
        '--sample',
        action='append',
        default=[],
        help='只渲染指定样本名或代码；可重复传入。不传则渲染全部默认样本。',
    )
    parser.add_argument(
        '--fixture',
        action='store_true',
        help='使用内置离线 fixture 生成验证图，适合本地没有 MySQL 时跑 P0.2 回归。',
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
