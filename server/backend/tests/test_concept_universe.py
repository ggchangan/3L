"""概念主线宇宙、活跃性过滤与缺失项同源补齐。"""


def test_concept_universe_excludes_labels_and_inactive_sources(monkeypatch):
    from backend.data_access import data_layer

    names = [
        '人脸识别',
        '大飞机',
        '2025年报预增',
        '沪深300样本股',
        '回购增持再贷款概念',
    ]
    concept_list = {
        f'C{i}': {'name': name}
        for i, name in enumerate(names)
    }
    stock_concept_map = {}
    watchlist = []
    for index, concept_code in enumerate(concept_list):
        for stock_index in range(6):
            code = f'{index:02d}{stock_index:04d}'
            watchlist.append({'code': code})
            stock_concept_map[code] = {
                'concept_codes': [concept_code],
                'concept_names': [concept_list[concept_code]['name']],
            }

    monkeypatch.setattr(data_layer, 'get_concept_list', lambda: concept_list)
    monkeypatch.setattr(data_layer, 'get_stock_concept_map', lambda: stock_concept_map)
    monkeypatch.setattr(data_layer, 'get_watchlist', lambda: watchlist)
    monkeypatch.setattr(
        'backend.data_access.data_source.get_ths_concept_latest_dates',
        lambda names, reference_date=None: {
            '人脸识别': '20260721',
            '大飞机': '20260721',
            '回购增持再贷款概念': '20260608',
        },
    )

    universe = data_layer.get_tracked_concept_universe(
        min_related_stocks=6,
        reference_date='20260722',
    )

    assert universe['names'] == {'人脸识别', '大飞机'}
    assert universe['excluded']['2025年报预增']['reason'] == 'expired_periodic_event'
    assert universe['excluded']['沪深300样本股']['reason'] == 'index_membership'
    assert universe['excluded']['回购增持再贷款概念'] == {
        'reason': 'source_inactive',
        'last_date': '20260608',
        'related_watchlist': 6,
    }
    # 过滤仅决定主线宇宙，不改写个股原始概念标签。
    assert stock_concept_map['020000']['concept_names'] == ['2025年报预增']


def test_retry_missing_concepts_uses_ths_target_rows_and_writes_db(monkeypatch):
    from backend.data_access import data_source

    written = []

    class FakeDb:
        def upsert_many_from_dicts(self, table, records):
            assert table == 'ths_daily'
            written.extend(records)
            return len(records)

    monkeypatch.setattr(data_source, '_get_tushare_db', lambda: FakeDb())
    monkeypatch.setattr(
        data_source,
        '_fetch_ths_kline_close_snapshots',
        lambda target_date, names, ths_type: {
            '大飞机': {
                'ts_code': '885566.TI',
                'open': 100,
                'high': 103,
                'low': 99,
                'close': 102,
                'volume': 1200,
                'change_pct': 2,
            },
        },
    )

    result = data_source.retry_missing_ths_concepts(
        '20260722',
        ['大飞机', '工业互联网'],
    )

    assert result == {
        'requested': 2,
        'covered': 1,
        'written': 1,
        'covered_names': ['大飞机'],
        'missing': ['工业互联网'],
    }
    assert written == [{
        'ts_code': '885566.TI',
        'trade_date': '20260722',
        'open': 100,
        'high': 103,
        'low': 99,
        'close': 102,
        'vol': 1200,
        'pct_chg': 2,
    }]


def test_retry_missing_industries_uses_ths_target_rows_and_writes_db(monkeypatch):
    from backend.data_access import data_source

    written = []
    calls = []

    class FakeDb:
        def upsert_many_from_dicts(self, table, records):
            assert table == 'ths_daily'
            written.extend(records)
            return len(records)

    def fake_snapshots(target_date, names, ths_type):
        calls.append((target_date, set(names), ths_type))
        return {
            '中药': {
                'ts_code': '881141.TI',
                'open': 100,
                'high': 103,
                'low': 99,
                'close': 102,
                'volume': 1200,
                'change_pct': 2,
            },
        }

    monkeypatch.setattr(data_source, '_get_tushare_db', lambda: FakeDb())
    monkeypatch.setattr(data_source, '_fetch_ths_kline_close_snapshots', fake_snapshots)

    result = data_source.retry_missing_ths_industries(
        '20260811',
        ['中药', '保险'],
    )

    assert calls == [('20260811', {'中药', '保险'}, 'I')]
    assert result == {
        'requested': 2,
        'covered': 1,
        'written': 1,
        'covered_names': ['中药'],
        'missing': ['保险'],
    }
    assert written == [{
        'ts_code': '881141.TI',
        'trade_date': '20260811',
        'open': 100,
        'high': 103,
        'low': 99,
        'close': 102,
        'vol': 1200,
        'pct_chg': 2,
    }]
