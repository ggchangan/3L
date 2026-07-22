"""复盘 API 公共契约。

将历史兼容、数据日期和正式/预估/过期状态集中在一个模块，避免接口层、
计算层和前端分别推断同一件事。
"""


def _normalize_date(value):
    return str(value or '').replace('-', '')


def _quote_status(date_value, requested_date):
    date_value = _normalize_date(date_value)
    requested_date = _normalize_date(requested_date)
    if not date_value:
        return 'unknown'
    return 'confirmed' if requested_date and date_value >= requested_date else 'stale'


def _ranking_status(mainline, confirmed_date):
    mainline = mainline if isinstance(mainline, dict) else {}
    status = mainline.get('ranking_status') or 'unknown'
    return {
        'status': status,
        'date': _normalize_date(mainline.get('ranking_date')),
        'confirmed_date': _normalize_date(confirmed_date),
        'base_date': _normalize_date(mainline.get('base_date')),
        'coverage': mainline.get('estimate_coverage'),
        'coverage_detail': mainline.get('estimate_coverage_detail') or {},
    }


def build_review_data_status(requested_date, index_date, stock_date, sector_date, mainline):
    """生成唯一的数据状态语义，明确区分正式、预估和过期。"""
    mainline = mainline if isinstance(mainline, dict) else {}
    concept = mainline.get('concept_mainline') or {}
    result = {
        'requested_date': _normalize_date(requested_date),
        'index': {
            'status': _quote_status(index_date, requested_date),
            'date': _normalize_date(index_date),
        },
        'stocks': {
            'status': _quote_status(stock_date, requested_date),
            'date': _normalize_date(stock_date),
        },
        'industry': _ranking_status(mainline, sector_date),
        'concept': _ranking_status(concept, sector_date),
    }
    statuses = [result[key]['status'] for key in ('index', 'stocks', 'industry', 'concept')]
    if all(status in ('confirmed', 'estimated') for status in statuses):
        result['overall'] = 'ready'
    elif any(status in ('confirmed', 'estimated') for status in statuses):
        result['overall'] = 'partial'
    else:
        result['overall'] = 'stale'
    return result


def _legacy_freshness(status):
    if status == 'confirmed':
        return 'current'
    if status in ('estimated', 'stale'):
        return 'stale'
    return 'unknown'


def normalize_review_response(data, source='cache'):
    """补齐 v3 复盘契约，并为历史缓存提供无损兼容。"""
    result = dict(data) if isinstance(data, dict) else {}
    result.setdefault('date', '')
    result.setdefault('market', {})
    result.setdefault('mainline', {})
    result.setdefault('timing_signals', {})
    result.setdefault('trading_plan', {})

    # review 后缀字段是 v3 唯一页面契约；旧字段仅作为历史缓存输入。
    result.setdefault('holdings_review', result.get('holdings') or [])
    result.setdefault('buy_signals_review', result.get('buy_signals') or [])

    for key in ('holdings_review', 'buy_signals_review'):
        items = result.get(key)
        if not isinstance(items, list):
            result[key] = []
            continue
        for item in items:
            if isinstance(item, dict):
                industry = item.get('industry') or item.get('sector') or item.get('ths_industry') or ''
                item.setdefault('industry', industry)
                item.setdefault('sector', industry)

    legacy_dates = result.get('data_dates') if isinstance(result.get('data_dates'), dict) else {}
    data_status = result.get('data_status')
    if not isinstance(data_status, dict) or not data_status:
        data_status = build_review_data_status(
            legacy_dates.get('requested') or result.get('date'),
            legacy_dates.get('index'),
            legacy_dates.get('stocks'),
            legacy_dates.get('sectors'),
            result.get('mainline'),
        )
    result['data_status'] = data_status
    result['data_stale'] = data_status.get('overall') != 'ready'

    # 两个旧字段只用于旧客户端；新代码不得再从它们推断预估状态。
    result.setdefault('data_dates', {
        'requested': result.get('date', ''),
        'index': data_status.get('index', {}).get('date', ''),
        'stocks': data_status.get('stocks', {}).get('date', ''),
        'sectors': data_status.get('industry', {}).get('confirmed_date', ''),
    })
    result.setdefault('data_freshness', {
        'index': _legacy_freshness(data_status.get('index', {}).get('status')),
        'stocks': _legacy_freshness(data_status.get('stocks', {}).get('status')),
        'sectors': _legacy_freshness(data_status.get('industry', {}).get('status')),
    })
    result['response_meta'] = {
        'source': source,
        'computed_live': source == 'live',
        'contract_version': 3,
        'deprecated_fields': ['holdings', 'buy_signals', 'data_dates', 'data_freshness', 'data_stale'],
    }
    return result
