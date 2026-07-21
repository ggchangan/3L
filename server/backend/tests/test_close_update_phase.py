from datetime import datetime
from unittest.mock import patch


def test_last_completed_trading_day_includes_today_after_close():
    from backend.data_access import data_source

    class AfterClose(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 21, 17, 30)

    with patch.object(data_source, 'datetime', AfterClose), \
         patch.object(data_source, '_get_trade_date_cache', return_value={'20260721'}):
        assert data_source.get_last_completed_trading_day() == '20260721'


def test_last_completed_trading_day_uses_previous_day_before_close():
    from backend.data_access import data_source

    class BeforeClose(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 21, 6, 0)

    with patch.object(data_source, 'datetime', BeforeClose), \
         patch.object(data_source, '_get_trade_date_cache', return_value={'2026-07-20', '2026-07-21'}):
        assert data_source.get_last_completed_trading_day() == '20260720'


def test_close_phase_waits_until_stocks_and_all_indices_are_ready():
    from backend.core import update_stock_data

    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value={
             'ready': False,
             'stock_date': '20260721',
             'missing_indices': ['000985'],
         }), \
         patch.object(update_stock_data, 'update_stocks') as update_stocks:
        assert update_stock_data.run_close_phase() is False
        update_stocks.assert_not_called()


def test_close_phase_skips_weekday_holiday_without_rebuilding_review():
    from backend.core import update_stock_data

    class Holiday(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 2, 17, 30)

    with patch.object(update_stock_data, 'datetime', Holiday), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260930'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental') as fetch, \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is True
        fetch.assert_not_called()
        refresh.assert_not_called()


def test_close_phase_refreshes_review_after_daily_data_is_ready():
    from backend.core import update_stock_data

    freshness = {
        'ready': True,
        'stock_date': '20260721',
        'missing_indices': [],
    }
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value=freshness), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks'), \
         patch.object(update_stock_data, 'update_index'), \
         patch.object(update_stock_data, 'refresh_sector_close_snapshot', return_value={
             'coverage': {'industry': {'covered': 280, 'expected': 319, 'ratio': 0.878}},
         }), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is True
        refresh.assert_called_once_with('20260721')


def test_close_cli_retries_until_data_is_ready():
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'run_close_phase', side_effect=[False, True]) as run, \
         patch.object(update_stock_data.time, 'sleep') as sleep:
        result = update_stock_data.main([
            '--phase', 'close', '--max-attempts', '3', '--retry-interval', '0',
        ])

    assert result == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(0)


def test_close_cli_retries_after_recoverable_exception():
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'run_close_phase', side_effect=[RuntimeError('暂时失败'), True]) as run, \
         patch.object(update_stock_data.time, 'sleep') as sleep:
        result = update_stock_data.main([
            '--phase', 'close', '--max-attempts', '3', '--retry-interval', '0',
        ])

    assert result == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(0)


def test_full_phase_refreshes_review_after_sector_update(tmp_path):
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'DATA_DIR', str(tmp_path)), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks', return_value=(0, 0, 0)), \
         patch.object(update_stock_data, 'update_index', return_value=(0, '20260721')), \
         patch.object(update_stock_data, 'update_sectors', return_value=(319, 20)), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        update_stock_data.run_full_phase()

    refresh.assert_called_once_with('20260721')


def test_close_phase_keeps_review_available_when_sector_snapshot_fails():
    from backend.core import update_stock_data

    freshness = {'ready': True, 'stock_date': '20260721', 'missing_indices': []}
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value=freshness), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks'), \
         patch.object(update_stock_data, 'update_index'), \
         patch.object(update_stock_data, 'refresh_sector_close_snapshot', side_effect=RuntimeError('暂时不可用')), \
         patch.object(update_stock_data, '_clear_mainline_cache'), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is True

    refresh.assert_called_once_with('20260721')


def test_sector_update_coverage_rejects_partial_target_date():
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [{'name': 'A', 'type': 'I'}]
    requested = [('A', 'industry'), ('B', 'industry')]
    confirmation = {'confirmed_date': '20260720', 'industry_names': ['A', 'B']}
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['covered'] == 1
    assert result['industry']['expected'] == 2
    assert result['missing'] == ['B']


def test_partial_sector_rows_never_become_next_day_baseline():
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'name': 'A', 'type': 'I'},
        {'name': 'B', 'type': 'I'},
    ]
    requested = [(name, 'industry') for name in ('A', 'B', 'C')]
    confirmation = {
        'confirmed_date': '20260720',
        'industry_names': ['A', 'B', 'C'],
    }
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        first = data_source.get_ths_daily_update_coverage(requested, '20260721')
        second = data_source.get_ths_daily_update_coverage(requested, '20260722')

    assert first['ready'] is False
    assert second['ready'] is False
    assert first['industry']['expected'] == second['industry']['expected'] == 3
    assert first['industry_names'] == second['industry_names'] == ['A', 'B', 'C']


def test_same_count_sector_member_replacement_is_not_complete():
    from backend.data_access import data_source

    class FakeDB:
        def execute_raw(self, sql, params=None):
            # 新行业 X 必须在目标日查询范围中，否则它永远进不了新基线。
            assert params == ['20260721', 'A', 'B', 'C', 'X']
            return [
                {'name': 'A', 'type': 'I'},
                {'name': 'B', 'type': 'I'},
                {'name': 'X', 'type': 'I'},
            ]

    requested = [(name, 'industry') for name in ('A', 'B', 'C', 'X')]
    confirmation = {'confirmed_date': '20260720', 'industry_names': ['A', 'B', 'C']}
    with patch.object(data_source, '_get_tushare_db', return_value=FakeDB()), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['covered'] == 2
    assert result['industry']['expected'] == 3
    assert result['missing'] == ['C']
    assert result['industry_names'] == ['A', 'B', 'C', 'X']


def test_sector_coverage_uses_shared_safe_legacy_bootstrap():
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]
    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'name': name, 'type': 'I'} for name in names
    ]
    confirmation = {'confirmed_date': '20260720', 'industry_names': names}

    requested = [(name, 'industry') for name in names]
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value={}), \
         patch.object(data_source, 'bootstrap_ths_daily_update_confirmation', return_value=confirmation) as bootstrap:
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is True
    assert result['bootstrap'] is False
    assert result['industry']['expected'] == 80
    bootstrap.assert_called_once_with()


def test_sector_coverage_does_not_bootstrap_from_target_day_itself():
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]

    class FakeDB:
        def execute_raw(self, sql, params=None):
            if 'COUNT(DISTINCT td.ts_code)' in sql:
                return []
            return [{'name': name, 'type': 'I'} for name in names]

    requested = [(name, 'industry') for name in names]
    with patch.object(data_source, '_get_tushare_db', return_value=FakeDB()), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value={}):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['expected'] == 0
    assert result['industry']['bootstrap_minimum'] == 80


def test_legacy_sector_state_bootstraps_only_from_repeated_stable_history(tmp_path):
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]

    class FakeDB:
        def execute_raw(self, sql, params=None):
            if 'COUNT(DISTINCT td.ts_code)' in sql:
                return [
                    {'trade_date': '20260720', 'board_count': 79},
                    {'trade_date': '20260719', 'board_count': 80},
                ]
            assert params == ['20260719']
            return [{'name': name} for name in names]

    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)), \
         patch.object(data_source, '_get_tushare_db', return_value=FakeDB()):
        state = data_source.bootstrap_ths_daily_update_confirmation()

    assert state['confirmed_date'] == '20260719'
    assert state['industry_names'] == names


def test_legacy_sector_state_rejects_a_single_partial_history_day(tmp_path):
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'trade_date': '20260720', 'board_count': 80},
    ]
    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        state = data_source.bootstrap_ths_daily_update_confirmation()

    assert state == {}
    assert not state_path.exists()


def test_sector_confirmation_is_not_hidden_by_cross_process_kline_cache():
    from backend.data_access import data_layer

    klines = {'industries': {'A': []}, 'concepts': {}}
    confirmations = [
        {'confirmed_date': '20260720', 'industry_coverage': 1.0},
        {'confirmed_date': '20260721', 'industry_coverage': 0.98},
    ]
    with patch.object(data_layer.cache, 'get', return_value=klines), \
         patch.object(data_layer, 'get_ths_daily_update_confirmation', side_effect=confirmations):
        first = data_layer.get_sector_daily()
        second = data_layer.get_sector_daily()

    assert first['last_updated'] == '20260720'
    assert second['last_updated'] == '20260721'
    assert first['industries'] is second['industries']


def test_sector_confirmation_is_saved_and_loaded_atomically(tmp_path):
    from backend.data_access import data_source

    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    coverage = {
        'industry_names': ['A', 'B'],
        'industry': {'ratio': 1.0},
        'concept': {'ratio': 0.95},
    }
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)):
        data_source.save_ths_daily_update_confirmation('20260721', coverage)
        state = data_source.get_ths_daily_update_confirmation()

    assert state['confirmed_date'] == '20260721'
    assert state['industry_names'] == ['A', 'B']
    assert state['industry_coverage'] == 1.0
    assert state['concept_coverage'] == 0.95
    assert not (tmp_path / 'computed' / 'sector_update_state.json.tmp').exists()


def test_sector_update_advances_confirmation_only_after_gate_passes():
    from backend.core import update_stock_data

    coverage = {
        'ready': True,
        'industry': {'expected': 1, 'covered': 1},
        'concept': {'expected': 0, 'covered': 0},
        'missing': [],
        'industry_names': ['A'],
    }
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, 'datetime') as current_time, \
         patch.object(update_stock_data, 'get_tracked_concept_names', return_value=set()), \
         patch.object(update_stock_data, 'get_ths_index_names', return_value=[('A', '881001.TI')]), \
         patch.object(update_stock_data, 'fetch_ths_daily_klines_akshare', return_value=(1, 1)), \
         patch.object(update_stock_data, 'get_ths_daily_update_coverage', return_value=coverage), \
         patch.object(update_stock_data, 'save_ths_daily_update_confirmation') as save:
        current_time.now.return_value.weekday.return_value = 0
        assert update_stock_data.update_sectors() == (1, 0)

    save.assert_called_once_with('20260721', coverage)
