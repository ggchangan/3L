"""
自选股服务 — 自选股管理 + 方向管理
"""
import json
import os
import config as cfg
from config import WATCHLIST_PATH, ALL_STOCKS_PATH, ALL_CODES_PATH, PINYIN_PATH
from config import atomic_json_dump

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
    new_stocks = data.get('stocks', [])
    # 安全保护：禁止用少量股票覆盖大量自选股
    with open(WATCHLIST_PATH, 'r', encoding='utf-8') as _old_f:
        old_data = json.load(_old_f)
    old_codes = {s['code'] for s in old_data.get('stocks', [])}
    if len(old_codes) > 50 and len(new_stocks) < 10:
        return {'success': False, 'error': f'安全保护：不能将{len(old_codes)}只自选股覆盖为{len(new_stocks)}只'}
    new_codes = {s['code'] for s in new_stocks}
    added = new_codes - old_codes
    for code in added:
        ensure_stock_data(code)
    atomic_json_dump(data, WATCHLIST_PATH, indent=2)
    cache.invalidate('watchlist')
    log.info('自选股已保存 (%d只, 新增%d只)', len(new_stocks), len(added))
    return {'success': True, 'count': len(new_stocks)}


def _build_dir_price_map():
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
    """搜索股票（支持代码/名称/拼音）"""
    query = query.strip().lower()
    if not query:
        return []

    if not os.path.isfile(ALL_CODES_PATH):
        log.warning('all_stock_codes.json 不存在，无法搜索')
        return []
    with open(ALL_CODES_PATH, 'r', encoding='utf-8') as f:
        all_codes = json.load(f)

    pinyin_map = {}
    if os.path.isfile(PINYIN_PATH):
        with open(PINYIN_PATH, 'r', encoding='utf-8') as f:
            pinyin_map = json.load(f)

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


# ── 方向管理 ────────────────────────────────────────


def _load_watchlist(path=None):
    """加载 watchlist.json，返回数据字典"""
    p = path or WATCHLIST_PATH
    if os.path.isfile(p):
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'stocks': [], 'count': 0}


def _save_watchlist_data(data, path=None):
    """保存 watchlist.json（线程安全）"""
    p = path or WATCHLIST_PATH
    atomic_json_dump(data, p, indent=2)


def get_all_directions(path=None):
    """获取全部方向及其启用状态、股票计数"""
    data = _load_watchlist(path)
    directions = data.get('directions', {})
    stocks = data.get('stocks', [])
    dir_counts = {}
    for s in stocks:
        d = s.get('direction', '其他')
        dir_counts[d] = dir_counts.get(d, 0) + 1
    result = {}
    for name, info in directions.items():
        result[name] = {
            'enabled': info.get('enabled', True),
            'count': dir_counts.get(name, 0),
        }
    return result


def get_directions(path=None):
    """获取方向字典 {name: {enabled: bool}}"""
    data = _load_watchlist(path)
    return data.get('directions', {})


def get_enabled_directions(path=None):
    """获取启用方向名称列表（兼容老数据）"""
    data = _load_watchlist(path)
    directions = data.get('directions')
    if not directions:  # None 或 {} 都走兼容
        stocks = data.get('stocks', [])
        dirs = {s.get('direction', '其他') for s in stocks if s.get('direction')}
        return sorted(dirs)
    return sorted([name for name, info in directions.items() if info.get('enabled', True)])


def is_enabled_direction(direction, path=None):
    """判断某个方向是否启用"""
    return direction in get_enabled_directions(path)


def add_direction(name, path=None):
    """添加新方向（默认为启用）"""
    name = name.strip()
    if not name:
        return {'success': False, 'error': '方向名称不能为空'}
    if name in ('全部', '其他'):
        return {'success': False, 'error': '不能添加系统保留方向'}
    data = _load_watchlist(path)
    if 'directions' not in data:
        migrate_directions(path)
        data = _load_watchlist(path)
    directions = data.setdefault('directions', {})
    if name in directions:
        return {'success': False, 'error': f'方向 "{name}" 已存在'}
    directions[name] = {'enabled': True}
    _save_watchlist_data(data, path)
    return {'success': True, 'name': name}


def remove_direction(name, path=None):
    """删除方向，该方向股票归入'其他'"""
    if name == '其他':
        return {'success': False, 'error': '不能删除"其他"方向'}
    data = _load_watchlist(path)
    directions = data.get('directions', {})
    if name not in directions:
        return {'success': False, 'error': f'方向 "{name}" 不存在'}
    for s in data.get('stocks', []):
        if s.get('direction') == name:
            s['direction'] = '其他'
    del directions[name]
    _save_watchlist_data(data, path)
    return {'success': True}


def set_direction_enabled(name, enabled, path=None):
    """设置方向启用/禁用"""
    data = _load_watchlist(path)
    directions = data.get('directions', {})
    if name not in directions:
        return {'success': False, 'error': f'方向 "{name}" 不存在'}
    directions[name]['enabled'] = enabled
    _save_watchlist_data(data, path)
    return {'success': True}


def suggest_directions(path=None):
    """从现有数据提供方向建议（基于行业等）"""
    data = _load_watchlist(path)
    stocks = data.get('stocks', [])
    existing_dirs = set(data.get('directions', {}).keys())
    industries = set()
    for s in stocks:
        ind = s.get('industry', '')
        if ind and len(ind) <= 6:
            industries.add(ind)
    return sorted(industries - existing_dirs)[:10]


def migrate_directions(path=None):
    """迁移老数据：从股票方向自动生成 directions 字段（全部启用）"""
    data = _load_watchlist(path)
    if 'directions' in data:
        return {'success': True, 'migrated': False}
    stocks = data.get('stocks', [])
    dirs = {}
    for s in stocks:
        d = s.get('direction', '其他')
        if d and d not in dirs:
            dirs[d] = {'enabled': True}
    data['directions'] = dirs
    _save_watchlist_data(data, path)
    return {'success': True, 'migrated': True, 'count': len(dirs)}
