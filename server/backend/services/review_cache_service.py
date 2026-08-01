"""复盘缓存、存档和后台刷新。

计算编排留在 review_service；本模块只负责并发、持久化与缓存生命周期。
"""
import json
import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime

from backend.core import config
from backend.core.config import DATA_DIR, REVIEW_ARCHIVE_DIR, REVIEW_DATA_PATH
from backend.core.logger import get_logger
from backend.services.review_contract import normalize_review_response

log = get_logger(__name__)
REVIEW_CACHE_MAX_AGE_SECONDS = int(os.environ.get('REVIEW_CACHE_MAX_AGE_SECONDS', '600'))
_review_refresh_lock = threading.RLock()
_review_refresh_state = {
    'status': 'idle', 'started_at': '', 'completed_at': '', 'error': '',
}


@contextmanager
def review_refresh_file_lock():
    """跨进程串行化复盘计算，避免 cron 与 Web 同时写缓存。"""
    import fcntl

    lock_path = os.path.join(DATA_DIR, '.cache', 'review_refresh.lock')
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, 'a+', encoding='utf-8') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def get_completed_review_date():
    from backend.data_access.data_source import get_last_completed_trading_day

    target = get_last_completed_trading_day()
    return datetime.strptime(target, '%Y%m%d').strftime('%Y-%m-%d')


def get_previous_review_date(date_str):
    """返回指定复盘日的上一有效交易日，供严格相邻日轮动比较。"""
    from backend.data_access.data_source import get_previous_trading_day

    reference = datetime.strptime(date_str, '%Y-%m-%d').date()
    target = get_previous_trading_day(reference)
    return datetime.strptime(target, '%Y%m%d').strftime('%Y-%m-%d')


def compute_review_serialized(date_str=None):
    from backend.services import review_service

    with review_refresh_file_lock():
        return review_service.compute_review_real_time(date_str or get_completed_review_date())


def get_archive_dates():
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return []
    return sorted([
        name.replace('.json', '') for name in os.listdir(REVIEW_ARCHIVE_DIR)
        if name.endswith('.json')
    ], reverse=True)


def get_archive(date_str):
    path = os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as file:
            return json.load(file)
    return None


def get_latest_archive():
    dates = get_archive_dates()
    return get_archive(dates[0]) if dates else None


def load_current_review():
    if os.path.isfile(REVIEW_DATA_PATH):
        try:
            with open(REVIEW_DATA_PATH, 'r', encoding='utf-8') as file:
                return normalize_review_response(json.load(file), source='cache')
        except (OSError, json.JSONDecodeError, TypeError):
            log.warning('当前复盘缓存不可读，返回空复盘契约', exc_info=True)
    archive = get_latest_archive()
    return normalize_review_response(archive or {}, source='archive' if archive else 'cache')


def save_review_data(data):
    os.makedirs(os.path.dirname(REVIEW_DATA_PATH), exist_ok=True)
    config.atomic_json_dump(data, REVIEW_DATA_PATH, indent=2)


def save_review_snapshot(data):
    """把已完成的实时复盘保存为当日快照，供下一交易日轮动比较。"""
    date_str = str(data.get('date') or '')
    parsed = datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y-%m-%d')
    if parsed != date_str:
        raise ValueError('复盘快照日期必须为 YYYY-MM-DD')
    os.makedirs(REVIEW_ARCHIVE_DIR, exist_ok=True)
    config.atomic_json_dump(data, os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), indent=2)


def get_review_refresh_status():
    with _review_refresh_lock:
        state = dict(_review_refresh_state)
    try:
        mtime = os.path.getmtime(REVIEW_DATA_PATH)
        age_seconds = max(0, int(time.time() - mtime))
        state.update({
            'cache_exists': True,
            'cache_updated_at': datetime.fromtimestamp(mtime).isoformat(timespec='seconds'),
            'cache_age_seconds': age_seconds,
            'cache_stale': age_seconds >= REVIEW_CACHE_MAX_AGE_SECONDS,
        })
    except OSError:
        state.update({
            'cache_exists': False, 'cache_updated_at': '',
            'cache_age_seconds': None, 'cache_stale': True,
        })
    return state


def request_review_refresh(force=False):
    """单飞启动后台复盘计算；并发请求共享同一个任务。"""
    status = get_review_refresh_status()
    with _review_refresh_lock:
        if _review_refresh_state['status'] == 'running':
            return {'started': False, **get_review_refresh_status()}
        if not force and status['cache_exists'] and not status['cache_stale']:
            return {'started': False, **status}
        _review_refresh_state.update({
            'status': 'running',
            'started_at': datetime.now().isoformat(timespec='seconds'),
            'completed_at': '', 'error': '',
        })

    def _worker():
        from backend.services import review_service

        try:
            with review_refresh_file_lock():
                data = review_service.compute_review_real_time(review_service.get_completed_review_date())
                data['cache_generated_at'] = datetime.now().isoformat(timespec='seconds')
                # 通过编排模块调用，保留可替换测试边界和旧扩展点。
                review_service.save_review_data(data)
                review_service.save_review_snapshot(data)
            with _review_refresh_lock:
                _review_refresh_state.update({
                    'status': 'completed',
                    'completed_at': datetime.now().isoformat(timespec='seconds'),
                    'error': '',
                })
        except Exception as exc:
            log.exception('后台复盘计算失败')
            with _review_refresh_lock:
                _review_refresh_state.update({
                    'status': 'failed',
                    'completed_at': datetime.now().isoformat(timespec='seconds'),
                    'error': str(exc),
                })

    threading.Thread(target=_worker, daemon=True, name='review-refresh').start()
    return {'started': True, **get_review_refresh_status()}


def save_review(data):
    date = data.get('date', '')
    if not date:
        return {'status': 'error', 'msg': 'missing date'}
    archive_dirs = [
        os.path.join(os.path.dirname(REVIEW_ARCHIVE_DIR), 'data', 'review_archive'),
        REVIEW_ARCHIVE_DIR,
    ]
    for directory in archive_dirs:
        os.makedirs(directory, exist_ok=True)
        config.atomic_json_dump(data, os.path.join(directory, f'{date}.json'), indent=2)
    return {'status': 'ok'}


def get_mainline_archive():
    archive = get_latest_archive()
    return archive.get('mainline', {}) if archive else {}
