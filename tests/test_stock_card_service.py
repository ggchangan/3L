"""Tests for StockCardService — 硬编码K线数据，所有依赖mock，不碰生产数据"""
import pytest
import os, sys, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _make_klines(closes, dates=None, vol_base=1000):
    """从收盘价列表生成标准K线"""
    klines = []
    for i, c in enumerate(closes):
        klines.append({
            'date': (dates[i] if dates else f'2026{i//30+3:02d}{i%30+1:02d}'),
            'open': float(c - c * 0.006),
            'close': float(c),
            'high': float(c + c * 0.014),
            'low': float(c - c * 0.01),
            'volume': int(vol_base * (0.9 + 0.2 * (i % 5))),
            'name': '测试股',
        })
    return klines


# ── 测试数据 ──
_UPTREND = [100 + i * 0.8 for i in range(60)]           # 上涨趋势 100→148
_DOWNTREND = [100 - i * 0.5 for i in range(60)]         # 下降趋势 100→70
_RANGE = [100 + (i % 10) * 2 for i in range(60)]        # 区间震荡 100~118
_SMOOTH = [100 + i * 1.2 for i in range(60)]            # 平滑上涨趋势
_DATES = [f'2026{i//30+3:02d}{i%30+1:02d}' for i in range(60)]


class TestAnalyzeStructure:
    """_analyze_structure — 只依赖 klines/ema_utils，不需要mock"""

    def test_uptrend(self):
        from services.stock_card_service import _analyze_structure
        klines = _make_klines(_UPTREND, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '上涨趋势'
        assert 'stage' in r
        assert 'ema' in r

    def test_downtrend(self):
        from services.stock_card_service import _analyze_structure
        klines = _make_klines(_DOWNTREND, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '下降趋势'

    def test_range(self):
        from services.stock_card_service import _analyze_structure
        klines = _make_klines(_RANGE, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '区间震荡'


class TestDecideTradingSystem:
    """_decide_trading_system — mock manual_trend_stocks.json"""

    def _patch_manual(self, codes_set):
        """创建临时 manual_trend_stocks.json 并patch"""
        import services.stock_card_service as scs
        # 保存原路径
        self._orig_path = scs.MANUAL_TREND_PATH
        # 创建临时文件
        self._tmp = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json')
        json.dump(list(codes_set), self._tmp)
        self._tmp.close()
        scs.MANUAL_TREND_PATH = self._tmp.name
        # 清除缓存
        scs._manual_trend_cache = None

    def _restore(self):
        import services.stock_card_service as scs
        scs.MANUAL_TREND_PATH = self._orig_path
        scs._manual_trend_cache = None
        os.unlink(self._tmp.name)

    def test_trend_stock(self):
        self._patch_manual({'000001'})
        try:
            from services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000001')
            assert result == 'trend'
        finally:
            self._restore()

    def test_3l_stock(self):
        self._patch_manual({'000002'})
        try:
            from services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000003')
            assert result == '3l'
        finally:
            self._restore()

    def test_empty_manual_list(self):
        self._patch_manual(set())
        try:
            from services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000001')
            assert result == '3l'
        finally:
            self._restore()


class TestCalcStopLoss:
    """_calc_stop_loss — 只依赖 klines，不需要mock"""

    def test_uptrend_stop_loss(self):
        from services.stock_card_service import _calc_stop_loss
        klines = _make_klines(_UPTREND, _DATES)
        sl, pct = _calc_stop_loss(klines, len(klines) - 1)
        assert sl is not None
        assert sl > 0
        assert pct is not None and pct > 0

    def test_short_data_returns_none(self):
        from services.stock_card_service import _calc_stop_loss
        klines = _make_klines([100, 101, 102])
        sl, pct = _calc_stop_loss(klines, len(klines) - 1)
        assert sl is None


class TestBuildConclusion:
    """_build_conclusion — 纯逻辑，不需要mock"""

    def test_3l_buy_conclusion(self):
        from services.stock_card_service import _build_conclusion
        card = {
            'signal': 'buy',
            'trading_system': '3l',
            'buy_point': '突破买点',
            'stage': '上行',
            'stop_loss': 95.0,
            'stop_loss_pct': 5.0,
        }
        c = _build_conclusion(card)
        assert '突破买点' in c
        assert '止损' in c

    def test_trend_buy_conclusion(self):
        from services.stock_card_service import _build_conclusion
        card = {
            'signal': 'buy',
            'trading_system': 'trend',
            'trend_bias': 1.5,
            'buy_point': 'BIAS5乖离率买入',
            'stage': '上行',
            'stop_loss': 95.0,
            'stop_loss_pct': 5.0,
        }
        c = _build_conclusion(card)
        assert 'BIAS5' in c
        assert '买入区' in c

    def test_hold_conclusion(self):
        from services.stock_card_service import _build_conclusion
        card = {
            'signal': 'hold',
            'trading_system': '3l',
            'structure': '上涨趋势',
            'stage': '上行',
        }
        c = _build_conclusion(card)
        assert '上行' in c

    def test_sell_conclusion(self):
        from services.stock_card_service import _build_conclusion
        card = {
            'signal': 'sell',
            'trading_system': '3l',
            'structure': '下降趋势',
            'stage': '下行',
        }
        c = _build_conclusion(card)
        assert '下降' in c or '下行' in c


class TestGetStockCardIntegration:
    """get_stock_card 集成测试 — mock 外部依赖"""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, monkeypatch, tmp_path):
        """mock data_layer + manual_trend_stocks.json + 外部服务"""
        import services.stock_card_service as scs

        # mock manual_trend_stocks.json
        self._manual_file = tmp_path / 'manual_trend.json'
        json.dump([], open(self._manual_file, 'w'))
        self._orig_manual_path = scs.MANUAL_TREND_PATH
        scs.MANUAL_TREND_PATH = str(self._manual_file)
        scs._manual_trend_cache = None

        # mock data_layer: get_stock_klines
        def mock_get_stock_klines(code, direction=None, stocks=None):
            """返回硬编码的上涨趋势数据"""
            return _make_klines(_UPTREND, _DATES)

        # mock get_industry_map
        def mock_get_industry_map():
            return {'000001': {'name': '测试股', 'ths_industry': '半导体'}}

        monkeypatch.setattr('services.stock_card_service.get_stock_klines', mock_get_stock_klines)
        monkeypatch.setattr('services.stock_card_service.get_industry_map', mock_get_industry_map)

        yield

        scs.MANUAL_TREND_PATH = self._orig_manual_path
        scs._manual_trend_cache = None

    def test_basic_card_has_required_fields(self):
        """基本卡片包含所有前端必填字段"""
        from services.stock_card_service import get_stock_card

        card = get_stock_card(
            code='000001',
            date_str='20260920',
            market_position='波中',
            main_lines=[],
        )

        assert card is not None
        assert card['code'] == '000001'
        assert card['name'] == '测试股'
        assert card['sector'] == '半导体'
        assert card['structure'] is not None
        assert card['stage'] is not None
        assert card['signal'] in ('buy', 'hold', 'sell')
        assert card['trading_system'] in ('3l', 'trend')
        assert 'price' in card
        assert 'change' in card
        assert 'conclusion' in card

    def test_trend_stock_uses_trend_system(self):
        """手动指定趋势股 → trading_system='trend', signal=buy"""
        import services.stock_card_service as scs
        json.dump(['000001'], open(self._manual_file, 'w'))
        scs._manual_trend_cache = None

        card = scs.get_stock_card(
            code='000001',
            date_str='20260920',
        )
        assert card['trading_system'] == 'trend'
        assert card['signal'] in ('buy', 'hold')

    def test_3l_stock_uses_3l_system(self):
        """非趋势股 → trading_system='3l'"""
        import services.stock_card_service as scs
        json.dump([], open(self._manual_file, 'w'))
        scs._manual_trend_cache = None

        card = scs.get_stock_card(
            code='000001',
            date_str='20260920',
        )
        assert card['trading_system'] == '3l'
