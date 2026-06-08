"""
3L 交易系统 — 统一日志配置

用法:
    from backend.core.logger import get_logger
    log = get_logger(__name__)
    log.info("message")
    log.error("error", exc_info=True)

首次导入时自动配置日志（控制台 + 文件 + 独立错误日志）。
通过 config.LOG_LEVEL / LOG_DIR 控制级别和路径。
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# 防止重复配置
_initialized = False

# 格式模板
_CONSOLE_FMT = '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
_FILE_FMT = '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
_DATE_FMT = '%Y-%m-%d %H:%M:%S'


def setup_logging():
    """全局初始化日志配置（幂等，只执行一次）"""
    global _initialized
    if _initialized:
        return

    # 延迟导入 config（避免循环依赖）
    from backend.config import LOG_LEVEL, LOG_DIR

    level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)

    # ── 控制台 Handler ──
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(_CONSOLE_FMT, _DATE_FMT))
    root.addHandler(console)

    # ── 文件 Handler ──
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        log_path = os.path.join(LOG_DIR, '3l-server.log')
        file_handler = RotatingFileHandler(
            log_path, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(logging.Formatter(_FILE_FMT, _DATE_FMT))
        root.addHandler(file_handler)

        # ── 独立错误日志 ──
        err_path = os.path.join(LOG_DIR, '3l-server.error.log')
        err_handler = RotatingFileHandler(
            err_path, maxBytes=10 * 1024 * 1024, backupCount=5,
            encoding='utf-8'
        )
        err_handler.setLevel(logging.ERROR)
        err_handler.setFormatter(logging.Formatter(_FILE_FMT, _DATE_FMT))
        root.addHandler(err_handler)
    except (OSError, PermissionError) as e:
        root.warning('无法创建日志文件 %s: %s', LOG_DIR, e)

    _initialized = True
    root.info('日志初始化完成 (level=%s, dir=%s)', LOG_LEVEL, LOG_DIR)


def get_logger(name):
    """获取 logger 实例（首次自动初始化）

    Args:
        name: 通常传入 __name__
    Returns:
        logging.Logger 实例
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(name)
