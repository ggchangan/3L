"""
逻辑追踪存储层测试

测试 backend.core.logic_tracking_store 的所有操作
使用 tmp_path 隔离，不碰生产文件
"""
import json
import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


SAMPLE_TAG = {
    "id": "tag-test",
    "name": "测试逻辑",
    "description": "测试用",
    "related_industries": ["半导体"],
    "related_stocks": ["002371"],
    "tier": "focused",
    "tier_override": False,
    "event_count": 0,
    "verify_rate": 0.0,
    "earnings_verify_rate": 0.0,
    "forecast_accuracy": "0/0",
    "created_at": "2026-05-27",
    "updated_at": "2026-05-27",
}

SAMPLE_ENTRY = {
    "id": "entry-test",
    "source_type": "link",
    "source_name": "测试源",
    "title": "测试文章",
    "summary": "摘要内容",
    "url": "https://example.com/test",
    "industries": ["半导体"],
    "companies": ["002371"],
    "logic_tags": ["tag-test"],
    "fed_at": "2026-05-27 14:30",
    "verify": {
        "3d_return": 0.0, "5d_return": 0.0, "10d_return": 0.0,
        "sector_rank_before": 5, "sector_rank_after": 3,
        "buy_signal_count": 0, "summary": "", "score": None, "verified_at": None,
    },
}


@pytest.fixture
def store():
    """用 tmp_path 创建隔离的存储实例"""
    from backend.core.logic_tracking_store import LogicTrackingStore
    tmp = pytest.ensuretemp  # not used, we pass path directly
    # Use monkeypatch to override path
    return None


@pytest.fixture
def store_path(tmp_path):
    """返回临时文件路径"""
    return os.path.join(tmp_path, 'logic_tracking.json')


# ═══════════════════════════════════════════════════
# init / empty store
# ═══════════════════════════════════════════════════

class TestInit:

    def test_init_creates_file(self, store_path):
        """初始化时文件不存在则使用空模板，首次写操作后创建"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        assert not os.path.isfile(store_path)  # 懒加载，不直接写文件
        assert s.get_all()['tags'] == []
        # 首次写操作后文件才创建
        s.add_tag(SAMPLE_TAG)
        assert os.path.isfile(store_path)

    def test_init_loads_existing(self, store_path):
        """初始化时文件已存在则加载"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        initial = {'tags': [SAMPLE_TAG], 'entries': [], 'forecasts': [], 'updated_at': '2026-05-27'}
        with open(store_path, 'w') as f:
            json.dump(initial, f)
        s = LogicTrackingStore(store_path)
        assert len(s.get_all()['tags']) == 1
        assert s.get_all()['tags'][0]['name'] == '测试逻辑'


# ═══════════════════════════════════════════════════
# tag CRUD
# ═══════════════════════════════════════════════════

class TestTags:

    def test_add_tag(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        tags = s.get_tags()
        assert len(tags) == 1
        assert tags[0]['name'] == '测试逻辑'

    def test_add_duplicate_id_raises(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        with pytest.raises(ValueError, match='已存在'):
            s.add_tag(SAMPLE_TAG)

    def test_get_tag_by_id(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        t = s.get_tag('tag-test')
        assert t is not None
        assert t['name'] == '测试逻辑'

    def test_get_tag_not_found(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        assert s.get_tag('nonexistent') is None

    def test_update_tag(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        updated = dict(SAMPLE_TAG)
        updated['name'] = '新名字'
        updated['tier'] = 'core'
        s.update_tag('tag-test', updated)
        t = s.get_tag('tag-test')
        assert t['name'] == '新名字'
        assert t['tier'] == 'core'

    def test_update_tag_not_found(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        with pytest.raises(ValueError, match='不存在'):
            s.update_tag('nonexistent', SAMPLE_TAG)

    def test_delete_tag(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.delete_tag('tag-test')
        assert s.get_tag('tag-test') is None
        assert len(s.get_tags()) == 0

    def test_delete_tag_not_found(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        with pytest.raises(ValueError, match='不存在'):
            s.delete_tag('nonexistent')

    def test_get_tags_by_tier(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        focus = dict(SAMPLE_TAG, id='tag-f1', tier='focused')
        core = dict(SAMPLE_TAG, id='tag-c1', tier='core', name='核心逻辑')
        watch = dict(SAMPLE_TAG, id='tag-w1', tier='watch', name='观察逻辑')
        s.add_tag(focus)
        s.add_tag(core)
        s.add_tag(watch)
        focused = s.get_tags(tier='focused')
        assert len(focused) == 1
        assert focused[0]['id'] == 'tag-f1'
        assert len(s.get_tags(tier='core')) == 1
        assert len(s.get_tags(tier='watch')) == 1

    def test_focused_limit(self, store_path):
        """聚焦层级最多3个"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        for i in range(3):
            t = dict(SAMPLE_TAG, id=f'tag-f{i}', name=f'聚焦{i}', tier='focused')
            s.add_tag(t)
        # 尝试加第4个
        t4 = dict(SAMPLE_TAG, id='tag-f4', name='聚焦4', tier='focused')
        with pytest.raises(ValueError, match='聚焦层级最多3个'):
            s.add_tag(t4)

    def test_tag_count_increments_on_entry(self, store_path):
        """添加条目时自动更新标签事件数"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.add_entry(SAMPLE_ENTRY)
        t = s.get_tag('tag-test')
        assert t['event_count'] == 1


# ═══════════════════════════════════════════════════
# entry CRUD
# ═══════════════════════════════════════════════════

class TestEntries:

    def test_add_entry(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.add_entry(SAMPLE_ENTRY)
        assert len(s.get_entries()) == 1
        assert s.get_entries()[0]['title'] == '测试文章'

    def test_get_entries_by_tag(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.add_entry(SAMPLE_ENTRY)
        entries = s.get_entries(tag_id='tag-test')
        assert len(entries) == 1

    def test_get_entries_by_tag_none(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        entries = s.get_entries(tag_id='nonexistent')
        assert len(entries) == 0

    def test_delete_entry(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.add_entry(SAMPLE_ENTRY)
        s.delete_entry('entry-test')
        assert len(s.get_entries()) == 0


# ═══════════════════════════════════════════════════
# forecast CRUD
# ═══════════════════════════════════════════════════

class TestForecasts:

    SAMPLE_FCST = {
        "id": "fcst-test",
        "type": "forecast",
        "subtype": "earnings",
        "title": "英伟达财报",
        "event_date": "2026-06-03",
        "remind_before_days": 3,
        "logic_tags": ["tag-test"],
        "related_stocks": ["300502"],
        "prediction": "超预期→光模块受益",
        "baseline": {},
        "created_at": "2026-05-27",
    }

    def test_add_forecast(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        s.add_forecast(self.SAMPLE_FCST)
        assert len(s.get_forecasts()) == 1
        assert s.get_forecasts()[0]['title'] == '英伟达财报'

    def test_get_forecasts_by_date_range(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        fcst = dict(self.SAMPLE_FCST)
        s.add_forecast(fcst)
        # Query around the date
        upcoming = s.get_forecasts(upcoming_days=30)
        assert len(upcoming) == 1
        # Far future should be empty
        upcoming_far = s.get_forecasts(upcoming_days=1)
        assert len(upcoming_far) == 0


# ═══════════════════════════════════════════════════
# persistence (atomic write)
# ═══════════════════════════════════════════════════

class TestPersistence:

    def test_data_survives_reload(self, store_path):
        from backend.core.logic_tracking_store import LogicTrackingStore
        s1 = LogicTrackingStore(store_path)
        s1.add_tag(SAMPLE_TAG)
        # 重新加载
        s2 = LogicTrackingStore(store_path)
        assert len(s2.get_tags()) == 1
        assert s2.get_tag('tag-test')['name'] == '测试逻辑'

    def test_no_tmp_file_leftover(self, store_path):
        """原子写入后不能残留 .tmp 文件"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        s = LogicTrackingStore(store_path)
        s.add_tag(SAMPLE_TAG)
        tmp_files = [f for f in os.listdir(os.path.dirname(store_path)) if f.endswith('.tmp')]
        assert len(tmp_files) == 0

    def test_corrupted_file_initializes_empty(self, store_path):
        """文件损坏时自动重置为空"""
        from backend.core.logic_tracking_store import LogicTrackingStore
        with open(store_path, 'w') as f:
            f.write('{not json')
        s = LogicTrackingStore(store_path)
        data = s.get_all()
        assert data['tags'] == []
        assert data['entries'] == []
