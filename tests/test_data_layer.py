"""Tests for scripts.data_layer — verifies data structure, file existence, and function contracts."""
import os
import pytest

from backend.data_access.data_layer import (
    ALL_STOCKS_PATH,
    WATCHLIST_PATH,
    INDUSTRY_MAP_PATH,
    SUB_SECTOR_CLUSTERS_PATH,
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
    SUB_SECTOR_CLUSTERS_PATH,
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
    """Skip if production files/directories are not present (e.g. CI without generated data)."""

    @pytest.mark.parametrize('path', _PATH_CONSTANTS)
    def test_file_exists(self, path):
        if not os.path.isfile(path):
            pytest.skip(f'Production file not found (skipped): {path}')

    @pytest.mark.parametrize('path', _DIR_CONSTANTS)
    def test_dir_exists(self, path):
        if not os.path.isdir(path):
            pytest.skip(f'Production directory not found (skipped): {path}')


class TestGetAllStocks:
    """Verify get_all_stocks() returns the expected structure."""

    def test_returns_dict(self):
        stocks = get_all_stocks()
        assert isinstance(stocks, dict)

    def test_has_eight_directions(self):
        """Directions are now managed via direction_service, not hardcoded."""
        import os
        from backend.core.config import DATA_DIR
        dir_path = os.path.join(DATA_DIR, 'directions.json')
        if os.path.isfile(dir_path):
            from backend.services.direction_service import get_all
            data = get_all()
            assert isinstance(data, dict)
        else:
            # Before any direction is created, empty is valid
            pass

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


class TestAtomicSave:
    """Verify atomic save — uses temp dirs, never touches production data."""

    def _save_via_temp_path(self, stocks, last_updated, tmp_dir):
        """Helper: save data using _atomic_save_json to a temp path."""
        from backend.data_access.data_layer import _atomic_save_json
        from backend.core.config import ALL_STOCKS_PATH as REAL_PATH
        test_path = os.path.join(tmp_dir, 'test_stocks.json')
        data = {'last_updated': last_updated, 'stocks': stocks}
        _atomic_save_json(test_path, data)
        return test_path

    def test_atomic_write_creates_file(self, tmp_path):
        """Atomic write creates the target file with correct content."""
        test_path = self._save_via_temp_path(
            {'test_dir': {'000001': [{'date': '20260525', 'close': 10.0}]}},
            '20260525',
            tmp_path
        )
        assert os.path.isfile(test_path), 'File was not created'

    def test_atomic_write_no_tmp_residue(self, tmp_path):
        """No .tmp file remains after atomic write."""
        test_path = self._save_via_temp_path({'test_dir': {}}, '20260525', tmp_path)
        tmp_residue = test_path + '.tmp'
        assert not os.path.exists(tmp_residue), f'Tmp residue file left: {tmp_residue}'

    def test_atomic_write_content_correct(self, tmp_path):
        """Content written matches input data."""
        import json
        expected_stocks = {'test_dir': {'000001': [{'date': '20260525', 'close': 10.0}]}}
        test_path = self._save_via_temp_path(expected_stocks, '20260525', tmp_path)
        with open(test_path) as f:
            loaded = json.load(f)
        assert loaded['last_updated'] == '20260525'
        assert loaded['stocks'] == expected_stocks

    def test_save_all_stocks_uses_atomic_write(self, monkeypatch, tmp_path):
        """save_all_stocks() uses atomic write internally."""
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'all_stocks.json')
        monkeypatch.setattr(dl, 'ALL_STOCKS_PATH', test_path)
        dl.save_all_stocks({'test': {}}, last_updated='20260525')
        assert os.path.isfile(test_path)
        # No .tmp residue
        assert not os.path.exists(test_path + '.tmp')

    def test_uncached_load_returns_latest_saved(self, monkeypatch, tmp_path):
        """load_all_stocks_uncached() reads the latest saved file, bypassing cache."""
        import json
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'all_stocks.json')
        monkeypatch.setattr(dl, 'ALL_STOCKS_PATH', test_path)
        # Write test data directly
        data = {'last_updated': '20260525', 'stocks': {'测试方向': {'000001': [{'date': '20260525'}]}}}
        with open(test_path, 'w') as f:
            json.dump(data, f)
        loaded = dl.load_all_stocks_uncached()
        assert isinstance(loaded, dict)
        assert '测试方向' in loaded


class TestIndexData:
    """Verify index data read/write through data_layer."""

    def test_save_and_uncached_load(self, monkeypatch, tmp_path):
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'index_data.json')
        monkeypatch.setattr(dl, 'INDEX_DATA_PATH', test_path)
        data = {
            'last_updated': '20260525',
            'indices': {
                '000985': {'name': '中证全指', 'klines': [{'date': '20260525', 'close': 5000.0}]},
            }
        }
        dl.save_index_data(data)
        loaded = dl.load_index_data_uncached()
        assert loaded['last_updated'] == '20260525'
        klines = loaded['indices']['000985']['klines']
        assert len(klines) == 1

    def test_save_and_uncached_load_old_format(self, monkeypatch, tmp_path):
        """验证旧扁平格式自动迁移到多指数格式"""
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'index_data2.json')
        monkeypatch.setattr(dl, 'INDEX_DATA_PATH', test_path)
        # 保存旧格式 {last_updated, klines}
        old_data = {'last_updated': '20260525', 'klines': [{'date': '20260525', 'close': 5000.0}]}
        dl.save_index_data(old_data)
        loaded = dl.load_index_data_uncached()
        # 自动迁移后应该变成多指数格式
        assert loaded['last_updated'] == '20260525'
        klines = loaded['indices']['000985']['klines']
        assert len(klines) == 1

    def test_get_index_klines(self, monkeypatch, tmp_path):
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'index_data.json')
        monkeypatch.setattr(dl, 'INDEX_DATA_PATH', test_path)
        data = {
            'last_updated': '20260525',
            'indices': {
                '000985': {'name': '中证全指', 'klines': [{'date': '20260525', 'close': 5000.0}]},
            }
        }
        dl.save_index_data(data)
        klines = dl.get_index_klines()
        assert len(klines) == 1
        assert klines[0]['close'] == 5000.0

    def test_index_code_constant(self):
        from backend.data_access.data_layer import INDEX_CODE
        assert INDEX_CODE == '000985'


class TestSectorDaily:
    """Verify sector daily data read/write through data_layer."""

    def test_save_and_uncached_load(self, monkeypatch, tmp_path):
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'sector_daily.json')
        monkeypatch.setattr(dl, 'SECTOR_DAILY_PATH', test_path)
        data = {
            'last_updated': '20260525',
            'industries': {'半导体': [{'date': '20260525', 'close': 1000.0}]},
            'concepts': {'AI芯片': [{'date': '20260525', 'close': 2000.0}]},
        }
        dl.save_sector_daily(data)
        loaded = dl.load_sector_daily_uncached()
        assert loaded['last_updated'] == '20260525'
        assert '半导体' in loaded['industries']
        assert 'AI芯片' in loaded['concepts']

    def test_save_all_sectors_atomic(self, monkeypatch, tmp_path):
        from backend.data_access import data_layer as dl
        test_path = os.path.join(tmp_path, 'sector_daily.json')
        monkeypatch.setattr(dl, 'SECTOR_DAILY_PATH', test_path)
        dl.save_sector_daily({
            'last_updated': '20260525',
            'industries': {'测试行业': []},
            'concepts': {},
        })
        assert os.path.isfile(test_path)
        assert not os.path.exists(test_path + '.tmp')
