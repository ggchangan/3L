"""Stock card should use the unified 3L structure context as its structure口径."""

from __future__ import annotations


def _rows(closes):
    rows = []
    for idx, close in enumerate(closes):
        rows.append({
            'date': f'202607{idx + 1:02d}',
            'open': close * 0.99,
            'high': close * 1.02,
            'low': close * 0.98,
            'close': close,
            'volume': 100000 + idx * 1000,
        })
    return rows


def _ok_context(structure='区间震荡', stage='区间顶部', *, wave_position=None, risk=None):
    return {
        'version': '3l-structure-context-v1',
        'status': 'ok',
        'is_trade_decision': False,
        'market_structure': {
            'structure': structure,
            'stage': stage,
            'supply_demand_regime': 'balance',
            'confidence': 72,
            'evidence': ['测试统一结构上下文'],
            'source': 'test',
        },
        'wave_position': wave_position or {'position': 'peak_left', 'label': stage},
        'major_decline_risk': risk or {'level': 'watch', 'reason': '测试风险说明'},
        'position_context': {'stage': stage, 'current_zone': {'type': 'near_resistance'}},
        'supply_demand_events': [],
        'warnings': [],
    }


def test_unified_structure_context_overrides_legacy_structure_stage():
    from backend.services.stock_card_service import _analyze_3l_structure_context

    legacy = {'structure': '上涨趋势', 'stage': '上行', 'ema': '多头排列'}
    result = _analyze_3l_structure_context(
        _rows([100 + i for i in range(40)]),
        39,
        legacy_info=legacy,
    )

    assert result['structure_context_status'] == 'ok'
    assert result['structure_context']['is_trade_decision'] is False
    assert result['legacy_structure'] == legacy
    assert result['structure'] in {'上涨趋势', '下降趋势', '区间震荡', '未识别'}
    assert result['stage']


def test_unified_structure_context_falls_back_to_legacy_on_detector_failure(monkeypatch):
    from backend.services import stock_card_service as scs

    def boom(*args, **kwargs):
        raise RuntimeError('detector unavailable')

    monkeypatch.setattr(scs, 'detect_3l_structure_context', boom)
    legacy = {'structure': '上涨趋势', 'stage': '上行', 'ema': '多头排列'}

    result = scs._analyze_3l_structure_context(
        _rows([100 + i for i in range(40)]),
        39,
        legacy_info=legacy,
    )

    assert result['structure_context_status'] == 'fallback'
    assert result['structure'] == '上涨趋势'
    assert result['stage'] == '上行'
    assert 'detector unavailable' in result['structure_context_error']


def test_stock_card_rejects_legacy_continuation_buy_at_unified_range_top(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 102, 104, 106, 108, 110, 109, 108, 109, 110] * 4)
    monkeypatch.setattr(scs, '_ALL_A_STOCKS', {'000001': '测试股'})
    monkeypatch.setattr(scs, '_decide_trading_system', lambda code: '3l')
    monkeypatch.setattr(scs, 'get_stock_klines', lambda code, direction=None: klines)
    monkeypatch.setattr(
        scs,
        'get_industry_map',
        lambda: {'000001': {'name': '测试股', 'ths_industry': '半导体'}},
    )
    monkeypatch.setattr(
        scs,
        'detect_3l_structure_context',
        lambda *args, **kwargs: _ok_context('区间震荡', '区间顶部'),
    )
    monkeypatch.setattr(
        scs,
        'detect_buy_point',
        lambda *args, **kwargs: {
            'buy_type': '中继买点',
            'score': 80,
            'vol_ratio': 0.6,
            'detail': {'reason': '旧逻辑误判中继'},
        },
    )

    card = scs.get_stock_card('000001', '20260740')

    assert card['structure'] == '区间震荡'
    assert card['stage'] == '区间顶部'
    assert card['structure_context_status'] == 'ok'
    assert card['structure_context']['is_trade_decision'] is False
    assert card['legacy_structure']
    assert card['signal'] != 'buy'
    assert card['buy_point'] == ''
    assert '位置冲突' in card['signal_text']


def test_stock_card_does_not_repromote_rejected_continuation_from_fusion(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 102, 104, 106, 108, 110, 109, 108, 109, 110] * 4)
    monkeypatch.setattr(scs, '_ALL_A_STOCKS', {'000001': '测试股'})
    monkeypatch.setattr(scs, '_decide_trading_system', lambda code: '3l')
    monkeypatch.setattr(scs, 'get_stock_klines', lambda code, direction=None: klines)
    monkeypatch.setattr(
        scs,
        'get_industry_map',
        lambda: {'000001': {'name': '测试股', 'ths_industry': '半导体'}},
    )
    monkeypatch.setattr(
        scs,
        'detect_3l_structure_context',
        lambda *args, **kwargs: _ok_context('区间震荡', '区间顶部'),
    )
    monkeypatch.setattr(
        scs,
        'detect_buy_point',
        lambda *args, **kwargs: {
            'buy_type': '中继买点',
            'score': 80,
            'vol_ratio': 0.6,
            'detail': {'reason': '旧逻辑误判中继'},
        },
    )
    monkeypatch.setattr(
        scs,
        'fusion_judge',
        lambda *args, **kwargs: {
            'triggered_signals': [{
                'key': 'upward_continuation',
                'name': '上涨中继',
                'direction': 'bullish',
                'confidence': 82,
                'keypoint_allowed': False,
                'keypoint_reject_reason': '中继/回踩买点只能位于上涨趋势，区间顶部或下降趋势不成立',
            }],
            'fusion_type': 'signal_buy',
            'reason': '模拟 fusion 误升级',
            'signal': 'buy',
            'signal_text': '上涨中继',
            'confidence': 70,
            'technical_signal': 'buy',
            'detected_buy_point': '中继买点',
            'technical_confidence': 82,
            'technical_reason': '模拟技术事实',
        },
    )

    card = scs.get_stock_card('000001', '20260740')

    assert card['structure'] == '区间震荡'
    assert card['stage'] == '区间顶部'
    assert card['signal'] == 'hold'
    assert card['buy_point'] == ''
    assert card['technical_signal'] == 'buy'
    assert card['technical_confidence'] == 82
    assert '位置冲突' in card['signal_text']


def test_stock_card_downgrades_range_bottom_breakdown_risk_action(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 99, 98, 97, 96, 95, 96, 95, 94, 93] * 4)
    monkeypatch.setattr(scs, '_ALL_A_STOCKS', {'000001': '测试股'})
    monkeypatch.setattr(scs, '_decide_trading_system', lambda code: '3l')
    monkeypatch.setattr(scs, 'get_stock_klines', lambda code, direction=None: klines)
    monkeypatch.setattr(
        scs,
        'get_industry_map',
        lambda: {'000001': {'name': '测试股', 'ths_industry': '半导体'}},
    )
    monkeypatch.setattr(
        scs,
        'detect_3l_structure_context',
        lambda *args, **kwargs: _ok_context(
            '区间震荡',
            '区间底部',
            wave_position={'position': 'falling_middle', 'label': '区间底部跌破风险'},
            risk={'level': 'watch', 'reason': '支撑附近被供应跌破'},
        ),
    )
    monkeypatch.setattr(scs, 'detect_buy_point', lambda *args, **kwargs: None)

    card = scs.get_stock_card('000001', '20260740')

    assert card['structure'] == '区间震荡'
    assert card['stage'] == '区间底部'
    assert card['signal'] == 'hold'
    assert card['buy_point'] == ''
    assert card['action_type'] == '持有'
    assert card['action_signal'] == '等确认'
    assert card['action_priority'] == '高'
    assert '跌破风险' in card['action_reason']
    assert card['conclusion'] == card['action_reason']
    assert card['major_decline_risk']['level'] == 'watch'
