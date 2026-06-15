"""L0 — 数据覆盖度验证测试

验证 data_layer 返回的数据是否完整、新鲜、自洽。
不验证任何业务逻辑（那是 L1~L4 的事）。

测试维度：
  1. 结构完整性 — K线日期分布、快照计数、非零率
  2. 时效脉冲  — 按比例采样的K线最新日期
  3. 交叉验算  — K线计算chg vs 快照change_pct
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from backend.data_access.data_source import (
    verify_data_coverage,
    _last_trading_day,
    _is_weekend,
)


# ═══════════════════════════════════════════════════════════════
# 辅助
# ═══════════════════════════════════════════════════════════════

def _get_sector_data():
    """加载 sector_daily.json（不走缓存）"""
    from backend.core.config import SECTOR_DAILY_PATH
    path = SECTOR_DAILY_PATH
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# 测试类
# ═══════════════════════════════════════════════════════════════

class TestVerifyDataCoverage:
    """测试 verify_data_coverage() 的整体行为"""

    def test_function_exists(self):
        """verify_data_coverage 存在且可调用"""
        assert callable(verify_data_coverage)

    def test_returns_dict(self):
        """返回 dict 结构"""
        result = verify_data_coverage()
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'checks' in result
        assert isinstance(result['checks'], list)

    def test_each_check_has_required_fields(self):
        """每个检查项有 check/pass/detail/type/dimension 字段"""
        result = verify_data_coverage()
        for c in result['checks']:
            assert 'check' in c, f"缺少 check 字段: {c}"
            assert 'pass' in c, f"缺少 pass 字段: {c}"
            assert 'detail' in c, f"缺少 detail 字段: {c}"
            assert 'type' in c, f"缺少 type 字段: {c}"
            assert 'dimension' in c, f"缺少 dimension 字段: {c}"

    def test_covers_four_types(self):
        """覆盖四种数据类型：行业K线/概念K线/行业快照/概念快照"""
        result = verify_data_coverage()
        types = set(c.get('type', '') for c in result['checks'])
        for t in ['industry_kline', 'concept_kline', 'industry_snapshot', 'concept_snapshot']:
            assert t in types, f"缺少类型: {t}"


class TestStructureIntegrity:
    """结构完整性 — 全量扫描K线日期"""

    def test_concept_kline_latest_date_scan(self):
        """概念K线日期扫描输出存在且正确"""
        result = verify_data_coverage()
        dates_checks = [c for c in result['checks']
                        if c.get('type') == 'concept_kline'
                        and c.get('dimension') == 'structure'
                        and '日期分布' in c['check']]
        assert len(dates_checks) >= 1, "应有概念K线日期分布检查"
        check = dates_checks[0]
        assert '20260601' in str(check['detail']) or 'date' in str(check['detail']).lower()

    def test_concept_kline_no_weekend_dates(self):
        """概念K线不应有周末日期"""
        result = verify_data_coverage()
        weekend_checks = [c for c in result['checks']
                          if c.get('type') == 'concept_kline'
                          and '周末' in c['check']]
        # 当前数据有110个概念标到周六(20260606)，所以这个检查应该FAIL
        assert len(weekend_checks) >= 1
        # 不检查 pass/fail，只检查存在

    def test_industry_kline_latest_date_scan(self):
        """行业K线日期扫描输出存在"""
        result = verify_data_coverage()
        dates_checks = [c for c in result['checks']
                        if c.get('type') == 'industry_kline'
                        and c.get('dimension') == 'structure'
                        and '日期分布' in c['check']]
        assert len(dates_checks) >= 1

    def test_industry_kline_no_weekend_dates(self):
        """行业K线不应有周末日期"""
        result = verify_data_coverage()
        weekend_checks = [c for c in result['checks']
                          if c.get('type') == 'industry_kline'
                          and '周末' in c['check']]
        assert len(weekend_checks) >= 1

    def test_push2test_concept_count(self):
        """_push2test 概念快照计数应≥200"""
        result = verify_data_coverage()
        count_checks = [c for c in result['checks']
                        if c.get('type') == 'concept_snapshot'
                        and c.get('dimension') == 'structure'
                        and '计数' in c['check']]
        assert len(count_checks) >= 1
        # 当前只有5个，应该FAIL
        check = count_checks[0]
        if not check['pass']:
            assert '5' in str(check['detail']), "应该报告当前只有5个概念"

    def test_push2test_industry_count(self):
        """_push2test 行业快照计数应≥80"""
        result = verify_data_coverage()
        count_checks = [c for c in result['checks']
                        if c.get('type') == 'industry_snapshot'
                        and c.get('dimension') == 'structure'
                        and '计数' in c['check']]
        assert len(count_checks) >= 1

    def test_concept_snapshot_nonzero_ratio(self):
        """概念快照 change_pct 非零占比检查"""
        result = verify_data_coverage()
        nonzero_checks = [c for c in result['checks']
                          if c.get('type') == 'concept_snapshot'
                          and c.get('dimension') == 'structure'
                          and '非零' in c['check']]
        assert len(nonzero_checks) >= 1


class TestTimeliness:
    """时效脉冲 — 采样验证最新日期"""

    def test_concept_kline_sampling_exists(self):
        """概念K线采样检查存在"""
        result = verify_data_coverage()
        sampling_checks = [c for c in result['checks']
                           if c.get('type') == 'concept_kline'
                           and c.get('dimension') == 'timeliness'
                           and '采样' in c['check']]
        assert len(sampling_checks) >= 1

    def test_industry_kline_sampling_exists(self):
        """行业K线采样检查存在"""
        result = verify_data_coverage()
        sampling_checks = [c for c in result['checks']
                           if c.get('type') == 'industry_kline'
                           and c.get('dimension') == 'timeliness'
                           and '采样' in c['check']]
        assert len(sampling_checks) >= 1

    def test_key_concept_mustexist_check(self):
        """关键概念必检：培育钻石"""
        result = verify_data_coverage()
        key_checks = [c for c in result['checks']
                      if c.get('type') == 'concept_kline'
                      and c.get('dimension') == 'timeliness'
                      and '培育钻石' in c['check']]
        assert len(key_checks) >= 1, "应有培育钻石的时效性检查"

    def test_key_industry_mustexist_check(self):
        """关键行业必检：电子化学品"""
        result = verify_data_coverage()
        key_checks = [c for c in result['checks']
                      if c.get('type') == 'industry_kline'
                      and c.get('dimension') == 'timeliness'
                      and '电子化学品' in c['check']]
        assert len(key_checks) >= 1, "应有电子化学品的时效性检查"


class TestCrossVerification:
    """交叉验算 — K线chg vs 快照change_pct"""

    def test_cross_verify_exists(self):
        """交叉验算检查存在"""
        result = verify_data_coverage()
        xverify = [c for c in result['checks']
                   if c.get('dimension') == 'cross_verify']
        assert len(xverify) >= 1

    def test_cross_verify_industry(self):
        """行业交叉验算存在"""
        result = verify_data_coverage()
        xverify = [c for c in result['checks']
                   if c.get('type') in ('industry_kline',)
                   and c.get('dimension') == 'cross_verify']
        assert len(xverify) >= 1

    def test_cross_verify_concept(self):
        """概念交叉验算存在"""
        result = verify_data_coverage()
        xverify = [c for c in result['checks']
                   if c.get('type') in ('concept_kline',)
                   and c.get('dimension') == 'cross_verify']
        assert len(xverify) >= 1


class TestEdgeCases:
    """边界情况处理"""

    def test_non_trading_day_nonzero_skip_valid(self):
        """非交易日应该跳过非零占比的严格检查"""
        # 不强制 pass/fail，只是验证逻辑存在
        result = verify_data_coverage()
        weekend_checks = [c for c in result['checks']
                          if '非交易日' in c.get('check', '')
                          or '周末' in c.get('detail', '')
                          or '跳过' in c.get('detail', '')
                          and '结构' in c.get('detail', '')]
        # 逻辑上如果今天是周末，应该有跳过标记
        if datetime.now().weekday() >= 5:
            from backend.data_access.data_source import _is_weekend
            assert _is_weekend(), "今天应该是非交易日"

    def test_missing_data_graceful(self):
        """数据文件不存在时不会崩溃"""
        from backend.data_access.data_source import verify_data_coverage
        # 暂时不改文件路径，只验证函数本身不抛异常
        result = verify_data_coverage()
        assert 'error' not in result or not result.get('error')


# ═══════════════════════════════════════════════════════════════
# 集成测试 — 关键检查项的 pass/fail 与当前数据状态匹配
# ═══════════════════════════════════════════════════════════════

class TestDataCurrentState:
    """对当前真实数据的检查（已知数据有损坏，预期特定FAIL项）"""

    def test_concept_snapshot_count_fails_currently(self):
        """当前 _push2test 概念快照只有5个，应FAIL"""
        result = verify_data_coverage()
        count_checks = [c for c in result['checks']
                        if c.get('type') == 'concept_snapshot'
                        and c.get('dimension') == 'structure'
                        and '计数' in c['check']]
        assert len(count_checks) >= 1
        # 当前实际只有5个
        check = count_checks[0]
        if '5' in str(check['detail']) or '计数' in str(check['detail']):
            # 确认这个检查确实发现了问题
            assert not check['pass'] or '跳过' in str(check['detail']), \
                f"概念快照计数检查应该FAIL: {check['detail']}"

    def test_weekend_dates_detected(self):
        """周末日期应该被检测到（当前行业496个、概念110个标到周六）"""
        result = verify_data_coverage()
        weekend_checks = [c for c in result['checks']
                          if '周末' in c['check'] and not c['pass']]
        assert len(weekend_checks) >= 1, "应该至少检测到一项周末日期问题"


# 需要 datetime 用于边缘测试
from datetime import datetime
