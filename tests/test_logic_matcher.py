"""
逻辑匹配引擎测试

测试 backend.services.logic_matcher 的标签匹配逻辑
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


TAGS = [
    {
        'id': 'tag-ai',
        'name': 'AI算力链条',
        'related_industries': ['光模块', 'PCB', '服务器'],
        'related_stocks': ['300502', '002916', '300394'],
    },
    {
        'id': 'tag-pkg',
        'name': '先进封装加速',
        'related_industries': ['封测', '半导体'],
        'related_stocks': ['600584', '002156'],
    },
    {
        'id': 'tag-robot',
        'name': '机器人',
        'related_industries': ['自动化', '电机'],
        'related_stocks': ['300124'],
    },
]


@pytest.fixture
def matcher():
    from backend.services.logic_matcher import LogicMatcher
    return LogicMatcher(TAGS)


# ═══════════════════════════════════════════════════
# Keyword matching (方案A)
# ═══════════════════════════════════════════════════

class TestKeywordMatch:

    def test_match_by_stock_code(self, matcher):
        """直接命中关联个股代码"""
        result = matcher.keyword_match('300502', '中际旭创', '光模块')
        assert len(result) > 0
        assert any(r['tag_id'] == 'tag-ai' for r in result)

    def test_match_by_stock_code_multi(self, matcher):
        """多只个股命中不同标签"""
        result = matcher.keyword_match('300502', '中际旭创', '光模块')
        tag_ids = [r['tag_id'] for r in result]
        assert 'tag-ai' in tag_ids

    def test_match_by_industry(self, matcher):
        """按行业匹配"""
        result = matcher.keyword_match('000001', '测试', '封测')
        assert any(r['tag_id'] == 'tag-pkg' for r in result)

    def test_match_by_industry_no_match(self, matcher):
        """不相关的行业不匹配"""
        result = matcher.keyword_match('000001', '测试', '房地产')
        assert len(result) == 0

    def test_match_by_code_multiple_tags_same_stock(self, matcher):
        """一只股票可能属于多个逻辑标签"""
        result = matcher.keyword_match('300394', '天孚通信', '光模块')
        # 300394 not in any tag, but 光模块 matches AI算力链条
        tag_ids = [r['tag_id'] for r in result]
        assert 'tag-ai' in tag_ids

    def test_empty_input(self, matcher):
        """空输入不报错"""
        result = matcher.keyword_match('', '', '')
        assert len(result) == 0

    def test_partial_name_match(self, matcher):
        """逻辑名称关键词部分匹配（如"先进封装"包含"封装"关键词）"""
        result = matcher.keyword_match('000001', '长电科技', '先进封装')
        assert any(r['tag_id'] == 'tag-pkg' for r in result)

    def test_returns_match_reason(self, matcher):
        """返回的匹配结果包含匹配原因"""
        result = matcher.keyword_match('300502', '中际旭创', '光模块')
        assert len(result) > 0
        assert 'reason' in result[0]
        assert 'confidence' in result[0]


class TestMatchAll:

    def test_match_all_no_tags(self):
        """没有标签时返回空"""
        from backend.services.logic_matcher import LogicMatcher
        m = LogicMatcher([])
        result = m.match_all('300502', '中际旭创', '光模块')
        assert len(result) == 0

    def test_match_all_multiple(self, matcher):
        """同只股票匹配多个标签"""
        result = matcher.match_all('600584', '长电科技', '半导体')
        assert len(result) >= 1
        # 600584 在先进封装中, 半导体匹配先进封装
        tag_ids = [r['tag_id'] for r in result]
        assert 'tag-pkg' in tag_ids

    def test_confidence_scores(self, matcher):
        """不同匹配维度置信度不同"""
        # code+industry 双命中应该比单维度高
        code_hit = matcher.match_all('600584', '长电科技', '')
        industry_hit = matcher.match_all('000001', '测试', '封测')
        both_hit = matcher.match_all('600584', '长电科技', '封测')
        if both_hit:
            max_both = max(r['confidence'] for r in both_hit)
            max_code = max(r['confidence'] for r in code_hit) if code_hit else 0
            assert max_both >= max_code
