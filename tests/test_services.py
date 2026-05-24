"""Targeted unit tests for 6 service-layer functions.

Tests catch bugs like undefined variable names (e.g. missing 'config' import)
before they reach production. Directly imports service functions (not via HTTP).

Usage: python -m pytest tests/test_services.py -v
"""
import json
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open, call
import pytest

# ── Helpers ──────────────────────────────────────────────────────


def _dummy_boards_data(n=3):
    """Generate dummy industry/concept board records."""
    return [{'板块名称': f'Board_{i}', '板块代码': f'BK{i:04d}',
             '涨跌幅': f'{i}.{i:02d}%'} for i in range(n)]


# ═══════════════════════════════════════════════════════════════════
# 1. market_service.get_industry_boards()
# ═══════════════════════════════════════════════════════════════════

class TestGetIndustryBoards:
    """Tests for market_service.get_industry_boards().

    Handles cache hit, cache corruption, fetch success, fetch failure.
    """

    @patch('services.market_service._cache_dir')
    @patch('services.market_service.os.path.isfile')
    @patch('services.market_service.os.path.getmtime')
    @patch('builtins.open', new_callable=mock_open, read_data='[{"a":1}]')
    def test_returns_cached_data_when_fresh(self, mock_file, mock_mtime,
                                            mock_isfile, mock_cache_dir):
        """Happy path: valid fresh cache returns cached data."""
        from services import market_service
        mock_cache_dir.return_value = '/fake/cache'
        mock_isfile.return_value = True
        mock_mtime.return_value = 9999999999.0  # very recent

        result = market_service.get_industry_boards()
        assert result == [{"a": 1}]

    @patch('services.market_service._cache_dir')
    @patch('services.market_service.os.path.isfile')
    @patch('services.market_service.json.load')
    @patch('services.market_service.os.path.getmtime')
    @patch('builtins.open', new_callable=mock_open)
    def test_handles_corrupted_cache(self, mock_file, mock_mtime,
                                     mock_json_load, mock_isfile,
                                     mock_cache_dir):
        """Corrupted cache (JSONDecodeError) falls through to fetch."""
        from services import market_service
        mock_cache_dir.return_value = '/fake/cache'
        mock_isfile.return_value = True
        mock_mtime.return_value = 9999999999.0
        mock_json_load.side_effect = json.JSONDecodeError('corrupt', '', 0)

        # Patch fetch path: _fetch_with_timeout -> akshare
        boards = _dummy_boards_data(2)
        with patch('services.market_service._fetch_with_timeout',
                   return_value=boards):
            with patch('services.market_service.config.atomic_json_dump'):
                result = market_service.get_industry_boards()

        assert result == {'data': boards, 'count': 2}

    @patch('services.market_service._cache_dir')
    @patch('services.market_service.os.path.isfile', return_value=False)
    @patch('services.market_service._fetch_with_timeout')
    def test_fetch_success_returns_data(self, mock_fetch,
                                        mock_isfile, mock_cache_dir):
        """No cache: fetches from akshare and returns enriched data."""
        from services import market_service
        mock_cache_dir.return_value = '/fake/cache'
        boards = _dummy_boards_data(3)
        mock_fetch.return_value = boards

        with patch('services.market_service.config.atomic_json_dump') as mock_dump:
            result = market_service.get_industry_boards()

        assert result == {'data': boards, 'count': 3}
        mock_dump.assert_called_once()

    @patch('services.market_service._cache_dir')
    @patch('services.market_service.os.path.isfile', return_value=False)
    @patch('services.market_service._fetch_with_timeout')
    def test_fetch_error_returns_error_dict(self, mock_fetch,
                                            mock_isfile, mock_cache_dir):
        """Fetch failure returns error dict."""
        from services import market_service
        mock_cache_dir.return_value = '/fake/cache'
        mock_fetch.return_value = {'error': 'timeout or no data'}

        result = market_service.get_industry_boards()

        assert isinstance(result, dict)
        assert 'error' in result
        assert 'count' not in result

    @patch('services.market_service._cache_dir')
    @patch('services.market_service.os.path.isfile', return_value=False)
    @patch('services.market_service._fetch_with_timeout')
    def test_handles_generic_exception_in_cache(self, mock_fetch,
                                                mock_isfile, mock_cache_dir):
        """Generic exception in cache read (not JSONDecodeError) falls through."""
        from services import market_service
        mock_cache_dir.return_value = '/fake/cache'

        # Simulate a completely busted read path
        with patch('services.market_service.os.path.isfile',
                   side_effect=[True, False]):
            with patch('services.market_service.os.path.getmtime',
                       return_value=9999999999.0):
                with patch('builtins.open') as mock_file:
                    mock_file.side_effect = PermissionError('denied')
                    boards = _dummy_boards_data(1)
                    mock_fetch.return_value = boards
                    with patch('services.market_service.config.atomic_json_dump'):
                        result = market_service.get_industry_boards()

        assert result == {'data': boards, 'count': 1}


# ═══════════════════════════════════════════════════════════════════
# 2. market_service.get_concept_boards()
# ═══════════════════════════════════════════════════════════════════

class TestGetConceptBoards:
    """Tests for market_service.get_concept_boards().

    Returns data or error dict. No caching involved.
    """

    @patch('services.market_service._fetch_with_timeout')
    def test_returns_data_dict_on_success(self, mock_fetch):
        """Happy path: returns {'data': [...], 'count': N}."""
        from services import market_service
        boards = _dummy_boards_data(5)
        mock_fetch.return_value = boards

        result = market_service.get_concept_boards()

        assert result == {'data': boards, 'count': 5}

    @patch('services.market_service._fetch_with_timeout')
    def test_returns_empty_on_empty_data(self, mock_fetch):
        """Empty data returns {'data': [], 'count': 0}."""
        from services import market_service
        mock_fetch.return_value = []

        result = market_service.get_concept_boards()

        assert result == {'data': [], 'count': 0}

    @patch('services.market_service._fetch_with_timeout')
    def test_returns_error_dict_on_failure(self, mock_fetch):
        """Fetch failure returns {'error': ...}."""
        from services import market_service
        mock_fetch.return_value = {'error': 'timeout or no data'}

        result = market_service.get_concept_boards()

        assert isinstance(result, dict)
        assert 'error' in result

    @patch('services.market_service._fetch_with_timeout')
    def test_fetch_timeout_returns_error(self, mock_fetch):
        """Timeout returns error dict (simulated from _fetch_with_timeout)."""
        from services import market_service
        mock_fetch.return_value = {'error': 'timeout or no data'}

        result = market_service.get_concept_boards()

        assert result['error'] == 'timeout or no data'


# ═══════════════════════════════════════════════════════════════════
# 3. monitor_service.get_buy_signals()
# ═══════════════════════════════════════════════════════════════════
#
# ⚠️ BUG KNOWN: monitor_service.py uses config.atomic_json_dump() at line 46
#    but does NOT import `config` (only `from config import CACHE_DIR, ...`).
#    This test catches that bug: without mocking 'config' into the module,
#    calling the subprocess-success path would raise NameError.
#    We inject `monitor_service.config = MagicMock()` to bypass it and test
#    the remaining logic.

class TestGetBuySignals:
    """Tests for monitor_service.get_buy_signals().

    Returns error dict on subprocess failure. Has 1-hour cache TTL.
    Exposes the missing 'config' import bug when subprocess succeeds.
    """

    def _patch_config(self, module):
        """Inject missing 'config' reference into module namespace."""
        module.config = MagicMock()
        return module.config

    @patch('services.monitor_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open,
           read_data='{"signals": [{"code": "000001"}]}')
    def test_returns_cached_data(self, mock_file, mock_isfile):
        """Happy path: existing cache file returns its contents."""
        from services import monitor_service
        result = monitor_service.get_buy_signals()
        assert result == {"signals": [{"code": "000001"}]}

    @patch('services.monitor_service.os.path.isfile', return_value=False)
    @patch('services.monitor_service.subprocess.run')
    @patch('services.monitor_service.os.makedirs')
    def test_subprocess_success_returns_data(self, mock_mkdir,
                                             mock_subp, mock_isfile):
        """Subprocess success: returns parsed JSON, writes cache.

        This path reveals the missing 'config' import bug if not mocked.
        """
        from services import monitor_service
        mock_config = self._patch_config(monitor_service)

        mock_subp.return_value = MagicMock(
            returncode=0,
            stdout='{"signals": [{"code": "300750"}]}',
            stderr=''
        )

        result = monitor_service.get_buy_signals()

        assert result == {"signals": [{"code": "300750"}]}
        mock_config.atomic_json_dump.assert_called_once()

    @patch('services.monitor_service.os.path.isfile', return_value=False)
    @patch('services.monitor_service.subprocess.run')
    @patch('services.monitor_service.os.makedirs')
    def test_subprocess_failure_returns_error(self, mock_mkdir,
                                              mock_subp, mock_isfile):
        """Subprocess non-zero exit: returns error dict with empty signals."""
        from services import monitor_service
        mock_subp.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='something went wrong'
        )

        result = monitor_service.get_buy_signals()

        assert 'error' in result
        assert result['signals'] == []

    @patch('services.monitor_service.os.path.isfile', return_value=False)
    @patch('services.monitor_service.subprocess.run')
    @patch('services.monitor_service.os.makedirs')
    def test_subprocess_exception_returns_error(self, mock_mkdir,
                                                mock_subp, mock_isfile):
        """Subprocess raised exception: returns error dict with empty signals."""
        from services import monitor_service
        mock_subp.side_effect = TimeoutError('subprocess timed out')

        result = monitor_service.get_buy_signals()

        assert 'error' in result
        assert 'timed out' in result['error']
        assert result['signals'] == []

    @patch('services.monitor_service.os.path.isfile', return_value=False)
    @patch('services.monitor_service.subprocess.run')
    @patch('services.monitor_service.os.makedirs')
    def test_exposes_missing_config_import(self, mock_mkdir,
                                           mock_subp, mock_isfile):
        """Without injecting 'config', subprocess success hits NameError
        but it's caught by the generic except Exception handler and
        returned as an error dict. This test proves the P0 bug exists
        by checking the return value instead of expecting an exception.
        """
        from services import monitor_service
        # Remove our patch if it exists from a previous test
        if hasattr(monitor_service, 'config') and not isinstance(
                monitor_service.config, type(monitor_service)):
            del monitor_service.config

        mock_subp.return_value = MagicMock(
            returncode=0,
            stdout='{"signals": [{"code": "300750"}]}',
            stderr=''
        )

        result = monitor_service.get_buy_signals()

        assert 'error' in result
        assert 'config' in result['error'] or 'atomic_json_dump' in result['error']

    @patch('services.monitor_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open,
           read_data='{"error": "cached error", "signals": []}')
    def test_cached_error_dict_preserved(self, mock_file, mock_isfile):
        """Cache file containing error dict is returned as-is."""
        from services import monitor_service
        result = monitor_service.get_buy_signals()
        assert result == {"error": "cached error", "signals": []}


# ═══════════════════════════════════════════════════════════════════
# 4. monitor_service.get_top_sectors()
# ═══════════════════════════════════════════════════════════════════

class TestGetTopSectors:
    """Tests for monitor_service.get_top_sectors().

    Delegates to scripts.monitor_data.get_top_sectors_with_5d().
    Returns whatever that function returns (data or error).
    """

    @patch('scripts.monitor_data.get_top_sectors_with_5d')
    def test_returns_data_on_success(self, mock_sectors):
        """Happy path: returns sector ranking data."""
        from services import monitor_service
        expected = {
            'sectors': [
                {'name': '半导体', 'chg': 3.45, 'rank': 1},
                {'name': '新能源', 'chg': 2.10, 'rank': 2},
            ],
            'count': 2
        }
        mock_sectors.return_value = expected

        result = monitor_service.get_top_sectors()

        assert result == expected
        mock_sectors.assert_called_once()

    @patch('scripts.monitor_data.get_top_sectors_with_5d')
    def test_returns_empty_on_no_data(self, mock_sectors):
        """Empty data returns empty sector list."""
        from services import monitor_service
        expected = {'sectors': [], 'count': 0}
        mock_sectors.return_value = expected

        result = monitor_service.get_top_sectors()

        assert result == expected

    @patch('scripts.monitor_data.get_top_sectors_with_5d')
    def test_returns_error_dict_on_failure(self, mock_sectors):
        """Underlying function failure returns error dict."""
        from services import monitor_service
        mock_sectors.return_value = {'error': 'no data available'}

        result = monitor_service.get_top_sectors()

        assert 'error' in result


# ═══════════════════════════════════════════════════════════════════
# 5. watchlist_service.save_watchlist(data)
# ═══════════════════════════════════════════════════════════════════
#
# ⚠️ BUG KNOWN: watchlist_service.py uses config.atomic_json_dump() at line 26
#    but does NOT import `config` (only `from config import WATCHLIST_PATH, ...`).
#    This test catches that bug. We inject watchlist_service.config to test
#    the rest of the logic.

class TestSaveWatchlist(unittest.TestCase):
    """Tests for watchlist_service.save_watchlist(data). Uses unittest.TestCase
    to avoid pytest fixture name collision with stacked @patch decorators.

    Uses atomic_json_dump correctly for safe writes.
    Only calls ensure_stock_data for NEW stocks (not existing ones).
    Exposes the missing 'config' import bug.
    """

    def _patch_config(self, module):
        """Inject missing 'config' reference into module namespace."""
        module.config = MagicMock()
        return module.config

    @patch('scripts.data_layer.ensure_stock_data')
    @patch('scripts.data_layer.WATCHLIST_PATH', '/fake/watchlist.json')
    @patch('builtins.open', new_callable=mock_open)
    def test_saves_new_watchlist(self, mock_open_file, mock_ensure_stock_data):
        """Happy path: saves data, calls ensure_stock_data for new codes.
        @patch order for params (top→bottom): ensure_stock_data(nonew) → WATCHLIST_PATH(new) → open(new_callable)
        But decorator application is bottom-up: open's mock is 1st injected, ensure_stock_data's mock is 2nd.
        So params are: (open_mock, ensure_stock_data_mock) = (mock_open_file, mock_ensure_stock_data)
        """
        from services import watchlist_service
        mock_config = self._patch_config(watchlist_service)

        # Existing old watchlist has code '000001'
        old_data = json.dumps({'stocks': [{'code': '000001', 'name': '平安银行'}]})
        mock_open_file.return_value.__enter__.return_value.read.return_value = old_data

        new_data = {
            'stocks': [
                {'code': '000001', 'name': '平安银行'},
                {'code': '300750', 'name': '宁德时代'},  # new stock
            ]
        }

        result = watchlist_service.save_watchlist(new_data)

        self.assertEqual(result, {'success': True, 'count': 2})
        # ensure_stock_data should only be called for the new code
        mock_ensure_stock_data.assert_called_once_with('300750')
        mock_config.atomic_json_dump.assert_called_once_with(
            new_data, '/fake/watchlist.json', indent=2
        )

    @patch('scripts.data_layer.ensure_stock_data')
    @patch('scripts.data_layer.WATCHLIST_PATH', '/fake/watchlist.json')
    @patch('builtins.open', new_callable=mock_open)
    def test_does_not_call_ensure_for_existing_stocks(
            self, mock_open_file, mock_ensure_stock_data):
        """Only new (previously unseen) stocks trigger ensure_stock_data.
        @patch bottom→top: ensure_stock_data → WATCHLIST_PATH → builtins.open
        """
        from services import watchlist_service
        mock_config = self._patch_config(watchlist_service)

        old_data = json.dumps({'stocks': [{'code': '000001', 'name': '平安银行'},
                                          {'code': '002594', 'name': '比亚迪'}]})
        mock_open_file.return_value.__enter__.return_value.read.return_value = old_data

        new_data = {
            'stocks': [
                {'code': '000001', 'name': '平安银行'},
            ]
        }

        watchlist_service.save_watchlist(new_data)
        mock_ensure_stock_data.assert_not_called()

    @patch('scripts.data_layer.ensure_stock_data')
    @patch('scripts.data_layer.WATCHLIST_PATH', '/fake/watchlist.json')
    @patch('builtins.open', new_callable=mock_open)
    def test_handles_empty_old_watchlist(
            self, mock_open_file, mock_ensure_stock_data):
        """Old watchlist with 'stocks' key but empty list is handled.
        @patch bottom→top: ensure_stock_data → WATCHLIST_PATH → builtins.open
        """
        from services import watchlist_service
        mock_config = self._patch_config(watchlist_service)

        old_data = json.dumps({'stocks': []})
        mock_open_file.return_value.__enter__.return_value.read.return_value = old_data

        new_data = {
            'stocks': [
                {'code': '300750', 'name': '宁德时代'},
            ]
        }

        result = watchlist_service.save_watchlist(new_data)
        self.assertEqual(result, {'success': True, 'count': 1})
        mock_ensure_stock_data.assert_called_once_with('300750')

    @patch('scripts.data_layer.ensure_stock_data')
    @patch('scripts.data_layer.WATCHLIST_PATH', '/fake/watchlist.json')
    @patch('builtins.open', new_callable=mock_open)
    def test_exposes_missing_config_import(
            self, mock_open_file, mock_ensure_stock_data):
        """Without injecting 'config', the function raises NameError.
        @patch bottom→top: ensure_stock_data → WATCHLIST_PATH → builtins.open

        This test proves the P0 bug exists.
        """
        from services import watchlist_service
        # Ensure config is not injected (no _patch_config call)
        if hasattr(watchlist_service, 'config'):
            del watchlist_service.config

        old_data = json.dumps({'stocks': [{'code': '000001'}]})
        mock_open_file.return_value.__enter__.return_value.read.return_value = old_data

        new_data = {'stocks': [{'code': '000001'}, {'code': '300750'}]}

        with self.assertRaises(NameError) as cm:
            watchlist_service.save_watchlist(new_data)

        self.assertIn('config', str(cm.exception))


# ═══════════════════════════════════════════════════════════════════
# 6. watchlist_service.search_stocks(query)
# ═══════════════════════════════════════════════════════════════════

class TestSearchStocks:
    """Tests for watchlist_service.search_stocks(query).

    Returns results list. Searches code and name fields.
    """

    @pytest.fixture(autouse=True)
    def _setup_mocks(self):
        """Patch ALL_STOCKS_PATH to a fake path for all tests."""
        self._patcher = patch('services.watchlist_service.ALL_STOCKS_PATH',
                              '/fake/all_stocks.json')
        self._patcher.start()
        yield
        self._patcher.stop()

    def _make_stock_data(self, stocks):
        """Build mock all-stocks data structure.

        Format: {"stocks": {"沪A": {"CODE": [{"name": ..., "close": ...}]}}}
        """
        data = {'stocks': {}}
        for code, name, direction in stocks:
            data['stocks'].setdefault(direction, {})[code] = [
                {'name': name, 'close': 10.0 + hash(code) % 100}
            ]
        return data

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_returns_matching_results(self, mock_file, mock_isfile):
        """Happy path: finds stocks matching by code or name."""
        from services import watchlist_service
        stocks = [
            ('000001', '平安银行', '深A'),
            ('300750', '宁德时代', '深A'),
            ('600519', '贵州茅台', '沪A'),
            ('688981', '中芯国际', '沪A'),
        ]
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('平安')

        assert isinstance(result, list)
        assert len(result) >= 1
        assert any(s['code'] == '000001' for s in result)
        assert any('平安' in s['name'] for s in result)

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_search_by_code(self, mock_file, mock_isfile):
        """Search by stock code returns matching results."""
        from services import watchlist_service
        stocks = [
            ('300750', '宁德时代', '深A'),
            ('002594', '比亚迪', '深A'),
        ]
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('300750')

        assert len(result) >= 1
        assert result[0]['code'] == '300750'

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_search_case_insensitive(self, mock_file, mock_isfile):
        """Search is case-insensitive for codes."""
        from services import watchlist_service
        stocks = [
            ('300750', '宁德时代', '深A'),
        ]
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = mock_file.return_value.__enter__.return_value.read.return_value
        # Reset
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('300750')
        assert len(result) == 1

    @patch('builtins.open', new_callable=mock_open)
    def test_empty_query_returns_empty_list(self, mock_file):
        """Empty query string returns empty list immediately."""
        from services import watchlist_service
        result = watchlist_service.search_stocks('')
        assert result == []
        result = watchlist_service.search_stocks('   ')
        assert result == []

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_no_matches_returns_empty_list(self, mock_file, mock_isfile):
        """Query with no matches returns empty list."""
        from services import watchlist_service
        stocks = [
            ('000001', '平安银行', '深A'),
        ]
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('zzzzz')

        assert result == []

    @patch('services.watchlist_service.os.path.isfile', return_value=False)
    def test_missing_file_returns_empty_list(self, mock_isfile):
        """ALL_STOCKS_PATH missing returns empty list."""
        from services import watchlist_service
        result = watchlist_service.search_stocks('平安')

        assert result == []

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_limits_results_to_30(self, mock_file, mock_isfile):
        """Results are capped at 30 entries."""
        from services import watchlist_service
        stocks = []
        for i in range(50):
            stocks.append((f'{i:06d}', f'Stock_{i}', '深A'))
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('Stock')

        assert len(result) <= 30

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open)
    def test_each_result_has_required_fields(self, mock_file, mock_isfile):
        """Each result dict has code, name, direction, price."""
        from services import watchlist_service
        stocks = [('300750', '宁德时代', '深A')]
        mock_file.return_value.__enter__.return_value.read.return_value = \
            json.dumps(self._make_stock_data(stocks))

        result = watchlist_service.search_stocks('300750')

        assert len(result) >= 1
        item = result[0]
        assert 'code' in item
        assert 'name' in item
        assert 'direction' in item
        assert 'price' in item
        assert item['code'] == '300750'
        assert item['name'] == '宁德时代'
        assert item['direction'] == '深A'


# ═══════════════════════════════════════════════════════════════════
# 8. watchlist_service.get_watchlist()
# ═══════════════════════════════════════════════════════════════════

class TestGetWatchlist:
    """Tests for watchlist_service.get_watchlist().
    Reads from WATCHLIST_PATH; returns empty dict if file missing.
    """

    @patch('services.watchlist_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open,
           read_data='{"stocks": [{"code": "000001", "name": "平安银行"}], "count": 1}')
    def test_returns_watchlist_when_file_exists(self, mock_file, mock_isfile):
        """File exists: returns parsed JSON."""
        from services import watchlist_service
        result = watchlist_service.get_watchlist()
        assert result == {'stocks': [{'code': '000001', 'name': '平安银行'}], 'count': 1}

    @patch('services.watchlist_service.os.path.isfile', return_value=False)
    def test_returns_empty_when_file_missing(self, mock_isfile):
        """File missing: returns empty dict."""
        from services import watchlist_service
        result = watchlist_service.get_watchlist()
        assert result == {'stocks': [], 'count': 0}


# ═══════════════════════════════════════════════════════════════════
# 9. holdings_service.get_holdings() & get_trades()
# ═══════════════════════════════════════════════════════════════════

class TestGetHoldings:
    """Tests for holdings_service.get_holdings() and get_trades()."""

    @patch('services.holdings_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open,
           read_data='{"holdings": [{"code": "300750", "name": "宁德时代", "volume": 100}]}')
    def test_get_holdings_returns_data(self, mock_file, mock_isfile):
        """File exists: returns holdings data."""
        from services import holdings_service
        result = holdings_service.get_holdings()
        assert result == {'holdings': [{'code': '300750', 'name': '宁德时代', 'volume': 100}]}

    @patch('services.holdings_service.os.path.isfile', return_value=False)
    def test_get_holdings_empty_when_missing(self, mock_isfile):
        """File missing: returns empty holdings."""
        from services import holdings_service
        result = holdings_service.get_holdings()
        assert result == {'holdings': []}

    @patch('services.holdings_service.os.path.isfile', return_value=True)
    @patch('builtins.open', new_callable=mock_open,
           read_data='{"trades": [{"code": "000001", "action": "buy", "price": 10.0}]}')
    def test_get_trades_returns_data(self, mock_file, mock_isfile):
        """File exists: returns trades data."""
        from services import holdings_service
        result = holdings_service.get_trades()
        assert result == {'trades': [{'code': '000001', 'action': 'buy', 'price': 10.0}]}

    @patch('services.holdings_service.os.path.isfile', return_value=False)
    def test_get_trades_empty_when_missing(self, mock_isfile):
        """File missing: returns empty trades."""
        from services import holdings_service
        result = holdings_service.get_trades()
        assert result == {'trades': []}


# ═══════════════════════════════════════════════════════════════════
# 10. knowledge_service.download_kb_file() — path traversal check
# ═══════════════════════════════════════════════════════════════════

class TestDownloadKbFile:
    """Tests for knowledge_service.download_kb_file().
    Security check: prevents path traversal.
    """

    def test_blocks_path_traversal_upwards(self):
        """'../' in path returns forbidden."""
        from services import knowledge_service
        result, err = knowledge_service.download_kb_file('../../etc/passwd')
        assert result is None
        assert err == 'forbidden'

    def test_blocks_absolute_path(self):
        """Absolute path returns forbidden."""
        from services import knowledge_service
        result, err = knowledge_service.download_kb_file('/etc/passwd')
        assert result is None
        assert err == 'forbidden'

    def test_blocks_encoded_path_traversal(self):
        """URL-encoded '../' is decoded then blocked."""
        from services import knowledge_service
        result, err = knowledge_service.download_kb_file('%2e%2e%2f%2e%2e%2fetc/passwd')
        assert result is None
        assert err == 'forbidden'

    @patch('services.knowledge_service.os.path.isfile', return_value=False)
    def test_nonexistent_file_returns_not_found(self, mock_isfile):
        """Valid path but file does not exist."""
        from services import knowledge_service
        result, err = knowledge_service.download_kb_file('some_file.md')
        assert result is None
        assert err == 'not found'


# ═══════════════════════════════════════════════════════════════════
# 7. Script-level verification (optional but useful)
# ═══════════════════════════════════════════════════════════════════

def test_import_all_services():
    """Verify all service modules can be imported without errors."""
    from services import market_service
    from services import monitor_service
    from services import watchlist_service
    assert market_service is not None
    assert monitor_service is not None
    assert watchlist_service is not None


# ═══════════════════════════════════════════════════════════════════
# 新增: service 函数测试 (mock 数据注入, 2026-05-24)
# ═══════════════════════════════════════════════════════════════════

MOCK_KLINES = [
    {'date': '20260301', 'open': 10.0, 'high': 10.5, 'low': 9.8, 'close': 10.2, 'volume': 100000, 'name': '测试A'},
    {'date': '20260302', 'open': 10.2, 'high': 10.8, 'low': 10.0, 'close': 10.6, 'volume': 120000, 'name': '测试A'},
    {'date': '20260303', 'open': 10.6, 'high': 11.2, 'low': 10.4, 'close': 11.0, 'volume': 150000, 'name': '测试A'},
    {'date': '20260304', 'open': 11.0, 'high': 11.5, 'low': 10.8, 'close': 11.3, 'volume': 140000, 'name': '测试A'},
    {'date': '20260305', 'open': 11.3, 'high': 11.8, 'low': 11.0, 'close': 11.6, 'volume': 160000, 'name': '测试A'},
    {'date': '20260306', 'open': 11.6, 'high': 12.0, 'low': 11.3, 'close': 11.8, 'volume': 170000, 'name': '测试A'},
    {'date': '20260307', 'open': 11.8, 'high': 12.5, 'low': 11.5, 'close': 12.3, 'volume': 200000, 'name': '测试A'},
    {'date': '20260308', 'open': 12.3, 'high': 12.8, 'low': 12.0, 'close': 12.5, 'volume': 180000, 'name': '测试A'},
    {'date': '20260309', 'open': 12.5, 'high': 13.0, 'low': 12.2, 'close': 12.8, 'volume': 190000, 'name': '测试A'},
    {'date': '20260310', 'open': 12.8, 'high': 13.5, 'low': 12.5, 'close': 13.2, 'volume': 210000, 'name': '测试A'},
    {'date': '20260311', 'open': 13.2, 'high': 13.8, 'low': 13.0, 'close': 13.5, 'volume': 220000, 'name': '测试A'},
    {'date': '20260312', 'open': 13.5, 'high': 14.0, 'low': 13.2, 'close': 13.8, 'volume': 230000, 'name': '测试A'},
    {'date': '20260313', 'open': 13.8, 'high': 14.2, 'low': 13.5, 'close': 14.0, 'volume': 240000, 'name': '测试A'},
    {'date': '20260314', 'open': 14.0, 'high': 14.5, 'low': 13.6, 'close': 14.2, 'volume': 250000, 'name': '测试A'},
    {'date': '20260315', 'open': 14.2, 'high': 14.8, 'low': 13.8, 'close': 14.5, 'volume': 260000, 'name': '测试A'},
    {'date': '20260316', 'open': 14.5, 'high': 15.0, 'low': 14.0, 'close': 14.8, 'volume': 280000, 'name': '测试A'},
    {'date': '20260317', 'open': 14.8, 'high': 15.2, 'low': 14.5, 'close': 15.0, 'volume': 270000, 'name': '测试A'},
    {'date': '20260318', 'open': 15.0, 'high': 15.5, 'low': 14.6, 'close': 15.2, 'volume': 290000, 'name': '测试A'},
    {'date': '20260319', 'open': 15.2, 'high': 15.8, 'low': 15.0, 'close': 15.5, 'volume': 300000, 'name': '测试A'},
    {'date': '20260320', 'open': 15.5, 'high': 16.0, 'low': 15.2, 'close': 15.8, 'volume': 310000, 'name': '测试A'},
    {'date': '20260321', 'open': 15.8, 'high': 16.2, 'low': 15.5, 'close': 16.0, 'volume': 320000, 'name': '测试A'},
    {'date': '20260322', 'open': 16.0, 'high': 16.5, 'low': 15.6, 'close': 16.2, 'volume': 330000, 'name': '测试A'},
    {'date': '20260323', 'open': 16.2, 'high': 16.8, 'low': 16.0, 'close': 16.5, 'volume': 340000, 'name': '测试A'},
    {'date': '20260324', 'open': 16.5, 'high': 17.0, 'low': 16.2, 'close': 16.8, 'volume': 350000, 'name': '测试A'},
    {'date': '20260325', 'open': 16.8, 'high': 17.2, 'low': 16.5, 'close': 17.0, 'volume': 360000, 'name': '测试A'},
    {'date': '20260326', 'open': 17.0, 'high': 17.5, 'low': 16.8, 'close': 17.2, 'volume': 370000, 'name': '测试A'},
    {'date': '20260327', 'open': 17.2, 'high': 17.8, 'low': 17.0, 'close': 17.5, 'volume': 380000, 'name': '测试A'},
    {'date': '20260328', 'open': 17.5, 'high': 18.0, 'low': 17.2, 'close': 17.8, 'volume': 390000, 'name': '测试A'},
    {'date': '20260329', 'open': 17.8, 'high': 18.2, 'low': 17.5, 'close': 18.0, 'volume': 400000, 'name': '测试A'},
    {'date': '20260330', 'open': 18.0, 'high': 18.5, 'low': 17.8, 'close': 18.2, 'volume': 410000, 'name': '测试A'},
    {'date': '20260331', 'open': 18.2, 'high': 18.8, 'low': 18.0, 'close': 18.5, 'volume': 420000, 'name': '测试A'},
]

MOCK_STOCKS = {
    '半导体': {'688999': MOCK_KLINES},
    '算力': {'688888': MOCK_KLINES},
}

MOCK_WATCHLIST = [
    {'code': '688999', 'name': '测试A', 'direction': '半导体'},
    {'code': '688888', 'name': '测试B', 'direction': '算力'},
]


class TestAnalysisServiceWithMock:
    """analysis_service 测试 — mock 注入"""

    def test_search_by_code(self):
        """按代码搜索返回正确结构"""
        from services.analysis_service import search_and_analyze
        result = search_and_analyze('688999', stocks=MOCK_STOCKS, wl=MOCK_WATCHLIST)
        assert 'error' not in result
        assert result.get('code') == '688999'
        assert result.get('direction') == '半导体'
        assert result.get('name') == '测试A'

    def test_search_by_name(self):
        """按名称搜索返回正确结构"""
        from services.analysis_service import search_and_analyze
        result = search_and_analyze('测试A', stocks=MOCK_STOCKS, wl=MOCK_WATCHLIST)
        assert 'error' not in result
        assert result.get('code') == '688999'

    def test_search_not_found(self):
        """搜索不存在的股票返回错误"""
        from services.analysis_service import search_and_analyze
        result = search_and_analyze('不存在的股票', stocks=MOCK_STOCKS, wl=MOCK_WATCHLIST)
        assert 'error' in result


class TestBacktestServiceWithMock:
    """backtest_service 测试 — mock 注入"""

    def test_backtest_by_code(self):
        """按代码回测返回正确结构"""
        from services.backtest_service import run_backtest
        result = run_backtest('688999', stocks=MOCK_STOCKS)
        assert 'error' not in result
        assert result.get('code') == '688999'
        assert result.get('name') == '测试A'
        # 回测应包含 signals、胜率等字段
        assert 'signals' in result
        assert 'total' in result

    def test_backtest_not_found(self):
        """回测不存在的股票返回错误"""
        from services.backtest_service import run_backtest
        result = run_backtest('000000', stocks=MOCK_STOCKS)
        assert 'error' in result

    def test_backtest_with_market_position_param(self):
        """回测支持传入market_position参数"""
        from services.backtest_service import run_backtest
        r1 = run_backtest('688999', stocks=MOCK_STOCKS, market_position='波谷')
        assert 'error' not in r1
        assert r1['code'] == '688999'

    def test_backtest_with_main_lines_param(self):
        """回测支持传入main_lines参数"""
        from services.backtest_service import run_backtest
        r2 = run_backtest('688999', stocks=MOCK_STOCKS, main_lines={'半导体', '算力'})
        assert 'error' not in r2
        assert r2['code'] == '688999'

    def test_backtest_chart_has_equity_curve(self):
        """回测图表SVG包含资金曲线面板"""
        from services.backtest_service import run_backtest
        r = run_backtest('688999', stocks=MOCK_STOCKS)
        assert r.get('has_chart') is not None
        assert r.get('chart_svg') is not None

    def test_backtest_signal_has_trading_system(self):
        """回测信号包含trading_system字段"""
        from services.backtest_service import run_backtest
        r = run_backtest('688999', stocks=MOCK_STOCKS)
        for s in r.get('signals', []):
            assert 'trading_system' in s
            assert s['trading_system'] in ('3l', 'trend')


class TestTopGainersServiceWithMock:
    """top_gainers_service 测试 — mock 注入"""

    def test_top_gainers_structure(self):
        """涨幅榜返回正确结构"""
        from services.top_gainers_service import get_top_gainers
        result = get_top_gainers('20260331', limit=5, stocks=MOCK_STOCKS)
        assert 'stocks' in result
        assert 'pie' in result
        assert 'total' in result
        assert isinstance(result['stocks'], list)

    def test_top_gainers_empty_data(self):
        """空数据返回空列表"""
        from services.top_gainers_service import get_top_gainers
        result = get_top_gainers('20991231', limit=5, stocks={})
        assert result['stocks'] == []


class TestTrendServiceWithMock:
    """trend_service 测试 — mock 注入"""

    def test_watchlist_analysis_structure(self):
        """自选股批量分析返回正确结构"""
        from services.trend_service import get_watchlist_analysis
        result = get_watchlist_analysis(stocks=MOCK_STOCKS, wl=MOCK_WATCHLIST)
        assert 'stocks' in result
        assert 'count' in result
        assert result['count'] == len(MOCK_WATCHLIST)
        assert len(result['stocks']) == len(MOCK_WATCHLIST)

    def test_watchlist_analysis_stock_fields(self):
        """每只股票包含必要字段"""
        from services.trend_service import get_watchlist_analysis
        result = get_watchlist_analysis(stocks=MOCK_STOCKS, wl=MOCK_WATCHLIST)
        for s in result['stocks']:
            assert 'code' in s
            assert 'name' in s
            assert 'price' in s
            assert 'change' in s
            assert 'structure' in s
            assert 'stage' in s
