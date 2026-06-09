"""操作计划追踪 API 路由 — v2（SQLite + review数据源）"""

import json
from backend.core.logger import get_logger
log = get_logger(__name__)

from backend.services.plan_tracking_service import get_tracking, compute_tracking, annotate_plan


def _handle_get(h, path):
    """GET /api/plan-tracking — 获取计划追踪结果

    Query params:
        start_date: 起始日期 'YYYY-MM-DD'（默认30天前）
        end_date: 结束日期 'YYYY-MM-DD'（默认今天）
        refresh: 是否强制重新计算
    """
    from urllib.parse import urlparse, parse_qs
    qs = parse_qs(urlparse(path).query)
    force = 'refresh' in qs
    start_date = qs.get('start_date', [None])[0]
    end_date = qs.get('end_date', [None])[0]

    if force:
        compute_tracking(force=True)

    data = get_tracking(start_date=start_date, end_date=end_date)
    h.send_json(data)


def _handle_annotate(h, path, body):
    """POST /api/plan-tracking/annotate — 标记计划执行状态

    Body: {
        "date": "2026-05-28",
        "code": "601177",
        "executed": true,
        "user_note": "盘中触发买点"
    }
    """
    try:
        data = json.loads(body)
        from backend.config import DATA_DIR
        import os
        db_path = os.path.join(DATA_DIR, 'private', 'plan_tracking.db')
        result = annotate_plan(
            db_path=db_path,
            date_str=data.get('date', ''),
            code=data.get('code', ''),
            executed=data.get('executed'),
            user_note=data.get('user_note', ''),
        )
        h.send_json(result)
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def _handle_refresh(h, path):
    """POST /api/plan-tracking/refresh — 强制重新计算"""
    try:
        data = compute_tracking(force=True)
        h.send_json({
            'success': True,
            'total_plans': data['summary']['total_plans'],
            'last_updated': data['last_updated'],
        })
    except Exception as e:
        h.send_json({'success': False, 'error': str(e)})


def register_routes(routes):
    routes.exact('/api/plan-tracking', func=_handle_get)
    routes.exact('/api/plan-tracking/annotate', func=_handle_annotate)
    routes.exact('/api/plan-tracking/refresh', func=_handle_refresh)
    return routes
