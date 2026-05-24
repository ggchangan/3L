"""复盘相关路由（生成、保存、日期列表）"""
from . import parse_query
from services.review_service import run_daily_review, generate_review, save_review


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
        h.send_json({'status': 'error', 'msg': str(e)})


def _handle_cron_daily_review(h, path):
    """定时任务：执行每日复盘"""
    h.send_json(run_daily_review())


def _handle_review_dates(h, path):
    """返回历史复盘日期列表"""
    import os
    import config
    archive_dir = config.REVIEW_ARCHIVE_DIR
    dates = []
    if os.path.isdir(archive_dir):
        dates = sorted([
            f[:-5] for f in os.listdir(archive_dir)
            if f.endswith('.json')
        ])
    h.send_json({'dates': dates})


def register_routes(routes):
    routes.exact('/api/cron/daily-review', func=_handle_cron_daily_review)
    routes.exact('/api/review/generate', func=_handle_review_generate)
    routes.exact('/api/review/dates', func=_handle_review_dates)
    # POST 路由在 server.py 的 do_POST 中直接处理，保持兼容
    return routes
