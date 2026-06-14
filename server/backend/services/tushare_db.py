"""
Tushare MySQL 数据库封装层
- 建表(初始化)
- 批量写入(upsert with REPLACE INTO)
- 查询封装(get_stock_daily, get_daily_basic, ...)
- 连接管理
"""
import os, json, time
from typing import Dict, List, Optional, Any
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor

from backend.config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE,
    TUSHARE_TOKEN, TUSHARE_TOKEN_HIGH, TUSHARE_PROXY_URL, DATA_DIR
)


# ════════════════════════════════════════════════════════════
# CREATE TABLE 语句（MySQL 语法）
# ════════════════════════════════════════════════════════════

CREATE_TABLES = {
    'stock_daily': """
        CREATE TABLE IF NOT EXISTS stock_daily (
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(10) NOT NULL,
            open        DOUBLE,
            high        DOUBLE,
            low         DOUBLE,
            close       DOUBLE,
            pre_close   DOUBLE,
            `change`    DOUBLE,
            pct_chg     DOUBLE,
            vol         DOUBLE,
            amount      DOUBLE,
            PRIMARY KEY (ts_code, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'daily_basic': """
        CREATE TABLE IF NOT EXISTS daily_basic (
            ts_code         VARCHAR(20) NOT NULL,
            trade_date      VARCHAR(10) NOT NULL,
            close           DOUBLE,
            turnover_rate   DOUBLE,
            turnover_rate_f DOUBLE,
            volume_ratio    DOUBLE,
            pe              DOUBLE,
            pe_ttm          DOUBLE,
            pb              DOUBLE,
            ps              DOUBLE,
            pcf             DOUBLE,
            total_mv        DOUBLE,
            circ_mv         DOUBLE,
            total_share     DOUBLE,
            float_share     DOUBLE,
            free_share      DOUBLE,
            PRIMARY KEY (ts_code, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'index_daily': """
        CREATE TABLE IF NOT EXISTS index_daily (
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(10) NOT NULL,
            open        DOUBLE,
            high        DOUBLE,
            low         DOUBLE,
            close       DOUBLE,
            pre_close   DOUBLE,
            `change`    DOUBLE,
            pct_chg     DOUBLE,
            vol         DOUBLE,
            amount      DOUBLE,
            PRIMARY KEY (ts_code, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'ths_daily': """
        CREATE TABLE IF NOT EXISTS ths_daily (
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(10) NOT NULL,
            open        DOUBLE,
            high        DOUBLE,
            low         DOUBLE,
            close       DOUBLE,
            pre_close   DOUBLE,
            `change`    DOUBLE,
            pct_chg     DOUBLE,
            vol         DOUBLE,
            amount      DOUBLE,
            PRIMARY KEY (ts_code, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'ths_index': """
        CREATE TABLE IF NOT EXISTS ths_index (
            ts_code     VARCHAR(20) PRIMARY KEY,
            name        VARCHAR(100) NOT NULL,
            count       INT,
            list_date   VARCHAR(10),
            type        VARCHAR(10)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'ths_member': """
        CREATE TABLE IF NOT EXISTS ths_member (
            ts_code     VARCHAR(20) NOT NULL,
            con_code    VARCHAR(20) NOT NULL,
            con_name    VARCHAR(100),
            weight      DOUBLE,
            PRIMARY KEY (ts_code, con_code)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'stock_basic': """
        CREATE TABLE IF NOT EXISTS stock_basic (
            ts_code     VARCHAR(20) PRIMARY KEY,
            symbol      VARCHAR(10),
            name        VARCHAR(50),
            area        VARCHAR(20),
            industry    VARCHAR(50),
            market      VARCHAR(10),
            list_date   VARCHAR(10),
            delist_date VARCHAR(10),
            is_hs       VARCHAR(5)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'adj_factor': """
        CREATE TABLE IF NOT EXISTS adj_factor (
            ts_code     VARCHAR(20) NOT NULL,
            trade_date  VARCHAR(10) NOT NULL,
            adj_factor  DOUBLE,
            PRIMARY KEY (ts_code, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    'trade_cal': """
        CREATE TABLE IF NOT EXISTS trade_cal (
            exchange    VARCHAR(10) NOT NULL,
            cal_date    VARCHAR(10) NOT NULL,
            is_open     INT,
            pretrade_date VARCHAR(10),
            PRIMARY KEY (exchange, cal_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}

# 索引（MySQL 语法 — 不含 IF NOT EXISTS）
CREATE_INDEXES = {
    'idx_stock_daily_ts_code': 'CREATE INDEX idx_stock_daily_ts_code ON stock_daily(ts_code)',
    'idx_stock_daily_date': 'CREATE INDEX idx_stock_daily_date ON stock_daily(trade_date)',
    'idx_daily_basic_ts_code': 'CREATE INDEX idx_daily_basic_ts_code ON daily_basic(ts_code)',
    'idx_adj_factor_ts_code': 'CREATE INDEX idx_adj_factor_ts_code ON adj_factor(ts_code)',
    'idx_ths_daily_ts_code': 'CREATE INDEX idx_ths_daily_ts_code ON ths_daily(ts_code)',
    'idx_ths_member_con_code': 'CREATE INDEX idx_ths_member_con_code ON ths_member(con_code)',
    'idx_ths_index_type': 'CREATE INDEX idx_ths_index_type ON ths_index(type)',
    'idx_index_daily_ts_code': 'CREATE INDEX idx_index_daily_ts_code ON index_daily(ts_code)',
}


class TushareDB:
    """Tushare MySQL 数据库封装

    Args:
        host: MySQL host
        port: MySQL port
        user: MySQL user
        password: MySQL password
        database: MySQL database name
    """

    def __init__(self, host: str = None, port: int = None,
                 user: str = None, password: str = None,
                 database: str = None):
        self.host = host or MYSQL_HOST
        self.port = port or MYSQL_PORT
        self.user = user or MYSQL_USER
        self.password = password or MYSQL_PASSWORD
        self.database = database or MYSQL_DATABASE
        self._conn = None
        self._init_tables()

    def _get_conn(self):
        """获取连接（懒加载，每次调用创建新连接）"""
        return pymysql.connect(
            host=self.host, port=self.port,
            user=self.user, password=self.password,
            database=self.database, charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=True,
        )

    def _init_tables(self):
        """建表+建索引（幂等）"""
        try:
            conn = self._get_conn()
            with conn.cursor() as cur:
                for sql in CREATE_TABLES.values():
                    cur.execute(sql)
                for sql in CREATE_INDEXES.values():
                    try:
                        cur.execute(sql)
                    except Exception:
                        pass  # 索引已存在时忽略
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # 批量写入
    # ════════════════════════════════════════════════════════════

    def upsert_many(self, table: str, df) -> int:
        """从 Tushare DataFrame 批量写入

        Args:
            table: 表名
            df: Tushare 返回的 DataFrame（有 .to_dict() 方法）

        Returns:
            写入行数
        """
        try:
            records = df.to_dict(orient='records')
        except Exception:
            return 0
        return self.upsert_many_from_dicts(table, records)

    def get_table_columns(self, cur, table: str) -> set:
        """获取表的所有字段名"""
        cur.execute(f"SHOW COLUMNS FROM `{table}`")
        return {r['Field'] for r in cur.fetchall()}

    def _ensure_columns(self, cur, table: str, record: dict):
        """动态添加列"""
        existing = self.get_table_columns(cur, table)
        new_cols = set(record.keys()) - existing
        if not new_cols:
            return
        for col in new_cols:
            try:
                cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` TEXT")
            except Exception:
                pass

    def upsert_many_from_dicts(self, table: str, records: List[dict]) -> int:
        """从 dict 列表批量写入（REPLACE INTO），支持动态列

        Args:
            table: 表名
            records: dict 列表

        Returns:
            写入行数
        """
        if not records:
            return 0

        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                # 确保所有列已存在
                for rec in records:
                    self._ensure_columns(cur, table, rec)

                existing = self.get_table_columns(cur, table)
                col_names = sorted(existing & set(records[0].keys()))
                if not col_names:
                    return 0

                placeholders = ','.join(['%s'] * len(col_names))
                quoted_cols = ','.join([f'`{c}`' for c in col_names])
                sql = f"REPLACE INTO `{table}` ({quoted_cols}) VALUES ({placeholders})"

                batch = []
                for rec in records:
                    batch.append(tuple(rec.get(c) for c in col_names))

                cur.executemany(sql, batch)
                conn.commit()
                return len(batch)
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # 基础查询
    # ════════════════════════════════════════════════════════════

    def query_one(self, table: str, **conditions) -> Optional[dict]:
        """查询单条记录

        Args:
            table: 表名
            **conditions: WHERE 条件 (col=val)

        Returns:
            dict 或 None
        """
        if not conditions:
            return None
        where = ' AND '.join([f"`{k}`=%s" for k in conditions])
        vals = list(conditions.values())
        sql = f"SELECT * FROM `{table}` WHERE {where} LIMIT 1"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, vals)
                return cur.fetchone()
        finally:
            conn.close()

    def query_many(self, table: str, where: str = None,
                   params: list = None, order_by: str = None,
                   limit: int = None) -> List[dict]:
        """批量查询

        Args:
            table: 表名
            where: WHERE 子句（不含 WHERE 关键字）
            params: 参数列表
            order_by: ORDER BY 子句
            limit: 返回行数上限

        Returns:
            dict 列表
        """
        sql = f"SELECT * FROM `{table}`"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                return list(cur.fetchall())
        finally:
            conn.close()

    def execute_raw(self, sql: str, params: list = None) -> List[dict]:
        """执行原始 SQL 查询，返回 dict 列表"""
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                return list(cur.fetchall())
        finally:
            conn.close()

    # ════════════════════════════════════════════════════════════
    # 元数据查询
    # ════════════════════════════════════════════════════════════

    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        rows = self.execute_raw("SHOW TABLES")
        key = list(rows[0].keys())[0] if rows else 'Tables_in_tushare'
        return [r[key] for r in rows]

    def get_index_names(self, table: str) -> List[str]:
        """获取指定表上的索引名"""
        rows = self.execute_raw(f"SHOW INDEX FROM `{table}`")
        return list(set(r['Key_name'] for r in rows))

    # ════════════════════════════════════════════════════════════
    # 个股日线查询
    # ════════════════════════════════════════════════════════════

    def query_stock_daily(self, ts_code: str, limit: int = 60,
                          adj: str = 'qfq') -> List[dict]:
        """查询个股日线（按日期倒序），返回兼容现有 Kline 合约

        Args:
            ts_code: 股票代码含后缀 (600519.SH)
            limit: 最多返回条数
            adj: 复权类型，None=不复权，'qfq'=前复权（默认）

        输出格式: [{date, open, close, high, low, volume}, ...]
        """
        rows = self.query_many(
            'stock_daily',
            where='ts_code=%s',
            params=[ts_code],
            order_by='trade_date DESC',
            limit=limit,
        )
        if not rows:
            return []

        if adj == 'qfq':
            return self._apply_qfq(rows, ts_code)
        return self._to_kline_format(rows)

    def _to_kline_format(self, rows: List[dict]) -> List[dict]:
        """原始行 → Kline 合约格式"""
        return [
            {
                'date': r['trade_date'],
                'open': r['open'],
                'close': r['close'],
                'high': r['high'],
                'low': r['low'],
                'volume': int(r['vol']) if r['vol'] else 0,
            }
            for r in rows
        ]

    def _apply_qfq(self, rows: List[dict], ts_code: str) -> List[dict]:
        """对原始K线数据应用前复权

        前复权价 = 原始价 × latest_adj / adj_factor[t]
        """
        dates = [r['trade_date'] for r in rows]
        placeholders = ','.join(['%s'] * len(dates))
        adj_rows = self.query_many(
            'adj_factor',
            where=f'ts_code=%s AND trade_date IN ({placeholders})',
            params=[ts_code] + dates,
        )
        adj_map = {r['trade_date']: r['adj_factor'] for r in adj_rows}

        latest = self.query_one('adj_factor', ts_code=ts_code,
                                trade_date=rows[0]['trade_date'])
        if not latest or not latest.get('adj_factor'):
            return self._to_kline_format(rows)
        latest_adj = float(latest['adj_factor'])

        result = []
        for r in rows:
            adj_factor = adj_map.get(r['trade_date'])
            ratio = latest_adj / float(adj_factor) if (adj_factor and float(adj_factor) > 0) else 1.0
            result.append({
                'date': r['trade_date'],
                'open': round(float(r['open']) * ratio, 2) if r['open'] else None,
                'close': round(float(r['close']) * ratio, 2) if r['close'] else None,
                'high': round(float(r['high']) * ratio, 2) if r['high'] else None,
                'low': round(float(r['low']) * ratio, 2) if r['low'] else None,
                'volume': int(r['vol']) if r['vol'] else 0,
            })
        return result

    def query_daily_basic(self, ts_code: str, trade_date: str) -> Optional[dict]:
        """查询每日指标（PE/PB/市值等）"""
        return self.query_one('daily_basic', ts_code=ts_code, trade_date=trade_date)

    # ════════════════════════════════════════════════════════════
    # 个股代码转换
    # ════════════════════════════════════════════════════════════

    def code_to_ts_code(self, code: str) -> Optional[str]:
        """6位纯代码 → ts_code (600519.SH)"""
        row = self.query_one('stock_basic', symbol=code)
        if row:
            return row['ts_code']
        if code.startswith('6') or code.startswith('9'):
            return f"{code}.SH"
        elif code.startswith('0') or code.startswith('3') or code.startswith('2'):
            return f"{code}.SZ"
        elif code.startswith('4') or code.startswith('8'):
            return f"{code}.BJ"
        return f"{code}.SH"

    # ════════════════════════════════════════════════════════════
    # 批量个股K线查询（方向分组用）
    # ════════════════════════════════════════════════════════════

    def query_stock_klines_batch(self, codes: List[str], limit: int = 60,
                                  adj: str = 'qfq') -> Dict[str, List[dict]]:
        """批量查询多只股票K线

        Args:
            codes: 6位纯代码列表 ['000062', '000066', ...]
            limit: 每只股票返回的K线数
            adj: 复权类型

        Returns:
            {code: [{date, open, close, high, low, volume}, ...], ...}
        """
        if not codes:
            return {}

        code_map = {}
        for code in codes:
            ts = self.code_to_ts_code(code)
            code_map[ts] = code

        ts_codes = list(code_map.keys())
        placeholders = ','.join(['%s'] * len(ts_codes))
        sql = (f"SELECT ts_code, trade_date, open, high, low, close, vol "
               f"FROM stock_daily WHERE ts_code IN ({placeholders}) "
               f"ORDER BY ts_code, trade_date DESC")
        rows = self.execute_raw(sql, ts_codes)

        raw_groups = {}
        for r in rows:
            ts = r['ts_code']
            if ts not in raw_groups:
                raw_groups[ts] = []
            raw_groups[ts].append(r)

        result = {}
        for ts, group in raw_groups.items():
            code = code_map.get(ts, ts)
            klines = group[:limit]
            if adj == 'qfq':
                klines = self._apply_qfq(klines, ts)
            else:
                klines = self._to_kline_format(klines)
            result[code] = klines

        return result

    # ════════════════════════════════════════════════════════════
    # 最新交易日查询
    # ════════════════════════════════════════════════════════════

    def get_last_stock_date(self) -> Optional[str]:
        """获取 stock_daily 表中最大 trade_date"""
        rows = self.execute_raw("SELECT max(trade_date) as last_date FROM stock_daily")
        return rows[0]['last_date'] if rows else None

    # ════════════════════════════════════════════════════════════
    # 指数查询
    # ════════════════════════════════════════════════════════════

    def get_index_klines(self, ts_code: str, limit: int = 500) -> List[dict]:
        """获取指数K线（按日期倒序）"""
        rows = self.query_many(
            'index_daily',
            where='ts_code=%s',
            params=[ts_code],
            order_by='trade_date DESC',
            limit=limit,
        )
        return [
            {
                'date': r['trade_date'],
                'open': r['open'],
                'close': r['close'],
                'high': r['high'],
                'low': r['low'],
                'volume': int(r['vol']) if r['vol'] else 0,
            }
            for r in rows
        ]

    # ════════════════════════════════════════════════════════════
    # 板块查询
    # ════════════════════════════════════════════════════════════

    def query_ths_code_by_name(self, name: str) -> Optional[str]:
        """中文板块名 → ts_code"""
        row = self.query_one('ths_index', name=name)
        return row['ts_code'] if row else None

    def query_ths_name_by_code(self, ts_code: str) -> Optional[str]:
        """ts_code → 中文板块名"""
        row = self.query_one('ths_index', ts_code=ts_code)
        return row['name'] if row else None

    def get_all_ths_codes(self) -> List[tuple]:
        """获取所有板块 (ts_code, name, type)"""
        rows = self.query_many('ths_index')
        return [(r['ts_code'], r['name'], r['type']) for r in rows]

    def get_sector_klines(self, sector_name: str, sector_type: str = 'industry',
                          limit: int = 120) -> List[dict]:
        """获取板块K线（按日期倒序）"""
        ts_code = self.query_ths_code_by_name(sector_name)
        if not ts_code:
            return []

        info = self.query_one('ths_index', ts_code=ts_code)
        if info:
            expected = 'I' if sector_type == 'industry' else 'N'
            if info['type'] != expected:
                return []

        rows = self.query_many(
            'ths_daily',
            where='ts_code=%s',
            params=[ts_code],
            order_by='trade_date DESC',
            limit=limit,
        )
        return [
            {
                'date': r['trade_date'],
                'open': r['open'],
                'close': r['close'],
                'high': r['high'],
                'low': r['low'],
                'volume': int(r['vol']) if r['vol'] else 0,
            }
            for r in rows
        ]

    # ════════════════════════════════════════════════════════════
    # 工具查询
    # ════════════════════════════════════════════════════════════

    def get_last_trade_date(self, table: str) -> Optional[str]:
        """获取指定表的最大交易日期"""
        rows = self.query_many(table, order_by='trade_date DESC', limit=1)
        return rows[0]['trade_date'] if rows else None

    # ════════════════════════════════════════════════════════════
    # 兼容：SQLite 下的一些操作
    # ════════════════════════════════════════════════════════════

    @property
    def conn(self):
        """兼容旧代码中直接访问 conn 的用法"""
        return self._get_conn()

    def close(self):
        """兼容旧代码"""
        pass
