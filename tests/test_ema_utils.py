"""ema_utils 单元测试 — 纯函数/硬编码数据"""
import sys
sys.path.insert(0, '/home/ubuntu/3l-server')
import pytest
from scripts.ema_utils import ema_list, get_ema_arrangement, _reg_slope, get_mainline_level


class TestEmaList:
    """ema_list 计算测试"""

    def test_basic_calculation(self):
        closes = [100, 101, 102, 103, 104]  # 递增
        ema5 = ema_list(closes, 2)
        # EMA(2): m=2/(2+1)=2/3
        # [0]=100, [1]=100+(101-100)*2/3=100.67, [2]=100.67+(102-100.67)*2/3=101.56
        assert ema5[0] == 100
        assert abs(ema5[1] - round(100 + 2/3, 2)) < 0.01
        assert ema5[-1] > ema5[0], "递增数据→EMA>初值"

    def test_flat_data(self):
        closes = [100, 100, 100, 100]
        ema3 = ema_list(closes, 3)
        assert all(e == 100 for e in ema3), "flat data → all = value"

    def test_decreasing_data(self):
        closes = [100, 99, 98, 97, 96]
        ema5 = ema_list(closes, 5)
        assert ema5[-1] < ema5[0], "递减数据→EMA<初值"

    def test_single_element(self):
        ema = ema_list([50], 5)
        assert ema == [50], "单元素→等于该值"

    def test_period_longer_than_data(self):
        ema = ema_list([10, 20], 20)
        assert ema[0] == 10
        assert abs(ema[1] - (20-10)*2/21 - 10) < 0.01, "短数据也能算出EMA"


class TestGetEmaArrangement:
    """get_ema_arrangement 排列判定测试"""

    def test_bullish(self):
        closes = list(range(90, 111))  # 90→110 上升
        result = get_ema_arrangement(closes)
        assert result == '多头排列'

    def test_bearish(self):
        closes = list(range(110, 89, -1))  # 110→90 下降
        result = get_ema_arrangement(closes)
        assert result == '空头排列'

    def test_cross(self):
        closes = [100, 102, 101, 103, 100, 99, 101, 102, 100, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108]
        result = get_ema_arrangement(closes)
        assert result == '多头排列' or result == '交叉'

    def test_short_data(self):
        closes = [1, 2, 3]
        result = get_ema_arrangement(closes)
        assert result == '--', "数据不足20返回--"


class TestRegSlope:
    """_reg_slope 线性回归斜率测试"""

    def test_positive_slope(self):
        ys = [1, 2, 3, 4, 5]
        slope = _reg_slope(ys)
        assert slope > 0

    def test_negative_slope(self):
        ys = [5, 4, 3, 2, 1]
        slope = _reg_slope(ys)
        assert slope < 0

    def test_zero_slope(self):
        ys = [3, 3, 3, 3, 3]
        slope = _reg_slope(ys)
        assert abs(slope) < 1e-6

    def test_slope_value(self):
        """y = x (0,1,2,3,4) → 理论上斜率=1"""
        ys = [0, 1, 2, 3, 4]
        slope = _reg_slope(ys)
        assert abs(slope - 1.0) < 0.01, f"斜率应接近1, 实际={slope}"

    def test_single_point_returns_zero(self):
        slope = _reg_slope([5])
        assert slope == 0

    def test_two_points_perfect_line(self):
        ys = [10, 20]
        slope = _reg_slope(ys)
        assert abs(slope - 10.0) < 0.01, f"两点斜率应=10, 实际={slope}"


class TestGetMainlineLevel:
    """get_mainline_level 主线判定测试"""

    def test_main_line(self):
        assert get_mainline_level('半导体', ['半导体', '元件'], ['光伏']) == '主线'

    def test_sub_line(self):
        assert get_mainline_level('光伏', ['半导体', '元件'], ['光伏']) == '次级主线'

    def test_non_mainline(self):
        assert get_mainline_level('白酒', ['半导体', '元件'], ['光伏']) == '非主线'

    def test_empty_sector(self):
        assert get_mainline_level('', ['半导体'], []) == ''

    def test_empty_main_lines(self):
        assert get_mainline_level('半导体', None, None) == ''

    def test_sector_not_found(self):
        assert get_mainline_level('银行', ['半导体', '元件'], ['光伏']) == '非主线'
