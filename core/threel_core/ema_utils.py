#!/usr/bin/env python3
"""EMA辅助函数 — 基于ema10-trend-judgment skill 的结构/阶段/排列判断

共用函数，纯计算，无服务器依赖。
"""

def ema_list(data, period):
    """计算EMA列表（与skill算法一致）"""
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r

def get_ema_arrangement(closes):
    """判断EMA排列: EMA5 > EMA10 > EMA20 → 多头排列 / 空头排列 / 交叉"""
    if len(closes) < 20:
        return '--'
    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    e5v, e10v, e20v = e5[-1], e10[-1], e20[-1]
    if e5v and e10v and e20v:
        if e5v > e10v > e20v:
            return '多头排列'
        elif e5v < e10v < e20v:
            return '空头排列'
        else:
            return '交叉'
    return '--'

def get_structure(closes):
    """基于EMA12+EMA5长短配合判定结构（2026-06-02 C方案）

    不对称阈值：上涨严格(斜率高) + 下降宽松(斜率低)

    上涨趋势判定（需同时满足长/短周期条件）：
    ① 长周期：EMA12斜率>0.8% + BIAS>-5% + 多头排列
    ② 短周期确认：EMA5斜率>0%（短周期动量未转弱）
    ①②均满足→上涨趋势；①满足但②不满足→区间震荡(转弱降级)

    下降趋势：EMA12斜率<-0.2% + BIAS<3%
    其他 → 区间震荡
    """
    if len(closes) < 25:
        return '--'
    
    # ── 长周期：EMA12 ──
    ema12 = ema_list(closes, 12)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    if len(e12_recent) < 5:
        return '--'
    
    slope = _reg_slope(e12_recent)
    slope_pct = slope / e12_recent[0] * 100 if e12_recent[0] else 0
    
    cur, cur_ema12 = closes[-1], e12_recent[-1]
    bias = (cur - cur_ema12) / cur_ema12 * 100 if cur_ema12 else 0
    
    # ── 多头排列检查 ──
    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    bull_arrange = (e5[-1] and e10[-1] and e20[-1] and e5[-1] > e10[-1] > e20[-1])
    
    # ── 短周期确认：EMA5斜率 ──
    ema5 = ema_list(closes, 5)
    e5_recent = [v for v in ema5[-5:] if v is not None]
    ema5_slope_pct = 0
    if len(e5_recent) >= 3:
        s5 = _reg_slope(e5_recent)
        ema5_slope_pct = s5 / e5_recent[0] * 100 if e5_recent[0] else 0
    
    # ── 结构判定 ──
    if slope_pct > 0.8 and bias > -5 and bull_arrange:
        # 长周期看涨，但需短周期确认
        if ema5_slope_pct > 0:
            return '上涨趋势'
        else:
            return '区间震荡'  # 趋势转弱，降级
    
    if slope_pct < -0.2 and bias < 3:
        return '下降趋势'
    
    return '区间震荡'

def get_stage(closes, structure=None, highs=None, lows=None, support_level=None, resistance_level=None, volumes=None, opens_p=None):
    """基于EMA10半段斜率判断阶段
    - s1=末15根EMA10整体斜率（趋势基准），s2=末3根斜率（近期动量，更敏感）
    - 上涨趋势:
        - 上行(ratio 0.4~1.8) / 加速(>1.8) — 正常上行阶段
        - 放量滞涨(放量+价不涨) / 缩量滞涨(缩量+横盘) — **信号驱动的场景描述词**
        - 缩量整理(缩量+回踩) / 转弱(s1>0,s2<0) — 蓄力/右侧转弱
    - 下降趋势: 下行(ratio≤1.8) / 加速跌(>1.8) / 转强(s1<0,s2>0)
    - 区间震荡: 区间顶部/区间中段/区间底部（价格位置）

    设计原则：
    - 放量滞涨/缩量滞涨是量价信号驱动，不依赖斜率ratio阈值
    - 它们是「场景描述词」而非独立卖出信号
    - 真正的卖出决策由融合引擎(_keypoint_direction)组合其他条件判定
    - 详见 docs/stock-card-logic-design.md 第4章
    """
    if structure == '区间震荡':
        cur = closes[-1] if closes else 0
        lo = support_level if support_level else (min(lows[-15:]) if highs and lows and len(lows) >= 15 else cur)
        hi = resistance_level if resistance_level else (max(highs[-15:]) if highs and lows and len(highs) >= 15 else cur)
        if hi > lo:
            pct = (cur - lo) / (hi - lo) * 100
            if pct < 30: return '区间底部'
            elif pct > 70: return '区间顶部'
            else: return '区间中段'
        return '--'

    if len(closes) < 15:
        return '--'
    e10 = ema_list(closes, 10)
    e10_last = [v for v in e10[-15:] if v is not None]
    if len(e10_last) < 10:
        return '--'
    s1 = _reg_slope(e10_last)
    s2 = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0

    # ── A. 量价异常信号检查（先于斜率分类，信号驱动） ──
    # 仅检查上涨趋势结构的个股
    if s1 > 0 and structure != '下降趋势':
        if volumes and len(volumes) >= 13 and closes[-1] > e10_last[-1]:
            vol_last3 = sum(volumes[-3:]) / 3
            vol_prev10 = sum(volumes[-13:-3]) / 10
            if vol_prev10 > 0:
                vol_ratio = vol_last3 / vol_prev10

                # 放量滞涨：量放大 + 价不涨 + 窄幅
                if vol_ratio > 1.2:
                    # 价不涨：近3日涨幅<3%
                    recent_3d_change = (closes[-1] - closes[-4]) / closes[-4] * 100 if len(closes) >= 4 else 100
                    if recent_3d_change < 3:
                        # 窄幅：当日实体小 or 振幅小
                        op = opens_p[-1] if opens_p else closes[-1]
                        body_pct = abs(closes[-1] - op) / op if op else 0
                        hi = highs[-1] if highs else closes[-1]
                        lo = lows[-1] if lows else closes[-1]
                        amp = (hi - lo) / lo if lo else 0
                        if body_pct < 0.03 or amp < 0.05:
                            return '放量滞涨'

                # 缩量滞涨：量萎缩 + 横盘不创新高 + 波动小
                if vol_ratio < 0.8:
                    if len(closes) >= 10:
                        recent_low = min(closes[-10:])
                        recent_high = max(closes[-10:])
                        recent_range = (recent_high - recent_low) / recent_low * 100
                        # 近10日波动<5%且不创新高
                        prev_high = max(closes[-20:-10]) if len(closes) >= 20 else recent_high
                        if recent_range < 5 and closes[-1] <= prev_high * 1.01:
                            return '缩量滞涨'

    # ── B. 斜率分类（无异常信号时按正常斜率判断） ──
    if s1 > 0 and s2 > 0:
        ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
        if ratio > 1.8:
            # C方案：检测近5日是否有急跌阴线导致V反误判加速
            if len(closes) >= 6:
                check = closes[-6:]
                for ci in range(1, len(check)):
                    if (check[ci] - check[ci-1]) / check[ci-1] < -0.03:
                        n_after = len(check) - ci
                        start = max(1, len(e10_last) - n_after + 1)
                        if start < len(e10_last) - 2:
                            s1_adj = _reg_slope(e10_last[start:])
                            if s1_adj > 0:
                                ratio = s2 / s1_adj
                        break
            # D方案：判断整理后突破
            if len(closes) >= 23:
                w = closes[-23:-3]
                if len(w) >= 10:
                    for i in range(len(w)-1, len(w)-8, -1):
                        if w[i] > w[i-1]:
                            trough_val = w[i-1]
                            peak_val = max(w[:i-1])
                            pull = (peak_val - trough_val) / peak_val * 100
                            if pull > 5:
                                e20_full = ema_list(closes, 20)
                                trough_abs_i = len(closes) - 23 + i - 1
                                is_holding = (trough_abs_i < len(e20_full) and e20_full[trough_abs_i] is not None
                                            and trough_val > e20_full[trough_abs_i] * 0.98)
                                if is_holding:
                                    ratio = 1.0
                                break
        if ratio > 1.8: return '加速'
        elif ratio < 0.4:
            # 斜率极低 → 如果有成交量数据但上面没判定，检查缩量整理
            if volumes and len(volumes) >= 13 and closes[-1] > e10_last[-1]:
                vol_last3 = sum(volumes[-3:]) / 3
                vol_prev10 = sum(volumes[-13:-3]) / 10
                if vol_prev10 > 0 and (vol_last3 / vol_prev10) < 0.8:
                    # 缩量整理：缩量 + 有回踩 + 价不破EMA10
                    if len(closes) >= 10:
                        recent_low = min(closes[-10:])
                        recent_high = max(closes[-10:])
                        recent_range = (recent_high - recent_low) / recent_low * 100
                        if recent_range > 3:
                            return '缩量整理'
            # 斜率低但非异常量价 → 仍算上行（只是慢）
            return '上行'
        else:
            return '上行'
    elif s1 < 0 and s2 < 0:
        ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
        if ratio > 1.8: return '加速跌'
        else: return '下行'
    elif s1 > 0 and s2 < 0:
        return '转弱'
    else:
        return '转强'

def _reg_slope(y_list):
    """线性回归斜率"""
    n = len(y_list)
    if n < 2:
        return 0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(y_list) / n
    num = sum((xs[i] - mx) * (y_list[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den else 0

def get_mainline_level(sector, main_lines, sub_lines):
    """判断板块属于主线/次级主线/非主线"""
    if not sector or not main_lines:
        return ''
    if sector in main_lines:
        return '主线'
    if sector in sub_lines:
        return '次级主线'
    return '非主线'
