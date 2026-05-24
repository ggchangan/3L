"""持仓/交易记录路由"""
from services.holdings_service import get_holdings, get_trades


def _handle_holdings(h, path):
    h.send_json(get_holdings())


def _handle_trades(h, path):
    h.send_json(get_trades())


def register_routes(routes):
    routes.exact('/api/holdings', func=_handle_holdings)
    routes.exact('/api/trades', func=_handle_trades)
    return routes
