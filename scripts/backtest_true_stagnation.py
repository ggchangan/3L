#!/usr/bin/env python3
"""真滞涨 vs 假滞涨 — 什么条件下上涨趋势的股票5日会跌"""

import json, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope, get_structure, get_stage

def load_stocks():
    with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
        data = json.load(f)
    stocks = data.get('stocks', data)
    result = []
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            result.append((code, name, klines))
    return result

stocks = load_stocks()
print(f'{len(stocks)} 只股票')

# ── 找出上涨趋势中后续5日实际走弱的样本 ──
bad_samples = []  # 后续5日跌的
good_samples = []  # 后续5日涨的

for code, name, klines in stocks:
    if len(klines) < 40:
        continue
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    volumes = [k['volume'] for k in klines]
    
    for i in range(25, len(klines) - 5):
        window_c = closes[:i+1]
        window_v = volumes[:i+1]
        struct = get_structure(window_c)
        if struct != '上涨趋势':
            continue
        
        fwd_ret = (closes[i+5] - closes[i]) / closes[i] * 100
        sample = {
            'code': code, 'name': name, 'idx': i,
            'close': closes[i], 'fwd_ret': fwd_ret,
            'stage': get_stage(window_c, struct, highs=highs[:i+1], lows=lows[:i+1], volumes=window_v),
        }
        
        # 当前EMA10
        e10 = ema_list(window_c, 10)
        e10_last = [v for v in e10[-15:] if v is not None]
        s1 = _reg_slope(e10_last) if len(e10_last) >= 5 else 0
        s2 = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
        sample['s1'] = s1; sample['s2'] = s2
        sample['ratio'] = s2 / s1 if abs(s1) > 1e-8 else 1.0
        
        cur_ema10 = e10_last[-1] if e10_last else closes[i]
        sample['bias10'] = (closes[i] - cur_ema10) / cur_ema10 * 100
        
        vol3 = sum(window_v[-3:]) / 3 if len(window_v) >= 3 else 0
        vol10 = sum(window_v[-13:-3]) / 10 if len(window_v) >= 13 else 0
        sample['vol_ratio'] = vol3 / vol10 if vol10 > 0 else 1.0
        
        # 近5根K线振幅
        recent_high = max(highs[i-4:i+1]) if i >= 4 else highs[i]
        recent_low = min(lows[i-4:i+1]) if i >= 4 else lows[i]
        sample['recent_amp'] = (recent_high - recent_low) / recent_low * 100
        
        # 距前高距离
        if i >= 10:
            prev_high = max(highs[i-10:i])
            sample['dist_from_high'] = (closes[i] - prev_high) / prev_high * 100
        else:
            sample['dist_from_high'] = 0
        
        if fwd_ret < 0:
            bad_samples.append(sample)
        else:
            good_samples.append(sample)

print(f'\n上涨趋势中后续5日涨: {len(good_samples)}次')
print(f'上涨趋势中后续5日跌: {len(bad_samples)}次')
print(f'整体5日胜率: {len(good_samples)/(len(good_samples)+len(bad_samples))*100:.1f}%')

# ── 分析走弱样本的特征 ──
print(f'\n{"="*70}')
print(f'走弱样本 vs 走强样本 特征对比')
print(f'{"="*70}')

features = [
    ('斜率比(s2/s1)', 'ratio'),
    ('EMA10乖离率', 'bias10'),
    ('量比(3d/10d)', 'vol_ratio'),
    ('近5日振幅%', 'recent_amp'),
    ('距前高距离%', 'dist_from_high'),
]

for name, key in features:
    bad_avg = sum(s[key] for s in bad_samples) / len(bad_samples)
    good_avg = sum(s[key] for s in good_samples) / len(good_samples)
    print(f'  {name}: 走弱{bad_avg:.2f} vs 走强{good_avg:.2f}')

# ── 找最佳截止点 ──
print(f'\n{"="*70}')
print(f'各特征分档 — 走弱率')
print(f'{"="*70}')

all_samples = bad_samples + good_samples
total = len(all_samples)

for name, key in features:
    values = sorted(set(s[key] for s in all_samples))
    # 分5档
    n = len(all_samples)
    sorted_s = sorted(all_samples, key=lambda s: s[key])
    for pct in [10, 25, 50, 75, 90]:
        idx = int(n * pct / 100)
        threshold = sorted_s[min(idx, n-1)][key] if idx < n else sorted_s[-1][key]
        # 低于阈值的样本中走弱比例
        subset = [s for s in all_samples if s[key] <= threshold]
        if len(subset) > 0:
            bad_in = sum(1 for s in subset if s['fwd_ret'] < 0)
            print(f'  第{pct}%分位({name}<={threshold:.2f}): {bad_in}/{len(subset)}={bad_in/len(subset)*100:.1f}%走弱')
    
    # 高于阈值的走弱率
    for pct in [90]:
        idx = int(n * pct / 100)
        threshold = sorted_s[min(idx, n-1)][key] if idx < n else sorted_s[-1][key]
        subset = [s for s in all_samples if s[key] > threshold]
        if len(subset) > 0:
            bad_in = sum(1 for s in subset if s['fwd_ret'] < 0)
            print(f'  第{pct}%分位({name}>{threshold:.2f}): {bad_in}/{len(subset)}={bad_in/len(subset)*100:.1f}%走弱')
    print()

# ── 综合条件：寻找"真滞涨" ──
print(f'\n{"="*70}')
print(f'综合条件筛选 — 真滞涨特征')
print(f'{"="*70}')

conditions = [
    ('斜率比<0.2', lambda s: s['ratio'] < 0.2),
    ('斜率比<0.1', lambda s: s['ratio'] < 0.1),
    ('量比<0.6', lambda s: s['vol_ratio'] < 0.6),
    ('量比<0.5', lambda s: s['vol_ratio'] < 0.5),
    ('振幅<2%', lambda s: s['recent_amp'] < 2),
    ('振幅<1.5%', lambda s: s['recent_amp'] < 1.5),
    ('距前高-5~0%', lambda s: -5 < s['dist_from_high'] < 0),
    ('距前高-3~0%', lambda s: -3 < s['dist_from_high'] < 0),
    ('BIAS<1%', lambda s: s['bias10'] < 1),
    ('BIAS<0.5%', lambda s: s['bias10'] < 0.5),
]

for label, fn in conditions:
    subset = [s for s in all_samples if fn(s)]
    if len(subset) > 0:
        bad_in = sum(1 for s in subset if s['fwd_ret'] < 0)
        avg_ret = sum(s['fwd_ret'] for s in subset) / len(subset)
        print(f'  {label}: {len(subset)}次 走弱{bad_in}/{len(subset)}={bad_in/len(subset)*100:.1f}% 均收益{avg_ret:+.2f}%')

# ── 组合条件 ──
print(f'\n--- 组合条件 ---')
combos = [
    ('斜率<0.2 + 缩量<0.6', lambda s: s['ratio'] < 0.2 and s['vol_ratio'] < 0.6),
    ('斜率<0.2 + 振幅<2', lambda s: s['ratio'] < 0.2 and s['recent_amp'] < 2),
    ('斜率<0.2 + 距前高±3%', lambda s: s['ratio'] < 0.2 and abs(s['dist_from_high']) < 3),
    ('斜率<0.1 + 振幅<2', lambda s: s['ratio'] < 0.1 and s['recent_amp'] < 2),
    ('斜率<0.1 + BIAS<1', lambda s: s['ratio'] < 0.1 and s['bias10'] < 1),
    ('斜率<0.2 + BIAS<0.5 + 振幅<2', lambda s: s['ratio'] < 0.2 and s['bias10'] < 0.5 and s['recent_amp'] < 2),
    ('斜率<0.1 + BIAS<0.5', lambda s: s['ratio'] < 0.1 and s['bias10'] < 0.5),
    ('斜率<0.1 + BIAS<0.5 + 振幅<2', lambda s: s['ratio'] < 0.1 and s['bias10'] < 0.5 and s['recent_amp'] < 2),
    ('斜率<0.05 + BIAS<0.5', lambda s: s['ratio'] < 0.05 and s['bias10'] < 0.5),
    ('斜率<0.05 + BIAS<0 + 振幅<2', lambda s: s['ratio'] < 0.05 and s['bias10'] < 0 and s['recent_amp'] < 2),
    ('斜率<0.2 + 量增(>1.2)', lambda s: s['ratio'] < 0.2 and s['vol_ratio'] > 1.2),
    ('斜率<0.3 + 距前高<0', lambda s: s['ratio'] < 0.3 and s['dist_from_high'] < 0),
    ('斜率<0.3 + 距前高< -2%', lambda s: s['ratio'] < 0.3 and s['dist_from_high'] < -2),
]

for label, fn in combos:
    subset = [s for s in all_samples if fn(s)]
    if len(subset) >= 10:
        bad_in = sum(1 for s in subset if s['fwd_ret'] < 0)
        avg_ret = sum(s['fwd_ret'] for s in subset) / len(subset)
        print(f'  {label}: {len(subset)}次 走弱{bad_in}/{len(subset)}={bad_in/len(subset)*100:.1f}% 均收益{avg_ret:+.2f}%')
