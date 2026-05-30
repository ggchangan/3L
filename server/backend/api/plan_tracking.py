"""操作计划追踪 API 路由"""

import json
from backend.services.plan_tracking_service import get_tracking, compute_tracking, annotate_plan, _filter_plans_by_date, _compute_summary, _generate_suggestions


def _handle_get(h, path):
    """GET /api/plan-tracking — 获取计划追踪结果，支持日期筛选
    
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
        data = compute_tracking(force=True)
        # 强制计算后仍然应用日期筛选
        filtered = _filter_plans_by_date(data.get('plans', []), start_date, end_date)
        summary, by_condition, by_type = _compute_summary(filtered)
        suggestions = _generate_suggestions(filtered, summary, by_condition)
        data['plans'] = filtered
        data['summary'] = summary
        data['by_condition'] = by_condition
        data['by_type'] = by_type
        data['suggestions'] = suggestions
    else:
        data = get_tracking(start_date=start_date, end_date=end_date)
    h.send_json(data)


def _handle_annotate(h, path, body):
    """POST /api/plan-tracking/annotate — 标记计划执行状态

    Body: {
        "plan_date": "2026-05-28",
        "type": "buy",
        "stock": "杭齿前进",
        "executed": true,
        "user_note": "盘中触发买点"
    }
    """
    try:
        data = json.loads(body)
        result = annotate_plan(
            plan_date=data.get('plan_date', ''),
            type_=data.get('type', ''),
            stock=data.get('stock', ''),
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
