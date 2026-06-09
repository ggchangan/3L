"""
3L 交易系统 — 统一异常层次

分层异常体系，所有自定义异常继承自 ThreeLError。
构建时可选自动记录错误日志，确保异常不会静默丢失。

用法:
    raise APIError("参数缺失: code")
    raise DataError("数据文件不存在")
    raise DataSourceError("同花顺API超时", log_when=True)

异常层次:
    ThreeLError (基类)
    ├── DataError          — 数据层：数据缺失/格式错误/过期
    │   └── DataSourceError — 数据源：第三方API调用失败
    ├── APIError           — API层：参数校验/资源未找到
    └── ConfigError        — 配置层：配置缺失/格式错误
"""
from backend.core.logger import get_logger


class ThreeLError(Exception):
    """基础异常，所有自定义异常的基类。抛出时自动记录错误日志。"""

    def __init__(self, message, *, log_when=True, exc_info=True):
        super().__init__(message)
        if log_when:
            get_logger(self.__class__.__module__).error(
                '%s: %s', self.__class__.__name__, message,
                exc_info=exc_info or None
            )


class DataError(ThreeLError):
    """数据层异常 — 数据缺失/格式错误/过期"""
    pass


class APIError(ThreeLError):
    """API 层异常 — 参数校验/资源未找到/请求格式错误"""
    pass


class ConfigError(ThreeLError):
    """配置异常 — 配置缺失/格式错误/环境变量未设置"""
    pass


class DataSourceError(DataError):
    """数据源异常 — 第三方 API 调用失败/返回格式异常"""
    pass
