from backend.services import holdings_service


def _klines():
    return [
        {
            'date': f'202607{day:02d}',
            'open': 90 + day,
            'high': 92 + day,
            'low': 89 + day,
            'close': 91 + day,
            'volume': 1000,
        }
        for day in range(1, 21)
    ]


def _patch_calculation(monkeypatch, initial=92.0, protective=108.0):
    monkeypatch.setattr('backend.data_access.data_layer.get_stock_klines', lambda code: _klines())

    calls = []

    def fake_calc(klines, idx, close_price=None, cost_price=None, buy_date=None, **kwargs):
        calls.append({'idx': idx, 'cost_price': cost_price, 'buy_date': buy_date})
        return (initial, 5.0) if cost_price is not None else (protective, 3.0)

    monkeypatch.setattr('backend.core.buy_point_detection.calc_stop_loss', fake_calc)
    return calls


def test_uses_buy_date_and_price_for_initial_stop(monkeypatch):
    calls = _patch_calculation(monkeypatch, protective=90.0)

    result = holdings_service.get_stop_loss_recommendation(
        '000001', buy_date='2026-07-12', buy_price=100,
    )

    assert result['success'] is True
    assert result['recommendation_type'] == 'initial_risk_stop'
    assert result['stop_loss'] == 92.0
    assert result['initial_stop'] == 92.0
    assert result['buy_date_used'] == '2026-07-12'
    assert calls[0]['idx'] == 11


def test_profitable_holding_without_saved_stop_uses_higher_protective_stop(monkeypatch):
    _patch_calculation(monkeypatch, initial=92.0, protective=108.0)

    result = holdings_service.get_stop_loss_recommendation(
        '000001', buy_date='2026-07-12', buy_price=100,
    )

    assert result['recommendation_type'] == 'protective_stop'
    assert result['stop_loss'] == 108.0
    assert result['initial_stop'] == 92.0


def test_protective_stop_only_moves_up(monkeypatch):
    _patch_calculation(monkeypatch, protective=108.0)

    raised = holdings_service.get_stop_loss_recommendation('000001', current_stop=95)
    kept = holdings_service.get_stop_loss_recommendation('000001', current_stop=109)

    assert raised['recommendation_type'] == 'raise_protective_stop'
    assert raised['stop_loss'] == 108.0
    assert raised['can_raise'] is True
    assert kept['recommendation_type'] == 'keep_current_stop'
    assert kept['stop_loss'] == 109.0
    assert kept['can_raise'] is False


def test_reached_stop_is_not_replaced_by_lower_suggestion(monkeypatch):
    _patch_calculation(monkeypatch, protective=108.0)

    result = holdings_service.get_stop_loss_recommendation('000001', current_stop=120)

    assert result['recommendation_type'] == 'stop_reached'
    assert result['stop_loss'] == 120.0
    assert '风险处置' in result['reason']


def test_invalid_numeric_input_returns_user_error(monkeypatch):
    _patch_calculation(monkeypatch)

    result = holdings_service.get_stop_loss_recommendation('000001', buy_price='not-a-number')

    assert result == {'success': False, 'error': '买入价或当前止损不是有效数字'}


def test_future_or_invalid_buy_date_is_rejected(monkeypatch):
    _patch_calculation(monkeypatch)

    invalid = holdings_service.get_stop_loss_recommendation('000001', buy_date='2026-13-99', buy_price=100)
    future = holdings_service.get_stop_loss_recommendation('000001', buy_date='2099-01-01', buy_price=100)

    assert invalid['success'] is False
    assert future == {'success': False, 'error': '买入日期不能晚于今天'}


def test_save_rejects_invalid_price_and_future_date_without_writing():
    base = {'cash_ratio': 90, 'holdings': [{'code': '000001', 'name': '测试', 'ratio': 10}]}

    negative = {**base, 'holdings': [{**base['holdings'][0], 'stop_loss_price': -1}]}
    future = {**base, 'holdings': [{**base['holdings'][0], 'buy_date': '2099-01-01'}]}

    assert '止损价必须为大于0' in holdings_service.save_holdings(negative)['error']
    assert '买入日期不能晚于今天' in holdings_service.save_holdings(future)['error']
