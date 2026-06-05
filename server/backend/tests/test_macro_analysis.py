"""外围美股映射 — 异动分析API 单元测试"""
import sys, os, pytest
from unittest.mock import patch, MagicMock

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


class TestAnalyzeAbnormal:
    """测试分析API"""

    def test_analyze_returns_expected_fields(self):
        """验证分析API返回正确的字段结构"""
        from backend.services.macro_analysis_service import analyze_us_stock_abnormal

        with patch('backend.services.macro_analysis_service._search_us_stock_news') as mock_search:
            mock_search.return_value = [
                {'time': '2026-06-05 08:00', 'title': '英伟达Q2指引不及预期', 'source': '财联社'},
            ]
            result = analyze_us_stock_abnormal('NVDA', '英伟达', -5.21)

        assert result['success'] is True
        assert result['code'] == 'NVDA'
        assert result['name'] == '英伟达'
        assert result['change_pct'] == -5.21
        assert 'news' in result
        assert 'summary' in result
        assert 'related_a_shares' in result

    def test_analyze_empty_news(self):
        """找不到新闻时也正常返回"""
        from backend.services.macro_analysis_service import analyze_us_stock_abnormal

        with patch('backend.services.macro_analysis_service._search_us_stock_news') as mock_search:
            mock_search.return_value = []
            result = analyze_us_stock_abnormal('NVDA', '英伟达', -5.21)

        assert result['success'] is True
        assert result['news'] == []
        assert '暂无' in result['summary']

    def test_invalid_code_returns_error(self):
        """无效股票代码返回错误"""
        from backend.services.macro_analysis_service import analyze_us_stock_abnormal

        result = analyze_us_stock_abnormal('', '', 0)
        assert result['success'] is False


class TestNewsSearch:
    """测试新闻搜索"""

    @patch('backend.services.macro_analysis_service.requests.get')
    def test_search_returns_articles(self, mock_get):
        """验证新闻搜索能返回文章列表"""
        from backend.services.macro_analysis_service import _search_us_stock_news

        # 模拟东财个股新闻JSONP响应
        mock_resp = MagicMock()
        mock_resp.text = (
            'jQuery_news('
            '{"result": {"cmsArticleWebOld": ['
            '{"title": "英伟达Q2指引不及预期", "date": "2026-06-05 08:00", "mediaName": "财联社", "url": "https://example.com/1"},'
            '{"title": "美国考虑限制AI芯片出口", "date": "2026-06-04 16:00", "mediaName": "路透", "url": "https://example.com/2"}'
            ']}})'
        )
        mock_get.return_value = mock_resp

        articles = _search_us_stock_news('NVDA')
        assert len(articles) == 2
        assert articles[0]['title'] == '英伟达Q2指引不及预期'
        assert articles[0]['source'] == '财联社'
        assert 'url' in articles[0]

    @patch('backend.services.macro_analysis_service.requests.get')
    def test_search_empty_response(self, mock_get):
        """API异常时返回空列表"""
        from backend.services.macro_analysis_service import _search_us_stock_news

        mock_get.side_effect = Exception('API不可用')
        articles = _search_us_stock_news('NVDA')
        assert articles == []
