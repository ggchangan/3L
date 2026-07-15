"""
恐慌检测回测脚本
目的：在历史指数数据上遍历阈值组合，找到最优恐慌阈值
"""
import json
import sys
import os
sys.path.insert(0, '/home/ubuntu/3l-server/server')
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

import warnings
warnings.filterwarnings('ignore')

from datetime import datetime, timedelta
import numpy as np

def fetch_index_klines_akshare(code, name):
    """拉取指数历史日K线（同 update_stock_data.py 的方式）"""
    import akshare as ak
    try:
        df = ak.stock_zh_index_daily_tx(symbol=f'sh{code}')
        if df is None or len(df) == 0:
            return []
        records = []
        for _, row in df.iterrows():
            # akshare 返回列: date, open, close, high, low, amount, volume
            dt = row['date']
            if isinstance(dt, str):
                dt = dt.replace('-', '')
            records.append({
                'date': str(dt),
                'close': float(row['close']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'volume': float(row.get('volume', 0) or 0),
            })
        # 排序
        records.sort(key=lambda x: x['date'])
        return records
    except Exception as e:
        print(f"  ⚠️ {name}({code})拉取失败: {e}")
        return []

def calc_change_pct(klines):
    """计算每日涨跌幅"""
    results = []
    for i in range(1, len(klines)):
        prev = klines[i-1]['close']
        cur = klines[i]['close']
        chg = round((cur - prev) / prev * 100, 2)
        results.append({
            'date': klines[i]['date'],
            'close': cur,
            'change_pct': chg,
            'volume': klines[i].get('volume', 0),
        })
    return results

def backtest_threshold(changes, threshold_pct, min_vol_ratio=0.8):
    """
    回测单个阈值
    
    返回:
    {
        'trigger_count': 触发次数,
        'avg_1d_return': 恐慌后1日平均涨跌幅,
        'win_rate_1d': 1日后反弹概率,
        'avg_3d_return': 3日后平均涨跌幅,
        'win_rate_3d': 3日后反弹概率,
        'avg_5d_return': 5日后平均涨跌幅,
        'triggers': [{date, change_pct, ...}]
    }
    """
    triggers = []
    for i, d in enumerate(changes):
        if d['change_pct'] <= -threshold_pct:
            # 去重：连续两天触发只算第一次
            if triggers and triggers[-1]['date'] == d['date']:
                continue
            if i+1 > len(changes) - 1:
                triggers.append({'date': d['date'], 'change_pct': d['change_pct']})
                continue
            
            # 后续1/3/5日涨幅
            ret_1d = changes[i+1]['change_pct'] if i+1 < len(changes) else 0
            ret_3d = sum(changes[min(i+j, len(changes)-1)]['change_pct'] for j in range(1, min(4, len(changes)-i)))
            ret_5d = sum(changes[min(i+j, len(changes)-1)]['change_pct'] for j in range(1, min(6, len(changes)-i)))
            
            triggers.append({
                'date': d['date'],
                'change_pct': d['change_pct'],
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'close': d['close'],
            })
    
    # 合并连续触发日（同一次恐慌只计一次，取最大跌幅那天）
    merged = []
    i = 0
    while i < len(triggers):
        merged.append(triggers[i])
        # 跳过后续连续触发的
        j = i + 1
        while j < len(triggers) and not is_new_panic_event(triggers, i, j):
            j += 1
        i = j
    
    if not merged:
        return {
            'trigger_count': 0,
            'count_per_year': 0,
            'avg_1d_return': 0,
            'win_rate_1d': 0,
            'avg_3d_return': 0,
            'win_rate_3d': 0,
            'avg_5d_return': 0,
            'triggers': [],
            'trigger_dates': [],
        }
    
    # 筛选有后续数据的
    with_data = [t for t in merged if 'ret_1d' in t]
    
    if not with_data:
        return {
            'trigger_count': len(merged),
            'count_per_year': 0,
            'avg_1d_return': 0,
            'win_rate_1d': 0,
            'avg_3d_return': 0,
            'win_rate_3d': 0,
            'avg_5d_return': 0,
            'triggers': merged,
            'trigger_dates': [t['date'] for t in merged],
        }
    
    ret_1d_list = [t['ret_1d'] for t in with_data]
    ret_3d_list = [t['ret_3d'] for t in with_data]
    ret_5d_list = [t['ret_5d'] for t in with_data]
    
    return {
        'trigger_count': len(merged),
        'count_per_year': round(len(merged) / (len(changes) / 245), 1),  # 年化
        'avg_1d_return': round(np.mean(ret_1d_list), 2),
        'win_rate_1d': round(sum(1 for r in ret_1d_list if r > 0) / len(ret_1d_list) * 100, 1),
        'avg_3d_return': round(np.mean(ret_3d_list), 2),
        'win_rate_3d': round(sum(1 for r in ret_3d_list if r > 0) / len(ret_3d_list) * 100, 1),
        'avg_5d_return': round(np.mean(ret_5d_list), 2),
        'win_rate_5d': round(sum(1 for r in ret_5d_list if r > 0) / len(ret_5d_list) * 100, 1),
        'triggers': merged,
        'trigger_dates': [t['date'] for t in merged],
    }

def is_new_panic_event(triggers, i, j):
    """判断第j次触发是否属于第i次同一次恐慌事件（连续2天内的算一次）"""
    if j <= i:
        return False
    d1 = triggers[i]['date']
    d2 = triggers[j]['date']
    # 如果是同一天或相邻日期，算同一次事件
    if len(d1) == 8 and len(d2) == 8:
        # YYYYMMDD 格式
        diff = int(d2) - int(d1)
        return diff > 2
    return True


def main():
    print("=" * 60)
    print("恐慌检测回测 — 遍历阈值组合")
    print("=" * 60)
    
    indices_config = [
        ('000001', '上证指数'),
        ('399001', '深证成指'),
        ('399006', '创业板指'),
        ('000688', '科创50'),
        ('000985', '中证全指'),
    ]
    
    # 拉取数据
    all_changes = {}
    for code, name in indices_config:
        print(f"\n拉取 {name}({code}) 日K线...")
        klines = fetch_index_klines_akshare(code, name)
        if len(klines) < 30:
            print(f"  ❌ 数据不足，跳过")
            continue
        changes = calc_change_pct(klines)
        all_changes[name] = changes
        print(f"  ✅ {len(klines)}条K线, {len(changes)}个交易日")
        print(f"  区间: {changes[0]['date']} ~ {changes[-1]['date']}")
        
        # 统计最大跌幅
        max_drop = min(c['change_pct'] for c in changes)
        avg_drop = np.mean([c['change_pct'] for c in changes])
        neg_days = sum(1 for c in changes if c['change_pct'] < 0)
        print(f"  最大单日跌幅: {max_drop}%")
        print(f"  日均涨跌幅: {avg_drop:.2f}%")
        print(f"  下跌天数: {neg_days}/{len(changes)} ({neg_days/len(changes)*100:.0f}%)")
    
    # --- 遍历阈值 ---
    print("\n" + "=" * 60)
    print("阈值遍历结果")
    print("=" * 60)
    
    # 使用中证全指（全市场代表）和上证指数做主要回测
    # 只取最近3年的数据
    CUTOFF = '2025-12-01'
    
    changes_recent = {}
    for name, cs in all_changes.items():
        changes_recent[name] = [c for c in cs if c['date'] >= CUTOFF.replace('-', '')]
    
    primary_index = '上证指数'
    
    if primary_index not in changes_recent:
        primary_index = list(changes_recent.keys())[0]
    
    changes = changes_recent[primary_index]
    print(f"\n使用 {primary_index} 最近3年 ({len(changes)}个交易日)")
    
    # 也打印中证全指近期数据
    if '中证全指' in changes_recent:
        zz_changes = changes_recent['中证全指']
        print(f"中证全指 最近3年 ({len(zz_changes)}个交易日)")
    
    # 单一阈值遍历 (1.0% ~ 5.0%)
    thresholds = [x/10 for x in range(10, 51, 2)]  # 1.0, 1.2, 1.4 ... 5.0
    
    print(f"\n{'阈值':>5} | {'触发':>5} | {'次/年':>6} | {'1日后':>6} | {'胜率1':>6} | {'3日后':>6} | {'胜率3':>6} | {'5日后':>6} | {'胜率5':>6}")
    print("-" * 75)
    
    best_score = -999
    best_threshold = None
    
    for t in thresholds:
        result = backtest_threshold(changes, t)
        cnt = result['trigger_count']
        cpy = result['count_per_year']
        r1 = result['avg_1d_return']
        w1 = result['win_rate_1d']
        r3 = result['avg_3d_return']
        w3 = result['win_rate_3d']
        r5 = result['avg_5d_return']
        w5 = result['win_rate_5d']
        
        # 综合评分：适中触发次数(3-12次/年) + 3日胜率高 + 3日均值好
        year_rate = cpy
        if 2 <= year_rate <= 15:
            freq_score = 10
        elif year_rate < 2:
            freq_score = year_rate * 3  # 低于2次/年的，惩罚
        else:
            freq_score = max(0, 15 - year_rate)  # 超过15次/年，逐步惩罚
        
        score = freq_score + w3 * 0.5 + max(0, r3) * 10
        
        print(f" {t:>4.1f}% | {cnt:>5} | {cpy:>6.1f} | {r1:>6.2f} | {w1:>5.1f}% | {r3:>6.2f} | {w3:>5.1f}% | {r5:>6.2f} | {w5:>5.1f}%")
        
        if score > best_score:
            best_score = score
            best_threshold = t
    
    print("-" * 75)
    print(f"\n🏆 最优阈值: {best_threshold:.1f}% (评分 {best_score:.1f})")
    best_result = backtest_threshold(changes, best_threshold)
    print(f"\n  触发 {best_result['trigger_count']}次 ({best_result['count_per_year']:.1f}次/年)")
    print(f"  触发日期: {', '.join(best_result['trigger_dates'][:10])}{'...' if len(best_result['trigger_dates']) > 10 else ''}")
    
    # 测试上证+中证全指双指数联合判定
    print("\n\n" + "=" * 60)
    print("双指数联合判定（任一触发即算）")
    print("=" * 60)
    
    if '深证成指' in all_changes:
        combined_changes = all_changes['深证成指']
        print(f"\n+ 深证成指 ({len(combined_changes)}个交易日)")
    elif '中证全指' in all_changes:
        combined_changes = all_changes['中证全指']
        print(f"\n+ 中证全指 ({len(combined_changes)}个交易日)")
    
    # 展示推荐阈值组合
    print(f"\n\n{'='*60}")
    print("推荐方案")
    print(f"{'='*60}")
    
    # 方案：caution=2.5%, warning=3.5% on 上证指数
    for label, threshold in [('注意⚠️', 2.5), ('预警🔴', 3.5)]:
        r = backtest_threshold(changes, threshold)
        print(f"\n{label} 阈值 {threshold:.1f}%:")
        print(f"  触发: {r['trigger_count']}次 ({r['count_per_year']:.1f}次/年)")
        print(f"  1日后: 均值{r['avg_1d_return']:+.2f}% 胜率{r['win_rate_1d']}%")
        print(f"  3日后: 均值{r['avg_3d_return']:+.2f}% 胜率{r['win_rate_3d']}%")
        print(f"  5日后: 均值{r['avg_5d_return']:+.2f}% 胜率{r['win_rate_5d']}%")

if __name__ == '__main__':
    main()
