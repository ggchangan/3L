"""
信号检测器 — 基于 3L《量价原理》5.6 关键信号 六大量价信号
每个信号按原文量价语言逐条编码，独立检测，输出触发信号+置信度
"""
from .upward_breakout import detect_upward_breakout
from .downward_breakout import detect_downward_breakout
from .upward_continuation import detect_upward_continuation
from .downward_continuation import detect_downward_continuation
from .range_continuation import detect_range_continuation
from .upward_reversal_detector import detect_upward_reversal
from .downward_reversal import detect_downward_reversal
from .demand_exhaustion import detect_demand_exhaustion
from .supply_exhaustion import detect_supply_exhaustion

__all__ = [
    'detect_upward_breakout',
    'detect_downward_breakout',
    'detect_upward_continuation',
    'detect_downward_continuation',
    'detect_range_continuation',
    'detect_upward_reversal',
    'detect_downward_reversal',
    'detect_demand_exhaustion',
    'detect_supply_exhaustion',
]

SIGNAL_NAMES = {
    'upward_breakout': '向上突破',
    'downward_breakout': '向下突破',
    'upward_continuation': '上涨中继',
    'downward_continuation': '下跌中继',
    'range_continuation': '区间震荡中继',
    'upward_reversal': '向上反转',
    'downward_reversal': '向下反转',
    'demand_exhaustion': '需求衰竭',
    'supply_exhaustion': '供应衰竭',
}
