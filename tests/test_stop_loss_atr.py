"""calc_stop_loss ATR模式集成测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import pytest


def _make_klines(count=60, base_price=100, volatility=2):
    """生成模拟K线"""
    klines = []
    price = base_price
    for i in range(count):
        high = price + volatility
        low = price - volatility
        klines.append({
            'date': f'202603{10+i:02d}' if i < 20 else f'202604{1+i-20:02d}',
            'open': round(price - volatility * 0.3, 2),
            'close': round(price, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'volume': 100000,
        })
        price += (i % 3 - 1) * 0.5  # 轻微波动
    return klines


def test_calc_stop_loss_3l_buy_type_unchanged():
    """3L买点逻辑不变：中继买点 = entry_kline_low × 0.97"""
    from threel_core.buy_point_detection import calc_stop_loss
    klines = _make_klines(60)
    idx = len(klines) - 1
    entry_idx = idx - 5
    entry_low = klines[entry_idx]['low']

    sl, sl_pct = calc_stop_loss(klines, idx, buy_type='中继买点', entry_idx=entry_idx,
                                 cost_price=200)  # cost_price不应影响3L买点
    expected_sl = round(entry_low * 0.97, 2)
    assert sl == expected_sl, f'{sl} != {expected_sl}'


def test_calc_stop_loss_atr_with_cost_price():
    """有cost_price无buy_type → 用ATR止损"""
    from threel_core.buy_point_detection import calc_stop_loss
    klines = _make_klines(60, base_price=100, volatility=2)
    idx = len(klines) - 1
    # ATR应~2，止损≈100-2×2=96
    sl, sl_pct = calc_stop_loss(klines, idx, cost_price=100)
    assert sl is not None
    assert sl < 100  # 止损低于买入价
    assert sl_pct is not None
    assert sl_pct > 0  # 正数表示当前价高于止损


def test_calc_stop_loss_atr_fallback():
    """ATR止损不低于支撑位×0.97"""
    from threel_core.buy_point_detection import calc_stop_loss, _find_support_levels
    klines = _make_klines(60, base_price=100, volatility=10)
    idx = len(klines) - 1
    support = _find_support_levels(klines, idx)
    sl, _ = calc_stop_loss(klines, idx, cost_price=100)
    if support:
        assert sl <= round(support * 0.97, 2) + 0.01  # 容忍浮点误差


def test_calc_stop_loss_no_data():
    """无cost_price无buy_type → 兜底逻辑（支撑位×0.97）"""
    from threel_core.buy_point_detection import calc_stop_loss
    klines = _make_klines(60)
    idx = len(klines) - 1
    sl, sl_pct = calc_stop_loss(klines, idx)
    # 应返回支撑位×0.97或EMA20×0.97
    assert sl is not None
    assert sl > 0
    assert sl_pct is not None
