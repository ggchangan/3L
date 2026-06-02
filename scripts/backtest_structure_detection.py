#!/usr/bin/env python3
"""
结构判定回测 — 测试不同方法对上涨趋势/区间震荡/下降趋势的识别准确度

回测思路：
  滚动窗口 → 用方法X判定当前结构 → 未来N天涨跌幅
  - 判上涨趋势 → 后续应该涨（正收益）
  - 判下降趋势 → 后续应该跌（负收益）
  - 判区间震荡 → 后续振幅应该窄（小涨小跌）

方法对比：
  1. 生产版: EMA10极值位置法 + 对称末端校验（当前代码）
  2. 简化版: EMA20斜率 + BIAS20（回测脚本中的 judge_structure）
  3. EMA5斜率法: 更敏感
  4. 联合版: 多种方法投票

运行:
  python3 scripts/backtest_structure_detection.py
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
    """返回 [(code, name, klines), ...]"""
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
# EMA工具
# ════════════════════════════════════════════════════════════════

def ema_list(values, period):
    r = [None] * len(values)
    m = 2 / (period + 1)
    for i in range(len(values)):
        if i == 0:
            r[i] = values[i]
        elif r[i-1] is not None:
            r[i] = (values[i] - r[i-1]) * m + r[i-1]
    return r


def _reg_slope(y_list):
    n = len(y_list)
    if n < 2:
        return 0
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(y_list) / n
    num = sum((xs[i] - mx) * (y_list[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den else 0


# ════════════════════════════════════════════════════════════════
# 各方法的结构判定
# ════════════════════════════════════════════════════════════════

def struct_A_production(closes):
    """A. 生产版 — EMA10极值位置法 + 对称末端校验"""
    if len(closes) < 15:
        return '--'
    e10 = ema_list(closes, 10)[-15:]
    n = len(e10)
    fq = n // 4
    lq = n - 1 - n // 4
    max_pos = max(range(n), key=lambda i: e10[i] if e10[i] is not None else -1e9)
    min_pos = min(range(n), key=lambda i: e10[i] if e10[i] is not None else 1e9)
    
    if max_pos >= lq and min_pos <= fq:
        base = '上涨趋势'
    elif min_pos >= lq and max_pos <= fq:
        base = '下降趋势'
    else:
        base = '区间震荡'
    
    # 对称末端校验
    l3 = [v for v in e10[-3:] if v is not None]
    if base == '上涨趋势' and len(l3) == 3 and l3[0] > l3[1] > l3[2] and closes[-1] < l3[-1]:
        return '区间震荡'
    if base == '下降趋势' and len(l3) == 3 and l3[0] < l3[1] < l3[2] and closes[-1] > l3[-1]:
        return '区间震荡'
    return base


def struct_B_ema20_slope(closes, slope_thresh=0.3, bias_thresh=2):
    """B. EMA20斜率法（简化版）— 可调参"""
    if len(closes) < 25:
        return '--'
    ema20 = ema_list(closes, 20)
    e20_recent = [v for v in ema20[-10:] if v is not None]
    close_recent = closes[-10:]
    if len(e20_recent) < 5:
        return '--'
    
    slope = _reg_slope(e20_recent)
    slope_pct = slope / e20_recent[0] * 100 if e20_recent[0] else 0
    
    cur, cur_ema20 = closes[-1], e20_recent[-1]
    bias20 = (cur - cur_ema20) / cur_ema20 * 100 if cur_ema20 else 0
    
    amplitude = (max(close_recent) - min(close_recent)) / min(close_recent) * 100
    
    if slope_pct > slope_thresh and bias20 > -bias_thresh:
        return '上涨趋势'
    elif slope_pct < -slope_thresh and bias20 < bias_thresh:
        return '下降趋势'
    else:
        return '区间震荡'


def struct_C_ema5_slope(closes):
    """C. EMA5斜率法 — 更敏感"""
    if len(closes) < 15:
        return '--'
    ema5 = ema_list(closes, 5)
    e5_recent = [v for v in ema5[-10:] if v is not None]
    if len(e5_recent) < 5:
        return '--'
    
    slope = _reg_slope(e5_recent)
    slope_pct = slope / e5_recent[0] * 100 if e5_recent[0] else 0
    
    cur, cur_ema5 = closes[-1], e5_recent[-1]
    bias5 = (cur - cur_ema5) / cur_ema5 * 100 if cur_ema5 else 0
    
    amplitude = (max(closes[-10:]) - min(closes[-10:])) / min(closes[-10:]) * 100
    
    if slope_pct > 0.5 and bias5 > -3:
        return '上涨趋势'
    elif slope_pct < -0.5 and bias5 < 3:
        return '下降趋势'
    else:
        return '区间震荡'


def struct_D_hybrid(closes):
    """D. 联合投票 — A+B+C多数决"""
    a = struct_A_production(closes)
    b = struct_B_ema20_slope(closes)
    c = struct_C_ema5_slope(closes)
    votes = [a, b, c]
    up = votes.count('上涨趋势')
    down = votes.count('下降趋势')
    flat = votes.count('区间震荡')
    if up >= 2:
        return '上涨趋势'
    elif down >= 2:
        return '下降趋势'
    else:
        return '区间震荡'


METHODS = {
    'A_生产版EMA10极值': struct_A_production,
    'B_EMA20斜率': struct_B_ema20_slope,
    'C_EMA5斜率': struct_C_ema5_slope,
    'D_联合投票': struct_D_hybrid,
}


# ════════════════════════════════════════════════════════════════
# 回测核心
# ════════════════════════════════════════════════════════════════

def backtest_structure(klines, method_fn, forward=5):
    """
    回测一只股票的结构判定效果
    
    返回: {method_stats}
    """
    n = len(klines)
    if n < 40:
        return None
    
    closes = [k['close'] for k in klines]
    
    stats = {
        '上涨趋势': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
        '下降趋势': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
        '区间震荡': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
        '--': {'count': 0},
    }
    
    for i in range(20, n - forward):
        window = closes[:i+1]
        struct = method_fn(window)
        if struct not in stats or struct == '--':
            continue
        
        stats[struct]['count'] += 1
        
        # 未来forward天收益
        fwd_close = closes[i + forward]
        ret = (fwd_close - closes[i]) / closes[i] * 100
        stats[struct]['fwd_return'].append(ret)
        stats[struct]['fwd_abs_return'].append(abs(ret))
        
        # 未来forward天振幅
        fwd_high = max(k['high'] for k in klines[i+1:i+forward+1])
        fwd_low = min(k['low'] for k in klines[i+1:i+forward+1])
        fwd_amp = (fwd_high - fwd_low) / klines[i]['close'] * 100
        stats[struct]['fwd_amplitude'].append(fwd_amp)
    
    return stats


def print_results(results, forward):
    print(f'\n{"="*80}')
    print(f'结构判定回测报告（预测{forward}天）')
    print(f'{"="*80}')
    
    for method_name, stats in sorted(results.items()):
        print(f'\n── {method_name} ──')
        
        for struct in ['上涨趋势', '区间震荡', '下降趋势']:
            s = stats[struct]
            cnt = s['count']
            if cnt == 0:
                continue
            avg_ret = sum(s['fwd_return']) / cnt
            avg_abs = sum(s['fwd_abs_return']) / cnt
            avg_amp = sum(s['fwd_amplitude']) / cnt
            win_rate = sum(1 for r in s['fwd_return'] if r > 0) / cnt * 100
            loss_rate = sum(1 for r in s['fwd_return'] if r < 0) / cnt * 100
            
            print(f'  {struct}: {cnt}次')
            print(f'    胜率 {win_rate:.1f}% | 均收益 {avg_ret:+.2f}% | 均绝对收益 {avg_abs:.2f}% | 均振幅 {avg_amp:.2f}%')
        
        # 区分度评分：上涨收益 - 下降收益
        up_ret = sum(stats['上涨趋势']['fwd_return']) / stats['上涨趋势']['count'] if stats['上涨趋势']['count'] > 0 else 0
        down_ret = sum(stats['下降趋势']['fwd_return']) / stats['下降趋势']['count'] if stats['下降趋势']['count'] > 0 else 0
        flat_ret = sum(stats['区间震荡']['fwd_return']) / stats['区间震荡']['count'] if stats['区间震荡']['count'] > 0 else 0
        flat_amp = sum(stats['区间震荡']['fwd_amplitude']) / stats['区间震荡']['count'] if stats['区间震荡']['count'] > 0 else 0
        
        discrimination = up_ret - down_ret
        print(f'  区分度（上涨收益-下降收益）: {discrimination:+.2f}%')
        print(f'  区间震荡均收益: {flat_ret:+.2f}%（期望接近0）均振幅: {flat_amp:.2f}%（期望小）')


# ════════════════════════════════════════════════════════════════
# 参数扫描（EMA20斜率法）
# ════════════════════════════════════════════════════════════════

def scan_params(all_stocks, forward=5):
    """扫描EMA20斜率法的最佳参数"""
    print(f'\n{"="*80}')
    print(f'参数扫描 — B(EMA20斜率法)')
    print(f'{"="*80}')
    
    best = {'discrimination': -999, 'params': None}
    
    for slope_thresh in [0.2, 0.3, 0.4, 0.5]:
        for bias_thresh in [1, 2, 3, 4]:
            combined = {
                '上涨趋势': {'count': 0, 'fwd_return': []},
                '下降趋势': {'count': 0, 'fwd_return': []},
                '区间震荡': {'count': 0, 'fwd_return': [], 'fwd_amplitude': []},
            }
            
            for code, name, klines in all_stocks:
                if len(klines) < 40:
                    continue
                closes = [k['close'] for k in klines]
                for i in range(20, len(klines) - forward):
                    window = closes[:i+1]
                    struct = struct_B_ema20_slope(window, slope_thresh=slope_thresh, bias_thresh=bias_thresh)
                    if struct not in combined or struct == '--':
                        continue
                    combined[struct]['count'] += 1
                    fwd_close = closes[i + forward]
                    ret = (fwd_close - closes[i]) / closes[i] * 100
                    combined[struct]['fwd_return'].append(ret)
                    if struct == '区间震荡':
                        fwd_high = max(k['high'] for k in klines[i+1:i+forward+1])
                        fwd_low = min(k['low'] for k in klines[i+1:i+forward+1])
                        fwd_amp = (fwd_high - fwd_low) / klines[i]['close'] * 100
                        combined['区间震荡']['fwd_amplitude'].append(fwd_amp)
            
            up_ret = sum(combined['上涨趋势']['fwd_return']) / combined['上涨趋势']['count'] if combined['上涨趋势']['count'] > 0 else 0
            down_ret = sum(combined['下降趋势']['fwd_return']) / combined['下降趋势']['count'] if combined['下降趋势']['count'] > 0 else 0
            disc = up_ret - down_ret
            flat_ret = sum(combined['区间震荡']['fwd_return']) / combined['区间震荡']['count'] if combined['区间震荡']['count'] > 0 else 0
            flat_amp = sum(combined['区间震荡']['fwd_amplitude']) / combined['区间震荡']['count'] if combined['区间震荡']['fwd_amplitude'] else 0
            
            print(f'  斜率>{slope_thresh} BIAS>-{bias_thresh}: 区分度{disc:+.2f}% | 上涨{up_ret:+.2f}%({combined["上涨趋势"]["count"]}) 下降{down_ret:+.2f}%({combined["下降趋势"]["count"]}) 震荡{flat_ret:+.2f}%({combined["区间震荡"]["count"]}) 振幅{flat_amp:.2f}%')
            
            if disc > best['discrimination']:
                best = {'discrimination': disc, 'params': (slope_thresh, bias_thresh)}
    
    print(f'\n最佳参数: 斜率>{best["params"][0]} BIAS>-{best["params"][1]} → 区分度{best["discrimination"]:+.2f}%')
    return best


# ════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--forward', type=int, default=5)
    parser.add_argument('--scan', action='store_true', help='只跑参数扫描')
    args = parser.parse_args()
    
    print('加载股票数据...')
    all_stocks = load_stocks()
    print(f'共 {len(all_stocks)} 只股票')
    
    # 参数扫描
    best = scan_params(all_stocks, forward=args.forward)
    
    if args.scan:
        return
    
    # 全方法对比（用最佳参数跑B）
    print(f'\n{"="*80}')
    print(f'全方法对比（B用最佳参数: 斜率>{best["params"][0]} BIAS>-{best["params"][1]}）')
    
    results = {}
    for method_name, method_fn in METHODS.items():
        combined = {
            '上涨趋势': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
            '下降趋势': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
            '区间震荡': {'count': 0, 'fwd_return': [], 'fwd_abs_return': [], 'fwd_amplitude': []},
        }
        
        t0 = time.time()
        for code, name, klines in all_stocks:
            if len(klines) < 40:
                continue
            if method_name == 'B_EMA20斜率':
                # 用最佳参数
                orig_fn = method_fn
                method_fn_custom = lambda c: struct_B_ema20_slope(c, slope_thresh=best['params'][0], bias_thresh=best['params'][1])
                st = backtest_structure(klines, method_fn_custom, forward=args.forward)
            else:
                st = backtest_structure(klines, method_fn, forward=args.forward)
            if st is None:
                continue
            for s in ['上涨趋势', '区间震荡', '下降趋势']:
                if s in st:
                    for k in ['count', 'fwd_return', 'fwd_abs_return', 'fwd_amplitude']:
                        if isinstance(combined[s][k], list):
                            combined[s][k].extend(st[s][k])
                        else:
                            combined[s][k] += st[s][k]
        
        elapsed = time.time() - t0
        results[method_name] = combined
        print(f'\n{method_name}: 耗时{elapsed:.0f}s')
        for s in ['上涨趋势', '区间震荡', '下降趋势']:
            c = combined[s]
            if c['count'] > 0:
                avg_ret = sum(c['fwd_return']) / c['count']
                win = sum(1 for r in c['fwd_return'] if r > 0) / c['count'] * 100
                avg_amp = sum(c['fwd_amplitude']) / c['count'] if c['fwd_amplitude'] else 0
                print(f'  {s}: {c["count"]}次 胜率{win:.1f}% 均收益{avg_ret:+.2f}% 振幅{avg_amp:.2f}%')
    
    # 结果保存
    out_path = os.path.join(DATA_DIR, 'cache', 'backtest_structure_detection.json')
    with open(out_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'params': {'forward': args.forward, 'best_b_params': best},
            'results': {k: {s: {kk: vv for kk, vv in combined[s].items() if kk != 'fwd_return'}
                           for s in ['上涨趋势', '区间震荡', '下降趋势']}
                       for k, combined in results.items()},
        }, f, ensure_ascii=False)
    print(f'\n结果已保存: {out_path}')
    
    # 打印总表
    print(f'\n{"="*80}')
    print(f'总表')
    for method_name, combined in sorted(results.items()):
        up = combined['上涨趋势']
        down = combined['下降趋势']
        flat = combined['区间震荡']
        up_ret = sum(up['fwd_return']) / up['count'] if up['count'] > 0 else 0
        down_ret = sum(down['fwd_return']) / down['count'] if down['count'] > 0 else 0
        flat_ret = sum(flat['fwd_return']) / flat['count'] if flat['count'] > 0 else 0
        flat_amp = sum(flat['fwd_amplitude']) / flat['count'] if flat['fwd_amplitude'] else 0
        disc = up_ret - down_ret
        print(f'  {method_name}: 区分度{disc:+.2f}% | 上涨{up_ret:+.2f}%({up["count"]}) 下降{down_ret:+.2f}%({down["count"]}) 震荡{flat_ret:+.2f}%({flat["count"]}) 振幅{flat_amp:.2f}%')


if __name__ == '__main__':
    main()
