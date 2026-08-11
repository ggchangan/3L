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
    monkeypatch.setattr(
        'backend.services.stock_card_service.get_stock_card',
        lambda *args, **kwargs: {'signal': 'hold'},
    )

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


def test_review_chart_uses_stock_klines_for_current_signal(monkeypatch, tmp_path):
    """买卖点计算必须接收该股票K线，而不是全市场嵌套字典。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    received = {}

    def fake_card(code, date_str, **kwargs):
        received['klines'] = kwargs.get('klines')
        return {'signal': 'buy'}

    monkeypatch.setattr('backend.services.stock_card_service.get_stock_card', fake_card)
    svg, error = stock_chart_service.generate_stock_chart('000001', mode='review')

    assert error is None
    assert received['klines'] is rows
    assert '>买<' in svg


def test_review_chart_cache_isolated_by_signal_snapshot(monkeypatch, tmp_path):
    """同日信号变化后必须重新生成右上角信号图例。"""
    from backend.services import stock_chart_service

    rows = _klines()
    _patch_chart_inputs(monkeypatch, rows)
    monkeypatch.setattr(stock_chart_service, 'REVIEW_CHARTS_DIR', str(tmp_path))
    monkeypatch.setattr(
        'backend.services.stock_card_service.get_stock_card',
        lambda *args, **kwargs: {'signal': 'hold'},
    )
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
