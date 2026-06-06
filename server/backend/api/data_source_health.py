"""
数据源健康状态 API — 查看所有数据源的可用性和状态变迁
"""
import json


def _handle_data_source_health(h, path):
    """GET /api/data-source/health — 返回所有数据源状态"""
    from backend.services.data_source import get_data_source_status
    status = get_data_source_status()
    h.send_json(status)


def register_routes(routes):
    routes.exact('/api/data-source/health', func=_handle_data_source_health)
