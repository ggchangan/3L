"""TushareDB 单元测试 — 测试SQLite建表+CRUD 不依赖Tushare网络"""
import os, sys, json, tempfile, sqlite3
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest

@pytest.fixture
def db():
    """使用临时内存数据库，不写磁盘"""
    from backend.services.tushare_db import TushareDB
    _db = TushareDB(db_path=':memory:')
    yield _db


class TestTushareDBInit:
    """TushareDB 初始化与建表"""

    def test_init_creates_tables(self, db):
        """建表后9张表都应存在"""
        tables = db.get_table_names()
        expected = {
            'stock_daily', 'daily_basic', 'index_daily',
            'ths_daily', 'ths_index', 'ths_member',
            'stock_basic', 'adj_factor', 'trade_cal',
        }
        assert expected.issubset(set(tables)), f"Missing tables: {expected - set(tables)}"

    def test_has_required_indexes(self, db):
        """验证关键索引存在"""
        idxs = db.get_index_names('stock_daily')
        assert 'idx_stock_daily_ts_code' in idxs
        assert 'idx_stock_daily_date' in idxs


class TestStockBasic:
    """stock_basic 表 CRUD"""

    def test_upsert_and_query(self, db):
        df = type('Df', (), {
            'to_dict': lambda self, orient: [{
                'ts_code': '000001.SZ', 'symbol': '000001', 'name': '平安银行',
                'area': '深圳', 'industry': '银行', 'market': '主板',
                'list_date': '19910403', 'delist_date': None, 'is_hs': 'H',
            }]
        })()
        db.upsert_many('stock_basic', df)

        row = db.query_one('stock_basic', ts_code='000001.SZ')
        assert row is not None
        assert row['name'] == '平安银行'
        assert row['industry'] == '银行'

    def test_upsert_overwrite(self, db):
        df1 = type('Df', (), {'to_dict': lambda self, orient: [{
            'ts_code': '000001.SZ', 'symbol': '000001', 'name': '旧名',
            'area': '', 'industry': '', 'market': '', 'list_date': '', 'delist_date': None, 'is_hs': '',
        }]})()
        db.upsert_many('stock_basic', df1)

        df2 = type('Df', (), {'to_dict': lambda self, orient: [{
            'ts_code': '000001.SZ', 'symbol': '000001', 'name': '新名',
            'area': '', 'industry': '', 'market': '', 'list_date': '', 'delist_date': None, 'is_hs': '',
        }]})()
        db.upsert_many('stock_basic', df2)

        row = db.query_one('stock_basic', ts_code='000001.SZ')
        assert row['name'] == '新名', "INSERT OR REPLACE 应覆盖旧数据"


class TestStockDaily:
    """stock_daily 表 — 个股日线"""

    def test_upsert_and_query_recent(self, db):
        rows = [
            {'ts_code': '600519.SH', 'trade_date': '20260601', 'open': 1500.0,
             'high': 1520.0, 'low': 1490.0, 'close': 1510.0,
             'pre_close': 1500.0, 'change': 10.0, 'pct_chg': 0.67,
             'vol': 1000000.0, 'amount': 1.5e9},
            {'ts_code': '600519.SH', 'trade_date': '20260602', 'open': 1510.0,
             'high': 1530.0, 'low': 1500.0, 'close': 1525.0,
             'pre_close': 1510.0, 'change': 15.0, 'pct_chg': 0.99,
             'vol': 1200000.0, 'amount': 1.8e9},
        ]
        db.upsert_many_from_dicts('stock_daily', rows)

        klines = db.query_stock_daily('600519.SH', limit=5)
        assert len(klines) == 2
        # 按日期倒序
        assert klines[0]['date'] == '20260602'
        assert klines[1]['date'] == '20260601'
        # 输出格式兼容现有 Kline 合约
        assert 'open' in klines[0] and 'close' in klines[0]
        assert 'high' in klines[0] and 'low' in klines[0]
        assert 'volume' in klines[0]

    def test_empty_query_returns_empty_list(self, db):
        klines = db.query_stock_daily('999999.SH', limit=10)
        assert klines == []


class TestDailyBasic:
    """daily_basic 表 — PE/PB/市值"""

    def test_upsert_and_query(self, db):
        rows = [{
            'ts_code': '600519.SH', 'trade_date': '20260601',
            'close': 1510.0, 'turnover_rate': 0.35, 'turnover_rate_f': 0.30,
            'volume_ratio': 1.2, 'pe': 30.5, 'pe_ttm': 28.3, 'pb': 8.1,
            'ps': 10.2, 'pcf': 15.0, 'total_mv': 19000.0, 'circ_mv': 19000.0,
            'total_share': 12.56, 'float_share': 12.56, 'free_share': 12.56,
        }]
        db.upsert_many_from_dicts('daily_basic', rows)

        result = db.query_daily_basic('600519.SH', '20260601')
        assert result is not None
        assert result['pe_ttm'] == 28.3
        assert result['total_mv'] == 19000.0
        assert result['turnover_rate'] == 0.35

    def test_no_data_returns_none(self, db):
        result = db.query_daily_basic('000001.SZ', '20200101')
        assert result is None


class TestThsIndex:
    """ths_index 表 — 板块列表"""

    def test_upsert(self, db):
        rows = [
            {'ts_code': '881121.TI', 'name': '半导体', 'count': 86, 'list_date': '20100101', 'type': 'I'},
            {'ts_code': '884112.TI', 'name': '人工智能', 'count': 52, 'list_date': '20200101', 'type': 'N'},
        ]
        db.upsert_many_from_dicts('ths_index', rows)

        assert db.query_ths_code_by_name('半导体') == '881121.TI'
        assert db.query_ths_name_by_code('884112.TI') == '人工智能'
        assert db.query_ths_code_by_name('不存在的') is None

    def test_get_all_ths_codes(self, db):
        rows = [
            {'ts_code': '881121.TI', 'name': '半导体', 'count': 86, 'list_date': '', 'type': 'I'},
            {'ts_code': '884112.TI', 'name': '人工智能', 'count': 52, 'list_date': '', 'type': 'N'},
        ]
        db.upsert_many_from_dicts('ths_index', rows)

        all_codes = db.get_all_ths_codes()
        assert len(all_codes) == 2
        assert ('881121.TI', '半导体', 'I') in all_codes


class TestSectorKlines:
    """通过 ths_index + ths_daily 查询板块K线"""

    def test_get_sector_klines(self, db):
        # 先插入板块
        db.upsert_many_from_dicts('ths_index', [
            {'ts_code': '881121.TI', 'name': '半导体', 'count': 86, 'list_date': '', 'type': 'I'},
        ])
        # 再插入K线
        rows = [
            {'ts_code': '881121.TI', 'trade_date': '20260601', 'open': 5000.0, 'close': 5100.0,
             'high': 5150.0, 'low': 4980.0, 'pre_close': 5000.0, 'change': 100.0,
             'pct_chg': 2.0, 'vol': 1e8, 'amount': 5e10},
            {'ts_code': '881121.TI', 'trade_date': '20260602', 'open': 5100.0, 'close': 5050.0,
             'high': 5120.0, 'low': 5030.0, 'pre_close': 5100.0, 'change': -50.0,
             'pct_chg': -0.98, 'vol': 0.8e8, 'amount': 4e10},
        ]
        db.upsert_many_from_dicts('ths_daily', rows)

        klines = db.get_sector_klines('半导体', 'industry', limit=5)
        assert len(klines) == 2
        assert klines[0]['date'] == '20260602'
        assert klines[0]['close'] == 5050.0
        assert klines[-1]['close'] == 5100.0

    def test_get_sector_klines_unknown(self, db):
        klines = db.get_sector_klines('不存在的板块', 'industry', limit=5)
        assert klines == []


class TestIndexDaily:
    """index_daily 表 — 指数K线"""

    def test_upsert_and_query(self, db):
        rows = [
            {'ts_code': '000001.SH', 'trade_date': '20260601', 'open': 3200.0, 'close': 3210.0,
             'high': 3220.0, 'low': 3190.0, 'pre_close': 3200.0, 'change': 10.0,
             'pct_chg': 0.31, 'vol': 3e9, 'amount': 3.5e10},
        ]
        db.upsert_many_from_dicts('index_daily', rows)

        klines = db.get_index_klines('000001.SH', limit=5)
        assert len(klines) == 1
        assert klines[0]['date'] == '20260601'
        assert klines[0]['close'] == 3210.0

    def test_index_klines_empty(self, db):
        assert db.get_index_klines('000001.SH') == []


class TestGetLastTradeDate:
    """获取表的最大交易日期"""

    def test_get_last_trade_date(self, db):
        rows = [
            {'ts_code': '600519.SH', 'trade_date': '20260601', 'open': 1, 'high': 2,
             'low': 1, 'close': 2, 'pre_close': 1, 'change': 1, 'pct_chg': 1,
             'vol': 1, 'amount': 1},
            {'ts_code': '600519.SH', 'trade_date': '20260603', 'open': 1, 'high': 2,
             'low': 1, 'close': 2, 'pre_close': 1, 'change': 1, 'pct_chg': 1,
             'vol': 1, 'amount': 1},
        ]
        db.upsert_many_from_dicts('stock_daily', rows)

        assert db.get_last_trade_date('stock_daily') == '20260603'

    def test_last_trade_date_empty_table(self, db):
        assert db.get_last_trade_date('stock_daily') is None


class TestUpsertMany:
    """批量写入边缘情况"""

    def test_upsert_many_empty_dataframe(self, db):
        """空DataFrame不应报错"""
        class EmptyDf:
            def to_dict(self, orient='records'):
                return []
        db.upsert_many('stock_daily', EmptyDf())

    def test_upsert_many_empty_dict_list(self, db):
        """空列表不应报错"""
        db.upsert_many_from_dicts('stock_daily', [])

    def test_upsert_many_invalid_table(self, db):
        """不存在的表应报错"""
        with pytest.raises(Exception):
            db.upsert_many_from_dicts('nonexistent_table', [{'a': 1}])

    def test_upsert_many_float_values(self, db):
        """浮点数应保留精度"""
        rows = [{
            'ts_code': '600519.SH', 'trade_date': '20260601',
            'open': 1500.55, 'high': 1520.88, 'low': 1498.12, 'close': 1510.33,
            'pre_close': 1500.55, 'change': 9.78, 'pct_chg': 0.65,
            'vol': 1000000.0, 'amount': 1510330000.0,
        }]
        db.upsert_many_from_dicts('stock_daily', rows)
        row = db.query_one('stock_daily', ts_code='600519.SH', trade_date='20260601')
        assert row['open'] == 1500.55
        assert row['close'] == 1510.33
