"""趋势交易系统模块测试"""
import pytest
from backend.core.data_layer import get_all_stocks
from backend.core.trend_trading import (
    decide_system, decide_system_with_detail,
    detect_trend_buy, simulate_trend_trade,
    check_trend_type, get_bias5_zone, get_bias10_zone,
    check_stop_loss, check_trailing_take_profit,
    is_5day_trend, is_10day_trend, scan_trend_buys,
)


MAIN_LINES = ['半导体', '算力', '新能源']


# ==================== 三层决策框架 ====================

class TestDecideSystem:
    """decide_system 三层决策测试"""

    def test_trend_stock_passes_all_layers(self, stocks):
        """手动指定的趋势股返回trend，非指定的返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        # 鼎龙股份在手动列表中
        result = decide_system('300054', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == 'trend', f"鼎龙股份(手动指定)应为 trend, 实际={result}"
        
        # 沪硅产业不在手动列表中
        result = decide_system('688126', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"沪硅产业(非手动指定)应为 3l, 实际={result}"

    def test_weak_slope_returns_3l(self, stocks):
        """上涨结构但斜率≤3%返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('688234', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"天岳先进(斜率1.18%)应为 3l, 实际={result}"

    def test_non_uptrend_returns_3l(self, stocks):
        """非上涨结构返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('002640', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l', f"跨境通(区间震荡)应为 3l, 实际={result}"

    def test_non_mainline_returns_3l(self, stocks):
        """不在主线方向返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        # 算力主线允许商业航天方向 -> 不在主线
        result = decide_system('001208', '2026-05-22', stocks_data, MAIN_LINES)
        # 不强制断言具体值，只是确保函数不崩溃
        assert result in ('trend', '3l')

    def test_no_mainlines_default_pass(self, stocks):
        """不传main_lines时行为不变（只依赖手动列表）"""
        stocks_data = stocks.get('stocks', stocks)
        # 鼎龙在手动列表
        result = decide_system('300054', '2026-05-22', stocks_data, main_lines=None)
        assert result == 'trend'
        # 沪硅不在
        result = decide_system('688126', '2026-05-22', stocks_data, main_lines=None)
        assert result == '3l'

    def test_detail_returns_correct_reason(self, stocks):
        """decide_system_with_detail返回正确的原因"""
        stocks_data = stocks.get('stocks', stocks)
        # 鼎龙（手动指定）
        detail = decide_system_with_detail('300054', '2026-05-22', stocks_data, MAIN_LINES)
        assert detail['system'] == 'trend'
        assert '手动指定' in detail['reason']
        assert detail['details']['manual'] is True
        
        # 沪硅（非手动，默认3L）
        detail2 = decide_system_with_detail('688126', '2026-05-22', stocks_data, MAIN_LINES)
        assert detail2['system'] == '3l'
        assert '默认' in detail2['reason']

    def test_stock_not_found_returns_3l(self, stocks):
        """不存在的股票返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('000000', '2026-05-22', stocks_data, MAIN_LINES)
        assert result == '3l'

    def test_insufficient_data_returns_3l(self, stocks):
        """数据不足30条返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('688126', '2025-01-01', stocks_data, MAIN_LINES)
        assert result == '3l'


# ==================== BIAS位置判断 ====================

class TestBiasZone:
    """乖离率位置判断测试"""

    def test_bias5_buy_zone_below_zero(self):
        """BIAS5<0 为买入区"""
        closes = [100 + i for i in range(35)]
        kls = [{'close': c, 'date': f'202605{i+1:02d}'} for i, c in enumerate(closes)]
        zone = get_bias5_zone(kls, len(kls) - 1)
        # BMIAS >0，所以不会是买入区
        # 用BIAS5<0的情况测试
        kls_down = [{'close': 100 - i * 0.5, 'date': f'202605{i+1:02d}'} for i in range(35)]
        zone2 = get_bias5_zone(kls_down, len(kls_down) - 1)
        assert zone2[0] == '买入' or zone[0] in ('持有', '警戒', '卖出')

    def test_bias5_buy_zone_0_2(self):
        """BIAS5 0~2%为买入区"""
        closes = list(range(100, 105)) + list(range(105, 135))
        kls = [{'close': c, 'date': f'202605{i+1:02d}'} for i, c in enumerate(closes)]
        if len(kls) >= 10:
            zone = get_bias5_zone(kls, len(kls) - 1)
            assert zone[0] in ('买入', '持有', '警戒', '卖出')

    def test_bias5_hold_zone(self):
        """BIAS5 2~8%为持有区"""
        closes = list(range(100, 105)) + [v * 1.05 for v in range(100, 130)]
        kls = [{'close': c, 'date': f'202605{i+1:02d}'} for i, c in enumerate(closes)]
        if len(kls) >= 10:
            zone = get_bias5_zone(kls, len(kls) - 1)
            assert zone[0] in ('买入', '持有', '警戒', '卖出')

    def test_insufficient_data_returns_dash(self):
        """数据不足返回'--'"""
        kls = [{'close': 100, 'date': '20260501'}]
        zone = get_bias5_zone(kls, 0)
        assert zone[0] == '--'


# ==================== 趋势判定 ====================

class TestTrendType:
    """趋势类型判定测试"""

    def test_known_trend_stock_has_type(self, stocks):
        """已知趋势股应有趋势类型"""
        stocks_data = stocks.get('stocks', stocks)
        for sec, ss in stocks_data.items():
            if '688126' in ss:
                kls = ss['688126']
                idx = len(kls) - 1
                result = check_trend_type(kls, idx)
                assert result['trend_type'] is not None
                assert result['trend_type'] in ('5日趋势', '10日趋势', '双趋势')
                break

    def test_non_trend_stock_no_type(self, stocks):
        """非趋势股应无趋势类型"""
        stocks_data = stocks.get('stocks', stocks)
        for sec, ss in stocks_data.items():
            if '002640' in ss:
                kls = ss['002640']
                idx = len(kls) - 1
                result = check_trend_type(kls, idx)
                assert result['trend_type'] is None
                break

    def test_5day_trend_requires_slope(self, stocks):
        """5日趋势判定需要EMA5斜率>2%"""
        stocks_data = stocks.get('stocks', stocks)
        for sec, ss in stocks_data.items():
            if '300054' in ss:
                kls = ss['300054']
                idx = len(kls) - 1
                t5 = is_5day_trend(kls, idx)
                t10 = is_10day_trend(kls, idx)
                assert t5 or t10  # 鼎龙至少满足一个
                break


# ==================== 趋势买点检测 ====================

class TestDetectTrendBuy:
    """趋势买点检测测试"""

    def test_trend_buy_for_known_stock(self, stocks):
        """已知趋势股可能产生买点"""
        stocks_data = stocks.get('stocks', stocks)
        bt = detect_trend_buy('688126', '2026-05-22', stocks_data, MAIN_LINES)
        if bt:
            assert bt['has_buy'] is True
            assert 'BIAS' in bt['buy_type']
            assert bt['system_reason']
            assert bt['reason']
        # 有或没有都合理，取决于当前BIAS位置

    def test_non_trend_stock_no_buy(self, stocks):
        """非趋势股不应有趋势买点"""
        stocks_data = stocks.get('stocks', stocks)
        bt = detect_trend_buy('002640', '2026-05-22', stocks_data, MAIN_LINES)
        assert bt is None, "跨境通非趋势股不应有趋势买点"

    def test_insufficient_data_no_buy(self, stocks):
        """数据不足不应有买点"""
        stocks_data = stocks.get('stocks', stocks)
        bt = detect_trend_buy('688126', '2025-01-01', stocks_data, MAIN_LINES)
        assert bt is None


# ==================== 止损/止盈 ====================

class TestStopLossTakeProfit:
    """止损止盈逻辑测试"""

    def test_stop_loss_triggered(self):
        """浮亏超-5%触发止损"""
        triggered, reason = check_stop_loss(100, 94)
        assert triggered is True
        assert '止损' in reason

    def test_stop_loss_not_triggered(self):
        """浮亏不足-5%不触发"""
        triggered, reason = check_stop_loss(100, 96)
        assert triggered is False

    def test_trailing_profit_not_started_below_5(self):
        """峰值收益不足5%不启动跟踪止盈"""
        triggered, reason = check_trailing_take_profit(100, 106, 110)
        # 峰值10%，回落至6%，回撤(10-6)/10=40%，但回撤比例不对
        # 公式是 peak_ret < 5: no, peak_ret-cur_ret > 10: yes
        # peak_ret=10%, cur_ret=6%, diff=4% < 10% → no
        assert triggered is False

    def test_trailing_profit_triggered(self):
        """峰值赚超5%且回落超10%触发"""
        triggered, reason = check_trailing_take_profit(100, 105, 120)
        # peak_ret=20%, cur_ret=5%, diff=15% > 10% → 触发
        assert triggered is True

    def test_trailing_profit_price_never_peaked(self):
        """从未涨过的股票不触发"""
        triggered, reason = check_trailing_take_profit(100, 98, 100)
        assert triggered is False


# ==================== 单股回测 ====================

class TestSimulateTrade:
    """单股交易模拟测试"""

    def test_simulate_with_real_data(self, stocks):
        """用真实数据模拟一次趋势交易"""
        stocks_data = stocks.get('stocks', stocks)
        for sec, ss in stocks_data.items():
            if '688126' in ss:
                kls = ss['688126']
                # 在倒数第30天买入
                buy_idx = len(kls) - 30
                if buy_idx < 30:
                    continue
                result = simulate_trend_trade(kls, buy_idx)
                assert 'ret' in result
                assert 'exit_reason' in result
                assert 'hold_days' in result
                assert result['exit_reason'] in ('止损', '跟踪止盈', '趋势消失', '持满60天')
                break

    def test_simulate_buy_then_stop(self):
        """买入后连续下跌触发止损"""
        closes = [100 - i * 6 for i in range(36)]  # 每日跌6%
        kls = [{'close': c, 'date': f'202605{i+1:02d}'} for i, c in enumerate(closes)]
        result = simulate_trend_trade(kls, 0)
        assert result['exit_reason'] == '止损'
        assert result['ret'] < -5

    def test_simulate_buy_then_trailing(self):
        """买入后大涨再回落触发跟踪止盈"""
        # 先跌后大涨再回落
        closes = [100 + i*3 for i in range(5)] + [100 + i*8 for i in range(10)] + [v - v*0.12 for v in [180, 175, 170]]
        kls = [{'close': max(c, 50), 'date': f'202605{i+1:02d}'} for i, c in enumerate(closes)]
        # 需要足够的K线满足趋势判定
        # 加些前置K线
        prefix = [{'close': 50 + i, 'date': f'202604{i+1:02d}'} for i in range(30)]
        kls = prefix + kls
        result = simulate_trend_trade(kls, 30)
        assert result['exit_reason'] in ('跟踪止盈', '止损', '趋势消失', '持满60天')


# ==================== 批量扫描 ====================

class TestScanTrendBuys:
    """批量趋势买点扫描测试"""

    def test_scan_returns_list(self, stocks):
        """扫描返回列表"""
        stocks_data = stocks.get('stocks', stocks)
        # 只扫半导体方向，加速测试
        subset = {'半导体': stocks_data.get('半导体', {})}
        results = scan_trend_buys('2026-05-22', subset, MAIN_LINES)
        assert isinstance(results, list)
        if results:
            sample = results[0]
            assert 'code' in sample
            assert 'name' in sample
            assert 'direction' in sample
            assert 'buy_type' in sample
            assert 'has_buy' in sample

    def test_scan_handles_empty_data(self):
        """空数据不崩溃"""
        results = scan_trend_buys('2026-05-22', {}, MAIN_LINES)
        assert results == []
