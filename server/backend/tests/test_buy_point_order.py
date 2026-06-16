"""测试 — detect_buy_point 接受降序K线"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from threel_core.buy_point_detection import detect_buy_point, find_idx


def make_klines_ascending():
    """构造升序（旧→新）60根K线用于测试"""
    klines = []
    base_price = 100.0
    for i in range(60):
        day = 20260318 + i  # 模拟日期
        if day % 100 > 31:
            day = day + 100 - 31 + 1  # 简单跳月
        price = base_price + i * 0.5 + (i % 10) * 0.2
        klines.append({
            'date': str(day),
            'open': round(price - 0.5, 2),
            'close': round(price, 2),
            'high': round(price + 1.0, 2),
            'low': round(price - 1.0, 2),
            'volume': 1000000 + i * 10000,
        })
    return klines


def make_klines_descending():
    """构造降序（新→旧）60根K线"""
    asc = make_klines_ascending()
    return list(reversed(asc))


class TestDetectBuyPointOrder:

    def test_find_idx_works_on_ascending(self):
        """升序K线 find_idx 返回正确索引"""
        kls = make_klines_ascending()
        # 第1根日期
        idx = find_idx(kls[0]['date'], kls)
        assert idx == 0, f"升序首日应在 index=0, 实际 {idx}"
        # 最后1根日期
        idx = find_idx(kls[-1]['date'], kls)
        assert idx == len(kls) - 1, f"升序末日应在 index=倒数, 实际 {idx}"

    def test_find_idx_on_descending_still_finds(self):
        """降序K线 find_idx 仍能找到日期（在头部）"""
        kls = make_klines_descending()
        # 第1根是最新的
        idx = find_idx(kls[0]['date'], kls)
        assert idx == 0, f"降序首日(最新)在 index=0, 实际 {idx}"
        # 降序时最新日期在 index=0 → idx < 30 会被拒绝

    def test_detect_buy_point_ascending(self):
        """升序K线应能正常检测买点"""
        kls = make_klines_ascending()
        all_stocks = {'测试': {'000001': kls}}
        bt = detect_buy_point('000001', kls[-1]['date'], all_stocks, main_lines=[])
        # 可能没有买点（模拟数据），但不应因idx<30被拒绝
        # 关键是 find_idx 找到的 idx 应 >= 30
        idx = find_idx(kls[-1]['date'], kls)
        assert idx >= 30, f"升序时最后日期的 idx 应 >= 30, 实际 {idx}"

    def test_detect_buy_point_descending_fails(self):
        """降序K线当前会失败（idx<30），需要修复"""
        kls = make_klines_descending()
        all_stocks = {'测试': {'000001': kls}}
        bt = detect_buy_point('000001', kls[0]['date'], all_stocks, main_lines=[])
        # 因为降序，最新日期在 index=0 → idx=0 < 30 → 返回 None
        idx = find_idx(kls[0]['date'], kls)
        assert idx < 30, f"降序时最新日期的 idx = {idx} < 30"
        assert bt is None, "降序K线当前应返回 None"

    def test_auto_reverse_descending_in_detect(self):
        """期望 detect_buy_point 内部自动处理降序K线"""
        asc_kls = make_klines_ascending()
        desc_kls = make_klines_descending()
        all_stocks_asc = {'测试': {'000001': asc_kls}}
        all_stocks_desc = {'测试': {'000001': desc_kls}}

        bt_asc = detect_buy_point('000001', asc_kls[-1]['date'], all_stocks_asc, main_lines=[])
        bt_desc = detect_buy_point('000001', desc_kls[0]['date'], all_stocks_desc, main_lines=[])

        # 两者不应因顺序问题结果差异过大
        # bt_asc 和 bt_desc 要么都有买点，要么都没有
        if bt_asc is not None:
            assert bt_desc is not None, "降序K线处理后有买点"
