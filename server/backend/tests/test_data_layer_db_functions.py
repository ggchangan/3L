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
