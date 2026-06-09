"""自选股相关路由"""
import json
from backend.core.exceptions import APIError
from backend.core.logger import get_logger
from . import parse_query

log = get_logger(__name__)
from backend.services.watchlist_service import (
    get_watchlist, search_stocks, save_watchlist,
    get_all_directions, add_direction, remove_direction,
    set_direction_enabled, suggest_directions, migrate_directions,
    get_watchlist_analysis,
)


def _handle_watchlist(h, path):
    h.send_json(get_watchlist())


def _handle_watchlist_save(h, path, body):
    """POST: 保存自选股"""
    try:
        data = json.loads(body)
        result = save_watchlist(data)
        h.send_json(result)
    except Exception as e:
        raise APIError(f"自选股异常: {e}") from e


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
        raise APIError(f"自选股异常: {e}") from e


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
        raise APIError(f"自选股异常: {e}") from e


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
        raise APIError(f"自选股异常: {e}") from e


def _handle_watchlist_boards(h, path):
    """GET: 按行业分组浏览（用于批量添加）"""
    import json, os
    from backend.config import DATA_DIR
    leaders_path = os.path.join(DATA_DIR, 'industry_leaders.json')
    sp = os.path.join(DATA_DIR, 'all_stocks_60d.json')
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
        wl_path = os.path.join(DATA_DIR, 'watchlist.json')
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


def _handle_watchlist_add_stock(h, path, body):
    '''POST: 添加单只股票到自选股（自动分配方向）'''
    try:
        data = json.loads(body)
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        direction = data.get('direction', '').strip() or None
        if not code:
            h.send_json({'success': False, 'error': '缺少股票代码'})
            return

        wl = get_watchlist()
        stocks = wl.get('stocks', []) if isinstance(wl, dict) else wl

        # 查重
        if any(s.get('code') == code for s in stocks if isinstance(s, dict)):
            h.send_json({'success': True, 'msg': '已在自选股中'})
            return

        # 如果没有指定方向，尝试从行业映射推断
        if not direction:
            try:
                import os
                from backend.config import INDUSTRY_MAP_PATH
                if os.path.isfile(INDUSTRY_MAP_PATH):
                    with open(INDUSTRY_MAP_PATH) as _f:
                        _im = json.load(_f)
                    info = _im.get(code, {})
                    suggested = info.get('direction', info.get('ths_industry', ''))
                    if suggested and suggested not in ('未知', '获取失败'):
                        direction = suggested
                # 如果推断出的方向是裸大类（不含'.'），统一归入"未分类.XXX"
                if direction and '.' not in direction and direction != '其他':
                    direction = f'未分类.{direction}'
                if not direction:
                    direction = '其他'
            except:
                direction = '其他'

        new_stock = {'code': code, 'name': name or code, 'direction': direction or '其他'}
        stocks.append(new_stock)
        wl_data = {'stocks': stocks, 'directions': wl.get('directions', [])} if isinstance(wl, dict) else {'stocks': stocks, 'directions': []}
        save_watchlist(wl_data)
        h.send_json({'success': True, 'msg': f'已添加 {name} 到自选股'})
    except Exception as e:
        raise APIError(f"自选股异常: {e}") from e


def register_routes(routes):
    routes.exact('/api/watchlist', func=_handle_watchlist)
    routes.exact('/api/watchlist/boards', func=_handle_watchlist_boards)
    routes.exact('/api/watchlist/search', func=_handle_watchlist_search)
    routes.exact('/api/watchlist/analysis', func=_handle_watchlist_analysis)
    routes.exact('/api/watchlist/directions/get', func=_handle_get_directions)
    # POST routes handled in server.py do_POST
    return routes
