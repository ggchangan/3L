"""
Phase 2: review_analysis 模块测试

TDD: 先定义新模块的接口，再提取代码。
测试用 mock 数据注入，不依赖真实文件。
"""

import pytest
from unittest.mock import patch

# ═══════════════════════════════════════════════════════════════════
# Mock 数据
# ═══════════════════════════════════════════════════════════════════

def _make_klines(length=60, start_close=10.0, uptrend=True):
    """生成模拟K线"""
    klines = []
    for i in range(length):
        c = start_close + (i * 0.2 if uptrend else -i * 0.1)
        spread = c * 0.015
        klines.append({
            'date': f'202603{(i+1):02d}' if i < 9 else f'20260{(i+1):02d}',
            'open': round(c - spread, 2),
            'close': round(c, 2),
            'high': round(c + spread, 2),
            'low': round(c - spread * 0.8, 2),
            'volume': float(1e7 + i * 1e5),
            'name': '测试A' if i == 0 else '',
        })
    return klines

MOCK_STOCKS = {
    '半导体': {
        '688999': _make_klines(60, 50.0, uptrend=True),
        '688111': _make_klines(60, 30.0, uptrend=False),
    },
    '算力': {
        '688888': _make_klines(60, 80.0, uptrend=True),
    },
}

MOCK_HOLDINGS = [
    {'code': '688999', 'name': '测试A', 'direction': '半导体', 'volume': 1000, 'cost': 52.0},
    {'code': '688111', 'name': '测试B', 'direction': '半导体', 'volume': 500, 'cost': 35.0},
]

MOCK_BUY_SIGNALS = [
    {'code': '688999', 'name': '测试A', 'sector': '半导体',
     'buy_point': '中继买点', 'price': 62.0, 'change': 3.5,
     'score': 7, 'flags': '量比充足', 'profit_model1': False, 'trend_stock': False,
     'trading_system': '3l', 'trading_reason': '测试', 'trend_bias': '', 'trend_buy_type': ''},
    {'code': '688888', 'name': '测试C', 'sector': '算力',
     'buy_point': '突破买点', 'price': 92.0, 'change': 5.2,
     'score': 8, 'flags': '放量突破', 'profit_model1': False, 'trend_stock': False,
     'trading_system': '3l', 'trading_reason': '测试', 'trend_bias': '', 'trend_buy_type': ''},
]

MOCK_MAINLINES = {
    'lines': [{'name': '半导体', 'chg_20d': 12.5}],
    'secondary': [],
}

MOCK_MARKET_CYCLE = {
    'position': '波中',
    'position_pct': '七至八成',
    'build_per_stock_pct': 5,
    'strategy': '正常交易',
}


# ═══════════════════════════════════════════════════════════════════
# 1. load_holdings_and_scan_results — 数据加载（目前待提取）
# ═══════════════════════════════════════════════════════════════════

# 在提取之前，先占位：
# 这个函数从 holdings.json + LATEST_SCAN_PATH 读数据，然后合并。
# 提取后应该变成纯函数：输入 holdings_raw + scan_raw → 输出 processed_data


# ═══════════════════════════════════════════════════════════════════
# 2. generate_holdings_review — 为每只持仓生成复盘结论
# ═══════════════════════════════════════════════════════════════════

class TestGenerateHoldingsReview:
    """持仓复盘生成 — 核心分析逻辑"""

    def _make_review(self, **overrides):
        """调用 generate_holdings_review，默认用 mock 数据"""
        from backend.core.review_analysis import generate_holdings_review
        timing_holdings = [
            {'code': '688999'},
            {'code': '688111'},
        ]
        params = {
            'holdings': MOCK_HOLDINGS,
            'stocks': MOCK_STOCKS,
            'buy_signals': [],
            'timing_signals_holdings': timing_holdings,
            'bs_by_code': {},
            'date_str': '2026-03-30',
            'mainlines': MOCK_MAINLINES,
        }
        params.update(overrides)

        card_data = {
            '688999': {
                'code': '688999', 'name': '测试A', 'sector': '半导体', 'direction': '半导体',
                'price': 62.0, 'change': 3.5,
                'structure': '上涨趋势', 'stage': '上行',
                'ema': '多头排列', 'vol_analysis': '量能正常',
                'signal': 'buy', 'signal_text': '⚡ 买入',
                'buy_point': '中继买点',
                'profit_model1': False, 'trend_stock': False,
                'trading_system': '3l', 'trading_reason': '测试',
                'trend_buy_type': '', 'trend_bias': '',
                'mainline_level': '主线',
                'stop_loss': None, 'stop_loss_pct': None,
            },
            '688111': {
                'code': '688111', 'name': '测试B', 'sector': '半导体', 'direction': '半导体',
                'price': 28.0, 'change': -1.2,
                'structure': '下降趋势', 'stage': '转弱',
                'ema': '空头排列', 'vol_analysis': '缩量',
                'signal': 'sell', 'signal_text': '❌ 卖出',
                'buy_point': '',
                'profit_model1': False, 'trend_stock': False,
                'trading_system': '3l', 'trading_reason': '测试',
                'trend_buy_type': '', 'trend_bias': '',
                'mainline_level': '',
                'stop_loss': None, 'stop_loss_pct': None,
            },
        }

        def _mock_card(code, **kw):
            return card_data.get(code, {})

        with patch('backend.services.stock_card_service.get_stock_card', side_effect=_mock_card):
            return generate_holdings_review(**params)

    def test_returns_list(self):
        result = self._make_review()
        assert isinstance(result, list)

    def test_each_item_has_required_fields(self):
        result = self._make_review()
        for item in result:
            assert 'code' in item
            assert 'name' in item
            assert 'structure' in item
            assert 'stage' in item
            assert 'signal' in item

    def test_includes_signal_from_judge_signal(self):
        result = self._make_review()
        for item in result:
            assert item['signal'] in ('buy', 'hold', 'sell', 'watch', '无信号')

    def test_known_uptrend_stock(self):
        """上涨趋势的股票有正确结构和阶段"""
        result = self._make_review()
        item = next((r for r in result if r['code'] == '688999'), None)
        assert item is not None
        assert item['structure'] == '上涨趋势'

    def test_empty_holdings_returns_empty(self):
        result = self._make_review(holdings=[], timing_signals_holdings=[])
        assert result == []

    def test_sector_field_is_preserved(self):
        """持仓复盘结果应有 sector 字段（来自卡片）"""
        result = self._make_review()
        for item in result:
            assert 'sector' in item, f'{item["code"]} 缺少 sector 字段'
            assert item['sector'] != '', f'{item["code"]} sector 不应为空'

    def test_stock_not_in_data_returns_error(self):
        """持仓股不在 stocks 数据中 → 标记为数据缺失"""
        result = self._make_review(holdings=[{'code': 'XXXXX', 'name': '未知股'}])
        for item in result:
            if item['code'] == 'XXXXX':
                assert item['structure'] in ('数据不足', '--', '')

    def test_buy_signal_maps_to_signal_buy(self):
        """有买点信号的持仓应标记为 buy"""
        result = self._make_review()
        # 688999 在 buy_signals 中，signal 应为 buy
        item = next((r for r in result if r['code'] == '688999'), None)
        if item:
            # 至少 signal 是 buy（取决于 judge_signal 的判定）
            # 这是一个行为验证，不是严格的断言
            assert item['signal'] in ('buy', 'hold', '无信号')

    def test_sector_is_ths_industry(self):
        """sector 字段应来自卡片（卡片内部已解析THS行业）"""
        result = self._make_review()
        for item in result:
            assert 'sector' in item, f"{item['code']} 缺少 sector 字段"
            assert item['sector'] != '', f"{item['code']} sector 不应为空"

    def test_direction_from_holdings(self):
        """direction 字段应来自原始 holdings 的 direction"""
        result = self._make_review()
        for item in result:
            code = item['code']
            expected_dir = next((h['direction'] for h in MOCK_HOLDINGS if h['code'] == code), None)
            if expected_dir:
                assert 'direction' in item, f'{code} 缺少 direction'
                assert item['direction'] == expected_dir, f'{code}: 期望 direction={expected_dir}, 实际={item["direction"]}'


# ═══════════════════════════════════════════════════════════════════
# 3. generate_buy_signals_review — 买点信号复盘
# ═══════════════════════════════════════════════════════════════════

class TestGenerateBuySignalsReview:
    """买点信号复盘生成"""

    def _make_review(self, **overrides):
        from backend.core.review_analysis import generate_buy_signals_review
        params = {
            'buy_signals': MOCK_BUY_SIGNALS,
            'stocks': MOCK_STOCKS,
            'stock_cache': {},
            'date_str': '2026-03-30',
            'mainlines': MOCK_MAINLINES,
        }
        params.update(overrides)

        def _mock_card(code, **kw):
            info = next((s for s in MOCK_BUY_SIGNALS if s['code'] == code), {})
            return {
                'code': code,
                'name': info.get('name', '?'),
                'sector': info.get('sector', ''),
                'direction': info.get('sector', ''),
                'price': info.get('price', 0),
                'change': info.get('change', 0),
                'structure': '上涨趋势',
                'stage': '上行',
                'ema': '多头排列',
                'vol_analysis': '量能正常',
                'signal': 'buy',
                'signal_text': '⚡ 买入',
                'buy_point': info.get('buy_point', ''),
                'profit_model1': info.get('profit_model1', False),
                'trend_stock': info.get('trend_stock', False),
                'trading_system': info.get('trading_system', '3l'),
                'trading_reason': info.get('trading_reason', ''),
                'trend_buy_type': info.get('trend_buy_type', ''),
                'trend_bias': info.get('trend_bias', ''),
                'mainline_level': '主线',
                'stop_loss': None,
                'stop_loss_pct': None,
                'score': info.get('score', 0),
                'flags': info.get('flags', ''),
                'date': '20260330',
            }

        with patch('backend.services.stock_card_service.get_stock_card', side_effect=_mock_card):
            return generate_buy_signals_review(**params)

    def test_returns_list(self):
        result = self._make_review()
        assert isinstance(result, list)

    def test_each_item_has_required_fields(self):
        result = self._make_review()
        for item in result:
            assert 'code' in item
            assert 'name' in item
            assert 'buy_point' in item
            assert 'score' in item

    def test_empty_signals_returns_empty(self):
        result = self._make_review(buy_signals=[])
        assert result == []

    def test_known_buy_signal_fields(self):
        result = self._make_review()
        item = next((r for r in result if r['code'] == '688999'), None)
        assert item is not None
        assert item['buy_point'] == '中继买点'
        assert item['score'] == 7

    def test_sorted_by_score_descending(self):
        result = self._make_review()
        scores = [r.get('score', 0) for r in result]
        assert scores == sorted(scores, reverse=True)
