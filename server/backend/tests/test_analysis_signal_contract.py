from backend.services.analysis_service import _stock_card_signal_contract


def test_stock_analysis_keeps_fused_reversal_buy_point():
    card = {
        'signal': 'hold',
        'technical_signal': 'buy',
        'technical_confidence': 87.6,
        'technical_reason': '下降末端放量长阳',
        'buy_point': '反转买点',
        'fusion_type': 'ignore_signal',
        'fusion_reason': '关键点中性，暂不执行',
        'triggered_signals': [{
            'key': 'upward_reversal', 'name': '向上反转',
            'direction': 'bullish', 'confidence': 87.6,
        }],
    }

    result = _stock_card_signal_contract(card)

    assert result['buy_point'] == '反转买点'
    assert result['technical_signal'] == 'buy'
    assert result['execution_signal'] == 'hold'
    assert result['action_type'] == '技术信号'
    assert result['decision']['action'] == '技术信号'
    assert result['buy_detail']['signal_key'] == 'upward_reversal'


def test_stock_analysis_keeps_executable_signal_when_fusion_confirms_buy():
    card = {
        'signal': 'buy', 'technical_signal': 'buy',
        'buy_point': '中继买点', 'action_type': '买入',
        'triggered_signals': [],
    }

    result = _stock_card_signal_contract(card)

    assert result['execution_signal'] == 'buy'
    assert result['action_type'] == '买入'


def test_stock_analysis_never_hides_sell_behind_bullish_technical_signal():
    card = {
        'signal': 'sell', 'technical_signal': 'buy',
        'buy_point': '反转买点', 'action_type': '卖出',
        'decision': {'action': '卖出', 'reason': '更高置信度卖点'},
        'triggered_signals': [{
            'key': 'upward_reversal', 'direction': 'bullish', 'confidence': 70,
        }],
    }

    result = _stock_card_signal_contract(card)

    assert result['execution_signal'] == 'sell'
    assert result['action_type'] == '卖出'
    assert result['decision']['action'] == '卖出'


def test_stock_analysis_uses_same_day_review_market_position(monkeypatch):
    monkeypatch.setattr(
        'backend.services.review_cache_service.load_current_review',
        lambda: {'date': '2026-07-31', 'market': {'position': '波谷左侧'}},
    )

    from backend.services.analysis_service import _review_market_position_for_stock_date

    assert _review_market_position_for_stock_date('20260731') == '波谷左侧'
    assert _review_market_position_for_stock_date('20260730') == '波中'
