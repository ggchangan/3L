"""买点扫描15分钟间隔测试

测试覆盖：
1. _get_timeslot_key — 15分钟时段标识计算（边界值/跨小时）
2. _find_latest_cache — 15分钟文件名匹配（新旧格式兼容）
3. _should_trigger_scan — 交易日+交易时段+缓存过期的完整判定
4. get_buy_signals — 完整流程（mocked：固定时间+临时缓存目录）
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ==============================================================
# 夹具
# ==============================================================

@pytest.fixture
def temp_cache_dir():
    """临时缓存目录"""
    with tempfile.TemporaryDirectory() as td:
        yield td


def _make_cache(dir_path, timeslot, valid=True):
    """在 dir_path 下创建一份模拟缓存文件"""
    fname = f'buy_signals_{timeslot}.json'
    data = {
        'signals': [{'name': 'test', 'code': '000001', 'buy_type': '测试'}] if valid else [],
        'scan_time': timeslot.replace('_', ' ') + ':00',
        'stocks_scanned': 1,
    }
    fpath = os.path.join(dir_path, fname)
    with open(fpath, 'w') as f:
        json.dump(data, f)
    return fpath


# ==============================================================
# _get_timeslot_key 测试
# ==============================================================

class TestTimeslotKey:
    """时段标识计算 — 回归测试2：15分钟粒度"""

    def test_00_minute(self):
        """整点 → 11-00"""
        dt = datetime(2026, 6, 12, 11, 0, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-00'

    def test_01_minute(self):
        """整点过1分 → 11-00（仍在同一时段）"""
        dt = datetime(2026, 6, 12, 11, 1, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-00'

    def test_14_minute(self):
        """14分 → 11-00（时段边界内）"""
        dt = datetime(2026, 6, 12, 11, 14, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-00'

    def test_15_minute(self):
        """15分 → 11-15（跨时段）"""
        dt = datetime(2026, 6, 12, 11, 15, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-15'

    def test_29_minute(self):
        """29分 → 11-15"""
        dt = datetime(2026, 6, 12, 11, 29, 59)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-15'

    def test_45_minute(self):
        """45分 → 11-45"""
        dt = datetime(2026, 6, 12, 11, 45, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-45'

    def test_59_minute(self):
        """59分 → 11-45（仍在同一时段）"""
        dt = datetime(2026, 6, 12, 11, 59, 0)
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(dt) == '2026-06-12_11-45'

    def test_cross_hour(self):
        """跨小时：11:59→11-45, 12:00→12-00"""
        from backend.services.monitor_service import _get_timeslot_key
        assert _get_timeslot_key(datetime(2026, 6, 12, 11, 59, 0)) == '2026-06-12_11-45'
        assert _get_timeslot_key(datetime(2026, 6, 12, 12, 0, 0)) == '2026-06-12_12-00'


# ==============================================================
# _find_latest_cache 测试（15分钟匹配）
# ==============================================================

class TestFindLatestCache:
    """最新缓存查找 — 支持15分钟文件名"""

    def test_15min_format_matched(self):
        """匹配 buy_signals_YYYY-MM-DD_HH-MM.json"""
        from backend.services.monitor_service import _find_latest_cache
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_11-00')
            _make_cache(td, '2026-06-12_11-15')
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _find_latest_cache()
                assert result is not None
                assert '11-15' in result

    def test_returns_newest(self):
        """多缓存返回最新的"""
        from backend.services.monitor_service import _find_latest_cache
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_09-30')
            _make_cache(td, '2026-06-12_10-00')
            _make_cache(td, '2026-06-12_10-15')
            _make_cache(td, '2026-06-12_10-45')
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _find_latest_cache()
                assert '10-45' in result

    def test_cross_day_newest(self):
        """跨天也是最新日期优先"""
        from backend.services.monitor_service import _find_latest_cache
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-11_14-30')
            _make_cache(td, '2026-06-12_09-00')
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _find_latest_cache()
                assert '06-12' in result

    def test_old_hour_format_still_matched(self):
        """旧格式 buy_signals_YYYY-MM-DD_HH.json 也兼容"""
        from backend.services.monitor_service import _find_latest_cache
        with tempfile.TemporaryDirectory() as td:
            # 旧格式
            fpath = os.path.join(td, 'buy_signals_2026-06-12_10.json')
            with open(fpath, 'w') as f:
                json.dump({'signals': [{'name': 'old'}]}, f)
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _find_latest_cache()
                assert result is not None

    def test_no_cache_returns_none(self):
        """无缓存文件返回None"""
        from backend.services.monitor_service import _find_latest_cache
        with tempfile.TemporaryDirectory() as td:
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                assert _find_latest_cache() is None


# ==============================================================
# _should_trigger_scan 测试
# ==============================================================

class TestShouldTriggerScan:
    """扫描触发判定 — 交易日+交易时段+缓存过期"""

    def test_trading_day_morning_trigger(self):
        """交易日 10:00 → 当前无缓存 → 触发扫描"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _should_trigger_scan(
                    datetime(2026, 6, 12, 10, 0, 0),  # 周五
                    current_cache_path=os.path.join(td, 'buy_signals_2026-06-12_10-00.json'),
                )
                assert result is True, '交易日盘中无缓存应触发扫描'

    def test_trading_day_cache_hit_no_trigger(self):
        """交易日 10:00 → 已有当前缓存 → 不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_10-00')
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_10-00.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 12, 10, 0, 0),
                current_cache_path=cache_path,
            )
            assert result is False, '已有当前缓存不应触发扫描'

    def test_non_trading_day_no_trigger(self):
        """周六 → 有旧缓存但不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_14-45')  # 周五的旧缓存
            cache_path = os.path.join(td, 'buy_signals_2026-06-13_10-00.json')  # 周六
            result = _should_trigger_scan(
                datetime(2026, 6, 13, 10, 0, 0),  # 周六
                current_cache_path=cache_path,
            )
            assert result is False, '非交易日不触发扫描'

    def test_after_market_no_trigger(self):
        """交易日 15:30 → 收盘后不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_15-30.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 12, 15, 30, 0),
                current_cache_path=cache_path,
            )
            assert result is False, '盘后不触发扫描'

    def test_before_market_no_trigger(self):
        """交易日 09:00 → 开盘前不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_09-00.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 12, 9, 0, 0),
                current_cache_path=cache_path,
            )
            assert result is False, '盘前不触发扫描'

    def test_lunch_break_no_trigger(self):
        """交易日 12:00 → 午休不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_12-00.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 12, 12, 0, 0),
                current_cache_path=cache_path,
            )
            assert result is False, '午休不触发扫描'

    def test_trading_day_no_cache_trigger(self):
        """交易日 10:00 → 没有旧缓存也没有当前缓存 → 触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            with patch('backend.services.monitor_service.CACHE_DIR', td):
                result = _should_trigger_scan(
                    datetime(2026, 6, 12, 10, 0, 0),
                    current_cache_path=os.path.join(td, 'buy_signals_2026-06-12_10-00.json'),
                )
                assert result is True

    def test_sunday_no_trigger(self):
        """周日 → 不触发"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, 'buy_signals_2026-06-14_10-00.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 14, 10, 0, 0),  # 周日
                current_cache_path=cache_path,
            )
            assert result is False, '周日不触发扫描'

    def test_last_trading_slot_no_expiry(self):
        """交易日 14:45 → 当前有缓存 → 不触发（最后一个交易时段）"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_14-45')
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_14-45.json')
            result = _should_trigger_scan(
                datetime(2026, 6, 12, 14, 45, 0),
                current_cache_path=cache_path,
            )
            assert result is False


# ==============================================================
# _should_trigger_scan 集成测试（用真实 _is_trading_time 代码）
# ==============================================================

class TestShouldTriggerScanIntegration:
    """用真实 _is_trading_time 判定的集成场景"""

    def test_mocked_trading_time_trigger(self):
        """模拟交易时段10:00，真实 is_trading_session 走 mock，触发扫描"""
        from backend.services.monitor_service import _should_trigger_scan
        with tempfile.TemporaryDirectory() as td:
            with patch('backend.core.data_models.is_trading_session', return_value=True):
                result = _should_trigger_scan(
                    datetime(2026, 6, 12, 10, 0, 0),
                    current_cache_path=os.path.join(td, 'buy_signals_2026-06-12_10-00.json'),
                )
                assert result is True


# ==============================================================
# get_buy_signals 完整流程测试
# ==============================================================

class TestGetBuySignals:
    """get_buy_signals 完整流程"""

    def test_current_slot_cache_hit(self):
        """当前15分钟时段有缓存 → 直接返回"""
        from backend.services.monitor_service import get_buy_signals
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_10-00')
            with patch.multiple(
                'backend.services.monitor_service',
                CACHE_DIR=td,
                _should_trigger_scan=MagicMock(return_value=False),
            ):
                result = get_buy_signals()
                assert result is not None
                assert 'signals' in result
                assert len(result['signals']) == 1

    def test_no_cache_returns_empty_with_scan_time(self):
        """无任何缓存 → 返回空 + scan_time"""
        from backend.services.monitor_service import get_buy_signals
        with tempfile.TemporaryDirectory() as td:
            with patch.multiple(
                'backend.services.monitor_service',
                CACHE_DIR=td,
                datetime=MagicMock(wraps=datetime),
            ):
                # 模拟 get_buy_signals 中没有缓存的情况
                # 通过 mock _should_trigger_scan 返回 True 来验证走后台扫描路径
                with patch('backend.services.monitor_service._should_trigger_scan', return_value=True):
                    with patch('backend.services.monitor_service._start_background_scan') as mock_scan:
                        with patch('backend.services.monitor_service._find_latest_cache', return_value=None):
                            result = get_buy_signals()
                            assert result['signals'] == []
                            assert 'scan_time' in result
                            assert result['stocks_scanned'] == 0
                            mock_scan.assert_called_once()

    def test_old_cache_triggers_scan(self):
        """有旧缓存但当前时段无缓存 → 返回旧缓存 + 后台启动扫描"""
        from backend.services.monitor_service import get_buy_signals
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_09-30')
            with patch.multiple(
                'backend.services.monitor_service',
                CACHE_DIR=td,
                _should_trigger_scan=MagicMock(return_value=True),  # 盘中+无当前缓存
            ):
                with patch('backend.services.monitor_service._start_background_scan') as mock_scan:
                    result = get_buy_signals()
                    assert result is not None
                    assert len(result['signals']) == 1
                    mock_scan.assert_called_once()

    def test_should_not_trigger_outside_trading_hours(self):
        """非交易时间 → 不触发扫描，返回旧缓存"""
        from backend.services.monitor_service import get_buy_signals
        with tempfile.TemporaryDirectory() as td:
            _make_cache(td, '2026-06-12_14-45')
            with patch.multiple(
                'backend.services.monitor_service',
                CACHE_DIR=td,
                _should_trigger_scan=MagicMock(return_value=False),
            ):
                with patch('backend.services.monitor_service._start_background_scan') as mock_scan:
                    result = get_buy_signals()
                    assert result is not None
                    assert len(result['signals']) == 1
                    mock_scan.assert_not_called()

    def test_scan_lock_prevents_duplicate(self):
        """_scan_in_progress 为 True 时不再启动扫描"""
        from backend.services.monitor_service import _start_background_scan, _scan_in_progress, _scan_lock
        with tempfile.TemporaryDirectory() as td:
            cache_path = os.path.join(td, 'buy_signals_2026-06-12_10-00.json')
            # 手动置锁
            with _scan_lock:
                _scan_in_progress_orig = True  # 保存原值，不依赖全局变量
            # 实际上 _scan_in_progress 是模块级变量，直接 mock
            with patch('backend.services.monitor_service._scan_in_progress', True):
                with patch('backend.services.monitor_service._scan_lock'):
                    with patch('backend.services.monitor_service._run_scan_sync') as mock_run:
                        _start_background_scan(cache_path)
                        mock_run.assert_not_called()


# ==============================================================
# 并行抓K线测试（scan_buy_signals.py main 改动部分）
# ==============================================================

class TestParallelKlineFetch:
    """并行抓K线逻辑 — 晚于单元测试，需 mock network"""

    def test_parallel_fetch_basic(self):
        """并行抓取应返回与串行相同的结果"""
        from backend.core.scan_buy_signals import _parallel_fetch_klines
        mock_stocks = [
            {'code': '000001', 'direction': '半导体', 'name': '平安银行'},
            {'code': '000002', 'direction': '房地产', 'name': '万科A'},
        ]

        def fake_klines(code, direction):
            """模拟 get_realtime_kline 返回，35条K线满足>=30条件"""
            return [{'date': '2026-06-12', 'close': 10.0, 'volume': 1000}] * 35

        result = _parallel_fetch_klines(mock_stocks, fetch_fn=fake_klines, max_workers=2)
        assert len(result) == 2
        # 按原始顺序返回
        assert result[0]['code'] == '000001'
        assert result[1]['code'] == '000002'
        assert 'klines' in result[0]
        assert len(result[0]['klines']) == 35

    def test_parallel_skip_failed(self):
        """某只股票抓取失败（返回空列表）应跳过"""
        from backend.core.scan_buy_signals import _parallel_fetch_klines
        mock_stocks = [
            {'code': '000001', 'direction': '半导体', 'name': '平安银行'},
            {'code': '999999', 'direction': '其他', 'name': '无效股票'},
        ]
        call_count = [0]

        def fake_klines(code, direction):
            call_count[0] += 1
            if code == '999999':
                return []  # K线不足30天，跳过
            return [{'date': '2026-06-12', 'close': 10.0, 'volume': 1000}] * 35

        result = _parallel_fetch_klines(mock_stocks, fetch_fn=fake_klines, max_workers=2)
        assert len(result) == 1
        assert result[0]['code'] == '000001'

    def test_parallel_result_order(self):
        """返回顺序应与输入顺序一致"""
        from backend.core.scan_buy_signals import _parallel_fetch_klines
        stocks = [{'code': f'{300+i}', 'direction': '半导体', 'name': f'股{i}'} for i in range(5)]

        def fake_klines(code, direction):
            k = [{'date': '2026-06-12', 'close': float(code[-3:]), 'volume': 1000}] * 35
            return k

        result = _parallel_fetch_klines(stocks, fetch_fn=fake_klines, max_workers=5)
        assert len(result) == 5
        for i in range(5):
            assert result[i]['code'] == f'{300+i}'
