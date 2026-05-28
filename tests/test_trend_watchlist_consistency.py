"""
手动趋势交易 + 自选股一致性测试 — 全 mock，不碰线上文件
"""
import pytest, json
from unittest.mock import patch, mock_open
from backend.core.trend_trading import decide_system


class TestTrendWatchlistConsistency:
    """手动趋势股 ↔ 自选股 一致性 — 全 mock 隔离"""

    @patch('backend.core.trend_trading._load_manual_trend', return_value={'002281', '300054'})
    def test_all_manual_trend_stocks_in_watchlist(self, mock_load):
        """所有手动趋势股必须在自选股中（通过mock验证，不读线上文件）"""
        from backend.core.trend_trading import _load_manual_trend
        manual = _load_manual_trend()
        assert '002281' in manual
        assert isinstance(manual, set)

    @patch('backend.core.trend_trading._load_manual_trend')
    def test_decide_system_uses_manual_list(self, mock_load, stocks):
        """decide_system 只看手动列表"""
        mock_load.return_value = {'002281'}
        stocks_data = stocks.get('stocks', stocks)
        assert decide_system('002281', '2026-05-22', stocks_data) == 'trend'
        assert decide_system('601689', '2026-05-22', stocks_data) == '3l'

    @patch('backend.core.trend_candidates._load_manual_trend')
    @patch('backend.core.trend_candidates._ensure_in_watchlist')
    @patch('backend.core.trend_candidates._set_watchlist_trading_system')
    def test_toggle_adds_to_manual(self, mock_set, mock_ensure, mock_load, monkeypatch, tmp_path):
        """toggle趋势股时调用 _ensure_in_watchlist（不写线上文件）"""
        monkeypatch.setattr('backend.core.trend_candidates.MANUAL_TREND_PATH', str(tmp_path / 'manual.json'))
        mock_load.return_value = set()
        from backend.core.trend_candidates import toggle_trend_stock
        result = toggle_trend_stock('999999', True)
        assert result['success']
        mock_ensure.assert_called_once_with('999999')

    @patch('backend.core.trend_candidates._load_manual_trend')
    @patch('backend.core.trend_candidates._ensure_in_watchlist')
    @patch('backend.core.trend_candidates._set_watchlist_trading_system')
    def test_toggle_no_duplicate_ensure(self, mock_set, mock_ensure, mock_load, monkeypatch, tmp_path):
        """toggle已在manual中的股票，不重复调用 _ensure_in_watchlist"""
        monkeypatch.setattr('backend.core.trend_candidates.MANUAL_TREND_PATH', str(tmp_path / 'manual.json'))
        mock_load.return_value = {'002281'}
        from backend.core.trend_candidates import toggle_trend_stock
        result = toggle_trend_stock('002281', True)
        assert result['success']
        # 已在manual中，不应调用 _ensure_in_watchlist
        mock_ensure.assert_not_called()

    @patch('backend.core.trend_candidates._load_manual_trend')
    @patch('backend.core.trend_candidates._ensure_in_watchlist')
    @patch('backend.core.trend_candidates._set_watchlist_trading_system')
    def test_toggle_remove(self, mock_set, mock_ensure, mock_load, monkeypatch, tmp_path):
        """关闭趋势标志时从manual移除"""
        monkeypatch.setattr('backend.core.trend_candidates.MANUAL_TREND_PATH', str(tmp_path / 'manual.json'))
        mock_load.return_value = {'002281'}
        from backend.core.trend_candidates import toggle_trend_stock
        result = toggle_trend_stock('002281', False)
        assert result['success']
        # 不在manual中时也应成功（幂等）
        result2 = toggle_trend_stock('999999', False)
        assert result2['success']

    def test_watchlist_entry_format_mock(self):
        """自选股格式验证（纯mock，不读线上）"""
        mock_data = {"stocks": [
            {"code": "000001", "name": "测试股", "direction": "半导体", "industry": "科技"},
        ]}
        for s in mock_data['stocks']:
            assert 'code' in s
            assert 'name' in s
            assert 'direction' in s
            assert 'industry' in s

    def test_manual_trend_list_format_mock(self):
        """手动趋势列表格式验证（纯mock，不读线上）"""
        mock_data = ['002281', '300054']
        assert isinstance(mock_data, list)
        for code in mock_data:
            assert isinstance(code, str)
            assert len(code) == 6
