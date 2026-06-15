"""
最小 MySQL 读取器 — 供 threel_core 共享包独立使用

通过环境变量配置数据库连接（与 server/backend/core/config.py 同源）：
  DB_HOST / MYSQL_HOST  (默认 localhost)
  DB_PORT / MYSQL_PORT  (默认 3306)
  DB_USER / MYSQL_USER  (默认 tushare)
  DB_PASSWORD / MYSQL_PASSWORD (默认 tushare_pass)
  DB_NAME / MYSQL_DATABASE (默认 tushare)

只做 SELECT 读，不含任何 Tushare API 或写入逻辑。
"""
import os
from typing import List, Dict, Optional

import pymysql
from pymysql.cursors import DictCursor


def _get_config() -> dict:
    """从环境变量读取数据库配置（兼容 MYSQL_ 和 DB_ 前缀）"""
    return {
        'host': os.environ.get('DB_HOST') or os.environ.get('MYSQL_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT') or os.environ.get('MYSQL_PORT', '3306')),
        'user': os.environ.get('DB_USER') or os.environ.get('MYSQL_USER', 'tushare'),
        'password': os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD', 'tushare_pass'),
        'database': os.environ.get('DB_NAME') or os.environ.get('MYSQL_DATABASE', 'tushare'),
        'charset': 'utf8mb4',
    }


def query_stock_klines(codes: List[str], limit: int = 60) -> Dict[str, List[dict]]:
    """批量查询多只股票的日K线（前复权），返回 {code: [{date, open, close, high, low, volume}, ...]}

    Args:
        codes: 股票代码列表（8位含后缀，如 '002916.SZ'）
        limit: 每只股票最多返回条数

    Returns:
        {code: [{date, open, close, high, low, volume}, ...]}
        查询失败的股票不返回
    """
    if not codes:
        return {}

    config = _get_config()
    conn = pymysql.connect(**config)
    try:
        with conn.cursor(DictCursor) as cur:
            # 1. 查询原始K线
            placeholders = ','.join(['%s'] * len(codes))
            sql = f"""SELECT ts_code, trade_date, open, high, low, close, vol
                      FROM stock_daily
                      WHERE ts_code IN ({placeholders})
                      ORDER BY ts_code, trade_date DESC"""
            cur.execute(sql, codes)
            all_rows = cur.fetchall()

        # 2. 按 ts_code 分组，每组取最新 limit 条
        grouped: Dict[str, List[dict]] = {}
        for r in all_rows:
            code = r['ts_code']
            if code not in grouped:
                grouped[code] = []
            if len(grouped[code]) < limit:
                grouped[code].append(r)

        # 3. 对每组做前复权（批量查 adj_factor）
        result: Dict[str, List[dict]] = {}
        for code, rows in grouped.items():
            dates = [r['trade_date'] for r in rows]
            result[code] = _apply_qfq_batch(conn, code, rows, dates)

        return result
    finally:
        conn.close()


def get_last_stock_date() -> Optional[str]:
    """返回 stock_daily 最新交易日（YYYYMMDD）"""
    config = _get_config()
    conn = pymysql.connect(**config)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT MAX(trade_date) FROM stock_daily')
            row = cur.fetchone()
            return str(row[0]) if row and row[0] else None
    finally:
        conn.close()


def _apply_qfq_batch(conn, ts_code: str, rows: List[dict],
                      dates: List[str]) -> List[dict]:
    """对单个股票的一组K线数据应用前复权

    前复权价 = 原始价 × latest_adj / adj_factor[t]
    """
    if not rows or not dates:
        return []

    # 查询 adj_factor
    placeholders = ','.join(['%s'] * len(dates))
    with conn.cursor(DictCursor) as cur:
        sql = f"""SELECT trade_date, adj_factor
                  FROM adj_factor
                  WHERE ts_code=%s AND trade_date IN ({placeholders})"""
        params = [ts_code] + dates
        cur.execute(sql, params)
        adj_rows = cur.fetchall()

    adj_map: Dict[str, float] = {r['trade_date']: float(r['adj_factor']) for r in adj_rows if r.get('adj_factor')}

    # 最新一条的 adj_factor 作为基准
    latest_date = dates[0]  # 因为按 trade_date DESC 排序
    latest_adj = adj_map.get(latest_date)
    if not latest_adj:
        # 没有复权因子，返回原始数据
        return [
            {
                'date': r['trade_date'],
                'open': float(r['open']) if r['open'] else 0,
                'close': float(r['close']) if r['close'] else 0,
                'high': float(r['high']) if r['high'] else 0,
                'low': float(r['low']) if r['low'] else 0,
                'volume': int(r['vol']) if r['vol'] else 0,
            }
            for r in rows
        ]

    result = []
    for r in reversed(rows):  # 正序返回
        adj_factor = adj_map.get(r['trade_date'])
        ratio = latest_adj / adj_factor if (adj_factor and adj_factor > 0) else 1.0
        result.append({
            'date': r['trade_date'],
            'open': round(float(r['open']) * ratio, 2) if r['open'] else None,
            'close': round(float(r['close']) * ratio, 2) if r['close'] else None,
            'high': round(float(r['high']) * ratio, 2) if r['high'] else None,
            'low': round(float(r['low']) * ratio, 2) if r['low'] else None,
            'volume': int(r['vol']) if r['vol'] else 0,
        })
    return result
