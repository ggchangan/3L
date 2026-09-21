#!/usr/bin/env python3
"""汇总 3L 波段结构人工/回归基准集。

只读取 tests/fixtures，不连接数据库。用于快速查看 L2/L3 fixture
覆盖了哪些结构、阶段、交易波段和交易状态。
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
    structures = Counter()
    phases = Counter()
    trading_wave_directions = Counter()
    trading_states = Counter()
    recipes = Counter()

    for sample in fixture.get('samples', []):
        expected = sample.get('expected', {})
        asset_types[sample.get('asset_type', 'unknown')] += 1
        recipes[sample.get('recipe', 'unknown')] += 1
        if expected.get('structure'):
            structures[expected['structure']] += 1
        if expected.get('phase'):
            phases[expected['phase']] += 1
        for phase in expected.get('phase_in', []):
            phases[f'{phase}*'] += 1
        if expected.get('trading_wave_direction'):
            trading_wave_directions[expected['trading_wave_direction']] += 1
        if expected.get('trading_state'):
            trading_states[expected['trading_state']] += 1
        for state in expected.get('trading_state_in', []):
            trading_states[f'{state}*'] += 1

    return {
        'file': path.name,
        'version': fixture.get('version', ''),
        'algorithm_version': fixture.get('algorithm_version', ''),
        'confirmed_at': fixture.get('confirmed_at', ''),
        'confirmed_by': fixture.get('confirmed_by', ''),
        'sample_count': len(fixture.get('samples', [])),
        'asset_types': _counter_dict(asset_types),
        'structures': _counter_dict(structures),
        'phases': _counter_dict(phases),
        'trading_wave_directions': _counter_dict(trading_wave_directions),
        'trading_states': _counter_dict(trading_states),
        'recipes': _counter_dict(recipes),
        'sample_names': [sample.get('name', sample.get('slug', '')) for sample in fixture.get('samples', [])],
    }


def summarize_all(fixture_dir: Path = FIXTURE_DIR) -> Dict:
    fixtures = [
        summarize_fixture(path)
        for path in sorted(fixture_dir.glob('wave_structure_benchmark_v*.json'))
    ]
    asset_types = Counter()
    structures = Counter()
    phases = Counter()
    trading_wave_directions = Counter()
    trading_states = Counter()
    for item in fixtures:
        asset_types.update(item['asset_types'])
        structures.update(item['structures'])
        phases.update(item['phases'])
        trading_wave_directions.update(item['trading_wave_directions'])
        trading_states.update(item['trading_states'])
    return {
        'benchmark_family': 'wave-structure',
        'fixture_count': len(fixtures),
        'sample_count': sum(item['sample_count'] for item in fixtures),
        'asset_types': _counter_dict(asset_types),
        'structures': _counter_dict(structures),
        'phases': _counter_dict(phases),
        'trading_wave_directions': _counter_dict(trading_wave_directions),
        'trading_states': _counter_dict(trading_states),
        'fixtures': fixtures,
    }


def render_markdown(summary: Dict) -> str:
    lines: List[str] = [
        '# 3L 波段结构基准摘要',
        '',
        f"- fixture 数：{summary['fixture_count']}",
        f"- 样本数：{summary['sample_count']}",
        f"- 资产类型：{summary['asset_types']}",
        f"- 结构覆盖：{summary['structures']}",
        f"- 阶段覆盖：{summary['phases']}",
        f"- 交易波段方向：{summary['trading_wave_directions']}",
        '',
        '| 版本 | 确认日期 | 样本 | 资产类型 | 结构 | 阶段 | 交易波段方向 |',
        '| --- | --- | ---: | --- | --- | --- | --- |',
    ]
    for item in summary['fixtures']:
        lines.append(
            '| {version} | {confirmed_at} | {sample_count} | {asset_types} | {structures} | {phases} | {directions} |'.format(
                version=item['version'],
                confirmed_at=item['confirmed_at'],
                sample_count=item['sample_count'],
                asset_types=item['asset_types'],
                structures=item['structures'],
                phases=item['phases'],
                directions=item['trading_wave_directions'],
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
