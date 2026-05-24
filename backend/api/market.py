"""大盘市场数据路由"""
from . import parse_query, get_server
from services.market_service import get_momentum_data
from services.logger import get_logger

log = get_logger('api.market')


def _handle_market(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA.get('market', {}))


def _handle_mainlines(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA.get('mainlines', {}))


def _handle_stocks(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA.get('stocks', {}))


def _handle_momentum(h, path):
    """返回动量数据"""
    h.send_json(get_momentum_data())


def _handle_review_full(h, path):
    _srv = get_server()
    h.send_json(_srv.REVIEW_DATA)


def register_routes(routes):
    routes.exact('/api/market', func=_handle_market)
    routes.exact('/api/mainlines', func=_handle_mainlines)
    routes.exact('/api/stocks', func=_handle_stocks)
    routes.exact('/api/momentum', func=_handle_momentum)
    routes.exact('/api/review', func=_handle_review_full)
    return routes
