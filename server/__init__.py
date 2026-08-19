"""3L Server 包 — 让 server/ 成为可导入的 Python 包。

保持包导入轻量，避免 pytest 收集 `server/` 包时触发完整 API 路由注册、
数据目录创建和外部数据源初始化。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .server import RouteRegistry as RouteRegistry


def __getattr__(name):
    if name == 'RouteRegistry':
        from .server import RouteRegistry

        return RouteRegistry
    raise AttributeError(name)
