#!/usr/bin/env python3
"""结构判定 — 深入分析选中的最优参数"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope, get_stage, get_structure as current_get_structure

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def new_structure(closes, period=10, lookback=12, slope_thresh=0.4, bias_thresh=3.0):
    if len(closes) < lookback + 5:
        return '--'
    ema = ema_list(closes, period)
    ema_recent = [v for v in ema[-lookback:] if v is not None]
    if len(ema_recent) < 5:
        return '--'
    slope = _reg_slope(ema_recent)
    slope_pct = slope / ema_recent[0] * 100 if ema_recent[0] else 0
    cur = closes[-1]
    cur_ema = ema_recent[-1]
    bias = (cur - cur_ema) / cur_ema * 100 if cur_ema else 0
    
    if slope_pct > slope_thresh and bias > -bias_thresh:
        return '上涨趋势'
    elif slope_pct < -slope_thresh and bias < bias_thresh:
        return '下降趋势'
    else:
        return '区间震荡'

print('=' * 80)
print('新旧结构判定对比 — 分布 + 各结构内阶段分布')
print('=' * 80)

for label, struct_fn in [('当前版(EMA20/10/0.2/2.0)', current_get_structure),
                          ('新版(EMA10/12/0.4/3.0)', new_structure)]:
    struct_counts = {}
    stage_in_struct = {}
    
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35: continue
            closes = [k['close'] for k in klines]
            volumes = [k['volume'] for k in klines]
            opens_p = [k['open'] for k in klines]
            highs = [k['high'] for k in klines]
            lows = [k['low'] for k in klines]
            
            for i in range(30, len(klines)):
                wc = closes[:i+1]
                wv = volumes[:i+1]
                wo = opens_p[:i+1]
                wh = highs[:i+1]
                wl = lows[:i+1]
                
                struct = struct_fn(wc)
                struct_counts[struct] = struct_counts.get(struct, 0) + 1
                
                # 显示阶段分布
                stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
                key = (struct, stage)
                stage_in_struct[key] = stage_in_struct.get(key, 0) + 1

    total = sum(struct_counts.values())
    print(f'\n{label}:')
    for struct in ['上涨趋势', '区间震荡', '下降趋势', '--']:
        cnt = struct_counts.get(struct, 0)
        pct = cnt / total * 100 if total else 0
        print(f'  {struct}: {cnt:>6}次 ({pct:>5.1f}%)')
        
        # 该结构下的阶段详情
        sub_stages = {}
        for (s, stg), c in stage_in_struct.items():
            if s == struct:
                sub_stages[stg] = sub_stages.get(stg, 0) + c
        if sub_stages:
            for stg, c in sorted(sub_stages.items(), key=lambda x: -x[1]):
                sp = c / cnt * 100 if cnt else 0
                print(f'    ├─{stg}: {c:>6}次 ({sp:>5.1f}%)')

# 检查新版下各结构的5日收益
print()
print('=' * 80)
print('新版结构各阶段5日收益详表')
print('=' * 80)

results = {}
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
            
            struct = new_structure(wc)
            stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
            fwd = (closes[i+5] - closes[i]) / closes[i] * 100
            
            key = f'{struct}·{stage}'
            if key not in results:
                results[key] = {'returns': [], 'struct': struct, 'stage': stage}
            results[key]['returns'].append(fwd)

total_all = 0
all_returns = []
for key, r in sorted(results.items(), key=lambda x: (x[1]['struct'], x[1]['stage'])):
    rets = r['returns']
    bad = sum(1 for v in rets if v < 0)
    avg = sum(rets) / len(rets)
    total_all += len(rets)
    all_returns.extend(rets)
    print(f'  {key:<20}: {len(rets):>5}次 走弱{bad/len(rets)*100:5.1f}% 均{avg:+6.2f}%')

all_bad = sum(1 for v in all_returns if v < 0)
all_avg = sum(all_returns) / len(all_returns)
print(f'  {"总计":<20}: {total_all:>5}次 走弱{all_bad/total_all*100:5.1f}% 均{all_avg:+6.2f}%')
