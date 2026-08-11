"""实验性 L1 动量主线模型：从强势个股聚合到 THS 行业。"""

from collections import defaultdict


def _return_20d(rows, as_of_date):
    cutoff = str(as_of_date or '').replace('-', '')
    eligible = sorted(
        (row for row in (rows or []) if not cutoff or str(row.get('date', '')).replace('-', '') <= cutoff),
        key=lambda row: str(row.get('date', '')),
    )
    if len(eligible) < 21:
        return None, eligible
    base = float(eligible[-21].get('close', 0) or 0)
    current = float(eligible[-1].get('close', 0) or 0)
    if base <= 0 or current <= 0:
        return None, eligible
    return (current / base - 1) * 100, eligible


def compute_l1_industry_rankings(stocks, industry_map, as_of_date,
                                 institution_holdings=None, previous=None,
                                 top_n_floor=700, dynamic_top_ratio=0.13):
    """计算可回放的 THS 行业 L1 影子榜，不接入交易计划。"""
    stock_rows = {}
    for group in (stocks or {}).values():
        if isinstance(group, dict):
            stock_rows.update({str(code).split('.')[0]: rows for code, rows in group.items()})

    candidates = []
    incomplete_kline = 0
    for code, rows in stock_rows.items():
        return_20d, eligible_rows = _return_20d(rows, as_of_date)
        if return_20d is None:
            incomplete_kline += 1
            continue
        candidates.append((code, return_20d, eligible_rows))

    candidates.sort(key=lambda item: item[1], reverse=True)
    top_n = min(len(candidates), max(int(top_n_floor), round(len(candidates) * dynamic_top_ratio)))
    momentum_pool = candidates[:top_n]

    holdings = institution_holdings or {}
    holdings_coverage = (
        sum(1 for code, _, _ in momentum_pool if code in holdings) / len(momentum_pool)
        if momentum_pool else 0.0
    )
    institution_filter_ready = bool(momentum_pool) and holdings_coverage >= 0.95
    if institution_filter_ready:
        momentum_pool = [
            item for item in momentum_pool
            if float(holdings[item[0]].get('fund_pct', 0) or 0) >= 2
            and float(holdings[item[0]].get('northbound_pct', 0) or 0) >= 0.5
        ]

    members = defaultdict(set)
    for code, info in (industry_map or {}).items():
        industry = info.get('ths_industry', '') if isinstance(info, dict) else str(info or '')
        if industry:
            members[industry].add(str(code).split('.')[0])

    hits = defaultdict(list)
    for code, return_20d, rows in momentum_pool:
        info = (industry_map or {}).get(code, {})
        industry = info.get('ths_industry', '') if isinstance(info, dict) else str(info or '')
        if industry:
            hits[industry].append((code, return_20d, rows))

    previous_by_name = {item.get('name'): item for item in (previous or [])}
    rankings = []
    for industry, constituent_codes in members.items():
        industry_hits = hits.get(industry, [])
        count = len(industry_hits)
        constituent_count = len(constituent_codes)
        coverage = count / constituent_count if constituent_count else 0.0
        score = count * coverage
        status = 'climax_warning' if score > 7 else 'confirmed' if score > 1 else 'not_confirmed'
        prior = previous_by_name.get(industry)
        if not prior and status != 'not_confirmed':
            rotation_state = 'new'
        elif prior and score > float(prior.get('momentum_score', 0)):
            rotation_state = 'strengthening'
        elif prior and score < float(prior.get('momentum_score', 0)):
            rotation_state = 'declining'
        else:
            rotation_state = 'persistent' if prior else 'none'
        rankings.append({
            'name': industry,
            'momentum_stock_count': count,
            'constituent_count': constituent_count,
            'coverage': round(coverage, 4),
            'momentum_score': round(score, 4),
            'status': status,
            'rotation_state': rotation_state,
            'consecutive_days': int(prior.get('consecutive_days', 0)) + 1 if prior else 1,
            'new_high_count': None,
            'new_high_overlap': None,
            'top_stocks': [code for code, _, _ in industry_hits[:10]],
        })
    rankings.sort(key=lambda item: item['momentum_score'], reverse=True)

    return {
        'model_type': 'l1_momentum_mainline',
        'is_l1_model': True,
        'experimental': True,
        'as_of_date': str(as_of_date),
        'data_status': 'experimental' if institution_filter_ready else 'partial',
        'institution_filter_applied': institution_filter_ready,
        'input_coverage': {
            'eligible_stock_count': len(candidates),
            'missing_kline_count': incomplete_kline,
            'institution_holdings': round(holdings_coverage, 4),
            'new_high_52w': 0.0,
        },
        'momentum_pool_size': len(momentum_pool),
        'rankings': rankings,
    }
