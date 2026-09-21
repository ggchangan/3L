#!/usr/bin/env python3
"""生成 3L L2/L3 波段结构人工审查材料包。

输入：
    server/backend/tests/fixtures/wave_structure_benchmark_v*.json

输出：
    - 每个样本一张结构/波段图；
    - summary.json：机器可读审查摘要；
    - review.md：给人工审查用的表格和问题。

脚本不连接数据库，只复用已经固化到 fixture 的离线 recipe 或真实行情 rows。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / 'server'
CORE = ROOT / 'core'
for path in (SERVER, CORE):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import matplotlib  # noqa: E402

matplotlib.use('Agg')
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from backend.core.wave_structure_detector import judge_wave_structure  # noqa: E402


FIXTURE_DIR = SERVER / 'backend' / 'tests' / 'fixtures'
DEFAULT_OUTPUT_DIR = ROOT / 'data' / 'validation' / 'wave_structure_review_20260921'

STRUCTURE_COLORS = {
    '上涨趋势': '#ef4444',
    '下降趋势': '#22c55e',
    '区间震荡': '#3b82f6',
    '--': '#64748b',
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
    'pullback': '回调',
    'countertrend_bounce': '反弹',
    'range': '震荡',
    'warmup': '样本不足',
}


def _row(date, open_, high, low, close, volume=100000):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def _date(day):
    return f'202606{day:02d}' if day <= 30 else f'202607{day - 30:02d}'


def _recipe_fall_then_strong_rise():
    rows = []
    price = 100.0
    for idx in range(1, 16):
        price -= 1.0
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.8, price))
    for idx in range(16, 24):
        price += 2.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.7, price))
    return rows


def _recipe_rise_then_downtrend_bounce():
    rows = []
    price = 120.0
    for idx in range(1, 18):
        price += 1.0
        rows.append(_row(_date(idx), price - 0.4, price + 0.8, price - 0.8, price))
    for idx in range(18, 31):
        price -= 2.2
        rows.append(_row(_date(idx), price + 0.4, price + 0.8, price - 0.9, price))
    for idx in range(31, 34):
        price += 1.2
        rows.append(_row(_date(idx), price - 0.3, price + 0.8, price - 0.5, price))
    return rows


def _recipe_range_oscillation():
    rows = []
    price = 100.0
    for idx in range(1, 30):
        price += 0.5 if idx % 2 else -0.45
        rows.append(_row(_date(idx), price - 0.3, price + 0.6, price - 0.6, price))
    return rows


def _recipe_uptrend_pullback():
    rows = []
    price = 100.0
    for idx in range(1, 23):
        price += 1.5
        rows.append(_row(_date(idx), price - 0.4, price + 0.9, price - 0.6, price))
    for idx in range(23, 29):
        price -= 1.4
        rows.append(_row(_date(idx), price + 0.3, price + 0.7, price - 0.8, price))
    return rows


def _recipe_stock_candidate_counter_wave():
    rows = []
    price = 100.0
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))
    price -= 12.0
    rows.append(_row(_date(25), price + 1.0, price + 3.0, price - 2.0, price))
    return rows


def _recipe_stock_intraday_dip_close_back():
    rows = []
    price = 100.0
    for idx in range(1, 25):
        price += 2.0
        rows.append(_row(_date(idx), price - 1.0, price + 6.0, price - 5.5, price))
    rows.append(_row(_date(25), price - 1.0, price + 2.0, price - 18.0, price - 2.0))
    return rows


RECIPES = {
    'fall_then_strong_rise': _recipe_fall_then_strong_rise,
    'rise_then_downtrend_bounce': _recipe_rise_then_downtrend_bounce,
    'range_oscillation': _recipe_range_oscillation,
    'uptrend_pullback': _recipe_uptrend_pullback,
    'stock_candidate_counter_wave': _recipe_stock_candidate_counter_wave,
    'stock_intraday_dip_close_back': _recipe_stock_intraday_dip_close_back,
}


def _setup_font():
    candidates = [
        '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
        '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/STHeiti Light.ttc',
    ]
    for path in candidates:
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
            prop = font_manager.FontProperties(fname=path)
            plt.rcParams['font.family'] = prop.get_name()
            plt.rcParams['axes.unicode_minus'] = False
            return prop
    plt.rcParams['axes.unicode_minus'] = False
    return None


def _font_kwargs(font_prop):
    return {'fontproperties': font_prop} if font_prop else {}


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding='utf-8'))


def _source_fixture_rows(sample: Dict) -> List[Dict] | None:
    source_fixture = sample.get('source_fixture')
    source_sample = sample.get('source_sample')
    if not source_fixture or not source_sample:
        return None
    fixture_files = {
        'pure-keypoint-benchmark-v1': 'pure_keypoint_benchmark_v1.json',
        'pure-keypoint-benchmark-v2': 'pure_keypoint_benchmark_v2.json',
    }
    source = _load_json(FIXTURE_DIR / fixture_files[source_fixture])
    matched = next(item for item in source['samples'] if item['name'] == source_sample)
    return matched['rows']


def _sample_rows(sample: Dict) -> List[Dict]:
    if sample.get('recipe'):
        return RECIPES[sample['recipe']]()
    rows = _source_fixture_rows(sample)
    if rows is None:
        raise ValueError(f"无法解析样本数据: {sample.get('name')}")
    return rows


def _load_benchmark_samples() -> List[Tuple[Dict, Dict]]:
    items = []
    for fixture_path in sorted(FIXTURE_DIR.glob('wave_structure_benchmark_v*.json')):
        fixture = _load_json(fixture_path)
        for sample in fixture.get('samples', []):
            items.append((fixture, sample))
    return items


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


def _segments(states: List[Dict], key_fn):
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


def _dt(value: str) -> datetime:
    text = str(value)
    fmt = '%Y-%m-%d' if '-' in text else '%Y%m%d'
    return datetime.strptime(text, fmt)


def _safe_filename(index: int, sample: Dict) -> str:
    slug = sample.get('slug') or sample.get('name', f'sample-{index}')
    return f'{index:02d}_{slug}.png'


MANUAL_FOCUS_NAMES = {'科创50', '普冉股份', '圣邦股份', '美年健康', '绿的谐波'}


def _priority_and_reason(sample: Dict, result: Dict) -> Tuple[str, str, str]:
    name = sample.get('name', '')
    structure = result.get('structure')
    phase = result.get('phase')
    trading_wave = result.get('trading_wave') or {}
    active_wave = result.get('active_wave') or {}
    direction = trading_wave.get('direction')
    source = trading_wave.get('source')
    active_direction = active_wave.get('direction')

    if name in MANUAL_FOCUS_NAMES:
        return 'high', '用户历史重点讨论样本', '请优先确认该样本的结构/交易波段是否符合 3L 人眼判断。'
    if structure == '上涨趋势' and phase == 'impulse' and direction == 'down':
        return 'high', 'phase=推动波但交易波段=下降', '这可能是强趋势中的短线回调，也可能是 phase 没及时切换。'
    if structure == '上涨趋势' and direction == 'down':
        return 'medium', '上涨趋势中的下降交易波段', '请确认这是正常回调，还是已经接近结构反转。'
    if source == 'candidate_counter_wave':
        return 'medium', '交易波段来自候选反向波', '请确认候选反向波是否足够代表当前波段。'
    if structure == '下降趋势' and direction == 'up':
        return 'medium', '下降趋势中的反弹波', '请确认这是反弹而非新的上涨启动。'
    if active_direction and direction and active_direction != direction:
        return 'medium', 'active_wave 与 trading_wave 方向不一致', '通常来自候选反向波，需要人工确认是否合理。'
    return 'low', '暂未发现明显语义冲突', '可以低优先级抽查。'


def _render_sample(index: int, fixture: Dict, sample: Dict, rows: List[Dict],
                   result: Dict, output_dir: Path, font_prop) -> str:
    states = _rolling_states(rows, sample['asset_type'])
    dates = [_dt(row['date']) for row in rows]
    lows = [float(row['low']) for row in rows]
    highs = [float(row['high']) for row in rows]
    closes = [float(row['close']) for row in rows]
    volumes = [float(row.get('volume') or row.get('vol') or 0) for row in rows]

    fig, ax = plt.subplots(figsize=(15, 6))
    fig.patch.set_facecolor('#0b1120')
    ax.set_facecolor('#0f172a')
    ax.plot(dates, closes, color='#e5e7eb', lw=1.6)
    ax.fill_between(dates, lows, highs, color='#94a3b8', alpha=0.12, linewidth=0)

    ymin, ymax = min(lows), max(highs)
    y_range = max(ymax - ymin, 1e-6)
    for start, end, structure in _segments(states, lambda state: state.get('structure')):
        ax.axvspan(dates[start], dates[end], color=STRUCTURE_COLORS.get(structure, '#64748b'), alpha=0.10, lw=0)

    for start, end, direction in _segments(states, lambda state: (state.get('trading_wave') or {}).get('direction')):
        ax.axvspan(dates[start], dates[end], ymin=0.0, ymax=0.055, color=WAVE_COLORS.get(direction, '#64748b'), alpha=0.42, lw=0)

    pivots = result.get('pivots') or []
    for pivot in pivots:
        idx = pivot.get('idx')
        if not isinstance(idx, int) or idx < 0 or idx >= len(rows):
            continue
        if pivot.get('type') == 'high':
            ax.scatter(dates[idx], highs[idx], marker='^', s=72, color='#f59e0b', edgecolor='#111827', zorder=5)
            ax.text(dates[idx], highs[idx], ' 高', color='#fbbf24', fontsize=8, va='bottom', **_font_kwargs(font_prop))
        else:
            ax.scatter(dates[idx], lows[idx], marker='v', s=72, color='#22d3ee', edgecolor='#111827', zorder=5)
            ax.text(dates[idx], lows[idx], ' 低', color='#67e8f9', fontsize=8, va='top', **_font_kwargs(font_prop))

    active = result.get('active_wave') or {}
    start_idx = active.get('start_idx')
    extreme_idx = active.get('extreme_idx')
    if isinstance(start_idx, int) and isinstance(extreme_idx, int) and 0 <= start_idx < len(rows) and 0 <= extreme_idx < len(rows):
        ax.plot([dates[start_idx], dates[extreme_idx]], [closes[start_idx], closes[extreme_idx]], color='#fde047', lw=2.3)

    previous_phase = None
    label_count = 0
    for idx, state in enumerate(states):
        phase = state.get('phase')
        if phase != previous_phase and idx >= 19 and label_count < 8:
            ax.text(
                dates[idx],
                ymax + y_range * 0.035,
                PHASE_LABELS.get(phase, phase or '--'),
                color='#cbd5e1',
                fontsize=8,
                ha='center',
                **_font_kwargs(font_prop),
            )
            ax.axvline(dates[idx], color='#475569', alpha=0.22, lw=0.8)
            previous_phase = phase
            label_count += 1

    priority, reason, _ = _priority_and_reason(sample, result)
    tw = result.get('trading_wave') or {}
    title = (
        f"{index:02d}. {sample['name']}｜{sample['asset_type']}｜{fixture['version']}｜重点={priority}\n"
        f"结构={result.get('structure')} / 阶段={result.get('phase')}｜"
        f"交易波段={tw.get('label')}({tw.get('direction')}, {tw.get('source')})｜{result.get('trading_state')}｜疑点：{reason}"
    )
    ax.set_title(title, loc='left', color='#f8fafc', fontsize=11, **_font_kwargs(font_prop))
    ax.set_ylim(ymin - y_range * 0.12, ymax + y_range * 0.13)
    ax.grid(True, color='#334155', alpha=0.35, lw=0.6)
    ax.tick_params(colors='#cbd5e1', labelsize=8)
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=5, maxticks=10))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
    for spine in ax.spines.values():
        spine.set_color('#334155')

    volume_ax = ax.twinx()
    volume_ax.bar(dates, volumes, width=0.8, color='#64748b', alpha=0.16)
    volume_ax.set_yticks([])
    for spine in volume_ax.spines.values():
        spine.set_visible(False)

    ax.text(
        dates[0],
        ymin - y_range * 0.09,
        '背景色：主结构 红=上涨 绿=下降 蓝=区间｜底部色带：交易波段 红=上行 绿=下行 灰=横向｜黄线：active_wave',
        color='#cbd5e1',
        fontsize=8,
        va='top',
        **_font_kwargs(font_prop),
    )

    fig.tight_layout()
    filename = _safe_filename(index, sample)
    path = output_dir / filename
    fig.savefig(path, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    return filename


def _review_question(result: Dict) -> str:
    structure = result.get('structure')
    phase = result.get('phase')
    tw = result.get('trading_wave') or {}
    if structure == '上涨趋势' and tw.get('direction') == 'down':
        return '你是否认可“主结构上涨，但当前是下降波段/回调”？'
    if structure == '下降趋势' and tw.get('direction') == 'up':
        return '你是否认可这是下降趋势中的反弹，而不是上涨启动？'
    if structure != '下降趋势' and phase == 'impulse' and tw.get('direction') == 'down':
        return 'phase 仍是推动波但交易波段向下，这个分层是否可接受？'
    if structure == '区间震荡':
        return '你是否认可此处不是趋势，而是区间震荡？'
    return '抽查：当前结构/波段是否符合 3L 人眼判断？'


def build_review_pack(output_dir: Path) -> List[Dict]:
    output_dir.mkdir(parents=True, exist_ok=True)
    font_prop = _setup_font()
    items = []
    for index, (fixture, sample) in enumerate(_load_benchmark_samples(), 1):
        rows = _sample_rows(sample)
        result = judge_wave_structure(rows, asset_type=sample['asset_type'])
        image = _render_sample(index, fixture, sample, rows, result, output_dir, font_prop)
        priority, reason, suggestion = _priority_and_reason(sample, result)
        tw = result.get('trading_wave') or {}
        aw = result.get('active_wave') or {}
        item = {
            'index': index,
            'name': sample['name'],
            'asset_type': sample['asset_type'],
            'fixture': fixture['version'],
            'source_fixture': sample.get('source_fixture', ''),
            'source': sample.get('source', ''),
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'image': image,
            'priority': priority,
            'risk_reason': reason,
            'suggestion': suggestion,
            'review_question': _review_question(result),
            'structure': result.get('structure'),
            'phase': result.get('phase'),
            'trading_wave_direction': tw.get('direction'),
            'trading_wave_label': tw.get('label'),
            'trading_wave_source': tw.get('source'),
            'trading_state': result.get('trading_state'),
            'active_wave_direction': aw.get('direction'),
        }
        items.append(item)
    return items


def render_markdown(items: List[Dict], output_dir: Path) -> str:
    high = [item for item in items if item['priority'] == 'high']
    medium = [item for item in items if item['priority'] == 'medium']
    lines = [
        '# 3L 波段结构 benchmark 人工审查包',
        '',
        f'- 生成时间：{datetime.now().isoformat(timespec="seconds")}',
        f'- 样本数：{len(items)}',
        f'- 高优先级：{len(high)}',
        f'- 中优先级：{len(medium)}',
        '',
        '## 建议你优先看的样本',
        '',
        '| # | 样本 | 当前判断 | 疑点 | 审查问题 | 图 |',
        '|---:|---|---|---|---|---|',
    ]
    for item in high + medium:
        current = f"{item['structure']} / {item['phase']} / {item['trading_wave_label']}({item['trading_wave_direction']})"
        lines.append(
            f"| {item['index']} | {item['name']} | {current} | {item['risk_reason']} | {item['review_question']} | [图]({item['image']}) |"
        )
    lines.extend([
        '',
        '## 全量样本表',
        '',
        '| # | 优先级 | 样本 | 类型 | 结构 | 阶段 | 交易波段 | trading source | 审查问题 | 图 |',
        '|---:|---|---|---|---|---|---|---|---|---|',
    ])
    priority_order = {'high': 0, 'medium': 1, 'low': 2}
    for item in sorted(items, key=lambda x: (priority_order.get(x['priority'], 9), x['index'])):
        wave = f"{item['trading_wave_label']}({item['trading_wave_direction']})"
        lines.append(
            f"| {item['index']} | {item['priority']} | {item['name']} | {item['asset_type']} | "
            f"{item['structure']} | {item['phase']} | {wave} | {item['trading_wave_source']} | "
            f"{item['review_question']} | [图]({item['image']}) |"
        )
    lines.extend([
        '',
        '## 审查口径',
        '',
        '- 结构只判断背景：上涨趋势 / 下降趋势 / 区间震荡。',
        '- 交易波段判断当前 3L 波段：上涨波段 / 下降波段 / 横向。',
        '- “上涨趋势 + 下降波段”可以成立，含义是趋势内回调；但需要人工判断是否已经接近结构反转。',
        '- 本材料不判断买卖点，只为后续 L4 供需转换和 L5 买卖点提供结构基线。',
        '',
        f'输出目录：`{output_dir}`',
    ])
    return '\n'.join(lines) + '\n'


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)

    items = build_review_pack(args.output_dir)
    (args.output_dir / 'summary.json').write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    (args.output_dir / 'review.md').write_text(
        render_markdown(items, args.output_dir),
        encoding='utf-8',
    )
    print(args.output_dir / 'review.md')
    print(args.output_dir / 'summary.json')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
