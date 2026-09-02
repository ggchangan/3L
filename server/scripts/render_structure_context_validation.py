#!/usr/bin/env python3
"""生成 3L 结构上下文验证图。

该脚本用于人工核验 `detect_3l_structure_context()`：

- 主图：K 线；
- 背景：统一结构上下文（上涨趋势/下降趋势/区间震荡）；
- 顶部色带：主跌风险；
- 底部色带：交易波段；
- 标注：最新结构、阶段、波段位置、风险。

注意：本图是实验旁路，只解释结构上下文，不输出买卖建议。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
for path in (ROOT / 'server', ROOT / 'core'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from backend.core.structure_context_detector import detect_3l_structure_context  # noqa: E402
from backend.core.wave_structure_detector import MIN_BARS  # noqa: E402
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


STRUCTURE_COLORS = {
    '上涨趋势': '#ef4444',
    '下降趋势': '#22c55e',
    '区间震荡': '#60a5fa',
    '未识别': '#64748b',
    None: '#64748b',
}

WAVE_COLORS = {
    'up': '#ef4444',
    'down': '#22c55e',
    'flat': '#64748b',
    None: '#64748b',
}

RISK_COLORS = {
    'high': '#f97316',
    'watch': '#facc15',
    'none': '#64748b',
    None: '#64748b',
}


def _safe_float(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _normalize_date(value) -> str:
    raw = str(value).replace('-', '')[:8]
    return raw


def _fixture_date(offset: int) -> str:
    return (date(2026, 7, 1) + timedelta(days=offset)).strftime('%Y%m%d')


def _fixture_rows() -> List[Dict]:
    rows: List[Dict] = []
    close = 100.0
    for idx in range(28):
        close += 1.2
        rows.append({
            'date': _fixture_date(idx),
            'open': close - 0.6,
            'high': close + 1.0,
            'low': close - 1.2,
            'close': close,
            'volume': 100000 + idx * 1200,
        })
    for idx in range(28, 42):
        close -= 1.6
        rows.append({
            'date': _fixture_date(idx),
            'open': close + 0.7,
            'high': close + 1.3,
            'low': close - 1.0,
            'close': close,
            'volume': 145000 + idx * 900,
        })
    return rows


def collect_fixture_samples() -> List[Dict]:
    return [{
        'name': 'fixture-structure-context',
        'asset_type': 'stock',
        'table': 'fixture',
        'code': 'fixture-structure-context',
        'source': 'offline-fixture',
        'rows': _fixture_rows(),
        'data_quality': 'ok',
        'quality_issues': [],
    }]


def filter_samples(samples: List[Dict], selected_names: List[str]) -> List[Dict]:
    if not selected_names:
        return samples
    selected = set(selected_names)
    return [sample for sample in samples if sample['name'] in selected or sample['code'] in selected]


def _normalize_rows(rows: Iterable[Dict]) -> List[Dict]:
    result = []
    for row in rows:
        result.append({
            'date': _normalize_date(row.get('trade_date') or row.get('date')),
            'open': _safe_float(row.get('open')),
            'high': _safe_float(row.get('high')),
            'low': _safe_float(row.get('low')),
            'close': _safe_float(row.get('close')),
            'volume': _safe_float(row.get('vol') or row.get('volume')),
        })
    return sorted([row for row in result if row['date'] and row['close'] > 0], key=lambda item: item['date'])


def validate_price_continuity(rows: List[Dict], *, max_open_gap_pct: float = 30.0) -> Tuple[str, List[Dict]]:
    issues: List[Dict] = []
    for index in range(1, len(rows)):
        previous = rows[index - 1]
        current = rows[index]
        prev_close = float(previous.get('close') or 0)
        if prev_close <= 0:
            continue
        open_gap = (float(current.get('open') or 0) / prev_close - 1) * 100
        if abs(open_gap) > max_open_gap_pct:
            issues.append({
                'date': current.get('date'),
                'prev_date': previous.get('date'),
                'prev_close': round(prev_close, 4),
                'open': current.get('open'),
                'open_gap_pct': round(open_gap, 2),
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
            raw = db.execute_raw(
                f'SELECT trade_date, open, high, low, close, vol FROM {sample["table"]} '
                'WHERE ts_code=%s ORDER BY trade_date DESC LIMIT %s',
                [sample['code'], limit],
            )
            rows = _normalize_rows(reversed(raw))
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


def detect_all_contexts(rows: List[Dict], asset_type: str) -> List[Dict]:
    contexts = []
    for idx in range(MIN_BARS - 1, len(rows)):
        result = detect_3l_structure_context(rows[:idx + 1], asset_type=asset_type)
        if result.get('status') == 'ok':
            contexts.append({'idx': idx, **result})
    return contexts


def _segments(contexts: List[Dict], key_fn) -> List[Tuple[int, int, str]]:
    if not contexts:
        return []
    result = []
    start = contexts[0]['idx']
    end = start
    current = key_fn(contexts[0])
    for context in contexts[1:]:
        value = key_fn(context)
        if value != current:
            result.append((start, end, current))
            start = context['idx']
            current = value
        end = context['idx']
    result.append((start, end, current))
    return result


def _setup_font():
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
    ]
    for path in candidates:
        if os.path.exists(path):
            font_manager.fontManager.addfont(path)
            font_prop = font_manager.FontProperties(fname=path)
            plt.rcParams['font.family'] = font_prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
            return font_prop
    plt.rcParams['axes.unicode_minus'] = False
    return None


def _draw_candles(ax, rows: List[Dict], y_range: float) -> None:
    for idx, row in enumerate(rows):
        color = '#ef4444' if row['close'] >= row['open'] else '#22c55e'
        ax.vlines(idx, row['low'], row['high'], color=color, linewidth=0.75, alpha=0.82)
        lower = min(row['open'], row['close'])
        height = max(abs(row['close'] - row['open']), y_range * 0.002)
        ax.add_patch(Rectangle((idx - 0.28, lower), 0.56, height, facecolor=color, edgecolor=color, alpha=0.72))


def _format_date(value: str) -> str:
    try:
        return datetime.strptime(str(value).replace('-', '')[:8], '%Y%m%d').strftime('%m-%d')
    except ValueError:
        return str(value)[4:8]


def render(samples: List[Dict], output: Path) -> None:
    font = _setup_font()
    rows_count = max(1, (len(samples) + 1) // 2)
    fig, axes = plt.subplots(rows_count, 2, figsize=(20, rows_count * 5.9), dpi=160)
    fig.patch.set_facecolor('#0b1020')
    axes_list = axes.ravel() if hasattr(axes, 'ravel') else [axes]

    for ax, sample in zip(axes_list, samples):
        rows = sample.get('rows') or []
        if not rows:
            ax.set_title(f"{sample['name']} 无数据", color='#e5e7eb', fontproperties=font)
            continue

        contexts = detect_all_contexts(rows, sample['asset_type'])
        y_min = min(row['low'] for row in rows)
        y_max = max(row['high'] for row in rows)
        y_range = max(y_max - y_min, 1e-6)

        for start, end, structure in _segments(contexts, lambda ctx: ctx['market_structure']['structure']):
            ax.axvspan(start - 0.5, end + 0.5, color=STRUCTURE_COLORS.get(structure, '#64748b'), alpha=0.10, linewidth=0)
        _draw_candles(ax, rows, y_range)
        for start, end, risk in _segments(contexts, lambda ctx: ctx['major_decline_risk']['level']):
            ax.axvspan(start - 0.5, end + 0.5, ymin=0.948, ymax=0.992,
                       color=RISK_COLORS.get(risk, '#64748b'), alpha=0.58, linewidth=0)
        for start, end, direction in _segments(contexts, lambda ctx: (ctx['wave_context']['trading_wave'] or {}).get('direction')):
            ax.axvspan(start - 0.5, end + 0.5, ymin=0.0, ymax=0.042,
                       color=WAVE_COLORS.get(direction, '#64748b'), alpha=0.42, linewidth=0)

        latest = contexts[-1] if contexts else {}
        market = latest.get('market_structure') or {}
        wave_position = latest.get('wave_position') or {}
        risk = latest.get('major_decline_risk') or {}
        position_context = latest.get('position_context') or {}
        quality_label = ''
        if sample.get('data_quality') and sample.get('data_quality') != 'ok':
            quality_label = f" | ⚠ 数据断层{len(sample.get('quality_issues') or [])}"
        title = (
            f"{sample['name']} · {sample['asset_type']}\n"
            f"{rows[0]['date']}~{rows[-1]['date']} | "
            f"{market.get('structure', '--')} · {market.get('stage', '--')} · "
            f"{wave_position.get('label', '--')} | 主跌风险 {risk.get('level', '--')}"
            f"{quality_label}"
        )
        ax.set_title(title, color='#e5e7eb', fontsize=10.5, fontproperties=font)
        details = (
            f"结构依据：{'; '.join((market.get('evidence') or [])[:2]) or '--'}\n"
            f"位置：{position_context.get('zone_type', '--')}；"
            f"风险理由：{risk.get('reason', '--')}"
        )
        ax.text(0, y_min - y_range * 0.083, details, color='#cbd5e1', fontsize=7.0,
                va='top', fontproperties=font)
        ax.set_ylim(y_min - y_range * 0.17, y_max + y_range * 0.13)
        ax.set_facecolor('#10131f')
        ax.grid(color='#283044', linestyle='--', linewidth=0.45, alpha=0.55)
        for spine in ax.spines.values():
            spine.set_color('#374151')
        ax.tick_params(colors='#cbd5e1', labelsize=8)
        step = max(1, len(rows) // 6)
        ticks = list(range(0, len(rows), step))
        ax.set_xticks(ticks)
        ax.set_xticklabels([_format_date(rows[i]['date']) for i in ticks], fontproperties=font)

    for ax in axes_list[len(samples):]:
        ax.axis('off')

    handles = [
        plt.Line2D([0], [0], color=color, linewidth=8, alpha=0.65, label=label)
        for label, color in [
            ('背景红=上涨结构', STRUCTURE_COLORS['上涨趋势']),
            ('背景绿=下降结构', STRUCTURE_COLORS['下降趋势']),
            ('背景蓝=区间震荡', STRUCTURE_COLORS['区间震荡']),
            ('顶部橙=主跌高风险', RISK_COLORS['high']),
            ('底部色带=交易波段', '#ef4444'),
        ]
    ]
    leg = fig.legend(handles=handles, loc='upper center', ncol=5, bbox_to_anchor=(0.5, 0.995),
                     facecolor='#111827', edgecolor='#374151', prop=font)
    for text in leg.get_texts():
        text.set_color('#e5e7eb')
    fig.suptitle('3L 结构上下文验证总览：结构/阶段/波段位置/主跌风险，不是买卖点',
                 color='#e5e7eb', fontsize=16, y=1.012, fontproperties=font)
    fig.tight_layout(rect=[0, 0, 1, 0.985])
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, bbox_inches='tight', facecolor=fig.get_facecolor())


def build_summary(samples: List[Dict]) -> List[Dict]:
    summary = []
    for sample in samples:
        rows = sample.get('rows') or []
        contexts = detect_all_contexts(rows, sample['asset_type']) if rows else []
        latest = contexts[-1] if contexts else {}
        summary.append({
            'name': sample['name'],
            'code': sample['code'],
            'asset_type': sample['asset_type'],
            'source': sample.get('source'),
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'data_quality': sample.get('data_quality', 'ok'),
            'quality_issues': sample.get('quality_issues', []),
            'latest': latest,
            'structure_segments': [
                {'start_idx': start, 'end_idx': end, 'value': value}
                for start, end, value in _segments(contexts, lambda ctx: ctx['market_structure']['structure'])
            ],
            'risk_segments': [
                {'start_idx': start, 'end_idx': end, 'value': value}
                for start, end, value in _segments(contexts, lambda ctx: ctx['major_decline_risk']['level'])
            ],
        })
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=120)
    parser.add_argument('--output', default='/tmp/structure_context_validation_overview.png')
    parser.add_argument('--summary', default='/tmp/structure_context_validation_summary.json')
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
