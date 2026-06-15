#!/usr/bin/env python3
"""刷新行业+概念板块日K线数据：清旧数据 → 拉最新200条 → 保存"""
import sys, os, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TQDM_DISABLE'] = '1'
os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

import akshare as ak
from backend.data_access.data_layer import save_sector_daily
from backend.core.update_stock_data import _df_to_kline

MAX_K = 60  # 最多保留60根K线（约3个月，足够20日涨幅计算）

def refresh():
    t0 = time.time()
    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
    
    # 1. 获取名称列表
    print('[1] 获取行业名称...', flush=True)
    ind_names = list(ak.stock_board_industry_name_ths()['name'])
    print(f'    行业: {len(ind_names)} 个', flush=True)
    
    print('[2] 获取概念名称...', flush=True)
    con_names = list(ak.stock_board_concept_name_ths()['name'])
    print(f'    概念: {len(con_names)} 个', flush=True)
    
    all_names = [(n, 'industry') for n in ind_names] + [(n, 'concept') for n in con_names]
    total = len(all_names)
    print(f'    合计: {total} 个', flush=True)
    
    # 2. 分批拉取
    industries = {}
    concepts = {}
    errors = 0
    
    for i, (name, stype) in enumerate(all_names):
        try:
            df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=today) if stype == 'industry' else ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=today)
            if df is None or len(df) == 0:
                errors += 1
                continue
            
            klines = _df_to_kline(df)
            if len(klines) > MAX_K:
                klines = klines[-MAX_K:]
            
            if stype == 'industry':
                industries[name] = klines
            else:
                concepts[name] = klines
            
            if (i + 1) % 20 == 0:
                save_sector_daily({'last_updated': klines[-1]['date'] if klines else '', 'industries': industries, 'concepts': concepts})
            
            elapsed = time.time() - t0
            print(f'  [{i+1}/{total}] {name} ({stype}) ✅ {len(klines)}条 ({elapsed:.0f}s)', flush=True)
            
        except Exception as e:
            errors += 1
            elapsed = time.time() - t0
            print(f'  [{i+1}/{total}] {name} ❌ {str(e)[:60]} ({elapsed:.0f}s)', flush=True)
    
    # 3. 最终保存
    all_dates = set()
    for n, k in industries.items():
        if k: all_dates.add(k[-1]['date'])
    for n, k in concepts.items():
        if k: all_dates.add(k[-1]['date'])
    latest = max(all_dates) if all_dates else ''
    
    save_sector_daily({'last_updated': latest, 'industries': industries, 'concepts': concepts})
    
    elapsed = time.time() - t0
    print(f'\n完成! 耗时{elapsed:.0f}s', flush=True)
    print(f'行业: {len(industries)} 个, 概念: {len(concepts)} 个, 失败: {errors}, 最新日期: {latest}', flush=True)

if __name__ == '__main__':
    refresh()
