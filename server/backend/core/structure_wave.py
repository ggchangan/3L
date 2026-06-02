"""
结构感知的波峰波谷统一判定 — 核心函数

《量价原理》6.2节"波段峰谷识别"的可编程实现。
先定结构（上升/下降/震荡），再按结构选对应的量价行为规则来判峰谷。

用法:
    from backend.core.structure_wave import judge_structure_wave
    result = judge_structure_wave(klines, structure='上升趋势')
"""

from typing import List, Dict, Optional
from backend.core.ema_utils import get_structure, ema_list


def _calc_bias(closes, ema_vals, period):
    """计算BIAS（乖离率）"""
    if len(closes) < period or len(ema_vals) < 1:
        return 0
    ema_val = ema_vals[-1]
    if ema_val and ema_val > 0:
        return (closes[-1] - ema_val) / ema_val * 100
    return 0


def _ma(closes, period):
    """简单移动平均"""
    if len(closes) < period:
        return closes[-1] if closes else 0
    return sum(closes[-period:]) / period


def _calc_vol_ratio(volumes):
    """量比 = 当日量 / 5日均量"""
    if len(volumes) < 6:
        return 1.0
    vma5 = sum(volumes[-6:-1]) / 5
    if vma5 > 0:
        return volumes[-1] / vma5
    return 1.0


def _calc_slope(ema_vals, lookback=3):
    """计算EMA斜率（近3根变化百分比）"""
    if len(ema_vals) < lookback + 1:
        return 0
    base = ema_vals[-lookback - 1]
    if base and base > 0:
        return (ema_vals[-1] - base) / base * 100
    return 0


def judge_structure_wave(klines: List[Dict], structure: Optional[str] = None):
    """
    统一的结构感知峰谷判定。

    Args:
        klines: 日K线列表 [{open, high, low, close, volume, date}, ...]
        structure: 可选，外部传入的结构名。不传则内部调用 get_structure()

    Returns:
        dict: {
            'position': '偏波峰'/'波中偏上'/'波中'/'波中偏下'/'偏波谷',
            'pk_score': int,       # 波峰评分 0~n
            'vl_score': int,       # 波谷评分 0~n
            'stage': str,          # 细化阶段（可用于概念板块5阶段）
            'structure': str,      # 当前结构
            'bias5': float,
            'bias10': float,
            'vol_ratio': float,
            'peak_sig': int,       # 波峰信号明细计数
            'valley_sig': int,     # 波谷信号明细计数
            'details': dict,       # 各条件判定结果
        }
    """
    if not klines or len(klines) < 20:
        return _empty_result('数据不足')

    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    opens = [k['open'] for k in klines]
    volumes = [k.get('volume', k.get('vol', 0)) for k in klines]

    # ── 计算通用指标 ──
    ema5 = ema_list(closes, 5) or [closes[-1]]
    ema10 = ema_list(closes, 10) or [closes[-1]]
    ema20 = ema_list(closes, 20) or [closes[-1]]

    bias5 = _calc_bias(closes, ema5, 5)
    bias10 = _calc_bias(closes, ema10, 10)
    ema10_slope = _calc_slope(ema10, 3)
    ema10_slope_5d = _calc_slope(ema10, 5)

    # 当日K线细节
    cur = klines[-1]
    body_pct = abs(cur['close'] - cur['open']) / cur['open'] * 100 if cur['open'] > 0 else 0
    range_pct = (cur['high'] - cur['low']) / cur['open'] * 100 if cur['open'] > 0 else 0
    us_pct = (cur['high'] - max(cur['open'], cur['close'])) / cur['open'] * 100 if cur['open'] > 0 else 0
    ls_pct = (min(cur['open'], cur['close']) - cur['low']) / cur['open'] * 100 if cur['open'] > 0 else 0
    gain = (cur['close'] - cur['open']) / cur['open'] * 100 if cur['open'] > 0 else 0
    gain_prev = (cur['close'] - klines[-2]['close']) / klines[-2]['close'] * 100 if len(klines) >= 2 else 0

    # 成交量（兼容 volume / vol 字段名）
    cur_vol = cur.get('volume', cur.get('vol', 0))
    has_volume = cur_vol > 0

    vol_ratio = _calc_vol_ratio(volumes) if has_volume else 1.0

    # 近5日涨幅分布
    gains_5d = []
    for i in range(max(0, len(closes) - 5), len(closes)):
        if i > 0:
            gains_5d.append((closes[i] - closes[i - 1]) / closes[i - 1] * 100)
    yang_count_5d = sum(1 for g in gains_5d if g > 0)
    yin_count_5d = sum(1 for g in gains_5d if g < 0)
    avg_gain_5d = sum(gains_5d) / len(gains_5d) if gains_5d else 0

    # 回调深度
    recent_high = max(closes[-5:]) if len(closes) >= 5 else closes[-1]
    pullback_pct = (recent_high - cur['close']) / recent_high * 100

    # 近5日均振幅
    recent_ranges = []
    for j in range(max(0, len(klines) - 6), len(klines) - 1):
        k = klines[j]
        recent_ranges.append((k['high'] - k['low']) / k['open'] * 100 if k['open'] > 0 else 0)
    avg_range_5d = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0

    # ── 第一步：判定结构 ──
    if structure is None:
        # 使用最近60天判定结构（避免全量数据中前期极端行情干扰）
        recent_window = max(60, min(len(closes), 80))
        structure = get_structure(closes[-recent_window:]) or '区间震荡'
        # 双重校验：如果长期趋势过于极端，参考短期EMA10斜率
        short_slope = _calc_slope(ema10, 3)
        if structure == '下降趋势' and short_slope > 0.1 and bias5 > -2:
            structure = '上升趋势'
        elif structure == '上升趋势' and short_slope < -0.1 and bias5 < 2:
            structure = '下降趋势'

    # ── 第二步：按结构选规则 ──
    pk_score = 0
    vl_score = 0
    peak_conds = {}
    valley_conds = {}

    if structure in ('上涨趋势', '上升趋势'):
        # ========== 上涨趋势规则 ==========
        # --- 波峰（需求透支型） ---
        conds_p = {}
        recent_gain_5d = sum(g for g in gains_5d)
        conds_p['有上涨基础'] = recent_gain_5d > 3
        conds_p['加速+实体收窄'] = yang_count_5d >= 3 and avg_gain_5d > 1.0 and body_pct < 0.8
        conds_p['放量滞涨'] = vol_ratio > 1.5 and body_pct < 0.8 and abs(gain_prev) < 1.5
        conds_p['缩量滞涨'] = bias5 > 3 and vol_ratio < 0.6 and body_pct < 0.5
        conds_p['长上影'] = us_pct > 2.0 and gain_prev < 1.0
        pk_score = sum(1 for v in conds_p.values() if v) if conds_p.get('有上涨基础', False) else 0
        peak_conds = conds_p

        # --- 波谷（缩量回踩型） ---
        conds_v = {}
        conds_v['不在加速区'] = bias5 < 2
        conds_v['有回调'] = pullback_pct > 1.5
        can_trigger = conds_v['不在加速区'] and conds_v['有回调']
        conds_v['缩量'] = vol_ratio < 0.7 and has_volume
        conds_v['价波收窄'] = avg_range_5d > 0 and range_pct < avg_range_5d * 0.7
        conds_v['ema10支撑'] = cur['close'] >= (ema10[-1] * 0.97) if isinstance(ema10, list) else False
        conds_v['下影线企稳'] = ls_pct > body_pct * 1.2 and ls_pct > 0.3
        conds_v['回调深度充足'] = pullback_pct > 3.0
        scoring_v = ['缩量', '价波收窄', 'ema10支撑', '下影线企稳', '回调深度充足']
        real_vl = sum(1 for k in scoring_v if conds_v.get(k, False))
        # 缩量是必要条件（原文核心：供应枯竭），其余条件≥2个
        strict_vl = conds_v.get('缩量', False) and real_vl >= 3
        normal_vl = real_vl >= 4  # 即使没缩量，4个其他条件也够
        vl_score = real_vl if (can_trigger and (strict_vl or normal_vl)) else 0
        valley_conds = conds_v

    elif structure in ('下降趋势', '下跌趋势'):
        # ========== 下降趋势规则 ==========
        # --- 波峰（反弹失败型） ---
        conds_p = {}
        recent_bias5_vals = []
        for j in range(max(0, len(closes) - 5), len(closes)):
            e5_j = ema_list(closes[:j+1], 5)
            if e5_j and e5_j[-1] > 0:
                b5_j = (closes[j] - e5_j[-1]) / e5_j[-1] * 100
                recent_bias5_vals.append(b5_j)
        had_meaningful_bounce = any(b > 2 for b in recent_bias5_vals) if recent_bias5_vals else False
        conds_p['有显著反弹'] = had_meaningful_bounce
        conds_p['反弹缩量'] = had_meaningful_bounce and vol_ratio < 0.7
        conds_p['供应重现'] = had_meaningful_bounce and vol_ratio > 1.0 and gain_prev < -1.0
        conds_p['长上影压力'] = had_meaningful_bounce and us_pct > 2.0
        conds_p['ema10压制'] = had_meaningful_bounce and cur['close'] < (ema10[-1] * 0.99)
        conds_p['bias5重新转负'] = had_meaningful_bounce and bias5 < 0 and (len(closes) < 3 or ((closes[-2] - ema5[-2]) / ema5[-2] * 100) > 0 if ema5[-2] > 0 else False)
        pk_score = sum(1 for v in conds_p.values() if v) if conds_p.get('有显著反弹', False) else 0
        peak_conds = conds_p

        # --- 波谷（恐慌抛售型） ---
        # 原文6.2.1: 下降趋势中的波谷=恐慌抛售：大跌+放量+不破位
        conds_v = {}
        conds_v['大跌'] = gain_prev < -3
        conds_v['放量'] = vol_ratio > 1.5
        conds_v['下影线'] = ls_pct > body_pct * 1.5 and ls_pct > 0.5
        conds_v['不破位'] = cur['close'] >= klines[-2]['low'] * 0.97
        conds_v['收相对高位'] = cur['close'] > (cur['high'] + cur['low']) / 2
        # 恐慌抛售模式（高质量信号）
        panic_mode = conds_v['大跌'] and conds_v['放量'] and (conds_v['不破位'] or conds_v['下影线'] or conds_v['收相对高位'])
        # 放量不跌模式（低质量但可接受）
        absorb_mode = conds_v['放量'] and not conds_v['大跌'] and conds_v['不破位'] and conds_v['收相对高位']
        # 单纯下影线不算！必须有实质性的恐慌或放量吸收
        score_v = sum(1 for v in conds_v.values() if v)
        vl_score = score_v if (panic_mode or absorb_mode) else 0
        valley_conds = conds_v

    else:  # 区间震荡
        # ========== 区间震荡规则 ==========
        recent_max = max(closes[-20:]) if len(closes) >= 20 else max(closes)
        recent_min = min(closes[-20:]) if len(closes) >= 20 else min(closes)
        range_size = (recent_max - recent_min) / recent_min * 100 if recent_min > 0 else 0
        cur_vs_max = (cur['close'] - recent_min) / (recent_max - recent_min) * 100 if recent_max > recent_min else 50

        # 波峰（区间顶+放量滞涨）
        conds_p = {}
        conds_p['近区间顶'] = cur_vs_max > 80
        conds_p['放量滞涨'] = vol_ratio > 1.3 and body_pct < 1.0
        conds_p['上影线'] = us_pct > 1.5
        conds_p['bias5转负'] = False
        if bias5 <= 0:
            conds_p['bias5转负'] = True
        pk_score = sum(1 for v in conds_p.values() if v) if any([
            conds_p['近区间顶'], conds_p['放量滞涨']
        ]) else 0
        peak_conds = conds_p

        # 波谷（区间底+缩量企稳）
        conds_v = {}
        conds_v['近区间底'] = cur_vs_max < 20
        conds_v['缩量'] = vol_ratio < 0.7
        conds_v['下影线'] = ls_pct > body_pct and ls_pct > 0.3
        conds_v['收阳企稳'] = gain > 0 or (gain >= gain_prev and gain > -0.5)
        conds_v['bias5转正'] = bias5 > 0
        vl_score = sum(1 for v in conds_v.values() if v) if any([
            conds_v['近区间底'], conds_v['缩量']
        ]) else 0
        valley_conds = conds_v

    # ── 第三步：5档判定 ──
    # 极端偏离辅助确认（不作为硬覆盖，只作为加分）
    if bias5 > 10 and structure in ('下降趋势', '下跌趋势', '区间震荡'):
        pk_score = max(pk_score, 2)
    if bias5 < -10 and structure in ('上涨趋势', '上升趋势', '区间震荡'):
        vl_score = max(vl_score, 2)

    if pk_score >= 3:
        position = '偏波峰'
    elif pk_score >= 2:
        position = '波中偏上'
    elif vl_score >= 3:
        position = '偏波谷'
    elif vl_score >= 2:
        position = '波中偏下'
    else:
        position = '波中'

    # 细化阶段（用于概念板块5阶段输出）
    stage = _determine_stage(position, structure, bias5, ema10_slope, vol_ratio, gain, pk_score, vl_score)

    return {
        'position': position,
        'pk_score': pk_score,
        'vl_score': vl_score,
        'stage': stage,
        'structure': structure,
        'bias5': round(bias5, 2),
        'bias10': round(bias10, 2),
        'ema10_slope': round(ema10_slope, 4),
        'vol_ratio': round(vol_ratio, 2),
        'peak_sig': pk_score,
        'valley_sig': vl_score,
        'details': {
            'structure': structure,
            'peak_conds': peak_conds,
            'valley_conds': valley_conds,
        },
    }


def _determine_stage(position, structure, bias5, ema10_slope, vol_ratio, gain, pk_score, vl_score):
    """细化阶段（兼容概念板块5阶段输出）"""
    if position == '偏波谷':
        return '波谷'
    if structure in ('上涨趋势', '上升趋势') and position == '波中':
        if bias5 > 5 and (pk_score >= 2 or vol_ratio > 1.5):
            return '波峰' if pk_score >= 2 else '波中'
        if vl_score >= 2 and vol_ratio < 0.7:
            return '波谷'
        if ema10_slope > 0.1:
            return '上涨'
        return '波中'
    if structure in ('下降趋势', '下跌趋势') and position == '波中':
        if vl_score >= 3:
            return '波谷'
        if ema10_slope < -0.1:
            return '下跌'
        if bias5 > 0:
            return '上涨'  # 反弹
        return '波中'
    return '波中'


def _empty_result(reason='数据不足'):
    return {
        'position': '波中',
        'pk_score': 0,
        'vl_score': 0,
        'stage': '波中',
        'structure': '--',
        'bias5': 0,
        'bias10': 0,
        'ema10_slope': 0,
        'vol_ratio': 0,
        'peak_sig': 0,
        'valley_sig': 0,
        'details': {'reason': reason},
    }
