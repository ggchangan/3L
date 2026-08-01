from backend.services.review_compute_service import _market_buy_compatibility


def test_reversal_evidence_is_not_erased_by_coarse_range_middle_stage():
    item = {
        'buy_point': '反转买点',
        'structure': '区间震荡',
        'stage': '区间中段',
        'triggered_signals': [{
            'key': 'upward_reversal', 'direction': 'bullish',
            'scores': {'drawdown_pct': -48.31, 'supply_context': 'supply_shrink'},
        }],
    }

    allowed, reason, category = _market_buy_compatibility(item, 'weak', 'normal')

    assert allowed is True
    assert category == 'reversal'
    assert '匹配' in reason


def test_main_decline_still_blocks_new_position_even_with_reversal():
    item = {
        'buy_point': '反转买点', 'structure': '下降趋势', 'stage': '下行',
        'triggered_signals': [{'key': 'upward_reversal', 'direction': 'bullish'}],
    }

    allowed, reason, _ = _market_buy_compatibility(item, 'weak', 'main_decline')

    assert allowed is False
    assert '主跌' in reason


def test_panic_stagnation_evidence_survives_coarse_range_middle_stage():
    item = {
        'buy_point': '恐慌买点', 'structure': '区间震荡', 'stage': '区间中段',
        'triggered_signals': [{
            'key': 'panic_stagnation', 'direction': 'bullish',
            'scores': {'near_20d_low': True, 'background_loss_pct': -8.2},
        }],
    }

    allowed, reason, category = _market_buy_compatibility(item, 'weak', 'normal')

    assert allowed is True
    assert category == 'panic'
    assert '匹配' in reason


def test_range_bottom_break_and_recovery_is_valid_panic_context_without_prior_decline():
    item = {
        'buy_point': '恐慌买点', 'structure': '区间震荡', 'stage': '区间中段',
        'triggered_signals': [{
            'key': 'panic_stagnation', 'direction': 'bullish',
            'scores': {
                'near_20d_low': True,
                'breaks_20d_low': True,
                'background_loss_pct': -0.5,
            },
        }],
    }

    allowed, reason, category = _market_buy_compatibility(item, 'weak', 'normal')

    assert allowed is True
    assert category == 'panic'
    assert '匹配' in reason
