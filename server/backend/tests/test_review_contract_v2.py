"""复盘 API v2 契约：统一接口语义、行业字段和数据时效。"""
from backend.services.review_service import normalize_review_response


def test_cached_review_contract_is_completed_without_losing_legacy_sector():
    review = normalize_review_response({
        'date': '2026-07-15',
        'holdings_review': [{'code': '000001', 'sector': '银行'}],
    })

    assert review['holdings_review'][0]['industry'] == '银行'
    assert review['holdings_review'][0]['sector'] == '银行'
    assert review['data_dates'] == {}
    assert review['data_freshness'] == {}
    assert review['response_meta'] == {
        'source': 'cache',
        'computed_live': False,
        'contract_version': 2,
    }


def test_live_review_contract_marks_computation_source():
    review = normalize_review_response({}, source='live')

    assert review['response_meta']['source'] == 'live'
    assert review['response_meta']['computed_live'] is True
    assert review['holdings'] == []
    assert review['buy_signals'] == []
