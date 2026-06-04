#!/usr/bin/env python3
"""下降趋势短周期确认 — v2-5 多方案对比

关键发现：旧逻辑的下降趋势5日平均+2.2%，说明它本身就不是一个「会继续跌」的标签。
这次的重点：判断「当前是否已经止跌」→ 降级为区间震荡。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
DATA_DIR = os.environ['DATA_DIR']

from threel_core.ema_utils import ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def get_extras(closes):
    """计算所有辅助指标"""
    if len(closes) < 25:
        return None
    ema12 = ema_list(closes, 12)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    if len(e12_recent) < 5:
        return None
    slope = _reg_slope(e12_recent)
    slope_pct = slope / e12_recent[0] * 100 if e12_recent[0] else 0
    cur, cur_ema12 = closes[-1], e12_recent[-1]
    bias = (cur - cur_ema12) / cur_ema12 * 100 if cur_ema12 else 0
    
    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    bull_arrange = (e5[-1] and e10[-1] and e20[-1] and e5[-1] > e10[-1] > e20[-1])
    bear_arrange = (e5[-1] and e10[-1] and e5[-1] < e10[-1])
    
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
    
    # 近2日涨幅
    recent_2d_change = (closes[-1] - closes[-3]) / closes[-3] * 100 if len(closes) >= 3 else 0
    # 近3日涨幅
    recent_3d_change = (closes[-1] - closes[-4]) / closes[-4] * 100 if len(closes) >= 4 else 0
    
    # 创新低检查
    recent_3_low = min(closes[-3:])
    prev_5_low = min(closes[-8:-3]) if len(closes) >= 8 else min(closes[:-3])
    making_new_low = recent_3_low <= prev_5_low * 0.995
    
    # 最近3天涨跌日数
    gains_l3 = []
    for j in range(max(0, len(closes)-4), len(closes)):
        if j > 0:
            gains_l3.append(closes[j] - closes[j-1])
    up_days_3 = sum(1 for g in gains_l3 if g > 0)
    down_days_3 = sum(1 for g in gains_l3 if g < 0)
    
    # BIAS5
    bias5 = (closes[-1] - e5[-1]) / e5[-1] * 100 if e5[-1] else 0
    
    return {
        'slope_pct': slope_pct, 'bias': bias,
        'ema5_slope_pct': ema5_slope_pct, 'close_slope_pct': close_slope_pct,
        'bear_arrange': bear_arrange, 'bull_arrange': bull_arrange,
        'recent_2d_change': recent_2d_change, 'recent_3d_change': recent_3d_change,
        'making_new_low': making_new_low,
        'bias5': bias5,
        'up_days_3': up_days_3, 'down_days_3': down_days_3,
    }

def get_structure_base(closes):
    """旧逻辑"""
    ex = get_extras(closes)
    if ex is None:
        return '--', None
    s = ex['slope_pct']
    b = ex['bias']
    ba = ex['bull_arrange']
    
    if s > 0.8 and b > -5 and ba:
        if ex['ema5_slope_pct'] > 0 and ex['close_slope_pct'] > 0:
            return '上涨趋势', ex
        else:
            return '区间震荡', ex
    if s < -0.2 and b < 3:
        return '下降趋势', ex
    return '区间震荡', ex


# 各种方案
def v2_newlow(closes):
    """v2: 创新低确认"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['making_new_low']:
        return '下降趋势', ex
    return '区间震荡', ex

def v3_recent2d(closes):
    """v3: 近2日涨幅<0（还在跌）"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['recent_2d_change'] < 0:
        return '下降趋势', ex
    return '区间震荡', ex

def v4_recent2d_neg1(closes):
    """v4: 近2日跌幅>1%（还在明显跌）"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['recent_2d_change'] < -1:
        return '下降趋势', ex
    return '区间震荡', ex

def v5_3down2(closes):
    """v5: 最近3天至少2天收阴"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['down_days_3'] >= 2:
        return '下降趋势', ex
    return '区间震荡', ex

def v6_bias5neg(closes):
    """v6: BIAS5<0（价格在短期均线下方）"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['bias5'] < -1:
        return '下降趋势', ex
    return '区间震荡', ex

def v7_newlow_3d(closes):
    """v7: 近3日最低创新低（排除隔日数据）"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    # 只检查最近2天是否创新低（排除3天前的大跌干扰）
    recent_2_low = min(closes[-2:])
    prev_5_low = min(closes[-7:-2]) if len(closes) >= 7 else min(closes[:-2])
    if recent_2_low <= prev_5_low * 0.995:
        return '下降趋势', ex
    return '区间震荡', ex

def v8_bear_and_falling(closes):
    """v8: 空头排列+阴线多"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['bear_arrange'] and ex['down_days_3'] >= 2:
        return '下降趋势', ex
    return '区间震荡', ex

def v9_falling_5d(closes):
    """v9: 5日涨幅为负"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['close_slope_pct'] < -0.5:
        return '下降趋势', ex
    return '区间震荡', ex

def v10_3d_falling(closes):
    """v10: 3日涨幅为负且阴线多"""
    s, ex = get_structure_base(closes)
    if s != '下降趋势' or ex is None:
        return s, ex
    if ex['recent_3d_change'] < -2 and ex['down_days_3'] >= 2:
        return '下降趋势', ex
    return '区间震荡', ex


# ── 回测 ──
def run_backtest(name, struct_fn):
    old_dn_5d = []
    new_dn_5d = []
    new_rg_5d = []
    old_dn_10d = []
    new_dn_10d = []
    new_rg_10d = []
    downgrade_count = 0
    total_old_down = 0
    
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            if len(klines) < 35:
                continue
            closes = [k['close'] for k in klines]
            for i in range(30, len(klines) - 10):
                wc = closes[:i+1]
                old_s, _ = get_structure_base(wc)
                new_s, _ = struct_fn(wc)
                fwd5 = (closes[i+5] - closes[i]) / closes[i] * 100
                fwd10 = (closes[i+10] - closes[i]) / closes[i] * 100
                if old_s == '下降趋势':
                    total_old_down += 1
                    old_dn_5d.append(fwd5)
                    old_dn_10d.append(fwd10)
                    if new_s == '下降趋势':
                        new_dn_5d.append(fwd5)
                        new_dn_10d.append(fwd10)
                    else:
                        new_rg_5d.append(fwd5)
                        new_rg_10d.append(fwd10)
                        downgrade_count += 1
    
    def stats(arr):
        if not arr:
            return 0, 0, 0, 0, 0, 0
        n = len(arr)
        avg = sum(arr) / n
        pos = sum(1 for v in arr if v > 0) / n * 100
        neg = sum(1 for v in arr if v < 0) / n * 100
        med = sorted(arr)[n//2]
        # 大幅下跌率（跌超3%）
        big_loss = sum(1 for v in arr if v < -3) / n * 100
        return n, avg, pos, neg, med, big_loss
    
    n_old, avg_old, pos_old, neg_old, med_old, big_old = stats(old_dn_5d)
    n_new, avg_new, pos_new, neg_new, med_new, big_new = stats(new_dn_5d)
    n_rg, avg_rg, pos_rg, neg_rg, med_rg, big_rg = stats(new_rg_5d)
    
    return {
        'name': name,
        'downgrade_pct': downgrade_count / max(total_old_down, 1) * 100,
        'downgrade_n': downgrade_count, 'total_old': total_old_down,
        'old_5d': avg_old, 'new_5d': avg_new, 'rg_5d': avg_rg,
        'old_med': med_old, 'new_med': med_new, 'rg_med': med_rg,
        'old_pos': pos_old, 'new_pos': pos_new, 'rg_pos': pos_rg,
        'old_big': big_old, 'new_big': big_new, 'rg_big': big_rg,
        'n_old': n_old, 'n_new': n_new, 'n_rg': n_rg,
        'old_10d': sum(old_dn_10d)/len(old_dn_10d) if old_dn_10d else 0,
        'new_10d': sum(new_dn_10d)/len(new_dn_10d) if new_dn_10d else 0,
        'rg_10d': sum(new_rg_10d)/len(new_rg_10d) if new_rg_10d else 0,
        'old_10d_n': len(old_dn_10d),
        'new_10d_n': len(new_dn_10d),
        'rg_10d_n': len(new_rg_10d),
    }


variants = [
    ('基准(旧逻辑)', get_structure_base),
    ('v2 创新低', v2_newlow),
    ('v3 近2日涨幅<0', v3_recent2d),
    ('v4 近2日跌>1%', v4_recent2d_neg1),
    ('v5 3天至少2阴', v5_3down2),
    ('v6 BIAS5<0', v6_bias5neg),
    ('v7 近2日创新低', v7_newlow_3d),
    ('v8 空头+多阴', v8_bear_and_falling),
    ('v9 5日涨幅为负', v9_falling_5d),
    ('v10 3日跌>2%+多阴', v10_3d_falling),
]

print('=' * 140)
print('下降趋势短周期确认 — v2~v10 对比回测')
print('=' * 140)
print()

results = []
for name, fn in variants:
    r = run_backtest(name, fn)
    results.append(r)

# 表格
header = (f'{"方案":>18} {"降级率":>7} {"旧↓5日":>9} {"新↓5日":>9} '
          f'{"降级→震荡":>12} {"旧中位":>8} {"降级中位":>10} '
          f'{"旧涨率":>7} {"降级涨率":>9} {"旧大跌率":>8} {"降级大跌率":>10}')
print(header)
print('─' * len(header))
for r in results:
    d = r['new_5d'] - r['rg_5d'] if r['name'] != '基准(旧逻辑)' else 0
    print(f'{r["name"]:>18} {r["downgrade_pct"]:>6.1f}% '
          f'{r["old_5d"]:+7.3f}% {r["new_5d"]:+7.3f}% '
          f'{r["rg_5d"]:+9.3f}% {r["old_med"]:+7.3f}% {r["rg_med"]:+8.3f}% '
          f'{r["old_pos"]:>6.1f}% {r["rg_pos"]:>7.1f}% '
          f'{r["old_big"]:>6.1f}% {r["rg_big"]:>7.1f}%')

print()
print('─' * len(header))

# 每方案详细
print()
print('评估准则（从描述性角度）：')
print('  S1: 降级组5日收益接近0（震荡特征） → 合理')
print('  S2: 降级组中位收益接近0')
print('  S3: 区分度新↓ - 降级→震荡 > 旧↓ - 0 (比纯旧逻辑好)')
print()

for r in results:
    if r['name'] == '基准(旧逻辑)':
        continue
    print(f'── {r["name"]} ──')
    print(f'  降级率 {r["downgrade_pct"]:.1f}% ({r["downgrade_n"]}/{r["total_old"]})')
    print(f'  5日: 旧↓={r["old_5d"]:+6.3f}% 新↓={r["new_5d"]:+6.3f}% 降级→震荡={r["rg_5d"]:+6.3f}%')
    print(f'  中位: 旧↓={r["old_med"]:+6.3f}% 降级={r["rg_med"]:+6.3f}%')
    
    # 关键指标：降级组是否接近0
    if abs(r['rg_5d']) < 2:
        print(f'  降级组合格 ✅ 均值={r["rg_5d"]:+6.3f}% < 2%（接近0，符合震荡描述）')
    else:
        print(f'  降级组不合格 ❌ 均值={r["rg_5d"]:+6.3f}% > 2%（偏差太大）')
    
    if abs(r['rg_med']) < 1.5:
        print(f'  降级中位合格 ✅ 中位={r["rg_med"]:+6.3f}% < 1.5%')
    else:
        print(f'  降级中位不合格 ❌ 中位={r["rg_med"]:+6.3f}% > 1.5%')
    
    print()
