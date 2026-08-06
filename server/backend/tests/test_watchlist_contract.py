"""get_watchlist 返回结构契约测试 — 防止多用户改造回归

2026-08-06 回归：多用户隔离改造后 get_watchlist() 从 list 变为
dict {'stocks': [...], 'count': N}，但 6 处调用点仍按旧 list 直接遍历
（data_layer/review_service/analysis_service/monitor_service/concept_wave/
watchlist_service），导致 'str' object has no attribute 'get'。
本测试锁定返回结构契约 + 扫描调用点模式，防止再次回归。

CI 只跑本目录：cd server && python -m pytest backend/tests/
"""
import os
import sys

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest  # noqa: E402


def _get_watchlist_impls():
    """返回所有定义 get_watchlist 的模块路径。"""
    from backend.data_access import data_layer
    from backend.services import watchlist_service
    return [data_layer, watchlist_service]


@pytest.mark.parametrize('module', _get_watchlist_impls())
def test_get_watchlist_returns_dict_contract(module):
    """get_watchlist() 必须返回 dict（{'stocks': [...], 'count': N}）。"""
    wl = module.get_watchlist()
    assert isinstance(wl, dict), (
        f'{module.__name__}.get_watchlist() 应返回 dict，实际 {type(wl).__name__}'
    )
    assert 'stocks' in wl
    assert isinstance(wl['stocks'], list)
    assert wl.get('count') == len(wl['stocks'])


def test_get_watchlist_stocks_are_dicts():
    """stocks 元素必须是 dict（含 code），不能是裸字符串。"""
    from backend.data_access import data_layer
    wl = data_layer.get_watchlist()
    for item in wl['stocks']:
        assert isinstance(item, dict), f'自选股元素应为 dict，实际 {type(item).__name__}'
        assert 'code' in item


def test_no_direct_iteration_over_get_watchlist():
    """扫描：禁止 `for x in get_watchlist()` 直接遍历（dict 会被当 keys 遍历）。

    正确的消费模式：`get_watchlist().get('stocks', [])` 或兼容 dict/list。
    """
    import re
    import glob

    patterns = [
        re.compile(r'for\s+\w+\s+in\s+get_watchlist\(\)'),
        re.compile(r'\{[^}]*\w+\.get\([^)]*\)[^}]*for\s+\w+\s+in\s+get_watchlist\(\)'),
    ]
    offenders = []
    for py in glob.glob(os.path.join(_server_root, 'backend', '**', '*.py'),
                        recursive=True):
        if 'test' in py or '__pycache__' in py:
            continue
        with open(py, encoding='utf-8') as f:
            for lineno, line in enumerate(f, 1):
                for pat in patterns:
                    if pat.search(line):
                        offenders.append(f'{os.path.relpath(py, _server_root)}:{lineno}')
    assert not offenders, f'发现直接遍历 get_watchlist() 的调用点（应改用 .get("stocks", [])）:\n' + '\n'.join(offenders)


def test_watchlist_dict_consumers_use_get_stocks():
    """已知消费点必须走 .get('stocks') 兼容路径（dict/list 双格式）。"""
    import glob

    # 这些文件里 get_watchlist() 赋值后必须能处理 dict 形态
    consumers = [
        'backend/data_access/data_layer.py',
        'backend/services/review_service.py',
        'backend/services/analysis_service.py',
        'backend/services/monitor_service.py',
        'backend/api/concept_wave.py',
        'backend/services/watchlist_service.py',
    ]
    for rel in consumers:
        path = os.path.join(_server_root, rel)
        with open(path, encoding='utf-8') as f:
            content = f.read()
        assert '.get(\'stocks\'' in content or 'isinstance' in content, (
            f'{rel} 未使用 dict/list 兼容消费模式，可能重蹈 str.get 回归'
        )
