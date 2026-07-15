"""热点个股追踪路由 — 同花顺热股Top100 + 3L分析

性能优化：批量预取K线 + 并行 get_stock_card，避免串行超时。
"""
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from backend.core.logger import get_logger
from . import parse_query

log = get_logger(__name__)

# 同花顺热点API配置
_THS_HOT_API = 'http://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock'
_THS_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.10jqka.com.cn/',
    'Accept': 'application/json, text/plain, */*',
}

_MARKET_MAP = {17: '.SS', 33: '.SZ'}

_MAX_WORKERS = 10  # 并行卡分析上限


def _ensure_suffix(code):
    if '.' in code:
        return code
    if code.startswith('6'):
        return f'{code}.SH'
    return f'{code}.SZ'


def _code_with_market(code, market):
    suffix = _MARKET_MAP.get(market, '')
    return code + suffix


def _fetch_hot_stocks(stock_type='a', list_type='normal', limit=100):
    """从同花顺获取热门个股列表"""
    params = {'stock_type': stock_type, 'type': 'day', 'list_type': list_type}
    try:
        r = requests.get(_THS_HOT_API, headers=_THS_HEADERS, params=params, timeout=15)
        if r.status_code != 200:
            return None, f'同花顺API返回 {r.status_code}'
        data = r.json()
        if data.get('status_code') != 0:
            return None, data.get('status_msg', '未知错误')
        stock_list = data.get('data', {}).get('stock_list', [])
        return stock_list[:limit], None
    except Exception as e:
        log.error("hot stocks fetch error: %s", e, exc_info=True)
        return None, str(e)


def _batch_prefetch_klines(codes_list):
    """批量预取K线（单连接，快）"""
    if not codes_list:
        return {}
    from threel_core.db import query_stock_klines
    lookup = [_ensure_suffix(c) for c in codes_list]
    ts_map = {_ensure_suffix(c): c for c in codes_list}
    raw = query_stock_klines(lookup, limit=90)
    result = {}
    for ts, kls in raw.items():
        code = ts_map.get(ts, ts)
        result[code] = kls
    return result


def _analyze_one_stock(code, name, hot_rank, hot_value_int, change, concept_tags,
                       popularity_tag, klines, today):
    """分析单只热股 — 调用 get_stock_card（可被 ThreadPoolExecutor 并行）"""
    try:
        from backend.services.stock_card_service import get_stock_card
        card = get_stock_card(code.strip(), today, klines=klines)
        if card:
            card['hot_rank'] = hot_rank
            card['hot_value'] = hot_value_int
            card['concept_tags'] = concept_tags
            card['popularity_tag'] = popularity_tag
            if change is not None:
                card['change'] = change
            return card
    except Exception:
        pass

    return {
        'code': code, 'name': name,
        'hot_rank': hot_rank, 'hot_value': hot_value_int,
        'change': change or 0, 'price': None,
        'sector': '', 'structure': '--', 'stage': '--',
        'signal': 'hold', 'trading_system': '3l',
        'buy_point': '', 'stop_loss': None, 'stop_loss_pct': None,
        'mainline_level': '', 'concept_tags': concept_tags,
        'popularity_tag': popularity_tag, 'triggered_signals': [],
        'fusion_type': '', 'conclusion': '数据不足',
    }


def _handle_hot_stocks(h, path):
    """GET /api/hot-stocks — 返回热点个股 + 3L分析"""
    params = parse_query(path)
    limit = int(params.get('limit', ['100'])[0])
    stock_type = params.get('stock_type', ['a'])[0]

    # 1. 获取热股列表
    stock_list, err = _fetch_hot_stocks(stock_type=stock_type, limit=limit)
    if err:
        h.send_json({'error': f'获取热股失败: {err}', 'stocks': [], 'total': 0})
        return

    if not stock_list:
        h.send_json({'stocks': [], 'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'total': 0})
        return

    # 2. 批量预取所有热股的K线
    today = datetime.now().strftime('%Y%m%d')
    all_codes = [item.get('code', '').strip() for item in stock_list if item.get('code')]
    klines_map = _batch_prefetch_klines(all_codes)

    # 3. 并行分析（跳过K线不足的）
    prepared = []
    for item in stock_list:
        code = item.get('code', '').strip()
        if not code:
            continue
        klines = klines_map.get(code, [])
        if not klines or len(klines) < 30:
            name = item.get('name', code)
            prepared.append({
                'code': code, 'name': name,
                'hot_rank': item.get('order', 0),
                'hot_value': _safe_int(item.get('rate', '0')),
                'change': round(item.get('rise_and_fall', 0), 2) if item.get('rise_and_fall') else None,
                'concept_tags': (item.get('tag', {}) or {}).get('concept_tag', []),
                'popularity_tag': (item.get('tag', {}) or {}).get('popularity_tag', ''),
                'klines': None,
            })
            continue
        name = item.get('name', code)
        hot_rank = item.get('order', 0)
        hot_value_int = _safe_int(item.get('rate', '0'))
        change = round(item.get('rise_and_fall', 0), 2) if item.get('rise_and_fall') else None
        tags = item.get('tag', {}) or {}
        concept_tags = tags.get('concept_tag', [])
        popularity_tag = tags.get('popularity_tag', '')
        prepared.append({
            'code': code, 'name': name,
            'hot_rank': hot_rank, 'hot_value': hot_value_int,
            'change': change,
            'concept_tags': concept_tags,
            'popularity_tag': popularity_tag,
            'klines': klines,
        })

    # 4. 并行执行 get_stock_card
    results = []
    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {}
        for p in prepared:
            if p['klines']:
                fut = pool.submit(
                    _analyze_one_stock,
                    p['code'], p['name'],
                    p['hot_rank'], p['hot_value'], p['change'],
                    p['concept_tags'], p['popularity_tag'],
                    p['klines'], today,
                )
                futures[fut] = p['code']
            else:
                results.append({
                    'code': p['code'], 'name': p['name'],
                    'hot_rank': p['hot_rank'], 'hot_value': p['hot_value'],
                    'change': p['change'] or 0, 'price': None,
                    'sector': '', 'structure': '--', 'stage': '--',
                    'signal': 'hold', 'trading_system': '3l',
                    'buy_point': '', 'stop_loss': None, 'stop_loss_pct': None,
                    'mainline_level': '', 'concept_tags': p['concept_tags'],
                    'popularity_tag': p['popularity_tag'],
                    'triggered_signals': [], 'fusion_type': '', 'conclusion': '数据不足',
                })

        for fut in as_completed(futures):
            try:
                card = fut.result()
                if card:
                    results.append(card)
            except Exception:
                code = futures[fut]
                results.append({
                    'code': code, 'name': code,
                    'hot_rank': 0, 'hot_value': 0,
                    'change': 0, 'price': None,
                    'sector': '', 'structure': '--', 'stage': '--',
                    'signal': 'hold', 'trading_system': '3l',
                    'buy_point': '', 'stop_loss': None, 'stop_loss_pct': None,
                    'mainline_level': '', 'concept_tags': [],
                    'popularity_tag': '', 'triggered_signals': [],
                    'fusion_type': '', 'conclusion': '分析失败',
                })

    results.sort(key=lambda x: x.get('hot_rank', 0))
    scan_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    h.send_json({'stocks': results, 'scan_time': scan_time, 'total': len(results)})


def _safe_int(v, default=0):
    try:
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


def register_routes(routes):
    routes.exact('/api/hot-stocks', func=_handle_hot_stocks)
    return routes
