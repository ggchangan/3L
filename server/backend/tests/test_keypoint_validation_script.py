import importlib.util
from pathlib import Path


def _load_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_pure_keypoint_validation.py'
    spec = importlib.util.spec_from_file_location('render_pure_keypoint_validation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_price_continuity_flags_unexplained_stock_gap():
    module = _load_script()
    rows = [
        {'date': '20260801', 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1},
        {'date': '20260802', 'open': 238, 'high': 242, 'low': 230, 'close': 240, 'volume': 1},
    ]

    status, issues = module.validate_price_continuity(rows)

    assert status == 'suspicious_price_gap'
    assert issues == [{
        'date': '20260802',
        'prev_date': '20260801',
        'prev_close': 100.0,
        'open': 238,
        'close': 240,
        'open_gap_pct': 138.0,
        'close_gap_pct': 140.0,
    }]


def test_validate_price_continuity_allows_normal_limit_move():
    module = _load_script()
    rows = [
        {'date': '20260801', 'open': 100, 'high': 101, 'low': 99, 'close': 100, 'volume': 1},
        {'date': '20260802', 'open': 118, 'high': 120, 'low': 116, 'close': 120, 'volume': 1},
    ]

    status, issues = module.validate_price_continuity(rows)

    assert status == 'ok'
    assert issues == []


def test_normalize_qfq_rows_keeps_adjustment_status_and_sorts():
    module = _load_script()

    rows = module._normalize_qfq_rows([
        {
            'date': '20260802', 'open': 12, 'high': 13, 'low': 11,
            'close': 12.5, 'volume': 200, 'adjustment_status': 'qfq',
        },
        {
            'date': '20260801', 'open': 10, 'high': 11, 'low': 9,
            'close': 10.5, 'volume': 100, 'adjustment_status': 'qfq',
        },
    ])

    assert [row['date'] for row in rows] == ['20260801', '20260802']
    assert all(row['adjustment_status'] == 'qfq' for row in rows)


def _load_supply_demand_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_supply_demand_keypoint_validation.py'
    spec = importlib.util.spec_from_file_location('render_supply_demand_keypoint_validation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_supply_demand_validation_fixture_builds_summary():
    module = _load_supply_demand_script()

    samples = module.collect_fixture_samples()
    summary = module.build_summary(samples)

    assert summary[0]['name'] == 'fixture-P0.2'
    assert summary[0]['asset_type'] == 'stock'
    assert summary[0]['transition_points']
    assert all(point['is_trade_decision'] is False for point in summary[0]['transition_points'])


def _load_structure_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'render_structure_validation.py'
    spec = importlib.util.spec_from_file_location('render_structure_validation', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_structure_validation_fixture_builds_summary():
    module = _load_structure_script()

    samples = module.collect_fixture_samples()
    summary = module.build_summary(samples)

    assert summary[0]['name'] == 'fixture-P0-structure'
    assert summary[0]['asset_type'] == 'stock'
    assert summary[0]['states']
    assert {'date', 'structure', 'stage', 'metrics', 'reason'} <= set(summary[0]['states'][-1])
    assert any(state['structure'] in ('上涨趋势', '区间震荡', '下降趋势') for state in summary[0]['states'])


def _load_pure_benchmark_summary_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'summarize_pure_keypoint_benchmark.py'
    spec = importlib.util.spec_from_file_location('summarize_pure_keypoint_benchmark', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_pure_keypoint_benchmark_summary_tracks_confirmed_baseline():
    module = _load_pure_benchmark_summary_script()

    summary = module.summarize_all()

    assert summary['fixture_count'] == 2
    assert summary['sample_count'] == 33
    assert summary['point_count'] == 568
    assert summary['asset_types'] == {'market': 4, 'sector': 17, 'stock': 12}
    assert summary['statuses'] == {'candidate': 75, 'confirmed': 493}
    assert summary['point_types'] == {
        'price_high': 141,
        'price_low': 168,
        'volume_peak': 99,
        'volume_trough': 160,
    }
    v2 = next(item for item in summary['fixtures'] if item['version'] == 'pure-keypoint-benchmark-v2')
    assert [item['name'] for item in v2['excluded_samples']] == ['工业富联', '新易盛', '寒武纪']


def test_pure_keypoint_benchmark_summary_renders_markdown():
    module = _load_pure_benchmark_summary_script()

    markdown = module.render_markdown(module.summarize_all())

    assert '# 3L 纯关键点基准摘要' in markdown
    assert 'pure-keypoint-benchmark-v1' in markdown
    assert 'pure-keypoint-benchmark-v2' in markdown
    assert '工业富联、新易盛、寒武纪' in markdown


def _load_wave_benchmark_summary_script():
    script = Path(__file__).resolve().parents[2] / 'scripts' / 'summarize_wave_structure_benchmark.py'
    spec = importlib.util.spec_from_file_location('summarize_wave_structure_benchmark', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wave_structure_benchmark_summary_tracks_confirmed_baseline():
    module = _load_wave_benchmark_summary_script()

    summary = module.summarize_all()

    assert summary['fixture_count'] == 1
    assert summary['sample_count'] == 6
    assert summary['asset_types'] == {'market': 4, 'stock': 2}
    assert summary['structures'] == {'上涨趋势': 4, '下降趋势': 1, '区间震荡': 1}
    assert summary['trading_wave_directions'] == {'down': 2, 'up': 3}
    fixture = summary['fixtures'][0]
    assert fixture['version'] == 'wave-structure-benchmark-v1'
    assert fixture['algorithm_version'] == 'wave-structure-v1'


def test_wave_structure_benchmark_summary_renders_markdown():
    module = _load_wave_benchmark_summary_script()

    markdown = module.render_markdown(module.summarize_all())

    assert '# 3L 波段结构基准摘要' in markdown
    assert 'wave-structure-benchmark-v1' in markdown
    assert '上涨趋势' in markdown
    assert '下降趋势' in markdown
