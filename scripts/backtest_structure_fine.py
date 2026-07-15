#!/usr/bin/env python3
"""结构判定 — 精细参数扫描"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def structure_fn(closes, period, lookback, st, bt):
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
    if slope_pct > st and bias > -bt:
        return '上涨趋势'
    elif slope_pct < -st and bias < bt:
        return '下降趋势'
    else:
        return '区间震荡'

print('=' * 120)
print('精细参数扫描 — EMA10 窗口/斜率/乖离 网格')
print('=' * 120)

results = []
# EMA10 + 窗口变化
for lookback in [10, 11, 12, 13, 14, 15]:
    # 斜率阈值
    for st in [0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.55]:
        # 乖离阈值
        for bt in [2.0, 2.5, 3.0, 3.5, 4.0]:
            up_r = []; down_r = []; range_r = []
            for sector, codes in stocks.items():
                for code, klines in codes.items():
                    if len(klines) < 35: continue
                    closes = [k['close'] for k in klines]
                    for i in range(30, len(klines) - 5):
                        wc = closes[:i+1]
                        struct = structure_fn(wc, 10, lookback, st, bt)
                        fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                        if struct == '上涨趋势': up_r.append(fwd)
                        elif struct == '下降趋势': down_r.append(fwd)
                        else: range_r.append(fwd)
            
            if len(up_r) < 50 or len(down_r) < 20:
                continue
            up_avg = sum(up_r)/len(up_r)
            down_avg = sum(down_r)/len(down_r)
            range_avg = sum(range_r)/len(range_r) if range_r else 0
            disc = up_avg - down_avg
            results.append({
                'lookback': lookback, 'st': st, 'bt': bt,
                'up': len(up_r), 'up_avg': up_avg,
                'down': len(down_r), 'down_avg': down_avg,
                'range': len(range_r), 'range_avg': range_avg,
                'disc': disc
            })

results.sort(key=lambda x: -x['disc'])

print(f'{"排名":>4} {"窗口":>4} {"斜率":>6} {"乖离":>6} {"上涨量":>6} {"涨均":>8} {"下跌量":>6} {"跌均":>8} {"震荡量":>6} {"震均":>8} {"区分度":>8}')
print('-' * 100)
for i, r in enumerate(results[:25]):
    print(f'{i+1:>4} {r["lookback"]:>4} {r["st"]:>5.2f} {r["bt"]:>4.1f} {r["up"]:>6} {r["up_avg"]:+7.2f}% {r["down"]:>6} {r["down_avg"]:+7.2f}% {r["range"]:>6} {r["range_avg"]:+7.2f}% {r["disc"]:+7.2f}%')

# 稳定性：TOP5 前30天 vs 后30天
print()
print('=' * 120)
print('稳定性检查：TOP5 × 时间分段')
print('=' * 120)

for ri, r in enumerate(results[:5]):
    for split_name, split_range in [('前30天', (25, 30)), ('后30天', (len(list(stocks.values())[0])-15, len(list(stocks.values())[0])-5))]:
        up_s = []; down_s = []; range_s = []
        for sector, codes in stocks.items():
            for code, klines in codes.items():
                if len(klines) < 35: continue
                closes = [k['close'] for k in klines]
                start, end = split_range
                for i in range(max(start, 25), min(end, len(closes) - 5)):
                    wc = closes[:i+1]
                    struct = structure_fn(wc, 10, r['lookback'], r['st'], r['bt'])
                    fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                    if struct == '上涨趋势': up_s.append(fwd)
                    elif struct == '下降趋势': down_s.append(fwd)
                    else: range_s.append(fwd)
        
        if up_s and down_s:
            disc = sum(up_s)/len(up_s) - sum(down_s)/len(down_s)
            print(f'  #{ri+1}(EMA10/窗{r["lookback"]}/{r["st"]}/{r["bt"]:+.1f}) {split_name}: 区分度{disc:+7.2f}% (涨{len(up_s):>4}次 {sum(up_s)/len(up_s):+6.2f}% | 跌{len(down_s):>4}次 {sum(down_s)/len(down_s):+6.2f}%)')
