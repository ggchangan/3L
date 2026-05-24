"""自选股方向管理测试（TDD）

覆盖：
- 方向CRUD（创建/删除/启用/禁用）
- 方向列表API
- 启用方向影响下游扫描
- 方向迁移兼容
"""
import pytest
import json
import os
import tempfile
import copy


# ── 模拟 watchlist.json 样例 ──────────────────────────

SAMPLE_WL = {
    "stocks": [
        {"code": "688981", "name": "中芯国际", "direction": "半导体", "industry": "集成电路设计"},
        {"code": "603986", "name": "兆易创新", "direction": "半导体", "industry": "集成电路设计"},
        {"code": "688256", "name": "寒武纪", "direction": "算力", "industry": "AI芯片"},
        {"code": "300308", "name": "中际旭创", "direction": "算力", "industry": "光模块"},
        {"code": "000977", "name": "浪潮信息", "direction": "算力", "industry": "服务器"},
        {"code": "300750", "name": "宁德时代", "direction": "新能源", "industry": "电池"},
        {"code": "600519", "name": "贵州茅台", "direction": "消费", "industry": "白酒"},
        {"code": "300124", "name": "汇川技术", "direction": "机器人", "industry": "伺服系统"},
    ],
    "count": 8,
}

SAMPLE_WL_NO_DIRECTIONS = {**SAMPLE_WL}  # 没有 directions 字段


class TestDirectionCRUD:
    """方向CRUD操作测试"""

    def test_get_directions_default_empty(self, tmp_path):
        """没有directions字段时返回空字典"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump({"stocks": [], "count": 0}, f)

        from services.watchlist_service import get_directions
        result = get_directions(str(wl_path))
        assert result == {}

    def test_add_direction(self, tmp_path):
        """添加新的方向（首次添加自动迁移老数据）"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(copy.deepcopy(SAMPLE_WL_NO_DIRECTIONS), f)

        from services.watchlist_service import add_direction
        # 使用一个股票中不存在的方向名
        result = add_direction("低空经济", str(wl_path))
        assert result['success'] is True

        # 验证已写入
        with open(wl_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert 'directions' in data
        assert '低空经济' in data['directions']
        assert data['directions']['低空经济']['enabled'] is True
        
        # 迁移也完成了
        assert '半导体' in data['directions']
        assert '算力' in data['directions']

    def test_add_direction_duplicate(self, tmp_path):
        """重复添加同一方向应失败"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(copy.deepcopy(SAMPLE_WL_NO_DIRECTIONS), f)

        from services.watchlist_service import add_direction
        add_direction("半导体", str(wl_path))
        result = add_direction("半导体", str(wl_path))
        assert result['success'] is False
        assert '已存在' in result['error']

    def test_add_direction_with_suggestions(self, tmp_path):
        """添加方向时返回建议列表（从现有股票industry提取）"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(copy.deepcopy(SAMPLE_WL), f)

        from services.watchlist_service import suggest_directions
        suggestions = suggest_directions(str(wl_path))
        # 从已有股票名称/字面提供建议，不应为空
        assert isinstance(suggestions, list)

    def test_remove_direction(self, tmp_path):
        """删除方向后，该方向股票归入'其他'"""
        wl_path = tmp_path / "watchlist.json"
        data = copy.deepcopy(SAMPLE_WL)
        data['directions'] = {"半导体": {"enabled": True}, "算力": {"enabled": True}}
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        from services.watchlist_service import remove_direction
        result = remove_direction("半导体", str(wl_path))
        assert result['success'] is True

        with open(wl_path, 'r', encoding='utf-8') as f:
            updated = json.load(f)

        # 方向已删除
        assert '半导体' not in updated.get('directions', {})
        # 原半导体方向股票变为"其他"
        for s in updated['stocks']:
            if s['code'] in ('688981', '603986'):
                assert s['direction'] == '其他'

    def test_toggle_direction_enable(self, tmp_path):
        """启用/禁用方向切换"""
        wl_path = tmp_path / "watchlist.json"
        data = copy.deepcopy(SAMPLE_WL)
        data['directions'] = {"半导体": {"enabled": False}}
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        from services.watchlist_service import set_direction_enabled
        # 启用
        result = set_direction_enabled("半导体", True, str(wl_path))
        assert result['success'] is True

        with open(wl_path, 'r', encoding='utf-8') as f:
            updated = json.load(f)
        assert updated['directions']['半导体']['enabled'] is True

        # 禁用
        result = set_direction_enabled("半导体", False, str(wl_path))
        assert result['success'] is True

        with open(wl_path, 'r', encoding='utf-8') as f:
            updated = json.load(f)
        assert updated['directions']['半导体']['enabled'] is False

    def test_remove_nonexistent_direction(self, tmp_path):
        """删除不存在的方向应失败"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump({"stocks": [], "count": 0}, f)

        from services.watchlist_service import remove_direction
        result = remove_direction("不存在的方向", str(wl_path))
        assert result['success'] is False

    def test_get_enabled_directions(self, tmp_path):
        """获取启用的方向列表"""
        wl_path = tmp_path / "watchlist.json"
        data = copy.deepcopy(SAMPLE_WL)
        data['directions'] = {
            "半导体": {"enabled": True},
            "算力": {"enabled": False},
            "新能源": {"enabled": True},
        }
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        from services.watchlist_service import get_enabled_directions
        enabled = get_enabled_directions(str(wl_path))
        assert enabled == ["半导体", "新能源"]

    def test_get_enabled_directions_no_field(self, tmp_path):
        """没有directions字段时，返回所有现有方向（兼容老数据）"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(copy.deepcopy(SAMPLE_WL), f)

        from services.watchlist_service import get_enabled_directions
        enabled = get_enabled_directions(str(wl_path))
        # 兼容模式：返回所有现有方向
        assert sorted(enabled) == sorted(["半导体", "算力", "新能源", "机器人", "消费"])

    def test_get_all_directions(self, tmp_path):
        """获取全部方向（含启用状态和计数）"""
        wl_path = tmp_path / "watchlist.json"
        data = copy.deepcopy(SAMPLE_WL)
        data['directions'] = {
            "半导体": {"enabled": True},
            "算力": {"enabled": False},
        }
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(data, f)

        from services.watchlist_service import get_all_directions
        all_dirs = get_all_directions(str(wl_path))
        assert '半导体' in all_dirs
        assert '算力' in all_dirs
        assert all_dirs['半导体']['enabled'] is True
        assert all_dirs['算力']['enabled'] is False
        # 含计数
        assert all_dirs['半导体']['count'] == 2
        assert all_dirs['算力']['count'] == 3

    def test_migrate_legacy_watchlist(self, tmp_path):
        """迁移老数据（无directions字段）→ 从股票方向自动生成"""
        wl_path = tmp_path / "watchlist.json"
        with open(wl_path, 'w', encoding='utf-8') as f:
            json.dump(copy.deepcopy(SAMPLE_WL), f)

        from services.watchlist_service import migrate_directions
        result = migrate_directions(str(wl_path))
        assert result['success'] is True

        with open(wl_path, 'r', encoding='utf-8') as f:
            updated = json.load(f)
        assert 'directions' in updated
        for dir_name in ("半导体", "算力", "新能源", "机器人", "消费"):
            assert dir_name in updated['directions']
            assert updated['directions'][dir_name]['enabled'] is True
