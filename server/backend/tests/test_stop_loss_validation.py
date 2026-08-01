"""止损回测核心的无前视、结构锚点和成交规则。"""
import pytest

from threel_core.stop_loss_validation import (
    calculate_stop_candidates,
    calc_recent_atr,
    detect_buy_point_without_future,
    simulate_stop_trade,
    summarize_results,
    validate_adjusted_continuity,
)


def _klines(count=50, close=100.0):
    return [
        {
            'date': f'2026{i // 28 + 1:02d}{i % 28 + 1:02d}',
            'open': close, 'high': close + 2, 'low': close - 2,
            'close': close, 'volume': 1000,
        }
        for i in range(count)
    ]


def test_detector_never_receives_future_bars():
    klines = _klines(45)
    seen = []

    def detector(code, date_str, all_stocks, **_kwargs):
        visible = all_stocks['回测样本'][code]
        seen.append((date_str, len(visible), visible[-1]['date']))
        return {'buy_type': '中继买点'}

    first = detect_buy_point_without_future(detector, '000001', klines, 30)
    extended = klines + _klines(5, close=50)
    second = detect_buy_point_without_future(detector, '000001', extended, 30)

    assert first == second
    assert seen == [(klines[30]['date'], 31, klines[30]['date'])] * 2


def test_breakout_structure_stop_uses_broken_level_not_future_data():
    klines = _klines(40)
    for i in range(24, 39):
        klines[i].update({'high': 105, 'low': 98, 'close': 101})
    klines[39].update({'open': 104, 'high': 110, 'low': 100, 'close': 108})

    candidates = calculate_stop_candidates(klines, 39, '突破买点', next_open=108)

    assert candidates['production_baseline'] == 97.0
    assert candidates['structure_atr_0.0'] == 105.0
    assert candidates['structure_atr_0.1'] < 105.0
    assert candidates['cost_2atr'] < 108


def test_gap_below_planned_stop_cancels_entry_but_stays_covered():
    klines = _klines(25)
    klines[21].update({'open': 94, 'high': 96, 'low': 92, 'close': 95})

    result = simulate_stop_trade(klines, 20, stop=95, horizon=4)

    assert result['covered'] is True
    assert result['gap_cancelled'] is True
    assert result['net_return_pct'] == 0


def test_holding_gap_below_stop_executes_at_open_and_records_slippage():
    klines = _klines(25)
    klines[21].update({'open': 100, 'high': 102, 'low': 99, 'close': 101})
    klines[22].update({'open': 90, 'high': 94, 'low': 88, 'close': 92})

    result = simulate_stop_trade(klines, 20, stop=95, horizon=4)

    assert result['stop_hit'] is True
    assert result['stop_day'] == 2
    assert result['gross_return_pct'] == -10
    assert result['gap_slippage_pct'] == 5


def test_recent_atr_uses_only_latest_fourteen_true_ranges():
    klines = _klines(30)
    klines[1].update({'high': 200, 'low': 1})  # 早期异常波动不得进入最近14日ATR。

    assert calc_recent_atr(klines, 14) == pytest.approx(4.0)


def test_false_stop_includes_recovery_on_stop_day_close():
    klines = _klines(23)
    klines[21].update({'open': 100, 'high': 103, 'low': 94, 'close': 102})

    result = simulate_stop_trade(klines, 20, stop=95, horizon=2)

    assert result['stop_hit'] is True
    assert result['false_stop'] is True


def test_stopped_trade_is_not_marked_as_terminal_exit_when_history_is_short():
    klines = _klines(22)
    klines[21].update({'open': 100, 'high': 101, 'low': 94, 'close': 96})

    result = simulate_stop_trade(klines, 20, stop=95, horizon=20, terminal_if_short=True)

    assert result['stop_hit'] is True
    assert result['terminal_exit'] is False


def test_summary_keeps_cancelled_signals_in_denominator_and_reports_tail():
    rows = [
        {'code': 'A', 'covered': True, 'gap_cancelled': True, 'net_return_pct': 0},
        {'code': 'A', 'covered': True, 'gap_cancelled': False, 'stop_hit': True,
         'stop_day': 3, 'false_stop': True, 'net_return_pct': -5,
         'initial_risk_pct': 4, 'hold_return_pct': 2, 'gap_slippage_pct': 0,
         'terminal_exit': False},
        {'code': 'B', 'covered': False},
    ]

    result = summarize_results(rows, bootstrap_runs=0)

    assert result['signals'] == 3
    assert result['coverage_pct'] == pytest.approx(66.6667)
    assert result['gap_cancel_rate_pct'] == 50
    assert result['false_stop_rate_pct'] == 100
    assert result['max_loss_pct'] == -5


def test_adjusted_continuity_accepts_corporate_action_and_rejects_polluted_row():
    valid = [
        {'trade_date': '1', 'close': 100, 'pre_close': 99, 'adj_factor': 1},
        # 除权参考价 50、因子 2，与前一日 100×1 连续。
        {'trade_date': '2', 'close': 51, 'pre_close': 50, 'adj_factor': 2},
    ]
    ok, detail = validate_adjusted_continuity(valid)
    assert ok is True and detail is None

    polluted = valid + [
        {'trade_date': '3', 'close': 2, 'pre_close': 1, 'adj_factor': 2},
    ]
    ok, detail = validate_adjusted_continuity(polluted)
    assert ok is False
    assert detail['reason'] == 'adjusted_pre_close_mismatch'
