"""
沿EMA5平滑趋势检测测试（3L失效场景 → 趋势交易补充）

测试目标：
1. 平滑趋势检测函数 is_smooth_trend() 是否正确识别
2. decide_system_with_detail() 集成后是否正确返回 'trend'
3. 现有逻辑不被破坏
"""
import pytest
from scripts.trend_trading import (
    decide_system, decide_system_with_detail,
)

MAIN_LINES = ['半导体', '算力', '机器人', '新能源']


class TestIsSmoothTrend:
    """is_smooth_trend 函数单元测试"""

    def test_tuopu_is_smooth(self, stocks):
        """拓普集团(601689) 是平滑趋势"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('601689', '2026-05-22', stocks_data)
        assert result['is_smooth'] is True, \
            f"拓普集团应为平滑趋势, 实际={result}"
        assert result['details']['cycles'] == 0

    def test_weichuang_is_smooth(self, stocks):
        """伟创电气(688698) 是平滑趋势"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('688698', '2026-05-22', stocks_data)
        assert result['is_smooth'] is True, \
            f"伟创电气应为平滑趋势, 实际={result}"

    def test_dashu_not_smooth(self, stocks):
        """大族数控(301200) 不是平滑趋势（有峰谷循环）"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('301200', '2026-05-22', stocks_data)
        assert result['is_smooth'] is False, \
            f"大族数控不应为平滑趋势, 实际={result}"

    def test_guangxun_not_smooth(self, stocks):
        """光迅科技(002281) 不是平滑趋势（有峰谷循环）"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('002281', '2026-05-22', stocks_data)
        assert result['is_smooth'] is False, \
            f"光迅科技不应为平滑趋势, 实际={result}"

    def test_yaomingkangde_not_smooth(self, stocks):
        """药明康德(603259) 不是平滑趋势（非上涨趋势）"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('603259', '2026-05-22', stocks_data)
        assert result['is_smooth'] is False, \
            f"药明康德(区间震荡)不应为平滑趋势, 实际={result}"

    def test_stock_not_found_returns_false(self, stocks):
        """不存在的股票返回 False"""
        from scripts.trend_trading import is_smooth_trend
        stocks_data = stocks.get('stocks', stocks)
        result = is_smooth_trend('000000', '2026-05-22', stocks_data)
        assert result['is_smooth'] is False


class TestDecideSystemSmooth:
    """集成测试：平滑趋势股票在手动指定后的表现"""

    def test_weichuang_returns_trend(self, stocks):
        """伟创电气（在手动列表）应返回 trend"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('688698', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == 'trend', \
            f"伟创电气(手动指定)应为 trend, 实际={result}"

    def test_tuopu_returns_3l(self, stocks):
        """拓普集团（不在手动列表）应返回 3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('601689', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', \
            f"拓普集团(非指定)应为 3l, 实际={result}"

    def test_tuopu_detail_shows_default_reason(self, stocks):
        """拓普集团 detail 应显示默认3L"""
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('601689', '2026-05-22', stocks_data, MAIN_LINES)
        assert detail['system'] == '3l'
        assert '默认' in detail['reason'], \
            f"原因应显示默认3L, 实际={detail['reason']}"

    def test_weichuang_detail_shows_manual_reason(self, stocks):
        """伟创电气 detail 应显示手动指定"""
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('688698', '2026-05-22', stocks_data, MAIN_LINES)
        assert detail['system'] == 'trend'
        assert '手动指定' in detail['reason'], \
            f"原因应显示手动指定, 实际={detail['reason']}"

    def test_non_manual_stock_returns_3l(self, stocks):
        """不在手动列表中的票返回3L"""
        stocks_data = stocks.get('stocks', stocks)
        # 沪硅产业(688126) - 不在手动列表
        result = decide_system('688126', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"沪硅产业(非指定)应为 3l, 实际={result}"

    def test_interval_stock_still_3l(self, stocks):
        """区间震荡的票返回3L"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('002640', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"跨境通(区间震荡)应为 3l, 实际={result}"

    def test_weak_slope_returns_3l(self, stocks):
        """不在手动列表的票返回3L（无论斜率如何）"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('688234', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"天岳先进(非指定)应为 3l, 实际={result}"

    def test_no_mainlines_default_pass_manual(self, stocks):
        """不传main_lines时手动指定的票仍为trend"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('002281', '2026-05-22', stocks_data)
        assert result == 'trend', \
            f"不传主线时光迅(手动指定)应为 trend, 实际={result}"
        
        result = decide_system('601689', '2026-05-22', stocks_data)
        assert result == '3l', \
            f"不传主线时拓普(非指定)应为 3l, 实际={result}"
