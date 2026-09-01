#!/usr/bin/env python3
"""导出 3L 结构化供需事件 P0.4-B 验证摘要。

该脚本只读数据库并输出 JSON/Markdown，方便人工审查“事件语义”是否符合
3L 定义；不接生产页面，不生成买卖点。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


SCRIPT_PATH = Path(__file__).resolve()
ROOT = SCRIPT_PATH.parents[2] if len(SCRIPT_PATH.parents) > 2 else Path.cwd()
for path in (ROOT / 'server', ROOT / 'core'):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from backend.core.supply_demand_event_detector import detect_supply_demand_events  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402


SAMPLES = [
    {'name': '科创50', 'asset_type': 'market', 'table': 'index_daily', 'code': '000688.SH'},
    {'name': '中证全指', 'asset_type': 'market', 'table': 'index_daily', 'code': '000985.CSI'},
    {'name': '元件', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '881270.TI'},
    {'name': 'CPO', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886033.TI'},
    {'name': '存储芯片', 'asset_type': 'sector', 'table': 'ths_daily', 'code': '886042.TI'},
    {'name': '圣邦股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300661.SZ'},
    {'name': '美年健康', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '002044.SZ'},
    {'name': '绿的谐波', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688017.SH'},
    {'name': '太辰光', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300570.SZ'},
    {'name': '中际旭创', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300308.SZ'},
    {'name': '胜宏科技', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '300476.SZ'},
    {'name': '中国巨石', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '600176.SH'},
    {'name': '普冉股份', 'asset_type': 'stock', 'table': 'stock_daily', 'code': '688766.SH'},
]


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
            'high': close + 1,
            'low': close - 1,
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
        'name': 'fixture-P0.4-B',
        'asset_type': 'stock',
        'table': 'fixture',
        'code': 'fixture-P0.4-B',
        'source': 'offline-fixture',
        'rows': _fixture_rows(),
    }]


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


def _load_rows(db: TushareDB, sample: Dict, limit: int) -> Tuple[List[Dict], str]:
    if sample['table'] == 'stock_daily':
        rows = db.query_stock_daily(sample['code'], limit=limit, adj='qfq')
        return _normalize_rows(rows), f"{sample['table']}:{sample['code']}:qfq"
    rows = _query_rows(db, sample['table'], sample['code'], limit)
    return _normalize_rows(rows), f"{sample['table']}:{sample['code']}"


def filter_samples(samples: List[Dict], selected_names: List[str]) -> List[Dict]:
    if not selected_names:
        return samples
    selected = set(selected_names)
    return [
        sample for sample in samples
        if sample['name'] in selected or sample['code'] in selected
    ]


def _compact_event(event: Dict) -> Dict:
    return {
        'date': event.get('date'),
        'event_type': event.get('event_type'),
        'subtype': event.get('subtype'),
        'direction': event.get('direction'),
        'dominant_force': event.get('dominant_force'),
        'status': event.get('status'),
        'confidence': event.get('confidence'),
        'tier': event.get('tier'),
        'trade_implication': event.get('trade_implication'),
        'structure': (event.get('structure_context') or {}).get('structure'),
        'stage': (event.get('structure_context') or {}).get('stage'),
        'zone_type': (event.get('position_context') or {}).get('zone_type'),
        'vpa': (event.get('volume_price_evidence') or {}).get('action_type'),
        'meaning': event.get('meaning'),
        'definition_aligned': event.get('definition_aligned'),
        'semantic_warnings': event.get('semantic_warnings', []),
    }


def build_summary(samples: List[Dict]) -> List[Dict]:
    summary = []
    for sample in samples:
        rows = sample.get('rows') or []
        result = detect_supply_demand_events(rows, asset_type=sample['asset_type']) if rows else {}
        summary.append({
            'name': sample['name'],
            'code': sample['code'],
            'asset_type': sample['asset_type'],
            'source': sample.get('source'),
            'date_range': [rows[0]['date'], rows[-1]['date']] if rows else [],
            'event_counts': result.get('event_counts', {}),
            'events': [_compact_event(event) for event in result.get('events', [])],
        })
    return summary


def collect_samples(limit: int) -> List[Dict]:
    db = TushareDB()
    samples = []
    for sample in SAMPLES:
        rows, source = _load_rows(db, sample, limit)
        samples.append({**sample, 'source': source, 'rows': rows})
    return samples


def write_markdown(summary: List[Dict], output: Path) -> None:
    lines = ['# 3L 结构化供需事件 P0.4-B 验证摘要', '']
    for sample in summary:
        lines.append(f"## {sample['name']} `{sample['code']}`")
        lines.append('')
        lines.append(f"- 区间：{sample.get('date_range')}")
        lines.append(f"- 事件统计：{sample.get('event_counts')}")
        events = sample.get('events') or []
        if not events:
            lines.append('- 最新无供需事件')
            lines.append('')
            continue
        lines.append('')
        lines.append('| 日期 | 事件 | 方向 | 主导力量 | 结构/阶段 | 位置 | 量价 | 定义检查 | 含义 |')
        lines.append('|---|---|---|---|---|---|---|---|---|')
        for event in events:
            warnings = '✅' if event['definition_aligned'] else '；'.join(event['semantic_warnings'])
            lines.append(
                f"| {event['date']} | {event['event_type']} / {event['subtype']} | "
                f"{event['direction']} | {event['dominant_force']} | "
                f"{event['structure']} / {event['stage']} | {event['zone_type']} | "
                f"{event['vpa']} | {warnings} | {event['meaning']} |"
            )
        lines.append('')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines), encoding='utf-8')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=120)
    parser.add_argument('--output', default='/tmp/supply_demand_event_validation.json')
    parser.add_argument('--markdown', default='/tmp/supply_demand_event_validation.md')
    parser.add_argument('--sample', action='append', default=[], help='按名称或代码筛选样本，可重复传入')
    parser.add_argument('--fixture', action='store_true', help='使用离线 fixture，不连接数据库')
    args = parser.parse_args()

    samples = collect_fixture_samples() if args.fixture else collect_samples(args.limit)
    samples = filter_samples(samples, args.sample)
    summary = build_summary(samples)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    write_markdown(summary, Path(args.markdown))
    print(output)
    print(args.markdown)


if __name__ == '__main__':
    main()
