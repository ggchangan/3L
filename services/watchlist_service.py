"""
自选股服务 — 自选股管理
"""
import json, os
from config import WATCHLIST_PATH, ALL_STOCKS_PATH, ALL_CODES_PATH, PINYIN_PATH

from services.logger import get_logger

log = get_logger(__name__)


def get_watchlist():
    """获取自选股列表"""
    if os.path.isfile(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'stocks': [], 'count': 0}


def save_watchlist(data):
    """保存自选股列表，新增股票自动拉取数据"""
    from scripts.data_layer import ensure_stock_data
    from scripts.cache_layer import cache
    import config as cfg
    with open(WATCHLIST_PATH, 'r', encoding='utf-8') as _old_f:
        old_data = json.load(_old_f)
    old_codes = {s['code'] for s in old_data.get('stocks', [])}
    new_stocks = data.get('stocks', [])
    new_codes = {s['code'] for s in new_stocks}
    added = new_codes - old_codes
    for code in added:
        ensure_stock_data(code)
    cfg.atomic_json_dump(data, WATCHLIST_PATH, indent=2)
    cache.invalidate('watchlist')
    log.info('自选股已保存 (%d只, 新增%d只)', len(new_stocks), len(added))
    return {'success': True, 'count': len(new_stocks)}


def _build_dir_price_map():
    """构建 代码→(direction, price) 映射（从 all_stocks_60d.json）"""
    m = {}
    if os.path.isfile(ALL_STOCKS_PATH):
        with open(ALL_STOCKS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for direction, stocks in data.get('stocks', {}).items():
            for code, klines in stocks.items():
                price = klines[-1]['close'] if klines else 0
                m[code] = (direction, price)
    return m


def search_stocks(query):
    """搜索股票（支持代码或名称）
    
    搜索池为全部A股（all_stock_codes.json），
    若有方向/价格信息则补充显示。
    """
    query = query.strip().lower()
    if not query:
        return []

    # 加载全部A股 代码→名称 映射
    if not os.path.isfile(ALL_CODES_PATH):
        log.warning('all_stock_codes.json 不存在，无法搜索')
        return []
    with open(ALL_CODES_PATH, 'r', encoding='utf-8') as f:
        all_codes = json.load(f)

    # 加载拼音首字母映射
    pinyin_map = {}
    if os.path.isfile(PINYIN_PATH):
        with open(PINYIN_PATH, 'r', encoding='utf-8') as f:
            pinyin_map = json.load(f)

    # 加载方向/价格信息（部分股票有）
    dir_price = _build_dir_price_map()

    results = []
    for code, name in all_codes.items():
        name_lower = (name or '').lower()
        pinyin = pinyin_map.get(code, '')
        if not (query in code.lower() or (name_lower and query in name_lower) or (pinyin and query in pinyin)):
            continue
        direction, price = dir_price.get(code, ('其他', 0))
        results.append({
            'code': code,
            'name': name or code,
            'direction': direction,
            'price': price,
        })
        if len(results) >= 30:
            return results

    return results
