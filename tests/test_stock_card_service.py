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
        from backend.services.stock_card_service import _analyze_structure
        klines = _make_klines(_UPTREND, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '上涨趋势'
        assert 'stage' in r
        assert 'ema' in r

    def test_downtrend(self):
        from backend.services.stock_card_service import _analyze_structure
        klines = _make_klines(_DOWNTREND, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '下降趋势'

    def test_range(self):
        from backend.services.stock_card_service import _analyze_structure
        klines = _make_klines(_RANGE, _DATES)
        r = _analyze_structure(klines, len(klines) - 1)
        assert r['structure'] == '区间震荡'


class TestDecideTradingSystem:
    """_decide_trading_system — mock manual_trend_stocks.json"""

    def _patch_manual(self, codes_set):
        """创建临时 manual_trend_stocks.json 并patch"""
        from backend.services import stock_card_service as scs
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
        from backend.services import stock_card_service as scs
        scs.MANUAL_TREND_PATH = self._orig_path
        scs._manual_trend_cache = None
        os.unlink(self._tmp.name)

    def test_trend_stock(self):
        self._patch_manual({'000001'})
        try:
            from backend.services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000001')
            assert result == 'trend'
        finally:
            self._restore()

    def test_3l_stock(self):
        self._patch_manual({'000002'})
        try:
            from backend.services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000003')
            assert result == '3l'
        finally:
            self._restore()

    def test_empty_manual_list(self):
        self._patch_manual(set())
        try:
            from backend.services.stock_card_service import _decide_trading_system
            result = _decide_trading_system('000001')
            assert result == '3l'
        finally:
            self._restore()


class TestCalcStopLoss:
    """_calc_stop_loss — 只依赖 klines，不需要mock"""

    def test_uptrend_stop_loss(self):
        from backend.services.stock_card_service import _calc_stop_loss
        klines = _make_klines(_UPTREND, _DATES)
        sl, pct = _calc_stop_loss(klines, len(klines) - 1)
        assert sl is not None
        assert sl > 0
        assert pct is not None and pct > 0

    def test_short_data_returns_none(self):
        from backend.services.stock_card_service import _calc_stop_loss
        klines = _make_klines([100, 101, 102])
        sl, pct = _calc_stop_loss(klines, len(klines) - 1)
        assert sl is None


class TestBuildConclusion:
    """_build_conclusion — 纯逻辑，不需要mock"""

    def test_3l_buy_conclusion(self):
        from backend.services.stock_card_service import _build_conclusion
        card = {
            'signal': 'buy',
            'trading_system': '3l',
            'buy_point': '突破买点',
            'stage': '上行',
            'stop_loss': 97.0,
            'stop_loss_pct': 3.0,
        }
        c = _build_conclusion(card)
        assert '突破买点' in c
        assert '止损' in c

    def test_trend_buy_conclusion(self):
        from backend.services.stock_card_service import _build_conclusion
        card = {
            'signal': 'buy',
            'trading_system': 'trend',
            'trend_bias': 1.5,
            'buy_point': 'BIAS5乖离率买入',
            'stage': '上行',
            'stop_loss': 97.0,
            'stop_loss_pct': 3.0,
        }
        c = _build_conclusion(card)
        assert 'BIAS5' in c
        assert '买入区' in c

    def test_hold_conclusion(self):
        from backend.services.stock_card_service import _build_conclusion
        card = {
            'signal': 'hold',
            'trading_system': '3l',
            'structure': '上涨趋势',
            'stage': '上行',
        }
        c = _build_conclusion(card)
        assert '上行' in c

    def test_sell_conclusion(self):
        from backend.services.stock_card_service import _build_conclusion
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
        from backend.services import stock_card_service as scs

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

        # mock _ALL_A_STOCKS（name 来源）
        monkeypatch.setattr(scs, '_ALL_A_STOCKS', {'000001': '测试股'})
        monkeypatch.setattr('backend.services.stock_card_service.get_stock_klines', mock_get_stock_klines)
        monkeypatch.setattr('backend.services.stock_card_service.get_industry_map', mock_get_industry_map)

        yield

        scs.MANUAL_TREND_PATH = self._orig_manual_path
        scs._manual_trend_cache = None

    def test_basic_card_has_required_fields(self):
        """基本卡片包含所有前端必填字段"""
        from backend.services.stock_card_service import get_stock_card

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

    def test_new_fields_added(self):
        """卡片包含新增的通用字段：date/ema5/ema10/vol_ratio/deviation_pct"""
        from backend.services.stock_card_service import get_stock_card
        card = get_stock_card(code='000001', date_str='20260920')
        assert card['date'] == '20260920'
        assert card['ema5'] is not None
        assert card['ema10'] is not None
        assert card['vol_ratio'] >= 0
        assert isinstance(card['deviation_pct'], (int, float))

    def test_trend_stock_uses_trend_system(self):
        """手动指定趋势股 → trading_system='trend', signal=buy"""
        from backend.services import stock_card_service as scs
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
        from backend.services import stock_card_service as scs
        json.dump([], open(self._manual_file, 'w'))
        scs._manual_trend_cache = None

        card = scs.get_stock_card(
            code='000001',
            date_str='20260920',
        )
        assert card['trading_system'] == '3l'

    def test_empty_card_all_fields(self):
        """_empty_card 包含所有卡片字段"""
        from backend.services.stock_card_service import _empty_card
        card = _empty_card('000001', '测试', '半导体', 'AI', '数据不足')
        assert card['code'] == '000001'
        assert card['name'] == '测试'
        assert card['sector'] == '半导体'
        assert card['direction'] == 'AI'
        assert card['conclusion'] == '数据不足'
        # 所有数值字段有默认值
        assert card['ema5'] is None
        assert card['ema10'] is None
        assert card['ema20'] is None
        assert card['ema30'] is None
        assert card['vol_ratio'] == 0
        assert card['deviation_pct'] == 0
        assert card['stop_loss'] is None
        assert card['stop_loss_pct'] is None

    def test_get_stock_card_insufficient_data(self):
        """K线不足30条 → 返回空卡片"""
        from backend.services.stock_card_service import get_stock_card
        # mock klines 返回不足30条
        from backend.services import stock_card_service as scs
        def mock_short_klines(code, direction=None, stocks=None):
            return [{'date': '20260920', 'close': 100, 'volume': 1000}]
        import pytest
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr('backend.services.stock_card_service.get_stock_klines', mock_short_klines)
        try:
            card = get_stock_card(code='000001', date_str='20260920')
            assert card['code'] == '000001'
            assert card['structure'] == '--'
            assert card['trading_reason'] == '数据不足'
        finally:
            monkeypatch.undo()

    def test_get_stock_card_with_external_klines(self):
        """传入外部 klines → 优先使用，不走 data_layer"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES

        klines = _make_klines(_UPTREND, _DATES)
        card = get_stock_card(
            code='999999',
            date_str='20260920',
            klines=klines,
        )
        assert card['code'] == '999999'
        assert card['structure'] == '上涨趋势'
        assert card['stage'] != '--'
        assert card['price'] > 0

    def test_get_stock_card_with_downtrend_klines(self):
        """下降趋势K线 → structure=下降趋势, signal=sell"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _DOWNTREND, _DATES
        klines = _make_klines(_DOWNTREND, _DATES)
        card = get_stock_card(code='999999', date_str='20260920', klines=klines)
        assert card['structure'] == '下降趋势'
        assert card['signal'] == 'sell'

    def test_get_stock_card_with_range_klines(self):
        """区间震荡K线 → structure=区间震荡"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _RANGE, _DATES
        klines = _make_klines(_RANGE, _DATES)
        card = get_stock_card(code='999999', date_str='20260920', klines=klines)
        assert card['structure'] == '区间震荡'

    def test_get_stock_card_with_direction(self):
        """传入 direction → card['direction'] 正确"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES
        klines = _make_klines(_UPTREND, _DATES)
        card = get_stock_card(
            code='999999', date_str='20260920',
            direction='AI应用', klines=klines,
        )
        assert card['direction'] == 'AI应用'
        # 没有行业映射时 sector 取 direction
        assert card['sector'] == 'AI应用'

    def test_get_stock_card_with_mainlines_struct(self):
        """main_lines 传 dict 格式（含 lines/secondary）"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES
        klines = _make_klines(_UPTREND, _DATES)
        card = get_stock_card(
            code='999999', date_str='20260920',
            klines=klines,
            main_lines={'lines': [{'name': '半导体'}], 'secondary': []},
        )
        assert card['trading_system'] in ('3l', 'trend')

    def test_get_stock_card_with_mainlines_list(self):
        """main_lines 传 list 格式（字符串列表）"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES
        klines = _make_klines(_UPTREND, _DATES)
        # 带 sector=半导体 则 klines 需要传给 card，但卡片的 sector 来自 klines
        # 用不存在的 direction 测试
        card = get_stock_card(
            code='999999', date_str='20260920',
            klines=klines,
            main_lines=['半导体', '算力'],
        )
        assert card['trading_system'] in ('3l', 'trend')

    def test_build_tags(self):
        """_build_tags 正确生成标签"""
        from backend.services.stock_card_service import _build_tags
        tags = _build_tags({'profit_model1': True, 'trend_stock': False})
        assert '盈利1' in tags[0] if tags else True

        tags2 = _build_tags({'profit_model1': True, 'trend_stock': True})
        assert len(tags2) == 2
        assert '盈利1' in tags2[0]
        assert '趋势' in tags2[1]

        tags3 = _build_tags({'profit_model1': False, 'trend_stock': False})
        assert tags3 == []

    def test_get_stock_card_ema_fields(self):
        """卡片 ema5/10/20/30 数值合理"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES
        klines = _make_klines(_UPTREND, _DATES)
        card = get_stock_card(code='999999', date_str='20260920', klines=klines)
        assert card['ema5'] is not None and card['ema5'] > 0
        assert card['ema10'] is not None and card['ema10'] > 0
        assert card['ema20'] is not None and card['ema20'] > 0
        assert card['ema30'] is not None and card['ema30'] > 0
        # ema5 应接近收盘价
        assert abs(card['ema5'] - card['price']) / card['price'] < 0.1

    def test_external_klines_overrides_all_stocks_for_detect_buy_point(self, monkeypatch):
        """外部传实时K线时，all_stocks中对应股票的K线被覆盖，detect_buy_point用实时K线"""
        from backend.services.stock_card_service import get_stock_card
        from tests.test_stock_card_service import _make_klines, _UPTREND, _DATES

        # 模拟 get_all_stocks 返回旧数据（低成交量）
        old_klines = _make_klines(_UPTREND, _DATES, vol_base=100)
        old_klines[-1]['volume'] = 500  # 旧数据：最后一根成交量很低

        def mock_get_all_stocks():
            return {'半导体': {'999999': old_klines}, '其他': {}}

        monkeypatch.setattr(
            'backend.core.data_layer.get_all_stocks',
            mock_get_all_stocks
        )

        # 模拟 detect_buy_point，捕获传进来的 all_stocks
        captured = {}

        def mock_detect_buy_point(code, date_str, all_stocks, **kwargs):
            captured['all_stocks'] = all_stocks
            captured['code'] = code
            return None  # 不返回买点，只验证数据传进去了

        monkeypatch.setattr(
            'backend.services.stock_card_service.detect_buy_point',
            mock_detect_buy_point
        )

        # 外部传入实时K线（高预估成交量）
        realtime_klines = _make_klines(_UPTREND, _DATES, vol_base=8000)
        realtime_klines[-1]['volume'] = 15000000  # 实时：最后一根高成交量

        card = get_stock_card(
            code='999999', date_str='20260920',
            klines=realtime_klines,
            main_lines=[],
        )

        # 验证 all_stocks 中 '999999' 的K线已被实时K线覆盖
        assert 'all_stocks' in captured
        target_stock_klines = None
        for sec, stocks in captured['all_stocks'].items():
            if '999999' in stocks:
                target_stock_klines = stocks['999999']
                break
        assert target_stock_klines is not None, 'all_stocks 中应有 999999'
        # 使用最后一根成交量判断：实时K线的高成交量应覆盖旧数据的低成交量
        assert target_stock_klines[-1]['volume'] == 15000000, \
            'all_stocks 中的K线应为外部传入的实时K线（高成交量），而非旧数据（低成交量）'
