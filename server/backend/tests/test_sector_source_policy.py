"""板块数据源口径与获取通道契约。"""

import json

import pytest


def test_default_ths_chain_uses_only_ths_transports():
    from backend.data_access.data_source import (
        SECTOR_TRANSPORT_PROVIDERS,
        _sector_ranking_chain,
    )

    names = [name for name, _ in _sector_ranking_chain('ths')]

    assert names == [
        'tushare_ths_db',
        'ths_live_akshare',
        'tushare_ths_confirmed',
        'ths_snapshot',
    ]
    assert {SECTOR_TRANSPORT_PROVIDERS[name] for name in names} == {'ths'}


def test_unknown_provider_is_rejected():
    from backend.data_access.data_source import _sector_ranking_chain

    with pytest.raises(RuntimeError, match='未知板块 provider'):
        _sector_ranking_chain('unknown')


def test_incomplete_primary_provider_is_rejected():
    from backend.data_access.data_source import _validate_primary_sector_provider

    with pytest.raises(RuntimeError, match='主 provider 不完整'):
        _validate_primary_sector_provider('eastmoney')


def test_unknown_auxiliary_provider_is_rejected():
    from backend.data_access.data_source import _validate_auxiliary_sector_provider

    with pytest.raises(RuntimeError, match='未知或未实现'):
        _validate_auxiliary_sector_provider('unknown')


def test_cross_provider_transport_is_rejected(monkeypatch):
    from backend.data_access import data_source

    bad_chain = list(data_source.SECTOR_RANKING_CHAINS['ths']) + [
        ('eastmoney_live', lambda date: None),
    ]
    monkeypatch.setitem(data_source.SECTOR_RANKING_CHAINS, 'ths', bad_chain)

    with pytest.raises(RuntimeError, match='跨 provider'):
        data_source._sector_ranking_chain('ths')


def test_health_status_exposes_active_sector_policy(monkeypatch):
    from backend.data_access import data_source

    monkeypatch.setattr(data_source, 'get_all_health', lambda: {'sources': {}, 'transitions': []})

    status = data_source.get_data_source_status()

    assert status['sector_policy']['provider'] == 'ths'
    assert status['sector_policy']['authoritative_cross_provider_merge'] is False
    assert status['sector_policy']['intraday_estimate'] == {
        'enabled': True,
        'provider': 'ths',
        'cross_provider_composite': False,
        'status': 'same_provider_estimate',
        'transports': ['10jqka_kline'],
    }


def test_disabling_auxiliary_provider_prevents_close_fetch(monkeypatch):
    from backend.data_access import data_source
    from backend.core.exceptions import DataSourceError

    monkeypatch.setattr(data_source, '_ACTIVE_AUXILIARY_PROVIDER', 'disabled')
    monkeypatch.setattr(
        data_source,
        '_fetch_eastmoney_close_ranking',
        lambda date: pytest.fail('disabled auxiliary source must not be called'),
    )

    with pytest.raises(DataSourceError, match='辅助 provider 已禁用'):
        data_source.fetch_sector_close_snapshot('20260722', [], [])


def test_disabling_auxiliary_provider_hides_existing_snapshot(monkeypatch):
    from backend.data_access import data_source

    monkeypatch.setattr(data_source, '_ACTIVE_AUXILIARY_PROVIDER', 'disabled')
    monkeypatch.setattr(
        data_source,
        '_load_json',
        lambda *args: pytest.fail('disabled auxiliary snapshot must not be read'),
    )

    assert data_source.get_sector_close_snapshot() == {}


def test_close_snapshot_rejects_previous_provider_file(monkeypatch):
    from backend.data_access import data_source

    monkeypatch.setattr(data_source, '_ACTIVE_AUXILIARY_PROVIDER', 'ths')
    monkeypatch.setattr(
        data_source,
        '_load_json',
        lambda *args: {'date': '20260722', 'source': 'eastmoney_close'},
    )

    assert data_source.get_sector_close_snapshot() == {}


def test_ths_snapshot_passes_full_authoritative_coverage(monkeypatch, tmp_path):
    from backend.data_access import data_source

    names = [f'I{i:03d}' for i in range(319)]
    raw = {
        'source': 'ths_close',
        'last_updated': '20260722',
        'industries': {
            name: {
                'date': '20260722',
                'change_pct': 1.0,
                'timestamp_verified': True,
            }
            for name in names
        },
        'concepts': {},
    }
    monkeypatch.setattr(data_source, '_ACTIVE_AUXILIARY_PROVIDER', 'ths')
    monkeypatch.setattr(
        data_source,
        'SECTOR_CLOSE_SNAPSHOT_PATH',
        str(tmp_path / 'sector_close_snapshot.json'),
    )
    monkeypatch.setattr(
        data_source,
        '_fetch_ths_close_ranking',
        lambda target, industry_names, concept_names: raw,
    )

    result = data_source.fetch_sector_close_snapshot('20260722', names, [])

    assert result['source'] == 'ths_close'
    assert result['coverage']['industry']['covered'] == 319
    assert result['coverage']['industry']['ratio'] == 1.0
    assert result['coverage']['industry']['ready'] is True


def test_ths_close_ranking_combines_verified_industries_and_concepts(monkeypatch):
    from backend.data_access import data_source

    monkeypatch.setattr(
        data_source,
        '_fetch_ths_kline_close_snapshots',
        lambda date, names, kind: (
            {'半导体': {'date': date, 'change_pct': 2.5, 'provider': 'ths'}}
            if kind == 'I'
            else {'机器人概念': {'date': date, 'change_pct': 1.2}}
        ),
    )

    result = data_source._fetch_ths_close_ranking(
        '20260722', ['半导体'], ['机器人概念']
    )

    assert result['source'] == 'ths_close'
    assert result['industries']['半导体']['provider'] == 'ths'
    assert result['concepts']['机器人概念']['change_pct'] == 1.2


def test_ths_concept_snapshot_requires_explicit_target_date(monkeypatch):
    from backend.data_access import data_source

    class FakeDb:
        def get_all_ths_codes(self):
            return [('885517.TI', '机器人概念', 'N')]

    class Response:
        text = 'callback(' + json.dumps({
            'data': (
                '20260720,100,102,99,101,1000,10000;'
                '20260721,101,104,100,103,1200,12000'
            ),
        }) + ')'

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(data_source, '_get_tushare_db', lambda: FakeDb())
    monkeypatch.setattr('requests.get', lambda *args, **kwargs: Response())

    available = data_source._fetch_ths_kline_close_snapshots(
        '20260721', ['机器人概念'], 'N'
    )
    missing = data_source._fetch_ths_kline_close_snapshots(
        '20260722', ['机器人概念'], 'N'
    )

    assert available['机器人概念']['change_pct'] == 1.98
    assert available['机器人概念']['date_verification'] == 'ths_kline_target_row'
    assert missing == {}


def test_ths_snapshot_uses_previous_year_close_on_first_trading_day(monkeypatch):
    from backend.data_access import data_source

    class FakeDb:
        def get_all_ths_codes(self):
            return [('885517.TI', '机器人概念', 'N')]

    class Response:
        def __init__(self, rows):
            self.text = 'callback(' + json.dumps({'data': rows}) + ')'

        @staticmethod
        def raise_for_status():
            return None

    def fake_get(url, **kwargs):
        if url.endswith('/2026.js'):
            return Response('20261231,100,102,99,100,1000,10000')
        return Response('20270104,103,106,102,105,1200,12000')

    monkeypatch.setattr(data_source, '_get_tushare_db', lambda: FakeDb())
    monkeypatch.setattr('requests.get', fake_get)

    result = data_source._fetch_ths_kline_close_snapshots(
        '20270104', ['机器人概念'], 'N'
    )

    assert result['机器人概念']['prev_close'] == 100
    assert result['机器人概念']['change_pct'] == 5.0


def test_ths_snapshot_retries_only_missing_items_after_partial_success(monkeypatch):
    from backend.data_access import data_source

    class FakeDb:
        def get_all_ths_codes(self):
            return [
                ('885001.TI', '概念一', 'N'),
                ('885002.TI', '概念二', 'N'),
            ]

    class Response:
        def __init__(self, text):
            self.text = text

        @staticmethod
        def raise_for_status():
            return None

    calls = {'885001': 0, '885002': 0}

    def fake_get(url, **kwargs):
        code = '885001' if '885001' in url else '885002'
        calls[code] += 1
        if code == '885002' and calls[code] <= 2:
            return Response('rate limited')
        rows = '20260720,100,102,99,100,1000,10000;20260721,101,103,100,102,1200,12000'
        return Response('callback(' + json.dumps({'data': rows}) + ')')

    monkeypatch.setattr(data_source, '_get_tushare_db', lambda: FakeDb())
    monkeypatch.setattr('requests.get', fake_get)
    monkeypatch.setattr(data_source.time, 'sleep', lambda seconds: None)

    result = data_source._fetch_ths_kline_close_snapshots(
        '20260721', ['概念一', '概念二'], 'N'
    )

    assert set(result) == {'概念一', '概念二'}
    assert calls['885001'] == 1
    assert calls['885002'] == 3


def test_ranking_failover_skips_transport_without_requested_type(monkeypatch):
    from backend.data_access import data_source

    chain = [
        ('industry_only', lambda date: {'industries': {'银行': {}}, 'concepts': {}}),
        ('concept_snapshot', lambda date: {'concepts': {'机器人': {'change_pct': 1.0}}}),
    ]
    monkeypatch.setitem(data_source.DATA_SOURCE_CHAINS, 'sector_ranking', chain)
    monkeypatch.setattr(data_source, 'is_source_available', lambda name: True)
    monkeypatch.setattr(data_source, 'report_success', lambda name: None)

    result = data_source.get_sector_rankings('concept', '20260722')

    assert result == {'机器人': {'change_pct': 1.0}}
