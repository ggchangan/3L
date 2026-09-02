import importlib.util
from pathlib import Path


def _load_script_module():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_structure_context_validation.py'
    spec = importlib.util.spec_from_file_location('render_structure_context_validation', script)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def test_structure_context_chart_fixture_builds_summary():
    module = _load_script_module()
    samples = module.collect_fixture_samples()

    summary = module.build_summary(samples)

    assert summary[0]['name'] == 'fixture-structure-context'
    assert summary[0]['date_range']
    assert summary[0]['latest']['is_trade_decision'] is False
    assert summary[0]['structure_segments']
    assert summary[0]['risk_segments']


def test_structure_context_chart_fixture_renders_png(tmp_path):
    module = _load_script_module()
    output = tmp_path / 'structure_context_validation.png'
    samples = module.collect_fixture_samples()

    module.render(samples, output)

    assert output.exists()
    assert output.stat().st_size > 0
