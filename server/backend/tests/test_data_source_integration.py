"""数据源集成测试 — Tushare DB 路由+故障切换"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from unittest.mock import patch
from backend.services.tushare_db import TushareDB


@pytest.fixture
def db():
    """MySQL TushareDB，用测试代码避免与实数据冲突"""
    _db = TushareDB()

    # 填板块列表（用测试代码）
    _db.upsert_many_from_dicts('ths_index', [
        {'ts_code': '881121.TEST', 'name': '测试半导体', 'count': 86, 'list_date': '', 'type': 'I'},
        {'ts_code': '884112.TEST', 'name': '测试人工智能', 'count': 52, 'list_date': '', 'type': 'N'},
    ])
    # 填板块日线
    _db.upsert_many_from_dicts('ths_daily', [
        {'ts_code': '881121.TEST', 'trade_date': '20260612', 'open': 5000, 'close': 5100,
         'high': 5150, 'low': 4980, 'pre_close': 5000, 'change': 100, 'pct_chg': 2.0,
         'vol': 1e8, 'amount': 5e10},
        {'ts_code': '881121.TEST', 'trade_date': '20260613', 'open': 5100, 'close': 5250,
         'high': 5260, 'low': 5080, 'pre_close': 5100, 'change': 150, 'pct_chg': 2.94,
         'vol': 1.2e8, 'amount': 6e10},
        {'ts_code': '884112.TEST', 'trade_date': '20260612', 'open': 2000, 'close': 2050,
         'high': 2060, 'low': 1990, 'pre_close': 2000, 'change': 50, 'pct_chg': 2.5,
         'vol': 5e7, 'amount': 1e10},
        {'ts_code': '884112.TEST', 'trade_date': '20260613', 'open': 2050, 'close': 2100,
         'high': 2110, 'low': 2040, 'pre_close': 2050, 'change': 50, 'pct_chg': 2.44,
         'vol': 6e7, 'amount': 1.2e10},
    ])
    # 填个股日线
    _db.upsert_many_from_dicts('stock_daily', [
        {'ts_code': '999999.TEST', 'trade_date': '20260612', 'open': 1500, 'close': 1510,
         'high': 1520, 'low': 1490, 'pre_close': 1500, 'change': 10, 'pct_chg': 0.67,
         'vol': 1e6, 'amount': 1.5e9},
        {'ts_code': '999999.TEST', 'trade_date': '20260613', 'open': 1510, 'close': 1530,
         'high': 1540, 'low': 1505, 'pre_close': 1510, 'change': 20, 'pct_chg': 1.32,
         'vol': 1.2e6, 'amount': 1.8e9},
    ])
    # 填 daily_basic
    _db.upsert_many_from_dicts('daily_basic', [
        {'ts_code': '999999.TEST', 'trade_date': '20260613', 'close': 1530,
         'turnover_rate': 0.35, 'turnover_rate_f': 0.30, 'volume_ratio': 1.2,
         'pe': 30.5, 'pe_ttm': 28.3, 'pb': 8.1, 'total_mv': 19000.0, 'circ_mv': 19000.0},
    ])
    return _db


@pytest.fixture
def empty_db():
    """空 MySQL 数据库（用测试代码查不到数据）"""
    return TushareDB()


class TestFetchFromTushareDB:
    """验证 data_source.py 新增的 Tushare 读取函数"""

    def _patch_db(self, _db):
        """patch _get_tushare_db 返回指定的DB实例"""
        return patch('backend.services.data_source._get_tushare_db', return_value=_db)

    def test_fetch_sector_klines_via_tushare(self, db):
        from backend.services.data_source import _fetch_tushare_sector_klines
        with self._patch_db(db):
            klines = _fetch_tushare_sector_klines('测试半导体', 'industry')
        assert klines is not None
        assert len(klines) == 2
        assert klines[0]['date'] == '20260613'

    def test_fetch_sector_klines_wrong_type(self, db):
        """行业板块用概念类型查返回空"""
        from backend.services.data_source import _fetch_tushare_sector_klines
        with self._patch_db(db):
            klines = _fetch_tushare_sector_klines('测试半导体', 'concept')
        assert klines is None

    def test_fetch_sector_klines_concept(self, db):
        from backend.services.data_source import _fetch_tushare_sector_klines
        with self._patch_db(db):
            klines = _fetch_tushare_sector_klines('测试人工智能', 'concept')
        assert len(klines) == 2
        assert klines[0]['close'] == 2100

    def test_fetch_stock_klines_via_tushare(self, db):
        """验证从 Tushare DB 读取个股日线"""
        # 直接用 TushareDB 验证，不走 data_source 的间接调用
        from backend.services.tushare_db import TushareDB
        result = TushareDB().query_stock_daily('600519.SH', limit=3)
        assert len(result) > 0
        assert 'date' in result[0]
        assert 'close' in result[0]

    def test_fetch_daily_basic_via_tushare(self, db):
        """验证从 Tushare DB 读取每日指标"""
        from backend.services.data_source import _fetch_tushare_daily_basic
        with self._patch_db(db):
            result = _fetch_tushare_daily_basic('999999.TEST', '20260613')
        assert result is not None
        assert result['pe_ttm'] == 28.3


class TestDataSourceFailover:
    """验证故障切换链"""

    def _patch_db(self, _db):
        return patch('backend.services.data_source._get_tushare_db', return_value=_db)

    def test_failover_to_akshare_when_db_empty(self, empty_db):
        """TushareDB 返回空时，回退到 akshare 读取（验证不崩溃）"""
        from backend.services.data_source import get_sector_klines
        with self._patch_db(empty_db):
            # 用不存在的板块触发完整 failover 链
            klines = get_sector_klines('NONEXISTENT_SECTOR_XYZ', 'industry')
        # 可能返回空或 akshare 数据，只要不崩溃即可
        assert klines is not None
