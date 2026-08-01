"""Tushare 前复权公式回归测试。"""
import math

import pytest

from threel_core.price_adjustment import qfq_ratio


def test_qfq_uses_historical_factor_over_latest_factor():
    ratio = qfq_ratio(116.713, 139.008)
    assert ratio == pytest.approx(116.713 / 139.008)
    assert 9.21 * ratio == pytest.approx(7.7319, rel=1e-3)
    assert ratio < 1


@pytest.mark.parametrize('factor,base', [
    (None, 2), (1, None), (0, 2), (-1, 2), (1, 0),
    (math.nan, 2), (1, math.inf), ('bad', 2),
])
def test_qfq_invalid_factor_is_explicitly_unavailable(factor, base):
    assert qfq_ratio(factor, base) is None


def _daily_rows():
    return [
        {'trade_date': '20260724', 'open': 11.0, 'high': 11.2, 'low': 10.9, 'close': 11.1, 'vol': 100},
        {'trade_date': '20240102', 'open': 9.0, 'high': 9.3, 'low': 8.9, 'close': 9.21, 'vol': 80},
    ]


def test_tushare_db_applies_official_qfq_direction():
    from backend.data_access.tushare_db import TushareDB
    db = object.__new__(TushareDB)
    db.query_many = lambda *_args, **_kwargs: [
        {'trade_date': '20260724', 'adj_factor': 139.008},
        {'trade_date': '20240102', 'adj_factor': 116.713},
    ]
    adjusted = db._apply_qfq(_daily_rows(), '000001.SZ')
    assert adjusted[0]['close'] == 11.1
    assert adjusted[1]['close'] == 7.73
    assert all(item['adjustment_status'] == 'qfq' for item in adjusted)


def test_shared_core_batch_reader_applies_official_qfq_direction():
    from threel_core.db import _apply_qfq_batch

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args): pass
        def fetchall(self):
            return [
                {'trade_date': '20260724', 'adj_factor': 139.008},
                {'trade_date': '20240102', 'adj_factor': 116.713},
            ]
    class Connection:
        def cursor(self, *_args): return Cursor()

    rows = _daily_rows()
    adjusted = _apply_qfq_batch(Connection(), '000001.SZ', rows, [r['trade_date'] for r in rows])
    assert adjusted[-1]['close'] == 11.1
    assert adjusted[0]['close'] == 7.73
    assert all(item['adjustment_status'] == 'qfq' for item in adjusted)


def test_tushare_db_never_mixes_raw_and_adjusted_prices_when_factor_missing():
    from backend.data_access.tushare_db import TushareDB
    db = object.__new__(TushareDB)
    db.query_many = lambda *_args, **_kwargs: [{'trade_date': '20260724', 'adj_factor': 139.008}]
    result = db._apply_qfq(_daily_rows(), '000001.SZ')
    assert [item['close'] for item in result] == [11.1, 9.21]
    assert all(item['adjustment_status'] == 'raw_factor_incomplete' for item in result)


def test_shared_core_reader_never_mixes_raw_and_adjusted_prices_when_factor_missing():
    from threel_core.db import _apply_qfq_batch

    class Cursor:
        def __enter__(self): return self
        def __exit__(self, *_args): return False
        def execute(self, *_args): pass
        def fetchall(self): return [{'trade_date': '20260724', 'adj_factor': 139.008}]
    class Connection:
        def cursor(self, *_args): return Cursor()

    rows = _daily_rows()
    result = _apply_qfq_batch(Connection(), '000001.SZ', rows, [r['trade_date'] for r in rows])
    assert [item['close'] for item in result] == [9.21, 11.1]
    assert all(item['adjustment_status'] == 'raw_factor_incomplete' for item in result)


def test_tushare_db_missing_latest_factor_returns_one_raw_sequence():
    from backend.data_access.tushare_db import TushareDB
    db = object.__new__(TushareDB)
    db.query_many = lambda *_args, **_kwargs: [{'trade_date': '20240102', 'adj_factor': 116.713}]
    result = db._apply_qfq(_daily_rows(), '000001.SZ')
    assert [item['close'] for item in result] == [11.1, 9.21]
    assert all(item['adjustment_status'] == 'raw_factor_incomplete' for item in result)
