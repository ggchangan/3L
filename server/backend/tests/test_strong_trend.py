"""强势趋势追踪 — 单元测试"""
import sys, os, json
from unittest.mock import patch, MagicMock

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── 模拟数据 ──

def _make_sector_daily():
    """生成模拟板块K线数据"""
    import datetime
    base = datetime.date(2026, 5, 1)
    industries = {}
    for name, base_close in [('元件', 5000), ('半导体', 4800), ('电力', 4600),
                               ('消费电子', 4400), ('银行', 4200), ('煤炭', 4000),
                               ('化学制药', 3800), ('通信设备', 3600)]:
        klines = []
        for i in range(60):
            d = (base + datetime.timedelta(days=i)).strftime('%Y%m%d')
            # 元件涨幅最大，半导体次之
            factor = 1.0 + (i / 59) * 0.24 if name == '元件' else 1.0 + (i / 59) * 0.06
            price = base_close * factor
            klines.append({'date': d, 'open': price, 'close': price, 'high': price, 'low': price, 'volume': 100000})
        industries[name] = klines

    # 5日涨幅高的板块（近5天突然涨）
    for name, base_close in [('自动化设备', 4200), ('光学光电子', 4000)]:
        klines = []
        for i in range(60):
            d = (base + datetime.timedelta(days=i)).strftime('%Y%m%d')
            # 前55天平，后5天暴涨
            if i < 55:
                factor = 1.0
            else:
                factor = 1.0 + ((i - 54) / 5) * 0.08  # 5日涨8%
            price = base_close * factor
            klines.append({'date': d, 'open': price, 'close': price, 'high': price, 'low': price, 'volume': 100000})
        industries[name] = klines

    concepts = {}
    for name, base_close in [('国家大基金持股', 5000), ('先进封装', 4800)]:
        klines = []
        for i in range(60):
            d = (base + datetime.timedelta(days=i)).strftime('%Y%m%d')
            factor = 1.0 + (i / 59) * 0.17 if name == '国家大基金持股' else 1.0 + (i / 59) * 0.15
            price = base_close * factor
            klines.append({'date': d, 'open': price, 'close': price, 'high': price, 'low': price, 'volume': 100000})
        concepts[name] = klines

    return {'last_updated': '20260603', 'industries': industries, 'concepts': concepts}

def _make_reverse_industry_map():
    """生成模拟行业反向索引 {行业名: [股票code]}"""
    return {
        '元件': ['000725', '002049', '600171', '300666', '688012'],
        '半导体': ['002371', '688981', '600703', '300661', '688126'],
        '自动化设备': ['300124', '688017', '002747'],
        '光学光电子': ['002456', '000050'],
    }

def _make_stock_klines(code, base_close=50.0, trend='up'):
    """生成个股K线（60天），trend=up为上涨趋势"""
    import datetime
    base = datetime.date(2026, 5, 1)
    klines = []
    for i in range(60):
        d = (base + datetime.timedelta(days=i)).strftime('%Y%m%d')
        if trend == 'up':
            price = base_close * (1.0 + (i / 59) * 0.15)
        elif trend == 'flat':
            price = base_close * (1.0 + 0.02 * (i / 59 - 0.5))
        else:  # down
            price = base_close * (1.0 - (i / 59) * 0.10)

        # 调整日（模拟浅调整）
        if i >= 55 and trend == 'up':
            price *= 0.98  # 近期一个2%的回调

        klines.append({
            'date': d, 'open': price, 'close': price,
            'high': price * 1.01, 'low': price * 0.99,
            'volume': 100000 + (i % 5) * 10000
        })
    return klines

def _make_all_stocks():
    """生成模拟个股K线数据"""
    stocks = {}
    codes_data = {
        '000725': (18.5, 'up', '元件'),
        '002049': (85.0, 'up', '元件'),
        '600171': (22.0, 'up', '元件'),
        '300666': (68.0, 'up', '元件'),
        '688012': (95.0, 'up', '元件'),
        '002371': (320.0, 'up', '半导体'),
        '688981': (75.0, 'up', '半导体'),
        '600703': (28.0, 'up', '半导体'),
        '300661': (180.0, 'up', '半导体'),
        '688126': (45.0, 'up', '半导体'),
        '300124': (65.0, 'up', '自动化设备'),
        '688017': (150.0, 'up', '自动化设备'),
        '002747': (35.0, 'up', '自动化设备'),
        # 非强势板块股
        '000001': (10.0, 'flat', '银行'),
        '600036': (35.0, 'down', '银行'),
    }
    for code, (base_close, trend, industry) in codes_data.items():
        stocks[code] = _make_stock_klines(code, base_close, trend)
    return stocks


class TestStrongTrendService:
    """强势趋势追踪 — 服务层测试"""

    def test_get_top_sectors_20d(self):
        """20日涨幅TOP N包含涨幅较高的板块"""
        from backend.services.strong_trend_service import get_top_sectors
        sd = _make_sector_daily()
        industries = sd['industries']

        result = get_top_sectors(industries, window_days=20, top_n=3)
        # 自动化设备和光学光电子在最后20日涨幅最高（之前平的，后5天暴涨8%）
        assert len(result) <= 3
        assert len(result) > 0
        assert result[0][1] >= 5.0  # 第一名至少5%以上

    def test_get_top_sectors_5d(self):
        """5日涨幅TOP N包含刚启动板块"""
        from backend.services.strong_trend_service import get_top_sectors
        sd = _make_sector_daily()
        industries = sd['industries']

        result = get_top_sectors(industries, window_days=5, top_n=3)
        # 自动化设备和光学光电子5日涨幅最高
        names = [r[0] for r in result]
        assert '自动化设备' in names
        assert '光学光电子' in names

    def test_score_stock_bullish(self):
        """上涨趋势股评分为正"""
        from backend.services.strong_trend_service import score_stock
        klines = _make_stock_klines('000725', 18.5, 'up')
        result = score_stock(klines)
        assert result['ema_alignment'] == 'bullish'
        assert result['score'] >= 5.0

    def test_score_stock_flat(self):
        """下跌趋势股评分低于上涨股"""
        from backend.services.strong_trend_service import score_stock
        up_klines = _make_stock_klines('000725', 18.5, 'up')
        down_klines = _make_stock_klines('600036', 35.0, 'down')
        up_result = score_stock(up_klines)
        down_result = score_stock(down_klines)
        assert up_result['score'] > down_result['score']

    def test_score_stock_down(self):
        """下跌趋势股的评分最低"""
        from backend.services.strong_trend_service import score_stock
        klines = _make_stock_klines('600036', 35.0, 'down')
        result = score_stock(klines)
        assert result['ema_alignment'] != 'bullish'
        assert result['score'] <= 6.0

    @patch('backend.services.stock_card_service.get_stock_card')
    @patch('backend.services.strong_trend_service.get_stock_concepts')
    @patch('backend.services.strong_trend_service.get_stock_industry')
    @patch('backend.services.strong_trend_service.load_sector_daily')
    @patch('threel_core.db.query_stock_klines')
    @patch('backend.services.strong_trend_service._load_industry_map')
    def test_full_pipeline(self, mock_imap, mock_db_klines, mock_sector,
                           mock_industry, mock_concepts, mock_card):
        """完整筛选流程返回正确格式"""
        from backend.services.strong_trend_service import get_strong_trend_candidates

        # 模拟行业映射 {code: {ths_industry: 行业名}}
        rev = _make_reverse_industry_map()
        imap = {}
        for ind, codes in rev.items():
            for code in codes:
                imap[code] = {'code': code, 'name': code, 'ths_industry': ind}
        mock_imap.return_value = imap

        # 模拟DB批量K线查询（返回 {带后缀code: [klines]}）
        all_stocks = _make_all_stocks()
        db_result = {}
        for code, kls in all_stocks.items():
            suffix = f'{code}.SH' if code.startswith('6') else f'{code}.SZ'
            db_result[suffix] = kls
        mock_db_klines.return_value = db_result

        mock_sector.return_value = _make_sector_daily()
        # 模拟个股行业归属
        def _mock_industry(code):
            rev = _make_reverse_industry_map()
            for ind, codes in rev.items():
                if code in codes:
                    return ind
            return ''
        mock_industry.side_effect = _mock_industry
        # 模拟个股概念归属：都返回空
        mock_concepts.return_value = []
        # 模拟 get_stock_card 返回信号数据
        def _mock_card(code, date_str, klines=None, **kwargs):
            ind = _mock_industry(code)
            has_signal = ind in ('元件', '半导体', '自动化设备')
            return {
                'signal': 'buy' if has_signal else 'hold',
                'signal_text': '量价配合良好' if has_signal else '',
                'buy_point': '突破买点' if has_signal else '',
                'stop_loss': 45.0,
                'stop_loss_pct': 5.2,
                'trading_system': '3l',
                'triggered_signals': [],
                'fusion_type': '',
                'mainline_level': '主线' if has_signal else '',
                'conclusion': '趋势健康，持有区' if has_signal else '数据不足',
            }
        mock_card.side_effect = _mock_card

        result = get_strong_trend_candidates(top_industries=3, hot_industries=2,
                                              top_concepts=1, hot_concepts=1, limit=10)
        assert 'date' in result
        assert 'top_industries' in result
        assert 'hot_industries' in result
        assert 'candidates' in result
        assert len(result['candidates']) > 0
        # 检查返回格式
        c = result['candidates'][0]
        assert 'code' in c
        assert 'name' in c
        assert 'score' in c
        assert 'score_breakdown' in c
        assert 'sectors' in c
        assert 'trend_metrics' in c
        assert 'adjustment_quality' in c
        # 检查信号字段
        assert 'signal' in c
        assert 'buy_point' in c
        assert 'stop_loss' in c
        assert 'stop_loss_pct' in c
        assert 'trading_system' in c
        assert 'mainline_level' in c
        assert 'conclusion' in c
        assert c['signal'] in ('buy', 'hold', 'sell')
        assert c['trading_system'] in ('3l', 'trend')
        # 强势板块股应有 buy 信号
        buy_candidates = [x for x in result['candidates'] if x['signal'] == 'buy']
        assert len(buy_candidates) > 0, '至少有一个buy信号'
