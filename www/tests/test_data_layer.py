"""Tests for scripts.data_layer — verifies data structure, file existence, and function contracts."""
import os
import pytest

from scripts.data_layer import (
    ALL_STOCKS_PATH,
    WATCHLIST_PATH,
    INDUSTRY_MAP_PATH,
    SUBSECTOR_PATH,
    FINANCIAL_CACHE_PATH,
    PROFIT_QUALITY_PATH,
    INDEX_DATA_PATH,
    INDUSTRY_LEADERS_PATH,
    LATEST_SCAN_PATH,
    HOLDINGS_PATH,
    TRADES_PATH,
    KEY_POINTS_DIR,
    REVIEW_ARCHIVE_DIR,
    REVIEW_CHARTS_DIR,
    SCRIPTS_DIR,
    SIMULATION_DIR,
    OUTPUT_DIR,
    get_all_stocks,
    get_watchlist,
    get_last_updated,
    get_stock_klines,
    get_industry_map,
)

# ── file paths to check ──
_PATH_CONSTANTS = [
    ALL_STOCKS_PATH,
    WATCHLIST_PATH,
    INDUSTRY_MAP_PATH,
    SUBSECTOR_PATH,
    FINANCIAL_CACHE_PATH,
    PROFIT_QUALITY_PATH,
    INDEX_DATA_PATH,
    INDUSTRY_LEADERS_PATH,
    LATEST_SCAN_PATH,
    HOLDINGS_PATH,
    TRADES_PATH,
]

_DIR_CONSTANTS = [
    KEY_POINTS_DIR,
    REVIEW_ARCHIVE_DIR,
    REVIEW_CHARTS_DIR,
    SCRIPTS_DIR,
    SIMULATION_DIR,
    OUTPUT_DIR,
]


class TestPathsExist:
    """All path-constant files and directories exist on disk."""

    @pytest.mark.parametrize('path', _PATH_CONSTANTS)
    def test_file_exists(self, path):
        assert os.path.isfile(path), f'Missing file: {path}'

    @pytest.mark.parametrize('path', _DIR_CONSTANTS)
    def test_dir_exists(self, path):
        assert os.path.isdir(path), f'Missing directory: {path}'


class TestGetAllStocks:
    """Verify get_all_stocks() returns the expected structure."""

    def test_returns_dict(self):
        stocks = get_all_stocks()
        assert isinstance(stocks, dict)

    def test_has_eight_directions(self):
        stocks = get_all_stocks()
        assert len(stocks) == 8, f'Expected 8 directions, got {len(stocks)}'

    def test_each_direction_has_stocks(self, stocks):
        for direction, stock_dict in stocks.items():
            assert isinstance(stock_dict, dict), f'{direction} is not a dict'
            assert len(stock_dict) > 0, f'{direction} has no stocks'

    def test_each_stock_has_klines(self, stocks):
        for direction, stock_dict in stocks.items():
            for code, klines in stock_dict.items():
                assert isinstance(klines, list), f'{code} klines is not a list'
                assert len(klines) > 0, f'{code} has empty klines'


class TestGetWatchlist:
    """Verify watchlist content."""

    def test_count_greater_than_100(self, watchlist):
        assert len(watchlist) > 100, f'Expected > 100 watchlist stocks, got {len(watchlist)}'

    def test_each_stock_has_required_fields(self, watchlist):
        for stock in watchlist:
            assert 'code' in stock, f'Missing code in {stock}'
            assert 'name' in stock, f'Missing name in {stock}'
            assert 'direction' in stock, f'Missing direction in {stock}'


class TestGetLastUpdated:
    """Verify last_updated is non-empty."""

    def test_not_empty(self):
        dt = get_last_updated()
        assert isinstance(dt, str) and len(dt) > 0, f'Expected non-empty string, got {dt!r}'


class TestGetStockKlines:
    """Verify kline retrieval for a known stock."""

    def test_known_stock_has_klines(self):
        """688126 (沪硅产业) is known to have 60 klines as of 2026-05-21."""
        klines = get_stock_klines('688126')
        assert isinstance(klines, list), 'Expected a list of klines'
        assert len(klines) > 30, f'Expected > 30 klines, got {len(klines)}'


class TestGetIndustryMap:
    """Verify industry map is a dict."""

    def test_is_dict(self):
        im = get_industry_map()
        assert isinstance(im, dict), f'Expected dict, got {type(im).__name__}'
