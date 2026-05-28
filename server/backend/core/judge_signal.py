#!/usr/bin/env python3
"""
3L个股操作信号判断模块

基于 6.6持股模板 + 6.7回避模板
判断规则详见 SKILL.md
"""


def judge_signal(structure: str, stage: str = '', buy_point: str = '') -> tuple:
    """
    判断操作信号

    Args:
        structure: 结构 - '上涨趋势' / '区间震荡' / '下降趋势'
        stage: 阶段 - '上行' / '加速' / '滞涨' / '缩量整理' / '转弱' / '下行' / '加速跌' / '转强' / '区间顶部' / '区间中段' / '区间底部'
        buy_point: 买点描述 - 包含'突破买点'或'中继买点'时视为买入信号

    Returns:
        (signal_code, signal_text, css_class)
        signal_code: 'buy' / 'hold' / 'sell'
        signal_text: 中文说明
        css_class: 'warn' / 'hold' / 'danger'
    """
    # 优先级1: 卖出（回避模板）
    if structure == '下降趋势':
        return ('sell', '❌ 卖出 · 下降趋势（回避模板①）', 'danger')
    if structure == '区间震荡' and stage in ('区间顶部',):
        return ('sell', '❌ 卖出 · 区间顶部向下突破风险（回避模板②）', 'danger')
    if structure == '上涨趋势' and stage == '加速':
        return ('sell', '❌ 卖出 · 加速后兑现压力（回避模板③）', 'danger')

    # 优先级2: 买入（买点条件）
    if buy_point and ('突破买点' in buy_point or '中继买点' in buy_point or '回踩买点' in buy_point):
        return ('buy', '⚡ 买入 · 符合买点条件', 'warn')

    # 优先级3: 持有（持股模板）
    return ('hold', '✅ 持有 · 符合持股模板', 'hold')


def build_holdings_review(holdings_data: list) -> list:
    """
    对持仓数据批量生成操作信号

    Args:
        holdings_data: 含 code/name/sector/structure/stage/buy_point/price/change 的字典列表

    Returns:
        添加了 signal/signal_text/css_class 字段的列表，已按结构排序
    """
    result = []
    for h in holdings_data:
        code, code_signal, code_text, css = judge_signal(
            structure=h.get('structure', ''),
            stage=h.get('stage', ''),
            buy_point=h.get('buy_point', h.get('action', '')),
        )
        result.append({
            **h,
            'signal': code_signal,
            'signal_text': code_text,
            'css_class': css,
        })

    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}
    result.sort(key=lambda x: struct_priority.get(x.get('structure', ''), 3))
    return result
