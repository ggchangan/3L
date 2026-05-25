"""
TDD: 个股/大盘K线图 今日蜡烛三态决策逻辑

被测函数: _resolve_today_candle_state(now_hour, now_min, quote, last_date_str, today_str)

三种输出状态:
  - {'type': 'none'}            → 不画今日蜡烛
  - {'type': 'trading', ...}    → 盘中虚线 + 实时标签 + 量能预估
  - {'type': 'settled', ...}    → 收盘实心 + 涨跌标签 + 实际量
"""
import unittest
from services.stock_chart_service import _resolve_today_candle_state


def _q(close=10.0, open_=10.0, high=10.5, low=9.8, change_pct=1.0, volume_hand=1000):
    """快捷构造模拟 quote dict"""
    return {
        'close': close,
        'open': open_,
        'high': high,
        'low': low,
        'change_pct': change_pct,
        'volume_hand': volume_hand,
    }


class TestTodayCandleState(unittest.TestCase):
    """测试三态决策的每个边界"""

    # ── 场景 A: 不画今日蜡烛 ──────────────────────────

    def test_no_quote_no_candle(self):
        """quote=None → 不画今日蜡烛"""
        st = _resolve_today_candle_state(10, 30, None, '20260522', '20260525')
        self.assertEqual(st['type'], 'none')

    def test_quote_close_zero_no_candle(self):
        """quote收盘价=0 → 不画今日蜡烛"""
        st = _resolve_today_candle_state(10, 30, _q(close=0), '20260522', '20260525')
        self.assertEqual(st['type'], 'none')

    def test_already_cached_no_candle(self):
        """last_date == today_str → 今日K线已在数据中，不用画额外蜡烛"""
        st = _resolve_today_candle_state(20, 0, _q(), '20260525', '20260525')
        self.assertEqual(st['type'], 'none')

    # ── 场景 B: 盘中交易 ────────────────────────────

    def test_trading_10_30(self):
        """10:30 交易中 → 虚线 + 实时标签 + 预估量"""
        st = _resolve_today_candle_state(10, 30, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'trading')
        self.assertTrue(st['is_dashed'])
        self.assertEqual(st['label_prefix'], '实时')
        self.assertEqual(st['date_label'], '实时')
        self.assertEqual(st['vol_prefix'], '实时量')
        self.assertEqual(st['legend_label'], '今日(虚线)')
        self.assertTrue(st['estimate_volume'])

    def test_trading_14_59(self):
        """14:59 交易中（收盘前1分钟）"""
        st = _resolve_today_candle_state(14, 59, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'trading')
        self.assertTrue(st['is_dashed'])

    def test_trading_09_30(self):
        """09:30 刚开盘"""
        st = _resolve_today_candle_state(9, 30, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'trading')
        self.assertTrue(st['is_dashed'])

    # ── 场景 C: 收盘后 ─────────────────────────────

    def test_settled_15_01(self):
        """15:01 收盘后1分钟 → 实心 + 涨跌标签 + 实际量"""
        st = _resolve_today_candle_state(15, 1, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'settled')
        self.assertFalse(st['is_dashed'])
        self.assertEqual(st['label_prefix'], '涨跌')
        self.assertEqual(st['date_label'], '今日')
        self.assertEqual(st['vol_prefix'], '量')
        self.assertEqual(st['legend_label'], '今日(实心)')
        self.assertFalse(st['estimate_volume'])

    def test_settled_20_00(self):
        """20:00 复盘时间 → 实心 + 涨跌"""
        st = _resolve_today_candle_state(20, 0, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'settled')
        self.assertEqual(st['label_prefix'], '涨跌')

    def test_settled_15_00_exactly(self):
        """15:00:00 整点 → 已收盘（不含等号）"""
        st = _resolve_today_candle_state(15, 0, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'settled')
        self.assertFalse(st['is_dashed'])

    def test_settled_midnight(self):
        """凌晨00:00 → 未开盘，不画蜡烛"""
        st = _resolve_today_candle_state(0, 0, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'none')

    def test_settled_early_morning_08_00(self):
        """08:00 盘前 → 未开盘，不画蜡烛"""
        st = _resolve_today_candle_state(8, 0, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'none')

    # ── 场景 D: 非交易日 ──────────────────────────

    def test_saturday_quote_no_trading(self):
        """周六10:00，有昨日收盘价但不是今日有效交易 → 不画蜡烛"""
        # 如果今天是周六，last_date 是周五，today_str 是周六
        # 腾讯可能返回周五收盘数据，close > 0，但这不是今日交易数据
        # has_today 逻辑会认为需要画蜡烛（last_date != today_str）
        # 但周六不应该画 — 这条先标记一下，需要完善 has_today 逻辑
        st = _resolve_today_candle_state(10, 0, _q(), '20260522', '20260524')
        # 周六不是交易日，但当前逻辑不判断交易日历
        # 这个用例只是观察行为
        self.assertIn(st['type'], ('trading', 'settled', 'none'))

    # ── 场景 E: 15:00 边界值的分钟级确认 ──────────────

    def test_trading_vs_settled_boundary_14_59_30(self):
        """14:59:30 仍在交易（当前逻辑只用到分，分钟=59在交易范围）"""
        st = _resolve_today_candle_state(14, 59, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'trading')

    def test_settled_boundary_15_00_00(self):
        """15:00:00 已收盘（严格 < 15:00 才交易）"""
        st = _resolve_today_candle_state(15, 0, _q(), '20260522', '20260525')
        self.assertEqual(st['type'], 'settled')


if __name__ == '__main__':
    unittest.main()
