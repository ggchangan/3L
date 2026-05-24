"""买点检测模块测试 — 基于真实案例数据"""

import json
import pytest
from scripts.buy_point_detection import (
    check_trend_stock,
    detect_huicai_buy_point,
    detect_buy_point,
    scan_all_stocks,
    format_buy_signals,
    gen_trade_chart_svg,
    compute_trade_stats,
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
        # 具体验证：603009 (北特科技) 为非自选股且在扫描结果中
        assert '603009' in codes_without, "全量扫描应包含 603009 (北特科技)"
        assert '603127' in codes_without, "全量扫描应包含 603127 (昭衍新药)"


class TestDemailiBacktest:
    """德明利(001309) 3L优化回测验证（2026-05-24 新规则）"""

    def test_demaili_buy_signals_count(self, stocks):
        """验证新规则下德明利90天共检测到6个买点（旧规则13个→精减为6个）"""
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
        expected = 6
        assert len(signals) == expected, f"预期{expected}个买点，实际{len(signals)}: {[s['date'] for s in signals]}"

    def test_demaili_no_bad_breakouts(self, stocks):
        """验证3/10、3/18这些错误突破点已被排除（3/16涨停突破有效，不在排除列表）"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bad_dates = ['2026-03-10', '2026-03-18']
        for bd in bad_dates:
            bt = detect_buy_point('001309', bd, raw, market_position='波中', main_lines={'半导体'})
            assert bt is None, f"{bd}不应是买点，返回{bt}"

    def test_demaili_0410_is_breakout(self, stocks):
        """验证4/10是有效突破买点"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bt = detect_buy_point('001309', '2026-04-10', raw, market_position='波中', main_lines={'半导体'})
        assert bt is not None, "4/10应为突破买点"

    def test_demaili_0320_is_not_zhongji(self, stocks):
        """验证3/20大阴线(实体87%)+距支撑远+非地量，不被识别为中继买点"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        bt = detect_buy_point('001309', '2026-03-20', raw, market_position='波中', main_lines={'半导体'})
        assert bt is None, "3/20大实体+距支撑远不应是中继买点"

    def test_demaili_vol_condition_filters(self, stocks):
        """验证量比≤1.2的突破过滤+涨停豁免"""
        data = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
        raw = data.get('stocks', data)
        # 3/10量比0.95 ≤ 1.2, 非涨停, 应被过滤
        bt = detect_buy_point('001309', '2026-03-10', raw, market_position='波中', main_lines={'半导体'})
        assert bt is None, "3/10量比0.95未放量，不应是买点"
        # 5/06量比0.57 ≤ 1.2, 但涨停豁免应判定为突破买点
        bt2 = detect_buy_point('001309', '2026-05-06', raw, market_position='波中', main_lines={'半导体'})
        assert bt2 is not None, "5/06涨停突破应有效"
        assert bt2['buy_type'] == '突破买点', f"5/06应为突破买点(涨停豁免)，实际{bt2['buy_type']}"


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


# ====== 辅助函数：阴包阳止盈检测（三维判定版，与test_demingli_3l.py保持一致） ======
def _check_reverse_yingbaoyang(klines, current_idx, key_point=None):
    """右侧止盈：阴包阳三维判定

    第1层 跌幅: < -5%直接走 / > -3%不走 / -5%~-3%继续看支撑
    第2层 支撑: 破支撑走 / 没破观察
    第3层 量能: 放量(>1.0)加强判断
    """
    if current_idx < 1:
        return False, ''
    k, kp = klines[current_idx], klines[current_idx - 1]
    c, o = k['close'], k['open']
    cp_, op_ = kp['close'], kp['open']

    # 日跌幅
    prev_close = klines[current_idx - 1]['close'] if current_idx >= 1 else 0
    day_loss = (c - prev_close) / prev_close * 100 if prev_close else 0

    # 量比
    vol = k.get('volume', 0)
    prev_vols = [klines[current_idx - j - 1].get('volume', 0) for j in range(1, 6)]
    avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 0
    vol_ratio = vol / avg_vol if avg_vol > 0 else 0

    # 条件：阴包阳（前阳+本阴+本收≤前开）
    if cp_ >= op_ and c < o and c <= op_:
        # 第1层：跌幅判定
        if day_loss < -5:
            return True, f"阴包阳(跌{day_loss:.1f}%大阴,走)"
        elif day_loss > -3:
            return False, f"阴包阳(跌{day_loss:.1f}%小阴,观察)"
        # -5%~-3%：继续看支撑
        # 第2层：支撑判定
        if key_point and c < key_point:
            if vol_ratio > 1.0:
                return True, f"阴包阳(破支撑+放量{vol_ratio:.1f}x,走)"
            return True, f"阴包阳(破支撑{key_point:.0f},走)"
        else:
            return False, f"阴包阳(跌{day_loss:.1f}%未破支撑,观察)"
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
        规则2a: 地量(15%分位法)中继买点不限实体大小
        德明利(001309) 2026-04-27: vol低于近20日15%分位(分位地量), gain=-0.35%(小体)
        应通过地量豁免被判定为中继买点
        """
        raw = self._load_data()
        bt = detect_buy_point('001309', '2026-04-27', raw,
                              market_position='波中', main_lines={'半导体'})
        assert bt is not None, '地量中继买点应被识别'
        assert bt['buy_type'] == '中继买点', f'应为中继买点，实际: {bt["buy_type"]}'
        detail = bt.get('detail', {})
        pullback_reason = detail.get('pullback_reason', '')
        assert '支撑' in pullback_reason or 'EMA' in pullback_reason, f'应检测到回踩到位: {pullback_reason}'

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

    def test_yinbaoyang_big_drop_exits(self):
        """
        规则3a: 阴包阳跌幅<-5%直接触发止盈退出
        德明利(001309) 2026-03-19: 阴包阳+跌幅-7.75%+量比0.91
        应返回True(直接止盈)
        """
        raw = self._load_data()
        kls = None
        for sec, stocks in raw.items():
            if '001309' in stocks:
                kls = stocks['001309']
                break
        assert kls is not None, '未找到001309数据'

        target_date = '20260319'
        found_idx = -1
        for i, k in enumerate(kls):
            d = str(k['date']).replace('-', '')
            if d == target_date:
                found_idx = i
                break
        assert found_idx >= 2, f'未找到日期{target_date}或索引不足'

        rev, reason = _check_reverse_yingbaoyang(kls, found_idx, key_point=345)
        assert rev is True, f'跌幅-7.75%阴包阳应触发止盈，实际: rev={rev}'
        assert '大阴' in reason or '走' in reason, f'原因应包含止盈说明: {reason}'

    def test_yinbaoyang_mid_drop_checks_support(self):
        """
        规则3b: 阴包阳跌幅-3%~-5%看支撑，支撑远则持有
        德明利(001309) 2026-05-08: 阴包阳+跌幅-3.05%+量比0.88+支撑远
        应返回False(持有观察)
        """
        raw = self._load_data()
        kls = None
        for sec, stocks in raw.items():
            if '001309' in stocks:
                kls = stocks['001309']
                break
        assert kls is not None, '未找到001309数据'

        target_date = '20260508'
        found_idx = -1
        for i, k in enumerate(kls):
            d = str(k['date']).replace('-', '')
            if d == target_date:
                found_idx = i
                break
        assert found_idx >= 2, f'未找到日期{target_date}或索引不足'

        rev, reason = _check_reverse_yingbaoyang(kls, found_idx, key_point=577)
        assert rev is False, f'05-08阴包阳(跌-3.05%,支撑远)不应触发止盈，实际: rev={rev}'
        assert '支撑' in reason or '观察' in reason, f'原因应包含观察/支撑说明: {reason}'

    def test_breakout_vol_ratio_1dot2_filter(self):
        """
        规则4: 非涨停突破量比<=1.2被过滤
        德明利(001309) 2026-03-10: vol_ratio=0.95(<=1.2), 非涨停
        2026-03-25: vol_ratio=1.10(<=1.2), 非涨停
        均不应是突破买点
        """
        raw = self._load_data()
        # 3/10 vol_ratio=0.95 非涨停
        bt1 = detect_buy_point('001309', '2026-03-10', raw,
                               market_position='波中', main_lines={'半导体'})
        assert bt1 is None, f'3/10量比0.95非涨停不应是突破买点，实际: {bt1}'
        # 3/25 vol_ratio=1.10 非涨停
        bt2 = detect_buy_point('001309', '2026-03-25', raw,
                               market_position='波中', main_lines={'半导体'})
        assert bt2 is None, f'3/25量比1.10非涨停不应是突破买点，实际: {bt2}'

    def test_midcycle_big_body_no_pullback_fails(self):
        """
        规则5: 中继买点大实体+距支撑远应被过滤
        德明利(001309) 2026-03-20: 阴线实体87%+距支撑+2.68%, vol_ratio=0.60
        不是真回踩 -> 应返回None
        """
        raw = self._load_data()
        bt = detect_buy_point('001309', '2026-03-20', raw,
                              market_position='波中', main_lines={'半导体'})
        assert bt is None, f'3/20大实体+距支撑远不应是中继买点，实际: {bt}'

    def test_dili_pullback_captured(self):
        """
        规则6: 地量+乖离率双重验证，回踩到位被正确识别为中继买点
        德明利(001309) 2026-04-21: 地量(近20日15%分位以下)+乖离率EMA5在±2%内
        新规则通过地量分位法+乖离率双路径识别
        """
        raw = self._load_data()
        bt = detect_buy_point('001309', '2026-04-21', raw,
                              market_position='波中', main_lines={'半导体'})
        assert bt is not None, f'4/21地量+乖离率应被识别为中继买点'
        assert bt['buy_type'] == '中继买点', f'应为中继买点，实际: {bt["buy_type"]}'
        detail = bt.get('detail', {})
        reason = str(detail.get('pullback_reason', ''))
        assert '乖离' in reason or '支撑' in reason, f'应检测到回踩到位: {reason}'

    def test_yinbaoyang_shrink_does_not_exit(self):
        """
        规则7: 缩量阴包阳(量比<0.8)观察一天，不触发止盈退出
        沪硅产业(688126) 2026-03-09: 阴包阳+日跌幅-1.69%(>-3%)
        应返回False(小阴观察)
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
        assert rev is False, f'阴包阳(跌-1.69%)不应触发止盈，实际: rev={rev}, reason={reason}'
        assert '小阴' in reason or '观察' in reason, f'原因应包含"小阴"/"观察"字样，实际: {reason}'


class TestGenTradeChartSvg:
    """gen_trade_chart_svg 测试"""

    def test_chart_creates_file(self, tmp_path):
        """生成有效SVG文件"""
        kls = [
            {'date': '2026-05-01', 'open': 100, 'high': 105, 'low': 99, 'close': 103, 'volume': 1000},
            {'date': '2026-05-02', 'open': 103, 'high': 108, 'low': 102, 'close': 107, 'volume': 1200},
            {'date': '2026-05-03', 'open': 107, 'high': 110, 'low': 106, 'close': 109, 'volume': 900},
        ] * 8  # 24根K线（足够绘制）
        # 修正日期为连续交易日
        kls = []
        for i in range(24):
            kls.append({
                'date': f'2026-05-{i+1:02d}',
                'open': 100 + i * 0.5,
                'high': 102 + i * 0.8,
                'low': 99 + i * 0.3,
                'close': 101 + i * 0.6,
                'volume': 1000 + i * 50,
            })
        signals = [
            {'n': 1, 'date': '2026-05-03', 'type': '突破买点', 'entry': 102.0,
             'exit': 108.0, 'exit_date': '2026-05-06', 'gain': 5.88, 'cum_gain': 5.88, 'days': 3},
            {'n': 2, 'date': '2026-05-10', 'type': '中继买点', 'entry': 108.0,
             'exit': 106.0, 'exit_date': '2026-05-13', 'gain': -1.85, 'cum_gain': 3.92, 'days': 3},
        ]
        out = tmp_path / 'test_chart.svg'
        result = gen_trade_chart_svg(kls, signals, '测试股票', '000000', str(out))
        assert result is True, 'SVG生成应返回True'
        assert out.exists(), 'SVG文件应在指定路径生成'
        content = out.read_text()
        assert '<svg' in content, '内容应包含SVG标签'
        assert '测试股票(000000)' in content, '标题应含股票名'
        assert 'B1' in content, '应含买入标注B1'
        assert 'S2' in content or '+5.88%' in content, '应含卖出标注'
        assert 'B2' in content, '应含第二笔买入标注'

    def test_chart_empty_signals(self, tmp_path):
        """空信号列表仍生成有效SVG"""
        kls = [{'date': f'2026-05-{i+1:02d}', 'open': 100, 'high': 101, 'low': 99,
                'close': 100, 'volume': 1000} for i in range(20)]
        out = tmp_path / 'empty.svg'
        result = gen_trade_chart_svg(kls, [], '空信号', '000001', str(out))
        assert result is True
        assert out.exists()
        content = out.read_text()
        assert '空信号(000001)' in content
        assert '0笔信号' in content

    def test_chart_returns_false_on_bad_klines(self, tmp_path):
        """K线数据不完整返回False"""
        kls = [{'date': '2026-05-01', 'open': 100}]  # 缺少high/low/close
        out = tmp_path / 'bad.svg'
        result = gen_trade_chart_svg(kls, [], '坏数据', '000001', str(out))
        assert result is False


class TestComputeTradeStats:
    """compute_trade_stats 测试"""

    def test_all_profitable(self):
        """全盈利信号"""
        signals = [
            {'gain': 5.0, 'cum_gain': 5.0},
            {'gain': 3.0, 'cum_gain': 8.15},
            {'gain': 10.0, 'cum_gain': 18.97},
        ]
        stats = compute_trade_stats(signals)
        assert stats['total'] == 3
        assert stats['wins'] == 3
        assert stats['losses'] == 0
        assert stats['win_rate'] == 100.0
        assert stats['avg_win'] == 6.0  # (5+3+10)/3
        assert stats['avg_loss'] == 0
        assert stats['cumulative_return'] == 18.97

    def test_all_losses(self):
        """全亏损信号"""
        signals = [
            {'gain': -2.0, 'cum_gain': -2.0},
            {'gain': -5.0, 'cum_gain': -6.9},
        ]
        stats = compute_trade_stats(signals)
        assert stats['total'] == 2
        assert stats['wins'] == 0
        assert stats['losses'] == 2
        assert stats['win_rate'] == 0.0
        assert stats['avg_win'] == 0
        assert stats['avg_loss'] == -3.5  # (-2 + -5)/2
        assert stats['cumulative_return'] == -6.9

    def test_mixed_results(self):
        """盈亏混合"""
        signals = [
            {'gain': 8.0, 'cum_gain': 8.0},
            {'gain': -3.0, 'cum_gain': 4.76},
            {'gain': 12.0, 'cum_gain': 17.33},
            {'gain': -1.5, 'cum_gain': 15.57},
        ]
        stats = compute_trade_stats(signals)
        assert stats['total'] == 4
        assert stats['wins'] == 2
        assert stats['losses'] == 2
        assert stats['win_rate'] == 50.0
        assert stats['avg_win'] == 10.0  # (8+12)/2
        assert stats['avg_loss'] == -2.25  # (-3 + -1.5)/2
        assert stats['cumulative_return'] == 15.57

    def test_empty_signals(self):
        """空列表"""
        stats = compute_trade_stats([])
        assert stats['total'] == 0
        assert stats['wins'] == 0
        assert stats['losses'] == 0
        assert stats['win_rate'] == 0
        assert stats['cumulative_return'] == 0

    def test_single_signal(self):
        """单笔信号"""
        stats = compute_trade_stats([{'gain': 5.5, 'cum_gain': 5.5}])
        assert stats['total'] == 1
        assert stats['wins'] == 1
        assert stats['win_rate'] == 100.0
        assert stats['avg_win'] == 5.5
        assert stats['cumulative_return'] == 5.5
