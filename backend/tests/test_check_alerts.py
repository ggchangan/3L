"""测试 check_alerts 价格报警服务"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


SAMPLE_PLAN = {
    'date': '2026-05-27',
    'plan': {
        'buy': [
            {
                'stock': '飞沃科技(301232)',
                'condition': '区间底部·区底企稳',
                'stop_loss': 128.88,
                'stop_loss_pct': 7.66,
                'alert': {'type': 'price', 'enabled': True},
            },
            {
                'stock': '北方华创(002371)',
                'condition': '中继买点 -2.31%',
                'stop_loss': 614.63,
                'stop_loss_pct': 6.13,
                'alert': None,
            },
            {
                'stock': '兴森科技(002436)',
                'condition': '中继买点 -2.86%',
                'stop_loss': 35.68,
                'stop_loss_pct': 3.62,
                'alert': {'type': 'price', 'enabled': True},
            },
        ],
        'sell': [
            {
                'stock': '天华新能(300390)',
                'condition': '下降趋势·下行',
                'stop_loss': 85.33,
                'stop_loss_pct': 8.16,
                'alert': {'type': 'price', 'enabled': True},
            },
        ],
        'watch': [
            {
                'stock': '华工科技(000988)',
                'focus': '关注突破',
                'stop_loss': 163.88,
                'stop_loss_pct': 5.0,
                'alert': {'type': 'price', 'enabled': False},
            },
        ],
    },
}


def _mock_price(code: str) -> float:
    """模拟实时价格：飞沃破止损、北方未破、兴森破、天华未破"""
    prices = {
        '301232': 120.00,   # 跌破 128.88 → 触发
        '002371': 620.00,   # 未破 614.63 → 不触发
        '002436': 33.00,    # 跌破 35.68 → 触发
        '300390': 90.00,    # 未破 85.33 → 不触发
        '000988': 160.00,   # 已禁用 → 不检查
    }
    return prices.get(code, 0)


@pytest.fixture
def mock_workbench_log():
    """mock 工作台日志读取"""
    with patch('backend.services.check_alerts._load_workbench_plan') as mock:
        mock.return_value = SAMPLE_PLAN['plan']
        yield mock


@pytest.fixture
def mock_real_time_price():
    """mock 实时行情接口"""
    with patch('backend.services.check_alerts._get_realtime_price') as mock:
        mock.side_effect = _mock_price
        yield mock


class TestCheckPriceAlerts:
    """价格报警检查"""

    def test_triggered_when_price_below_stop_loss(self, mock_workbench_log, mock_real_time_price):
        """跌破止损价应触发报警"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        # 飞沃科技 120 < 128.88 → 触发
        hit = [t for t in triggered if '飞沃科技' in t['stock']]
        assert len(hit) == 1
        assert hit[0]['current_price'] == 120.00
        assert hit[0]['stop_loss'] == 128.88

    def test_not_triggered_when_price_above_stop_loss(self, mock_workbench_log, mock_real_time_price):
        """未跌破止损价不触发"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        hit = [t for t in triggered if '北方华创' in t['stock']]
        assert len(hit) == 0

    def test_disabled_alert_not_checked(self, mock_workbench_log, mock_real_time_price):
        """禁用的报警不检查"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        hit = [t for t in triggered if '华工科技' in t['stock']]
        assert len(hit) == 0

    def test_multiple_triggered(self, mock_workbench_log, mock_real_time_price):
        """多个股票同时跌破止损"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        assert len(result['triggered']) == 2  # 飞沃+兴森
        stocks = [t['stock'] for t in result['triggered']]
        assert '飞沃科技' in str(stocks)
        assert '兴森科技' in str(stocks)

    def test_no_alert_plan_returns_empty(self):
        """没有报警配置的计划返回空"""
        empty_plan = {'buy': [], 'sell': [], 'watch': []}
        with patch('backend.services.check_alerts._load_workbench_plan', return_value=empty_plan):
            from backend.services.check_alerts import check_price_alerts
            result = check_price_alerts('2026-05-27')
            assert result['triggered'] == []
            assert result['count'] == 0

    def test_parse_stock_code(self):
        """从 '北方华创(002371)' 解析出 002371"""
        from backend.services.check_alerts import _parse_stock_code
        assert _parse_stock_code('北方华创(002371)') == '002371'
        assert _parse_stock_code('飞沃科技(301232)') == '301232'
        assert _parse_stock_code('') is None

    def test_price_alert_fields(self, mock_workbench_log, mock_real_time_price):
        """触发报警包含完整字段"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        t = result['triggered'][0]
        assert 'stock' in t
        assert 'code' in t
        assert 'current_price' in t
        assert 'stop_loss' in t
        assert 'loss_pct' in t
        assert 'ts' in t
