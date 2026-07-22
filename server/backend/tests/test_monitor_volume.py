def test_index_volume_is_not_used_as_market_turnover(monkeypatch):
    from backend.core import monitor_data

    monkeypatch.setattr(monitor_data, 'record_volume_snapshot', lambda: None)
    monkeypatch.setattr(monitor_data, 'get_index_quote', lambda: {
        'price': 5800,
        'change_pct': 1.0,
        'time': '10:30',
        'amount_yuan': 1_000_000,
        'source': 'tencent',
    })
    monkeypatch.setattr(monitor_data, 'get_yesterday_total', lambda: {
        'date': '20260721',
        'volume': 1_500_000_000,
        'amount': 0,
        'source': 'tushare',
    })
    monkeypatch.setattr(monitor_data, 'get_volume_snapshots', lambda date: [])
    monkeypatch.setattr(monitor_data, 'get_today_minute_curve', lambda: [
        {'time': '10:30', 'amount': 1_000_000},
    ])

    result = monitor_data.get_volume_comparison()

    assert result['yesterday_amount_yuan'] == 0
    assert result['yesterday_unavailable'] is True
    assert result['amount_ratio'] is None

