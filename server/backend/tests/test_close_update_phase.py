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
