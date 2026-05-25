"""趋势交易路由"""
from . import parse_query
from services.trend_service import (
    get_trend_candidates, get_trend_tracked, toggle_trend_stock,
    search_watchlist_for_trend,
)


def _handle_trend_candidates(h, path):
    h.send_json(get_trend_candidates())


def _handle_trend_tracked(h, path):
    h.send_json(get_trend_tracked())


def _handle_trend_toggle(h, path):
    params = parse_query(path)
    code = params.get('code', [''])[0].strip()
    enable = params.get('enable', ['true'])[0].lower() == 'true'
    if not code:
        h.send_json({'error': '缺少code参数'})
        return
    h.send_json(toggle_trend_stock(code, enable))


def _handle_trend_search_watchlist(h, path):
    q = parse_query(path).get('q', [''])[0].strip().lower()
    if not q or len(q) < 1:
        h.send_json({'results': []})
        return
    h.send_json(search_watchlist_for_trend(q))


def register_routes(routes):
    routes.exact('/api/trend-candidates', func=_handle_trend_candidates)
    routes.exact('/api/trend-tracked', func=_handle_trend_tracked)
    routes.exact('/api/trend-candidates/toggle', func=_handle_trend_toggle)
    routes.exact('/api/trend-candidates/search-watchlist', func=_handle_trend_search_watchlist)
    return routes
