"""买点检测模块测试 — 基于真实案例数据"""

import json
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


class TestDemailiBacktest:
    """德明利(001309) 3L优化回测验证（2026-05-24）"""

    def test_demaili_buy_signals_count(self, stocks):
        """验证优化后德明利90天共检测到13个买点"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        for sec, ss in raw.items():
            if '001309' in ss:
                kls = ss['001309']
                break
        signals = []
        for i in range(30, len(kls)):
            ds = str(kls[i]['date']).replace('-','')
            df = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
            bt = detect_buy_point('001309', df, raw, market_position='波中', main_lines={'半导体'})
            if bt:
                signals.append({'date': df, 'type': bt['buy_type']})
        assert len(signals) == 13, f"预期13个买点，实际{len(signals)}: {[s['date'] for s in signals]}"

    def test_demaili_no_bad_breakouts(self, stocks):
        """验证3/10、3/16、3/18这些错误突破点已被排除"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bad_dates = ['2026-03-10', '2026-03-16', '2026-03-18']
        for bd in bad_dates:
            bt = detect_buy_point('001309', bd, raw, market_position='波中', main_lines={'半导体'})
            assert bt is None, f"{bd}不应是买点，返回{bt}"

    def test_demaili_0313_is_breakout(self, stocks):
        """验证3/13是有效突破买点（评分9）"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bt = detect_buy_point('001309', '2026-03-13', raw, market_position='波中', main_lines={'半导体'})
        assert bt is not None, "3/13应为突破买点"
        assert bt['buy_type'] == '突破买点', f"3/13应为突破买点，实际{bt['buy_type']}"
        bs = bt.get('detail', {}).get('breakout_score', 0)
        assert bs >= 5, f"3/13突破评分应≥5，实际{bs}"

    def test_demaili_0320_is_zhongji(self, stocks):
        """验证3/20是回踩中继买点"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bt = detect_buy_point('001309', '2026-03-20', raw, market_position='波中', main_lines={'半导体'})
        assert bt is not None, "3/20应为买点"
        assert bt['buy_type'] == '中继买点', f"3/20应为中继买点，实际{bt['buy_type']}"

    def test_demaili_vol_condition_filters(self, stocks):
        """验证量比≤1.0的突破不被接受"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        # 3/10量比0.95 ≤ 1.0, 应被过滤
        bt = detect_buy_point('001309', '2026-03-10', raw, market_position='波中', main_lines={'半导体'})
        assert bt is None, "3/10量比0.95未放量，不应是买点"
        # 5/06量比0.57 ≤ 1.0, 但作为中继买点应有效
        bt2 = detect_buy_point('001309', '2026-05-06', raw, market_position='波中', main_lines={'半导体'})
        assert bt2 is not None, "5/06缩量应为中继买点"
        assert bt2['buy_type'] == '中继买点', f"5/06应为中继买点，实际{bt2['buy_type']}"


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


# ====== 辅助函数：阴包阳止盈检测（来自 test_demingli_3l.py） ======
def _check_reverse_yingbaoyang(klines, current_idx):
    """右侧止盈：阴包阳(放量走/缩量观察)"""
    if current_idx < 1:
        return False, ''
    k, kp = klines[current_idx], klines[current_idx - 1]
    c, o = k['close'], k['open']
    cp_, op_ = kp['close'], kp['open']

    vol = k.get('volume', 0)
    prev_vols = [klines[current_idx - j - 1].get('volume', 0) for j in range(1, 6)]
    avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 0
    vol_ratio = vol / avg_vol if avg_vol > 0 else 0

    # 条件：阴包阳（前阳+本阴+本收≤前开）
    if cp_ >= op_ and c < o and c <= op_:
        if vol_ratio < 0.8:
            return False, f'缩量阴包阳(量{vol_ratio:.1f}x,观察)'
        else:
            return True, f'阴包阳(昨{op_:.0f}->{cp_:.0f},今{o:.0f}->{c:.0f},量{vol_ratio:.1f}x)'
    return False, ''


class TestNewRules20260524:
    """2026-05-24 新规则验证测试"""

    DATA_PATH = '/home/ubuntu/data/3l/all_stocks_60d.json'

    @classmethod
    def _load_data(cls):
        import json
        data = json.load(open(cls.DATA_PATH))
        return data.get('stocks', data)

    def test_zhangting_breakout_skips_volume_check(self):
        """
        规则1: 涨停突破豁免量比检查
        德明利(001309) 2026-05-06: 涨停(+10%), vol_ratio=0.57(<=1.2)
        应通过涨停豁免被判定为有效突破买点
        """
        raw = self._load_data()
        bt = detect_buy_point('001309', '2026-05-06', raw,
                              market_position='波中', main_lines={'半导体'})
        assert bt is not None, '涨停突破应被识别为买点'
        assert bt['buy_type'] == '突破买点', f'应为突破买点，实际: {bt["buy_type"]}'
        detail = bt.get('detail', {})
        bd = detail.get('breakout_detail', {})
        assert bd.get('is_limit_up') is True, '应识别为涨停'
        assert bd.get('limit_up_skip') is True, '应豁免量比检查'
        assert bt['vol_ratio'] <= 1.2, f'量比{bt["vol_ratio"]}虽<=1.2，但涨停豁免应通过'
        assert detail.get('breakout_score', 0) >= 5, f'突破评分应>=5，实际{detail.get("breakout_score")}'

    def test_dili_midcycle_with_large_body(self):
        """
        规则2a: 地量(量比<0.6)中继买点不限实体大小
        中信出版(300788) 2026-04-24: vol_ratio=0.51(地量), gain=-4.87%(大实体)
        应通过地量豁免被判定为中继买点
        """
        raw = self._load_data()
        bt = detect_buy_point('300788', '2026-04-24', raw,
                              market_position='波中')
        assert bt is not None, '地量中继买点应被识别'
        assert bt['buy_type'] == '中继买点', f'应为中继买点，实际: {bt["buy_type"]}'
        assert bt['vol_ratio'] < 0.6, f'量比{bt["vol_ratio"]}应<0.6(地量)'
        detail = bt.get('detail', {})
        gain_pct = detail.get('gain_pct', 0)
        assert gain_pct < -3, f'实体涨跌幅{gain_pct}%应<-3%(大实体)，但地量豁免应通过'

    def test_midcycle_without_pullback_fails(self):
        """
        规则2b: 中继买点缺少回踩到位检查应失败
        天岳先进(688234) 2026-04-21: 上涨趋势+缩量(vr=0.73), gain=-1.3%(小实体OK)
        但回踩到位三条件均不满足 -> 应返回None
        """
        raw = self._load_data()
        bt = detect_buy_point('688234', '2026-04-21', raw,
                              market_position='波中')
        assert bt is None, f'未回踩到位应返回None，实际返回: {bt}'

    def test_yinbaoyang_shrink_does_not_exit(self):
        """
        规则3: 缩量阴包阳(量比<0.8)观察一天，不触发止盈退出
        沪硅产业(688126) 2026-03-09: 阴包阳形态+量比0.78(<0.8)
        应返回False(不触发)
        """
        raw = self._load_data()
        # 定位K线索引
        kls = None
        for sec, stocks in raw.items():
            if '688126' in stocks:
                kls = stocks['688126']
                break
        assert kls is not None, '未找到688126数据'

        target_date = '20260309'
        found_idx = -1
        for i, k in enumerate(kls):
            d = str(k['date']).replace('-', '')
            if d == target_date:
                found_idx = i
                break
        assert found_idx >= 2, f'未找到日期{target_date}或索引不足'

        rev, reason = _check_reverse_yingbaoyang(kls, found_idx)
        assert rev is False, f'缩量阴包阳不应触发止盈，实际: rev={rev}, reason={reason}'
        assert '缩量' in reason, f'原因应包含"缩量"字样，实际: {reason}'
        assert '观察' in reason, f'原因应包含"观察"字样，实际: {reason}'
