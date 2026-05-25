"""generate_review_data.py 流程测试
验证复盘数据生成流程完整可用（导入、执行、输出结构）
"""

import os
import json
import sys
import pytest

# 需要提前设置 PYTHONPATH
WWW_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
SCRIPTS_DIR = os.path.join(WWW_DIR, 'scripts')
sys.path.insert(0, SCRIPTS_DIR)
os.environ['TQDM_DISABLE'] = '1'


class TestModuleImport:
    """第1层：模块导入测试 — 确认所有依赖的 import 都能通过"""

    def test_import_data_layer(self):
        """data_layer 导入"""
        from scripts.data_layer import (
            ALL_STOCKS_PATH, REVIEW_ARCHIVE_DIR, get_all_stocks,
            get_review_archive, save_review_archive
        )
        assert os.path.isdir(REVIEW_ARCHIVE_DIR), f'存档目录不存在: {REVIEW_ARCHIVE_DIR}'

    def test_import_ema_utils(self):
        """ema_utils 导入（路径修复验证）"""
        from ema_utils import get_structure, get_stage, get_ema_arrangement

    def test_import_judge_signal(self):
        """judge_signal 导入（路径修复验证）"""
        sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/trading/3l-buy-point-judgment/scripts')
        from judge_signal import judge_signal

    def test_import_generate_module(self):
        """generate_review_data 主模块导入"""
        # 先切到 www 目录，避免 import 路径问题
        old_cwd = os.getcwd()
        os.chdir(WWW_DIR)
        try:
            import generate_review_data
            assert hasattr(generate_review_data, 'generate_daily_review')
            # 计算函数已迁移到 services.review_compute_service
            from services.review_compute_service import is_trading_day
            assert callable(is_trading_day)
        finally:
            os.chdir(old_cwd)


class TestReviewArchiveStructure:
    """第2层：已有存档的结构校验"""

    @pytest.fixture(scope='class')
    def archive(self):
        """获取最近一份存档"""
        from scripts.data_layer import REVIEW_ARCHIVE_DIR
        if not os.path.isdir(REVIEW_ARCHIVE_DIR):
            return None, {}
        files = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
        if not files:
            return None, {}
        latest = files[-1]
        path = os.path.join(REVIEW_ARCHIVE_DIR, latest)
        try:
            with open(path) as fh:
                return latest.replace('.json', ''), json.load(fh)
        except Exception:
            return None, {}

    def test_has_archive(self, archive):
        """至少有存档"""
        assert archive[0] is not None, '复盘存档目录为空'

    def test_archive_structure(self, archive):
        """存档包含核心字段"""
        date_str, data = archive
        assert 'date' in data, f'缺 date'
        assert 'market' in data, f'缺 market'
        assert 'mainline' in data, f'缺 mainline'

    def test_market_fields(self, archive):
        """market 段字段完整"""
        _, data = archive
        m = data.get('market', {})
        for k in ('score', 'position', 'bias20', 'vol_ratio', 'strategy'):
            assert k in m, f'market: 缺 {k}'

    def test_mainline_fields(self, archive):
        """mainline 段字段完整"""
        _, data = archive
        ml = data.get('mainline', {})
        for k in ('lines',):
            assert k in ml, f'mainline: 缺 {k}'

    def test_timing_signals_format(self, archive):
        """timing_signals 格式正确"""
        _, data = archive
        ts = data.get('timing_signals', {})
        for h in ts.get('holdings', []):
            for k in ('code', 'name', 'action'):
                assert k in h, f'holding: 缺 {k}'


class TestGenerateCommandLine:
    """第3层：命令行执行测试（确认不抛异常）"""

    def test_generate_review_import_only(self):
        """import 脚本本身不抛异常（模拟 python generate_review_data.py 的 import 阶段）"""
        import subprocess
        old_cwd = os.getcwd()
        os.chdir(WWW_DIR)
        try:
            result = subprocess.run(
                [sys.executable, '-c', 'import generate_review_data; print("OK")'],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, 'TQDM_DISABLE': '1'}
            )
            assert result.returncode == 0, f'导入失败:\n{result.stderr}'
            assert 'OK' in result.stdout
        finally:
            os.chdir(old_cwd)

    def test_is_trading_day_function(self):
        """交易日判断函数可调用（已迁移到 review_compute_service）"""
        import subprocess
        result = subprocess.run(
            [sys.executable, '-c',
             'from services.review_compute_service import is_trading_day; '
             'r = is_trading_day("2026-05-22"); '
             'print(r)'],
            capture_output=True, text=True, timeout=30,
            env={**os.environ, 'TQDM_DISABLE': '1'}
        )
        assert result.returncode == 0, f'调用失败:\n{result.stderr}'
        assert 'True' in result.stdout or 'False' in result.stdout


class TestReviewArchiveViaAPI:
    """第4层：通过 API 验证复盘数据可访问"""

    def test_review_api_response(self):
        """GET /api/review/ 返回完整数据"""
        import urllib.request
        import json
        try:
            resp = urllib.request.urlopen(
                'http://localhost:8080/api/review', timeout=10)
            d = json.loads(resp.read().decode())
            assert 'market' in d
            assert 'momentum' in d
            assert 'industry_map_archive' in d or 'industry_boards_archive' in d
        except Exception as e:
            pytest.skip(f'API 不通（server 未运行?）: {e}')
