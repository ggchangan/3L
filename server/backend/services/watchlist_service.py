"""
自选股服务 — 自选股管理 + 方向管理
"""
import json
import os
from backend.core import config as cfg
from backend.core.config import WATCHLIST_PATH, ALL_STOCKS_PATH, ALL_CODES_PATH, PINYIN_PATH, INDUSTRY_MAP_PATH, ANALYSIS_CACHE_PATH
from backend.core.config import atomic_json_dump

from backend.core.logger import get_logger

log = get_logger(__name__)


def get_watchlist():
    """获取自选股列表"""
    if os.path.isfile(WATCHLIST_PATH):
        with open(WATCHLIST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'stocks': [], 'count': 0}


def save_watchlist(data, wl_path=None):
    """保存自选股列表（数据由 update_stock_data.py 统一更新）"""
    from backend.data_access.cache_layer import cache
    p = wl_path or WATCHLIST_PATH
    new_stocks = data.get('stocks', [])
    # 安全保护：禁止用少量股票覆盖大量自选股
    try:
        with open(p, 'r', encoding='utf-8') as _old_f:
            old_data = json.load(_old_f)
    except (FileNotFoundError, json.JSONDecodeError):
        old_data = {'stocks': []}
    old_codes = {s['code'] for s in old_data.get('stocks', [])}
    if len(old_codes) > 50 and len(new_stocks) < 10:
        return {'success': False, 'error': f'安全保护：不能将{len(old_codes)}只自选股覆盖为{len(new_stocks)}只'}
    new_codes = {s['code'] for s in new_stocks}
    _save_watchlist_data(data, p)
    cache.invalidate('watchlist')
    log.info('自选股已保存 (%d只)', len(new_stocks))
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


# ════════════════════════════════════════════════════════
# 自选股批量分析 — 逐只计算结构/阶段/偏倚/系统/信号
# ════════════════════════════════════════════════════════

def get_watchlist_analysis(stocks=None, wl=None):
    """自选股批量分析 — 对自选股列表逐只计算结构/阶段/偏倚/系统/信号

    返回 {'stocks': [...], 'count': N}，每个股票条目包含：
      price, change, structure, stage, sector, trading_system,
      trend_bias, signal, trend_stock, profit_model1

    走磁盘缓存（ANALYSIS_CACHE_PATH），
    当 WATCHLIST_PATH 或 ALL_STOCKS_PATH 有变更时自动失效。
    传入 stocks/wl 参数时跳过缓存（用于测试注入）。
    """
    # 未传测试参数 → 尝试缓存
    if stocks is None and wl is None:
        try:
            if os.path.exists(ANALYSIS_CACHE_PATH):
                cache_mtime = os.path.getmtime(ANALYSIS_CACHE_PATH)
                wl_mtime = os.path.getmtime(WATCHLIST_PATH)
                ks_mtime = os.path.getmtime(ALL_STOCKS_PATH)
                # 缓存比数据文件新 → 有效
                if cache_mtime > wl_mtime and cache_mtime > ks_mtime:
                    with open(ANALYSIS_CACHE_PATH, 'r', encoding='utf-8') as f:
                        cached = json.load(f)
                    # 验证缓存股票数量与自选股一致
                    if cached.get('count') == len(_load_watchlist().get('stocks', [])):
                        log.info('watchlist_analysis: 命中缓存')
                        return cached
        except Exception:
            pass

    from backend.core.data_layer import get_all_stocks, get_watchlist, _load_json
    from backend.core.scan_buy_signals import get_full_mainlines

    if stocks is None:
        stocks = get_all_stocks()
    if wl is None:
        wl = get_watchlist()
    imap = _load_json(INDUSTRY_MAP_PATH, {})
    _mainlines = get_full_mainlines()

    # 建倒排索引：code → klines，避免逐方向遍历
    kline_index = {}
    for sec, codes in stocks.items():
        for code, kls in codes.items():
            kline_index[code] = kls

    results = []
    for s in wl:
        code = s['code']
        kls = kline_index.get(code)

        if not kls or len(kls) < 30:
            results.append({
                **s,
                'price': None,
                'change': None,
                'structure': '数据不足',
                'stage': '',
                'sector': imap.get(code, {}).get('ths_industry', '') or s.get('industry', ''),
                'trading_system': '3l',
                'trend_bias': None,
                'signal': 'hold',
                'trend_stock': False,
                'profit_model1': False,
            })
            continue

        today_str = kls[-1]['date']
        today_fmt = f'{today_str[:4]}-{today_str[4:6]}-{today_str[6:8]}'

        # 通过 StockCardService 统一获取卡片数据
        try:
            from backend.services.stock_card_service import get_stock_card
            card = get_stock_card(
                code=code,
                date_str=today_fmt,
                market_position='波中',
                main_lines=_mainlines,
                klines=kls,
            )
        except Exception as e:
            results.append({
                **s,
                'price': round(kls[-1]['close'], 2),
                'change': round((kls[-1]['close'] - kls[-2]['close']) / kls[-2]['close'] * 100, 2) if len(kls) >= 2 else 0,
                'structure': '--',
                'stage': '--',
                'sector': imap.get(code, {}).get('ths_industry', '') or s.get('industry', ''),
                'trading_system': '3l',
                'trend_bias': None,
                'signal': 'hold',
                'trend_stock': False,
                'profit_model1': False,
            })
            continue

        results.append({
            **s,
            'price': card.get('price'),
            'change': card.get('change'),
            'structure': card.get('structure', '--'),
            'stage': card.get('stage', '--'),
            'sector': card.get('sector', '') or s.get('industry', ''),
            'trading_system': card.get('trading_system', '3l'),
            'trend_bias': card.get('trend_bias', None) or card.get('deviation_pct'),
            'signal': card.get('signal', 'hold'),
            'trend_stock': card.get('trend_stock', False),
            'profit_model1': card.get('profit_model1', False),
            # 补充卡片字段
            'buy_point': card.get('buy_point', ''),
            'stop_loss': card.get('stop_loss'),
            'stop_loss_pct': card.get('stop_loss_pct'),
            'mainline_level': card.get('mainline_level', ''),
            'trading_reason': card.get('trading_reason', ''),
            'vol_analysis': card.get('vol_analysis', ''),
            'sector_chg': card.get('sector_chg'),
        })

    result = {'stocks': results, 'count': len(results)}

    # 写缓存
    try:
        os.makedirs(os.path.dirname(ANALYSIS_CACHE_PATH), exist_ok=True)
        atomic_json_dump(result, ANALYSIS_CACHE_PATH)
        log.info('watchlist_analysis: 缓存已更新 (%d只)', len(results))
    except Exception as e:
        log.warning('watchlist_analysis: 缓存写入失败 %s', e)

    return result
