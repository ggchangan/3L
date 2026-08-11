from datetime import date, timedelta

from backend.services.l1_momentum_service import compute_l1_industry_rankings


def _rows(gain, count=21, new_high=False):
    start = date(2026, 1, 1)
    rows = []
    for i in range(count):
        close = 10 + gain * i / max(count - 1, 1)
        rows.append({
            'date': (start + timedelta(days=i)).strftime('%Y%m%d'),
            'close': close, 'high': close + (5 if new_high and i == count - 1 else 0),
        })
    return rows


def test_l1_aggregates_top_stocks_by_count_times_coverage():
    stocks = {'all': {f'{i:06d}': _rows(10 - i) for i in range(6)}}
    industry_map = {
        '000000': {'ths_industry': '行业A'}, '000001': {'ths_industry': '行业A'},
        '000002': {'ths_industry': '行业A'}, '000003': {'ths_industry': '行业B'},
        '000004': {'ths_industry': '行业B'}, '000005': {'ths_industry': '行业B'},
    }
    result = compute_l1_industry_rankings(
        stocks, industry_map, '20260121', top_n_floor=3, dynamic_top_ratio=0,
    )

    assert result['data_status'] == 'partial'
    assert result['momentum_pool_size'] == 3
    assert result['rankings'][0]['name'] == '行业A'
    assert result['rankings'][0]['momentum_stock_count'] == 3
    assert result['rankings'][0]['coverage'] == 1
    assert result['rankings'][0]['momentum_score'] == 3
    assert result['rankings'][0]['status'] == 'confirmed'
    assert result['rankings'][0]['new_high_count'] is None


def test_institution_filter_requires_both_thresholds_when_coverage_ready():
    stocks = {'all': {'000001': _rows(10), '000002': _rows(9)}}
    industry_map = {
        '000001': {'ths_industry': '行业A'}, '000002': {'ths_industry': '行业A'},
    }
    holdings = {
        '000001': {'fund_pct': 2.1, 'northbound_pct': 0.6},
        '000002': {'fund_pct': 3.0, 'northbound_pct': 0.4},
    }
    result = compute_l1_industry_rankings(
        stocks, industry_map, '20260121', institution_holdings=holdings,
        top_n_floor=2, dynamic_top_ratio=0,
    )

    assert result['institution_filter_applied'] is True
    assert result['momentum_pool_size'] == 1
    assert result['rankings'][0]['momentum_stock_count'] == 1


def test_score_above_seven_is_climax_not_stronger_recommendation():
    stocks = {'all': {f'{i:06d}': _rows(20 - i / 10) for i in range(10)}}
    industry_map = {f'{i:06d}': {'ths_industry': '拥挤行业'} for i in range(10)}
    result = compute_l1_industry_rankings(
        stocks, industry_map, '20260121', top_n_floor=10, dynamic_top_ratio=0,
    )

    assert result['rankings'][0]['momentum_score'] == 10
    assert result['rankings'][0]['status'] == 'climax_warning'


def test_52_week_high_validation_is_reported_when_long_history_exists():
    stocks = {'all': {'000001': _rows(20, count=250, new_high=True)}}
    industry_map = {'000001': {'ths_industry': '行业A'}}
    result = compute_l1_industry_rankings(
        stocks, industry_map, '20260907', top_n_floor=1, dynamic_top_ratio=0,
    )

    assert result['input_coverage']['new_high_52w'] == 1
    assert result['rankings'][0]['new_high_count'] == 1
    assert result['rankings'][0]['new_high_overlap'] == 1


def test_shadow_snapshot_uses_data_layer_and_previous_snapshot(monkeypatch, tmp_path):
    from backend.services import l1_momentum_service

    monkeypatch.setattr(l1_momentum_service, 'L1_SHADOW_DIR', str(tmp_path))
    monkeypatch.setattr('backend.data_access.data_layer.get_all_stocks', lambda: {
        'all': {'000001': _rows(10)},
    })
    monkeypatch.setattr('backend.data_access.data_layer.get_industry_map', lambda: {
        '000001': {'ths_industry': '行业A'},
    })

    first = l1_momentum_service.compute_and_persist_l1_shadow('20260121')
    second = l1_momentum_service.compute_and_persist_l1_shadow('20260122')

    assert (tmp_path / '20260121.json').exists()
    assert second['rankings'][0]['consecutive_days'] == 2
    assert first['snapshot_version'] == 1
