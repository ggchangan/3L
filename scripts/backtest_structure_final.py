#!/usr/bin/env python3
"""最终对比：旧版(EMA20) vs 新版(EMA10/窗11/0.55/4.0) + 各阶段收益"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope, get_stage

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

# 旧版结构判定（保留原始逻辑用于对比）
def old_structure(closes):
    if len(closes) < 25: return '--'
    ema20 = ema_list(closes, 20)
    e20 = [v for v in ema20[-10:] if v is not None]
    if len(e20) < 5: return '--'
    slope = _reg_slope(e20)
    sp = slope / e20[0] * 100 if e20[0] else 0
    bias = (closes[-1] - e20[-1]) / e20[-1] * 100 if e20[-1] else 0
    if sp > 0.2 and bias > -2: return '上涨趋势'
    elif sp < -0.2 and bias < 2: return '下降趋势'
    else: return '区间震荡'

# 新版结构判定
def new_structure(closes):
    if len(closes) < 25: return '--'
    ema10 = ema_list(closes, 10)
    e10 = [v for v in ema10[-11:] if v is not None]
    if len(e10) < 5: return '--'
    slope = _reg_slope(e10)
    sp = slope / e10[0] * 100 if e10[0] else 0
    bias = (closes[-1] - e10[-1]) / e10[-1] * 100 if e10[-1] else 0
    if sp > 0.55 and bias > -4: return '上涨趋势'
    elif sp < -0.55 and bias < 4: return '下降趋势'
    else: return '区间震荡'

for label, fn in [('旧版(EMA20/10/0.2/2.0)', old_structure),
                   ('新版(EMA10/11/0.55/4.0)', new_structure)]:
    up_r = []; down_r = []; range_r = []
    struct_counts = {}
    stage_detail = {}
    
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35: continue
            closes = [k['close'] for k in klines]
            volumes = [k['volume'] for k in klines]
            opens_p = [k['open'] for k in klines]
            highs = [k['high'] for k in klines]
            lows = [k['low'] for k in klines]
            
            for i in range(30, len(klines) - 5):
                wc = closes[:i+1]
                wv = volumes[:i+1]
                wo = opens_p[:i+1]
                wh = highs[:i+1]
                wl = lows[:i+1]
                
                struct = fn(wc)
                stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
                fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                
                struct_counts[struct] = struct_counts.get(struct, 0) + 1
                key = f'{struct}·{stage}'
                if key not in stage_detail:
                    stage_detail[key] = {'struct': struct, 'stage': stage, 'returns': []}
                stage_detail[key]['returns'].append(fwd)
                
                if struct == '上涨趋势': up_r.append(fwd)
                elif struct == '下降趋势': down_r.append(fwd)
                else: range_r.append(fwd)
    
    total = sum(struct_counts.values())
    up_avg = sum(up_r)/len(up_r) if up_r else 0
    down_avg = sum(down_r)/len(down_r) if down_r else 0
    range_avg = sum(range_r)/len(range_r) if range_r else 0
    disc = up_avg - down_avg
    
    print(f'\n{"="*80}')
    print(f'{label}')
    print(f'{"="*80}')
    for s in ['上涨趋势', '区间震荡', '下降趋势']:
        c = struct_counts.get(s, 0)
        p = c/total*100
        if s == '上涨趋势': avg = up_avg; r_cnt = len(up_r)
        elif s == '下降趋势': avg = down_avg; r_cnt = len(down_r)
        else: avg = range_avg; r_cnt = len(range_r)
        bad = sum(1 for v in (up_r if s=='上涨趋势' else down_r if s=='下降趋势' else range_r) if v < 0)
        print(f'  {s:<12}: {c:>6}次({p:5.1f}%) 5日走弱{bad/r_cnt*100:5.1f}% 均{avg:+6.2f}%')
    
    print(f'  {"区分度":<12}: {disc:+7.2f}%')
    print(f'  {"阶段详情":}')
    for key, r in sorted(stage_detail.items(), key=lambda x: -len(x[1]['returns'])):
        rets = r['returns']
        bad = sum(1 for v in rets if v < 0)
        avg = sum(rets)/len(rets)
        if len(rets) >= 10:
            print(f'    {key:<25}: {len(rets):>4}次 走弱{bad/len(rets)*100:5.1f}% 均{avg:+6.2f}%')
