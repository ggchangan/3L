"""盯盘 — 市场健康卡片 API"""
from backend.services.market_health_service import get_market_health


def _handle_market_health(h, path):
    h.send_json(get_market_health())


def register_routes(routes):
    routes.exact('/api/market-health', func=_handle_market_health)
    return routes
