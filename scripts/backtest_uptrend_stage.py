#!/usr/bin/env python3
"""
上涨趋势阶段判定优化 — 测试上行/加速/滞涨/缩量整理/转弱的最佳参数

回测思路：
  对判为 上涨趋势 的窗口：
    → 检查各阶段判定参数
    → 后续N天涨跌幅
    → 上行应该涨、加速应该冲高回落、滞涨/转弱应该跌

参数优化：
  1. s1/s2 斜率比阈值 (当前: 加速>1.8, 滞涨<0.4)
  2. 缩量整理量比阈值 (当前: <0.8)
"""
import json, os, sys, time, math
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']

from threel_core.ema_utils import ema_list, _reg_slope, get_structure

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

# ════════════════════════════════════════════════════════════════
# 阶段判定（可调参版）
# ════════════════════════════════════════════════════════════════

def get_stage_custom(closes, volumes, accel_ratio=1.8, stag_ratio=0.4, vol_shrink=0.8):
    """可调参的上涨趋势阶段判定"""
    if len(closes) < 15:
        return '--'
    e10 = ema_list(closes, 10)
    e10_last = [v for v in e10[-15:] if v is not None]
    if len(e10_last) < 10:
        return '--'
    s1 = _reg_slope(e10_last)
    s2 = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
    
    if s1 > 0 and s2 > 0:
        ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
        # C方案：V反修正
        if ratio > accel_ratio and len(closes) >= 6:
            check = closes[-6:]
            for ci in range(1, len(check)):
                if (check[ci] - check[ci-1]) / check[ci-1] < -0.03:
                    n_after = len(check) - ci
                    start = max(1, len(e10_last) - n_after + 1)
                    if start < len(e10_last) - 2:
                        s1_adj = _reg_slope(e10_last[start:])
                        if s1_adj > 0:
                            ratio = s2 / s1_adj
                    break
        # D方案：整理后突破
        if ratio > accel_ratio and len(closes) >= 23:
            w = closes[-23:-3]
            if len(w) >= 10:
                for i in range(len(w)-1, len(w)-8, -1):
                    if w[i] > w[i-1]:
                        tv = w[i-1]; pv = max(w[:i-1])
                        pull = (pv - tv) / pv * 100
                        if pull > 5:
                            e20 = ema_list(closes, 20)
                            tai = len(closes) - 23 + i - 1
                            if tai < len(e20) and e20[tai] is not None and tv > e20[tai] * 0.98:
                                ratio = 1.0
                        break
        
        if ratio > accel_ratio:
            return '加速'
        elif ratio < stag_ratio:
            if volumes and len(volumes) >= 13 and closes[-1] > e10_last[-1]:
                v3 = sum(volumes[-3:]) / 3
                v10 = sum(volumes[-13:-3]) / 10
                if v10 > 0 and v3 / v10 < vol_shrink:
                    return '缩量整理'
            return '滞涨'
        else:
            return '上行'
    elif s1 > 0 and s2 < 0:
        return '转弱'
    return '--'


def backtest_stage_params(stocks, accel_ratio=1.8, stag_ratio=0.4, vol_shrink=0.8, forward=5):
    """回测阶段判定参数"""
    stats = {
        '上行': {'count': 0, 'fwd_return': [], 'max_fwd_return': []},
        '加速': {'count': 0, 'fwd_return': [], 'max_fwd_return': []},
        '滞涨': {'count': 0, 'fwd_return': [], 'max_fwd_return': []},
        '缩量整理': {'count': 0, 'fwd_return': [], 'max_fwd_return': []},
        '转弱': {'count': 0, 'fwd_return': [], 'max_fwd_return': []},
    }
    
    for code, name, klines in stocks:
        if len(klines) < 40:
            continue
        closes = [k['close'] for k in klines]
        volumes = [k['volume'] for k in klines]
        
        for i in range(25, len(klines) - forward):
            window_c = closes[:i+1]
            window_v = volumes[:i+1]
            struct = get_structure(window_c)
            if struct != '上涨趋势':
                continue
            
            stage = get_stage_custom(window_c, window_v, accel_ratio, stag_ratio, vol_shrink)
            if stage not in stats:
                continue
            
            stats[stage]['count'] += 1
            fwd_ret = (closes[i+forward] - closes[i]) / closes[i] * 100
            stats[stage]['fwd_return'].append(fwd_ret)
            max_ret = max(0, max(k['high'] for k in klines[i+1:i+forward+1]) - closes[i]) / closes[i] * 100
            stats[stage]['max_fwd_return'].append(max_ret)
    
    return stats


def print_stats(stats, label):
    print(f'\n── {label} ──')
    total = sum(s['count'] for s in stats.values())
    for stage, s in sorted(stats.items(), key=lambda x: -x[1]['count']):
        if s['count'] == 0:
            continue
        avg = sum(s['fwd_return']) / s['count']
        win = sum(1 for r in s['fwd_return'] if r > 0) / s['count'] * 100
        avg_max = sum(s['max_fwd_return']) / s['count']
        pct = s['count'] / total * 100
        print(f'  {stage}: {s["count"]}次({pct:.1f}%) 胜率{win:.1f}% 均收益{avg:+.2f}% 最大浮盈{avg_max:.2f}%')


print('加载数据...')
stocks = load_stocks()
print(f'共 {len(stocks)} 只股票')

# ── 基准参数 ──
print(f'\n{"="*70}')
print(f'上涨趋势阶段判定 — 参数扫描')
print(f'{"="*70}')

# 扫描加速阈值
print(f'\n--- 加速阈值 (stag_ratio=0.4, vol_shrink=0.8) ---')
for ar in [1.5, 1.8, 2.0, 2.5]:
    stats = backtest_stage_params(stocks, accel_ratio=ar)
    print_stats(stats, f'accel>{ar}')

# 扫描滞涨阈值
print(f'\n--- 滞涨阈值 (accel_ratio=1.8, vol_shrink=0.8) ---')
for sr in [0.3, 0.4, 0.5]:
    stats = backtest_stage_params(stocks, stag_ratio=sr)
    print_stats(stats, f'stag<{sr}')

# 扫描缩量阈值
print(f'\n--- 缩量阈值 (accel_ratio=1.8, stag_ratio=0.4) ---')
for vs in [0.7, 0.8, 0.9]:
    stats = backtest_stage_params(stocks, vol_shrink=vs)
    print_stats(stats, f'vol_shrink<{vs}')

# ── 最优组合 ──
print(f'\n{"="*70}')
print(f'最优组合 vs 当前组合')
print(f'{"="*70}')

# 当前: accel=1.8, stag=0.4, vol=0.8
current = backtest_stage_params(stocks, accel_ratio=1.8, stag_ratio=0.4, vol_shrink=0.8)
print_stats(current, '当前 (1.8/0.4/0.8)')

# 推荐: 
for ar, sr, vs in [(1.8, 0.3, 0.8), (2.0, 0.3, 0.8), (1.5, 0.4, 0.9)]:
    stats = backtest_stage_params(stocks, accel_ratio=ar, stag_ratio=sr, vol_shrink=vs)
    print_stats(stats, f'推荐 ({ar}/{sr}/{vs})')
