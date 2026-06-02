"""
供应衰竭信号检测

原文：《量价原理》5.6(3) — 供应衰竭信号

  ① 发生在下降趋势中（否决项）
  ② 下降趋势已持续一段时间（否决项）
  ③ 缓跌后急跌形态：前10日跌幅<10% 且 今日跌幅>3%（35分）
     [注：额外考虑快速下跌后急跌的情况：前10日跌幅>=10%但今日出现放量恐慌]
  ④ 突然放量大跌：今日 volume_ratio > 2.0，且阴线实体>50%（35分）
  ⑤ 可能伴随恐慌性抛售：今日成交量 > 前20日最大量的1.2倍（30分）

注：条件③④⑤为连续评分，非硬否决，总分>60触发。
"""
from typing import List, Dict
from .base import (
    calc_volume_ratio,
    detect_trend, make_result, SignalResult,
)

CONFIDENCE_PASS = 60


def detect_supply_exhaustion(klines: List[Dict], idx: int = -1) -> SignalResult:
    if len(klines) < 30:
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion', '数据不足')

    end = idx if idx >= 0 else len(klines) - 1
    data = klines[:end + 1]
    if len(data) < 30:
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion', '数据不足')

    today = data[-1]
    scores = {}
    total = 0.0
    closes = [k['close'] for k in data]

    # ── 条件①：发生在下降趋势或区间震荡中（否决项）──
    # 注：原文要求下降趋势，但区间震荡中的急跌放量同样可视为供应衰竭
    trend = detect_trend(data)
    if trend == 'up':
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           '上升趋势中', {'trend': 0})

    # ── 条件②：下降趋势已持续一段时间（否决项）──
    if len(closes) < 16:
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           '数据不足', {'trend_duration': 0})
    loss_15d = (closes[-1] - closes[-15]) / (closes[-15] or 1)
    if loss_15d > -0.03:  # 放宽到-3%（原文没给具体值）
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           f'跌幅不足({loss_15d:.1%})', {'trend_duration': 0})
    scores['trend_duration'] = 1.0

    # ── 条件③：缓跌后急跌形态（35分）──
    if len(closes) >= 10:
        loss_10d = (closes[-1] - closes[-10]) / (closes[-10] or 1)
    else:
        loss_10d = 0

    # 今日跌幅（限幅±10%防数据异常）
    today_pct = 0
    if len(data) >= 2 and data[-2]['close'] > 0:
        raw_pct = (today['close'] - data[-2]['close']) / data[-2]['close'] * 100
        today_pct = max(min(raw_pct, 10), -10)

    # 缓跌后急跌：前10日跌幅<10% 且 今日下跌明显
    # 快速下跌后恐慌：前10日跌幅>=10%但今日放量+急跌+阴线实体大
    if loss_10d > -0.10 and today_pct < -3:
        rush_score = 100  # 经典缓跌后急跌
    elif loss_10d > -0.10 and today_pct < -2:
        rush_score = 70
    elif today_pct < -5:
        rush_score = 80  # 急跌超5%，无论前10日
    elif today_pct < -3:
        rush_score = 60  # 今日急跌
    elif today_pct < -2:
        rush_score = 40
    else:
        rush_score = 20
    scores['rush_drop'] = rush_score
    total += rush_score * 0.35

    # ── 条件④：突然放量大跌（35分）──
    vr = calc_volume_ratio(data, len(data) - 1, 20)
    is_bear = today['close'] < today['open']
    body_abs = abs(today['close'] - today['open'])
    total_range = today['high'] - today['low']
    body_ratio = body_abs / total_range if total_range > 0 else 0

    if vr >= 3.0:
        vol_score = 80
    elif vr >= 2.0:
        vol_score = 60
    elif vr >= 1.5:
        vol_score = 40
    elif vr >= 1.2:
        vol_score = 20
    else:
        vol_score = 10

    if is_bear:
        if body_ratio >= 0.5:
            vol_score += 20
        vol_score = min(vol_score, 100)
    else:
        vol_score = max(vol_score // 2, 10)

    scores['volume_surge'] = vol_score
    total += vol_score * 0.35

    # ── 条件⑤：恐慌性抛售（30分）──
    if len(data) >= 21:
        max_vol_20 = max(k['volume'] for k in data[-21:-1])
        today_vol = today['volume']
        panic_ratio = today_vol / max_vol_20 if max_vol_20 > 0 else 0
        if panic_ratio >= 1.5:
            panic_score = 100
        elif panic_ratio >= 1.2:
            panic_score = 80
        elif panic_ratio >= 1.0:
            panic_score = 50
        elif panic_ratio >= 0.8:
            panic_score = 20
        else:
            panic_score = 0
    else:
        panic_score = 30
    scores['panic'] = panic_score
    total += panic_score * 0.30

    confidence = total
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append('下降末端')
        if today_pct < -3:
            detail_parts.append(f'急跌{today_pct:.1f}%')
        if vr >= 1.5:
            detail_parts.append(f'量{vr:.1f}倍')
        if panic_score > 60:
            detail_parts.append('恐慌抛售')

    return make_result(triggered, confidence, '供应衰竭', 'supply_exhaustion',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
