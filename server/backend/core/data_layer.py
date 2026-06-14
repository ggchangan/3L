#!/usr/bin/env python3
"""
统一数据层 — 所有股票数据的单一入口
所有文件路径集中定义在 config.py，此处通过 import 引用
"""
import json, os
from datetime import datetime
from backend.core.cache_layer import cache
from backend.core.logger import get_logger

log = get_logger(__name__)
from backend.config import (
    DATA_DIR, WWW_DIR, CACHE_DIR, PRIVATE_DIR,
    ALL_STOCKS_PATH, WATCHLIST_PATH, INDUSTRY_MAP_PATH,
    SUB_SECTOR_CLUSTERS_PATH, FINANCIAL_CACHE_PATH,
    PROFIT_QUALITY_PATH, INDEX_DATA_PATH, SECTOR_DAILY_PATH,
    INDUSTRY_LEADERS_PATH,
    LATEST_SCAN_PATH, ALL_CODES_PATH, KEY_POINTS_DIR,
    HOLDINGS_PATH, TRADES_PATH, REVIEW_ARCHIVE_DIR,
    REVIEW_CHARTS_DIR, SCRIPTS_DIR, SIMULATION_DIR,
    MAINLINES_CACHE_PATH,
    SIMULATION_V3_DIR as OUTPUT_DIR,
    CONCEPT_LIST_PATH, STOCK_CONCEPT_MAP_PATH,
)

# ====== 通用 ======
def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.warning('读 %s 失败: %s', path, e)
        return default if default is not None else {}

def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _atomic_save_json(path, data):
    """原子写入：临时文件 → rename 覆盖，避免读到半成品"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.rename(tmp, path)

# ====== K线数据 ======
def _load_all_stocks_from_disk():
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('stocks', raw)

def get_all_stocks():
    """返回 {方向: {code: [klines]}} 格式的K线数据（优先JSON缓存，无JSON时从DB读取）"""
    # 优先 JSON（快速，测试环境大量调用）
    json_path = ALL_STOCKS_PATH
    if os.path.isfile(json_path):
        return cache.get('all_stocks', _load_all_stocks_from_disk, ttl=30)
    # JSON 不存在 → 从 DB 读
    try:
        return cache.get('all_stocks_db', lambda: get_all_stocks_db(), ttl=30)
    except Exception as e:
        log.warning('DB获取K线失败(%s)，返回空', e)
        return {'last_updated': ''}

def get_all_stocks_db(limit: int = 60):
    """从 TushareDB 读取K线数据，按方向分组

    替代 get_all_stocks() 的 JSON 路径。
    方向分组从 watchlist 的方向标签推导，不在自选股中的股票归入"其他"。

    Returns:
        {方向: {code: [{date, open, close, high, low, volume}, ...]}, ...}
        同时包含 last_updated 字段（最新交易日）
    """
    from backend.services.tushare_db import TushareDB
    db = TushareDB()

    # 获取自选股列表（含方向）
    wl = get_watchlist()

    # 收集所有需要查询的股票代码
    all_codes = set()
    code_info = {}  # {code: direction}
    for s in wl:
        code = s.get('code', '')
        if code:
            all_codes.add(code)
            code_info[code] = s.get('direction', '其他')

    if not all_codes:
        return {'last_updated': ''}

    # 批量从 DB 查 K线
    codes_list = list(all_codes)
    klines_map = db.query_stock_klines_batch(codes_list, limit=limit, adj='qfq')

    # 查股票名称（批量查询，避免逐个股查）
    code_name_map = {}
    ts_codes = [db.code_to_ts_code(c) for c in codes_list]
    placeholders = ','.join(['%s'] * len(ts_codes))
    name_rows = db.execute_raw(
        f"SELECT symbol, name FROM stock_basic WHERE symbol IN ({placeholders})",
        list(codes_list)
    )
    for r in name_rows:
        code_name_map[r['symbol']] = r.get('name', '')
    # 回退：对于 stock_basic 里查不到的，从已获取的K线数据里取第一个的 name（如果有）
    for code in codes_list:
        if code not in code_name_map:
            klines = klines_map.get(code, [])
            if klines and 'name' in klines[0]:
                code_name_map[code] = klines[0]['name']

    # 按方向分组，补 name
    result = {}
    for code, klines in klines_map.items():
        direction = code_info.get(code, '其他')
        if direction not in result:
            result[direction] = {}
        name = code_name_map.get(code, '')
        if name:
            for k in klines:
                k['name'] = name
        result[direction][code] = klines

    # last_updated
    last_date = db.get_last_stock_date()
    result['last_updated'] = last_date or ''

    return result

def get_last_updated():
    """返回缓存最新交易日 YYYYMMDD（优先DB，回退JSON）"""
    try:
        from backend.services.tushare_db import TushareDB
        date = TushareDB().get_last_stock_date()
        if date:
            return date
    except Exception:
        pass
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('last_updated', '')

def save_all_stocks(stocks, last_updated=None):
    """保存K线数据到DB。stocks格式: {方向: {code: [klines]}}"""
    from backend.services.tushare_db import TushareDB
    db = TushareDB()
    total = 0
    for direction, codes in stocks.items():
        if direction == 'last_updated':
            continue
        for code, klines in codes.items():
            ts = db.code_to_ts_code(code)
            rows = []
            for k in klines:
                rows.append({
                    'ts_code': ts,
                    'trade_date': k['date'],
                    'open': k.get('open'),
                    'high': k.get('high'),
                    'low': k.get('low'),
                    'close': k.get('close'),
                    'vol': k.get('volume', 0),
                    'pre_close': k.get('pre_close'),
                    'change': k.get('change'),
                    'pct_chg': k.get('pct_chg'),
                })
            if rows:
                db.upsert_many_from_dicts('stock_daily', rows)
                total += len(rows)
    cache.invalidate('all_stocks_db')
    _clear_stock_chart_svg_cache()
    if total:
        log.info('save_all_stocks: %d条写入DB', total)

def load_all_stocks_uncached():
    """强制从磁盘读取K线数据（不走缓存），供更新脚本使用"""
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('stocks', raw)


def _clear_stock_chart_svg_cache():
    """清除所有个股SVG图表缓存

    当存储的K线数据被修改（如前复权矫正、新数据追加）时调用。
    直接删除磁盘上的缓存文件，下次页面访问时自动基于新数据重新生成。
    """
    try:
        from backend.config import CHARTS_DIR
        if not os.path.isdir(CHARTS_DIR):
            return
        removed = 0
        for fname in os.listdir(CHARTS_DIR):
            if fname.startswith('zzqz_stock_chart_') and fname.endswith('.svg'):
                os.remove(os.path.join(CHARTS_DIR, fname))
                removed += 1
            elif fname.startswith('zzqz_trend_stock_chart_') and fname.endswith('.svg'):
                os.remove(os.path.join(CHARTS_DIR, fname))
                removed += 1
        if removed:
            log.info('已清除%d个SVG图表缓存', removed)
    except Exception:
        log.warning('SVG图表缓存清理异常')
        pass

def get_stock_klines(code, direction=None, stocks=None):
    """获取单只股票K线列表（优先从 stocks 参数找，回退DB）"""
    if stocks is None:
        stocks = get_all_stocks()
    if direction and direction in stocks and code in stocks[direction]:
        return stocks[direction][code]
    for sec, codes in stocks.items():
        if code in codes:
            return codes[code]
    # DB回退
    try:
        from backend.services.tushare_db import TushareDB
        ts = TushareDB().code_to_ts_code(code)
        return TushareDB().query_stock_daily(ts, limit=60)
    except Exception:
        pass
    return []


# ====== 指数数据（多指数结构）======
# index_sh_data.json 格式: {last_updated, indices: {code: {name, klines: [{date, open, close, high, low, volume}]}}}
INDEX_CODE = '000985'

INDEX_CODES = {
    '000001': '上证指数',
    '000688': '科创50',
    '000985': '中证全指',
    '399006': '创业板指',
}

def get_index_data():
    """返回完整指数数据 {last_updated, indices: {code: {name, klines}}}（优先JSON，无JSON时从DB读取）"""
    if os.path.isfile(INDEX_DATA_PATH):
        return cache.get('index_data', lambda: _load_json(INDEX_DATA_PATH, {}), ttl=60)
    try:
        from backend.services.tushare_db import TushareDB
        db = TushareDB()
        indices = {}
        latest = ''
        for code, name in INDEX_CODES.items():
            ts = f"{code}.SH" if code != '399006' else f"{code}.SZ"
            klines = db.get_index_klines(ts, limit=500)
            if klines:
                indices[code] = {'name': name, 'klines': klines}
                if klines[0]['date'] > latest:
                    latest = klines[0]['date']
        if indices:
            return {'last_updated': latest, 'indices': indices}
    except Exception as e:
        log.warning('DB获取指数失败(%s)', e)
    return {'last_updated': '', 'indices': {}}

def save_index_data(data):
    """保存指数数据到DB"""
    _atomic_save_json(INDEX_DATA_PATH, data)
    cache.invalidate('index_data')
    try:
        from backend.services.tushare_db import TushareDB
        db = TushareDB()
        indices = data.get('indices', {})
        total = 0
        for code, info in indices.items():
            ts = f"{code}.SH" if code != '399006' else f"{code}.SZ"
            klines = info.get('klines', [])
            rows = []
            for k in klines:
                rows.append({
                    'ts_code': ts,
                    'trade_date': k['date'],
                    'open': k.get('open'),
                    'high': k.get('high'),
                    'low': k.get('low'),
                    'close': k.get('close'),
                    'vol': k.get('volume', 0),
                })
            if rows:
                db.upsert_many_from_dicts('index_daily', rows)
                total += len(rows)
        if total:
            log.info('save_index_data: %d条写入DB', total)
    except Exception as e:
        log.warning('save_index_data写入DB失败: %s', e)

def load_index_data_uncached():
    """强制从磁盘读取指数数据（不走缓存），供更新脚本使用
    兼容旧格式：
      - 纯 [{date, ...}] → 自动转换为多指数格式 {indices: {000985: {klines: ...}}}
      - {last_updated, klines} → 自动转换为多指数格式
    """
    raw = _load_json(INDEX_DATA_PATH, {})
    if isinstance(raw, list):
        # 旧格式迁移：纯K线列表
        klines = raw
        latest = klines[-1]['date'] if klines else ''
        data = {
            'last_updated': latest,
            'indices': {
                '000985': {'name': '中证全指', 'klines': klines},
            }
        }
        _atomic_save_json(INDEX_DATA_PATH, data)
        return data
    if 'klines' in raw and 'indices' not in raw:
        # 旧格式迁移：{last_updated, klines}
        latest = raw.get('last_updated', '')
        klines = raw.get('klines', [])
        data = {
            'last_updated': latest,
            'indices': {
                '000985': {'name': '中证全指', 'klines': klines},
            }
        }
        _atomic_save_json(INDEX_DATA_PATH, data)
        return data
    return raw

def get_index_klines(code=INDEX_CODE):
    """返回指定指数代码的K线列表，默认中证全指"""
    data = get_index_data()
    indices = data.get('indices', {})
    info = indices.get(code, {})
    return info.get('klines', [])


# ====== 板块日K线数据（行业+概念）======
def get_sector_daily():
    """返回 {last_updated, industries, concepts}（走缓存，TTL=60s）
    
    优先从 data_source 抽象层合并多源，兜底读 sector_daily.json
    """
    def _load_from_data_source():
        try:
            from backend.services.data_source import get_merged_sector_data
            return get_merged_sector_data()
        except Exception:
            return _load_json(SECTOR_DAILY_PATH, {})
    return cache.get('sector_daily', _load_from_data_source, ttl=60)

def save_sector_daily(data):
    """原子保存板块日K线数据"""
    _atomic_save_json(SECTOR_DAILY_PATH, data)
    cache.invalidate('sector_daily')

def load_sector_daily_uncached():
    """强制从磁盘读取板块日K线数据（不走缓存），供更新脚本使用"""
    return _load_json(SECTOR_DAILY_PATH, {})


def get_sector_push2test():
    """获取当日涨跌幅快照（_push2test 字段）

    返回 SectorPush2Test 包含：
    - industries: {name: ThsIndustrySnapshot} — 来自同花顺THS（含上涨家数/领涨股）
    - concepts: {name: Push2TestConceptSnapshot} — 来自 push2test

    这是业务代码读取 _push2test 的唯一入口。
    不得直接调 load_sector_daily_uncached() 读原始文件。
    """
    from backend.core.data_models import SectorPush2Test, ths_dict_to_snapshot, push2test_dict_to_snapshot
    data = _load_json(SECTOR_DAILY_PATH, {})
    raw = data.get('_push2test', {})
    if not isinstance(raw, dict):
        return SectorPush2Test()

    industries = {}
    for name, entry in raw.get('industries', {}).items():
        if isinstance(entry, dict):
            industries[name] = ths_dict_to_snapshot(entry)

    concepts = {}
    for name, entry in raw.get('concepts', {}).items():
        if isinstance(entry, dict):
            concepts[name] = push2test_dict_to_snapshot(entry)

    return SectorPush2Test(industries=industries, concepts=concepts)


def get_sector_klines(sector_name, sector_type='industry'):
    """获取单个板块的历史K线数据

    内部通过 data_source 的多源故障切换获取（THS→EM→legacy）

    Args:
        sector_name: 板块名称（如 '电子化学品'）
        sector_type: 'industry' 或 'concept'

    Returns: [{date, open, close, high, low, volume}, ...] 或 []
    """
    try:
        from backend.services.data_source import get_sector_klines as _ds_klines
        return _ds_klines(sector_name, sector_type)
    except Exception:
        data = _load_json(SECTOR_DAILY_PATH, {})
        key = 'industries' if sector_type == 'industry' else 'concepts'
        return data.get(key, {}).get(sector_name, [])


def get_concept_snapshots(name_list: list = None) -> dict:
    """获取概念板块今日快照数据

    通过 data_source 统一入口路由到当前数据源实现（当前：同花顺 THS）。
    使用名称映射表将系统概念名转为数据源概念名。

    Args:
        name_list: 系统概念名称列表，None=获取所有已映射概念

    Returns:
        {系统名: {date, change_pct, up_count, down_count, ...}}
    """
    try:
        from backend.services.data_source import get_concept_snapshots as _ds_get
        return _ds_get(name_list)
    except Exception as e:
        log.warning('get_concept_snapshots 失败: %s', e)
        return {}


def get_concept_klines(name_list: list) -> dict:
    """获取概念板块最新日K线数据

    通过 data_source 统一入口路由到当前数据源实现（当前：同花顺 THS）。
    仅拉取已映射的概念。

    Args:
        name_list: 系统概念名称列表

    Returns:
        {系统名: {date, open, close, high, low, volume}}
        只返回成功拉取到的概念
    """
    try:
        from backend.services.data_source import get_concept_klines as _ds_klines
        return _ds_klines(name_list)
    except Exception as e:
        log.warning('get_concept_klines 失败: %s', e)
        return {}


def verify_data_sources(verbose=False):
    """验证所有数据源的正确性、及时性、缓存一致性

    通过 data_layer 统一入口调用 data_source 的验证逻辑，
    update_stock_data.py 等更新脚本通过此函数验证数据完整性。
    """
    try:
        from backend.services.data_source import verify_data_sources as _ds_verify
        return _ds_verify(verbose=verbose)
    except Exception as e:
        return {'status': 'fail', 'error': str(e), 'checks': [], 'pass_count': 0, 'fail_count': 1}


# ====== 自选股 ======
def _load_watchlist_from_disk():
    raw = _load_json(WATCHLIST_PATH, {})
    return raw.get('stocks', [])

def get_watchlist():
    """返回 [{'code':..., 'name':..., 'direction':...}, ...]（走缓存，TTL=10s）"""
    return cache.get('watchlist', _load_watchlist_from_disk, ttl=10)

def get_watchlist_by_direction():
    """返回 {direction: [{'code':..., 'name':...}, ...]}"""
    wl = get_watchlist()
    result = {}
    for s in wl:
        d = s.get('direction', '其他')
        result.setdefault(d, []).append(s)
    return result

# ====== 行业地图 ======
def get_industry_map():
    """返回 {code: {name, ths_industry, ...}}（走缓存，TTL=60s）"""
    return cache.get('industry_map', lambda: _load_json(INDUSTRY_MAP_PATH, {}), ttl=60)

def save_industry_map(data):
    """原子保存行业映射，清缓存"""
    _atomic_save_json(INDUSTRY_MAP_PATH, data)
    cache.invalidate('industry_map')


# ====== 概念板块映射 ======
def get_concept_list():
    """返回 {code: {name, stock_count, stocks}}（走缓存，TTL=60s）"""
    return cache.get('concept_list', lambda: _load_json(CONCEPT_LIST_PATH, {}), ttl=60)


def save_concept_list(data):
    """原子保存概念列表，清缓存"""
    _atomic_save_json(CONCEPT_LIST_PATH, data)
    cache.invalidate('concept_list')


def get_stock_concept_map():
    """返回 {code: {code, name, concept_codes, concept_names}}（走缓存，TTL=60s）"""
    return cache.get('stock_concept_map', lambda: _load_json(STOCK_CONCEPT_MAP_PATH, {}), ttl=60)


def save_stock_concept_map(data):
    """原子保存个股概念映射，清缓存"""
    _atomic_save_json(STOCK_CONCEPT_MAP_PATH, data)
    cache.invalidate('stock_concept_map')


# ====== 股票搜索 ======
def resolve_stock(query, stocks=None):
    """搜索股票：精确code→模糊code→模糊name→全市场搜索
    Returns: (matched_code, matched_direction, matched_name) 或 (None, None, None)
    """
    if stocks is None:
        stocks = get_all_stocks()
    q = query.strip()
    # 1. 精确code匹配
    for sec, ss in stocks.items():
        if q in ss:
            name = ss[q][0].get('name', q) if ss[q] else q
            return q, sec, name
    # 2. 模糊code匹配
    for sec, ss in stocks.items():
        for code in ss:
            if q in code or code.endswith(q):
                name = ss[code][0].get('name', code) if ss[code] else code
                return code, sec, name
    # 3. 模糊name匹配
    for sec, ss in stocks.items():
        for code, kls in ss.items():
            name = kls[0].get('name', '') if kls else ''
            if q in name:
                return code, sec, name
    # 3.5 拼音首字母匹配
    try:
        from pypinyin import lazy_pinyin, Style
        _py_cache = {}
        q_lower = q.lower()
        # 只检查字母查询（纯中文不进入此分支）
        if q_lower.isascii() and q_lower.isalpha():
            for sec, ss in stocks.items():
                for code, kls in ss.items():
                    if code in _py_cache:
                        initials = _py_cache[code]
                    else:
                        name = kls[0].get('name', '') if kls else ''
                        if not name:
                            continue
                        initials = ''.join(p[0] for p in lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()
                        _py_cache[code] = initials
                    if q_lower in initials:
                        return code, sec, kls[0].get('name', code) if kls else code
    except ImportError:
        pass
    # 4. 全市场搜索
    market_results = search_stock_full_market(q, max_results=1)
    if market_results:
        m = market_results[0]
        stocks = get_all_stocks()
        for sec, ss in stocks.items():
            if m['code'] in ss:
                return m['code'], sec, m['name']
    return None, None, None

def search_stock_full_market(query, max_results=20):
    """先查本地缓存，再查全市场股票列表
    
    返回 [{'code': str, 'name': str, 'direction': str, 'industry': str, 'has_data': bool}]
    """
    q = query.strip().lower()
    if not q:
        return []
    
    stocks_data = get_all_stocks()
    imap = get_industry_map()
    results = []
    seen = set()
    
    # 第1轮：本地缓存
    for sec, codes in stocks_data.items():
        for code, kls in codes.items():
            if len(results) >= max_results:
                break
            if code in seen:
                continue
            name = kls[0].get('name', '') if kls else ''
            if q in code or q in name.lower():
                seen.add(code)
                info = imap.get(code, {})
                results.append({
                    'code': code, 'name': name,
                    'direction': sec,
                    'industry': info.get('ths_industry', ''),
                    'has_data': True,
                })
        if len(results) >= max_results:
            break
    
    # 第2轮：全市场（本地没有的）
    if len(results) < max_results:
        _codes = _load_json(ALL_CODES_PATH, {})
        if not _codes:
            # 首次运行，拉取全市场列表并缓存
            try:
                import akshare as ak
                df = ak.stock_info_a_code_name()
                _codes = dict(zip(df['code'], df['name']))
                _save_json(ALL_CODES_PATH, _codes)
            except:
                pass
        for code, name in _codes.items():
            if len(results) >= max_results:
                break
            if code in seen:
                continue
            if q in code or q in name.lower():
                seen.add(code)
                # 查行业映射
                info = imap.get(code, {})
                results.append({
                    'code': code, 'name': name,
                    'direction': info.get('direction', ''),
                    'industry': info.get('ths_industry', ''),
                    'has_data': seen_local(code, stocks_data),
                })
    
    return results


def seen_local(code, stocks_data):
    """检查股票是否在本地缓存中"""
    for sec, codes in stocks_data.items():
        if code in codes:
            return True
    return False


def ensure_stock_data(code):
    """确保股票在本地缓存中有K线数据，没有则从腾讯接口拉取
    
    返回: (success, message)
    """
    stocks_data = get_all_stocks()
    imap = get_industry_map()
    
    # 检查是否已有
    local_code = code
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if code.startswith(pfx):
            local_code = code[len(pfx):]
            break
    local_code = local_code[-6:] if len(local_code) >= 6 else local_code
    
    for sec, codes in stocks_data.items():
        if local_code in codes:
            return (True, '已有数据')
    
    # 没有，拉取
    try:
        import requests
        prefix = 'sh' if local_code.startswith('6') else 'sz'
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{local_code},day,,,60,qfq'
        r = requests.get(url, timeout=15)
        raw = r.json()
        data_node = raw.get('data', {})
        if not isinstance(data_node, dict):
            return (False, f'API返回异常: data字段类型={type(data_node).__name__}')
        klines_raw = data_node.get(f'{prefix}{local_code}', {}).get('qfqday', [])
        if not klines_raw or len(klines_raw) < 5:
            return (False, f'数据不足: {len(klines_raw)}条')
        
        # 转格式
        klines = []
        for k in klines_raw:
            klines.append({
                'date': k[0].replace('-', ''),
                'open': float(k[1]), 'close': float(k[2]),
                'high': float(k[3]), 'low': float(k[4]),
                'volume': int(float(k[5])),
                'name': next((v['name'] for v in [imap.get(local_code, {})] if v.get('name')), local_code),
            })
        
        # 找它的THS行业归属（通过行业板块成分股反查）
        ths_industry = imap.get(local_code, {}).get('ths_industry', '')
        if not ths_industry:
            # 暂存到未知行业
            ths_industry = '未知'
            direction = ''
        else:
            direction = imap.get(local_code, {}).get('direction', '')
        
        # findBy: K线数据已由 update_stock_data.py 统一更新
        return (True, f'已拉取{len(klines)}天数据')
    except Exception as e:
        return (False, f'拉取失败: {e}')

# ====== 财务数据 ======
def get_financial_cache():
    return _load_json(FINANCIAL_CACHE_PATH, {})

def save_financial_cache(data):
    _save_json(FINANCIAL_CACHE_PATH, data)

def get_profit_quality_results():
    return _load_json(PROFIT_QUALITY_PATH, {})

def save_profit_quality_results(data):
    _save_json(PROFIT_QUALITY_PATH, data)

# ====== 持仓与交易 ======
def get_holdings():
    return _load_json(HOLDINGS_PATH, [])

def save_holdings(data):
    _save_json(HOLDINGS_PATH, data)

def get_trades():
    return _load_json(TRADES_PATH, [])

def save_trades(data):
    _save_json(TRADES_PATH, data)

# ====== 扫描结果 ======
def get_latest_scan():
    return _load_json(LATEST_SCAN_PATH, {})

def save_latest_scan(data):
    _save_json(LATEST_SCAN_PATH, data)

# ====== 复盘存档 ======
def get_review_archive(date_str=None):
    """date_str: YYYY-MM-DD 或 None（读取最新）"""
    if date_str:
        return _load_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), {})
    # 找最新
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return {}
    files = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
    if not files:
        return {}
    return _load_json(os.path.join(REVIEW_ARCHIVE_DIR, files[-1]), {})

def save_review_archive(date_str, data):
    _save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), data)

def get_review_latest_date():
    """返回存档中最新复盘日期 YYYY-MM-DD"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return ''
    files = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
    return files[-1].replace('.json', '') if files else ''

# ====== 缓存（动量/板块/行业） ======
def get_cache_path(name, date_str=None):
    """返回缓存文件路径，如 get_cache_path('momentum', '2026-05-21')"""
    if date_str:
        date_str = date_str.replace('-', '')
        return os.path.join(CACHE_DIR, f'{name}_{date_str}.json')
    return CACHE_DIR

def save_cache(name, data, date_str=None):
    path = get_cache_path(name, date_str)
    _save_json(path, data)

def load_cache(name, date_str=None):
    return _load_json(get_cache_path(name, date_str), {})

# ====== 关键点 ======
def get_key_points_dir():
    return KEY_POINTS_DIR

# ====== 快速验证 ======
if __name__ == '__main__':
    stocks = get_all_stocks()
    print(f'方向数: {len(stocks)}')
    codes = set()
    for sec, ss in stocks.items():
        codes.update(ss.keys())
    print(f'股票数: {len(codes)}')
    print(f'最新日期: {get_last_updated()}')
    wl = get_watchlist()
    print(f'自选股: {len(wl)} 只')
    h = get_holdings()
    print(f'持仓: {len(h)} 只')


def calc_sector_leaders(stock_codes, kline_index, top_n=5):
    """计算板块领涨股（按5日涨跌幅排名）

    从 review_service._calc_stock_leaders 提取的公共版本。
    Args:
        stock_codes: 板块内个股代码列表
        kline_index: {code: [kline,...]} 索引
        top_n: 返回前N只（默认5）
    Returns:
        [{code, name, chg_1d, chg_5d, tag}, ...]
    """
    candidates = []
    for _c in stock_codes:
        _kls = kline_index.get(_c)
        if not _kls or len(_kls) < 5:
            continue
        _close_now = _kls[-1]['close']
        _close_1d = _kls[-2]['close'] if len(_kls) >= 2 else _close_now
        _close_5d = _kls[-5]['close'] if len(_kls) >= 5 else _close_now
        _chg_1d = round((_close_now - _close_1d) / _close_1d * 100, 1)
        _chg_5d = round((_close_now - _close_5d) / _close_5d * 100, 1)
        _name = _kls[0].get('name', _c) if isinstance(_kls[0], dict) else _c
        _tag = '🏆领涨' if _chg_5d >= 5 else ('💪中军' if _chg_1d > 0 else '')
        candidates.append({
            'code': _c,
            'name': _name or _c,
            'chg_1d': _chg_1d,
            'chg_5d': _chg_5d,
            'tag': _tag,
        })
    candidates.sort(key=lambda x: -x['chg_5d'])
    return candidates[:top_n]


def build_kline_index(all_stocks_data=None):
    """从 all_stocks 数据构建 {code: [kline,...]} 索引

    Args:
        all_stocks_data: get_all_stocks() 返回值（可选，不传则自动加载）
    Returns: {code: [kline,...]}
    """
    from backend.config import ALL_STOCKS_PATH
    import os, json
    if all_stocks_data is None:
        if os.path.isfile(ALL_STOCKS_PATH):
            with open(ALL_STOCKS_PATH) as _f:
                _raw = json.load(_f)
            all_stocks_data = _raw.get('stocks', {})
        else:
            all_stocks_data = get_all_stocks()
    index = {}
    for _dir, _ss in all_stocks_data.items():
        if isinstance(_ss, dict):
            for _code, _kls in _ss.items():
                index[_code] = _kls
    return index


def build_industry_stock_map(industry_map_data=None):
    """从行业映射构建 {行业名: [code,...]} 索引

    Args:
        industry_map_data: get_industry_map() 返回值（可选）
    Returns: {industry_name: [code, ...]}
    """
    from backend.config import INDUSTRY_MAP_PATH
    import os, json
    if industry_map_data is None:
        if os.path.isfile(INDUSTRY_MAP_PATH):
            with open(INDUSTRY_MAP_PATH) as _f:
                industry_map_data = json.load(_f)
        else:
            industry_map_data = {}
    mapping = {}
    for _code, _info in industry_map_data.items():
        _ind = _info.get('ths_industry', '')
        if _ind:
            mapping.setdefault(_ind, []).append(_code)
    return mapping
