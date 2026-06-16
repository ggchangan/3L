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
    save_index_data,
    get_index_data,
    fetch_stock_klines_from_db,
    get_stock_names_from_db,
    get_stock_daily_latest_date,
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
    """从 index_daily DB 重建指数缓存（替代 akshare→JSON 旧路径）

    经 Phase 1 的 Tushare 增量拉取，index_daily DB 已有最新数据。
    这里直接从 DB 读取并保存到缓存。
    """
    data = get_index_data()
    indices = data.get('indices', {})
    if not indices:
        log('⚠️  指数数据为空')
        return (0, '')

    total = 0
    last_date = data.get('last_updated', '')
    for code, info in indices.items():
        klines = info.get('klines', [])
        name = info.get('name', code)
        total += len(klines)
        if klines:
            log(f'📈  {name}: {len(klines)}条, 最新{klines[0]["date"]}')

    save_index_data(data)
    log(f'📈  指数合计: {total}条, 最新{last_date}')
    return (total, last_date)


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
    """从 ths_member + ths_index DB 重建行业映射，写入 stock_industry_map.json

    数据源：ths_member（成分股）+ ths_index(type=I)（同花顺行业列表）
    一只股票可能属于多个同花顺行业（如银行+银行Ⅲ），取名称最长的（最细粒度）。
    格式：{code: {code, name, ths_industry}}
    返回：写入的股票数量
    """
    try:
        db = TushareDB()
        conn = db._get_conn()
        from pymysql.cursors import DictCursor
        try:
            with conn.cursor(DictCursor) as cur:
                cur.execute("""
                    SELECT m.con_code, m.con_name, i.name
                    FROM ths_member m
                    JOIN ths_index i ON m.ts_code = i.ts_code
                    WHERE i.type = 'I'
                """)
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception as e:
        log(f'⚠️  DB查询行业映射失败: {e}')
        return 0

    # 组装：同只股票多个行业 → 取名称最长的
    from collections import defaultdict
    stock_industries = defaultdict(list)
    for r in rows:
        code = r['con_code'].replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
        name = r['con_name']
        industry = r['name']
        if code and industry:
            stock_industries[code].append((industry, name))

    result = {}
    for code, entries in stock_industries.items():
        # 取行业名最长的（最细粒度）
        entries.sort(key=lambda x: -len(x[0]))
        best_industry = entries[0][0]
        best_name = entries[0][1]
        result[code] = {'code': code, 'name': best_name, 'ths_industry': best_industry}

    if result:
        save_industry_map(result)
        log(f'🏭  行业映射: DB重建完成 ({len(result)}只)')
    return len(result)


# ════════════════════════════════════════════════════════════════
# 概念板块映射（stock→concept + concept→stocks）
# ════════════════════════════════════════════════════════════════

def update_concept_maps():
    """从 ths_member + ths_index DB 重建概念映射

    数据源:
      ths_index(type=N): 概念板块列表 {ts_code, name}
      ths_member: 成分股归属 {ts_code, con_code, con_name}

    输出:
      concept_list.json:  {概念code: {name, stock_count, stocks: [股票code,...]}}
      stock_concept_map.json: {股票code: {code, name, concept_codes, concept_names}}
    """
    try:
        db = TushareDB()
        conn = db._get_conn()
        from pymysql.cursors import DictCursor
        try:
            # 查概念列表
            with conn.cursor(DictCursor) as cur:
                cur.execute("SELECT ts_code, name FROM ths_index WHERE type = 'N'")
                concepts = {r['ts_code']: r['name'] for r in cur.fetchall()}
                log(f'🗺️  概念板块列表: {len(concepts)} 个')

            # 查概念成分股
            if concepts:
                codes_list = list(concepts.keys())
                concept_list = {}
                stock_concept_data = {}
                # 分批查询（SQL IN 限制）
                chunk_size = 500
                for i in range(0, len(codes_list), chunk_size):
                    chunk = codes_list[i:i + chunk_size]
                    placeholders = ','.join(['%s'] * len(chunk))
                    with conn.cursor(DictCursor) as cur:
                        cur.execute(
                            f"SELECT ts_code, con_code, con_name FROM ths_member WHERE ts_code IN ({placeholders})",
                            chunk
                        )
                        for r in cur.fetchall():
                            ts_code = r['ts_code']
                            con_code = r['con_code'].replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
                            con_name = r['con_name']
                            cname = concepts.get(ts_code, '')

                            # concept_list: 概念→股票
                            if ts_code not in concept_list:
                                concept_list[ts_code] = {'name': cname, 'stock_count': 0, 'stocks': []}
                            if con_code not in concept_list[ts_code]['stocks']:
                                concept_list[ts_code]['stocks'].append(con_code)

                            # stock_concept_data: 股票→概念
                            if con_code not in stock_concept_data:
                                stock_concept_data[con_code] = {
                                    'code': con_code, 'name': con_name,
                                    'concept_codes': [], 'concept_names': [],
                                }
                            if ts_code not in stock_concept_data[con_code]['concept_codes']:
                                stock_concept_data[con_code]['concept_codes'].append(ts_code)
                                stock_concept_data[con_code]['concept_names'].append(cname)

                # 回写 stock_count
                for ci in concept_list.values():
                    ci['stock_count'] = len(ci['stocks'])

                # 保存
                save_concept_list(concept_list)
                save_stock_concept_map(stock_concept_data)

                concept_cnt = sum(1 for c in concept_list.values() if c['stocks'])
                log(f'  ✅ 概念映射: {concept_cnt}个有成分股, {len(stock_concept_data)}只有概念')

        finally:
            conn.close()
    except Exception as e:
        log(f'⚠️  概念映射DB重建失败: {e}')
        import traceback
        for line in traceback.format_exc().splitlines():
            log(f'  {line}')

    return (len(concept_list) if 'concept_list' in dir() else 0,
            len(stock_concept_data) if 'stock_concept_data' in dir() else 0)


# ════════════════════════════════════════════════════════════════

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

# ════════════════════════════════════════════════════════════════
# Tushare 增量拉取 — 将最新交易日数据写入 DB
# ════════════════════════════════════════════════════════════════

def _fetch_tushare_daily_incremental():
    """拉取最新交易日数据到 stock_daily + index_daily DB 表

    只在交易时段后执行（08:00~20:00），非交易日直接跳过。
    检查该日期是否已有数据，避免重复拉取。
    """
    from backend.data_access.data_source import get_last_completed_trading_day
    from backend.data_access.tushare_db import TushareDB
    from backend.core.config import TUSHARE_TOKEN
    import tushare as ts

    # 非交易日跳过
    now = datetime.now()
    if now.weekday() >= 5:
        log('⏭️  非交易日，跳过 Tushare 增量拉取')
        return

    # 确定目标日期（上一个已完成交易日）
    trade_date = get_last_completed_trading_day()
    if not trade_date:
        log('⚠️  无法确定交易日，跳过 Tushare 增量拉取')
        return

    log(f'📡 Tushare 增量拉取目标日期: {trade_date}')

    start = time.time()
    db = TushareDB()
    api = ts.pro_api(TUSHARE_TOKEN)
    total_rows = 0

    # ── 个股日线 stock_daily ──
    try:
        latest = db.get_last_trade_date('stock_daily')
        if latest and latest >= trade_date:
            log(f'  stock_daily 已有 {trade_date} 数据，跳过')
        else:
            df = api.daily(trade_date=trade_date)
            if df is not None and not df.empty:
                rows = db.upsert_many('stock_daily', df)
                log(f'  stock_daily: 写入 {rows} 条')
                total_rows += rows
            time.sleep(0.6)
    except Exception as e:
        log(f'⚠️  stock_daily 增量失败: {e}')

    # ── 指数日线 index_daily ──
    try:
        for ts_code in ['000001.SH', '000688.SH', '000985.SH', '399006.SZ']:
            try:
                latest = db.get_last_trade_date('index_daily')
                if latest and latest >= trade_date:
                    log(f'  index_daily[{ts_code}] 已有数据 ({latest})，跳过')
                    continue
                df = api.index_daily(ts_code=ts_code, start_date=trade_date, end_date=trade_date)
                if df is not None and not df.empty:
                    rows = db.upsert_many('index_daily', df)
                    log(f'  index_daily[{ts_code}]: 写入 {rows} 条')
                    total_rows += rows
                time.sleep(0.6)
            except Exception as e:
                log(f'  ⚠️  index_daily[{ts_code}] 失败: {e}')
    except Exception as e:
        log(f'⚠️  index_daily 增量失败: {e}')

    elapsed = time.time() - start
    log(f'📡 Tushare 增量完成: {total_rows} 条写入 DB，耗时 {elapsed:.1f}s')


def main():
    t0 = time.time()

    # 全局关闭 tqdm 进度条（在 akshare 首次导入前生效）
    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    # ── Tushare 增量拉取（先确保 stock_daily / index_daily 有最新数据）──
    _fetch_tushare_daily_incremental()

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
