"""
Phase 1: generate_review_data.py 现有纯函数测试

TDD 第一步：先测试现有行为，再重构。
覆盖：
  - to_yyyymmdd()          字符串日期格式化
  - is_trading_day()        交易日判断（含fallback）
  - generate_trading_plan() 交易计划生成（纯）
  - get_buy_sell_signals()  买卖信号提取
"""

import pytest
from unittest.mock import patch, MagicMock

# ═══════════════════════════════════════════════════════════════════
# to_yyyymmdd
# ═══════════════════════════════════════════════════════════════════

class TestToYyyymmdd:
    def test_already_yyyy_mm_dd(self):
        from generate_review_data import to_yyyymmdd
        assert to_yyyymmdd('2026-05-24') == '2026-05-24'

    def test_slash_format(self):
        from generate_review_data import to_yyyymmdd
        assert to_yyyymmdd('2026/05/24') == '2026-05-24'

    def test_empty_string(self):
        from generate_review_data import to_yyyymmdd
        assert to_yyyymmdd('') == ''

    def test_none_input(self):
        from generate_review_data import to_yyyymmdd
        assert to_yyyymmdd(None) == ''

    def test_whitespace_stripped(self):
        from generate_review_data import to_yyyymmdd
        assert to_yyyymmdd(' 2026-05-24 ') == '2026-05-24'


# ═══════════════════════════════════════════════════════════════════
# is_trading_day
# ═══════════════════════════════════════════════════════════════════

class TestIsTradingDay:
    """测试 is_trading_day — 可观测行为测试"""

    def test_known_sunday_is_not_trading_day(self):
        """2026-05-24 是周日 → 非交易日"""
        from generate_review_data import is_trading_day
        result = is_trading_day('2026-05-24')
        assert result is False

    def test_known_friday_is_trading_day(self):
        """2026-05-22 是周五 → 交易日"""
        from generate_review_data import is_trading_day
        result = is_trading_day('2026-05-22')
        assert result is True

    def test_saturday_is_not_trading_day(self):
        """2026-05-23 是周六 → 非交易日"""
        from generate_review_data import is_trading_day
        result = is_trading_day('2026-05-23')
        assert result is False


# ═══════════════════════════════════════════════════════════════════
# generate_trading_plan — 纯函数，无需mock
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_market_cycle():
    return {
        'position': '波中偏下',
        'strategy': '谨慎交易',
        'position_pct': '六至七成',
        'build_per_stock_pct': 5,
    }

@pytest.fixture
def sample_mainline_data():
    return {
        'lines': [
            {'name': '半导体', 'chg_20d': 12.5},
            {'name': '算力', 'chg_20d': 8.3},
        ]
    }

@pytest.fixture
def sample_signals_data():
    return {'stocks': {'stocks': []}, 'holdings': [], 'buy_signals': []}

@pytest.fixture
def sample_holdings_review():
    return [
        {'code': '300750', 'name': '宁德时代', 'signal': 'hold', 'stage': '加速', 'structure': '上涨趋势'},
        {'code': '688981', 'name': '中芯国际', 'signal': 'buy', 'stage': '缩量整理', 'structure': '区间震荡', 'buy_point': '突破'},
    ]


class TestGenerateTradingPlan:
    def test_returns_expected_structure(self, sample_market_cycle, sample_mainline_data,
                                        sample_signals_data, sample_holdings_review):
        """交易计划返回标准dict结构"""
        from generate_review_data import generate_trading_plan
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data,
            [],  # existing_holdings
            holdings_review=sample_holdings_review,
        )
        assert isinstance(result, dict)
        assert 'overall_strategy' in result
        assert 'position_level' in result
        assert 'main_lines' in result
        assert 'holdings_action' in result
        assert 'buy_priority' in result
        assert 'risk_items' in result

    def test_main_lines_from_input(self, sample_market_cycle, sample_mainline_data,
                                    sample_signals_data):
        """主线方向来自 mainline_data"""
        from generate_review_data import generate_trading_plan
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data, [],
        )
        assert len(result['main_lines']) == 2
        assert '半导体' in result['main_lines'][0]

    def test_position_detail_based_on_cycle(self, sample_market_cycle, sample_mainline_data,
                                            sample_signals_data):
        """仓位说明基于大盘位置"""
        from generate_review_data import generate_trading_plan
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data, [],
        )
        assert '波中偏下' in result['position_detail']

    def test_buy_signal_creates_action(self, sample_market_cycle, sample_mainline_data,
                                       sample_signals_data, sample_holdings_review):
        """买点信号生成可执行操作项"""
        from generate_review_data import generate_trading_plan
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data, [],
            holdings_review=sample_holdings_review,
        )
        actions = [a for a in result['holdings_action'] if '执行' in a.get('action', '')]
        assert len(actions) >= 1

    def test_holdings_action_priority_sell_highest(self, sample_market_cycle, sample_mainline_data,
                                                   sample_signals_data):
        """卖出信号优先级标记为'高'"""
        from generate_review_data import generate_trading_plan
        holdings = [
            {'code': '000001', 'name': '平安银行', 'signal': 'sell',
             'stage': '转弱', 'structure': '下降趋势'},
        ]
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data, [],
            holdings_review=holdings,
        )
        sell_actions = [a for a in result['holdings_action'] if a.get('action') == '卖出']
        assert len(sell_actions) == 1
        assert sell_actions[0]['priority'] == '高'

    def test_empty_holdings_no_actions(self, sample_market_cycle, sample_mainline_data,
                                       sample_signals_data):
        """空持仓 → 无个股操作建议"""
        from generate_review_data import generate_trading_plan
        result = generate_trading_plan(
            sample_market_cycle, sample_mainline_data, sample_signals_data, [],
        )
        assert result['holdings_action'] == []


# ═══════════════════════════════════════════════════════════════════
# get_buy_sell_signals
# ═══════════════════════════════════════════════════════════════════

class TestGetBuySellSignals:
    """get_buy_sell_signals 返回 (signals, cache, bs_by_code) 三元组"""

    def test_returns_tuple(self):
        """返回的是三元组"""
        from generate_review_data import get_buy_sell_signals
        holdings = [{'code': '300750', 'direction': '新能源',
                      'name': '宁德时代', 'price': 180.0}]
        buy_signals = [{'code': '688981', 'name': '中芯国际',
                        'price': 85.0, 'signal_type': '突破'}]
        result = get_buy_sell_signals(holdings, buy_signals, date_str='2026-05-22')
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_first_element_has_holdings_and_signals(self):
        """第一元素包含 holdings 和 signals 键"""
        from generate_review_data import get_buy_sell_signals
        result = get_buy_sell_signals([], [], date_str='2026-05-22')
        signals = result[0]
        assert 'holdings' in signals
        assert 'signals' in signals
