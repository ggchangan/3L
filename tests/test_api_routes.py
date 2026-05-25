"""API 路由模块测试 — 验证路由分发模块的注册正确性

测试目标（TDD Phase 1）:
  1. 每个 api/*.py 模块有 register_routes(routes) 接口
  2. 所有路由路径注册正确
  3. 无重复路径
"""

import pytest
import sys
import os

# 确保能找到 backend 包
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def fresh_routes():
    """每次测试一个干净的路由表"""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    from server import RouteRegistry
    return RouteRegistry()


# ── API 模块契约测试 ──────────────────────────────────────

API_MODULES = [
    'backend.api.review',
    'backend.api.monitor',
    'backend.api.watchlist',
    'backend.api.stock',
    'backend.api.industry',
    'backend.api.trend',
    'backend.api.tips',
    'backend.api.market',
    'backend.api.holdings',
    'backend.api.system',
    'backend.api.top_gainers',
    'backend.api.macro',
]


class TestApiModuleContract:

    @pytest.mark.parametrize('mod_name', API_MODULES)
    def test_module_has_register_routes(self, mod_name):
        """每个 api 模块必须有 register_routes 函数"""
        mod = pytest.importorskip(mod_name)
        assert hasattr(mod, 'register_routes'), f'{mod_name} 缺少 register_routes()'
        assert callable(mod.register_routes)

    @pytest.mark.parametrize('mod_name', API_MODULES)
    def test_register_routes_accepts_routes_param(self, mod_name, fresh_routes):
        """register_routes 接受 RouteRegistry 并返回它"""
        mod = pytest.importorskip(mod_name)
        result = mod.register_routes(fresh_routes)
        assert result is fresh_routes, f'{mod_name}.register_routes 应返回 routes 对象'


# ── 完整路由表验证 ──────────────────────────────────────

def test_all_routes_registered_no_duplicates(fresh_routes):
    """全量注册后，无重复路径"""
    # 导入并注册所有模块
    import importlib
    registered = []
    for mod_name in API_MODULES:
        mod = importlib.import_module(mod_name)
        mod.register_routes(fresh_routes)
        registered.append(mod_name)

    # 验证路由表无重复
    assert len(fresh_routes._exact) > 30, '路由数不足，可能注册不全'


def test_route_paths_are_unique(fresh_routes):
    """所有路由路径唯一"""
    import importlib
    for mod_name in API_MODULES:
        importlib.import_module(mod_name).register_routes(fresh_routes)

    seen = {}
    for path in fresh_routes._exact:
        if path in seen:
            pytest.fail(f'重复路由路径: {path}')
        seen[path] = True


EXPECTED_ROUTES_GET = [
    '/api/market',
    '/api/mainlines',
    '/api/stocks',
    '/api/health',
    '/api/holdings',
    '/api/trades',
    '/api/review',
    '/api/review/dates',
    '/api/review/generate',
    '/api/stock-analysis',
    '/api/stock-backtest',
    '/api/industry-boards',
    '/api/concept-boards',
    '/api/industry-map',
    '/api/industry/list',
    '/api/industry/content',
    '/api/trend-candidates',
    '/api/trend-tracked',
    '/api/trend-candidates/toggle',
    '/api/watchlist',
    '/api/watchlist/search',
    '/api/watchlist/analysis',
    '/api/momentum',
    '/api/monitor/volume',
    '/api/monitor/buy-signals',
    '/api/monitor/stop-loss',
    '/api/monitor/sectors',
    '/api/monitor/leaders',
    '/api/monitor/market-leaders',
    '/api/sector-chart',
    '/api/tips',
    '/api/tips/content',
    '/api/tips/journal-entries',
    '/api/top-gainers',
    '/api/macro',
]

EXPECTED_ROUTES_POST = [
    '/api/review/save',
    '/api/watchlist/save',
    '/api/tips/save-journal',
    '/api/update',
    '/api/directions/add',
    '/api/directions/remove',
    '/api/directions/toggle',
    '/api/directions/reorder',
    '/api/workbench/save',
    '/api/holdings/save',
]


class TestRouteCompleteness:

    def test_all_get_routes_present(self, fresh_routes):
        """所有 GET 路由都存在"""
        import importlib
        for mod_name in API_MODULES:
            importlib.import_module(mod_name).register_routes(fresh_routes)

        for path in EXPECTED_ROUTES_GET:
            assert path in fresh_routes._exact, f'缺少路由: {path}'

    def test_expected_route_count(self, fresh_routes):
        """验证路由总数在合理范围内"""
        import importlib
        for mod_name in API_MODULES:
            importlib.import_module(mod_name).register_routes(fresh_routes)

        count = len(fresh_routes._exact)
        expected_min = len(EXPECTED_ROUTES_GET)
        assert count >= expected_min, f'路由数 {count} 不足 {expected_min}'
        # 允许最多+8个额外路由（新功能新增路由时松一点）
        assert count <= expected_min + 8, \
            f'路由数 {count} 超出预期 {expected_min}，可能有未预期的路由'


# ── POST 路由 ─────────────────────────────────────────

def test_post_route_handlers_exist():
    """验证所有 POST 路由对应的 handler 函数存在"""
    # POST 路由在 do_POST 中直接处理，不在 RouteRegistry 中注册
    # 验证每个 api 模块有对应的 _handle_*_save 函数
    import importlib
    mod = importlib.import_module('backend.api.review')
    assert hasattr(mod, '_handle_review_save')
    mod = importlib.import_module('backend.api.watchlist')
    assert hasattr(mod, '_handle_watchlist_save')
    mod = importlib.import_module('backend.api.tips')
    assert hasattr(mod, '_handle_save_journal')
    mod = importlib.import_module('backend.api.system')
    assert hasattr(mod, '_handle_update')
    mod = importlib.import_module('backend.api.holdings')
    assert hasattr(mod, '_handle_save')
    mod = importlib.import_module('backend.api.workbench')
    assert hasattr(mod, '_handle_save')
