#!/usr/bin/env python3
"""
区间震荡支撑/压力线回测 — 找出哪种方法画的支撑/压力最准

待测方法：
  A. 前低/前高关键点 — 最近一段前低做支撑，最近一段前高做压力
  B. 统计边界 — N天最低点做支撑，N天最高点做压力
  C. 突破点（现有逻辑）— 突破过的前压力做支撑，15日最高做压力
  D. 混合 — 有突破用突破，无突破用前低/前高

回测逻辑：
  滚动窗口 → 判断结构→ 区间震荡 → 用各方法画支撑S/压力R
  → 后续N天：碰S反弹？碰R回落？还是突破S/R？
  → 统计胜率

运行：
  python3 scripts/backtest_support_resistance.py [--method all] [--window 20]
"""
import json, os, sys, time, math
from collections import defaultdict, Counter
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

DATA_DIR = os.environ['DATA_DIR']

# ════════════════════════════════════════════════════════════════
# 数据加载
# ════════════════════════════════════════════════════════════════

def load_stocks():
    """返回 [(code, name, klines), ...]，按股票平铺"""
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
# 结构判定（简化版 — 用EMA20斜率+BIAS振幅）
# ════════════════════════════════════════════════════════════════

def ema_list(values, period):
    """计算EMA"""
    result = []
    multiplier = 2 / (period + 1)
    for i, v in enumerate(values):
        if i == 0:
            result.append(v)
        else:
            result.append((v - result[-1]) * multiplier + result[-1])
    return result


def judge_structure(closes, window=20):
    """简化版结构判定，返回 '上涨趋势'/'区间震荡'/'下降趋势'"""
    if len(closes) < window + 5:
        return '区间震荡'
    
    ema20 = ema_list(closes, 20)
    e20_recent = ema20[-(window//2):]
    
    # EMA20斜率
    slope = (e20_recent[-1] - e20_recent[0]) / e20_recent[0] * 100
    
    # 当前价格相对EMA20的偏离
    cur = closes[-1]
    cur_ema20 = ema20[-1]
    bias20 = (cur - cur_ema20) / cur_ema20 * 100
    
    # 近期振幅
    recent = closes[-window:]
    amplitude = (max(recent) - min(recent)) / min(recent) * 100
    
    if slope > 0.3 and bias20 > -2:
        return '上涨趋势'
    elif slope < -0.3 and bias20 < 2:
        return '下降趋势'
    else:
        return '区间震荡'


# ════════════════════════════════════════════════════════════════
# 关键点识别
# ════════════════════════════════════════════════════════════════

def find_keypoints(klines, window=20):
    """找前高/前低/突破关键点
    返回 [{idx, label, y, type}, ...]
    label: '前高'/'前低'/'突'
    """
    n = len(klines)
    if n < window:
        return []
    
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    closes = [k['close'] for k in klines]
    opens_p = [k['open'] for k in klines]
    
    kps = []
    half = window // 2
    
    # 前高/前低（局部极值）
    for i in range(half, n - half):
        win_high = highs[i-half:i+half+1]
        win_low = lows[i-half:i+half+1]
        if highs[i] == max(win_high) and highs[i] != min(win_high):
            kps.append({'idx': i, 'label': '前高', 'y': highs[i], 'type': 1})
        if lows[i] == min(win_low) and lows[i] != max(win_low):
            kps.append({'idx': i, 'label': '前低', 'y': lows[i], 'type': -1})
    
    # 突破点：价格突破前N天最高，且收阳放量
    lookback = 15
    for i in range(lookback, n):
        prev_highs = highs[i-lookback:i]
        prev_max = max(prev_highs)
        if closes[i] > prev_max and closes[i] > opens_p[i]:
            # 阳线突破前高 → 突破点
            vol_ratio = 1.0
            if i >= lookback:
                avg_vol = sum(klines[j]['volume'] for j in range(i-lookback, i)) / lookback
                vol_ratio = klines[i]['volume'] / avg_vol if avg_vol > 0 else 1
            if vol_ratio > 1.2:  # 放量突破
                kps.append({'idx': i, 'label': '突', 'y': closes[i], 'type': 0})
    return kps


# ════════════════════════════════════════════════════════════════
# 支撑/压力计算方法
# ════════════════════════════════════════════════════════════════

def method_A_keypoints(klines, kps, lookback=20):
    """A. 前低/前高关键点 — 最近一段前低做支撑，最近一段前高做压力"""
    n = len(klines)
    if n < 5:
        return None, None
    
    cur_close = klines[-1]['close']
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    
    # 支撑：近N天内的最低前低值
    recent_lows = [kp['y'] for kp in kps 
                   if kp['label'] == '前低' and kp['idx'] >= n - lookback and kp['y'] < cur_close]
    support = max(recent_lows) if recent_lows else min(lows[-lookback:])
    
    # 压力：近N天内的最高前高值
    recent_highs = [kp['y'] for kp in kps 
                    if kp['label'] == '前高' and kp['idx'] >= n - lookback and kp['y'] > cur_close]
    resistance = min(recent_highs) if recent_highs else max(highs[-lookback:])
    
    return support, resistance


def method_B_statistical(klines, lookback=20):
    """B. 统计边界 — N天最低点做支撑，N天最高点做压力"""
    n = len(klines)
    look = min(lookback, n)
    highs = [k['high'] for k in klines[-look:]]
    lows = [k['low'] for k in klines[-look:]]
    
    support = min(lows)
    resistance = max(highs)
    
    return support, resistance


def method_C_breakout(klines, kps):
    """C. 突破点（现有逻辑）— 突破过的前压力做支撑，15日最高做压力"""
    n = len(klines)
    cur_close = klines[-1]['close']
    highs = [k['high'] for k in klines]
    
    # 支撑：突破点且低于现价
    bk_pts = sorted(
        [kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close],
        key=lambda x: x['y'], reverse=True
    )
    support = bk_pts[0]['y'] if bk_pts else None
    
    # 压力：15日最高
    nd15 = min(15, n)
    resistance = max(highs[-nd15:])
    
    return support, resistance


def method_D_hybrid(klines, kps, lookback=20):
    """D. 混合 — 有突破用突破，无突破用前低/前高"""
    n = len(klines)
    cur_close = klines[-1]['close']
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    
    # 支撑：先试突破点
    bk_pts = sorted(
        [kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close],
        key=lambda x: x['y'], reverse=True
    )
    if bk_pts:
        support = bk_pts[0]['y']
    else:
        # 退到前低
        recent_lows = [kp['y'] for kp in kps 
                       if kp['label'] == '前低' and kp['idx'] >= n - lookback and kp['y'] < cur_close]
        support = max(recent_lows) if recent_lows else min(lows[-lookback:])
    
    # 压力：有前高用前高，否则用15日最高
    recent_highs = [kp['y'] for kp in kps 
                    if kp['label'] == '前高' and kp['idx'] >= n - lookback and kp['y'] > cur_close]
    nd15 = min(15, n)
    resistance = min(recent_highs) if recent_highs else max(highs[-nd15:])
    
    return support, resistance


# ════════════════════════════════════════════════════════════════
# 回测核心
# ════════════════════════════════════════════════════════════════

METHODS = {
    'A_前低前高': method_A_keypoints,
    'B_统计边界': method_B_statistical,
    'C_突破点': method_C_breakout,
    'D_混合': method_D_hybrid,
}


def backtest_stock(klines, method_fn, method_name, lookback=20, forward=5, touch_bp=0.01):
    """
    对一只股票滚动回测
    
    Args:
        klines: [{date, open, close, high, low, volume}, ...]
        method_fn: 支撑/压力计算方法
        lookback: 计算视窗
        forward: 预测天数
        touch_bp: 触碰阈值（±1%）
    
    Returns:
        {support_bounce: [...], resistance_reject: [...], support_break: [...], resistance_break: [...]}
    """
    n = len(klines)
    if n < lookback + forward + 10:
        return None
    
    closes = [k['close'] for k in klines]
    highs = [k['high'] for k in klines]
    lows = [k['low'] for k in klines]
    
    stats = {
        'support_touch': 0, 'support_bounce': 0, 'support_break': 0,
        'resistance_touch': 0, 'resistance_reject': 0, 'resistance_break': 0,
        'support_bounce_returns': [], 'resistance_reject_returns': [],
        'details': [],
    }
    
    for i in range(lookback + forward, n - forward):
        window_klines = klines[:i+1]
        kps = find_keypoints(window_klines, window=min(20, i))
        structure = judge_structure([k['close'] for k in window_klines])
        
        if structure != '区间震荡':
            continue
        
        # 计算支撑/压力
        if method_name == 'B_统计边界':
            s, r = method_fn(window_klines, lookback=lookback)
        elif method_name == 'C_突破点':
            s, r = method_fn(window_klines, kps)
        elif method_name == 'A_前低前高':
            s, r = method_fn(window_klines, kps, lookback=lookback)
        elif method_name == 'D_混合':
            n2 = len(window_klines)
            s, r = method_fn(window_klines, kps, lookback=lookback)
        else:
            continue
        
        if s is None:
            continue
        
        # 当前价在区间位置
        cur_close = closes[i]
        
        # 检查后续forward天是否触碰支撑/压力
        for j in range(1, forward + 1):
            idx = i + j
            if idx >= n:
                break
            
            lo = lows[idx]
            hi = highs[idx]
            close_fwd = closes[idx]
            
            # 触碰支撑
            if lo <= s * (1 + touch_bp) and s > 0:
                stats['support_touch'] += 1
                # N天后收盘价 > 支撑价 → 反弹成功
                bounce_return = (close_fwd - s) / s * 100
                if bounce_return > 0:
                    stats['support_bounce'] += 1
                else:
                    stats['support_break'] += 1
                stats['support_bounce_returns'].append(bounce_return)
                break  # 只记第一次触碰
            
            # 触碰压力
            if hi >= r * (1 - touch_bp) and r > 0:
                stats['resistance_touch'] += 1
                reject_return = (close_fwd - r) / r * 100
                if reject_return < 0:
                    stats['resistance_reject'] += 1
                else:
                    stats['resistance_break'] += 1
                stats['resistance_reject_returns'].append(reject_return)
                break
    
    return stats


def print_results(results, total_stocks):
    """打印回测结果"""
    print(f'\n{"="*80}')
    print(f'区间震荡 支撑/压力线 回测报告')
    print(f'数据源: {total_stocks}只股票, 滚动窗口回测')
    print(f'{"="*80}')
    
    for method_name, stats in sorted(results.items()):
        print(f'\n── {method_name} ──')
        
        st = stats['support']
        rt = stats['resistance']
        
        sup_total = st['support_touch']
        sup_bounce = st['support_bounce']
        sup_break = st['support_break']
        bounce_rate = sup_bounce / sup_total * 100 if sup_total > 0 else 0
        avg_bounce = sum(st['support_bounce_returns']) / len(st['support_bounce_returns']) if st['support_bounce_returns'] else 0
        
        res_total = rt['resistance_touch']
        res_reject = rt['resistance_reject']
        res_break = rt['resistance_break']
        reject_rate = res_reject / res_total * 100 if res_total > 0 else 0
        avg_reject = sum(rt['resistance_reject_returns']) / len(rt['resistance_reject_returns']) if rt['resistance_reject_returns'] else 0
        
        print(f'  支撑线: {sup_total}次触碰, 反弹{bounce_rate:.1f}% ({sup_bounce}/{sup_total}), 均收益{avg_bounce:+.2f}%')
        print(f'  压力线: {res_total}次触碰, 回落{reject_rate:.1f}% ({res_reject}/{res_total}), 均收益{avg_reject:+.2f}%')
        
        # 综合评分
        if sup_total + res_total > 0:
            total_correct = sup_bounce + res_reject
            total_touches = sup_total + res_total
            print(f'  综合: {total_correct}/{total_touches} = {total_correct/total_touches*100:.1f}% 正确率')


def main():
    import argparse
    parser = argparse.ArgumentParser(description='区间震荡支撑/压力线回测')
    parser.add_argument('--method', default='all', choices=['all', 'A', 'B', 'C', 'D'])
    parser.add_argument('--lookback', type=int, default=20, help='计算视窗')
    parser.add_argument('--forward', type=int, default=5, help='预测天数')
    args = parser.parse_args()
    
    print('加载股票数据...')
    all_stocks = load_stocks()
    print(f'共 {len(all_stocks)} 只股票')
    
    methods_to_test = list(METHODS.items())
    if args.method != 'all':
        idx = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
        methods_to_test = [methods_to_test[idx[args.method]]]
    
    results = {}
    for method_name, method_fn in methods_to_test:
        print(f'\n{"-"*60}')
        print(f'回测方法: {method_name}')
        print(f'{"-"*60}')
        
        combined = {
            'support': {'support_touch': 0, 'support_bounce': 0, 'support_break': 0, 'support_bounce_returns': []},
            'resistance': {'resistance_touch': 0, 'resistance_reject': 0, 'resistance_break': 0, 'resistance_reject_returns': []},
        }
        
        t0 = time.time()
        count = 0
        for code, name, klines in all_stocks:
            if len(klines) < 60:
                continue
            st = backtest_stock(klines, method_fn, method_name, lookback=args.lookback, forward=args.forward)
            if st is None:
                continue
            count += 1
            for key in ['support_touch', 'support_bounce', 'support_break']:
                combined['support'][key] += st[key]
            for key in ['resistance_touch', 'resistance_reject', 'resistance_break']:
                combined['resistance'][key] += st[key]
            combined['support']['support_bounce_returns'].extend(st['support_bounce_returns'])
            combined['resistance']['resistance_reject_returns'].extend(st['resistance_reject_returns'])
        
        results[method_name] = combined
        elapsed = time.time() - t0
        print(f'  → 区间震荡样本: {count}只, 耗时{elapsed:.0f}s')
    
    print_results(results, len(all_stocks))
    
    # 保存结果
    out_path = os.path.join(DATA_DIR, 'cache', 'backtest_support_resistance.json')
    with open(out_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'params': {'lookback': args.lookback, 'forward': args.forward},
            'results': results,
        }, f, ensure_ascii=False)
    print(f'\n结果已保存: {out_path}')


if __name__ == '__main__':
    main()
