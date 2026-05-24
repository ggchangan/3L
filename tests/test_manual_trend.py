"""
手动趋势交易指定测试
"""
import pytest, json, os
from scripts.trend_trading import (
    decide_system, decide_system_with_detail, _load_manual_trend,
)

MANUAL_PATH = '/home/ubuntu/data/3l/private/manual_trend_stocks.json'


class TestManualTrendList:
    """手动趋势股票列表测试"""

    def test_load_manual_list(self):
        """能加载手动列表"""
        result = _load_manual_trend()
        assert isinstance(result, set)
        assert '002281' in result

    def test_trend_stock_returns_trend(self, stocks):
        """在手动列表中的返回trend"""
        stocks_data = stocks.get('stocks', stocks)
        for code in ['002281', '300054', '688698']:
            result = decide_system(code, '2026-05-22', stocks_data)
            assert result == 'trend', f"{code}应为 trend, 实际={result}"

    def test_non_trend_stock_returns_3l(self, stocks):
        """不在手动列表中的返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        for code in ['601689', '301200', '603259', '688126']:
            result = decide_system(code, '2026-05-22', stocks_data)
            assert result == '3l', f"{code}应为 3l, 实际={result}"

    def test_detail_manual_reason(self, stocks):
        """手动指定的detail包含原因"""
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('002281', '2026-05-22', stocks_data)
        assert detail['system'] == 'trend'
        assert '手动指定' in detail['reason']

    def test_detail_3l_reason(self, stocks):
        """非手动指定的detail包含3L原因"""
        stocks_data = stocks.get('stocks', stocks)
        detail = decide_system_with_detail('601689', '2026-05-22', stocks_data)
        assert detail['system'] == '3l'
        assert '默认' in detail['reason']

    def test_unknown_code_returns_3l(self, stocks):
        """不存在的代码返回3l"""
        stocks_data = stocks.get('stocks', stocks)
        result = decide_system('999999', '2026-05-22', stocks_data)
        assert result == '3l'

    def test_add_to_manual_then_trend(self, stocks):
        """往手动列表加股票后变成trend"""
        stocks_data = stocks.get('stocks', stocks)
        # 拓普原本不在列表
        result_before = decide_system('601689', '2026-05-22', stocks_data)
        assert result_before == '3l'
        
        # 临时加进去
        old_data = json.load(open(MANUAL_PATH))
        json.dump(old_data + ['601689'], open(MANUAL_PATH, 'w'))
        
        result_after = decide_system('601689', '2026-05-22', stocks_data)
        assert result_after == 'trend', f"添加后应为trend, 实际={result_after}"
        
        # 恢复
        json.dump(old_data, open(MANUAL_PATH, 'w'))
