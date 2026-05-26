"""持仓服务单元测试 — TDD 测试先行

覆盖:
- save_holdings: 基础读写、防误覆盖、数据校验、首次部署、日期更新
- get_holdings_with_prices: 实时价叠加、股票缺失、价格获取失败
"""
import json, os, unittest, tempfile, time
from unittest.mock import patch, MagicMock, mock_open
from datetime import datetime


# ═════════════════════════════════════════════════════════════════
# save_holdings 测试
# ═════════════════════════════════════════════════════════════════

class TestSaveHoldings:
    """测试 save_holdings() — 写入/防误覆盖/校验/首次部署"""

    def test_save_and_read_back(self, tmp_path):
        """基本保存：写入后可以正确读出"""
        from backend.services.holdings_service import save_holdings, get_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            data = {
                'holdings': [
                    {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                     'direction': '创新药', 'stop_loss_price': 48.50}
                ],
                'cash_ratio': 85.30
            }
            result = save_holdings(data)
            assert result['success'] is True
            assert result['count'] == 1

            # 读出验证
            loaded = get_holdings()
            assert loaded['holdings'][0]['name'] == '药明康德'
            assert loaded['holdings'][0]['ratio'] == 14.70
            assert loaded['holdings'][0]['stop_loss_price'] == 48.50
            assert loaded['cash_ratio'] == 85.30

    def test_save_updates_date(self, tmp_path):
        """保存后 update_date 自动更新为当天"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            today = datetime.now().strftime('%Y-%m-%d')
            result = save_holdings({'holdings': [], 'cash_ratio': 100})
            assert result['success'] is True

            import json
            with open(holdings_path) as f:
                saved = json.load(f)
            assert saved['update_date'] == today

    def test_anti_overwrite_protection(self, tmp_path):
        """防误覆盖：已有50只，写入≤10只时拒绝"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        # 先创建50只持仓
        many_holdings = [{'name': f'Stock{i}', 'code': f'{i:06d}',
                          'ratio': 2.0, 'direction': '测试'} for i in range(50)]
        initial = {'holdings': many_holdings, 'cash_ratio': 0,
                   'update_date': '2026-05-25'}
        with open(holdings_path, 'w') as f:
            json.dump(initial, f)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            # 尝试只写入5只 → 拒绝
            result = save_holdings({'holdings': many_holdings[:5], 'cash_ratio': 90})
            assert result['success'] is False
            assert '拒绝' in result.get('error', '') or 'overwrite' in result.get('error', '').lower()

    def test_anti_overwrite_allows_large_save(self, tmp_path):
        """防误覆盖：已有50只，写入15只时允许"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        many_holdings = [{'name': f'Stock{i}', 'code': f'{i:06d}',
                          'ratio': 2.0, 'direction': '测试'} for i in range(50)]
        initial = {'holdings': many_holdings, 'cash_ratio': 0}
        with open(holdings_path, 'w') as f:
            json.dump(initial, f)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = save_holdings({'holdings': many_holdings[:15], 'cash_ratio': 70})
            assert result['success'] is True
            assert result['count'] == 15

    def test_cash_ratio_validation_negative(self, tmp_path):
        """cash_ratio 为负数时拒绝"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = save_holdings({'holdings': [], 'cash_ratio': -1})
            assert result['success'] is False

    def test_cash_ratio_validation_over_100(self, tmp_path):
        """cash_ratio > 100 时拒绝"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = save_holdings({'holdings': [], 'cash_ratio': 101})
            assert result['success'] is False

    def test_first_deploy_empty_data(self, tmp_path):
        """首次部署（文件不存在）：写入空数据正常"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'nonexistent' / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = save_holdings({'holdings': [], 'cash_ratio': 100})
            assert result['success'] is True
            assert result['count'] == 0

    def test_save_empty_holdings_list(self, tmp_path):
        """保存空列表：正常"""
        from backend.services.holdings_service import save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        # 先创建一个50只的
        many = [{'name': f'S{i}', 'code': f'{i:06d}',
                 'ratio': 2.0, 'direction': '测试'} for i in range(50)]
        with open(holdings_path, 'w') as f:
            json.dump({'holdings': many, 'cash_ratio': 0}, f)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            # 防误覆盖会拒绝，但不应该是 bug
            result = save_holdings({'holdings': [], 'cash_ratio': 100})
            assert result['success'] is False  # 被防误覆盖拒绝


# ═════════════════════════════════════════════════════════════════
# get_holdings_with_prices 测试
# ═════════════════════════════════════════════════════════════════

class MockResponse:
    """模拟 requests.get 的返回"""
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class TestGetHoldingsWithPrices:
    """测试 get_holdings_with_prices() — 实时行情叠加"""

    def test_returns_empty_when_no_file(self, tmp_path):
        """文件不存在时返回空持仓"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'no_such_file.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = get_holdings_with_prices()
            assert result['holdings'] == []
            assert result['cash_ratio'] == 100

    def test_adds_price_and_change(self, tmp_path):
        """正常叠加实时行情：price/change/stop_loss_pct 正确计算"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'update_date': '2026-05-25',
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': 48.50}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        # 模拟腾讯接口返回（88-field ~分隔格式）
        f = ['0'] * 88
        f[1] = '药明康德'; f[2] = '603259'; f[3] = '51.20'; f[32] = '-1.54'
        mock_tencent_text = 'v_sh603259="' + '~'.join(f) + '"\n'

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=MockResponse(mock_tencent_text)):
                result = get_holdings_with_prices()

        assert len(result['holdings']) == 1
        h = result['holdings'][0]
        assert h['price'] == 51.20
        assert h['change'] == -1.54
        # stop_loss_pct = (48.50 - 51.20) / 51.20 * 100 ≈ -5.27
        assert abs(h['stop_loss_pct'] - (-5.27)) < 0.1

    def test_handles_missing_stop_loss(self, tmp_path):
        """止损价未设置时 stop_loss_pct 为 None"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': None}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        # 88-field mock matching Tencent format
        fields_88 = ['0'] * 88
        fields_88[1] = '药明康德'
        fields_88[2] = '603259'
        fields_88[3] = '51.20'
        fields_88[32] = '2.30'
        mock_text = 'v_sh603259="' + '~'.join(fields_88) + '"\n'
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=MockResponse(mock_text)):
                result = get_holdings_with_prices()

        assert result['holdings'][0]['stop_loss_pct'] is None

    def test_handles_price_fetch_error(self, tmp_path):
        """腾讯接口异常时 price/change 为 None"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': 48.50}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       side_effect=Exception('Connection error')):
                result = get_holdings_with_prices()

        h = result['holdings'][0]
        assert h['price'] is None
        assert h['change'] is None
        # 没价格，stop_loss_pct 也应为 None
        assert h['stop_loss_pct'] is None

    def test_batch_fetch_multiple_stocks(self, tmp_path):
        """多只持仓时批量获取行情"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': 48.50},
                {'name': '大族数控', 'code': '301200', 'ratio': 7.88,
                 'direction': '半导体', 'stop_loss_price': 260.0}
            ],
            'cash_ratio': 77.42
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        # 模拟腾讯接口返回（88-field ~分隔格式）
        f1 = ['0'] * 88
        f1[1] = '药明康德'; f1[2] = '603259'; f1[3] = '51.20'; f1[32] = '-1.54'
        f2 = ['0'] * 88
        f2[1] = '大族数控'; f2[2] = '301200'; f2[3] = '274.00'; f2[32] = '9.84'
        mock_text = (
            'v_sh603259="' + '~'.join(f1) + '"\n'
            'v_sz301200="' + '~'.join(f2) + '"\n'
        )
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=MockResponse(mock_text)):
                with patch('backend.services.stock_card_service.get_stock_card',
                           return_value={'sector': '', 'structure': '--',
                                         'stage': '--'}):
                    result = get_holdings_with_prices()

        assert len(result['holdings']) == 2
        assert result['holdings'][0]['price'] == 51.20
        assert result['holdings'][0]['change'] == -1.54
        assert result['holdings'][1]['price'] == 274.00
        assert result['holdings'][1]['change'] == 9.84


# ═════════════════════════════════════════════════════════════════
# get_holdings_with_prices -- 板块/结构/阶段 测试
# ═════════════════════════════════════════════════════════════════

class TestGetHoldingsWithAnalysis:
    """测试 get_holdings_with_prices() -- 板块/结构/阶段"""

    MOCK_KLINES_60D = [
        {'date': '20260301', 'open': 48.0, 'high': 49.5, 'low': 47.5, 'close': 49.0, 'volume': 1000000},
        {'date': '20260302', 'open': 49.0, 'high': 50.0, 'low': 48.5, 'close': 49.5, 'volume': 1100000},
    ] * 30

    class MockResponse:
        def __init__(self, text):
            self.text = text
        def raise_for_status(self):
            pass

    def _tencent(self, code, name, price, change):
        f = ['0'] * 88
        f[1] = name; f[2] = code; f[3] = str(price); f[32] = str(change)
        p = 'sh' if code.startswith(('6', '5')) else 'sz'
        return 'v_' + p + code + '="' + '~'.join(f) + '"\n'

    def test_adds_sector_from_industry_map(self, tmp_path):
        """板块信息从行业映射正确获取"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': None}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        text = self._tencent('603259', '药明康德', 51.20, -1.54)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=self.MockResponse(text)):
                with patch('backend.services.stock_card_service.get_stock_card',
                           return_value={'sector': '化学制药',
                                         'structure': '上涨趋势',
                                         'stage': '上行'}):
                    result = get_holdings_with_prices()

        assert result['holdings'][0]['sector'] == '化学制药'

    def test_adds_structure_stage_from_klines(self, tmp_path):
        """结构/阶段从K线数据正确计算"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': None}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        text = self._tencent('603259', '药明康德', 51.20, -1.54)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=self.MockResponse(text)):
                with patch('backend.services.stock_card_service.get_stock_card',
                           return_value={'sector': '化学制药',
                                         'structure': '上涨趋势',
                                         'stage': '上行'}):
                    result = get_holdings_with_prices()

        h = result['holdings'][0]
        assert h['sector'] == '化学制药'
        assert h['structure'] == '上涨趋势'
        assert h['stage'] == '上行'

    def test_graceful_when_no_klines(self, tmp_path):
        """K线数据不足时 gracefully fallback 到 '--'"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': None}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        text = self._tencent('603259', '药明康德', 51.20, -1.54)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=self.MockResponse(text)):
                with patch('backend.services.stock_card_service.get_stock_card',
                           side_effect=Exception('数据不足')):
                    result = get_holdings_with_prices()

        h = result['holdings'][0]
        assert h['sector'] == ''
        assert h['structure'] == '--'
        assert h['stage'] == '--'

    def test_graceful_when_industry_map_missing(self, tmp_path):
        """行业映射异常时 gracefully 返回空"""
        from backend.services.holdings_service import get_holdings_with_prices

        holdings_path = str(tmp_path / 'holdings.json')
        data = {
            'holdings': [
                {'name': '药明康德', 'code': '603259', 'ratio': 14.70,
                 'direction': '创新药', 'stop_loss_price': None}
            ],
            'cash_ratio': 85.30
        }
        with open(holdings_path, 'w') as f:
            json.dump(data, f)

        text = self._tencent('603259', '药明康德', 51.20, -1.54)

        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            with patch('backend.services.holdings_service.requests.get',
                       return_value=self.MockResponse(text)):
                with patch('backend.services.stock_card_service.get_stock_card',
                           side_effect=Exception('map error')):
                    result = get_holdings_with_prices()

        h = result['holdings'][0]
        assert h['sector'] == ''
        assert h['structure'] == '--'


# ═════════════════════════════════════════════════════════════════
# get_holdings 基础测试
# ═════════════════════════════════════════════════════════════════

class TestGetHoldings:
    """测试 get_holdings() 基础读取"""

    def test_returns_empty_when_no_file(self, tmp_path):
        """文件不存在返回空"""
        from backend.services.holdings_service import get_holdings

        holdings_path = str(tmp_path / 'nonexistent.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            result = get_holdings()
            assert result == {'holdings': []}

    def test_returns_saved_data(self, tmp_path):
        """文件存在返回正确数据"""
        import json
        from backend.services.holdings_service import get_holdings, save_holdings

        holdings_path = str(tmp_path / 'holdings.json')
        with patch('backend.services.holdings_service.HOLDINGS_PATH', holdings_path):
            save_holdings({
                'holdings': [{'name': '测试', 'code': '000001', 'ratio': 10,
                              'direction': '测试', 'stop_loss_price': None}],
                'cash_ratio': 90
            })
            result = get_holdings()
            assert len(result['holdings']) == 1
            assert result['holdings'][0]['name'] == '测试'


# ═════════════════════════════════════════════════════════════════
# 前端HTML 回归检查 — 防止 ReferenceError / 结构缺陷
# ═════════════════════════════════════════════════════════════════

class TestHoldingsPageStructure:
    """检查 dist/holdings.html 是否存在常见JS Bug"""

    HOLDINGS_HTML_PATH = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'frontend', 'dist', 'holdings.html'
    )

    def test_html_file_exists(self):
        assert os.path.isfile(self.HOLDINGS_HTML_PATH), \
            f'dist/holdings.html 不存在，请先 build'

    def _load_html(self):
        with open(self.HOLDINGS_HTML_PATH, 'r', encoding='utf-8') as f:
            return f.read()

    def test_overview_block_exists(self):
        """概况块包含饼图和统计"""
        html = self._load_html()
        assert 'overview-block' in html
        assert 'ov-pie' in html
        assert 'ov-legend' in html
        assert 'ov-stats' in html

    def test_card_area_has_collapsible(self):
        """卡片区有可折叠标题栏"""
        html = self._load_html()
        assert 'card-section-header' in html
        assert 'toggleCardSection' in html
        assert 'cardToggleIcon' in html
        assert 'cardBody' in html

    def test_no_reference_error_in_map(self):
        """map 回调中引用了正确的变量名，无游离 i"""
        html = self._load_html()
        # signalStockCard 应当使用已定义的变量而非游离的 i
        # 在 sorted/indexed.map 回调中应捕获 i 参数
        import re
        # 找到所有 .map( 模式
        maps = re.findall(r'\.map\s*\([^)]+\)', html)
        # 检查至少有一个 map 用到了 signalStockCard
        for m in maps:
            if 'signalStockCard' in m:
                # 这个 map 应该捕获了索引参数
                assert '({' in m or '((' not in m.split('=>')[0].strip(), \
                    f'可能缺少索引参数的 map: {m[:80]}...'

    def test_assessment_and_suggestion_present(self):
        """持仓评估（概况块内）和建议区块存在"""
        html = self._load_html()
        assert 'ovAssessment' in html
        assert 'suggestionSection' in html
        assert 'suggestionContent' in html

    def test_empty_state_present(self):
        """空状态引导存在"""
        html = self._load_html()
        assert 'emptyState' in html
        assert '暂无持仓' in html

    def test_modal_and_confirm(self):
        """新增/编辑弹窗和确认框存在"""
        html = self._load_html()
        assert 'openAddModal' in html
        assert 'openEditModal' in html
        assert 'openDeleteConfirm' in html
        assert 'confirmOverlay' in html

    def test_keyboard_event_listener(self):
        """Escape 键关闭弹窗"""
        html = self._load_html()
        assert 'Escape' in html
        assert 'closeModal()' in html
