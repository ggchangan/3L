"""系统管理路由（健康检查、数据更新等）"""
import json
from backend.core.logger import get_logger
from backend.core.exceptions import APIError
from . import parse_query

log = get_logger(__name__)


def _handle_health(h, path):
    """动态健康检查：验证数据源/缓存/磁盘"""
    import os, shutil, time
    from backend.core import config
    DATA_DIR = os.environ.get('DATA_DIR', config.DATA_DIR)
    checks = {}

    # 1. 复盘数据文件可读
    review_file = os.path.join(DATA_DIR, 'private', 'review_data.json')
    try:
        mtime = os.path.getmtime(review_file)
        age = time.time() - mtime
        age_ok = age < 86400 * 7
        checks['review_data'] = {
            'ok': True,
            'age_hours': round(age / 3600, 1),
            'fresh': age_ok,
        }
    except Exception as e:
        log.warning("health check field failed")
        checks['review_data'] = {'ok': False, 'error': str(e)}

    # 2. 缓存目录可读写
    cache_dir = os.path.join(DATA_DIR, 'cache')
    try:
        files = os.listdir(cache_dir)
        checks['cache'] = {'ok': True, 'file_count': len(files), 'path': cache_dir}
    except Exception as e:
        log.warning("health check field failed")
        checks['cache'] = {'ok': False, 'error': str(e)}

    # 3. 磁盘空间
    try:
        stat = shutil.disk_usage(DATA_DIR)
        gb_free = stat.free / (1024**3)
        checks['disk'] = {
            'ok': gb_free > 1.0,
            'free_gb': round(gb_free, 1),
            'total_gb': round(stat.total / (1024**3), 1),
            'used_pct': round(100 * stat.used / stat.total, 1),
        }
    except Exception as e:
        log.warning("health check field failed")
        checks['disk'] = {'ok': False, 'error': str(e)}

    # 4. 服务状态
    import sys
    checks['service'] = {
        'ok': True,
        'name': '3l-server',
        'python': '.venv (self-contained)' if 'venv' in sys.executable else 'system',
    }

    overall = all(c.get('ok') for c in checks.values())
    h.send_json({'status': 'ok' if overall else 'degraded', 'checks': checks})


def _handle_update(h, path, body):
    import json
    try:
        from . import get_server
        _srv = get_server()
        data = json.loads(body)
        for k in ('market', 'mainlines', 'stocks'):
            if k in data:
                _srv.REVIEW_DATA[k] = data[k]
        _srv.save_review_data()
        h.send_json({'status': 'ok'})
    except Exception as e:
        raise APIError(f"系统模块异常: {e}") from e


def register_routes(routes):
    routes.exact('/api/health', func=_handle_health)
    return routes
