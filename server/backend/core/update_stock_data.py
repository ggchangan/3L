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
    INDEX_CODE,
    load_sector_daily_uncached,
    save_sector_daily,
)
from backend.core.data_layer import (
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
# 指数（中证全指 000985）
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
    """更新中证全指（000985）日K线"""
    import akshare as ak
    import warnings
    warnings.filterwarnings('ignore')

    existing = load_index_data_uncached()
    existing_klines = existing.get('klines', [])
    last_updated = existing.get('last_updated', '')

    # 拉取全量（akshare 返回所有历史日K线）
    try:
        df = ak.stock_zh_index_daily_tx(symbol=f'sh{INDEX_CODE}')
    except Exception as e:
        log(f'⚠️  指数拉取失败: {e}')
        return (0, 0)

    if df is None or len(df) == 0:
        log('⚠️  指数数据为空')
        return (0, 0)

    new_klines = _df_to_kline(df)

    # 去重：只追加比现有新的
    existing_dates = {k['date'] for k in existing_klines}
    added = 0
    for k in new_klines:
        if k['date'] not in existing_dates:
            existing_klines.append(k)
            added += 1

    if added == 0:
        log('✅  指数数据已最新')
        # 确保 last_updated 更新
        if new_klines:
            existing['last_updated'] = new_klines[-1]['date']
            save_index_data(existing)
        return (0, 0)

    existing_klines.sort(key=lambda x: x['date'])
    # 裁剪：保留最近200天足够
    if len(existing_klines) > 200:
        existing_klines = existing_klines[-200:]

    latest_date = existing_klines[-1]['date']
    save_index_data({
        'last_updated': latest_date,
        'klines': existing_klines,
    })

    log(f'📈  指数: {added}条新增, 最新{latest_date}')
    return (added, latest_date)


# ════════════════════════════════════════════════════════════════
# 板块（行业+概念）
# ════════════════════════════════════════════════════════════════

def _fetch_sector_klines_akshare(sector_type, name):
    """拉取单个板块的日K线（带重试，对抗akshare限流）
    sector_type: 'industry' 或 'concept'
    name: 板块名称
    返回 [{date, open, close, high, low, volume}] 或 []
    """
    import akshare as ak
    import time
    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y%m%d')
    start = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

    for attempt in range(3):
        try:
            if sector_type == 'industry':
                df = ak.stock_board_industry_index_ths(symbol=name, start_date=start, end_date=today)
            else:
                df = ak.stock_board_concept_index_ths(symbol=name, start_date=start, end_date=today)
            if df is None or len(df) == 0:
                return []
            return _df_to_kline(df)
        except Exception:
            if attempt < 2:
                time.sleep(2 + attempt * 2)  # 2s → 4s → give up
            continue
    return []


def update_sectors():
    """更新行业+概念板块日K线"""
    import akshare as ak
    import warnings
    warnings.filterwarnings('ignore')

    existing = load_sector_daily_uncached()
    last_updated = existing.get('last_updated', '')
    industries = existing.get('industries', {})
    concepts = existing.get('concepts', {})

    # 获取板块名称列表
    try:
        ind_names = list(ak.stock_board_industry_name_ths()['name'])
    except Exception as e:
        log(f'⚠️  行业板块列表拉取失败: {e}')
        ind_names = list(industries.keys())  # 用缓存的
    try:
        con_names = list(ak.stock_board_concept_name_ths()['name'])
    except Exception as e:
        log(f'⚠️  概念板块列表拉取失败: {e}')
        con_names = list(concepts.keys())

    log(f'📋  行业{len(ind_names)}个, 概念{len(con_names)}个, 上次更新{last_updated}')

    # 更新行业
    ind_updated = 0
    ind_new = 0
    for name in ind_names:
        try:
            # 已有且已是最新 → 跳过
            if name in industries and industries[name] and industries[name][-1]['date'] == last_updated:
                continue

            # 新板块：拉全量
            if name not in industries:
                klines = _fetch_sector_klines_akshare('industry', name)
                if klines:
                    industries[name] = klines
                    ind_new += 1
                time.sleep(0.3)
                continue

            # 已有板块但落后：只追最新日
            klines = industries[name]
            existing_dates = {k['date'] for k in klines}
            fetched = _fetch_sector_klines_akshare('industry', name)
            if not fetched:
                time.sleep(0.3)
                continue

            added = 0
            for k in fetched:
                if k['date'] not in existing_dates:
                    klines.append(k)
                    added += 1
            if added > 0:
                klines.sort(key=lambda x: x['date'])
                if len(klines) > 60:
                    klines = klines[-60:]
                    industries[name] = klines
                ind_updated += 1
            time.sleep(0.3)
        except Exception as e:
            log(f'  ⚠️  行业-{name}: {e}')

    # 更新概念
    con_updated = 0
    con_new = 0
    for name in con_names:
        try:
            # 已有且已是最新 → 跳过
            if name in concepts and concepts[name] and concepts[name][-1]['date'] == last_updated:
                continue

            if name not in concepts:
                klines = _fetch_sector_klines_akshare('concept', name)
                if klines:
                    concepts[name] = klines
                    con_new += 1
                time.sleep(0.3)
                continue

            klines = concepts[name]
            existing_dates = {k['date'] for k in klines}
            fetched = _fetch_sector_klines_akshare('concept', name)
            if not fetched:
                time.sleep(0.3)
                continue

            added = 0
            for k in fetched:
                if k['date'] not in existing_dates:
                    klines.append(k)
                    added += 1
            if added > 0:
                klines.sort(key=lambda x: x['date'])
                if len(klines) > 60:
                    klines = klines[-60:]
                    concepts[name] = klines
                con_updated += 1
            time.sleep(0.3)
        except Exception as e:
            log(f'  ⚠️  概念-{name}: {e}')

    # 确定最新日期
    all_dates = set()
    for name, kls in industries.items():
        if kls:
            all_dates.add(kls[-1]['date'])
    for name, kls in concepts.items():
        if kls:
            all_dates.add(kls[-1]['date'])
    latest_date = max(all_dates) if all_dates else last_updated

    save_sector_daily({
        'last_updated': latest_date,
        'industries': industries,
        'concepts': concepts,
    })

    stats = f'行业{ind_updated}只更新+{ind_new}只新增, 概念{con_updated}只更新+{con_new}只新增'
    log(f'📈  板块: {stats}')
    return (ind_updated + con_updated, ind_new + con_new)


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
        'pn': '1', 'pz': '5000',
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

    client = _create_mootdx_client()

    # 阶段1: 个股
    log('━━━ 个股更新 ━━━')
    s1 = update_stocks(client)

    # 阶段2: 指数
    log('━━━ 指数更新 ━━━')
    s2 = update_index(client)

    # 阶段3: 板块
    log('━━━ 板块更新 ━━━')
    s3 = update_sectors()

    elapsed = time.time() - t0
    log(f'{"━"*30}')
    log(f'📊 汇总: 个股{s1[0]+s1[1]}只变动 | 指数{s2[0]}条新增 | 板块{s3[0]+s3[1]}只变动')
    log(f'⏱️  总耗时 {elapsed:.1f}s')


if __name__ == '__main__':
    main()
