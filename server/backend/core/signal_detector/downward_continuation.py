"""
下跌中继信号检测

原文：《量价原理》5.6(4) — 中继信号·下跌中继

发生位置：下降趋势中
量价行为：缩量反弹，显示出买入意愿不强，无法改变原有下降趋势的构成条件（供过于求）
从供需角度理解：
  下降趋势中偶尔会出现反弹，最重要的观察点是成交量，
  缩量反弹证明需求不足，难以改变原有供需格局，
  即下降趋势中的需求不足，产生下跌中继信号。
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, calc_ema,
    detect_trend, make_result, SignalResult,
)

CONFIDENCE_PASS = 60
TREND_LOOKBACK = 25
BOUNCE_WINDOW = 5          # 反弹观察窗口
MAX_BOUNCE_PCT = 0.10      # 最大反弹幅度（超过10%可能改变趋势）
MIN_BOUNCE_PCT = 0.01      # 最少反弹幅度（至少反弹1%才叫反弹）
VOLUME_SHRINK = 0.8        # 反弹缩量阈值（反弹均量 / 下跌均量 < 0.8）


def detect_downward_continuation(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < TREND_LOOKBACK + BOUNCE_WINDOW:
        return make_result(False, 0, '下跌中继', 'downward_continuation', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < TREND_LOOKBACK + BOUNCE_WINDOW:
        return make_result(False, 0, '下跌中继', 'downward_continuation', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0
    closes = [k['close'] for k in data]

    # ── 条件①：发生在下降趋势中（否决项）──
    trend = detect_trend(data)
    if trend != 'down':
        return make_result(False, 0, '下跌中继', 'downward_continuation',
                           '非下降趋势', {'trend': 0})

    # ── 条件②：下降趋势已持续一段时间（否决项）──
    if len(closes) < 16:
        return make_result(False, 0, '下跌中继', 'downward_continuation',
                           '数据不足', {'trend_duration': 0})
    loss_15d = (closes[-1] - closes[-15]) / (closes[-15] or 1)
    if loss_15d > -0.05:
        return make_result(False, 0, '下跌中继', 'downward_continuation',
                           f'跌幅不足({loss_15d:.1%})', {'trend_duration': 0})
    scores['trend_duration'] = 1.0

    # ── 条件③：出现了反弹（先跌后涨）──
    # 原文：下降趋势中偶尔会出现反弹
    # 算法：最近BOUNCE_WINDOW天收盘价反弹幅度>MIN_BOUNCE_PCT
    if len(data) >= BOUNCE_WINDOW + 3:
        recent_low = min(k['close'] for k in data[-BOUNCE_WINDOW - 3:-1])
        bounce_pct = (today['close'] - recent_low) / (recent_low or 1)
    else:
        bounce_pct = 0

    if bounce_pct < MIN_BOUNCE_PCT:
        return make_result(False, 0, '下跌中继', 'downward_continuation',
                           f'无反弹({bounce_pct:.1%})', {**scores, 'bounce': 0})

    # 反弹幅度评分：反弹太大可能改变趋势，太小不算反弹
    if bounce_pct > MAX_BOUNCE_PCT:
        # 反弹超10%，可能改变趋势——不认为是中继
        return make_result(False, 0, '下跌中继', 'downward_continuation',
                           f'反弹过大({bounce_pct:.1%})', {**scores, 'bounce': 0})
    elif bounce_pct > 0.05:
        bounce_score = 70  # 中等反弹
    elif bounce_pct > 0.02:
        bounce_score = 90  # 小幅反弹，典型的弱反弹
    else:
        bounce_score = 100  # 极小反弹
    scores['bounce'] = bounce_score
    total += bounce_score * 0.20

    # ── 条件④：反弹缩量（核心条件）──
    # 原文：缩量反弹，买入意愿不强
    # 算法：反弹期间均量 / 下跌期间均量 < 阈值
    if len(data) >= BOUNCE_WINDOW + 10:
        # 反弹期间成交量
        bounce_vols = [k['volume'] for k in data[-BOUNCE_WINDOW:]]
        avg_bounce_vol = sum(bounce_vols) / len(bounce_vols)
        # 下跌期间成交量（反弹前10天）
        pre_bounce_vols = [k['volume'] for k in data[-BOUNCE_WINDOW - 10:-BOUNCE_WINDOW]]
        avg_down_vol = sum(pre_bounce_vols) / len(pre_bounce_vols) if pre_bounce_vols else 1
        vol_ratio = avg_bounce_vol / avg_down_vol if avg_down_vol > 0 else 1.0
    else:
        vol_ratio = 1.0

    if vol_ratio <= 0.5:
        vol_score = 100  # 极度缩量反弹
    elif vol_ratio <= VOLUME_SHRINK:
        vol_score = 80   # 明显缩量
    elif vol_ratio <= 1.0:
        vol_score = 50   # 缩量不明显
    else:
        vol_score = max(30 - (vol_ratio - 1.0) * 60, 0)  # 放量反弹，不像是中继
    scores['volume_shrink'] = vol_score
    total += vol_score * 0.35

    # ── 条件⑤：不破坏下降趋势结构 ──
    # 原文：无法改变原有下降趋势
    # 算法：EMA10仍然向下，EMA20支撑（反弹不能站上EMA10）
    ema10_vals = calc_ema(closes, 10)
    ema20_vals = calc_ema(closes, 20)

    # EMA10斜率（必须仍然向下）
    if len(ema10_vals) >= 3:
        ema_slope = (ema10_vals[-1] - ema10_vals[-3]) / (ema10_vals[-3] or 1)
        slope_score = 100 if ema_slope < 0 else 20  # 向下才健康（维持跌势）
    else:
        slope_score = 50
    scores['ema_slope'] = slope_score
    total += slope_score * 0.25

    # EMA10压力（反弹不能站上EMA10）
    if len(ema10_vals) >= 1 and ema10_vals[-1] > 0:
        ema10_pct = (today['close'] - ema10_vals[-1]) / ema10_vals[-1]
        if ema10_pct <= -0.02:
            ema_score = 100  # 远低于EMA10，典型的弱势反弹
        elif ema10_pct <= 0:
            ema_score = 70   # 靠近EMA10但未站上
        elif ema10_pct <= 0.02:
            ema_score = 30   # 略站上EMA10，可能改变趋势
        else:
            ema_score = 5    # 站上EMA10太多，可能不是中继
    else:
        ema_score = 50
    scores['ema_pressure'] = ema_score
    total += ema_score * 0.20

    # ── 条件⑥：反弹K线窄幅（反弹疲弱）──
    recent_ranges = [(k['high'] - k['low']) / (k['close'] or 1) for k in data[-BOUNCE_WINDOW:]]
    avg_range = sum(recent_ranges) / len(recent_ranges)
    overall_ranges = [(k['high'] - k['low']) / (k['close'] or 1) for k in data[-20:]]
    overall_avg_range = sum(overall_ranges) / len(overall_ranges)

    if overall_avg_range > 0:
        range_ratio = avg_range / overall_avg_range
        if range_ratio <= 0.6:
            kline_score = 100  # 振幅收窄，反弹无力
        elif range_ratio <= 0.8:
            kline_score = 75
        elif range_ratio <= 1.0:
            kline_score = 50
        else:
            kline_score = 25
    else:
        kline_score = 50
    scores['kline_narrow'] = kline_score
    total += kline_score * 0.0  # 权重0（作为辅助参考）

    # ── 总置信度 ──
    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append(f"反弹{bounce_pct:.1%}")
        detail_parts.append(f"量{vol_ratio:.2f}倍")
        if vol_ratio < VOLUME_SHRINK:
            detail_parts.append("缩量")

    return make_result(triggered, confidence, '下跌中继', 'downward_continuation',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
