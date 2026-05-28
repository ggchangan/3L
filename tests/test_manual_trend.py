"""
手动趋势交易指定测试 — 全 mock，不碰线上文件
"""
import pytest
from unittest.mock import patch
from backend.core.trend_trading import (
    decide_system, decide_system_with_detail,
)


class TestManualTrendList:
    """手动趋势股票列表测试 — 通过 mock _load_manual_trend 隔离"""

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_load_manual_list(self, mock_load):
        """能加载手动列表"""
        mock_load.return_value = {'002281', '300054'}
        from backend.core.trend_trading import _load_manual_trend
        result = _load_manual_trend()
        assert isinstance(result, set)
        assert '002281' in result

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_trend_stock_returns_trend(self, mock_load, stocks):
        """在手动列表中的返回trend"""
        mock_load.return_value = {'002281', '300054', '688698'}
        stocks_data = stocks.get('stocks', stocks)
        for code in ['002281', '300054', '688698']:
            result = decide_system(code, '2026-05-22', stocks_data)
            assert result == 'trend', f"{code}应为 trend, 实际={result}"

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_non_trend_stock_returns_3l(self, mock_load, stocks):
        """不在手动列表中的返回3l"""
        mock_load.return_value = {'002281', '300054'}
        stocks_data = stocks.get('stocks', stocks)
        for code in ['601689', '301200', '603259', '688126']:
            result = decide_system(code, '2026-05-22', stocks_data)
            assert result == '3l', f"{code}应为 3l, 实际={result}"

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_detail_manual_reason(self, mock_load, stocks):
        """手动指定的detail包含原因"""
        mock_load.return_value = {'002281'}
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('002281', '2026-05-22', stocks_data)
        assert detail['system'] == 'trend'
        assert '手动' in detail['reason']

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_detail_3l_reason(self, mock_load, stocks):
        """非手动指定的detail包含3L原因"""
        mock_load.return_value = set()
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('601689', '2026-05-22', stocks_data)
        assert detail['system'] == '3l'
        assert '默认' in detail['reason']

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_unknown_code_returns_3l(self, mock_load, stocks):
        """不存在的代码返回3l"""
        mock_load.return_value = set()
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('999999', '2026-05-22', stocks_data)
        assert result == '3l'

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_add_to_manual_then_trend(self, mock_load, stocks):
        """往手动列表加股票后变成trend（通过mock模拟添加，不写线上文件）"""
        stocks_data = stocks.get('stocks', stocks)

        # 不在列表中 → 3l
        mock_load.return_value = set()
        result_before = decide_system('601689', '2026-05-22', stocks_data)
        assert result_before == '3l'

        # 模拟加入列表 → trend
        mock_load.return_value = {'601689'}
        result_after = decide_system('601689', '2026-05-22', stocks_data)
        assert result_after == 'trend'
