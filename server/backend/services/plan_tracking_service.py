"""
操作计划追踪服务 v2

数据源: review 实时计算的 trading_plan (holdings_action + buy_priority)
存储: SQLite（零外部依赖，适合多维度统计）
"""
import json, os, re, sqlite3
from datetime import datetime, timedelta
from backend.config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, 'private', 'plan_tracking.db')

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS plan_records (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT    NOT NULL,
    code            TEXT    NOT NULL,
    name            TEXT,
    source          TEXT,
    action          TEXT,
    reason          TEXT,
    structure       TEXT,
    stage           TEXT,
    buy_point       TEXT,
    is_main         INTEGER DEFAULT 0,
    priority        TEXT,
    stop_loss       REAL,
    stop_loss_pct   REAL,
    plan_close      REAL,
    next_date       TEXT,
    next_open       REAL,
    next_close      REAL,
    next_high       REAL,
    next_low        REAL,
    change_pct      REAL,
    max_gain        REAL,
    max_loss        REAL,
    hit_stop_loss   INTEGER DEFAULT 0,
    result          TEXT,
    executed        INTEGER,
    user_note       TEXT DEFAULT '',
    created_at      TEXT,
    updated_at      TEXT,
    UNIQUE(date, code)
);
CREATE INDEX IF NOT EXISTS idx_records_date      ON plan_records(date);
CREATE INDEX IF NOT EXISTS idx_records_result    ON plan_records(result);
CREATE INDEX IF NOT EXISTS idx_records_source    ON plan_records(source);
CREATE INDEX IF NOT EXISTS idx_records_buy_point ON plan_records(buy_point);
CREATE INDEX IF NOT EXISTS idx_records_structure ON plan_records(structure, stage);
CREATE INDEX IF NOT EXISTS idx_records_is_main   ON plan_records(is_main);
"""


# ═══════════════════════════════════════════════════════════════
# 数据库初始化
# ═══════════════════════════════════════════════════════════════

def _init_db(db_path=None):
    """初始化数据库表结构（幂等）"""
    if db_path is None:
        db_path = DB_PATH
    if db_path != ':memory:':
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA_SQL)
        # 兼容旧表：追加新列（幂等）
        for col, col_type in [('exit_date', 'TEXT'), ('exit_price', 'REAL'),
                               ('exit_reason', 'TEXT'), ('holding_days', 'INTEGER'),
                               ('max_price', 'REAL'), ('min_price', 'REAL')]:
            try:
                conn.execute(f'ALTER TABLE plan_records ADD COLUMN {col} {col_type}')
            except sqlite3.OperationalError:
                pass  # 列已存在
        conn.commit()
    finally:
        conn.close()


def _get_conn(db_path=None):
    """获取数据库连接（Row 工厂模式）"""
    if db_path is None:
        db_path = DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ═══════════════════════════════════════════════════════════════
# 从 trading_plan 提取计划
# ═══════════════════════════════════════════════════════════════

def _parse_stock_name_code(stock_field: str) -> tuple:
    """从 '杭齿前进(601177)' 提取 (name, code)"""
    if not stock_field:
        return ('', '')
    m = re.match(r'(.+)\((\d{6})\)', stock_field)
    if m:
        return (m.group(1).strip(), m.group(2))
    # 只有代码
    m = re.search(r'\d{6}', stock_field)
    if m:
        return ('', m.group(0))
    return (stock_field.strip(), '')


def _parse_reason(reason: str) -> tuple:
    """'上涨趋势·上行' → ('上涨趋势', '上行')"""
    if not reason:
        return ('', '')
    parts = reason.split('·')
    return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else '')


def extract_plans_from_trading_plan(trading_plan: dict, date_str: str) -> list:
    """从复盘 trading_plan 提取所有个股操作计划

    Args:
        trading_plan: compute_review_real_time 返回的 trading_plan dict
        date_str: 计划日期 'YYYY-MM-DD'

    Returns:
        [{
            'date', 'code', 'name', 'source',
            'action', 'reason', 'structure', 'stage',
            'buy_point', 'is_main', 'priority',
            'stop_loss', 'stop_loss_pct',
            'plan_close', 'result': 'pending',
        }]
    """
    plans = []
    if not trading_plan:
        return plans

    # 1. 持仓操作
    for ha in trading_plan.get('holdings_action', []):
        stock_field = ha.get('stock', '')
        name, code = _parse_stock_name_code(stock_field)
        if not code:
            continue
        action = ha.get('action', '')
        reason = ha.get('reason', '')
        structure, stage = _parse_reason(reason)
        plans.append({
            'date': date_str,
            'code': code,
            'name': name,
            'source': 'holdings_action',
            'action': action,
            'reason': reason,
            'structure': structure,
            'stage': stage,
            'buy_point': None,
            'is_main': 0,
            'priority': ha.get('priority', ''),
            'stop_loss': ha.get('stop_loss'),
            'stop_loss_pct': ha.get('stop_loss_pct'),
            'plan_close': None,
            'result': 'pending',
        })

    # 2. 关注买入
    for bp in trading_plan.get('buy_priority', []):
        code = bp.get('code', '')
        if not code:
            continue
        structure = bp.get('structure', '')
        stage = bp.get('stage', '')
        plans.append({
            'date': date_str,
            'code': code,
            'name': bp.get('name', ''),
            'source': 'buy_priority',
            'action': '',
            'reason': f"{structure}·{stage}" if structure and stage else structure,
            'structure': structure,
            'stage': stage,
            'buy_point': bp.get('buy_point', ''),
            'is_main': 1 if bp.get('is_main') else 0,
            'priority': str(bp.get('priority', '')),
            'stop_loss': bp.get('stop_loss'),
            'stop_loss_pct': bp.get('stop_loss_pct'),
            'plan_close': None,
            'result': 'pending',
        })

    return plans


# ═══════════════════════════════════════════════════════════════
# 完整交易判定（持有期扫描）
# ═══════════════════════════════════════════════════════════════

def judge_trade_exit(plan: dict, klines: list, all_stocks: dict = None) -> dict:
    """从买入日往后扫描，直到触发卖出条件

    退出优先级：
    1. 止损：最低价跌破止损价 → 止损价卖出
    2. 信号卖出：get_stock_card().signal='sell' → 当日收盘价卖出

    Args:
        plan: plan dict，含 date / code / stop_loss
        klines: 该股票全量K线 [{date, close, open, high, low}, ...] 升序
        all_stocks: get_all_stocks() 全量数据（用于 get_stock_card）

    Returns:
        更新后的 plan 字段（result, exit_date, exit_price, exit_reason, ...）
    """
    result = dict(plan)
    date_compact = plan['date'].replace('-', '')
    code = plan.get('code', '')
    stop_loss = plan.get('stop_loss')
    stop_loss_pct = plan.get('stop_loss_pct')
    action = plan.get('action', '')

    # 找入场日
    entry_idx = None
    for i, k in enumerate(klines):
        if str(k.get('date', '')) == date_compact:
            entry_idx = i
            result['plan_close'] = float(k.get('close', 0))
            break

    plan_close = result.get('plan_close')
    if not plan_close or plan_close == 0 or entry_idx is None:
        result['result'] = 'pending'
        return result

    # 卖出类 — 沿用次日判定（卖出后第二天涨=卖飞，跌=卖对）
    is_sell_plan = '卖出' in action
    if is_sell_plan:
        if entry_idx + 1 < len(klines):
            nk = klines[entry_idx + 1]
            nc = float(nk.get('close', 0))
            change = (nc - plan_close) / plan_close * 100
            result['next_date'] = str(nk.get('date', ''))
            result['next_close'] = nc
            result['change_pct'] = round(change, 2)
            if change <= -0.5:
                result['result'] = 'success'
                result['exit_reason'] = 'price_down'
            elif change >= 0.5:
                result['result'] = 'failure'
                result['exit_reason'] = 'price_up'
            else:
                result['result'] = 'flat'
                result['exit_reason'] = 'flat'
            result['exit_date'] = result['next_date']
            result['exit_price'] = nc
            result['holding_days'] = 1
        else:
            result['result'] = 'pending'
        return result

    # ── 买入类：扫描持有期 ──
    max_price = plan_close
    min_price = plan_close

    # 从次日开始逐日扫描
    for i in range(entry_idx + 1, len(klines)):
        k = klines[i]
        cur_close = float(k.get('close', 0))
        cur_low = float(k.get('low', 0))
        cur_high = float(k.get('high', 0))
        cur_date = str(k.get('date', ''))

        max_price = max(max_price, cur_high)
        min_price = min(min_price, cur_low)
        holding_days = i - entry_idx

        # 1. 止损 — 用 stop_loss_pct 按入场价算，避免入场价变化导致止损失效
        actual_sl = None
        if stop_loss_pct is not None and stop_loss_pct > 0:
            actual_sl = plan_close * (1 - stop_loss_pct / 100)
        elif stop_loss is not None:
            actual_sl = float(stop_loss)
        if actual_sl is not None and cur_low < actual_sl:
            result['exit_date'] = cur_date
            result['exit_price'] = round(actual_sl, 2)
            result['exit_reason'] = 'stop_loss'
            result['change_pct'] = round((actual_sl - plan_close) / plan_close * 100, 2)
            result['holding_days'] = holding_days
            result['max_gain'] = round((max_price - plan_close) / plan_close * 100, 2)
            result['max_loss'] = round((min_price - plan_close) / plan_close * 100, 2)
            result['max_price'] = max_price
            result['min_price'] = min_price
            result['hit_stop_loss'] = 1
            result['result'] = 'failure'  # 止损就是失败
            break

        # 2. 信号卖出 — 调用 get_stock_card
        if all_stocks:
            try:
                from backend.services.stock_card_service import get_stock_card
                # 用截至当天的K线数据判断
                date_for_card = cur_date[:4] + '-' + cur_date[4:6] + '-' + cur_date[6:8]
                card = get_stock_card(code, date_str=date_for_card, klines=klines[:i+1])
                if card and card.get('signal') == 'sell':
                    result['exit_date'] = cur_date
                    result['exit_price'] = cur_close
                    result['exit_reason'] = 'signal_sell'
                    result['holding_days'] = holding_days
                    result['change_pct'] = round((cur_close - plan_close) / plan_close * 100, 2)
                    result['max_gain'] = round((max_price - plan_close) / plan_close * 100, 2)
                    result['max_loss'] = round((min_price - plan_close) / plan_close * 100, 2)
                    result['max_price'] = max_price
                    result['min_price'] = min_price
                    result['result'] = 'success' if result['change_pct'] >= 0 else 'failure'
                    break
            except Exception:
                pass

    # 扫描完成但未退出
    if 'exit_date' not in result or not result.get('exit_date'):
        result['result'] = 'pending'
        # 但记录截至目前的浮动盈亏
        last_close = float(klines[-1].get('close', 0))
        result['change_pct'] = round((last_close - plan_close) / plan_close * 100, 2)
        result['max_gain'] = round((max_price - plan_close) / plan_close * 100, 2)
        result['max_loss'] = round((min_price - plan_close) / plan_close * 100, 2)
        result['max_price'] = max_price
        result['min_price'] = min_price
        result['holding_days'] = len(klines) - entry_idx - 1

    return result


# ═══════════════════════════════════════════════════════════════
# 数据库 CRUD
# ═══════════════════════════════════════════════════════════════

def _plan_to_row(p: dict) -> dict:
    """将 plan dict 转为数据库行"""
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    return {
        'date': p.get('date', ''),
        'code': p.get('code', ''),
        'name': p.get('name', ''),
        'source': p.get('source', ''),
        'action': p.get('action', ''),
        'reason': p.get('reason', ''),
        'structure': p.get('structure', ''),
        'stage': p.get('stage', ''),
        'buy_point': p.get('buy_point', ''),
        'is_main': p.get('is_main', 0),
        'priority': p.get('priority', ''),
        'stop_loss': p.get('stop_loss'),
        'stop_loss_pct': p.get('stop_loss_pct'),
        'plan_close': p.get('plan_close'),
        'next_date': p.get('next_date'),
        'next_open': p.get('next_open'),
        'next_close': p.get('next_close'),
        'next_high': p.get('next_high'),
        'next_low': p.get('next_low'),
        'change_pct': p.get('change_pct'),
        'max_gain': p.get('max_gain'),
        'max_loss': p.get('max_loss'),
        'hit_stop_loss': p.get('hit_stop_loss', 0),
        'exit_date': p.get('exit_date'),
        'exit_price': p.get('exit_price'),
        'exit_reason': p.get('exit_reason'),
        'holding_days': p.get('holding_days'),
        'max_price': p.get('max_price'),
        'min_price': p.get('min_price'),
        'result': p.get('result'),
        'executed': p.get('executed'),
        'user_note': p.get('user_note', ''),
        'created_at': now,
        'updated_at': now,
    }


def _save_plan_record(db_path: str, plan: dict):
    """保存一条计划记录（INSERT OR REPLACE）"""
    row = _plan_to_row(plan)
    conn = _get_conn(db_path)
    try:
        cols = ', '.join(row.keys())
        placeholders = ', '.join(['?' for _ in row])
        update_cols = ', '.join([f'{k}=excluded.{k}' for k in row.keys()
                                 if k not in ('date', 'code', 'created_at')])
        sql = f"""INSERT INTO plan_records ({cols})
                  VALUES ({placeholders})
                  ON CONFLICT(date, code) DO UPDATE SET {update_cols}"""
        conn.execute(sql, list(row.values()))
        conn.commit()
    finally:
        conn.close()


def get_plans(db_path: str, start_date: str = None, end_date: str = None) -> list:
    """获取计划列表，支持日期筛选"""
    conn = _get_conn(db_path)
    try:
        conditions = []
        params = []
        if start_date:
            conditions.append("date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("date <= ?")
            params.append(end_date)

        where = "WHERE " + " AND ".join(conditions) if conditions else ""
        rows = conn.execute(
            f"SELECT * FROM plan_records {where} ORDER BY date DESC, code",
            params
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def annotate_plan(db_path: str, date_str: str, code: str,
                  executed: bool = None, user_note: str = '') -> dict:
    """标记计划执行状态"""
    conn = _get_conn(db_path)
    try:
        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        updates = ['updated_at = ?']
        params = [now]
        if executed is not None:
            updates.append('executed = ?')
            params.append(1 if executed else 0)
        if user_note:
            updates.append('user_note = ?')
            params.append(user_note)
        params.extend([date_str, code])
        conn.execute(
            f"UPDATE plan_records SET {', '.join(updates)} WHERE date = ? AND code = ?",
            params
        )
        affected = conn.total_changes
        conn.commit()
        if affected == 0:
            return {'success': False, 'error': '记录不存在'}
        return {'success': True}
    finally:
        conn.close()


def _execute_query(db_path: str, sql: str, params: list = None) -> list:
    """执行SQL查询并返回dict列表"""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(sql, params or []).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# 多维统计摘要
# ═══════════════════════════════════════════════════════════════

def _group_stats(rows: list, group_field: str = None) -> dict:
    """对记录列表做分组统计

    Args:
        rows: plan_records 行列表
        group_field: 分组的字段名，None=不分组只算总计

    Returns:
        {group_key: {total, success, failure, flat, rate}} 或单组
    """
    if group_field:
        groups = {}
        for r in rows:
            key = str(r.get(group_field, '')) or '(空)'
            if key not in groups:
                groups[key] = {'total': 0, 'success': 0, 'failure': 0, 'flat': 0}
            groups[key]['total'] += 1
            res = r.get('result', '')
            if res in groups[key]:
                groups[key][res] += 1
        for key, st in groups.items():
            valid = st['success'] + st['failure']
            st['rate'] = round(st['success'] / valid * 100, 1) if valid > 0 else 0
        return groups
    else:
        total = len(rows)
        success = sum(1 for r in rows if r.get('result') == 'success')
        failure = sum(1 for r in rows if r.get('result') == 'failure')
        flat = sum(1 for r in rows if r.get('result') == 'flat')
        valid = success + failure
        return {
            'total_plans': total,
            'success': success,
            'failure': failure,
            'flat': flat,
            'pending': sum(1 for r in rows if r.get('result') == 'pending'),
            'success_rate': round(success / valid * 100, 1) if valid > 0 else 0,
            'avg_gain': round(sum((r.get('change_pct') or 0) for r in rows if r.get('result') == 'success') / success, 2) if success > 0 else 0,
            'avg_loss': round(sum((r.get('change_pct') or 0) for r in rows if r.get('result') == 'failure') / failure, 2) if failure > 0 else 0,
            'best_gain': max((r.get('change_pct', 0) for r in rows if r.get('change_pct') is not None), default=0),
            'worst_loss': min((r.get('change_pct', 0) for r in rows if r.get('change_pct') is not None), default=0),
        }


def _compute_daily_stats(all_plans: list) -> list:
    """按日期聚合统计 — 用于算法效果追踪折线图"""
    from collections import defaultdict
    daily = defaultdict(lambda: {'total': 0, 'success': 0, 'failure': 0, 'flat': 0,
                                 'changes': [], 'gain_sum': 0.0, 'loss_sum': 0.0})
    for p in all_plans:
        d = p.get('date', '')
        r = p.get('result', '')
        chg = p.get('change_pct')
        if r not in ('success', 'failure', 'flat'):
            continue
        daily[d]['total'] += 1
        daily[d][r] += 1
        if chg is not None:
            daily[d]['changes'].append(chg)
            if r == 'success':
                daily[d]['gain_sum'] += chg
            elif r == 'failure':
                daily[d]['loss_sum'] += chg

    result = []
    for date in sorted(daily.keys()):
        st = daily[date]
        valid = st['success'] + st['failure']
        rate = round(st['success'] / valid * 100, 1) if valid > 0 else 0
        avg_chg = round(sum(st['changes']) / len(st['changes']), 2) if st['changes'] else 0
        avg_gain = round(st['gain_sum'] / st['success'], 2) if st['success'] > 0 else 0
        avg_loss = round(st['loss_sum'] / st['failure'], 2) if st['failure'] > 0 else 0
        result.append({
            'date': date,
            'total': st['total'],
            'success': st['success'],
            'failure': st['failure'],
            'flat': st['flat'],
            'success_rate': rate,
            'avg_change': avg_chg,
            'avg_gain': avg_gain,
            'avg_loss': avg_loss,
        })
    return result


def get_tracking(db_path: str = None, start_date: str = None, end_date: str = None,
                 force_db_init: bool = True) -> dict:
    """获取完整的追踪数据（含多维统计）

    Returns: {plans, summary, by_buy_point, by_structure, by_is_main, by_source, suggestions, last_updated}
    """
    if db_path is None:
        db_path = DB_PATH
    if force_db_init:
        _init_db(db_path)

    # 读取原始数据
    all_plans = get_plans(db_path, start_date=start_date, end_date=end_date)

    # 只有有result的结果才参与统计（排除None=持有类）
    stat_plans = [p for p in all_plans if p.get('result') in ('success', 'failure', 'flat')]

    summary = _group_stats(stat_plans, group_field=None)
    by_buy_point = _group_stats(
        [p for p in stat_plans if p.get('buy_point')],
        group_field='buy_point'
    )
    by_structure = _group_stats(
        [p for p in stat_plans if p.get('structure')],
        group_field='structure'
    )
    by_is_main = _group_stats(
        [p for p in stat_plans if p.get('is_main') is not None],
        group_field='is_main'
    )
    by_source = _group_stats(
        [p for p in stat_plans if p.get('source')],
        group_field='source'
    )

    suggestions = generate_suggestions(all_plans, summary, by_buy_point, by_structure, by_is_main)

    # 每日聚合统计 — 用于算法效果追踪折线图
    daily_stats = _compute_daily_stats(all_plans)

    return {
        'plans': all_plans,
        'summary': summary,
        'by_buy_point': by_buy_point,
        'by_structure': by_structure,
        'by_is_main': by_is_main,
        'by_source': by_source,
        'suggestions': suggestions,
        'daily_stats': daily_stats,
        'last_updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    }


# ═══════════════════════════════════════════════════════════════
# 自动建议
# ═══════════════════════════════════════════════════════════════

def generate_suggestions(all_plans: list, summary: dict,
                         by_buy_point: dict = None, by_structure: dict = None,
                         by_is_main: dict = None) -> list:
    """根据统计数据生成自动建议"""
    suggestions = []
    stat_plans = [p for p in all_plans if p.get('result') in ('success', 'failure')]
    if len(stat_plans) < 3:
        return suggestions

    overall_rate = summary.get('success_rate', 0)

    # 1. 按买点类型分析
    if by_buy_point:
        for bp, stats in sorted(by_buy_point.items(), key=lambda x: -x[1]['total']):
            if stats['total'] >= 3:
                if stats['rate'] < 50:
                    suggestions.append({
                        'type': 'warning', 'dimension': 'buy_point',
                        'category': bp, 'rate_current': stats['rate'],
                        'rate_overall': overall_rate, 'count': stats['total'],
                        'message': f'买点「{bp}」{stats["total"]}次仅{stats["rate"]}%成功率（整体{overall_rate}%），建议检查该买点筛选逻辑',
                    })
                elif stats['rate'] > 70 and stats['total'] >= 5:
                    suggestions.append({
                        'type': 'best', 'dimension': 'buy_point',
                        'category': bp, 'rate_current': stats['rate'],
                        'rate_overall': overall_rate, 'count': stats['total'],
                        'message': f'买点「{bp}」{stats["total"]}次{stats["rate"]}%成功率，表现优秀，继续保持',
                    })

    # 2. 按结构分析
    if by_structure:
        for struct, stats in by_structure.items():
            if stats['total'] >= 3:
                if stats['rate'] < 50:
                    suggestions.append({
                        'type': 'warning', 'dimension': 'structure',
                        'category': struct, 'rate_current': stats['rate'],
                        'rate_overall': overall_rate, 'count': stats['total'],
                        'message': f'结构「{struct}」{stats["total"]}次仅{stats["rate"]}%成功率，注意该结构下的选股质量',
                    })

    # 3. 主线 vs 非主线对比
    if by_is_main:
        main_stats = by_is_main.get('1')
        non_main_stats = by_is_main.get('0')
        if main_stats and non_main_stats:
            diff = main_stats.get('rate', 0) - non_main_stats.get('rate', 0)
            if abs(diff) > 15 and main_stats['total'] >= 3 and non_main_stats['total'] >= 3:
                if diff > 0:
                    suggestions.append({
                        'type': 'best' if diff > 20 else 'info',
                        'dimension': 'mainline',
                        'category': '主线与非主线',
                        'rate_current': main_stats['rate'],
                        'rate_overall': non_main_stats['rate'],
                        'count': main_stats['total'] + non_main_stats['total'],
                        'message': f'主线股票成功率{main_stats["rate"]}%，非主线{non_main_stats["rate"]}%，相差{diff}个百分点，聚焦主线板块操作',
                    })
                else:
                    suggestions.append({
                        'type': 'warning',
                        'dimension': 'mainline',
                        'category': '非主线',
                        'rate_current': non_main_stats['rate'],
                        'rate_overall': main_stats['rate'],
                        'count': non_main_stats['total'],
                        'message': f'非主线股票成功率{non_main_stats["rate"]}%低于主线{main_stats["rate"]}%，注意非主线股票的风险',
                    })

    # 4. 止损分析
    with_stop = [p for p in stat_plans if p.get('stop_loss') is not None]
    if len(with_stop) >= 5:
        hit = sum(1 for p in with_stop if p.get('hit_stop_loss'))
        hit_rate = hit / len(with_stop) * 100
        if hit_rate > 25:
            suggestions.append({
                'type': 'warning', 'dimension': 'stop_loss',
                'category': '止损设置',
                'rate_current': round(hit_rate, 1),
                'rate_overall': 0, 'count': len(with_stop),
                'message': f'止损偏紧：{len(with_stop)}笔中{hit}笔盘中止损被触发（{round(hit_rate,1)}%），建议适当放宽止损幅度',
            })

    # 5. 个股频繁失败
    stock_fails = {}
    for p in stat_plans:
        key = p.get('code', '')
        if key:
            if key not in stock_fails:
                stock_fails[key] = {'name': p.get('name', key), 'total': 0, 'fail': 0}
            stock_fails[key]['total'] += 1
            if p['result'] == 'failure':
                stock_fails[key]['fail'] += 1
    for code, st in stock_fails.items():
        if st['total'] >= 3 and st['fail'] >= 3:
            suggestions.append({
                'type': 'warning', 'dimension': 'stock',
                'category': st['name'],
                'rate_current': round(st['fail'] / st['total'] * 100, 1),
                'rate_overall': 0, 'count': st['total'],
                'message': f'股票{st["name"]}({code}) {st["total"]}次计划中{st["fail"]}次失败，注意识别该股买点有效性',
            })

    type_order = {'warning': 0, 'best': 1, 'info': 2}
    suggestions.sort(key=lambda x: type_order.get(x['type'], 9))
    return suggestions


def generate_suggestions_for_db(db_path: str = None) -> list:
    """从数据库读取数据后生成建议（供测试调用）"""
    data = get_tracking(db_path)
    return data.get('suggestions', [])


# ═══════════════════════════════════════════════════════════════
# 完整计算流程
# ═══════════════════════════════════════════════════════════════

def _get_review_dates() -> list:
    """获取有复盘的日期列表（从CACHE_RECORDS或review数据推断）

    这里用 workbench 目录的存在日期作为候选，避免依赖 review_archive
    """
    from backend.config import PRIVATE_DIR
    wb_dir = os.path.join(PRIVATE_DIR, 'workbench')
    if os.path.isdir(wb_dir):
        return sorted(
            f.replace('.json', '') for f in os.listdir(wb_dir)
            if f.endswith('.json') and len(f.replace('.json', '')) == 10
        )
    return []


def compute_tracking(force=False, db_path=None) -> dict:
    """扫描所有交易日，从 review 数据提取计划并计算追踪

    force=True: 从头重新计算
    返回: get_tracking() 的完整结果
    """
    if db_path is None:
        db_path = DB_PATH

    _init_db(db_path)

    # 获取已有的记录作为缓存
    existing = {}
    if not force:
        for p in get_plans(db_path):
            key = f"{p['date']}|{p['code']}"
            if p.get('result') == 'pending':
                existing[key] = p  # 只保留待更新的

    dates = _get_review_dates()
    if not dates:
        # 没有workbench数据，用已有的db数据
        return get_tracking(db_path)

    from backend.services.review_service import compute_review_real_time
    from backend.core.data_layer import get_all_stocks, get_stock_klines

    for date_str in dates:
        try:
            review_data = compute_review_real_time(date_str)
        except Exception:
            continue
        trading_plan = review_data.get('trading_plan', {})
        if not trading_plan:
            continue

        plans = extract_plans_from_trading_plan(trading_plan, date_str)
        all_stocks = get_all_stocks()

        for plan in plans:
            key = f"{plan['date']}|{plan['code']}"

            # 如果有已决结果且不需要强制重新计算
            if not force and key not in existing:
                continue

            # 获取K线
            klines = get_stock_klines(plan['code'], stocks=all_stocks)
            if not klines or not isinstance(klines, list):
                plan['result'] = 'no_data'
            else:
                plan = judge_trade_exit(plan, klines, all_stocks)

            _save_plan_record(db_path, plan)

    return get_tracking(db_path)


def get_realtime_tracking(db_path=None) -> dict:
    """获取追踪结果（读缓存，不重新计算）"""
    return get_tracking(db_path)
