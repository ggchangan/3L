"""
每日涨停扫描服务

收盘后自动拉取涨停板池，匹配已有逻辑标签。
"""
import os
import sys
import traceback
from datetime import datetime

# 确保可导入项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_store():
    """获取存储实例（延迟加载避免循环引用）"""
    from backend.core.logic_tracking_store import LogicTrackingStore
    return LogicTrackingStore()


def _get_matcher(tags):
    """创建匹配器"""
    from backend.services.logic_matcher import LogicMatcher
    return LogicMatcher(tags)


def _format_code(raw_code):
    """格式化股票代码为6位字符串"""
    try:
        return str(int(raw_code)).zfill(6)
    except (ValueError, TypeError):
        return str(raw_code).zfill(6)


def scan_zt_pool(date_str=None):
    """扫描当日涨停板池

    Args:
        date_str: 日期字符串 YYYY-MM-DD，默认今天

    Returns:
        {
            'total': int,          # 涨停总数
            'matched': [...],      # 匹配到的涨停股
            'unmatched': [...],    # 未匹配的涨停股
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

        # 格式化日期为YYYYMMDD
        api_date = date_str.replace('-', '')
        zt_df = ak.stock_zt_pool_em(date=api_date)
    except Exception as e:
        result['error'] = f'涨停数据拉取失败: {e}'
        return result

    if zt_df is None or zt_df.empty:
        return result

    store = _get_store()
    tags = store.get_tags()
    if not tags:
        result['total'] = len(zt_df)
        for _, row in zt_df.iterrows():
            result['unmatched'].append({
                'code': _format_code(row.get('代码', '')),
                'name': row.get('名称', ''),
                'reason': '暂无逻辑标签',
            })
        return result

    matcher = _get_matcher(tags)

    for _, row in zt_df.iterrows():
        code = _format_code(row.get('代码', ''))
        name = row.get('名称', '')
        industry = row.get('所属行业', '')
        limit_up_count = int(row.get('连板数', 1))
        first_time = str(row.get('首次封板时间', ''))

        # 匹配逻辑标签
        matches = matcher.match_all(code, name, industry)

        stock_info = {
            'code': code,
            'name': name,
            'industry': industry,
            'limit_up_count': limit_up_count,
            'first_seal_time': first_time,
        }

        if matches:
            stock_info['matched_tags'] = matches
            result['matched'].append(stock_info)

            # 更新验证事件
            try:
                _record_verify_event(store, code, name, matches,
                                     limit_up_count, date_str)
            except Exception:
                pass
        else:
            result['unmatched'].append(stock_info)

    result['total'] = len(zt_df)
    return result


def _record_verify_event(store, code, name, matched_tags, limit_up_count, date_str):
    """记录涨停匹配到验证事件

    更新逻辑标签的健康分：首次涨停+1，连板+2，板块联动+3
    """
    from datetime import datetime as dt

    # 计算权重
    weight = 1
    if limit_up_count >= 3:
        weight = 3
    elif limit_up_count >= 2:
        weight = 2

    entry_id = f'zt-verify-{code}-{date_str}'
    entry = {
        'id': entry_id,
        'source_type': 'daily_scan',
        'source_name': '涨停扫描',
        'title': f'{name}({code}) 涨停',
        'summary': f'{name} 涨停(连板{limit_up_count}板)，关联逻辑验证通过',
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

    # 手动更新关联标签的verify_rate
    all_data = store.get_all()
    for tag in all_data.get('tags', []):
        if tag['id'] in [m['tag_id'] for m in matched_tags]:
            current = tag.get('verify_rate', 0) or 0
            count = tag.get('event_count', 0) or 0
            if count > 0:
                tag['verify_rate'] = round(
                    (current * (count - 1) + 1) / count, 2)
    store.add_tag  # Trigger save by calling a write op
    # Actually just use internal save
    import json, shutil
    tmp = store._path + '.tmp'
    all_data['updated_at'] = dt.now().strftime('%Y-%m-%d %H:%M')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    shutil.move(tmp, store._path)
