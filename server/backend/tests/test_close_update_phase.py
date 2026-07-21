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


def test_confirmed_sector_date_requires_coverage_and_never_fakes_today():
    from backend.data_access.data_layer import _confirmed_sector_date

    assert _confirmed_sector_date({}) == ('', 0.0)
    industries = {
        'A': [{'date': '20260720'}, {'date': '20260721'}],
        'B': [{'date': '20260720'}, {'date': '20260721'}],
        'C': [{'date': '20260720'}],
    }
    assert _confirmed_sector_date(industries, min_coverage=0.95) == ('20260720', 1.0)


def test_confirmed_sector_date_ignores_inactive_historical_boards():
    from backend.data_access.data_layer import _confirmed_sector_date

    industries = {
        'A': [{'date': '20260612'}, {'date': '20260720'}, {'date': '20260721'}],
        'B': [{'date': '20260612'}, {'date': '20260720'}, {'date': '20260721'}],
        '已停用旧板块': [{'date': '20260612'}],
    }

    assert _confirmed_sector_date(industries) == ('20260721', 1.0)


def test_sector_update_coverage_rejects_partial_target_date():
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: (
        [{'name': 'A', 'type': 'I'}, {'name': 'B', 'type': 'I'}]
        if "WHERE ti.type='I'" in sql
        else [{'name': 'A', 'type': 'I'}]
    )
    requested = [('A', 'industry'), ('B', 'industry')]
    with patch.object(data_source, '_get_tushare_db', return_value=db):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['covered'] == 1
    assert result['industry']['expected'] == 2
    assert result['missing'] == ['B']
