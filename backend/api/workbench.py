"""
工作台 API 路由
"""
import json
import os
from urllib.parse import urlparse, parse_qs

from backend.services.workbench_service import get_log, save_log, list_logs


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


def register_routes(routes):
    routes.exact('/api/workbench/get', func=_handle_get)
    routes.exact('/api/workbench/list', func=_handle_list)
    routes.exact('/api/workbench/save', func=_handle_save)  # POST handled separately
    return routes
