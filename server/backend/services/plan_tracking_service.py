"""
操作计划追踪服务

扫描工作台历史计划，自动计算次日表现（涨跌幅/成功/失败），
缓存结果到 plan_tracking.json。
"""

import json, os, re
from datetime import datetime, timedelta
from backend.config import DATA_DIR
from backend.core.data_layer import get_all_stocks, get_stock_klines

PLAN_TRACKING_PATH = os.path.join(DATA_DIR, 'private', 'plan_tracking.json')
WORKBENCH_DIR = os.path.join(DATA_DIR, 'private', 'workbench')

_SUCCESS_THRESHOLD = 0.5  # 涨超过0.5%算成功
_FAILURE_THRESHOLD = -0.5  # 跌超过0.5%算失败


def _extract_code(stock_field: str) -> str:
    """从 '杭齿前进(601177)' 或 '601177' 提取股票代码"""
    if not stock_field:
        return ''
    m = re.search(r'\((\d{6})\)', stock_field)
    if m:
        return m.group(1)
    m = re.search(r'\d{6}', stock_field)
    if m:
        return m.group(0)
    # 尝试通过名字查 all_a_stocks
    name = stock_field.strip()
    aas_path = os.path.join(DATA_DIR, 'all_a_stocks.json')
    if os.path.exists(aas_path):
        try:
            with open(aas_path) as f:
                name_map = json.load(f)
            for code, n in name_map.items():
                if n == name:
                    return code
        except Exception:
            pass
    return ''


def _get_all_workbench_dates() -> list:
    """返回所有工作台文件日期（升序）"""
    if not os.path.isdir(WORKBENCH_DIR):
        return []
    return sorted(
        f.replace('.json', '') for f in os.listdir(WORKBENCH_DIR)
        if f.endswith('.json') and len(f.replace('.json', '')) == 10
    )


def _get_kline_dict(code: str) -> list:
    """获取个股K线 [{date, close, open, high, low}]，date格式YYYYMMDD"""
    stocks = get_all_stocks()
    klines = get_stock_klines(code, stocks=stocks)
    if not klines or not isinstance(klines, list):
        return []
    return klines


def _find_next_trading_day(klines: list, plan_date_str: str) -> dict:
    """在K线列表中找到计划日期之后的下一个交易日
    
    klines: [{date: '20260528', close: xx}, ...]，已按日期升序
    plan_date_str: '2026-05-28'
    返回: 该交易日的kline记录，或 None
    """
    plan_compact = plan_date_str.replace('-', '')
    found_plan = False
    for k in klines:
        date_str = str(k.get('date', ''))
        if date_str == plan_compact:
            found_plan = True
            continue
        if found_plan and date_str > plan_compact:
            return k
    return None


def _categorize_condition(condition: str) -> tuple:
    """将条件分为大类+细类，如 '上涨趋势·上行' → ('上涨趋势','上行')"""
    if not condition:
        return ('', '')
    parts = condition.split('·')
    cat = parts[0].strip() if len(parts) > 0 else condition
    detail = parts[1].strip() if len(parts) > 1 else ''
    return (cat, detail)


def compute_tracking(force=False) -> dict:
    """扫描所有工作台计划，计算追踪结果
    
    force=True: 忽略缓存，从头重新计算
    返回: 追踪结果字典
    """
    # 读取现有缓存
    cache = {}
    if not force and os.path.exists(PLAN_TRACKING_PATH):
        try:
            with open(PLAN_TRACKING_PATH) as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    
    existing_plans = cache.get('plans', [])
    # 用 plan_date + type + stock 作为唯一标识
    seen_keys = set()
    for p in existing_plans:
        key = f"{p.get('plan_date')}|{p.get('type')}|{p.get('stock')}"
        seen_keys.add(key)
    
    dates = _get_all_workbench_dates()
    new_plans = []
    
    for date_str in dates:
        fp = os.path.join(WORKBENCH_DIR, f'{date_str}.json')
        if not os.path.exists(fp):
            continue
        with open(fp) as f:
            wb = json.load(f)
        plan = wb.get('plan', {})
        for cat in ['buy', 'sell']:
            items = plan.get(cat, [])
            for i, item in enumerate(items):
                stock_field = item.get('stock', '')
                if not stock_field:
                    continue
                # 提取股票名（去掉括号部分）
                stock_name = re.sub(r'\(.*\)', '', stock_field).strip() or stock_field
                code = _extract_code(stock_field)
                key = f"{date_str}|{cat}|{stock_name}"
                
                if key in seen_keys:
                    continue  # 已存在缓存
                
                condition = item.get('condition', '')
                cat_big, cat_detail = _categorize_condition(condition)
                stop_loss = item.get('stop_loss')
                stop_loss_pct = item.get('stop_loss_pct')
                
                entry = {
                    'plan_date': date_str,
                    'type': cat,
                    'stock': stock_name,
                    'code': code,
                    'condition': condition,
                    'condition_category': cat_big,
                    'condition_detail': cat_detail,
                    'stop_loss': stop_loss,
                    'stop_loss_pct': stop_loss_pct,
                    'plan_close': None,
                    'next_date': None,
                    'next_open': None,
                    'next_close': None,
                    'next_high': None,
                    'next_low': None,
                    'change_pct': None,
                    'max_gain': None,
                    'max_loss': None,
                    'hit_stop_loss': False,
                    'result': 'no_data',
                    'executed': None,
                    'user_note': '',
                }
                
                if not code:
                    entry['result'] = 'no_data'
                else:
                    klines = _get_kline_dict(code)
                    if not klines:
                        entry['result'] = 'no_data'
                    else:
                        # 找计划当天的收盘价
                        plan_compact = date_str.replace('-', '')
                        plan_kline = None
                        for k in klines:
                            if str(k.get('date', '')) == plan_compact:
                                plan_kline = k
                                break
                        if plan_kline:
                            plan_close = float(plan_kline.get('close', 0))
                            entry['plan_close'] = plan_close
                            
                            # 找下一个交易日
                            next_k = _find_next_trading_day(klines, date_str)
                            if next_k:
                                nc = float(next_k.get('close', 0))
                                nh = float(next_k.get('high', 0))
                                nl_ = float(next_k.get('low', 0))
                                no_ = float(next_k.get('open', 0))
                                
                                entry['next_date'] = str(next_k.get('date', ''))
                                entry['next_open'] = no_
                                entry['next_close'] = nc
                                entry['next_high'] = nh
                                entry['next_low'] = nl_
                                
                                change = (nc - plan_close) / plan_close * 100
                                entry['change_pct'] = round(change, 2)
                                entry['max_gain'] = round((nh - plan_close) / plan_close * 100, 2)
                                entry['max_loss'] = round((nl_ - plan_close) / plan_close * 100, 2)
                                
                                # 判定结果
                                if cat == 'sell':
                                    # 卖出：跌算成功
                                    if change <= _FAILURE_THRESHOLD:
                                        entry['result'] = 'success'
                                    elif change >= _SUCCESS_THRESHOLD:
                                        entry['result'] = 'failure'
                                    else:
                                        entry['result'] = 'flat'
                                else:
                                    # 买入：涨算成功
                                    if change >= _SUCCESS_THRESHOLD:
                                        entry['result'] = 'success'
                                    elif change <= _FAILURE_THRESHOLD:
                                        entry['result'] = 'failure'
                                    else:
                                        entry['result'] = 'flat'
                                
                                # 检查是否触及止损
                                if stop_loss is not None and nl_ < stop_loss:
                                    entry['hit_stop_loss'] = True
                            else:
                                entry['result'] = 'pending'
                        else:
                            entry['result'] = 'pending'
                
                new_plans.append(entry)
                seen_keys.add(key)
        
        # watch 计划也加入（但不参与统计）
        for item in plan.get('watch', []):
            stock_field = item.get('stock', '')
            if not stock_field:
                continue
            stock_name = re.sub(r'\(.*\)', '', stock_field).strip() or stock_field
            code = _extract_code(stock_field)
            key = f"{date_str}|watch|{stock_name}"
            if key in seen_keys:
                continue
            entry = {
                'plan_date': date_str,
                'type': 'watch',
                'stock': stock_name,
                'code': code,
                'condition': '',
                'condition_category': '',
                'condition_detail': '',
                'stop_loss': None,
                'stop_loss_pct': None,
                'plan_close': None,
                'next_date': None,
                'next_open': None,
                'next_close': None,
                'next_high': None,
                'next_low': None,
                'change_pct': None,
                'max_gain': None,
                'max_loss': None,
                'hit_stop_loss': False,
                'result': 'no_data',
                'executed': None,
                'user_note': '',
            }
            if code:
                klines = _get_kline_dict(code)
                if klines:
                    plan_compact = date_str.replace('-', '')
                    plan_kline = None
                    for k in klines:
                        if str(k.get('date', '')) == plan_compact:
                            plan_kline = k
                            break
                    if plan_kline:
                        plan_close = float(plan_kline.get('close', 0))
                        entry['plan_close'] = plan_close
                        next_k = _find_next_trading_day(klines, date_str)
                        if next_k:
                            nc = float(next_k.get('close', 0))
                            nh = float(next_k.get('high', 0))
                            nl_ = float(next_k.get('low', 0))
                            entry['next_date'] = str(next_k.get('date', ''))
                            entry['next_close'] = nc
                            entry['next_high'] = nh
                            entry['next_low'] = nl_
                            change = (nc - plan_close) / plan_close * 100
                            entry['change_pct'] = round(change, 2)
                            entry['result'] = 'flat'  # watch不计success/failure
            seen_keys.add(key)
            new_plans.append(entry)
    
    all_plans = existing_plans + new_plans
    
    # 计算统计摘要
    buy_sell = [p for p in all_plans if p['type'] in ('buy', 'sell') and p['result'] in ('success', 'failure', 'flat')]
    success_list = [p for p in buy_sell if p['result'] == 'success']
    failure_list = [p for p in buy_sell if p['result'] == 'failure']
    flat_list = [p for p in buy_sell if p['result'] == 'flat']
    
    total = len(buy_sell)
    success_count = len(success_list)
    failure_count = len(failure_list)
    
    avg_gain = round(sum(p['change_pct'] for p in success_list) / success_count, 2) if success_count > 0 else 0
    avg_loss = round(sum(p['change_pct'] for p in failure_list) / failure_count, 2) if failure_count > 0 else 0
    best = max((p['change_pct'] for p in buy_sell if p['change_pct'] is not None), default=0)
    worst = min((p['change_pct'] for p in buy_sell if p['change_pct'] is not None), default=0)
    wl_ratio = round(avg_gain / abs(avg_loss), 2) if avg_loss != 0 else 0
    
    # 按条件大类分组
    by_condition = {}
    for p in buy_sell:
        cat = p.get('condition_category', '') or '未分类'
        if cat not in by_condition:
            by_condition[cat] = {'total': 0, 'success': 0, 'failure': 0, 'flat': 0}
        by_condition[cat]['total'] += 1
        if p['result'] == 'success':
            by_condition[cat]['success'] += 1
        elif p['result'] == 'failure':
            by_condition[cat]['failure'] += 1
        else:
            by_condition[cat]['flat'] += 1
    
    # 按类型(买入/卖出)分组
    by_type = {'buy': {'total': 0, 'success': 0, 'failure': 0, 'flat': 0},
               'sell': {'total': 0, 'success': 0, 'failure': 0, 'flat': 0}}
    for p in buy_sell:
        t = p['type']
        if t in by_type:
            by_type[t]['total'] += 1
            if p['result'] == 'success':
                by_type[t]['success'] += 1
            elif p['result'] == 'failure':
                by_type[t]['failure'] += 1
            else:
                by_type[t]['flat'] += 1
    
    summary = {
        'total_plans': total,
        'success': success_count,
        'failure': failure_count,
        'flat': len(flat_list),
        'pending': len([p for p in all_plans if p['result'] == 'pending']),
        'no_data': len([p for p in all_plans if p['result'] == 'no_data']),
        'success_rate': round(success_count / total * 100, 1) if total > 0 else 0,
        'avg_gain_pct': avg_gain,
        'avg_loss_pct': avg_loss,
        'best_gain': best,
        'worst_loss': worst,
        'win_loss_ratio': wl_ratio,
    }
    
    result = {
        'plans': all_plans,
        'summary': summary,
        'by_condition': by_condition,
        'by_type': by_type,
        'last_updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    }
    
    # 持久化缓存
    os.makedirs(os.path.dirname(PLAN_TRACKING_PATH), exist_ok=True)
    with open(PLAN_TRACKING_PATH, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result


def get_tracking() -> dict:
    """获取追踪结果（优先缓存）"""
    if os.path.exists(PLAN_TRACKING_PATH):
        try:
            with open(PLAN_TRACKING_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return compute_tracking()


def annotate_plan(plan_date: str, type_: str, stock: str, executed: bool = None, user_note: str = '') -> dict:
    """标记计划的执行状态和备注"""
    data = get_tracking()
    plans = data.get('plans', [])
    found = False
    for p in plans:
        if p.get('plan_date') == plan_date and p.get('type') == type_ and p.get('stock') == stock:
            if executed is not None:
                p['executed'] = executed
            if user_note:
                p['user_note'] = user_note
            found = True
            break
    if found:
        data['last_updated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        # 重算摘要
        buy_sell = [p for p in plans if p['type'] in ('buy', 'sell') and p['result'] in ('success', 'failure', 'flat')]
        success_list = [p for p in buy_sell if p['result'] == 'success']
        failure_list = [p for p in buy_sell if p['result'] == 'failure']
        data['summary']['success'] = len(success_list)
        data['summary']['failure'] = len(failure_list)
        data['summary']['success_rate'] = round(len(success_list) / len(buy_sell) * 100, 1) if buy_sell else 0
        os.makedirs(os.path.dirname(PLAN_TRACKING_PATH), exist_ok=True)
        with open(PLAN_TRACKING_PATH, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return {'success': found}
