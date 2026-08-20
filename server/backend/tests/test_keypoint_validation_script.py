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
