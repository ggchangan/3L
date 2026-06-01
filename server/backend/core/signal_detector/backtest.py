"""
回测框架 v2 — 支持结构分层

逐日滚动检测六大信号，按以下维度分层统计：
1. 个股所属板块 vs 当日主线板块
2. 个股趋势方向

数据源：
- stock_industry_map.json: 个股→行业映射
- mainline_history.json: 每日主线板块列表
- all_stocks_60d.json: 60天日K线
"""
import json
import os
import sys
from typing import List, Dict, Any, Optional
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from core.signal_detector import (
    detect_upward_breakout,
    detect_downward_breakout,
    detect_upward_continuation,
    detect_downward_continuation,
    detect_range_continuation,
    detect_upward_reversal,
    detect_downward_reversal,
    detect_demand_exhaustion,
    detect_supply_exhaustion,
    SIGNAL_NAMES,
)

DETECTORS = {
    'upward_breakout': detect_upward_breakout,
    'downward_breakout': detect_downward_breakout,
    'upward_continuation': detect_upward_continuation,
    'downward_continuation': detect_downward_continuation,
    'range_continuation': detect_range_continuation,
    'upward_reversal': detect_upward_reversal,
    'downward_reversal': detect_downward_reversal,
    'demand_exhaustion': detect_demand_exhaustion,
    'supply_exhaustion': detect_supply_exhaustion,
}

DATA_DIR = '/home/ubuntu/data/3l'


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_all():
    """加载所有回测所需数据"""
    # 行业映射
    industry_map = load_json(f'{DATA_DIR}/stock_industry_map.json')
    
    # 主线历史
    mainline_history = load_json(f'{DATA_DIR}/mainline_history.json')
    
    # 60天K线
    raw = load_json(f'{DATA_DIR}/all_stocks_60d.json')
    
    stocks = {}
    for sector_name, sector_data in raw.get('stocks', {}).items():
        for code, klines in sector_data.items():
            name = klines[0].get('name', code) if klines else code
            sector = industry_map.get(code, {}).get('ths_industry', sector_name)
            stocks[code] = {
                'code': code,
                'name': name,
                'sector': sector,
                'raw_sector': sector_name,
                'klines': klines,
            }
    
    return stocks, mainline_history


def get_stock_trend(klines, idx, lookback=20):
    """简易趋势判定"""
    if idx < lookback:
        return 'unknown'
    window = klines[idx - lookback:idx + 1]
    closes = [k['close'] for k in window]
    gain = (closes[-1] - closes[0]) / (closes[0] or 1)
    if gain > 0.08:
        return 'up'
    elif gain < -0.08:
        return 'down'
    else:
        return 'range'


def is_mainline_sector(mainline_history, date_str, sector):
    """判断某天某板块是否为主线"""
    # 收集所有可用的主线板块列表
    all_mainline_sectors = set()
    for date_key, data in mainline_history.items():
        for ml in data.get('top10', []):
            all_mainline_sectors.add(ml)
    
    # 精确匹配
    if sector in all_mainline_sectors:
        return True
    
    # 部分匹配
    for ms in all_mainline_sectors:
        if ms in sector or sector in ms:
            return True
    
    return False


def run_stratified_backtest(signal_key, stocks, mainline_history,
                            min_klines=40, horizons=[5, 10]):
    """按结构分层回测"""
    detector = DETECTORS.get(signal_key)
    if not detector:
        return {'signal_key': signal_key, 'error': '未实现'}

    # 结果存储：维度 → [(horizon, return_pct)]
    all_results = []
    
    for code, stock_data in stocks.items():
        klines = stock_data['klines']
        sector = stock_data['sector']
        
        if len(klines) < min_klines:
            continue
        
        for i in range(min_klines, len(klines)):
            signal = detector(klines, i)
            if not signal['triggered']:
                continue
            
            entry_price = klines[i]['close']
            entry_date = klines[i]['date']
            
            # 结构信息
            trend = get_stock_trend(klines, i)
            is_mainline = is_mainline_sector(mainline_history, entry_date, sector)
            
            record = {
                'code': code,
                'name': stock_data['name'],
                'sector': sector,
                'entry_date': entry_date,
                'entry_price': entry_price,
                'confidence': signal['confidence'],
                'trend': trend,
                'is_mainline': is_mainline,
                'detail': signal.get('detail', ''),
                'form': signal.get('scores', {}).get('form', ''),
            }
            
            for h in horizons:
                if i + h >= len(klines):
                    continue
                ret = (klines[i + h]['close'] - entry_price) / (entry_price or 1) * 100
                record[f'ret_{h}d'] = round(ret, 2)
            
            all_results.append(record)
    
    return all_results


def print_stratified_stats(results, signal_name):
    """打印分层统计"""
    if not results:
        print(f"\n  [{signal_name}] ❌ 未触发任何信号")
        return
    
    total_signals = len(set((r['code'], r['entry_date']) for r in results))
    print(f"\n  {'='*50}")
    print(f"  [{signal_name}] 共 {total_signals} 次信号")
    
    # 1. 整体（含分层维度）
    for h in [5, 10]:
        ret_key = f'ret_{h}d'
        valid = [r for r in results if ret_key in r]
        if not valid:
            continue
        
        print(f"\n  ─── 持有{h}日 ───")
        
        # 整体
        wins = [r for r in valid if r[ret_key] > 0]
        wr = len(wins) / len(valid) * 100
        avg = sum(r[ret_key] for r in valid) / len(valid)
        avg_w = sum(r[ret_key] for r in wins) / len(wins) if wins else 0
        avg_l = sum(r[ret_key] for r in [r for r in valid if r[ret_key] <= 0]) / len([r for r in valid if r[ret_key] <= 0]) if [r for r in valid if r[ret_key] <= 0] else 0
        pr = abs(avg_w / avg_l) if avg_l != 0 else float('inf')
        print(f"  整体: {len(valid)}次 涨率{wr:.1f}% 均{avg:+.2f}% 盈亏比{pr:.2f}")
        
        # 按板块主线状态分层
        for ml_label, ml_val in [('主线板块', True), ('非主线', False)]:
            group = [r for r in valid if r['is_mainline'] == ml_val]
            if group:
                gw = [r for r in group if r[ret_key] > 0]
                gwr = len(gw) / len(group) * 100
                gavg = sum(r[ret_key] for r in group) / len(group)
                print(f"    ├ {ml_label}: {len(group)}次 涨率{gwr:.1f}% 均{gavg:+.2f}%")
        
        # 按趋势分层
        for trend_label in ['up', 'down', 'range']:
            group = [r for r in valid if r['trend'] == trend_label]
            if group:
                gw = [r for r in group if r[ret_key] > 0]
                gwr = len(gw) / len(group) * 100
                gavg = sum(r[ret_key] for r in group) / len(group)
                trend_cn = {'up': '上涨', 'down': '下跌', 'range': '震荡'}.get(trend_label, trend_label)
                print(f"    ├ 趋势{trend_cn}: {len(group)}次 涨率{gwr:.1f}% 均{gavg:+.2f}%")
        
        # 交叉分层：主线 + 趋势
        for ml_label, ml_val in [('主线', True), ('非主线', False)]:
            for trend_label in ['up', 'down', 'range']:
                group = [r for r in valid if r['is_mainline'] == ml_val and r['trend'] == trend_label]
                if len(group) >= 3:
                    gw = [r for r in group if r[ret_key] > 0]
                    gwr = len(gw) / len(group) * 100
                    gavg = sum(r[ret_key] for r in group) / len(group)
                    trend_cn = {'up': '上涨', 'down': '下跌', 'range': '震荡'}.get(trend_label, trend_label)
                    print(f"    └ {ml_label}+{trend_cn}: {len(group)}次 涨率{gwr:.1f}% 均{gavg:+.2f}%")
    
    # 按置信度分层
    print(f"\n  置信度分层:")
    for tier in [(60, 70), (70, 80), (80, 90), (90, 101)]:
        tier_results = [r for r in results if tier[0] <= r['confidence'] < tier[1]]
        if tier_results:
            tier_5d = [r for r in tier_results if 'ret_5d' in r]
            if tier_5d:
                tw = [r for r in tier_5d if r['ret_5d'] > 0]
                twr = len(tw) / len(tier_5d) * 100
                tavg = sum(r['ret_5d'] for r in tier_5d) / len(tier_5d)
                ex = tier_5d[0]
                mc = len(set(r['code'] for r in tier_results))
                print(f"    {tier[0]}-{tier[1]}分: {len(tier_results)}次({mc}股) 涨率{twr:.1f}% 均{tavg:+.2f}%")
    
    return results


if __name__ == '__main__':
    print("=" * 60)
    print("  3L六大信号 — 结构分层回测 v2")
    print("=" * 60)
    
    stocks, mainline_history = load_all()
    print(f"  股票数: {len(stocks)}")
    print(f"  主线历史日期: {sorted(mainline_history.keys())[:5]}")
    
    # 只跑衰竭信号
    for signal_key in ['demand_exhaustion', 'supply_exhaustion']:
        signal_name = SIGNAL_NAMES.get(signal_key, signal_key)
        results = run_stratified_backtest(signal_key, stocks, mainline_history)
        print_stratified_stats(results, signal_name)
    
    print("\n" + "=" * 60)
