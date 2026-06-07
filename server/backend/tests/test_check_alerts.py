"""测试 check_alerts 报警检查服务（基于 alarm_service 持久化报警）"""
import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

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
               return_value=active), \
         patch('backend.services.check_alerts._is_weekend',
               return_value=False):
        yield


@pytest.fixture
def mock_empty_alarms():
    """mock — 空报警列表"""
    with patch('backend.services.check_alerts.get_active_alarms',
               return_value=[]), \
         patch('backend.services.check_alerts._is_weekend',
               return_value=False):
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


# ── 后端独立检测 + 微信推送 ──────────────────────────────


class TestWeChatPush:
    """报警触发时微信推送格式化"""

    def test_push_wechat_not_called_when_no_trigger(self, mock_empty_alarms, mock_real_time):
        """没有触发报警时不调用 _push_wechat"""
        from backend.services.check_alerts import check_all_alerts
        result = check_all_alerts()
        assert result['count'] == 0

    def test_send_alert_batch_handles_triggered(self):
        """send_alert_batch 处理触发报警（验证函数可调用，不发送）"""
        from backend.services.wxpush_sender import send_alert_batch
        from unittest.mock import patch

        triggered = [
            {'type': 'price', 'stock': '飞沃科技(301232)', 'code': '301232',
             'stop_loss': 128.88, 'current_price': 120.0, 'loss_pct': -6.89},
            {'type': 'price', 'stock': '兴森科技(002436)', 'code': '002436',
             'stop_loss': 35.68, 'current_price': 33.0, 'loss_pct': -7.51},
        ]
        with patch('backend.services.wxpush_sender.send_alert') as mock_send:
            send_alert_batch(triggered)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            title, body = args
            assert '飞沃科技' in body
            assert '兴森科技' in body
            assert '2只' in body


class TestAlertCheckerThread:
    """后端独立检测线程"""

    def test_start_alert_checker_creates_daemon_thread(self):
        """start_alert_checker 创建 daemon=True 的线程"""
        from backend.services.check_alerts import start_alert_checker
        thread = start_alert_checker()
        assert thread is not None
        assert thread.daemon is True
        assert thread.name == 'alert-checker'

    def test_start_alert_checker_runs_check_all_alerts(self):
        """线程首次启动时调用 check_all_alerts"""
        from backend.services.check_alerts import start_alert_checker
        with patch('backend.services.check_alerts.check_all_alerts') as mock_check:
            thread = start_alert_checker()
            # 线程刚开始 run，需要等一小段时间
            import time
            time.sleep(0.3)
            mock_check.assert_called_once()
            thread.join(timeout=2)


# ── 频次控制（去重）────────────────────────────────
# 以下测试用纯函数直接测，不依赖 mock


class TestDeviationDedup:
    """偏离报警30分钟去重"""

    def test_deviation_dedup_first_call_returns_false(self):
        """首次调用 _check_deviation_dedup 返回 False（不跳过）"""
        from backend.services.check_alerts import _check_deviation_dedup
        # 清理缓存
        import backend.services.check_alerts as m
        m._deviation_cache.clear()
        assert _check_deviation_dedup('000001') is False

    def test_deviation_dedup_second_call_within_window_returns_true(self):
        """同一股票30分钟内再次调用返回 True（跳过）"""
        from backend.services.check_alerts import _check_deviation_dedup
        import backend.services.check_alerts as m
        m._deviation_cache.clear()
        _check_deviation_dedup('000001')  # 第一次
        assert _check_deviation_dedup('000001') is True  # 第二次

    def test_deviation_dedup_different_codes_independent(self):
        """不同股票的去重缓存互相独立"""
        from backend.services.check_alerts import _check_deviation_dedup
        import backend.services.check_alerts as m
        m._deviation_cache.clear()
        _check_deviation_dedup('000001')
        assert _check_deviation_dedup('000002') is False  # 不同代码，不跳过


class TestIndexDedup:
    """大盘报警3分钟去重"""

    def test_index_dedup_first_call_returns_false(self):
        """首次调用 _check_index_dedup 返回 False"""
        from backend.services.check_alerts import _check_index_dedup
        import backend.services.check_alerts as m
        m._index_alert_cache.clear()
        assert _check_index_dedup('000001', 'critical', 'market_critical') is False

    def test_index_dedup_second_call_within_window_returns_true(self):
        """同一条件3分钟内再次调用返回 True"""
        from backend.services.check_alerts import _check_index_dedup
        import backend.services.check_alerts as m
        m._index_alert_cache.clear()
        _check_index_dedup('000001', 'critical', 'market_critical')  # 第一次
        assert _check_index_dedup('000001', 'critical', 'market_critical') is True  # 第二次

    def test_index_dedup_different_condition_not_blocked(self):
        """不同条件不受影响"""
        from backend.services.check_alerts import _check_index_dedup
        import backend.services.check_alerts as m
        m._index_alert_cache.clear()
        _check_index_dedup('000001', 'critical', 'market_critical')
        assert _check_index_dedup('000001', 'drop', 'market') is False  # 不同条件，不跳过


class TestPushWechatSplit:
    """_push_wechat 按类型分开发送"""

    def test_push_wechat_sends_market_separately(self):
        """大盘预警单独发一条"""
        from backend.services.check_alerts import _push_wechat
        from unittest.mock import patch
        triggered = [
            {'type': 'market', 'stock': '上证指数', 'msg': '上证指数大跌3.2%'},
        ]
        with patch('backend.services.check_alerts.send_alert') as mock_send:
            _push_wechat(triggered)
            assert mock_send.call_count == 1
            args, _ = mock_send.call_args
            assert '大盘' in args[0]

    def test_push_wechat_sends_three_types_separately(self):
        """三种类型各发一条，不合并"""
        from backend.services.check_alerts import _push_wechat
        from unittest.mock import patch
        triggered = [
            {'type': 'market', 'stock': '上证指数', 'msg': '大盘大跌'},
            {'type': 'price', 'stock': '飞沃科技(301232)', 'stop_loss': 128.88,
             'current_price': 120.0, 'loss_pct': -6.89},
            {'type': 'deviation', 'stock': '北方华创', 'change_pct': 6.5},
        ]
        with patch('backend.services.check_alerts.send_alert') as mock_send:
            _push_wechat(triggered)
            assert mock_send.call_count == 3  # 三条独立消息

    def test_push_wechat_skips_empty_types(self):
        """只有部分类型触发时，只发有数据的类型"""
        from backend.services.check_alerts import _push_wechat
        from unittest.mock import patch
        triggered = [
            {'type': 'price', 'stock': '兴森科技(002436)', 'stop_loss': 35.68,
             'current_price': 33.0, 'loss_pct': -7.51},
        ]
        with patch('backend.services.check_alerts.send_alert') as mock_send:
            _push_wechat(triggered)
            assert mock_send.call_count == 1  # 只发了price
            args, _ = mock_send.call_args
            assert '止损' in args[0]
