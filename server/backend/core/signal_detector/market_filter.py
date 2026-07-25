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
    if not bias20:
        bias20 = market_cycle.get('deviation_pct', 0) or 0

    valley_confirmed = position in ('偏波谷', '波谷', '波谷偏多') or vl >= 4

    # 下降趋势且尚未形成明确波谷，按主跌风险处理。波谷修复不能被
    # vl_score>=4 误判为“休息”，否则会与“波谷重仓”直接冲突。
    if (structure == '下降趋势' or position == '下降趋势') and not valley_confirmed:
        return {
            'filter': 'rest',
            'risk_phase': 'main_decline',
            'reason': '下降趋势尚未形成明确波谷，按主跌风险处理，暂停新增仓位',
            'max_position': None,
        }

    # 波峰/严重正乖离是风险升高，不设固定仓位上限。
    if position in ('偏波峰', '波峰', '波峰偏多') or pk >= 4:
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
