"""3L 买卖点统一契约。

知识库原则：
- 只在关键点和关键信号交易；
- 上涨中继只发生在上涨趋势中；
- 区间震荡只重点交易区间顶部/底部：区顶不突破是卖点，区顶有效突破
  才是突破买点；区底获得支撑是买点，区底跌破是卖点；
- 恐慌买点是天量滞跌，只能出现在下降趋势末端或区间底部附近。

本模块只处理“语义门禁”和字段归一，不直接读取行情数据。
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple


BUY_POINT_BY_SIGNAL = {
    'upward_breakout': '突破买点',
    'upward_continuation': '中继买点',
    'upward_reversal': '反转买点',
    'panic_stagnation': '恐慌买点',
}

BUY_POINT_CATEGORY_LABELS = {
    'breakout': '突破买点',
    'continuation': '中继/回踩买点',
    'range_support': '区底支撑买点',
    'reversal': '反转买点',
    'panic': '恐慌买点（天量滞跌）',
    'unknown': '未识别买点',
}


def _norm_structure(structure: str) -> str:
    if structure == '上升趋势':
        return '上涨趋势'
    return structure or ''


def classify_buy_point(item: Dict) -> str:
    """把买点文案和结构化量价信号归一到 3L 买点类别。

    注意：`continuation` 特指上涨趋势里的中继/趋势回踩；区间底部支撑
    单独归为 `range_support`，避免把区间低吸错误显示为上涨中继。
    """
    bullish_signals = [
        signal for signal in item.get('triggered_signals', [])
        if signal.get('direction') == 'bullish'
    ]
    signal_keys = {
        str(signal.get('key') or signal.get('signal_key') or '')
        for signal in bullish_signals
    }
    signal_names = ' '.join(str(signal.get('name', '')) for signal in bullish_signals)
    text = ' '.join(str(item.get(key, '') or '') for key in (
        'buy_point', 'signal', 'fusion_reason',
    )) + ' ' + signal_names
    structure = _norm_structure(item.get('structure', ''))
    stage = item.get('stage', '')

    if item.get('trading_system') == 'trend' and any(
        token in text for token in ('BIAS5乖离率买入', 'BIAS10乖离率买入', '乖离率买入')
    ):
        return 'continuation'
    if 'panic_stagnation' in signal_keys or '恐慌' in text:
        return 'panic'
    if 'upward_reversal' in signal_keys or any(token in text for token in ('向上反转', '明确反转', '反转买点')):
        return 'reversal'
    if 'upward_breakout' in signal_keys or '突破' in text:
        return 'breakout'
    if structure == '区间震荡' and stage == '区间底部':
        return 'range_support'
    if 'upward_continuation' in signal_keys or any(token in text for token in ('中继', '回踩')):
        return 'continuation'
    if '区间底部' in text:
        return 'range_support'
    return 'unknown'


def _panic_or_reversal_evidence(signals: Iterable[Dict]) -> bool:
    for signal in signals or []:
        scores = signal.get('scores') or {}
        key = signal.get('key')
        if key == 'upward_reversal' and float(scores.get('drawdown_pct', 0) or 0) <= -7:
            return True
        if key == 'panic_stagnation':
            if (
                bool(scores.get('near_20d_low'))
                and (
                    float(scores.get('background_loss_pct', 0) or 0) <= -3
                    or bool(scores.get('breaks_20d_low'))
                )
            ):
                return True
    return False


def is_buy_item_allowed_by_structure(item: Dict) -> Tuple[bool, str, str]:
    """判断一个完整买点 item 是否符合 3L 结构/阶段语义。

    Returns:
        (allowed, reason, category)
    """
    category = classify_buy_point(item)
    buy_point = str(item.get('buy_point', '') or '')
    structure = _norm_structure(item.get('structure', ''))
    stage = item.get('stage', '')
    triggered_signals = item.get('triggered_signals', [])
    if not buy_point and category == 'unknown':
        return True, '', category
    # 兼容 threel_core 旧命名：盈利模式1/2 是已经由旧检测器确认的
    # 买点事实；在当前契约里不重新解释其结构语义，交给 fusion 再结合
    # 关键点决定是否可执行。
    if str(buy_point).startswith('盈利模式'):
        return True, '旧3L盈利模式买点，保留技术事实并进入融合判定', category

    if category == 'breakout':
        structure = _norm_structure(structure)
        if structure == '上涨趋势' or (structure == '区间震荡' and stage in ('区间顶部', '突破位')):
            return True, '突破买点位于上涨趋势或区间顶部有效突破位置', category
        return False, '突破买点需来自上涨趋势或区间顶部有效突破', category

    if category == 'continuation':
        structure = _norm_structure(structure)
        if structure == '上涨趋势':
            return True, '上涨中继买点位于上涨趋势缩量回踩位置', category
        return False, '中继/回踩买点只能位于上涨趋势，区间顶部或下降趋势不成立', category

    if category == 'range_support':
        structure = _norm_structure(structure)
        if structure == '区间震荡' and stage == '区间底部':
            return True, '区间底部获得支撑，属于区底支撑买点', category
        return False, '区底支撑买点只能位于区间底部', category

    if category in ('reversal', 'panic'):
        if (
            _norm_structure(structure) == '下降趋势'
            or (structure == '区间震荡' and stage == '区间底部')
            or _panic_or_reversal_evidence(triggered_signals or [])
        ):
            return True, '反转/恐慌买点具备下降末端或区间底部证据', category
        return False, '反转/恐慌买点需位于下降末端或区间底部附近', category

    return False, '无法将当前信号确认为3L买点', category


def is_buy_point_allowed_by_structure(
    buy_point: str,
    structure: str,
    stage: str,
    *,
    triggered_signals: Iterable[Dict] | None = None,
) -> Tuple[bool, str, str]:
    """兼容旧调用：只传买点文案、结构和阶段。"""
    return is_buy_item_allowed_by_structure({
        'buy_point': buy_point,
        'structure': structure,
        'stage': stage,
        'triggered_signals': list(triggered_signals or []),
    })


def is_bullish_signal_allowed_at_keypoint(signal_key: str, structure: str, stage: str) -> bool:
    """过滤与关键点语义冲突的看多量价信号。"""
    if not structure and not stage:
        return True
    category = classify_buy_point({
        'buy_point': BUY_POINT_BY_SIGNAL.get(signal_key, ''),
        'structure': structure,
        'stage': stage,
        'triggered_signals': [{'key': signal_key, 'direction': 'bullish'}],
    })
    allowed, _, _ = is_buy_point_allowed_by_structure(
        BUY_POINT_BY_SIGNAL.get(signal_key, ''),
        structure,
        stage,
        triggered_signals=[{'key': signal_key, 'direction': 'bullish'}],
    )
    if category == 'unknown':
        return False
    return allowed


def annotate_keypoint_permission(signal: Dict, structure: str, stage: str) -> Dict:
    """给量价信号补充关键点门禁结果，保留技术事实但阻止越权执行。"""
    if signal.get('direction') != 'bullish':
        return {**signal, 'keypoint_allowed': True, 'keypoint_reject_reason': ''}
    buy_point = BUY_POINT_BY_SIGNAL.get(signal.get('key', ''), '')
    allowed, reason, category = is_buy_point_allowed_by_structure(
        buy_point,
        structure,
        stage,
        triggered_signals=[signal],
    )
    return {
        **signal,
        'keypoint_allowed': allowed,
        'keypoint_reject_reason': '' if allowed else reason,
        'buy_point_category': category,
    }
