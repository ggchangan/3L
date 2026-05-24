"""补全剩余的买点检测辅助函数测试"""
import sys
sys.path.insert(0, '/home/ubuntu/3l-server')

import pytest
from scripts.buy_point_detection import (
    _layer2_factor, _shrink_threshold, _surge_threshold,
    _is_trend_with_ema5, check_panic,
)


class TestLayer2Factor:
    def test_main_line(self):
        assert _layer2_factor(True) == 1.05

    def test_non_main_line(self):
        assert _layer2_factor(False) == 0.80

    def test_default_is_main(self):
        assert _layer2_factor() == 1.05


class TestShrinkThreshold:
    """缩量阈值 — 大盘位置+板块系数"""

    def test_peak_main(self):
        t = _shrink_threshold('波峰', True)
        assert t == round(0.85 * 1.05, 2), f"波峰+主线: {t}"

    def test_valley_non_main(self):
        t = _shrink_threshold('波谷', False)
        assert t == round(0.70 * 0.80, 2), f"波谷+非主线: {t}"

    def test_default_position(self):
        t = _shrink_threshold()
        assert t == round(0.80 * 1.05, 2), f"默认: {t}"

    def test_all_positions(self):
        for pos, base in [('波峰', 0.85), ('波中偏上', 0.85),
                          ('波中', 0.80), ('波中偏下', 0.75), ('波谷', 0.70)]:
            t = _shrink_threshold(pos, True)
            assert t == round(base * 1.05, 2)


class TestSurgeThreshold:
    """放量阈值 — 大盘位置+板块系数"""

    def test_peak_main(self):
        t = _surge_threshold('波峰', True)
        assert t == round(1.2 / 1.05, 2), f"波峰+主线: {t}"

    def test_valley_non_main(self):
        t = _surge_threshold('波谷', False)
        assert t == round(1.5 / 0.80, 2), f"波谷+非主线: {t}"

    def test_default(self):
        t = _surge_threshold()
        assert t == round(1.3 / 1.05, 2), f"默认: {t}"


class TestCheckPanic:
    """恐慌信号 — 占位符，始终返回False"""

    def test_returns_false(self):
        triggered, reason = check_panic([{'close': 100}], 0)
        assert triggered is False
        assert reason == ''

    def test_with_entry_and_keypoint(self):
        kls = [{'close': 100}, {'close': 101}, {'close': 99}]
        triggered, reason = check_panic(kls, 2, entry_idx=0, key_point=95)
        assert triggered is False

    def test_always_placeholder(self):
        """各种输入都应返回False（占位符）"""
        for idx in [0, 1, 5]:
            assert check_panic([{'close': 100}] * 10, idx) == (False, '')


class TestIsTrendWithEma5:
    """_is_trend_with_ema5 — 需要30根K线"""

    def test_not_enough_data(self):
        # 只有10根
        kls = [{'close': 100 + i, 'high': 105 + i, 'low': 95 + i, 'volume': 1000, 'vol': 1000} for i in range(10)]
        assert _is_trend_with_ema5(kls, 9) is False

    def test_not_trend_structure(self):
        # 30根下降K线
        kls = [{'close': 200 - i * 2, 'high': 205 - i, 'low': 195 - i, 'volume': 1000, 'vol': 1000} for i in range(40)]
        assert _is_trend_with_ema5(kls, 39) is False
