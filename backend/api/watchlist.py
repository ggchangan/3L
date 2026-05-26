"""自选股相关路由"""
import json
from . import parse_query
from backend.services.watchlist_service import (
    get_watchlist, search_stocks, save_watchlist,
    get_all_directions, add_direction, remove_direction,
    set_direction_enabled, suggest_directions, migrate_directions,
)
from backend.services.trend_service import get_watchlist_analysis


def _handle_watchlist(h, path):
    h.send_json(get_watchlist())


def _handle_watchlist_save(h, path, body):
    """POST: 保存自选股"""
    try:
        data = json.loads(body)
        result = save_watchlist(data)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_watchlist_search(h, path):
    q = parse_query(path).get('q', [''])[0].strip().lower()
    if not q or len(q) < 1:
        h.send_json({'results': []})
        return
    h.send_json({'results': search_stocks(q)})


def _handle_watchlist_analysis(h, path):
    h.send_json(get_watchlist_analysis())


def _handle_get_directions(h, path):
    """GET: 获取全部方向（含启用状态和计数）"""
    h.send_json({
        'directions': get_all_directions(),
        'suggestions': suggest_directions(),
    })


def _handle_add_direction(h, path, body):
    """POST: 添加方向"""
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        result = add_direction(name)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_remove_direction(h, path, body):
    """POST: 删除方向"""
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        result = remove_direction(name)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_set_direction_enabled(h, path, body):
    """POST: 启用/禁用方向"""
    try:
        data = json.loads(body)
        name = data.get('name', '').strip()
        enabled = data.get('enabled', True)
        if not name:
            h.send_json({'success': False, 'error': '方向名称不能为空'})
            return
        result = set_direction_enabled(name, enabled)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_watchlist_boards(h, path):
    """GET: 按行业分组浏览（用于批量添加）"""
    import json, os
    leaders_path = '/home/ubuntu/data/3l/industry_leaders.json'
    sp = '/home/ubuntu/data/3l/all_stocks_60d.json'
    if not os.path.isfile(leaders_path):
        h.send_json({'error': 'industry_leaders.json 不存在', 'boards': []})
        return
    with open(leaders_path, 'r') as f:
        ld = json.load(f)
    industries = ld.get('by_industry', {})
    # 从全部数据取最新价格
    prices = {}
    if os.path.isfile(sp):
        with open(sp, 'r') as f:
            sd = json.load(f)
        for sec, stocks in sd.get('stocks', {}).items():
            for code, kls in stocks.items():
                if kls:
                    prices[code] = {'price': kls[-1]['close'], 'change': kls[-1].get('change_pct', 0)}
    # 构建板块列表
    boards = []
    for ind_name, stocks in industries.items():
        enriched = []
        for s in stocks[:20]:  # 每行业最多20只
            code_raw = s['code']
            code = code_raw.replace('SH', '').replace('SZ', '')
            pdata = prices.get(code, {})
            enriched.append({
                'code': code,
                'name': s.get('name', ''),
                'price': pdata.get('price', 0),
                'change': s.get('chg', ''),
                'mcap': s.get('mcap', 0),
                'in_watchlist': False,
            })
        # 标记在自选股的
        wl_path = '/home/ubuntu/data/3l/watchlist.json'
        if os.path.isfile(wl_path):
            with open(wl_path) as wf:
                wld = json.load(wf)
            wl_codes = {s['code'] for s in wld.get('stocks', [])}
            for s in enriched:
                if s['code'] in wl_codes:
                    s['in_watchlist'] = True
        boards.append({'name': ind_name, 'count': len(stocks), 'stocks': enriched})
    # 按股票数量排序
    boards.sort(key=lambda b: b['count'], reverse=True)
    h.send_json({'boards': boards, 'total': sum(b['count'] for b in boards)})


def register_routes(routes):
    routes.exact('/api/watchlist', func=_handle_watchlist)
    routes.exact('/api/watchlist/boards', func=_handle_watchlist_boards)
    routes.exact('/api/watchlist/search', func=_handle_watchlist_search)
    routes.exact('/api/watchlist/analysis', func=_handle_watchlist_analysis)
    routes.exact('/api/watchlist/directions/get', func=_handle_get_directions)
    # POST routes handled in server.py do_POST
    return routes
