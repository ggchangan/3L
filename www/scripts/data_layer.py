#!/usr/bin/env python3
"""
统一数据层 — 所有股票数据的单一入口
所有文件路径只在此定义，其余模块通过此层读写
"""
import json, os
from datetime import datetime

# ====== 数据目录 ======
DATA_DIR = '/home/ubuntu/data/3l'
WWW_DIR = '/home/ubuntu/www'
CACHE_DIR = os.path.join(WWW_DIR, 'data', 'cache')
PRIVATE_DIR = os.path.join(WWW_DIR, 'private')

# ====== 文件路径 ======
ALL_STOCKS_PATH       = os.path.join(DATA_DIR, 'all_stocks_60d.json')
WATCHLIST_PATH         = os.path.join(DATA_DIR, 'watchlist.json')
INDUSTRY_MAP_PATH      = os.path.join(DATA_DIR, 'stock_industry_map.json')
SUBSECTOR_PATH         = os.path.join(DATA_DIR, 'sub_sector_clusters.json')
FINANCIAL_CACHE_PATH   = os.path.join(DATA_DIR, 'financial_data_cache.json')
PROFIT_QUALITY_PATH    = os.path.join(DATA_DIR, 'profit_quality_results.json')
INDEX_DATA_PATH        = os.path.join(DATA_DIR, 'index_sh_data.json')
INDUSTRY_LEADERS_PATH  = os.path.join(DATA_DIR, 'industry_leaders.json')
LATEST_SCAN_PATH       = os.path.join(DATA_DIR, 'latest_scan_result.json')
KEY_POINTS_DIR         = os.path.join(DATA_DIR, 'key_points')
HOLDINGS_PATH          = os.path.join(PRIVATE_DIR, 'holdings.json')
TRADES_PATH            = os.path.join(PRIVATE_DIR, 'trades.json')
REVIEW_ARCHIVE_DIR     = os.path.join(PRIVATE_DIR, 'review_archive')
REVIEW_CHARTS_DIR      = os.path.join(WWW_DIR, 'review_charts')
SCRIPTS_DIR            = os.path.join(WWW_DIR, 'scripts')
SIMULATION_DIR         = os.path.join(DATA_DIR, 'simulation')
OUTPUT_DIR             = os.path.join(DATA_DIR, 'simulation', 'v3')

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

# ====== K线数据 ======
def get_all_stocks():
    """返回 {方向: {code: [klines]}} 格式的K线数据"""
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('stocks', raw)

def get_last_updated():
    """返回缓存最新交易日 YYYYMMDD"""
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('last_updated', '')

def save_all_stocks(stocks, last_updated=None):
    """保存K线数据"""
    data = {'last_updated': last_updated or datetime.now().strftime('%Y%m%d'), 'stocks': stocks}
    _save_json(ALL_STOCKS_PATH, data)

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

# ====== 自选股 ======
def get_watchlist():
    """返回 [{'code':..., 'name':..., 'direction':...}, ...]"""
    raw = _load_json(WATCHLIST_PATH, {})
    return raw.get('stocks', [])

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
    """返回 {code: {name, ths_industry, ...}}"""
    return _load_json(INDUSTRY_MAP_PATH, {})

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
