"""部署构建安全边界测试。"""
from frontend import build


def test_regression_disables_live_database_tests(monkeypatch):
    """构建脚本必须把真实数据库禁用开关传给回归子进程。"""
    captured = {}

    class Completed:
        returncode = 0
        stdout = ''
        stderr = ''

    def fake_run(*args, **kwargs):
        captured.update(kwargs)
        return Completed()

    monkeypatch.setattr(build.subprocess, 'run', fake_run)

    assert build.run_regression() is True
    assert captured['env']['DISABLE_LIVE_DB_TESTS'] == '1'
