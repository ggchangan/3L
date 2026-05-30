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


def _filter_plans_by_date(plans: list, start_date: str = None, end_date: str = None) -> list:
    """按日期范围筛选计划，最多30天
    
    Args:
        plans: 完整计划列表
        start_date: 起始日期 'YYYY-MM-DD' 或 None（不限）
        end_date: 结束日期 'YYYY-MM-DD' 或 None（不限）
    Returns:
        筛选后的计划列表
    """
    if not start_date and not end_date:
        # 默认最近30天
        end = datetime.now()
        start = end - timedelta(days=30)
        start_date = start.strftime('%Y-%m-%d')
        end_date = end.strftime('%Y-%m-%d')
    
    # 后端兜底：最多30天
    if start_date and end_date:
        sd = datetime.strptime(start_date, '%Y-%m-%d')
        ed = datetime.strptime(end_date, '%Y-%m-%d')
        if (ed - sd).days > 30:
            start_date = (ed - timedelta(days=30)).strftime('%Y-%m-%d')
    
    filtered = []
    for p in plans:
        pd_str = p.get('plan_date', '')
        if not pd_str:
            continue
        # plan_date 可能是 '2026-05-28' 或 '20260528'
        pd_clean = pd_str.replace('-', '')
        if start_date:
            sd_clean = start_date.replace('-', '')
            if pd_clean < sd_clean:
                continue
        if end_date:
            ed_clean = end_date.replace('-', '')
            if pd_clean > ed_clean:
                continue
        filtered.append(p)
    return filtered


def _compute_summary(plans: list) -> dict:
    """从计划列表计算统计摘要"""
    buy_sell = [p for p in plans if p['type'] in ('buy', 'sell') and p['result'] in ('success', 'failure', 'flat')]
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
    
    # 按类型分组
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
        'pending': len([p for p in plans if p['result'] == 'pending']),
        'no_data': len([p for p in plans if p['result'] == 'no_data']),
        'success_rate': round(success_count / total * 100, 1) if total > 0 else 0,
        'avg_gain_pct': avg_gain,
        'avg_loss_pct': avg_loss,
        'best_gain': best,
        'worst_loss': worst,
        'win_loss_ratio': wl_ratio,
    }
    
    return summary, by_condition, by_type


def _generate_suggestions(plans: list, summary: dict, by_condition: dict) -> list:
    """根据追踪数据生成自动建议"""
    suggestions = []
    
    # 只分析有结果的 buy/sell 计划
    buy_sell = [p for p in plans if p['type'] in ('buy', 'sell') and p['result'] in ('success', 'failure')]
    if len(buy_sell) < 3:
        return suggestions  # 数据太少不生成建议
    
    overall_rate = summary.get('success_rate', 0)
    
    # 1. 条件成功率偏低
    for cat, stats in by_condition.items():
        if cat == '未分类':
            continue
        if stats['total'] >= 3:
            rate = round(stats['success'] / stats['total'] * 100, 1) if stats['total'] > 0 else 0
            if rate < 50:
                suggestions.append({
                    'type': 'warning',
                    'dimension': 'condition',
                    'category': cat,
                    'rate_current': rate,
                    'rate_overall': overall_rate,
                    'count': stats['total'],
                    'message': f'条件「{cat}」{stats["total"]}次仅{rate}%成功率（整体{overall_rate}%），建议检查该条件筛选逻辑',
                })
            elif rate > 70 and stats['total'] >= 5:
                suggestions.append({
                    'type': 'best',
                    'dimension': 'condition',
                    'category': cat,
                    'rate_current': rate,
                    'rate_overall': overall_rate,
                    'count': stats['total'],
                    'message': f'条件「{cat}」{stats["total"]}次{rate}%成功率，表现优秀，继续保持',
                })
    
    # 2. 止损偏紧分析
    with_stop = [p for p in buy_sell if p.get('stop_loss') is not None]
    if len(with_stop) >= 5:
        hit = sum(1 for p in with_stop if p.get('hit_stop_loss'))
        hit_rate = hit / len(with_stop) * 100
        if hit_rate > 25:
            suggestions.append({
                'type': 'warning',
                'dimension': 'stop_loss',
                'category': '止损设置',
                'rate_current': round(hit_rate, 1),
                'rate_overall': 0,
                'count': len(with_stop),
                'message': f'止损偏紧：{len(with_stop)}笔中{hit}笔盘中止损被触发（{round(hit_rate,1)}%），建议适当放宽止损幅度',
            })
    
    # 3. 个股频繁失败
    stock_stats = {}
    for p in buy_sell:
        stock = p.get('stock', '')
        code = p.get('code', '')
        key = f'{stock}({code})' if code else stock
        if key not in stock_stats:
            stock_stats[key] = {'total': 0, 'fail': 0}
        stock_stats[key]['total'] += 1
        if p['result'] == 'failure':
            stock_stats[key]['fail'] += 1
    
    for stock, st in stock_stats.items():
        if st['total'] >= 3 and st['fail'] >= 3:
            suggestions.append({
                'type': 'warning',
                'dimension': 'stock',
                'category': stock,
                'rate_current': round(st['fail'] / st['total'] * 100, 1),
                'rate_overall': 0,
                'count': st['total'],
                'message': f'{stock} {st["total"]}次计划中{st["fail"]}次失败，注意识别该股买点有效性',
            })
    
    # 4. 类型对比分析
    by_type_analysis = {}
    for p in buy_sell:
        t = p.get('type', '')
        if t not in by_type_analysis:
            by_type_analysis[t] = {'total': 0, 'success': 0}
        by_type_analysis[t]['total'] += 1
        if p['result'] == 'success':
            by_type_analysis[t]['success'] += 1
    
    for t, st in by_type_analysis.items():
        if st['total'] >= 5:
            rate = round(st['success'] / st['total'] * 100, 1)
            label = '买入' if t == 'buy' else '卖出'
            if rate < 50:
                suggestions.append({
                    'type': 'warning',
                    'dimension': 'type',
                    'category': label,
                    'rate_current': rate,
                    'rate_overall': overall_rate,
                    'count': st['total'],
                    'message': f'{label}计划{st["total"]}次仅{rate}%成功率，低于整体（{overall_rate}%），需重点优化',
                })
            elif rate > 70:
                suggestions.append({
                    'type': 'best',
                    'dimension': 'type',
                    'category': label,
                    'rate_current': rate,
                    'rate_overall': overall_rate,
                    'count': st['total'],
                    'message': f'{label}计划{st["total"]}次{rate}%成功率，表现稳定',
                })
    
    # 按严重程度排序：warning > best > info
    type_order = {'warning': 0, 'best': 1, 'info': 2}
    suggestions.sort(key=lambda x: type_order.get(x['type'], 9))
    
    return suggestions


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
    summary, by_condition, by_type = _compute_summary(all_plans)
    suggestions = _generate_suggestions(all_plans, summary, by_condition)
    
    result = {
        'plans': all_plans,
        'summary': summary,
        'by_condition': by_condition,
        'by_type': by_type,
        'suggestions': suggestions,
        'last_updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    }
    
    # 持久化缓存
    os.makedirs(os.path.dirname(PLAN_TRACKING_PATH), exist_ok=True)
    with open(PLAN_TRACKING_PATH, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result


def get_tracking(start_date: str = None, end_date: str = None) -> dict:
    """获取追踪结果（优先缓存），支持日期范围筛选
    
    Args:
        start_date: 起始日期 'YYYY-MM-DD'，默认30天前
        end_date: 结束日期 'YYYY-MM-DD'，默认今天
    Returns:
        筛选后的追踪结果（含 suggestions）
    """
    if os.path.exists(PLAN_TRACKING_PATH):
        try:
            with open(PLAN_TRACKING_PATH) as f:
                data = json.load(f)
        except Exception:
            data = compute_tracking()
    else:
        data = compute_tracking()
    
    # 日期筛选
    filtered_plans = _filter_plans_by_date(data.get('plans', []), start_date, end_date)
    
    # 重算摘要和建议
    summary, by_condition, by_type = _compute_summary(filtered_plans)
    suggestions = _generate_suggestions(filtered_plans, summary, by_condition)
    
    data['plans'] = filtered_plans
    data['summary'] = summary
    data['by_condition'] = by_condition
    data['by_type'] = by_type
    data['suggestions'] = suggestions
    data['last_updated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    
    return data


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
        # 重算摘要和建议
        summary, by_condition, by_type = _compute_summary(plans)
        suggestions = _generate_suggestions(plans, summary, by_condition)
        data['summary'] = summary
        data['by_condition'] = by_condition
        data['by_type'] = by_type
        data['suggestions'] = suggestions
        os.makedirs(os.path.dirname(PLAN_TRACKING_PATH), exist_ok=True)
        with open(PLAN_TRACKING_PATH, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return {'success': found}
