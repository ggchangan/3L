"""个股卡片合约测试 — 验证 StockCardData + action_type 推导与原版一致

测试策略：
1. StockCardData 实例化测试
2. _calc_action_type/signal/priority/reason 逐场景测试（严格对应旧 _make_item_action）
3. A/B 对比：new = old 对所有输入组合成立
"""
import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.models.data_models import StockCardData
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
            action_type='买入', action_signal='',
            action_priority='高', action_reason='上涨趋势·上行·触发缩量回踩',
            stop_loss=9.5, stop_loss_pct=5.0,
            sector_chg=None, sector_chg_5d=None, vs_sector_5d=None,
            conclusion='触发缩量回踩，上行阶段确认，可执行买入计划',
            tags=['🏆 盈利1'],
        )
        assert card.code == '000001'
        assert card.action_type == '买入'

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
        assert card.action_type  # action_type 永远不为空


# ═══════════════════════════════════════════════════════
# _calc_action_type 测试 — 严格对应旧 _make_item_action
# ═══════════════════════════════════════════════════════

class TestCalcActionType:

    @pytest.mark.parametrize('signal,stage,expected', [
        ('sell', '上行',      '卖出'),
        ('buy',  '上行',      '买入'),
        ('hold', '加速',      '持有'),
        ('hold', '缩量整理',  '持有'),
        ('hold', '上行',      '持有'),
        ('hold', '滞涨',      '减仓'),
        ('hold', '转弱',      '换股'),
        ('hold', '区间底部',  '加仓'),
        ('hold', '区间顶部',  '减仓'),
        ('hold', '区间中段',  '持有'),
        ('hold', '下行',      '持有'),  # 默认
    ])
    def test_action_type(self, signal, stage, expected):
        result = _calc_action_type(signal, stage, '')
        assert result == expected, f'sig={signal}, stage={stage} → {result}, expected {expected}'


# ═══════════════════════════════════════════════════════
# _calc_action_signal 测试 — 严格对应旧 _make_item_action
# ═══════════════════════════════════════════════════════

class TestCalcActionSignal:

    @pytest.mark.parametrize('signal,stage,expected', [
        ('sell', '上行',      ''),
        ('buy',  '上行',      '买点'),
        ('hold', '加速',      '关注止盈'),
        ('hold', '缩量整理',  '可加仓'),
        ('hold', '上行',      ''),
        ('hold', '滞涨',      '警惕滞涨'),
        ('hold', '转弱',      '关注转弱'),
        ('hold', '区间底部',  '支撑位'),
        ('hold', '区间顶部',  '压力位'),
        ('hold', '区间中段',  ''),
        ('hold', '下行',      ''),
    ])
    def test_action_signal(self, signal, stage, expected):
        result = _calc_action_signal(signal, stage, '', [])
        assert result == expected, f'sig={signal}, stage={stage} → {result!r}, expected {expected!r}'


# ═══════════════════════════════════════════════════════
# _calc_action_priority 测试 — 严格对应旧 _make_item_action
# ═══════════════════════════════════════════════════════

class TestCalcActionPriority:

    @pytest.mark.parametrize('signal,stage,expected', [
        ('buy',  '上行',   '高'),
        ('sell', '上行',   '高'),
        ('hold', '加速',   '中'),
        ('hold', '缩量整理','中'),
        ('hold', '上行',   '低'),
        ('hold', '滞涨',   '高'),
        ('hold', '转弱',   '高'),
        ('hold', '区间底部','中'),
        ('hold', '区间顶部','高'),
        ('hold', '区间中段','低'),
        ('hold', '下行',   '中'),  # 默认
    ])
    def test_priority(self, signal, stage, expected):
        result = _calc_action_priority(signal, stage, '')
        assert result == expected


# ═══════════════════════════════════════════════════════
# _calc_action_reason 测试 — 严格对应旧 _make_item_action
# ═══════════════════════════════════════════════════════

class TestCalcActionReason:

    def test_sell_signal(self):
        result = _calc_action_reason('sell', '上涨趋势', '上行', '', [], '')
        assert result == '上涨趋势·上行'

    def test_buy_signal(self):
        result = _calc_action_reason('buy', '上涨趋势', '上行', '', [], '缩量回踩')
        assert result == '上涨趋势·上行'

    def test_hold_stage_up(self):
        result = _calc_action_reason('hold', '上涨趋势', '上行', '', [], '')
        assert result == '上涨趋势·上行，趋势健康'

    def test_hold_stage_accelerate(self):
        result = _calc_action_reason('hold', '上涨趋势', '加速', '', [], '')
        assert '加速' in result
        assert '放量滞涨' in result

    def test_hold_stage_bottom(self):
        result = _calc_action_reason('hold', '区间震荡', '区间底部', '', [], '')
        assert '区底企稳' in result


# ═══════════════════════════════════════════════════════
# A/B 对比测试：验证新函数 = 旧 _make_item_action 对所有场景一致
# ═══════════════════════════════════════════════════════

class TestABCompatibility:

    def _old_make_item_action(self, item_sig, item_stage, item_struct, buy_point=''):
        """旧 _make_item_action 的精确还原（git show HEAD~2 版本，无 fusion 优先）"""
        if item_sig == 'sell':
            return ('卖出', '', f'{item_struct}·{item_stage}', '高')
        elif item_sig == 'buy':
            bp = buy_point or '买点'
            return ('买入', bp, f'{item_struct}·{item_stage}', '高')
        elif item_stage == '加速':
            return ('持有', '关注止盈', f'{item_struct}·{item_stage}，关注放量滞涨/加速变缓', '中')
        elif item_stage == '缩量整理':
            return ('持有', '可加仓', f'{item_struct}·{item_stage}，供应枯竭等待放量', '中')
        elif item_stage == '上行':
            return ('持有', '', f'{item_struct}·{item_stage}，趋势健康', '低')
        elif item_stage == '滞涨':
            return ('减仓', '警惕滞涨', f'{item_struct}·{item_stage}，EMA10走平', '高')
        elif item_stage == '转弱':
            return ('换股', '关注转弱', f'{item_struct}·{item_stage}，EMA10拐头向下', '高')
        elif item_stage == '区间底部':
            return ('加仓', '支撑位', f'{item_struct}·{item_stage}，区底企稳', '中')
        elif item_stage == '区间顶部':
            return ('减仓', '压力位', f'{item_struct}·{item_stage}，区顶受阻', '高')
        elif item_stage == '区间中段':
            return ('持有', '', f'{item_struct}·{item_stage}，方向未明', '低')
        else:
            return ('持有', '', f'{item_struct}·{item_stage}', '中')

    # 所有信号+阶段组合
    _ALL_SIGNALS = ['sell', 'buy', 'hold']
    _ALL_STAGES = ['上行', '加速', '缩量整理', '滞涨', '转弱',
                   '区间底部', '区间顶部', '区间中段', '下行', '下跌', '--']
    _ALL_STRUCTURES = ['上涨趋势', '区间震荡', '下降趋势']

    def test_all_combinations(self):
        """对所有信号×阶段×结构组合，验证新函数输出=旧函数输出"""
        errors = []
        for sig in self._ALL_SIGNALS:
            for stage in self._ALL_STAGES:
                for struct in self._ALL_STRUCTURES:
                    old = self._old_make_item_action(sig, stage, struct)
                    new_at = _calc_action_type(sig, stage, '')
                    new_sig = _calc_action_signal(sig, stage, '', [])
                    new_pri = _calc_action_priority(sig, stage, '')
                    new_reason = _calc_action_reason(sig, struct, stage, '', [], '')
                    old_ok = (old[0] == new_at and old[1] == new_sig
                              and old[2] == new_reason and old[3] == new_pri)
                    if not old_ok:
                        errors.append(
                            f'  sig={sig}, stage={stage}, struct={struct}\n'
                            f'    old: ({old[0]}, {old[1]!r}, {old[2][:30]}, {old[3]})\n'
                            f'    new: ({new_at}, {new_sig!r}, {new_reason[:30]}, {new_pri})')
        assert not errors, f'不匹配的场景:\n' + '\n'.join(errors[:10])

    def test_reason_with_buy_point(self):
        """买点信号时 reason 不含 buy_point（与旧逻辑一致）"""
        old = self._old_make_item_action('buy', '上行', '上涨趋势', buy_point='缩量回踩')
        new_reason = _calc_action_reason('buy', '上涨趋势', '上行', '', [], '缩量回踩')
        assert old[2] == new_reason
        assert new_reason == '上涨趋势·上行'
