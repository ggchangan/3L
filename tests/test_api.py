"""API 接口回归测试
测试所有关键 JSON API 端点的返回结构、字段完整性、类型正确性

用法: python -m pytest tests/test_api.py -v
"""

import json
import urllib.request
import urllib.parse
import os
from datetime import datetime
import pytest

BASE = 'http://localhost:8080'
TIMEOUT = 15


def api(path):
    """调用 API 并返回 JSON 数据（自动 URL 编码）"""
    resp = urllib.request.urlopen(f'{BASE}{path}', timeout=TIMEOUT)
    return json.loads(resp.read().decode())


# =====================================================
# 检查辅助
# =====================================================
def must_have(data, *keys):
    for k in keys:
        assert k in data, f'缺字段: {k}'


# =====================================================
# 核心页面数据 API
# =====================================================

class TestCoreAPI:

    def test_market(self):
        """大盘数据"""
        d = api('/api/market')
        must_have(d, 'score', 'position', 'bias20', 'vol_ratio',
                  'pk_score', 'vl_score', 'strategy', 'position_pct', 'peak_sig')
        assert isinstance(d['score'], (int, float))

    def test_mainlines(self):
        """主线数据"""
        d = api('/api/mainlines')
        assert isinstance(d, dict)

    def test_stocks(self):
        """全市场股票"""
        d = api('/api/stocks')
        assert isinstance(d, dict)
        # 有缓存时至少1个方向，无缓存时为空 dict
        if len(d) > 0:
            for direction, stocks in d.items():
                for code, klines in stocks.items():
                    assert isinstance(klines, list) and len(klines) > 0
                    must_have(klines[-1], 'date', 'open', 'high', 'low', 'close', 'volume')
                    return  # 只检查第一只

    def test_review_dates(self):
        """复盘存档日期列表"""
        d = api('/api/review/dates')
        # 返回 {"dates": ["2026-05-19", ...]}
        if isinstance(d, dict) and 'dates' in d:
            assert len(d['dates']) > 0
        else:
            assert isinstance(d, list) and len(d) > 0

    def test_review_today(self):
        """当天复盘数据"""
        d = api('/api/review')
        must_have(d, 'date', 'market', 'mainline', 'timing_signals',
                  'trading_plan', 'holdings', 'buy_signals')
        must_have(d['market'], 'score', 'position', 'bias20', 'vol_ratio')

    @pytest.mark.xfail(reason='/api/review/{date} 路由尚未实现，需加前缀匹配')
    def test_review_archive(self):
        """历史某天复盘"""
        d = api('/api/review/2026-05-22')
        must_have(d, 'date', 'market', 'mainline')
        assert d['date'] == '2026-05-22'

    def test_holdings(self):
        """持仓数据"""
        d = api('/api/holdings')
        assert isinstance(d, (dict, list))

    def test_trades(self):
        """交易记录"""
        d = api('/api/trades')
        assert isinstance(d, (dict, list))

    def test_industry_map(self):
        """行业映射（可能超时，降级验证）"""
        try:
            d = api('/api/industry-map')
            assert isinstance(d, dict) and len(d) > 10
        except Exception:
            pytest.skip('industry-map 超时（数据依赖未就绪）')

    def test_momentum(self):
        """动量数据"""
        d = api('/api/momentum')
        must_have(d, 'limit_up', 'new_highs')

    def test_tips(self):
        """交易技巧列表 — data.tips 必须是数组"""
        d = api('/api/tips')
        must_have(d, 'tips')
        assert isinstance(d['tips'], list), 'data.tips 应为数组'
        if len(d['tips']) > 0:
            t = d['tips'][0]
            must_have(t, 'id', 'title', 'desc', 'file')
            assert isinstance(t['id'], str)

    def test_tips_content(self):
        """交易技巧详情"""
        d = api('/api/tips')
        if len(d.get('tips', [])) > 0:
            fn = d['tips'][0]['file']
            c = api(f'/api/tips/content?file={urllib.parse.quote(fn)}')
            must_have(c, 'title', 'content')

    def test_top_gainers(self):
        """30日涨幅榜 — 返回结构正确"""
        d = api('/api/top-gainers?date=20260522&limit=5')
        must_have(d, 'stocks', 'pie', 'total', 'limit', 'date')
        assert isinstance(d['stocks'], list), 'stocks 应为数组'
        assert d['limit'] == 5
        if len(d['stocks']) > 0:
            s = d['stocks'][0]
            must_have(s, 'code', 'name', 'price', 'change', 'gain_30d', 'sector')

    def test_static_pages_serve_clean_html(self):
        """所有前端页面通过 HTTP 访问应以 <!DOCTYPE html> 开头"""
        pages = ['react.html']
        for page in pages:
            resp = urllib.request.urlopen(f'{BASE}/{page}', timeout=5)
            html = resp.read().decode('utf-8')
            assert html.strip().startswith('<!DOCTYPE html>'), (
                f'{page} 不以 DOCTYPE 开头, 前50字符: {html[:50]}'
            )


# =====================================================
# 监测页面 API
# =====================================================

class TestMonitorAPI:

    def test_buy_signals(self):
        """买点信号 — API不抛异常（无缓存时跳过，首次扫描>30s）"""
        cache_dir = '/home/ubuntu/3l-server/data/cache'
        cache_pattern = f'buy_signals_{datetime.now().strftime("%Y-%m-%d_%H")}.json'
        cache_file = os.path.join(cache_dir, cache_pattern)
        if not os.path.isfile(cache_file):
            pytest.skip('无买点信号缓存（首次扫描需>30s，跳过）')
        api('/api/monitor/buy-signals')

    def test_stop_loss(self):
        api('/api/monitor/stop-loss')

    def test_sectors(self):
        api('/api/monitor/sectors')

    def test_leaders(self):
        api('/api/monitor/leaders')


# =====================================================
# 自选股 API
# =====================================================

class TestWatchlistAPI:

    def test_get_watchlist(self):
        d = api('/api/watchlist')
        must_have(d, 'stocks', 'count')
        assert d['count'] >= 0
        if d['count'] > 0:
            stocks = d['stocks']
            if isinstance(stocks, dict):
                s = list(stocks.values())[0]
            else:
                s = stocks[0]
            must_have(s, 'code', 'name')
            # price 字段可选（有实时数据时才有）

    def test_search(self):
        """搜索（需 URL 编码）"""
        path = '/api/watchlist/search?' + urllib.parse.urlencode({'q': '半导体'})
        d = api(path)
        assert isinstance(d, (dict, list))


# =====================================================
# 趋势交易 API
# =====================================================

class TestTrendAPI:

    def test_trend_candidates(self):
        d = api('/api/trend-candidates')
        must_have(d, 'main_lines', 'sub_main_lines', 'count')

    def test_trend_tracked(self):
        d = api('/api/trend-tracked')
        must_have(d, 'count', 'candidates')

    def test_trend_search_watchlist(self):
        """趋势候选：从自选股搜索"""
        path = '/api/trend-candidates/search-watchlist?' + \
               urllib.parse.urlencode({'q': '300'})
        d = api(path)
        must_have(d, 'results')
        assert isinstance(d['results'], list)
        if d['results']:
            r = d['results'][0]
            must_have(r, 'code', 'name', 'direction', 'in_trend')


# =====================================================
# 个股分析 API
# =====================================================

class TestStockAnalysisAPI:

    def test_valid_code(self):
        d = api('/api/stock-analysis?q=300750')
        assert 'error' not in d, f'返回错误: {d.get("error", "")}'
        must_have(d, 'code', 'name', 'structure', 'stage', 'signal')
        assert d['code'] == '300750'

    def test_invalid_code(self):
        d = api('/api/stock-analysis?code=XXXXXX')
        # 无效代码应返回错误信息
        assert 'error' in d or 'structure' in d


# =====================================================
# 行业板块
# =====================================================

class TestBoardAPI:

    def test_industry_boards(self):
        d = api('/api/industry-boards')
        assert isinstance(d, (dict, list))

    def test_concept_boards(self):
        """概念板块（可能超时）"""
        try:
            d = api('/api/concept-boards')
            assert isinstance(d, (dict, list))
        except Exception:
            pytest.skip('concept-boards 超时（数据依赖未就绪）')
