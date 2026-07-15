#!/usr/bin/env python3
"""
数据源健康监测模块 — 每次数据调用自动更新

Usage:
    from backend.services.source_health import report_success, report_failure, get_all_health
    report_success('mootdx')  # 调用成功后
    report_failure('ths_sector', 'ConnectionError: ...')  # 调用失败后
"""

import json, os, sys, tempfile, threading
from contextlib import contextmanager
from datetime import datetime

import fcntl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from backend.core.config import SOURCE_HEALTH_PATH

_DEFAULT_HEALTH = {
    'status': 'UNKNOWN',
    'last_ok': '',
    'last_fail': '',
    'fail_count': 0,
    'total_calls': 0,
    'success_rate_pct': 100.0,
    'last_error': '',
}

_THREAD_LOCK = threading.RLock()


def _empty_health():
    return {'sources': {}, 'transitions': []}


@contextmanager
def _health_lock():
    """Serialize health-state updates across threads and processes."""
    lock_path = SOURCE_HEALTH_PATH + '.lock'
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with _THREAD_LOCK:
        with open(lock_path, 'a+') as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def _load_health():
    if os.path.isfile(SOURCE_HEALTH_PATH):
        try:
            with open(SOURCE_HEALTH_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return _empty_health()
            data.setdefault('sources', {})
            data.setdefault('transitions', [])
            return data
        except (OSError, json.JSONDecodeError, TypeError):
            # Health telemetry must never break the data source it observes.
            return _empty_health()
    return _empty_health()

def _save_health(data):
    os.makedirs(os.path.dirname(SOURCE_HEALTH_PATH), exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=os.path.dirname(SOURCE_HEALTH_PATH),
        prefix=os.path.basename(SOURCE_HEALTH_PATH) + '.',
        suffix='.tmp',
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, SOURCE_HEALTH_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)

def get_all_health():
    with _health_lock():
        return _load_health()

def get_source_health(source_name):
    with _health_lock():
        data = _load_health()
        if source_name not in data['sources']:
            data['sources'][source_name] = dict(_DEFAULT_HEALTH)
        return data['sources'][source_name]

def report_success(source_name):
    with _health_lock():
        data = _load_health()
        now = datetime.now().strftime('%Y%m%d %H:%M:%S')
        src = data['sources'].get(source_name, dict(_DEFAULT_HEALTH))
        src['last_ok'] = now
        src['total_calls'] = src.get('total_calls', 0) + 1
        src['fail_count'] = 0
        src['last_error'] = ''
        if src.get('status') == 'DOWN':
            prev_fail = src.get('fail_count_before_down', 3)
            if prev_fail >= 3:
                consecutive_ok = src.get('_consecutive_ok', 0) + 1
                src['_consecutive_ok'] = consecutive_ok
                if consecutive_ok >= 3:
                    src['status'] = 'UP'
                    src['_consecutive_ok'] = 0
                    data['transitions'].append({
                        'time': now,
                        'source': source_name,
                        'from': 'DOWN',
                        'to': 'UP',
                        'reason': '连续3次成功调用'
                    })
                    print(f'[source_health] {source_name} 已自动恢复为 UP')
            else:
                src['status'] = 'UP'
                data['transitions'].append({
                    'time': now, 'source': source_name, 'from': 'DOWN', 'to': 'UP', 'reason': '自动恢复'
                })
        else:
            src['status'] = 'UP'
        total = src.get('total_calls', 0)
        if total > 0:
            src['success_rate_pct'] = round((total - src.get('fail_count', 0)) / total * 100, 1)
        data['sources'][source_name] = src
        _save_health(data)

def report_failure(source_name, error_msg):
    with _health_lock():
        data = _load_health()
        now = datetime.now().strftime('%Y%m%d %H:%M:%S')
        src = data['sources'].get(source_name, dict(_DEFAULT_HEALTH))
        src['last_fail'] = now
        src['total_calls'] = src.get('total_calls', 0) + 1
        src['fail_count'] = src.get('fail_count', 0) + 1
        src['last_error'] = str(error_msg)[:200]
        src['_consecutive_ok'] = 0
        if src['fail_count'] >= 3 and src.get('status') != 'DOWN':
            src['status'] = 'DOWN'
            src['fail_count_before_down'] = src['fail_count']
            prev_status = src.get('status_before', 'UNKNOWN')
            data['transitions'].append({
                'time': now,
                'source': source_name,
                'from': prev_status if prev_status != 'DOWN' else 'UP',
                'to': 'DOWN',
                'reason': f'连续{src["fail_count"]}次失败: {str(error_msg)[:100]}'
            })
            print(f'[source_health] {source_name} 已标记为 DOWN (连续{src["fail_count"]}次失败)')
        else:
            src['status'] = 'DEGRADED' if src['fail_count'] > 0 else 'UP'
        total = src.get('total_calls', 0)
        if total > 0:
            src['success_rate_pct'] = round((total - src.get('fail_count', 0)) / total * 100, 1)
        data['sources'][source_name] = src
        _save_health(data)

def is_source_available(source_name):
    src = get_source_health(source_name)
    if src.get('status') == 'DOWN' and src.get('fail_count', 0) >= 3:
        return False
    return True

def reset_source(source_name):
    with _health_lock():
        data = _load_health()
        if source_name in data['sources']:
            data['sources'][source_name] = dict(_DEFAULT_HEALTH)
            data['sources'][source_name]['status'] = 'UP'
            _save_health(data)
            return True
        return False
