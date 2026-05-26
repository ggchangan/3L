"""宏观数据路由"""
from backend.services.macro_service import get_macro_data


def _handle_macro(h, path):
    h.send_json(get_macro_data())


def register_routes(routes):
    routes.exact('/api/macro', func=_handle_macro)
    return routes
