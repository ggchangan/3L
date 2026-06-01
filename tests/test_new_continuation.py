"""测试下跌中继和区间震荡中继"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../server/backend'))
import unittest
from core.signal_detector.downward_continuation import detect_downward_continuation
from core.signal_detector.range_continuation import detect_range_continuation

def make_k(close, open=None, high=None, low=None, volume=1000000, date='20260101'):
    open = open or close
    high = high or max(open, close)
    low = low or min(open, close)
    return {'date': date, 'open': open, 'close': close, 'high': high, 'low': low, 'volume': volume}

class TestDownwardContinuation(unittest.TestCase):
    
    def test_downward_with_weak_bounce(self):
        """下跌趋势中的缩量弱反弹"""
        klines = []
        # 下跌20天
        for i in range(20):
            klines.append(make_k(20 - i * 0.4, volume=1500000))
        # 弱反弹5天（缩量）
        for i in range(5):
            klines.append(make_k(12 + i * 0.1, volume=500000))
        
        result = detect_downward_continuation(klines)
        self.assertIsNotNone(result)
    
    def test_no_signal_in_uptrend(self):
        """上涨趋势不应触发"""
        klines = [make_k(10 + i * 0.3, volume=1000000) for i in range(30)]
        result = detect_downward_continuation(klines)
        self.assertFalse(result['triggered'])

class TestRangeContinuation(unittest.TestCase):
    
    def test_top_stalling(self):
        """区间顶部滞涨"""
        klines = []
        # 区间震荡
        for i in range(25):
            klines.append(make_k(10 + (i % 3) * 0.5, volume=500000))
        # 区间顶部放量滞涨
        klines.append(make_k(11.5, open=11.5, high=11.6, low=11.3, volume=2000000))
        
        result = detect_range_continuation(klines)
        self.assertIsNotNone(result)
    
    def test_no_signal_in_trend(self):
        """单边趋势不应触发"""
        klines = [make_k(10 + i * 0.5, volume=1000000) for i in range(35)]
        result = detect_range_continuation(klines)
        self.assertFalse(result.get('triggered', False))

if __name__ == '__main__':
    unittest.main(verbosity=2)
