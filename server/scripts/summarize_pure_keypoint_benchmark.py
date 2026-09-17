#!/usr/bin/env python3
"""汇总 3L 纯关键点人工确认基准集。

这个脚本只读取 tests/fixtures 中已经人工确认的 benchmark，不连接数据库，
用于回答两个问题：

1. 当前 L1 纯关键点基准到底覆盖了多少样本/点位；
2. 后续算法改动发生漂移时，哪些资产类型和关键点类型受到影响。

用法：

    python server/scripts/summarize_pure_keypoint_benchmark.py --format markdown
    python server/scripts/summarize_pure_keypoint_benchmark.py --format json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / 'server' / 'backend' / 'tests' / 'fixtures'


def _counter_dict(counter: Counter) -> Dict[str, int]:
    return dict(sorted(counter.items()))


def summarize_fixture(path: Path) -> Dict:
    fixture = json.loads(path.read_text(encoding='utf-8'))
    asset_types = Counter()
    point_types = Counter()
    statuses = Counter()
    sample_names = []

    for sample in fixture.get('samples', []):
        asset_types[sample.get('asset_type', 'unknown')] += 1
        sample_names.append(sample.get('name', sample.get('slug', '')))
        for point in sample.get('expected_points', []):
            point_types[point.get('type', 'unknown')] += 1
            statuses[point.get('status', 'unknown')] += 1

    return {
        'file': path.name,
        'version': fixture.get('version', ''),
        'algorithm_version': fixture.get('algorithm_version', ''),
        'confirmed_at': fixture.get('confirmed_at', ''),
        'confirmed_by': fixture.get('confirmed_by', ''),
        'sample_count': sum(asset_types.values()),
        'point_count': sum(point_types.values()),
        'asset_types': _counter_dict(asset_types),
        'point_types': _counter_dict(point_types),
        'statuses': _counter_dict(statuses),
        'excluded_count': len(fixture.get('excluded_samples', [])),
        'excluded_samples': [
            {
                'name': item.get('name', item.get('slug', '')),
                'reason': item.get('reason', ''),
                'data_quality': item.get('data_quality', ''),
            }
            for item in fixture.get('excluded_samples', [])
        ],
        'sample_names': sample_names,
    }


def summarize_all(fixture_dir: Path = FIXTURE_DIR) -> Dict:
    fixtures = [
        summarize_fixture(path)
        for path in sorted(fixture_dir.glob('pure_keypoint_benchmark_v*.json'))
    ]
    total_asset_types = Counter()
    total_point_types = Counter()
    total_statuses = Counter()
    for item in fixtures:
        total_asset_types.update(item['asset_types'])
        total_point_types.update(item['point_types'])
        total_statuses.update(item['statuses'])

    return {
        'benchmark_family': 'pure-keypoint',
        'fixture_count': len(fixtures),
        'sample_count': sum(item['sample_count'] for item in fixtures),
        'point_count': sum(item['point_count'] for item in fixtures),
        'asset_types': _counter_dict(total_asset_types),
        'point_types': _counter_dict(total_point_types),
        'statuses': _counter_dict(total_statuses),
        'fixtures': fixtures,
    }


def render_markdown(summary: Dict) -> str:
    lines: List[str] = [
        '# 3L 纯关键点基准摘要',
        '',
        f"- fixture 数：{summary['fixture_count']}",
        f"- 样本数：{summary['sample_count']}",
        f"- 锁定关键点数：{summary['point_count']}",
        f"- 资产类型：{summary['asset_types']}",
        f"- 关键点类型：{summary['point_types']}",
        f"- 状态分布：{summary['statuses']}",
        '',
        '| 版本 | 确认日期 | 样本 | 点位 | 资产类型 | 关键点类型 | 状态 | 排除样本 |',
        '| --- | --- | ---: | ---: | --- | --- | --- | --- |',
    ]
    for item in summary['fixtures']:
        excluded = '、'.join(sample['name'] for sample in item['excluded_samples']) or '-'
        lines.append(
            '| {version} | {confirmed_at} | {sample_count} | {point_count} | {asset_types} | {point_types} | {statuses} | {excluded} |'.format(
                version=item['version'],
                confirmed_at=item['confirmed_at'],
                sample_count=item['sample_count'],
                point_count=item['point_count'],
                asset_types=item['asset_types'],
                point_types=item['point_types'],
                statuses=item['statuses'],
                excluded=excluded,
            )
        )
    return '\n'.join(lines) + '\n'


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format', choices=('json', 'markdown'), default='json')
    parser.add_argument('--fixture-dir', type=Path, default=FIXTURE_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)

    summary = summarize_all(args.fixture_dir)
    if args.format == 'markdown':
        print(render_markdown(summary), end='')
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
