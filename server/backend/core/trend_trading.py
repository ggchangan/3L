#!/usr/bin/env python3
"""趋势交易系统 — 转发层，从 threel_core 导入

3l-core 迁移期间保持向后兼容。
所有逻辑实现在 /home/ubuntu/3l-core/threel_core/trend_trading.py

多用户隔离：_load_manual_trend 按当前用户读取 manual_trend.json，
并 monkey-patch threel_core 内部引用，使 decide_system 等模块内调用
也走用户路径（无请求上下文时默认 admin）。
"""
import json as _json

import threel_core.trend_trading as _tt
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
    MANUAL_TREND_PATH,
    decide_system,
    decide_system_with_detail,
    detect_trend_buy,
    simulate_trend_trade,
    scan_trend_buys,
    check_trend_stock_v2,
)


def _load_manual_trend():
    """按当前用户加载手动趋势股票列表（覆盖 threel_core 实现）。"""
    from backend.core.config import get_user_config_path
    try:
        with open(get_user_config_path('manual_trend.json')) as f:
            return set(_json.load(f))
    except Exception:
        return set()


# 让 threel_core 内部的 decide_system 等也走用户路径
_tt._load_manual_trend = _load_manual_trend
