#!/usr/bin/env python3
"""买点检测模块 — 基于系统B（EMA10趋势分析）

完全基于3L教材的买点定义：
- 中继买点：上升趋势中缩量回踩关键点 / 区间底部缩量企稳
- 突破买点：整理平台放量突破前高关键阻力

不使用独立于系统B的任何机械条件（已废弃check_zhongji/check_tupo）。
"""
import json, sys, os
from backend.core.data_layer import get_industry_map, PROFIT_QUALITY_PATH, ALL_STOCKS_PATH

# 导入系统B：EMA10趋势分析
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ema_utils import get_ema_arrangement, get_structure, get_stage, ema_list

def find_idx(date_str, klines):
    """找K线中指定日期的索引"""
    date_clean = date_str.replace('-', '')
    for i, k in enumerate(klines):
        k_date = str(k["date"]).replace('-', '')
        if k_date == date_clean:
            return i
    return -1

def _resolve_code(code, all_stocks):
    """统一code格式，返回(code, klines)"""
    for sec, stocks in all_stocks.items():
        if code in stocks:
            return code, stocks[code]
        # 去掉前缀再试
        raw = code
        for p in ['SH', 'SZ', 'sh', 'sz']:
            if code.startswith(p):
                raw = code[len(p):]
                break
        if raw in stocks:
            return raw, stocks[raw]
        # 6位纯数字
        raw_final = code[-6:] if len(code) >= 6 else code
        if raw_final in stocks:
            return raw_final, stocks[raw_final]
    return None, None

def _volume_ratio(klines, idx, field='volume'):
    """计算当日量/MA5均量的比值"""
    vols = [klines[idx-4+i].get(field, klines[idx-4+i].get('vol', 0)) for i in range(5)]
    vma5 = sum(vols) / 5 if all(v > 0 for v in vols) else 0
    vol = klines[idx].get(field, klines[idx].get('vol', 0))
    return vol / vma5 if vma5 > 0 else 0

def _find_support_levels(klines, idx):
    """找最近的关键支撑位（从突破点计算）"""
    highs = [k['high'] for k in klines[:idx+1]]
    closes = [k['close'] for k in klines[:idx+1]]
    opens = [k['open'] for k in klines[:idx+1]]
    
    # 找所有"突"关键点：close突破前10日最高
    supports = []
    for i in range(10, idx+1):
        if closes[i] > max(highs[i-10:i]) and closes[i] > opens[i]:
            support_price = max(highs[i-10:i])
            if support_price < closes[-1]:
                supports.append(support_price)
    
    # 从高到低排序，取距收盘≥1.5%的最近支撑
    supports = sorted(set(supports), reverse=True)
    for s in supports:
        if (closes[-1] - s) / closes[-1] >= 0.015:
            return s
    return min(highs[-20:]) if len(highs) >= 20 else None


def calc_stop_loss(klines, idx, close_price=None):
    """计算推荐止损位和止损率

    逻辑：
    - 找最近关键支撑位
    - 止损位 = 支撑位 × 0.98（支撑下方2%防假破）
    - 若找不到支撑，用EMA20 × 0.97（EMA下方3%）

    返回: (stop_loss_price, stop_loss_pct)
    """
    if idx < 10 or not klines or len(klines) <= idx:
        return (None, None)

    closes = [k['close'] for k in klines[:idx+1]]
    cur = close_price or closes[-1]
    support = _find_support_levels(klines, idx)
    if support is not None and support > 0:
        sl = round(support * 0.98, 2)
    else:
        # 退而求其次：用EMA20
        from backend.core.ema_utils import ema_list
        ema20 = ema_list(closes, 20)
        if ema20[-1] and ema20[-1] > 0:
            sl = round(ema20[-1] * 0.97, 2)
        else:
            return (None, None)
    sl_pct = round((cur - sl) / cur * 100, 2) if cur > 0 else None
    return (sl, sl_pct)


def _layer2_factor(is_main_line=True):
    """第2层：板块主线系数调整
    主线板块（动量评分领先）：资金聚集，供应衰竭可信 → 放宽5%（×1.05）
    非主线板块：不被资金关注，缩量不可靠 → 大幅收紧（×0.80）
    """
    return 1.05 if is_main_line else 0.80


def _shrink_threshold(market_position='', is_main_line=True):
    """根据市场环境和板块主线动态调整缩量阈值
    
    三层递进：
      第1层 大盘 → 基准阈值（0.70~0.85）
      第2层 板块 → 系数调整（主线×1.05 / 非主线×0.95）
      第3层 个股 → 不调阈值，只决定买点类型
    """
    mapping = {
        '波峰': 0.85, '波中偏上': 0.85,
        '波中': 0.80,
        '波中偏下': 0.75,
        '波谷': 0.70,
    }
    base = mapping.get(market_position, 0.80)
    factor = _layer2_factor(is_main_line)
    return round(base * factor, 2)


def _surge_threshold(market_position='', is_main_line=True):
    """放量阈值 — 含板块系数调整
    主线：阈值更低（易达标），非主线：阈值更高（需更强放量）
    """
    mapping = {
        '波峰': 1.2, '波中偏上': 1.25,
        '波中': 1.3,
        '波中偏下': 1.4,
        '波谷': 1.5,
    }
    base = mapping.get(market_position, 1.3)
    factor = _layer2_factor(is_main_line)
    # 主线放宽(base变小)，非主线收紧(base变大)
    return round(base / factor, 2)


def _breakout_score(close, prev_close, prev_10d_high, vol_ratio, body_ratio, high=None, low=None):
    """多维评分判定突破有效性 — 替代单一量比阈值
    
    硬条件（必须满足）：
    - 放量：量比 > 1.2（涨停日豁免）
    - 收高位：收盘 > 当日振幅中点
    
    4维度评分，总分≥5分为有效突破：
    - 突破幅度分：收盘突破前高多远
    - 涨幅分：当日涨多少
    - 量比分：量能放大程度
    - 实体分：K线实体占振幅比
    
    涨停日豁免：日涨幅≥+9.5%时，量比条件跳过（涨停=需求碾压）
    """
    # 判断涨停
    gain = (close - prev_close) / prev_close * 100 if prev_close else 0
    is_limit_up = gain >= 9.5
    
    # 硬条件：必须放量（涨停日豁免）
    if not is_limit_up and vol_ratio <= 1.1:
        return False, 0, {'reason': f'量比{vol_ratio:.2f}≤1.1，未放量' if not is_limit_up else '涨停豁免'}
    
    # 硬条件：必须收在相对高位
    if high is not None and low is not None and high > low:
        mid_point = (high + low) / 2
        if close <= mid_point and not is_limit_up:
            return False, 0, {'reason': f'收盘{close}≤中点{mid_point:.2f}，未收高位'}
    
    break_pct = (close - prev_10d_high) / prev_10d_high * 100 if prev_10d_high else 0
    
    # 突破幅度分（越高越好）
    s1 = 3 if break_pct > 5 else (2 if break_pct > 3 else (1 if break_pct > 1 else 0))
    # 涨幅分（越大越好）
    s2 = 3 if gain > 7 else (2 if gain > 5 else (1 if gain > 3 else 0))
    # 量比分（涨停豁免给3分满分，非涨停按实际量比）
    if is_limit_up:
        s3 = 3
    else:
        s3 = 3 if vol_ratio > 1.6 else (2 if vol_ratio > 1.4 else (1 if vol_ratio > 1.1 else 0))
    # 实体分（实体饱满说明需求主动）
    s4 = 2 if body_ratio > 0.7 else (1 if body_ratio > 0.5 else 0)
    
    total = round(s1 + s2 + s3 + s4, 1)
    return total >= 5, round(total, 1), {'break_pct': round(break_pct, 2), 's1': s1, 's2': s2, 's3': s3, 's4': s4,
        'is_limit_up': is_limit_up, 'limit_up_skip': is_limit_up}


def _check_pullback(klines, idx, close, ema5_val, ema10_val, ema20_val):
    """回踩到位检查 — 二选一满足即可
    
    1. 距关键点支撑 < 2%
    2. 乖离率(EMA5/10/20最近)在±2%范围
    """
    # ① 关键点支撑检查
    support = _find_support_levels(klines, idx)
    if support:
        dist = (close - support) / support * 100
        if abs(dist) < 2:
            return True, f'关键支撑(sup{support:.0f},距{dist:+.2f}%)'
    
    # ② 最近均线乖离率检查（哪条近算哪条）
    min_bias = None
    min_name = ''
    for name, val in [('EMA5', ema5_val), ('EMA10', ema10_val), ('EMA20', ema20_val)]:
        if val and val > 0:
            bias = abs((close - val) / val * 100)
            if min_bias is None or bias < min_bias:
                min_bias = bias
                min_name = name
    
    if min_bias is not None and min_bias <= 2:
        return True, f'{min_name}支撑(乖离{min_bias:.2f}%)'
    
    return False, '未回踩到位'


def _is_extreme_shrink(klines, idx):
    """地量判断: 当日量是否低于近20日量能的15%分位"""
    start = max(0, idx - 19)
    vols = sorted([klines[j].get('volume', 0) for j in range(start, idx)])
    if len(vols) < 5:
        return False
    # 15%分位 = 排序后第15%位置的量
    pct_pos = max(0, int(len(vols) * 0.15) - 1)
    threshold = vols[pct_pos]
    current_vol = klines[idx].get('volume', 0)
    return current_vol <= threshold, threshold, current_vol
def _ema_list(data, period):
    """计算EMA列表"""
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r


def _is_trend_with_ema5(klines, idx):
    """判断是否为沿EMA5上行的趋势票

    条件：
    1. 上涨趋势（structure == '上涨趋势'）
    2. 阶段为'上行'或'缩量整理'（排除加速/滞涨/转弱）
    3. 末15根K线中 ≥60%收盘在EMA5上方（贴着EMA5走）
    4. 最近3天收盘不能跌破EMA10（站在10线上）
    5. EMA5/10/20/30多头排列并向上发散
    6. 末30根最低点起涨幅≥30%
    """
    closes = [k['close'] for k in klines[:idx+1]]
    if len(closes) < 30:
        return False

    structure = get_structure(closes)
    if structure != '上涨趋势':
        return False

    highs_60 = [k['high'] for k in klines[:idx+1]]
    lows_60 = [k['low'] for k in klines[:idx+1]]
    vols_60 = [k.get('volume', k.get('vol', 0)) for k in klines[:idx+1]]
    stage = get_stage(closes, structure, highs_60, lows_60, volumes=vols_60)
    if stage not in ('上行', '缩量整理'):
        return False

    # 计算EMA5/10/20/30
    ema5 = _ema_list(closes, 5)
    ema10 = ema_list(closes, 10)
    ema20 = ema_list(closes, 20)
    ema30 = ema_list(closes, 30)

    last15_close = closes[-15:]
    last15_ema5 = [v for v in ema5[-15:] if v is not None]
    last15_ema10 = [v for v in ema10[-15:] if v is not None]

    if len(last15_ema5) < 15 or len(last15_ema10) < 15:
        return False

    # 条件：≥60%的K线收盘在EMA5上方
    above_count = sum(1 for i in range(15) if last15_close[i] > last15_ema5[i])
    if above_count / 15 < 0.60:
        return False

    # 条件：最近3天收盘不能跌破EMA10
    for i in range(-3, 0):
        if last15_close[i] < last15_ema10[i]:
            return False

    # 条件：EMA5/10/20/30多头排列并向上发散
    # 多头排列：E5 > E10 > E20 > E30
    # 向上发散：各EMA斜率都为正（末3根上升）
    e5v, e10v, e20v, e30v = ema5[-1], ema10[-1], ema20[-1], ema30[-1]
    if not all([e5v, e10v, e20v, e30v]):
        return False
    if not (e5v > e10v > e20v > e30v):
        return False

    # 各EMA末3根斜率向上
    for ema in [ema5, ema10, ema20, ema30]:
        e_last3 = [v for v in ema[-3:] if v is not None]
        if len(e_last3) < 3:
            return False
        if e_last3[-1] <= e_last3[0]:
            return False

    # 条件：涨幅足够大（从阶段最低点起至少30%）
    low_30 = min(closes[-30:])
    gain_30 = (closes[-1] - low_30) / low_30 * 100
    if gain_30 < 30:
        return False

    return True


def detect_huicai_buy_point(code, date_str, all_stocks):
    """盈利模式2 — 趋势票回踩EMA5买点

    条件：
    1. 趋势票（_is_trend_with_ema5）
    2. 当前收盘在EMA5附近（±1.5%范围内）= 回踩到了
    3. 评分固定5分，不考虑大盘/主线系数调整

    返回 dict 或 None
    """
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None

    idx = find_idx(date_str, kls)
    if idx < 30:
        return None

    if not _is_trend_with_ema5(kls, idx):
        return None

    closes = [k['close'] for k in kls[:idx+1]]
    ema5 = _ema_list(closes, 5)
    cur_ema5 = ema5[-1]
    cur_close = kls[idx]['close']

    if not cur_ema5 or cur_ema5 <= 0:
        return None

    # 当前收盘在EMA5附近 ±1.5%
    deviation = (cur_close - cur_ema5) / cur_ema5 * 100
    if abs(deviation) > 1.5:
        return None

    return {
        'code': resolved_code,
        'buy_type': '回踩买点',
        'score': 5,
        'close': round(cur_close, 2),
        'gain': round((cur_close - kls[idx-1]['close']) / kls[idx-1]['close'] * 100, 2) if idx > 0 else 0,
        'structure': '上涨趋势',
        'stage': '沿EMA5趋势',
        'ema_arrangement': get_ema_arrangement(closes),
        'detail': {
            'reason': '趋势票回踩EMA5',
            'ema5': round(cur_ema5, 2),
            'deviation_pct': round(deviation, 2),
        },
        'flags': '回踩买点',
    }


def check_trend_stock(code, date_str, all_stocks):
    """公开接口：检查个股是否为趋势股（满足6条件）"""
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return False
    idx = find_idx(date_str, kls)
    if idx < 30:
        return False
    return _is_trend_with_ema5(kls, idx)


def scan_huicai_buy_points(date_str, all_stocks):
    """批量扫描盈利模式2 — 回踩买点"""
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            try:
                bt = detect_huicai_buy_point(code, date_str, all_stocks)
                if bt:
                    name = stocks[code][0].get('name', code) if stocks[code] else code
                    bt['name'] = name
                    bt['sector'] = sec_name
                    results.append(bt)
            except Exception:
                continue
    results.sort(key=lambda x: -x['score'])
    return results


def detect_buy_point(code, date_str, all_stocks, market_position='', main_lines=None):
    """基于系统B判断买点 — 返回 dict 或 None
    
    三层递进判定框架：
      第1层 大盘 -> market_position 决定基准阈值
      第2层 板块 -> main_lines 决定系数调整（+5%/-5%）
      第3层 个股 -> EMA10结构/阶段 决定买点类型
    """
    main_line_set = set(main_lines) if main_lines else set()
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None
    
    idx = find_idx(date_str, kls)
    if idx < 30:
        return None
    
    k = kls[idx]
    close = k['close']
    vol = k.get('volume', k.get('vol', 0))
    high = k['high']
    low = k['low']
    prev_close = kls[idx-1]['close']
    gain = (close - prev_close) / prev_close * 100 if prev_close else 0
    
    # ====== 系统B分析 ======
    closes_60 = [k['close'] for k in kls[:idx+1]]
    highs_60 = [k['high'] for k in kls[:idx+1]]
    lows_60 = [k['low'] for k in kls[:idx+1]]
    vols_60 = [k.get('volume', k.get('vol', 0)) for k in kls[:idx+1]]
    
    structure = get_structure(closes_60)
    stage = get_stage(closes_60, structure, highs_60, lows_60, volumes=vols_60)
    ema_arr = get_ema_arrangement(closes_60)
    
    # ====== 支撑/阻力（提前计算，供突破确认用） ======
    prev_10d_high = max(kls[idx-j]['high'] for j in range(1, 11)) if idx >= 10 else None
    is_breakout = prev_10d_high and close > prev_10d_high  # 突破前10日最高
    
    # ====== 突破后3天确认机制 ======
    # 突破日买入，但结构改变需要3天确认
    # 只有在结构从非上涨趋势变成上涨趋势的那次突破才允许
    _original_structure = structure
    _structure_changed_uptrend = False
    if idx >= 13:
        for back in range(idx-1, max(10, idx-5)-1, -1):
            bk2 = kls[back]
            bc2 = bk2['close']
            bp2 = kls[back-1]['close']
            b10h2 = max(kls[back-j]['high'] for j in range(1, 11))
            if bc2 <= b10h2 or bc2 <= bk2['open']:
                continue
            bvr2 = _volume_ratio(kls, back)
            bb2 = abs(bc2 - bk2['open'])
            br2 = bk2['high'] - bk2['low']
            bbr2 = bb2 / br2 if br2 > 0 else 0
            is_valid, _, _ = _breakout_score(bc2, bp2, b10h2, bvr2, bbr2, high=bk2['high'], low=bk2['low'])
            if not is_valid:
                continue
            
            # 向前确认：突破后3天内价格是否保持在关键点之上
            confirmed = True
            for cf in range(1, 4):
                if back + cf >= len(kls):
                    confirmed = False
                    break
                if kls[back + cf]['close'] < b10h2:
                    confirmed = False
                    break
            
            if confirmed and structure != '上涨趋势':
                structure = '上涨趋势'
                stage = get_stage(closes_60, structure, highs_60, lows_60, volumes=vols_60)
                # 记录结构变化发生在哪天
                _structure_changed_uptrend = True
            break  # 只检查最近的一次突破
    
    # ====== 量能分析（三层递进：大盘→基准，板块→系数，个股→不调） ======
    vol_ratio = _volume_ratio(kls, idx)
    # 第2层：此股票所属板块是否是主线
    # 使用同花顺行业板块（与主线评分一致的口径）判断
    is_main_line = False
    try:
        if main_line_set and resolved_code:
            _imd = getattr(detect_buy_point, '_ind_map', None)
            if _imd is None:
                _imd = get_industry_map()  # 从数据层读取
                detect_buy_point._ind_map = _imd
            if _imd and resolved_code in _imd:
                stock_ind = _imd[resolved_code]
                ths_ind = stock_ind.get('ths_industry', '') if isinstance(stock_ind, dict) else ''
                if ths_ind in main_line_set:
                    is_main_line = True
    except Exception:
        # 回退到按方向判断
        for sec_name, sec_stocks in all_stocks.items():
            if resolved_code in sec_stocks and sec_name in main_line_set:
                is_main_line = True
                break
    shrink_th = _shrink_threshold(market_position, is_main_line)
    is_shrink = vol_ratio < shrink_th
    
    # ====== 突破多维评分（替代旧的 is_surge 单一量比阈值） ======
    # K线实体占振幅比
    body = abs(close - k['open'])
    rng = high - low
    body_ratio = body / rng if rng > 0 else 0
    # 突破评分
    is_breakout_valid = False
    breakout_score = 0
    breakout_detail = {}
    
    # ====== 买点判定 ======
    # 以3L框架为主（structure/stage/volume量价分析），趋势股仅用于打标签
    # 不走 detect_huicai_buy_point（趋势股条件会抢先截胡，忽略量价形态）
    buy_type = None
    score = 0
    detail = {}

    # 上涨趋势 + 滞涨/转弱 → 不产生买点（阶段→卖出优先于形态→买入）
    if structure == '上涨趋势' and stage in ('滞涨', '转弱'):
        return None

    if structure == '上涨趋势':
        # ====== 中继买点（新规则） ======
        # 计算涨跌幅（从昨收）
        gain_pct = (close - prev_close) / prev_close * 100 if prev_close else 0
        # 计算EMA5/10/20（用于回踩到位检查）
        closes_ema = [k['close'] for k in kls[:idx+1]]
        ema5_val = _ema_list(closes_ema, 5)[-1] if len(closes_ema) >= 5 else None
        ema10_val = _ema_list(closes_ema, 10)[-1] if len(closes_ema) >= 10 else None
        ema20_val = _ema_list(closes_ema, 20)[-1] if len(closes_ema) >= 20 else None
        
        if is_shrink:
            # 实体条件：地量（分位法）不限，普通缩量需小实体
            extreme_shrink_result = _is_extreme_shrink(kls, idx)
            is_extreme_shrink = extreme_shrink_result if isinstance(extreme_shrink_result, bool) else extreme_shrink_result[0]
            is_small_body = -3 <= gain_pct <= 2
            body_ok = is_extreme_shrink or is_small_body
            
            if body_ok:
                # 回踩到位检查
                pullback_ok, pullback_reason = _check_pullback(kls, idx, close, ema5_val, ema10_val, ema20_val)
                if pullback_ok:
                    buy_type = '中继买点'
                    score = 3
                    detail = {
                        'reason': f'缩量回踩({pullback_reason})',
                        'structure': structure,
                        'stage': stage,
                        'vol_ratio': round(vol_ratio, 2),
                        'shrink': True,
                        'gain_pct': round(gain_pct, 2),
                        'pullback_reason': pullback_reason,
                    }
        
    if is_breakout:
        # 多维评分判定突破有效性
        is_breakout_valid, breakout_score, breakout_detail = _breakout_score(
            close, prev_close, prev_10d_high, vol_ratio, body_ratio, high=high, low=low
        )
    
    # 上涨趋势中不产生突破买点：3天内已有评分≥6的有效突破就跳过
    _has_recent_breakout = False
    if idx >= 12:
        for back in range(max(11, idx-3), idx):
            bk = kls[back]
            bc = bk['close']
            bp = kls[back-1]['close']
            b10h = max(kls[back-j]['high'] for j in range(1, 11))
            if bc <= b10h or bc <= bk['open']:
                continue
            bvr = _volume_ratio(kls, back)
            bb = abs(bc - bk['open'])
            br = bk['high'] - bk['low']
            bbr = bb / br if br > 0 else 0
            _bs = _breakout_score(bc, bp, b10h, bvr, bbr, high=bk['high'], low=bk['low'])
            if _bs[0] and _bs[1] >= 6:
                _has_recent_breakout = True
                break
    
    should_skip_breakout_buy = _has_recent_breakout
    
    if is_breakout and is_breakout_valid and not should_skip_breakout_buy:
            # 突破前高 → 突破买点（有更高的优先级，覆盖中继）
            buy_type = '突破买点'
            score = 4
            detail = {
                'reason': f'突破前高(评分{breakout_score})',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'breakout_pct': round((close - prev_10d_high) / prev_10d_high * 100, 2),
                'breakout_score': breakout_score,
                'breakout_detail': breakout_detail,
            }
    
    elif structure == '区间震荡':
        if stage == '区间底部' and is_shrink:
            # 区间底部缩量企稳 → 中继买点
            buy_type = '中继买点'
            score = 3
            detail = {
                'reason': '区间底部缩量企稳',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'shrink': True,
            }
        
        if stage == '区间顶部' and is_breakout:
            # 多维评分判定突破有效性
            is_breakout_valid, breakout_score, breakout_detail = _breakout_score(
                close, prev_close, prev_10d_high, vol_ratio, body_ratio, high=high, low=low
            )
        
        if stage == '区间顶部' and is_breakout and is_breakout_valid:
            # 区顶放量突破 → 突破买点
            buy_type = '突破买点'
            score = 4
            detail = {
                'reason': f'区顶突破(评分{breakout_score})',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'breakout_pct': round((close - prev_10d_high) / prev_10d_high * 100, 2),
                'breakout_score': breakout_score,
                'breakout_detail': breakout_detail,
            }
    
    if not buy_type:
        return None
    
    return {
        'code': resolved_code,
        'buy_type': buy_type,
        'score': score,
        'close': round(close, 2),
        'gain': round(gain, 2),
        'vol_ratio': round(vol_ratio, 2),
        'structure': structure,
        'stage': stage,
        'ema_arrangement': ema_arr,
        'detail': detail,
        'flags': buy_type,  # 兼容接口
    }


def scan_all_stocks(date_str, all_stocks, market_position='', main_lines=None, watchlist_codes=None):
    """扫描所有股票，返回买点列表
    
    参数:
        main_lines: 主线板块名单（用于第2层阈值调整）
        watchlist_codes: set of codes，非空时只扫描这些自选股
    """
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            if watchlist_codes and code not in watchlist_codes:
                continue
            try:
                bt = detect_buy_point(code, date_str, all_stocks, market_position=market_position, main_lines=main_lines)
                if bt:
                    name = stocks[code][0].get('name', code) if stocks[code] else code
                    bt['name'] = name
                    bt['sector'] = sec_name
                    results.append(bt)
            except Exception:
                continue
    
    # 排序：突破买点优先于中继，同类型按score
    results.sort(key=lambda x: (0 if x['buy_type'] == '突破买点' else 1, -x['score']))
    return results


def format_buy_signals(date_str, all_stocks, main_lines, top_n=5, market_position='', watchlist_codes=None):
    """格式化输出买点信号（按主线板块优先，三层阈值感知）"""
    scan_results = scan_all_stocks(date_str, all_stocks, market_position=market_position, main_lines=main_lines, watchlist_codes=watchlist_codes)
    ml_set = set(main_lines) if main_lines else set()
    
    result = {"date": date_str}
    
    zhongji = [x for x in scan_results if x['buy_type'] == '中继买点']
    tupo = [x for x in scan_results if x['buy_type'] == '突破买点']
    
    result['zhongji_main'] = [x for x in zhongji if x['sector'] in ml_set][:top_n]
    result['zhongji_nonmain'] = [x for x in zhongji if x['sector'] not in ml_set][:top_n]
    result['tupo_main'] = [x for x in tupo if x['sector'] in ml_set][:top_n]
    result['tupo_nonmain'] = [x for x in tupo if x['sector'] not in ml_set][:top_n]
    
    return result


def check_profit_model1(code, date_str, all_stocks):
    """盈利模式1检查 — MA10朝上 + 近10日涨停 + 回踩买点 + 业绩好"""
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None
    
    idx = find_idx(date_str, kls)
    if idx < 15:
        return None
    
    k = kls[idx]
    close = k["close"]
    
    # ① MA10持续朝上
    ma10_now = sum(kls[idx-9+i]["close"] for i in range(10)) / 10
    ma10_5ago = sum(kls[idx-14+i]["close"] for i in range(10)) / 10
    ma10_up = ma10_now > ma10_5ago
    
    # ② 近10日涨停过
    has_limit_up = False
    for j in range(1, 11):
        if idx - j < 0:
            break
        prev = kls[idx-j-1]["close"] if idx-j-1 >= 0 else kls[idx-j]["open"]
        d_gain = (kls[idx-j]["close"] - prev) / prev * 100 if prev > 0 else 0
        if d_gain >= 9.5:
            has_limit_up = True
            break
    
    # ③ 回踩买点（用系统B检测）
    bt = detect_buy_point(code, date_str, all_stocks, main_lines=None)
    has_huicai = bt and bt['buy_type'] in ('中继买点', '突破买点')
    
    # ④ 业绩好
    try:
        from profit_quality_check import check_profit_quality
        perf_res = check_profit_quality(resolved_code)
        has_perf = perf_res['pass']
    except ImportError:
        try:
            cache_path = PROFIT_QUALITY_PATH
            if os.path.exists(cache_path):
                cache = json.load(open(cache_path))
                has_perf = resolved_code in cache.get('passed_codes', [])
            else:
                has_perf = True
        except:
            has_perf = True
    
    conditions = {
        "ma10_up": ma10_up,
        "has_limit_up": has_limit_up,
        "has_huicai": has_huicai,
        "has_perf": has_perf,
    }
    score_val = sum(1 for v in conditions.values() if v)
    
    return {
        "match": score_val >= 4,
        "score": score_val,
        "total": 4,
        "conditions": conditions,
        "detail": {
            "ma10_now": round(ma10_now, 2),
            "ma10_5ago": round(ma10_5ago, 2),
            "limit_up": "有" if has_limit_up else "无",
            "has_perf": has_perf,
        },
        "model": "盈利模式1",
    }


def scan_profit_model1(date_str, all_stocks, only_watchlist=None):
    """批量扫描盈利模式1（保持接口兼容）"""
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            if only_watchlist and code not in only_watchlist:
                continue
            name = stocks[code][0].get("name", code) if stocks[code] else code
            res = check_profit_model1(code, date_str, all_stocks)
            if res and res["match"]:
                results.append({"code": code, "name": name, "sector": sec_name, **res})
    return results

# ====== 数据获取（共享函数） ======

STOCKS_FILE = ALL_STOCKS_PATH

def get_realtime_kline(code, direction):
    """从all_stocks_60d.json缓存读已有K线，再追加今日腾讯实时行情
    统一单位：缓存(mootdx)=股，腾讯实时(手→×100→股)
    返回 [{date, open, close, high, low, volume}, ...]
    """
    import requests
    from datetime import datetime

    klines = []
    if os.path.isfile(STOCKS_FILE):
        try:
            with open(STOCKS_FILE) as f:
                data = json.load(f)
            stocks = data.get('stocks', data) if isinstance(data, dict) else data
            sec_stocks = stocks.get(direction, {}) if isinstance(stocks, dict) else {}
            if code in sec_stocks:
                cached = sec_stocks[code]
                if isinstance(cached, list):
                    klines = list(cached)  # 复制，不修改原缓存
        except:
            pass

    qcode = code
    if not code.startswith(('sh', 'sz', 'SH', 'SZ')):
        qcode = ('sh' if code.startswith(('6', '9')) else 'sz') + code
    try:
        r = requests.get(f'https://qt.gtimg.cn/q={qcode}',
                         headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                         timeout=5)
        line = r.text
        try:
            line = line.decode('gbk')
        except:
            pass
        fields = line.split('"')[1].split('~') if '"' in line else []
        if len(fields) >= 40:
            today_str = datetime.now().strftime('%Y-%m-%d')
            # 腾讯fields[6]单位是手，缓存单位是股，×100统一
            today_vol = (int(fields[6]) if fields[6].isdigit() else 0) * 100
            if klines and str(klines[-1].get('date', '')).replace('-', '') == datetime.now().strftime('%Y%m%d'):
                klines[-1]['close'] = float(fields[3]) if fields[3] else klines[-1]['close']
                klines[-1]['high'] = max(float(fields[33]) if fields[33] else 0, klines[-1]['high'])
                klines[-1]['low'] = min(float(fields[34]) if fields[34] else float('inf'), klines[-1]['low'])
                klines[-1]['volume'] = today_vol or klines[-1]['volume']
            else:
                last_close = klines[-1]['close'] if klines else 0
                klines.append({
                    'date': today_str,
                    'open': float(fields[5]) if fields[5] else last_close,
                    'close': float(fields[3]) if fields[3] else last_close,
                    'high': float(fields[33]) if fields[33] else last_close,
                    'low': float(fields[34]) if fields[34] else last_close,
                    'volume': today_vol or 0,
                })
    except:
        pass

    return klines


# ====== 公共批量检查函数 ======

def find_latest_date_in_data(all_stocks, default_date):
    """找到all_stocks中所有K线的最大日期"""
    latest = ''
    for sec_name, stocks in all_stocks.items():
        for code, kls in stocks.items():
            if kls:
                d = kls[-1].get('date', '')
                if d > latest:
                    latest = d
    return latest if latest else default_date

def check_profit_model1_on_signals(buy_signals, all_stocks, check_date):
    """对每个买点信号检查是否符合盈利模式1，添加标记"""
    if not all_stocks:
        return buy_signals
    actual_date = find_latest_date_in_data(all_stocks, check_date)
    if actual_date != check_date:
        print(f"[盈利模式1] 使用数据中最新日期: {actual_date} (原请求: {check_date})")
    updated = []
    for sig in buy_signals:
        code = sig.get('code', '')
        if not code:
            updated.append(sig)
            continue
        res = check_profit_model1(code, actual_date, all_stocks)
        sig['profit_model1'] = bool(res and res['match'])
        updated.append(sig)
    return updated

def check_trend_stock_on_signals(buy_signals, all_stocks, check_date):
    """对每个买点信号检查是否为趋势股，添加标记"""
    if not all_stocks:
        return buy_signals
    actual_date = find_latest_date_in_data(all_stocks, check_date)
    if actual_date != check_date:
        print(f"[趋势股] 使用数据中最新日期: {actual_date} (原请求: {check_date})")
    updated = []
    for sig in buy_signals:
        code = sig.get('code', '')
        if not code:
            updated.append(sig)
            continue
        sig['trend_stock'] = bool(check_trend_stock(code, actual_date, all_stocks))
        updated.append(sig)
    return updated


def gen_trade_chart_svg(kls, signals, stock_name, code, chart_abs):
    """生成带买卖标注的交易K线SVG图（独立于server.py，可供多个端调用）

    Args:
        kls: K线列表 [{date,open,high,low,close,volume}]
        signals: 信号列表 [{n,date,type,entry,exit,exit_date,gain,cum_gain,days}]
        stock_name: 股票名称
        code: 股票代码
        chart_abs: SVG输出路径
    Returns:
        bool: 是否生成成功
    """
    try:
        cl = [k['close'] for k in kls]
        hi = [k['high'] for k in kls]
        lo = [k['low'] for k in kls]
        op = [k['open'] for k in kls]
        vo = [k.get('volume', 0) for k in kls]
        n = len(kls)
        mx, mn = max(hi), min(lo)
        rg = mx - mn if mx != mn else 1
        e5 = _ema_list(cl, 5)
        e10 = _ema_list(cl, 10)
        e20 = _ema_list(cl, 20)
        vm = max(vo) if max(vo) > 0 else 1

        sv = []
        sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="900" viewBox="0 0 1200 900">')
        sv.append('<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a1a2e"/><stop offset="100%" stop-color="#16213e"/></linearGradient><filter id="sh"><feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.3"/></filter></defs>')
        sv.append(f'<rect width="1200" height="900" fill="url(#bg)"/>')
        sv.append(f'<text x="600" y="26" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#fff" font-weight="bold">{stock_name}({code}) 交易 — {len(signals)}笔信号</text>')
        # ── Layout constants ──
        pl, pr, pt, pb = 70, 40, 50, 120
        ec_top = 690          # equity curve panel top
        pnl_top = 800         # P&L distribution panel top
        svg_w, svg_h = 1200, 900
        cw = (svg_w - pl - pr) / n
        bv = svg_h - pb - 50  # volume bars baseline
        px = lambda i: pl + i * cw + cw / 2
        py = lambda v: pt + (mx - v) / rg * (svg_h - pt - pb - 50 - 120)
        for i in range(5):
            yv = mx - i * rg / 4
            yp = py(yv)
            sv.append(f'<line x1="{pl}" y1="{yp}" x2="{1160}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
            sv.append(f'<text x="{pl - 4}" y="{yp + 3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#666">{yv:.0f}</text>')
        sv.append(f'<line x1="{pl}" y1="{bv}" x2="{1160}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
        # 量能柱
        for ii in range(n):
            x = px(ii) - cw * 0.35
            w = max(cw * 0.55, 1)
            vh = vo[ii] / vm * 45
            sv.append(f'<rect x="{x:.1f}" y="{bv - vh:.1f}" width="{w:.1f}" height="{max(vh, 0.5):.1f}" fill="{"#ff4444" if cl[ii] >= op[ii] else "#44aa44"}" opacity="0.25"/>')
        # EMA
        for ev, clr in [(e5, "#ffd700"), (e10, "#ff6b6b"), (e20, "#4ecdc4")]:
            pts = [f"{px(i):.1f},{py(ev[i]):.1f}" for i in range(n) if ev[i] is not None]
            if pts:
                sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="1.2" opacity="0.7"/>')
        # K线
        for ii in range(15, n):
            x = px(ii) - cw * 0.3
            w = cw * 0.4
            o, c, h, l = op[ii], cl[ii], hi[ii], lo[ii]
            kc = "#ff4444" if c >= o else "#44aa44"
            bt, bb = py(max(o, c)), py(min(o, c))
            sv.append(f'<rect x="{x:.1f}" y="{bt:.1f}" width="{w:.1f}" height="{max(bb - bt, 1):.1f}" fill="{kc}" opacity="0.85" rx="1"/>')
            sv.append(f'<line x1="{px(ii):.1f}" y1="{py(h):.1f}" x2="{px(ii):.1f}" y2="{py(l):.1f}" stroke="{kc}" stroke-width="1" opacity="0.85"/>')
        # 买卖标注（区分3L和趋势）
        for s in signals:
            is_trend = s.get('trading_system') == 'trend'
            si = find_idx(s['date'], kls)
            if si < 0:
                continue
            xb = px(si)
            yb = py(s['entry'])
            buy_color = '#4ecdc4' if is_trend else '#ff4444'
            buy_label = 'T' if is_trend else 'B'
            sv.append(f'<line x1="{xb:.1f}" y1="{yb:.1f}" x2="{xb:.1f}" y2="{pt + 18:.1f}" stroke="{buy_color}" stroke-width="1" stroke-dasharray="4,3" opacity="0.6"/>')
            txt = f'{buy_label}{s["n"]} {s["date"][5:10]} {s["entry"]:.0f}'
            tw = len(txt) * 7 + 16
            sv.append(f'<rect x="{xb - tw / 2:.1f}" y="{pt - 2:.1f}" width="{tw:.1f}" height="18" rx="4" fill="{buy_color}" opacity="0.85" filter="url(#sh)"/>')
            sv.append(f'<text x="{xb:.1f}" y="{pt + 11:.1f}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="white" font-weight="bold">{txt}</text>')
            if s.get('exit_date'):
                ei = find_idx(s['exit_date'], kls)
                if ei > 0:
                    xx = px(ei)
                    yb2 = py(s['exit'])
                    sv.append(f'<line x1="{xx:.1f}" y1="{yb2:.1f}" x2="{xx:.1f}" y2="{bv + 38:.1f}" stroke="#2196f3" stroke-width="1" stroke-dasharray="3,3" opacity="0.5"/>')
                    txt2 = f'S{s["n"]} {s["gain"]:+.1f}%'
                    tw2 = len(txt2) * 7 + 12
                    sv.append(f'<rect x="{xx - tw2 / 2:.1f}" y="{bv + 30:.1f}" width="{tw2:.1f}" height="16" rx="4" fill="#2196f3" opacity="0.85" filter="url(#sh)"/>')
                    sv.append(f'<text x="{xx:.1f}" y="{bv + 42:.1f}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="white" font-weight="bold">{txt2}</text>')
        # 日期标签
        for ii in range(0, n, 5):
            ds = str(kls[ii]['date']).replace('-', '')
            lab = f'{ds[4:6]}/{ds[6:8]}'
            sv.append(f'<text x="{px(ii):.1f}" y="{bv + 20}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#555" transform="rotate(-40,{px(ii)},{bv + 20})">{lab}</text>')
        # 图例
        for i, (clr, lbl) in enumerate([("#ff4444", "3L买入↑"), ("#4ecdc4", "趋势买入↑"), ("#2196f3", "卖出↓"), ("#ffd700", "EMA5"), ("#ff6b6b", "EMA10"), ("#4ecdc4", "EMA20")]):
            xl = pl + i * 140
            sv.append(f'<rect x="{xl}" y="{bv + 8}" width="10" height="10" fill="{clr}" opacity="0.85" rx="1"/>')
            sv.append(f'<text x="{xl + 14}" y="{bv + 17}" font-family="sans-serif" font-size="10" fill="#888">{lbl}</text>')

        # ── 资金曲线面板 (equity curve) ──
        sv.append(f'<text x="{pl}" y="{ec_top + 14}" font-family="sans-serif" font-size="12" fill="#aaa" font-weight="bold">📈 资金曲线</text>')
        sv.append(f'<line x1="{pl}" y1="{ec_top + 20}" x2="{svg_w - pr}" y2="{ec_top + 20}" stroke="#2a2a4e" stroke-width="0.5"/>')
        # 找到有exit_date的信号，计算时间轴上的累计收益
        ec_pts = []
        ec_mx, ec_mn = -999, 999
        for s in signals:
            if s.get('exit_date') and s.get('cum_gain') is not None:
                ei2 = find_idx(s['exit_date'], kls)
                if ei2 >= 0:
                    ec_pts.append((px(ei2), s['cum_gain']))
                    ec_mx = max(ec_mx, s['cum_gain'])
                    ec_mn = min(ec_mn, s['cum_gain'])
        if len(ec_pts) >= 2:
            ec_rg = ec_mx - ec_mn if ec_mx != ec_mn else 1
            ec_py = lambda v: ec_top + 110 - (v - ec_mn) / ec_rg * 90
            ec_center = (ec_mx + ec_mn) / 2
            # 0% reference line
            sv.append(f'<line x1="{pl}" y1="{ec_py(0):.1f}" x2="{svg_w - pr}" y2="{ec_py(0):.1f}" stroke="#2a2a4e" stroke-width="0.5" stroke-dasharray="4,4"/>')
            sv.append(f'<text x="{svg_w - pr + 4}" y="{ec_py(0) + 3}" font-family="sans-serif" font-size="8" fill="#555">0%</text>')
            # 基准线标注
            for v in [ec_mn, ec_center, ec_mx]:
                sv.append(f'<text x="{pl - 4}" y="{ec_py(v) + 3}" text-anchor="end" font-family="sans-serif" font-size="8" fill="#555">{v:+.0f}%</text>')
            # 连线和点
            pts_str = ' '.join(f'{x:.1f},{ec_py(v):.1f}' for x, v in ec_pts)
            sv.append(f'<polyline points="{pts_str}" fill="none" stroke="#4ecdc4" stroke-width="2" opacity="0.9"/>')
            for x, v in ec_pts:
                sv.append(f'<circle cx="{x:.1f}" cy="{ec_py(v):.1f}" r="3" fill="#4ecdc4" opacity="0.9"/>')
                sv.append(f'<text x="{x:.1f}" y="{ec_py(v) - 6}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#aaa">{v:+.1f}%</text>')
        else:
            sv.append(f'<text x="{pl + 10}" y="{ec_top + 60}" font-family="sans-serif" font-size="12" fill="#555">信号不足，无法绘制资金曲线</text>')

        # ── 盈亏分布面板 (P&L distribution) ──
        sv.append(f'<text x="{pl}" y="{pnl_top + 14}" font-family="sans-serif" font-size="12" fill="#aaa" font-weight="bold">📊 盈亏分布</text>')
        sv.append(f'<line x1="{pl}" y1="{pnl_top + 20}" x2="{svg_w - pr}" y2="{pnl_top + 20}" stroke="#2a2a4e" stroke-width="0.5"/>')
        gains = [s['gain'] for s in signals if s.get('gain') is not None]
        if gains:
            # 按盈亏区间分组: <-10%, -10~-5%, -5~0%, 0~5%, 5~10%, >10%
            buckets = [(-50, -10), (-10, -5), (-5, 0), (0, 5), (5, 10), (10, 50)]
            bucket_labels = ['&lt;-10%', '-10~-5%', '-5~0%', '0~5%', '5~10%', '&gt;10%']
            bucket_colors = ['#e94560', '#ff6b6b', '#ff9999', '#99cc99', '#44aa44', '#4ecdc4']
            counts = [sum(1 for g in gains if lo <= g < hi) for lo, hi in buckets]
            mc = max(max(counts), 1)
            bar_w = 80
            bar_gap = 20
            start_x = pl + 30
            bar_h_max = 50
            for bi, (cnt, lbl, clr) in enumerate(zip(counts, bucket_labels, bucket_colors)):
                bx = start_x + bi * (bar_w + bar_gap)
                bh = cnt / mc * bar_h_max
                sv.append(f'<rect x="{bx}" y="{pnl_top + 65 - bh:.1f}" width="{bar_w}" height="{max(bh, 1):.1f}" fill="{clr}" opacity="0.8" rx="3"/>')
                sv.append(f'<text x="{bx + bar_w / 2}" y="{pnl_top + 65 - bh - 4}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#fff">{cnt}</text>')
                sv.append(f'<text x="{bx + bar_w / 2}" y="{pnl_top + 78}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#888">{lbl}</text>')
            # 区间坐标线
            sv.append(f'<line x1="{start_x - 5}" y1="{pnl_top + 65}" x2="{start_x + 6 * (bar_w + bar_gap) - bar_gap + 5}" y2="{pnl_top + 65}" stroke="#2a2a4e" stroke-width="0.5"/>')
        else:
            sv.append(f'<text x="{pl + 10}" y="{pnl_top + 60}" font-family="sans-serif" font-size="12" fill="#555">无盈亏数据</text>')
        sv.append('</svg>')
        with open(chart_abs, 'w') as f:
            f.write('\n'.join(sv))
        return True
    except Exception as e:
        print(f"gen_trade_chart_svg error: {e}")
        return False


def compute_trade_stats(signals):
    """从信号列表计算回测统计数据

    Returns: {total, wins, losses, win_rate, avg_win, avg_loss, cumulative_return}
    """
    if not signals:
        return {'total': 0, 'wins': 0, 'losses': 0, 'win_rate': 0,
                'avg_win': 0, 'avg_loss': 0, 'cumulative_return': 0}
    wins = sum(1 for s in signals if s['gain'] > 0)
    losses = len(signals) - wins
    cum = signals[-1]['cum_gain'] if signals else 0
    avg_win = round(sum(s['gain'] for s in signals if s['gain'] > 0) / wins, 2) if wins > 0 else 0
    avg_loss = round(sum(s['gain'] for s in signals if s['gain'] <= 0) / losses, 2) if losses > 0 else 0
    return {
        'total': len(signals),
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / len(signals) * 100, 1),
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'cumulative_return': round(cum, 2),
    }


# ═══════════════════════════════════════════
# 3L退出检测函数（提取自 test_demingli_3l.py）
# ═══════════════════════════════════════════

def check_acceleration(kls, start_idx, current_idx):
    """左侧止盈：D方案两步法判断加速
    基于EMA10斜率比 + 确认过程检查（整理后突破不算加速）
    
    逻辑：
    1. 计算EMA10末15根斜率s1、末3根斜率s2
    2. ratio = s2/s1 > 1.8 → 可能加速
    3. C方案：近5日有急跌阴线(>3%)导致V反 → 调整s1
    4. D方案：找局部低点，若回调>5%且守住EMA20→整理后突破，不算加速
    """
    if current_idx < 15 or current_idx >= len(kls):
        return False, ''
    from backend.core.ema_utils import ema_list, _reg_slope
    closes = [k['close'] for k in kls[:current_idx+1]]
    e10 = ema_list(closes, 10)
    e10_last = [v for v in e10[-15:] if v is not None]
    if len(e10_last) < 10:
        return False, ''
    s1 = _reg_slope(e10_last)
    s2_val = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
    if not (s1 > 0 and s2_val > 0):
        return False, ''
    ratio = s2_val / s1 if abs(s1) > 1e-8 else 1.0
    if ratio <= 1.8:
        return False, ''
    # C方案：近5日有急跌阴线导致V反
    if len(closes) >= 6:
        check = closes[-6:]
        for ci in range(1, len(check)):
            if (check[ci] - check[ci-1]) / check[ci-1] < -0.03:
                n_after = len(check) - ci
                start_i = max(1, len(e10_last) - n_after + 1)
                if start_i < len(e10_last) - 2:
                    s1_adj = _reg_slope(e10_last[start_i:])
                    if s1_adj > 0:
                        ratio = s2_val / s1_adj
                break
    if ratio <= 1.8:
        return False, ''
    # D方案：判断整理后突破
    if len(closes) >= 23:
        w = closes[-23:-3]
        if len(w) >= 10:
            for i in range(len(w)-1, len(w)-8, -1):
                if i-1 < 0 or i-1 >= len(w):
                    continue
                if w[i] > w[i-1]:
                    trough_val = w[i-1]
                    peak_val = max(w[:i-1]) if i-1 > 0 else w[i-1]
                    pull = (peak_val - trough_val) / peak_val * 100 if peak_val > 0 else 0
                    if pull > 5:
                        e20_full = ema_list(closes, 20)
                        trough_abs_i = len(closes) - 23 + i - 1
                        if (trough_abs_i < len(e20_full) and e20_full[trough_abs_i] is not None
                                and trough_val > e20_full[trough_abs_i] * 0.98):
                            ratio = 1.0
                        break
    if ratio > 1.8:
        return True, f"加速(斜率比{round(ratio,1)})"
    return False, ''


def check_volume_stagnation(kls, current_idx):
    """左侧止盈：放量滞涨"""
    if current_idx < 5 or current_idx >= len(kls):
        return False, ''
    vol = kls[current_idx].get('volume', kls[current_idx].get('vol', 0))
    if vol <= 0:
        return False, ''
    vols = [kls[current_idx - 4 + i].get('volume', kls[current_idx - 4 + i].get('vol', 0)) for i in range(5)]
    vma5 = sum(vols) / 5 if all(v > 0 for v in vols) else 1
    vr = vol / vma5
    if vr > 1.5:
        o, c = kls[current_idx]['open'], kls[current_idx]['close']
        body = abs(c - o)
        rng = kls[current_idx]['high'] - kls[current_idx]['low']
        if rng > 0 and body / rng < 0.3:
            return True, f"放量滞涨(量比{round(vr,1)})"
    return False, ''


def check_power_fading(kls, current_idx, entry_idx):
    """左侧止盈：动力减弱（价创新高量递减）"""
    if current_idx - entry_idx < 3 or current_idx >= len(kls):
        return False, ''
    recent_vols = [kls[max(0, current_idx - 2) + j].get('volume', kls[max(0, current_idx - 2) + j].get('vol', 0)) for j in range(3)]
    if not all(v > 0 for v in recent_vols) or recent_vols[0] <= 0:
        return False, ''
    if recent_vols[1] < recent_vols[0] * 0.95 and recent_vols[2] < recent_vols[1] * 0.95:
        recent_highs = [kls[j]['high'] for j in range(max(0, current_idx - 5), current_idx + 1)]
        if len(recent_highs) >= 3 and recent_highs[-1] == max(recent_highs):
            return True, "动力减弱(价新高量递减)"
    return False, ''


def check_reverse_yingbaoyang(kls, current_idx, key_point):
    """右侧止盈：阴包阳三维判定 + 大阴线反转

    三维判定:
    第1层 跌幅: < -5%直接走 / > -3%不走 / -5%~-3%继续
    第2层 支撑: 破支撑走 / 没破观察
    第3层 量能: 放量(>1.0)加强判断
    """
    if current_idx < 1 or current_idx >= len(kls):
        return False, ''
    k, kp = kls[current_idx], kls[current_idx - 1]
    c, o, h, l = k['close'], k['open'], k['high'], k['low']

    prev_close = kls[current_idx - 1]['close'] if current_idx >= 1 else 0
    day_loss = (c - prev_close) / prev_close * 100 if prev_close else 0

    vol = k.get('volume', k.get('vol', 0))
    prev_vols = [kls[current_idx - j - 1].get('volume', kls[current_idx - j - 1].get('vol', 0)) for j in range(1, 6)]
    avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 0
    vol_ratio = vol / avg_vol if avg_vol > 0 else 0

    # 条件1：阴包阳（前阳+本阴+本收≤前开）
    if kp['close'] >= kp['open'] and c < o and c <= kp['open']:
        if day_loss < -5:
            return True, f"阴包阳(跌{day_loss:.1f}%大阴,走)"
        elif day_loss > -3:
            return False, f"阴包阳(跌{day_loss:.1f}%小阴,观察)"
        if key_point and c < key_point:
            if vol_ratio > 1.0:
                return True, f"阴包阳(破支撑+放量{vol_ratio:.1f}x,走)"
            return True, f"阴包阳(破支撑{key_point:.0f},走)"
        else:
            return False, f"阴包阳(跌{day_loss:.1f}%未破支撑,观察)"

    # 条件2：大阴线反转
    if c < o:
        body = o - c
        bodies = [abs(kls[j]['close'] - kls[j]['open']) for j in range(max(0, current_idx - 5), current_idx)]
        avg_b = sum(bodies) / len(bodies) if bodies else 0
        rng_ = h - l if h > l else 1
        if avg_b > 0 and body >= avg_b * 1.5 and (c - l) / rng_ < 0.3:
            return True, f"大阴线反转(体{body:.0f}≥均{avg_b:.0f}×1.5)"
    return False, ''


def check_panic(kls, current_idx, entry_idx=None, key_point=None):
    """恐慌退出信号 — 占位符，规则待定

    位于左侧止盈链的最后一道防线：
    加速 → 衰竭 → 恐慌

    Args:
        kls: K线列表 [{date,open,high,low,close,volume}]
        current_idx: 当前K线索引
        entry_idx: 入场索引（可选）
        key_point: 关键点价格（可选）

    Returns:
        (triggered: bool, reason: str)
    """
    return False, ''


def simulate_trade(kls, entry_idx, entry_price, buy_type, key_point=None, max_days=60):
    """模拟一笔交易的完整生命周期（含止损→买回→最终退出）

    Args:
        kls: K线列表 [{date,open,high,low,close,volume}]
        entry_idx: 入场K线索引
        entry_price: 入场价
        buy_type: '突破买点' 或 '中继买点'
        key_point: 关键点（缺失时自动计算）
        max_days: 最大持有天数

    Returns:
        dict with keys: exit_idx, exit_price, exit_date, exit_reason,
                        gain, days, stop_loss_price, buy_back_price, max_gain, max_loss
                        or None if trade simulation failed
    """
    if key_point is None:
        if buy_type == '突破买点':
            if entry_idx >= 10:
                key_point = max(kls[j]['high'] for j in range(entry_idx - 10, entry_idx))
            else:
                key_point = max(kls[j]['high'] for j in range(entry_idx))
        else:
            key_point = _find_support_levels(kls, entry_idx)
        if key_point is None:
            return None

    stop_price = round(key_point * 0.97, 2)
    stop_triggered = False
    stop_day = None
    stop_loss_price = None
    buy_back_price = None
    buy_back_day = None
    re_entry_idx = None
    in_stop_observation = False
    exit_reason = None
    exit_day = None
    exit_price = None
    max_gain_pct = 0
    max_loss_pct = 0
    entry_gain_pct = 0

    for day_idx in range(entry_idx + 1, min(entry_idx + max_days + 1, len(kls))):
        k = kls[day_idx]
        hp, lp, cp, op = k['high'], k['low'], k['close'], k['open']

        base_price = buy_back_price if re_entry_idx is not None else entry_price
        gain_pct = round((cp - base_price) / base_price * 100, 2)
        max_gain_pct = max(max_gain_pct, gain_pct)
        if not stop_triggered:
            max_loss_pct = min(max_loss_pct, gain_pct)

        # 止损检测
        if not stop_triggered and not in_stop_observation:
            if lp < stop_price:
                stop_triggered = True
                stop_day = day_idx
                stop_loss_price = min(cp, stop_price)
                stop_loss_pct = round((stop_loss_price - entry_price) / entry_price * 100, 2)
                entry_gain_pct = stop_loss_pct
                in_stop_observation = True
                continue

        # 买回检测
        if in_stop_observation:
            if cp > key_point and cp > op:
                buy_back_price = cp
                buy_back_day = day_idx
                in_stop_observation = False
                re_entry_idx = day_idx
                continue

            # 观察期也检查加速止盈
            accel, ar = check_acceleration(kls, entry_idx if re_entry_idx is None else re_entry_idx, day_idx)
            if accel:
                exit_reason = f"左侧止盈-{ar}(止损后)"
                exit_day = day_idx
                exit_price = cp
                break
            continue

        # 左侧止盈
        accel, ar = check_acceleration(kls, entry_idx if re_entry_idx is None else re_entry_idx, day_idx)
        if accel:
            exit_reason = f"左侧止盈-{ar}"
            exit_day = day_idx
            exit_price = cp
            break

        stag, sr = check_volume_stagnation(kls, day_idx)
        if stag:
            exit_reason = f"左侧止盈-{sr}"
            exit_day = day_idx
            exit_price = cp
            break

        fade, fr = check_power_fading(kls, day_idx, entry_idx if re_entry_idx is None else re_entry_idx)
        if fade:
            exit_reason = f"左侧止盈-{fr}"
            exit_day = day_idx
            exit_price = cp
            break

        # 恐慌退出
        panic, pr = check_panic(kls, day_idx, entry_idx if re_entry_idx is None else re_entry_idx, key_point)
        if panic:
            exit_reason = f"左侧止盈-恐慌{pr}"
            exit_day = day_idx
            exit_price = cp
            break

        # 右侧止盈
        rev, rr = check_reverse_yingbaoyang(kls, day_idx, key_point)
        if rev:
            exit_reason = f"右侧止盈-{rr}"
            exit_day = day_idx
            exit_price = cp
            break

    if exit_day is None and stop_triggered and buy_back_day is None:
        # 止损后没买回也没退出
        exit_day = stop_day
        exit_price = stop_loss_price
        exit_reason = "止损未买回"
        final_gain = round((exit_price - entry_price) / entry_price * 100, 2)
    elif exit_day is None and stop_triggered and buy_back_day is not None:
        # 买回后到最后都没触发退出，按最后收盘价算
        exit_day = len(kls) - 1
        exit_price = kls[-1]['close']
        exit_reason = "持有到期"
        final_gain = round((exit_price - buy_back_price) / buy_back_price * 100, 2)
    elif exit_day is None:
        # 一直持有到最后
        exit_day = len(kls) - 1
        exit_price = kls[-1]['close']
        exit_reason = "持有到期"
        final_gain = round((exit_price - entry_price) / entry_price * 100, 2)
    else:
        # 正常退出
        final_gain = round((exit_price - (buy_back_price if re_entry_idx is not None else entry_price)) / (buy_back_price if re_entry_idx is not None else entry_price) * 100, 2)

    total_gain = round((exit_price - entry_price) / entry_price * 100, 2)

    return {
        'exit_idx': exit_day,
        'exit_price': round(exit_price, 2),
        'exit_gain': total_gain,  # 相对入场价的总收益
        'exit_reason': exit_reason,
        'hold_days': exit_day - entry_idx if exit_day else 0,
        'stop_triggered': stop_triggered,
        'stop_loss_price': round(stop_loss_price, 2) if stop_loss_price else None,
        'buy_back_price': round(buy_back_price, 2) if buy_back_price else None,
        'max_gain': round(max_gain_pct, 2),
        'max_loss': round(max_loss_pct, 2),
    }
