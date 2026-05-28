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


def _mock_realtime(code: str) -> tuple:
    """模拟实时行情：(price, change_pct)
    飞沃破止损（-7%）、北方未破（+1%）、兴森破（-8%）、天华未破（+2%）
    """
    data = {
        '301232': (120.00, -7.5),   # 跌破 128.88 → 触发价格；跌幅 7.5% > 6% → 也触发偏差
        '002371': (620.00, 1.2),    # 未破 614.63 → 不触发价格；1.2% < 6% → 不触发偏差
        '002436': (33.00, -8.1),    # 跌破 35.68 → 触发价格；8.1% > 6% → 也触发偏差
        '300390': (90.00, 2.5),     # 未破 85.33 → 不触发价格
        '000988': (160.00, 0.5),    # 已禁用 → 不检查
    }
    return data.get(code, (0, 0))


@pytest.fixture
def mock_workbench_log():
    """mock 工作台日志读取"""
    with patch('backend.services.check_alerts._load_workbench_plan') as mock:
        mock.return_value = SAMPLE_PLAN['plan']
        yield mock


@pytest.fixture
def mock_real_time_data():
    """mock 实时行情接口"""
    with patch('backend.services.check_alerts._get_realtime_data') as mock:
        mock.side_effect = _mock_realtime
        yield mock


class TestCheckPriceAlerts:
    """价格报警检查"""

    def test_triggered_when_price_below_stop_loss(self, mock_workbench_log, mock_real_time_data):
        """跌破止损价应触发报警"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        # 飞沃科技 120 < 128.88 → 触发
        hit = [t for t in triggered if '飞沃科技' in t['stock']]
        assert len(hit) == 1
        assert hit[0]['current_price'] == 120.00
        assert hit[0]['stop_loss'] == 128.88

    def test_not_triggered_when_price_above_stop_loss(self, mock_workbench_log, mock_real_time_data):
        """未跌破止损价不触发"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        hit = [t for t in triggered if '北方华创' in t['stock']]
        assert len(hit) == 0

    def test_disabled_alert_not_checked(self, mock_workbench_log, mock_real_time_data):
        """禁用的报警不检查"""
        from backend.services.check_alerts import check_price_alerts
        result = check_price_alerts('2026-05-27')
        triggered = result['triggered']
        hit = [t for t in triggered if '华工科技' in t['stock']]
        assert len(hit) == 0

    def test_multiple_triggered(self, mock_workbench_log, mock_real_time_data):
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

    def test_price_alert_fields(self, mock_workbench_log, mock_real_time_data):
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


class TestDeviationAlerts:
    """偏差报警检查"""

    def test_core_stock_deviation_triggered(self, mock_real_time_data):
        """核心股涨跌幅超过阈值触发偏差报警"""
        mock_core = {'301232': {'name': '飞沃科技', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            with patch('backend.services.check_alerts._load_workbench_plan',
                       return_value={'buy': [], 'sell': [], 'watch': []}):
                from backend.services.check_alerts import check_all_alerts
                result = check_all_alerts('2026-05-27')
                dev = [t for t in result['triggered'] if t['type'] == 'deviation']
                assert len(dev) == 1
                assert '飞沃科技' in dev[0]['stock']
                assert dev[0]['change_pct'] == -7.5
                assert dev[0]['threshold'] == 6

    def test_core_stock_below_threshold_not_triggered(self, mock_real_time_data):
        """核心股涨跌幅未超过阈值不触发"""
        mock_core = {'002371': {'name': '北方华创', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            with patch('backend.services.check_alerts._load_workbench_plan',
                       return_value={'buy': [], 'sell': [], 'watch': []}):
                from backend.services.check_alerts import check_all_alerts
                result = check_all_alerts('2026-05-27')
                dev = [t for t in result['triggered'] if t['type'] == 'deviation']
                assert len(dev) == 0

    def test_plan_item_deviation_triggered(self, mock_real_time_data):
        """计划项的手动偏差报警触发"""
        plan = {
            'buy': [{'stock': '兴森科技(002436)', 'alert': {'type': 'deviation', 'enabled': True, 'condition': '5'}}],
            'sell': [], 'watch': []
        }
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value={}):
            with patch('backend.services.check_alerts._load_workbench_plan',
                       return_value=plan):
                from backend.services.check_alerts import check_all_alerts
                result = check_all_alerts('2026-05-27')
                dev = [t for t in result['triggered'] if t['type'] == 'deviation']
                assert len(dev) == 1
                assert '兴森科技' in dev[0]['stock']
                assert dev[0]['change_pct'] == -8.1
                assert dev[0]['threshold'] == 5

    def test_deviation_alert_fields(self, mock_real_time_data):
        """偏差触发报警包含完整字段"""
        mock_core = {'301232': {'name': '飞沃科技', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            with patch('backend.services.check_alerts._load_workbench_plan',
                       return_value={'buy': [], 'sell': [], 'watch': []}):
                from backend.services.check_alerts import check_all_alerts
                result = check_all_alerts('2026-05-27')
                t = result['triggered'][0]
                assert 'type' in t
                assert 'stock' in t
                assert 'code' in t
                assert 'change_pct' in t
                assert 'threshold' in t
                assert 'msg' in t
                assert 'ts' in t

    def test_check_all_alerts_returns_both_types(self, mock_workbench_log, mock_real_time_data):
        """check_all_alerts 同时返回价格和偏差报警"""
        mock_core = {'301232': {'name': '飞沃科技', 'deviation': 6}}
        with patch('backend.services.check_alerts._get_core_stocks',
                   return_value=mock_core):
            from backend.services.check_alerts import check_all_alerts
            result = check_all_alerts('2026-05-27')
            types = {t['type'] for t in result['triggered']}
            assert 'price' in types
            assert 'deviation' in types

    def test_merge_dates_combines_plans(self, mock_real_time_data):
        """merge_dates 合并多天计划"""
        plan_a = {'buy': [{'stock': '飞沃科技(301232)', 'stop_loss': 128.88, 'alert': {'type': 'price', 'enabled': True}}], 'sell': [], 'watch': []}
        plan_b = {'buy': [{'stock': '兴森科技(002436)', 'stop_loss': 35.68, 'alert': {'type': 'price', 'enabled': True}}], 'sell': [], 'watch': []}
        load_mock = {
            '2026-05-27': plan_a,
            '2026-05-28': plan_b,
        }
        with patch('backend.services.check_alerts._load_workbench_plan',
                   side_effect=lambda d: load_mock.get(d, {'buy': [], 'sell': [], 'watch': []})):
            with patch('backend.services.check_alerts._get_core_stocks', return_value={}):
                from backend.services.check_alerts import check_all_alerts
                result = check_all_alerts(merge_dates=['2026-05-27', '2026-05-28'])
                stocks = {t['stock'] for t in result['triggered']}
                assert '飞沃科技(301232)' in stocks
                assert '兴森科技(002436)' in stocks


class TestCoreStocks:
    """核心股读取"""

    def test_get_core_stocks_returns_empty_when_not_set(self):
        """directions.json 没有 core 字段时返回空"""
        with patch('backend.services.direction_service._load',
                   return_value={'all': [], 'active': []}):
            from backend.services.direction_service import get_core_stocks
            assert get_core_stocks() == {}

    def test_get_core_stocks_with_data(self):
        """正常返回核心股列表"""
        mock_data = {
            'all': ['半导体'],
            'active': ['半导体'],
            'core': {
                '002371': {'name': '北方华创', 'deviation': 6},
                '301232': {'name': '飞沃科技', 'deviation': 3},
            }
        }
        with patch('backend.services.direction_service._load',
                   return_value=mock_data):
            from backend.services.direction_service import get_core_stocks
            result = get_core_stocks()
            assert result['002371']['name'] == '北方华创'
            assert result['002371']['deviation'] == 6
            assert result['301232']['deviation'] == 3

    def test_core_stock_default_deviation(self):
        """未设 deviation 默认 6%"""
        mock_data = {
            'all': [],
            'active': [],
            'core': {
                '000001': {'name': '平安银行'},
            }
        }
        with patch('backend.services.direction_service._load',
                   return_value=mock_data):
            from backend.services.direction_service import get_core_stocks
            assert get_core_stocks()['000001']['deviation'] == 6
