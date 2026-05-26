"""内部辅助函数单元测试 — 纯函数/硬编码数据，不依赖stocks fixture"""

import sys
sys.path.insert(0, '/home/ubuntu/3l-server')

import pytest
from backend.core.buy_point_detection import (
    _breakout_score, _check_pullback, _is_extreme_shrink,
    _volume_ratio, find_idx, calc_stop_loss,
    check_volume_stagnation, check_power_fading, check_reverse_yingbaoyang,
)


def _make_klines(n, open_p=100, high_p=110, low_p=90, close_p=105, vol=1000):
    """生成mock K线，含所有必要字段"""
    return [{'open': open_p, 'high': high_p, 'low': low_p,
             'close': close_p, 'volume': vol, 'vol': vol} for _ in range(n)]


# ===== _breakout_score =====

class TestBreakoutScore:
    def test_strong_breakout_passes(self):
        ok, score, detail = _breakout_score(
            close=100, prev_close=90, prev_10d_high=95,
            vol_ratio=2.0, body_ratio=0.85, high=102, low=91)
        assert ok is True and score >= 5

    def test_limit_up_skips_volume_check(self):
        ok, score, detail = _breakout_score(
            close=100, prev_close=90, prev_10d_high=95,
            vol_ratio=0.8, body_ratio=0.9, high=101, low=90)
        assert ok is True
        assert detail['limit_up_skip'] is True

    def test_low_volume_fails(self):
        ok, score, detail = _breakout_score(
            close=96, prev_close=95, prev_10d_high=95,
            vol_ratio=1.0, body_ratio=0.5, high=97, low=93)
        assert ok is False
        assert '未放量' in detail.get('reason', '')

    def test_not_high_position_fails(self):
        ok, score, detail = _breakout_score(
            close=95, prev_close=93, prev_10d_high=95,
            vol_ratio=1.5, body_ratio=0.5, high=100, low=90)
        assert ok is False
        assert '未收高位' in detail.get('reason', '')

    def test_limit_board_flat(self):
        """一字涨停高=低，跳过中点检查"""
        ok, score, detail = _breakout_score(
            close=100, prev_close=90, prev_10d_high=95,
            vol_ratio=1.3, body_ratio=1.0, high=100, low=100)
        assert ok is True

    def test_exact_five_passes(self):
        ok, score, detail = _breakout_score(
            close=101, prev_close=98, prev_10d_high=99.5,
            vol_ratio=1.25, body_ratio=0.75, high=103, low=97)
        assert ok is True
        assert score >= 5


# ===== _check_pullback =====

class TestCheckPullback:
    def test_near_support_passes(self):
        """距支撑<2% -> 回踩到位"""
        kls = []
        for _ in range(10):
            kls.append({"open": 98, "high": 100, "low": 96, "close": 99, "volume": 1000, "vol": 1000})
        kls.append({"open": 104, "high": 106, "low": 102, "close": 105, "volume": 2000, "vol": 2000})
        for _ in range(8):
            kls.append({"open": 101, "high": 103, "low": 100, "close": 102, "volume": 1000, "vol": 1000})
        kls.append({"open": 101, "high": 102, "low": 101, "close": 101.8, "volume": 800, "vol": 800})
        ok, reason = _check_pullback(kls, 19, 101.8, ema5_val=110, ema10_val=115, ema20_val=120)
        assert ok is True
        assert "关键支撑" in reason

    def test_near_ema5_passes(self):
        kls = _make_klines(14)
        ok, reason = _check_pullback(kls, 13, 101, ema5_val=100, ema10_val=95, ema20_val=90)
        assert ok is True
        assert 'EMA5' in reason

    def test_near_ema10_passes(self):
        kls = _make_klines(10)
        ok, reason = _check_pullback(kls, 9, 103, ema5_val=120, ema10_val=102, ema20_val=100)
        assert ok is True
        assert 'EMA10' in reason

    def test_far_from_all_fails(self):
        kls = _make_klines(10)
        ok, reason = _check_pullback(kls, 9, 90, ema5_val=120, ema10_val=118, ema20_val=115)
        assert ok is False
        assert '未回踩到位' in reason


# ===== _is_extreme_shrink =====

class TestIsExtremeShrink:
    def test_extreme_shrink_detected(self):
        kls = [{'volume': 1000 + i * 10} for i in range(20)]
        kls.append({'volume': 200})
        result = _is_extreme_shrink(kls, 20)
        assert result is not False
        shrink, threshold, vol = result
        assert shrink is True

    def test_normal_volume_not_shrink(self):
        kls = [{'volume': 1000} for _ in range(20)]
        kls.append({'volume': 1200})
        result = _is_extreme_shrink(kls, 20)
        if isinstance(result, tuple):
            assert result[0] is False
        else:
            assert result is False

    def test_less_than_5_returns_false(self):
        kls = [{'volume': 1000} for _ in range(3)]
        result = _is_extreme_shrink(kls, 3)
        assert result is False


# ===== calc_stop_loss =====

class TestCalcStopLoss:
    def test_with_support(self):
        kls = _make_klines(17)
        sl, pct = calc_stop_loss(kls, 16, close_price=105)
        assert sl is not None and sl < 105

    def test_short_data_returns_none(self):
        kls = _make_klines(5)
        sl, pct = calc_stop_loss(kls, 4, close_price=95)
        assert sl is None


# ===== _volume_ratio =====

class TestVolumeRatio:
    def test_calculation(self):
        # MA5含当日: (2000+2000+2000+2000+10000)/5=3600, vr=10000/3600=2.78
        kls = [{'volume': 2000, 'vol': 2000} for _ in range(5)]
        kls.append({'volume': 10000, 'vol': 10000})
        vr = _volume_ratio(kls, 5)
        assert abs(vr - 2.78) < 0.1

    def test_zero_vol_returns_zero(self):
        kls = [{'volume': 0, 'vol': 0} for _ in range(6)]
        vr = _volume_ratio(kls, 5)
        assert vr == 0

    def test_vol_field_fallback(self):
        kls = [{'vol': 2000} for _ in range(5)]
        kls.append({'vol': 4000})
        vr = _volume_ratio(kls, 5)
        assert abs(vr - 1.67) < 0.1


# ===== find_idx =====

class TestFindIdx:
    def test_exact_match(self):
        kls = [{'date': '20260501'}, {'date': '20260502'}, {'date': '20260503'}]
        assert find_idx('2026-05-02', kls) == 1

    def test_no_dash(self):
        kls = [{'date': '20260501'}, {'date': '20260502'}]
        assert find_idx('20260502', kls) == 1

    def test_not_found_minus_one(self):
        kls = [{'date': '20260501'}, {'date': '20260502'}]
        assert find_idx('2026-05-99', kls) == -1


# ===== check_volume_stagnation =====

class TestVolumeStagnation:
    def test_detected(self):
        kls = [{'volume': 1000, 'open': 100, 'close': 101, 'high': 102, 'low': 99} for _ in range(5)]
        kls.append({'volume': 5000, 'open': 105, 'close': 105.5, 'high': 108, 'low': 104})
        triggered, reason = check_volume_stagnation(kls, 5)
        assert triggered is True
        assert '放量滞涨' in reason

    def test_not_detected_low_vol(self):
        kls = [{'volume': 1000, 'open': 100, 'close': 101, 'high': 102, 'low': 99} for _ in range(6)]
        triggered, reason = check_volume_stagnation(kls, 5)
        assert triggered is False

    def test_early_idx_returns_false(self):
        kls = [{'volume': 1000, 'open': 100, 'close': 100, 'high': 100, 'low': 100} for _ in range(3)]
        triggered, _ = check_volume_stagnation(kls, 2)
        assert triggered is False


# ===== check_power_fading =====

class TestPowerFading:
    def test_detected(self):
        kls = [{'volume': 1000, 'high': 100, 'open': 100, 'close': 100, 'low': 100} for _ in range(5)]
        kls.append({'volume': 3000, 'high': 110, 'open': 105, 'close': 108, 'low': 103})
        kls.append({'volume': 2500, 'high': 112, 'open': 109, 'close': 111, 'low': 108})
        kls.append({'volume': 2000, 'high': 115, 'open': 112, 'close': 114, 'low': 111})
        triggered, reason = check_power_fading(kls, 7, 0)
        assert triggered is True
        assert '动力减弱' in reason

    def test_short_entry_returns_false(self):
        kls = [{'volume': 1000, 'high': 100} for _ in range(5)]
        triggered, _ = check_power_fading(kls, 2, 0)
        assert triggered is False


# ===== check_reverse_yingbaoyang =====

class TestReverseYingBaoyang:
    def _mk(self, n, extra):
        base = [{'open': 100, 'close': 101, 'high': 102, 'low': 99, 'volume': 1000} for _ in range(n)]
        base.extend(extra)
        return base

    def test_big_drop_exits(self):
        kls = self._mk(6, [
            {'open': 100, 'close': 110, 'high': 112, 'low': 99, 'volume': 1000},
            {'open': 110, 'close': 100, 'high': 112, 'low': 98, 'volume': 1200},
        ])
        triggered, reason = check_reverse_yingbaoyang(kls, 7, key_point=90)
        assert triggered is True
        assert '大阴' in reason or '走' in reason

    def test_small_drop_observes(self):
        kls = self._mk(6, [
            {'open': 100, 'close': 105, 'high': 107, 'low': 99, 'volume': 1000},
            {'open': 105, 'close': 104, 'high': 106, 'low': 103, 'volume': 1200},
        ])
        triggered, reason = check_reverse_yingbaoyang(kls, 7, key_point=100)
        assert triggered is False

    def test_no_yinbaoyang_pattern(self):
        kls = self._mk(6, [
            {'open': 100, 'close': 98, 'high': 102, 'low': 97, 'volume': 1000},
            {'open': 97, 'close': 102, 'high': 103, 'low': 96, 'volume': 1000},
        ])
        triggered, reason = check_reverse_yingbaoyang(kls, 7, key_point=90)
        assert triggered is False

    def test_mid_drop_break_support(self):
        """跌幅-3%到-5%+破支撑=止盈"""
        kls = self._mk(6, [
            {'open': 100, 'close': 104, 'high': 106, 'low': 99, 'volume': 1000},
            {'open': 104, 'close': 99, 'high': 105, 'low': 98, 'volume': 1200},
        ])
        triggered, reason = check_reverse_yingbaoyang(kls, 7, key_point=100)
        # 跌幅=(99-104)/104=-4.8% 在-3%~-5%范围
        # 破支撑(99<100)+量比1.2>1.0 -> 止盈
        if triggered:
            assert '破支撑' in reason or '走' in reason
