import json
from pathlib import Path


FIXTURE_PATH = Path(__file__).parent / 'fixtures' / 'structure_context_benchmark_v1.json'


def test_structure_context_benchmark_v1_schema():
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))

    assert data['version'] == 'structure-context-benchmark-v1'
    assert data['algorithm_version'] == '3l-structure-context-v1'
    assert data['confirmed_by'] == 'user'
    assert data['samples']

    for sample in data['samples']:
        assert sample['slug']
        assert sample['name']
        assert sample['asset_type'] in {'market', 'sector', 'stock'}
        assert sample['table']
        assert sample['code']
        assert sample['windows']

        for window in sample['windows']:
            assert len(window['start']) == 8
            assert len(window['end']) == 8
            assert window['start'] <= window['end']
            assert window['user_note']
            assert 'primary' in window['acceptance']
            if window['acceptance']['primary'] == 'trading_wave':
                assert window['expected_trading_wave'] in {'up', 'down', 'flat'}
                assert window['expected_structure'] in {'上涨趋势', '下降趋势', '区间震荡'}
                assert 0 < window['acceptance']['min_match_ratio'] <= 1


def test_structure_context_benchmark_v1_records_known_gaps():
    data = json.loads(FIXTURE_PATH.read_text(encoding='utf-8'))

    gaps = data.get('known_current_gaps') or []

    assert gaps
    assert all(gap['sample'] and gap['window'] and gap['issue'] for gap in gaps)
