"""3L 关键点展示契约。

第一类关键点是锚定参考位；第二类关键点才描述供需格局转换。
该模块只统一语义，不把任何图表标记直接升级为买卖指令。
"""

from html import escape

REFERENCE_LABELS = {'前高', '前低', '天量', '地量'}
VOLUME_EVIDENCE_LABELS = {'放↑', '放↓', '缩', '↯', '量'}
TRANSITION_LABELS = {'突', '反', '继↑', '继↓'}
TECHNICAL_SIGNAL_LABELS = {'技买', '技卖'}
DECISION_LABELS = {'买', '卖'}


_CONTRACT = {
    '前高': ('reference', 'neutral', '第一类·前高参考位；是潜在压力锚点，不等于卖点'),
    '前低': ('reference', 'neutral', '第一类·前低参考位；是潜在支撑锚点，不等于买点'),
    '天量': ('reference', 'neutral', '第一类·天量成本聚集区；方向需结合价格结果判断'),
    '地量': ('reference', 'neutral', '第一类·地量供需两弱；需等待需求或供应进入'),
    '放↑': ('volume_evidence', 'bullish', '放量上涨证据；需结合所处关键位置判断'),
    '放↓': ('volume_evidence', 'bearish', '放量下跌证据；需结合所处关键位置判断'),
    '缩': ('volume_evidence', 'neutral', '缩量证据；上升回踩与下降阴跌含义不同'),
    '↯': ('volume_evidence', 'bearish', '放量滞涨证据；提示需求推进效率下降'),
    '量': ('volume_evidence', 'neutral', '异常量能证据；不单独构成方向结论'),
    '突': ('transition', 'bullish', '第二类·向上突破；供需平衡转向需求占优'),
    '反': ('transition', 'bullish', '第二类·向上反转形态；仍需后续需求确认'),
    '继↑': ('transition', 'bullish', '第二类·上涨中继；原上升趋势延续'),
    '继↓': ('transition', 'bearish', '第二类·下跌中继；原下降趋势延续'),
    '买': ('decision', 'bullish', '复盘最终可执行买入标记'),
    '卖': ('decision', 'bearish', '复盘最终可执行卖出标记'),
    '技买': ('technical_signal', 'bullish', '个股技术买点；尚非复盘可执行结论'),
    '技卖': ('technical_signal', 'bearish', '个股技术卖点；尚非复盘可执行结论'),
}


def keypoint_semantics(label):
    """返回稳定的展示语义；未知标签保守视为中性证据。"""
    kind, direction, explanation = _CONTRACT.get(
        label, ('evidence', 'neutral', '量价证据；需结合结构、位置和上下文判断'),
    )
    return {
        'kind': kind,
        'direction': direction,
        'explanation': explanation,
        'is_trade_decision': kind == 'decision',
        'is_executable': kind == 'decision',
    }


def enrich_keypoints(points):
    """为检测结果附加契约字段，同时保持旧字段完全兼容。"""
    result = []
    for point in points or []:
        enriched = dict(point)
        for key, value in keypoint_semantics(enriched.get('label', '')).items():
            enriched.setdefault(key, value)
        result.append(enriched)
    return result


def keypoint_svg_title(point):
    """生成可安全嵌入 SVG <title> 的自解释文本。"""
    explanation = point.get('explanation') or keypoint_semantics(point.get('label', ''))['explanation']
    return escape(str(explanation))
