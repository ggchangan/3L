import os
import time
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
    assert result['quality_gates']['formal_publish_ready'] is False
    assert result['input_coverage']['kline_10d'] == 1
    assert result['input_coverage']['industry_mapping'] == 1
    assert result['momentum_pool_size'] == 3
    assert result['rankings'][0]['name'] == '行业A'
    assert result['rankings'][0]['momentum_stock_count'] == 3
    assert result['rankings'][0]['coverage'] == 1
    assert result['rankings'][0]['momentum_score'] == 3
    assert result['rankings'][0]['score_status'] == 'confirmed'
    assert result['rankings'][0]['status'] == 'insufficient_data'
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
    assert result['rankings'][0]['score_status'] == 'climax_warning'
    assert result['rankings'][0]['status'] == 'insufficient_data'


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
    def fake_market_features(date_str):
        return {
        'source': 'test_full_market', 'expected_stock_count': 2,
        'constituent_as_of_supported': False,
        'stocks': [
            {'code': '000001', 'return_10d': 10, 'high_52w': True,
             'adjustment_complete': True, 'list_date': '20200101', 'latest_date': date_str},
            {'code': '000002', 'return_10d': 9, 'high_52w': False,
             'adjustment_complete': True, 'list_date': '20200101', 'latest_date': date_str},
        ],
        }

    monkeypatch.setattr('backend.data_access.data_layer.get_l1_market_features', fake_market_features)
    monkeypatch.setattr('backend.data_access.data_layer.get_industry_map', lambda: {
        '000001': {'ths_industry': '行业A'}, '000002': {'ths_industry': '行业A'},
    })

    first = l1_momentum_service.compute_and_persist_l1_shadow('20260121')
    second = l1_momentum_service.compute_and_persist_l1_shadow('20260122')

    assert (tmp_path / '20260121.json').exists()
    assert second['rankings'][0]['score_status'] == 'confirmed'
    assert second['rankings'][0]['rotation_state'] == 'unavailable'
    assert first['snapshot_version'] == 3


def test_get_or_compute_reuses_same_day_snapshot(monkeypatch, tmp_path):
    from backend.services import l1_momentum_service

    monkeypatch.setattr(l1_momentum_service, 'L1_SHADOW_DIR', str(tmp_path))
    calls = []

    def fake_compute(as_of_date):
        calls.append(as_of_date)
        tmp_path.mkdir(exist_ok=True)
        result = {
            'as_of_date': as_of_date,
            'snapshot_version': l1_momentum_service.L1_SNAPSHOT_VERSION,
            'rankings': [],
        }
        l1_momentum_service.config.atomic_json_dump(
            result, str(tmp_path / f'{as_of_date}.json'), indent=2,
        )
        return result

    monkeypatch.setattr(l1_momentum_service, 'compute_and_persist_l1_shadow', fake_compute)

    first = l1_momentum_service.get_or_compute_l1_shadow('2026-01-21')
    second = l1_momentum_service.get_or_compute_l1_shadow('2026-01-21')

    assert first == second
    assert calls == ['20260121']


def test_partial_same_day_snapshot_expires_and_recomputes(monkeypatch, tmp_path):
    from backend.services import l1_momentum_service

    monkeypatch.setattr(l1_momentum_service, 'L1_SHADOW_DIR', str(tmp_path))
    snapshot_path = tmp_path / '20260121.json'
    tmp_path.mkdir(exist_ok=True)
    l1_momentum_service.config.atomic_json_dump(
        {'as_of_date': '20260121', 'data_status': 'partial', 'rankings': []},
        str(snapshot_path),
    )
    old = time.time() - 901
    os.utime(snapshot_path, (old, old))
    calls = []

    def fake_compute(as_of_date):
        calls.append(as_of_date)
        return {'as_of_date': as_of_date, 'data_status': 'partial', 'rankings': ['fresh']}

    monkeypatch.setattr(l1_momentum_service, 'compute_and_persist_l1_shadow', fake_compute)

    result = l1_momentum_service.get_or_compute_l1_shadow('2026-01-21')

    assert result['rankings'] == ['fresh']
    assert calls == ['20260121']


def test_rotation_exits_when_score_loses_board_effect():
    stocks = {'all': {'000001': _rows(10)}}
    industry_map = {
        '000001': {'ths_industry': '行业A'},
        '000002': {'ths_industry': '行业A'},
    }
    previous = [{
        'name': '行业A', 'status': 'confirmed',
        'momentum_score': 2, 'consecutive_days': 3,
    }]
    result = compute_l1_industry_rankings(
        stocks, industry_map, '20260121', previous=previous,
        top_n_floor=1, dynamic_top_ratio=0,
    )

    assert result['rankings'][0]['score_status'] == 'not_confirmed'
    assert result['rankings'][0]['status'] == 'insufficient_data'
    assert result['rankings'][0]['rotation_state'] == 'unavailable'
    assert result['rankings'][0]['consecutive_days'] == 0


def test_full_input_ready_keeps_formal_publish_gate_closed_until_calibrated():
    features = [
        {'code': '000001', 'return_10d': 10, 'high_52w': True,
         'adjustment_complete': True, 'list_date': '20200101', 'latest_date': '20260121'},
        {'code': '000002', 'return_10d': 9, 'high_52w': False,
         'adjustment_complete': True, 'list_date': '20200101', 'latest_date': '20260121'},
    ]
    industry_map = {
        '000001': {'ths_industry': '行业A'}, '000002': {'ths_industry': '行业A'},
    }
    holdings = {
        '000001': {'fund_pct': 2.1, 'northbound_pct': 0.6},
        '000002': {'fund_pct': 3.0, 'northbound_pct': 0.7},
    }
    result = compute_l1_industry_rankings(
        {}, industry_map, '20260121', institution_holdings=holdings,
        institution_as_of_date='20260121', stock_features=features,
        universe_meta={'expected_stock_count': 2, 'constituent_as_of_supported': True},
        top_n_floor=2, dynamic_top_ratio=0,
    )

    assert result['data_status'] == 'experimental'
    assert result['rankings'][0]['status'] == 'confirmed'
    assert result['quality_gates']['input_ready'] is True
    assert result['quality_gates']['formal_publish_ready'] is False


def test_institution_filter_tolerates_missing_rows_at_coverage_boundary():
    features = [
        {'code': f'{idx:06d}', 'return_10d': 100 - idx, 'high_52w': True,
         'adjustment_complete': True, 'list_date': '20200101', 'latest_date': '20260121'}
        for idx in range(20)
    ]
    industry_map = {f'{idx:06d}': {'ths_industry': '行业A'} for idx in range(20)}
    holdings = {
        f'{idx:06d}': {'fund_pct': 2.1, 'northbound_pct': 0.6}
        for idx in range(19)
    }
    result = compute_l1_industry_rankings(
        {}, industry_map, '20260121', institution_holdings=holdings,
        stock_features=features, universe_meta={'expected_stock_count': 20},
        top_n_floor=20, dynamic_top_ratio=0,
    )

    assert result['institution_filter_applied'] is True
    assert result['momentum_pool_size'] == 19
