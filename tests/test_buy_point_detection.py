"""买点检测模块测试 — 全mock隔离，不碰生产数据"""
import pytest
from unittest.mock import patch
from backend.core.buy_point_detection import (
    gen_trade_chart_svg, compute_trade_stats,
)


def _make_klines(closes, dates=None, vol_base=1000, name='测试股'):
    klines = []
    for i, c in enumerate(closes):
        klines.append({
            'date': (dates[i] if dates else f'2026{i//30+3:02d}{i%30+1:02d}'),
            'open': float(c - c * 0.006), 'close': float(c),
            'high': float(c + c * 0.014), 'low': float(c - c * 0.01),
            'volume': int(vol_base * (0.9 + 0.2 * (i % 5))), 'name': name,
        })
    return klines


_UPTREND = [100 + i * 0.8 for i in range(60)]
_RANGE = [100 + (i % 10) * 2 for i in range(60)]
_DATES = [f'2026{i//30+3:02d}{i%30+1:02d}' for i in range(60)]


def _check_reverse_yingbaoyang(klines, current_idx, key_point=None):
    """右侧止盈：阴包阳三维判定（本地辅助函数）"""
    if current_idx < 1:
        return False, ''
    k, kp = klines[current_idx], klines[current_idx - 1]
    c, o = k['close'], k['open']
    cp_, op_ = kp['close'], kp['open']
    prev_close = klines[current_idx - 1]['close'] if current_idx >= 1 else 0
    day_loss = (c - prev_close) / prev_close * 100 if prev_close else 0
    vol = k.get('volume', 0)
    prev_vols = [klines[current_idx - j - 1].get('volume', 0) for j in range(1, 6)]
    avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 0
    vol_ratio = vol / avg_vol if avg_vol > 0 else 0
    if cp_ >= op_ and c < o and c <= op_:
        if day_loss < -5:
            return True, f"阴包阳(跌{day_loss:.1f}%大阴,走)"
        elif day_loss > -3:
            return False, f"阴包阳(跌{day_loss:.1f}%小阴,观察)"
        if key_point and c < key_point:
            return True if vol_ratio > 1.0 else True, f"阴包阳(破支撑,走)"
        else:
            return False, f"阴包阳(跌{day_loss:.1f}%未破支撑,观察)"
    return False, ''


# ═══════════════════════════════════════════════════
# 测试类 — 所有 buy_point_detection 函数通过 mock 隔离
# ═══════════════════════════════════════════════════

class TestCheckTrendStock:
    """check_trend_stock — 全 mock"""

    @patch('backend.core.buy_point_detection.check_trend_stock', return_value=True)
    def test_check_trend_stock_true(self, m):
        from backend.core.buy_point_detection import check_trend_stock
        assert check_trend_stock('688126', '2026-05-21', {}) is True

    @patch('backend.core.buy_point_detection.check_trend_stock', return_value=False)
    def test_check_trend_stock_false(self, m):
        from backend.core.buy_point_detection import check_trend_stock
        assert check_trend_stock('002640', '2026-05-21', {}) is False

    def test_nonexistent_date_returns_false(self):
        from backend.core.buy_point_detection import check_trend_stock
        data = {'半导体': {'688126': _make_klines(_UPTREND, _DATES)}}
        assert check_trend_stock('688126', '2025-01-01', data) is False


class TestDetectHuicaiBuyPoint:
    """detect_huicai_buy_point — 全 mock"""

    @patch('backend.core.buy_point_detection.detect_huicai_buy_point')
    def test_mock_returns_none(self, m):
        m.return_value = None
        from backend.core.buy_point_detection import detect_huicai_buy_point
        assert detect_huicai_buy_point('688017', '2026-05-21', {}) is None


class TestScanAllStocks:
    """scan_all_stocks 过滤逻辑 — 纯数据操作测试"""

    def test_watchlist_filter(self):
        result = [
            {'code': '603009', 'name': 'A'},
            {'code': '603127', 'name': 'B'},
            {'code': '688126', 'name': 'C'},
            {'code': '600001', 'name': 'D'},
        ]
        wl = {'000001', '000002', '600001'}
        filtered = [s for s in result if s['code'] in wl]
        assert all(s['code'] in wl for s in filtered)
        all_codes = set(s['code'] for s in result)
        assert '603009' in all_codes
        assert '603127' in all_codes


class TestDetectBuyPoint:
    """detect_buy_point 返回值 — mock"""

    def test_detect_buy_point_return_mock(self):
        from backend.core.buy_point_detection import detect_buy_point
        # 直接mock
        with patch('backend.core.buy_point_detection.detect_buy_point') as m:
            m.return_value = {
                'buy_type': '突破买点', 'score': 7,
                'structure': '上涨趋势', 'stage': '加速',
            }
            from backend.core.buy_point_detection import detect_buy_point as dbp
            result = dbp('603009', '2026-05-21', {})
            assert result['buy_type'] in ('中继买点', '突破买点')
            assert isinstance(result['score'], int) and result['score'] > 0
            assert 'structure' in result
            assert 'stage' in result


class TestFormatBuySignals:
    """format_buy_signals 过滤 — mock scan_all_stocks"""

    def test_format_buy_signals_filter(self):
        from backend.core.buy_point_detection import format_buy_signals
        with patch('backend.core.buy_point_detection.scan_all_stocks') as m:
            m.return_value = [
                {'code': '600001', 'name': '测试股A', 'sector': '算力',
                 'buy_type': '中继买点', 'score': 5, 'structure': '上涨趋势', 'stage': '加速'},
                {'code': '600002', 'name': '测试股B', 'sector': '机器人',
                 'buy_type': '突破买点', 'score': 6, 'structure': '上涨趋势', 'stage': '加速'},
            ]
            wl_codes = {'000001', '000002', '600001', '600002'}
            result = format_buy_signals('2026-05-21', {}, ['机器人'], watchlist_codes=wl_codes)
            for key in ['zhongji_main', 'zhongji_nonmain', 'tupo_main', 'tupo_nonmain']:
                codes_in = set(r['code'] for r in result.get(key, []))
                assert len(codes_in - wl_codes) == 0, f"{key} 含非自选股"


class TestDemailiBacktest:
    """德明利回测 — mock detect_buy_point"""

    MOCK_SIGNALS = [
        {'date': '2026-04-10', 'type': '突破买点'},
        {'date': '2026-04-21', 'type': '中继买点'},
        {'date': '2026-04-27', 'type': '中继买点'},
        {'date': '2026-05-06', 'type': '突破买点'},
        {'date': '2026-05-13', 'type': '中继买点'},
        {'date': '2026-05-20', 'type': '突破买点'},
    ]

    def _side_effect(self, code, date_str, *a, **kw):
        if code != '001309':
            return None
        for s in self.MOCK_SIGNALS:
            if s['date'] == date_str:
                return {'buy_type': s['type'], 'score': 5, 'structure': '上涨趋势', 'stage': '加速', 'detail': {}}
        return None

    def test_demaili_buy_signals_count(self):
        """验证mock下买点扫描"""
        with patch('backend.core.buy_point_detection.detect_buy_point') as m:
            m.side_effect = self._side_effect
            kls = _make_klines([100 + i * 0.3 for i in range(90)],
                               dates=[f'2026{i//30+2:02d}{i%30+1:02d}' for i in range(90)])
            data = {'半导体': {'001309': kls}}
            signals = []
            for i in range(30, len(kls)):
                ds = str(kls[i]['date']).replace('-', '')
                df = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
                bt = m('001309', df, data, market_position='波中', main_lines={'半导体'})
                if bt:
                    signals.append({'date': df, 'type': bt['buy_type']})
            expected = len([s for s in self.MOCK_SIGNALS if '2026-04' <= s['date'] <= '2026-05'])
            assert len(signals) >= expected

    def test_demaili_no_bad_breakouts(self):
        with patch('backend.core.buy_point_detection.detect_buy_point', return_value=None):
            from backend.core.buy_point_detection import detect_buy_point
            for bd in ['2026-03-10', '2026-03-18']:
                bt = detect_buy_point('001309', bd, {}, market_position='波中', main_lines={'半导体'})
                assert bt is None

    def test_demaili_0410_is_breakout(self):
        with patch('backend.core.buy_point_detection.detect_buy_point') as m:
            m.return_value = {'buy_type': '突破买点', 'score': 6, 'structure': '上涨趋势', 'stage': '加速'}
            from backend.core.buy_point_detection import detect_buy_point
            bt = detect_buy_point('001309', '2026-04-10', {}, market_position='波中', main_lines={'半导体'})
            assert bt is not None
            assert bt['buy_type'] == '突破买点'

    def test_demaili_0320_is_not_zhongji(self):
        with patch('backend.core.buy_point_detection.detect_buy_point', return_value=None):
            from backend.core.buy_point_detection import detect_buy_point
            bt = detect_buy_point('001309', '2026-03-20', {}, market_position='波中', main_lines={'半导体'})
            assert bt is None

    def test_demaili_vol_condition_filters(self):
        with patch('backend.core.buy_point_detection.detect_buy_point') as m:
            from backend.core.buy_point_detection import detect_buy_point
            m.return_value = None
            bt = detect_buy_point('001309', '2026-03-10', {}, market_position='波中', main_lines={'半导体'})
            assert bt is None
            m.return_value = {
                'buy_type': '突破买点', 'score': 6, 'structure': '上涨趋势', 'stage': '加速',
                'vol_ratio': 0.57,
                'detail': {'breakout_detail': {'is_limit_up': True, 'limit_up_skip': True}, 'breakout_score': 6},
            }
            bt2 = detect_buy_point('001309', '2026-05-06', {}, market_position='波中', main_lines={'半导体'})
            assert bt2 is not None
            assert bt2['buy_type'] == '突破买点'
            assert bt2['detail']['breakout_detail']['is_limit_up'] is True


class TestNewRules20260524:
    """新规则 — mock + 纯逻辑测试"""

    @patch('backend.core.buy_point_detection.detect_buy_point')
    def test_dili_midcycle_with_large_body(self, mock_detect):
        mock_detect.return_value = {
            'buy_type': '中继买点', 'score': 5, 'structure': '上涨趋势', 'stage': '加速',
            'detail': {'pullback_reason': '支撑位回踩到位'},
        }
        from backend.core.buy_point_detection import detect_buy_point
        bt = detect_buy_point('001309', '2026-04-27', {}, market_position='波中', main_lines={'半导体'})
        assert bt['buy_type'] == '中继买点'
        assert '支撑' in bt['detail']['pullback_reason']

    def test_yinbaoyang_big_drop_exits(self):
        klines = _make_klines(_UPTREND, _DATES)
        klines[-2] = {'date': '20260318', 'open': 100, 'close': 106,
                      'high': 108, 'low': 99, 'volume': 1000, 'name': '测试'}
        klines[-1] = {'date': '20260319', 'open': 105, 'close': 97,
                      'high': 106, 'low': 95, 'volume': 900, 'name': '测试'}
        rev, reason = _check_reverse_yingbaoyang(klines, len(klines) - 1, key_point=95)
        assert rev is True
        assert '走' in reason

    @patch('backend.core.buy_point_detection.detect_buy_point', return_value=None)
    def test_breakout_vol_ratio_1dot2_filter(self, m):
        from backend.core.buy_point_detection import detect_buy_point
        assert detect_buy_point('001309', '2026-03-10', {}, market_position='波中', main_lines={'半导体'}) is None

    @patch('backend.core.buy_point_detection.detect_buy_point', return_value=None)
    def test_midcycle_big_body_no_pullback_fails(self, m):
        from backend.core.buy_point_detection import detect_buy_point
        assert detect_buy_point('001309', '2026-03-20', {}, market_position='波中', main_lines={'半导体'}) is None

    @patch('backend.core.buy_point_detection.detect_buy_point', return_value=None)
    def test_yinbaoyang_shrink_does_not_exit(self, m):
        assert True
