from unittest.mock import Mock


def _tencent_line(symbol='sh600000', code='600000', name='浦发银行', price='10.50'):
    fields = [''] * 88
    fields[1] = name
    fields[2] = code
    fields[3] = price
    fields[4] = '10.00'
    fields[5] = '10.10'
    fields[6] = '12345'
    fields[30] = '20260722143000'
    fields[32] = '5.00'
    fields[33] = '10.80'
    fields[34] = '9.90'
    fields[37] = '1234.5'
    fields[38] = '2.30'
    return f'v_{symbol}="' + '~'.join(fields) + '";'


def test_normalize_symbol_does_not_confuse_stock_with_index():
    from backend.data_access.realtime_quotes import normalize_symbol

    assert normalize_symbol('000001') == 'sz000001'
    assert normalize_symbol('sh000001') == 'sh000001'
    assert normalize_symbol('600000') == 'sh600000'


def test_standard_quote_contract(monkeypatch):
    from backend.data_access import realtime_quotes

    response = Mock(text=_tencent_line())
    monkeypatch.setattr(realtime_quotes.requests, 'get', lambda *args, **kwargs: response)

    quote = realtime_quotes.get_realtime_quote('600000', providers=['tencent'])

    assert quote['price'] == 10.5
    assert quote['prev_close'] == 10.0
    assert quote['change_pct'] == 5.0
    assert quote['source'] == 'tencent'
    assert quote['realtime'] is True


def test_batch_response_accepts_newline_delimiter(monkeypatch):
    from backend.data_access import realtime_quotes

    text = '\n'.join([
        _tencent_line('sh603259', '603259', '药明康德', '51.20').rstrip(';'),
        _tencent_line('sz301200', '301200', '大族数控', '274.00').rstrip(';'),
    ])
    response = Mock(text=text)
    monkeypatch.setattr(realtime_quotes.requests, 'get', lambda *args, **kwargs: response)

    quotes = realtime_quotes.get_realtime_quotes(
        ['603259', '301200'], providers=['tencent'],
    )

    assert quotes['603259']['price'] == 51.2
    assert quotes['301200']['price'] == 274.0


def test_provider_fallback_only_fills_missing_quotes(monkeypatch):
    from backend.data_access import realtime_quotes

    monkeypatch.setattr(
        realtime_quotes, '_fetch_tencent',
        lambda symbols, timeout=5: {'sh600000': {'source': 'tencent'}},
    )
    monkeypatch.setattr(
        realtime_quotes, '_fetch_mootdx',
        lambda symbols: {'sh000985': {'source': 'mootdx'}},
    )

    result = realtime_quotes.get_realtime_quotes(
        ['sh600000', 'sh000985'], providers=['tencent', 'mootdx'],
    )

    assert result['sh600000']['source'] == 'tencent'
    assert result['sh000985']['source'] == 'mootdx'


def test_review_index_klines_come_from_confirmed_data_layer(monkeypatch):
    from backend.data_access import data_layer
    from backend.services.review_compute_service import fetch_index_klines

    monkeypatch.setattr(data_layer, 'get_index_klines', lambda code: [
        {'date': '20260722', 'open': 1, 'close': 2, 'high': 3, 'low': 1, 'volume': 10},
    ])

    result = fetch_index_klines(60)

    assert result[0]['date'] == '2026-07-22'
    assert result[0]['close'] == 2
