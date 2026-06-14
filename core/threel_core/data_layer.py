"""
数据层 — 共享数据访问门面（供 3l-server 和 3l-analysis 共用）

从 MySQL + JSON 读取数据，不依赖 server/backend。
所有对外接口与原有 server/backend/core/data_layer.py 兼容。

共享 6 个只读函数：
  get_all_stocks()       — 从 MySQL 读取K线，按方向分组
  get_stock_klines()     — 单只股票K线
  get_watchlist()        — 自选股（JSON）
  get_industry_map()     — 行业映射（JSON）
  resolve_stock()        — 股票搜索
  search_stock_full_market() — 全市场搜索
"""
import json
import os
from typing import List, Optional

from threel_core.db import query_stock_klines, get_last_stock_date

# ── 数据目录 ──
_DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
WATCHLIST_PATH = os.path.join(_DATA_DIR, 'config', 'watchlist.json')
INDUSTRY_MAP_PATH = os.path.join(_DATA_DIR, 'computed', 'stock_industry_map.json')
ALL_CODES_PATH = os.path.join(_DATA_DIR, 'public', 'all_a_stocks.json')

# 向后兼容常量（buy_point_detection.py 等内部模块使用）
PROFIT_QUALITY_PATH = os.path.join(_DATA_DIR, 'computed', 'profit_quality.json')
ALL_STOCKS_PATH = os.path.join(_DATA_DIR, 'all_stocks_60d.json')  # 可能不存在，由调用方处理


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


# ====== K线数据（MySQL）======

def get_all_stocks(limit: int = 60) -> dict:
    """从 MySQL 读取K线数据，按 watchlist 方向分组

    Returns:
        {方向: {code: [{date, open, close, high, low, volume}, ...]}, ...}
        包含 last_updated 字段
    """
    wl = get_watchlist()
    if not wl:
        return {'last_updated': ''}

    # 收集所有需要查询的股票代码
    all_codes = []
    code_info = {}  # {code: direction}
    for s in wl:
        code = s.get('code', '')
        if code:
            all_codes.append(code)
            code_info[code] = s.get('direction', '其他')

    if not all_codes:
        return {'last_updated': ''}

    # MySQL 查询需要含后缀的代码
    lookup_codes = _ensure_suffix(all_codes)
    stock_data = query_stock_klines(lookup_codes, limit=limit)

    # 按方向分组
    result = {}
    name_map = _load_json(INDUSTRY_MAP_PATH, {})
    wl_by_code = {s.get('code', ''): s.get('name', '') for s in wl}
    for code in all_codes:
        lookup = _ensure_suffix([code])[0]
        klines = stock_data.get(lookup, [])
        direction = code_info.get(code, '其他')
        if direction not in result:
            result[direction] = {}
        # 补 name
        if klines:
            info = name_map.get(code, {})
            name = info.get('name', '') if isinstance(info, dict) else ''
            if not name:
                name = wl_by_code.get(code, '')
            if name:
                for k in klines:
                    k['name'] = name
        result[direction][code] = klines

    last_date = get_last_stock_date()
    result['last_updated'] = last_date or ''

    return result


def get_stock_klines(code: str, direction: Optional[str] = None,
                     stocks: Optional[dict] = None) -> list:
    """获取单只股票K线列表

    优先从 stocks 参数找，回退 MySQL 查询。

    Args:
        code: 股票代码（6位纯数字或含后缀 002916.SZ）
        direction: 可选，加速查找
        stocks: get_all_stocks() 返回值的缓存

    Returns:
        [{date, open, close, high, low, volume}, ...]
    """
    # 确保为 6 位纯数字用于字典查找
    plain_code = code[-6:] if len(code) >= 6 and '.' not in code else code
    if '.' in code:
        plain_code = code.split('.')[0]

    if stocks is None:
        stocks = get_all_stocks()

    if direction and direction in stocks and plain_code in stocks[direction]:
        return stocks[direction][plain_code]
    for sec, codes in stocks.items():
        if isinstance(codes, dict) and plain_code in codes:
            return codes[plain_code]

    # MySQL 回退
    lookup_codes = _ensure_suffix([plain_code])
    stock_data = query_stock_klines(lookup_codes, limit=60)
    if lookup_codes and stock_data.get(lookup_codes[0]):
        return stock_data[lookup_codes[0]]

    return []


def _ensure_suffix(codes: List[str]) -> List[str]:
    """为纯数字代码添加交易所后缀（用于MySQL查询）"""
    result = []
    for c in codes:
        c = c.strip()
        if '.' in c:
            result.append(c)
        elif c.startswith('6'):
            result.append(f'{c}.SH')
        elif c.startswith('0') or c.startswith('3'):
            result.append(f'{c}.SZ')
        elif c.startswith('4') or c.startswith('8') or c.startswith('9'):
            result.append(f'{c}.BJ')
        else:
            result.append(f'{c}.SZ')
    return result


def get_last_updated() -> str:
    """返回最新交易日 YYYYMMDD"""
    date = get_last_stock_date()
    return date or ''


# ====== 自选股（JSON）======

def get_watchlist() -> list:
    """返回 [{'code':..., 'name':..., 'direction':...}, ...]"""
    raw = _load_json(WATCHLIST_PATH, {})
    return raw.get('stocks', [])


def get_watchlist_by_direction() -> dict:
    """返回 {direction: [{'code':..., 'name':...}, ...]}"""
    wl = get_watchlist()
    result = {}
    for s in wl:
        d = s.get('direction', '其他')
        result.setdefault(d, []).append(s)
    return result


# ====== 行业映射（JSON）======

def get_industry_map() -> dict:
    """返回 {code: {name, ths_industry, ...}}"""
    return _load_json(INDUSTRY_MAP_PATH, {})


# ====== 股票搜索 ======

def resolve_stock(query: str, stocks: Optional[dict] = None):
    """搜索股票：精确code→模糊code→模糊name→全市场搜索

    Returns:
        (matched_code, matched_direction, matched_name) 或 (None, None, None)
    """
    if stocks is None:
        stocks = get_all_stocks()
    q = query.strip().lower()

    # 1. 精确code匹配
    for sec, ss in stocks.items():
        if not isinstance(ss, dict):
            continue
        for code in ss:
            if q == code.lower():
                name = ss[code][0].get('name', code) if ss[code] else code
                return code, sec, name

    # 2. 模糊code匹配
    for sec, ss in stocks.items():
        if not isinstance(ss, dict):
            continue
        for code in ss:
            if q in code.lower() or code.endswith(q):
                name = ss[code][0].get('name', code) if ss[code] else code
                return code, sec, name

    # 3. 模糊name匹配
    for sec, ss in stocks.items():
        if not isinstance(ss, dict):
            continue
        for code, kls in ss.items():
            name = kls[0].get('name', '') if kls else ''
            if q in name.lower():
                return code, sec, name

    # 3.5 拼音首字母匹配
    try:
        from pypinyin import lazy_pinyin, Style
        q_lower = q.lower()
        if q_lower.isascii() and q_lower.isalpha():
            for sec, ss in stocks.items():
                if not isinstance(ss, dict):
                    continue
                for code, kls in ss.items():
                    name = kls[0].get('name', '') if kls else ''
                    if not name:
                        continue
                    initials = ''.join(p[0] for p in lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()
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
            if isinstance(ss, dict) and m['code'] in ss:
                return m['code'], sec, m['name']
    return None, None, None


def search_stock_full_market(query: str, max_results: int = 20) -> list:
    """全市场股票搜索

    Returns:
        [{'code': str, 'name': str, 'direction': str, 'industry': str, 'has_data': bool}, ...]
    """
    q = query.strip().lower()
    if not q:
        return []

    stocks_data = get_all_stocks()
    imap = get_industry_map()
    results = []
    seen = set()

    # 第1轮：watchlist 中搜索
    for sec, codes in stocks_data.items():
        if not isinstance(codes, dict):
            continue
        for code, kls in codes.items():
            if len(results) >= max_results:
                break
            if code in seen:
                continue
            name = kls[0].get('name', '') if kls else ''
            if q in code.lower() or q in name.lower():
                seen.add(code)
                info = imap.get(code, {})
                if isinstance(info, dict):
                    industry = info.get('ths_industry', '')
                else:
                    industry = str(info) if info else ''
                results.append({
                    'code': code, 'name': name,
                    'direction': sec,
                    'industry': industry,
                    'has_data': True,
                })

    # 第2轮：全市场（从 all_codes.json）
    if len(results) < max_results:
        _codes = _load_json(ALL_CODES_PATH, {})
        if not _codes:
            try:
                import akshare as ak
                df = ak.stock_info_a_code_name()
                _codes = dict(zip(df['code'], df['name']))
            except Exception:
                pass
        for code, name in _codes.items():
            if len(results) >= max_results:
                break
            if code in seen:
                continue
            if q in code.lower() or q in name.lower():
                seen.add(code)
                info = imap.get(code, {})
                if isinstance(info, dict):
                    industry = info.get('ths_industry', '')
                else:
                    industry = str(info) if info else ''
                results.append({
                    'code': code, 'name': name,
                    'direction': '',
                    'industry': industry,
                    'has_data': code in seen_local(code, stocks_data),
                })

    return results


def seen_local(code: str, stocks_data: dict) -> bool:
    """检查股票是否在本地缓存中"""
    for sec, codes in stocks_data.items():
        if isinstance(codes, dict) and code in codes:
            return True
    return False
