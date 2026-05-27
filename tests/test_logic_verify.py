"""
走势验证服务测试
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_kline(date_str, close):
    """Helper: create a kline dict"""
    return {'date': date_str.replace('-', ''), 'close': close}


MOCK_KLINES = {
    '300502': [
        {'date': '20260520', 'close': 100.0},
        {'date': '20260521', 'close': 102.0},
        {'date': '20260522', 'close': 105.0},
        {'date': '20260523', 'close': 103.0},
        {'date': '20260526', 'close': 110.0},
    ],
    '600584': [
        {'date': '20260520', 'close': 50.0},
        {'date': '20260521', 'close': 51.0},
        {'date': '20260526', 'close': 52.0},
    ],
}


@pytest.fixture
def mock_all_stocks():
    """mock data_layer.get_all_stocks to return controlled data"""
    with patch('backend.services.logic_verify_service._get_stock_klines') as m:
        def side_effect(code):
            return MOCK_KLINES.get(code, None)
        m.side_effect = side_effect
        yield m


class TestVerifyEvent:

    def test_verify_3d_return(self, mock_all_stocks):
        """验证事件后3日涨跌幅"""
        from backend.services.logic_verify_service import verify_entry
        result = verify_entry('300502', '中际旭创', '2026-05-20')
        assert result is not None
        # Event on 2026-05-20 (close 100.0)
        # 3 trading days: 05-20→05-21→05-22→05-23, but 05-23 closes at 103.0
        # Actually: start at 05-20 (100), after 3 trading sessions = 05-23 (103.0)
        # 103 vs 100 = +3%
        assert abs(result['3d_return'] - 3.0) < 0.01

    def test_verify_5d_return(self, mock_all_stocks):
        from backend.services.logic_verify_service import verify_entry
        result = verify_entry('300502', '中际旭创', '2026-05-20')
        # 5 trading days from 05-20: 05-21(1), 05-22(2), 05-23(3), 05-26(4), next(5)
        # Only 4 trading days available, so 5d_return = 0
        assert '5d_return' in result

    def test_verify_recent_event(self, mock_all_stocks):
        """近期事件（数据不足）也能验证，返回已有数据"""
        from backend.services.logic_verify_service import verify_entry
        result = verify_entry('300502', '中际旭创', '2026-05-26')
        assert result is not None
        assert '3d_return' in result

    def test_verify_stock_not_found(self, mock_all_stocks):
        """不存在的股票返回None"""
        from backend.services.logic_verify_service import verify_entry
        result = verify_entry('999999', '不存在', '2026-05-20')
        assert result is None


class TestAutoVerifyAfterFeed:

    def test_verify_all_entries(self, mock_all_stocks, tmp_path):
        """对所有未验证的条目批量验证"""
        store_path = tmp_path / 'logic_test.json'
        from backend.core.logic_tracking_store import LogicTrackingStore
        store = LogicTrackingStore(str(store_path))
        # Add entries directly
        entries = [
            {'id': 'e1', 'companies': ['300502'], 'fed_at': '2026-05-20',
             'verify': {'verified_at': None, '3d_return': 0}},
            {'id': 'e2', 'companies': ['600584'], 'fed_at': '2026-05-20',
             'verify': {'verified_at': None, '3d_return': 0}},
        ]
        for e in entries:
            store.add_entry(e)

        with patch('backend.services.logic_verify_service._get_store', return_value=store):
            from backend.services.logic_verify_service import verify_unverified_entries
            count = verify_unverified_entries()
            assert count == 2
            # Verify the store was updated
            updated = store.get_entries()
            for e in updated:
                assert e['verify']['verified_at'] is not None
                assert e['verify']['3d_return'] is not None

    def test_verify_skip_already_verified(self, mock_all_stocks):
        """已经验证过的跳过"""
        with patch('backend.services.logic_verify_service._get_store') as mock_s:
            store = MagicMock()
            entries = [
                {'id': 'e1', 'companies': ['300502'], 'fed_at': '2026-05-20',
                 'verify': {'verified_at': '2026-05-27', '3d_return': 5.0}},
            ]
            store.get_entries.return_value = entries
            mock_s.return_value = store

            from backend.services.logic_verify_service import verify_unverified_entries
            count = verify_unverified_entries()
            assert count == 0  # 已验证，跳过
