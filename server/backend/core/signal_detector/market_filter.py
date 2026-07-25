"""3L 大盘风险门禁。

市场强弱决定买点与交易节奏；这里只判断是否处于需要暂停新增仓位
或优先控风险的阶段，不再给出静态目标仓位。
"""

from typing import Dict


def get_market_filter(market_cycle: Dict) -> Dict:
    """返回风险门禁，保留 ``filter`` 字段兼容现有交易计划。"""
    position = market_cycle.get('position', '波中')
    pk = market_cycle.get('pk_score', 0) or 0
    vl = market_cycle.get('vl_score', 0) or 0
    bias20 = market_cycle.get('bias20', 0) or 0
    structure = market_cycle.get('structure', '')
    algorithm_version = market_cycle.get('algorithm_version', '')
    wave_side = market_cycle.get('wave_side', 'none')
    wave_phase = market_cycle.get('wave_phase', 'none')
    evidence = market_cycle.get('evidence') or {}
    context = market_cycle.get('context') or {}
    if not bias20:
        bias20 = market_cycle.get('deviation_pct', 0) or 0

    if algorithm_version == 'supply_demand_v3':
        valley_confirmed = wave_side == 'valley' and wave_phase in ('biased', 'confirmed')
        main_decline = (
            structure == '下降趋势'
            and context.get('decline_context', 0) >= 45
            and evidence.get('supply_entry', 0) >= 55
            and not valley_confirmed
        )
        peak_risk = wave_side == 'peak' and wave_phase in ('biased', 'confirmed')
    else:
        valley_confirmed = position in ('偏波谷', '波谷', '波谷偏多') or vl >= 4
        main_decline = (structure == '下降趋势' or position == '下降趋势') and not valley_confirmed
        peak_risk = position in ('偏波峰', '波峰', '波峰偏多') or pk >= 4

    # 弱势结构不等于主跌。V3 还要求下降过程仍在、供应继续有效进入；
    # 兼容旧调用时保留原判定，避免缺少供需字段时静默放松门禁。
    if main_decline:
        return {
            'filter': 'rest',
            'risk_phase': 'main_decline',
            'reason': '下降过程仍在且供应继续占优，按主跌风险处理，暂停新增仓位',
            'max_position': None,
        }

    # 波峰/严重正乖离是风险升高，不设固定仓位上限。
    if peak_risk:
        return {
            'filter': 'reduce',
            'risk_phase': 'risk_rising',
            'reason': f'大盘接近波峰(pk={pk})，不追高并优先兑现风险持仓',
            'max_position': None,
        }
    if bias20 > 12:
        return {
            'filter': 'reduce',
            'risk_phase': 'risk_rising',
            'reason': f'BIAS20={bias20:.1f}%，严重超买，不追高并收紧止盈',
            'max_position': None,
        }

    if valley_confirmed:
        return {
            'filter': 'normal',
            'risk_phase': 'valley_recovery',
            'reason': f'大盘形成明确波谷(vl={vl})，仅随有效个股买点逐步增加仓位',
            'max_position': None,
        }

    return {
        'filter': 'normal',
        'risk_phase': 'normal',
        'reason': '未识别主跌或波峰风险，继续关注方向和个股买卖点',
        'max_position': None,
    }
