import importlib.util
from pathlib import Path


def _load_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_transition_zone_validation.py'
    spec = importlib.util.spec_from_file_location('render_transition_zone_validation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_transition_zone_validation_fixture_builds_summary():
    module = _load_script()

    samples = module.collect_fixture_samples()
    summary = module.build_summary(samples)

    assert summary[0]['name'] == 'fixture-P0.3'
    assert summary[0]['asset_type'] == 'market'
    assert 'zones' in summary[0]


def test_transition_zone_validation_price_continuity_flags_gap():
    module = _load_script()

    rows = [
        {'date': '20260801', 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1},
        {'date': '20260802', 'open': 170, 'high': 172, 'low': 168, 'close': 171, 'volume': 1},
    ]

    status, issues = module.validate_price_continuity(rows)

    assert status == 'suspicious_price_gap'
    assert issues[0]['date'] == '20260802'
