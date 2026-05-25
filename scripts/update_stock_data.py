#!/usr/bin/env python3
"""
唯一数据更新脚本 — 17:00 cron 运行
范围 = watchlist 自选股，全量更新K线数据
所有文件I/O通过 backend.core.data_layer 完成

用法:
    python3 scripts/update_stock_data.py
"""

import json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR
from backend.core.data_layer import (
    get_watchlist,
    load_all_stocks_uncached,
    get_last_updated,
    get_industry_map,
    save_all_stocks,
)

CACHE_DIR = os.path.join(DATA_DIR, '.cache')


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {msg}')


def _get_stock_name(code):
    """从腾讯API获取股票名称"""
    market = 'sz' if code.startswith(('0', '3')) else 'sh'
    try:
        import requests
        r = requests.get(
            f'https://qt.gtimg.cn/q={market}{code}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=5,
        )
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
    except Exception:
        pass
    return None


def fetch_klines_from_mootdx(client, code, count=800):
    """从mootdx拉取日K线"""
    try:
        bars = client.bars(symbol=code, frequency=9, start=0, count=count, fq=True)
        if bars is None or len(bars) == 0:
            return []
        records = []
        for _, row in bars.iterrows():
            records.append({
                'date': row['datetime'][:10].replace('-', ''),
                'open': round(float(row['open']), 2),
                'close': round(float(row['close']), 2),
                'high': round(float(row['high']), 2),
                'low': round(float(row['low']), 2),
                'volume': int(float(row['volume'])) * 100,  # mootdx单位为手(100股)，转股
            })
        return records
    except Exception:
        return []


def _flatten_stocks(sector_map):
    """{sector: {code: [klines]}} → {code: {sector, klines, name}}"""
    result = {}
    for sector, codes in sector_map.items():
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            result[code] = {'sector': sector, 'klines': klines, 'name': name}
    return result


def main():
    t0 = time.time()

    # 1. 读watchlist（通过 data_layer）
    wl = get_watchlist()
    codes = sorted(set(
        s.get('code', '')[-6:] for s in wl if s.get('code')
    ))
    if not codes:
        log('⚠️ 自选股列表为空，跳过')
        return
    log(f'📋 自选股共 {len(codes)} 只')

    # 2. 加载现有数据（不走缓存，要最新）
    existing_sector_map = load_all_stocks_uncached()
    existing = _flatten_stocks(existing_sector_map)
    last_updated = get_last_updated()
    log(f'📂 现有数据: {len(existing)} 只, 上次更新: {last_updated or "无"}')

    # 3. 加载行业映射
    industry_map = get_industry_map()
    log(f'🗺️  行业映射: {len(industry_map)} 只')

    # 4. 连接mootdx
    from mootdx.quotes import Quotes
    client = Quotes.factory(market='std')

    # 5. 确定最新交易日
    today_str = datetime.now().strftime('%Y%m%d')
    if codes:
        sample = client.bars(symbol=codes[0], frequency=9, start=0, count=3)
        if sample is not None and len(sample) > 0:
            latest_mootdx = sample.iloc[-1]['datetime'][:10].replace('-', '')
        else:
            latest_mootdx = today_str
    else:
        latest_mootdx = today_str
    log(f'📡 mootdx最新: {latest_mootdx}')

    # 6. 判断是否需要更新
    need_update = False
    for code in codes:
        if code not in existing:
            need_update = True
            break
    if not need_update and last_updated and latest_mootdx <= last_updated.replace('-', ''):
        log('✅ 已最新，跳过')
        return

    # 7. 清除缓存
    cache_path = os.path.join(CACHE_DIR, 'all_stocks.json')
    try:
        os.remove(cache_path)
    except (FileNotFoundError, OSError):
        pass

    # 8. 逐只更新
    updated = 0
    new_added = 0
    names_fixed = 0

    for code in codes:
        try:
            records = fetch_klines_from_mootdx(client, code)
            if not records:
                continue

            if code in existing:  # 已有股票，追最新日
                klines = existing[code]['klines']
                seen = {k['date'] for k in klines}
                has_new = False
                for r in records:
                    if r['date'] > (last_updated or '').replace('-', ''):
                        if r['date'] not in seen:
                            klines.append(r)
                            has_new = True
                if has_new:
                    klines.sort(key=lambda x: x['date'])
                    while len(klines) > 60:
                        klines.pop(0)
                    updated += 1
            else:  # 新股票，拉60天
                name = None
                im = industry_map.get(code, {})
                if isinstance(im, dict):
                    name = im.get('name', '')
                if not name:
                    name = _get_stock_name(code)
                    if name:
                        names_fixed += 1

                records = records[-60:]
                for r in records:
                    r['name'] = name or code

                ths_industry = '未知'
                if isinstance(im, dict) and im.get('ths_industry'):
                    ths_industry = im['ths_industry']

                existing[code] = {
                    'sector': ths_industry,
                    'klines': records,
                    'name': name or code,
                }
                new_added += 1
        except Exception as e:
            log(f'  ⚠️ {code}: {e}')

    # 9. 组装输出
    sector_map = {}
    for code, info in existing.items():
        if code in codes:
            sec = info.get('sector', '未知')
            if sec not in sector_map:
                sector_map[sec] = {}
            klines = info['klines']
            name = info.get('name', '')
            if name and klines:
                for k in klines:
                    k['name'] = name
            klines.sort(key=lambda x: x['date'])
            while len(klines) > 60:
                klines.pop(0)
            sector_map[sec][code] = klines

    # 10. 原子保存（通过 data_layer）
    save_all_stocks(sector_map, last_updated=latest_mootdx)

    elapsed = time.time() - t0
    log(f'✅ 完成: {updated}只更新, {new_added}只新增, {names_fixed}只补名')
    log(f'⏱️  耗时 {elapsed:.1f}s, 共{len(codes)}只')


if __name__ == '__main__':
    main()
