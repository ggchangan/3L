#!/usr/bin/env python3
"""生成 3L 结构化供需事件 P0.4-C 验证图。

该脚本是实验旁路，只用于人工校验“供需事件是否识别正确”：

- 价格 K 线；
- 底部交易波段色带；
- 供需事件标注；
- 结构/阶段/位置口径不一致时在摘要中暴露警告。

注意：供需事件不是买卖点，本图不输出任何买卖建议。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2] if len(SCRIPT_PATH.parents) > 2 else Path.cwd()
for path in (ROOT / 'server', ROOT / 'core'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.core.supply_demand_event_detector import detect_supply_demand_events  # noqa: E402
from backend.core.supply_demand_keypoint_detector import MIN_BARS  # noqa: E402
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
    {'name': '中国巨石', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '600176.SH'},
    {'name': '普冉股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688766.SH'},
]


EVENT_STYLES = {
    'breakout': {'label': '突破', 'color': '#ef4444', 'marker': '^', 'offset': 0.070},
    'failure': {'label': '失败', 'color': '#f97316', 'marker': 'X', 'offset': 0.095},
    'continuation': {'label': '中继', 'color': '#facc15', 'marker': 'P', 'offset': 0.055},
    'reversal': {'label': '反转', 'color': '#fb7185', 'marker': '*', 'offset': 0.085},
    'exhaustion': {'label': '衰竭', 'color': '#c084fc', 'marker': 'D', 'offset': 0.110},
    'unknown': {'label': '事件', 'color': '#94a3b8', 'marker': 'o', 'offset': 0.065},
}

BULLISH_EVENTS = {'upward_breakout', 'failed_breakdown', 'bullish_continuation', 'bullish_reversal', 'panic_stagnation'}
WAVE_BAND_COLORS = {'up': '#ef4444', 'down': '#22c55e', 'flat': '#64748b', None: '#64748b'}


def _to_float(value) -> float:
    return float(value or 0)


def _normalize_date(value) -> str:
    return str(value).replace('-', '')[:8]


def _fixture_date(offset: int) -> str:
    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows() -> List[Dict]:
    rows: List[Dict] = []
    close = 100.0
    for idx in range(35):
        close += 1.0
        rows.append({
            'date': _fixture_date(idx),
            'open': close - 0.5,
            'high': close + 1.0,
            'low': close - 1.0,
            'close': close,
            'volume': 100000 + idx * 1000,
        })
    rows.extend([
        {'date': '20260810', 'open': 135.0, 'high': 136.0, 'low': 132.0, 'close': 133.0, 'volume': 85000},
        {'date': '20260811', 'open': 133.0, 'high': 134.0, 'low': 131.8, 'close': 132.6, 'volume': 65000},
    ])
    return rows


def collect_fixture_samples() -> List[Dict]:
    return [{
        'name': 'fixture-P0.4-C',
        'asset_type': 'stock',
        'table': 'fixture',
        'code': 'fixture-P0.4-C',
        'source': 'offline-fixture',
        'data_quality': 'ok',
        'quality_issues': [],
        'rows': _fixture_rows(),
    }]


def filter_samples(samples: List[Dict], selected_names: List[str]) -> List[Dict]:
    if not selected_names:
        return samples
    selected = set(selected_names)
    return [sample for sample in samples if sample['name'] in selected or sample['code'] in selected]


def _query_rows(db: TushareDB, table: str, code: str, limit: int) -> List[Dict]:
    rows = db.execute_raw(
        f'SELECT trade_date, open, high, low, close, vol FROM {table} '
        'WHERE ts_code=%s ORDER BY trade_date DESC LIMIT %s',
        [code, limit],
    )
    return list(reversed(rows))


def _normalize_rows(rows: Iterable[Dict]) -> List[Dict]:
    result = []
    for row in rows:
        result.append({
            'date': _normalize_date(row.get('trade_date') or row.get('date')),
            'open': _to_float(row.get('open')),
            'high': _to_float(row.get('high')),
            'low': _to_float(row.get('low')),
            'close': _to_float(row.get('close')),
            'volume': _to_float(row.get('vol') or row.get('volume')),
        })
    return sorted(result, key=lambda item: item['date'])


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
    for sample in DEFAULT_SAMPLES:
        if sample['table'] == 'stock_daily':
            rows = _normalize_rows(db.query_stock_daily(sample['code'], limit=limit, adj='qfq'))
            source = f"{sample['table']}:{sample['code']}:qfq"
            data_quality, quality_issues = validate_price_continuity(rows)
        else:
            rows = _normalize_rows(_query_rows(db, sample['table'], sample['code'], limit))
            source = f"{sample['table']}:{sample['code']}"
            data_quality, quality_issues = 'ok', []
        samples.append({
            **sample,
            'source': source,
            'rows': rows,
            'data_quality': data_quality,
            'quality_issues': quality_issues,
        })
    return samples


def detect_all_events(rows: List[Dict], asset_type: str) -> List[Dict]:
    events = []
    for idx in range(MIN_BARS - 1, len(rows)):
        result = detect_supply_demand_events(rows, asset_type=asset_type, end_idx=idx)
        for event in result.get('events', []):
            events.append(event)
    return events


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


def _setup_font():
    import matplotlib.pyplot as plt
    from matplotlib.font_manager import FontProperties

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
    return font


def _draw_candles(ax, rows: List[Dict], y_range: float) -> None:
    from matplotlib.patches import Rectangle

    for idx, row in enumerate(rows):
        color = '#ef4444' if row['close'] >= row['open'] else '#22c55e'
        ax.vlines(idx, row['low'], row['high'], color=color, linewidth=0.8, alpha=0.8)
        lower = min(row['open'], row['close'])
        height = max(abs(row['close'] - row['open']), y_range * 0.002)
        ax.add_patch(Rectangle((idx - 0.28, lower), 0.56, height, facecolor=color, edgecolor=color, alpha=0.75))


def _event_y(row: Dict, y_range: float, event: Dict, style: Dict) -> float:
    subtype = event.get('subtype')
    direction = event.get('direction')
    bullish = subtype in BULLISH_EVENTS or direction == 'bullish'
    if bullish:
        return row['low'] - y_range * style['offset']
    return row['high'] + y_range * style['offset']


def render(samples: List[Dict], output: Path) -> None:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    font = _setup_font()
    rows_count = max(1, (len(samples) + 1) // 2)
    fig, axes = plt.subplots(rows_count, 2, figsize=(20, rows_count * 5.8), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    for ax, sample in zip(axes_list, samples):
        rows = sample.get('rows') or []
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            continue

        events = detect_all_events(rows, sample['asset_type'])
        wave_states = detect_all_wave_states(rows, sample['asset_type'])
        y_min = min(row['low'] for row in rows)
        y_max = max(row['high'] for row in rows)
        y_range = max(y_max - y_min, 1e-6)

        _draw_candles(ax, rows, y_range)
        for start, end, direction in _wave_segments(wave_states):
            ax.axvspan(start - 0.5, end + 0.5, ymin=0.0, ymax=0.045,
                       color=WAVE_BAND_COLORS.get(direction, '#64748b'), alpha=0.38, linewidth=0)

        for event in events:
            idx = event.get('idx')
            if idx is None or idx < 0 or idx >= len(rows):
                continue
            style = EVENT_STYLES.get(event.get('event_type')) or EVENT_STYLES['unknown']
            y = _event_y(rows[idx], y_range, event, style)
            display_level = event.get('display_level') or 'secondary'
            tier = event.get('tier') or 'weak'
            alpha = {'primary': 1.0, 'secondary': 0.74, 'muted': 0.30}.get(display_level, 0.74)
            if not event.get('definition_aligned', True):
                alpha = max(alpha, 0.88)
            size = {'core': 95, 'watch': 72, 'weak': 42}.get(tier, 72)
            edge = '#f8fafc' if event.get('definition_aligned', True) else '#f97316'
            ax.scatter(idx, y, s=size, marker=style['marker'], color=style['color'],
                       edgecolors=edge, linewidths=0.8, alpha=alpha, zorder=6)
            if tier == 'core' or not event.get('definition_aligned', True):
                ax.text(idx, y + y_range * 0.012, style['label'],
                        color=style['color'], fontsize=7.5, ha='center', va='bottom',
                        fontproperties=font, zorder=7)

        counts = {}
        warning_count = 0
        for event in events:
            key = event.get('event_type') or 'unknown'
            counts[key] = counts.get(key, 0) + 1
            if event.get('semantic_warnings'):
                warning_count += 1
        compact_counts = ' '.join(
            f"{EVENT_STYLES.get(k, EVENT_STYLES['unknown'])['label']}{v}" for k, v in counts.items() if v
        ) or '无事件'
        latest_state = wave_states[-1].get('trading_state') if wave_states else '--'
        quality_label = ''
        if sample.get('data_quality') and sample.get('data_quality') != 'ok':
            quality_label = f" | ⚠ 数据断层{len(sample.get('quality_issues') or [])}"
        title = (
            f"{sample['name']} · {sample['asset_type']}\n"
            f"{rows[0]['date']}~{rows[-1]['date']} | {compact_counts} | 定义警告{warning_count}{quality_label} | {latest_state}"
        )
        ax.set_title(title, color='#e5e7eb', fontsize=10.5, fontproperties=font)
        ax.text(0, y_min - y_range * 0.075, '底部色带：交易波段 红=上涨 绿=下降 灰=横向；图中事件≠买卖点',
                color='#cbd5e1', fontsize=7.2, va='top', fontproperties=font)
        ax.set_ylim(y_min - y_range * 0.14, y_max + y_range * 0.16)
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
        for style in EVENT_STYLES.values()
    ]
    leg = fig.legend(handles=handles, loc='upper center', ncol=len(handles),
                     bbox_to_anchor=(0.5, 0.995), facecolor='#111827',
                     edgecolor='#374151', prop=font)
    for text in leg.get_texts():
        text.set_color('#e5e7eb')
    fig.suptitle('3L 结构化供需事件 P0.4-C 验证总览：事件层，不是买卖点',
                 color='#e5e7eb', fontsize=16, y=1.012, fontproperties=font)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())


def build_summary(samples: List[Dict]) -> List[Dict]:
    summary = []
    for sample in samples:
        rows = sample.get('rows') or []
        events = detect_all_events(rows, sample['asset_type']) if rows else []
        summary.append({
            'name': sample['name'],
            'code': sample['code'],
            'asset_type': sample['asset_type'],
            'source': sample.get('source'),
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'data_quality': sample.get('data_quality', 'ok'),
            'quality_issues': sample.get('quality_issues', []),
            'events': events,
            'warning_events': [event for event in events if event.get('semantic_warnings')],
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=120)
    parser.add_argument('--output', default='/tmp/supply_demand_event_validation_overview.png')
    parser.add_argument('--summary', default='/tmp/supply_demand_event_validation_summary.json')
    parser.add_argument('--sample', action='append', default=[], help='按名称或代码筛选样本，可重复传入')
    parser.add_argument('--fixture', action='store_true', help='使用内置离线 fixture，不连接数据库')
    args = parser.parse_args()

    samples = collect_fixture_samples() if args.fixture else collect_samples(args.limit)
    samples = filter_samples(samples, args.sample)
    render(samples, Path(args.output))
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(build_summary(samples), ensure_ascii=False, indent=2), encoding='utf-8')
    print(args.output)
    print(args.summary)


if __name__ == '__main__':
    main()
