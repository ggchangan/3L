"""前复权矫正测试 — TDD: 先测试，再实现，后验证

测试策略：
1. 送转股调整：构造有除权缺口的K线 + mock xdxr，验证价格被正确前复权
2. 分红调整：验证小幅度调整的精度
3. 组合场景：同一天既有分红又有送转股
4. 无需调整的场景：无除权事件的股票
5. 集成测试：对腾景科技(688195)走完整流程，对比腾讯qfq数据
"""

import sys, os
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest


def _make_record(date_str, price, volume=1000000):
    return {
        'date': date_str,
        'open': round(price + 0.5, 2),
        'close': round(price, 2),
        'high': round(price + 2.5, 2),
        'low': round(price - 1.5, 2),
        'volume': volume,
    }


def _make_xdxr(date_str='20260606', category=9,
               qianzongguben=10000, houzongguben=14000,
               fenhong=None):
    return {
        'year': int(date_str[:4]), 'month': int(date_str[4:6]),
        'day': int(date_str[6:]), 'category': category,
        'qianzongguben': qianzongguben,
        'houzongguben': houzongguben,
        'fenhong': fenhong,
        'panqianliutong': qianzongguben if category == 9 else None,
        'panhouliutong': houzongguben if category == 9 else None,
    }


class TestFqAdjustmentUnit:
    """前复权调整算法的单元测试"""

    def test_songzhuan_adjusts_prices_before_gap(self):
        """送转股：除权日前的所有价格乘以系数，之后的不变"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record(f'202606{str(i+1).zfill(2)}', 100.5) for i in range(5)]
        records += [_make_record(f'202606{str(i+1).zfill(2)}', 70.5) for i in range(5, 10)]

        xdxr_events = [_make_xdxr('20260606', category=9)]

        result = _apply_fq_adjustment(records, xdxr_events)
        factor = 10000 / 14000  # 0.7143

        for r in result:
            if r['date'] < '20260606':
                assert abs(r['close'] - 100.5 * factor) < 0.01
                assert abs(r['open'] - 101.0 * factor) < 0.01
            else:
                assert abs(r['close'] - 70.5) < 0.01

    def test_songzhuan_specific_factor(self):
        """送转股：特定系数 12935/18109 ≈ 0.7143"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260603', 100.5)]
        records += [_make_record('20260604', 70.5)]

        xdxr_events = [_make_xdxr('20260604', category=9,
                                   qianzongguben=12935, houzongguben=18109)]

        result = _apply_fq_adjustment(records, xdxr_events)
        expected_factor = 12935 / 18109

        assert abs(result[0]['close'] - 100.5 * expected_factor) < 0.01
        assert abs(result[0]['open'] - 101.0 * expected_factor) < 0.01
        assert abs(result[0]['high'] - 103.0 * expected_factor) < 0.01
        assert abs(result[0]['low'] - 99.0 * expected_factor) < 0.01
        assert abs(result[1]['close'] - 70.5) < 0.01  # 除权日不变

    def test_no_adjustment_without_events(self):
        """无除权事件：数据不变"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260601', 100.0),
                   _make_record('20260602', 101.0)]

        result = _apply_fq_adjustment(records, [])
        assert result[0]['close'] == 100.0
        assert result[1]['close'] == 101.0

    def test_cash_dividend_adjustment(self):
        """分红：除权日前价格略下调"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260603', 100.5)]
        records += [_make_record('20260604', 70.5)]

        xdxr_events = [_make_xdxr('20260604', category=1, fenhong=1.64)]

        result = _apply_fq_adjustment(records, xdxr_events)

        # 分红1.64元，系数=(100.5-1.64)/100.5 ≈ 0.9837
        expected_factor = (100.5 - 1.64) / 100.5
        assert abs(result[0]['close'] - 100.5 * expected_factor) < 0.01
        # 除权日不变
        assert abs(result[1]['close'] - 70.5) < 0.01

    def test_combined_dividend_and_songzhuan(self):
        """同一天既有分红又有送转股：综合调整"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260603', 100.5),
                   _make_record('20260604', 70.5)]

        # 同一天，先category 1后9（顺序无关，函数对同天都处理）
        xdxr_events = [
            _make_xdxr('20260604', category=1, fenhong=1.64),
            _make_xdxr('20260604', category=9,
                       qianzongguben=12935, houzongguben=18109),
        ]

        result = _apply_fq_adjustment(records, xdxr_events)

        songzhuan_factor = 12935 / 18109
        dividend_factor = (100.5 - 1.64) / 100.5
        combined = songzhuan_factor * dividend_factor

        # 调整后价格应比纯送转股调整更低（多了分红）
        assert result[0]['close'] < 100.5 * songzhuan_factor
        assert result[0]['close'] > 70.5  # 应该在中间
        # 除权日不变
        assert abs(result[1]['close'] - 70.5) < 0.01

    def test_multiple_events_over_time(self):
        """多次除权：从最新到最旧逐次调整"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        # 3段价格：150(前10天)→100(中间5天)→70(后5天)
        records = [_make_record(f'202605{str(i+20).zfill(2)}', 150.0) for i in range(10)]
        records += [_make_record(f'202606{str(i+1).zfill(2)}', 100.0) for i in range(5)]
        records += [_make_record(f'202606{str(i+6).zfill(2)}', 70.0) for i in range(5)]

        xdxr_events = [
            _make_xdxr('20260606', category=9,
                       qianzongguben=10000, houzongguben=12000),
            _make_xdxr('20260530', category=9,
                       qianzongguben=8000, houzongguben=10000),
        ]

        result = _apply_fq_adjustment(records, xdxr_events)
        factor1 = 10000 / 12000   # 0.8333
        factor2 = 8000 / 10000    # 0.8
        combined = factor1 * factor2  # 0.6667

        # 两次调整前的价格(<20260530)：combined factor
        for r in result:
            if r['date'] < '20260530':
                assert abs(r['close'] - 150.0 * combined) < 0.1
            elif '20260530' <= r['date'] < '20260606':
                assert abs(r['close'] - 100.0 * factor1) < 0.1
            else:
                assert abs(r['close'] - 70.0) < 0.1

    def test_events_outside_kline_range(self):
        """除权事件在K线范围之外：不影响"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260601', 100.0),
                   _make_record('20260602', 101.0)]

        # 除权事件在K线之前（2024年）
        xdxr_events = [_make_xdxr('20240529', category=9)]

        result = _apply_fq_adjustment(records, xdxr_events)
        assert result[0]['close'] == 100.0
        assert result[1]['close'] == 101.0

    def test_small_factor_ignored(self):
        """系数偏离<0.1%时不调整（避免频繁浮点计算）"""
        from backend.core.update_stock_data import _apply_fq_adjustment

        records = [_make_record('20260603', 100.0),
                   _make_record('20260604', 99.0)]

        # 系数=10000/10001 ≈ 0.9999，偏离<0.1%
        xdxr_events = [_make_xdxr('20260604', category=9,
                                   qianzongguben=10000, houzongguben=10001)]

        result = _apply_fq_adjustment(records, xdxr_events)
        assert result[0]['close'] == 100.0  # 未调整

    def test_empty_records(self):
        """空K线列表返回空"""
        from backend.core.update_stock_data import _apply_fq_adjustment
        assert _apply_fq_adjustment([], []) == []
        assert _apply_fq_adjustment([], [{'year': 2026}]) == []


# ====== Integration Tests ======


class TestFqAdjustmentIntegration:
    """集成测试：对真实股票验证前复权效果"""

    def test_tengjing_keji_688195(self):
        """腾景科技(688195)：验证5/29除权前的价格被正确调整为前复权

        原始mootdx: 5/28收盘341.42（未复权）
        腾讯qfq:    5/28收盘243.75（前复权）
        调整后5/28收盘应≈243.75
        """
        from backend.core.update_stock_data import _apply_fq_adjustment
        from mootdx.quotes import Quotes

        client = Quotes.factory(market='std')
        bars = client.bars(symbol='688195', frequency=9, start=0, count=60)
        assert bars is not None and len(bars) >= 30

        records = []
        for _, row in bars.iterrows():
            records.append({
                'date': row['datetime'][:10].replace('-', ''),
                'open': round(float(row['open']), 2),
                'close': round(float(row['close']), 2),
                'high': round(float(row['high']), 2),
                'low': round(float(row['low']), 2),
                'volume': int(float(row['volume'])) * 100,
            })

        xdxr_df = client.xdxr(symbol='688195')
        assert xdxr_df is not None
        xdxr_events = []
        for _, row in xdxr_df.iterrows():
            if row['year'] >= 2024:
                xdxr_events.append({
                    'year': row['year'], 'month': row['month'], 'day': row['day'],
                    'category': row['category'],
                    'qianzongguben': row['qianzongguben'],
                    'houzongguben': row['houzongguben'],
                    'fenhong': row['fenhong'],
                    'panqianliutong': row['panqianliutong'],
                    'panhouliutong': row['panhouliutong'],
                })

        result = _apply_fq_adjustment(records, xdxr_events)

        may28 = next(r for r in result if r['date'] == '20260528')
        may29 = next(r for r in result if r['date'] == '20260529')

        print(f"\n  调整后5/28收盘: {may28['close']}")
        print(f"  调整后5/29收盘: {may29['close']}")
        print(f"  腾讯qfq 5/28: 243.75")
        print(f"  腾讯qfq 5/29: 233.90")

        # 5/28前复权后应接近243.75（允许±5元，分红调整有微小差异）
        assert abs(may28['close'] - 243.75) < 5.0, \
            f"5/28收盘{may28['close']}应接近243.75"
        assert abs(may29['close'] - 233.90) < 5.0, \
            f"5/29收盘{may29['close']}应接近233.90"

        # 修正后缺口应<15%（原来是30%）
        gap = (may28['close'] - may29['close']) / may29['close'] * 100
        assert abs(gap) < 15, f"修正后缺口{gap:.1f}%应<15%"

    def test_normal_stock_ping_an_bank(self):
        """无近期除权的股票(平安银行)：调整前后数据基本不变"""
        from backend.core.update_stock_data import _apply_fq_adjustment
        from mootdx.quotes import Quotes

        client = Quotes.factory(market='std')
        bars = client.bars(symbol='000001', frequency=9, start=0, count=60)
        assert bars is not None

        records = []
        for _, row in bars.iterrows():
            records.append({
                'date': row['datetime'][:10].replace('-', ''),
                'open': round(float(row['open']), 2),
                'close': round(float(row['close']), 2),
                'high': round(float(row['high']), 2),
                'low': round(float(row['low']), 2),
                'volume': int(float(row['volume'])) * 100,
            })

        xdxr_df = client.xdxr(symbol='000001')
        xdxr_events = []
        if xdxr_df is not None:
            for _, row in xdxr_df.iterrows():
                if row['year'] >= 2024:
                    xdxr_events.append({
                        'year': row['year'], 'month': row['month'], 'day': row['day'],
                        'category': row['category'],
                        'qianzongguben': row['qianzongguben'],
                        'houzongguben': row['houzongguben'],
                        'fenhong': row['fenhong'],
                        'panqianliutong': row['panqianliutong'],
                        'panhouliutong': row['panhouliutong'],
                    })

        result = _apply_fq_adjustment(records, xdxr_events)

        # 无近期除权的股票，数据基本不变
        for i in range(len(records)):
            diff = abs(result[i]['close'] - records[i]['close'])
            assert diff < 5.0, f"index {i} diff={diff} 应<5"
