from backend.core.keypoint_context import build_keypoint_context
from backend.services.stock_card_service import _can_promote_detected_buy_point


def _row(date, open_, high, low, close, volume):
    return {
        'date': date,
        'open': open_,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume,
    }


def test_keypoint_context_marks_range_top_volume_down_as_failed_breakout():
    klines = [
        _row('20260720', 100, 104, 99, 103, 120000),
        _row('20260721', 103, 105, 101, 104, 130000),
        _row('20260722', 104, 106, 102, 105, 125000),
        _row('20260723', 105, 108, 103, 107, 150000),
        _row('20260724', 107, 109, 104, 106, 160000),
        _row('20260727', 106, 107, 98, 99, 190000),
        _row('20260728', 99, 101, 94, 96, 175000),
        _row('20260729', 96, 99, 92, 95, 150000),
        _row('20260730', 95, 98, 88.72, 92, 140000),
        _row('20260731', 92, 97, 90, 96, 110000),
        _row('20260803', 96, 101, 95, 100, 130000),
        _row('20260804', 100, 106, 99, 104, 150000),
        _row('20260805', 104, 109, 103, 108, 165000),
        _row('20260806', 108, 112, 106, 110, 170000),
        _row('20260807', 106.87, 113.3, 106.02, 111.68, 131702),
        _row('20260810', 115.13, 115.13, 105.28, 110.27, 161458),
        _row('20260811', 110.84, 118.5, 110.5, 115.49, 193308),
        _row('20260812', 114.36, 118.78, 113.58, 116.02, 106596),
        _row('20260813', 118.37, 122.59, 115.1, 118.7, 156062),
        _row('20260814', 119.0, 123.8, 117.0, 123.0, 198824),
        _row('20260817', 122.45, 123.6, 120.0, 123.24, 148669),
        _row('20260818', 122.22, 122.89, 115.0, 116.92, 227188),
    ]

    context = build_keypoint_context(
        klines,
        structure='区间震荡',
        stage='区间顶部',
    )

    assert context['current_zone']['type'] == 'near_resistance'
    assert context['volume_price_action']['type'] == 'volume_down'
    assert context['volume_price_action']['day_volume_ratio'] == 1.53
    assert context['supply_demand_keypoint']['type'] == 'failed_breakout'
    assert context['supply_demand_keypoint']['direction'] == 'bearish'


def test_keypoint_context_marks_uptrend_shrink_pullback_as_continuation():
    klines = []
    close = 100.0
    for i in range(35):
        date = f'202607{i + 1:02d}'
        close += 1.0
        klines.append(_row(date, close - 0.5, close + 1, close - 1, close, 100000 + i * 1000))
    klines.extend([
        _row('20260810', 135.0, 136.0, 132.0, 133.0, 85000),
        _row('20260811', 133.0, 134.0, 131.8, 132.6, 65000),
    ])

    context = build_keypoint_context(
        klines,
        structure='上涨趋势',
        stage='缩量整理',
    )

    assert context['current_zone']['type'] == 'trend_pullback'
    assert context['volume_price_action']['type'] == 'shrink_pullback'
    assert context['supply_demand_keypoint']['type'] == 'continuation'
    assert context['supply_demand_keypoint']['direction'] == 'bullish'


def test_rejected_bullish_signal_cannot_promote_to_official_buy_point():
    assert _can_promote_detected_buy_point(
        'keypoint_rejected_bullish',
        [{'key': 'upward_continuation', 'direction': 'bullish', 'keypoint_allowed': False}],
    ) is False
    assert _can_promote_detected_buy_point(
        'signal_buy',
        [{'key': 'upward_continuation', 'direction': 'bullish', 'keypoint_allowed': True}],
    ) is True
