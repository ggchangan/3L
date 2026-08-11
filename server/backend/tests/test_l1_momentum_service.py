from datetime import date, timedelta

from backend.services.l1_momentum_service import compute_l1_industry_rankings


def _rows(gain):
    start = date(2026, 1, 1)
    return [
        {'date': (start + timedelta(days=i)).strftime('%Y%m%d'), 'close': 10 + gain * i / 20}
        for i in range(21)
    ]


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
