"""复盘相关路由（生成、保存、日期列表）"""
from datetime import datetime

from . import parse_query
from backend.core.logger import get_logger
log = get_logger(__name__)

from backend.services.review_service import (
    run_daily_review, generate_review, save_review, compute_review_serialized,
    load_current_review,
    get_archive, normalize_review_response,
    get_review_refresh_status, request_review_refresh,
)
from backend.core.exceptions import APIError


def _empty_review():
    return {
        'date': '',
        'market': {
            'score': 0, 'position': '未知', 'bias20': 0, 'vol_ratio': 0,
        },
        'mainline': {},
        'timing_signals': {},
        'trading_plan': {},
        'holdings_review': [],
        'buy_signals_review': [],
    }


def _handle_review_today(h, path):
    """兼容旧接口：等价于 /api/review/live。"""
    import json
    try:
        data = compute_review_serialized()
        h.send_json(data)
    except Exception as e:
        raise APIError(f"复盘模块异常: {e}") from e


def _handle_review_generate(h, path):
    params = parse_query(path)
    date_arg = params.get('date', [None])[0]
    h.send_json(generate_review(date_arg))


def _handle_review_save(h, path, body):
    """POST: 保存复盘数据"""
    import json
    try:
        data = json.loads(body)
        result = save_review(data)
        h.send_json(result)
    except Exception as e:
        raise APIError(f"复盘模块异常: {e}") from e


def _handle_cron_daily_review(h, path):
    """定时任务：执行每日复盘"""
    h.send_json(run_daily_review())


def _handle_review_dates(h, path):
    """返回历史复盘日期列表"""
    import os
    from backend.core import config
    archive_dir = config.get_user_archive_dir()
    dates = []
    if os.path.isdir(archive_dir):
        dates = sorted([
            f[:-5] for f in os.listdir(archive_dir)
            if f.endswith('.json')
        ])
    h.send_json({'dates': dates})


def _handle_review_archive(h, path):
    """按严格日期读取只读复盘归档，避免动态路径和目录穿越。"""
    params = parse_query(path)
    date_arg = params.get('date', [''])[0]
    try:
        valid_date = datetime.strptime(date_arg, '%Y-%m-%d').strftime('%Y-%m-%d')
    except (TypeError, ValueError):
        h.send_json({'success': False, 'error': 'date 必须为 YYYY-MM-DD'}, 400)
        return
    if valid_date != date_arg:
        h.send_json({'success': False, 'error': 'date 必须为 YYYY-MM-DD'}, 400)
        return
    archive = get_archive(valid_date)
    if archive is None:
        h.send_json({'success': False, 'error': '复盘归档不存在', 'date': valid_date}, 404)
        return
    h.send_json(normalize_review_response(archive, source='archive'))


def _handle_review_get(h, path):
    """兼容旧接口：等价于 /api/review/current。"""
    try:
        data = load_current_review()
        refresh = request_review_refresh(force=False)
        data['market'] = {**_empty_review()['market'], **data.get('market', {})}
        data['refresh_status'] = refresh
        h.send_json(data)
    except (OSError, ValueError, TypeError):
        h.send_json(load_current_review())


def _handle_review_refresh(h, path):
    """立即返回，由后台单飞任务重新生成缓存。"""
    h.send_json(request_review_refresh(force=True))


def _handle_review_status(h, path):
    h.send_json(get_review_refresh_status())


def register_routes(routes):
    routes.exact('/api/cron/daily-review', func=_handle_cron_daily_review)
    routes.exact('/api/review/today', func=_handle_review_today)
    routes.exact('/api/review/live', func=_handle_review_today)
    routes.exact('/api/review/generate', func=_handle_review_generate)
    routes.exact('/api/review/get', func=_handle_review_get)
    routes.exact('/api/review/current', func=_handle_review_get)
    routes.exact('/api/review/refresh', func=_handle_review_refresh)
    routes.exact('/api/review/status', func=_handle_review_status)
    routes.exact('/api/review/dates', func=_handle_review_dates)
    routes.exact('/api/review/archive', func=_handle_review_archive)
    # POST 路由在 server.py 的 do_POST 中直接处理，保持兼容
    return routes
