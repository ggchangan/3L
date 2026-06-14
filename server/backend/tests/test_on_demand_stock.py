"""按需拉取服务单元测试"""
import sys, os, json, time
from unittest.mock import patch, MagicMock, mock_open
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
_core_root = os.path.join(_server_root, '..', 'core')
for p in [_server_root, _core_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core.on_demand_stock import (
    get_or_fetch_stock_data,
    _fetch_klines_akshare,
    _get_direction,
    _load_cache,
    _check_cache,
    _save_to_cache,
    MAX_CACHED_STOCKS,
    CACHE_TTL_HOURS,
    ON_DEMAND_CACHE_PATH,
)
from backend.services.analysis_service import _try_on_demand_fetch


# ====== akshare K线拉取 ======

class TestFetchKlinesAkshare:
    """验证akshare数据格式转换"""

    def test_returns_correct_format(self):
        """akshare返回数据被正确转换为内部格式"""
        import pandas as pd
        # 至少30条才能通过 len>=30 检查
        rows = [{'日期': f'202605{20+i:02d}', '开盘': 10.5, '收盘': 11.2,
                 '最高': 11.5, '最低': 10.3, '成交量': 100000} for i in range(30)]
        mock_df = pd.DataFrame(rows)
        with patch('akshare.stock_zh_a_hist', return_value=mock_df):
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=None):
                klines = _fetch_klines_akshare('300894')
                assert klines is not None
                # 30条以上，截取后60条 → 全部保留
                assert len(klines) == 30
                row = klines[0]
                assert row['date'] == '20260520'
                assert row['open'] == 10.5
                assert row['close'] == 11.2
                assert row['high'] == 11.5
                assert row['low'] == 10.3
                assert row['volume'] == 100000
                # 不包含 name 字段（与 mootdx 格式一致）
                assert 'name' not in row

    def test_empty_df(self):
        """akshare返回空DataFrame时返回None"""
        import pandas as pd
        with patch('akshare.stock_zh_a_hist', return_value=pd.DataFrame()):
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=None):
                assert _fetch_klines_akshare('000001') is None

    def test_none_df(self):
        """akshare返回None时返回None"""
        with patch('akshare.stock_zh_a_hist', return_value=None):
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=None):
                assert _fetch_klines_akshare('000001') is None

    def test_truncated_to_60(self):
        """返回数据超过60条时只保留最近60条"""
        import pandas as pd
        dates = [f'202601{i+1:02d}' for i in range(70)]
        mock_df = pd.DataFrame([{
            '日期': d, '开盘': 10, '收盘': 10, '最高': 11,
            '最低': 9, '成交量': 1000,
        } for d in dates])
        with patch('akshare.stock_zh_a_hist', return_value=mock_df):
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=None):
                klines = _fetch_klines_akshare('300894')
                assert len(klines) == 60
                assert klines[0]['date'] == '20260111'
                assert klines[-1]['date'] == '20260170'

    def test_mootdx_fallback_when_akshare_fails(self):
        """akshare失败时自动回退到mootdx"""
        with patch('akshare.stock_zh_a_hist', return_value=None):
            # 让 mootdx 也返回 None（避免真实网络请求）
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=None):
                assert _fetch_klines_akshare('000001') is None

    def test_mootdx_fallback_returns_data(self):
        """akshare失败但mootdx成功时返回mootdx数据"""
        mock_klines = [{'date': '20260101', 'open': 10, 'close': 11,
                        'high': 12, 'low': 9, 'volume': 1000}] * 60
        with patch('akshare.stock_zh_a_hist', return_value=None):
            with patch('backend.core.on_demand_stock._fetch_via_mootdx', return_value=mock_klines):
                klines = _fetch_klines_akshare('000001')
                assert len(klines) == 60
                assert klines[0]['close'] == 11


# ====== 方向映射 ======

class TestGetDirection:
    """行业→方向映射"""

    def test_known_semiconductor(self):
        with patch('backend.data_access.data_layer.get_industry_map', return_value={
            '688981': {'ths_industry': '半导体'},
        }):
            assert _get_direction('688981') == '半导体'

    def test_known_robot(self):
        with patch('backend.data_access.data_layer.get_industry_map', return_value={
            '300124': {'ths_industry': '机器人'},
        }):
            assert _get_direction('300124') == '机器人'

    def test_unknown_returns_qita(self):
        with patch('backend.data_access.data_layer.get_industry_map', return_value={
            '600000': {'ths_industry': '银行'},
        }):
            assert _get_direction('600000') == '其他'

    def test_no_industry_map_entry(self):
        with patch('backend.data_access.data_layer.get_industry_map', return_value={}):
            assert _get_direction('999999') == '其他'

    def test_info_is_not_dict(self):
        with patch('backend.data_access.data_layer.get_industry_map', return_value={
            '600000': '浦发银行',
        }):
            assert _get_direction('600000') == '其他'


# ====== 缓存管理 ======

class TestCacheManagement:
    def test_cache_hit_within_ttl(self, tmp_path):
        """同一只股票在TTL内第二次搜索命中缓存"""
        cache_file = tmp_path / 'stock_on_demand_cache.json'
        with patch('backend.core.on_demand_stock.ON_DEMAND_CACHE_PATH', str(cache_file)):
            klines = [{'date': '20260101', 'open': 10, 'close': 11,
                       'high': 12, 'low': 9, 'volume': 1000}]
            _save_to_cache('300894', {
                'klines': klines,
                'direction': '其他',
                'name': '火星人',
            })

            cache = _load_cache()
            entry = _check_cache(cache, '300894')
            assert entry is not None
            assert entry['direction'] == '其他'
            assert entry['name'] == '火星人'
            assert entry['klines'][0]['date'] == '20260101'

    def test_cache_miss_wrong_code(self, tmp_path):
        """不存在的股票代码不命中缓存"""
        cache_file = tmp_path / 'stock_on_demand_cache.json'
        with patch('backend.core.on_demand_stock.ON_DEMAND_CACHE_PATH', str(cache_file)):
            _save_to_cache('300894', {
                'klines': [], 'direction': '其他', 'name': '火星人',
            })
            cache = _load_cache()
            assert _check_cache(cache, '000001') is None

    def test_cache_max_stocks_pruning(self, tmp_path):
        """超过MAX_CACHED_STOCKS只保留最新的"""
        cache_file = tmp_path / 'stock_on_demand_cache.json'
        with patch('backend.core.on_demand_stock.ON_DEMAND_CACHE_PATH', str(cache_file)):
            for i in range(MAX_CACHED_STOCKS + 5):
                code = f'{i:06d}'
                _save_to_cache(code, {
                    'klines': [], 'direction': '其他', 'name': code,
                })
            cache = _load_cache()
            stocks = cache.get('stocks', {})
            assert len(stocks) <= MAX_CACHED_STOCKS


# ====== get_or_fetch_stock_data ======

class TestGetOrFetchStockData:
    def test_already_in_main_data(self):
        """股票已在主数据文件中，直接返回"""
        mock_stocks = {'半导体': {'688981': [{'date': '20260101', 'close': 50}]}}
        with patch('backend.data_access.data_layer.get_all_stocks', return_value=mock_stocks):
            klines, direction, name = get_or_fetch_stock_data('688981')
            assert direction == '半导体'
            assert klines[0]['close'] == 50

    def test_fetch_and_cache(self, tmp_path):
        """股票不在主数据→akshare拉取→缓存→返回"""
        import pandas as pd
        cache_file = tmp_path / 'stock_on_demand_cache.json'

        patches = [
            patch('backend.data_access.data_layer.get_all_stocks', return_value={}),
            patch('backend.core.on_demand_stock.ON_DEMAND_CACHE_PATH', str(cache_file)),
            patch('backend.core.on_demand_stock._fetch_klines_akshare', return_value=[
                {'date': f'202601{i:02d}', 'open': 10, 'close': 11,
                 'high': 12, 'low': 9, 'volume': 1000}
                for i in range(1, 31)
            ]),
            patch('backend.core.on_demand_stock._get_direction', return_value='其他'),
            patch('backend.core.on_demand_stock._get_name', return_value='火星人'),
        ]
        for p in patches:
            p.start()
        try:
            klines, direction, name = get_or_fetch_stock_data('300894')
            assert len(klines) >= 30
            assert direction == '其他'
            assert name == '火星人'

            cache = _load_cache()
            assert '300894' in cache.get('stocks', {})
        finally:
            for p in patches:
                p.stop()

    def test_klines_less_than_30_returns_none(self, tmp_path):
        """K线不足30条时不缓存、不注入"""
        cache_file = tmp_path / 'stock_on_demand_cache.json'
        patches = [
            patch('backend.data_access.data_layer.get_all_stocks', return_value={}),
            patch('backend.core.on_demand_stock.ON_DEMAND_CACHE_PATH', str(cache_file)),
            patch('backend.core.on_demand_stock._fetch_klines_akshare', return_value=[
                {'date': '20260101', 'open': 10, 'close': 11,
                 'high': 12, 'low': 9, 'volume': 1000}
            ]),
        ]
        for p in patches:
            p.start()
        try:
            result = get_or_fetch_stock_data('300894')
            assert result == (None, None, None)

            cache = _load_cache()
            assert '300894' not in cache.get('stocks', {})
        finally:
            for p in patches:
                p.stop()


# ====== _try_on_demand_fetch ======

class TestTryOnDemandFetch:
    def test_successful_on_demand(self, tmp_path):
        """按需拉取成功后注入stocks dict并返回(code, direction, name)"""
        mock_market = [{'code': '300894', 'name': '火星人'}]
        klines = [{'date': '20260101', 'open': 10, 'close': 11,
                   'high': 12, 'low': 9, 'volume': 1000}] * 30

        with patch('backend.services.analysis_service.search_stock_full_market',
                   return_value=mock_market):
            with patch('backend.core.on_demand_stock.get_or_fetch_stock_data',
                       return_value=(klines, '其他', '火星人')):
                stocks = {}
                result = _try_on_demand_fetch('300894', stocks)
                assert result == ('300894', '其他', '火星人')
                assert '其他' in stocks
                assert stocks['其他']['300894'] == klines

    def test_market_not_found(self):
        """全市场找不到该股票时返回None"""
        with patch('backend.services.analysis_service.search_stock_full_market',
                   return_value=[]):
            result = _try_on_demand_fetch('NOTEXIST', {})
            assert result is None

    def test_klines_insufficient(self):
        """K线不足30条时返回None"""
        mock_market = [{'code': '300894', 'name': '火星人'}]
        with patch('backend.services.analysis_service.search_stock_full_market',
                   return_value=mock_market):
            with patch('backend.core.on_demand_stock.get_or_fetch_stock_data',
                       return_value=(None, None, None)):
                result = _try_on_demand_fetch('300894', {})
                assert result is None
