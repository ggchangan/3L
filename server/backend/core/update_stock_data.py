#!/usr/bin/env python3
"""
唯一数据更新脚本 — 17:00 cron 运行
范围 = 个股K线 + 中证全指 + 行业/概念板块日K线
所有文件I/O通过 backend.data_access.data_layer 完成

用法:
    python3 scripts/update_stock_data.py
"""

import json, os, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# ⚠️ 注意: file 在 server/backend/core/ 下
# dirname×1=core/  ×2=backend/  ×3=server/（backend 包所在位置）
from backend.core.config import DATA_DIR, ALL_CODES_PATH, CONCEPT_LIST_PATH
from backend.data_access.data_layer import (
    get_watchlist,
    load_all_stocks_uncached,
    get_last_updated,
    get_industry_map,
    save_industry_map,
    save_all_stocks,
    load_index_data_uncached,
    save_index_data,
    INDEX_CODES,
    fetch_stock_klines_from_db,
    get_stock_names_from_db,
    get_stock_daily_latest_date,
    fetch_index_klines_from_akshare,
    update_trade_cal_from_tushare,
)
from backend.data_access.data_layer import (
    get_concept_list,
    get_stock_concept_map,
    save_concept_list,
    save_stock_concept_map,
)

CACHE_DIR = os.path.join(DATA_DIR, '.cache')


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {msg}')


# ════════════════════════════════════════════════════════════════
# 个股
# ════════════════════════════════════════════════════════════════

def _get_stock_name(code):
    """通过腾讯接口获取股票名称"""
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
        log('获取股票名称失败')
        pass
    return None


def _flatten_stocks(sector_map):
    """{sector: {code: [klines]}} → {code: {sector, klines, name}}"""
    result = {}
    for sector, codes in sector_map.items():
        if not isinstance(codes, dict):
            continue
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            result[code] = {'sector': sector, 'klines': klines, 'name': name}
    return result


def update_stocks():
    """更新个股K线 — 从 stock_daily DB 批量拉取，不再用 mootdx"""
    wl = get_watchlist()
    codes = sorted(set(
        s.get('code', '')[-6:] for s in wl if s.get('code')
    ))
    if not codes:
        log('⚠️  自选股列表为空，跳过个股更新')
        return (0, 0, 0)

    industry_map = get_industry_map()
    existing_sector_map = load_all_stocks_uncached()
    existing = _flatten_stocks(existing_sector_map)
    last_updated = get_last_updated()
    db_latest = get_stock_daily_latest_date()

    # 判断是否需要更新
    need_update = False
    for code in codes:
        if code not in existing:
            need_update = True
            break
    if not need_update and last_updated and db_latest:
        if db_latest <= last_updated.replace('-', ''):
            log('✅  个股数据已最新，跳过')
            return (0, 0, 0)

    # 从 stock_daily 批量拉取最新60天K线
    klines_map = fetch_stock_klines_from_db(codes, limit=60)
    name_map = get_stock_names_from_db(codes)

    # 清除缓存
    try:
        os.remove(os.path.join(CACHE_DIR, 'all_stocks.json'))
    except (FileNotFoundError, OSError):
        pass

    updated = 0
    new_added = 0
    names_fixed = 0

    for code in codes:
        klines = klines_map.get(code, [])
        if not klines:
            log(f'  ⚠️ {code}: 无K线数据')
            continue

        if code in existing:
            existing_dates = {k['date'] for k in existing[code]['klines']}
            has_new = any(k['date'] not in existing_dates for k in klines)
            if has_new:
                existing[code]['klines'] = sorted(klines, key=lambda x: x['date'])[-60:]
                updated += 1
        else:
            im = industry_map.get(code, {})
            if isinstance(im, dict):
                name = im.get('name', '') or name_map.get(code, '')
            else:
                name = name_map.get(code, '')
            if not name:
                name = _get_stock_name(code)
                if name:
                    names_fixed += 1

            klines = sorted(klines, key=lambda x: x['date'])[-60:]
            for r in klines:
                r['name'] = name or code

            ths_industry = '未知'
            if isinstance(im, dict) and im.get('ths_industry'):
                ths_industry = im['ths_industry']

            existing[code] = {
                'sector': ths_industry,
                'klines': klines,
                'name': name or code,
            }
            new_added += 1

    # 组装 sector_map
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

    save_all_stocks(sector_map, last_updated=db_latest)
    stats = f'{updated}只更新, {new_added}只新增, {names_fixed}只补名'
    log(f'📈  个股: {stats}')
    return (updated, new_added, names_fixed)


# ════════════════════════════════════════════════════════════════
# 指数（中证全指 000985 + 上证 000001 + 科创50 000688）
# ════════════════════════════════════════════════════════════════

def _df_to_kline(df):
    """akshare DataFrame → [{date, open, close, high, low, volume}]
    兼容中英文列名（akshare 不同接口用不同语言）
    """
    records = []
    # 列名映射：中/英 → 标准键
    col_map = {
        '日期': 'date', 'date': 'date',
        '开盘价': 'open', 'open': 'open',
        '收盘价': 'close', 'close': 'close',
        '最高价': 'high', 'high': 'high',
        '最低价': 'low', 'low': 'low',
        '成交量': 'volume', 'volume': 'volume',
        '成交额': 'amount', 'amount': 'amount',
    }
    # 找到存在的列
    present = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if col_lower in col_map:
            present[col_map[col_lower]] = col

    for _, row in df.iterrows():
        r = {}
        # 日期
        date_col = present.get('date')
        if date_col:
            raw = str(row[date_col])
            r['date'] = raw[:10].replace('-', '') if '-' in raw else raw[:8]
        else:
            continue

        # OHL
        for key in ('open', 'close', 'high', 'low'):
            col = present.get(key)
            if col:
                try:
                    r[key] = round(float(row[col]), 2)
                except (ValueError, TypeError):
                    r[key] = 0.0
            else:
                r[key] = 0.0

        # 成交量：优先 volume，其次 amount 转股（指数/板块用股数），都没有则0
        vol_col = present.get('volume')
        if vol_col:
            try:
                r['volume'] = int(float(row[vol_col]))
            except (ValueError, TypeError):
                r['volume'] = 0
        else:
            amt_col = present.get('amount')
            if amt_col:
                # 成交额(元) 无法精确转股数，记0
                r['volume'] = 0
            else:
                r['volume'] = 0

        if 'date' in r and r['date']:
            records.append(r)
    return records


def update_index():
    """更新所有指数日K线（通过 data_layer 封装，不再直接调 akshare）"""
    existing = load_index_data_uncached()
    indices = existing.get('indices', {})
    total_added = 0
    last_date = existing.get('last_updated', '')

    for code, name in INDEX_CODES.items():
        info = indices.get(code, {'name': name, 'klines': []})
        existing_klines = info.get('klines', [])
        existing_dates = {k['date'] for k in existing_klines}

        new_klines = fetch_index_klines_from_akshare(code)

        if not new_klines:
            log(f'⚠️  {name}({code})数据为空' if len(existing_klines) == 0 else '')
            continue

        added = 0
        for k in new_klines:
            if k['date'] not in existing_dates:
                existing_klines.append(k)
                added += 1

        if added > 0:
            existing_klines.sort(key=lambda x: x['date'])
            if len(existing_klines) > 200:
                existing_klines = existing_klines[-200:]
            last_kline = existing_klines[-1]
            if last_kline['date'] > last_date:
                last_date = last_kline['date']
            log(f'📈  {name}: {added}条新增, 最新{last_kline["date"]}')

        indices[code] = {'name': name, 'klines': existing_klines}
        total_added += added

    if total_added == 0:
        log('✅  指数数据已最新')
    else:
        log(f'📈  指数合计: {total_added}条新增, 最新{last_date}')

    existing['indices'] = indices
    existing['last_updated'] = last_date or existing.get('last_updated', '')
    save_index_data(existing)
    return (total_added, last_date)


# ════════════════════════════════════════════════════════════════
# 板块（行业+概念）
# ════════════════════════════════════════════════════════════════

# ── push2test 常量（主数据源：东财测试API，实测可用） ──
_PUSH2TEST_URL = 'https://push2test.eastmoney.com/api/qt/clist/get'
_PUSH2TEST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/',
}
_PUSH2TEST_UT = 'bd1d9ddb04089700cf9c27f6f7426281'
_SECTOR_FS = {'industry': 'm:90+t:2', 'concept': 'm:90+t:3'}


def _fetch_board_names_from_push2test(sector_type):
    """从 push2test 获取板块名称列表
    sector_type: 'industry' | 'concept'
    返回 [name, ...]，失败返回 []
    """
    import requests as _req
    fs = _SECTOR_FS.get(sector_type)
    if not fs:
        return []
    params = {
        'pn': '1', 'pz': '2000', 'po': '1', 'np': '1',
        'ut': _PUSH2TEST_UT, 'fltt': '2', 'invt': '2',
        'fs': fs, 'fields': 'f14',
    }
    try:
        r = _req.get(_PUSH2TEST_URL, params=params, headers=_PUSH2TEST_HEADERS, timeout=15)
        items = r.json().get('data', {}).get('diff', [])
        names = [(item.get('f14') or '').strip() for item in items if item.get('f14')]
        log(f'  push2test[{sector_type}]: {len(names)}个板块名')
        return names
    except Exception as e:
        log(f'❌ push2test[{sector_type}] 板块列表失败: {type(e).__name__}: {e}')
        return []


def _fetch_today_industries_from_ths():
    """【行业主源】从同花顺获取行业板块今日实时涨跌幅

    数据源: stock_board_industry_summary_ths()
    同花顺行业数据一直稳定好用，90个行业一次返回。
    字段: 涨跌幅、总成交量、总成交额、净流入、上涨/下跌家数、领涨股
    返回 {name: {date, change_pct, ...}}，全部失败返回 {}
    """
    try:
        import os
        os.environ['TQDM_DISABLE'] = '1'
        import akshare as ak

        df = ak.stock_board_industry_summary_ths()
        # 目标日期是上一个已完成交易日（交易日历含节假日）
        from backend.data_access.data_source import get_last_completed_trading_day
        today = get_last_completed_trading_day()

        result = {}
        for _, row in df.iterrows():
            name = str(row.get('板块', '')).strip()
            chg = row.get('涨跌幅', None)
            up = row.get('上涨家数', None)
            down = row.get('下跌家数', None)
            vol = row.get('总成交量', None)
            amt = row.get('总成交额', None)
            net = row.get('净流入', None)
            leader = row.get('领涨股', None)
            leader_chg = row.get('领涨股-涨跌幅', None)
            if name and chg is not None:
                result[name] = {
                    'date': today,
                    'change_pct': round(float(chg), 2),
                    'up_count': int(up) if up is not None else None,
                    'down_count': int(down) if down is not None else None,
                    'volume': float(vol) if vol is not None else None,
                    'amount': float(amt) if amt is not None else None,
                    'net_flow': float(net) if net is not None else None,
                    'leader': str(leader) if leader else '',
                    'leader_chg': round(float(leader_chg), 2) if leader_chg is not None else None,
                }

        log(f'  THS[industry]: 成功获取{len(result)}个行业（同花顺主源，含涨跌幅/上涨下跌家数/领涨股）')
        return result
    except Exception as e:
        log(f'❌ THS行业数据获取失败: {type(e).__name__}: {e}')
        return {}


def _fetch_today_sectors_from_push2test(sector_type, name_list):
    """【概念主源】从 push2test.eastmoney.com 批量获取概念板块今日实时数据
    sector_type: 'industry' | 'concept'
    name_list: 板块名称列表（仅用于日志，实际拉全量再过滤）
    返回 {name: {date, open, close, high, low, volume}}，全部失败则返回 {}
    """
    import requests as _req

    fs = _SECTOR_FS.get(sector_type)
    if not fs:
        log(f'❌ _fetch_today_sectors_from_push2test: 未知板块类型 {sector_type}')
        return {}

    today = datetime.now().strftime('%Y%m%d')
    # 非交易日回退到上一个交易日
    d = datetime.now()
    for _ in range(7):
        if d.weekday() < 5:
            today = d.strftime('%Y%m%d')
            break
        d -= timedelta(days=1)
    params = {
        'pn': '1', 'pz': '2000', 'po': '1', 'np': '1',
        'ut': _PUSH2TEST_UT, 'fltt': '2', 'invt': '2',
        'fs': fs,
        'fields': 'f2,f12,f14,f15,f16,f17,f18,f5,f6',
    }

    try:
        r = _req.get(_PUSH2TEST_URL, params=params, headers=_PUSH2TEST_HEADERS, timeout=20)
        items = r.json().get('data', {}).get('diff', [])
    except Exception as e:
        log(f'❌ push2test板块列表请求失败 [{sector_type}]: {type(e).__name__}: {e}')
        return {}

    # 建立 name → 数据的映射
    name_map = {}
    for item in items:
        name = (item.get('f14') or '').strip()
        if name and name in name_list:
            # 归一化名称：去掉东财的Ⅱ/Ⅲ/D后缀，对齐 legacy 命名
            clean = name.replace('Ⅱ', '').replace('Ⅲ', '').replace('D', '').strip()
            close = float(item.get('f2', 0) or 0)
            high = float(item.get('f15', close) or close)
            low = float(item.get('f16', close) or close)
            open_ = float(item.get('f17', close) or close)
            volume = int(float(item.get('f5', 0) or 0))
            change_pct = float(item.get('f3', 0) or 0)   # 当日涨跌幅%
            prev_close = float(item.get('f18', 0) or 0)   # 昨收
            name_map[clean] = {
                'date': today,
                'open': round(open_, 2),
                'close': round(close, 2),
                'high': round(high, 2),
                'low': round(low, 2),
                'volume': volume,
                'change_pct': round(change_pct, 2),
                'prev_close': round(prev_close, 2),
            }

    hit_rate = len(name_map) / len(name_list) * 100 if name_list else 0
    log(f'  push2test[{sector_type}]: 命中{len(name_map)}/{len(name_list)} ({hit_rate:.0f}%)')
    return name_map


def _upsert_klines_to_db(names_with_type, today):
    """从 akshare 拉板块K线，计算 pct_chg，upsert 到 ths_daily DB

    Args:
        names_with_type: [(name, stype), ...]  stype='industry'|'concept'
        today: YYYYMMDD

    Returns:
        (写入行数, 请求板块数)
    """
    import akshare as ak
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from backend.data_access.tushare_db import TushareDB

    LOOKBACK_DAYS = 5
    start = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime('%Y%m%d')

    # 建 name → ts_code 映射 + name → stype 映射
    db = TushareDB()
    name_code_map = {}
    name_type_map = {}
    for name, stype in names_with_type:
        ts_code = db.query_ths_code_by_name(name)
        if ts_code:
            name_code_map[name] = ts_code
            name_type_map[name] = stype

    if not name_code_map:
        return (0, 0)

    def _fetch_one(name):
        try:
            stype = name_type_map[name]
            if stype == 'industry':
                df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=today)
            else:
                df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=today)
            if df is None or df.empty:
                return name, []
            return name, _df_to_kline(df)
        except Exception:
            return name, []

    records = []
    names_to_fetch = list(name_code_map.keys())
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_one, n): n for n in names_to_fetch}
        for future in as_completed(futures):
            name, klines = future.result()
            if not klines:
                continue
            ts_code = name_code_map[name]
            klines.sort(key=lambda x: x['date'])  # 旧→新，算 pct_chg
            for i, k in enumerate(klines):
                prev_close = klines[i - 1]['close'] if i > 0 else 0
                pct = round((k['close'] - prev_close) / prev_close * 100, 2) if prev_close else 0
                records.append({
                    'ts_code': ts_code,
                    'trade_date': k['date'],
                    'open': k.get('open', 0),
                    'high': k.get('high', 0),
                    'low': k.get('low', 0),
                    'close': k.get('close', 0),
                    'vol': k.get('volume', 0),
                    'pct_chg': pct,
                })

    if not records:
        return (0, len(names_to_fetch))

    written = db.upsert_many_from_dicts('ths_daily', records)
    log(f'  写入 ths_daily: {written}条 (请求{len(names_to_fetch)}个板块)')
    return (written, len(names_to_fetch))


def update_sectors():
    """更新行业+概念板块日K线

    数据源：
    - 行业（industries）：同花顺 THS（stock_board_industry_summary_ths）
    - 概念（concepts）：同花顺 THS（stock_board_concept_info_ths）

    失败率>50%告警，全部失败抛异常
    """
    import warnings
    warnings.filterwarnings('ignore')

    # 非交易日跳过（push2test 返回的是旧缓存，不可信）
    now = datetime.now()
    if now.weekday() >= 5:
        log('⏭️  非交易日，跳过板块更新')
        return (0, 0)

    # 目标日期是上一个已完成交易日
    from backend.data_access.data_source import get_last_completed_trading_day
    today = get_last_completed_trading_day()
    log(f'📋  目标日期: {today}')

    # ── 确定追踪中的概念 ──
    try:
        _concept_list = get_concept_list()
        _stock_concept_map = get_stock_concept_map()
        wl = get_watchlist()
        wl_codes = set(s.get('code', '') for s in wl)

        tracked_concepts = set()
        for code, cinfo in _concept_list.items():
            name = cinfo.get('name', '')
            if not name:
                continue
            related = 0
            for scode, sinfo in _stock_concept_map.items():
                if code in sinfo.get('concept_codes', []) and scode in wl_codes:
                    related += 1
            if related >= 6:
                tracked_concepts.add(name)

        log(f'📋  追踪概念: {len(tracked_concepts)}个（自选股关联≥6只）')
    except Exception as e:
        log(f'⚠️  计算追踪概念失败: {e}，回退到全量更新')
        tracked_concepts = set()

    # ── 行业今日快照 ──
    ind_today = _fetch_today_industries_from_ths()

    # ── 概念今日快照 ──
    from backend.data_access.data_layer import get_concept_snapshots
    con_today = get_concept_snapshots(list(tracked_concepts))

    ind_saved = len(ind_today)
    con_saved = len(con_today)

    # ── 失败率分析 ──
    if len(ind_today) == 0:
        log('🚨 行业板块从同花顺 THS 获取全部失败！')

    con_tracked = len(tracked_concepts)
    con_miss = con_tracked - len(con_today)
    if con_tracked > 0 and con_miss / con_tracked > 0.5:
        log(f'🚨 概念板块大面积获取失败: {con_miss}/{con_tracked}({con_miss/con_tracked*100:.0f}%)')

    # ── 构建要更新的板块列表 ──
    names_to_update = []
    for name in ind_today:
        names_to_update.append((name, 'industry'))
    for name in tracked_concepts:
        if name not in ind_today:
            names_to_update.append((name, 'concept'))

    # ── 写 K 线到 ths_daily DB ──
    try:
        written, requested = _upsert_klines_to_db(names_to_update, today)
        log(f'📊  板块K线写入DB: {written}条 (请求{requested}个板块)')
    except Exception as e:
        log(f'🚨 板块K线写入DB失败: {e}')
        import traceback
        for line in traceback.format_exc().splitlines():
            log(f'  {line}')

    stats = f'push2test: 行业{ind_saved}条, 概念{con_saved}条 (THS旧数据保留不变)'
    log(f'📈  板块: {stats}')

    # ── 板块数据验证 ──
    try:
        from backend.data_access.data_layer import verify_data_sources
        vresult = verify_data_sources(verbose=False)
        vpass = vresult['pass_count'] if 'pass_count' in vresult else sum(1 for c in vresult['checks'] if c['pass'])
        vtotal = len(vresult['checks'])
        if vresult['status'] == 'pass':
            log(f'✅  数据源验证通过: {vpass}/{vtotal}')
        else:
            fails = [c for c in vresult['checks'] if not c['pass']]
            log(f'⚠️  数据源验证: {vpass}/{vtotal}, 失败项: {[c["check"] for c in fails]}')
    except Exception as e:
        log(f'⚠️  数据源验证异常: {e}')

    return (ind_saved, con_saved)


# ════════════════════════════════════════════════════════════════
# 行业映射（push2test.eastmoney.com → 申万二级行业）
# ════════════════════════════════════════════════════════════════

def _normalize_industry(name):
    """去掉申万二级分类的'Ⅱ'后缀（如'电机Ⅱ'→'电机'）"""
    if not name:
        return name
    return name.replace('Ⅱ', '').strip()

def update_industry_map():
    """从 push2test 拉全量A股行业映射，写入 stock_industry_map.json

    数据源：push2test.eastmoney.com → f100=申万二级行业名
    格式：{code: {code, name, ths_industry}}
    返回：写入的股票数量
    """
    import requests as _requests

    url = 'https://push2test.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': '1', 'pz': '6000',
        'po': '1', 'np': '1',
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': '2', 'invt': '2',
        'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
        'fields': 'f12,f14,f100',
    }
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://quote.eastmoney.com/',
    }

    try:
        r = _requests.get(url, params=params, headers=headers, timeout=30)
        data = r.json()
        items = data.get('data', {}).get('diff', [])
        if not items:
            log(f'⚠️  push2test返回空数据: {data.get("data","?")}')
            return 0
    except Exception as e:
        log(f'⚠️  push2test请求失败: {e}')
        return 0

    result = {}
    for item in items:
        code = item.get('f12', '')
        name = (item.get('f14', '') or '').strip()
        industry = _normalize_industry(item.get('f100', ''))
        if code and name and industry and industry != '-':
            result[code] = {'code': code, 'name': name, 'ths_industry': industry}

    if result:
        save_industry_map(result)
        log(f'🏭  行业映射: 已全量更新 ({len(result)}只, {len(items)-len(result)}只无行业)')
    return len(result)


# ════════════════════════════════════════════════════════════════
# 概念板块映射（stock→concept + concept→stocks）
# ════════════════════════════════════════════════════════════════

def update_concept_maps():
    """
    概念板块映射 — 稳定版（东方财富 push2test f103 + 名称映射）

    数据源:
      - 概念名/代码: 同花顺（已缓存至 map/concept_list.json）
      - 成分股归属: 东方财富 push2test f103（稳定可用）
      - 名称匹配: 映射表（EM 名 → THS 名）

    map/concept_list.json:  {concept_code: {name, stock_count, stocks: [code,...]}}
    map/stock_concept.json: {stock_code: {code, name, concept_codes, concept_names}}
    """
    import json as _json
    try:
        t0 = time.time()

        # ── 手动名称映射表 ────────────────────────────────
        # 东方财富 f103 概念名 → 同花顺概念名
        # 处理两数据源命名体系不同的情况
        MANUAL = {
            'CPO概念': '共封装光学(CPO)',
            '东数西算': '东数西算(算力)',
            '算力概念': '东数西算(算力)',
            '光刻机(胶)': '光刻机',
            '光通信模块': '光纤概念',
            'AIPC': 'AI PC',
            '车联网(路云)': '车联网(车路协同)',
            '数据中心': '数据中心(AIDC)',
            '新型烟草(电子烟)': '新型烟草(电子烟)',
            '国产芯片': '芯片概念',
            '新能源汽车': '新能源车',
            '国企改革': '央国企改革',
            '央企国企改革': '央国企改革',
            '时空大数据': '大数据',
            '白酒': '白酒概念',
            '流感': '禽流感',
        }

        # ── 第一步：加载缓存的概念名列表 ─────────────────
        log('🗺️  加载概念板块列表（缓存）...')
        try:
            with open(CONCEPT_LIST_PATH, 'r', encoding='utf-8') as _f:
                concept_list = _json.load(_f)
        except (FileNotFoundError, _json.JSONDecodeError):
            log('⚠️  概念缓存文件损坏或不存在，尝试从 akshare 拉取...')
            import akshare as ak
            df = ak.stock_board_concept_name_ths()
            if df is None or len(df) == 0:
                log('⚠️  akshare 概念列表也失败')
                return 0, 0
            concept_list = {}
            for _, row in df.iterrows():
                name = row.get('name', '')
                code = row.get('code', '')
                if name and code:
                    concept_list[code] = {'name': name, 'stock_count': 0, 'stocks': []}

        if not concept_list:
            log('⚠️  概念列表为空')
            return 0, 0

        # 重置 stocks（重新从 f103 构建）
        for ci in concept_list.values():
            ci['stocks'] = []
            ci['stock_count'] = 0

        log(f'    概念板块列表: {len(concept_list)} 个')

        # ── 第二步：从 push2test f103 拉个股→概念映射 ────
        log('    从 push2test 拉取个股概念映射(f103)...')
        import requests as _requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': '1', 'pz': '5000', 'po': '1', 'np': '1',
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': '2', 'invt': '2',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',
            'fields': 'f12,f14,f103',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://quote.eastmoney.com/',
        }
        r = _requests.get(url, params=params, headers=headers, timeout=30)
        items = r.json().get('data', {}).get('diff', [])
        if not items:
            log('⚠️  push2test f103 返回空')
            save_concept_list(concept_list)
            return len(concept_list), 0

        # 构建 ths_pool = {name: code} 快速查找
        ths_pool = {ci['name']: cc for cc, ci in concept_list.items()}

        def _match(cname):
            """东方财富概念名 → 同花顺概念 code"""
            # 手动映射
            if cname in MANUAL:
                target = MANUAL[cname]
                return ths_pool.get(target)

            # 精确匹配
            if cname in ths_pool:
                return ths_pool[cname]

            # 概念后缀差异
            if cname.endswith('概念'):
                base = cname[:-2]
                if base in ths_pool:
                    return ths_pool[base]
            else:
                with_suffix = cname + '概念'
                if with_suffix in ths_pool:
                    return ths_pool[with_suffix]

            # 括号清理后匹配
            import re
            cleaned = re.sub(r'[（(][^）)]*[）)]', '', cname).strip()
            if cleaned != cname:
                if cleaned in ths_pool:
                    return ths_pool[cleaned]
                with_suffix = cleaned + '概念'
                if with_suffix in ths_pool:
                    return ths_pool[with_suffix]

            # 子串包含: EM 名被 THS 名包含
            for tn, tc in ths_pool.items():
                if cname in tn:
                    return tc

            return None

        stock_concept_data = {}
        match_stats = {'hit': 0, 'miss': 0, 'total': 0}
        import re as _re

        for item in items:
            scode = item.get('f12', '')
            sname = (item.get('f14', '') or '').strip()
            concept_str = (item.get('f103', '') or '').strip()
            if not scode or not concept_str or concept_str == '-':
                continue

            cnames = [c.strip() for c in concept_str.replace(';', ',').split(',') if c.strip()]
            matched_codes = []
            matched_names = []

            for cn in cnames:
                match_stats['total'] += 1
                cc = _match(cn)
                if cc:
                    matched_codes.append(cc)
                    matched_names.append(concept_list[cc]['name'])
                    if scode not in concept_list[cc]['stocks']:
                        concept_list[cc]['stocks'].append(scode)
                    match_stats['hit'] += 1
                else:
                    match_stats['miss'] += 1

            if matched_codes:
                stock_concept_data[scode] = {
                    'code': scode,
                    'name': sname,
                    'concept_codes': matched_codes,
                    'concept_names': matched_names,
                }

        # 回写 stock_count
        for ci in concept_list.values():
            ci['stock_count'] = len(ci['stocks'])

        # 保存
        save_concept_list(concept_list)
        save_stock_concept_map(stock_concept_data)

        concept_cnt = sum(1 for c in concept_list.values() if c['stocks'])
        stock_cnt = len(stock_concept_data)
        hit_pct = match_stats['hit'] / match_stats['total'] * 100 if match_stats['total'] > 0 else 0
        log(f'    ✅ 概念映射完成: {concept_cnt}个概念含成分股, {stock_cnt}只个股有概念')
        log(f'       名称匹配率: {match_stats["hit"]}/{match_stats["total"]} ({hit_pct:.0f}%)')
        log(f'       ({time.time()-t0:.0f}s)')
        return concept_cnt, stock_cnt

    except Exception as e:
        log(f'⚠️  概念映射失败: {e}')
        import traceback
        log(traceback.format_exc())
        return 0, 0


# ════════════════════════════════════════════════════════════════
# 概念板块K线增量更新（仅拉取追踪中的概念）
# ════════════════════════════════════════════════════════════════

def update_concept_klines():
    """
    从 sector_daily.json 提取概念板块K线，按 tracked_concepts 筛选保存。
    目前 sector_daily.json 已由 refresh_sectors.py 全量更新，此处只做提取。

    未来可优化为：只拉取追踪中的概念（减少请求量）
    """
    t0 = time.time()
    # 从 DB 读概念K线
    from backend.data_access.data_layer import get_ths_industry_klines
    concepts_kline = get_ths_industry_klines(ths_type='N')
    if not concepts_kline:
        log('⚠️  板块数据中无概念K线')
        return 0

    log(f'📊  概念K线: {len(concepts_kline)}个有数据')
    log(f'    ✅ 概念K线就绪 ({time.time()-t0:.0f}s)')
    return len(concepts_kline)


# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════

def main():
    t0 = time.time()

    # 全局关闭 tqdm 进度条（在 akshare 首次导入前生效）
    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    # 增量更新交易日历（补最新交易日）
    try:
        cnt = update_trade_cal_from_tushare()
        if cnt:
            log(f'📅 trade_cal: 补 {cnt} 行')
    except Exception as e:
        log(f'⚠️  trade_cal更新失败: {e}')

    # 确保 all_stock_codes.json 存在（搜索用）
    if not os.path.isfile(ALL_CODES_PATH):
        log('📋  生成 all_stock_codes.json（全量A股代码表）...')
        try:
            import akshare as ak
            df = ak.stock_info_a_code_name()
            codes = dict(zip(df['code'], df['name']))
            with open(ALL_CODES_PATH, 'w', encoding='utf-8') as f:
                json.dump(codes, f, ensure_ascii=False)
            log(f'✅  已生成 ({len(codes)}只)')
        except Exception as e:
            log(f'⚠️  生成失败: {e}')

    # 行业映射（全量更新，～1-2秒）
    log('━━━ 行业映射 ━━━')
    update_industry_map()

    # 概念映射（东方财富 f103 + 名称映射表，~1秒）
    log('━━━ 概念映射 ━━━')
    update_concept_maps()

    # 阶段1: 个股
    log('━━━ 个股更新 ━━━')
    s1 = update_stocks()

    # 阶段2: 指数
    log('━━━ 指数更新 ━━━')
    s2 = update_index()

    # 阶段3: 板块
    log('━━━ 板块更新 ━━━')
    try:
        s3 = update_sectors()
    except Exception as e:
        log(f'🚨 板块更新失败: {e}')
        import traceback
        for line in traceback.format_exc().splitlines():
            log(f'  {line}')
        raise  # 非零退出码让cron感知

    elapsed = time.time() - t0
    log(f'{"━"*30}')
    log(f'📊 汇总: 个股{s1[0]+s1[1]}只变动 | 指数{s2[0]}条新增 | 板块{s3[0]+s3[1]}只变动')
    log(f'⏱️  总耗时 {elapsed:.1f}s')


if __name__ == '__main__':
    main()
