#!/usr/bin/env python3
"""结构判定精细优化 — 不对称阈值 + EMA排列过滤"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope, get_ema_arrangement

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

# ═══════════════════════════════════════════
# 方案A: 不对称阈值 — 上涨严/下降宽 或 上涨宽/下降严
# ═══════════════════════════════════════════
print('=' * 120)
print('方案A: 不对称阈值扫描')
print('思路: 上涨用高斜率(少而精)，下降用低斜率(多且真跌)')
print('=' * 120)

asan_configs = []
for period in [10, 12]:
    for lookback in [10, 11, 12, 13]:
        # 上涨 — 严格：高斜率+宽乖离
        for up_st in [0.5, 0.6, 0.7, 0.8]:
            for up_bt in [2, 3, 4, 5]:
                # 下降 — 宽松：低斜率+窄乖离，让下降更多
                for dn_st in [0.2, 0.25, 0.3, 0.35, 0.4]:
                    for dn_bt in [1.0, 1.5, 2.0, 3.0]:
                        asan_configs.append((period, lookback, up_st, up_bt, dn_st, dn_bt))

# ═══════════════════════════════════════════
# 方案B: EMA排列过滤 + 基础斜率
# ═══════════════════════════════════════════
print('方案B: EMA排列过滤扫描')
print('思路: 上涨趋势需多头排列/交叉，下降需空头排列/交叉')
print('=' * 120)

b_configs = []
for period in [10, 12]:
    for lookback in [10, 11, 12]:
        # 基础斜率条件（比纯斜率版宽松，靠排列过滤把关）
        for up_st in [0.2, 0.3, 0.4, 0.5]:
            for up_bt in [2, 3, 4]:
                for dn_st in [0.2, 0.3, 0.4]:
                    for dn_bt in [2, 3]:
                        b_configs.append((period, lookback, up_st, up_bt, dn_st, dn_bt))

# ═══════════════════════════════════════════
# 方案C: 多因子综合评分
# ═══════════════════════════════════════════
print('方案C: 多因子综合评分')
print('思路: EMA斜率×0.4 + BIAS×0.3 + EMA排列×0.3 加权判断')
print('=' * 120)

def structure_multi(closes, period=10, lookback=11, up_th=0.55, dn_th=0.55, bt_th=4.0, use_arr=True):
    """多因子结构判定"""
    if len(closes) < 25: return '--'
    
    # 因子1: EMA斜率分 (-100~+100)
    ema = ema_list(closes, period)
    ema_r = [v for v in ema[-lookback:] if v is not None]
    if len(ema_r) < 5: return '--'
    slope = _reg_slope(ema_r)
    sp = slope / ema_r[0] * 100 if ema_r[0] else 0
    
    # 因子2: BIAS分 (-100~+100)
    bias = (closes[-1] - ema_r[-1]) / ema_r[-1] * 100 if ema_r[-1] else 0
    
    # 因子3: EMA排列分 (多头=+50, 交叉=0, 空头=-50)
    arr_score = 0
    if use_arr:
        arr = get_ema_arrangement(closes)
        if arr == '多头排列': arr_score = 50
        elif arr == '空头排列': arr_score = -50
    
    # 综合评分
    score = sp * 0.4 + bias * 0.3 + arr_score * 0.3
    
    if score > up_th: return '上涨趋势'
    elif score < -dn_th: return '下降趋势'
    else: return '区间震荡'

multi_configs = []
for period in [10, 12]:
    for lookback in [10, 11, 12, 13]:
        for up_th in [3, 4, 5, 6, 7]:
            for dn_th in [3, 4, 5, 6, 7]:
                for use_arr in [True, False]:
                    multi_configs.append((period, lookback, up_th, dn_th, use_arr))

# ── 运行所有扫描 ──
all_results = []

def score_config(label, period, lookback, up_st, dn_st, up_bt, dn_bt, mode='slope', use_arr=False, multi_up=5, multi_dn=5):
    up_r = []; down_r = []; range_r = []
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35: continue
            closes = [k['close'] for k in klines]
            for i in range(30, len(klines) - 5):
                wc = closes[:i+1]
                
                if mode == 'multi':
                    struct = structure_multi(wc, period, lookback, multi_up, multi_dn, use_arr=use_arr)
                else:
                    ema = ema_list(wc, period)
                    ema_r = [v for v in ema[-lookback:] if v is not None]
                    if len(ema_r) < 5:
                        struct = '区间震荡'
                    else:
                        slope = _reg_slope(ema_r)
                        sp = slope / ema_r[0] * 100 if ema_r[0] else 0
                        bias = (wc[-1] - ema_r[-1]) / ema_r[-1] * 100 if ema_r[-1] else 0
                        
                        if mode == 'slope_asymmetric':
                            if sp > up_st and bias > -up_bt:
                                struct = '上涨趋势'
                            elif sp < -dn_st and bias < dn_bt:
                                struct = '下降趋势'
                            else:
                                struct = '区间震荡'
                        elif mode == 'slope_arr':
                            up_cond = sp > up_st and bias > -up_bt
                            dn_cond = sp < -dn_st and bias < dn_bt
                            arr = get_ema_arrangement(wc)
                            if up_cond and arr in ('多头排列', '交叉'):
                                struct = '上涨趋势'
                            elif dn_cond and arr in ('空头排列', '交叉'):
                                struct = '下降趋势'
                            else:
                                struct = '区间震荡'
                        else:
                            if sp > up_st and bias > -up_bt: struct = '上涨趋势'
                            elif sp < -dn_st and bias < dn_bt: struct = '下降趋势'
                            else: struct = '区间震荡'
                
                fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                if struct == '上涨趋势': up_r.append(fwd)
                elif struct == '下降趋势': down_r.append(fwd)
                else: range_r.append(fwd)
    
    if len(up_r) < 20 or len(down_r) < 20:
        return None
    
    ua = sum(up_r)/len(up_r)
    da = sum(down_r)/len(down_r)
    ra = sum(range_r)/len(range_r) if range_r else 0
    
    return {
        'label': label, 'period': period, 'lookback': lookback,
        'up_st': up_st, 'up_bt': up_bt, 'dn_st': dn_st, 'dn_bt': dn_bt,
        'use_arr': use_arr, 'multi_up': multi_up, 'multi_dn': multi_dn,
        'mode': mode,
        'up': len(up_r), 'ua': ua,
        'down': len(down_r), 'da': da,
        'range': len(range_r), 'ra': ra,
        'disc': ua - da,
        'up_pct': len(up_r) / (len(up_r)+len(down_r)+len(range_r)) * 100,
        'down_pct': len(down_r) / (len(up_r)+len(down_r)+len(range_r)) * 100,
    }

# 跑A: 不对称阈值
import random
random.seed(42)
random.shuffle(asan_configs)
asan_configs = asan_configs[:600]

for idx, (period, lookback, up_st, up_bt, dn_st, dn_bt) in enumerate(asan_configs):
    if idx % 100 == 0:
        print(f'  方案A进度: {idx}/{len(asan_configs)}')
    r = score_config('A', period, lookback, up_st, dn_st, up_bt, dn_bt, mode='slope_asymmetric')
    if r: all_results.append(r)

# 跑B: EMA排列过滤
random.shuffle(b_configs)
b_configs = b_configs[:400]
for idx, (period, lookback, up_st, up_bt, dn_st, dn_bt) in enumerate(b_configs):
    if idx % 100 == 0:
        print(f'  方案B进度: {idx}/{len(b_configs)}')
    r = score_config('B', period, lookback, up_st, dn_st, up_bt, dn_bt, mode='slope_arr')
    if r: all_results.append(r)

# 跑C: 多因子评分
for idx, (period, lookback, multi_up, multi_dn, use_arr) in enumerate(multi_configs):
    r = score_config('C', period, lookback, 0, 0, 0, 0, mode='multi', use_arr=use_arr, multi_up=multi_up, multi_dn=multi_dn)
    if r: all_results.append(r)

# ── 汇总 ──
# 按区分度排
by_disc = sorted(all_results, key=lambda x: -x['disc'])
# 按下降收益排（最低最好）
by_down = sorted(all_results, key=lambda x: x['da'])
# 按上涨收益排（最高最好）
by_up = sorted(all_results, key=lambda x: -x['ua'])

print()
print('=' * 120)
print(f'总测试组合: {len(all_results)}')
print('=' * 120)

print()
print('─' * 120)
print('按区分度排序 TOP15')
print('─' * 120)
print(f'{"排名":>4} {"方案":>4} {"EMA":>4} {"窗口":>4} {"涨斜":>6} {"涨乖":>6} {"跌斜":>6} {"跌乖":>6} {"排滤":>6} {"涨次":>6} {"涨%":>5} {"涨均":>8} {"跌次":>6} {"跌%":>5} {"跌均":>8} {"震次":>6} {"区分":>8}')
print('-' * 120)
for i, r in enumerate(by_disc[:15]):
    pct_up = r['up'] / (r['up']+r['down']+r['range']) * 100
    pct_dn = r['down'] / (r['up']+r['down']+r['range']) * 100
    arr_f = '是' if r.get('use_arr') else '-'
    if r['mode'] == 'multi':
        extra = f' 多{r.get("multi_up",5)}/{r.get("multi_dn",5)}'
    else:
        extra = ''
    print(f'{i+1:>4} {r["mode"]:>4} {r["period"]:>4} {r["lookback"]:>4} {r["up_st"]:>5.2f} {r["up_bt"]:>4.1f} {r["dn_st"]:>5.2f} {r["dn_bt"]:>4.1f} {arr_f:>6} {r["up"]:>6} {pct_up:>4.1f}% {r["ua"]:+7.2f}% {r["down"]:>6} {pct_dn:>4.1f}% {r["da"]:+7.2f}% {r["range"]:>6} {r["disc"]:+7.2f}%{extra}')

print()
print('─' * 120)
print('按下降收益排序 TOP10（下降最亏钱→判跌最准）')
print('─' * 120)
print(f'{"方案":>4} {"EMA":>4} {"窗口":>4} {"涨斜":>6} {"涨乖":>6} {"跌斜":>6} {"跌乖":>6} {"涨次":>6} {"涨%":>5} {"涨均":>8} {"跌次":>6} {"跌%":>5} {"跌均":>8} {"区分":>8}')
print('-' * 100)
for r in by_down[:10]:
    pct_up = r['up'] / (r['up']+r['down']+r['range']) * 100
    pct_dn = r['down'] / (r['up']+r['down']+r['range']) * 100
    print(f'{r["mode"]:>4} {r["period"]:>4} {r["lookback"]:>4} {r["up_st"]:>5.2f} {r["up_bt"]:>4.1f} {r["dn_st"]:>5.2f} {r["dn_bt"]:>4.1f} {r["up"]:>6} {pct_up:>4.1f}% {r["ua"]:+7.2f}% {r["down"]:>6} {pct_dn:>4.1f}% {r["da"]:+7.2f}% {r["disc"]:+7.2f}%')

print()
print('─' * 120)
print('按上涨收益排序 TOP10（上涨最赚钱→判涨最准）')
print('─' * 120)
print(f'{"方案":>4} {"EMA":>4} {"窗口":>4} {"涨斜":>6} {"涨乖":>6} {"跌斜":>6} {"跌乖":>6} {"涨次":>6} {"涨%":>5} {"涨均":>8} {"跌次":>6} {"跌%":>5} {"跌均":>8} {"区分":>8}')
print('-' * 100)
for r in by_up[:10]:
    pct_up = r['up'] / (r['up']+r['down']+r['range']) * 100
    pct_dn = r['down'] / (r['up']+r['down']+r['range']) * 100
    print(f'{r["mode"]:>4} {r["period"]:>4} {r["lookback"]:>4} {r["up_st"]:>5.2f} {r["up_bt"]:>4.1f} {r["dn_st"]:>5.2f} {r["dn_bt"]:>4.1f} {r["up"]:>6} {pct_up:>4.1f}% {r["ua"]:+7.2f}% {r["down"]:>6} {pct_dn:>4.1f}% {r["da"]:+7.2f}% {r["disc"]:+7.2f}%')

# 最终推荐: 找上涨占比<65% + 下降收益<-0.5% + 上涨收益>+4.5% + 区分度最高
print()
print('─' * 120)
print('最优推荐（上涨<65% + 下降收益<-0.5% + 上涨>+4.5% + 区分度高）')
print('─' * 120)
candidates = [r for r in all_results if r['up_pct'] < 65 and r['da'] < -0.5 and r['ua'] > 4.5 and r['disc'] > 4.0]
candidates.sort(key=lambda x: -x['disc'])
for r in candidates[:5]:
    pct_up = r['up'] / (r['up']+r['down']+r['range']) * 100
    pct_dn = r['down'] / (r['up']+r['down']+r['range']) * 100
    print(f'  {r["mode"]:>4} EMA{r["period"]}/窗{r["lookback"]}/涨斜{r["up_st"]:.2f}/涨乖{r["up_bt"]:.0f}/跌斜{r["dn_st"]:.2f}/跌乖{r["dn_bt"]:.0f}: '
          f'涨{pct_up:.1f}%({r["up"]:>4}次 {r["ua"]:+7.2f}%) '
          f'跌{pct_dn:.1f}%({r["down"]:>4}次 {r["da"]:+7.2f}%) '
          f'区分{r["disc"]:+7.2f}%')
