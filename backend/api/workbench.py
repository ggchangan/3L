"""工作台 API 路由"""
import json
from urllib.parse import urlparse, parse_qs
from datetime import date, timedelta

from backend.services.workbench_service import get_log, save_log, list_logs


def _handle_suggestions(h, path):
    """GET /api/workbench/suggestions — 从复盘拉取操作建议（实时计算）"""
    from backend.services.review_service import compute_review_real_time
    try:
        review = compute_review_real_time()
        trading_plan = review.get('trading_plan', {})
    except Exception:
        trading_plan = {}
    h.send_json({
        'holdings_action': trading_plan.get('holdings_action', []),
        'buy_priority': trading_plan.get('buy_priority', []),
        'risk_items': trading_plan.get('risk_items', []),
    })


def _handle_get(h, path):
    """GET /api/workbench/get?date=2026-05-25"""
    qs = parse_qs(urlparse(path).query)
    dt = qs.get('date', [None])[0]
    h.send_json(get_log(dt))


def _handle_save(h, path, body):
    """POST /api/workbench/save"""
    try:
        data = json.loads(body)
        dt = data.get('date', '')
        if not dt:
            h.send_json({'success': False, 'error': '缺少日期'})
            return
        result = save_log(dt, data)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_list(h, path):
    """GET /api/workbench/list"""
    h.send_json({'dates': list_logs()})


def _handle_check_alerts(h, path):
    """GET /api/workbench/check-alerts?date=2026-05-27

    检查今日计划中的价格报警（默认昨日 -> 今日计划）
    """
    qs = parse_qs(urlparse(path).query)
    dt = qs.get('date', [None])[0]
    if not dt:
        dt = (date.today() - timedelta(days=1)).isoformat()
    from backend.services.check_alerts import check_all_alerts
    try:
        result = check_all_alerts(dt)
        h.send_json(result)
    except Exception as e:
        h.send_json({'triggered': [], 'count': 0, 'error': str(e)})


def register_routes(routes):
    routes.exact('/api/workbench/get', func=_handle_get)
    routes.exact('/api/workbench/list', func=_handle_list)
    routes.exact('/api/workbench/save', func=_handle_save)  # POST handled separately
    routes.exact('/api/workbench/suggestions', func=_handle_suggestions)
    routes.exact('/api/workbench/check-alerts', func=_handle_check_alerts)
    return routes
