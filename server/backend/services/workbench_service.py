"""
工作台（交易日志）服务

管理结构化交易日志的保存和读取。
每个用户、每个日期独立一个 JSON 文件，存储在 config/users/<uid>/workbench/ 下。
"""
import json
import os
import re
from datetime import date
from backend.core.config import get_user_config_path

_DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')


def _file_path(dt: str) -> str:
    """按用户隔离的日志路径；dt 必须是 YYYY-MM-DD（防目录穿越）。"""
    if not _DATE_RE.match(dt or ''):
        raise ValueError(f'日期格式不合法: {dt!r}，应为 YYYY-MM-DD')
    return get_user_config_path(os.path.join('workbench', f'{dt}.json'))


def get_log(dt: str = None) -> dict:
    """读取指定日期的日志，如果不存在返回空模板"""
    dt = dt or date.today().isoformat()
    fp = _file_path(dt)
    if os.path.isfile(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    return _empty_log(dt)


def save_log(dt: str, data: dict) -> dict:
    """保存日志"""
    fp = _file_path(dt)
    os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {'success': True, 'date': dt}


def list_logs() -> list:
    """列出当前用户所有日志日期（降序）"""
    log_dir = os.path.dirname(_file_path('2000-01-01'))
    if not os.path.isdir(log_dir):
        return []
    files = sorted(
        (f.replace('.json', '') for f in os.listdir(log_dir)
         if f.endswith('.json') and _DATE_RE.match(f.replace('.json', ''))),
        reverse=True
    )
    return files


def _empty_log(dt: str) -> dict:
    """返回空日志模板"""
    return {
        'date': dt,
        'review_summary': {
            'market': '',
            'mainline': '',
            'signals_count': 0,
            'marked_count': 0,
        },
        'todos': [],
        'plan': {
            'buy': [],
            'sell': [],
            'watch': [],
        },
        'operations': '',
        'execution_review': '',
        'reflection': {
            'discipline': '',
            'learned': '',
            'rating': '',
        },
        'alerts': [],
    }
