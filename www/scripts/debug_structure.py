#!/usr/bin/env python3
"""诊断3/16结构为什么会回退到区间震荡"""
import json, sys, os
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)
for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from ema_utils import get_structure, ema_list

def print_day(ds, closes, highlight=False):
    struct = get_structure(closes)
    e10 = ema_list(closes, 10)
    e10v = round(e10[-1], 2) if e10[-1] else 'N/A'
    
    # 极值位置检查
    el15 = e10[-15:]
    n = len(el15)
    fq = n // 4
    lq = n - 1 - n // 4
    max_pos = max(range(n), key=lambda i: el15[i] if el15[i] is not None else -1e9)
    min_pos = min(range(n), key=lambda i: el15[i] if el15[i] is not None else 1e9)
    
    up_cond = max_pos >= lq and min_pos <= fq
    dn_cond = min_pos >= lq and max_pos <= fq
    
    # 末端校验
    l3 = [v for v in e10[-3:] if v is not None]
    end_check = ''
    if struct == '上涨趋势' and len(l3) == 3 and l3[0] > l3[1] > l3[2] and closes[-1] < l3[-1]:
        end_check = '← 被降级！'
    
    tag = '<<<' if highlight else ''
    print(f"{ds:>12} C={closes[-1]:>7.2f} E10={e10v:>8} 基={struct:>6} maxP={max_pos}/lq={lq} minP={min_pos}/fq={fq} up={up_cond} dn={dn_cond} l3={l3[0]:.1f}→{l3[-1]:.1f} {end_check} {tag}")

# 逐日打印从3/10到3/20的数据
for i, k in enumerate(kls):
    ds = str(k['date']).replace('-','')
    if ds < '20260310' or ds > '20260320':
        continue
    
    closes = [kk['close'] for kk in kls[:i+1]]
    highlight = (ds == '20260316')
    print_day(f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}", closes, highlight=highlight)

print("\n\n详细EMA10序列(3/10→3/18):")
for i, k in enumerate(kls):
    ds = str(k['date']).replace('-','')
    if ds < '20260310' or ds > '20260318':
        continue
    closes = [kk['close'] for kk in kls[:i+1]]
    e10 = ema_list(closes, 10)
    e10_15 = e10[-15:]
    n15 = len(e10_15)
    print(f"\n{ds[:4]}-{ds[4:6]}-{ds[6:8]}  close={closes[-1]}")
    for j, v in enumerate(e10_15):
        marker = ' <<<' if j == n15-1 else ''
        print(f"  [{j:>2}] E10={v:.2f}{marker}")
