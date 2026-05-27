"""
逻辑追踪API测试

测试 backend.api.logic_tracking 的所有 handler
mock 存储层，不碰真实文件
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_TAG = {
    'id': 'tag-test',
    'name': '测试逻辑',
    'description': '测试用',
    'related_industries': ['半导体'],
    'related_stocks': ['002371'],
    'tier': 'focused',
    'tier_override': False,
    'event_count': 0,
    'verify_rate': 0.0,
    'earnings_verify_rate': 0.0,
    'forecast_accuracy': '0/0',
    'created_at': '2026-05-27',
    'updated_at': '2026-05-27',
}


@pytest.fixture
def mock_h():
    h = MagicMock()
    h.send_json = MagicMock()
    return h


@pytest.fixture
def mock_store():
    """mock 整个 LogicTrackingStore"""
    with patch('backend.api.logic_tracking._get_store') as m:
        store = MagicMock()
        m.return_value = store
        yield store


# ═══════════════════════════════════════════════════
# GET /api/logic-tracking/tags
# ═══════════════════════════════════════════════════

class TestListTags:

    def test_list_all(self, mock_h, mock_store):
        mock_store.get_tags.return_value = [SAMPLE_TAG]
        from backend.api.logic_tracking import _handle_list_tags
        _handle_list_tags(mock_h, '/api/logic-tracking/tags')
        mock_h.send_json.assert_called_once()
        data = mock_h.send_json.call_args[0][0]
        assert len(data['tags']) == 1
        assert data['tags'][0]['name'] == '测试逻辑'

    def test_list_by_tier(self, mock_h, mock_store):
        mock_store.get_tags.return_value = [SAMPLE_TAG]
        from backend.api.logic_tracking import _handle_list_tags
        _handle_list_tags(mock_h, '/api/logic-tracking/tags?tier=focused')
        mock_store.get_tags.assert_called_with(tier='focused')

    def test_list_empty(self, mock_h, mock_store):
        mock_store.get_tags.return_value = []
        from backend.api.logic_tracking import _handle_list_tags
        _handle_list_tags(mock_h, '/api/logic-tracking/tags')
        data = mock_h.send_json.call_args[0][0]
        assert data['tags'] == []


# ═══════════════════════════════════════════════════
# GET /api/logic-tracking/tags/get?id=xxx
# ═══════════════════════════════════════════════════

class TestGetTag:

    def test_get_exists(self, mock_h, mock_store):
        mock_store.get_tag.return_value = SAMPLE_TAG
        from backend.api.logic_tracking import _handle_get_tag
        _handle_get_tag(mock_h, '/api/logic-tracking/tags/get?id=tag-test')
        data = mock_h.send_json.call_args[0][0]
        assert data['name'] == '测试逻辑'

    def test_get_not_found(self, mock_h, mock_store):
        mock_store.get_tag.return_value = None
        from backend.api.logic_tracking import _handle_get_tag
        _handle_get_tag(mock_h, '/api/logic-tracking/tags/get?id=nonexistent')
        data = mock_h.send_json.call_args[0][0]
        assert 'error' in data

    def test_get_no_id(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_get_tag
        _handle_get_tag(mock_h, '/api/logic-tracking/tags/get')
        data = mock_h.send_json.call_args[0][0]
        assert '缺少id' in data.get('error', '')


# ═══════════════════════════════════════════════════
# POST /api/logic-tracking/tags/add
# ═══════════════════════════════════════════════════

class TestAddTag:

    def test_add_success(self, mock_h, mock_store):
        mock_store.add_tag.return_value = None
        from backend.api.logic_tracking import _handle_add_tag
        _handle_add_tag(mock_h, '/api/logic-tracking/tags/add', json.dumps(SAMPLE_TAG))
        mock_store.add_tag.assert_called_once()
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True

    def test_add_duplicate(self, mock_h, mock_store):
        mock_store.add_tag.side_effect = ValueError('标签 tag-test 已存在')
        from backend.api.logic_tracking import _handle_add_tag
        _handle_add_tag(mock_h, '/api/logic-tracking/tags/add', json.dumps(SAMPLE_TAG))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is False
        assert '已存在' in data['error']


# ═══════════════════════════════════════════════════
# POST /api/logic-tracking/tags/update
# ═══════════════════════════════════════════════════

class TestUpdateTag:

    def test_update_success(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_update_tag
        body = json.dumps({'id': 'tag-test', 'name': '新名字'})
        _handle_update_tag(mock_h, '/api/logic-tracking/tags/update', body)
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True

    def test_update_no_id(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_update_tag
        _handle_update_tag(mock_h, '/api/logic-tracking/tags/update', '{}')
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is False
        assert '缺少id' in data.get('error', '')

    def test_update_not_found(self, mock_h, mock_store):
        mock_store.update_tag.side_effect = ValueError('标签 nonexistent 不存在')
        from backend.api.logic_tracking import _handle_update_tag
        _handle_update_tag(mock_h, '/api/logic-tracking/tags/update', json.dumps({'id': 'nonexistent'}))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is False


# ═══════════════════════════════════════════════════
# POST /api/logic-tracking/tags/delete
# ═══════════════════════════════════════════════════

class TestDeleteTag:

    def test_delete_success(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_delete_tag
        _handle_delete_tag(mock_h, '/api/logic-tracking/tags/delete', json.dumps({'id': 'tag-test'}))
        mock_store.delete_tag.assert_called_with('tag-test')
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True

    def test_delete_no_id(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_delete_tag
        _handle_delete_tag(mock_h, '/api/logic-tracking/tags/delete', '{}')
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is False


# ═══════════════════════════════════════════════════
# Entry handlers
# ═══════════════════════════════════════════════════

class TestEntries:

    def test_list_entries(self, mock_h, mock_store):
        mock_store.get_entries.return_value = [{'id': 'e1', 'title': '测试'}]
        from backend.api.logic_tracking import _handle_list_entries
        _handle_list_entries(mock_h, '/api/logic-tracking/entries')
        data = mock_h.send_json.call_args[0][0]
        assert len(data['entries']) == 1

    def test_add_entry(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_add_entry
        _handle_add_entry(mock_h, '/api/logic-tracking/entries/add', json.dumps({'id': 'e1'}))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True

    def test_delete_entry(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_delete_entry
        _handle_delete_entry(mock_h, '/api/logic-tracking/entries/delete', json.dumps({'id': 'e1'}))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True


# ═══════════════════════════════════════════════════
# Forecast handlers
# ═══════════════════════════════════════════════════

class TestForecasts:

    def test_list_forecasts(self, mock_h, mock_store):
        mock_store.get_forecasts.return_value = [{'id': 'f1', 'title': '财报预测'}]
        from backend.api.logic_tracking import _handle_list_forecasts
        _handle_list_forecasts(mock_h, '/api/logic-tracking/forecasts')
        data = mock_h.send_json.call_args[0][0]
        assert len(data['forecasts']) == 1

    def test_list_forecasts_with_upcoming(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_list_forecasts
        _handle_list_forecasts(mock_h, '/api/logic-tracking/forecasts?upcoming=30')
        mock_store.get_forecasts.assert_called_with(upcoming_days=30)

    def test_add_forecast(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_add_forecast
        _handle_add_forecast(mock_h, '/api/logic-tracking/forecasts/add', json.dumps({'id': 'f1'}))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True

    def test_delete_forecast(self, mock_h, mock_store):
        from backend.api.logic_tracking import _handle_delete_forecast
        _handle_delete_forecast(mock_h, '/api/logic-tracking/forecasts/delete', json.dumps({'id': 'f1'}))
        data = mock_h.send_json.call_args[0][0]
        assert data['success'] is True
