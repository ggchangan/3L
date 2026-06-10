import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

"""测试指数数据相关功能"""
import pytest
from backend.core.data_layer import INDEX_CODES, INDEX_CODE


class TestIndexCodes:
    """INDEX_CODES 应包含4个指数"""

    def test_contains_all_four_indexes(self):
        assert '000985' in INDEX_CODES  # 中证全指
        assert '000001' in INDEX_CODES  # 上证指数
        assert '000688' in INDEX_CODES  # 科创50
        assert '399006' in INDEX_CODES  # 创业板指

    def test_default_index_is_985(self):
        assert INDEX_CODE == '000985'


class TestIndexSymbol:
    """_index_symbol 应正确判断 sz/sh 前缀"""

    @pytest.fixture(autouse=True)
    def _import(self):
        from backend.core.update_stock_data import _index_symbol
        self._f = _index_symbol

    def test_985_uses_sh_prefix(self):
        assert self._f('000985') == 'sh000985'

    def test_001_uses_sh_prefix(self):
        assert self._f('000001') == 'sh000001'

    def test_688_uses_sh_prefix(self):
        assert self._f('000688') == 'sh000688'

    def test_399006_uses_sz_prefix(self):
        """创业板指 399006 应使用 sz 前缀"""
        assert self._f('399006') == 'sz399006'

    def test_300_code_uses_sz_prefix(self):
        """300xxx 系列也使用 sz 前缀"""
        assert self._f('300999') == 'sz300999'
