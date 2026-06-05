"""宏观数据路由"""
from backend.services.macro_service import get_macro_data
from backend.services.macro_analysis_service import analyze_us_stock_abnormal
import json


def _handle_macro(h, path):
    h.send_json(get_macro_data())


def _handle_analyze_abnormal(h, path, body):
    try:
        data = json.loads(body) if body else {}
        code = data.get('code', '')
        name = data.get('name', '')
        change_pct = data.get('change_pct', 0)
    except Exception:
        code = ''
        name = ''
        change_pct = 0
    result = analyze_us_stock_abnormal(code, name, change_pct)
    h.send_json(result)


def register_routes(routes):
    routes.exact('/api/macro', func=_handle_macro)
    routes.exact('/api/macro/analyze-abnormal', func=_handle_analyze_abnormal)
    return routes
