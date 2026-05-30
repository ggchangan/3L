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
                 'alert': None},  # 无显式alert但有stop_loss → 自动创建
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
        # 4项进入current_keys: (301232,p) (002371,p) (002436,d) (300390,p)
        # 旧(301232,deviation)不在→移除；旧(002371,price)在→保留更新
        assert result['synced'] == 4
        assert result['removed'] == 1

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        codes = {(a['stock_code'], a['type']) for a in alarms}
        assert len(alarms) == 4  # 4条报警（新增3+保留1）
        assert ('002371', 'price') in codes      # 原price保留更新
        assert ('301232', 'price') in codes      # 显式alert新增
        assert ('301232', 'deviation') not in codes  # 旧偏差被移除
        assert ('002436', 'deviation') in codes  # 新增
        assert ('300390', 'price') in codes      # 新增

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
        """报警触发后标记（保持 active，记录触发时间）"""
        from backend.services.alarm_service import mark_alarm_triggered
        result = mark_alarm_triggered('alarm_002371_1745800000')
        assert result['success'] is True

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        match = [a for a in alarms if a['id'] == 'alarm_002371_1745800000']
        assert len(match) == 1
        assert match[0]['status'] == 'active'  # 保持 active 可继续被检查
        assert 'triggered_at' in match[0]      # 记录触发时间

    def test_plan_items_without_alert_get_removed(self, mock_alarm_file_with_data):
        """计划项删除报警后，同步时应移除对应报警"""
        plan = {
            'buy': [{'stock': '北方华创(002371)', 'stop_loss': 614.63,
                     'alert': None}],  # 有stop_loss，自动创建price
            'sell': [],
            'watch': [],
        }
        from backend.services.alarm_service import sync_alarms_from_plan
        result = sync_alarms_from_plan(plan)
        # 旧(002371,price)在current_keys中→保留更新，(301232,deviation)不在→移除
        assert result['removed'] == 1
        assert result['synced'] == 1

        from backend.services.alarm_service import get_alarms
        alarms = get_alarms()
        assert len(alarms) == 1  # 北方华创price报警保留
        assert alarms[0]['stock_code'] == '002371'
        assert alarms[0]['type'] == 'price'

    def test_dismiss_handled_status(self, mock_alarm_file_with_data):
        """dismiss 报警后 status 变为 handled"""
        from backend.services.alarm_service import dismiss_alarm, get_alarms
        result = dismiss_alarm('alarm_002371_1745800000')
        assert result['success'] is True
        assert result['status'] == 'handled'

        alarms = get_alarms()
        match = [a for a in alarms if a['id'] == 'alarm_002371_1745800000']
        assert len(match) == 1
        assert match[0]['status'] == 'handled'
        assert 'dismissed_at' in match[0]

    def test_reenable_restores_active(self, mock_alarm_file_with_data):
        """重新启用报警后 status 变回 active"""
        from backend.services.alarm_service import (
            dismiss_alarm, reenable_alarm, get_alarms, get_active_alarms
        )
        # 先 dismiss
        dismiss_alarm('alarm_002371_1745800000')
        active_before = get_active_alarms()
        assert len(active_before) == 1  # 只剩飞沃科技还 active

        # 再 reenable
        result = reenable_alarm('alarm_002371_1745800000')
        assert result['success'] is True
        assert result['status'] == 'active'

        active_after = get_active_alarms()
        assert len(active_after) == 2  # 两个都恢复了

    def test_dismiss_reenable_toggle_cycle(self, mock_alarm_file_with_data):
        """多次 dismiss-reenable 循环不丢失数据"""
        from backend.services.alarm_service import (
            dismiss_alarm, reenable_alarm, get_alarms
        )
        alarm_id = 'alarm_002371_1745800000'
        for _ in range(3):
            dismiss_alarm(alarm_id)
            reenable_alarm(alarm_id)

        alarms = get_alarms()
        match = [a for a in alarms if a['id'] == alarm_id]
        assert len(match) == 1
        assert match[0]['status'] == 'active'
        assert match[0]['stop_loss'] == 614.63  # 数据不丢失
