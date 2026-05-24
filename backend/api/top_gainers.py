"""涨幅榜路由"""
from . import parse_query
from services.top_gainers_service import get_top_gainers


def _handle_top_gainers(h, path):
    params = parse_query(path)
    date_str = params.get('date', [''])[0].replace('-', '')
    limit = int(params.get('limit', ['50'])[0])
    h.send_json(get_top_gainers(date_str, limit))


def register_routes(routes):
    routes.exact('/api/top-gainers', func=_handle_top_gainers)
    return routes
