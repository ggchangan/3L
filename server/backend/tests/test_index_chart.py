import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

"""测试 generate_index_chart 参数化"""
import pytest


class TestIndexSymbols:
    """INDEX_SYMBOLS 应包含4个指数映射"""

    @pytest.fixture(autouse=True)
    def _import(self):
        from backend.services.stock_chart_service import INDEX_SYMBOLS
        self.symbols = INDEX_SYMBOLS

    def test_has_symbol_for_all_indexes(self):
        assert '000985' in self.symbols
        assert '000001' in self.symbols
        assert '000688' in self.symbols
        assert '399006' in self.symbols

    def test_985_symbol_is_sh(self):
        assert self.symbols['000985'] == 'sh000985'

    def test_001_symbol_is_sh(self):
        assert self.symbols['000001'] == 'sh000001'

    def test_688_symbol_is_sh(self):
        assert self.symbols['000688'] == 'sh000688'

    def test_399006_symbol_is_sz(self):
        assert self.symbols['399006'] == 'sz399006'

    def test_default_code_is_985(self):
        """generate_index_chart 不传 code 时默认 000985"""
        from backend.services.stock_chart_service import INDEX_CODE_CHART
        assert INDEX_CODE_CHART == '000985'
