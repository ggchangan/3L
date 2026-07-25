#!/usr/bin/env python3
"""用数据库中的四个指数回归供需峰谷 V3，并与线上旧算法对比。"""
from __future__ import annotations

import argparse
import json
import os
import sys

SERVER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SERVER_DIR not in sys.path:
    sys.path.insert(0, SERVER_DIR)

from backend.core.market_peak_valley import judge_peak_valley_v3
from backend.core.market_peak_valley_backtest import adapt_legacy_result, run_regression
from backend.data_access.data_layer import INDEX_CODES, get_index_data
from backend.data_access.data_source import INDEX_TS_CODE_MAP, _get_tushare_db
from backend.services.review_compute_service import _judge_peak_valley_legacy


def _legacy_judge(klines):
    return adapt_legacy_result(_judge_peak_valley_legacy(klines))


def _load_all_index_data(max_bars):
    db = _get_tushare_db()
    if not db:
        return get_index_data()
    indices = {}
    for code, name in INDEX_CODES.items():
        klines = db.get_index_klines(INDEX_TS_CODE_MAP[code], limit=max_bars)
        if klines:
            indices[code] = {'name': name, 'klines': klines}
    latest = max((item['klines'][0]['date'] for item in indices.values()), default='')
    return {'last_updated': latest, 'indices': indices}


def _markdown(report):
    lines = [
        '# 大盘峰谷供需 V3 历史事件回归', '',
        '> 滚动、无未来函数；未来收益仅作事后诊断，不参与当日判定。', '',
        '| 算法 | 数据段 | 方向 | 阶段 | 事件数 | 10日有效数 | 10日方向正确率 | 10日平均方向收益 | MFE | MAE |',
        '|---|---|---|---|---:|---:|---:|---:|---:|---:|',
    ]
    for algorithm, payload in report['algorithms'].items():
        for row in payload['summary']:
            ratio = row['positive_10d_ratio']
            ratio_text = '--' if ratio is None else f'{ratio * 100:.1f}%'
            def value(key):
                item = row.get(key)
                return '--' if item is None else f'{item:.2f}%'
            lines.append(
                f"| {algorithm} | {row['dataset']} | {row['side']} | {row['phase']} | "
                f"{row['count']} | {row['evaluated_10d']} | {ratio_text} | "
                f"{value('avg_signed_return_10d')} | {value('avg_mfe')} | {value('avg_mae')} |"
            )
    lines.extend(['', '## 样本说明', ''])
    for algorithm, payload in report['algorithms'].items():
        counts = '、'.join(
            f"{item['name']} {item['bars']}根/{item['event_count']}事件"
            for item in payload['indices'].values()
        )
        lines.append(f'- {algorithm}：{counts}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='可选：指数数据 JSON；传 - 时从标准输入读取')
    parser.add_argument('--max-bars', type=int, default=2000, help='直接读数据库时每个指数最多读取的日线数')
    parser.add_argument('--json-output', help='可选：写出完整事件 JSON')
    parser.add_argument('--markdown-output', help='可选：写出汇总 Markdown')
    args = parser.parse_args()

    if args.input == '-':
        data = json.load(sys.stdin)
    elif args.input:
        with open(args.input, encoding='utf-8') as file:
            data = json.load(file)
    else:
        data = _load_all_index_data(args.max_bars)
    indices = data.get('indices', {})
    if not indices:
        raise SystemExit('未从数据库读取到指数数据')
    report = run_regression(indices, {
        'supply_demand_v3': judge_peak_valley_v3,
        'legacy_bias20_v5': _legacy_judge,
    })
    report['data_last_updated'] = data.get('last_updated', '')
    markdown = _markdown(report)
    print(markdown)
    if args.json_output:
        with open(args.json_output, 'w', encoding='utf-8') as file:
            json.dump(report, file, ensure_ascii=False, indent=2)
    if args.markdown_output:
        with open(args.markdown_output, 'w', encoding='utf-8') as file:
            file.write(markdown)


if __name__ == '__main__':
    main()
