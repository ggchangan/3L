#!/usr/bin/env python3
"""
唯一数据更新脚本 — 17:00 cron 运行
范围 = 个股K线 + 中证全指 + 行业/概念板块日K线
所有文件I/O通过 backend.core.data_layer 完成

用法:
    python3 scripts/update_stock_data.py
"""

import json, os, sys, time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# ⚠️ 注意: file 在 server/backend/core/ 下
# dirname×1=core/  ×2=backend/  ×3=server/（backend 包所在位置）
from backend.config import DATA_DIR, ALL_CODES_PATH, CONCEPT_LIST_PATH
from backend.core.data_layer import (
    get_watchlist,
    load_all_stocks_uncached,
    get_last_updated,
    get_industry_map,
    save_industry_map,
    save_all_stocks,
    load_index_data_uncached,
    save_index_data,
    INDEX_CODES,
    load_sector_daily_uncached,
    save_sector_daily,
)
from backend.core.data_layer import (
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
                'volume': int(float(row['volume'])) * 100,
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


def update_stocks(client):
    """更新个股K线，返回统计 (updated, new_added, names_fixed)"""
    wl = get_watchlist()
    codes = sorted(set(
        s.get('code', '')[-6:] for s in wl if s.get('code')
    ))
    if not codes:
        log('⚠️  自选股列表为空，跳过个股更新')
        return (0, 0, 0)

    existing_sector_map = load_all_stocks_uncached()
    existing = _flatten_stocks(existing_sector_map)
    last_updated = get_last_updated()
    industry_map = get_industry_map()

    # 判断是否需要更新
    need_update = False
    for code in codes:
        if code not in existing:
            need_update = True
            break
    if not need_update and last_updated:
        # 用第一只股票判断mootdx最新交易日
        sample = client.bars(symbol=codes[0], frequency=9, start=0, count=3)
        if sample is not None and len(sample) > 0:
            latest = sample.iloc[-1]['datetime'][:10].replace('-', '')
        else:
            latest = datetime.now().strftime('%Y%m%d')
        if latest <= last_updated.replace('-', ''):
            log('✅  个股数据已最新，跳过')
            # 但还要返回 codes 给上游判断最新交易日
            return (0, 0, 0)

    today_str = datetime.now().strftime('%Y%m%d')
    if codes:
        sample = client.bars(symbol=codes[0], frequency=9, start=0, count=3)
        if sample is not None and len(sample) > 0:
            latest_mootdx = sample.iloc[-1]['datetime'][:10].replace('-', '')
        else:
            latest_mootdx = today_str
    else:
        latest_mootdx = today_str

    # 清除缓存
    cache_path = os.path.join(CACHE_DIR, 'all_stocks.json')
    try:
        os.remove(cache_path)
    except (FileNotFoundError, OSError):
        pass

    updated = 0
    new_added = 0
    names_fixed = 0

    for code in codes:
        try:
            records = fetch_klines_from_mootdx(client, code)
            if not records:
                continue

            if code in existing:
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
            else:
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

    # 组装输出
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

    save_all_stocks(sector_map, last_updated=latest_mootdx)

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


def update_index(client):
    """更新所有指数日K线（上证000001 + 科创50 000688 + 中证全指000985）"""
    import akshare as ak
    import warnings
    warnings.filterwarnings('ignore')

    existing = load_index_data_uncached()
    indices = existing.get('indices', {})
    total_added = 0
    last_date = existing.get('last_updated', '')

    for code, name in INDEX_CODES.items():
        info = indices.get(code, {'name': name, 'klines': []})
        existing_klines = info.get('klines', [])
        existing_dates = {k['date'] for k in existing_klines}

        try:
            df = ak.stock_zh_index_daily_tx(symbol=f'sh{code}')
        except Exception as e:
            log(f'⚠️  {name}({code})拉取失败: {e}')
            continue

        if df is None or len(df) == 0:
            log(f'⚠️  {name}({code})数据为空')
            continue

        new_klines = _df_to_kline(df)

        added = 0
        for k in new_klines:
            if k['date'] not in existing_dates:
                existing_klines.append(k)
                added += 1

        if added > 0:
            existing_klines.sort(key=lambda x: x['date'])
            # 裁剪：保留最近200天
            if len(existing_klines) > 200:
                existing_klines = existing_klines[-200:]
            last_kline = existing_klines[-1]
            if last_kline['date'] > last_date:
                last_date = last_kline['date']
            log(f'📈  {name}: {added}条新增, 最新{last_kline["date"]}')

        indices[code] = {'name': name, 'klines': existing_klines}
        total_added += added

    if total_added == 0:
        log(f'✅  指数数据已最新')
    else:
        log(f'📈  指数合计: {total_added}条新增, 最新{last_date}')

    # 统一保存
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


def _fetch_today_sectors_from_push2test(sector_type, name_list):
    """主源：从 push2test.eastmoney.com 批量获取板块今日实时数据
    sector_type: 'industry' | 'concept'
    name_list: 板块名称列表（仅用于日志，实际拉全量再过滤）
    返回 {name: {date, open, close, high, low, volume}}，全部失败则返回 {}
    """
    import requests as _req
    from datetime import datetime

    fs = _SECTOR_FS.get(sector_type)
    if not fs:
        log(f'❌ _fetch_today_sectors_from_push2test: 未知板块类型 {sector_type}')
        return {}

    today = datetime.now().strftime('%Y%m%d')
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
            close = float(item.get('f2', 0) or 0)
            high = float(item.get('f15', close) or close)
            low = float(item.get('f16', close) or close)
            open_ = float(item.get('f17', close) or close)
            volume = int(float(item.get('f5', 0) or 0))
            change_pct = float(item.get('f3', 0) or 0)   # 当日涨跌幅%
            prev_close = float(item.get('f18', 0) or 0)   # 昨收
            name_map[name] = {
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


def update_sectors():
    """更新行业+概念板块日K线
    数据源：push2test.eastmoney.com（主源，批量获取今日实时数据）
    失败率>50%告警，全部失败抛异常
    """
    import warnings
    warnings.filterwarnings('ignore')

    existing = load_sector_daily_uncached()
    last_updated = existing.get('last_updated', '')
    industries = existing.get('industries', {})
    concepts = existing.get('concepts', {})

    # ── 获取板块名称列表（push2test优先 → 缓存兜底） ──
    ind_names = _fetch_board_names_from_push2test('industry')
    if not ind_names:
        log('⚠️  行业板块列表获取失败，用缓存数据')
        ind_names = list(industries.keys())

    con_names = _fetch_board_names_from_push2test('concept')
    if not con_names:
        log('⚠️  概念板块列表获取失败，用缓存数据')
        con_names = list(concepts.keys())

    log(f'📋  行业{len(ind_names)}个, 概念{len(con_names)}个, 上次更新{last_updated}')

    # ── 确定追踪中的概念 ──
    today = datetime.now().strftime('%Y%m%d')
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
        tracked_concepts = set(con_names)

    # ═══════════════════════════════════════════════════
    # 主源：push2test 批量获取今日数据
    # push2test(东财)和旧akshare(同花顺)的指数基准不同，不能混合
    # → 直接完全替换：有push2test数据的板块全部替换，没有的保留旧数据
    # ═══════════════════════════════════════════════════
    ind_today = _fetch_today_sectors_from_push2test('industry', ind_names)
    con_today = _fetch_today_sectors_from_push2test('concept', list(tracked_concepts))

    # ── 保留旧THS数据不变，另存push2test数据到独立字段 ──
    # push2test(东财)和akshare(同花顺)的指数绝对值不同，不能混
    # push2test的f3字段本身就是当日涨跌幅，无需历史即可排行
    push2test_data = {'industries': ind_today, 'concepts': con_today}
    existing['_push2test'] = push2test_data
    existing['_push2test_updated'] = today
    
    # 统计
    ind_saved = len(ind_today)
    con_saved = len(con_today)

    # ═══════════════════════════════════════════════════
    # 失败率分析 + 告警
    # ═══════════════════════════════════════════════════
    ind_total = len(ind_names)
    con_tracked = len(tracked_concepts)
    ind_miss = ind_total - len(ind_today)
    con_miss = con_tracked - len(con_today)

    if ind_total > 0 and ind_miss / ind_total > 0.5:
        msg = f'🚨 行业板块大面积获取失败: {ind_miss}/{ind_total}({ind_miss/ind_total*100:.0f}%) 未从push2test获取到数据'
        log(msg)

    if con_tracked > 0 and con_miss / con_tracked > 0.5:
        msg = f'🚨 概念板块大面积获取失败: {con_miss}/{con_tracked}({con_miss/con_tracked*100:.0f}%) 未从push2test获取到数据'
        log(msg)

    # 全源全量失败 → 抛异常让cron能感知
    if ind_total > 0 and len(ind_today) == 0 and not industries:
        raise RuntimeError('行业板块全源获取失败，无任何缓存数据可用')
    if con_tracked > 0 and len(con_today) == 0 and not any(name in concepts for name in tracked_concepts):
        raise RuntimeError('概念板块全源获取失败（追踪中），无任何缓存数据可用')

    # 最新日期：来自push2test的更新时间
    latest_date = existing.get('_push2test_updated', existing.get('last_updated', ''))

    save_sector_daily({
        'last_updated': latest_date,
        'industries': industries,
        'concepts': concepts,
        '_push2test': existing.get('_push2test', {}),
        '_push2test_updated': existing.get('_push2test_updated', ''),
    })

    stats = f'push2test: 行业{ind_saved}条, 概念{con_saved}条 (THS旧数据保留不变)'
    log(f'📈  板块: {stats}')
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
    # 从 sector_daily.json 读概念K线
    sector = load_sector_daily_uncached()
    concepts_kline = sector.get('concepts', {})
    if not concepts_kline:
        log('⚠️  板块数据中无概念K线')
        return 0

    log(f'📊  概念K线: {len(concepts_kline)}个有数据')
    log(f'    ✅ 概念K线就绪 ({time.time()-t0:.0f}s)')
    return len(concepts_kline)


# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════

def _ensure_mootdx_config():
    """确保 mootdx 配置文件中有有效的 BESTIP，避免空配置导致连接失败。"""
    from pathlib import Path
    import json
    config_path = Path.home() / '.mootdx' / 'config.json'
    if not config_path.exists():
        return
    try:
        cfg = json.loads(config_path.read_text(encoding='utf-8'))
        bestip = cfg.get('BESTIP', {})
        hq = bestip.get('HQ', '')
        if not hq or (isinstance(hq, (list, tuple)) and len(hq) != 2):
            # 空BESTIP或格式错误 → 写入一个已知可达的服务器
            bestip['HQ'] = ['218.6.170.47', 7709]
            bestip['EX'] = ['47.112.95.207', 7720]
            bestip['GP'] = ['120.76.152.87', 7709]
            config_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding='utf-8')
            log('🔧 已修复 mootdx 配置: BESTIP.HQ 为空，填入默认服务器')
    except Exception as e:
        log(f'⚠️  读取mootdx配置失败: {e}')


def _create_mootdx_client(max_retries=3, delay=5):
    """创建 mootdx 客户端，带重试机制。通达信服务器偶发连接失败，自动重试。"""
    from mootdx.quotes import Quotes
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            client = Quotes.factory(market='std')
            # 快速验证：请求1根K线确认连接可用
            test = client.bars(symbol='000001', frequency=9, start=0, count=1)
            if test is not None:
                return client
        except Exception as e:
            last_err = e
            log(f'⚠️  mootdx连接第{attempt}次失败: {e}')
            if attempt < max_retries:
                time.sleep(delay)
    raise last_err or RuntimeError('mootdx所有重试均失败')


def main():
    t0 = time.time()

    # 全局关闭 tqdm 进度条（在 akshare 首次导入前生效）
    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    # 启动前确保 mootdx 配置有效（避免空BESTIP导致连接失败）
    _ensure_mootdx_config()

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

    client = _create_mootdx_client()

    # 阶段1: 个股
    log('━━━ 个股更新 ━━━')
    s1 = update_stocks(client)

    # 阶段2: 指数
    log('━━━ 指数更新 ━━━')
    s2 = update_index(client)

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
