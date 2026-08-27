#!/usr/bin/env python3
"""生成 3L 波段结构识别验证图。

用途：
    旁路验证 `backend.core.wave_structure_detector`，不改生产页面。

运行：
    PYTHONPATH=server:core python server/scripts/render_wave_structure_validation.py \
      --output-dir /home/ubuntu/data/3l/validation/wave_structure_p0

图形口径：
    - 主图背景色：大级别结构 structure；
    - 底部色带：当前交易波段 trading_wave.direction；
    - 橙色高/蓝色低：最终确认的波段 pivot；
    - 黄色线：当前活动波。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'core'))
sys.path.insert(0, str(ROOT / 'server'))
sys.path.insert(0, str(ROOT / 'server' / 'backend'))

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from backend.core.wave_structure_detector import judge_wave_structure  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


STRUCTURE_COLORS = {
    '上涨趋势': '#ff4d6d',
    '下降趋势': '#2dd4bf',
    '区间震荡': '#60a5fa',
    '样本不足': '#64748b',
    None: '#64748b',
}

WAVE_COLORS = {
    'up': '#ef4444',
    'down': '#22c55e',
    'flat': '#64748b',
    None: '#64748b',
}

PHASE_LABELS = {
    'impulse': '推动波',
    'pullback': '回调波',
    'countertrend_bounce': '反弹波',
    'range': '震荡',
    'warmup': '样本不足',
}


SAMPLE_GROUPS = [
    {
        'filename': '01_kc50_focus_cn.png',
        'title': 'P0-Structure 波段识别：科创50重点区间',
        'highlight_kc50': True,
        'items': [
            {'name': '科创50', 'table': 'index_daily', 'code': '000688.SH', 'asset_type': 'market', 'days': 120},
        ],
    },
    {
        'filename': '02_market_sector_examples_cn.png',
        'title': 'P0-Structure 波段识别：大盘与板块',
        'highlight_kc50': True,
        'items': [
            {'name': '科创50', 'table': 'index_daily', 'code': '000688.SH', 'asset_type': 'market', 'days': 120},
            {'name': '中证全指', 'table': 'index_daily', 'code': '000985.CSI', 'asset_type': 'market', 'days': 120},
            {'name': '元件', 'table': 'ths_daily', 'code': '881124.TI', 'asset_type': 'sector', 'days': 120},
            {'name': '共封装光学(CPO)', 'table': 'ths_daily', 'code': '885902.TI', 'asset_type': 'sector', 'days': 120},
            {'name': '存储芯片', 'table': 'ths_daily', 'code': '885756.TI', 'asset_type': 'sector', 'days': 120},
        ],
    },
    {
        'filename': '03_problem_stock_examples_cn.png',
        'title': 'P0-Structure 波段识别：近期争议个股',
        'items': [
            {'name': '圣邦股份', 'table': 'stock_daily', 'code': '300661.SZ', 'asset_type': 'stock', 'days': 120},
            {'name': '美年健康', 'table': 'stock_daily', 'code': '002044.SZ', 'asset_type': 'stock', 'days': 120},
            {'name': '绿的谐波', 'table': 'stock_daily', 'code': '688017.SH', 'asset_type': 'stock', 'days': 120},
            {'name': '永鼎股份', 'table': 'stock_daily', 'code': '600105.SH', 'asset_type': 'stock', 'days': 120},
            {'name': '长川科技', 'table': 'stock_daily', 'code': '300604.SZ', 'asset_type': 'stock', 'days': 120},
        ],
    },
    {
        'filename': '04_strong_stock_examples_cn.png',
        'title': 'P0-Structure 波段识别：强势/样本个股',
        'items': [
            {'name': '太辰光', 'table': 'stock_daily', 'code': '300570.SZ', 'asset_type': 'stock', 'days': 120},
            {'name': '中际旭创', 'table': 'stock_daily', 'code': '300308.SZ', 'asset_type': 'stock', 'days': 120},
            {'name': '胜宏科技', 'table': 'stock_daily', 'code': '300476.SZ', 'asset_type': 'stock', 'days': 120},
            {'name': '中国巨石', 'table': 'stock_daily', 'code': '600176.SH', 'asset_type': 'stock', 'days': 120},
            {'name': '普冉股份', 'table': 'stock_daily', 'code': '688766.SH', 'asset_type': 'stock', 'days': 120},
        ],
    },
]


def _safe_float(value) -> float:
    if isinstance(value, Decimal):
        return float(value)
    return float(value or 0)


def _setup_font() -> font_manager.FontProperties | None:
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
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


def _font_kwargs(font_prop):
    return {'fontproperties': font_prop} if font_prop else {}


def _load_series(db: TushareDB, table: str, code: str, days: int) -> List[Dict]:
    rows = db.execute_raw(
        f"""
        SELECT trade_date, open, high, low, close, vol AS volume
        FROM `{table}`
        WHERE ts_code=%s
        ORDER BY trade_date DESC
        LIMIT %s
        """,
        [code, days],
    )
    result = []
    for row in rows:
        if any(row.get(key) is None for key in ('open', 'high', 'low', 'close')):
            continue
        date = str(row['trade_date'])[:10]
        if len(date) == 8 and '-' not in date:
            date = f'{date[:4]}-{date[4:6]}-{date[6:]}'
        result.append({
            'date': date,
            'open': _safe_float(row['open']),
            'high': _safe_float(row['high']),
            'low': _safe_float(row['low']),
            'close': _safe_float(row['close']),
            'volume': _safe_float(row.get('volume')),
        })
    return sorted(result, key=lambda item: item['date'])


def _rolling_states(rows: List[Dict], asset_type: str) -> List[Dict]:
    states = []
    for idx, row in enumerate(rows):
        if idx + 1 < 20:
            states.append({
                'date': row['date'],
                'structure': '样本不足',
                'phase': 'warmup',
                'trading_wave': {'direction': 'flat', 'label': '横向波段'},
                'trading_state': '样本不足',
            })
            continue
        state = judge_wave_structure(rows[:idx + 1], asset_type=asset_type)
        states.append({
            'date': row['date'],
            'structure': state.get('structure'),
            'phase': state.get('phase'),
            'trading_wave': state.get('trading_wave') or {},
            'trading_state': state.get('trading_state'),
        })
    return states


def _segments(states: List[Dict], key_fn) -> Iterable[tuple[int, int, str]]:
    if not states:
        return
    start = 0
    current = key_fn(states[0])
    for idx, state in enumerate(states[1:], 1):
        value = key_fn(state)
        if value != current:
            yield start, idx - 1, current
            start, current = idx, value
    yield start, len(states) - 1, current


def _phase_label(phase: str) -> str:
    return PHASE_LABELS.get(phase or '', phase or '--')


def _plot_group(db: TushareDB, group: Dict, output_dir: Path, font_prop) -> Dict:
    items = group['items']
    fig, axes = plt.subplots(len(items), 1, figsize=(16, max(4, 3.9 * len(items))), sharex=False)
    if len(items) == 1:
        axes = [axes]

    summaries = []
    for ax, item in zip(axes, items):
        rows = _load_series(db, item['table'], item['code'], item.get('days', 120))
        if not rows:
            ax.set_title(f"{item['name']} {item['code']} 无数据", **_font_kwargs(font_prop))
            summaries.append({'name': item['name'], 'code': item['code'], 'error': '无数据'})
            continue

        states = _rolling_states(rows, item['asset_type'])
        final = judge_wave_structure(rows, asset_type=item['asset_type'])

        dates = [datetime.strptime(row['date'], '%Y-%m-%d') for row in rows]
        lows = [row['low'] for row in rows]
        highs = [row['high'] for row in rows]
        closes = [row['close'] for row in rows]
        volumes = [row['volume'] for row in rows]

        ax.plot(dates, closes, color='#e5e7eb', lw=1.6)
        ax.fill_between(dates, lows, highs, color='#94a3b8', alpha=0.12, linewidth=0)

        for start, end, structure in _segments(states, lambda state: state.get('structure')):
            ax.axvspan(
                dates[start],
                dates[end],
                color=STRUCTURE_COLORS.get(structure, '#64748b'),
                alpha=0.09,
                lw=0,
            )

        ymin, ymax = min(lows), max(highs)
        y_range = max(ymax - ymin, 1e-6)
        band_y0 = ymin - y_range * 0.105
        band_y1 = ymin - y_range * 0.045
        for start, end, direction in _segments(
            states,
            lambda state: (state.get('trading_wave') or {}).get('direction'),
        ):
            ax.axvspan(
                dates[start],
                dates[end],
                ymin=0.0,
                ymax=0.055,
                color=WAVE_COLORS.get(direction, '#64748b'),
                alpha=0.38,
                lw=0,
            )
        ax.text(
            dates[0],
            band_y0,
            '底部色带：当前交易波段 红=上涨 绿=下降 灰=横向',
            color='#cbd5e1',
            fontsize=8,
            va='top',
            **_font_kwargs(font_prop),
        )

        for pivot in final.get('pivots') or []:
            idx = pivot.get('idx')
            if idx is None or idx < 0 or idx >= len(rows):
                continue
            if pivot.get('type') == 'high':
                ax.scatter(dates[idx], rows[idx]['high'], marker='^', s=68, color='#f59e0b', edgecolor='#111827', zorder=5)
                ax.text(dates[idx], rows[idx]['high'], ' 高', color='#fbbf24', fontsize=8, va='bottom', **_font_kwargs(font_prop))
            else:
                ax.scatter(dates[idx], rows[idx]['low'], marker='v', s=68, color='#22d3ee', edgecolor='#111827', zorder=5)
                ax.text(dates[idx], rows[idx]['low'], ' 低', color='#67e8f9', fontsize=8, va='top', **_font_kwargs(font_prop))

        active = final.get('active_wave') or {}
        start_idx = active.get('start_idx')
        extreme_idx = active.get('extreme_idx')
        if isinstance(start_idx, int) and isinstance(extreme_idx, int) and 0 <= start_idx < len(rows) and 0 <= extreme_idx < len(rows):
            ax.plot(
                [dates[start_idx], dates[extreme_idx]],
                [rows[start_idx]['close'], rows[extreme_idx]['close']],
                color='#fde047',
                lw=2.4,
                alpha=0.9,
            )

        previous_phase = None
        label_count = 0
        for idx, state in enumerate(states):
            phase = state.get('phase')
            if phase != previous_phase and idx >= 19 and label_count < 9:
                ax.text(
                    dates[idx],
                    ymax + y_range * 0.035,
                    _phase_label(phase),
                    color='#cbd5e1',
                    fontsize=8,
                    ha='center',
                    **_font_kwargs(font_prop),
                )
                ax.axvline(dates[idx], color='#475569', alpha=0.22, lw=0.8)
                previous_phase = phase
                label_count += 1

        if group.get('highlight_kc50') and item['name'] == '科创50':
            for label, start, end in [
                ('04-08~05-25 人工：上升趋势', '2026-04-08', '2026-05-25'),
                ('05-26~06-09 人工：下降波段/回调', '2026-05-26', '2026-06-09'),
                ('06-08~06-30 人工：上涨波', '2026-06-08', '2026-06-30'),
                ('07-10~08-03 人工：下降/反弹扰动', '2026-07-10', '2026-08-03'),
            ]:
                start_date = datetime.strptime(start, '%Y-%m-%d')
                end_date = datetime.strptime(end, '%Y-%m-%d')
                ax.axvspan(start_date, end_date, fill=False, edgecolor='#a78bfa', lw=1.4, linestyle='--')
                ax.text(start_date, band_y1, label, color='#c4b5fd', fontsize=8, va='bottom', **_font_kwargs(font_prop))

        title = (
            f"{item['name']} {item['code']} ｜主结构: {final.get('structure')} / {_phase_label(final.get('phase'))}"
            f" ｜交易波段: {(final.get('trading_wave') or {}).get('label')} ｜{final.get('trading_state')}"
            f" ｜{rows[0]['date']}~{rows[-1]['date']}"
        )
        ax.set_title(title, loc='left', color='#f8fafc', fontsize=11, **_font_kwargs(font_prop))
        ax.set_ylim(band_y0, ymax + y_range * 0.1)
        ax.grid(True, color='#334155', alpha=0.35, lw=0.6)
        ax.tick_params(colors='#cbd5e1', labelsize=8)
        ax.set_facecolor('#0f172a')
        for spine in ax.spines.values():
            spine.set_color('#334155')
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=9))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))

        volume_ax = ax.twinx()
        volume_ax.bar(dates, volumes, width=0.8, color='#64748b', alpha=0.16)
        volume_ax.set_yticks([])
        for spine in volume_ax.spines.values():
            spine.set_visible(False)

        summaries.append({
            'name': item['name'],
            'table': item['table'],
            'code': item['code'],
            'asset_type': item['asset_type'],
            'date_range': [rows[0]['date'], rows[-1]['date']],
            'final': final,
            'states_tail': states[-10:],
        })

    fig.patch.set_facecolor('#0b1120')
    fig.suptitle(group['title'], color='#f8fafc', fontsize=16, y=0.995, **_font_kwargs(font_prop))
    fig.tight_layout(rect=[0, 0, 1, 0.985])

    image_path = output_dir / group['filename']
    summary_path = output_dir / group['filename'].replace('.png', '.json')
    fig.savefig(image_path, dpi=170, facecolor=fig.get_facecolor())
    plt.close(fig)
    summary_path.write_text(json.dumps(summaries, ensure_ascii=False, indent=2), encoding='utf-8')
    return {'image': str(image_path), 'summary': str(summary_path)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', default='/tmp/wave_structure_validation')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    font_prop = _setup_font()
    db = TushareDB()

    outputs = [_plot_group(db, group, output_dir, font_prop) for group in SAMPLE_GROUPS]
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
