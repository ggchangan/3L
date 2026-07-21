"""板块数据源口径与获取通道契约。"""

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
        _validate_auxiliary_sector_provider('ths')


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
        'provider': 'eastmoney',
        'cross_provider_composite': True,
        'status': 'legacy_pending_ths_migration',
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
