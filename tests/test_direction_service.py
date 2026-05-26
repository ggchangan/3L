"""方向管理系统测试（独立 directions.json + direction_service）

覆盖当前 direction_service.py 的完整 CRUD + 启用管理
使用临时文件，不依赖真实数据
"""
import pytest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def ds(monkeypatch, tmp_path):
    """加载 direction_service 并指向临时文件"""
    from backend.services import direction_service as mod
    dir_path = tmp_path / "directions.json"
    monkeypatch.setattr(mod, 'DIRECTIONS_FILE', str(dir_path))
    # 初始化空数据
    mod._save({'all': [], 'active': [], 'suggestions': {}})
    return mod


@pytest.fixture
def ds_sample(monkeypatch, tmp_path):
    """预填充 4 个方向（2 个启用）"""
    from backend.services import direction_service as mod
    dir_path = tmp_path / "directions.json"
    monkeypatch.setattr(mod, 'DIRECTIONS_FILE', str(dir_path))
    mod._save({
        'all': ['半导体', '算力', '机器人', '新能源'],
        'active': ['半导体', '算力'],
        'suggestions': {},
    })
    return mod


# ═══════════════════════════════════════════════════════════════════
# get_all / get_active
# ═══════════════════════════════════════════════════════════════════

def test_get_all_empty(ds):
    """空文件返回空字典"""
    assert ds.get_all() == {}


def test_get_active_empty(ds):
    """空文件返回空列表"""
    assert ds.get_active() == []


def test_get_all_sample(ds_sample):
    """返回所有方向及其启用状态 dict"""
    data = ds_sample.get_all()
    assert data == {
        '半导体': True,
        '算力': True,
        '机器人': False,
        '新能源': False,
    }


def test_get_active_sample(ds_sample):
    """只返回已启用方向"""
    active = ds_sample.get_active()
    assert sorted(active) == ['半导体', '算力']


# ═══════════════════════════════════════════════════════════════════
# add
# ═══════════════════════════════════════════════════════════════════

def test_add_new(ds):
    """添加新方向，默认启用"""
    result = ds.add('AI应用')
    assert result['success'] is True
    assert ds.get_all()['AI应用'] is True


def test_add_duplicate_fails(ds_sample):
    """重复添加应失败"""
    result = ds_sample.add('半导体')
    assert result['success'] is False
    assert '已存在' in result.get('error', '')


def test_add_empty_name_fails(ds):
    """空名称应失败"""
    result = ds.add('   ')
    assert result['success'] is False


def test_add_reserved_names_fails(ds):
    """不能添加系统保留方向"""
    for name in ('全部', '其他'):
        result = ds.add(name)
        assert result['success'] is False


def test_add_auto_activates(ds):
    """新方向自动加入 active 列表"""
    ds.add('机器人')
    assert '机器人' in ds.get_active()


# ═══════════════════════════════════════════════════════════════════
# remove
# ═══════════════════════════════════════════════════════════════════

def test_remove_existing(ds_sample):
    """删除已存在方向"""
    result = ds_sample.remove('机器人')
    assert result['success'] is True
    assert '机器人' not in ds_sample.get_all()


def test_remove_also_removes_from_active(ds_sample):
    """删除时应从 active 中移除"""
    ds_sample.remove('半导体')
    assert '半导体' not in ds_sample.get_active()


def test_remove_nonexistent_fails(ds):
    """删除不存在的方向应失败"""
    result = ds.remove('不存在的方向')
    assert result['success'] is False


def test_remove_reserved_fails(ds):
    """不能删除 '其他'"""
    ds.add('其他')
    result = ds.remove('其他')
    assert result['success'] is False


# ═══════════════════════════════════════════════════════════════════
# set_active（启用/禁用）
# ═══════════════════════════════════════════════════════════════════

def test_enable_direction(ds_sample):
    """启用已禁用的方向"""
    ds_sample.set_active('机器人', True)
    assert '机器人' in ds_sample.get_active()


def test_disable_direction(ds_sample):
    """禁用已启用的方向"""
    ds_sample.set_active('半导体', False)
    assert '半导体' not in ds_sample.get_active()


def test_set_active_nonexistent_fails(ds):
    """操作不存在的方向应失败"""
    result = ds.set_active('不存在', True)
    assert result['success'] is False


def test_enable_already_enabled_is_idempotent(ds_sample):
    """重复启用不影响已有数据"""
    ds_sample.set_active('半导体', True)
    assert ds_sample.get_active() == ['半导体', '算力']


def test_disable_already_disabled_is_idempotent(ds_sample):
    """重复禁用不影响已有数据"""
    ds_sample.set_active('机器人', False)
    assert '机器人' not in ds_sample.get_active()


# ═══════════════════════════════════════════════════════════════════
# get_suggestions
# ═══════════════════════════════════════════════════════════════════

def test_get_suggestions_cached(ds):
    """已缓存的建议直接返回"""
    ds._save({'all': [], 'active': [], 'suggestions': {'custom': ['测试']}})
    sug = ds.get_suggestions()
    assert sug == {'custom': ['测试']}


def test_get_suggestions_custom(ds):
    """自定义建议包含预期项"""
    sug = ds.get_suggestions()
    assert 'custom' in sug
    assert '北交所' in sug['custom']
    assert '科创板' in sug['custom']
