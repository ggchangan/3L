from backend.core.trade_signal_contract import (
    classify_buy_point,
    is_bullish_signal_allowed_at_keypoint,
    is_buy_point_allowed_by_structure,
)


def test_uptrend_continuation_is_allowed_only_in_uptrend():
    allowed, reason, category = is_buy_point_allowed_by_structure(
        '中继买点', '上涨趋势', '上行'
    )

    assert allowed is True
    assert category == 'continuation'
    assert '上涨趋势' in reason


def test_range_top_rejects_continuation_buy_point():
    allowed, reason, category = is_buy_point_allowed_by_structure(
        '中继买点', '区间震荡', '区间顶部'
    )

    assert allowed is False
    assert category == 'continuation'
    assert '只能位于上涨趋势' in reason


def test_range_top_allows_breakout_buy_point():
    allowed, reason, category = is_buy_point_allowed_by_structure(
        '突破买点', '区间震荡', '区间顶部'
    )

    assert allowed is True
    assert category == 'breakout'
    assert '有效突破' in reason


def test_range_bottom_is_range_support_not_uptrend_continuation():
    category = classify_buy_point({
        'buy_point': '区间底部获得支撑',
        'structure': '区间震荡',
        'stage': '区间底部',
        'triggered_signals': [],
    })

    assert category == 'range_support'


def test_panic_buy_point_is_rejected_at_range_top():
    allowed, reason, category = is_buy_point_allowed_by_structure(
        '恐慌买点', '区间震荡', '区间顶部',
        triggered_signals=[{'key': 'panic_stagnation', 'direction': 'bullish'}],
    )

    assert allowed is False
    assert category == 'panic'
    assert '下降末端或区间底部' in reason


def test_bullish_signal_filter_uses_keypoint_contract():
    assert is_bullish_signal_allowed_at_keypoint(
        'upward_continuation', '区间震荡', '区间顶部'
    ) is False
    assert is_bullish_signal_allowed_at_keypoint(
        'upward_breakout', '区间震荡', '区间顶部'
    ) is True


def test_keypoint_annotation_preserves_rejected_technical_signal():
    from backend.core.trade_signal_contract import annotate_keypoint_permission

    annotated = annotate_keypoint_permission(
        {'key': 'upward_continuation', 'direction': 'bullish', 'confidence': 75},
        '区间震荡',
        '区间顶部',
    )

    assert annotated['keypoint_allowed'] is False
    assert '只能位于上涨趋势' in annotated['keypoint_reject_reason']
