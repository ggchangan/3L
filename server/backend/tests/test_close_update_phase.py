from datetime import datetime
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch


class TradingDayAfterClose(datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 7, 21, 17, 30)


def test_last_completed_trading_day_includes_today_after_close():
    from backend.data_access import data_source

    class AfterClose(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 21, 17, 30)

    with patch.object(data_source, 'datetime', AfterClose), \
         patch.object(data_source, '_get_trade_date_cache', return_value={'20260721'}):
        assert data_source.get_last_completed_trading_day() == '20260721'


def test_last_completed_trading_day_uses_previous_day_before_close():
    from backend.data_access import data_source

    class BeforeClose(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 21, 6, 0)

    with patch.object(data_source, 'datetime', BeforeClose), \
         patch.object(data_source, '_get_trade_date_cache', return_value={'2026-07-20', '2026-07-21'}):
        assert data_source.get_last_completed_trading_day() == '20260720'


def test_close_phase_waits_until_stocks_and_all_indices_are_ready():
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'datetime', TradingDayAfterClose), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value={
             'ready': False,
             'stock_date': '20260721',
             'missing_indices': ['000985'],
         }), \
         patch.object(update_stock_data, 'update_stocks') as update_stocks:
        assert update_stock_data.run_close_phase() is False
        update_stocks.assert_not_called()


def test_close_phase_skips_weekday_holiday_without_rebuilding_review():
    from backend.core import update_stock_data

    class Holiday(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 2, 17, 30)

    with patch.object(update_stock_data, 'datetime', Holiday), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260930'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental') as fetch, \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is True
        fetch.assert_not_called()
        refresh.assert_not_called()


def test_close_phase_refreshes_review_after_daily_data_is_ready():
    from backend.core import update_stock_data

    freshness = {
        'ready': True,
        'stock_date': '20260721',
        'missing_indices': [],
    }
    with patch.object(update_stock_data, 'datetime', TradingDayAfterClose), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value=freshness), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks'), \
         patch.object(update_stock_data, 'update_index'), \
         patch.object(update_stock_data, 'refresh_sector_close_snapshot', return_value={
             'coverage': {'industry': {'covered': 280, 'expected': 319, 'ratio': 0.878}},
         }), \
         patch.object(update_stock_data, '_market_temperature_data_freshness', return_value={
             'ready': True, 'adj_factor_date': '20260721', 'stk_limit_date': '20260721',
         }), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is True
        refresh.assert_called_once_with('20260721')


def test_close_cli_retries_until_data_is_ready():
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'run_close_phase', side_effect=[False, True]) as run, \
         patch.object(update_stock_data.time, 'sleep') as sleep:
        result = update_stock_data.main([
            '--phase', 'close', '--max-attempts', '3', '--retry-interval', '0',
        ])

    assert result == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(0)


def test_close_cli_retries_after_recoverable_exception():
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'run_close_phase', side_effect=[RuntimeError('暂时失败'), True]) as run, \
         patch.object(update_stock_data.time, 'sleep') as sleep:
        result = update_stock_data.main([
            '--phase', 'close', '--max-attempts', '3', '--retry-interval', '0',
        ])

    assert result == 0
    assert run.call_count == 2
    sleep.assert_called_once_with(0)


def test_full_phase_refreshes_review_after_sector_update(tmp_path):
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'DATA_DIR', str(tmp_path)), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks', return_value=(0, 0, 0)), \
         patch.object(update_stock_data, '_run_full_stage_isolated', side_effect=[
             (2000, '20260721'), (319, 20),
         ]), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        update_stock_data.run_full_phase()

    refresh.assert_called_once_with('20260721')


def test_full_phase_still_attempts_sectors_after_index_native_failure(tmp_path):
    from backend.core import update_stock_data

    with patch.object(update_stock_data, 'DATA_DIR', str(tmp_path)), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks', return_value=(0, 0, 0)), \
         patch.object(update_stock_data, '_run_full_stage_isolated', side_effect=[
             RuntimeError('index 子进程被信号 11 终止'), (319, 20),
         ]) as isolated, \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        try:
            update_stock_data.run_full_phase()
            assert False, '阶段失败必须让 cron 收到非零退出'
        except RuntimeError as exc:
            assert '信号 11' in str(exc)

    assert isolated.call_args_list[0].args == ('index',)
    assert isolated.call_args_list[1].args == ('sectors',)
    refresh.assert_called_once()


def test_isolated_stage_reports_signal_without_losing_other_output(capsys):
    from backend.core import update_stock_data

    crashed = type('Result', (), {
        'returncode': -11,
        'stdout': '[stage] index wrote data\n',
        'stderr': '',
    })()
    with patch.object(update_stock_data, 'STAGE_RETRY_INTERVAL', 0), \
         patch.object(update_stock_data.subprocess, 'run', return_value=crashed):
        try:
            update_stock_data._run_full_stage_isolated('index')
            assert False, 'native signal must fail the stage'
        except RuntimeError as exc:
            assert '信号 11' in str(exc)

    assert 'index wrote data' in capsys.readouterr().out


def test_production_review_refresh_persists_current_cache_and_daily_snapshot():
    from backend.core import update_stock_data
    from backend.services import market_temperature_service, review_service

    review = {'date': '2026-07-21', 'mainline': {'all_ranked': []}}
    with patch.object(review_service, 'compute_review_real_time', return_value=review), \
         patch.object(review_service, 'review_refresh_file_lock', return_value=nullcontext()), \
         patch.object(review_service, 'save_review_data') as save_current, \
         patch.object(review_service, 'save_review_snapshot') as save_snapshot, \
         patch.object(market_temperature_service, 'invalidate_market_temperature_cache'):
        update_stock_data._refresh_review_cache('20260721')

    saved = save_current.call_args.args[0]
    assert saved['date'] == '2026-07-21'
    assert saved['cache_generated_at']
    save_snapshot.assert_called_once_with(saved)


def test_close_phase_keeps_review_available_and_requests_retry_when_sector_snapshot_fails():
    from backend.core import update_stock_data

    freshness = {'ready': True, 'stock_date': '20260721', 'missing_indices': []}
    with patch.object(update_stock_data, 'datetime', TradingDayAfterClose), \
         patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch.object(update_stock_data, '_fetch_tushare_daily_incremental'), \
         patch.object(update_stock_data, '_daily_data_freshness', return_value=freshness), \
         patch.object(update_stock_data, '_ensure_all_stock_codes'), \
         patch.object(update_stock_data, 'update_industry_map'), \
         patch.object(update_stock_data, 'update_concept_maps'), \
         patch.object(update_stock_data, 'update_stocks'), \
         patch.object(update_stock_data, 'update_index'), \
         patch.object(update_stock_data, 'refresh_sector_close_snapshot', side_effect=RuntimeError('暂时不可用')), \
         patch.object(update_stock_data, '_market_temperature_data_freshness', return_value={
             'ready': True, 'adj_factor_date': '20260721', 'stk_limit_date': '20260721',
         }), \
         patch.object(update_stock_data, '_clear_mainline_cache'), \
         patch.object(update_stock_data, '_refresh_review_cache') as refresh:
        assert update_stock_data.run_close_phase() is False

    refresh.assert_called_once_with('20260721')


def test_sector_update_coverage_rejects_partial_target_date():
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [{'name': 'A', 'type': 'I'}]
    requested = [('A', 'industry'), ('B', 'industry')]
    confirmation = {'confirmed_date': '20260720', 'industry_names': ['A', 'B']}
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['covered'] == 1
    assert result['industry']['expected'] == 2
    assert result['missing'] == ['B']


def test_partial_sector_rows_never_become_next_day_baseline():
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'name': 'A', 'type': 'I'},
        {'name': 'B', 'type': 'I'},
    ]
    requested = [(name, 'industry') for name in ('A', 'B', 'C')]
    confirmation = {
        'confirmed_date': '20260720',
        'industry_names': ['A', 'B', 'C'],
    }
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        first = data_source.get_ths_daily_update_coverage(requested, '20260721')
        second = data_source.get_ths_daily_update_coverage(requested, '20260722')

    assert first['ready'] is False
    assert second['ready'] is False
    assert first['industry']['expected'] == second['industry']['expected'] == 3
    assert first['industry_names'] == second['industry_names'] == ['A', 'B', 'C']


def test_same_count_sector_member_replacement_is_not_complete():
    from backend.data_access import data_source

    class FakeDB:
        def execute_raw(self, sql, params=None):
            # 新行业 X 必须在目标日查询范围中，否则它永远进不了新基线。
            assert params == ['20260721', 'A', 'B', 'C', 'X']
            return [
                {'name': 'A', 'type': 'I'},
                {'name': 'B', 'type': 'I'},
                {'name': 'X', 'type': 'I'},
            ]

    requested = [(name, 'industry') for name in ('A', 'B', 'C', 'X')]
    confirmation = {'confirmed_date': '20260720', 'industry_names': ['A', 'B', 'C']}
    with patch.object(data_source, '_get_tushare_db', return_value=FakeDB()), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value=confirmation):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['covered'] == 2
    assert result['industry']['expected'] == 3
    assert result['missing'] == ['C']
    assert result['industry_names'] == ['A', 'B', 'C', 'X']


def test_sector_coverage_uses_shared_safe_legacy_bootstrap():
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]
    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'name': name, 'type': 'I'} for name in names
    ]
    confirmation = {'confirmed_date': '20260720', 'industry_names': names}

    requested = [(name, 'industry') for name in names]
    with patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value={}), \
         patch.object(data_source, 'bootstrap_ths_daily_update_confirmation', return_value=confirmation) as bootstrap:
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is True
    assert result['bootstrap'] is False
    assert result['industry']['expected'] == 80
    bootstrap.assert_called_once_with()


def test_sector_coverage_does_not_bootstrap_from_target_day_itself():
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]

    class FakeDB:
        def execute_raw(self, sql, params=None):
            if 'COUNT(DISTINCT td.ts_code)' in sql:
                return []
            return [{'name': name, 'type': 'I'} for name in names]

    requested = [(name, 'industry') for name in names]
    with patch.object(data_source, '_get_tushare_db', return_value=FakeDB()), \
         patch.object(data_source, 'get_ths_daily_update_confirmation', return_value={}):
        result = data_source.get_ths_daily_update_coverage(requested, '20260721')

    assert result['ready'] is False
    assert result['industry']['expected'] == 0
    assert result['industry']['bootstrap_minimum'] == 80


def test_legacy_sector_state_bootstraps_only_from_repeated_stable_history(tmp_path):
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(80)]

    class FakeDB:
        def execute_raw(self, sql, params=None):
            if 'COUNT(DISTINCT td.ts_code)' in sql:
                return [
                    {'trade_date': '20260720', 'board_count': 79},
                    {'trade_date': '20260719', 'board_count': 80},
                ]
            assert params == ['20260719']
            return [{'name': name} for name in names]

    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)), \
         patch.object(data_source, '_get_tushare_db', return_value=FakeDB()):
        state = data_source.bootstrap_ths_daily_update_confirmation()

    assert state['confirmed_date'] == '20260719'
    assert state['industry_names'] == names


def test_legacy_sector_state_rejects_a_single_partial_history_day(tmp_path):
    from backend.data_access import data_source

    db = type('FakeDB', (), {})()
    db.execute_raw = lambda sql, params=None: [
        {'trade_date': '20260720', 'board_count': 80},
    ]
    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        state = data_source.bootstrap_ths_daily_update_confirmation()

    assert state == {}
    assert not state_path.exists()


def test_sector_confirmation_is_not_hidden_by_cross_process_kline_cache():
    from backend.data_access import data_layer

    klines = {'industries': {'A': []}, 'concepts': {}}
    confirmations = [
        {'confirmed_date': '20260720', 'industry_coverage': 1.0},
        {'confirmed_date': '20260721', 'industry_coverage': 0.98},
    ]
    with patch.object(data_layer.cache, 'get', return_value=klines), \
         patch.object(data_layer, 'get_ths_daily_update_confirmation', side_effect=confirmations):
        first = data_layer.get_sector_daily()
        second = data_layer.get_sector_daily()

    assert first['last_updated'] == '20260720'
    assert second['last_updated'] == '20260721'
    assert first['industries'] is second['industries']


def test_sector_confirmation_is_saved_and_loaded_atomically(tmp_path):
    from backend.data_access import data_source

    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    coverage = {
        'industry_names': ['A', 'B'],
        'industry': {'ratio': 1.0},
        'concept': {'ratio': 0.95},
    }
    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)):
        data_source.save_ths_daily_update_confirmation('20260721', coverage)
        state = data_source.get_ths_daily_update_confirmation()

    assert state['confirmed_date'] == '20260721'
    assert state['industry_names'] == ['A', 'B']
    assert state['industry_coverage'] == 1.0
    assert state['concept_coverage'] == 0.95
    assert not (tmp_path / 'computed' / 'sector_update_state.json.tmp').exists()


def test_partial_concept_confirmation_keeps_previous_official_date(tmp_path):
    from backend.data_access import data_source

    state_path = tmp_path / 'computed' / 'sector_update_state.json'
    complete = {
        'industry_names': ['A'],
        'concept_names': ['C', 'D'],
        'industry': {
            'ready': True, 'ratio': 1.0, 'covered': 1,
            'expected': 1, 'complete': True, 'missing': [],
        },
        'concept': {
            'ready': True, 'ratio': 1.0, 'covered': 2,
            'expected': 2, 'complete': True, 'missing': [],
        },
    }
    partial = {
        'industry_names': ['A'],
        'concept_names': ['C', 'D'],
        'industry': {
            'ready': True, 'ratio': 1.0, 'covered': 1,
            'expected': 1, 'complete': True, 'missing': [],
        },
        'concept': {
            'ready': True, 'ratio': 0.5, 'covered': 1,
            'expected': 2, 'complete': False, 'missing': ['D'],
        },
    }

    with patch.object(data_source, 'SECTOR_UPDATE_STATE_PATH', str(state_path)):
        data_source.save_ths_daily_update_confirmation('20260721', complete)
        data_source.save_ths_daily_update_confirmation('20260722', partial)
        state = data_source.get_ths_daily_update_confirmation()

    assert state['industry_confirmed_date'] == '20260722'
    assert state['concept_data_date'] == '20260722'
    assert state['concept_confirmed_date'] == '20260721'
    assert state['concept_status'] == 'partial'
    assert state['concept_coverage'] == 0.5
    assert state['concept_coverage_detail'] == {
        'covered': 1,
        'expected': 2,
        'missing': ['D'],
    }


def test_sector_update_advances_confirmation_only_after_gate_passes():
    from backend.core import update_stock_data

    coverage = {
        'ready': True,
        'industry': {'expected': 1, 'covered': 1},
        'concept': {'expected': 0, 'covered': 0},
        'missing': [],
        'industry_names': ['A'],
    }
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch('backend.data_access.data_source.sync_ths_index_from_tushare', return_value=0), \
         patch('backend.data_access.data_source.sync_ths_member_from_tushare', return_value=0), \
         patch.object(update_stock_data, 'datetime') as current_time, \
         patch.object(update_stock_data, 'get_tracked_concept_universe', return_value={
             'names': set(), 'excluded': {},
         }), \
         patch.object(update_stock_data, 'get_ths_index_names', return_value=[('A', '881001.TI')]), \
         patch.object(update_stock_data, 'fetch_ths_daily_klines_akshare', return_value=(1, 1)), \
         patch.object(update_stock_data, 'get_ths_daily_update_coverage', return_value=coverage), \
         patch.object(update_stock_data, 'save_ths_daily_update_confirmation') as save:
        current_time.now.return_value.weekday.return_value = 0
        assert update_stock_data.update_sectors() == (1, 0)

    save.assert_called_once_with('20260721', coverage)


def test_sector_update_runs_on_saturday_to_confirm_friday_data():
    from backend.core import update_stock_data

    coverage = {
        'ready': True,
        'industry': {'expected': 1, 'covered': 1},
        'concept': {'expected': 0, 'covered': 0},
        'missing': [],
        'industry_names': ['A'],
    }
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260724'), \
         patch('backend.data_access.data_source.sync_ths_index_from_tushare', return_value=0), \
         patch('backend.data_access.data_source.sync_ths_member_from_tushare', return_value=0), \
         patch('backend.data_access.watched_sectors_repo.get_all_watched', return_value=[]), \
         patch.object(update_stock_data, 'get_tracked_concept_universe', return_value={
             'names': set(), 'excluded': {},
         }), \
         patch.object(update_stock_data, 'get_ths_index_names', return_value=[('A', '881001.TI')]), \
         patch.object(update_stock_data, 'fetch_ths_daily_klines_akshare', return_value=(1, 1)) as fetch, \
         patch.object(update_stock_data, 'get_ths_daily_update_coverage', return_value=coverage), \
         patch.object(update_stock_data, 'save_ths_daily_update_confirmation') as save:
        assert update_stock_data.update_sectors() == (1, 0)

    fetch.assert_called_once_with([('A', 'industry')], '20260724')
    save.assert_called_once_with('20260724', coverage)


def test_full_sector_cron_runs_tuesday_through_saturday():
    crontab = (Path(__file__).resolve().parents[3] / 'deploy' / 'crontab').read_text()
    full_lines = [line for line in crontab.splitlines() if '--phase full' in line]

    assert len(full_lines) == 1
    assert full_lines[0].startswith('0 6 * * 2-6 ')


def test_board_kline_conversion_rejects_bad_prices_and_sanitizes_volume():
    import pandas as pd
    from backend.data_access.data_source import _convert_board_kline

    frame = pd.DataFrame([
        {
            '日期': '2026-07-23', '开盘价': 9, '收盘价': float('nan'),
            '最高价': 11, '最低价': 8, '成交量': 100,
        },
        {
            '日期': float('nan'), '开盘价': 9, '收盘价': 10,
            '最高价': 11, '最低价': 8, '成交量': 100,
        },
        {
            '日期': '2026-07-24', '开盘价': 9, '收盘价': 10,
            '最高价': 11, '最低价': 8, '成交量': float('inf'),
        },
    ])

    assert _convert_board_kline(frame) == [{
        'date': '20260724', 'open': 9.0, 'close': 10.0,
        'high': 11.0, 'low': 8.0, 'volume': 0,
    }]


def test_board_fetch_never_writes_invalid_close_as_formal_coverage(monkeypatch):
    import math
    from backend.data_access import data_source

    # 模拟同花顺原始K线接口响应：第2行 close=0 属非法行情，必须整行拒绝。
    # 直连按 start~today 的年份范围逐年请求文件，仅 2026 年文件返回有效数据。
    class FakeResponse:
        status_code = 200

        def __init__(self, year):
            self.year = year

        @property
        def text(self):
            if self.year == 2026:
                return ('quotebridge_v4_line_bk881001_2026({'
                        '"data":"20260723,9,11,8,10,100,1000;20260724,9,11,8,0,100,1000"})')
            return f'quotebridge_v4_line_bk881001_{self.year}({{"data":""}})'

    def fake_get(url, **kwargs):
        year = int(url.split('/01/')[1][:4])
        return FakeResponse(year)

    class FakeDB:
        records = []

        def execute_raw(self, sql, params=None):
            return [{'ts_code': '881001.TI', 'name': 'A'}]

        def upsert_many_from_dicts(self, table, records):
            self.records = records
            return len(records)

    db = FakeDB()
    # Tushare 主路径失败 → 回退直连（本测试验证直连的非法行情整行拒绝）
    with patch('requests.get', side_effect=fake_get), \
         patch.object(data_source, '_call_ths_proxy',
                      side_effect=data_source.DataSourceError('mock代理失败')), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        written, requested = data_source.fetch_ths_daily_klines_akshare(
            [('A', 'industry')], '20260724',
        )

    assert (written, requested) == (1, 1)
    assert len(db.records) == 1
    assert db.records[0]['trade_date'] == '20260723'
    assert db.records[0]['close'] == 10
    assert all(math.isfinite(value) for value in db.records[0].values() if isinstance(value, float))


def test_sector_update_rechecks_coverage_after_targeted_concept_retry():
    from backend.core import update_stock_data

    initial = {
        'ready': True,
        'industry': {'expected': 1, 'covered': 1, 'ready': True},
        'concept': {
            'expected': 2, 'covered': 1, 'ready': True,
            'missing': ['工业互联网'],
        },
        'missing': ['工业互联网'],
        'industry_names': ['A'],
        'concept_names': ['大飞机', '工业互联网'],
    }
    completed = {
        'ready': True,
        'industry': {'expected': 1, 'covered': 1, 'ready': True},
        'concept': {
            'expected': 2, 'covered': 2, 'ready': True,
            'complete': True, 'missing': [],
        },
        'missing': [],
        'industry_names': ['A'],
        'concept_names': ['大飞机', '工业互联网'],
    }
    with patch('backend.data_access.data_source.get_last_completed_trading_day', return_value='20260721'), \
         patch('backend.data_access.data_source.sync_ths_index_from_tushare', return_value=0), \
         patch('backend.data_access.data_source.sync_ths_member_from_tushare', return_value=0), \
         patch.object(update_stock_data, 'datetime') as current_time, \
         patch.object(update_stock_data, 'get_tracked_concept_universe', return_value={
             'names': {'大飞机', '工业互联网'}, 'excluded': {},
         }), \
         patch.object(update_stock_data, 'get_ths_index_names', return_value=[('A', '881001.TI')]), \
         patch.object(update_stock_data, 'fetch_ths_daily_klines_akshare', return_value=(2, 3)), \
         patch.object(
             update_stock_data,
             'get_ths_daily_update_coverage',
             side_effect=[initial, completed],
         ) as get_coverage, \
         patch.object(update_stock_data, 'retry_missing_ths_concepts', return_value={
             'requested': 1, 'covered': 1, 'written': 1,
         }) as retry, \
         patch.object(update_stock_data, 'save_ths_daily_update_confirmation') as save:
        current_time.now.return_value.weekday.return_value = 0
        assert update_stock_data.update_sectors() == (1, 2)

    retry.assert_called_once_with('20260721', ['工业互联网'])
    assert get_coverage.call_count == 2
    save.assert_called_once_with('20260721', completed)


def test_isolated_stage_retries_after_signal_then_succeeds():
    """native 段错误是环境问题：首次信号终止后重跑同阶段应能成功。"""
    from backend.core import update_stock_data

    crashed = type('Result', (), {
        'returncode': -11,
        'stdout': '[stage] first attempt crashed\n',
        'stderr': '',
    })()
    ok = type('Result', (), {
        'returncode': 0,
        'stdout': '__3L_STAGE_RESULT__=[319, 20]\n',
        'stderr': '',
    })()
    with patch.object(update_stock_data.subprocess, 'run', side_effect=[crashed, ok]) as run_mock:
        result = update_stock_data._run_full_stage_isolated('sectors', retry_interval=0)

    assert result == (319, 20)
    assert run_mock.call_count == 2


def test_isolated_stage_gives_up_after_max_attempts():
    """连续信号终止时按最大尝试次数放弃，并向 cron 暴露信号详情。"""
    from backend.core import update_stock_data

    crashed = type('Result', (), {
        'returncode': -11,
        'stdout': '',
        'stderr': '',
    })()
    with patch.object(update_stock_data.subprocess, 'run', return_value=crashed) as run_mock:
        try:
            update_stock_data._run_full_stage_isolated(
                'sectors', max_attempts=2, retry_interval=0,
            )
            assert False, '连续信号终止必须失败'
        except RuntimeError as exc:
            assert '信号 11' in str(exc)

    assert run_mock.call_count == 2


def test_board_fetch_skips_non_ths_codes():
    """GICS/申万等非 88 前缀代码无法直连同花顺，按现状返回空并计入请求数。"""
    from backend.data_access import data_source

    class FakeDB:
        def execute_raw(self, sql, params=None):
            return [{'ts_code': '861001.TI', 'name': 'GICS行业'}]

        def upsert_many_from_dicts(self, table, records):
            return len(records)

    db = FakeDB()
    # Tushare 主路径失败 → 回退直连（GICS 等非 88 前缀无内码，直连返回空）
    with patch.object(data_source, '_call_ths_proxy',
                      side_effect=data_source.DataSourceError('mock代理失败')), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        written, requested = data_source.fetch_ths_daily_klines_akshare(
            [('GICS行业', 'industry')], '20260724',
        )

    assert (written, requested) == (0, 1)


def test_call_ths_proxy_parses_items(monkeypatch):
    """_call_ths_proxy 解析 Tushare 标准响应 {data:{fields, items}}。"""
    from backend.data_access import data_source

    monkeypatch.setattr(data_source, 'TUSHARE_THS_TOKEN', 'test-token')
    monkeypatch.setattr(data_source, 'TUSHARE_THS_URL', 'https://proxy.example.test')

    payload = {
        'code': 0, 'msg': '',
        'data': {
            'fields': ['ts_code', 'trade_date', 'close'],
            'items': [['881271.TI', '20260804', 12018.1]],
        },
    }
    with patch('requests.post', return_value=type('R', (), {'json': lambda self: payload})()):
        rows = data_source._call_ths_proxy('ths_daily', {'trade_date': '20260804'})

    assert rows == [{'ts_code': '881271.TI', 'trade_date': '20260804', 'close': 12018.1}]


def test_call_ths_proxy_raises_on_error_code(monkeypatch):
    """接口返回非零 code 时抛 DataSourceError。"""
    from backend.data_access import data_source

    monkeypatch.setattr(data_source, 'TUSHARE_THS_TOKEN', 'test-token')
    monkeypatch.setattr(data_source, 'TUSHARE_THS_URL', 'https://proxy.example.test')

    payload = {'code': 10001, 'msg': '积分不足', 'data': None}
    with patch('requests.post', return_value=type('R', (), {'json': lambda self: payload})()):
        try:
            data_source._call_ths_proxy('ths_daily', {'trade_date': '20260804'})
            assert False, '非零 code 必须抛异常'
        except data_source.DataSourceError as exc:
            assert '积分不足' in str(exc)


def test_fetch_board_klines_uses_tushare_as_primary():
    """Tushare ths_daily 批量为主路径：一次请求全市场，过滤目标板块后写入。"""
    import math
    from backend.data_access import data_source

    tushare_rows = [
        {'ts_code': '881001.TI', 'trade_date': '20260724',
         'open': 9, 'high': 11, 'low': 8, 'close': 10,
         'pre_close': 9.5, 'change': 0.5, 'pct_chg': 5.26,
         'vol': 100.0, 'amount': 1000.0},
        {'ts_code': '999999.TI', 'trade_date': '20260724',
         'open': 1, 'high': 1, 'low': 1, 'close': 1,
         'pre_close': 1, 'change': 0, 'pct_chg': 0,
         'vol': 1, 'amount': 1},  # 非目标板块，应被过滤
    ]

    class FakeDB:
        records = []

        def execute_raw(self, sql, params=None):
            return [{'ts_code': '881001.TI', 'name': 'A'}]

        def upsert_many_from_dicts(self, table, records):
            self.records = records
            return len(records)

    db = FakeDB()
    with patch.object(data_source, '_call_ths_proxy', return_value=tushare_rows), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        written, requested = data_source.fetch_ths_daily_klines_akshare(
            [('A', 'industry')], '20260724',
        )

    assert (written, requested) == (1, 1)
    assert len(db.records) == 1
    assert db.records[0]['ts_code'] == '881001.TI'
    assert db.records[0]['trade_date'] == '20260724'
    assert db.records[0]['pct_chg'] == 5.26
    assert db.records[0]['amount'] == 1000.0
    assert all(math.isfinite(v) for v in db.records[0].values() if isinstance(v, float))


def test_sync_ths_index_upserts_full_list():
    """ths_index 全量同步：Tushare 返回的板块清单写入表。"""
    from backend.data_access import data_source

    rows = [
        {'ts_code': '881001.TI', 'name': '半导体', 'count': 120, 'list_date': '20200101', 'type': 'I'},
        {'ts_code': '885430.TI', 'name': '人形机器人', 'count': 60, 'list_date': '20240101', 'type': 'N'},
    ]

    class FakeDB:
        def upsert_many_from_dicts(self, table, records):
            self.saved = (table, records)
            return len(records)

    db = FakeDB()
    with patch.object(data_source, '_call_ths_proxy', return_value=rows), \
         patch.object(data_source, '_get_tushare_db', return_value=db):
        written = data_source.sync_ths_index_from_tushare()

    assert written == 2
    assert db.saved[0] == 'ths_index'
    assert db.saved[1][0]['type'] == 'I'


def test_sync_ths_member_only_fetches_missing_concepts():
    """ths_member 增量同步：仅为尚无成分记录的板块拉取。"""
    from backend.data_access import data_source

    class FakeDB:
        def __init__(self):
            self.saved = []

        def execute_raw(self, sql, params=None):
            if 'SELECT DISTINCT ts_code FROM ths_member' in sql:
                return [{'ts_code': '885001.TI'}]  # 已有成分
            return [{'ts_code': '885430.TI'}, {'ts_code': '885001.TI'}]  # ths_index 全量

        def upsert_many_from_dicts(self, table, records):
            self.saved.append(records)
            return len(records)

    db = FakeDB()
    member_rows = [
        {'ts_code': '885430.TI', 'con_code': '000027.SZ', 'con_name': '深圳能源'},
    ]
    with patch.object(data_source, '_call_ths_proxy', return_value=member_rows) as proxy_mock, \
         patch.object(data_source, '_get_tushare_db', return_value=db), \
         patch.object(data_source.time, 'sleep'):
        written = data_source.sync_ths_member_from_tushare()

    assert written == 1
    assert db.saved[0][0]['con_name'] == '深圳能源'
    assert proxy_mock.call_count == 1  # 只拉缺失的 885430
