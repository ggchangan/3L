"""
每日新高扫描服务

收盘后自动拉取新高股池，匹配已有逻辑标签。
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_store():
    from backend.core.logic_tracking_store import LogicTrackingStore
    return LogicTrackingStore()


def _get_matcher(tags):
    from backend.services.logic_matcher import LogicMatcher
    return LogicMatcher(tags)


def _format_code(raw_code):
    try:
        return str(int(raw_code)).zfill(6)
    except (ValueError, TypeError):
        return str(raw_code).zfill(6)


def scan_new_highs(date_str=None):
    """扫描当日新高股池

    Args:
        date_str: 日期字符串 YYYY-MM-DD，默认今天

    Returns:
        {
            'total': int,
            'matched': [...],
            'unmatched': [...],
            'scan_date': str,
        }
    """
    date_str = date_str or datetime.now().strftime('%Y-%m-%d')
    result = {
        'total': 0,
        'matched': [],
        'unmatched': [],
        'scan_date': date_str,
    }

    try:
        import akshare as ak
        import pandas as pd

        high_df = ak.stock_rank_cxg_ths()
    except Exception as e:
        result['error'] = f'新高数据拉取失败: {e}'
        return result

    if high_df is None or high_df.empty:
        return result

    store = _get_store()
    tags = store.get_tags()
    if not tags:
        result['total'] = len(high_df)
        for _, row in high_df.iterrows():
            result['unmatched'].append({
                'code': _format_code(row.get('股票代码', '')),
                'name': row.get('股票简称', ''),
                'reason': '暂无逻辑标签',
            })
        return result

    matcher = _get_matcher(tags)

    for _, row in high_df.iterrows():
        code = _format_code(row.get('股票代码', ''))
        name = row.get('股票简称', '')
        change_pct = float(row.get('涨跌幅', 0))

        # 新高扫描没有直接的行业字段，走代码+名称匹配
        matches = matcher.match_all(code, name, '')

        stock_info = {
            'code': code,
            'name': name,
            'change_pct': change_pct,
        }

        if matches:
            stock_info['matched_tags'] = matches
            result['matched'].append(stock_info)

            try:
                _record_high_verify(store, code, name, matches, date_str, change_pct)
            except Exception:
                pass
        else:
            result['unmatched'].append(stock_info)

    result['total'] = len(high_df)
    return result


def _record_high_verify(store, code, name, matched_tags, date_str, change_pct):
    """记录新高验证事件（新高匹配即+3分）"""
    from datetime import datetime as dt
    import json, shutil

    entry_id = f'high-verify-{code}-{date_str}'
    entry = {
        'id': entry_id,
        'source_type': 'daily_scan',
        'source_name': '新高扫描',
        'title': f'{name}({code}) 创历史新高',
        'summary': f'{name} 创历史新高(涨幅+{change_pct}%)，逻辑验证加强',
        'industries': [m.get('tag_name', '') for m in matched_tags],
        'companies': [code],
        'logic_tags': [m['tag_id'] for m in matched_tags],
        'fed_at': date_str,
        'verify': {
            '3d_return': 0.0, '5d_return': 0.0, '10d_return': 0.0,
            'sector_rank_before': None, 'sector_rank_after': None,
            'buy_signal_count': 0, 'score': 'confirmed',
            'verified_at': date_str,
        },
    }
    store.add_entry(entry)

    # 新高信号强，拉高verify_rate
    all_data = store.get_all()
    for tag in all_data.get('tags', []):
        if tag['id'] in [m['tag_id'] for m in matched_tags]:
            current = tag.get('verify_rate', 0) or 0
            count = tag.get('event_count', 0) or 0
            if count > 0:
                tag['verify_rate'] = round(
                    (current * (count - 1) + 0.8) / count, 2)

    all_data['updated_at'] = dt.now().strftime('%Y-%m-%d %H:%M')
    with open(tmp := store._path + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    shutil.move(tmp, store._path)
