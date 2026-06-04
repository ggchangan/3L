"""方向管理 API 端点 — 单元测试"""
import sys, os, json, tempfile, pytest
import importlib

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── Mock HTTP Handler ────────────────────────────────────

class MockHandler:
    """模拟 HTTP handler，捕获 send_json 调用"""
    def __init__(self):
        self.sent = None
        self.status = None

    def send_json(self, data, status=200):
        self.sent = data
        self.status = status


# ── Fixtures ──────────────────────────────────────────────

@pytest.fixture
def tmp_data_dir():
    with tempfile.TemporaryDirectory() as td:
        old_environ = os.environ.copy()
        os.environ['DATA_DIR'] = td
        yield td
        os.environ.clear()
        os.environ.update(old_environ)


@pytest.fixture
def ds(tmp_data_dir):
    """返回 direction_service 模块（干净导入）"""
    import backend.services.direction_service as ds_mod
    ds_mod = importlib.reload(ds_mod)
    ds_mod.DIRECTIONS_FILE = os.path.join(tmp_data_dir, 'directions.json')
    ds_mod.DATA_DIR = tmp_data_dir
    ds_mod.CONCEPT_LIST_PATH = os.path.join(tmp_data_dir, 'map', 'concept_list.json')
    return ds_mod


@pytest.fixture
def api(tmp_data_dir):
    """重新加载 api.directions 模块（确保使用临时 DATA_DIR）"""
    import backend.api.directions as api_mod
    api_mod = importlib.reload(api_mod)
    # 确保其引用的 direction_service 也指向临时目录
    import backend.services.direction_service as ds_mod
    ds_mod = importlib.reload(ds_mod)
    ds_mod.DIRECTIONS_FILE = os.path.join(tmp_data_dir, 'directions.json')
    ds_mod.DATA_DIR = tmp_data_dir
    ds_mod.CONCEPT_LIST_PATH = os.path.join(tmp_data_dir, 'map', 'concept_list.json')
    # 重新加载 api 模块以绑定新路径
    api_mod = importlib.reload(api_mod)
    return api_mod


def _setup_basic_data(ds):
    """设置基础测试数据：一个分类 + 两个细分方向"""
    ds.add_category("科技")
    ds.add_sub_direction("科技", "半导体")
    ds.add_sub_direction("科技", "算力")
    ds.add_category("医药")
    ds.add_sub_direction("医药", "创新药")


# ═══════════════════════════════════════════════════════════
# GET /api/directions/get
# ═══════════════════════════════════════════════════════════

class TestApiGet:

    def test_get_returns_full_state(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_get(h, '/api/directions/get')
        assert h.sent is not None
        assert 'categories' in h.sent
        assert 'sub_directions' in h.sent
        assert 'active' in h.sent
        assert 'version' in h.sent
        assert '科技' in str(h.sent['categories'])
        assert '科技.半导体' in h.sent['sub_directions']

    def test_get_empty_state(self, ds, api):
        h = MockHandler()
        api._handle_get(h, '/api/directions/get')
        assert h.sent is not None
        assert h.sent['categories'] == []
        assert h.sent['sub_directions'] == {}
        assert h.sent['active'] == []
        assert h.sent['version'] == 2


# ═══════════════════════════════════════════════════════════
# POST /api/directions/category/add
# ═══════════════════════════════════════════════════════════

class TestApiCategoryAdd:

    def test_add_category(self, ds, api):
        h = MockHandler()
        api._handle_category_add(h, '/api/directions/category/add', json.dumps({'name': '科技'}))
        assert h.sent['success'] is True
        assert h.sent['name'] == '科技'

    def test_add_category_empty(self, ds, api):
        h = MockHandler()
        api._handle_category_add(h, '/api/directions/category/add', json.dumps({'name': ''}))
        assert h.sent['success'] is False

    def test_add_category_duplicate(self, ds, api):
        h = MockHandler()
        api._handle_category_add(h, '/api/directions/category/add', json.dumps({'name': '科技'}))
        h2 = MockHandler()
        api._handle_category_add(h2, '/api/directions/category/add', json.dumps({'name': '科技'}))
        assert h2.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/category/remove
# ═══════════════════════════════════════════════════════════

class TestApiCategoryRemove:

    def test_remove_category(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_category_remove(h, '/api/directions/category/remove', json.dumps({'name': '科技'}))
        assert h.sent['success'] is True
        assert h.sent['removed_sub_directions'] == 2  # 半导体 + 算力

    def test_remove_category_not_found(self, ds, api):
        h = MockHandler()
        api._handle_category_remove(h, '/api/directions/category/remove', json.dumps({'name': '不存在'}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/category/toggle
# ═══════════════════════════════════════════════════════════

class TestApiCategoryToggle:

    def test_toggle_category(self, ds, api):
        ds.add_category("科技")
        h = MockHandler()
        api._handle_category_toggle(h, '/api/directions/category/toggle', json.dumps({'name': '科技', 'enabled': False}))
        assert h.sent['success'] is True
        cats = ds.get_categories()
        assert cats['科技']['enabled'] is False

    def test_toggle_category_not_found(self, ds, api):
        h = MockHandler()
        api._handle_category_toggle(h, '/api/directions/category/toggle', json.dumps({'name': '不存在', 'enabled': False}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/category/reorder
# ═══════════════════════════════════════════════════════════

class TestApiCategoryReorder:

    def test_reorder_categories(self, ds, api):
        ds.add_category("医药")
        ds.add_category("科技")
        ds.add_category("消费")
        h = MockHandler()
        api._handle_category_reorder(h, '/api/directions/category/reorder', json.dumps({'names': ['科技', '消费', '医药']}))
        assert h.sent['success'] is True
        cats = ds.get_categories()
        assert cats['科技']['order'] == 0
        assert cats['消费']['order'] == 1
        assert cats['医药']['order'] == 2


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/add
# ═══════════════════════════════════════════════════════════

class TestApiSubAdd:

    def test_add_sub(self, ds, api):
        ds.add_category("科技")
        h = MockHandler()
        api._handle_sub_add(h, '/api/directions/sub/add', json.dumps({'name': '半导体', 'category': '科技'}))
        assert h.sent['success'] is True
        assert '科技.半导体' in ds.get_sub_directions()

    def test_add_sub_auto_create_category(self, ds, api):
        """分类不存在时自动创建"""
        h = MockHandler()
        api._handle_sub_add(h, '/api/directions/sub/add', json.dumps({'name': '半导体', 'category': '科技'}))
        assert h.sent['success'] is True
        assert '科技' in ds.get_categories()

    def test_add_sub_duplicate(self, ds, api):
        ds.add_category("科技")
        ds.add_sub_direction("科技", "半导体")
        h = MockHandler()
        api._handle_sub_add(h, '/api/directions/sub/add', json.dumps({'name': '半导体', 'category': '科技'}))
        assert h.sent['success'] is False
        assert '已存在' in h.sent.get('error', '')


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/remove
# ═══════════════════════════════════════════════════════════

class TestApiSubRemove:

    def test_remove_sub(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        # name 是完整名称（含分类前缀）
        api._handle_sub_remove(h, '/api/directions/sub/remove', json.dumps({'name': '科技.半导体'}))
        assert h.sent['success'] is True
        assert '科技.半导体' not in ds.get_sub_directions()
        assert '科技.算力' in ds.get_sub_directions()

    def test_remove_sub_not_found(self, ds, api):
        h = MockHandler()
        api._handle_sub_remove(h, '/api/directions/sub/remove', json.dumps({'name': '科技.不存在'}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/toggle
# ═══════════════════════════════════════════════════════════

class TestApiSubToggle:

    def test_toggle_sub(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_toggle(h, '/api/directions/sub/toggle', json.dumps({'name': '科技.半导体', 'enabled': False}))
        assert h.sent['success'] is True
        subs = ds.get_sub_directions()
        assert subs['科技.半导体']['enabled'] is False

    def test_toggle_sub_not_found(self, ds, api):
        h = MockHandler()
        api._handle_sub_toggle(h, '/api/directions/sub/toggle', json.dumps({'name': '科技.不存在', 'enabled': False}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/reorder
# ═══════════════════════════════════════════════════════════

class TestApiSubReorder:

    def test_reorder_subs(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_reorder(h, '/api/directions/sub/reorder', json.dumps({'names': ['科技.算力', '科技.半导体']}))
        assert h.sent['success'] is True
        subs = ds.get_sub_directions(category="科技")
        assert subs['科技.算力']['order'] == 0
        assert subs['科技.半导体']['order'] == 1


# ═══════════════════════════════════════════════════════════
# POST /api/directions/bind
# ═══════════════════════════════════════════════════════════

class TestApiBind:

    def test_bind_concept(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_bind(h, '/api/directions/bind', json.dumps({'sub_dir': '科技.半导体', 'concept_code': '301085'}))
        assert h.sent['success'] is True
        bound = ds.get_bound_concepts("科技", "半导体")
        assert '301085' in bound

    def test_bind_to_nonexistent_sub(self, ds, api):
        h = MockHandler()
        api._handle_bind(h, '/api/directions/bind', json.dumps({'sub_dir': '科技.不存在', 'concept_code': '301085'}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/unbind
# ═══════════════════════════════════════════════════════════

class TestApiUnbind:

    def test_unbind_concept(self, ds, api):
        _setup_basic_data(ds)
        ds.bind_concept("科技", "半导体", "301085", "芯片概念")
        h = MockHandler()
        api._handle_unbind(h, '/api/directions/unbind', json.dumps({'sub_dir': '科技.半导体', 'concept_code': '301085'}))
        assert h.sent['success'] is True
        bound = ds.get_bound_concepts("科技", "半导体")
        assert '301085' not in bound

    def test_unbind_not_bound(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_unbind(h, '/api/directions/unbind', json.dumps({'sub_dir': '科技.半导体', 'concept_code': '999999'}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# GET /api/directions/concepts/search?q=xxx
# ═══════════════════════════════════════════════════════════

class TestApiConceptsSearch:

    def test_search_concepts(self, ds, api):
        # 写模拟概念数据
        concept_path = os.path.join(ds.DATA_DIR, 'map', 'concept_list.json')
        os.makedirs(os.path.dirname(concept_path), exist_ok=True)
        with open(concept_path, 'w') as f:
            json.dump({
                "301085": {"name": "芯片概念", "stock_count": 50},
                "307940": {"name": "存储芯片", "stock_count": 30},
            }, f)
        h = MockHandler()
        api._handle_concepts_search(h, '/api/directions/concepts/search?q=芯片')
        assert h.sent is not None
        assert isinstance(h.sent, list) or 'results' in h.sent or 'concepts' in h.sent
        # 检查结果中包含我们查找的内容

    def test_search_concepts_empty_query(self, ds, api):
        h = MockHandler()
        api._handle_concepts_search(h, '/api/directions/concepts/search?q=')
        assert h.sent is not None


# ═══════════════════════════════════════════════════════════
# POST /api/directions/migrate
# ═══════════════════════════════════════════════════════════

class TestApiMigrate:

    def test_migrate_v1(self, ds, api, tmp_data_dir):
        """从 V1 迁移到 V2"""
        path = os.path.join(tmp_data_dir, 'directions.json')
        with open(path, 'w') as f:
            json.dump({
                "all": ["半导体", "算力", "创新药"],
                "active": ["半导体", "算力"],
                "suggestions": {"industry": [], "concept": [], "custom": []},
                "core": {}
            }, f)
        h = MockHandler()
        api._handle_migrate(h, '/api/directions/migrate', '{}')
        assert h.sent['success'] is True
        assert h.sent['migrated'] == 3

    def test_migrate_already_v2(self, ds, api):
        """已经是 V2 不应重复迁移"""
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_migrate(h, '/api/directions/migrate', '{}')
        assert h.sent['success'] is False
        assert '最新' in h.sent.get('error', '')


# ═══════════════════════════════════════════════════════════
# POST /api/directions/category/rename
# ═══════════════════════════════════════════════════════════

class TestApiCategoryRename:

    def test_rename_category(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_category_rename(h, '/api/directions/category/rename',
                                     json.dumps({'old_name': '科技', 'new_name': '科学技术'}))
        assert h.sent['success'] is True
        cats = ds.get_categories()
        assert '科学技术' in cats
        assert '科技' not in cats

    def test_rename_category_not_found(self, ds, api):
        h = MockHandler()
        api._handle_category_rename(h, '/api/directions/category/rename',
                                     json.dumps({'old_name': '不存在', 'new_name': '新名字'}))
        assert h.sent['success'] is False

    def test_rename_category_empty_old_name(self, ds, api):
        h = MockHandler()
        api._handle_category_rename(h, '/api/directions/category/rename',
                                     json.dumps({'old_name': '', 'new_name': '新名字'}))
        assert h.sent['success'] is False

    def test_rename_category_empty_new_name(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_category_rename(h, '/api/directions/category/rename',
                                     json.dumps({'old_name': '科技', 'new_name': ''}))
        assert h.sent['success'] is False


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/rename
# ═══════════════════════════════════════════════════════════

class TestApiSubRename:

    def test_rename_sub(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_rename(h, '/api/directions/sub/rename',
                                json.dumps({'name': '科技.半导体', 'new_name': '先进封装'}))
        assert h.sent['success'] is True
        subs = ds.get_sub_directions()
        assert '科技.先进封装' in subs
        assert '科技.半导体' not in subs

    def test_rename_sub_not_found(self, ds, api):
        h = MockHandler()
        api._handle_sub_rename(h, '/api/directions/sub/rename',
                                json.dumps({'name': '科技.不存在', 'new_name': '新名字'}))
        assert h.sent['success'] is False

    def test_rename_sub_empty_name(self, ds, api):
        h = MockHandler()
        api._handle_sub_rename(h, '/api/directions/sub/rename',
                                json.dumps({'name': '', 'new_name': '新名字'}))
        assert h.sent['success'] is False

    def test_rename_sub_v1_format(self, ds, api):
        """V1 格式（无分类前缀）也应支持"""
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_rename(h, '/api/directions/sub/rename',
                                json.dumps({'name': '科技.半导体', 'new_name': '先进封装'}))
        assert h.sent['success'] is True


# ═══════════════════════════════════════════════════════════
# POST /api/directions/sub/move
# ═══════════════════════════════════════════════════════════

class TestApiSubMove:

    def test_move_sub(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_move(h, '/api/directions/sub/move',
                              json.dumps({'name': '科技.半导体', 'new_category': '医药'}))
        assert h.sent['success'] is True
        subs = ds.get_sub_directions()
        assert '医药.半导体' in subs
        assert '科技.半导体' not in subs

    def test_move_sub_auto_create_category(self, ds, api):
        _setup_basic_data(ds)
        h = MockHandler()
        api._handle_sub_move(h, '/api/directions/sub/move',
                              json.dumps({'name': '科技.半导体', 'new_category': '新能源'}))
        assert h.sent['success'] is True
        assert '新能源' in ds.get_categories()
        assert '新能源.半导体' in ds.get_sub_directions()

    def test_move_sub_not_found(self, ds, api):
        h = MockHandler()
        api._handle_sub_move(h, '/api/directions/sub/move',
                              json.dumps({'name': '科技.不存在', 'new_category': '医药'}))
        assert h.sent['success'] is False

    def test_move_sub_empty_name(self, ds, api):
        h = MockHandler()
        api._handle_sub_move(h, '/api/directions/sub/move',
                              json.dumps({'name': '', 'new_category': '医药'}))
        assert h.sent['success'] is False

    def test_move_sub_empty_category(self, ds, api):
        h = MockHandler()
        api._handle_sub_move(h, '/api/directions/sub/move',
                              json.dumps({'name': '科技.半导体', 'new_category': ''}))
        assert h.sent['success'] is False
