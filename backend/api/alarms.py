"""报警管理 API 路由"""
import json
from urllib.parse import urlparse, parse_qs
from datetime import date, timedelta

from backend.services.alarm_service import (
    get_active_alarms,
    get_alarms,
    remove_alarm,
    mark_alarm_triggered,
)


def _handle_list(h, path):
    """GET /api/alarms/list — 返回当前生效的报警"""
    alarms = get_active_alarms()
    h.send_json({'alarms': alarms, 'count': len(alarms)})


def _handle_list_all(h, path):
    """GET /api/alarms/list-all — 返回全部报警（含已触发/过期）"""
    alarms = get_alarms()
    h.send_json({'alarms': alarms, 'count': len(alarms)})


def _handle_remove(h, path, body):
    """POST /api/alarms/remove — 删除报警

    Body: {"id": "alarm_002371_xxx"}
    """
    try:
        data = json.loads(body)
        alarm_id = data.get('id', '')
        if not alarm_id:
            h.send_json({'success': False, 'error': '缺少 id'})
            return
        result = remove_alarm(alarm_id)
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def register_routes(routes):
    routes.exact('/api/alarms/list', func=_handle_list)
    routes.exact('/api/alarms/list-all', func=_handle_list_all)
    routes.exact('/api/alarms/remove', func=_handle_remove)
    return routes
