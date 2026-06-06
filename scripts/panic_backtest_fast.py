"""
恐慌检测回测脚本 — 快速版（使用缓存数据）
只使用最近6个月的历史数据
"""
import json
import sys
import os
sys.path.insert(0, '/home/ubuntu/3l-server/server')

import warnings
warnings.filterwarnings('ignore')

import numpy as np

def load_cached_index_data():
    """从本地缓存文件加载指数数据"""
    path = '/home/ubuntu/data/3l/public/index_data.json'
    if not os.path.isfile(path):
        print("❌ 找不到缓存数据文件")
        return {}
    with open(path) as f:
        data = json.load(f)
    
    indices_data = {}
    for code, info in data.get('indices', {}).items():
        klines = info.get('klines', [])
        if not klines:
            continue
        
        # 过滤最近6个月的
        cutoff = '20251201'  # 2025-12-01
        filtered = [k for k in klines if str(k['date']) >= cutoff]
        if len(filtered) < 10:
            continue
        
        # 计算涨跌幅
        changes = []
        for i in range(1, len(filtered)):
            prev = filtered[i-1]['close']
            cur = filtered[i]['close']
            chg = round((cur - prev) / prev * 100, 2)
            changes.append({
                'date': filtered[i]['date'],
                'close': cur,
                'change_pct': chg,
                'volume': filtered[i].get('volume', 0),
            })
        
        indices_data[info.get('name', code)] = {
            'changes': changes,
            'name': info.get('name', code),
            'code': code,
        }
    
    return indices_data

def backtest(changes, threshold):
    """回测单个阈值"""
    triggers = []
    i = 0
    while i < len(changes):
        d = changes[i]
        if d['change_pct'] <= -threshold:
            # 计算后续收益
            ret_1d = changes[i+1]['change_pct'] if i+1 < len(changes) else 0
            ret_3d = sum(changes[min(i+j, len(changes)-1)]['change_pct'] for j in range(1, min(4, len(changes)-i)))
            ret_5d = sum(changes[min(i+j, len(changes)-1)]['change_pct'] for j in range(1, min(6, len(changes)-i)))
            
            triggers.append({
                'date': d['date'],
                'change_pct': d['change_pct'],
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
            })
            
            # 跳过后续连续2天的触发（同一次恐慌事件）
            j = i + 1
            while j < len(changes):
                d2_date = str(changes[j]['date'])
                d1_date = str(d['date'])
                # 规范化日期比较
                d1 = d1_date.replace('-', '')[:8]
                d2 = d2_date.replace('-', '')[:8]
                if d2 <= d1 or (len(d2) == 8 and len(d1) == 8 and int(d2) - int(d1) <= 2):
                    j += 1
                else:
                    break
            i = j
        else:
            i += 1
    
    if not triggers:
        return {'count': 0, 'count_per_year': 0, 'avg_1d': 0, 'win_1d': 0, 'avg_3d': 0, 'win_3d': 0, 'avg_5d': 0, 'win_5d': 0, 'dates': []}
    
    r1 = [t['ret_1d'] for t in triggers]
    r3 = [t['ret_3d'] for t in triggers]
    r5 = [t['ret_5d'] for t in triggers]
    
    n = len(r1)
    trading_days = len(changes)
    years = trading_days / 245
    
    return {
        'count': n,
        'count_per_year': round(n / years, 1) if years > 0 else 0,
        'avg_1d': round(np.mean(r1), 2),
        'win_1d': round(sum(1 for r in r1 if r > 0) / n * 100, 1),
        'avg_3d': round(np.mean(r3), 2),
        'win_3d': round(sum(1 for r in r3 if r > 0) / n * 100, 1),
        'avg_5d': round(np.mean(r5), 2),
        'win_5d': round(sum(1 for r in r5 if r > 0) / n * 100, 1),
        'dates': [str(t['date']) for t in triggers],
    }

def main():
    print("=" * 55)
    print("恐慌检测回测 — 最近6个月（缓存数据）")
    print("=" * 55)
    
    all_data = load_cached_index_data()
    
    for name, data in all_data.items():
        cs = data['changes']
        print(f"\n{name}: {len(cs)}个交易日")
        
        thresholds = [x/10 for x in range(10, 51, 3)]  # 1.0, 1.3, 1.6 ... 5.0
        
        print(f"{'阈值':>5} | {'触发':>4} | {'次/年':>6} | {'1日后':>6} | {'胜率1':>6} | {'3日后':>6} | {'胜率3':>6} | {'5日后':>6} | {'胜率5':>6}")
        print("-" * 73)
        
        for t in thresholds:
            r = backtest(cs, t)
            print(f" {t:>4.1f}% | {r['count']:>4} | {r['count_per_year']:>6.1f} | {r['avg_1d']:>+6.2f} | {r['win_1d']:>5.1f}% | {r['avg_3d']:>+6.2f} | {r['win_3d']:>5.1f}% | {r['avg_5d']:>+6.2f} | {r['win_5d']:>5.1f}%")
        
        # 推荐方案
        print(f"\n  推荐方案:")
        for label, thr in [('注意⚠️', 2.5), ('预警🔴', 3.5)]:
            r = backtest(cs, thr)
            print(f"  {label} ≥{thr}%: {r['count']}次 ({r['count_per_year']:.1f}次/年) 1日{r['avg_1d']:+.2f}%({r['win_1d']}%) 3日{r['avg_3d']:+.2f}%({r['win_3d']}%)")
            if r['dates']:
                print(f"    日期: {', '.join(r['dates'][:8])}")

if __name__ == '__main__':
    main()
