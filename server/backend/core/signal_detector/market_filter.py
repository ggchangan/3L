"""
大盘过滤 — 加速/阴跌阶段嵌入交易计划

《量价原理》简化版大盘作用：
- 加速阶段（BIAS>12% 或 pk≥4）→ 减仓控风险
- 阴跌阶段（下降趋势/持续跌）→ 休息不动
- 其他阶段（波中/波谷）→ 不管大盘，直接看板块和个股
"""

from typing import Dict, Optional


def get_market_filter(market_cycle: Dict) -> Dict:
    """
    判断大盘过滤状态。

    Args:
        market_cycle: 大盘周期判定的结果 dict
            {'pk_score': int, 'vl_score': int, 'position': str,
             'bias20': float, 'position_level': str}

    Returns:
        {'filter': str, 'reason': str, 'max_position': str}
         filter: 'reduce' | 'rest' | 'normal'
         max_position: 建议最大仓位
    """
    # 安全取值
    position = market_cycle.get('position', '波中')
    pk = market_cycle.get('pk_score', 0) or 0
    vl = market_cycle.get('vl_score', 0) or 0
    bias20 = market_cycle.get('bias20', 0) or 0

    # 尝试从其他字段取
    if not bias20:
        bias20 = abs(market_cycle.get('deviation_pct', 0) or 0)

    # 规则1: 加速阶段（波峰+偏多）
    if position in ('波峰', '波峰偏多') or pk >= 4:
        return {
            'filter': 'reduce',
            'reason': f'大盘加速阶段(pk={pk})，减仓控风险，仓位建议5成以下',
            'max_position': '5成',
        }

    if bias20 > 12:
        return {
            'filter': 'reduce',
            'reason': f'BIAS20={bias20:.1f}%，严重超买，减仓控风险',
            'max_position': '5成',
        }

    # 规则2: 阴跌阶段（下降趋势）
    if position in ('下降趋势', '波谷偏空') or vl >= 4:
        return {
            'filter': 'rest',
            'reason': f'大盘阴跌阶段(vl={vl})，休息不动，等待企稳',
            'max_position': '3成',
        }

    if bias20 < -8:
        return {
            'filter': 'rest',
            'reason': f'BIAS20={bias20:.1f}%，严重超卖，等待企稳',
            'max_position': '3成',
        }

    # 规则3: 正常交易
    return {
        'filter': 'normal',
        'reason': '大盘正常，不管大盘，直接看板块和个股',
        'max_position': '8成',
    }
