#!/usr/bin/env python3
"""趋势交易系统 — 转发层，从 threel_core 导入

3l-core 迁移期间保持向后兼容。
所有逻辑实现在 /home/ubuntu/3l-core/threel_core/trend_trading.py
"""
from threel_core.trend_trading import (  # noqa: F401
    ema_slope,
    is_5day_trend,
    is_10day_trend,
    get_bias5_zone,
    get_bias10_zone,
    check_stop_loss,
    check_trailing_take_profit,
    check_trend_type,
    is_smooth_trend,
    _load_manual_trend,
    MANUAL_TREND_PATH,
    decide_system,
    decide_system_with_detail,
    detect_trend_buy,
    simulate_trend_trade,
    scan_trend_buys,
    check_trend_stock_v2,
)
