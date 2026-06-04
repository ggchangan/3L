"""方向管理服务 — 单元测试（V2 分层 + 概念绑定）"""
import sys, os, json, tempfile, pytest
import importlib

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir():
    """为每个测试创建临时数据目录，避免污染真实数据"""
    with tempfile.TemporaryDirectory() as td:
        old_environ = os.environ.copy()
        os.environ['DATA_DIR'] = td
        # 不设 DIRECTIONS_PATH 让模块用 DATA_DIR 拼接
        yield td
        os.environ.clear()
        os.environ.update(old_environ)


@pytest.fixture
def ds(tmp_data_dir):
    """返回 direction_service 模块（通过 importlib.reload 确保每次干净导入）"""
    # 先确保基础包在 sys.modules 中
    import backend.services.direction_service as ds_mod
    ds_mod = importlib.reload(ds_mod)
    # 确保文件路径在临时目录
    ds_mod.DIRECTIONS_FILE = os.path.join(tmp_data_dir, 'directions.json')
    ds_mod.DATA_DIR = tmp_data_dir
    ds_mod.CONCEPT_LIST_PATH = os.path.join(tmp_data_dir, 'map', 'concept_list.json')
    return ds_mod


def _write_v1_data(tmpdir, data):
    """写入旧版本 V1 格式数据（绕过 _load 直接写文件）"""
    path = os.path.join(tmpdir, 'directions.json')
    with open(path, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════
# 基础 / 内部工具
# ═══════════════════════════════════════════════════════════

class TestParseAndFormatDirection:

    def test_parse_standard(self, ds):
        cat, sub = ds.parse_direction("科技.半导体")
        assert cat == "科技"
        assert sub == "半导体"

    def test_parse_with_dots_in_sub(self, ds):
        cat, sub = ds.parse_direction("科技.半.导.体")
        assert cat == "科技"
        assert sub == "半.导.体"

    def test_parse_no_dot(self, ds):
        cat, sub = ds.parse_direction("半导体")
        assert cat == ""
        assert sub == "半导体"

    def test_parse_empty(self, ds):
        cat, sub = ds.parse_direction("")
        assert cat == ""
        assert sub == ""

    def test_format_standard(self, ds):
        assert ds.format_direction("科技", "半导体") == "科技.半导体"

    def test_format_no_category(self, ds):
        assert ds.format_direction("", "半导体") == "半导体"

    def test_roundtrip(self, ds):
        cases = ["科技.半导体", "医药.创新药", "算力", "消费电子.AI手机"]
        for c in cases:
            cat, sub = ds.parse_direction(c)
            assert ds.format_direction(cat, sub) == c


# ═══════════════════════════════════════════════════════════
# CATEGORY 操作
# ═══════════════════════════════════════════════════════════

class TestCategory:

    def test_add_category_creates_file(self, ds, tmp_data_dir):
        result = ds.add_category("科技")
        assert result['success'] is True
        assert os.path.isfile(os.path.join(tmp_data_dir, 'directions.json'))

    def test_add_category_duplicate(self, ds):
        ds.add_category("科技")
        result = ds.add_category("科技")
        assert result['success'] is False
        assert '已存在' in result.get('error', '')

    def test_add_category_empty(self, ds):
        result = ds.add_category("")
        assert result['success'] is False

    def test_get_categories_empty(self, ds):
        cats = ds.get_categories()
        assert cats == {}

    def test_get_categories_after_add(self, ds):
        ds.add_category("科技")
        ds.add_category("医药")
        cats = ds.get_categories()
        assert "科技" in cats
        assert "医药" in cats
        assert cats["科技"]["enabled"] is True
        # order 从 0 开始
        assert cats["科技"]["order"] == 0
        assert cats["医药"]["order"] == 1

    def test_remove_category(self, ds):
        ds.add_category("科技")
        ds.add_category("医药")
        result = ds.remove_category("科技")
        assert result['success'] is True
        cats = ds.get_categories()
        assert "科技" not in cats
        assert "医药" in cats

    def test_remove_category_not_found(self, ds):
        result = ds.remove_category("不存在")
        assert result['success'] is False

    def test_remove_category_with_sub_directions(self, ds):
        """删除分类时，该分类下的所有细分方向也应删除"""
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.add_category("医药")
        ds.add_sub_direction("医药", "创新药")
        result = ds.remove_category("科技")
        assert result['success'] is True
        subs = ds.get_sub_directions()
        assert "科技.半导体" not in subs
        assert "科技.算力" not in subs
        assert "医药.创新药" in subs

    def test_set_category_enabled(self, ds):
        ds.add_category("科技")
        r = ds.set_category_enabled("科技", False)
        assert r['success'] is True
        cats = ds.get_categories()
        assert cats["科技"]["enabled"] is False

    def test_set_category_enabled_not_found(self, ds):
        r = ds.set_category_enabled("不存在", False)
        assert r['success'] is False

    def test_rename_category(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.rename_category("科技", "科学技术")
        assert r['success'] is True
        cats = ds.get_categories()
        assert "科学技术" in cats
        assert "科技" not in cats
        subs = ds.get_sub_directions()
        assert "科学技术.半导体" in subs
        assert "科技.半导体" not in subs

    def test_rename_category_not_found(self, ds):
        r = ds.rename_category("不存在", "新名字")
        assert r['success'] is False

    def test_rename_category_to_existing(self, ds):
        """重命名到已存在的分类名应失败"""
        ds.add_category("科技")
        ds.add_category("医药")
        r = ds.rename_category("科技", "医药")
        assert r['success'] is False
        assert '已存在' in r.get('error', '')

    def test_rename_category_empty_new_name(self, ds):
        """新名称为空时应失败"""
        ds.add_category("科技")
        r = ds.rename_category("科技", "")
        assert r['success'] is False

    def test_rename_category_updates_watchlist(self, ds, tmp_data_dir):
        """重命名分类应同步更新 watchlist 中的引用"""
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        # 写 watchlist
        wl_path = os.path.join(tmp_data_dir, 'watchlist.json')
        with open(wl_path, 'w') as f:
            json.dump({"stocks": [
                {"code": "000001", "name": "测试", "directions": ["科技.半导体"]}
            ]}, f)
        r = ds.rename_category("科技", "科学技术")
        assert r['success'] is True
        with open(wl_path, 'r') as f:
            wl = json.load(f)
        assert "科学技术.半导体" in wl['stocks'][0]['directions']
        assert "科技.半导体" not in wl['stocks'][0]['directions']

    def test_reorder_categories(self, ds):
        ds.add_category("医药")
        ds.add_category("科技")
        ds.add_category("消费")
        r = ds.reorder_categories(["科技", "消费", "医药"])
        assert r['success'] is True
        cats = ds.get_categories()
        assert cats["科技"]["order"] == 0
        assert cats["消费"]["order"] == 1
        assert cats["医药"]["order"] == 2


# ═══════════════════════════════════════════════════════════
# SUB_DIRECTION 操作
# ═══════════════════════════════════════════════════════════

class TestSubDirection:

    def test_add_sub_direction(self, ds):
        ds.add_category("科技")
        r = ds.add_sub_direction("科技", "半导体")
        assert r['success'] is True
        subs = ds.get_sub_directions()
        assert "科技.半导体" in subs
        assert subs["科技.半导体"]["category"] == "科技"
        assert subs["科技.半导体"]["enabled"] is True

    def test_add_sub_direction_auto_create_category(self, ds):
        """当分类不存在时自动创建"""
        r = ds.add_sub_direction("科技", "半导体", auto_create_category=True)
        assert r['success'] is True
        cats = ds.get_categories()
        assert "科技" in cats

    def test_add_sub_direction_no_auto_create(self, ds):
        """当分类不存在且不自动创建时失败"""
        r = ds.add_sub_direction("科技", "半导体", auto_create_category=False)
        assert r['success'] is False

    def test_add_sub_direction_duplicate(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.add_sub_direction("科技", "半导体")
        assert r['success'] is False
        assert '已存在' in r.get('error', '')

    def test_remove_sub_direction(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        r = ds.remove_sub_direction("科技", "半导体")
        assert r['success'] is True
        subs = ds.get_sub_directions()
        assert "科技.半导体" not in subs
        assert "科技.算力" in subs

    def test_remove_sub_direction_not_found(self, ds):
        r = ds.remove_sub_direction("科技", "不存在")
        assert r['success'] is False

    def test_get_sub_directions_filter_by_category(self, ds):
        ds.add_category("科技")
        ds.add_category("医药")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.add_sub_direction("医药", "创新药")
        subs = ds.get_sub_directions(category="科技")
        assert len(subs) == 2
        assert "科技.半导体" in subs
        assert "科技.算力" in subs
        assert "医药.创新药" not in subs

    def test_get_sub_directions_all(self, ds):
        ds.add_category("科技")
        ds.add_category("医药")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("医药", "创新药")
        subs = ds.get_sub_directions()  # no filter
        assert len(subs) == 2

    def test_set_sub_direction_enabled(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.set_sub_direction_enabled("科技", "半导体", False)
        assert r['success'] is True
        subs = ds.get_sub_directions()
        assert subs["科技.半导体"]["enabled"] is False

    def test_rename_sub_direction(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.rename_sub_direction("科技", "半导体", "先进封装")
        assert r['success'] is True
        subs = ds.get_sub_directions()
        assert "科技.先进封装" in subs
        assert "科技.半导体" not in subs

    def test_rename_sub_direction_not_found(self, ds):
        r = ds.rename_sub_direction("科技", "不存在", "新名字")
        assert r['success'] is False

    def test_rename_sub_direction_empty_new_name(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.rename_sub_direction("科技", "半导体", "")
        assert r['success'] is False

    def test_rename_sub_direction_duplicate(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "先进封装")
        r = ds.rename_sub_direction("科技", "半导体", "先进封装")
        assert r['success'] is False
        assert '已存在' in r.get('error', '')

    def test_move_sub_direction(self, ds):
        ds.add_category("科技")
        ds.add_category("医药")
        ds.add_sub_direction("科技", "半导体")
        r = ds.move_sub_direction("科技", "半导体", "医药")
        assert r['success'] is True
        subs = ds.get_sub_directions()
        assert "医药.半导体" in subs
        assert "科技.半导体" not in subs
        assert subs["医药.半导体"]["category"] == "医药"

    def test_move_sub_direction_auto_create_category(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.move_sub_direction("科技", "半导体", "新能源")
        assert r['success'] is True
        cats = ds.get_categories()
        assert "新能源" in cats
        assert "新能源.半导体" in ds.get_sub_directions()

    def test_move_sub_direction_same_category(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.move_sub_direction("科技", "半导体", "科技")
        assert r['success'] is False
        assert '已经在当前分类中' in r.get('error', '')

    def test_move_sub_direction_not_found(self, ds):
        r = ds.move_sub_direction("科技", "不存在", "医药")
        assert r['success'] is False

    def test_move_sub_direction_updates_watchlist(self, ds, tmp_data_dir):
        ds.add_category("科技")
        ds.add_category("医药")
        ds.add_sub_direction("科技", "半导体")
        wl_path = os.path.join(tmp_data_dir, 'watchlist.json')
        with open(wl_path, 'w') as f:
            json.dump({"stocks": [
                {"code": "000001", "name": "测试", "directions": ["科技.半导体"]}
            ]}, f)
        r = ds.move_sub_direction("科技", "半导体", "医药")
        assert r['success'] is True
        with open(wl_path, 'r') as f:
            wl = json.load(f)
        assert "医药.半导体" in wl['stocks'][0]['directions']
        assert "科技.半导体" not in wl['stocks'][0]['directions']

    def test_reorder_sub_directions(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.add_sub_direction("科技", "AI")
        r = ds.reorder_sub_directions("科技", ["AI", "算力", "半导体"])
        assert r['success'] is True
        subs = ds.get_sub_directions(category="科技")
        assert subs["科技.AI"]["order"] == 0
        assert subs["科技.算力"]["order"] == 1
        assert subs["科技.半导体"]["order"] == 2


# ═══════════════════════════════════════════════════════════
# 概念绑定
# ═══════════════════════════════════════════════════════════

class TestConceptBinding:

    def test_bind_concept(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.bind_concept("科技", "半导体", "301085", "芯片概念")
        assert r['success'] is True
        bound = ds.get_bound_concepts("科技", "半导体")
        assert "301085" in bound
        assert bound["301085"] == "芯片概念"

    def test_bind_multiple_concepts(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.bind_concept("科技", "半导体", "301085", "芯片概念")
        ds.bind_concept("科技", "半导体", "307940", "存储芯片")
        bound = ds.get_bound_concepts("科技", "半导体")
        assert len(bound) == 2

    def test_unbind_concept(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.bind_concept("科技", "半导体", "301085", "芯片概念")
        ds.bind_concept("科技", "半导体", "307940", "存储芯片")
        r = ds.unbind_concept("科技", "半导体", "301085")
        assert r['success'] is True
        bound = ds.get_bound_concepts("科技", "半导体")
        assert "301085" not in bound
        assert "307940" in bound

    def test_unbind_concept_not_found(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        r = ds.unbind_concept("科技", "半导体", "999999")
        assert r['success'] is False

    def test_get_bound_concepts_empty(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        bound = ds.get_bound_concepts("科技", "半导体")
        assert bound == {}

    def test_search_concepts_returns_results(self, ds):
        """搜索概念 - 使用 mock 概念数据写入临时目录"""
        # 写模拟概念数据到临时目录
        concept_path = os.path.join(ds.DATA_DIR, 'map', 'concept_list.json')
        os.makedirs(os.path.dirname(concept_path), exist_ok=True)
        with open(concept_path, 'w') as f:
            json.dump({
                "301085": {"name": "芯片概念", "stock_count": 50},
                "307940": {"name": "存储芯片", "stock_count": 30},
                "301459": {"name": "华为概念", "stock_count": 100},
                "308969": {"name": "超超临界发电", "stock_count": 48},
            }, f)
        results = ds.search_concepts("芯片")
        assert len(results) > 0
        assert "301085" in results
        assert "307940" in results
        assert results["301085"]["name"] == "芯片概念"
        assert results["301085"]["stock_count"] == 50

    def test_search_concepts_empty_query(self, ds):
        results = ds.search_concepts("")
        assert results == {}

    def test_search_concepts_no_match(self, ds):
        results = ds.search_concepts("ZZZZNOTEXIST12345")
        assert results == {}

    def test_search_concepts_pinyin_match(self, ds):
        """拼音首字母匹配"""
        concept_path = os.path.join(ds.DATA_DIR, 'map', 'concept_list.json')
        os.makedirs(os.path.dirname(concept_path), exist_ok=True)
        with open(concept_path, 'w') as f:
            json.dump({
                "301085": {"name": "芯片概念", "stock_count": 50},
                "307940": {"name": "存储芯片", "stock_count": 30},
                "301459": {"name": "华为概念", "stock_count": 100},
                "308969": {"name": "超超临界发电", "stock_count": 48},
            }, f)
        # "芯片概念" -> "xpgn"
        results = ds.search_concepts("xpgn")
        assert "301085" in results
        assert results["301085"]["name"] == "芯片概念"
        # "华为概念" -> "hwgn"
        results2 = ds.search_concepts("hwgn")
        assert "301459" in results2
        # "超超临界发电" -> "ccljfd...
        results3 = ds.search_concepts("cclj")
        assert "308969" in results3
        # short query (<2 chars) should not match pinyin
        results4 = ds.search_concepts("x")
        assert "301085" not in results4


# ═══════════════════════════════════════════════════════════
# 兼容性：旧接口
# ═══════════════════════════════════════════════════════════

class TestBackwardCompatibility:

    def test_get_active_returns_enabled_sub_direction_names(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.add_sub_direction("科技", "AI")
        ds.set_sub_direction_enabled("科技", "AI", False)
        active = ds.get_active()
        assert "科技.半导体" in active
        assert "科技.算力" in active
        assert "科技.AI" not in active

    def test_get_all_ordered_returns_all_sub_direction_names(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        all_ordered = ds.get_all_ordered()
        assert len(all_ordered) == 2

    def test_get_all_returns_name_active_dict(self, ds):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.set_sub_direction_enabled("科技", "算力", False)
        all_d = ds.get_all()
        assert "科技.半导体" in all_d
        assert "科技.算力" in all_d
        assert all_d["科技.半导体"] is True
        assert all_d["科技.算力"] is False

    def test_reorder_compat(self, ds):
        """旧 reorder(names) 按名称重新排序所有细分方向"""
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        ds.add_sub_direction("科技", "AI")
        r = ds.reorder(["科技.AI", "科技.算力", "科技.半导体"])
        assert r['success'] is True
        all_o = ds.get_all_ordered()
        assert all_o[0] == "科技.AI"
        assert all_o[1] == "科技.算力"
        assert all_o[2] == "科技.半导体"

    def test_suggestions_compat(self, ds):
        """旧 get_suggestions() 返回与 V1 相同格式"""
        sugg = ds.get_suggestions()
        assert 'industry' in sugg
        assert 'concept' in sugg
        assert 'custom' in sugg

    def test_core_stocks_compat(self, ds):
        """旧 get_core_stocks() 返回与 V1 相同格式"""
        # 直接写文件
        with open(ds.DIRECTIONS_FILE, 'w') as f:
            json.dump({
                "version": 2,
                "categories": {},
                "sub_directions": {},
                "suggestions": {},
                "core": {"002371": {"name": "北方华创", "deviation": 6}}
            }, f)
        core = ds.get_core_stocks()
        assert "002371" in core
        assert core["002371"]["name"] == "北方华创"


# ═══════════════════════════════════════════════════════════
# 迁移
# ═══════════════════════════════════════════════════════════

class TestMigration:

    def test_migrate_v1_to_v2(self, ds, tmp_data_dir):
        """从 V1 平的格式迁移到 V2 层级格式"""
        # 直接写 V1 文件，绕过 _load() 的自动升级
        _write_v1_data(tmp_data_dir, {
            "all": ["半导体", "算力", "创新药"],
            "active": ["半导体", "算力"],
            "suggestions": {"industry": [], "concept": [], "custom": []},
            "core": {"002371": {"name": "北方华创", "deviation": 6}}
        })
        result = ds.migrate_v1_to_v2()
        assert result['success'] is True
        assert result['migrated'] == 3
        # 验证格式已升级
        data = ds._load()
        assert data.get('version') == 2
        assert 'categories' in data
        assert 'sub_directions' in data
        # 所有旧方向应归入 "未分类" 分类
        assert "未分类" in data['categories']
        # core 和 suggestions 应该保留
        assert 'core' in data
        assert 'suggestions' in data

    def test_migrate_v1_to_v2_idempotent(self, ds, tmp_data_dir):
        """已升级的版本不应重复迁移"""
        _write_v1_data(tmp_data_dir, {
            "all": ["半导体", "算力"],
            "active": ["半导体", "算力"],
            "suggestions": {},
            "core": {}
        })
        result1 = ds.migrate_v1_to_v2()
        assert result1['success'] is True
        result2 = ds.migrate_v1_to_v2()
        assert result2['success'] is False
        assert '已是最新' in result2.get('error', '')

    def test_migrate_from_watchlist_compat(self, ds, tmp_data_dir):
        """旧 migrate_from_watchlist 仍然可用"""
        wl_path = os.path.join(tmp_data_dir, 'watchlist.json')
        with open(wl_path, 'w') as f:
            json.dump({
                "stocks": [
                    {"code": "000001", "direction": "半导体"},
                    {"code": "000002", "direction": "算力"},
                    {"code": "000003", "direction": "半导体"},
                    {"code": "000004", "direction": "创新药"},
                ]
            }, f)
        result = ds.migrate_from_watchlist(wl_path)
        assert result['success'] is True
        assert result['migrated'] == 3


# ═══════════════════════════════════════════════════════════
# 边界情况 / 异常
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_load_empty_file(self, ds, tmp_data_dir):
        """空文件应返回默认结构"""
        with open(os.path.join(tmp_data_dir, 'directions.json'), 'w') as f:
            f.write('')
        data = ds._load()
        assert 'categories' in data
        assert 'sub_directions' in data
        assert data.get('version') == 2

    def test_load_corrupted_json(self, ds, tmp_data_dir):
        """损坏的 JSON 应返回默认结构而不崩溃"""
        with open(os.path.join(tmp_data_dir, 'directions.json'), 'w') as f:
            f.write('{invalid json!!!}')
        data = ds._load()
        assert 'categories' in data
        assert 'sub_directions' in data

    def test_no_categories_still_works(self, ds):
        """没有分类时，所有基本操作应正常工作"""
        assert ds.get_categories() == {}
        assert ds.get_sub_directions() == {}
        assert ds.get_active() == []
        assert ds.get_all_ordered() == []

    def test_bind_concept_to_nonexistent_subdir(self, ds):
        r = ds.bind_concept("科技", "不存在", "301085", "芯片概念")
        assert r['success'] is False

    def test_v1_format_auto_upgrade_on_load(self, ds, tmp_data_dir):
        """旧 V1 格式应在 _load 时自动升级"""
        _write_v1_data(tmp_data_dir, {
            "all": ["半导体", "算力"],
            "active": ["半导体"],
            "suggestions": {"industry": [], "concept": [], "custom": []},
        })
        # _load 自动升级
        data = ds._load()
        assert data.get('version') == 2
        subs = ds.get_sub_directions()
        assert len(subs) == 2

    def test_update_watchlist_on_key_change_both_formats(self, ds, tmp_data_dir):
        """_update_watchlist_on_key_change 应同时更新新格式(directions数组)和旧格式(direction字符串)"""
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        wl_path = os.path.join(tmp_data_dir, 'watchlist.json')
        with open(wl_path, 'w') as f:
            json.dump({"stocks": [
                {"code": "000001", "name": "新格式", "directions": ["科技.半导体"]},
                {"code": "000002", "name": "旧格式", "direction": "科技.半导体"},
                {"code": "000003", "name": "无关股票", "directions": ["科技.算力"]},
            ]}, f)
        ds._update_watchlist_on_key_change("科技.半导体", "科技.先进封装")
        with open(wl_path, 'r') as f:
            wl = json.load(f)
        assert "科技.先进封装" in wl['stocks'][0]['directions']
        assert "科技.半导体" not in wl['stocks'][0]['directions']
        assert wl['stocks'][1]['direction'] == "科技.先进封装"
        assert wl['stocks'][2]['directions'] == ["科技.算力"]  # unchanged

    def test_update_watchlist_on_key_change_no_file(self, ds):
        """watchlist.json 不存在时应静默返回"""
        ds._update_watchlist_on_key_change("old", "new")  # should not raise

    def test_update_watchlist_on_key_change_same_key(self, ds, tmp_data_dir):
        """old_key == new_key 时应直接返回"""
        wl_path = os.path.join(tmp_data_dir, 'watchlist.json')
        with open(wl_path, 'w') as f:
            json.dump({"stocks": [{"code": "000001", "directions": ["科技.半导体"]}]}, f)
        ds._update_watchlist_on_key_change("科技.半导体", "科技.半导体")
        with open(wl_path, 'r') as f:
            wl = json.load(f)
        assert wl['stocks'][0]['directions'] == ["科技.半导体"]

    def test_reorder_sub_directions_with_full_keys(self, ds):
        """reorder_sub_directions 支持完整 key 列表"""
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        ds.add_sub_direction("科技", "算力")
        r = ds.reorder_sub_directions("科技", ["科技.算力", "科技.半导体"])
        assert r['success'] is True
        assert ds.get_sub_directions(category="科技")["科技.算力"]["order"] == 0
        assert ds.get_sub_directions(category="科技")["科技.半导体"]["order"] == 1
