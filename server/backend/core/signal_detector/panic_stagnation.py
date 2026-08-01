"""恐慌买点：下降末端或区间底部的“天量滞跌”。

知识库《交易训练营第三期：如何判断恐慌》约束：
1. 恐慌发生在供应占优或弱平衡背景，通常是缓跌后急跌；
2. 成交量必须达到天量，说明供应集中释放且有需求承接；
3. 价格不能以最低点收盘，锤头、小实体或收回日内跌幅体现滞跌；
4. 上升趋势高位的放量长阴是供需转坏，不是恐慌买点。
"""
from typing import Dict, List

from .base import calc_volume_ratio, make_result, SignalResult

MIN_HISTORY = 30
MIN_VOLUME_RATIO_20 = 1.60
MIN_INTRADAY_DROP = -0.04


def _failed(detail: str, scores: Dict) -> SignalResult:
    return make_result(False, 0, '恐慌滞跌', 'panic_stagnation', detail, scores)


def detect_panic_stagnation(klines: List[Dict], idx: int = -1) -> SignalResult:
    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < MIN_HISTORY:
        return _failed('数据不足', {})

    today, yesterday = data[-1], data[-2]
    close = float(today['close'])
    prev_close = float(yesterday['close'])
    high = float(today['high'])
    low = float(today['low'])
    open_ = float(today['open'])
    day_range = high - low
    scores: Dict = {}

    # 结构：此前已有调整，且本日发生在20日低位附近。
    background_start = float(data[-15]['close'])
    background_loss = (prev_close - background_start) / (background_start or 1)
    prior_20_low = min(float(k['low']) for k in data[-21:-1])
    near_bottom = low <= prior_20_low * 1.03
    breaks_low = low < prior_20_low
    scores.update({
        'background_loss_pct': round(background_loss * 100, 2),
        'near_20d_low': near_bottom,
        'breaks_20d_low': breaks_low,
    })
    if not near_bottom or not (background_loss <= -0.03 or breaks_low):
        return _failed('不在下降末端或区间底部', scores)

    # 急跌：用日内最低价相对昨收衡量，允许锤头最终收回甚至翻红。
    intraday_drop = (low - prev_close) / (prev_close or 1)
    close_change = (close - prev_close) / (prev_close or 1)
    scores.update({
        'intraday_drop_pct': round(intraday_drop * 100, 2),
        'close_change_pct': round(close_change * 100, 2),
    })
    if intraday_drop > MIN_INTRADAY_DROP:
        return _failed(f'未出现急跌(日内最低仅{intraday_drop:.1%})', scores)

    # 天量：相对过去20日显著放量，且接近/超过此前20日最大成交量。
    vr20 = calc_volume_ratio(data, len(data) - 1, 20)
    current_volume = float(today.get('volume', 0) or 0)
    prior_max_volume = max(float(k.get('volume', 0) or 0) for k in data[-21:-1])
    volume_vs_max = current_volume / prior_max_volume if prior_max_volume else 0
    scores.update({
        'volume_ratio_20': round(vr20, 3),
        'volume_vs_prior_20d_max': round(volume_vs_max, 3),
        'volume_definition': '天量=20日量比≥1.60且不低于此前20日最大量的95%',
    })
    if vr20 < MIN_VOLUME_RATIO_20 or volume_vs_max < 0.95:
        return _failed(f'未达到天量(20日量比{vr20:.2f}，前高量{volume_vs_max:.2f}倍)', scores)

    # 滞跌：不能收在最低点；高收、锤头或小实体任一成立。
    close_position = (close - low) / day_range if day_range > 0 else 0
    body_ratio = abs(close - open_) / day_range if day_range > 0 else 1
    lower_shadow = min(open_, close) - low
    lower_shadow_ratio = lower_shadow / day_range if day_range > 0 else 0
    high_close = close_position >= 0.50
    hammer = lower_shadow_ratio >= 0.35
    small_body = body_ratio <= 0.25
    scores.update({
        'close_position': round(close_position, 3),
        'body_ratio': round(body_ratio, 3),
        'lower_shadow_ratio': round(lower_shadow_ratio, 3),
        'stagnation_shape': '高位收盘' if high_close else '锤头线' if hammer else '小实体' if small_body else '',
    })
    if close_position < 0.15 or not (high_close or hammer or small_body):
        return _failed('天量但未滞跌（仍接近日内最低或无承接形态）', scores)

    volume_score = min(100, 70 + (vr20 - MIN_VOLUME_RATIO_20) * 20)
    speed_score = min(100, 70 + abs(intraday_drop - MIN_INTRADAY_DROP) * 500)
    stagnation_score = min(100, 55 + close_position * 35
                           + (15 if hammer else 0) + (10 if small_body else 0))
    context_score = min(100, 65 + abs(min(background_loss, 0)) * 300)
    confidence = (volume_score * 0.35 + speed_score * 0.20
                  + stagnation_score * 0.30 + context_score * 0.15)
    scores.update({
        'volume': round(volume_score, 1),
        'panic_speed': round(speed_score, 1),
        'stagnation': round(stagnation_score, 1),
        'context': round(context_score, 1),
    })
    detail = (f'天量{vr20:.2f}倍，日内急跌{intraday_drop:.1%}后滞跌，'
              f'{scores["stagnation_shape"]}，收盘位置{close_position:.0%}')
    return make_result(True, round(confidence, 1), '恐慌滞跌',
                       'panic_stagnation', detail, scores)
