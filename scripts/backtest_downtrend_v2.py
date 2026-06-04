#!/usr/bin/env python3
"""下降趋势 — 短周期确认降级 v2 回测

尝试多种短期确认条件，找最佳方案。
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['DATA_DIR'] = '/home/ubuntu/data/3l'
DATA_DIR = os.environ['DATA_DIR']

from threel_core.ema_utils import ema_list, _reg_slope

with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
    data = json.load(f)
stocks = data.get('stocks', data)

def get_structure_base(closes):
    """基础版：旧逻辑（无降级）"""
    if len(closes) < 25:
        return '--', None
    ema12 = ema_list(closes, 12)
    e12_recent = [v for v in ema12[-12:] if v is not None]
    if len(e12_recent) < 5:
        return '--', None
    slope = _reg_slope(e12_recent)
    slope_pct = slope / e12_recent[0] * 100 if e12_recent[0] else 0
    cur, cur_ema12 = closes[-1], e12_recent[-1]
    bias = (cur - cur_ema12) / cur_ema12 * 100 if cur_ema12 else 0

    e5 = ema_list(closes, 5)
    e10 = ema_list(closes, 10)
    e20 = ema_list(closes, 20)
    bull_arrange = (e5[-1] and e10[-1] and e20[-1] and e5[-1] > e10[-1] > e20[-1])
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
    bear_arrange = (e5[-1] and e10[-1] and e5[-1] < e10[-1])

    if slope_pct > 0.8 and bias > -5 and bull_arrange:
        if ema5_slope_pct > 0 and close_slope_pct > 0:
            return '上涨趋势', None
        else:
            return '区间震荡', None

    extras = {
        'slope_pct': slope_pct, 'bias': bias,
        'ema5_slope_pct': ema5_slope_pct,
        'close_slope_pct': close_slope_pct,
        'bear_arrange': bear_arrange,
    }
    if slope_pct < -0.2 and bias < 3:
        return '下降趋势', extras
    return '区间震荡', extras


def get_structure_v2_newlow(closes):
    """v2: 创新低确认 — 近3日最低 < 之前5日最低"""
    s, extras = get_structure_base(closes)
    if s != '下降趋势':
        return s, extras
    if extras is None:
        return s, extras
    
    # 检查是否还在创新低
    recent_3_low = min(closes[-3:])
    prev_5_low = min(closes[-8:-3]) if len(closes) >= 8 else min(closes[:-3])
    
    if recent_3_low <= prev_5_low * 0.995:  # 近3日最低比之前5日最低低0.5%以上
        return '下降趋势', extras  # 还在创新低，维持下降
    else:
        return '区间震荡', extras  # 不再创新低，降级


def get_structure_v2_newlow_pct(pct=0.5):
    """v2变体: 带百分比的创新低"""
    def f(closes):
        s, extras = get_structure_base(closes)
        if s != '下降趋势':
            return s, extras
        if extras is None:
            return s, extras
        recent_3_low = min(closes[-3:])
        prev_5_low = min(closes[-8:-3]) if len(closes) >= 8 else min(closes[:-3])
        if recent_3_low <= prev_5_low * (1 - pct/100):
            return '下降趋势', extras
        else:
            return '区间震荡', extras
    return f


def get_structure_v2_recentfall(closes):
    """v3: 近3日涨幅为负"""
    s, extras = get_structure_base(closes)
    if s != '下降趋势':
        return s, extras
    if extras is None:
        return s, extras
    
    # 近3日涨幅
    recent_3d_gain = (closes[-1] - closes[-4]) / closes[-4] * 100 if len(closes) >= 4 else 0
    
    if recent_3d_gain < -1:  # 近3日还在跌至少1%
        return '下降趋势', extras
    else:
        return '区间震荡', extras


def get_structure_v2_beararrange(closes):
    """v4: 空头排列确认"""
    s, extras = get_structure_base(closes)
    if s != '下降趋势':
        return s, extras
    if extras is None:
        return s, extras
    
    if extras['bear_arrange'] and extras['ema5_slope_pct'] < 0:
        return '下降趋势', extras
    else:
        return '区间震荡', extras


def get_structure_v2_bias5(closes):
    """v5: BIAS5 < -2（处于负乖离区）+ 继续下跌"""
    s, extras = get_structure_base(closes)
    if s != '下降趋势':
        return s, extras
    if extras is None:
        return s, extras
    
    e5 = ema_list(closes, 5)
    bias5 = (closes[-1] - e5[-1]) / e5[-1] * 100 if e5[-1] else 0
    
    # 如果bias5非常负（超卖），说明短期跌太猛可能反弹，降级
    # 如果bias5为正或接近0但还在跌，保持
    if bias5 < -3 and extras['close_slope_pct'] < 0:
        # 超卖+还在跌 → 保持
        return '下降趋势', extras
    elif bias5 > -1:
        # 即使长期斜率向下，短期已经回到均线附近 → 降级
        return '区间震荡', extras
    else:
        # 中间区域 -3 <= bias5 <= -1 → 也可保持但力度弱
        return '下降趋势', extras


# ── 回测比较 ──
def run_backtest(name, struct_fn):
    old_dn_5d = []  # 旧逻辑的下降趋势
    new_dn_5d = []  # 新逻辑保持下降趋势
    new_rg_5d = []  # 新逻辑降级为震荡
    
    old_dn_10d = []
    new_dn_10d_10 = []
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
                        new_dn_10d_10.append(fwd10)
                    else:
                        new_rg_5d.append(fwd5)
                        new_rg_10d.append(fwd10)
                        downgrade_count += 1
    
    def stats(arr):
        if not arr:
            return 0, 0, 0, 0
        n = len(arr)
        avg = sum(arr) / n
        pos = sum(1 for v in arr if v > 0) / n * 100
        neg = sum(1 for v in arr if v < 0) / n * 100
        return n, avg, pos, neg
    
    n_old, avg_old, pos_old, neg_old = stats(old_dn_5d)
    n_new, avg_new, pos_new, neg_new = stats(new_dn_5d)
    n_rg, avg_rg, pos_rg, neg_rg = stats(new_rg_5d)
    n_old10, avg_old10, _, _ = stats(old_dn_10d)
    n_new10, avg_new10, _, _ = stats(new_dn_10d_10)
    n_rg10, avg_rg10, _, _ = stats(new_rg_10d)
    
    return {
        'name': name,
        'downgrade_pct': downgrade_count / max(total_old_down, 1) * 100,
        'downgrade_n': downgrade_count,
        'total_old': total_old_down,
        'old_5d': avg_old, 'new_5d': avg_new, 'rg_5d': avg_rg,
        'old_10d': avg_old10, 'new_10d': avg_new10, 'rg_10d': avg_rg10,
        'old_pos_pct': pos_old, 'new_pos_pct': pos_new, 'rg_pos_pct': pos_rg,
        'n_old': n_old, 'n_new': n_new, 'n_rg': n_rg,
    }


variants = [
    ('基准(旧逻辑)', get_structure_base),
    ('v2 创新低', get_structure_v2_newlow),
    ('v3 近3日跌>1%', get_structure_v2_recentfall),
    ('v4 空头排列', get_structure_v2_beararrange),
    ('v5 bias5区域', get_structure_v2_bias5),
]

print('=' * 120)
print('下降趋势短周期确认 — 多方案对比回测')
print('=' * 120)
print()

results = []
for name, fn in variants:
    r = run_backtest(name, fn)
    results.append(r)

# 表格输出
header = f'{"方案":>20} {"降级率":>8} {"旧↓5日":>10} {"新↓5日":>10} {"降级→震荡5日":>14} {"区分度":>10} {"旧涨率":>8} {"降级涨率":>10}'
print(header)
print('─' * len(header))
for r in results:
    if r['name'] == '基准(旧逻辑)':
        diff = 0
    else:
        diff = r['new_5d'] - r['rg_5d']
    print(f'{r["name"]:>20} {r["downgrade_pct"]:>7.1f}% {r["old_5d"]:+8.3f}% {r["new_5d"]:+8.3f}% {r["rg_5d"]:+11.3f}% {diff:+8.3f}% {r["old_pos_pct"]:>7.1f}% {r["rg_pos_pct"]:>8.1f}%')

print()
print('─' * len(header))

# 详细输出每个方案的5日
for r in results:
    print()
    print(f'── {r["name"]} ──')
    print(f'  旧↓趋势样本: {r["n_old"]} | 降级: {r["downgrade_n"]}({r["downgrade_pct"]:.1f}%)')
    print(f'  5日 旧↓={r["old_5d"]:+6.3f}%  新↓={r["new_5d"]:+6.3f}%  降级→震荡={r["rg_5d"]:+6.3f}%')
    print(f'  10日 旧↓={r["old_10d"]:+6.3f}%  新↓={r["new_10d"]:+6.3f}%  降级→震荡={r["rg_10d"]:+6.3f}%')
    
    if r['name'] != '基准(旧逻辑)':
        # 评估
        ok = []
        if r['new_5d'] < r['old_5d']:
            ok.append(f'C1(新↓更负) ✅ {r["new_5d"]:+6.3f}% < {r["old_5d"]:+6.3f}%')
        else:
            ok.append(f'C1(新↓更负) ❌ {r["new_5d"]:+6.3f}% >= {r["old_5d"]:+6.3f}%')
        
        if r['rg_5d'] > r['old_5d']:
            ok.append(f'C2(降级更好) ✅ {r["rg_5d"]:+6.3f}% > {r["old_5d"]:+6.3f}%')
        else:
            ok.append(f'C2(降级更好) ❌ {r["rg_5d"]:+6.3f}% <= {r["old_5d"]:+6.3f}%')
        
        diff = r['new_5d'] - r['rg_5d']
        if diff > 1:
            ok.append(f'C3(区分度>1%) ✅ {diff:+6.3f}%')
        else:
            ok.append(f'C3(区分度>1%) ❌ {diff:+6.3f}%')
        
        # 额外：降级组涨率 vs 下跌率
        if r['rg_pos_pct'] < 40:
            ok.append(f'C4(降级组涨率<40%) ✅ {r["rg_pos_pct"]:.1f}%')
        else:
            ok.append(f'C4(降级组涨率<40%) ❌ {r["rg_pos_pct"]:.1f}%')
        
        for line in ok:
            print(f'  {line}')
        
        # 综合评分
        score = sum(1 for l in ok if '✅' in l)
        print(f'  得分: {score}/{len(ok)}')
