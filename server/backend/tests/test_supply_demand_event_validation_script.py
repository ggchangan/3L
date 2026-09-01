import importlib.util
from pathlib import Path


def _load_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'export_supply_demand_event_validation.py'
    spec = importlib.util.spec_from_file_location('export_supply_demand_event_validation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_event_validation_fixture_builds_compact_summary():
    module = _load_script()

    summary = module.build_summary(module.collect_fixture_samples())

    assert summary[0]['name'] == 'fixture-P0.4-B'
    assert summary[0]['asset_type'] == 'stock'
    assert 'event_counts' in summary[0]
    assert isinstance(summary[0]['events'], list)


def test_filter_samples_matches_name_or_code():
    module = _load_script()
    samples = [
        {'name': '科创50', 'code': '000688.SH'},
        {'name': 'CPO', 'code': '886033.TI'},
    ]

    assert [item['name'] for item in module.filter_samples(samples, ['886033.TI'])] == ['CPO']
    assert [item['name'] for item in module.filter_samples(samples, ['科创50'])] == ['科创50']
