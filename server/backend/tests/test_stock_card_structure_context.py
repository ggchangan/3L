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


def test_stock_card_exposes_supply_demand_events_as_diagnostics(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 102, 104, 106, 108, 110, 109, 108, 109, 110] * 4)
    event_context = {
        'version': 'supply-demand-event-v1',
        'status': 'ok',
        'events': [{
            'event_type': 'failure',
            'event_label': '突破失败',
            'subtype': 'failed_breakout',
            'direction': 'bearish',
            'trade_implication': 'risk_or_sell_context',
            'is_trade_decision': False,
        }],
        'event_counts': {'total': 1, 'core': 1, 'watch': 0, 'weak': 0},
        'is_trade_decision': False,
    }
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
    monkeypatch.setattr(scs, 'detect_buy_point', lambda *args, **kwargs: None)
    monkeypatch.setattr(scs, 'detect_supply_demand_events', lambda *args, **kwargs: event_context)

    card = scs.get_stock_card('000001', '20260740')

    assert card['supply_demand_event_context']['is_trade_decision'] is False
    assert card['supply_demand_event_counts']['total'] == 1
    assert card['supply_demand_events'][0]['event_label'] == '突破失败'
    assert card['supply_demand_events'][0]['trade_implication'] == 'risk_or_sell_context'


def test_supply_demand_alignment_marks_matched_missing_and_conflict():
    from backend.services.stock_card_service import _build_supply_demand_alignment

    matched = _build_supply_demand_alignment({
        'buy_point': '突破买点',
        'technical_signal': 'buy',
        'triggered_signals': [],
        'supply_demand_events': [{
            'subtype': 'upward_breakout',
            'event_label': '向上突破',
            'direction': 'bullish',
            'tier': 'core',
        }],
    })
    assert matched['status'] == 'matched'
    assert matched['is_trade_decision'] is False
    assert matched['matched_subtypes'] == ['upward_breakout']

    missing = _build_supply_demand_alignment({
        'buy_point': '中继买点',
        'technical_signal': 'buy',
        'triggered_signals': [],
        'supply_demand_events': [],
    })
    assert missing['status'] == 'missing_event'
    assert missing['expected_subtypes'] == ['bullish_continuation']

    conflict = _build_supply_demand_alignment({
        'buy_point': '反转买点',
        'technical_signal': 'buy',
        'triggered_signals': [],
        'supply_demand_events': [{
            'subtype': 'downward_breakdown',
            'event_label': '向下跌破',
            'direction': 'bearish',
            'tier': 'core',
        }],
    })
    assert conflict['status'] == 'conflict'
    assert conflict['event_labels'] == ['向下跌破']


def test_final_sell_signal_clears_formal_buy_point_but_keeps_technical_fact(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 101, 102, 103, 104, 105, 106, 107, 108, 109] * 4)
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
            'buy_type': '突破买点',
            'score': 70,
            'vol_ratio': 1.8,
            'detail': {'reason': '技术层曾识别突破买点'},
        },
    )
    monkeypatch.setattr(
        scs,
        'detect_sell_point',
        lambda *args, **kwargs: {
            'triggered': True,
            'confidence': 95,
            'sell_type': '放量滞涨',
            'reason': '卖点更强，应覆盖执行信号',
        },
    )
    monkeypatch.setattr(
        scs,
        'fusion_judge',
        lambda *args, **kwargs: {
            'triggered_signals': [{
                'key': 'upward_breakout',
                'name': '向上突破',
                'direction': 'bullish',
                'confidence': 70,
            }],
            'fusion_type': 'signal_buy',
            'reason': '模拟技术突破事实',
            'signal': 'buy',
            'signal_text': '向上突破',
            'confidence': 70,
            'technical_signal': 'buy',
            'detected_buy_point': '突破买点',
            'technical_confidence': 70,
            'technical_reason': '技术突破事实',
        },
    )

    card = scs.get_stock_card('000001', '20260740')

    assert card['signal'] == 'sell'
    assert card['buy_point'] == ''
    assert card['technical_buy_point'] == '突破买点'
    assert card['decision']['action'] == '卖出'
    assert 'buy_point' not in card['decision']


def test_normalize_final_buy_point_separates_execution_and_diagnostic_fact():
    from backend.services.stock_card_service import _normalize_final_buy_point

    assert _normalize_final_buy_point('sell', '突破买点', '突破买点') == ('', '突破买点')
    assert _normalize_final_buy_point('hold', '', '中继买点') == ('', '中继买点')
    assert _normalize_final_buy_point('buy', '反转买点', '反转买点') == ('反转买点', '反转买点')


def test_supply_demand_gate_downgrades_3l_buy_without_matching_event():
    from backend.services.stock_card_service import _apply_supply_demand_buy_gate

    signal, buy_point, signal_text, score, alignment = _apply_supply_demand_buy_gate(
        trading_system='3l',
        signal='buy',
        buy_point='中继买点',
        signal_text='中继买点成立',
        score=82,
        technical_signal='buy',
        triggered_signals=[],
        events=[],
    )

    assert signal == 'hold'
    assert buy_point == ''
    assert score == 50
    assert alignment['status'] == 'missing_event'
    assert '缺少供需事件确认' in signal_text


def test_supply_demand_gate_keeps_3l_buy_with_matching_event():
    from backend.services.stock_card_service import _apply_supply_demand_buy_gate

    signal, buy_point, signal_text, score, alignment = _apply_supply_demand_buy_gate(
        trading_system='3l',
        signal='buy',
        buy_point='突破买点',
        signal_text='突破买点成立',
        score=82,
        technical_signal='buy',
        triggered_signals=[],
        events=[{
            'subtype': 'upward_breakout',
            'event_label': '向上突破',
            'direction': 'bullish',
            'tier': 'core',
        }],
    )

    assert signal == 'buy'
    assert buy_point == '突破买点'
    assert score == 82
    assert alignment['status'] == 'matched'


def test_stock_card_downgrades_buy_when_supply_demand_event_is_missing(monkeypatch):
    from backend.services import stock_card_service as scs

    klines = _rows([100, 101, 102, 103, 104, 105, 104, 103, 104, 105] * 4)
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
        lambda *args, **kwargs: _ok_context('上涨趋势', '上行'),
    )
    monkeypatch.setattr(
        scs,
        'detect_buy_point',
        lambda *args, **kwargs: {
            'buy_type': '中继买点',
            'score': 82,
            'vol_ratio': 0.6,
            'detail': {'reason': '技术层识别中继买点'},
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
            }],
            'fusion_type': 'signal_buy',
            'reason': '模拟技术中继事实',
            'signal': 'buy',
            'signal_text': '上涨中继',
            'confidence': 82,
            'technical_signal': 'buy',
            'detected_buy_point': '中继买点',
            'technical_confidence': 82,
            'technical_reason': '技术中继事实',
        },
    )
    monkeypatch.setattr(
        scs,
        'detect_supply_demand_events',
        lambda *args, **kwargs: {
            'version': 'supply-demand-event-v1',
            'status': 'ok',
            'events': [],
            'event_counts': {'total': 0, 'core': 0, 'watch': 0, 'weak': 0},
            'is_trade_decision': False,
        },
    )

    card = scs.get_stock_card('000001', '20260740')

    assert card['signal'] == 'hold'
    assert card['buy_point'] == ''
    assert card['technical_buy_point'] == '中继买点'
    assert card['supply_demand_alignment']['status'] == 'missing_event'
    assert card['decision']['action'] == '持有'
    assert '缺少供需事件确认' in card['signal_text']


def test_analysis_signal_contract_passes_structure_context_fields():
    from backend.services.analysis_service import _stock_card_signal_contract

    card = {
        'signal': 'hold',
        'technical_signal': 'buy',
        'technical_confidence': 66,
        'technical_reason': '测试技术事实',
        'buy_point': '',
        'technical_buy_point': '反转买点',
        'triggered_signals': [],
        'structure_context': {'status': 'ok', 'is_trade_decision': False},
        'structure_context_status': 'ok',
        'major_decline_risk': {'level': 'watch'},
        'structure_wave_position': {'position': 'falling_middle', 'label': '区间底部跌破风险'},
        'legacy_structure': {'structure': '上涨趋势', 'stage': '上行'},
        'supply_demand_event_context': {'status': 'ok', 'is_trade_decision': False},
        'supply_demand_events': [{
            'event_type': 'continuation',
            'event_label': '上涨中继',
            'is_trade_decision': False,
        }],
        'supply_demand_event_counts': {'total': 1},
        'supply_demand_alignment': {'status': 'matched', 'is_trade_decision': False},
        'decision': {'action': '持有', 'signal': '等确认', 'reason': '等待需求确认'},
    }

    result = _stock_card_signal_contract(card)

    assert result['structure_context']['is_trade_decision'] is False
    assert result['buy_point'] == ''
    assert result['technical_buy_point'] == '反转买点'
    assert result['structure_context_status'] == 'ok'
    assert result['major_decline_risk']['level'] == 'watch'
    assert result['structure_wave_position']['label'] == '区间底部跌破风险'
    assert result['legacy_structure']['stage'] == '上行'
    assert result['supply_demand_event_context']['is_trade_decision'] is False
    assert result['supply_demand_events'][0]['event_label'] == '上涨中继'
    assert result['supply_demand_event_counts']['total'] == 1
    assert result['supply_demand_alignment']['status'] == 'matched'
