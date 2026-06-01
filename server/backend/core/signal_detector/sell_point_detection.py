"""
卖点检测 — 基于向下信号的独立卖点判定

《量价原理》5.6节 + 5.7节框架：
  向下突破、向下反转、需求衰竭 → 在对应的关键点位置 → 卖出信号

卖点规则优先级：
  1. 向下突破（区间震荡→破位）：最强烈的卖出信号
  2. 向下反转（上涨趋势→不再创新高+放量长阴）：趋势逆转
  3. 需求衰竭（加速末端/缩量滞涨）：波峰预警
  4. 结构卖出（下降趋势/转弱/滞涨）：静态卖出
"""

from typing import List, Dict, Optional
from backend.core.signal_detector import (
    detect_downward_breakout,
    detect_downward_reversal,
    detect_demand_exhaustion,
    SIGNAL_NAMES,
)
from backend.core.ema_utils import get_structure, get_stage


def detect_sell_point(klines: List[Dict], idx: int,
                      structure: str = '', stage: str = '',
                      bias5: float = 0) -> Dict:
    """
    卖点检测主逻辑

    Returns:
        {'triggered': bool, 'sell_type': str, 'confidence': int,
         'reason': str, 'signal': str, 'score': 0-100}
    """
    if not klines or len(klines) < 20 or idx < 0:
        return {'triggered': False, 'sell_type': '', 'confidence': 0,
                'reason': '数据不足', 'signal': '', 'score': 0}

    closes = [k['close'] for k in klines[:idx + 1]]
    struct = structure or (get_structure(closes) or '')
    stg = stage or (get_stage(closes) or '')

    # ── 规则1: 向下突破（最强烈）──
    try:
        dd = detect_downward_breakout(klines, idx)
        if dd.get('triggered') and dd.get('confidence', 0) >= 60:
            return {
                'triggered': True,
                'sell_type': '下降突破',
                'confidence': min(90, int(dd.get('confidence', 60))),
                'reason': f'区间跌破前低+放量长阴 — {dd.get("detail","")}',
                'signal': '卖出',
                'score': min(90, int(dd.get('confidence', 60))),
            }
    except Exception:
        pass

    # ── 规则2: 向下反转（上涨趋势末端）──
    try:
        dr = detect_downward_reversal(klines, idx)
        if dr.get('triggered') and dr.get('confidence', 0) >= 65:
            return {
                'triggered': True,
                'sell_type': '高位反转向下',
                'confidence': min(80, int(dr.get('confidence', 65))),
                'reason': f'上涨趋势中不再创新高+放量长阴 — {dr.get("detail","")}',
                'signal': '卖出',
                'score': min(80, int(dr.get('confidence', 65))),
            }
    except Exception:
        pass

    # ── 规则3: 需求衰竭（波峰预警）──
    try:
        de = detect_demand_exhaustion(klines, idx)
        if de.get('triggered') and de.get('confidence', 0) >= 75:
            # 只在高分时使用
            return {
                'triggered': True,
                'sell_type': '需求衰竭',
                'confidence': min(75, int(de.get('confidence', 75))),
                'reason': f'上涨末端加速/缩量滞涨 — {de.get("detail","")}',
                'signal': '卖出',
                'score': min(75, int(de.get('confidence', 75))),
            }
    except Exception:
        pass

    # ── 规则4: 结构卖出（静态）──
    if struct == '下降趋势':
        return {
            'triggered': True,
            'sell_type': '趋势卖出',
            'confidence': 70,
            'reason': f'下降趋势中，卖出避险',
            'signal': '卖出',
            'score': 70,
        }
    if stg in ('转弱', '滞涨'):
        return {
            'triggered': True,
            'sell_type': f'{stg}卖出',
            'confidence': 55,
            'reason': f'{stg}阶段，趋势转弱',
            'signal': '卖出',
            'score': 55,
        }

    # ── 规则5: BIAS高位卖出 ──
    if bias5 > 15:
        return {
            'triggered': True,
            'sell_type': '乖离率过高',
            'confidence': 50,
            'reason': f'BIAS5={bias5:.1f}%，严重超买，注意回调风险',
            'signal': '卖出',
            'score': 50,
        }

    return {'triggered': False, 'sell_type': '', 'confidence': 0,
            'reason': '', 'signal': '', 'score': 0}
