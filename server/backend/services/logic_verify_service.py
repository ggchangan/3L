"""
走势验证服务

新事件投喂后自动运行，查关联个股3/5/10日涨跌幅。
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_store():
    from backend.core.logic_tracking_store import LogicTrackingStore
    return LogicTrackingStore()


def _get_stock_klines(code):
    """从 all_stocks_60d.json 获取个股K线数据"""
    from backend import config
    path = config.ALL_STOCKS_PATH
    if not os.path.isfile(path):
        return None

    with open(path) as f:
        data = json.load(f)

    # 格式：{last_updated, stocks: {code: {name, klines}}}
    if isinstance(data, dict):
        stocks = data.get('stocks', {})
        for key, stock in stocks.items():
            if isinstance(stock, dict):
                klines = stock.get('klines', [])
                if key == code:
                    return klines
                # 也可能 klines 中的某条有 code 字段
                if any(k.get('code') == code for k in klines):
                    return klines
        return None

    return None


def _get_close_on_date(klines, date_str):
    """获取指定日期（YYYY-MM-DD）的收盘价"""
    date_compact = date_str.replace('-', '')
    for k in klines:
        kdate = k.get('date', '')
        if kdate == date_compact or kdate == date_str:
            try:
                return float(k.get('close', 0))
            except (ValueError, TypeError):
                return 0
    return None


def _count_trading_days(klines, from_date, days):
    """从from_date开始，往后数days个交易日的收盘价

    Returns: 第days个交易日的收盘价，或None
    """
    date_compact = from_date.replace('-', '')
    dates = sorted(set(k.get('date', '') for k in klines))
    # 找到起始日期的位置
    start_idx = None
    for i, d in enumerate(dates):
        if d == date_compact or d == from_date:
            start_idx = i
            break

    if start_idx is None:
        return None

    target_idx = start_idx + days
    if target_idx >= len(dates):
        return None

    target_date = dates[target_idx]
    return _get_close_on_date(klines, target_date)


def verify_entry(code, name, event_date_str):
    """验证一条资料条目

    Args:
        code: 股票代码
        name: 股票名称
        event_date_str: 事件日期 YYYY-MM-DD

    Returns: {
        '3d_return': float,  # 事件后3交易日涨跌幅%
        '5d_return': float,  # 事件后5交易日涨跌幅%
        '10d_return': float, # 事件后10交易日涨跌幅%
    } or None (数据不足)
    """
    klines = _get_stock_klines(code)
    if not klines:
        return None

    # 获取事件日的收盘价
    event_close = _get_close_on_date(klines, event_date_str)
    if event_close is None:
        return None

    result = {}
    for days, key in [(3, '3d_return'), (5, '5d_return'), (10, '10d_return')]:
        target_close = _count_trading_days(klines, event_date_str, days)
        if target_close and target_close > 0:
            result[key] = round((target_close - event_close) / event_close * 100, 2)
        else:
            result[key] = 0.0

    return result


def verify_unverified_entries():
    """批量验证所有未验证的条目

    在每次资料投喂保存后自动调用。

    Returns: 验证的条目数
    """
    store = _get_store()
    entries = store.get_entries()
    count = 0

    for entry in entries:
        verify = entry.get('verify', {})
        if verify and verify.get('verified_at'):
            continue  # 已验证，跳过

        companies = entry.get('companies', [])
        if not companies:
            continue

        event_date = entry.get('fed_at', '')[:10]
        if not event_date:
            continue

        # 取第一个关联公司做验证
        code = companies[0]
        result = verify_entry(code, '', event_date)
        if result is None:
            continue

        # 更新验证结果
        if verify is None:
            verify = {}
            entry['verify'] = verify
        verify['3d_return'] = result.get('3d_return', 0)
        verify['5d_return'] = result.get('5d_return', 0)
        verify['10d_return'] = result.get('10d_return', 0)
        verify['verified_at'] = datetime.now().strftime('%Y-%m-%d')

        # 打分
        score = 'confirmed'
        avg_return = (result.get('3d_return', 0) + result.get('5d_return', 0) + result.get('10d_return', 0)) / 3
        if avg_return < -3:
            score = 'diverged'
        elif avg_return < 0:
            score = 'neutral'
        elif avg_return > 0:
            score = 'confirmed'
        verify['score'] = score

        count += 1

    if count > 0:
        # 触发保存
        all_data = store.get_all()
        all_data['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        import shutil
        with open(tmp := store._path + '.tmp', 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp, store._path)

    return count
