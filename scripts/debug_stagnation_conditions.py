#!/usr/bin/env python3
"""放量滞涨根因分析 — 找最佳区分条件"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import get_stage, get_structure, ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

examples = []
for sector, codes in stocks.items():
    for code, klines in codes.items():
        name = klines[0].get('name', '') if klines else ''
        if len(klines) < 35: continue
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
            if struct != '上涨趋势': continue
            stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
            if stage != '放量滞涨': continue

            fwd_5 = (closes[i+5] - closes[i]) / closes[i] * 100
            # 分析特征
            gains_10d = (closes[i] - closes[i-9]) / closes[i-9] * 100 if i >= 9 else 0
            gains_5d = (closes[i] - closes[i-4]) / closes[i-4] * 100 if i >= 4 else 0
            pre_20 = closes[max(0, i-20):i+1]
            pos_pct = (closes[i] - min(pre_20)) / (max(pre_20) - min(pre_20) + 0.01) * 100
            
            e10 = ema_list(wc, 10)
            bias = (closes[i] - e10[-1]) / e10[-1] * 100 if e10[-1] else 0
            
            # 放量程度
            vol_last3 = sum(wv[-3:]) / 3
            vol_prev10 = sum(wv[-13:-3]) / 10
            vol_ratio = vol_last3 / vol_prev10 if vol_prev10 > 0 else 0
            
            # 是否有加速背景（前几日斜率）
            e10_last = [v for v in e10[-15:] if v is not None]
            s1_prev = _reg_slope(e10_last) if len(e10_last) >= 5 else 0
            s2_prev = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
            ratio_ema = s2_prev / s1_prev if abs(s1_prev) > 1e-8 else 1.0
            
            # 成交量是否在萎缩
            vol_trend = (sum(wv[-6:-3])/3 - sum(wv[-3:])/3) / (sum(wv[-6:-3])/3 + 0.01) * 100

            examples.append({
                'fwd_5': fwd_5, 'gains_10d': gains_10d, 'gains_5d': gains_5d,
                'pos_pct': pos_pct, 'bias': bias, 'vol_ratio': vol_ratio,
                'ratio_ema': ratio_ema, 'vol_trend': vol_trend
            })

print(f'放量滞涨总样本: {len(examples)}')
print()

# ── 条件1: 前期涨幅 —— 分档 ──
print('=' * 70)
print('条件分析：10日涨幅 vs 5日后涨跌')
print('=' * 70)
for thresh in [5, 8, 10, 12, 15, 18, 20, 25]:
    subset = [e for e in examples if e['gains_10d'] > thresh]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    print(f'  10日涨幅>{thresh:+d}%: {len(subset):>4}次  走弱{loss:5.1f}%({bad:>3})  均收益{avg:+7.2f}%')

# ── 条件2: 位置 —— 分档 ──
print()
print('=' * 70)
print('条件分析：20日位置分位 vs 5日后涨跌')  
print('=' * 70)
for thresh in [60, 70, 80, 85, 90, 95]:
    subset = [e for e in examples if e['pos_pct'] > thresh]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    print(f'  20日位置>{thresh}%: {len(subset):>4}次  走弱{loss:5.1f}%({bad:>3})  均收益{avg:+7.2f}%')

# ── 条件3: EMA10乖离率 ──
print()
print('=' * 70)
print('条件分析：EMA10乖离率 vs 5日后涨跌')
print('=' * 70)
for thresh in [3, 5, 7, 8, 10, 12]:
    subset = [e for e in examples if e['bias'] > thresh]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    print(f'  乖离>{thresh:+.0f}%: {len(subset):>4}次  走弱{loss:5.1f}%({bad:>3})  均收益{avg:+7.2f}%')

# ── 条件4: EMA10斜率比（是否在加速后） ──
print()
print('=' * 70)
print('条件分析：EMA10斜率比 vs 5日后涨跌 (加速后≈ratio>1.8)')
print('=' * 70)
for lo, hi, label in [(0, 0.4, '极缓'), (0.4, 1.0, '偏缓'), (1.0, 1.8, '正常'), (1.8, 99, '加速')]:
    subset = [e for e in examples if lo <= e['ratio_ema'] < hi]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    print(f'  斜率比{label}({lo}~{hi}): {len(subset):>4}次  走弱{loss:5.1f}%({bad:>3})  均收益{avg:+7.2f}%')

# ── 条件5: 量比阈值 ──
print()
print('=' * 70)
print('条件分析：量比阈值 vs 5日后涨跌')
print('=' * 70)
for thresh in [1.2, 1.3, 1.5, 1.8, 2.0]:
    subset = [e for e in examples if e['vol_ratio'] > thresh]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    print(f'  量比>{thresh:.1f}x: {len(subset):>4}次  走弱{loss:5.1f}%({bad:>3})  均收益{avg:+7.2f}%')

# ── 组合分析 ──
print()
print('=' * 70)
print('组合条件分析（最佳筛选组合）')
print('=' * 70)

combos = [
    ('10日涨幅>10% + 位置>80%', lambda e: e['gains_10d'] > 10 and e['pos_pct'] > 80),
    ('10日涨幅>10% + 乖离>5%', lambda e: e['gains_10d'] > 10 and e['bias'] > 5),
    ('10日涨幅>15% + 位置>85%', lambda e: e['gains_10d'] > 15 and e['pos_pct'] > 85),
    ('10日涨幅>10% + 乖离>5% + 位置>80%', lambda e: e['gains_10d'] > 10 and e['bias'] > 5 and e['pos_pct'] > 80),
    ('10日涨幅>15% + 乖离>8%', lambda e: e['gains_10d'] > 15 and e['bias'] > 8),
    ('10日涨幅>12% + 位置>85%', lambda e: e['gains_10d'] > 12 and e['pos_pct'] > 85),
    ('位置>90%', lambda e: e['pos_pct'] > 90),
    ('位置>85%', lambda e: e['pos_pct'] > 85),
    ('10日涨幅>10%', lambda e: e['gains_10d'] > 10),
    ('10日涨幅>15%', lambda e: e['gains_10d'] > 15),
    ('乖离>8%', lambda e: e['bias'] > 8),
    ('乖离>10%', lambda e: e['bias'] > 10),
    ('量比>1.5x + 乖离>5%', lambda e: e['vol_ratio'] > 1.5 and e['bias'] > 5),
]

print(f'{"条件":<30} {"次数":>4} {"占比":>6} {"走弱率":>8} {"均收益":>8}')
print('-' * 60)
for label, fn in combos:
    subset = [e for e in examples if fn(e)]
    if len(subset) < 5: continue
    bad = sum(1 for e in subset if e['fwd_5'] < 0)
    loss = bad / len(subset) * 100
    avg = sum(e['fwd_5'] for e in subset) / len(subset)
    pct = len(subset) / len(examples) * 100
    print(f'{label:<30} {len(subset):>4} {pct:>5.1f}% {loss:>7.1f}% {avg:+7.2f}%')
