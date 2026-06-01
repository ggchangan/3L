"""
信号检测融合系统单元测试

覆盖范围：
  1. 信号检测基础 — 用模拟K线数据测试各信号检测器正常调用
  2. 融合判定引擎 — 测试 fusion.py 的 8 条规则分支
  3. 大盘过滤 — 测试 market_filter.py 的 reduce/rest/normal 三种状态
  4. 卖点检测 — 测试 sell_point_detection.py 的五条卖出规则

策略：
  - 全部使用 unittest.mock 隔离真实数据路径和第三方依赖
  - 不写磁盘、不 import 真实数据文件
  - 用构造的假数据测试接口行为
"""

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import date, timedelta

# ── 工具函数：生成模拟K线数据 ──


def make_kline(close: float, open_: float = None, high: float = None,
               low: float = None, volume: float = 1.0) -> dict:
    """生成单条K线"""
    open_ = open_ or close
    high = high or max(open_, close) * 1.02
    low = low or min(open_, close) * 0.98
    return {
        'close': close,
        'open': open_,
        'high': high,
        'low': low,
        'volume': volume,
    }


def make_klines(count: int = 60, base_price: float = 100.0,
                trend: str = 'flat', volume_base: float = 1.0) -> list:
    """
    生成指定数量、指定趋势的K线数据。

    trend:
      'flat'     — 区间震荡
      'up'       — 缓慢上涨
      'down'     — 缓慢下跌
      'breakout' — 前50天区间震荡，后10天向上突破
    """
    klines = []
    price = base_price

    for i in range(count):
        if trend == 'up':
            price = base_price * (1 + i * 0.005)
        elif trend == 'down':
            price = base_price * (1 - i * 0.005)
        elif trend == 'breakout':
            if i < 50:
                # 区间震荡
                price = base_price + (i % 10) * 0.5
            else:
                # 突破
                price = base_price * (1 + (i - 49) * 0.03)
        elif trend == 'breakdown':
            if i < 50:
                price = base_price + (i % 10) * 0.5
            else:
                price = base_price * (1 - (i - 49) * 0.03)
        else:
            # flat: 小幅震荡
            price = base_price + (i % 7) * 0.3

        vol = volume_base * (1 + (i % 5) * 0.1)
        klines.append(make_kline(round(price, 2), volume=round(vol, 2)))

    return klines


def make_klines_uptrend(count: int = 60) -> list:
    """生成上涨趋势K线"""
    return make_klines(count, trend='up')


def make_klines_downtrend(count: int = 60) -> list:
    """生成下跌趋势K线"""
    return make_klines(count, trend='down')


def make_klines_ranging(count: int = 60) -> list:
    """生成区间震荡K线"""
    return make_klines(count, trend='flat')


# ── 测试数据准备 ──

KLINES_60 = make_klines(60, trend='flat')
KLINES_UP = make_klines(60, trend='up')
KLINES_DOWN = make_klines(60, trend='down')
KLINES_BREAKOUT = make_klines(60, trend='breakout')
KLINES_BREAKDOWN = make_klines(60, trend='breakdown')


# ══════════════════════════════════════════════════════════════════
# 第1部分：信号检测基础测试
# ══════════════════════════════════════════════════════════════════

class TestSignalDetectors(unittest.TestCase):
    """验证所有信号检测器可以被正常调用并返回预期结构"""

    def _assert_signal_result(self, result: dict):
        """验证信号检测返回值结构"""
        self.assertIn('triggered', result)
        self.assertIn('confidence', result)
        self.assertIn('signal_name', result)
        self.assertIn('signal_key', result)
        self.assertIn('detail', result)
        self.assertIn('scores', result)
        self.assertIsInstance(result['triggered'], bool)
        self.assertIsInstance(result['confidence'], (int, float))
        self.assertIsInstance(result['signal_name'], str)
        self.assertIsInstance(result['signal_key'], str)

    def test_upward_breakout_called(self):
        """向上突破检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.upward_breakout import detect_upward_breakout
        result = detect_upward_breakout(KLINES_BREAKOUT)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'upward_breakout')

    def test_downward_breakout_called(self):
        """向下突破检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.downward_breakout import detect_downward_breakout
        result = detect_downward_breakout(KLINES_BREAKDOWN)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'downward_breakout')

    def test_upward_continuation_called(self):
        """上涨中继检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.upward_continuation import detect_upward_continuation
        result = detect_upward_continuation(KLINES_UP)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'upward_continuation')

    def test_downward_continuation_called(self):
        """下跌中继检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.downward_continuation import detect_downward_continuation
        result = detect_downward_continuation(KLINES_DOWN)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'downward_continuation')

    def test_range_continuation_called(self):
        """区间震荡中继检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.range_continuation import detect_range_continuation
        result = detect_range_continuation(KLINES_60)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'range_continuation')

    def test_upward_reversal_called(self):
        """向上反转检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.upward_reversal_detector import detect_upward_reversal
        result = detect_upward_reversal(KLINES_DOWN)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'upward_reversal')

    def test_downward_reversal_called(self):
        """向下反转检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.downward_reversal import detect_downward_reversal
        result = detect_downward_reversal(KLINES_UP)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'downward_reversal')

    def test_demand_exhaustion_called(self):
        """需求衰竭检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.demand_exhaustion import detect_demand_exhaustion
        result = detect_demand_exhaustion(KLINES_UP)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'demand_exhaustion')

    def test_supply_exhaustion_called(self):
        """供应衰竭检测器可被调用并返回正确结构"""
        from backend.core.signal_detector.supply_exhaustion import detect_supply_exhaustion
        result = detect_supply_exhaustion(KLINES_DOWN)
        self._assert_signal_result(result)
        self.assertEqual(result['signal_key'], 'supply_exhaustion')


# ══════════════════════════════════════════════════════════════════
# 第2部分：融合判定引擎 — 8条规则分支
# ══════════════════════════════════════════════════════════════════

class TestFusionEngine(unittest.TestCase):
    """测试 fusion.py 的 _run_fusion 8条规则分支"""

    def setUp(self):
        # 基础参数
        self.klines = KLINES_60
        self.idx = -1
        self.main_line_names = ['半导体']
        self.sector = '半导体'

        # 预先mock所有信号检测器返回空（无触发）
        self.detector_patcher = patch(
            'backend.core.signal_detector.fusion._get_triggered_signals',
            return_value=[]
        )
        self.mock_get_signals = self.detector_patcher.start()

    def tearDown(self):
        self.detector_patcher.stop()

    # ── 辅助：构造一个触发信号 ──
    def _make_signal(self, key='upward_breakout', name='向上突破',
                     direction='bullish', confidence=80):
        return {
            'key': key,
            'name': name,
            'direction': direction,
            'confidence': confidence,
            'scores': {},
            'detail': '',
        }

    def test_rule1_strong_buy(self):
        """规则1: 关键点看多 + 买点已确认 + 看多信号 → 买入"""
        self.mock_get_signals.return_value = [
            self._make_signal('upward_breakout', '向上突破', 'bullish', 80)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=5,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='buy', existing_buy_point='盈利模式1',
            confidence_threshold=60,
        )
        self.assertEqual(result['signal'], 'buy')
        self.assertEqual(result['fusion_type'], 'strong_buy')
        self.assertGreaterEqual(result['confidence'], 70)

    def test_rule2_signal_buy(self):
        """规则2: 关键点看多 + 看多信号（无买点）→ 潜在买点"""
        self.mock_get_signals.return_value = [
            self._make_signal('upward_continuation', '上涨中继', 'bullish', 75)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=3,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'buy')
        self.assertEqual(result['fusion_type'], 'signal_buy')
        self.assertIn('上涨中继', result['signal_text'])

    def test_rule2b_conflict_bearish(self):
        """规则2b: 关键点看多 + 看空信号 → 矛盾，警惕"""
        self.mock_get_signals.return_value = [
            self._make_signal('downward_reversal', '向下反转', 'bearish', 70)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=3,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'conflict_bearish')

    def test_rule3_signal_sell(self):
        """规则3: 关键点看空 + 看空信号 → 卖出"""
        self.mock_get_signals.return_value = [
            self._make_signal('downward_breakout', '向下突破', 'bearish', 80)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='下降趋势', stage='加速',
            ema_arrangement='空头排列', bias5=15,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'sell')
        self.assertEqual(result['fusion_type'], 'signal_sell')

    def test_rule3b_conflict_bullish(self):
        """规则3b: 关键点看空 + 看多信号 → 矛盾，等确认"""
        self.mock_get_signals.return_value = [
            self._make_signal('upward_reversal', '向上反转', 'bullish', 65)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='下降趋势', stage='加速',
            ema_arrangement='空头排列', bias5=15,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'conflict_bullish')

    def test_rule4_buy_point_only(self):
        """规则4: 已有盈利模式买点但无信号 → 维持买点"""
        self.mock_get_signals.return_value = []  # 无信号
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=3,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='buy', existing_buy_point='盈利模式1',
        )
        self.assertEqual(result['signal'], 'buy')
        self.assertEqual(result['fusion_type'], 'buy_point_only')

    def test_rule5_bearish_watch(self):
        """规则5: 关键点看空 + 无看空信号 → 持有但警惕"""
        self.mock_get_signals.return_value = []  # 无信号
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='下降趋势', stage='加速',
            ema_arrangement='空头排列', bias5=15,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'bearish_watch')

    def test_rule6_bullish_wait(self):
        """规则6: 关键点看多 + 无看多信号 → 等待"""
        self.mock_get_signals.return_value = [
            self._make_signal('downward_breakout', '向下突破', 'bearish', 70)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=3,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        # 关键点看多 + 无看多信号(只有看空) → 规则2b先匹配，但无看多信号进入规则6
        # 实际上规则2b会先匹配，所以这里测试规则6需要无bullish信号
        pass

    def test_rule6_bullish_wait_no_signals(self):
        """规则6: 关键点看多 + 无任何看多信号 → 等待"""
        self.mock_get_signals.return_value = []
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='上升趋势', stage='上行',
            ema_arrangement='多头排列', bias5=3,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'bullish_wait')

    def test_rule7_ignore_signal(self):
        """规则7: 关键点中性 + 有信号 → 忽略"""
        self.mock_get_signals.return_value = [
            self._make_signal('upward_breakout', '向上突破', 'bullish', 75)
        ]
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='', stage='',
            ema_arrangement='', bias5=0,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'ignore_signal')

    def test_rule8_balance(self):
        """规则8: 无信号 + 关键点中性 → 平衡状态"""
        self.mock_get_signals.return_value = []
        from backend.core.signal_detector.fusion import _run_fusion
        result = _run_fusion(
            self.klines, self.idx,
            structure='', stage='',
            ema_arrangement='', bias5=0,
            main_line_names=self.main_line_names,
            sector=self.sector,
            existing_signal='hold', existing_buy_point='',
        )
        self.assertEqual(result['signal'], 'hold')
        self.assertEqual(result['fusion_type'], 'balance')
        self.assertEqual(result['confidence'], 0)

    def test_keypoint_direction_bearish_structure(self):
        """关键点方向：下降趋势 → bearish"""
        from backend.core.signal_detector.fusion import _keypoint_direction
        result = _keypoint_direction(
            structure='下降趋势', stage='', ema_arrangement='',
            bias5=0, is_mainline=True
        )
        self.assertEqual(result, 'bearish')

    def test_keypoint_direction_bearish_stage(self):
        """关键点方向：滞涨阶段 → bearish"""
        from backend.core.signal_detector.fusion import _keypoint_direction
        result = _keypoint_direction(
            structure='', stage='滞涨', ema_arrangement='',
            bias5=0, is_mainline=True
        )
        self.assertEqual(result, 'bearish')

    def test_keypoint_direction_bearish_bias(self):
        """关键点方向：BIAS>12 → bearish"""
        from backend.core.signal_detector.fusion import _keypoint_direction
        result = _keypoint_direction(
            structure='', stage='', ema_arrangement='',
            bias5=15, is_mainline=True
        )
        self.assertEqual(result, 'bearish')

    def test_keypoint_direction_bullish_stage(self):
        """关键点方向：缩量整理 → bullish"""
        from backend.core.signal_detector.fusion import _keypoint_direction
        result = _keypoint_direction(
            structure='', stage='缩量整理', ema_arrangement='',
            bias5=0, is_mainline=True
        )
        self.assertEqual(result, 'bullish')

    def test_keypoint_direction_bullish_ema(self):
        """关键点方向：多头排列 → bullish"""
        from backend.core.signal_detector.fusion import _keypoint_direction
        result = _keypoint_direction(
            structure='', stage='', ema_arrangement='多头排列',
            bias5=0, is_mainline=True
        )
        self.assertEqual(result, 'bullish')

    def test_fusion_judge_interface(self):
        """fusion_judge 对外接口正常返回"""
        with patch('backend.core.signal_detector.fusion._get_triggered_signals',
                   return_value=[]):
            from backend.core.signal_detector.fusion import fusion_judge
            result = fusion_judge(
                klines=self.klines, idx=self.idx,
                main_line_names=self.main_line_names,
                sector=self.sector,
            )
            self.assertIn('signal', result)
            self.assertIn('fusion_type', result)
            self.assertIn('confidence', result)
            self.assertIn('reason', result)
            self.assertIn('triggered_signals', result)
            self.assertIn('keypoint_direction', result)


# ══════════════════════════════════════════════════════════════════
# 第3部分：大盘过滤 — reduce / rest / normal
# ══════════════════════════════════════════════════════════════════

class TestMarketFilter(unittest.TestCase):
    """测试 market_filter.py 的三种过滤状态"""

    def _get_filter(self, market_cycle: dict) -> dict:
        """Helper to call get_market_filter"""
        from backend.core.signal_detector.market_filter import get_market_filter
        return get_market_filter(market_cycle)

    def test_filter_reduce_peak(self):
        """波峰状态 → reduce"""
        result = self._get_filter({'position': '波峰', 'pk_score': 3, 'vl_score': 0, 'bias20': 5})
        self.assertEqual(result['filter'], 'reduce')
        self.assertIn('5成', result['max_position'])

    def test_filter_reduce_pk_high(self):
        """pk_score >= 4 → reduce"""
        result = self._get_filter({'position': '波中', 'pk_score': 4, 'vl_score': 0, 'bias20': 0})
        self.assertEqual(result['filter'], 'reduce')

    def test_filter_reduce_bias20_high(self):
        """BIAS20 > 12 → reduce"""
        result = self._get_filter({'position': '波中', 'pk_score': 0, 'vl_score': 0, 'bias20': 15})
        self.assertEqual(result['filter'], 'reduce')

    def test_filter_rest_downtrend(self):
        """下降趋势 → rest"""
        result = self._get_filter({'position': '下降趋势', 'pk_score': 0, 'vl_score': 3, 'bias20': 0})
        self.assertEqual(result['filter'], 'rest')
        self.assertIn('3成', result['max_position'])

    def test_filter_rest_vl_high(self):
        """vl_score >= 4 → rest"""
        result = self._get_filter({'position': '波中', 'pk_score': 0, 'vl_score': 4, 'bias20': 0})
        self.assertEqual(result['filter'], 'rest')

    def test_filter_rest_bias20_low(self):
        """BIAS20 < -8 → rest"""
        result = self._get_filter({'position': '波中', 'pk_score': 0, 'vl_score': 0, 'bias20': -10})
        self.assertEqual(result['filter'], 'rest')

    def test_filter_normal(self):
        """正常状态 → normal"""
        result = self._get_filter({'position': '波中', 'pk_score': 0, 'vl_score': 0, 'bias20': 0})
        self.assertEqual(result['filter'], 'normal')
        self.assertIn('8成', result['max_position'])

    def test_filter_normal_missing_keys(self):
        """缺少字段时安全降级到 normal"""
        result = self._get_filter({})
        self.assertEqual(result['filter'], 'normal')

    def test_filter_reduce_deviation_pct_fallback(self):
        """bias20=0时从 deviation_pct 取值"""
        result = self._get_filter({
            'position': '波中', 'pk_score': 0, 'vl_score': 0,
            'bias20': 0, 'deviation_pct': 15,
        })
        self.assertEqual(result['filter'], 'reduce')


# ══════════════════════════════════════════════════════════════════
# 第4部分：卖点检测 — 5条规则
# ══════════════════════════════════════════════════════════════════

class TestSellPointDetection(unittest.TestCase):
    """测试 sell_point_detection.py 的五条卖出规则"""

    def setUp(self):
        # 卖点检测依赖 ema_utils 的 get_structure / get_stage
        # 以及 signal_detector 的 detect_downward_breakout 等
        self.klines = KLINES_60
        self.idx = -1

    def _detect(self, structure='', stage='', bias5=0, klines=None):
        from backend.core.signal_detector.sell_point_detection import detect_sell_point
        k = klines or self.klines
        # sell_point_detection 要求 idx>=0，不处理 -1 索引
        idx = len(k) - 1
        return detect_sell_point(
            k, idx,
            structure=structure, stage=stage, bias5=bias5,
        )

    @patch('backend.core.signal_detector.sell_point_detection.detect_downward_breakout')
    def test_sell_rule1_downward_breakout(self, mock_dd):
        """规则1: 向下突破 → 卖出"""
        mock_dd.return_value = {
            'triggered': True, 'confidence': 80,
            'signal_name': '向下突破', 'signal_key': 'downward_breakout',
            'detail': '跌破前低', 'scores': {},
        }
        result = self._detect()
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '下降突破')
        self.assertEqual(result['signal'], '卖出')
        self.assertIn('跌破前低', result['reason'])

    @patch('backend.core.signal_detector.sell_point_detection.detect_downward_reversal')
    def test_sell_rule2_downward_reversal(self, mock_dr):
        """规则2: 向下反转 → 卖出"""
        mock_dr.return_value = {
            'triggered': True, 'confidence': 75,
            'signal_name': '向下反转', 'signal_key': 'downward_reversal',
            'detail': '上涨末端', 'scores': {},
        }
        result = self._detect()
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '高位反转向下')
        self.assertEqual(result['signal'], '卖出')

    @patch('backend.core.signal_detector.sell_point_detection.detect_demand_exhaustion')
    def test_sell_rule3_demand_exhaustion(self, mock_de):
        """规则3: 需求衰竭 → 卖出"""
        mock_de.return_value = {
            'triggered': True, 'confidence': 80,
            'signal_name': '需求衰竭', 'signal_key': 'demand_exhaustion',
            'detail': '加速形态', 'scores': {},
        }
        result = self._detect()
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '需求衰竭')
        self.assertEqual(result['signal'], '卖出')

    def test_sell_rule4_structure_sell(self):
        """规则4: 结构卖出 — 下降趋势"""
        result = self._detect(structure='下降趋势')
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '趋势卖出')
        self.assertEqual(result['confidence'], 70)

    def test_sell_rule4_stage_sell(self):
        """规则4: 结构卖出 — 转弱/滞涨阶段"""
        result = self._detect(stage='转弱')
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '转弱卖出')
        self.assertEqual(result['confidence'], 55)

        result2 = self._detect(stage='滞涨')
        self.assertTrue(result2['triggered'])
        self.assertEqual(result2['sell_type'], '滞涨卖出')

    def test_sell_rule5_bias_high(self):
        """规则5: BIAS高位卖出"""
        result = self._detect(bias5=18)
        self.assertTrue(result['triggered'])
        self.assertEqual(result['sell_type'], '乖离率过高')
        self.assertEqual(result['confidence'], 50)

    def test_sell_no_trigger(self):
        """无触发条件 → 返回未触发"""
        result = self._detect()
        self.assertFalse(result['triggered'])
        self.assertEqual(result['sell_type'], '')

    def test_sell_insufficient_data(self):
        """数据不足时返回未触发"""
        from backend.core.signal_detector.sell_point_detection import detect_sell_point
        result = detect_sell_point([], 0)
        self.assertFalse(result['triggered'])
        self.assertIn('数据不足', result['reason'])

    @patch('backend.core.signal_detector.sell_point_detection.detect_downward_breakout')
    def test_sell_rule1_low_confidence_ignored(self, mock_dd):
        """向下突破置信度低于60时不触发规则1（应继续检查后续规则）"""
        mock_dd.return_value = {
            'triggered': True, 'confidence': 50,
            'signal_name': '向下突破', 'signal_key': 'downward_breakout',
            'detail': '', 'scores': {},
        }
        # 无向下反转/需求衰竭/结构/BIAS → 最终未触发
        result = self._detect()
        self.assertFalse(result['triggered'])


# ══════════════════════════════════════════════════════════════════
# 运行入口（支持 python -m pytest 和 python -m unittest）
# ══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    unittest.main()
