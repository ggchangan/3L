"""测试 core/logger — 统一日志配置"""
import sys, os, logging, tempfile, shutil, pytest

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


class TestLoggerSetup:
    """测试日志初始化与输出"""

    def test_setup_logging_idempotent(self):
        """setup_logging() 幂等，多次调用不重复添加 handler"""
        from backend.core.logger import setup_logging

        import backend.core.logger as logger_mod
        logger_mod._initialized = False

        setup_logging()
        root = logging.getLogger()
        handler_count_before = len(root.handlers)

        setup_logging()  # 第二次调用
        handler_count_after = len(root.handlers)

        assert handler_count_after == handler_count_before, (
            f"setup_logging 不是幂等的：{handler_count_before} → {handler_count_after}"
        )

    def test_get_logger_returns_logger_instance(self):
        """get_logger 返回 logging.Logger 实例"""
        from backend.core.logger import get_logger

        log = get_logger("test.module")
        assert isinstance(log, logging.Logger)
        assert log.name == "test.module"

    def test_logger_outputs_to_console(self, caplog):
        """get_logger 的日志能输出到控制台（捕获）"""
        from backend.core.logger import get_logger

        with caplog.at_level(logging.INFO):
            log = get_logger("test.console")
            log.info("控制台测试消息")

        found = any("控制台测试消息" in record.message for record in caplog.records)
        assert found, "日志消息未出现在 caplog 捕获中"

    def test_logger_format_includes_level(self, caplog):
        """日志格式包含级别标识"""
        from backend.core.logger import get_logger

        with caplog.at_level(logging.WARNING):
            log = get_logger("test.format")
            log.warning("格式测试")

        assert any(
            record.levelname == "WARNING" and "格式测试" in record.message
            for record in caplog.records
        ), "日志格式缺少级别标识"


class TestLogFiles:
    """测试日志文件生成（使用临时目录）"""

    @pytest.fixture(autouse=True)
    def setup_temp_log_dir(self, monkeypatch, tmp_path):
        """为每个测试方法创建临时日志目录，重置日志状态"""
        self.log_dir = tmp_path / "logs"
        self.log_dir.mkdir()

        import backend.config
        monkeypatch.setattr(backend.config, 'LOG_DIR', str(self.log_dir))
        monkeypatch.setattr(backend.config, 'LOG_LEVEL', 'DEBUG')

        import backend.core.logger as logger_mod
        logger_mod._initialized = False

        # 清除 root logger 的所有 handler（避免干扰）
        root = logging.getLogger()
        for h in list(root.handlers):
            root.removeHandler(h)

        yield

    def test_log_file_created(self):
        """setup_logging 后 3l-server.log 文件生成"""
        from backend.core.logger import setup_logging

        setup_logging()
        log_path = self.log_dir / "3l-server.log"
        assert log_path.exists(), f"日志文件未生成: {log_path}"

    def test_error_log_separate_file(self):
        """ERROR 级别日志同时写入 3l-server.log 和 3l-server.error.log"""
        from backend.core.logger import setup_logging, get_logger

        setup_logging()
        log = get_logger("test.error_file")
        log.error("测试错误消息")

        # 主日志文件应包含
        main_log = self.log_dir / "3l-server.log"
        main_content = main_log.read_text(encoding="utf-8", errors="replace")
        assert "测试错误消息" in main_content, f"主日志未包含错误消息: {main_content}"

        # 独立错误日志文件也应包含
        err_log = self.log_dir / "3l-server.error.log"
        assert err_log.exists(), "独立错误日志文件未生成"
        err_content = err_log.read_text(encoding="utf-8", errors="replace")
        assert "测试错误消息" in err_content, f"错误日志未包含消息: {err_content}"

    def test_info_not_in_error_log(self):
        """INFO 级别日志不出现在 3l-server.error.log 中"""
        from backend.core.logger import setup_logging, get_logger

        setup_logging()
        log = get_logger("test.info_filter")
        log.info("这是一条 INFO 消息，不应出现在错误日志中")

        err_log = self.log_dir / "3l-server.error.log"
        if err_log.exists():
            err_content = err_log.read_text(encoding="utf-8", errors="replace")
            assert "INFO" not in err_content, "INFO 日志错误地写入了 error.log"

    def test_log_contains_module_name(self):
        """日志行包含模块名"""
        from backend.core.logger import setup_logging, get_logger

        setup_logging()
        log = get_logger("test.my_module")
        log.info("模块名测试")

        main_log = self.log_dir / "3l-server.log"
        content = main_log.read_text(encoding="utf-8", errors="replace")
        assert "test.my_module" in content, f"日志缺少模块名: {content}"
