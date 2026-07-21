import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest


def _klines(start_close=100.0, end_close=100.0, include_target=False):
    rows = []
    for day in range(1, 21):
        close = start_close + (end_close - start_close) * (day - 1) / 19
        rows.append({
            'date': f'202606{day:02d}',
            'open': close,
            'high': close,
            'low': close,
            'close': close,
            'volume': 1000,
        })
    rows[-1]['date'] = '20260720'
    if include_target:
        rows.append({
            'date': '20260721', 'open': end_close, 'high': end_close,
            'low': end_close, 'close': end_close, 'volume': 1000,
        })
    return rows


def test_mainline_uses_close_snapshot_for_estimated_20d_ranking(monkeypatch, tmp_path):
    from backend.data_access import data_layer
    from backend.services import concept_wave_service, review_compute_service

    monkeypatch.setattr(review_compute_service, 'MAINLINE_FULL_CACHE', str(tmp_path / 'mainline.json'))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_HISTORY_PATH', str(tmp_path / 'history.json'))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_CALIBRATION_PATH', str(tmp_path / 'calibration.json'))
    monkeypatch.setattr(review_compute_service, 'get_industry_rankings', lambda: [])
    monkeypatch.setattr(concept_wave_service, 'judge_concept_wave', lambda rows: {
        'stage': '上涨', 'vl_score': 1, 'volume_ratio': 1,
    })
    monkeypatch.setattr(data_layer, 'get_sector_daily', lambda: {'last_updated': '20260720'})
    monkeypatch.setattr(data_layer, 'get_ths_daily_update_confirmation', lambda: {
        'industry_names': ['A', 'B'],
    })
    monkeypatch.setattr(data_layer, 'get_sector_close_snapshot', lambda: {
        'date': '20260721',
        'coverage': {'industry': {'ready': True, 'ratio': 0.9}},
        'industries': {'A': {'change_pct': 10.0}, 'B': {'change_pct': 0.0}},
    })
    monkeypatch.setattr(
        data_layer, 'get_sector_push2test',
        lambda: type('Snapshot', (), {'industries': {}})(),
    )
    monkeypatch.setattr(data_layer, 'get_ths_industry_klines', lambda ths_type='I': {
        'A': _klines(100, 100),
        'B': _klines(95, 100),
        '已停用历史行业': _klines(1, 1000),
    })

    result = review_compute_service.get_mainline_data('2026-07-21')

    assert result['ranking_status'] == 'estimated'
    assert result['ranking_date'] == '20260721'
    assert result['base_date'] == '20260720'
    assert result['estimate_coverage'] == 0.9
    assert [item['name'] for item in result['all_ranked']] == ['A', 'B']
    assert result['all_ranked'][0]['chg_20d'] == 10.0
    assert result['all_ranked'][0]['estimate_applied'] is True
    assert result['calibration']['status'] == 'pending'


def test_official_mainline_completes_estimate_calibration(monkeypatch, tmp_path):
    from backend.data_access import data_layer
    from backend.services import concept_wave_service, review_compute_service

    cache_path = tmp_path / 'mainline.json'
    monkeypatch.setattr(review_compute_service, 'MAINLINE_FULL_CACHE', str(cache_path))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_HISTORY_PATH', str(tmp_path / 'history.json'))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_CALIBRATION_PATH', str(tmp_path / 'calibration.json'))
    monkeypatch.setattr(review_compute_service, 'get_industry_rankings', lambda: [])
    monkeypatch.setattr(concept_wave_service, 'judge_concept_wave', lambda rows: {
        'stage': '上涨', 'vl_score': 1, 'volume_ratio': 1,
    })
    state = {'sector_date': '20260720', 'official': False}
    monkeypatch.setattr(data_layer, 'get_sector_daily', lambda: {'last_updated': state['sector_date']})
    monkeypatch.setattr(data_layer, 'get_ths_daily_update_confirmation', lambda: {
        'industry_names': ['A', 'B'],
    })
    monkeypatch.setattr(data_layer, 'get_sector_close_snapshot', lambda: {
        'date': '20260721',
        'coverage': {'industry': {'ready': True, 'ratio': 1.0}},
        'industries': {'A': {'change_pct': 10.0}, 'B': {'change_pct': 0.0}},
    })
    monkeypatch.setattr(
        data_layer, 'get_sector_push2test',
        lambda: type('Snapshot', (), {'industries': {}})(),
    )
    monkeypatch.setattr(data_layer, 'get_ths_industry_klines', lambda ths_type='I': {
        'A': _klines(100, 100, state['official']),
        'B': _klines(95, 100, state['official']),
    })

    estimated = review_compute_service.get_mainline_data('2026-07-21')
    assert estimated['calibration']['status'] == 'pending'

    cache_path.unlink()
    state.update(sector_date='20260721', official=True)
    confirmed = review_compute_service.get_mainline_data('2026-07-21')

    assert confirmed['ranking_status'] == 'confirmed'
    assert confirmed['calibration']['status'] == 'completed'
    assert confirmed['calibration']['top10_overlap'] == 2
    saved = json.loads((tmp_path / 'calibration.json').read_text())
    assert saved['2026-07-21']['status'] == 'completed'


def test_stale_snapshot_never_marks_mainline_as_estimated(monkeypatch, tmp_path):
    from backend.data_access import data_layer
    from backend.services import concept_wave_service, review_compute_service

    monkeypatch.setattr(review_compute_service, 'MAINLINE_FULL_CACHE', str(tmp_path / 'mainline.json'))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_HISTORY_PATH', str(tmp_path / 'history.json'))
    monkeypatch.setattr(review_compute_service, 'MAINLINE_CALIBRATION_PATH', str(tmp_path / 'calibration.json'))
    monkeypatch.setattr(review_compute_service, 'get_industry_rankings', lambda: [])
    monkeypatch.setattr(concept_wave_service, 'judge_concept_wave', lambda rows: {
        'stage': '上涨', 'vl_score': 1, 'volume_ratio': 1,
    })
    monkeypatch.setattr(data_layer, 'get_sector_daily', lambda: {'last_updated': '20260720'})
    monkeypatch.setattr(data_layer, 'get_ths_daily_update_confirmation', lambda: {'industry_names': ['A']})
    monkeypatch.setattr(data_layer, 'get_sector_close_snapshot', lambda: {
        'date': '20260720',
        'coverage': {'industry': {'ready': True, 'ratio': 1.0}},
        'industries': {'A': {'change_pct': 10.0}},
    })
    monkeypatch.setattr(
        data_layer, 'get_sector_push2test',
        lambda: type('Snapshot', (), {'industries': {}})(),
    )
    monkeypatch.setattr(data_layer, 'get_ths_industry_klines', lambda ths_type='I': {'A': _klines()})

    result = review_compute_service.get_mainline_data('2026-07-21')

    assert result['ranking_status'] == 'stale'
    assert result['calibration'] is None
    assert result['all_ranked'][0]['estimate_applied'] is False


def test_concept_mainline_estimates_only_when_concept_coverage_is_ready(monkeypatch, tmp_path):
    from backend.data_access import data_layer
    from backend.services import concept_wave_service, review_compute_service

    monkeypatch.setattr(review_compute_service, 'MAINLINE_HISTORY_PATH', str(tmp_path / 'history.json'))
    monkeypatch.setattr(concept_wave_service, 'judge_concept_wave', lambda rows: {
        'stage': '上涨', 'vl_score': 1, 'volume_ratio': 1,
    })
    monkeypatch.setattr(data_layer, 'get_sector_daily', lambda: {'last_updated': '20260720'})
    monkeypatch.setattr(data_layer, 'get_tracked_concept_names', lambda min_related_stocks=6: {'C'})
    monkeypatch.setattr(data_layer, 'get_ths_industry_klines', lambda ths_type='N': {'C': _klines()})
    monkeypatch.setattr(data_layer, 'get_sector_close_snapshot', lambda: {
        'date': '20260721',
        'coverage': {'concept': {'ready': True, 'ratio': 0.85}},
        'concepts': {'C': {'change_pct': 8.0}},
    })
    monkeypatch.setattr(
        data_layer, 'get_sector_push2test',
        lambda: type('Snapshot', (), {'concepts': {}})(),
    )

    result = review_compute_service.get_concept_mainline_data('2026-07-21')

    assert result['ranking_status'] == 'estimated'
    assert result['estimate_coverage'] == 0.85
    assert result['all_ranked'][0]['estimate_applied'] is True


def test_live_sector_parser_skips_dash_values_without_discarding_snapshot(monkeypatch):
    from backend.data_access import data_source

    quote_ts = int(datetime(2026, 7, 21, 15, tzinfo=timezone(timedelta(hours=8))).timestamp())
    responses = [
        {'data': {'diff': {
            '0': {'f14': '有效行业', 'f2': '101', 'f3': '2.5', 'f15': '-', 'f16': '99', 'f17': '100', 'f18': '98', 'f5': '-', 'f124': quote_ts},
            '1': {'f14': '无效行业', 'f2': '-', 'f3': '-'},
        }}},
        {'data': {'diff': [{'f14': '有效概念', 'f2': '10', 'f3': '1.0', 'f124': quote_ts}]}},
    ]

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    with patch.object(data_source, '_last_trading_day', return_value='20260721'), \
         patch('requests.get', side_effect=[Response(item) for item in responses]):
        result = data_source._fetch_live_sector_ranking('20260721')

    assert result['last_updated'] == '20260721'
    assert set(result['industries']) == {'有效行业'}
    assert result['industries']['有效行业']['high'] == 101
    assert result['industries']['有效行业']['volume'] == 0
    assert set(result['concepts']) == {'有效概念'}


def test_close_snapshot_requires_industry_coverage_before_atomic_save(monkeypatch, tmp_path):
    from backend.data_access import data_source

    path = tmp_path / 'sector_close_snapshot.json'
    names = [f'I{i:03d}' for i in range(100)]
    raw = {
        'last_updated': '20260721',
        'industries': {
            name: {'date': '20260721', 'change_pct': 1.0, 'timestamp_verified': True}
            for name in names[:79]
        },
        'concepts': {},
    }
    monkeypatch.setattr(data_source, 'SECTOR_CLOSE_SNAPSHOT_PATH', str(path))
    monkeypatch.setattr(data_source, '_fetch_live_sector_ranking', lambda target: raw)

    with pytest.raises(Exception, match='覆盖不足'):
        data_source.fetch_sector_close_snapshot('20260721', names, [])

    assert not path.exists()


def test_close_snapshot_atomically_saves_covered_industries_and_concept_aliases(monkeypatch, tmp_path):
    from backend.data_access import data_source

    path = tmp_path / 'sector_close_snapshot.json'
    names = [f'I{i:03d}' for i in range(100)]
    raw = {
        'last_updated': '20260721',
        'industries': {
            name: {'date': '20260721', 'change_pct': 1.0, 'timestamp_verified': True}
            for name in names[:85]
        },
        'concepts': {
            '5G概念': {'date': '20260721', 'change_pct': 2.0, 'timestamp_verified': True},
        },
    }
    monkeypatch.setattr(data_source, 'SECTOR_CLOSE_SNAPSHOT_PATH', str(path))
    monkeypatch.setattr(data_source, '_fetch_live_sector_ranking', lambda target: raw)

    result = data_source.fetch_sector_close_snapshot('20260721', names, ['5G'])

    assert result['coverage']['industry']['ready'] is True
    assert result['coverage']['industry']['ratio'] == 0.85
    assert result['concepts']['5G']['source_name'] == '5G概念'
    assert json.loads(path.read_text())['date'] == '20260721'
