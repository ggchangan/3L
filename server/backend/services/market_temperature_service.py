"""3L 市场温度：以全市场宽度、涨跌停、新高新低和成交额描述赚钱效应。"""
import json
import os
import tempfile
from datetime import datetime

from backend.core.config import DATA_DIR

TEMPERATURE_CACHE_DIR = os.path.join(DATA_DIR, 'computed', 'market_temperature')


def _cache_path(trade_date):
    return os.path.join(TEMPERATURE_CACHE_DIR, f'{trade_date}.json')


def _load_confirmed_cache(trade_date):
    path = _cache_path(trade_date)
    try:
        with open(path, encoding='utf-8') as file:
            cached = json.load(file)
        if (cached.get('status') == 'confirmed'
                and cached.get('method_version') == 'market_temperature_v1'):
            return cached
    except (OSError, ValueError, TypeError):
        pass
    return None


def _save_confirmed_cache(result):
    if result.get('status') != 'confirmed' or not result.get('date'):
        return
    os.makedirs(TEMPERATURE_CACHE_DIR, exist_ok=True)
    path = _cache_path(result['date'])
    fd, temp_path = tempfile.mkstemp(prefix='.market-temperature-', suffix='.json', dir=TEMPERATURE_CACHE_DIR)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as file:
            json.dump(result, file, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def invalidate_market_temperature_cache(trade_date):
    """数据管线回补或修正后，强制重算依赖当日及历史窗口的温度。"""
    normalized = str(trade_date or '').replace('-', '')
    if not normalized:
        return
    try:
        os.remove(_cache_path(normalized))
    except FileNotFoundError:
        pass


def classify_market_temperature(metrics):
    """透明规则分类；原始证据始终随结论返回，分数不参与交易门禁。"""
    total = int(metrics.get('total') or 0)
    up = int(metrics.get('up') or 0)
    down = int(metrics.get('down') or 0)
    highs = metrics.get('new_high_1y')
    lows = metrics.get('new_low_1y')
    limit_up = int(metrics.get('limit_up') or 0)
    limit_down = int(metrics.get('limit_down') or 0)
    if total <= 0:
        return 'unknown', '温度待确认', ['缺少当日全市场涨跌数据']

    up_ratio = up / total
    down_ratio = down / total
    evidence = []
    if highs is not None and highs < 20:
        evidence.append(f'一年新高仅{highs}家，低于知识库冰点参考线20家')
    if down_ratio >= 0.65:
        evidence.append(f'下跌家数占比{down_ratio:.1%}，亏钱效应明显')
    if up_ratio >= 0.65:
        evidence.append(f'上涨家数占比{up_ratio:.1%}，赚钱效应明显')
    if highs is not None and lows is not None and lows > highs:
        evidence.append(f'一年新低{lows}家多于新高{highs}家')
    if limit_down > limit_up:
        evidence.append(f'收盘跌停{limit_down}家多于涨停{limit_up}家')

    if highs is not None and lows is not None and highs < 20 and (down_ratio >= 0.60 or lows > highs):
        return 'ice', '冰点观察', evidence
    if down_ratio >= 0.65 and ((lows is not None and highs is not None and lows > highs) or limit_down >= limit_up):
        return 'cold', '偏冷', evidence
    if up_ratio >= 0.65 and limit_up >= max(1, limit_down * 2) and (highs is None or lows is None or highs > lows):
        return 'hot', '偏热', evidence
    if up_ratio >= 0.55 and limit_up > limit_down:
        return 'warm', '回暖', evidence
    return 'neutral', '中性', evidence or ['涨跌宽度和极端情绪指标未形成明显单边']


def _empty_temperature(trade_date='', error=''):
    return {
        'level': 'unknown', 'label': '温度待确认', 'date': trade_date,
        'status': 'unavailable', 'source': 'tushare_mysql',
        'metrics': {}, 'evidence': [],
        'quality': {'missing': [error or '市场温度数据不可用']},
        'updated_at': datetime.now().isoformat(timespec='seconds'),
        'method_version': 'market_temperature_v1',
    }


def get_market_temperature(trade_date=None, db=None):
    """从 Tushare 落库数据计算指定交易日市场温度。"""
    use_cache = db is None
    normalized_date = str(trade_date or '').replace('-', '')
    if use_cache and normalized_date:
        cached = _load_confirmed_cache(normalized_date)
        if cached:
            return cached
    if use_cache:
        try:
            from backend.data_access.data_source import _get_tushare_db
            db = _get_tushare_db()
        except Exception as exc:
            return _empty_temperature(str(trade_date or ''), str(exc))
    if not db:
        return _empty_temperature(str(trade_date or ''), 'Tushare 数据库不可用')

    try:
        if not trade_date:
            rows = db.execute_raw('SELECT MAX(trade_date) AS trade_date FROM stock_daily')
            trade_date = rows[0].get('trade_date') if rows else ''
        trade_date = str(trade_date or '').replace('-', '')
        if not trade_date:
            return _empty_temperature('', '没有可用交易日')

        breadth_rows = db.execute_raw("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN pct_chg IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL THEN 1 ELSE 0 END) AS complete_count,
                   SUM(CASE WHEN pct_chg > 0 THEN 1 ELSE 0 END) AS up_count,
                   SUM(CASE WHEN pct_chg < 0 THEN 1 ELSE 0 END) AS down_count,
                   SUM(CASE WHEN pct_chg = 0 OR pct_chg IS NULL THEN 1 ELSE 0 END) AS flat_count,
                   SUM(COALESCE(amount, 0)) AS total_amount
            FROM stock_daily WHERE trade_date=%s
        """, [trade_date])
        breadth = breadth_rows[0] if breadth_rows else {}
        total = int(breadth.get('total') or 0)
        if total == 0:
            return _empty_temperature(trade_date, '当日个股日线为空')

        from backend.data_access.data_source import _expected_stock_daily_count
        expected_count = _expected_stock_daily_count(db, trade_date)
        complete_count = int(breadth.get('complete_count') or 0)

        limit_rows = db.execute_raw("""
            SELECT COUNT(l.ts_code) AS covered,
                   SUM(CASE WHEN d.close >= l.up_limit - 0.001 THEN 1 ELSE 0 END) AS limit_up,
                   SUM(CASE WHEN d.close <= l.down_limit + 0.001 THEN 1 ELSE 0 END) AS limit_down
            FROM stock_daily d LEFT JOIN stk_limit l
              ON l.ts_code=d.ts_code AND l.trade_date=d.trade_date
            WHERE d.trade_date=%s
        """, [trade_date])
        limit_data = limit_rows[0] if limit_rows else {}

        adj_rows = db.execute_raw("""
            SELECT COUNT(a.ts_code) AS covered FROM stock_daily d
            LEFT JOIN adj_factor a ON a.ts_code=d.ts_code AND a.trade_date=d.trade_date
            WHERE d.trade_date=%s
        """, [trade_date])
        adj_covered = int((adj_rows[0] if adj_rows else {}).get('covered') or 0)

        dates = db.execute_raw("""
            SELECT DISTINCT trade_date FROM stock_daily
            WHERE trade_date < %s ORDER BY trade_date DESC LIMIT 250
        """, [trade_date])
        history_start = min((str(row['trade_date']) for row in dates), default='')
        high_low = {}
        if history_start and adj_covered >= total * 0.98:
            high_low_rows = db.execute_raw("""
                SELECT COUNT(*) AS compared,
                       SUM(CASE WHEN cur_high >= prior_high * 0.9999 THEN 1 ELSE 0 END) AS new_high,
                       SUM(CASE WHEN cur_low <= prior_low * 1.0001 THEN 1 ELSE 0 END) AS new_low
                FROM (
                    SELECT c.ts_code, c.high AS cur_high, c.low AS cur_low,
                           MAX(h.high * ha.adj_factor / ca.adj_factor) AS prior_high,
                           MIN(h.low * ha.adj_factor / ca.adj_factor) AS prior_low,
                           COUNT(DISTINCT h.trade_date) AS sessions
                    FROM stock_daily c
                    JOIN adj_factor ca ON ca.ts_code=c.ts_code AND ca.trade_date=c.trade_date
                    JOIN stock_daily h ON h.ts_code=c.ts_code AND h.trade_date >= %s AND h.trade_date < c.trade_date
                    JOIN adj_factor ha ON ha.ts_code=h.ts_code AND ha.trade_date=h.trade_date
                    WHERE c.trade_date=%s AND ca.adj_factor > 0 AND ha.adj_factor > 0
                    GROUP BY c.ts_code, c.high, c.low
                    HAVING sessions >= 200
                ) yearly_extremes
            """, [history_start, trade_date])
            high_low = high_low_rows[0] if high_low_rows else {}

        amount_rows = db.execute_raw("""
            SELECT trade_date, SUM(COALESCE(amount, 0)) AS amount
            FROM stock_daily WHERE trade_date <= %s
            GROUP BY trade_date ORDER BY trade_date DESC LIMIT 20
        """, [trade_date])
        amounts = [float(row.get('amount') or 0) / 100000 for row in amount_rows]
        amount_today = float(breadth.get('total_amount') or 0) / 100000
        avg5 = sum(amounts[:5]) / len(amounts[:5]) if amounts[:5] else 0
        avg20 = sum(amounts) / len(amounts) if amounts else 0

        compared = int(high_low.get('compared') or 0)
        limit_covered = int(limit_data.get('covered') or 0)
        high_low_reliable = compared >= total * 0.85
        metrics = {
            'total': total,
            'up': int(breadth.get('up_count') or 0),
            'down': int(breadth.get('down_count') or 0),
            'flat': int(breadth.get('flat_count') or 0),
            'limit_up': int(limit_data.get('limit_up') or 0),
            'limit_down': int(limit_data.get('limit_down') or 0),
            'new_high_1y': int(high_low.get('new_high') or 0) if high_low_reliable else None,
            'new_low_1y': int(high_low.get('new_low') or 0) if high_low_reliable else None,
            'amount_yi': round(amount_today, 1),
            'amount_vs_5d_pct': round((amount_today / avg5 - 1) * 100, 1) if avg5 else None,
            'amount_vs_20d_pct': round((amount_today / avg20 - 1) * 100, 1) if avg20 else None,
        }
        level, label, evidence = classify_market_temperature(metrics)
        missing = []
        if not expected_count:
            missing.append('缺少可信的应上市股票池/历史完整日基线')
        elif total < expected_count * 0.98:
            missing.append(f'核心日线数量异常（当日{total}/可信基线{expected_count}）')
        if complete_count < total * 0.98:
            missing.append(f'核心日线字段不完整（{complete_count}/{total}）')
        if limit_covered < total * 0.98:
            missing.append(f'涨跌停价格覆盖不足（{limit_covered}/{total}）')
        if adj_covered < total * 0.98:
            missing.append(f'当日复权因子覆盖不足（{adj_covered}/{total}）')
        if compared < total * 0.85:
            missing.append(f'一年新高/新低可比样本不足（{compared}/{total}）')
        status = 'confirmed' if not missing else 'partial'
        result = {
            'level': level, 'label': label, 'date': trade_date,
            'status': status, 'source': 'tushare_mysql',
            'metrics': metrics, 'evidence': evidence,
            'quality': {
                'stock_count': total, 'limit_covered': limit_covered,
                'adj_factor_covered': adj_covered, 'year_comparable': compared,
                'expected_stock_count': expected_count, 'stock_complete': complete_count,
                'missing': missing,
            },
            'rules': [
                {'name': '冰点参考', 'rule': '一年新高少于20家，并伴随下跌宽度或新低占优', 'origin': '3L训练营'},
                {'name': '宽度与极端情绪', 'rule': '上涨/下跌占比、涨跌停和新高新低共同确认', 'origin': '工程口径v1'},
            ],
            'updated_at': datetime.now().isoformat(timespec='seconds'),
            'method_version': 'market_temperature_v1',
        }
        if use_cache:
            _save_confirmed_cache(result)
        return result
    except Exception as exc:
        return _empty_temperature(str(trade_date or ''), f'{type(exc).__name__}: {exc}')
