"""
需求衰竭信号检测

原文：《量价原理》5.6(3) — 需求衰竭信号

两种形态（取置信度高者）：

形态A：加速
  ① 发生在上升趋势中（否决项）
  ② 上升趋势已持续一段时间（否决项）
  ③ 连续大阳线：最近3日中至少2日实体>50%阳线（25分）
  ④ 斜率陡峭：最近5日收盘价的平均涨幅 > 3%/日（30分）[注：用BIAS5斜率辅助判定]
  ⑤ 成交量明显放大：最近3日均量 > 前20日均量的1.5倍（25分）
  ⑥ 发生在趋势末端：乖离率BIAS20 > 8%（20分）

形态B：需求不足（缩量滞涨）
  ① 发生在上涨趋势中（否决项）
  ② 一波上涨后成交量跟不上：最近5日均量 < 前20日均量的80%（35分）
  ③ 价格停滞不前：最近5日收盘价变化 < 2%（35分）
  ④ 可能形成平顶或圆弧顶：最近5日高点的波动 < 3%（30分）
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, is_big_candle,
    detect_trend, calc_ema, calc_ma, make_result, SignalResult,
)

CONFIDENCE_PASS = 60


def detect_demand_exhaustion(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < 30:
        return make_result(False, 0, '需求衰竭', 'demand_exhaustion', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < 30:
        return make_result(False, 0, '需求衰竭', 'demand_exhaustion', '数据不足')

    # ── 共同否决项：上升趋势 ──
    trend = detect_trend(data)
    if trend != 'up':
        return make_result(False, 0, '需求衰竭', 'demand_exhaustion', '非上升趋势')

    # 尝试两种形态
    result_a = _detect_accel_form(data)
    result_b = _detect_sluggish_form(data)

    # 取置信度高者
    if result_a['triggered'] and result_b['triggered']:
        return result_a if result_a['confidence'] >= result_b['confidence'] else result_b
    elif result_a['triggered']:
        return result_a
    elif result_b['triggered']:
        return result_b
    else:
        return result_a if result_a['confidence'] >= result_b['confidence'] else result_b


def _detect_accel_form(data: List[Dict]) -> SignalResult:
    """形态A：加速"""
    scores = {}
    total = 0.0
    closes = [k['close'] for k in data]

    # ── 条件②：上升趋势已持续一段时间 ──
    if len(closes) < 16:
        return make_result(False, 0, '需求衰竭(加速)', 'demand_exhaustion', '数据不足')
    gain_15d = (closes[-1] - closes[-15]) / (closes[-15] or 1)
    if gain_15d < 0.05:
        return make_result(False, 0, '需求衰竭(加速)', 'demand_exhaustion',
                           f'涨幅不足({gain_15d:.1%})', {'trend_duration': 0})
    scores['trend_duration'] = 1.0

    # ── 条件③：连续大阳线 ──
    big_count = 0
    for k in data[-4:-1]:  # 最近3天（不含今日）
        if k['close'] > k['open']:
            rng = k['high'] - k['low']
            if rng > 0 and (k['close'] - k['open']) / rng >= 0.5:
                big_count += 1
    if big_count >= 2:
        candle_score = 100
    elif big_count >= 1:
        candle_score = 60
    else:
        candle_score = 20
    scores['big_candles'] = candle_score
    total += candle_score * 0.25

    # ── 条件④：斜率陡峭（5日日均涨幅>3%）──
    if len(closes) >= 6:
        daily_returns = []
        for j in range(1, 6):
            dr = (closes[-j] - closes[-j-1]) / (closes[-j-1] or 1)
            daily_returns.append(dr)
        avg_daily = sum(daily_returns) / len(daily_returns)
    else:
        avg_daily = 0

    if avg_daily > 0.05:
        slope_score = 100
    elif avg_daily > 0.03:
        slope_score = 80
    elif avg_daily > 0.02:
        slope_score = 50
    elif avg_daily > 0.01:
        slope_score = 20
    else:
        slope_score = 0
    scores['slope'] = slope_score
    total += slope_score * 0.30

    # ── 条件⑤：成交量明显放大 ──
    if len(data) >= 23:
        vol_3 = sum(k['volume'] for k in data[-4:-1]) / 3
        vol_20 = sum(k['volume'] for k in data[-23:-3]) / 20
        vol_ratio = vol_3 / vol_20 if vol_20 > 0 else 0

        if vol_ratio >= 3.0:
            vol_score = 100
        elif vol_ratio >= 1.5:
            vol_score = 60 + (vol_ratio - 1.5) / (3.0 - 1.5) * 40
        elif vol_ratio >= 1.2:
            vol_score = 40
        else:
            vol_score = 10
    else:
        vol_score = 30
    scores['volume_surge'] = vol_score
    total += vol_score * 0.25

    # ── 条件⑥：发生在趋势末端（BIAS20 > 8%）──
    ma20 = calc_ma(data, 'close', 20)
    if ma20 > 0:
        bias20 = (data[-1]['close'] - ma20) / ma20 * 100
        if bias20 > 15:
            bias_score = 100
        elif bias20 > 8:
            bias_score = 60 + (bias20 - 8) / (15 - 8) * 40
        elif bias20 > 5:
            bias_score = 30
        else:
            bias_score = 0
    else:
        bias_score = 30
    scores['bias20'] = bias_score
    total += bias_score * 0.20

    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append('加速形态')
        if avg_daily > 0.03:
            detail_parts.append(f'日涨{avg_daily*100:.1f}%')
        if scores.get('bias20', 0) > 60:
            detail_parts.append(f'BIAS20={bias20:.1f}%')

    return make_result(triggered, confidence, '需求衰竭(加速)', 'demand_exhaustion',
                       '，'.join(detail_parts) if detail_parts else '',
                       {**scores, 'form': 'acceleration'})


def _detect_sluggish_form(data: List[Dict]) -> SignalResult:
    """形态B：需求不足（缩量滞涨）"""
    scores = {}
    total = 0.0
    closes = [k['close'] for k in data]

    # ── 条件②：成交量跟不上 ──
    if len(data) >= 25:
        vol_5 = sum(k['volume'] for k in data[-5:]) / 5
        vol_20 = sum(k['volume'] for k in data[-25:-5]) / 20
        vol_ratio = vol_5 / vol_20 if vol_20 > 0 else 1
        if vol_ratio < 0.5:
            vol_shrink = 100
        elif vol_ratio < 0.8:
            vol_shrink = 80
        elif vol_ratio < 1.0:
            vol_shrink = 40
        else:
            vol_shrink = 10
    else:
        vol_shrink = 30
    scores['vol_shrink'] = vol_shrink
    total += vol_shrink * 0.35

    # ── 条件③：价格停滞不前 ──
    if len(closes) >= 5:
        change = (closes[-1] - closes[-5]) / (closes[-5] or 1)
        if abs(change) < 0.01:
            stagnant = 100
        elif abs(change) < 0.02:
            stagnant = 80
        elif abs(change) < 0.03:
            stagnant = 50
        else:
            stagnant = 10
    else:
        stagnant = 50
    scores['stagnation'] = stagnant
    total += stagnant * 0.35

    # ── 条件④：平顶/圆弧顶 ──
    if len(data) >= 5:
        highs_5 = [k['high'] for k in data[-5:]]
        h_range = (max(highs_5) - min(highs_5)) / (min(highs_5) or 1)
        if h_range < 0.01:
            flat_score = 100
        elif h_range < 0.03:
            flat_score = 80
        elif h_range < 0.05:
            flat_score = 50
        else:
            flat_score = 10
    else:
        flat_score = 50
    scores['flat_top'] = flat_score
    total += flat_score * 0.30

    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append('缩量滞涨')
        if vol_shrink > 70:
            detail_parts.append('量萎缩')
        if flat_score > 70:
            detail_parts.append('平顶')

    return make_result(triggered, confidence, '需求衰竭(缩量)', 'demand_exhaustion',
                       '，'.join(detail_parts) if detail_parts else '',
                       {**scores, 'form': 'sluggish'})
