"""
区间震荡中继信号检测

原文：《量价原理》5.6(4) — 中继信号·区间震荡中继

发生位置：区间震荡中
量价行为：
  区间震荡形成的必要条件，就是在区间内供需双方打成平手，力量趋于平衡。
  区间震荡中继信号产生在区间顶部和区间底部位置：
  ① 区间顶部：没有足够的需求带领股价向上突破——放量滞涨或缩量滞涨
  ② 区间底部：没有足够的供应带领股价向下突破——放量滞跌或缩量滞跌
  ③ 股价折回区间内（无法突破）
"""
from typing import List, Dict, Tuple
from .base import (
    calc_volume_ratio, calc_ma,
    detect_range_trade, make_result, SignalResult,
)

CONFIDENCE_PASS = 60
RANGE_LOOKBACK = 30         # 区间判定窗口
ZONE_THRESHOLD = 0.10       # 区间顶底附近（距顶/底10%以内）


def detect_range_continuation(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < RANGE_LOOKBACK + 5:
        return make_result(False, 0, '区间震荡中继', 'range_continuation', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < RANGE_LOOKBACK + 5:
        return make_result(False, 0, '区间震荡中继', 'range_continuation', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0

    # ── 条件①：发生在区间震荡中（否决项）──
    # 自适应窗口检测
    best_range = None
    for w in [15, 20, 25, RANGE_LOOKBACK]:
        if len(data) >= w + 2:
            is_r, rh, rl, rm = detect_range_trade(data[:-1], w)
            if is_r:
                best_range = (w, rh, rl, rm)
                break

    if best_range is None:
        return make_result(False, 0, '区间震荡中继', 'range_continuation',
                           '非区间震荡环境', {'range': 0})

    _window_used, range_high, range_low, range_mid = best_range
    range_width = range_high - range_low
    scores['range'] = 1.0

    # ── 判断当前位置（区间顶部/底部/中部）──
    today_close = today['close']
    range_pct = (today_close - range_low) / (range_width or 1)  # 0=底部, 1=顶部

    if range_pct > 1 - ZONE_THRESHOLD:
        position = 'top'     # 区间顶部附近
    elif range_pct < ZONE_THRESHOLD:
        position = 'bottom'  # 区间底部附近
    else:
        # 区间中部，不产生中继信号
        return make_result(False, 0, '区间震荡中继', 'range_continuation',
                           f'区间中部(位置{range_pct:.0%})', {**scores, 'position': 0})

    scores['position'] = 100 if position == 'top' else 100

    # ── 条件②/③：量价行为判断 ──
    vr = calc_volume_ratio(data, len(data) - 1, 20)
    body = today['close'] - today['open']
    body_abs = abs(body)
    total_range = today['high'] - today['low']
    body_ratio = body_abs / total_range if total_range > 0 else 0

    if position == 'top':
        # 区间顶部：无法突破
        # 放量滞涨（成交量大但涨不动）或 缩量滞涨（成交萎缩、价格停滞）
        price_up = body > 0  # 阳线
        price_stalled = body_abs / (today['open'] or 1) < 0.02  # 价格几乎不动

        if price_stalled and vr >= 1.5:
            # 放量滞涨：动不了，说明上方供应强
            vol_score = 100
            scores['volume_pattern'] = '放量滞涨'
        elif price_stalled and vr < 0.8:
            # 缩量滞涨：没人买，需求不足
            vol_score = 80
            scores['volume_pattern'] = '缩量滞涨'
        elif not price_up and vr >= 1.3:
            # 区间顶部阴线+放量（供应出现）
            vol_score = 70
            scores['volume_pattern'] = '顶部放量阴'
        elif vr < 0.7:
            # 缩量到顶部（供需双弱）
            vol_score = 50
            scores['volume_pattern'] = '顶部缩量'
        else:
            vol_score = 20
    else:
        # 区间底部：无法突破
        # 放量滞跌（成交量大但跌不动）或 缩量滞跌（成交萎缩、价格不跌）
        price_down = body < 0
        price_stalled = body_abs / (today['open'] or 1) < 0.02

        if price_stalled and vr >= 1.5:
            vol_score = 100  # 放量滞跌：跌不动，说明下方有需求承接
            scores['volume_pattern'] = '放量滞跌'
        elif price_stalled and vr < 0.8:
            vol_score = 80   # 缩量滞跌：没人卖了
            scores['volume_pattern'] = '缩量滞跌'
        elif not price_down and vr >= 1.3:
            vol_score = 70   # 区间底部阳线+放量（需求出现）
            scores['volume_pattern'] = '底部放量阳'
        elif vr < 0.7:
            vol_score = 50   # 缩量到底部
            scores['volume_pattern'] = '底部缩量'
        else:
            vol_score = 20

    scores['volume_behavior'] = vol_score
    total += vol_score * 0.40

    # ── 条件③：折回迹象（无法突破确认）──
    if position == 'top':
        # 在顶部但收盘在区间内，未有效突破
        if today_close < range_high * 1.01:
            back_score = 100  # 确实没突破
        else:
            back_score = 10   # 似乎突破了
    else:
        if today_close > range_low * 0.99:
            back_score = 100  # 确实没跌破
        else:
            back_score = 10

    scores['no_break'] = back_score
    total += back_score * 0.30

    # ── 条件④：成交量确认 ──
    # 检查前几日是否也在缩量/停滞
    pre_volumes = [k['volume'] for k in data[-5:-1]]
    pre_vol_avg = sum(pre_volumes) / len(pre_volumes) if pre_volumes else 1
    vol_consistency = 50
    if pre_vol_avg < calc_ma(data, 'volume', 20) * 0.8:
        vol_consistency = 80  # 持续缩量
    scores['vol_consistency'] = vol_consistency
    total += vol_consistency * 0.30

    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        loc = '顶部' if position == 'top' else '底部'
        detail_parts.append(f'区间{loc}')
        pattern = scores.get('volume_pattern', '')
        if pattern:
            detail_parts.append(pattern)
        detail_parts.append(f'量{vr:.1f}倍')

    return make_result(triggered, confidence, '区间震荡中继', 'range_continuation',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
