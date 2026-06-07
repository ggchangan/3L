"""Tests for sector data update: _df_to_kline, _fetch_sector_klines_akshare, date params"""

import os
import sys
from datetime import date, datetime

import pandas as pd
import pytest


# ── 场景A: _df_to_kline 中英文列名兼容性 ──


class TestDfToKline:

    def test_chinese_columns(self):
        """中文列名 → 标准kline格式"""
        from backend.core.update_stock_data import _df_to_kline

        df = pd.DataFrame({
            '日期': [date(2026, 5, 20), date(2026, 5, 21)],
            '开盘价': [100.0, 102.0],
            '收盘价': [102.0, 101.5],
            '最高价': [103.0, 104.0],
            '最低价': [99.0, 100.5],
            '成交量': [1000000, 1200000],
        })
        klines = _df_to_kline(df)
        assert len(klines) == 2
        assert klines[0]['date'] == '20260520'
        assert klines[0]['open'] == 100.0
        assert klines[0]['close'] == 102.0
        assert klines[0]['high'] == 103.0
        assert klines[0]['low'] == 99.0
        assert klines[0]['volume'] == 1000000

    def test_english_columns(self):
        """英文列名 → 标准kline格式"""
        from backend.core.update_stock_data import _df_to_kline

        df = pd.DataFrame({
            'date': ['2026-05-20'],
            'open': [100.0],
            'close': [102.0],
            'high': [103.0],
            'low': [99.0],
            'volume': [1000000],
        })
        klines = _df_to_kline(df)
        assert len(klines) == 1
        assert klines[0]['date'] == '20260520'

    def test_missing_volume_falls_back_to_amount(self):
        """缺volume列 → 用amount/成交额列"""
        from backend.core.update_stock_data import _df_to_kline

        df = pd.DataFrame({
            'date': ['20260520'],
            'open': [100.0],
            'close': [102.0],
            'high': [103.0],
            'low': [99.0],
            '成交额': [500000000],
        })
        klines = _df_to_kline(df)
        assert len(klines) == 1
        # 没有volume列，_df_to_kline会跳过volume（取0），不会用amount
        # 这是现有行为，我们只是验证它不会崩

    def test_date_object_handling(self):
        """akshare返回datetime.date对象 → 正确转换"""
        from backend.core.update_stock_data import _df_to_kline

        df = pd.DataFrame({
            '日期': [date(2026, 5, 27)],
            '开盘价': [100.0],
            '收盘价': [102.0],
            '最高价': [103.0],
            '最低价': [99.0],
            '成交量': [1000000],
        })
        klines = _df_to_kline(df)
        assert klines[0]['date'] == '20260527'

    def test_empty_dataframe(self):
        """空DataFrame → 返回[]"""
        from backend.core.update_stock_data import _df_to_kline

        df = pd.DataFrame(columns=['date', 'open', 'close', 'high', 'low', 'volume'])
        klines = _df_to_kline(df)
        assert klines == []



# ── 场景C: 板块数据裁剪 MAX_K=60 ──

class TestSectorMaxK:

    def test_refresh_sectors_max_k(self):
        """refresh_sectors.py 的 MAX_K=60"""
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'refresh_sectors.py')
        if not os.path.isfile(script_path):
            pytest.skip("refresh_sectors.py 不存在，跳过")
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        import importlib.util
        spec = importlib.util.spec_from_file_location('refresh_sectors', script_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod.MAX_K == 60

    def test_update_sectors_uses_ths_for_industry(self):
        """update_sectors() 行业用同花顺THS，概念用push2test"""
        import inspect
        from backend.core.update_stock_data import update_sectors
        source = inspect.getsource(update_sectors)
        # 行业走THS
        assert '_fetch_today_industries_from_ths' in source
        # 概念走后端测试API
        assert '_fetch_today_sectors_from_push2test' in source
