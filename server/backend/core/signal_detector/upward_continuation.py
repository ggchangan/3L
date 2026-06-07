"""
上涨中继信号检测（中继买点）

原文：《量价原理》5.6(4) — 中继信号·上涨中继

发生位置：上涨趋势中
量价行为：
  缩量回踩，显示出卖出意愿不强，不破坏原有上升趋势的构成条件（供不应求）
  从供需角度理解，回踩的时候缩量，说明卖方意愿不强，不破原有的上升趋势，
  说明在更大的周期层面，需求依然是占优的。
  这就是上升趋势保持的必要条件。如此，上升趋势中的缩量回踩，就产生了
  低风险的买点——中继买点。这类买点是非常好的参与上升趋势的买点，
  会频繁出现在上升趋势中，也是最容易把握的买点。
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, calc_ma, calc_ema,
    volume_trend, detect_trend, make_result, SignalResult,
)

# ════════════════════════════════════════════
# 可调参数
# ════════════════════════════════════════════
CONFIDENCE_PASS = 60         # 视为触发的最低置信度
TREND_LOOKBACK = 25          # 趋势判定窗口
PULLBACK_WINDOW = 5          # 回踩观察窗口
RECENT_HIGH_LOOKBACK = 15    # 找近期高点的窗口
MIN_TREND_DAYS = 10          # 上升趋势最少持续天数
MAX_PULLBACK_PCT = -0.10     # 最大回踩幅度（超过10%可能破坏趋势）
MIN_PULLBACK_PCT = -0.01     # 最少回踩幅度（至少回调1%）
BODY_MA_VOLUME = 20          # 成交量对比均线周期


def detect_upward_continuation(klines: List[Dict], idx: int = -1) -> SignalResult:
    """
    检测上涨中继信号（中继买点）。

    参数：
        klines: 日K线，升序排列
        idx: 当前判定位置（默认-1表示最后一天）

    返回：
        SignalResult
    """
    if len(klines) < TREND_LOOKBACK + PULLBACK_WINDOW:
        return make_result(False, 0, '上涨中继', 'upward_continuation', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < TREND_LOOKBACK + PULLBACK_WINDOW:
        return make_result(False, 0, '上涨中继', 'upward_continuation', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0

    # ── 条件①：发生在上涨趋势中 ──
    trend = detect_trend(data, TREND_LOOKBACK)
    if trend != 'up':
        return make_result(False, 0, '上涨中继', 'upward_continuation',
                           '非上升趋势', {'trend': 0})
    scores['trend'] = 1.0

    # ── 条件②：上涨趋势已持续一段时间 ──
    recent_closes = [k['close'] for k in data[-15:]]
    price_change = (recent_closes[-1] - recent_closes[0]) / (recent_closes[0] or 1)
    if len(data) >= 20:
        longer_closes = [k['close'] for k in data[-20:-15]]
        if longer_closes:
            longer_change = (longer_closes[-1] - longer_closes[0]) / (longer_closes[0] or 1)
            trend_strength = abs(price_change) + abs(longer_change)
        else:
            trend_strength = abs(price_change)
    else:
        trend_strength = abs(price_change)

    trend_score = min(trend_strength * 300, 100)  # 3%涨幅趋势就接近满分
    scores['trend_duration'] = trend_score
    total += trend_score * 0.10  # 权重10%

    # ── 条件③：近期创出新高后出现回踩 ──
    recent_highs = [k['high'] for k in data[-RECENT_HIGH_LOOKBACK:]]
    recent_high = max(recent_highs)
    # 近期高点距今的天数
    high_idx = recent_highs.index(recent_high)
    days_since_high = RECENT_HIGH_LOOKBACK - 1 - high_idx

    pullback_pct = (today['close'] - recent_high) / (recent_high or 1)

    # 高点距今不足2天：上影线/当天冲高回落，不是真正回踩
    if days_since_high < 2:
        return make_result(False, 0, '上涨中继', 'upward_continuation',
                           f'非有效回踩（高点距今仅{days_since_high}天）',
                           {**scores, 'pullback': 0})

    if pullback_pct >= MIN_PULLBACK_PCT:
        return make_result(False, 0, '上涨中继', 'upward_continuation',
                           f'未回踩（距高点{pullback_pct:+.1f}%）',
                           {**scores, 'pullback': 0})

    if pullback_pct < MAX_PULLBACK_PCT:
        return make_result(False, 0, '上涨中继', 'upward_continuation',
                           f'回踩过深({pullback_pct:.1f}%)',
                           {**scores, 'pullback': 0})

    pb_abs = abs(pullback_pct)
    if pb_abs <= 0.03:
        pullback_score = 100 - (pb_abs - 0.01) / 0.02 * 30
    elif pb_abs <= 0.05:
        pullback_score = 80 - (pb_abs - 0.03) / 0.02 * 30
    else:
        pullback_score = max(50 - (pb_abs - 0.05) / 0.05 * 30, 20)
    scores['pullback'] = pullback_score
    total += pullback_score * 0.15  # 权重15%

    # ── 条件④：缩量回踩（核心）──
    # 回踩期成交量 vs 上涨期成交量
    start_idx = max(0, len(data) - 20)
    up_vols = [k['volume'] for k in data[start_idx:-PULLBACK_WINDOW]]
    pullback_vols = [k['volume'] for k in data[-PULLBACK_WINDOW:]]

    avg_up_vol = sum(up_vols) / len(up_vols) if up_vols else 1
    avg_pullback_vol = sum(pullback_vols) / len(pullback_vols) if pullback_vols else 0

    if avg_up_vol > 0:
        vol_ratio = avg_pullback_vol / avg_up_vol
    else:
        vol_ratio = 1.0

    if vol_ratio <= 0.5:
        vol_score = 100
    elif vol_ratio <= 0.7:
        vol_score = 80
    elif vol_ratio <= 0.85:
        vol_score = 65
    elif vol_ratio <= 1.0:
        vol_score = 50
    else:
        vol_score = max(30 - (vol_ratio - 1.0) * 60, 0)

    scores['volume_shrink'] = vol_score
    total += vol_score * 0.30

    # ── 条件⑤：不破坏上升趋势结构 ──
    closes = [k['close'] for k in data]
    ema10_vals = calc_ema(closes, 10)
    ema20_vals = calc_ema(closes, 20)
    if len(ema10_vals) >= 2:
        current_ema10 = ema10_vals[-1]
        ema10_pct = (today['close'] - current_ema10) / (current_ema10 or 1)
        if ema10_pct >= 0:
            ema_score = 100
        elif ema10_pct >= -0.02:
            ema_score = 70
        elif ema10_pct >= -0.05:
            ema_score = 35
        else:
            ema_score = 5
    else:
        ema_score = 50

    # EMA10斜率 — 要求仍然向上
    if len(ema10_vals) >= 3:
        ema_slope = (ema10_vals[-1] - ema10_vals[-3]) / (ema10_vals[-3] or 1)
        slope_score = 100 if ema_slope > 0 else 20
    else:
        slope_score = 50

    # EMA20支撑 — 不能跌破EMA20
    if len(ema20_vals) >= 1:
        current_ema20 = ema20_vals[-1]
        ema20_pct = (today['close'] - current_ema20) / (current_ema20 or 1)
        if ema20_pct >= 0:
            ema20_score = 100
        elif ema20_pct >= -0.03:
            ema20_score = 50
        else:
            ema20_score = 5  # 跌破EMA20太危险
    else:
        ema20_score = 50

    trend_health_score = ema_score * 0.35 + slope_score * 0.35 + ema20_score * 0.30
    scores['trend_health'] = trend_health_score
    total += trend_health_score * 0.20

    # ── 条件⑥：回踩K线窄幅 ──
    recent_ranges = [(k['high'] - k['low']) / (k['close'] or 1) for k in data[-PULLBACK_WINDOW:]]
    avg_range = sum(recent_ranges) / len(recent_ranges)
    overall_ranges = [(k['high'] - k['low']) / (k['close'] or 1) for k in data[-20:]]
    overall_avg_range = sum(overall_ranges) / len(overall_ranges)

    if overall_avg_range > 0:
        range_ratio = avg_range / overall_avg_range
        if range_ratio <= 0.6:
            kline_score = 100
        elif range_ratio <= 0.8:
            kline_score = 75
        elif range_ratio <= 1.0:
            kline_score = 50
        else:
            kline_score = 25
    else:
        kline_score = 50

    scores['kline_narrow'] = kline_score
    total += kline_score * 0.15  # 权重15%

    # ── 条件⑦：加速过滤（防止高位反转被误判为中继）──
    # 如果近期涨幅过大，回踩很可能是顶部而不是中继
    if len(data) >= 20:
        recent_15d_change = (data[-1]['close'] - data[-16]['close']) / (data[-16]['close'] or 1)
        if recent_15d_change > 0.30:
            accel_penalty = max(0, 100 - (recent_15d_change - 0.30) / 0.30 * 100)
        elif recent_15d_change > 0.20:
            accel_penalty = 85
        elif recent_15d_change > 0.15:
            accel_penalty = 95
        else:
            accel_penalty = 100
    else:
        accel_penalty = 100
    scores['accel_filter'] = accel_penalty
    total += accel_penalty * 0.20  # 权重20%（加速末端风险高，加重扣分）

    # ── 条件⑧：60天相对位置检查 ──
    # 如果股价已在60天高位，回踩失败的几率增加
    if len(data) >= 30:
        period_high = max(k['close'] for k in data[-30:])
        period_low = min(k['close'] for k in data[-30:])
        if period_high > period_low:
            pos_ratio = (today['close'] - period_low) / (period_high - period_low)
            if pos_ratio > 0.85:
                pos_score = 60  # 高位, 谨慎
            elif pos_ratio < 0.30:
                pos_score = 80  # 低位, 更容易反弹
            else:
                pos_score = 100
        else:
            pos_score = 100
    else:
        pos_score = 100
    scores['position'] = pos_score
    total += pos_score * 0.10  # 权重10%

    # ── 总置信度 ──
    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append(f"回踩{pullback_pct:.1f}%")
        detail_parts.append(f"量{vol_ratio:.2f}倍")
        if vol_ratio < 0.7:
            detail_parts.append("缩量")
        if ema_score >= 75:
            detail_parts.append("EMA10支撑")

    return make_result(triggered, confidence, '上涨中继', 'upward_continuation',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
