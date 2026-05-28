"""数据层 — 供 shared package 使用

从 DATA_DIR 环境变量读取数据，不依赖 backend.config。
包含 buy_point_detection 和 stock_card 需要的函数。
"""

import json, os

_DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
ALL_STOCKS_PATH = os.path.join(_DATA_DIR, 'all_stocks_60d.json')
PROFIT_QUALITY_PATH = os.path.join(_DATA_DIR, 'profit_quality_results.json')
INDUSTRY_MAP_PATH = os.path.join(_DATA_DIR, 'stock_industry_map.json')
WATCHLIST_PATH = os.path.join(_DATA_DIR, 'watchlist.json')


def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}


def get_industry_map():
    return _load_json(INDUSTRY_MAP_PATH, {})


def get_watchlist():
    raw = _load_json(WATCHLIST_PATH, {})
    return raw.get('stocks', [])


def get_all_stocks():
    raw = _load_json(ALL_STOCKS_PATH, {})
    return raw.get('stocks', raw)


def get_stock_klines(code, direction=None, stocks=None):
    if stocks is None:
        stocks = get_all_stocks()
    if direction and direction in stocks and code in stocks[direction]:
        return stocks[direction][code]
    for sec, codes in stocks.items():
        if code in codes:
            return codes[code]
    return []


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
        q_lower = q.lower()
        if q_lower.isascii() and q_lower.isalpha():
            for sec, ss in stocks.items():
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
            if m['code'] in ss:
                return m['code'], sec, m['name']
    return None, None, None


def search_stock_full_market(query, max_results=20):
    """全市场股票搜索（本地缓存+拼音）"""
    q = query.strip().lower()
    if not q:
        return []

    stocks_data = get_all_stocks()
    imap = get_industry_map()
    results = []
    seen = set()

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
                if isinstance(info, dict):
                    industry = info.get('industry', info.get('name', ''))
                else:
                    industry = str(info) if info else ''
                results.append({
                    'code': code,
                    'name': name,
                    'direction': sec,
                    'industry': industry,
                    'has_data': True,
                })

    # 拼音搜索
    if len(results) < max_results:
        try:
            from pypinyin import lazy_pinyin, Style
            for sec, codes in stocks_data.items():
                for code, kls in codes.items():
                    if len(results) >= max_results:
                        break
                    if code in seen:
                        continue
                    name = kls[0].get('name', '') if kls else ''
                    if not name:
                        continue
                    initials = ''.join(p[0] for p in lazy_pinyin(name, style=Style.FIRST_LETTER)).lower()
                    if q in initials or q in lazy_pinyin(name, style=Style.NORMAL)[0].lower().replace(' ', ''):
                        seen.add(code)
                        info = imap.get(code, {})
                        if isinstance(info, dict):
                            industry = info.get('industry', info.get('name', ''))
                        else:
                            industry = str(info) if info else ''
                        results.append({
                            'code': code,
                            'name': name,
                            'direction': sec,
                            'industry': industry,
                            'has_data': True,
                        })
        except ImportError:
            pass

    return results
