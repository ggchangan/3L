#!/usr/bin/env python3
"""测试 data_layer → data_source DB 访问函数的正确路由"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from unittest.mock import patch, MagicMock
import pytest


class TestDataLayerDbFunctions:
    """验证 data_layer 的 DB 访问函数正确转发到 data_source"""

    def _mock_data_source(self, func_name, return_value):
        """创建一个 mock 注入 data_source 中的函数"""
        patcher = patch(
            f'backend.data_access.data_source.{func_name}',
            return_value=return_value,
        )
        mock_fn = patcher.start()
        # 确保 data_layer 清理缓存重新导入
        if func_name in sys.modules.get('backend.data_access.data_layer', {}).__dict__:
            pass
        return patcher, mock_fn

    def test_get_ths_index_names_exists(self):
        """验证函数存在并可调用"""
        from backend.data_access.data_layer import get_ths_index_names
        assert callable(get_ths_index_names)

    def test_fetch_ths_daily_klines_akshare_exists(self):
        """验证函数存在并可调用"""
        from backend.data_access.data_layer import fetch_ths_daily_klines_akshare
        assert callable(fetch_ths_daily_klines_akshare)

    def test_build_industry_map_from_db_exists(self):
        """验证函数存在并可调用"""
        from backend.data_access.data_layer import build_industry_map_from_db
        assert callable(build_industry_map_from_db)

    def test_build_concept_maps_from_db_exists(self):
        """验证函数存在并可调用"""
        from backend.data_access.data_layer import build_concept_maps_from_db
        assert callable(build_concept_maps_from_db)

    def test_tushare_fetch_daily_incremental_exists(self):
        """验证函数存在并可调用"""
        from backend.data_access.data_layer import tushare_fetch_daily_incremental
        assert callable(tushare_fetch_daily_incremental)

    @patch('backend.data_access.data_source.get_ths_index_names')
    def test_get_ths_index_names_default(self, mock_source):
        """默认参数为 'I'（行业）"""
        mock_source.return_value = [('银行', 'I'), ('半导体', 'I')]
        from backend.data_access.data_layer import get_ths_index_names
        result = get_ths_index_names()
        mock_source.assert_called_once_with('I')
        assert result == [('银行', 'I'), ('半导体', 'I')]

    @patch('backend.data_access.data_source.get_ths_index_names')
    def test_get_ths_index_names_concept(self, mock_source):
        """概念参数 'N' 正确传递"""
        mock_source.return_value = [('AI概念', 'N')]
        from backend.data_access.data_layer import get_ths_index_names
        result = get_ths_index_names('N')
        mock_source.assert_called_once_with('N')
        assert result == [('AI概念', 'N')]


class TestUpdateStockDataModule:
    """验证 update_stock_data.py 不再直接调 TushareDB"""

    def test_no_tusharedb_import(self):
        """模块中不应存在 TushareDB 的导入和使用"""
        from backend.core import update_stock_data as usd
        source = open(usd.__file__).read()
        import_lines = [l for l in source.splitlines() if 'import' in l and 'TushareDB' in l]
        assert not import_lines, f'不应导入 TushareDB: {import_lines}'
        assert 'TushareDB()' not in source, '不应实例化 TushareDB'

    def test_update_industry_map_uses_data_layer(self):
        """update_industry_map 应调用 build_industry_map_from_db"""
        from backend.core import update_stock_data as usd
        source = open(usd.__file__).read()
        assert 'build_industry_map_from_db()' in source

    def test_update_concept_maps_uses_data_layer(self):
        """update_concept_maps 应调用 build_concept_maps_from_db"""
        from backend.core import update_stock_data as usd
        source = open(usd.__file__).read()
        assert 'build_concept_maps_from_db()' in source

    def test_update_sectors_no_tusharedb(self):
        """update_sectors 不再直接创建 TushareDB"""
        from backend.core import update_stock_data as usd
        source = open(usd.__file__).read()
        assert 'get_ths_index_names' in source
        assert 'fetch_ths_daily_klines_akshare' in source

    def test_fetch_tushare_daily_no_direct_db(self):
        """_fetch_tushare_daily_incremental 不再直接调 TushareDB"""
        from backend.core import update_stock_data as usd
        source = open(usd.__file__).read()
        assert 'tushare_fetch_daily_incremental()' in source


class TestDataSourceNewFunctions:
    """验证 data_source 的新函数结构正确"""

    def test_data_source_module_importable(self):
        """data_source 模块可正常导入"""
        from backend.data_access import data_source
        assert hasattr(data_source, 'get_ths_index_names')
        assert hasattr(data_source, 'fetch_ths_daily_klines_akshare')
        assert hasattr(data_source, 'build_industry_map_from_db')
        assert hasattr(data_source, 'build_concept_maps_from_db')
        assert hasattr(data_source, 'tushare_fetch_daily_incremental')
        assert hasattr(data_source, '_convert_board_kline')

    def test_convert_board_kline(self):
        """_convert_board_kline 正确转换 DataFrame"""
        import pandas as pd
        from backend.data_access.data_source import _convert_board_kline
        df = pd.DataFrame({
            '日期': ['2025-01-02', '2025-01-03'],
            '开盘价': [100.0, 101.0],
            '收盘价': [101.0, 102.0],
            '最高价': [102.0, 103.0],
            '最低价': [99.0, 100.0],
            '成交量': [10000, 20000],
        })
        result = _convert_board_kline(df)
        assert len(result) == 2
        assert result[0]['date'] == '20250102'
        assert result[0]['open'] == 100.0
        assert result[0]['close'] == 101.0
        assert result[0]['high'] == 102.0
        assert result[0]['low'] == 99.0
        assert result[0]['volume'] == 10000


class TestTushareIncrementalIndexDaily:
    """验证 index_daily 增量拉取的按代码独立检查逻辑（避免其他指数误跳过）"""

    @patch('backend.data_access.data_source.datetime')
    @patch('backend.data_access.data_source.get_last_completed_trading_day')
    @patch('backend.data_access.data_source._get_tushare_db')
    def test_index_checked_independently(self, mock_db, mock_ltd, mock_dt):
        """验证每个指数按 ts_code 独立检查最新日期，不互相干扰"""
        import pandas as pd

        mock_ltd.return_value = '20260617'
        mock_dt.now.return_value.weekday.return_value = 2  # 周三

        # mock DB
        mock_db_inst = MagicMock()
        mock_db_inst.get_last_trade_date.return_value = '20260617'

        def mock_execute_raw(sql, params=None):
            if '000001.SH' in str(params):
                return [{'latest': '20260617'}]
            elif '000688.SH' in str(params):
                return [{'latest': '20260616'}]
            elif '000985.SH' in str(params):
                return [{'latest': '20260617'}]
            elif '399006.SZ' in str(params):
                return [{'latest': '20260616'}]
            return [{'latest': '20260616'}]

        mock_db_inst.execute_raw.side_effect = mock_execute_raw
        mock_db_inst.upsert_many.return_value = 1
        mock_db.return_value = mock_db_inst

        # mock Tushare API via sys.modules（兼容无 tushare 库的环境）
        mock_pro_api = MagicMock()
        mock_pro_api.index_daily.return_value = pd.DataFrame({
            'ts_code': ['000688.SH'],
            'trade_date': ['20260617'],
            'open': [1750.0], 'close': [1760.0], 'high': [1770.0],
            'low': [1745.0], 'pre_close': [1750.0], 'change': [10.0],
            'pct_chg': [0.57], 'vol': [1e8], 'amount': [5e10],
        })
        mock_tushare = MagicMock(pro_api=MagicMock(return_value=mock_pro_api))

        from backend.data_access.data_source import tushare_fetch_daily_incremental

        with patch.dict('sys.modules', {'tushare': mock_tushare}):
            result = tushare_fetch_daily_incremental()

        assert result == 2, f'期望拉取2条指数，实际{result}条'
        assert mock_pro_api.index_daily.call_count == 2

        calls = [c[0] for c in mock_db_inst.execute_raw.call_args_list
                 if 'WHERE ts_code' in str(c[0])]
        assert len(calls) == 4, f'期望4次按代码查询，实际{len(calls)}次'
        for c in calls:
            sql, params = c
            assert params is not None and len(params) == 1
            assert params[0] in ['000001.SH', '000688.SH', '000985.SH', '399006.SZ']
