"""
TDD: 方向管理系统 — 第1轮测试

测试方向数据的 CRUD + 启用状态管理
使用临时文件，不依赖真实数据
"""
import pytest
import json
import os
import sys
import tempfile

sys.path.insert(0, '/home/ubuntu/3l-server')

# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def empty_dir_path():
    """空的方向文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({"all": [], "active": []}, f)
        path = f.name
    yield path
    os.unlink(path)

@pytest.fixture
def sample_dir_path():
    """有数据的方向文件"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump({
            "all": ["半导体", "算力", "机器人", "新能源"],
            "active": ["半导体", "算力"]
        }, f)
        path = f.name
    yield path
    os.unlink(path)

# ═══════════════════════════════════════════════════════════════════
# Tests (RED phase — functions don't exist yet)
# ═══════════════════════════════════════════════════════════════════

def test_load_empty_directions(empty_dir_path):
    """空文件应返回空列表"""
    from services.direction_service import load_directions
    data = load_directions(empty_dir_path)
    assert data == {"all": [], "active": []}

def test_load_sample_directions(sample_dir_path):
    """正常文件应返回完整数据"""
    from services.direction_service import load_directions
    data = load_directions(sample_dir_path)
    assert data["all"] == ["半导体", "算力", "机器人", "新能源"]
    assert data["active"] == ["半导体", "算力"]

def test_add_direction(sample_dir_path):
    """添加新方向"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, add=["AI应用"])
    assert "AI应用" in data["all"]
    assert len(data["all"]) == 5

def test_add_duplicate_direction(sample_dir_path):
    """添加已存在的方向不应重复"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, add=["半导体"])
    assert data["all"].count("半导体") == 1

def test_remove_direction(sample_dir_path):
    """删除方向"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, remove=["机器人"])
    assert "机器人" not in data["all"]
    assert len(data["all"]) == 3

def test_remove_nonexistent_direction(sample_dir_path):
    """删除不存在的方向不应报错"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, remove=["不存在"])
    assert len(data["all"]) == 4

def test_set_active_directions(sample_dir_path):
    """设置启用的方向"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, set_active=["半导体", "机器人"])
    assert data["active"] == ["半导体", "机器人"]

def test_get_active_directions(sample_dir_path):
    """获取启用的方向"""
    from services.direction_service import get_active_directions
    active = get_active_directions(sample_dir_path)
    assert active == ["半导体", "算力"]

def test_is_direction_active(sample_dir_path):
    """判断方向是否启用"""
    from services.direction_service import is_direction_active
    assert is_direction_active("半导体", sample_dir_path) is True
    assert is_direction_active("机器人", sample_dir_path) is False

def test_add_new_auto_activates(sample_dir_path):
    """新建方向应自动加入active列表"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, add=["AI应用"])
    assert "AI应用" in data["active"]

def test_remove_also_removes_from_active(sample_dir_path):
    """删除方向时也要从active里移除"""
    from services.direction_service import load_directions, save_directions
    data = load_directions(sample_dir_path)
    data = save_directions(sample_dir_path, data, remove=["算力"])
    assert "算力" not in data["active"]

def test_stock_reassignment_on_dir_removal(sample_dir_path):
    """删除方向后，该方向的股票应归到'其他'"""
    from services.direction_service import reassign_stocks_on_remove
    # 有3只股票: 半导体2只, 算力1只
    stocks = [
        {"code": "001", "direction": "半导体"},
        {"code": "002", "direction": "半导体"},
        {"code": "003", "direction": "算力"},
    ]
    updated = reassign_stocks_on_remove(stocks, "算力")
    assert updated[2]["direction"] == "其他"
    # 半导体方向的股票不受影响
    assert updated[0]["direction"] == "半导体"
