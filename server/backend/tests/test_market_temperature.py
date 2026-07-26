from backend.services.market_temperature_service import (
    _load_confirmed_cache,
    _save_confirmed_cache,
    classify_market_temperature,
    get_market_temperature,
)


class FakeTemperatureDB:
    def __init__(self, *, limit_covered=100, adj_covered=100, compared=90,
                 stock_complete=100, previous_count=100):
        self.limit_covered = limit_covered
        self.adj_covered = adj_covered
        self.compared = compared
        self.stock_complete = stock_complete
        self.previous_count = previous_count

    def execute_raw(self, sql, params=None):
        compact = ' '.join(sql.split())
        if 'MAX(trade_date) AS trade_date' in compact:
            return [{'trade_date': '20260724'}]
        if 'SUM(CASE WHEN pct_chg > 0' in compact:
            return [{
                'total': 100, 'up_count': 10, 'down_count': 88, 'flat_count': 2,
                'complete_count': self.stock_complete, 'total_amount': 1_000_000,
            }]
        if 'AS listed_count' in compact:
            return [{'listed_count': self.previous_count, 'recent_max': self.previous_count}]
        if 'LEFT JOIN stk_limit' in compact:
            return [{'covered': self.limit_covered, 'limit_up': 5, 'limit_down': 8}]
        if 'LEFT JOIN adj_factor' in compact:
            return [{'covered': self.adj_covered}]
        if 'SELECT DISTINCT trade_date' in compact:
            return [{'trade_date': f'2026{i:04d}'} for i in range(1, 251)]
        if 'yearly_extremes' in compact:
            return [{'compared': self.compared, 'new_high': 7, 'new_low': 30}]
        if 'SUM(COALESCE(amount, 0)) AS amount' in compact:
            return [{'trade_date': f'202607{i:02d}', 'amount': 1_000_000} for i in range(20, 0, -1)]
        raise AssertionError(f'未处理 SQL: {compact}')


def test_ice_point_uses_breadth_and_knowledge_base_year_high_threshold():
    level, label, evidence = classify_market_temperature({
        'total': 100, 'up': 10, 'down': 88,
        'new_high_1y': 7, 'new_low_1y': 30,
        'limit_up': 5, 'limit_down': 8,
    })

    assert level == 'ice'
    assert label == '冰点观察'
    assert any('知识库冰点参考线20家' in item for item in evidence)


def test_market_temperature_returns_transparent_confirmed_metrics():
    result = get_market_temperature('2026-07-24', db=FakeTemperatureDB())

    assert result['status'] == 'confirmed'
    assert result['level'] == 'ice'
    assert result['date'] == '20260724'
    assert result['metrics']['up'] == 10
    assert result['metrics']['down'] == 88
    assert result['metrics']['new_high_1y'] == 7
    assert result['metrics']['new_low_1y'] == 30
    assert result['metrics']['amount_yi'] == 10.0
    assert result['quality']['limit_covered'] == 100
    assert result['rules'][0]['origin'] == '3L训练营'


def test_partial_coverage_never_uses_unreliable_year_high_counts():
    result = get_market_temperature(
        '20260724',
        db=FakeTemperatureDB(limit_covered=60, adj_covered=100, compared=50),
    )

    assert result['status'] == 'partial'
    assert result['metrics']['new_high_1y'] is None
    assert result['metrics']['new_low_1y'] is None
    assert any('涨跌停价格覆盖不足' in item for item in result['quality']['missing'])
    assert any('一年新高/新低可比样本不足' in item for item in result['quality']['missing'])


def test_incomplete_core_daily_rows_never_become_confirmed():
    result = get_market_temperature(
        '20260724', db=FakeTemperatureDB(stock_complete=70, previous_count=120),
    )

    assert result['status'] == 'partial'
    assert any('核心日线数量异常' in item for item in result['quality']['missing'])
    assert any('核心日线字段不完整' in item for item in result['quality']['missing'])


def test_unavailable_database_degrades_only_temperature_block():
    result = get_market_temperature('20260724', db=False)
    assert result['status'] == 'unavailable'
    assert 'level' in result
    assert 'quality' in result


def test_only_confirmed_daily_temperature_is_cached(monkeypatch, tmp_path):
    import backend.services.market_temperature_service as service
    monkeypatch.setattr(service, 'TEMPERATURE_CACHE_DIR', str(tmp_path))
    confirmed = get_market_temperature('20260724', db=FakeTemperatureDB())
    _save_confirmed_cache(confirmed)
    assert _load_confirmed_cache('20260724')['metrics']['new_high_1y'] == 7

    partial = get_market_temperature(
        '20260725', db=FakeTemperatureDB(limit_covered=60, adj_covered=60, compared=0),
    )
    _save_confirmed_cache(partial)
    assert _load_confirmed_cache('20260725') is None
