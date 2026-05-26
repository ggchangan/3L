"""监控/盯盘相关路由"""
from backend.services.monitor_service import (
    get_volume_comparison, get_buy_signals, get_stop_loss_triggered,
    get_top_sectors, get_industry_leaders, get_market_leaders,
)


def _handle_volume(h, path):
    h.send_json(get_volume_comparison())


def _handle_buy_signals(h, path):
    h.send_json(get_buy_signals())


def _handle_stop_loss(h, path):
    h.send_json(get_stop_loss_triggered())


def _handle_top_sectors(h, path):
    h.send_json(get_top_sectors())


def _handle_industry_leaders(h, path):
    h.send_json(get_industry_leaders())


def _handle_market_leaders(h, path):
    h.send_json(get_market_leaders())


def register_routes(routes):
    routes.exact('/api/monitor/volume', func=_handle_volume)
    routes.exact('/api/monitor/buy-signals', func=_handle_buy_signals)
    routes.exact('/api/monitor/stop-loss', func=_handle_stop_loss)
    routes.exact('/api/monitor/sectors', func=_handle_top_sectors)
    routes.exact('/api/monitor/leaders', func=_handle_industry_leaders)
    routes.exact('/api/monitor/market-leaders', func=_handle_market_leaders)
    return routes
