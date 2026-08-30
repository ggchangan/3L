from backend.core.supply_demand_transition_zone_detector import detect_transition_zones


def _row(day, close, volume=1000):
    return {
        'date': f'202606{day:02d}',
        'open': close - 0.4,
        'high': close + 1,
        'low': close - 1,
        'close': close,
        'volume': volume,
    }


def _states(directions):
    return [
        {
            'idx': idx,
            'date': f'202606{idx + 1:02d}',
            'trading_wave': {'direction': direction},
            'trading_state': f'{direction}-state',
        }
        for idx, direction in enumerate(directions)
    ]


def test_detects_multiday_down_to_up_transition_zone():
    rows = [_row(idx + 1, 120 - idx * 1.2, 1000 + idx * 10) for idx in range(24)]
    for idx in range(24, 30):
        rows.append(_row(idx + 1, 91 + (idx - 24) * 2.0, 1500))
    states = _states(['down'] * 24 + ['up'] * 6)
    sd_results = {
        24: {
            'transition_points': [{
                'idx': 24,
                'date': '20260625',
                'type': 'failed_breakdown',
                'direction': 'bullish',
                'tier': 'core',
                'confidence': 82,
            }]
        }
    }

    result = detect_transition_zones(
        rows,
        asset_type='market',
        wave_states=states,
        supply_demand_results=sd_results,
        pre_bars=2,
        post_bars=3,
    )

    zone = result['zones'][0]
    assert zone['type'] == 'down_to_up'
    assert zone['direction'] == 'bullish'
    assert zone['status'] == 'confirmed'
    assert zone['tier'] in ('core', 'watch')
    assert zone['start_date'] == '20260623'
    assert zone['pivot_date'] == '20260625'
    assert zone['end_date'] == '20260627'
    assert zone['evidence']['matched_supply_demand_points'][0]['type'] == 'failed_breakdown'
    assert zone['is_trade_decision'] is False


def test_detects_up_to_down_transition_zone_and_counter_points_reduce_confidence():
    rows = [_row(idx + 1, 80 + idx * 1.5, 1000) for idx in range(22)]
    for idx in range(22, 28):
        rows.append(_row(idx + 1, 113 - (idx - 22) * 2.0, 1400))
    states = _states(['up'] * 22 + ['down'] * 6)
    sd_results = {
        22: {'transition_points': [{'idx': 22, 'date': '20260623', 'type': 'bearish_reversal', 'direction': 'bearish', 'tier': 'core'}]},
        23: {'transition_points': [{'idx': 23, 'date': '20260624', 'type': 'failed_breakdown', 'direction': 'bullish', 'tier': 'watch'}]},
    }

    result = detect_transition_zones(
        rows,
        asset_type='stock',
        wave_states=states,
        supply_demand_results=sd_results,
    )

    zone = result['zones'][0]
    assert zone['type'] == 'up_to_down'
    assert zone['direction'] == 'bearish'
    assert zone['status'] == 'confirmed'
    assert zone['evidence']['matched_supply_demand_points'][0]['type'] == 'bearish_reversal'
    assert zone['evidence']['counter_supply_demand_points'][0]['type'] == 'failed_breakdown'
    assert any('反向供需点' in reason for reason in zone['reasons'])


def test_marks_latest_one_day_transition_as_forming():
    rows = [_row(idx + 1, 100 - idx, 1000) for idx in range(24)]
    rows.append(_row(25, 82, 1200))
    states = _states(['down'] * 24 + ['up'])

    result = detect_transition_zones(
        rows,
        asset_type='market',
        wave_states=states,
        supply_demand_results={},
        include_failed=True,
    )

    assert result['latest_zone']['type'] == 'down_to_up'
    assert result['latest_zone']['status'] == 'forming'
    assert result['latest_zone']['display_level'] == 'secondary'
    assert any('最新波段刚开始' in reason for reason in result['latest_zone']['reasons'])


def test_marks_one_day_middle_transition_as_failed_when_immediately_reversed():
    rows = [_row(idx + 1, 100 - idx, 1000) for idx in range(24)]
    rows.extend([_row(25, 82), _row(26, 80), _row(27, 79)])
    states = _states(['down'] * 24 + ['up'] + ['down'] * 2)

    result = detect_transition_zones(
        rows,
        asset_type='market',
        wave_states=states,
        supply_demand_results={},
        include_failed=True,
    )

    assert result['zones'][0]['type'] == 'down_to_up'
    assert result['zones'][0]['status'] == 'failed'
    assert result['zones'][0]['tier'] == 'weak'


def test_filters_failed_one_day_transition_by_default():
    rows = [_row(idx + 1, 100 - idx, 1000) for idx in range(24)]
    rows.extend([_row(25, 82), _row(26, 80), _row(27, 79)])
    states = _states(['down'] * 24 + ['up'] + ['down'] * 2)

    result = detect_transition_zones(
        rows,
        asset_type='market',
        wave_states=states,
        supply_demand_results={},
    )

    assert result['zones'] == []


def test_assigns_display_tier_for_human_review():
    rows = [_row(idx + 1, 120 - idx * 1.2, 1000 + idx * 10) for idx in range(24)]
    for idx in range(24, 30):
        rows.append(_row(idx + 1, 91 + (idx - 24) * 2.0, 1500))
    states = _states(['down'] * 24 + ['up'] * 6)
    sd_results = {
        24: {'transition_points': [{'idx': 24, 'date': '20260625', 'type': 'failed_breakdown', 'direction': 'bullish', 'tier': 'core'}]},
        25: {'transition_points': [{'idx': 25, 'date': '20260626', 'type': 'bullish_reversal', 'direction': 'bullish', 'tier': 'core'}]},
    }

    result = detect_transition_zones(
        rows,
        asset_type='market',
        wave_states=states,
        supply_demand_results=sd_results,
    )

    zone = result['zones'][0]
    assert zone['tier'] in ('core', 'watch')
    assert zone['display_level'] in ('primary', 'secondary')


def test_returns_no_zone_without_direction_switch():
    rows = [_row(idx + 1, 100 + idx, 1000) for idx in range(30)]
    states = _states(['up'] * 30)

    result = detect_transition_zones(
        rows,
        asset_type='stock',
        wave_states=states,
        supply_demand_results={},
    )

    assert result['status'] == 'ok'
    assert result['zones'] == []
    assert result['latest_zone'] is None
