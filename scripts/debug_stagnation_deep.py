#!/usr/bin/env python3
"""放量滞涨根因分析 — 时间窗口+位置分析"""
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

        for i in range(25, len(klines) - 10):
            wc = closes[:i+1]
            wv = volumes[:i+1]
            wo = opens_p[:i+1]
            wh = highs[:i+1]
            wl = lows[:i+1]
            struct = get_structure(wc)
            if struct != '上涨趋势': continue
            stage = get_stage(wc, struct, wh, wl, volumes=wv, opens_p=wo)
            if stage != '放量滞涨': continue

            pre_20 = closes[max(0, i-20):i+1]
            pos_pct = (closes[i] - min(pre_20)) / (max(pre_20) - min(pre_20) + 0.01) * 100
            pre_high = max(closes[max(0, i-10):i+1])
            body_pct = abs(closes[i] - opens_p[i]) / opens_p[i] if opens_p[i] else 1
            amp = (highs[i] - lows[i]) / lows[i] if lows[i] else 0

            e10 = ema_list(wc, 10)
            bias = (closes[i] - e10[-1]) / e10[-1] * 100 if e10[-1] else 0

            # 多窗口收益
            fwds = {}
            for d in [1, 2, 3, 5, 10]:
                if i + d < len(closes):
                    fwds[d] = (closes[i+d] - closes[i]) / closes[i] * 100

            examples.append({
                'code': code, 'name': name, 'i': i,
                'close': closes[i], 'high': highs[i], 'low': lows[i],
                'body_pct': body_pct, 'amp': amp,
                'pos_pct': pos_pct, 'bias': bias,
                'pre_5d': [(closes[i-d]-closes[i-d-1])/closes[i-d-1]*100 for d in range(5) if i-d-1 >= 0],
                'post_prices': [closes[i+d] for d in range(1, 11) if i+d < len(closes)],
                'post_lows': [lows[i+d] for d in range(1, 11) if i+d < len(closes)],
                'post_highs': [highs[i+d] for d in range(1, 11) if i+d < len(closes)],
                'fwds': fwds,
                'closes': closes, 'opens_p': opens_p,
                'highs': highs, 'lows': lows
            })

print(f'放量滞涨总样本: {len(examples)}')

# 1. 不同时间窗口走弱率
print()
print('=' * 70)
print('多时间窗口走弱率')
print('=' * 70)
for d in [1, 2, 3, 5, 10]:
    valid = [e for e in examples if d in e['fwds']]
    bad = sum(1 for e in valid if e['fwds'][d] < 0)
    avg = sum(e['fwds'][d] for e in valid) / len(valid)
    print(f'  {d}日: {bad}/{len(valid)} ({bad/len(valid)*100:.1f}%)  均收益{avg:+.2f}%')

# 2. 放量滞涨后是否跌破信号日低点（止损关键）
print()
print('=' * 70)
print('放量滞涨后是否跌破信号日低点')
print('=' * 70)
for d in [3, 5, 10]:
    valid = [e for e in examples if len(e['post_lows']) >= d]
    broke = sum(1 for e in valid if min(e['post_lows'][:d]) < e['low'])
    print(f'  {d}日内跌破信号日低点: {broke}/{len(valid)} ({broke/len(valid)*100:.1f}%)')

# 3. 位置分层 + 时间窗口
print()
print('=' * 70)
print('位置分层 × 时间窗口')
print('=' * 70)
for pos_thresh in [80, 85, 90, 95]:
    subset = [e for e in examples if e['pos_pct'] > pos_thresh]
    if len(subset) < 5: continue
    for d in [1, 3, 5]:
        valid = [e for e in subset if d in e['fwds']]
        bad = sum(1 for e in valid if e['fwds'][d] < 0)
        avg = sum(e['fwds'][d] for e in valid) / len(valid)
        print(f'  位置>{pos_thresh}% × {d}日: {bad}/{len(valid)} ({bad/len(valid)*100:.1f}%)  均{avg:+.2f}%')

# 4. 放量滞涨信号日的实体大小 vs 预测力
print()
print('=' * 70)
print('实体大小 vs 预测力（5日）')
print('=' * 70)
for body_max in [0.005, 0.01, 0.015, 0.02, 0.025, 0.03]:
    subset = [e for e in examples if e['body_pct'] < body_max and 5 in e['fwds']]
    bad = sum(1 for e in subset if e['fwds'][5] < 0)
    avg = sum(e['fwds'][5] for e in subset) / len(subset)
    print(f'  实体<{body_max*100:.1f}%: {len(subset):>3}次  走弱{bad/len(subset)*100:5.1f}%  均{avg:+6.2f}%')

# 5. 检查：放量滞涨后是否紧接着继续下跌（连续2日走弱）
print()
print('=' * 70)
print('放量滞涨后是否连续走弱')
print('=' * 70)
for d in [2, 3, 5]:
    valid = [e for e in examples if d in e['fwds']]
    # 连续下跌：每1日都跌
    streak_bad = 0
    for e in valid:
        all_down = all(e['fwds'][dd] < 0 for dd in range(1, d+1) if dd in e['fwds'])
        if all_down:
            streak_bad += 1
    print(f'  连续{d}日全跌: {streak_bad}/{len(valid)} ({streak_bad/len(valid)*100:.1f}%)')

# 6. 放量滞涨后+后续日K线确认（次日又跌）
print()
print('=' * 70)
print('放量滞涨+次日低开/阴线确认')
print('=' * 70)
for cond_name, cond_fn in [
    ('+ 次日阴线', lambda e, c, o: c[0] < o[0] if len(c) >= 1 and len(o) >= 1 else False),
    ('+ 次日跌>1%', lambda e, c, o: (c[0]-o[0])/o[0]*100 < -1 if len(c) >= 1 and len(o) >= 1 else False),
    ('+ 次日跌>2%', lambda e, c, o: (c[0]-o[0])/o[0]*100 < -2 if len(c) >= 1 and len(o) >= 1 else False),
    ('+ 次日创新低', lambda e, c, o: c[0] < e['low'] if len(c) >= 1 else False),
]:
    subset = []
    for e in examples:
        if 1 not in e['fwds']: continue
        post_c = e['post_prices'][:1]
        post_o = [e['opens_p'][e['i']+1]] if e['i']+1 < len(e['opens_p']) else []
        if cond_fn(e, post_c, post_o):
            subset.append(e)
    if len(subset) < 3: continue
    valid = [e for e in subset if 5 in e['fwds']]
    bad = sum(1 for e in valid if e['fwds'][5] < 0)
    avg = sum(e['fwds'][5] for e in valid) / len(valid)
    print(f'  放量滞涨{cond_name}: {len(valid):>3}次  走弱{bad/len(valid)*100:5.1f}%  均{avg:+6.2f}%')

# 7. max drawdown after signal
print()
print('=' * 70)
print('放量滞涨后最大回撤')
print('=' * 70)
for d in [5, 10]:
    valid = [e for e in examples if len(e['post_lows']) >= d]
    dd_list = []
    for e in valid[:d]:
        max_price = e['close']
        min_price = min(e['post_lows'][:d])
        dd = (max_price - min_price) / max_price * 100
        dd_list.append(dd)
    avg_dd = sum(dd_list) / len(dd_list)
    dd_gt_5 = sum(1 for dd in dd_list if dd > 5)
    dd_gt_10 = sum(1 for dd in dd_list if dd > 10)
    print(f'  {d}日内平均最大回撤: {avg_dd:.1f}%')
    print(f'  回撤>5%: {dd_gt_5}/{len(valid)} ({dd_gt_5/len(valid)*100:.1f}%)')
    print(f'  回撤>10%: {dd_gt_10}/{len(valid)} ({dd_gt_10/len(valid)*100:.1f}%)')
