#!/usr/bin/env python3
"""生成 3L 多日供需转换区间 P0.3 验证图。

P0.3 是实验旁路：只验证“波段方向切换窗口”，不输出买卖点，不接生产页面。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2] if len(SCRIPT_PATH.parents) > 2 else Path.cwd()
for path in (ROOT / 'server', ROOT / 'core'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.core.supply_demand_transition_zone_detector import detect_transition_zones  # noqa: E402
from backend.core.wave_structure_detector import judge_wave_structure  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


SAMPLES = [
    {'name': '科创50', 'asset_type': 'market', 'table': 'index_daily', 'code': '000688.SH'},
    {'name': '中证全指', 'asset_type': 'market', 'table': 'index_daily', 'code': '000985.CSI'},
    {'name': '元件', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '881270.TI'},
    {'name': 'CPO', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886033.TI'},
    {'name': '存储芯片', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886042.TI'},
    {'name': '中国巨石', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '600176.SH'},
    {'name': '太辰光', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300570.SZ'},
    {'name': '普冉股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688766.SH'},
    {'name': '圣邦股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300661.SZ'},
    {'name': '美年健康', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '002044.SZ'},
]

MANUAL_ANCHORS = {
    '000688.SH': [
        {'start': '20260612', 'end': '20260615', 'label': '人工:下→上?'},
        {'start': '20260709', 'end': '20260711', 'label': '人工:上→下?'},
        {'start': '20260803', 'end': '20260804', 'label': '人工:下→上?'},
        {'start': '20260825', 'end': '20260825', 'label': '人工:最新风险?'},
    ],
}

ZONE_COLORS = {'down_to_up': '#ef4444', 'up_to_down': '#22c55e'}
WAVE_COLORS = {'up': '#ef4444', 'down': '#22c55e', 'flat': '#64748b', None: '#64748b'}


def _to_float(value) -> float:
    return float(value or 0)


def _fixture_date(offset: int) -> str:
    return (date(2026, 6, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows() -> List[Dict]:
    rows: List[Dict] = []
    close = 120.0
    phases = [(-1.1, 24, 100000), (1.8, 7, 150000), (-2.0, 7, 160000), (1.7, 7, 140000)]
    offset = 0
    for step, count, volume in phases:
        for _ in range(count):
            close += step
            rows.append({
                'date': _fixture_date(offset),
                'open': close - 0.35,
                'high': close + 1.0,
                'low': close - 1.0,
                'close': close,
                'volume': volume + offset * 100,
            })
            offset += 1
    return rows


def collect_fixture_samples() -> List[Dict]:
    return [{
        'name': 'fixture-P0.3',
        'asset_type': 'market',
        'table': 'fixture',
        'code': 'fixture-P0.3',
        'source': 'offline-fixture',
        'rows': _fixture_rows(),
    }]


def _normalize_date(value) -> str:
    return str(value).replace('-', '')[:8]


def _date_label(value) -> str:
    text = _normalize_date(value)
    return f'{text[4:6]}-{text[6:]}' if len(text) == 8 else str(value)


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


def _load_rows(db: TushareDB, sample: Dict, limit: int) -> Tuple[List[Dict], str]:
    if sample['table'] == 'stock_daily':
        rows = db.query_stock_daily(sample['code'], limit=limit, adj='qfq')
        return _normalize_rows(rows), f"{sample['table']}:{sample['code']}:qfq"
    rows = _query_rows(db, sample['table'], sample['code'], limit)
    return _normalize_rows(rows), f"{sample['table']}:{sample['code']}"


def _wave_states(rows: List[Dict], asset_type: str) -> List[Dict]:
    states = []
    for idx in range(19, len(rows)):
        state = judge_wave_structure(rows[:idx + 1], asset_type=asset_type)
        states.append({
            'idx': idx,
            'date': rows[idx]['date'],
            'trading_wave': state.get('trading_wave') or {},
            'trading_state': state.get('trading_state'),
            'structure': state.get('structure'),
            'phase': state.get('phase'),
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
        )
        if os.path.exists(path)
    ), None)
    font = FontProperties(fname=font_path) if font_path else None
    plt.rcParams['axes.unicode_minus'] = False
    return font


def _draw_candle(ax, rows: List[Dict], y_range: float):
    from matplotlib.patches import Rectangle

    for idx, row in enumerate(rows):
        color = '#ef4444' if row['close'] >= row['open'] else '#22c55e'
        ax.vlines(idx, row['low'], row['high'], color=color, linewidth=0.75, alpha=0.82)
        lower = min(row['open'], row['close'])
        height = max(abs(row['close'] - row['open']), y_range * 0.002)
        ax.add_patch(Rectangle((idx - 0.28, lower), 0.56, height, facecolor=color, edgecolor=color, alpha=0.72))


def _date_to_idx(rows: List[Dict], value: str) -> int | None:
    target = _normalize_date(value)
    for idx, row in enumerate(rows):
        if _normalize_date(row['date']) >= target:
            return idx
    return None


def _render_sample(ax, sample: Dict, rows: List[Dict], font) -> Dict:
    from matplotlib.patches import Rectangle

    states = _wave_states(rows, sample['asset_type'])
    result = detect_transition_zones(rows, asset_type=sample['asset_type'], wave_states=states)
    lows = [row['low'] for row in rows]
    highs = [row['high'] for row in rows]
    y_min, y_max = min(lows), max(highs)
    y_range = max(y_max - y_min, 1e-6)

    _draw_candle(ax, rows, y_range)
    for start, end, direction in _wave_segments(states):
        ax.axvspan(start - 0.5, end + 0.5, ymin=0, ymax=0.045, color=WAVE_COLORS.get(direction, '#64748b'), alpha=0.38, linewidth=0)

    zones = result.get('zones', [])
    latest_zone = result.get('latest_zone') or {}
    for zone in zones:
        color = ZONE_COLORS.get(zone['type'], '#94a3b8')
        start = int(zone['start_idx'])
        end = int(zone['end_idx'])
        alpha = {'primary': 0.20, 'secondary': 0.12, 'muted': 0.05}.get(zone.get('display_level'), 0.12)
        ax.axvspan(start - 0.5, end + 0.5, color=color, alpha=alpha, linewidth=0)
        ax.add_patch(Rectangle((start - 0.5, y_min - y_range * 0.02), max(1, end - start + 1), y_range * 1.09, fill=False, edgecolor=color, linewidth=1.1, linestyle='-', alpha=0.72))
        is_latest = zone.get('pivot_date') == latest_zone.get('pivot_date')
        if zone.get('tier') == 'core' or is_latest:
            label = f"{'下→上' if zone['type'] == 'down_to_up' else '上→下'} {zone.get('tier')} {zone['confidence']}"
            ax.text(start, y_max + y_range * 0.045, label, color=color, fontsize=7.5, fontproperties=font, ha='left', va='bottom')

    for anchor in MANUAL_ANCHORS.get(sample['code'], []):
        start = _date_to_idx(rows, anchor['start'])
        end = _date_to_idx(rows, anchor['end'])
        if start is None or end is None:
            continue
        ax.add_patch(Rectangle((start - 0.5, y_min - y_range * 0.045), max(1, end - start + 1), y_range * 1.16, fill=False, edgecolor='#facc15', linewidth=1.25, linestyle='--', alpha=0.95))
        ax.text(start, y_min - y_range * 0.075, anchor['label'], color='#facc15', fontsize=7.2, fontproperties=font, ha='left', va='top')

    latest = result.get('latest_zone') or {}
    latest_label = '--'
    if latest:
        latest_label = f"{latest.get('start_date')}~{latest.get('end_date')} {latest.get('type')} {latest.get('status')} {latest.get('confidence')}"
    core_count = sum(1 for zone in result.get('zones', []) if zone.get('tier') == 'core')
    watch_count = sum(1 for zone in result.get('zones', []) if zone.get('tier') == 'watch')
    ax.set_title(
        f"{sample['name']} {sample['code']} | {rows[0]['date']}~{rows[-1]['date']} | 核心{core_count} 关注{watch_count} | 最新 {latest_label}",
        color='#e5e7eb',
        fontsize=10,
        fontproperties=font,
    )
    ax.set_ylim(y_min - y_range * 0.12, y_max + y_range * 0.12)
    ax.set_facecolor('#10131f')
    ax.grid(color='#283044', linestyle='--', linewidth=0.45, alpha=0.55)
    for spine in ax.spines.values():
        spine.set_color('#374151')
    ax.tick_params(colors='#cbd5e1', labelsize=8)
    ticks = list(range(0, len(rows), max(1, len(rows) // 7)))
    ax.set_xticks(ticks)
    ax.set_xticklabels([_date_label(rows[idx]['date']) for idx in ticks], fontproperties=font)
    ax.text(0, y_min - y_range * 0.105, '底部色带：红=上涨波段 绿=下降波段；实框=算法区间；黄虚框=人工锚点', color='#cbd5e1', fontsize=7, fontproperties=font, va='top')
    return result


def build_summary(samples: List[Dict]) -> List[Dict]:
    summaries = []
    for sample in samples:
        rows = sample.get('rows') or []
        result = detect_transition_zones(rows, asset_type=sample['asset_type']) if rows else {}
        data_quality, quality_issues = validate_price_continuity(rows) if sample.get('table') == 'stock_daily' else ('ok', [])
        summaries.append({
            **sample,
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'data_quality': data_quality,
            'quality_issues': quality_issues,
            'zones': result.get('zones', []),
            'latest_zone': result.get('latest_zone'),
        })
    return summaries


def render(samples: List[Dict], output: Path, summary: Path, limit: int):
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    db = TushareDB()
    font = _setup_font()
    rows_count = max(1, (len(samples) + 1) // 2)
    fig, axes = plt.subplots(rows_count, 2, figsize=(22, rows_count * 5.9), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    summaries = []
    for ax, sample in zip(axes_list, samples):
        rows, source = _load_rows(db, sample, limit)
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            summaries.append({**sample, 'source': source, 'error': '无数据'})
            continue
        data_quality, quality_issues = validate_price_continuity(rows) if sample['table'] == 'stock_daily' else ('ok', [])
        result = _render_sample(ax, sample, rows, font)
        summaries.append({
            **sample,
            'source': source,
            'date_range': [rows[0]['date'], rows[-1]['date']],
            'data_quality': data_quality,
            'quality_issues': quality_issues,
            'zones': result.get('zones', []),
            'latest_zone': result.get('latest_zone'),
        })

    for ax in axes_list[len(samples):]:
        ax.axis('off')
    fig.suptitle('3L 多日供需转换区间 P0.3 验证：只识别波段切换窗口，不输出买卖点', color='#e5e7eb', fontsize=16, y=1.01, fontproperties=font)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
    print(summary)


def render_fixture(output: Path, summary: Path) -> None:
    import matplotlib

    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    samples = collect_fixture_samples()
    font = _setup_font()
    fig, ax = plt.subplots(1, 1, figsize=(14, 5.5), dpi=140)
    fig.patch.set_facecolor('#0b1020')
    result = _render_sample(ax, samples[0], samples[0]['rows'], font)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps([{**samples[0], 'zones': result.get('zones', [])}], ensure_ascii=False, indent=2), encoding='utf-8')
    print(output)
    print(summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=120)
    parser.add_argument('--output', default='/tmp/transition_zone_validation.png')
    parser.add_argument('--summary', default='/tmp/transition_zone_validation.json')
    parser.add_argument('--sample', action='append', default=[], help='按名称或代码筛选样本，可重复传入')
    parser.add_argument('--fixture', action='store_true', help='使用离线 fixture，不连接数据库')
    args = parser.parse_args()

    output = Path(args.output)
    summary = Path(args.summary)
    if args.fixture:
        render_fixture(output, summary)
        return

    selected = set(args.sample)
    samples = [
        sample for sample in SAMPLES
        if not selected or sample['name'] in selected or sample['code'] in selected
    ]
    render(samples, output, summary, args.limit)


if __name__ == '__main__':
    main()
