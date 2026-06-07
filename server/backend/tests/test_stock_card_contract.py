"""个股卡片合约测试 — 验证 StockCardData 字段完整性 + action_type 推导一致性

测试策略：
1. StockCardData 实例化测试
2. _calc_action_type() 逐场景测试（fusion优先 + stage回退）
3. _calc_action_signal() 逐场景测试
4. _calc_action_priority() 逐场景测试
5. _calc_action_reason() 逐场景测试
"""
import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core.data_models import StockCardData
from backend.services.stock_card_service import (
    _calc_action_type, _calc_action_signal,
    _calc_action_priority, _calc_action_reason,
)
import pytest


class TestStockCardDataContract:

    def test_can_instantiate(self):
        """验证 StockCardData 可以正常实例化"""
        card = StockCardData(
            code='000001', name='平安银行', sector='银行', direction='',
            price=10.0, change=0.5, date='20260605',
            structure='上涨趋势', stage='上行', ema='多头排列',
            ema5=9.8, ema10=9.5, ema20=9.0, ema30=8.5,
            deviation_pct=2.04, vol_ratio=1.2, vol_analysis='量能正常',
            signal='buy', signal_text='缩量回踩(65%)', buy_point='缩量回踩',
            profit_model1=True, trend_stock=False,
            trading_system='3l', trading_reason='默认3L交易',
            trend_buy_type='', trend_bias='',
            mainline_level='主线', score=75, flags='',
            triggered_signals=[], fusion_type='strong_buy',
            fusion_reason='缩量回踩确认', wave_position='',
            action_type='买入', action_signal='强势买入·缩量回踩(85)',
            action_priority='高', action_reason='缩量回踩确认',
            stop_loss=9.5, stop_loss_pct=5.0,
            sector_chg=None, sector_chg_5d=None, vs_sector_5d=None,
            conclusion='触发缩量回踩，上行阶段确认，可执行买入计划',
            tags=['🏆 盈利1'],
        )
        assert card.code == '000001'
        assert card.action_type == '买入'
        assert card.action_signal == '强势买入·缩量回踩(85)'
        assert card.action_priority == '高'
        assert card.action_reason == '缩量回踩确认'

    def test_required_fields_not_none(self):
        """验证必须字段不为 None"""
        card = StockCardData(
            code='', name='', sector='', direction='',
            price=0, change=0, date='',
            structure='--', stage='--', ema='--',
            ema5=None, ema10=None, ema20=None, ema30=None,
            deviation_pct=0, vol_ratio=0, vol_analysis='--',
            signal='hold', signal_text='', buy_point='',
            profit_model1=False, trend_stock=False,
            trading_system='3l', trading_reason='',
            trend_buy_type='', trend_bias='',
            mainline_level='', score=0, flags='',
            triggered_signals=[], fusion_type='', fusion_reason='',
            wave_position='',
            action_type='持有', action_signal='', action_priority='中',
            action_reason='--',
            stop_loss=None, stop_loss_pct=None,
            sector_chg=None, sector_chg_5d=None, vs_sector_5d=None,
            conclusion='', tags=[],
        )
        # action_type 永远不为空
        assert card.action_type


# ═══════════════════════════════════════════════════════
# _calc_action_type 测试 — 与旧 _make_item_action 逐条对照
# ═══════════════════════════════════════════════════════

class TestCalcActionType:

    @pytest.mark.parametrize('fusion_type,signal,stage,expected', [
        # ── 融合引擎优先 ──
        ('strong_buy',  'buy',  '上行',    '买入'),
        ('signal_buy',  'buy',  '上行',    '买入'),
        ('signal_sell', 'sell', '上行',    '卖出'),
        ('bullish_wait',    'hold', '上行',    '持有'),
        ('conflict_bearish','hold', '上行',    '减仓'),
        ('conflict_bullish','hold', '上行',    '持有'),
        # ── 回退：signal → stage ──
        ('', 'sell', '上行',      '卖出'),
        ('', 'buy',  '上行',      '买入'),
        ('', 'hold', '加速',      '持有'),
        ('', 'hold', '缩量整理',  '持有'),
        ('', 'hold', '上行',      '持有'),
        ('', 'hold', '滞涨',      '减仓'),
        ('', 'hold', '转弱',      '换股'),
        ('', 'hold', '区间底部',  '加仓'),
        ('', 'hold', '区间顶部',  '减仓'),
        ('', 'hold', '区间中段',  '持有'),
        ('', 'hold', '下行',      '持有'),  # 默认回退
    ])
    def test_action_type(self, fusion_type, signal, stage, expected):
        result = _calc_action_type(signal, stage, fusion_type)
        assert result == expected, f'fusion={fusion_type}, sig={signal}, stage={stage} → {result}, expected {expected}'


# ═══════════════════════════════════════════════════════
# _calc_action_signal 测试
# ═══════════════════════════════════════════════════════

class TestCalcActionSignal:

    def test_strong_buy_signal(self):
        triggered = [{'name': '缩量回踩', 'confidence': 85, 'direction': 'bullish'}]
        result = _calc_action_signal('buy', '上行', 'strong_buy', triggered)
        assert '强势买入' in result
        assert '缩量回踩' in result

    def test_bullish_wait(self):
        result = _calc_action_signal('hold', '上行', 'bullish_wait', [])
        assert result == '偏多等确认'

    def test_conflict_bearish(self):
        result = _calc_action_signal('hold', '上行', 'conflict_bearish', [])
        assert result == '空头冲突'

    def test_signal_sell(self):
        triggered = [{'name': '量价背离', 'confidence': 75, 'direction': 'bearish'}]
        result = _calc_action_signal('sell', '上行', 'signal_sell', triggered)
        assert '卖出信号' in result

    def test_stage_accelerate(self):
        result = _calc_action_signal('hold', '加速', '', [])
        assert result == '关注止盈'

    def test_stage_bottom(self):
        result = _calc_action_signal('hold', '区间底部', '', [])
        assert result == '支撑位'

    def test_plain_hold(self):
        result = _calc_action_signal('hold', '上行', '', [])
        assert result == ''


# ═══════════════════════════════════════════════════════
# _calc_action_priority 测试
# ═══════════════════════════════════════════════════════

class TestCalcActionPriority:

    @pytest.mark.parametrize('fusion_type,signal,stage,expected', [
        ('strong_buy',  'buy',  '上行', '高'),
        ('signal_sell', 'sell', '上行', '高'),
        ('conflict_bearish','hold','上行', '高'),
        ('', 'buy', '上行',  '高'),
        ('', 'sell', '上行', '高'),
        ('', 'hold', '加速',  '高'),
        ('', 'hold', '滞涨',  '高'),
        ('', 'hold', '转弱',  '高'),
        ('', 'hold', '区间顶部', '高'),
        ('', 'hold', '缩量整理', '中'),
        ('', 'hold', '区间底部', '中'),
        ('', 'hold', '上行',   '低'),
        ('', 'hold', '区间中段','低'),
        ('', 'hold', '下行',   '中'),  # 默认
    ])
    def test_priority(self, fusion_type, signal, stage, expected):
        result = _calc_action_priority(signal, stage, fusion_type)
        assert result == expected


# ═══════════════════════════════════════════════════════
# _calc_action_reason 测试
# ═══════════════════════════════════════════════════════

class TestCalcActionReason:

    def test_fusion_reason_priority(self):
        result = _calc_action_reason('sell', '上涨趋势', '上行',
                                      '量价背离', {}, '')
        assert result == '量价背离'

    def test_sell_signal(self):
        result = _calc_action_reason('sell', '上涨趋势', '上行',
                                      '', {}, '')
        assert '上涨趋势' in result
        assert '上行' in result

    def test_buy_signal(self):
        result = _calc_action_reason('buy', '区间震荡', '区间底部',
                                      '', {}, '缩量回踩')
        assert '区间底部' in result

    def test_stage_reason(self):
        result = _calc_action_reason('hold', '上涨趋势', '加速', '', {}, '')
        assert '加速' in result
        assert '放量滞涨' in result or '拉升' in result
