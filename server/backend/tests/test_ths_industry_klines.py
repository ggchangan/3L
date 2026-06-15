"""测试 — ths_daily 行业板块K线 DB 查询"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from backend.data_access.tushare_db import is_db_available


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestThsIndustryKlines:

    def test_get_ths_industry_list_has_semiconductor(self):
        """ths_index 中应有 半导体 (I=行业)"""
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        rows = db.execute_raw(
            "SELECT ts_code, name, type FROM ths_index WHERE name='半导体' AND type='I'"
        )
        assert len(rows) >= 1, "应有 半导体 I类"
        # 记录 ts_code 供后续测试
        semiconductor = [r for r in rows if r['ts_code'] == '881121.TI']
        assert len(semiconductor) >= 1, "应有 881121.TI 的 半导体"

    def test_semiconductor_has_20plus_klines(self):
        """半导体 (881121.TI) 在 ths_daily 中应有至少 20 根K线"""
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        rows = db.execute_raw(
            "SELECT COUNT(*) as cnt FROM ths_daily WHERE ts_code=%s",
            ['881121.TI']
        )
        assert rows[0]['cnt'] >= 20, f"半导体应有 20+ K线，实际 {rows[0]['cnt']}"

    def test_semiconductor_recent_data(self):
        """半导体最新数据应接近当前日期"""
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        rows = db.execute_raw(
            "SELECT MAX(trade_date) as max_d FROM ths_daily WHERE ts_code=%s",
            ['881121.TI']
        )
        max_d = rows[0]['max_d']
        assert max_d >= '20260601', f"半导体数据应到 6月，实际 {max_d}"

    def test_get_ths_industry_klines_format(self):
        """查询行业K线应返回 {name: [{date, open, close, high, low, volume}, ...]} 格式"""
        from backend.data_access.data_layer import get_ths_industry_klines
        data = get_ths_industry_klines()
        assert isinstance(data, dict)
        assert '半导体' in data, "应包含 半导体"
        semiconductor = data['半导体']
        assert len(semiconductor) >= 20, f"半导体应有 20+ K线，实际 {len(semiconductor)}"
        # 验证K线格式
        k = semiconductor[0]
        for field in ('date', 'open', 'close', 'high', 'low', 'volume'):
            assert field in k, f"K线缺少 {field}"
        # 验证按日期升序
        dates = [k['date'] for k in semiconductor]
        assert dates == sorted(dates), "K线应按日期升序"

    def test_ths_industry_klines_concept_filter(self):
        """应按 type 过滤（I=行业，N=概念），结果不为空"""
        from backend.data_access.data_layer import get_ths_industry_klines
        data = get_ths_industry_klines(ths_type='I')
        assert len(data) > 100, f"应有100+行业，实际 {len(data)}"
        # 结果中的行业应有足够K线
        for name in list(data.keys())[:3]:
            assert len(data[name]) >= 20, f"{name} 应有 20+ K线"
