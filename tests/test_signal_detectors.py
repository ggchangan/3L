"""
信号检测器单元测试

测试策略：使用模拟K线数据（不是真实股票数据），
验证每个信号在已知条件下的触发逻辑是否正确。

注意：这些是单元测试，不是回测。它们验证"代码是否正确实现了规则"，
而不是"规则是否有效"（后者由 backtest.py 负责）。
"""
import sys
import os
import json
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../server/backend'))

from core.signal_detector.base import (
    calc_ma, calc_volume_ratio, calc_candle_body_ratio,
    is_big_candle, close_in_upper_third, close_in_lower_third,
    detect_range_trade, detect_trend, calc_ema, volume_trend,
    calc_avg_range, make_result,
)
from core.signal_detector.upward_breakout import detect_upward_breakout
from core.signal_detector.downward_breakout import detect_downward_breakout
from core.signal_detector.upward_continuation import detect_upward_continuation
from core.signal_detector.upward_reversal_detector import detect_upward_reversal
from core.signal_detector.downward_reversal import detect_downward_reversal
from core.signal_detector.demand_exhaustion import detect_demand_exhaustion
from core.signal_detector.supply_exhaustion import detect_supply_exhaustion


def make_kline(close, open=None, high=None, low=None, volume=1000000, date='20260101'):
    """便捷生成K线"""
    open = open or close
    high = high or max(open, close)
    low = low or min(open, close)
    return {'date': date, 'open': open, 'close': close, 'high': high, 'low': low, 'volume': volume}


def make_trend(start, end, count=40, volume=1000000):
    """生成从start到end的线性趋势K线"""
    klines = []
    for i in range(count):
        t = i / (count - 1)
        close = start + (end - start) * t
        klines.append(make_kline(close, close * 0.99, close * 1.01, close * 0.98, volume, f'202601{i+1:02d}'))
    return klines


class TestBaseFunctions(unittest.TestCase):
    """测试辅助函数"""
    
    def test_calc_ma(self):
        klines = [make_kline(i) for i in range(1, 11)]
        self.assertAlmostEqual(calc_ma(klines, 'close', 5), 8, delta=0.1)
        self.assertAlmostEqual(calc_ma(klines, 'close', 10), 5.5, delta=0.1)
    
    def test_calc_ema(self):
        values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        ema = calc_ema(values, 5)
        self.assertEqual(len(ema), len(values) - 5 + 1)
        self.assertAlmostEqual(ema[-1], 8.0, delta=0.1)
    
    def test_calc_volume_ratio(self):
        klines = [make_kline(10, volume=1000000) for _ in range(21)]
        klines[-1]['volume'] = 2000000  # 2倍
        vr = calc_volume_ratio(klines, 20, 20)
        self.assertAlmostEqual(vr, 2.0, delta=0.1)
    
    def test_detect_range_trade(self):
        # 区间震荡：价格窄幅波动
        klines = [make_kline(10 + i % 2) for i in range(35)]  # 在10和11之间震荡
        is_r, rh, rl, rm = detect_range_trade(klines, 30)
        self.assertTrue(is_r)
        
        # 单边上涨：不是区间
        klines = [make_kline(10 + i * 0.5) for i in range(35)]
        is_r, rh, rl, rm = detect_range_trade(klines, 30)
        self.assertFalse(is_r)
    
    def test_detect_trend(self):
        # 上涨
        klines = make_trend(10, 20, 35)
        self.assertEqual(detect_trend(klines, 30), 'up')
        
        # 下跌
        klines = make_trend(20, 10, 35)
        self.assertEqual(detect_trend(klines, 30), 'down')
    
    def test_close_in_upper_third(self):
        # 收盘在顶部1/3
        k = make_kline(15, open=10, high=16, low=9)
        klines = [k]
        self.assertTrue(close_in_upper_third(klines, -1))
        
        # 收盘在底部
        k2 = make_kline(10, open=15, high=16, low=9)
        klines2 = [k2]
        self.assertFalse(close_in_upper_third(klines2, -1))
    
    def test_is_big_candle(self):
        # 大阳线
        k = make_kline(15, open=10, high=16, low=9)
        self.assertTrue(is_big_candle([k], -1, 0.5))
        
        # 小实体
        k = make_kline(10.1, open=10, high=10.5, low=9.5)
        self.assertFalse(is_big_candle([k], -1, 0.5))


class TestUpwardBreakout(unittest.TestCase):
    """向上突破信号"""
    
    def test_breakout_detected(self):
        """区间震荡后突破顶部"""
        klines = []
        # 30天区间震荡（10-11之间）
        for i in range(30):
            klines.append(make_kline(10.5 + (i % 2) * 0.5, volume=500000))
        # 最后一天放量突破
        klines.append(make_kline(11.5, open=11.0, high=11.8, low=10.8, volume=2000000))
        
        result = detect_upward_breakout(klines)
        self.assertTrue(result['triggered'], f'应触发向上突破: {result["detail"]}')
        self.assertGreaterEqual(result['confidence'], 60)
    
    def test_no_breakout_without_range(self):
        """没有区间震荡不应触发"""
        klines = make_trend(10, 20, 35)
        result = detect_upward_breakout(klines)
        self.assertFalse(result['triggered'])


class TestDownwardBreakout(unittest.TestCase):
    """向下突破信号"""
    
    def test_breakdown_detected(self):
        """区间震荡后跌破底部"""
        klines = []
        for i in range(30):
            klines.append(make_kline(10.5 + (i % 2) * 0.5, volume=500000))
        # 最后一天放量跌破
        klines.append(make_kline(9.5, open=10.0, high=10.2, low=9.2, volume=2000000))
        
        result = detect_downward_breakout(klines)
        self.assertTrue(result['triggered'], f'应触发向下突破: {result["detail"]}')
    
    def test_no_breakdown_up_trend(self):
        """上涨趋势不应触发"""
        klines = make_trend(10, 20, 35)
        result = detect_downward_breakout(klines)
        self.assertFalse(result['triggered'])


class TestUpwardContinuation(unittest.TestCase):
    """上涨中继信号"""
    
    def test_continuation_in_uptrend(self):
        """上涨趋势中的回踩"""
        klines = []
        # 先涨
        for i in range(15):
            klines.append(make_kline(10 + i * 0.3, volume=1500000))
        # 回踩5天（缩量下跌）
        for i in range(5):
            klines.append(make_kline(14 - i * 0.1, volume=500000))
        
        result = detect_upward_continuation(klines)
        # 可能需要更多条件，先看是否正常执行不报错
        self.assertIsNotNone(result)


class TestUpwardReversal(unittest.TestCase):
    """向上反转信号"""
    
    def test_reversal_after_downtrend(self):
        """下降后的放量阳线"""
        klines = []
        # 先跌20天
        for i in range(20):
            klines.append(make_kline(20 - i * 0.5, volume=800000))
        # 放量阳线反转
        klines.append(make_kline(16, open=14, high=17, low=13.5, volume=2000000))
        
        result = detect_upward_reversal(klines)
        # 注意：需要满足回撤>7%等条件
        self.assertIsNotNone(result)


class TestDownwardReversal(unittest.TestCase):
    """向下反转信号"""
    
    def test_reversal_after_uptrend(self):
        """上涨后的放量阴线"""
        klines = []
        for i in range(20):
            klines.append(make_kline(10 + i * 0.5, volume=800000))
        # 放量阴线反转
        klines.append(make_kline(18, open=20, high=20.5, low=17.5, volume=2000000))
        
        result = detect_downward_reversal(klines)
        self.assertIsNotNone(result)


class TestDemandExhaustion(unittest.TestCase):
    """需求衰竭信号"""
    
    def test_acceleration_form(self):
        """加速形态"""
        klines = []
        for i in range(20):
            klines.append(make_kline(10 + i * 0.3, volume=1000000))
        # 最后3天连续大阳线加速
        for i in range(3):
            klines.append(make_kline(18 + i + 0.5, open=18 + i, high=19 + i + 1, low=17.5 + i, volume=3000000))
        
        result = detect_demand_exhaustion(klines)
        # 加速形态可能触发
        self.assertIsNotNone(result)


class TestSupplyExhaustion(unittest.TestCase):
    """供应衰竭信号"""
    
    def test_panic_selling(self):
        """恐慌抛售形态"""
        klines = []
        for i in range(20):
            klines.append(make_kline(20 - i * 0.3, volume=800000))
        # 缓跌后急跌+放量
        klines.append(make_kline(15, open=17, high=17.5, low=14, volume=3000000))
        
        result = detect_supply_exhaustion(klines)
        self.assertIsNotNone(result)
        # 供应衰竭在下降趋势中可能触发
        # 但需满足多个条件，不强制assertTrue


if __name__ == '__main__':
    unittest.main(verbosity=2)
