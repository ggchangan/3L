"""
3L 交易系统 — 内存缓存层

三层缓存策略中的 Layer 3（数据缓存）：
- 存储已从 JSON 加载的 K 线数据、自选股等
- TTL 自动过期 + 主动失效
- 线程安全（Lock 保护）
- 支持 Mock（测试注入）

用法:
    from backend.data_access.cache_layer import cache
    data = cache.get('all_stocks', loader_func, ttl=30)
    cache.invalidate('all_stocks')
"""

import threading
import time


class TTLCache:
    """线程安全、TTL 自动过期、支持 Mock 的内存缓存。

    缓存未命中时调用 loader() 加载数据，加锁防止并发重复加载。
    """

    def __init__(self):
        self._data = {}       # key → value
        self._expiry = {}     # key → expiry_timestamp
        self._lock = threading.Lock()

    def get(self, key, loader, ttl=30):
        """获取缓存。

        缓存命中且未过期 → 直接返回。
        缓存未命中或已过期 → 调 loader() 加载，ttl 秒后过期。

        Args:
            key: 缓存键名
            loader: 无参回调函数，缓存未命中时调用
            ttl: 过期时间（秒），默认 30s

        Returns:
            加载的数据
        """
        now = time.time()
        # 快速路径：命中且未过期（无锁）
        if key in self._data and now < self._expiry.get(key, 0):
            return self._data[key]

        # 慢速路径：加锁加载（防止多个线程同时读磁盘）
        with self._lock:
            # Double-check：第一个线程加载完后，第二个线程不用再读
            if key in self._data and now < self._expiry.get(key, 0):
                return self._data[key]
            self._data[key] = loader()
            self._expiry[key] = now + ttl
            return self._data[key]

    def invalidate(self, key):
        """主动失效缓存。

        当数据被手动更新时调用（如保存 watchlist 后）。
        """
        with self._lock:
            self._data.pop(key, None)
            self._expiry.pop(key, None)

    def clear(self):
        """清除所有缓存"""
        with self._lock:
            self._data.clear()
            self._expiry.clear()

    # ---------- 测试支持 ----------

    def set_mock(self, key, data):
        """注入 Mock 数据（永不过期）"""
        with self._lock:
            self._data[key] = data
            self._expiry[key] = float('inf')

    def clear_mocks(self):
        """清除所有 Mock 数据（移除永不过期的条目）"""
        with self._lock:
            expired = [k for k, v in self._expiry.items() if v == float('inf')]
            for k in expired:
                self._data.pop(k, None)
                self._expiry.pop(k, None)

    # ---------- 状态/统计 ----------

    def stats(self):
        """返回缓存统计"""
        now = time.time()
        return {
            'size': len(self._data),
            'keys': list(self._data.keys()),
            'expired_count': sum(1 for v in self._expiry.values() if v < now),
            'mock_keys': [k for k, v in self._expiry.items() if v == float('inf')],
        }


# 模块级单例
cache = TTLCache()
