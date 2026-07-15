"""测试 — data_layer 持仓 DB 读写接口"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from backend.data_access.tushare_db import is_db_available
from backend.data_access.data_layer import get_holdings, save_holdings


# 测试用的持仓数据
_TEST_HOLDINGS = [
    {'code': '300620', 'name': '光库科技', 'direction': '算力硬件.CPO', 'target_ratio': 6.86, 'cost_price': 343.05, 'stop_loss_price': 288.21, 'sector': '通信设备'},
    {'code': '600176', 'name': '中国巨石', 'direction': '算力硬件.PCB', 'target_ratio': 8.24, 'cost_price': 45.77, 'stop_loss_price': 38.49, 'sector': '玻璃玻纤'},
    {'code': '688008', 'name': '澜起科技', 'direction': '算力硬件.存储', 'target_ratio': 4.8, 'cost_price': 240.1, 'stop_loss_price': 206.61, 'sector': '半导体'},
]


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestDataLayerHoldings:

    def test_get_holdings_returns_list(self):
        """get_holdings 返回持仓列表"""
        holdings = get_holdings(user_id=1)
        assert isinstance(holdings, list)
        # 默认用户应已有持仓或空列表
        for h in holdings:
            assert 'code' in h
            assert 'name' in h
            assert 'direction' in h
            assert 'target_ratio' in h

    def test_save_and_get_holdings(self):
        """保存后能正确读取"""
        # 先保存测试数据
        save_holdings(1, _TEST_HOLDINGS)

        # 读取验证
        result = get_holdings(1)
        # 结果应包含测试数据
        codes = {h['code'] for h in result}
        for h in _TEST_HOLDINGS:
            assert h['code'] in codes, f"{h['code']} 应在持仓列表中"

        # 验证字段值
        for h in result:
            if h['code'] == '300620':
                assert h['name'] == '光库科技'
                assert h['direction'] == '算力硬件.CPO'
                assert h['target_ratio'] == 6.86

    def test_save_replaces_old_data(self):
        """重新保存应替换旧数据（先删后插）"""
        # 先保存一批
        save_holdings(1, _TEST_HOLDINGS[:2])

        # 再保存另一批（不同股票）
        new_data = [{'code': '301526', 'name': '国际复材', 'direction': '算力硬件.PCB', 'target_ratio': 4.44, 'cost_price': 34.13, 'sector': '玻璃玻纤'}]
        save_holdings(1, new_data)

        result = get_holdings(1)
        codes = {h['code'] for h in result}
        assert '301526' in codes, "新股票应在"
        assert '300620' not in codes, "旧股票应被替换"
        assert '600176' not in codes, "旧股票应被替换"

    def test_get_holdings_unknown_user_returns_empty(self):
        """不存在的用户返回空列表"""
        result = get_holdings(user_id=9999)
        assert result == []

    def test_holdings_format_matches_json_format(self):
        """返回格式与旧 JSON 的 holdings 列表兼容（无 id 字段）"""
        save_holdings(1, _TEST_HOLDINGS[:1])
        result = get_holdings(1)
        for h in result:
            # 不应有内部 DB 字段
            assert 'id' not in h
            assert 'user_id' not in h
            assert 'is_active' not in h
            # 应有应用层字段
            assert 'code' in h
            assert 'name' in h
            assert 'direction' in h
            assert 'target_ratio' in h

    def test_save_handles_empty_list(self):
        """保存空列表 = 清空持仓"""
        save_holdings(1, [])
        result = get_holdings(1)
        assert result == []

    def test_get_holdings_with_default_user(self):
        """默认用户（user_id=1）能正常查询"""
        holdings = get_holdings()
        assert isinstance(holdings, list)
        # 恢复测试数据
        save_holdings(1, _TEST_HOLDINGS)
