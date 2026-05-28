"""测试 alarm_service — 持久化报警存储"""
import json
import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta


SAMPLE_ALARMS = {
    'alarms': [
        {
            'id': 'alarm_002371_1745800000',
            'stock': '北方华创(002371)',
            'stock_code': '002371',
            'type': 'price',
            'enabled': True,
            'stop_loss': 614.63,
            'stop_loss_pct': 6.13,
            'condition': '',
            'created': '2026-05-28T10:30:00',
            'status': 'active',
            'expires_days': 7,
        },
        {
            'id': 'alarm_301232_1745800001',
            'stock': '飞沃科技(301232)',
            'stock_code': '301232',
            'type': 'deviation',
            'enabled': True,
            'stop_loss': None,
            'stop_loss_pct': None,
            'condition': '6',
            'created': '2026-05-28T10:35:00',
            'status': 'active',
            'expires_days': 7,
        },
    ]
}


@pytest.fixture
def mock_alarm_file(tmp_path):
    """临时 alarms.json"""
    fp = tmp_path / 'alarms.json'
    with patch('backend.services.alarm_service.ALARMS_PATH', str(fp)):
        yield fp


@pytest.fixture
def mock_alarm_file_with_data(mock_alarm_file):
    """预先写入测试数据"""
    with open(mock_alarm_file, 'w', encoding='utf-8') as f:
        json.dump(SAMPLE_ALARMS, f, ensure_ascii=False, indent=2)
    yield mock_alarm_file


class TestAlarmService:
    """报警存储服务"""

    def test_get_alarms_returns_empty_when_no_file(self, mock_alarm_file):
        """文件不存在时返回空列表"""
        from backend.services.alarm_service import get_alarms
        assert get_alarms() == []

    def test_get_alarms_returns_data(self, mock_alarm_file_with_data):
        """正常返回历史报警"""
        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 2
        assert alarms[0]['stock_code'] == '002371'
        assert alarms[0]['status'] == 'active'

    def test_get_active_alarms_filters_status(self, mock_alarm_file_with_data):
        """只返回 active 状态"""
        from backend.services.alarm_service import get_active_alarms
        alarms = get_active_alarms()
        assert len(alarms) == 2  # 两个都是 active

    def test_get_active_alarms_excludes_triggered(self, mock_alarm_file):
        """triggered/expired/disabled 不返回"""
        data = {
            'alarms': [
                {'id': 'a1', 'status': 'active'},
                {'id': 'a2', 'status': 'triggered'},
                {'id': 'a3', 'status': 'expired'},
                {'id': 'a4', 'status': 'disabled'},
            ]
        }
        with open(mock_alarm_file, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        from backend.services.alarm_service import get_active_alarms
        alarms = get_active_alarms()
        assert len(alarms) == 1
        assert alarms[0]['id'] == 'a1'

    def test_save_alarm_creates_new(self, mock_alarm_file):
        """添加新报警"""
        from backend.services.alarm_service import save_alarm
        alarm = {
            'stock': '兴森科技(002436)',
            'stock_code': '002436',
            'type': 'price',
            'enabled': True,
            'stop_loss': 35.68,
            'stop_loss_pct': 3.62,
            'condition': '',
        }
        result = save_alarm(alarm)
        assert result['success'] is True
        assert result['id'] is not None

        # 验证写入
        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 1
        assert alarms[0]['stock_code'] == '002436'
        assert alarms[0]['status'] == 'active'

    def test_save_alarm_updates_existing(self, mock_alarm_file_with_data):
        """更新已有报警（按 stock_code+type 匹配）"""
        from backend.services.alarm_service import save_alarm
        alarm = {
            'stock': '北方华创(002371)',
            'stock_code': '002371',
            'type': 'price',
            'enabled': False,  # 禁用
            'stop_loss': 600.00,  # 更新止损
            'stop_loss_pct': 5.0,
            'condition': '',
        }
        result = save_alarm(alarm)
        assert result['success'] is True

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 2  # 总数不变
        match = [a for a in alarms if a['stock_code'] == '002371' and a['type'] == 'price']
        assert len(match) == 1
        assert match[0]['enabled'] is False
        assert match[0]['stop_loss'] == 600.00

    def test_sync_alarms_from_plan(self, mock_alarm_file_with_data):
        """从计划项同步报警"""
        plan = {
            'buy': [
                {'stock': '飞沃科技(301232)', 'stop_loss': 128.88, 'stop_loss_pct': 7.66,
                 'alert': {'type': 'price', 'enabled': True, 'condition': ''}},
                {'stock': '北方华创(002371)', 'stop_loss': 614.63, 'stop_loss_pct': 6.13,
                 'alert': None},  # 无报警，不应同步
                {'stock': '兴森科技(002436)', 'stop_loss': 35.68, 'stop_loss_pct': 3.62,
                 'alert': {'type': 'deviation', 'enabled': True, 'condition': '5'}},
            ],
            'sell': [
                {'stock': '天华新能(300390)', 'stop_loss': 85.33, 'stop_loss_pct': 8.16,
                 'alert': {'type': 'price', 'enabled': True, 'condition': ''}},
            ],
            'watch': [],
        }
        from backend.services.alarm_service import sync_alarms_from_plan
        result = sync_alarms_from_plan(plan)
        assert result['synced'] == 3  # 3个有报警的
        # 原有的 (002371,price) 和 (301232,deviation) 都不在当前计划中
        # (002371,price) 没有了，(301232,deviation) 变成了 (301232,price) 覆盖
        assert result['removed'] == 2

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        # 北方华创没有alert → 被移除
        codes = {(a['stock_code'], a['type']) for a in alarms}
        assert ('002371', 'price') not in codes  # 被移除
        assert ('301232', 'deviation') not in codes  # 旧类型被移除
        assert ('301232', 'price') in codes  # 新增price类型
        assert ('002436', 'deviation') in codes  # 新增
        assert ('300390', 'price') in codes  # 新增

    def test_remove_alarm(self, mock_alarm_file_with_data):
        """删除指定报警"""
        from backend.services.alarm_service import remove_alarm
        result = remove_alarm('alarm_002371_1745800000')
        assert result['success'] is True

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 1
        assert alarms[0]['id'] != 'alarm_002371_1745800000'

    def test_remove_alarm_not_found(self, mock_alarm_file_with_data):
        """删除不存在的报警返回失败"""
        from backend.services.alarm_service import remove_alarm
        result = remove_alarm('nonexistent')
        assert result['success'] is False

    def test_mark_triggered(self, mock_alarm_file_with_data):
        """报警触发后标记状态"""
        from backend.services.alarm_service import mark_alarm_triggered
        result = mark_alarm_triggered('alarm_002371_1745800000')
        assert result['success'] is True

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        match = [a for a in alarms if a['id'] == 'alarm_002371_1745800000']
        assert len(match) == 1
        assert match[0]['status'] == 'triggered'
        assert 'triggered_at' in match[0]

    def test_plan_items_without_alert_get_removed(self, mock_alarm_file_with_data):
        """计划项删除报警后，同步时应移除对应报警"""
        plan = {
            'buy': [{'stock': '北方华创(002371)', 'stop_loss': 614.63,
                     'alert': None}],  # 之前有price报警，现在没了
            'sell': [],
            'watch': [],
        }
        from backend.services.alarm_service import sync_alarms_from_plan
        result = sync_alarms_from_plan(plan)
        # 之前2条报警（002371, 301232）全部不在计划中 → 全部移除
        assert result['removed'] == 2

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 0  # 全部被移除
