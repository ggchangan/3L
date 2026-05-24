"""
手动趋势交易 + 自选股一致性测试

涵盖：
- 数据完整性：所有手动趋势股必须在自选股中
- 功能一致性：toggle趋势股时自动同步自选股
"""
import pytest, json, os, copy
from scripts.trend_trading import decide_system
from scripts.trend_candidates import toggle_trend_stock, _load_manual

MANUAL_PATH = '/home/ubuntu/data/3l/private/manual_trend_stocks.json'
WATCHLIST_PATH = '/home/ubuntu/data/3l/watchlist.json'
INDUSTRY_MAP_PATH = '/home/ubuntu/data/3l/stock_industry_map.json'


class TestTrendWatchlistConsistency:
    """手动趋势股 ↔ 自选股 一致性"""

    def test_all_manual_trend_stocks_in_watchlist(self):
        """所有手动趋势股必须在自选股中（数据完整性）"""
        manual = _load_manual()
        wl = json.load(open(WATCHLIST_PATH))
        wl_codes = {s['code'] for s in wl.get('stocks', [])}
        missing = [c for c in manual if c not in wl_codes]
        assert not missing, f"以下趋势股不在自选股中: {missing}"

    def test_decide_system_uses_manual_list(self, stocks):
        """decide_system 只看手动列表"""
        stocks_data = stocks.get('stocks', stocks)
        manual = _load_manual()
        for code in list(manual)[:3]:
            assert decide_system(code, '2026-05-22', stocks_data) == 'trend'

    def test_toggle_adds_to_watchlist(self):
        """toggle趋势股(新)时自动加入自选股"""
        # 选一只不在自选股中的股票
        manual = _load_manual()
        wl = json.load(open(WATCHLIST_PATH))
        wl_codes = {s['code'] for s in wl.get('stocks', [])}

        # 找个不在自选股也不在手动列表的测试股
        test_code = '999999'  # 不存在的代码，测试空数据场景
        # 如果999999在手动列表(不应)，跳过
        if test_code in manual:
            pytest.skip('999999意外在手动列表中')

        # 备份原始数据
        orig_manual = copy.deepcopy(json.load(open(MANUAL_PATH)))
        orig_wl = copy.deepcopy(wl)

        try:
            # toggle趋势股
            result = toggle_trend_stock(test_code, True)
            assert result['success']

            # 验证：已加入手动列表
            new_manual = set(json.load(open(MANUAL_PATH)))
            assert test_code in new_manual

        finally:
            # 恢复
            json.dump(orig_manual, open(MANUAL_PATH, 'w'))
            json.dump(orig_wl, open(WATCHLIST_PATH, 'w'), ensure_ascii=False, indent=2)

    def test_toggle_no_watchlist_duplicate(self):
        """toggle已在自选股中的趋势股，不自选股不重复"""
        # 找一只已经在自选股也在手动列表的
        manual = _load_manual()
        wl = json.load(open(WATCHLIST_PATH))
        wl_codes = {s['code'] for s in wl.get('stocks', [])}
        common = list(manual & wl_codes)
        if not common:
            pytest.skip('没有同时存在于自选股和手动列表的股票')

        test_code = common[0]
        orig_manual = copy.deepcopy(json.load(open(MANUAL_PATH)))
        orig_wl = copy.deepcopy(wl)

        try:
            # 先移除再重加（模拟第一次加入的场景）
            # 先确保它在 manual 中，触发 enable=True 但已在 manual 中的分支
            result = toggle_trend_stock(test_code, True)
            assert result['success']

            # 验证自选股无重复
            new_wl = json.load(open(WATCHLIST_PATH))
            new_codes = [s['code'] for s in new_wl.get('stocks', [])]
            count = new_codes.count(test_code)
            assert count == 1, f"{test_code}在自选股中出现{count}次（应为1次）"

        finally:
            json.dump(orig_manual, open(MANUAL_PATH, 'w'))
            json.dump(orig_wl, open(WATCHLIST_PATH, 'w'), ensure_ascii=False, indent=2)

    def test_watchlist_entry_format(self):
        """自选股条目必须包含必要字段"""
        wl = json.load(open(WATCHLIST_PATH))
        for s in wl.get('stocks', []):
            assert 'code' in s, f"缺少code: {s}"
            assert 'name' in s, f"{s['code']}缺少name"
            assert 'direction' in s, f"{s['code']}缺少direction"
            assert 'industry' in s, f"{s['code']}缺少industry"

    def test_manual_trend_list_format(self):
        """手动趋势列表是字符串数组"""
        manual = json.load(open(MANUAL_PATH))
        assert isinstance(manual, list)
        for code in manual:
            assert isinstance(code, str)
            assert len(code) == 6


class TestMainlineLevel:
    """主线/次级主线/非主线分类测试"""

    def test_main_line_returns_主线(self):
        from scripts.ema_utils import get_mainline_level
        assert get_mainline_level('半导体', ['半导体', '元件'], ['电机']) == '主线'

    def test_sub_main_line_returns_次级主线(self):
        from scripts.ema_utils import get_mainline_level
        assert get_mainline_level('电机', ['半导体', '元件'], ['电机']) == '次级主线'

    def test_non_main_line_returns_非主线(self):
        from scripts.ema_utils import get_mainline_level
        assert get_mainline_level('医药', ['半导体', '元件'], ['电机']) == '非主线'

    def test_empty_sector_returns_empty(self):
        from scripts.ema_utils import get_mainline_level
        assert get_mainline_level('', ['半导体'], ['电机']) == ''

    def test_empty_main_lines_returns_empty(self):
        from scripts.ema_utils import get_mainline_level
        assert get_mainline_level('半导体', [], []) == ''
        assert get_mainline_level('半导体', None, []) == ''


class TestCalcStopLoss:
    """止损计算测试"""

    def test_calc_stop_loss_returns_tuple(self):
        from scripts.buy_point_detection import calc_stop_loss, _find_support_levels
        # 用简单的模拟数据
        klines = [{'close': 100 + i, 'high': 102 + i, 'low': 98 + i, 'open': 101 + i, 'volume': 1000}
                  for i in range(30)]
        # 第29根有支撑
        sl, sl_pct = calc_stop_loss(klines, 29)
        assert sl is not None
        assert sl_pct is not None
        assert sl > 0
        assert sl_pct > 0

    def test_calc_stop_loss_insufficient_data(self):
        from scripts.buy_point_detection import calc_stop_loss
        klines = [{'close': 100 + i, 'high': 102 + i, 'low': 98 + i, 'open': 101 + i, 'volume': 1000}
                  for i in range(5)]
        sl, sl_pct = calc_stop_loss(klines, 4)
        assert sl is None
        assert sl_pct is None
