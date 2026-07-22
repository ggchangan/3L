from datetime import datetime, timedelta
from unittest.mock import patch


def _descending_klines(count=40):
    rows = []
    start = datetime(2026, 1, 1)
    for day in range(1, count + 1):
        date_str = (start + timedelta(days=day - 1)).strftime('%Y%m%d')
        rows.append({
            'date': date_str,
            'open': day,
            'close': day,
            'high': day + 1,
            'low': day - 1,
            'volume': day * 100,
        })
    return list(reversed(rows))


def test_market_health_normalizes_descending_database_klines():
    from backend.services import market_health_service

    with patch(
        'backend.data_access.data_layer.get_index_klines',
        return_value=_descending_klines(),
    ):
        data = market_health_service._load_index_data()

    assert data['last_close'] == 40
    assert data['closes'][-1] == 40
    assert data['data_date'] == '20260209'
    assert data['source'] == 'tushare_mysql'


def test_mainline_does_not_publish_placeholder_gap(tmp_path, monkeypatch):
    from backend.services import market_health_service

    path = tmp_path / 'mainline_history.json'
    path.write_text(
        '{"2026-07-22":{"top10":["A","B","C","D","E"]}}',
        encoding='utf-8',
    )
    monkeypatch.setattr(market_health_service, 'DATA_DIR', str(tmp_path))

    result = market_health_service._load_mainline()

    assert result['gap_pct'] is None
    assert result['data_date'] == '2026-07-22'


def test_monitor_context_uses_previous_open_day(monkeypatch):
    from backend.services import monitor_service

    class Monday(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 27, 9, 0, 0)

    monkeypatch.setattr(monitor_service, 'datetime', Monday)
    monkeypatch.setattr(
        'backend.data_access.data_source._get_trade_date_cache',
        lambda: {'20260724', '20260727'},
    )

    result = monitor_service.get_monitor_context()

    assert result['today'] == '2026-07-27'
    assert result['previous_trading_day'] == '2026-07-24'


def test_concept_monitor_uses_unified_ths_ranking(monkeypatch):
    from backend.core import monitor_data

    monkeypatch.setattr(
        'backend.data_access.data_source.get_sector_rankings_with_meta',
        lambda sector_type: {
            'data': {
                '机器人概念': {'change_pct': 3.2},
                '算力概念': {'change_pct': -1.1},
            },
            'data_date': '20260721', 'requested_date': '20260722',
            'available': True, 'stale': True, 'provider': 'ths',
        },
    )

    result = monitor_data.get_top_concept_sectors_with_5d()

    assert result['today_top5'][0] == {'name': '机器人概念', 'chg': 3.2}
    assert result['meta']['data_date'] == '20260721'
    assert result['meta']['stale'] is True
