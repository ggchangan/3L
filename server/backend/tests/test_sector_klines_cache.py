"""get_sector_klines 缓存契约测试 — 防止自选股分析重算性能回归

2026-08-06 回归：多用户改造后 analysis_cache.json 未迁移 → 首次访问
触发 310 只自选股全量重算，每只调用 get_stock_card → _calc_sector_chg_5d
→ get_sector_klines 逐只查 MySQL（310 次查询 56s+），撞 nginx 60s 超时
→ 自选股页信息全部加载失败。

修复：data_layer.get_sector_klines 加 60s TTL 缓存（板块K线 T+1 数据
日内不变，缓存安全），同板块只查一次。全量重算 56s → 9s。

本测试锁定缓存行为：同板块两次调用，loader 只执行一次。

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


def test_get_sector_klines_uses_cache(monkeypatch):
    """同板块 60s 内两次调用，底层 loader 只执行一次。"""
    from backend.data_access import data_layer
    from backend.data_access.cache_layer import cache

    calls = {'n': 0}

    def fake_ds_klines(name, type_):
        calls['n'] += 1
        return [{'date': '20260805', 'close': 10.0},
                {'date': '20260804', 'close': 9.5}]

    monkeypatch.setattr(data_layer, 'cache', cache)
    monkeypatch.setattr(
        'backend.data_access.data_source.get_sector_klines', fake_ds_klines)

    # 清掉可能存在的缓存键
    cache.invalidate('sector_klines:industry:测试板块')

    # 第一次：loader 执行；第二次：缓存命中
    k1 = data_layer.get_sector_klines('测试板块', 'industry')
    k2 = data_layer.get_sector_klines('测试板块', 'industry')
    assert calls['n'] == 1, '同板块 60s 内应命中缓存，loader 只执行一次'
    assert k1 == k2
    assert k2[-1]['close'] == 10.0  # 日期正序

    # 不同板块：loader 再次执行（缓存键按板块隔离）
    calls['n'] = 0
    data_layer.get_sector_klines('另一板块', 'industry')
    assert calls['n'] == 1


def test_get_sector_klines_different_types_isolated(monkeypatch):
    """行业/概念类型缓存键隔离，互不污染。"""
    from backend.data_access import data_layer
    from backend.data_access.cache_layer import cache

    calls = []

    def fake_ds_klines(name, type_):
        calls.append(type_)
        return [{'date': '20260805', 'close': 1.0}]

    monkeypatch.setattr(data_layer, 'cache', cache)
    monkeypatch.setattr(
        'backend.data_access.data_source.get_sector_klines', fake_ds_klines)

    cache.invalidate('sector_klines:industry:混合板块')
    cache.invalidate('sector_klines:concept:混合板块')
    data_layer.get_sector_klines('混合板块', 'industry')
    data_layer.get_sector_klines('混合板块', 'concept')
    assert calls == ['industry', 'concept'], '不同类型应各自查一次'
