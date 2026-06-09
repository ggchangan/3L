"""强势趋势追踪 — API端点"""
from backend.services.strong_trend_service import get_strong_trend_candidates
from backend.core.logger import get_logger
from backend.core.exceptions import APIError
log = get_logger(__name__)



def register_routes(routes):
    routes.exact('/api/strong-trend-candidates', func=_handle_strong_trend_candidates)
    return routes


def _handle_strong_trend_candidates(h, path):
    """GET /api/strong-trend-candidates — 获取强势趋势候选股"""
    from backend.api import parse_query
    params = parse_query(path)
    try:
        top_industries = int(params.get('top_industries', [8])[0])
        hot_industries = int(params.get('hot_industries', [8])[0])
        top_concepts = int(params.get('top_concepts', [8])[0])
        hot_concepts = int(params.get('hot_concepts', [8])[0])
        limit = int(params.get('limit', [30])[0])
        min_score = float(params.get('min_score', [5.0])[0])
    except (ValueError, TypeError):
        h.send_json({'success': False, 'error': '参数格式错误'})
        return

    try:
        result = get_strong_trend_candidates(
            top_industries=top_industries,
            hot_industries=hot_industries,
            top_concepts=top_concepts,
            hot_concepts=hot_concepts,
            limit=limit,
            min_score=min_score,
        )
        h.send_json({'success': True, **result})
    except Exception as e:
        raise APIError(f"强势股异常: {e}") from e
