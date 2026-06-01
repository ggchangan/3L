"""
向下反转信号检测

原文：《量价原理》5.6(2) — 向下反转信号

发生位置：上涨趋势中
量价行为：
  ① 股价不再创新高，或股价当日触及新高后折回，收在低位
  ② 成交量明显放大（成交量越大反转成功概率越高，信号越可靠）
  ③ 向下反转之前，股价经历了一段清晰的上涨趋势后，
     要么出现了明显的需求不足（随着上涨成交量越来越低，K线越来越窄），
     要么出现了加速，成交量明显放大，需求一次性透支
  ④ 量价行为表现：放量长阴或放量长上影线（阴包阳/BC），且收盘在相对低位
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, is_big_candle, close_in_lower_third,
    detect_trend, calc_ema, make_result, SignalResult,
)

CONFIDENCE_PASS = 70     # v2: 提高至70减少假信号

def detect_downward_reversal(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < 30:
        return make_result(False, 0, '向下反转', 'downward_reversal', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < 30:
        return make_result(False, 0, '向下反转', 'downward_reversal', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0
    closes = [k['close'] for k in data]

    # ── 条件①：发生在上涨趋势中（否决项）──
    trend = detect_trend(data)
    if trend != 'up':
        return make_result(False, 0, '向下反转', 'downward_reversal', '非上涨趋势', {'trend': 0})

    # 累计涨幅
    if len(closes) >= 15:
        gain = (closes[-1] - closes[-15]) / (closes[-15] or 1)
        if gain < 0.05:
            return make_result(False, 0, '向下反转', 'downward_reversal', f'涨幅不足({gain:.1%})', {'trend': 0})
    scores['trend'] = 1.0

    # ── 条件②：不再创新高（否决项）──
    recent_5_high = max(k['high'] for k in data[-6:-1]) if len(data) >= 6 else 0
    makes_new_high = today['high'] > recent_5_high * 1.01
    amp = today['high'] - today['low']
    close_position = (today['close'] - today['low']) / amp if amp > 0 else 0

    if makes_new_high:
        if close_position <= 0.5:
            scores['new_high'] = 60
        else:
            return make_result(False, 0, '向下反转', 'downward_reversal', '触新高且收盘高位', {**scores, 'new_high': 0})
    else:
        scores['new_high'] = 100

    if close_position < 0.33:
        pos_score = 100
    elif close_position < 0.50:
        pos_score = 70
    else:
        pos_score = 40
    scores['close_position'] = pos_score
    total += pos_score * 0.20

    # ── 条件③：成交量放大（否决项）──
    vr = calc_volume_ratio(data, len(data) - 1, 20)
    if vr < 1.3:
        return make_result(False, 0, '向下反转', 'downward_reversal', f'放量不足({vr:.1f}倍)', {**scores, 'volume': 0})
    if vr >= 3.0:
        vol_score = 100
    else:
        vol_score = 60 + (vr - 1.3) / (3.0 - 1.3) * 40
    scores['volume'] = vol_score
    total += vol_score * 0.25

    # ── 条件④：反转前需求不足 or 加速 ──
    near_vols = [k['volume'] for k in data[-10:-1]]
    earlier_vols = [k['volume'] for k in data[-20:-10]]
    avg_near = sum(near_vols) / len(near_vols) if near_vols else 1
    avg_earlier = sum(earlier_vols) / len(earlier_vols) if earlier_vols else 1
    shrink_ratio = avg_near / avg_earlier if avg_earlier > 0 else 1
    shrink_score = min(shrink_ratio / 0.7 * 100, 100) if shrink_ratio < 0.7 else max(100 - (shrink_ratio - 0.7) / 0.3 * 80, 10)

    accel_score = 0
    if len(closes) >= 8:
        slope = (closes[-1] - closes[-5]) / (closes[-5] or 1)
        big_count = sum(1 for k in data[-5:-1] if k['close'] > k['open'] and (k['close'] - k['open']) / (k['high'] - k['low'] + 0.001) > 0.5)
        if slope > 0.08: accel_score += 50
        if big_count >= 2: accel_score += 50
    accel_score = min(accel_score, 100)

    pre_score = max(shrink_score, accel_score)
    scores['demand_check'] = pre_score
    total += pre_score * 0.20

    # ── 条件⑤：量价表现 ──
    candle_score = 0
    body = today['close'] - today['open']
    total_range = today['high'] - today['low']
    if body < 0:
        if total_range > 0:
            body_ratio = abs(body) / total_range
            if body_ratio >= 0.6: candle_score += 50
            elif body_ratio >= 0.4: candle_score += 30
        if len(data) >= 2:
            prev = data[-2]
            if prev['close'] > prev['open'] and today['close'] < prev['open'] and today['open'] > prev['close']:
                candle_score += 30
        upper_shadow = today['high'] - today['open']
        if total_range > 0 and upper_shadow / total_range >= 0.6:
            candle_score += 30
    if close_in_lower_third(data, -1):
        candle_score += 20
    candle_score = min(candle_score, 100)
    scores['candle'] = candle_score
    total += candle_score * 0.20

    # ── 条件⑥：跌破EMA5（否决项）──
    ema5_vals = calc_ema(closes, 5)
    if len(ema5_vals) >= 1:
        if today['close'] > ema5_vals[-1]:
            return make_result(False, 0, '向下反转', 'downward_reversal',
                               f'未跌破EMA5({ema5_vals[-1]:.1f})', {**scores, 'ema5': 0})
        ema5_pct = (today['close'] - ema5_vals[-1]) / (ema5_vals[-1] or 1)
        ema5_score = 100 if ema5_pct <= 0 else 60
    else:
        ema5_score = 50
    scores['ema5'] = ema5_score
    total += ema5_score * 0.15

    confidence = total
    triggered = confidence >= CONFIDENCE_PASS  # 提高到70分

    detail_parts = []
    if triggered:
        detail_parts.append('上涨末端')
        if vr >= 1.8:
            detail_parts.append(f'量{vr:.1f}倍')
        if candle_score >= 60:
            detail_parts.append('阴包阳' if '阴包阳' in str(candle_score) else '长阴')
        if ema5_score >= 80:
            detail_parts.append('跌破EMA5')

    return make_result(triggered, confidence, '向下反转', 'downward_reversal',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
