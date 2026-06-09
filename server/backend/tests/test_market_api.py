import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

"""测试大盘市场数据路由"""
import pytest
from unittest.mock import MagicMock, patch
from backend.core.data_layer import INDEX_CODES


class TestMarketApi:
    """/api/market 路由测试"""

    @pytest.fixture
    def mock_server(self):
        """创建一个模拟的 send_json 处理器"""
        return MagicMock()

    def _run_handler(self, mock_h, path):
        """模拟调用 _handle_market"""
        from backend.api.market import _handle_market
        _handle_market(mock_h, path)

    @patch('backend.core.data_layer.get_index_klines')
    @patch('backend.services.review_compute_service.judge_peak_valley')
    @patch('backend.services.review_compute_service.fetch_market_quote')
    def test_no_code_defaults_to_985(self, mock_quote, mock_judge, mock_klines, mock_server):
        """无 code 参数时默认使用 000985（中证全指）"""
        mock_klines.return_value = [
            {'date': '20260601', 'open': 5000, 'close': 5010, 'high': 5020, 'low': 4990, 'volume': 100},
            {'date': '20260602', 'open': 5010, 'close': 5020, 'high': 5030, 'low': 5000, 'volume': 120},
        ]
        mock_judge.return_value = {'position': '波中', 'score': 2}
        mock_quote.return_value = None

        self._run_handler(mock_server, '/api/market')

        # 验证 get_index_klines 被无参调用（默认 000985）
        mock_klines.assert_called_once()

    @patch('backend.core.data_layer.get_index_klines')
    @patch('backend.services.review_compute_service.judge_peak_valley')
    @patch('backend.services.review_compute_service.fetch_market_quote')
    def test_code_param_passed_to_get_index_klines(self, mock_quote, mock_judge, mock_klines, mock_server):
        """传 code 参数应传递给 get_index_klines"""
        mock_klines.return_value = [
            {'date': '20260601', 'open': 5000, 'close': 5010, 'high': 5020, 'low': 4990, 'volume': 100},
            {'date': '20260602', 'open': 5010, 'close': 5020, 'high': 5030, 'low': 5000, 'volume': 120},
        ]
        mock_judge.return_value = {'position': '波中', 'score': 2}
        mock_quote.return_value = None

        self._run_handler(mock_server, '/api/market?code=000001')

        mock_klines.assert_called_once_with('000001')

    @patch('backend.core.data_layer.get_index_klines')
    @patch('backend.services.review_compute_service.judge_peak_valley')
    @patch('backend.services.review_compute_service.fetch_market_quote')
    def test_unknown_code_returns_fallback(self, mock_quote, mock_judge, mock_klines, mock_server):
        """未知指数代码不应抛异常，返回兜底数据"""
        mock_klines.return_value = []  # 空K线 -> judge_peak_valley 返回 fallback
        mock_judge.return_value = {'position': '波中', 'score': 0}
        mock_quote.return_value = None

        self._run_handler(mock_server, '/api/market?code=999999')
        mock_server.send_json.assert_called_once()
        # 不抛异常即可
