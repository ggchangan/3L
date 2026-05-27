"""工作台（交易日志）服务层测试

覆盖 workbench_service.py 的 save/load/list/空模板
使用临时文件，不依赖真实数据
"""
import json
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_LOG = {
    'date': '2026-05-25',
    'review_summary': {'market': '上涨趋势', 'mainline': '算力', 'signals_count': 3, 'marked_count': 1},
    'todos': [{'text': '复盘', 'done': False}, {'text': '看报告', 'done': True}],
    'plan': {
        'buy': [{'stock': '000001', 'condition': '回踩EMA5', 'qty': '1000', 'status': 'pending'}],
        'sell': [],
        'watch': [{'stock': '002371', 'focus': '突破前高', 'status': 'pending'}],
    },
    'operations': '买入平安银行1000股',
    'execution_review': '按计划执行',
    'reflection': {'discipline': '✅ 完全按计划执行', 'learned': '耐心等待买点', 'rating': '⭐⭐⭐⭐'},
}


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def svc(monkeypatch, tmp_path):
    """加载 workbench_service 并指向临时目录"""
    from backend.services import workbench_service as mod
    wb_dir = tmp_path / 'workbench'
    wb_dir.mkdir()
    monkeypatch.setattr(mod, 'WORKBENCH_DIR', str(wb_dir))
    return mod


@pytest.fixture
def svc_with_data(monkeypatch, tmp_path):
    """预填充一条日志"""
    from backend.services import workbench_service as mod
    wb_dir = tmp_path / 'workbench'
    wb_dir.mkdir()
    monkeypatch.setattr(mod, 'WORKBENCH_DIR', str(wb_dir))
    mod.save_log('2026-05-25', SAMPLE_LOG)
    return mod


# ═══════════════════════════════════════════════════════════════════
# get_log
# ═══════════════════════════════════════════════════════════════════

class TestGetLog:

    def test_empty_date_returns_empty_template(self, svc):
        """不传日期返回当日空模板"""
        log = svc.get_log()
        assert log['date'] == date.today().isoformat()
        assert log['todos'] == []
        assert log['plan'] == {'buy': [], 'sell': [], 'watch': []}
        assert log['operations'] == ''
        assert log['execution_review'] == ''

    def test_non_existent_date_returns_empty_template(self, svc):
        """不存在的日期返回空模板"""
        log = svc.get_log('2026-01-01')
        assert log['date'] == '2026-01-01'
        assert log['todos'] == []

    def test_existing_date_returns_saved_data(self, svc_with_data):
        """已保存的日期返回完整数据"""
        log = svc_with_data.get_log('2026-05-25')
        assert log['date'] == '2026-05-25'
        assert log['review_summary']['market'] == '上涨趋势'
        assert log['review_summary']['mainline'] == '算力'
        assert len(log['todos']) == 2
        assert log['todos'][0]['text'] == '复盘'
        assert log['todos'][0]['done'] is False
        assert log['plan']['buy'][0]['stock'] == '000001'

    def test_data_fields_integrity(self, svc_with_data):
        """保存的数据6个区块字段完整不丢"""
        log = svc_with_data.get_log('2026-05-25')
        assert 'review_summary' in log
        assert 'todos' in log
        assert 'plan' in log
        assert 'operations' in log
        assert 'execution_review' in log
        assert 'reflection' in log

    def test_reflection_fields(self, svc_with_data):
        """reflection 子字段完整"""
        log = svc_with_data.get_log('2026-05-25')
        r = log['reflection']
        assert r['discipline'] == '✅ 完全按计划执行'
        assert r['learned'] == '耐心等待买点'
        assert r['rating'] == '⭐⭐⭐⭐'


# ═══════════════════════════════════════════════════════════════════
# save_log
# ═══════════════════════════════════════════════════════════════════

class TestSaveLog:

    def test_save_and_read_back(self, svc):
        """保存后能完整读回"""
        data = dict(SAMPLE_LOG)
        data['date'] = '2026-05-26'
        result = svc.save_log('2026-05-26', data)
        assert result['success'] is True
        assert result['date'] == '2026-05-26'

        log = svc.get_log('2026-05-26')
        assert log['date'] == '2026-05-26'
        assert log['review_summary']['mainline'] == '算力'

    def test_save_overwrites_existing(self, svc):
        """覆盖已有数据"""
        d1 = dict(SAMPLE_LOG)
        d1['date'] = '2026-05-27'
        d1['operations'] = '第一版'
        svc.save_log('2026-05-27', d1)

        d2 = dict(SAMPLE_LOG)
        d2['date'] = '2026-05-27'
        d2['operations'] = '覆盖版'
        svc.save_log('2026-05-27', d2)

        log = svc.get_log('2026-05-27')
        assert log['operations'] == '覆盖版'
        assert len(log['todos']) == 2  # 其它字段不变

    def test_save_with_partial_data(self, svc):
        """保存部分填充的数据（如只写操作没有待办）"""
        data = {
            'date': '2026-05-28',
            'operations': '今日无操作',
            'todos': [],
            'plan': {'buy': [], 'sell': [], 'watch': []},
            'reflection': {'discipline': '', 'learned': '', 'rating': ''},
            'review_summary': {},
            'execution_review': '',
        }
        result = svc.save_log('2026-05-28', data)
        assert result['success'] is True
        log = svc.get_log('2026-05-28')
        assert log['operations'] == '今日无操作'

    def test_save_file_actually_written(self, svc, tmp_path):
        """验证文件确实写入磁盘"""
        data = dict(SAMPLE_LOG)
        data['date'] = '2026-05-29'
        svc.save_log('2026-05-29', data)

        fp = tmp_path / 'workbench' / '2026-05-29.json'
        assert os.path.isfile(fp), '文件未写入'
        with open(fp) as f:
            saved = json.load(f)
        assert saved['date'] == '2026-05-29'
        assert saved['operations'] == '买入平安银行1000股'


# ═══════════════════════════════════════════════════════════════════
# list_logs
# ═══════════════════════════════════════════════════════════════════

class TestListLogs:

    def test_list_empty(self, svc):
        """空目录返回空列表"""
        assert svc.list_logs() == []

    def test_list_single(self, svc_with_data):
        """有一条日志时返回该日期"""
        dates = svc_with_data.list_logs()
        assert '2026-05-25' in dates

    def test_list_multiple_descending(self, svc):
        """多条日志按日期降序排列"""
        for d in ['2026-05-20', '2026-05-21', '2026-05-22', '2026-05-25']:
            data = dict(SAMPLE_LOG)
            data['date'] = d
            svc.save_log(d, data)

        dates = svc.list_logs()
        assert dates == ['2026-05-25', '2026-05-22', '2026-05-21', '2026-05-20']

    def test_list_filters_non_date_files(self, svc):
        """只返回日期格式文件，忽略其他文件"""
        svc.save_log('2026-05-25', dict(SAMPLE_LOG))
        # 手动写入非日期文件
        from backend.services import workbench_service as mod
        fp = os.path.join(mod.WORKBENCH_DIR, 'notes.txt')
        with open(fp, 'w') as f:
            f.write('not a log')

        dates = svc.list_logs()
        assert '2026-05-25' in dates
        assert len(dates) == 1


# ═══════════════════════════════════════════════════════════════════
# Empty template structure
# ═══════════════════════════════════════════════════════════════════

class TestEmptyTemplate:

    def test_empty_template_structure(self, svc):
        """空模板包含所有6个区块且结构正确"""
        log = svc.get_log('2026-06-01')
        # review_summary
        assert log['review_summary']['market'] == ''
        assert log['review_summary']['mainline'] == ''
        assert log['review_summary']['signals_count'] == 0
        assert log['review_summary']['marked_count'] == 0
        # todos
        assert log['todos'] == []
        # plan
        assert log['plan'] == {'buy': [], 'sell': [], 'watch': []}
        # operations
        assert log['operations'] == ''
        # execution_review
        assert log['execution_review'] == ''
        # reflection
        assert log['reflection']['discipline'] == ''
        assert log['reflection']['learned'] == ''
        assert log['reflection']['rating'] == ''
        # alerts
        assert log['alerts'] == []


# ═══════════════════════════════════════════════════════════════════
# Alerts
# ═══════════════════════════════════════════════════════════════════

class TestAlerts:

    def test_empty_template_has_alerts_field(self, svc):
        """空模板包含 alerts 字段"""
        log = svc.get_log('2026-06-01')
        assert 'alerts' in log
        assert log['alerts'] == []

    def test_save_and_read_alerts(self, svc):
        """保存 alerts 后能完整读回"""
        data = dict(SAMPLE_LOG)
        data['date'] = '2026-06-01'
        data['alerts'] = [
            {'type': 'price', 'stock': '雷赛智能', 'condition': '跌破22.5', 'enabled': True},
            {'type': 'deviation', 'stock': '大盘', 'condition': '成交额低于昨日50%', 'enabled': True},
        ]
        svc.save_log('2026-06-01', data)
        log = svc.get_log('2026-06-01')
        assert len(log['alerts']) == 2
        assert log['alerts'][0]['type'] == 'price'
        assert log['alerts'][0]['stock'] == '雷赛智能'
        assert log['alerts'][0]['condition'] == '跌破22.5'
        assert log['alerts'][1]['condition'] == '成交额低于昨日50%'

    def test_save_plan_with_alert(self, svc):
        """plan 每项可带 alert 字段"""
        data = dict(SAMPLE_LOG)
        data['date'] = '2026-06-02'
        data['plan']['buy'][0]['alert'] = {
            'type': 'price', 'stock': '000001', 'condition': '跌破10', 'enabled': True
        }
        svc.save_log('2026-06-02', data)
        log = svc.get_log('2026-06-02')
        buy_alert = log['plan']['buy'][0]['alert']
        assert buy_alert is not None
        assert buy_alert['type'] == 'price'
        assert buy_alert['condition'] == '跌破10'

    def test_plan_alert_defaults_to_null(self, svc):
        """未设置报警的 plan 项 alert 为 null"""
        log = svc.get_log('2026-06-03')
        for items in [log['plan']['buy'], log['plan']['sell'], log['plan']['watch']]:
            for item in items:
                assert item.get('alert') is None or item.get('alert') == ''

    def test_alerts_serialized_correctly(self, svc, tmp_path):
        """磁盘上的 JSON 文件包含 alerts 字段"""
        data = dict(SAMPLE_LOG)
        data['date'] = '2026-06-04'
        data['alerts'] = [{'type': 'time', 'condition': '收盘前15分钟提醒', 'enabled': True}]
        svc.save_log('2026-06-04', data)

        fp = tmp_path / 'workbench' / '2026-06-04.json'
        with open(fp) as f:
            saved = __import__('json').load(f)
        assert 'alerts' in saved
        assert saved['alerts'][0]['type'] == 'time'
