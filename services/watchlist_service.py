"""
自选股服务 — 自选股管理
"""
import json, os
from config import WATCHLIST_PATH, ALL_STOCKS_PATH
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
    from scripts.data_layer import WATCHLIST_PATH, ensure_stock_data
    from scripts.cache_layer import cache
    with open(WATCHLIST_PATH, 'r', encoding='utf-8') as _old_f:
        old_data = json.load(_old_f)
    old_codes = {s['code'] for s in old_data.get('stocks', [])}
    new_stocks = data.get('stocks', [])
    new_codes = {s['code'] for s in new_stocks}
    added = new_codes - old_codes
    for code in added:
        ensure_stock_data(code)
    config.atomic_json_dump(data, WATCHLIST_PATH, indent=2)
    cache.invalidate('watchlist')
    log.info('自选股已保存 (%d只, 新增%d只)', len(new_stocks), len(added))
    return {'success': True, 'count': len(new_stocks)}


def search_stocks(query):
    """搜索股票（支持代码或名称）
    从全市场数据中搜索匹配的股票
    """
    query = query.strip().lower()
    if not query:
        return []
    results = []
    if os.path.isfile(ALL_STOCKS_PATH):
        with open(ALL_STOCKS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for direction, stocks in data.get('stocks', {}).items():
            for code, klines in stocks.items():
                name = klines[-1].get('name', '') if klines else ''
                if query in code.lower() or query in name.lower():
                    price = klines[-1]['close'] if klines else 0
                    results.append({
                        'code': code, 'name': name,
                        'direction': direction, 'price': price
                    })
                    if len(results) >= 30:
                        return results
    return results
