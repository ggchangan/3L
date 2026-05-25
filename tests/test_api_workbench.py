"""工作台 API handler 测试

测试 backend/api/workbench.py 的 _handle_get / _handle_save / _handle_list
mock service 层，不碰真实文件
"""
import json
import os
import sys
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_LOG = {
    'date': '2026-05-25',
    'review_summary': {'market': '上涨', 'mainline': '算力', 'signals_count': 3, 'marked_count': 1},
    'todos': [{'text': '测试', 'done': False}],
    'plan': {'buy': [], 'sell': [], 'watch': []},
    'operations': '测试操作',
    'execution_review': '好',
    'reflection': {'discipline': '', 'learned': '', 'rating': ''},
}


@pytest.fixture
def mock_handler():
    """创建一个模拟的 handler 对象，捕获 send_json 调用"""
    h = MagicMock()
    h.send_json = MagicMock()
    return h


@pytest.fixture
def mock_all(monkeypatch):
    """mock 整个 backend.api.workbench 模块的 service 调用"""
    import backend.api.workbench as mod
    monkeypatch.setattr(mod, 'get_log', MagicMock())
    monkeypatch.setattr(mod, 'save_log', MagicMock())
    monkeypatch.setattr(mod, 'list_logs', MagicMock())
    return mod


# ═══════════════════════════════════════════════════════════════════
# _handle_get
# ═══════════════════════════════════════════════════════════════════

class TestHandleGet:

    def test_get_with_date(self, mock_all, mock_handler):
        """GET /api/workbench/get?date=2026-05-25 调用 get_log 并返回结果"""
        mock_all.get_log.return_value = SAMPLE_LOG
        mock_all._handle_get(mock_handler, '/api/workbench/get?date=2026-05-25')
        mock_all.get_log.assert_called_once_with('2026-05-25')
        mock_handler.send_json.assert_called_once_with(SAMPLE_LOG)

    def test_get_without_date(self, mock_all, mock_handler):
        """GET /api/workbench/get 不带日期也正常处理"""
        mock_all.get_log.return_value = {'date': '2026-05-25'}
        mock_all._handle_get(mock_handler, '/api/workbench/get')
        mock_all.get_log.assert_called_once_with(None)

    def test_get_returns_empty_on_missing(self, mock_all, mock_handler):
        """不存在的日期返回空模板"""
        mock_all.get_log.return_value = {
            'date': '2099-01-01', 'todos': [], 'plan': {'buy': [], 'sell': [], 'watch': []},
            'operations': '', 'execution_review': '', 'reflection': {},
            'review_summary': {},
        }
        mock_all._handle_get(mock_handler, '/api/workbench/get?date=2099-01-01')
        data = mock_handler.send_json.call_args[0][0]
        assert data['date'] == '2099-01-01'
        assert data['todos'] == []


# ═══════════════════════════════════════════════════════════════════
# _handle_save
# ═══════════════════════════════════════════════════════════════════

class TestHandleSave:

    def test_save_success(self, mock_all, mock_handler):
        """POST 正确数据返回成功"""
        mock_all.save_log.return_value = {'success': True, 'date': '2026-05-25'}
        mock_all._handle_save(mock_handler, '/api/workbench/save', json.dumps(SAMPLE_LOG))
        mock_all.save_log.assert_called_once()
        args = mock_all.save_log.call_args[0]
        assert args[0] == '2026-05-25'  # date
        assert args[1]['operations'] == '测试操作'
        mock_handler.send_json.assert_called_once_with({'success': True, 'date': '2026-05-25'})

    def test_save_missing_date(self, mock_all, mock_handler):
        """POST 缺少 date 返回错误"""
        data = dict(SAMPLE_LOG)
        del data['date']
        mock_all._handle_save(mock_handler, '/api/workbench/save', json.dumps(data))
        resp = mock_handler.send_json.call_args[0][0]
        assert resp['success'] is False
        assert '缺少日期' in resp.get('error', '')

    def test_save_invalid_json(self, mock_all, mock_handler):
        """POST 非法 JSON 返回错误"""
        mock_all._handle_save(mock_handler, '/api/workbench/save', 'not json{{{')
        resp = mock_handler.send_json.call_args[0][0]
        assert resp['success'] is False
        assert 'error' in resp

    def test_save_with_empty_date(self, mock_all, mock_handler):
        """POST date 为空字符串返回错误"""
        data = dict(SAMPLE_LOG)
        data['date'] = ''
        mock_all._handle_save(mock_handler, '/api/workbench/save', json.dumps(data))
        resp = mock_handler.send_json.call_args[0][0]
        assert resp['success'] is False


# ═══════════════════════════════════════════════════════════════════
# _handle_list
# ═══════════════════════════════════════════════════════════════════

class TestHandleList:

    def test_list_returns_dates(self, mock_all, mock_handler):
        """GET /api/workbench/list 返回日期列表"""
        mock_all.list_logs.return_value = ['2026-05-25', '2026-05-24']
        mock_all._handle_list(mock_handler, '/api/workbench/list')
        mock_all.list_logs.assert_called_once()
        mock_handler.send_json.assert_called_once_with({'dates': ['2026-05-25', '2026-05-24']})

    def test_list_empty(self, mock_all, mock_handler):
        """无日志时返回空列表"""
        mock_all.list_logs.return_value = []
        mock_all._handle_list(mock_handler, '/api/workbench/list')
        resp = mock_handler.send_json.call_args[0][0]
        assert resp == {'dates': []}
