#!/usr/bin/env python3
"""查3月16日-25日德明利详细数据"""
import json, sys, os
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)
for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from ema_utils import get_structure, get_stage, get_ema_arrangement
from buy_point_detection import _find_support_levels, _volume_ratio

print("日期      开盘   最高   最低   收盘   涨幅%   量比  EMA排  结构   阶段   前10高  突破?")
for i, k in enumerate(kls):
    ds = str(k['date']).replace('-','')
    if ds < '20260312' or ds > '20260325':
        continue
    
    closes = [kk['close'] for kk in kls[:i+1]]
    highs = [kk['high'] for kk in kls[:i+1]]
    lows = [kk['low'] for kk in kls[:i+1]]
    vols = [kk.get('volume', kk.get('vol', 0)) for kk in kls[:i+1]]
    
    struct = get_structure(closes)
    stage = get_stage(closes, struct, highs, lows, volumes=vols)
    ema = get_ema_arrangement(closes)
    vr = _volume_ratio(kls, i)
    
    prev = kls[i-1]['close']
    gain = (k['close'] - prev)/prev*100 if prev else 0
    
    prev10h = max(kls[i-j]['high'] for j in range(1,11)) if i>=10 else 0
    is_bo = k['close'] > prev10h
    
    prev10h_str = f"{prev10h:.2f}" if prev10h else '-'
    bo_str = '✓' if is_bo else '-'
    
    d = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    print(f"{d} {k['open']:>7.2f} {k['high']:>7.2f} {k['low']:>7.2f} {k['close']:>7.2f} {gain:>+6.2f} {vr:>5.2f} {ema:>6} {struct:>5} {stage:>6} {prev10h_str:>8} {bo_str:>3}")

# 支撑计算
for date_str in ['20260316','20260320','20260323']:
    for i, k in enumerate(kls):
        if str(k['date']).replace('-','') == date_str:
            support = _find_support_levels(kls, i)
            vr = _volume_ratio(kls, i)
            closes = [kk['close'] for kk in kls[:i+1]]
            struct = get_structure(closes)
            
            print(f"\n{'='*60}")
            print(f"=== {date_str[:4]}-{date_str[4:6]}-{date_str[6:8]} ===")
            print(f"  K线: O={k['open']} H={k['high']} L={k['low']} C={k['close']}")
            print(f"  结构={struct} 量比={vr:.2f} 支撑位={support}")
            if support:
                print(f"  (C-支撑)/C = {(k['close']-support)/k['close']*100:.2f}%")
            
            # 找突破关键点 chain
            print(f"\n  突破关键点链（从最早到最新）:")
            highs = [kk['high'] for kk in kls[:i+1]]
            closes_local = [kk['close'] for kk in kls[:i+1]]
            opens_local = [kk['open'] for kk in kls[:i+1]]
            for j in range(10, i+1):
                p10h = max(kls[j-t]['high'] for t in range(1,11))
                if closes_local[j] > p10h and closes_local[j] > opens_local[j]:
                    sp = p10h
                    print(f"    {str(kls[j]['date'])[:10]} 突破{p10h:.2f}→收盘{closes_local[j]:.2f}  support_price={sp:.2f}")
            
            # 买点检测
            from buy_point_detection import detect_buy_point
            d = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            bt = detect_buy_point('001309', d, raw, market_position='波中', main_lines={'半导体'})
            if bt:
                print(f"  买点: {bt['buy_type']} score={bt['score']}")
            else:
                print(f"  非买点")
            break
