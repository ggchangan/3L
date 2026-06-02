"""
向上反转信号检测

原文：《量价原理》5.6(2) — 向上反转信号

发生位置：下降趋势中
量价行为：
  ① 股价不再创新低，或股价当日触达新低后折回，收在高位，能体现出需求开始占优
  ② 成交量明显放大（成交量越大反转成功概率越高，信号越可靠）
  ③ 向上反转之前，股价经历了一段清晰的下降趋势后，
     要么出现了明显的供应萎缩（随着下跌成交量越来越低，K线越来越窄），
     要么出现了恐慌，成交量明显放大，供应一次性出清
  ④ 量价行为表现：放量长阳或放量长下影线（阳包阴/AB），且收盘在相对高位
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, is_big_candle, close_in_upper_third,
    detect_trend, calc_ema, make_result, SignalResult,
)

CONFIDENCE_PASS = 60
TREND_LOOKBACK = 25
PANIC_LOOKBACK = 10
VOLUME_SURGE = 1.3         # 放量阈值（阴跌后反弹温和量即可）
SUPPLY_SHRINK = 0.7        # 供应萎缩缩量阈值


def detect_upward_reversal(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < TREND_LOOKBACK + 5:
        return make_result(False, 0, '向上反转', 'upward_reversal', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < TREND_LOOKBACK + 5:
        return make_result(False, 0, '向上反转', 'upward_reversal', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0

    # ── 条件①：近期有明显下跌 ──
    # 检测20天内的最大回撤幅度（最低点到最高点）
    if len(data) >= 11:
        recent_high = max(k['close'] for k in data[-20:])
        recent_low = min(k['close'] for k in data[-20:])
        max_drawdown = (recent_low - recent_high) / (recent_high or 1)
        # 当前价格相对于高点的位置
        current_vs_high = (data[-1]['close'] - recent_high) / (recent_high or 1)
    else:
        max_drawdown = 0.0
        current_vs_high = 0.0
    
    if max_drawdown > -0.07:
        return make_result(False, 0, '向上反转', 'upward_reversal',
                           f'跌幅不足(最大回撤{max_drawdown:.1%})', {'trend': 0})
    
    # 下降趋势确认：EMA10向下
    closes = [k['close'] for k in data]
    ema10_vals = calc_ema(closes, 10)
    if len(ema10_vals) >= 3 and ema10_vals[-1] > ema10_vals[-3]:
        return make_result(False, 0, '向上反转', 'upward_reversal',
                           'EMA10向上，非下降趋势', {'trend': 0})
    scores['trend'] = 1.0

    # ── 条件②：股价不再创新低，或触新低后折回收高位 ──
    # 原文：股价不再创新低，或股价当日触达新低后折回，收在高位
    recent_5_low = min(k['low'] for k in data[-6:-1]) if len(data) >= 6 else 999
    makes_new_low = data[-1]['low'] < recent_5_low * 0.99
    
    amp = today['high'] - today['low']
    close_position = (today['close'] - today['low']) / amp if amp > 0 else 0
    
    if makes_new_low:
        # 触新低但收盘在高位 → 折回形态，正面信号
        if close_position >= 0.5:
            scores['new_low'] = 60
        else:
            return make_result(False, 0, '向上反转', 'upward_reversal',
                               '触新低且收盘低位', {**scores, 'new_low': 0})
    else:
        scores['new_low'] = 100

    # 收盘在高位（上1/3）
    amp = today['high'] - today['low']
    close_position = (today['close'] - today['low']) / amp if amp > 0 else 0

    if close_position > 0.66:
        pos_score = 100  # 完美收在高位
    elif close_position > 0.50:
        pos_score = 70
    else:
        pos_score = 40

    scores['close_position'] = pos_score
    total += pos_score * 0.20

    # ── 条件③：成交量明显放大 ──
    vr = calc_volume_ratio(data, len(data) - 1, 20)
    if vr < VOLUME_SURGE:
        return make_result(False, 0, '向上反转', 'upward_reversal',
                           f'放量不足({vr:.1f}倍)', {**scores, 'volume': 0})
    if vr >= 3.0:
        vol_score = 100
    else:
        vol_score = 60 + (vr - VOLUME_SURGE) / (3.0 - VOLUME_SURGE) * 40
    scores['volume'] = vol_score
    total += vol_score * 0.25

    # ── 条件④：反转前供应萎缩 或 恐慌抛售 ──
    # 方案A：供应萎缩（下跌缩量）
    down_vols = [k['volume'] for k in data[-PANIC_LOOKBACK:-1]]
    earlier_vols = [k['volume'] for k in data[-20:-PANIC_LOOKBACK]]
    avg_down = sum(down_vols) / len(down_vols) if down_vols else 1
    avg_earlier = sum(earlier_vols) / len(earlier_vols) if earlier_vols else 1

    if avg_earlier > 0:
        shrink_ratio = avg_down / avg_earlier
        if shrink_ratio <= 0.5:
            shrink_score = 100
        elif shrink_ratio <= SUPPLY_SHRINK:
            shrink_score = 75
        elif shrink_ratio <= 0.9:
            shrink_score = 50
        else:
            shrink_score = 20
    else:
        shrink_score = 30

    # 方案B：恐慌抛售（下跌末期突然放量大跌）
    panic_score = 0
    for j in range(max(0, len(data) - PANIC_LOOKBACK - 1), len(data) - 1):
        k = data[j]
        if k['close'] < k['open']:  # 阴线
            k_vr = calc_volume_ratio(data, j, 20)
            body_pct = (k['open'] - k['close']) / (k['open'] or 1)
            if k_vr >= 2.0 and body_pct > 0.03:
                panic_score += 30

    panic_score = min(panic_score, 100)

    pre_score = max(shrink_score, panic_score)  # 取信用度高者
    scores['supply_check'] = pre_score
    total += pre_score * 0.20

    # ── 条件⑤：放量长阳/阳包阴/长下影线 ──
    candle_score = 0
    body = today['close'] - today['open']
    body_abs = abs(body)
    lower_shadow = today['open'] - today['low'] if body > 0 else today['close'] - today['low']
    upper_shadow = today['high'] - today['close'] if body > 0 else today['high'] - today['open']
    total_range = today['high'] - today['low']

    if body > 0:  # 阳线
        if total_range > 0:
            body_ratio = body_abs / total_range
            if body_ratio >= 0.6:
                candle_score += 50  # 大阳线
            elif body_ratio >= 0.4:
                candle_score += 30

        # 阳包阴（今天阳线完全覆盖昨日阴线）
        if len(data) >= 2:
            prev = data[-2]
            if prev['close'] < prev['open'] and today['close'] > prev['open'] and today['open'] < prev['close']:
                candle_score += 30

        # 长下影线
        shadow_ratio = lower_shadow / total_range if total_range > 0 else 0
        if shadow_ratio >= 0.6:
            candle_score += 30

    # 收盘在高位加分
    if close_in_upper_third(data, -1):
        candle_score += 20

    candle_score = min(candle_score, 100)
    scores['candle'] = candle_score
    total += candle_score * 0.20

    # ── 条件⑥：今日收盘价站上EMA5（硬条件）──
    closes = [k['close'] for k in data]
    ema5_vals = calc_ema(closes, 5)
    if len(ema5_vals) >= 1:
        if today['close'] < ema5_vals[-1]:
            return make_result(False, 0, '向上反转', 'upward_reversal',
                               f'未站上EMA5({ema5_vals[-1]:.1f})', {**scores, 'ema5': 0})
        ema5 = ema5_vals[-1]
        ema5_pct = (today['close'] - ema5) / (ema5 or 1)
        if ema5_pct >= 0:
            ema5_score = 100
        elif ema5_pct >= -0.02:
            ema5_score = 60
        else:
            ema5_score = 20
    else:
        ema5_score = 50
    scores['ema5'] = ema5_score
    total += ema5_score * 0.15

    # ── 总置信度 ──
    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append('下降末端')
        if vr >= 1.8:
            detail_parts.append(f'量{vr:.1f}倍')
        if candle_score >= 60:
            detail_parts.append('阳包阴' if '阳包阴' in str(scores) else '长阳')
        if ema5_score >= 80:
            detail_parts.append('站上EMA5')

    return make_result(triggered, confidence, '向上反转', 'upward_reversal',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
