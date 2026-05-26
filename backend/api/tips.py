"""交易技巧/知识库路由"""
import json
from . import parse_query
from backend.services.knowledge_service import (
    get_tips_list, get_tip_content,
    get_journal_entries, save_journal_entry,
)


def _handle_tips_list(h, path):
    h.send_json(get_tips_list())


def _handle_tips_content(h, path):
    file_name = parse_query(path).get('file', [''])[0]
    if not file_name:
        h.send_json({'error': 'missing file param'})
        return
    h.send_json(get_tip_content(file_name))


def _handle_journal_entries(h, path):
    h.send_json(get_journal_entries())


def _handle_save_journal(h, path, body):
    """POST: 保存交易日志"""
    try:
        entry = json.loads(body)
        result = save_journal_entry(entry)
        h.send_json(result)
    except Exception as e:
        h.send_json({'status': 'error', 'msg': str(e)})


def register_routes(routes):
    routes.exact('/api/tips', func=_handle_tips_list)
    routes.exact('/api/tips/content', func=_handle_tips_content)
    routes.exact('/api/tips/journal-entries', func=_handle_journal_entries)
    # POST /api/tips/save-journal 在 server.py do_POST 处理
    return routes
