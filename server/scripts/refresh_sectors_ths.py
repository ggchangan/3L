#!/usr/bin/env python3
"""全量从同花顺THS重拉行业+概念板块K线，统一数据源

用法：
    cd /home/ubuntu/3l-server/server && python3 scripts/refresh_sectors_ths.py

流程：
    1. 备份现有 sector_daily.json → sector_daily.ths.backup.YYYYMMDD.json
    2. 获取同花顺行业列表（90个）+ 概念列表（~371个）
    3. 逐批拉取 K 线（10并发，每批20个存一次）
    4. 保留现有 _push2test 快照
    5. 保存统一后的数据到 sector_daily.json

设计文档：docs/data-source-unification/design.md
"""
import sys, os, time, json, copy
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ['TQDM_DISABLE'] = '1'
os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

import akshare as ak
from datetime import datetime, timedelta

from backend.core.config import DATA_DIR, SECTOR_DAILY_PATH
from backend.core.data_layer import load_sector_daily_uncached, save_sector_daily
from backend.core.update_stock_data import _df_to_kline

# ── 参数 ──
MAX_WORKERS = 10            # 并发数
MAX_K = 300                 # 最多保留K线数（约1年交易日足够）
BATCH_SAVE_INTERVAL = 20    # 每拉20个保存一次
START_DATE = '20250101'     # 起始日期（2025年起，够用）
TIME_BETWEEN = 0.2          # 并发批次内单次延迟


def backup_existing():
    """备份现有 sector_daily.json"""
    src = SECTOR_DAILY_PATH
    if not os.path.isfile(src):
        print(f'[备份] 文件不存在，跳过备份: {src}')
        return None
    today = datetime.now().strftime('%Y%m%d')
    backup_path = os.path.join(os.path.dirname(src), f'sector_daily.ths.backup.{today}.json')
    import shutil
    shutil.copy2(src, backup_path)
    size = os.path.getsize(backup_path)
    print(f'[备份] ✅ {backup_path} ({size/1024:.0f}KB)')
    return backup_path


def get_ths_names():
    """获取同花顺行业（90个）和概念（~371个）列表"""
    t0 = time.time()
    print('[名称] 获取同花顺行业列表...', flush=True)
    ind_df = ak.stock_board_industry_name_ths()
    ind_names = list(ind_df['name'])
    print(f'[名称] 行业: {len(ind_names)} 个 ({time.time()-t0:.0f}s)', flush=True)

    print('[名称] 获取同花顺概念列表...', flush=True)
    con_df = ak.stock_board_concept_name_ths()
    con_names = list(con_df['name'])
    print(f'[名称] 概念: {len(con_names)} 个 ({time.time()-t0:.0f}s)', flush=True)

    return ind_names, con_names


def fetch_kline(name: str, stype: str) -> tuple:
    """拉取单个板块的 K 线，返回 (name, stype, klines_or_None)"""
    try:
        start = START_DATE
        today = datetime.now().strftime('%Y%m%d')
        if stype == 'industry':
            df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=today)
        else:
            df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=today)
        if df is None or len(df) == 0:
            return (name, stype, None)
        klines = _df_to_kline(df)
        if not klines:
            return (name, stype, None)
        if len(klines) > MAX_K:
            klines = klines[-MAX_K:]
        return (name, stype, klines)
    except Exception as e:
        return (name, stype, None)


def batch_fetch(names, stype, total):
    """并发拉取一批 K 线，返回 {name: klines}"""
    result = {}
    errors = 0
    t0 = time.time()
    loop_i = 0

    # 分批并发
    for batch_start in range(0, len(names), MAX_WORKERS):
        batch = names[batch_start:batch_start + MAX_WORKERS]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(fetch_kline, name, stype): name for name in batch}
            for future in as_completed(futures):
                loop_i += 1
                name = futures[future]
                try:
                    fname, ftype, klines = future.result()
                except Exception as e:
                    errors += 1
                    print(f'  [{loop_i}/{total}] {name} ❌ 异常: {str(e)[:60]}', flush=True)
                    continue
                if klines is not None and len(klines) > 0:
                    result[name] = klines
                    if klines[-1].get('date', '').startswith('2026'):
                        status = '✅'
                    else:
                        status = '⚠️'
                else:
                    errors += 1
                    status = '❌'

                if loop_i % 10 == 0 or status in ('❌', '⚠️'):
                    print(f'  [{loop_i}/{total}] {name} ({ftype}) {status} {len(klines) if klines else 0}条 ({time.time()-t0:.0f}s)', flush=True)

        # 批次间延迟
        time.sleep(TIME_BETWEEN)

    return result, errors


def main():
    print('═' * 60)
    print('  全量同花顺THS K线重拉脚本')
    print(f'  开始时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print('═' * 60)
    t0 = time.time()

    # 1. 备份
    backup_path = backup_existing()

    # 2. 读取现有 _push2test（保留）
    existing = load_sector_daily_uncached() or {}
    push2test = existing.get('_push2test', {})
    push2test_updated = existing.get('_push2test_updated', '')
    print(f'[现有] _push2test: 行业{len(push2test.get("industries", {}))}个, 概念{len(push2test.get("concepts", {}))}个')

    # 3. 获取 THS 名称列表
    ind_names, con_names = get_ths_names()
    total = len(ind_names) + len(con_names)
    print(f'[名称] 共计 {total} 个板块')

    # 4. 拉取行业 K 线
    print('\n[拉取] ═══ 行业 K 线 ═══')
    industries, ind_err = batch_fetch(ind_names, 'industry', total)

    # 5. 拉取概念 K 线
    print('\n[拉取] ═══ 概念 K 线 ═══')
    concepts, con_err = batch_fetch(con_names, 'concept', total)

    # 6. 确定最新日期
    all_dates = set()
    for _, klines in industries.items():
        if klines:
            all_dates.add(klines[-1]['date'])
    for _, klines in concepts.items():
        if klines:
            all_dates.add(klines[-1]['date'])
    latest = max(all_dates) if all_dates else datetime.now().strftime('%Y%m%d')

    # 7. 组装保存
    output = {
        'last_updated': latest,
        'industries': industries,
        'concepts': concepts,
    }
    if push2test:
        output['_push2test'] = push2test
        output['_push2test_updated'] = push2test_updated or latest

    save_sector_daily(output)

    elapsed = time.time() - t0
    print()
    print('═' * 60)
    print(f'  ✅ 完成! 耗时 {elapsed:.0f}s')
    print(f'  行业: {len(industries)} 个 (失败 {ind_err})')
    print(f'  概念: {len(concepts)} 个 (失败 {con_err})')
    print(f'  最新日期: {latest}')
    if industries:
        sample = list(industries.keys())[:3]
        print(f'  行业样例: {sample}')
        for s in sample:
            print(f'    {s}: {len(industries[s])} 条, 最新 {industries[s][-1]["date"]}')
    if concepts:
        sample = list(concepts.keys())[:3]
        print(f'  概念样例: {sample}')
        for s in sample:
            print(f'    {s}: {len(concepts[s])} 条, 最新 {concepts[s][-1]["date"]}')
    print(f'  备份: {backup_path}')
    print('═' * 60)


if __name__ == '__main__':
    main()
