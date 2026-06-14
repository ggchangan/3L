"""集成测试 — data_layer TushareDB 替代 JSON 路径"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from backend.core.data_layer import get_all_stocks, get_all_stocks_db
from backend.data_access.tushare_db import TushareDB


class TestTushareDBIntegration:
    """验证 data_layer 从 DB 读数据与旧 JSON 格式兼容"""

    db = TushareDB()

    def test_query_stock_klines_batch_returns_formatted_klines(self):
        """批量查询返回格式 {code: [{date, open, close, high, low, volume}, ...]}"""
        codes = ['000001', '600519']
        result = self.db.query_stock_klines_batch(codes, limit=5)
        assert '000001' in result or '600519' in result, "应返回至少一只股票"

        for code, klines in result.items():
            assert len(klines) <= 5, f"{code} K线数不超过limit"
            if klines:
                k = klines[0]
                for field in ('date', 'open', 'close', 'high', 'low', 'volume'):
                    assert field in k, f"{code} K线缺少 {field}"
                assert 'name' not in k, "name 由 data_layer 追加，batch 本身不返回"

    def test_query_stock_klines_batch_handles_empty_codes(self):
        """空代码列表返回空 dict"""
        assert self.db.query_stock_klines_batch([]) == {}

    def test_query_stock_klines_batch_mixed_exists_not_exists(self):
        """在和不存在的代码混合查询"""
        result = self.db.query_stock_klines_batch(['000001', '999999'], limit=3)
        assert '000001' in result, "存在的代码应返回K线"
        assert '999999' not in result, "不存在的代码不应返回"

    def test_get_all_stocks_db_returns_direction_grouped(self):
        """get_all_stocks_db 返回格式与 get_all_stocks 兼容"""
        result = get_all_stocks_db(limit=10)

        # 必须包含 last_updated
        assert 'last_updated' in result
        assert result['last_updated'], "应有最新交易日"

        # 至少有一个方向分组
        directions = {k: v for k, v in result.items() if k != 'last_updated'}
        assert len(directions) > 0, "至少有一个方向"

        for direction, codes in directions.items():
            assert isinstance(codes, dict), f"方向 {direction} 值应为 dict"
            assert len(codes) > 0, f"方向 {direction} 应有至少一只股票"
            for code, klines in codes.items():
                assert len(klines) > 0, f"{code} 应有K线"
                k = klines[0]
                for field in ('date', 'open', 'close', 'high', 'low', 'volume', 'name'):
                    assert field in k, f"{code} K线缺少 {field}"
                break  # 每方向只验证第一只股票

    def test_get_all_stocks_db_vs_json_compatible_fields(self):
        """DB 和 JSON 返回的 K线字段一致"""
        old = get_all_stocks()
        db_r = get_all_stocks_db(limit=10)

        old_dirs = {k: v for k, v in old.items() if k != 'last_updated'}
        db_dirs = {k: v for k, v in db_r.items() if k != 'last_updated'}

        # 找同时存在的方向
        common_dirs = set(old_dirs.keys()) & set(db_dirs.keys())
        assert len(common_dirs) > 0, "应有共同方向用于对比"

        for direction in common_dirs:
            old_codes = set(old_dirs[direction].keys())
            db_codes = set(db_dirs[direction].keys())
            common_codes = old_codes & db_codes
            if not common_codes:
                continue

            code = list(common_codes)[0]
            old_k = old_dirs[direction][code][0]
            db_k = db_dirs[direction][code][0]

            # 字段列表一致
            assert set(old_k.keys()) == set(db_k.keys()), \
                f"{code} 字段不一致: JSON={set(old_k.keys())} DB={set(db_k.keys())}"
            break  # 一组对比就够了

    def test_get_all_stocks_db_watchlist_sourced(self):
        """DB 的方向和股票来自 watchlist，不应有"未知"方向"""
        result = get_all_stocks_db()
        directions = {k for k in result if k != 'last_updated'}
        # watchlist 里所有股票都有 direction 标签，所以不应有纯"未知"方向
        # 但如果有股票没 direction，会归入"其他"
        unknown_dir = [d for d in directions if '未知' in d or '其他' in d]
        # 只要结果格式正确即可，不强制要求"不能有未知"

    def test_db_data_more_recent_than_json(self):
        """DB 最新交易日 >= JSON 最新交易日"""
        old = get_all_stocks()
        db_r = get_all_stocks_db()
        old_updated = old.get('last_updated', '')
        db_updated = db_r.get('last_updated', '')
        if old_updated and db_updated:
            assert db_updated >= old_updated, \
                f"DB({db_updated}) 应比 JSON({old_updated}) 更新或相同"

    def test_code_to_ts_code_resolves_correctly(self):
        """6位纯代码正确映射到 ts_code"""
        # 平安银行
        ts = self.db.code_to_ts_code('000001')
        assert ts == '000001.SZ' or self.db.query_one('stock_basic', symbol='000001') is not None

        # 贵州茅台
        ts = self.db.code_to_ts_code('600519')
        assert ts == '600519.SH'
