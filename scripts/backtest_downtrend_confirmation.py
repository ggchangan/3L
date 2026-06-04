#!/usr/bin/env python3
"""下降趋势 — 短周期确认降级 回测

比较旧逻辑 vs 新逻辑在下降趋势判定上的效果。
旧：EMA12斜率<-0.2% + BIAS<3% → 下降趋势
新：同上 + EMA5斜率<0 + 收盘斜率<0 → 下降趋势；否则→区间震荡
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
DATA_DIR = os.environ['DATA_DIR']

from threel_core.ema_utils import ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def get_structure_old(closes):
    """旧逻辑：无条件下降趋势"""
    if len(closes) < 25:
        return '--'
    ema12 = ema_list(closes, 12)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    if len(e12_recent) < 5:
        return '--'
    slope = _reg_slope(e12_recent)
    slope_pct = slope / e12_recent[0] * 100 if e12_recent[0] else 0
    cur, cur_ema12 = closes[-1], e12_recent[-1]
    bias = (cur - cur_ema12) / cur_ema12 * 100 if cur_ema12 else 0

    # 上涨（与旧逻辑无关，但保持结构判定框架一致）
    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    bull_arrange = (e5[-1] and e10[-1] and e20[-1] and e5[-1] > e10[-1] > e20[-1])
    if slope_pct > 0.8 and bias > -5 and bull_arrange:
        ema5 = ema_list(closes, 5)
        e5_recent = [v for v in ema5[-5:] if v is not None]
        ema5_slope_pct = 0
        if len(e5_recent) >= 3:
            s5 = _reg_slope(e5_recent)
            ema5_slope_pct = s5 / e5_recent[0] * 100 if e5_recent[0] else 0
        close5 = closes[-5:]
        close_slope_pct = 0
        if len(close5) >= 5:
            sc = _reg_slope(close5)
            close_slope_pct = sc / close5[0] * 100 if close5[0] else 0
        if ema5_slope_pct > 0 and close_slope_pct > 0:
            return '上涨趋势'
        else:
            return '区间震荡'

    if slope_pct < -0.2 and bias < 3:
        return '下降趋势'
    return '区间震荡'

def get_structure_new(closes):
    """新逻辑：下降趋势需要短周期确认"""
    if len(closes) < 25:
        return '--'
    ema12 = ema_list(closes, 12)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    if len(e12_recent) < 5:
        return '--'
    slope = _reg_slope(e12_recent)
    slope_pct = slope / e12_recent[0] * 100 if e12_recent[0] else 0
    cur, cur_ema12 = closes[-1], e12_recent[-1]
    bias = (cur - cur_ema12) / cur_ema12 * 100 if cur_ema12 else 0

    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    bull_arrange = (e5[-1] and e10[-1] and e20[-1] and e5[-1] > e10[-1] > e20[-1])

    # EMA5斜率
    ema5 = ema_list(closes, 5)
    e5_recent = [v for v in ema5[-5:] if v is not None]
    ema5_slope_pct = 0
    if len(e5_recent) >= 3:
        s5 = _reg_slope(e5_recent)
        ema5_slope_pct = s5 / e5_recent[0] * 100 if e5_recent[0] else 0

    # 收盘价5日斜率
    close5 = closes[-5:]
    close_slope_pct = 0
    if len(close5) >= 5:
        sc = _reg_slope(close5)
        close_slope_pct = sc / close5[0] * 100 if close5[0] else 0

    # 上涨（同旧逻辑）
    if slope_pct > 0.8 and bias > -5 and bull_arrange:
        if ema5_slope_pct > 0 and close_slope_pct > 0:
            return '上涨趋势'
        else:
            return '区间震荡'

    # ★ 下降趋势 — 新逻辑
    if slope_pct < -0.2 and bias < 3:
        if ema5_slope_pct < 0 and close_slope_pct < 0:
            return '下降趋势'
        else:
            return '区间震荡'  # 短期已走平，降级

    return '区间震荡'


print('=' * 120)
print('下降趋势 — 短周期确认降级 回测')
print('比较旧逻辑 vs 新逻辑的下降趋势判定效果')
print('=' * 120)

# ── 收集数据 ──
# 每组存 [5日收益, 10日收益]
old_down_5d = []
new_down_5d = []
new_range_downgraded_5d = []  # 被新逻辑降级为区间震荡的
new_down_10d = []
old_down_10d = []
new_range_downgraded_10d = []

# 结构分布计数
old_structs = {'上涨趋势': 0, '下降趋势': 0, '区间震荡': 0, '--': 0}
new_structs = {'上涨趋势': 0, '下降趋势': 0, '区间震荡': 0, '--': 0}
downgrade_count = 0  # 新逻辑降级了多少个

total_stocks = 0
total_windows = 0

for sector, codes in stocks.items():
    for code, klines in codes.items():
        total_stocks += 1
        if len(klines) < 35:
            continue
        closes = [k['close'] for k in klines]
        for i in range(30, len(klines) - 10):
            wc = closes[:i+1]
            old_s = get_structure_old(wc)
            new_s = get_structure_new(wc)
            total_windows += 1

            old_structs[old_s] = old_structs.get(old_s, 0) + 1
            new_structs[new_s] = new_structs.get(new_s, 0) + 1

            fwd5 = (closes[i+5] - closes[i]) / closes[i] * 100
            fwd10 = (closes[i+10] - closes[i]) / closes[i] * 100

            # 旧逻辑：下降趋势
            if old_s == '下降趋势':
                old_down_5d.append(fwd5)
                old_down_10d.append(fwd10)

            # 新逻辑
            if new_s == '下降趋势':
                new_down_5d.append(fwd5)
                new_down_10d.append(fwd10)
            elif old_s == '下降趋势' and new_s == '区间震荡':
                # 被降级的（旧说下降，新说震荡）
                new_range_downgraded_5d.append(fwd5)
                new_range_downgraded_10d.append(fwd10)
                downgrade_count += 1

# ── 输出统计 ──
def stats(arr):
    if not arr:
        return 0, 0, 0, 0, 0
    n = len(arr)
    avg = sum(arr) / n
    pos = sum(1 for v in arr if v > 0) / n * 100
    neg = sum(1 for v in arr if v < 0) / n * 100
    winloss = pos / max(neg, 1)
    return n, avg, pos, neg, winloss

print()
print(f'总样本数: {total_stocks}只股票, {total_windows}个窗口')
print()

# 结构分布对比
print('结构分布对比（所有窗口）：')
print(f'  {"":>12} {"旧逻辑":>10} {"新逻辑":>10}')
for s in ['上涨趋势', '下降趋势', '区间震荡']:
    old_n = old_structs.get(s, 0)
    new_n = new_structs.get(s, 0)
    old_pct = old_n / total_windows * 100 if total_windows else 0
    new_pct = new_n / total_windows * 100 if total_windows else 0
    print(f'  {s:>12} {old_n:>8}({old_pct:>5.1f}%) {new_n:>8}({new_pct:>5.1f}%)')
print()

print(f'其中被降级的（旧→下降趋势，新→区间震荡）: {downgrade_count}次')
print()

# 5日收益对比
print('─' * 100)
print(f'{"":>30} {"样本量":>8} {"平均收益":>10} {"上涨率":>8} {"下跌率":>8} {"涨跌比":>8}')
print('─' * 100)

n, avg, pos, neg, wr = stats(old_down_5d)
print(f'{"旧逻辑-下降趋势(5日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

n, avg, pos, neg, wr = stats(new_down_5d)
print(f'{"新逻辑-下降趋势(5日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

n, avg, pos, neg, wr = stats(new_range_downgraded_5d)
print(f'{"新逻辑-被降级→震荡(5日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

print()

# 10日收益对比
n, avg, pos, neg, wr = stats(old_down_10d)
print(f'{"旧逻辑-下降趋势(10日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

n, avg, pos, neg, wr = stats(new_down_10d)
print(f'{"新逻辑-下降趋势(10日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

n, avg, pos, neg, wr = stats(new_range_downgraded_10d)
print(f'{"新逻辑-被降级→震荡(10日)":>30} {n:>8} {avg:+7.3f}% {pos:>7.1f}% {neg:>7.1f}% {wr:>7.2f}')

print()
print('─' * 100)

# 关键指标：被降级组 vs 原下降趋势的区分度
print()
print('★★★ 关键指标 ★★★')
print()
if old_down_5d and new_range_downgraded_5d:
    old_5d_avg = sum(old_down_5d) / len(old_down_5d)
    new_down_5d_avg = sum(new_down_5d) / len(new_down_5d) if new_down_5d else 0
    downgrade_5d_avg = sum(new_range_downgraded_5d) / len(new_range_downgraded_5d)
    
    print(f'旧逻辑"下降趋势"5日平均: {old_5d_avg:+6.3f}%')
    print(f'新逻辑"下降趋势"(确认)5日平均: {new_down_5d_avg:+6.3f}%')
    print(f'新逻辑"被降级→震荡"5日平均: {downgrade_5d_avg:+6.3f}%')
    print()
    diff = new_down_5d_avg - downgrade_5d_avg
    print(f'区分度(确认下跌 - 降级震荡): {diff:+6.3f}%  ← 正数越大说明区分越有效')
    print(f'降级组比旧逻辑"下降趋势"好: {downgrade_5d_avg - old_5d_avg:+6.3f}%')
    print()
    if old_down_10d and new_range_downgraded_10d:
        old_10d_avg = sum(old_down_10d) / len(old_down_10d)
        downgrade_10d_avg = sum(new_range_downgraded_10d) / len(new_range_downgraded_10d)
        new_down_10d_avg = sum(new_down_10d) / len(new_down_10d) if new_down_10d else 0
        print(f'10日: 旧下降={old_10d_avg:+6.3f}%  新下降(确认)={new_down_10d_avg:+6.3f}%  降级震荡={downgrade_10d_avg:+6.3f}%')

# ── 结论评级 ──
print()
print('─' * 100)
print('结论判定：')
if old_down_5d and new_range_downgraded_5d:
    old_avg = sum(old_down_5d) / len(old_down_5d)
    downgrade_avg = sum(new_range_downgraded_5d) / len(new_range_downgraded_5d)
    new_down_avg = sum(new_down_5d) / len(new_down_5d) if new_down_5d else 0
    
    # 评估标准
    criteria_pass = 0
    criteria_total = 3
    
    # C1: 新下降趋势的平均收益 < 旧下降趋势（确认的更熊）
    if new_down_avg < old_avg:
        print(f'  ✅ C1 新下降趋势更负: {new_down_avg:+6.3f}% < {old_avg:+6.3f}%')
        criteria_pass += 1
    else:
        print(f'  ❌ C1 新下降趋势不够负: {new_down_avg:+6.3f}% >= {old_avg:+6.3f}%')
    
    # C2: 降级组的平均收益 > 旧下降趋势（降级正确，不跌了）
    if downgrade_avg > old_avg:
        print(f'  ✅ C2 降级组走势更好: {downgrade_avg:+6.3f}% > {old_avg:+6.3f}%')
        criteria_pass += 1
    else:
        print(f'  ❌ C2 降级组走势仍差: {downgrade_avg:+6.3f}% <= {old_avg:+6.3f}%')
    
    # C3: 区分度显著（>1%）
    diff = new_down_avg - downgrade_avg
    if diff > 1:
        print(f'  ✅ C3 区分度显著: {diff:+6.3f}% > 1%')
        criteria_pass += 1
    else:
        print(f'  ❌ C3 区分度不足: {diff:+6.3f}% <= 1%')
    
    print()
    if criteria_pass >= 2:
        print(f'★ 回测结果: 通过 ({criteria_pass}/{criteria_total}) — 新逻辑有效')
    else:
        print(f'★ 回测结果: 不通过 ({criteria_pass}/{criteria_total}) — 需要调整')
else:
    print('★ 样本不足，无法判定')
