"""测试 check_alerts 报警检查服务（基于 alarm_service 持久化报警）"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


SAMPLE_ALARMS = [
    {
        'id': 'alarm_301232_1',
        'stock': '飞沃科技(301232)',
        'stock_code': '301232',
        'type': 'price',
        'enabled': True,
        'stop_loss': 128.88,
        'stop_loss_pct': 7.66,
        'condition': '',
        'created': '2026-05-28T10:30:00',
        'status': 'active',
    },
    {
        'id': 'alarm_002371_2',
        'stock': '北方华创(002371)',
        'stock_code': '002371',
        'type': 'price',
        'enabled': True,
        'stop_loss': 614.63,
        'stop_loss_pct': 6.13,
        'condition': '',
        'created': '2026-05-28T10:30:00',
        'status': 'active',
    },
    {
        'id': 'alarm_002436_3',
        'stock': '兴森科技(002436)',
        'stock_code': '002436',
        'type': 'price',
        'enabled': True,
        'stop_loss': 35.68,
        'stop_loss_pct': 3.62,
        'condition': '',
        'created': '2026-05-28T10:30:00',
        'status': 'active',
    },
    {
        'id': 'alarm_300390_4',
        'stock': '天华新能(300390)',
        'stock_code': '300390',
        'type': 'price',
        'enabled': True,
        'stop_loss': 85.33,
        'stop_loss_pct': 8.16,
        'condition': '',
        'created': '2026-05-28T10:30:00',
        'status': 'active',
    },
    {
        'id': 'alarm_000988_5',
        'stock': '华工科技(000988)',
        'stock_code': '000988',
        'type': 'price',
        'enabled': False,  # 禁用
        'stop_loss': 163.88,
        'stop_loss_pct': 5.0,
        'condition': '',
        'created': '2026-05-28T10:30:00',
        'status': 'disabled',
    },
    {
        'id': 'alarm_002185_6',
        'stock': '华天科技(002185)',
        'stock_code': '002185',
        'type': 'deviation',
        'enabled': True,
        'stop_loss': None,
        'stop_loss_pct': None,
        'condition': '5',
        'created': '2026-05-28T10:30:00',
        'status': 'active',
    },
]


def _mock_realtime(code: str) -> tuple:
    """模拟实时行情：(price, change_pct)"""
    data = {
        '301232': (120.00, -7.5),   # 跌破 128.88 → 触发价格
        '002371': (620.00, 1.2),    # 未破 614.63 → 不触发
        '002436': (33.00, -8.1),    # 跌破 35.68 → 触发价格
        '300390': (90.00, 2.5),     # 未破 85.33 → 不触发
        '000988': (160.00, 0.5),    # 已禁用 → 不检查（不应该在active列表）
        '002185': (18.50, -6.5),    # 偏差 -6.5% > 5% → 触发偏差
        # 以下为核心股
    }
    return data.get(code, (0, 0))


@pytest.fixture
def mock_active_alarms():
    """mock alarm_service.get_active_alarms() — 只返回 active 的报警"""
    active = [a for a in SAMPLE_ALARMS if a.get('status') == 'active']
    with patch('backend.services.check_alerts.get_active_alarms',
               return_value=active):
        yield


@pytest.fixture
def mock_empty_alarms():
    """mock — 空报警列表"""
    with patch('backend.services.check_alerts.get_active_alarms',
               return_value=[]):
        yield


@pytest.fixture
def mock_real_time():
    """mock 实时行情接口"""
    with patch('backend.services.check_alerts._get_realtime_data') as mock:
        mock.side_effect = _mock_realtime
        yield mock


@pytest.fixture
def mock_no_triggered_recently():
    """mock _has_recently_triggered — 返回 False（不走触发抑制）"""
    with patch('backend.services.check_alerts._has_recently_triggered',
               return_value=False):
        yield


class TestCheckAlertsFromAlarmService:
    """基于 alarm_service 的报警检查"""

    def test_price_triggered_when_below_stop_loss(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """跌破止损价应触发价格报警"""
        with patch('backend.services.check_alerts.mark_alarm_triggered') as mock_mark:
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            triggered = result['triggered']
            hit = [t for t in triggered if '飞沃科技' in t['stock']]
            assert len(hit) == 1
            assert hit[0]['current_price'] == 120.00
            assert hit[0]['stop_loss'] == 128.88
            mock_mark.assert_called()  # 至少被调用一次

    def test_price_not_triggered_above_stop_loss(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """未跌破止损价不触发"""
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            hit = [t for t in result['triggered'] if '北方华创' in t['stock']]
            assert len(hit) == 0

    def test_disabled_alert_not_checked(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """禁用的报警（status!=active）不出现在列表中"""
        # 华工科技 status=disabled，不在 mock_active_alarms 中
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            hit = [t for t in result['triggered'] if '华工科技' in t['stock']]
            assert len(hit) == 0

    def test_multiple_triggered(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """多个股票同时触发"""
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            # 飞沃(price) + 兴森(price) + 华天(deviation)
            assert len(result['triggered']) >= 2
            stocks = [t['stock'] for t in result['triggered']]
            assert any('飞沃科技' in s for s in stocks)
            assert any('兴森科技' in s for s in stocks)

    def test_no_alarms_returns_empty(
            self, mock_empty_alarms, mock_real_time):
        """没有报警时返回空"""
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            assert result['triggered'] == []
            assert result['count'] == 0

    def test_price_alert_fields(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """触发报警包含完整字段"""
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            t = result['triggered'][0]
            assert 'type' in t
            assert 'stock' in t
            assert 'code' in t
            assert 'current_price' in t
            assert 'stop_loss' in t
            assert 'loss_pct' in t
            assert 'msg' in t
            assert 'ts' in t

    def test_core_stock_deviation_triggered(self, mock_empty_alarms, mock_real_time):
        """核心股涨跌幅超过阈值触发偏差报警"""
        mock_core = {'301232': {'name': '飞沃科技', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            dev = [t for t in result['triggered'] if t['type'] == 'deviation']
            assert len(dev) == 1
            assert '飞沃科技' in dev[0]['stock']
            assert dev[0]['change_pct'] == -7.5
            assert dev[0]['threshold'] == 6

    def test_core_stock_below_threshold_not_triggered(
            self, mock_empty_alarms, mock_real_time):
        """核心股未超阈值不触发"""
        mock_core = {'002371': {'name': '北方华创', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            dev = [t for t in result['triggered'] if t['type'] == 'deviation']
            assert len(dev) == 0

    def test_deviation_alert_from_alarm_service(
            self, mock_active_alarms, mock_real_time, mock_no_triggered_recently):
        """alarms.json 中的偏差报警触发"""
        with patch('backend.services.check_alerts.mark_alarm_triggered'):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts()
            dev = [t for t in result['triggered'] if t['type'] == 'deviation']
            # 华天科技(002185) deviation 5%，实际 -6.5% > 5%
            hit = [t for t in dev if '华天科技' in t['stock']]
            assert len(hit) >= 1
