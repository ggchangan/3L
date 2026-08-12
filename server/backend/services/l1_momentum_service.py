"""实验性 L1 动量主线模型：从强势个股聚合到 THS 行业。"""

import json
import os
import hashlib
from collections import defaultdict
from datetime import datetime, timezone

from backend.core import config

L1_SHADOW_DIR = os.path.join(config.COMPUTED_DIR, 'l1_momentum_shadow')


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
                                 top_n_floor=700, dynamic_top_ratio=0.13,
                                 stock_features=None, universe_meta=None,
                                 institution_as_of_date=None, previous_as_of_date=None):
    """计算可回放的 THS 行业 L1 影子榜，不接入交易计划。"""
    stock_rows = {}
    for group in (stocks or {}).values():
        if isinstance(group, dict):
            stock_rows.update({str(code).split('.')[0]: rows for code, rows in group.items()})

    candidates = []
    incomplete_kline = 0
    feature_rows = list(stock_features or [])
    if feature_rows:
        for feature in feature_rows:
            code = str(feature.get('code') or '').split('.')[0]
            value = feature.get('return_20d')
            if not code or value is None or not feature.get('adjustment_complete', False):
                incomplete_kline += 1
                continue
            candidates.append((code, float(value), None, feature.get('high_52w')))
    else:
        for code, rows in stock_rows.items():
            return_20d, eligible_rows = _return_20d(rows, as_of_date)
            if return_20d is None:
                incomplete_kline += 1
                continue
            high_52w = None
            if len(eligible_rows) >= 250:
                current_high = float(eligible_rows[-1].get('high', eligible_rows[-1].get('close', 0)) or 0)
                prior_high = max(
                    float(row.get('high', row.get('close', 0)) or 0)
                    for row in eligible_rows[-250:-1]
                )
                high_52w = current_high >= prior_high
            candidates.append((code, return_20d, eligible_rows, high_52w))

    candidates.sort(key=lambda item: item[1], reverse=True)
    top_n = min(len(candidates), max(int(top_n_floor), round(len(candidates) * dynamic_top_ratio)))
    momentum_pool = candidates[:top_n]

    holdings = institution_holdings or {}
    holdings_coverage = (
        sum(1 for code, *_ in momentum_pool if code in holdings) / len(momentum_pool)
        if momentum_pool else 0.0
    )
    institution_filter_ready = bool(momentum_pool) and holdings_coverage >= 0.95
    if institution_filter_ready:
        momentum_pool = [
            item for item in momentum_pool
            if float(holdings.get(item[0], {}).get('fund_pct', 0) or 0) >= 2
            and float(holdings.get(item[0], {}).get('northbound_pct', 0) or 0) >= 0.5
        ]

    members = defaultdict(set)
    for code, info in (industry_map or {}).items():
        industry = info.get('ths_industry', '') if isinstance(info, dict) else str(info or '')
        if industry:
            members[industry].add(str(code).split('.')[0])

    mapped_candidate_count = sum(
        1 for code, *_ in candidates
        if code in (industry_map or {})
        and isinstance((industry_map or {}).get(code), dict)
        and (industry_map or {})[code].get('ths_industry')
    )
    observed_count = len(feature_rows) if feature_rows else len(stock_rows)
    expected_count = int((universe_meta or {}).get('expected_stock_count') or observed_count)
    universe_coverage = observed_count / expected_count if expected_count else 0.0
    kline_coverage = len(candidates) / expected_count if expected_count else 0.0
    listing_date_coverage = (
        sum(bool(row.get('list_date')) for row in feature_rows) / observed_count
        if feature_rows and observed_count else (1.0 if observed_count else 0.0)
    )
    target_date_coverage = (
        sum(str(row.get('latest_date') or '') == str(as_of_date).replace('-', '') for row in feature_rows)
        / observed_count if feature_rows and observed_count else (1.0 if observed_count else 0.0)
    )
    industry_mapping_coverage = (
        mapped_candidate_count / len(candidates) if candidates else 0.0
    )

    hits = defaultdict(list)
    for code, return_20d, rows, high_52w in momentum_pool:
        info = (industry_map or {}).get(code, {})
        industry = info.get('ths_industry', '') if isinstance(info, dict) else str(info or '')
        if industry:
            hits[industry].append((code, return_20d, rows, high_52w))

    high_52w_by_code = {code: high_52w for code, _, _, high_52w in candidates}
    high_52w_coverage = (
        sum(value is not None for value in high_52w_by_code.values()) / len(high_52w_by_code)
        if high_52w_by_code else 0.0
    )

    previous_by_name = {item.get('name'): item for item in (previous or [])}
    rankings = []
    for industry, constituent_codes in members.items():
        industry_hits = hits.get(industry, [])
        count = len(industry_hits)
        constituent_count = len(constituent_codes)
        coverage = count / constituent_count if constituent_count else 0.0
        score = count * coverage
        new_high_count = sum(high_52w_by_code.get(code) is True for code in constituent_codes)
        new_high_overlap = sum(item[3] is True for item in industry_hits)
        status = 'climax_warning' if score > 7 else 'confirmed' if score > 1 else 'not_confirmed'
        prior = previous_by_name.get(industry)
        prior_active = bool(prior and prior.get('score_status', prior.get('status')) in ('confirmed', 'climax_warning'))
        if status == 'not_confirmed':
            rotation_state = 'exited' if prior_active else 'none'
            consecutive_days = 0
        elif not prior_active:
            rotation_state = 'new'
        elif not previous_as_of_date and prior:
            rotation_state = 'unavailable'
        elif prior and score > float(prior.get('momentum_score', 0)):
            rotation_state = 'strengthening'
        elif prior and score < float(prior.get('momentum_score', 0)):
            rotation_state = 'declining'
        else:
            rotation_state = 'persistent'
        if status != 'not_confirmed' and rotation_state != 'unavailable':
            consecutive_days = int(prior.get('consecutive_days', 0)) + 1 if prior_active else 1
        elif rotation_state == 'unavailable':
            consecutive_days = 0
        rankings.append({
            'name': industry,
            'momentum_stock_count': count,
            'constituent_count': constituent_count,
            'coverage': round(coverage, 4),
            'momentum_score': round(score, 4),
            'status': status,
            'rotation_state': rotation_state,
            'consecutive_days': consecutive_days,
            'new_high_count': new_high_count if high_52w_coverage > 0 else None,
            'new_high_overlap': new_high_overlap if high_52w_coverage > 0 else None,
            'top_stocks': [item[0] for item in industry_hits[:10]],
        })
    rankings.sort(key=lambda item: item['momentum_score'], reverse=True)

    constituent_as_of_ready = bool((universe_meta or {}).get('constituent_as_of_supported'))
    institution_as_of_ready = bool(
        institution_as_of_date
        and str(institution_as_of_date).replace('-', '') <= str(as_of_date).replace('-', '')
    )
    input_ready = (
        universe_coverage >= 0.95
        and kline_coverage >= 0.95
        and listing_date_coverage >= 0.95
        and target_date_coverage >= 0.95
        and industry_mapping_coverage >= 0.95
        and constituent_as_of_ready
        and institution_filter_ready
        and institution_as_of_ready
        and high_52w_coverage >= 0.95
    )
    if not input_ready:
        for item in rankings:
            item['score_status'] = item['status']
            item['status'] = 'insufficient_data'
            item['rotation_state'] = 'unavailable'
            item['consecutive_days'] = 0
    fingerprint_rows = [
        f'{code}:{value:.8f}:{high}' for code, value, _, high in candidates
    ] + [
        f'{code}:{(industry_map or {}).get(code)}' for code, *_ in candidates
    ]
    input_fingerprint = hashlib.sha256('|'.join(sorted(fingerprint_rows)).encode()).hexdigest()
    return {
        'model_type': 'l1_momentum_mainline',
        'is_l1_model': True,
        'experimental': True,
        'as_of_date': str(as_of_date),
        'data_status': 'experimental' if input_ready else 'partial',
        'calibration_status': 'pending',
        'institution_filter_applied': institution_filter_ready,
        'input_fingerprint': input_fingerprint,
        'input_coverage': {
            'expected_stock_count': expected_count,
            'total_stock_count': observed_count,
            'eligible_stock_count': len(candidates),
            'missing_kline_count': incomplete_kline,
            'market_universe': round(universe_coverage, 4),
            'kline_20d': round(kline_coverage, 4),
            'listing_date': round(listing_date_coverage, 4),
            'target_date': round(target_date_coverage, 4),
            'industry_mapping': round(industry_mapping_coverage, 4),
            'institution_holdings': round(holdings_coverage, 4),
            'new_high_52w': round(high_52w_coverage, 4),
        },
        'quality_gates': {
            'market_universe_ready': universe_coverage >= 0.95,
            'kline_ready': kline_coverage >= 0.95,
            'listing_date_ready': listing_date_coverage >= 0.95,
            'target_date_ready': target_date_coverage >= 0.95,
            'industry_mapping_ready': industry_mapping_coverage >= 0.95,
            'constituent_as_of_ready': constituent_as_of_ready,
            'institution_holdings_ready': institution_filter_ready,
            'institution_as_of_ready': institution_as_of_ready,
            'new_high_validation_ready': high_52w_coverage >= 0.95,
            'input_ready': input_ready,
            # THS 阈值仍待历史标注集校准；输入齐全也只能运行影子模型。
            'formal_publish_ready': False,
        },
        'momentum_pool_size': len(momentum_pool),
        'rankings': rankings,
    }


def compute_and_persist_l1_shadow(as_of_date):
    """从统一数据层计算每日影子快照；不替换现有20日板块强度代理榜。"""
    from backend.data_access.data_layer import get_industry_map, get_l1_market_features

    os.makedirs(L1_SHADOW_DIR, exist_ok=True)
    normalized_date = str(as_of_date).replace('-', '')
    previous = []
    previous_as_of_date = None
    prior_files = sorted(
        filename for filename in os.listdir(L1_SHADOW_DIR)
        if filename.endswith('.json') and filename[:-5] < normalized_date
    )
    if prior_files:
        try:
            with open(os.path.join(L1_SHADOW_DIR, prior_files[-1]), encoding='utf-8') as stream:
                prior_snapshot = json.load(stream)
                previous = prior_snapshot.get('rankings', [])
                previous_as_of_date = prior_snapshot.get('as_of_date')
        except (OSError, ValueError):
            previous = []

    market_data = get_l1_market_features(normalized_date)
    result = compute_l1_industry_rankings(
        {}, get_industry_map(), normalized_date, previous=previous,
        stock_features=market_data.get('stocks', []), universe_meta=market_data,
        previous_as_of_date=previous_as_of_date,
    )
    result['source'] = market_data.get('source', '')
    result['generated_at'] = datetime.now(timezone.utc).isoformat()
    result['snapshot_version'] = 2
    config.atomic_json_dump(
        result, os.path.join(L1_SHADOW_DIR, f'{normalized_date}.json'), indent=2,
    )
    return result


def get_or_compute_l1_shadow(as_of_date, force=False):
    """读取目标日影子快照；缺失时计算。实验结果不得阻塞正式复盘。"""
    normalized_date = str(as_of_date).replace('-', '')
    snapshot_path = os.path.join(L1_SHADOW_DIR, f'{normalized_date}.json')
    if not force and os.path.isfile(snapshot_path):
        try:
            with open(snapshot_path, encoding='utf-8') as stream:
                cached = json.load(stream)
            if cached.get('data_status') != 'partial':
                return cached
            # 部分数据可能在盘后继续补齐，避免同日首个残缺快照永久固化。
            if (datetime.now().timestamp() - os.path.getmtime(snapshot_path)) < 900:
                return cached
        except (OSError, ValueError):
            pass
    return compute_and_persist_l1_shadow(normalized_date)
