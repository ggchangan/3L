"""自选股相关路由"""
import json
from . import parse_query
from services.watchlist_service import get_watchlist, search_stocks, save_watchlist
from services.trend_service import get_watchlist_analysis


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


def register_routes(routes):
    routes.exact('/api/watchlist', func=_handle_watchlist)
    routes.exact('/api/watchlist/search', func=_handle_watchlist_search)
    routes.exact('/api/watchlist/analysis', func=_handle_watchlist_analysis)
    # POST /api/watchlist/save 在 server.py do_POST 处理
    return routes
