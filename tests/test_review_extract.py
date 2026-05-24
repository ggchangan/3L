"""
Phase 3: generate_review_data 数据加载/扫描模块测试
"""

import pytest

# ═══════════════════════════════════════════════════════════════════
# 1. load_review_data — 加载持仓+扫描结果
# ═══════════════════════════════════════════════════════════════════

class TestLoadReviewData:
    """加载复盘基础数据"""

    def test_empty_holdings_file_returns_empty(self):
        """holdings.json 不存在时返回空列表"""
        from generate_review_data import load_review_data
        holdings, buy_signals, _ = load_review_data(
            date_str='2026-05-22',
            existing={'holdings': [], 'buy_signals': []},
            ww_dir='/tmp/nonexistent',
            latest_scan_path='/tmp/nonexistent/scan.json',
        )
        assert holdings == []
        assert buy_signals == []

    def test_uses_existing_as_fallback(self):
        """holdings.json 有问题时用 existing 数据"""
        from generate_review_data import load_review_data
        holdings, buy_signals, _ = load_review_data(
            date_str='2026-05-22',
            existing={'holdings': [{'code': '000001', 'name': '平安'}], 'buy_signals': [{'code': '000001'}]},
            ww_dir='/tmp/nonexistent',
            latest_scan_path='/tmp/nonexistent/scan.json',
        )
        assert len(holdings) >= 1
        # 至少拿到 existing 中的持仓


# ═══════════════════════════════════════════════════════════════════
# 2. scan_buy_signals_if_needed — 全量扫描买点
# ═══════════════════════════════════════════════════════════════════

class TestScanBuySignalsIfNeeded:
    """买点信号扫描"""

    def test_returns_existing_if_not_empty(self):
        """buy_signals 非空 → 不扫描，直接返回"""
        from generate_review_data import scan_buy_signals_if_needed
        result, stocks = scan_buy_signals_if_needed(
            buy_signals=[{'code': '000001', 'name': '平安'}],
            all_stocks_60d={},
            date_str='2026-05-22',
            ww_dir='/tmp',
            all_stocks_path='/tmp/nonexistent.json',
            mainline_data={'lines': []},
            market_cycle={},
            wl_func=lambda: [],
        )
        assert len(result) == 1

    def test_empty_signals_stays_empty(self):
        """buy_signals 为空且无数据源 → 空列表"""
        from generate_review_data import scan_buy_signals_if_needed
        result, stocks = scan_buy_signals_if_needed(
            buy_signals=[],
            all_stocks_60d=None,
            date_str='2026-05-22',
            ww_dir='/tmp',
            all_stocks_path='/tmp/nonexistent.json',
            mainline_data={'lines': []},
            market_cycle={},
            wl_func=lambda: [],
        )
        assert result == []
