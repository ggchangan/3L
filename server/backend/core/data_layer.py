#!/usr/bin/env python3
"""
统一数据层 — 所有股票数据的单一入口
所有文件路径集中定义在 config.py，此处通过 import 引用
"""
import json, os
from datetime import datetime
from backend.core.cache_layer import cache
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
        print(f"[data_layer] ⚠️ 读 {path} 失败: {e}")
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
    """返回 {方向: {code: [klines]}} 格式的K线数据（走缓存，TTL=30s）"""
    return cache.get('all_stocks', _load_all_stocks_from_disk, ttl=30)

def get_last_updated():
    """返回缓存最新交易日 YYYYMMDD"""
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('last_updated', '')

def save_all_stocks(stocks, last_updated=None):
    """原子保存K线数据"""
    data = {'last_updated': last_updated or datetime.now().strftime('%Y%m%d'), 'stocks': stocks}
    _atomic_save_json(ALL_STOCKS_PATH, data)
    cache.invalidate('all_stocks')

def load_all_stocks_uncached():
    """强制从磁盘读取K线数据（不走缓存），供更新脚本使用"""
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('stocks', raw)

def get_stock_klines(code, direction=None, stocks=None):
    """获取单只股票K线列表，stocks 为 get_all_stocks() 返回值"""
    if stocks is None:
        stocks = get_all_stocks()
    if direction and direction in stocks and code in stocks[direction]:
        return stocks[direction][code]
    # 遍历所有方向找
    for sec, codes in stocks.items():
        if code in codes:
            return codes[code]
    return []


# ====== 指数数据（多指数结构）======
# index_sh_data.json 格式: {last_updated, indices: {code: {name, klines: [{date, open, close, high, low, volume}]}}}
INDEX_CODE = '000985'

INDEX_CODES = {
    '000001': '上证指数',
    '000688': '科创50',
    '000985': '中证全指',
}

def get_index_data():
    """返回完整指数数据 {last_updated, indices: {code: {name, klines}}}（走缓存，TTL=60s）"""
    return cache.get('index_data', lambda: _load_json(INDEX_DATA_PATH, {}), ttl=60)

def save_index_data(data):
    """原子保存指数数据"""
    _atomic_save_json(INDEX_DATA_PATH, data)
    cache.invalidate('index_data')

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
    """返回 {last_updated, industries: {板块名: [klines]}, concepts: {板块名: [klines]}}（走缓存，TTL=60s）"""
    return cache.get('sector_daily', lambda: _load_json(SECTOR_DAILY_PATH, {}), ttl=60)

def save_sector_daily(data):
    """原子保存板块日K线数据"""
    _atomic_save_json(SECTOR_DAILY_PATH, data)
    cache.invalidate('sector_daily')

def load_sector_daily_uncached():
    """强制从磁盘读取板块日K线数据（不走缓存），供更新脚本使用"""
    return _load_json(SECTOR_DAILY_PATH, {})


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
