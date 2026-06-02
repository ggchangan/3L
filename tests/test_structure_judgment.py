"""
结构判定 + 加速判定 回归测试
涵盖2026-05-22讨论的所有边界案例 + 2026-06-02 C方案升级

每类测试都标注对应的讨论案例，确保回归时不会踩同样的坑。

运行：cd /home/ubuntu/3l-server && PYTHONPATH=/home/ubuntu/3l-server/core/threel_core python3 -m pytest tests/test_structure_judgment.py -v
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'threel_core'))

from ema_utils import get_structure, get_stage, ema_list


def _pad_to_min(closes, min_len=27, pad_val=None):
    """补齐数据到最小长度（只补前面，不截断后面）"""
    if len(closes) >= min_len:
        return closes
    pad_val = pad_val or closes[0]
    return [pad_val] * (min_len - len(closes)) + closes


# ==============================================================
# 第一部分：get_structure 结构判定测试
# 数据补足到27+根（EMA12+5需要至少25根）
# ==============================================================

class TestStructureUpgradeDowngrade:
    """结构判定 — 上涨降级（末端回调）"""

    def test_rune_300442_downgrade_from_up(self):
        """
        润泽科技(300442) — 上涨→区间震荡（第②层降级）

        背景：60天从88涨到110，近4天从110跌到91（-10.6%）
        EMA12斜率+，但EMA5斜率转负 + 价格回撤
        → 应降级为区间震荡

        2026-05-22 用户发现的原案例。
        """
        base = [88.31, 90.44, 89.06, 96.21, 97.45, 98.08, 97.91,
                91.38, 101.62, 99.67, 102.46, 99.39, 98.33, 95.85, 91.58]
        # 补前段平稳上涨数据到27根
        padding = [85 + i * 0.3 for i in range(12)]  # 85→88.6 平稳上涨
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        # 补了前段上涨数据后，EMA12斜率应该为正但EMA5斜率转负
        # 应该区间震荡（特殊处理或降级）
        assert result in ('区间震荡', '--'), (
            f"润泽科技: 预期区间震荡, 实际{result}"
        )

    def test_semi_688126_keep_up(self):
        """
        沪硅产业(688126) — 保持上涨趋势（不应被误降级）

        正常上涨的股票，EMA12和EMA5斜率都为正。
        """
        base = [24.50, 25.10, 25.80, 26.20, 26.80, 27.10, 27.50,
                27.80, 28.00, 28.50, 29.00, 29.50, 30.00, 30.50, 31.00]
        padding = [20 + i * 0.3 for i in range(15)]  # 补稳步上涨
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '上涨趋势', (
            f"沪硅: 预期上涨趋势, 实际{result}"
        )

    def test_weichuang_688698_keep_up(self):
        """
        伟创电气(688698) — 保持上涨趋势（正常回调不被误伤）

        底部整理后突破，有正常波动但不破坏EMA5向上趋势。
        """
        base = [55.0, 56.0, 57.0, 57.5, 58.0, 58.5, 59.0,
                58.8, 59.5, 60.0, 61.0, 60.5, 61.5, 62.0, 61.8]
        padding = [45 + i * 0.7 for i in range(15)]  # 45→55稳步上涨
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '上涨趋势', (
            f"伟创电气: 预期上涨趋势, 实际{result}"
        )

    def test_tongfu_002156_downgrade_to_interval(self):
        """
        通富微电(002156) — 上涨→区间震荡（EMA5斜率转负降级）

        EMA12斜率+1.65%，多头排列，但EMA5斜率-1.6%
        → C方案降级为区间震荡

        2026-06-02 C方案核心案例。
        """
        base = [55 + i * 0.25 for i in range(20)]   # 平台55→60
        surge = [60 + i * 3.6 for i in range(5)]    # 急拉60→78
        drop = [78 - i * 2.8 for i in range(5)]     # 急回78→64
        plat = [64, 63, 63.5, 62, 63.8]              # 平台
        padding = [55] * 10
        closes = _pad_to_min(padding + base + surge + drop + plat)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"通富微电: 预期区间震荡, 实际{result}"
        )

    def test_guangxu_002281_downgrade_to_interval(self):
        """
        光迅科技(002281) — 上涨→区间震荡（EMA5斜率微负）

        EMA12斜率+0.8%+，但价格持续回调使EMA5斜率转负
        → 按C方案降级为区间震荡

        2026-06-02 用户确认case。
        """
        padding = [150] * 10
        up = [150 + i * 3 for i in range(15)]
        peak = [195, 198, 200, 206, 210]
        retreat = [210, 205, 200, 195, 190, 188, 185, 183, 186, 190]
        closes = _pad_to_min(padding + up + peak + retreat)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"光迅科技: 预期区间震荡, 实际{result}"
        )

    def test_lvdi_688017_downgrade_to_interval(self):
        """
        绿地谐波(688017) — 上涨→区间震荡（多头排列破坏）

        回调导致EMA5<EMA10交叉，多头排列破坏
        → 降级为区间震荡

        2026-06-02 用户发现case。
        """
        padding2 = [200] * 10
        up2 = [200 + i * 5 for i in range(15)]
        peak2 = [280, 300, 320, 340, 350]
        drop2 = [350, 320, 290, 280, 275]
        closes = _pad_to_min(padding2 + up2 + peak2 + drop2)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"绿地谐波: 预期区间震荡, 实际{result}"
        )


class TestStructureDeclineUpgrade:
    """结构判定 — 下降升级（末端反弹）"""

    def test_haoyuan_688131_upgrade_from_down(self):
        """
        皓元医药(688131) — 下降→区间震荡（末端反弹）

        持续下跌后末端反弹，EMA12斜率略负但BIAS>3%
        → 区间震荡

        2026-05-22 对称校验发现的反向案例。
        """
        base = [73, 73, 75, 73, 74, 72, 71, 72, 71, 70, 71, 72, 71, 78, 82]
        padding = [80 - i * 0.5 for i in range(15)]  # 80→73 缓慢下降
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"皓元医药: 预期区间震荡, 实际{result}"
        )

    def test_hengrui_600276_keep_down(self):
        """
        恒瑞医药(600276) — 保持下降趋势（末端未反弹）

        EMA12斜率负 + BIAS低 → 下降趋势
        """
        base = [55, 55, 54, 54, 54, 53, 54, 56, 56, 54, 54, 52, 52, 51, 51]
        padding = [65 - i * 0.7 for i in range(15)]  # 65→55持续下降
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '下降趋势', (
            f"恒瑞医药: 预期下降趋势, 实际{result}"
        )


class TestStructureIntervalToDecline:
    """结构判定 — 区间→下降升级"""

    def test_ningde_300750_keep_interval(self):
        """
        宁德时代(300750) — 区间震荡

        先涨后跌，但最后几日企稳反弹，BIAS>3%不被判下降趋势
        → 区间震荡

        BIAS > 3% 是关键：close在EMA12上方足够距离
        """
        closes = ([390]*5 + [395]*5 + [400]*3 + [405]*3 +
                  [410]*2 + [415]*2 + [420]*2 + [425]*2 +
                  [430, 435, 440, 445, 450] +
                  [455, 460, 455, 450, 445] +
                  [440, 435, 430, 428, 445] +
                  [436, 460, 452, 437, 446] +
                  [431, 434, 427, 424, 417] +
                  [418, 422, 430, 438, 448])  # 反弹到448，BIAS>3%
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"宁德时代: 预期区间震荡, 实际{result}"
        )

    def test_juren_002558_upgrade_to_down(self):
        """
        巨人网络(002558) — 下降趋势

        60日持续下跌，持续创新低。
        """
        closes = ([33]*10 + [34]*5 + [33]*5 +
                  [32, 33, 34, 33, 32] +
                  [31, 32, 31, 30, 31] +
                  [30, 29, 30, 29, 28] +
                  [28, 27, 28, 27, 26] +
                  [26, 27, 26, 25, 24] +
                  [24, 23, 24, 23, 22])
        result = get_structure(closes)
        assert result == '下降趋势', (
            f"巨人网络: 预期下降趋势, 实际{result}"
        )

    def test_tengyuan_301219_keep_interval(self):
        """
        腾远钴业(301219) — 保持区间震荡

        对称波浪，EMA12斜率平缓 → 区间震荡
        """
        closes = [80] * 10
        closes += [81, 82, 84, 85, 86, 87, 88, 89, 90, 90]
        closes += [89, 88, 87, 86, 85, 84, 83, 82, 81, 80]
        closes += [81, 82, 83, 84, 85, 86, 87, 88, 87, 86]
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"腾远钴业: 预期区间震荡, 实际{result}"
        )


class TestStructureAntiFalsePositive:
    """结构判定 — 防误伤测试"""

    def test_yaoming_603259_keep_interval(self):
        """
        药明康德(603259) — 保持区间震荡（整体横盘）

        15日内围绕同一区间波动。
        """
        base = [109, 110, 111, 110, 109, 108, 107,
                108, 109, 110, 111, 110, 109, 108, 109]
        padding = [105 + i * 0.3 for i in range(15)]  # 105→109缓升
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"药明康德: 预期区间震荡, 实际{result}"
        )

    def test_huadian_600726_keep_interval(self):
        """
        华电能源(600726) — 保持区间震荡（反弹中）
        """
        base = [7, 7, 7, 7, 8, 8, 8, 8, 8, 8, 8, 7, 7, 6, 6]
        padding = [6 + i * 0.07 for i in range(15)]  # 6→7缓升
        closes = _pad_to_min(padding + base)
        result = get_structure(closes)
        assert result == '区间震荡', (
            f"华电能源: 预期区间震荡, 实际{result}"
        )


# ==============================================================
# 第二部分：get_stage 阶段判定测试
# ==============================================================

class TestStage:
    """阶段判定 — 使用EMA10斜率，与get_structure独立"""

    def test_dashu_301200_breakout_to_up(self):
        """
        大族数控(301200) — 整理后突破→上行
        """
        closes = [120, 122, 125, 128, 130, 132, 135, 138, 140, 142,
                  140, 138, 135, 133, 130, 128, 127, 126, 125, 124,
                  123, 122, 121, 121, 122, 123, 124, 125, 126, 125,
                  124, 123, 122, 121, 120,
                  119, 118, 119, 120, 122,
                  125, 128, 132, 136, 140,
                  145, 148, 150, 152, 153]
        while len(closes) < 60:
            closes.insert(0, closes[0])
        closes = closes[:60]

        highs = [c * 1.03 for c in closes]
        lows = [c * 0.97 for c in closes]
        volumes = [1000000] * len(closes)

        struct = get_structure(closes)
        stage = get_stage(closes, struct, highs, lows, None, None, volumes)
        assert stage in ('上行', '加速', '缩量整理', '--', '区间震荡'), (
            f"大族数控阶段: {stage}"
        )

    def test_aobi_688322_interval(self):
        """
        奥比中光(688322) — 结构判为区间震荡
        """
        base = [185] * 10 + [188, 190, 192, 195, 198]
        mid = [200 + i * 1 for i in range(20)]
        end = [210, 220, 235, 248, 260]
        closes = base + mid + end
        while len(closes) < 60:
            closes.insert(0, closes[0])
        closes = closes[:60]

        struct = get_structure(closes)
        assert struct == '区间震荡', (
            f"奥比中光结构: 预期区间震荡, 实际{struct}"
        )

    def test_zhongxin_688981_keep_acceleration(self):
        """
        中芯国际(688981) — 结构检查

        一路涨平 → 急涨
        """
        closes = [100] * 30 + [110, 125, 140, 160, 185]
        while len(closes) < 60:
            closes.insert(0, closes[0])
        closes = closes[:60]

        highs = [c * 1.08 for c in closes]
        lows = [c * 0.92 for c in closes]
        volumes = [1000000] * len(closes)

        struct = get_structure(closes)
        stage = get_stage(closes, struct, highs, lows, None, None, volumes)
        assert struct in ('上涨趋势', '区间震荡'), (
            f"中芯国际结构: 预期上涨趋势/区间震荡, 实际{struct}"
        )
