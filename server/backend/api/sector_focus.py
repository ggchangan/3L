"""关注板块/概念 API 路由 — 同花顺板块/概念选择关注 + 复盘页关注数据。

- GET  /api/sectors/list?type=industry|concept   → 板块/概念全列表（含关注状态、主线内标记）
- GET  /api/watched-sectors                       → 当前用户关注列表
- POST /api/watched-sectors/toggle                → {type, ts_code} 关注/取消
"""
import json
from urllib.parse import urlparse, parse_qs

from backend.core.auth import get_current_user_id
from backend.core.exceptions import APIError
from backend.core.logger import get_logger
from backend.services.sector_focus_service import (
    get_watched_sectors, get_all_sectors, toggle_watched_sector,
)

log = get_logger(__name__)


def _handle_sectors_list(h, path):
    """GET /api/sectors/list?type=industry|concept"""
    qs = parse_qs(urlparse(path).query)
    sector_type = qs.get('type', ['industry'])[0].strip().lower()
    try:
        h.send_json(get_all_sectors(sector_type, get_current_user_id()))
    except Exception as e:
        raise APIError(f"板块列表获取失败: {e}") from e


def _handle_watched_sectors_get(h, path):
    """GET /api/watched-sectors"""
    try:
        h.send_json(get_watched_sectors(get_current_user_id()))
    except Exception as e:
        raise APIError(f"关注板块列表获取失败: {e}") from e


def _handle_watched_sectors_toggle(h, path, body):
    """POST /api/watched-sectors/toggle  body: {type, ts_code}"""
    try:
        data = json.loads(body)
        sector_type = str(data.get('type', '')).strip().lower()
        ts_code = str(data.get('ts_code', '')).strip()
        if not sector_type or not ts_code:
            h.send_json({'success': False, 'error': 'type 和 ts_code 不能为空'})
            return
        h.send_json(toggle_watched_sector(get_current_user_id(), sector_type, ts_code))
    except Exception as e:
        raise APIError(f"关注板块切换失败: {e}") from e


def register_routes(routes):
    routes.exact('/api/sectors/list', func=_handle_sectors_list)
    routes.exact('/api/watched-sectors', func=_handle_watched_sectors_get)
    routes.exact('/api/watched-sectors/toggle', func=_handle_watched_sectors_toggle)
    return routes
