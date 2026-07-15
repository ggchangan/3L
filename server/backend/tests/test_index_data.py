import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

"""测试指数数据相关功能"""
import pytest
from backend.data_access.data_layer import INDEX_CODES, INDEX_CODE


class TestIndexCodes:
    """INDEX_CODES 应包含4个指数"""

    def test_contains_all_four_indexes(self):
        assert '000985' in INDEX_CODES  # 中证全指
        assert '000001' in INDEX_CODES  # 上证指数
        assert '000688' in INDEX_CODES  # 科创50
        assert '399006' in INDEX_CODES  # 创业板指

    def test_default_index_is_985(self):
        assert INDEX_CODE == '000985'
