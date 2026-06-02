"""
向下突破信号检测

原文：《量价原理》5.6(1) — 向下突破信号

发生位置：区间震荡中
量价行为：
  ① 股价突破前低（区间底部）
  ② 成交量明显放大（成交量越大突破信号越可靠）
  ③ 向下突破之前，成交量逐步萎缩（或量价比较均衡），波动收窄
  ④ 量价行为表现：放量长阴，且收盘在相对低位
  ⑤ 向下突破后能持续，2-3个交易日不再折回区间内，
     否则反而可以判定股价倾向于见底（回测项）
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio, close_in_lower_third,
    detect_range_trade, volume_trend, calc_avg_range,
    make_result, SignalResult,
)

# ════════════════════════════════════════════
# 可调参数
# ════════════════════════════════════════════
VOLUME_THRESHOLD = 1.8       # 突破日成交量倍率阈值
BREAK_PCT = 0.01             # 突破幅度（1%）
PRE_SHRINK_WINDOW = 10       # 突破前缩量观察窗口
BIG_BEAR_THRESHOLD = 0.5    # 大阴线实体占比阈值
CONFIDENCE_PASS = 60         # 视为触发的最低置信度

# 区间震荡判定使用多个窗口（震荡时间可能长也可能短）
RANGE_WINDOWS = [12, 15, 20, 25]


def detect_downward_breakout(klines: List[Dict], idx: int = -1) -> SignalResult:
    """
    检测向下突破信号。

    参数：
        klines: 日K线，升序排列
        idx: 当前判定位置（默认-1表示最后一天）

    返回：
        SignalResult
    """
    if len(klines) < 25 + 1:
        return make_result(False, 0, '向下突破', 'downward_breakout', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < 25 + 1:
        return make_result(False, 0, '向下突破', 'downward_breakout', '数据不足')

    today = data[-1]
    past = data[:-1]  # 突破前的历史数据

    scores = {}
    total = 0.0

    # ── 条件①：发生在区间震荡中（自适应窗口）──
    # 尝试多个窗口，取最优结果
    best_range = None
    for w in RANGE_WINDOWS:
        if len(past) >= w:
            is_r, r_high, r_low, r_mid = detect_range_trade(past, w)
            if is_r:
                best_range = (w, r_high, r_low, r_mid)
                break

    if best_range is None:
        return make_result(False, 0, '向下突破', 'downward_breakout',
                           '非区间震荡环境', {'range': 0})

    _window_used, range_high, range_low, range_mid = best_range
    scores['range_check'] = 1.0

    # ── 条件②：股价突破前低（区间底部）──
    # 原文：股价突破前低（区间底部）
    # 算法：close < range_low * 0.99（跌破1%以上）
    if today['close'] >= range_low * (1 - BREAK_PCT):
        return make_result(False, 0, '向下突破', 'downward_breakout',
                           f'未跌破区间底部 {range_low:.2f}',
                           {**scores, 'break_price': 0})

    break_amount = (range_low - today['close']) / (range_low or 1)
    # 跌破幅度越大越可靠：跌破5%以上满分
    break_score = min(break_amount / 0.05 * 100, 100)
    scores['break_price'] = break_score
    total += break_score * 0.30  # 权重30%

    # ── 条件③：成交量明显放大 ──
    # 原文：成交量明显放大（成交量越大突破信号越可靠）
    # 算法：突破日成交量 / 过去20日均量
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

    # ── 条件④：突破前成交量逐步萎缩、波动收窄 ──
    # 原文：向下突破之前，成交量逐步萎缩（或量价比较均衡），波动收窄
    # 算法：前10日成交量斜率（负值=缩量）+ 前10日振幅 / 整体振幅
    v_trend = volume_trend(data, PRE_SHRINK_WINDOW)
    if v_trend < 0:
        shrink_score = min(abs(v_trend) * 500, 100)
    else:
        shrink_score = max(100 - v_trend * 200, 0)

    recent_avg_range = calc_avg_range(data[-PRE_SHRINK_WINDOW - 1:-1], PRE_SHRINK_WINDOW)
    overall_avg_range = calc_avg_range(data[:-1], min(30, len(data) - 1))
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

    # ── 条件⑤：放量长阴，收盘在相对低位 ──
    # 原文：放量长阴，且收盘在相对低位
    # 算法：实体占比>60%（大阴线），close位于下1/3
    candle_score = 0

    # 是否为阴线且实体大
    body = today['close'] - today['open']
    if body < 0:  # 阴线
        total_range = today['high'] - today['low']
        if total_range > 0:
            body_ratio = abs(body) / total_range
            if body_ratio >= BIG_BEAR_THRESHOLD:
                # 实体越大越可靠
                candle_score += 50 * min(body_ratio / 0.8, 1.0)

    # 收盘在相对低位（下1/3）
    if close_in_lower_third(data, -1):
        candle_score += 50
    else:
        amp = today['high'] - today['low']
        if amp > 0:
            pos = (today['close'] - today['low']) / amp
            # 位置越低得分越高（1-pos）
            candle_score += max((1 - pos) * 50, 0)

    scores['candle'] = candle_score
    total += candle_score * 0.15  # 权重15%

    # ── 条件⑥：突破后验证（仅回测模式）──
    # 原文：向下突破后能持续，2-3个交易日不再折回区间内
    # 回测时检查后续2-3日收盘价是否仍低于区间底部
    post_confirm = 50  # 默认中等，回测时会重新计算
    scores['post_confirm'] = post_confirm
    total += post_confirm * 0.10

    # ── 总置信度 ──
    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append(f"跌破区间底{range_low:.2f}")
        detail_parts.append(f"量{vr:.1f}倍")
        if scores.get('pre_shrink', 0) > 60:
            detail_parts.append("缩量整理充分")

    return make_result(triggered, confidence, '向下突破', 'downward_breakout',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
