from backend.core.market_peak_valley_backtest import (
    adapt_legacy_result,
    collect_events,
    run_regression,
)


def _bars(count=100):
    return [
        {
            'date': f'2025-{index // 28 + 1:02d}-{index % 28 + 1:02d}',
            'open': 100 + index,
            'high': 101 + index,
            'low': 99 + index,
            'close': 100 + index,
            'volume': 1000,
        }
        for index in range(count)
    ]


def test_rolling_judge_never_receives_future_bars():
    seen_dates = []

    def judge(rows):
        seen_dates.append((len(rows), rows[-1]['date']))
        return {'wave_side': 'none', 'wave_phase': 'none'}

    bars = _bars(90)
    collect_events(list(reversed(bars)), judge, min_bars=80)
    assert seen_dates[0] == (80, bars[79]['date'])
    assert seen_dates[-1] == (90, bars[-1]['date'])


def test_continuous_phase_is_one_event_and_upgrade_is_new_event():
    calls = 0

    def judge(_rows):
        nonlocal calls
        calls += 1
        phase = 'forming' if calls <= 3 else 'biased'
        return {'wave_side': 'valley', 'wave_phase': phase, 'wave_label': phase}

    events = collect_events(_bars(85), judge, min_bars=80)
    assert [event['phase'] for event in events] == ['forming', 'biased']


def test_peak_forward_return_is_direction_adjusted():
    def judge(rows):
        return {'wave_side': 'peak', 'wave_phase': 'biased'} if len(rows) == 81 else {
            'wave_side': 'none', 'wave_phase': 'none',
        }

    events = collect_events(_bars(101), judge, min_bars=80)
    assert events[0]['return_10d'] > 0
    assert events[0]['signed_return_10d'] < 0
    assert events[0]['mfe'] == 0
    assert events[0]['mae'] < 0


def test_legacy_mapping_does_not_claim_confirmation():
    assert adapt_legacy_result({'position': '偏波谷'})['wave_phase'] == 'biased'
    assert adapt_legacy_result({'position': '波中'})['wave_side'] == 'none'


def test_preserved_legacy_judge_remains_executable_for_ab_regression():
    from backend.services.review_compute_service import _judge_peak_valley_legacy

    result = adapt_legacy_result(_judge_peak_valley_legacy(_bars(100)))
    assert result['algorithm_version'] == 'legacy_bias20_v5'


def test_report_keeps_calibration_and_validation_separate():
    def judge(rows):
        if len(rows) in (80, 95):
            return {'wave_side': 'valley', 'wave_phase': 'biased'}
        return {'wave_side': 'none', 'wave_phase': 'none'}

    report = run_regression({'x': {'name': '测试', 'klines': _bars(100)}}, {'algo': judge})
    datasets = {row['dataset'] for row in report['algorithms']['algo']['summary']}
    assert datasets == {'calibration', 'validation'}


def test_calibration_forward_returns_do_not_cross_validation_boundary():
    def judge(rows):
        if len(rows) == 79:
            return {'wave_side': 'valley', 'wave_phase': 'left'}
        return {'wave_side': 'none', 'wave_phase': 'none'}

    events = collect_events(
        _bars(100), judge, min_bars=20, horizons=(1, 3), calibration_ratio=.8,
    )
    assert events[0]['dataset'] == 'calibration'
    assert events[0]['return_1d'] is not None
    assert events[0]['return_3d'] is None
    assert events[0]['mfe'] is None


def test_backtest_uses_production_cleaning_and_deduplicates_dates():
    bars = _bars(90)
    duplicate = dict(bars[-1])
    malformed = {**bars[-1], 'date': '2099-01-01', 'high': 1}
    lengths = []

    def judge(rows):
        lengths.append(len(rows))
        return {'wave_side': 'none', 'wave_phase': 'none'}

    collect_events([*bars, duplicate, malformed], judge, min_bars=80)
    assert lengths[-1] == 90


def test_tail_event_has_returns_but_not_mixed_window_excursion():
    def judge(rows):
        if len(rows) == 95:
            return {'wave_side': 'valley', 'wave_phase': 'left'}
        return {'wave_side': 'none', 'wave_phase': 'none'}

    event = collect_events(_bars(100), judge, min_bars=80, horizons=(1, 10))[0]
    assert event['return_1d'] is not None
    assert event['return_10d'] is None
    assert event['mfe'] is None
    assert event['mae'] is None
