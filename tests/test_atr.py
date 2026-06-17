"""ATR 计算函数测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import pytest


def test_calc_atr_basic():
    """基本ATR计算：给5根K线算ATR，验证结果"""
    from threel_core.atr import calc_atr
    klines = [
        {'high': 11, 'low': 9,  'close': 10},
        {'high': 12, 'low': 10, 'close': 11},
        {'high': 13, 'low': 11, 'close': 12},
        {'high': 14, 'low': 12, 'close': 13},
        {'high': 15, 'low': 13, 'close': 14},
    ]
    atr = calc_atr(klines, period=3)
    assert atr > 0
    # ATR 应接近 2（每根K线振幅≈2）
    assert abs(atr - 2.0) < 0.5


def test_calc_atr_known_values():
    """使用已知数据的ATR验证：5根K线，period=3"""
    from threel_core.atr import calc_atr
    klines = [
        {'high': 12, 'low': 10, 'close': 11},
        {'high': 13, 'low': 11, 'close': 12},
        {'high': 12, 'low': 10, 'close': 11},
        {'high': 14, 'low': 12, 'close': 13},
        {'high': 13, 'low': 11, 'close': 12},
    ]
    atr = calc_atr(klines, period=3)
    # TRs=[2,2,3,2], 前3平均=2.333, EMA平滑后≈2.222
    assert abs(atr - 2.222) < 0.01


def test_calc_atr_insufficient_data():
    """K线不足period根时返回0"""
    from threel_core.atr import calc_atr
    klines = [{'high': 12, 'low': 10, 'close': 11}]
    atr = calc_atr(klines, period=14)
    assert atr == 0


def test_calc_atr_default_period():
    """默认period=14"""
    from threel_core.atr import calc_atr
    klines = [{'high': i+1, 'low': i, 'close': i+0.5} for i in range(20)]
    atr = calc_atr(klines)
    assert atr > 0
    assert atr < 2


def test_calc_stop_loss_atr():
    """calc_stop_loss ATR模式：cost_price=100, ATR=5 → 止损=90"""
    from threel_core.atr import calc_stop_loss_atr
    sl, sl_pct = calc_stop_loss_atr(cost_price=100, atr=5, cur_price=110)
    assert sl == 90.0
    assert abs(sl_pct - 18.18) < 0.1


def test_calc_stop_loss_atr_no_atr():
    """ATR=0时返回None兜底"""
    from threel_core.atr import calc_stop_loss_atr
    sl, sl_pct = calc_stop_loss_atr(cost_price=100, atr=0, cur_price=110)
    assert sl is None
    assert sl_pct is None


def test_calc_stop_loss_atr_zero_price():
    """cur_price=0时返回None"""
    from threel_core.atr import calc_stop_loss_atr
    sl, sl_pct = calc_stop_loss_atr(cost_price=100, atr=5, cur_price=0)
    assert sl is None
    assert sl_pct is None
