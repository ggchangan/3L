#!/usr/bin/env python3
"""EMA辅助函数 — 基于ema10-trend-judgment skill 的结构/阶段/排列判断
可供 generate_review_data.py 和 monitor_data.py 等脚本复用"""
import json

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
    """基于EMA10极值位置判断结构（同ema10-trend-judgment skill）"""
    if len(closes) < 15:
        return '--'
    e10_full = ema_list(closes, 10)
    e10 = e10_full[-15:]
    n = len(e10)
    max_pos = max(range(n), key=lambda i: e10[i] if e10[i] is not None else -1e9)
    min_pos = min(range(n), key=lambda i: e10[i] if e10[i] is not None else 1e9)
    first_q = n // 4
    last_q = n - 1 - n // 4
    if max_pos >= last_q and min_pos <= first_q:
        return '上涨趋势'
    elif min_pos >= last_q and max_pos <= first_q:
        return '下降趋势'
    else:
        return '区间震荡'

def get_stage(closes, structure=None, highs=None, lows=None, support_level=None, resistance_level=None, volumes=None):
    """基于EMA10半段斜率判断阶段
    - s1=末15根EMA10整体斜率（趋势基准），s2=末3根斜率（近期动量，更敏感）
    - 上涨趋势: 上行(ratio 0.4~1.8) / 加速(>1.8) / 滞涨(<0.4 量未缩) / 缩量整理(<0.4 量缩80%+价在EMA10上) / 转弱(s1>0,s2<0)
    - 下降趋势: 下行(ratio≤1.8) / 加速跌(>1.8) / 转强(s1<0,s2>0)
    - 区间震荡: 区间顶部/区间中段/区间底部（价格位置，用支撑/压力替代15日极值）
    """
    if structure == '区间震荡':
        cur = closes[-1] if closes else 0
        # 优先使用3L关键点识别的支撑/压力位
        lo = support_level if support_level else (min(lows[-15:]) if highs and lows and len(lows) >= 15 else cur)
        hi = resistance_level if resistance_level else (max(highs[-15:]) if highs and lows and len(highs) >= 15 else cur)
        if hi > lo:
            pct = (cur - lo) / (hi - lo) * 100
            if pct < 30: return '区间底部'
            elif pct > 70: return '区间顶部'
            else: return '区间中段'
        return '--'
    # 非区间震荡：用斜率判断
    if len(closes) < 15:
        return '--'
    e10 = ema_list(closes, 10)
    # 取末15根EMA10作为趋势基准
    e10_last = [v for v in e10[-15:] if v is not None]
    if len(e10_last) < 10:
        return '--'
    # s1 = 末15根整体斜率（趋势基准），s2 = 末3根斜率（近期动量，更敏感）
    # volumes参数用于区分"滞涨"vs"缩量整理"
    s1 = _reg_slope(e10_last)
    s2 = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
    if s1 > 0 and s2 > 0:
        # 上涨趋势：加速 / 滞涨 / 上行
        ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
        if ratio > 1.8:
            # C方案：检测近5日是否有急跌阴线（跌幅>3%）导致V反误判加速
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
            
            # D方案：两步法判断整理后突破（2026-05-22 改进版）
            # 第1步：加速前是否有过回调且守住了EMA20
            # 第2步：突破时量比是否失控(>1.7)
            if volumes is not None and len(closes) >= 25 and len(volumes) >= 25:
                w = closes[-25:-5]  # 20个交易日，排除最近5天拉升段
                if len(w) >= 10:
                    peak_val = max(w)
                    peak_i = w.index(peak_val)
                    after_w = w[peak_i+1:]
                    if after_w:
                        trough_val = min(after_w)
                        pull = (peak_val - trough_val) / peak_val * 100
                        if pull > 5:
                            # 第1步：回调低点守住EMA20？
                            e20_full = ema_list(closes, 20)
                            trough_abs_i = len(closes) - 25 + peak_i + 1 + after_w.index(trough_val)
                            is_holding = (trough_abs_i < len(e20_full) and e20_full[trough_abs_i] is not None
                                        and trough_val > e20_full[trough_abs_i] * 0.98)
                            if is_holding:
                                # 第2步：突破量控在1.7以下？
                                v3 = sum(volumes[-3:]) / 3
                                v12 = sum(volumes[-15:-3]) / 12 if len(volumes) >= 15 else 0
                                vr = v3 / v12 if v12 > 0 else 99
                                if vr < 1.7:
                                    ratio = 1.0  # 整理后突破 → 判为上行
        if ratio > 1.8: return '加速'
        elif ratio < 0.4:
            # 区分滞涨(危险) vs 缩量整理(中继蓄力)
            # 量能萎缩(末3日均量<前10日均量80%) + 价格在EMA10上方 → 缩量整理
            if volumes and len(volumes) >= 13 and closes[-1] > e10_last[-1]:
                vol_last3 = sum(volumes[-3:]) / 3
                vol_prev10 = sum(volumes[-13:-3]) / 10
                if vol_prev10 > 0 and vol_last3 / vol_prev10 < 0.8:
                    return '缩量整理'
            return '滞涨'
        else: return '上行'
    elif s1 < 0 and s2 < 0:
        # 下降趋势：加速跌 / 下行
        ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
        if ratio > 1.8: return '加速跌'
        else: return '下行'
    elif s1 > 0 and s2 < 0:
        # 之前涨，刚拐头向下
        return '转弱'
    else:
        # s1 < 0 and s2 > 0：之前跌，刚拐头向上
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
