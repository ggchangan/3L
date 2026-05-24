"""
TTLCache 单元测试

覆盖：
- 基本存取（get + loader）
- TTL 过期
- 主动失效（invalidate）
- Mock 支持
- 并发安全
- 统计/状态
"""

import time
import threading
from unittest.mock import MagicMock


def test_basic_get_and_cache_hit():
    """基本存取：首次调 loader，后续走缓存"""
    from scripts.cache_layer import cache as _real_cache

    # 用独立实例避免污染全局缓存
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    loader = MagicMock(return_value={'data': [1, 2, 3]})

    # 首次：调 loader
    result1 = c.get('test', loader, ttl=60)
    assert result1 == {'data': [1, 2, 3]}
    assert loader.call_count == 1

    # 再次：不调 loader
    result2 = c.get('test', loader, ttl=60)
    assert result2 == {'data': [1, 2, 3]}
    assert loader.call_count == 1  # 未增加


def test_loader_called_on_expiry():
    """TTL 过期后重新调 loader"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    call_count = [0]

    def loader():
        call_count[0] += 1
        return {'val': call_count[0]}

    # 第一次，ttl=0 立即过期
    r1 = c.get('exp', loader, ttl=0)
    assert r1 == {'val': 1}

    # 第二次，已过期
    r2 = c.get('exp', loader, ttl=0)
    assert r2 == {'val': 2}

    # 第三次，已过期
    r3 = c.get('exp', loader, ttl=0)
    assert r3 == {'val': 3}


def test_invalidate_clears_cache():
    """主动失效后再次调 loader"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    loader = MagicMock(return_value='fresh')

    r1 = c.get('inv', loader, ttl=60)
    assert r1 == 'fresh'
    assert loader.call_count == 1

    c.invalidate('inv')

    r2 = c.get('inv', loader, ttl=60)
    assert r2 == 'fresh'
    assert loader.call_count == 2  # 重新加载


def test_invalidate_non_existent_key():
    """invalidate 不存在的 key 不报错"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()
    c.invalidate('nope')  # 不应抛异常


def test_set_mock_and_get():
    """set_mock 注入的数据永不过期"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    c.set_mock('mock_key', {'mocked': True})

    # loader 不应被调用
    loader = MagicMock(return_value='new')
    result = c.get('mock_key', loader, ttl=0)
    assert result == {'mocked': True}
    assert loader.call_count == 0


def test_clear_mocks():
    """clear_mocks 只清除 mock 条目，保留普通缓存"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    c.set_mock('m1', 'mock_data')
    c.get('real', lambda: 'real_data', ttl=60)

    c.clear_mocks()

    # mock 数据被清除 → 调 loader
    loader = MagicMock(return_value='fresh')
    result = c.get('m1', loader, ttl=60)
    assert result == 'fresh'
    assert loader.call_count == 1

    # 普通缓存还在
    result2 = c.get('real', lambda: 'should_not_call', ttl=60)
    assert result2 == 'real_data'


def test_clear_removes_all():
    """clear 清除所有缓存"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    c.get('a', lambda: 1, ttl=60)
    c.get('b', lambda: 2, ttl=60)
    c.set_mock('m', 'mock')

    stats = c.stats()
    assert stats['size'] == 3

    c.clear()

    stats2 = c.stats()
    assert stats2['size'] == 0


def test_double_check_locking():
    """并发时 double-check 只调一次 loader"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    call_count = [0]
    loader_started = threading.Event()

    def slow_loader():
        call_count[0] += 1
        loader_started.set()  # 通知测试线程：loader 已开始
        time.sleep(0.3)       # 模拟慢加载
        return 'result'

    results = []
    errors = []

    def worker():
        try:
            r = c.get('concurrent', slow_loader, ttl=60)
            results.append(r)
        except Exception as e:
            errors.append(e)

    # 线程1：触发加载
    t1 = threading.Thread(target=worker)
    t1.start()
    loader_started.wait(timeout=5)  # 等 loader 开始（已拿锁）

    # 线程2、3：此时 cache miss，但锁被 t1 持有
    t2 = threading.Thread(target=worker)
    t3 = threading.Thread(target=worker)
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    assert len(errors) == 0
    assert all(r == 'result' for r in results)
    assert call_count[0] == 1  # loader 只被调一次


def test_stats_structure():
    """stats() 返回正确结构"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    c.get('a', lambda: 1, ttl=60)

    stats = c.stats()
    assert 'size' in stats
    assert 'keys' in stats
    assert 'expired_count' in stats
    assert 'mock_keys' in stats
    assert stats['size'] >= 1
    assert 'a' in stats['keys']
    assert stats['mock_keys'] == []

    c.set_mock('m', 'mock')
    stats2 = c.stats()
    assert 'm' in stats2['mock_keys']


def test_loader_error_propagates():
    """loader 抛异常时应该传播，不静默吞掉"""
    from scripts.cache_layer import TTLCache
    c = TTLCache()

    def broken_loader():
        raise ValueError("故意崩溃")

    import pytest
    with pytest.raises(ValueError, match="故意崩溃"):
        c.get('broken', broken_loader, ttl=60)
