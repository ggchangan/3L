#!/usr/bin/env python3
"""结构判定优化回测 — 全面参数扫描"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def structure_by_slope(closes, period=20, lookback=10, slope_thresh=0.2, bias_thresh=2.0):
    """通用结构判定函数"""
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

print('=' * 100)
print('结构判定参数扫描 — 239只股票 × 60天滚动')
print('衡量标准：结构判定后5日收益的区分度（上涨收益 - 下降收益）')
print('区分度越高，说明判定的涨/跌方向越准确')
print('=' * 100)

configs = []
# EMA周期
for period in [10, 15, 20, 30]:
    # 回看窗口
    for lookback in [8, 10, 12, 15, 20]:
        # 斜率阈值
        for st in [0.1, 0.15, 0.2, 0.25, 0.3, 0.4]:
            # 乖离阈值
            for bt in [1.0, 1.5, 2.0, 3.0, 4.0]:
                configs.append((period, lookback, st, bt))

import random
random.seed(42)
random.shuffle(configs)
configs = configs[:500]  # 扫描500种组合

results = []
for period, lookback, st, bt in configs:
    up_returns = []
    down_returns = []
    range_returns = []
    up_count = 0
    down_count = 0
    range_count = 0
    
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35:
                continue
            closes = [k['close'] for k in klines]
            
            for i in range(max(period + lookback, 30), len(klines) - 5):
                wc = closes[:i+1]
                struct = structure_by_slope(wc, period, lookback, st, bt)
                fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                
                if struct == '上涨趋势':
                    up_returns.append(fwd)
                    up_count += 1
                elif struct == '下降趋势':
                    down_returns.append(fwd)
                    down_count += 1
                else:
                    range_returns.append(fwd)
                    range_count += 1
    
    if up_count < 50 or down_count < 30:
        continue
    
    up_avg = sum(up_returns) / len(up_returns)
    down_avg = sum(down_returns) / len(down_returns)
    range_avg = sum(range_returns) / len(range_returns) if range_returns else 0
    discrimination = up_avg - down_avg
    
    results.append({
        'period': period, 'lookback': lookback, 'st': st, 'bt': bt,
        'up': up_count, 'up_avg': up_avg,
        'down': down_count, 'down_avg': down_avg,
        'range': range_count, 'range_avg': range_avg,
        'discrimination': discrimination
    })

# 按区分度排序
results.sort(key=lambda x: -x['discrimination'])

print(f'\n{"排名":>4} {"EMA":>4} {"窗口":>4} {"斜率阈":>6} {"乖离阈":>6} {"上涨":>6} {"涨收益":>8} {"下降":>6} {"跌收益":>8} {"震荡":>6} {"震收益":>8} {"区分度":>8}')
print('-' * 100)
for i, r in enumerate(results[:20]):
    print(f'{i+1:>4} {r["period"]:>4} {r["lookback"]:>4} {r["st"]:>5.2f} {r["bt"]:>5.1f} {r["up"]:>6} {r["up_avg"]:+7.2f}% {r["down"]:>6} {r["down_avg"]:+7.2f}% {r["range"]:>6} {r["range_avg"]:+7.2f}% {r["discrimination"]:+7.2f}%')

# 生成版对比
print('\n' + '=' * 100)
print('当前生产版 vs 最优参数对比')
print('=' * 100)

# 生产版
up_returns_p = []; down_returns_p = []; range_returns_p = []
for sector, codes in stocks.items():
    for code, klines in codes.items():
        if len(klines) < 35: continue
        closes = [k['close'] for k in klines]
        for i in range(30, len(klines) - 5):
            wc = closes[:i+1]
            struct = structure_by_slope(wc, 20, 10, 0.2, 2.0)
            fwd = (closes[i+5] - closes[i]) / closes[i] * 100
            if struct == '上涨趋势': up_returns_p.append(fwd)
            elif struct == '下降趋势': down_returns_p.append(fwd)
            else: range_returns_p.append(fwd)

up_avg_p = sum(up_returns_p) / len(up_returns_p)
down_avg_p = sum(down_returns_p) / len(down_returns_p)
range_avg_p = sum(range_returns_p) / len(range_returns_p) if range_returns_p else 0
disc_p = up_avg_p - down_avg_p

print(f'当前版(EMA20/10/0.2/2.0):')
print(f'  上涨{len(up_returns_p):>6}次 均{up_avg_p:+7.2f}% | 下降{len(down_returns_p):>6}次 均{down_avg_p:+7.2f}% | 震荡{len(range_returns_p):>6}次 均{range_avg_p:+7.2f}%')
print(f'  区分度: {disc_p:+7.2f}%')

# TOP3参数
for ri in range(min(3, len(results))):
    r = results[ri]
    up_r = []; down_r = []; range_r = []
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35: continue
            closes = [k['close'] for k in klines]
            for i in range(30, len(klines) - 5):
                wc = closes[:i+1]
                struct = structure_by_slope(wc, r['period'], r['lookback'], r['st'], r['bt'])
                fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                if struct == '上涨趋势': up_r.append(fwd)
                elif struct == '下降趋势': down_r.append(fwd)
                else: range_r.append(fwd)
    
    up_avg_r = sum(up_r) / len(up_r)
    down_avg_r = sum(down_r) / len(down_r)
    range_avg_r = sum(range_r) / len(range_r) if range_r else 0
    disc_r = up_avg_r - down_avg_r
    
    print(f'\n最优#{ri+1}(EMA{r["period"]}/窗口{r["lookback"]}/斜率{r["st"]}/乖离{r["bt"]}):')
    print(f'  上涨{len(up_r):>6}次 均{up_avg_r:+7.2f}% | 下降{len(down_r):>6}次 均{down_avg_r:+7.2f}% | 震荡{len(range_r):>6}次 均{range_avg_r:+7.2f}%')
    print(f'  区分度: {disc_r:+7.2f}%')

# 稳定性检查：不同行情分段
print('\n' + '=' * 100)
print('稳定性检查：不同行情分段（前30天 vs 后30天）')
print('=' * 100)

for split_label, split_fn in [
    ('前30天(2026/4-5)', lambda k: k[:30]),
    ('后30天(2026/5-6)', lambda k: k[-30:] if len(k) >= 30 else k),
]:
    up_s = []; down_s = []; range_s = []
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35: continue
            closes = [k['close'] for k in klines]
            if len(closes) < 35: continue
            
            if split_label == '前30天(2026/4-5)':
                # 前30天：判定位置在25-30之间
                for i in range(25, min(35, len(closes) - 5)):
                    wc = closes[:i+1]
                    struct = structure_by_slope(wc, 20, 10, 0.2, 2.0)
                    fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                    if struct == '上涨趋势': up_s.append(fwd)
                    elif struct == '下降趋势': down_s.append(fwd)
                    else: range_s.append(fwd)
            else:
                # 后30天：判定位置在最后
                for i in range(len(closes) - 10, len(closes) - 5):
                    wc = closes[:i+1]
                    struct = structure_by_slope(wc, 20, 10, 0.2, 2.0)
                    fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                    if struct == '上涨趋势': up_s.append(fwd)
                    elif struct == '下降趋势': down_s.append(fwd)
                    else: range_s.append(fwd)
    
    if up_s and down_s:
        disc = sum(up_s)/len(up_s) - sum(down_s)/len(down_s)
        print(f'{split_label}: 区分度{disc:+7.2f}% (上涨{len(up_s):>4}次 {sum(up_s)/len(up_s):+6.2f}% | 下降{len(down_s):>4}次 {sum(down_s)/len(down_s):+6.2f}%)')
    else:
        print(f'{split_label}: 样本不足')
