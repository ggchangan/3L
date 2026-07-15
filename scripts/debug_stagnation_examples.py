#!/usr/bin/env python3
"""放量滞涨个例分析"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import get_stage, get_structure, ema_list

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

# 收集所有放量滞涨实例
examples = []
for sector, codes in stocks.items():
    for code, klines in codes.items():
        name = klines[0].get('name', '') if klines else ''
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

            stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
            if stage != '放量滞涨':
                continue

            fwd_5 = (closes[i+5] - closes[i]) / closes[i] * 100
            examples.append({
                'code': code, 'name': name, 'date_idx': i,
                'cur_close': closes[i],
                'fwd_5': fwd_5,
                'vol_ratio': (sum(wv[-3:])/3) / (sum(wv[-13:-3])/10) if len(wv) >= 13 else 0,
                'body_pct': abs(closes[i] - opens_p[i]) / opens_p[i] if opens_p[i] else 0,
                'amp': (highs[i] - lows[i]) / lows[i] if lows[i] else 0,
                'closes': closes, 'volumes': volumes,
                'opens_p': opens_p, 'highs': highs, 'lows': lows,
                'i': i
            })

# 按5日收益排序
examples.sort(key=lambda x: x['fwd_5'])

print(f'放量滞涨总样本: {len(examples)}')
print()

# 最差的10个
print('=' * 80)
print(f'🔴 放量滞涨后5日跌幅最大的10例')
print('=' * 80)
for ex in examples[:10]:
    i = ex['i']
    c = ex['closes']
    v = ex['volumes']
    o = ex['opens_p']
    h = ex['highs']
    l = ex['lows']
    
    # 信号日前5日细节
    pre_5 = []
    for j in range(max(0, i-5), i+1):
        chg = (c[j] - c[j-1]) / c[j-1] * 100 if j > 0 else 0
        vol_c = v[j] if j < len(v) else 0
        pre_5.append(f'{chg:+.1f}%(量{vol_c/1e6:.0f}M)')
    
    fwd_5d = []
    for j in range(i+1, min(i+6, len(c))):
        chg = (c[j] - c[j-1]) / c[j-1] * 100 if j > 0 else 0
        fwd_5d.append(f'{chg:+.1f}%')
    
    print(f'\n{ex["code"]} {ex["name"]} (idx={i}, close={c[i]:.2f})')
    print(f'  信号参数: 量比={ex["vol_ratio"]:.2f}x 实体={ex["body_pct"]*100:.1f}% 振幅={ex["amp"]*100:.1f}%')
    print(f'  前5日: {" → ".join(pre_5)}')
    print(f'  后5日: {" → ".join(fwd_5d)} 总计={ex["fwd_5"]:+.2f}%')
    
    # 检查信号日是否为阶段高点
    peak_check = (c[i] - c[i-5]) / c[i-5] * 100
    print(f'  信号前5日涨幅: {peak_check:+.1f}%')

# 赢的10个
print()
print('=' * 80)
print(f'🟢 放量滞涨后5日涨幅最大的10例')
print('=' * 80)
for ex in reversed(examples[-10:]):
    i = ex['i']
    c = ex['closes']
    
    pre_5 = []
    for j in range(max(0, i-5), i+1):
        chg = (c[j] - c[j-1]) / c[j-1] * 100 if j > 0 else 0
        pre_5.append(f'{chg:+.1f}%')
    
    fwd_5d = []
    for j in range(i+1, min(i+6, len(c))):
        chg = (c[j] - c[j-1]) / c[j-1] * 100 if j > 0 else 0
        fwd_5d.append(f'{chg:+.1f}%')
    
    print(f'\n{ex["code"]} {ex["name"]} (idx={i}, close={c[i]:.2f})')
    print(f'  信号参数: 量比={ex["vol_ratio"]:.2f}x 实体={ex["body_pct"]*100:.1f}% 振幅={ex["amp"]*100:.1f}%')
    print(f'  前5日: {" → ".join(pre_5)}')
    print(f'  后5日: {" → ".join(fwd_5d)} 总计={ex["fwd_5"]:+.2f}%')
    peak_check = (c[i] - c[i-5]) / c[i-5] * 100
    print(f'  信号前5日涨幅: {peak_check:+.1f}%')

# 统计信号后收益分布
print()
print('=' * 80)
print('统计: 放量滞涨后5日收益分布')
print('=' * 80)

# 信号日是否在高位？
high_pos_count = 0
mid_pos_count = 0
for ex in examples:
    c = ex['closes']
    i = ex['i']
    pre_20 = c[max(0, i-20):i+1]
    pos = (c[i] - min(pre_20)) / (max(pre_20) - min(pre_20)) * 100 if max(pre_20) > min(pre_20) else 50
    if pos > 80:
        high_pos_count += 1
    elif pos > 30:
        mid_pos_count += 1

print(f'  信号在20日高位(>80%分位): {high_pos_count}/{len(examples)} ({high_pos_count/len(examples)*100:.1f}%)')
print(f'  信号在20日中部(30-80%): {mid_pos_count}/{len(examples)} ({mid_pos_count/len(examples)*100:.1f}%)')
print(f'  信号在20日低位(<30%): {len(examples)-high_pos_count-mid_pos_count}/{len(examples)}')

# 信号日成交量特征
vol_high = sum(1 for ex in examples if ex['vol_ratio'] > 1.5)
print(f'  量比>1.5x: {vol_high}/{len(examples)} ({vol_high/len(examples)*100:.1f}%)')

# 信号出现时在EMA10的乖离
from threel_core.ema_utils import ema_list
bias_analysis = []
for ex in examples:
    c = ex['closes'][:ex['i']+1]
    e10 = ema_list(c, 10)
    cur_e10 = e10[-1]
    cur_c = c[-1]
    bias = (cur_c - cur_e10) / cur_e10 * 100 if cur_e10 else 0
    bias_analysis.append(bias)

avg_bias = sum(bias_analysis) / len(bias_analysis)
bias_positive = sum(1 for b in bias_analysis if b > 0)
bias_over_5 = sum(1 for b in bias_analysis if b > 5)
print(f'  信号日平均EMA10乖离率: {avg_bias:+.2f}%')
print(f'  乖离>0%: {bias_positive}/{len(bias_analysis)} ({bias_positive/len(bias_analysis)*100:.1f}%)')
print(f'  乖离>5%: {bias_over_5}/{len(bias_analysis)} ({bias_over_5/len(bias_analysis)*100:.1f}%)')
