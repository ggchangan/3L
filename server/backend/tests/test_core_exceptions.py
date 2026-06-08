"""测试 core/exceptions — 分层异常体系"""
import sys, os, pytest

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.core.exceptions import (
    ThreeLError, DataError, APIError, ConfigError, DataSourceError
)


class TestExceptionHierarchy:
    """测试异常继承链"""

    def test_threeL_error_is_base(self):
        """ThreeLError 是 Exception 的子类"""
        err = ThreeLError("test", log_when=False)
        assert isinstance(err, Exception)
        assert str(err) == "test"

    def test_data_error_inherits_threeL(self):
        """DataError 继承 ThreeLError"""
        err = DataError("数据缺失", log_when=False)
        assert isinstance(err, ThreeLError)
        assert isinstance(err, Exception)

    def test_api_error_inherits_threeL(self):
        """APIError 继承 ThreeLError"""
        err = APIError("参数错误", log_when=False)
        assert isinstance(err, ThreeLError)

    def test_config_error_inherits_threeL(self):
        """ConfigError 继承 ThreeLError"""
        err = ConfigError("配置缺失", log_when=False)
        assert isinstance(err, ThreeLError)

    def test_data_source_error_chain(self):
        """DataSourceError 继承 DataError（链：DataSourceError→DataError→ThreeLError）"""
        err = DataSourceError("同花顺超时", log_when=False)
        assert isinstance(err, DataSourceError)
        assert isinstance(err, DataError)
        assert isinstance(err, ThreeLError)

    def test_raise_and_catch_data_error(self):
        """DataError 可以被 except DataError 捕获"""
        with pytest.raises(DataError) as exc:
            raise DataError("文件未找到", log_when=False)
        assert "文件未找到" in str(exc.value)

    def test_raise_and_catch_api_error(self):
        """APIError 可以被 except APIError 捕获"""
        with pytest.raises(APIError) as exc:
            raise APIError("缺少code参数", log_when=False)
        assert "缺少code参数" in str(exc.value)

    def test_raise_and_catch_generic_threeL(self):
        """子异常可以被基类 except ThreeLError 捕获"""
        with pytest.raises(ThreeLError) as exc:
            raise DataSourceError("连接超时", log_when=False)
        assert isinstance(exc.value, DataSourceError)


class TestLogWhenBehavior:
    """测试 log_when 参数控制自动日志"""

    def test_log_when_false_does_not_crash(self):
        """log_when=False 不触发日志，不报错（不需要 mock）"""
        # 仅验证不会抛出异常
        err = DataError("正常跳过", log_when=False)
        assert str(err) == "正常跳过"

    def test_auto_logs_on_creation(self, caplog):
        """log_when=True（默认）时创建异常自动记录日志"""
        # caplog 是 pytest 内置 fixture，捕获标准 logging 输出
        import logging
        from backend.core.logger import setup_logging
        setup_logging()

        with caplog.at_level(logging.ERROR):
            err = APIError("测试自动日志", log_when=True)
            assert str(err) == "测试自动日志"

        # 验证日志中包含了异常信息
        found = any("APIError" in record.message for record in caplog.records)
        assert found, f"未在日志中找到 APIError 记录。实际记录: {[r.message for r in caplog.records]}"
