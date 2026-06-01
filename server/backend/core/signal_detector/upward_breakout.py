"""
向上突破信号检测

原文：《量价原理》5.6(1) — 向上突破信号

发生位置：区间震荡中
量价行为：
  ① 股价突破前高（区间顶部）
  ② 成交量明显放大（成交量越大突破成功概率越高，信号越可靠）
  ③ 向上突破之前，成交量逐步萎缩（或量价比较均衡），波动收窄
     （突破前的成交量越低、波动幅度越窄信号越可靠）
  ④ 量价行为表现：放量长阳，且收盘在相对高位
  ⑤ 向上突破后能站住，2-3个交易日不再折回区间内，否则就是假突破（回测项）
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, is_big_candle, close_in_upper_third,
    detect_range_trade, volume_trend, calc_avg_range,
    make_result, SignalResult, calc_ma,
)

# ════════════════════════════════════════════
# 可调参数
# ════════════════════════════════════════════
VOLUME_THRESHOLD = 1.8       # 突破日成交量倍率阈值
BREAK_PCT = 0.01             # 突破幅度（1%）
RANGE_LOOKBACK = 30          # 区间震荡判定窗口
PRE_SHRINK_WINDOW = 10       # 突破前缩量观察窗口
BIG_CANDLE_THRESHOLD = 0.5   # 大阳线实体占比阈值
CONFIDENCE_PASS = 60         # 视为触发的最低置信度


def detect_upward_breakout(klines: List[Dict], idx: int = -1) -> SignalResult:
    """
    检测向上突破信号。

    参数：
        klines: 60天日K线，升序排列
        idx: 当前判定位置（默认-1表示最后一天）

    返回：
        SignalResult
    """
    if len(klines) < RANGE_LOOKBACK + 1:
        return make_result(False, 0, '向上突破', 'upward_breakout', '数据不足')

    # idx=-1 表示最后一天
    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < RANGE_LOOKBACK + 1:
        return make_result(False, 0, '向上突破', 'upward_breakout', '数据不足')

    today = data[-1]
    past = data[:-1]  # 突破前的历史数据

    scores = {}
    total = 0.0

    # ── 条件①：发生在区间震荡中（自适应窗口）──
    # 在强趋势中整理期短（10-20天），弱趋势中整理期长（20-30天）
    # 尝试多个窗口，取最优结果
    best_range = None
    for w in [12, 15, 20, 25]:
        if len(past) >= w:
            is_r, r_high, r_low, r_mid = detect_range_trade(past, w)
            if is_r:
                best_range = (w, r_high, r_low, r_mid)
                break

    if best_range is None:
        return make_result(False, 0, '向上突破', 'upward_breakout',
                           '非区间震荡环境', {'range': 0})

    window_used, range_high, range_low, range_mid = best_range
    scores['range_check'] = 1.0
    scores['range_window'] = window_used

    # ── 条件②：股价突破前高（区间顶部）──
    if today['close'] <= range_high * (1 + BREAK_PCT):
        return make_result(False, 0, '向上突破', 'upward_breakout',
                           f'未突破区间顶部 {range_high:.2f}',
                           {**scores, 'break_price': 0})
    break_amount = (today['close'] - range_high) / (range_high or 1)
    break_score = min(break_amount / 0.05 * 100, 100)  # 突破5%以上满分
    scores['break_price'] = break_score
    total += break_score * 0.30  # 权重30%

    # ── 条件③：成交量明显放大 ──
    vr = calc_volume_ratio(data, len(data) - 1, 20)
    if vr >= 5.0:
        vol_score = 100
    elif vr >= 3.0:
        vol_score = 80
    elif vr >= VOLUME_THRESHOLD:
        vol_score = 50 + (vr - VOLUME_THRESHOLD) / (3.0 - VOLUME_THRESHOLD) * 30
    else:
        vol_score = vr / VOLUME_THRESHOLD * 40
    scores['volume'] = vol_score
    total += vol_score * 0.25  # 权重25%

    # ── 条件④：突破前缩量 + 波动收窄 ──
    v_trend = volume_trend(data, PRE_SHRINK_WINDOW)
    if v_trend < 0:
        shrink_score = min(abs(v_trend) * 500, 100)
    else:
        shrink_score = max(100 - v_trend * 200, 0)

    recent_avg_range = calc_avg_range(data[-PRE_SHRINK_WINDOW - 1:-1], PRE_SHRINK_WINDOW)
    overall_avg_range = calc_avg_range(data[:-1], min(RANGE_LOOKBACK, len(data) - 1))
    if overall_avg_range > 0:
        range_ratio = recent_avg_range / overall_avg_range
        if range_ratio < 0.6:
            range_score = 100
        elif range_ratio < 0.8:
            range_score = 70
        elif range_ratio < 1.0:
            range_score = 50
        else:
            range_score = 20
    else:
        range_score = 50

    pre_score = shrink_score * 0.5 + range_score * 0.5
    scores['pre_shrink'] = pre_score
    total += pre_score * 0.20  # 权重20%

    # ── 条件⑤：放量长阳 + 收盘高位 ──
    candle_score = 0
    if is_big_candle(data, -1, BIG_CANDLE_THRESHOLD):
        body_ratio = (today['close'] - today['open']) / (today['high'] - today['low'] + 0.001)
        candle_score += 50 * min(abs(body_ratio) / 0.8, 1.0)

    if close_in_upper_third(data, -1):
        candle_score += 50
    else:
        amp = today['high'] - today['low']
        if amp > 0:
            pos = (today['close'] - today['low']) / amp
            candle_score += max(pos * 50, 0)

    scores['candle'] = candle_score
    total += candle_score * 0.15  # 权重15%

    # ── 条件⑥：突破后验证（仅回测模式，此处暂不计算）──
    scores['post_confirm'] = 50
    total += 50 * 0.10

    # ── 总置信度 ──
    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append(f"突破区间顶{range_high:.2f}")
        detail_parts.append(f"量{vr:.1f}倍")
        if scores.get('pre_shrink', 0) > 60:
            detail_parts.append("缩量整理充分")

    return make_result(triggered, confidence, '向上突破', 'upward_breakout',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
