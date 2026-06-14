"""
Phase R1 — TDD: data_source 新增 DB 读写接口
data_source 只做纯数据操作，不依赖 data_layer（避免循环引用）。
业务逻辑（方向分组、watchlist）留在 data_layer。
"""
import sys
sys.path.insert(0, 'server')
import os
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
import pytest
from unittest.mock import patch, MagicMock
from backend.services import data_source as ds


class TestGetAllStocksFromDB:
    """data_source.get_all_stocks_from_db() — 批量K线+名称"""

    @patch('backend.services.data_source._get_tushare_db')
    def test_returns_code_to_klines_map(self, mock_get_db):
        """返回 {code: [klines]} 格式"""
        mock_db = MagicMock()
        mock_db.query_stock_klines_batch.return_value = {
            '600519': [{'date': '20260612', 'open': 100.0, 'close': 101.0}],
        }
        mock_db.execute_raw.return_value = [{'symbol': '600519', 'name': '贵州茅台'}]
        mock_db.code_to_ts_code.side_effect = lambda c: f'{c}.SH'
        mock_get_db.return_value = mock_db

        result = ds.get_all_stocks_from_db(['600519'], limit=5)
        assert '600519' in result
        assert len(result['600519']['klines']) == 1
        assert result['600519']['name'] == '贵州茅台'

    @patch('backend.services.data_source._get_tushare_db')
    def test_handles_empty_codes_list(self, mock_get_db):
        """空列表返回空字典"""
        mock_get_db.return_value = MagicMock()
        result = ds.get_all_stocks_from_db([], limit=5)
        assert result == {}

    @patch('backend.services.data_source._get_tushare_db')
    def test_fills_name_from_stock_basic(self, mock_get_db):
        """名称从 stock_basic 表查询"""
        mock_db = MagicMock()
        mock_db.query_stock_klines_batch.return_value = {
            '600519': [{'date': '20260612', 'close': 101.0}],
            '000001': [{'date': '20260612', 'close': 10.0}],
        }
        mock_db.execute_raw.return_value = [
            {'symbol': '600519', 'name': '贵州茅台'},
            {'symbol': '000001', 'name': '平安银行'},
        ]
        mock_db.code_to_ts_code.side_effect = lambda c: f'{c}.SH'
        mock_get_db.return_value = mock_db

        result = ds.get_all_stocks_from_db(['600519', '000001'], limit=5)
        assert result['600519']['name'] == '贵州茅台'
        assert result['000001']['name'] == '平安银行'

    @patch('backend.services.data_source._get_tushare_db')
    def test_handles_missing_name_gracefully(self, mock_get_db):
        """stock_basic 查不到的code，name 置空"""
        mock_db = MagicMock()
        mock_db.query_stock_klines_batch.return_value = {
            '999999': [{'date': '20260612', 'close': 50.0}],
        }
        mock_db.execute_raw.return_value = []  # stock_basic 查不到
        mock_db.code_to_ts_code.side_effect = lambda c: f'{c}.SH'
        mock_get_db.return_value = mock_db

        result = ds.get_all_stocks_from_db(['999999'], limit=5)
        assert result['999999']['name'] == ''


class TestGetIndexDataFromDB:
    """data_source.get_index_data_from_db()"""

    INDEX_CODES = {
        '000001': '上证指数',
        '000688': '科创50',
        '000985': '中证全指',
        '399006': '创业板指',
    }

    @patch('backend.services.data_source._get_tushare_db')
    def test_returns_multi_index_structure(self, mock_get_db):
        """返回 {code: {name, klines}} 格式"""
        mock_db = MagicMock()
        def mock_get_klines(ts_code, limit=500):
            return [{'date': '20260612', 'close': 3000.0}] if 'SH' in ts_code else [{'date': '20260612', 'close': 2000.0}]
        mock_db.get_index_klines.side_effect = mock_get_klines
        mock_get_db.return_value = mock_db

        result = ds.get_index_data_from_db(self.INDEX_CODES)
        assert '000985' in result
        assert result['000985']['name'] == '中证全指'
        assert len(result['000985']['klines']) == 1

    @patch('backend.services.data_source._get_tushare_db')
    def test_empty_db_returns_empty(self, mock_get_db):
        """DB无数据时返回空字典"""
        mock_db = MagicMock()
        mock_db.get_index_klines.return_value = []
        mock_get_db.return_value = mock_db

        result = ds.get_index_data_from_db(self.INDEX_CODES)
        assert result == {}


class TestSaveStockKlines:
    """data_source.save_stock_klines_to_db()"""

    @patch('backend.services.data_source._get_tushare_db')
    def test_saves_klines_as_rows(self, mock_get_db):
        """将 {code: {klines, name}} 写入 stock_daily"""
        mock_db = MagicMock()
        mock_db.code_to_ts_code.return_value = '600519.SH'
        mock_get_db.return_value = mock_db

        stock_data = {
            '600519': {
                'name': '贵州茅台',
                'klines': [
                    {'date': '20260612', 'open': 100.0, 'close': 101.0, 'high': 102.0, 'low': 99.0, 'volume': 10000, 'pre_close': 99.0, 'change': 2.0, 'pct_chg': 2.02},
                ],
            },
        }
        ds.save_stock_klines_to_db(stock_data)
        mock_db.upsert_many_from_dicts.assert_called_once()
        args = mock_db.upsert_many_from_dicts.call_args
        assert args[0][0] == 'stock_daily'
        assert args[0][1][0]['ts_code'] == '600519.SH'


class TestSaveIndexKlines:
    """data_source.save_index_klines_to_db()"""

    @patch('backend.services.data_source._get_tushare_db')
    def test_saves_index_rows(self, mock_get_db):
        """将 {code: {name, klines}} 写入 index_daily"""
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        index_data = {
            '000985': {
                'name': '中证全指',
                'klines': [{'date': '20260612', 'open': 5000.0, 'high': 5100.0, 'close': 5050.0, 'volume': 100000}],
            },
        }
        ds.save_index_klines_to_db(index_data)
        mock_db.upsert_many_from_dicts.assert_called_once()
        args = mock_db.upsert_many_from_dicts.call_args
        assert args[0][0] == 'index_daily'
        assert args[0][1][0]['ts_code'] == '000985.SH'
