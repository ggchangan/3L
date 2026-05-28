#!/usr/bin/env python3
"""EMA辅助函数 — 转发层，从 threel_core 导入

3l-core 迁移期间保持向后兼容。
所有逻辑实现在 /home/ubuntu/3l-core/threel_core/ema_utils.py
"""
from threel_core.ema_utils import (  # noqa: F401
    ema_list,
    get_ema_arrangement,
    get_structure,
    get_stage,
    _reg_slope,
    get_mainline_level,
)
