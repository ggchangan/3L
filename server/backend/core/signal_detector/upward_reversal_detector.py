"""向上反转信号检测。

反转是个股量价事实，不由市场环境或粗粒度趋势标签决定。检测器只回答
“下降后的需求是否重新占优”；是否执行由复盘决策层另行判断。
"""
from typing import Dict, List

from .base import calc_ema, calc_volume_ratio, make_result, SignalResult

CONFIDENCE_PASS = 60
TREND_LOOKBACK = 25
PANIC_LOOKBACK = 10


def _failed(detail: str, scores: Dict) -> SignalResult:
    return make_result(False, 0, '向上反转', 'upward_reversal', detail, scores)


def detect_upward_reversal(klines: List[Dict], idx: int = -1) -> SignalResult:
    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < TREND_LOOKBACK + 5:
        return _failed('数据不足', {})

    today, yesterday = data[-1], data[-2]
    recent = data[-20:]
    prior = data[-21:-1]
    recent_high = max(float(k['high']) for k in prior)
    recent_lows = [float(k['low']) for k in recent]
    recent_low = min(recent_lows)
    days_since_low = len(recent_lows) - 1 - recent_lows.index(recent_low)
    drawdown = (recent_low - recent_high) / (recent_high or 1)
    scores: Dict = {
        'drawdown_pct': round(drawdown * 100, 2),
        'days_since_low': days_since_low,
    }
    if drawdown > -0.07:
        return _failed(f'下降背景不足(20日最大回撤{drawdown:.1%})', scores)
    if days_since_low > 7 and float(today['close']) > recent_low * 1.12:
        return _failed(f'前期低点距今{days_since_low}日且价格已脱离底部，非下降末端', scores)

    # EMA 只描述此前的下降背景，不要求反转日之后 EMA 仍继续向下。
    closes_before = [float(k['close']) for k in data[:-1]]
    ema10 = calc_ema(closes_before, 10)
    ema_down = len(ema10) >= 3 and ema10[-1] <= ema10[-3]
    scores['trend'] = 100 if ema_down else 60

    day_range = float(today['high']) - float(today['low'])
    close_position = ((float(today['close']) - float(today['low'])) / day_range
                      if day_range > 0 else 0)
    body_ratio = ((float(today['close']) - float(today['open'])) / day_range
                  if day_range > 0 else 0)
    gain_pct = ((float(today['close']) - float(yesterday['close'])) /
                (float(yesterday['close']) or 1))
    prior_low = min(float(k['low']) for k in data[-6:-1])
    makes_new_low = float(today['low']) < prior_low * 0.99
    reclaims_prior_low = float(today['close']) > prior_low
    scores.update({
        'close_position': round(close_position * 100, 1),
        'body_ratio': round(body_ratio, 3),
        'gain_pct': round(gain_pct * 100, 2),
        'makes_new_low': makes_new_low,
        'reclaims_prior_low': reclaims_prior_low,
    })
    if float(today['close']) <= float(today['open']):
        return _failed('反转日未收阳', scores)
    if close_position < 0.50:
        return _failed('反转日未收在振幅中位以上', scores)
    if makes_new_low and not reclaims_prior_low:
        return _failed('创新低后未收复前低', scores)

    vr20 = calc_volume_ratio(data, len(data) - 1, 20)
    vr5 = calc_volume_ratio(data, len(data) - 1, 5)
    prev_volume = float(yesterday.get('volume', 0) or 0)
    today_volume = float(today.get('volume', 0) or 0)
    volume_rule = ''
    if vr20 >= 1.30:
        volume_rule = '20日显著放量'
    elif vr5 >= 1.30 and body_ratio >= 0.50:
        volume_rule = '5日放量长阳'
    elif gain_pct >= 0.07 and body_ratio >= 0.55 and today_volume > prev_volume:
        volume_rule = '强需求长阳且量增'
    scores.update({
        'volume_ratio_20': round(vr20, 3),
        'volume_ratio_5': round(vr5, 3),
        'volume_rule': volume_rule,
    })
    if not volume_rule:
        return _failed(f'需求确认不足(20日量比{vr20:.2f}、5日量比{vr5:.2f})', scores)

    # 反转前允许两种供应背景：逐步萎缩，或恐慌集中释放。
    down_vols = [float(k.get('volume', 0) or 0) for k in data[-PANIC_LOOKBACK:-1]]
    earlier_vols = [float(k.get('volume', 0) or 0) for k in data[-20:-PANIC_LOOKBACK]]
    avg_down = sum(down_vols) / len(down_vols) if down_vols else 0
    avg_earlier = sum(earlier_vols) / len(earlier_vols) if earlier_vols else 0
    shrink_ratio = avg_down / avg_earlier if avg_earlier else 1.0
    panic_events = 0
    for j in range(max(20, len(data) - PANIC_LOOKBACK - 1), len(data) - 1):
        k, prev = data[j], data[j - 1]
        fall = (float(k['close']) - float(prev['close'])) / (float(prev['close']) or 1)
        if fall <= -0.05 and calc_volume_ratio(data, j, 20) >= 1.5:
            panic_events += 1
    supply_context = ('panic_release' if panic_events else
                      'supply_shrink' if shrink_ratio <= 0.9 else 'ordinary_decline')
    scores.update({
        'supply_shrink_ratio': round(shrink_ratio, 3),
        'panic_events': panic_events,
        'supply_context': supply_context,
    })
    if supply_context == 'ordinary_decline' and not (
        gain_pct >= 0.05 and (vr20 >= 1.30 or vr5 >= 1.50)
    ):
        return _failed('未见供应萎缩/恐慌背景，普通反弹的需求强度不足', scores)

    closes = [float(k['close']) for k in data]
    ema5 = calc_ema(closes, 5)[-1]
    ema5_score = 100 if float(today['close']) >= ema5 else 40
    price_score = min(100, 55 + close_position * 35 + (10 if reclaims_prior_low else 0))
    volume_score = min(100, 60 + max(vr20 - 1.0, vr5 - 1.0) * 35)
    candle_score = min(100, max(0, body_ratio) * 100 + (20 if gain_pct >= 0.07 else 0))
    supply_score = 100 if supply_context == 'panic_release' else 80 if supply_context == 'supply_shrink' else 50
    confidence = (
        scores['trend'] * 0.15 + price_score * 0.20 + volume_score * 0.20 +
        supply_score * 0.15 + candle_score * 0.20 + ema5_score * 0.10
    )
    scores.update({
        'price_reversal': round(price_score, 1),
        'volume': round(volume_score, 1),
        'supply_check': supply_score,
        'candle': round(candle_score, 1),
        'ema5': ema5_score,
    })
    triggered = confidence >= CONFIDENCE_PASS
    context_text = '恐慌释放后' if supply_context == 'panic_release' else '下降末端'
    detail = (f'{context_text}{volume_rule}，收盘位于日内{close_position:.0%}，'
              f'20日/5日量比{vr20:.2f}/{vr5:.2f}')
    return make_result(triggered, round(confidence, 1), '向上反转',
                       'upward_reversal', detail if triggered else '综合置信度不足', scores)
