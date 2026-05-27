"""
逻辑追踪系统 API 路由

GET /api/logic-tracking/tags               → 列表
GET /api/logic-tracking/tags?id=xxx        → 单个
POST /api/logic-tracking/tags/add          → 新增
PUT /api/logic-tracking/tags/update        → 更新
POST /api/logic-tracking/tags/delete       → 删除
GET /api/logic-tracking/entries            → 条目列表
POST /api/logic-tracking/entries/add       → 新增条目
POST /api/logic-tracking/entries/delete    → 删除条目
GET /api/logic-tracking/forecasts          → 预判列表
POST /api/logic-tracking/forecasts/add     → 新增预判
POST /api/logic-tracking/forecasts/delete  → 删除预判
"""
import json
from urllib.parse import urlparse, parse_qs

from backend.core.logic_tracking_store import LogicTrackingStore


_store = None


def _get_store():
    global _store
    if _store is None:
        _store = LogicTrackingStore()
    return _store


# ═══════════════════════════════════════════════════
# Tag handlers
# ═══════════════════════════════════════════════════

def _handle_list_tags(h, path):
    """GET /api/logic-tracking/tags?tier=focused"""
    qs = parse_qs(urlparse(path).query)
    tier = qs.get('tier', [None])[0]
    store = _get_store()
    h.send_json({'tags': store.get_tags(tier=tier)})


def _handle_get_tag(h, path):
    """GET /api/logic-tracking/tags/get?id=xxx"""
    qs = parse_qs(urlparse(path).query)
    tag_id = qs.get('id', [None])[0]
    if not tag_id:
        h.send_json({'error': '缺少id参数'})
        return
    store = _get_store()
    tag = store.get_tag(tag_id)
    if tag is None:
        h.send_json({'error': '标签不存在'})
        return
    h.send_json(tag)


def _handle_add_tag(h, path, body):
    """POST /api/logic-tracking/tags/add"""
    try:
        data = json.loads(body)
        store = _get_store()
        store.add_tag(data)
        h.send_json({'success': True})
    except ValueError as e:
        h.send_json({'success': False, 'error': str(e)})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_update_tag(h, path, body):
    """POST /api/logic-tracking/tags/update"""
    try:
        data = json.loads(body)
        tag_id = data.get('id', '')
        if not tag_id:
            h.send_json({'success': False, 'error': '缺少id'})
            return
        store = _get_store()
        store.update_tag(tag_id, data)
        h.send_json({'success': True})
    except ValueError as e:
        h.send_json({'success': False, 'error': str(e)})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_delete_tag(h, path, body):
    """POST /api/logic-tracking/tags/delete"""
    try:
        data = json.loads(body)
        tag_id = data.get('id', '')
        if not tag_id:
            h.send_json({'success': False, 'error': '缺少id'})
            return
        store = _get_store()
        store.delete_tag(tag_id)
        h.send_json({'success': True})
    except ValueError as e:
        h.send_json({'success': False, 'error': str(e)})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


# ═══════════════════════════════════════════════════
# Entry handlers
# ═══════════════════════════════════════════════════

def _handle_list_entries(h, path):
    """GET /api/logic-tracking/entries?tag_id=xxx"""
    qs = parse_qs(urlparse(path).query)
    tag_id = qs.get('tag_id', [None])[0]
    store = _get_store()
    h.send_json({'entries': store.get_entries(tag_id=tag_id)})


def _handle_add_entry(h, path, body):
    """POST /api/logic-tracking/entries/add"""
    try:
        data = json.loads(body)
        store = _get_store()
        store.add_entry(data)
        h.send_json({'success': True})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_delete_entry(h, path, body):
    """POST /api/logic-tracking/entries/delete"""
    try:
        data = json.loads(body)
        eid = data.get('id', '')
        if not eid:
            h.send_json({'success': False, 'error': '缺少id'})
            return
        store = _get_store()
        store.delete_entry(eid)
        h.send_json({'success': True})
    except ValueError as e:
        h.send_json({'success': False, 'error': str(e)})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


# ═══════════════════════════════════════════════════
# Forecast handlers
# ═══════════════════════════════════════════════════

def _handle_list_forecasts(h, path):
    """GET /api/logic-tracking/forecasts?upcoming=30"""
    qs = parse_qs(urlparse(path).query)
    upcoming = qs.get('upcoming', [None])[0]
    store = _get_store()
    if upcoming:
        try:
            days = int(upcoming)
            h.send_json({'forecasts': store.get_forecasts(upcoming_days=days)})
            return
        except ValueError:
            pass
    h.send_json({'forecasts': store.get_forecasts()})


def _handle_add_forecast(h, path, body):
    """POST /api/logic-tracking/forecasts/add"""
    try:
        data = json.loads(body)
        store = _get_store()
        store.add_forecast(data)
        h.send_json({'success': True})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_delete_forecast(h, path, body):
    """POST /api/logic-tracking/forecasts/delete"""
    try:
        data = json.loads(body)
        fid = data.get('id', '')
        if not fid:
            h.send_json({'success': False, 'error': '缺少id'})
            return
        store = _get_store()
        store.delete_forecast(fid)
        h.send_json({'success': True})
    except ValueError as e:
        h.send_json({'success': False, 'error': str(e)})
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


# ═══════════════════════════════════════════════════
# Route registration
# ═══════════════════════════════════════════════════

def register_routes(routes):
    routes.exact('/api/logic-tracking/tags', func=_handle_list_tags)
    routes.exact('/api/logic-tracking/tags/get', func=_handle_get_tag)
    routes.exact('/api/logic-tracking/entries', func=_handle_list_entries)
    routes.exact('/api/logic-tracking/forecasts', func=_handle_list_forecasts)
    return routes
