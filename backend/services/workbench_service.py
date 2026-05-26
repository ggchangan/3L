"""
工作台（交易日志）服务

管理结构化交易日志的保存和读取。
每个日期独立一个 JSON 文件，存储在 data/private/workbench/ 下。
"""
import json
import os
from datetime import date
from backend.config import DATA_DIR

WORKBENCH_DIR = os.path.join(DATA_DIR, 'private', 'workbench')
os.makedirs(WORKBENCH_DIR, exist_ok=True)


def _file_path(dt: str) -> str:
    return os.path.join(WORKBENCH_DIR, f'{dt}.json')


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
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {'success': True, 'date': dt}


def list_logs() -> list:
    """列出所有日志日期（降序）"""
    if not os.path.isdir(WORKBENCH_DIR):
        return []
    files = sorted(
        (f.replace('.json', '') for f in os.listdir(WORKBENCH_DIR)
         if f.endswith('.json') and len(f.replace('.json', '')) == 10),
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
