"""买点检测模块测试 — 基于真实案例数据"""

import pytest
from scripts.buy_point_detection import (
    check_trend_stock,
    detect_huicai_buy_point,
    detect_buy_point,
    scan_all_stocks,
    format_buy_signals,
)


class TestCheckTrendStock:
    """check_trend_stock 测试"""

    def test_check_trend_stock_true(self, stocks):
        """已知趋势股应返回 True"""
        # 沪硅产业 (688126) — 已知是趋势股
        assert check_trend_stock('688126', '2026-05-21', stocks) is True
        # 鼎龙股份 (300054) — 同样是趋势股
        assert check_trend_stock('300054', '2026-05-21', stocks) is True

    def test_check_trend_stock_false(self, stocks):
        """非趋势股应返回 False"""
        # 跨境通 (002640) — 已知不是趋势股
        assert check_trend_stock('002640', '2026-05-21', stocks) is False
        # 旅游ETF (562510) — ETF 不符合趋势股条件
        assert check_trend_stock('562510', '2026-05-21', stocks) is False
        # 不存在日期应返回 False
        assert check_trend_stock('688126', '2025-01-01', stocks) is False


class TestDetectHuicaiBuyPoint:
    """detect_huicai_buy_point 测试"""

    def test_detect_huicai_buy_point_绿谐波(self, stocks):
        """688017 (绿的谐波) 是趋势股但偏离EMA5 +5.10% > ±1.5%，应返回 None"""
        result = detect_huicai_buy_point('688017', '2026-05-21', stocks)
        assert result is None, f"预期 None，实际: {result}"


class TestScanAllStocks:
    """scan_all_stocks 自选股过滤测试"""

    def test_scan_all_stocks_watchlist_filter(self, stocks, wl_codes):
        """
        测试 watchlist_codes 过滤功能：
        - 传入 watchlist_codes 时，结果不应包含非自选股
        - 不传 watchlist_codes 时，结果应包含非自选股
        """
        date_str = '2026-05-21'

        # 传入 watchlist_codes — 不应出现非自选股
        with_wl = scan_all_stocks(date_str, stocks, watchlist_codes=wl_codes)
        codes_with = set(r['code'] for r in with_wl)
        outside = codes_with - wl_codes
        assert len(outside) == 0, (
            f"传入 watchlist_codes 后仍出现非自选股: {outside}"
        )

        # 不传 watchlist_codes — 应包含非自选股
        without_wl = scan_all_stocks(date_str, stocks)
        codes_without = set(r['code'] for r in without_wl)
        outside_all = codes_without - wl_codes
        assert len(outside_all) > 0, (
            "不传 watchlist_codes 时应包含非自选股，实际全部是自选股"
        )
        # 具体验证：300503 (昊志机电)、603009 (北特科技) 为非自选股且在扫描结果中
        assert '300503' in codes_without, "全量扫描应包含 300503 (昊志机电)"
        assert '603009' in codes_without, "全量扫描应包含 603009 (北特科技)"


class TestFormatBuySignals:
    """format_buy_signals 自选股过滤测试"""

    def test_format_buy_signals_filter(self, stocks, wl_codes):
        """
        format_buy_signals 传入 watchlist_codes：
        四条结果列表 (zhongji_main, zhongji_nonmain, tupo_main, tupo_nonmain)
        中不应有非自选股
        """
        date_str = '2026-05-21'
        result = format_buy_signals(
            date_str, stocks,
            main_lines=['机器人'],
            watchlist_codes=wl_codes,
        )

        for key in ['zhongji_main', 'zhongji_nonmain', 'tupo_main', 'tupo_nonmain']:
            items = result.get(key, [])
            codes_in = set(r['code'] for r in items)
            outside = codes_in - wl_codes
            assert len(outside) == 0, (
                f"{key} 中包含非自选股: {outside}"
            )


class TestDetectBuyPoint:
    """detect_buy_point 返回值结构测试 — 3L框架优先，趋势股仅打标签"""

    def test_detect_buy_point_return(self, stocks):
        """对北特科技跑 detect_buy_point，应返回 dict 且包含 buy_type/score/structure/stage"""
        # 北特科技(603009) — 上涨趋势+放量突破前高，预期3L突破买点
        result = detect_buy_point('603009', '2026-05-21', stocks)
        assert isinstance(result, dict), f"预期 dict，实际: {type(result)}"
        # 必含字段
        assert 'buy_type' in result, f"缺少 buy_type，实际 keys: {list(result.keys())}"
        assert 'score' in result, f"缺少 score"
        assert 'structure' in result, f"缺少 structure"
        assert 'stage' in result, f"缺少 stage"
        # 3L买点类型（中继买点 或 突破买点），不再是回踩买点
        assert result['buy_type'] in ('中继买点', '突破买点'), f"预期3L买点，实际: {result['buy_type']}"
        assert isinstance(result['score'], int)
        assert result['score'] > 0
