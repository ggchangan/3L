#!/usr/bin/env python3
"""各阶段5日预测力回测"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import get_stage, get_structure

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

results = {s: {'hits': 0, 'total': 0, 'returns': []}
           for s in ['放量滞涨', '加速', '上行', '转弱', '缩量整理', '缩量滞涨']}
total_uptrend = 0

for sector, codes in stocks.items():
    for code, klines in codes.items():
        if len(klines) < 35:
            continue
        closes = [k['close'] for k in klines]
        volumes = [k['volume'] for k in klines]
        opens_p = [k['open'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]

        for i in range(25, len(klines) - 5):
            wc = closes[:i+1]
            wv = volumes[:i+1]
            wo = opens_p[:i+1]
            wh = highs[:i+1]
            wl = lows[:i+1]

            struct = get_structure(wc)
            if struct != '上涨趋势':
                continue
            total_uptrend += 1

            stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
            if stage not in results:
                continue

            fwd = (closes[i+5] - closes[i]) / closes[i] * 100
            results[stage]['total'] += 1
            results[stage]['returns'].append(fwd)
            if fwd < 0:
                results[stage]['hits'] += 1

# 基准
all_returns = []
for s in ['加速', '上行', '转弱', '放量滞涨', '缩量整理']:
    all_returns.extend(results[s]['returns'])
all_bad = sum(1 for r in all_returns if r < 0)
all_avg = sum(all_returns) / len(all_returns) if all_returns else 0
base_loss = all_bad / len(all_returns) * 100

print(f'上涨趋势总样本: {total_uptrend}')
print()
print(f'{"阶段":<12} {"次数":>6} {"占比":>8}  {"5日走弱":<18} {"均收益":>8} {"跑赢基准":>8}')
print('-' * 65)
print(f'{"上涨趋势(总)":<12} {"":>6} {"100.0%":>8}  走弱{base_loss:.1f}%({all_bad}/{len(all_returns)})  {all_avg:+.2f}%     --')

for stage in ['加速', '上行', '转弱', '放量滞涨', '缩量整理', '缩量滞涨']:
    r = results[stage]
    if r['total'] == 0:
        continue
    bad_pct = r['hits'] / r['total'] * 100
    avg_ret = sum(r['returns']) / len(r['returns'])
    uplift = bad_pct - base_loss
    hit_str = f'走弱{bad_pct:.1f}%({r["hits"]}/{r["total"]})'
    print(f'{stage:<12} {r["total"]:>6} {r["total"]/total_uptrend*100:>7.1f}%  {hit_str:<18} {avg_ret:+8.2f}%  {-uplift:+7.1f}%')

# 放量滞涨详细
print()
r = results['放量滞涨']
win = r['total'] - r['hits']
big_wins = sum(1 for v in r['returns'] if v > 10)
big_loss = sum(1 for v in r['returns'] if v < -10)
rs = sorted(r['returns'], reverse=True)
print(f'放量滞涨 ({r["total"]}次):')
print(f'  盈利: {win}次({win/r["total"]*100:.1f}%)  亏损: {r["hits"]}次({r["hits"]/r["total"]*100:.1f}%)')
print(f'  大涨>10%: {big_wins}次({big_wins/r["total"]*100:.1f}%)  大跌<-10%: {big_loss}次({big_loss/r["total"]*100:.1f}%)')
print(f'  Max: {rs[0]:+.2f}%  中位: {rs[len(rs)//2]:+.2f}%  Min: {rs[-1]:+.2f}%')
