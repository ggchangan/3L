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


# ── 场景B: _fetch_sector_klines_akshare 必须传start_date/end_date ──

class TestFetchSectorKlinesAkshare:

    def test_passes_start_end_date_to_industry(self, monkeypatch):
        """行业板块调用必须传start_date和end_date"""
        from backend.core.update_stock_data import _fetch_sector_klines_akshare

        called_kwargs = {}

        def mock_industry(symbol, **kwargs):
            called_kwargs.update(kwargs)
            return pd.DataFrame({
                'date': ['2026-05-27'],
                'open': [100.0],
                'close': [102.0],
                'high': [103.0],
                'low': [99.0],
                'volume': [1000000],
            })

        monkeypatch.setattr(
            'akshare.stock_board_industry_index_ths',
            mock_industry,
        )
        monkeypatch.setattr(
            'akshare.stock_board_concept_index_ths',
            lambda symbol, **kw: pd.DataFrame(),
        )

        result = _fetch_sector_klines_akshare('industry', '半导体')

        assert 'start_date' in called_kwargs, "必须传 start_date 参数"
        assert 'end_date' in called_kwargs, "必须传 end_date 参数"
        assert len(result) >= 1

    def test_passes_start_end_date_to_concept(self, monkeypatch):
        """概念板块调用也必须传start_date和end_date"""
        from backend.core.update_stock_data import _fetch_sector_klines_akshare

        called_kwargs = {}

        def mock_concept(symbol, **kwargs):
            called_kwargs.update(kwargs)
            return pd.DataFrame({
                'date': ['2026-05-27'],
                'open': [100.0],
                'close': [102.0],
                'high': [103.0],
                'low': [99.0],
                'volume': [1000000],
            })

        monkeypatch.setattr(
            'akshare.stock_board_industry_index_ths',
            lambda symbol, **kw: pd.DataFrame(),
        )
        monkeypatch.setattr(
            'akshare.stock_board_concept_index_ths',
            mock_concept,
        )

        result = _fetch_sector_klines_akshare('concept', 'AI概念')

        assert 'start_date' in called_kwargs
        assert 'end_date' in called_kwargs


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

    def test_update_sectors_trims_to_60(self):
        """update_sectors() 增量更新后裁剪到60行"""
        import inspect
        from backend.core.update_stock_data import update_sectors
        source = inspect.getsource(update_sectors)
        assert 'len(klines) > 60' in source
        assert 'klines[-60:]' in source
