#!/usr/bin/env python3
"""诊断德明利 - 看看各时间点的EMA10结构/阶段/量比"""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)

for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from ema_utils import get_structure, get_stage, get_ema_arrangement
from buy_point_detection import _volume_ratio

print(f"{'日期':>12} {'收盘':>8} {'结构':>8} {'阶段':>8} {'EMA排':>6} {'量比':>6} {'前10高':>8} {'支撑':>8} {'信号':>10}")
print("-"*95)

for i in range(30, len(kls)):
    k = kls[i]
    closes = [kk['close'] for kk in kls[:i+1]]
    highs = [kk['high'] for kk in kls[:i+1]]
    lows = [kk['low'] for kk in kls[:i+1]]
    vols = [kk.get('volume', kk.get('vol', 0)) for kk in kls[:i+1]]
    
    structure = get_structure(closes)
    stage = get_stage(closes, structure, highs, lows, volumes=vols)
    ema_arr = get_ema_arrangement(closes)
    vr = _volume_ratio(kls, i)
    prev_10h = max(kls[i-j]['high'] for j in range(1, 11))
    is_breakout = k['close'] > prev_10h
    
    # 非主线阈值
    shrink_th_non = round(0.80 * 0.80, 2)  # 波中*非主线
    surge_th_non = round(1.30 / 0.80, 2)
    
    is_shrink_non = vr < shrink_th_non
    is_surge_non = vr > surge_th_non
    
    # 主线阈值
    shrink_th_main = round(0.80 * 1.05, 2)
    surge_th_main = round(1.30 / 1.05, 2)
    
    is_shrink_main = vr < shrink_th_main
    is_surge_main = vr > surge_th_main
    
    # 判断信号（非主线）
    signal = '-'
    if structure == '上涨趋势':
        if stage in ('上行', '缩量整理') and is_shrink_non:
            signal = '中继N'
        if is_breakout and is_surge_non:
            signal = '突破N'
    elif structure == '区间震荡':
        if stage == '区间底部' and is_shrink_non:
            signal = '中继N'
        if stage == '区间顶部' and is_breakout and is_surge_non:
            signal = '突破N'
    
    # 判断信号（主线）
    signal_m = '-'
    if structure == '上涨趋势':
        if stage in ('上行', '缩量整理') and is_shrink_main:
            signal_m = '中继'
        if is_breakout and is_surge_main:
            signal_m = '突破'
    elif structure == '区间震荡':
        if stage == '区间底部' and is_shrink_main:
            signal_m = '中继'
        if stage == '区间顶部' and is_breakout and is_surge_main:
            signal_m = '突破'
    
    date_str = str(k['date'])
    d = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    print(f"{d:>12} {k['close']:>8.2f} {structure:>8} {stage:>8} {ema_arr:>6} {vr:>6.2f} {prev_10h:>8.2f} {'-':>8} {signal_m:>8}")

print("\n阈值对比:")
print(f"  非主线: 缩量<{shrink_th_non}, 放量>{surge_th_non}")
print(f"  主线:   缩量<{shrink_th_main}, 放量>{surge_th_main}")
