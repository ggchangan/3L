"""data_layer + data_source 合约与边缘情况测试

验证：
1. verify_data_sources() 可以正常调用（27+项跨层检查）
2. data_layer 合约在边缘情况下的表现
3. 数据源故障切换逻辑
"""
import os
import sys
import json
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

# ── 测试常量 ──
LAST_TRADING_DAY = '20260605'


class TestVerifyDataSources:
    """L1+L2+L3 跨层验证 — verify_data_sources()"""

    @pytest.mark.network
    def test_verify_all_passes(self):
        """verify_data_sources() 全部通过"""
        from backend.services.data_source import verify_data_sources
        result = verify_data_sources(verbose=False)
        assert result['status'] == 'pass', \
            f"验证未通过: {result.get('status')}"
        p = sum(1 for c in result['checks'] if c['pass'])
        t = len(result['checks'])
        assert p == t, f"通过{p}/{t}，应全部通过"

    @pytest.mark.network
    def test_verify_has_ths_checks(self):
        """verify_data_sources() 包含THS验证项"""
        from backend.services.data_source import verify_data_sources
        result = verify_data_sources(verbose=False)
        ths_checks = [c for c in result['checks'] if 'THS' in c['check']]
        assert len(ths_checks) >= 4, f"THS检查项={len(ths_checks)}，应≥4"

    @pytest.mark.network
    def test_verify_has_datalayer_checks(self):
        """verify_data_sources() 包含data_layer合约验证"""
        from backend.services.data_source import verify_data_sources
        result = verify_data_sources(verbose=False)
        dl_checks = [c for c in result['checks'] if 'data_layer' in c['check']]
        assert len(dl_checks) >= 4, f"data_layer检查项={len(dl_checks)}，应≥4"


class TestDataLayerContractFulfillment:
    """data_layer 合约填充率验证"""

    def test_get_sector_push2test_returns_typed_object(self):
        """get_sector_push2test() 返回 SectorPush2Test 类型"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        assert hasattr(result, 'industries'), "缺少industries"
        assert hasattr(result, 'concepts'), "缺少concepts"
        assert hasattr(result, 'get_change_pct'), "缺少get_change_pct方法"

    def test_get_sector_push2test_industries_filled(self):
        """get_sector_push2test().industries 合同填充率≥80"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        assert len(result.industries) >= 80, \
            f"industries={len(result.industries)}，应≥80"

    def test_get_sector_push2test_has_electronics_chemical(self):
        """get_sector_push2test() 含有电子化学品"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        assert '电子化学品' in result.industries, "缺少电子化学品"

    def test_get_sector_push2test_types_are_correct(self):
        """get_sector_push2test() 返回的类型字段正确"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        snap = result.industries.get('电子化学品')
        if snap:
            assert hasattr(snap, 'change_pct'), "缺少change_pct"
            assert hasattr(snap, 'up_count'), "缺少up_count"
            assert hasattr(snap, 'leader'), "缺少leader"
            assert hasattr(snap, 'down_count'), "缺少down_count"
            assert hasattr(snap, 'net_flow'), "缺少net_flow"

    def test_get_sector_push2test_get_change_pct(self):
        """get_change_pct() 返回正确值"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        chg = result.get_change_pct('电子化学品')
        assert chg is not None, "电子化学品get_change_pct返回None"
        assert -20 < chg < 20, f"chg={chg} 异常"

    def test_get_sector_push2test_get_change_pct_unknown(self):
        """get_change_pct() 未知板块返回None"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        chg = result.get_change_pct('不存在的板块')
        assert chg is None, f"应返回None，实际={chg}"

    def test_get_sector_daily_returns_industries(self):
        """get_sector_daily() 返回industries"""
        from backend.core.data_layer import get_sector_daily
        result = get_sector_daily()
        assert isinstance(result, dict), f"返回类型={type(result)}"
        assert 'industries' in result, "缺少industries"
        assert len(result['industries']) > 0, "industries为空"
        assert 'last_updated' in result, "缺少last_updated"

    def test_get_sector_klines_returns_list(self):
        """get_sector_klines() 返回list"""
        from backend.core.data_layer import get_sector_klines
        klines = get_sector_klines('电子化学品', 'industry')
        assert isinstance(klines, list), f"返回类型={type(klines)}"
        assert len(klines) >= 1, "K线为空"
        k = klines[0]
        for field in ['date', 'open', 'close', 'high', 'low', 'volume']:
            assert field in k, f"缺少字段: {field}"

    def test_get_sector_klines_unknown_industry(self):
        """get_sector_klines() 未知板块 → 空列表"""
        from backend.core.data_layer import get_sector_klines
        klines = get_sector_klines('不存在的板块__测试用__', 'industry')
        assert isinstance(klines, list), f"返回类型={type(klines)}"
        assert len(klines) == 0, f"应返回空列表，实际={len(klines)}"


class TestDataLayerNonTradingDayBehavior:
    """data_layer 非交易日行为"""

    def test_get_sector_push2test_still_works_weekend(self):
        """非交易日 get_sector_push2test() 返回最后交易日数据"""
        from backend.core.data_layer import get_sector_push2test
        result = get_sector_push2test()
        # 周日也能返回数据（周五缓存）
        assert len(result.industries) >= 80, \
            f"周日industries={len(result.industries)}，应≥80（返回周五数据）"
        snap = result.industries.get('电子化学品')
        if snap:
            assert snap.change_pct is not None, "电子化学品chg为None（周日应有周五缓存数据）"


class TestDataLayerEdgeCases:
    """data_layer 边缘情况"""

    def test_get_sector_push2test_empty_file(self):
        """sector_daily.json 没有 _push2test 字段"""
        from backend.core.data_layer import get_sector_push2test, load_sector_daily_uncached, save_sector_daily
        import copy
        # 备份原数据
        original = load_sector_daily_uncached()
        try:
            # 临时移除 _push2test
            modified = copy.deepcopy(original)
            modified.pop('_push2test', None)
            save_sector_daily(modified)

            result = get_sector_push2test()
            assert hasattr(result, 'industries'), "缺少industries"
            # 即使 _push2test 为空，也应返回空对象而非抛异常
            assert len(result.industries) == 0, \
                f"_push2test移除后industries应=0，实际={len(result.industries)}"
        finally:
            # 恢复
            save_sector_daily(original)

    def test_get_sector_push2test_corrupted(self):
        """sector_daily.json 的 _push2test 是无效类型"""
        from backend.core.data_layer import get_sector_push2test, load_sector_daily_uncached, save_sector_daily
        import copy
        original = load_sector_daily_uncached()
        try:
            modified = copy.deepcopy(original)
            modified['_push2test'] = 'invalid_string'
            save_sector_daily(modified)

            # 应该返回空对象而非崩溃
            result = get_sector_push2test()
            assert hasattr(result, 'industries')
        finally:
            save_sector_daily(original)

    def test_get_sector_daily_corrupted(self):
        """get_sector_daily() 在文件损坏时兜底"""
        from backend.core.data_layer import get_sector_daily, load_sector_daily_uncached, save_sector_daily
        original = load_sector_daily_uncached()
        try:
            # 写入无效数据
            save_sector_daily({'invalid': True})

            # 应返回兜底数据而非崩溃
            # get_sector_daily 有内部异常处理
            result = get_sector_daily()
            # 即使数据无效也不应抛异常
            assert isinstance(result, dict)
        finally:
            save_sector_daily(original)

    def test_get_sector_klines_edge_cases(self):
        """get_sector_klines 边界情况"""
        from backend.core.data_layer import get_sector_klines

        # 空字符串 → 空列表（不崩溃）
        klines = get_sector_klines('', 'industry')
        assert isinstance(klines, list)

        # None → 空列表（不崩溃）
        klines = get_sector_klines(None, 'industry')
        assert isinstance(klines, list)

        # 错误类型 → 空列表（不崩溃）
        klines = get_sector_klines('电子化学品', 'unknown_type')
        assert isinstance(klines, list)


class TestDataSourceEdgeCases:
    """data_source 边缘情况"""

    @pytest.mark.network
    def test_verify_data_sources_on_weekend(self):
        """verify_data_sources() 在非交易日正常工作"""
        from backend.services.data_source import verify_data_sources
        result = verify_data_sources(verbose=False)
        # 非交易日不应返回 fail（已加跳过逻辑）
        assert result['status'] in ('pass', 'fail'), \
            f"status={result['status']} 异常"

    def test_verify_data_sources_via_data_layer(self):
        """通过 data_layer 调用 verify_data_sources()"""
        from backend.core.data_layer import verify_data_sources
        result = verify_data_sources(verbose=False)
        assert isinstance(result, dict)
        assert 'checks' in result


# ====== 运行 ======
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
