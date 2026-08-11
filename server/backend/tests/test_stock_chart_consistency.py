from datetime import date, timedelta


def _klines(count=60):
    start = date(2026, 5, 1)
    rows = []
    for idx in range(count):
        close = 10 + idx * 0.05
        rows.append({
            'date': (start + timedelta(days=idx)).strftime('%Y%m%d'),
            'name': '测试股票',
            'open': close - 0.03,
            'close': close,
            'high': close + 0.12,
            'low': close - 0.12,
            'volume': 100_000 + idx * 100,
        })
    return rows


def _patch_chart_inputs(monkeypatch, rows):
    monkeypatch.setattr(
        'backend.services.stock_chart_service.get_all_stocks',
        lambda: {},
    )
    monkeypatch.setattr(
        'backend.services.stock_chart_service.get_stock_klines',
        lambda *args, **kwargs: rows,
    )


def test_review_chart_cache_isolated_by_stop_loss(monkeypatch, tmp_path):
    """不同止损价不能命中同一个SVG缓存。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    first, first_error = stock_chart_service.generate_stock_chart(
        '000001', mode='review', stop_loss_price=9.11,
    )
    second, second_error = stock_chart_service.generate_stock_chart(
        '000001', mode='review', stop_loss_price=8.22,
    )

    assert first_error is None and second_error is None
    assert '止损 9.11' in first
    assert '止损 8.22' in second
    assert first != second
    assert len(list(tmp_path.glob('zzqz_stock_chart_*.svg'))) == 2


def test_review_chart_uses_final_marker_without_recomputing_card(monkeypatch, tmp_path):
    """图表只展示复盘最终决策快照，不能脱离市场上下文重算卡片。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    svg, error = stock_chart_service.generate_stock_chart(
        '000001', mode='review', signal_marker='technical_buy',
        signal_date=rows[-2]['date'],
    )

    assert error is None
    assert '>技买<' in svg
    assert '>买<' not in svg


def test_review_chart_cache_isolated_by_signal_snapshot(monkeypatch, tmp_path):
    """同日信号变化后必须重新生成右上角信号图例。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    breakout = [{'key': 'upward_breakout', 'name': '向上突破', 'direction': 'bullish', 'confidence': 80}]
    reversal = [{'key': 'upward_reversal', 'name': '向上反转', 'direction': 'bullish', 'confidence': 75}]

    first, _ = stock_chart_service.generate_stock_chart(
        '000001', mode='review', triggered_signals=breakout,
    )
    second, _ = stock_chart_service.generate_stock_chart(
        '000001', mode='review', triggered_signals=reversal,
    )

    assert '向上突破' in first
    assert '向上反转' in second
    assert first != second


def test_review_chart_cache_invalidated_by_final_marker(monkeypatch, tmp_path):
    """同日最终决策从技术观察变为可执行时必须重绘标记。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    technical, _ = stock_chart_service.generate_stock_chart(
        '000001', mode='review', signal_marker='technical_buy', signal_date=rows[-1]['date'],
    )
    executable, _ = stock_chart_service.generate_stock_chart(
        '000001', mode='review', signal_marker='buy', signal_date=rows[-1]['date'],
    )

    assert '>技买<' in technical
    assert '>买<' in executable
    assert technical != executable


def test_review_chart_does_not_move_missing_signal_date_to_latest_bar(monkeypatch, tmp_path):
    """明确的信号日期不在窗口内时不画标记，不能伪装成最新信号。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    svg, error = stock_chart_service.generate_stock_chart(
        '000001', mode='review', signal_marker='buy', signal_date='20200101',
    )

    assert error is None
    assert '>买<' not in svg


def test_review_chart_cache_invalidated_by_same_day_kline_revision(monkeypatch, tmp_path):
    """末日K线被数据源订正时，即使日期不变也不能命中旧图。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    first, _ = stock_chart_service.generate_stock_chart('000001', mode='review')
    rows[-1]['close'] += 1.5
    rows[-1]['high'] += 1.5
    second, _ = stock_chart_service.generate_stock_chart('000001', mode='review')

    assert first != second
    assert len(list(tmp_path.glob('zzqz_stock_chart_*.svg'))) == 2


def test_trend_chart_cached_response_keeps_stop_loss(monkeypatch, tmp_path):
    """趋势图相同请求第二次从缓存读取时仍应包含止损线。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    def fake_trend_svg(name, code, klines, out_path, trend_bias=None):
        with open(out_path, 'w') as stream:
            stream.write('<svg></svg>')

    monkeypatch.setattr('backend.core.gen_trend_chart.gen_trend_svg', fake_trend_svg)
    first, first_error = stock_chart_service.generate_trend_stock_chart(
        '000001', mode='review', stop_loss_price=9.12,
    )
    second, second_error = stock_chart_service.generate_trend_stock_chart(
        '000001', mode='review', stop_loss_price=9.12,
    )

    assert first_error is None and second_error is None
    assert '止损 9.12' in first
    assert '止损 9.12' in second
    assert first == second


def test_trend_chart_uses_final_marker_and_date(monkeypatch, tmp_path):
    """趋势图保留BIAS参考层，同时叠加复盘最终决策快照。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))

    def fake_trend_svg(name, code, klines, out_path, trend_bias=None):
        with open(out_path, 'w') as stream:
            stream.write('<svg></svg>')

    monkeypatch.setattr('backend.core.gen_trend_chart.gen_trend_svg', fake_trend_svg)
    first, _ = stock_chart_service.generate_trend_stock_chart(
        '000001', mode='review', signal_marker='technical_buy', signal_date=rows[-2]['date'],
    )
    second, _ = stock_chart_service.generate_trend_stock_chart(
        '000001', mode='review', signal_marker='technical_buy', signal_date=rows[-2]['date'],
    )
    missing, _ = stock_chart_service.generate_trend_stock_chart(
        '000001', mode='review', signal_marker='buy', signal_date='20200101',
    )

    assert '>技买<' in first
    assert first == second
    assert '>买<' not in missing


def test_stock_chart_cache_cleanup_is_per_stock(monkeypatch, tmp_path):
    from backend.services import stock_chart_service

    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    for idx in range(5):
        path = tmp_path / f'zzqz_stock_chart_000001_20260811_variant{idx}.svg'
        path.write_text('<svg/>')
        path.touch()
    other = tmp_path / 'zzqz_stock_chart_000002_20260811_variant.svg'
    other.write_text('<svg/>')

    stock_chart_service._cleanup_stock_chart_cache('000001', limit=2)

    assert len(list(tmp_path.glob('zzqz_stock_chart_000001_*.svg'))) == 2
    assert other.exists()


def test_volume_description_ignores_neutral_supply_exhaustion():
    from backend.services.stock_card_service import _select_bullish_volume_signal

    selected = _select_bullish_volume_signal([
        {'key': 'supply_exhaustion', 'direction': 'neutral', 'confidence': 99},
        {'key': 'panic_stagnation', 'direction': 'bullish', 'confidence': 80},
        {'key': 'upward_reversal', 'direction': 'bullish', 'confidence': 90},
    ], detected_buy_point='恐慌买点')

    assert selected['key'] == 'panic_stagnation'
