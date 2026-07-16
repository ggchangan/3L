from threel_core.parameters import (
    PARAMETER_MANIFEST, PARAMETER_VERSION, TREND_PARAMETERS,
    get_parameter_manifest,
)


def test_manifest_binds_version_sources_and_backtest_basis():
    assert PARAMETER_MANIFEST['version'] == PARAMETER_VERSION
    assert PARAMETER_MANIFEST['knowledge_sources']
    assert PARAMETER_MANIFEST['backtest_basis']['runner'].endswith('::run_backtest')
    assert PARAMETER_MANIFEST['backtest_basis']['metrics']
    assert PARAMETER_MANIFEST['parameters'] == TREND_PARAMETERS


def test_manifest_returns_defensive_copy():
    manifest = get_parameter_manifest()
    manifest['parameters']['bias5_buy_max'] = 999
    assert TREND_PARAMETERS['bias5_buy_max'] == 2.0
