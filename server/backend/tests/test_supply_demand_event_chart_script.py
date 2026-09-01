import importlib.util
from pathlib import Path


def _load_script_module():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_supply_demand_event_validation.py'
    spec = importlib.util.spec_from_file_location('render_supply_demand_event_validation', script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_supply_demand_event_chart_fixture_builds_summary(tmp_path):
    module = _load_script_module()
    samples = module.collect_fixture_samples()

    summary = module.build_summary(samples)

    assert summary[0]['name'] == 'fixture-P0.4-C'
    assert summary[0]['date_range']
    assert isinstance(summary[0]['events'], list)


def test_supply_demand_event_chart_fixture_renders_png(tmp_path):
    module = _load_script_module()
    output = tmp_path / 'event_validation.png'
    samples = module.collect_fixture_samples()

    module.render(samples, output)

    assert output.exists()
    assert output.stat().st_size > 0
