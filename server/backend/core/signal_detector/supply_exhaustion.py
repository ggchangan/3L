"""
供应衰竭信号检测

原文：《量价原理》5.6(3) — 供应衰竭信号

供应衰竭 ≠ 放量大跌。放量大跌是供应释放（恐慌抛售），
供应衰竭是卖盘枯竭——想卖的人都卖完了，成交量萎缩到地量，
价格不再创新低，振幅收窄。

  ① 发生在下降趋势或区间震荡中（硬否决：上升趋势不产生）
  ② 下跌已持续一段时间：15日跌幅 > -5%（硬否决：跌幅不够）
  ③ 跌速放缓：近5日跌幅 < 前10日跌幅的一半，或近3日不创新低（35分）
     [供应衰竭的关键特征是卖压减轻，不是急跌]
  ④ 缩量到地量：volume_ratio < 0.6，且量比越低分越高（35分）
     [卖盘枯竭的核心标志——没人卖了]
  ⑤ 振幅收窄：近3日平均振幅 < 前10日平均振幅的60%（30分）
     [供应衰竭的辅助确认——波动率下降]

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

    # ── 条件①：发生在下降趋势或区间震荡中（硬否决）──
    trend = detect_trend(data)
    if trend == 'up':
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           '上升趋势中', {'trend': 0})

    # ── 条件②：下跌已持续一段时间（硬否决）──
    if len(closes) < 16:
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           '数据不足', {'trend_duration': 0})
    loss_15d = (closes[-1] - closes[-15]) / (closes[-15] or 1)
    if loss_15d > -0.05:  # 跌幅至少-5%
        return make_result(False, 0, '供应衰竭', 'supply_exhaustion',
                           f'跌幅不足({loss_15d:.1%})', {'trend_duration': 0})
    scores['trend_duration'] = 1.0

    # ── 条件③：跌速放缓（35分）──
    # 供应衰竭的特征是卖压减轻，不是继续急跌
    if len(closes) >= 10:
        loss_10d = (closes[-1] - closes[-10]) / (closes[-10] or 1)
    else:
        loss_10d = 0
    if len(closes) >= 5:
        loss_5d = (closes[-1] - closes[-5]) / (closes[-5] or 1)
    else:
        loss_5d = 0

    # 近3日不创新低
    no_new_low = True
    if len(data) >= 4:
        recent_low = min(k['low'] for k in data[-4:-1])  # 近3日（不含当日）最低
        for k in data[-4:]:
            if k['low'] < recent_low:
                no_new_low = False
                break

    # 跌速放缓评分
    if no_new_low:
        slowdown_score = 100  # 不创新低 = 最强衰竭信号
    elif loss_5d > loss_10d:
        slowdown_score = 80   # 近5日跌速减缓
    elif abs(loss_5d) < abs(loss_10d) * 0.5:
        slowdown_score = 60   # 近5日跌幅不到前10日的一半
    elif loss_5d > -2:
        slowdown_score = 40   # 近5日跌幅小于2%
    else:
        slowdown_score = 10   # 还在加速跌
    scores['slowdown'] = slowdown_score
    total += slowdown_score * 0.35

    # ── 条件④：缩量到地量（35分）──
    # 供应衰竭的核心：没人卖了
    vr = calc_volume_ratio(data, len(data) - 1, 20)

    if vr < 0.3:
        vol_score = 100  # 极地量，卖盘完全枯竭
    elif vr < 0.5:
        vol_score = 80   # 地量，卖盘稀少
    elif vr < 0.6:
        vol_score = 60   # 显著缩量，卖盘减少
    elif vr < 0.8:
        vol_score = 40   # 轻度缩量
    elif vr < 1.0:
        vol_score = 20   # 量能正常偏低
    else:
        vol_score = 0    # 放量——这不是衰竭，是供应释放
    scores['volume_shrink'] = vol_score
    total += vol_score * 0.35

    # ── 条件⑤：振幅收窄（30分）──
    # 供应衰竭的辅助确认：波动率下降
    if len(data) >= 13:
        recent_range = [abs(k['high'] - k['low']) for k in data[-3:]]
        prev_range = [abs(k['high'] - k['low']) for k in data[-13:-3]]
        avg_recent = sum(recent_range) / len(recent_range) if recent_range else 0
        avg_prev = sum(prev_range) / len(prev_range) if prev_range else 0
        if avg_prev > 0:
            range_ratio = avg_recent / avg_prev
            if range_ratio < 0.5:
                range_score = 100  # 振幅减半
            elif range_ratio < 0.7:
                range_score = 70   # 振幅明显收窄
            elif range_ratio < 0.9:
                range_score = 40   # 振幅略窄
            else:
                range_score = 10   # 振幅未收窄
        else:
            range_score = 30
    else:
        range_score = 30
    scores['range_narrow'] = range_score
    total += range_score * 0.30

    # ── 持续性加分：衰竭是一个过程，连续多天衰减→更可信 ──
    # 检查前3根K线，每根也符合缩量+窄幅特征的，加持续分
    sustain_count = 0
    for bi in range(max(0, end-3), end):
        bk = data[bi]
        bvr = calc_volume_ratio(data, bi, 20)
        b_range = abs(bk['high'] - bk['low'])
        avg_range = sum(abs(data[j]['high'] - data[j]['low'])
                       for j in range(max(0, bi-10), bi)) / min(bi, 10) if bi >= 10 else b_range
        # 前一根也满足：缩量(量比<0.85) 且 振幅收窄(振幅小于平均)
        if bvr < 0.85 and avg_range > 0 and b_range < avg_range * 0.85:
            sustain_count += 1

    sustain_bonus = min(sustain_count * 8, 20)  # 最多加20分
    scores['sustain'] = sustain_bonus
    total += sustain_bonus

    confidence = min(total, 85)  # 封顶85分，衰竭永远不百分百确定
    triggered = confidence >= CONFIDENCE_PASS

    detail_parts = []
    if triggered:
        detail_parts.append('卖盘枯竭')
        if no_new_low:
            detail_parts.append('不创新低')
        if vr < 0.5:
            detail_parts.append(f'地量{vr:.2f}倍')
        elif vr < 0.8:
            detail_parts.append(f'缩量{vr:.2f}倍')
        if slowdown_score >= 80:
            detail_parts.append('跌速放缓')

    return make_result(triggered, confidence, '供应衰竭', 'supply_exhaustion',
                       '，'.join(detail_parts) if detail_parts else '',
                       scores)
