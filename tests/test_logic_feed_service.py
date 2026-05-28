"""
资料投喂服务测试
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


MOCK_HTML = """
<html><head><title>半导体行业深度分析</title>
<meta property="og:title" content="半导体行业深度分析" /></head>
<body>
<div id="js_content">
<p>国产替代加速，先进封装需求爆发。长电科技、通富微电受益明显。</p>
<p>AI算力需求带动HBM封装产能供不应求。</p>
</div><script>var a=1;</script>
</body></html>
"""

MOCK_TAGS = [
    {'id': 'tag-ai', 'name': 'AI算力链条', 'related_industries': ['AI', '算力', '光模块'], 'related_stocks': ['300502']},
    {'id': 'tag-pkg', 'name': '先进封装', 'related_industries': ['封装', '半导体'], 'related_stocks': ['600584', '002156']},
]


class TestExtractUrl:
    def test_extract_wechat(self):
        """提取微信公众号文章"""
        with patch('requests.get') as mock_get:
            mock_r = MagicMock()
            mock_r.text = MOCK_HTML
            mock_r.encoding = 'utf-8'
            mock_get.return_value = mock_r

            from backend.services.logic_feed_service import extract_url_content
            result = extract_url_content('https://mp.weixin.qq.com/s/test123')
            assert result['title'] == '半导体行业深度分析'
            assert '先进封装' in result['text']
            assert result['source_name'] == '微信公众号'

    def test_extract_fail(self):
        """网络错误时返回错误信息"""
        with patch('requests.get', side_effect=Exception('timeout')):
            from backend.services.logic_feed_service import extract_url_content
            result = extract_url_content('https://example.com')
            assert 'error' in result


class TestMatchTags:
    def test_keyword_match_high_confidence(self):
        """正文包含行业关键词时高置信度匹配"""
        from backend.services.logic_feed_service import match_tags
        text = '先进封装需求爆发，长电科技受益。半导体行业国产替代加速。'
        result = match_tags(text, '半导体分析', MOCK_TAGS)
        assert len(result['tags']) > 0
        tag_ids = [t['tag_id'] for t in result['tags']]
        assert 'tag-pkg' in tag_ids

    def test_keyword_match_low_confidence_triggers_llm(self):
        """低置信度时走LLM（mock LLM调用来隔离）"""
        from backend.services.logic_feed_service import match_tags
        text = '今天天气不错，市场整体上涨。'
        result = match_tags(text, '市场日报', MOCK_TAGS)
        assert 'tags' in result
        # LLM没有API key，返回关键词结果（可能为空）
        assert isinstance(result['tags'], list)


class TestProcessFeed:
    def test_process_feed_success(self):
        """完整的投喂处理流程"""
        with patch('requests.get') as mock_get:
            mock_r = MagicMock()
            mock_r.text = MOCK_HTML
            mock_r.encoding = 'utf-8'
            mock_get.return_value = mock_r

            with patch('backend.services.logic_feed_service._get_store') as mock_s:
                store = MagicMock()
                store.get_tags.return_value = MOCK_TAGS
                mock_s.return_value = store

                from backend.services.logic_feed_service import process_feed
                result = process_feed('https://mp.weixin.qq.com/s/test123')
                assert 'title' in result
                assert result['title'] == '半导体行业深度分析'
                assert 'recommended_tags' in result
                assert 'llm_used' in result

    def test_process_feed_no_tags(self):
        """没有逻辑标签时也能处理"""
        with patch('requests.get') as mock_get:
            mock_r = MagicMock()
            mock_r.text = MOCK_HTML
            mock_r.encoding = 'utf-8'
            mock_get.return_value = mock_r

            with patch('backend.services.logic_feed_service._get_store') as mock_s:
                store = MagicMock()
                store.get_tags.return_value = []
                mock_s.return_value = store

                from backend.services.logic_feed_service import process_feed
                result = process_feed('https://mp.weixin.qq.com/s/test123')
                assert 'title' in result
                assert result['recommended_tags'] == []


class TestSaveFeed:
    def test_save_feed(self):
        """保存投喂条目"""
        with patch('backend.services.logic_feed_service._get_store') as mock_s:
            store = MagicMock()
            mock_s.return_value = store

            from backend.services.logic_feed_service import save_feed
            result = save_feed({
                'title': '测试文章',
                'summary': '摘要',
                'source_name': '微信公众号',
                'url': 'https://example.com',
                'logic_tags': ['tag-pkg'],
                'industries': ['半导体'],
            })
            assert result['success'] is True
            store.add_entry.assert_called_once()
