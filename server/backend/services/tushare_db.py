"""
Tushare SQLite 数据库封装层
- 建表(初始化)
- 批量写入(upsert)
- 查询封装(get_stock_daily, get_daily_basic, ...)
- 双token管理（由 config.py 提供）
"""
import os, sqlite3, json
from typing import Dict, List, Optional, Any
from datetime import datetime

from backend.config import TUSHARE_TOKEN, TUSHARE_TOKEN_HIGH, DATA_DIR


# ════════════════════════════════════════════════════════════
# CREATE TABLE 语句（9张表）
# ════════════════════════════════════════════════════════════

CREATE_TABLES = {
    'stock_daily': """
        CREATE TABLE IF NOT EXISTS stock_daily (
            ts_code     TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            pre_close   REAL,
            change      REAL,
            pct_chg     REAL,
            vol         REAL,
            amount      REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    'daily_basic': """
        CREATE TABLE IF NOT EXISTS daily_basic (
            ts_code         TEXT NOT NULL,
            trade_date      TEXT NOT NULL,
            close           REAL,
            turnover_rate   REAL,
            turnover_rate_f REAL,
            volume_ratio    REAL,
            pe              REAL,
            pe_ttm          REAL,
            pb              REAL,
            ps              REAL,
            pcf             REAL,
            total_mv        REAL,
            circ_mv         REAL,
            total_share     REAL,
            float_share     REAL,
            free_share      REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    'index_daily': """
        CREATE TABLE IF NOT EXISTS index_daily (
            ts_code     TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            pre_close   REAL,
            change      REAL,
            pct_chg     REAL,
            vol         REAL,
            amount      REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    'ths_daily': """
        CREATE TABLE IF NOT EXISTS ths_daily (
            ts_code     TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            open        REAL,
            high        REAL,
            low         REAL,
            close       REAL,
            pre_close   REAL,
            change      REAL,
            pct_chg     REAL,
            vol         REAL,
            amount      REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    'ths_index': """
        CREATE TABLE IF NOT EXISTS ths_index (
            ts_code     TEXT PRIMARY KEY,
            name        TEXT NOT NULL,
            count       INTEGER,
            list_date   TEXT,
            type        TEXT
        )
    """,
    'ths_member': """
        CREATE TABLE IF NOT EXISTS ths_member (
            ts_code     TEXT NOT NULL,
            con_code    TEXT NOT NULL,
            con_name    TEXT,
            weight      REAL,
            PRIMARY KEY (ts_code, con_code)
        )
    """,
    'stock_basic': """
        CREATE TABLE IF NOT EXISTS stock_basic (
            ts_code         TEXT PRIMARY KEY,
            symbol          TEXT,
            name            TEXT,
            area            TEXT,
            industry        TEXT,
            market          TEXT,
            list_date       TEXT,
            delist_date     TEXT,
            is_hs           TEXT
        )
    """,
    'adj_factor': """
        CREATE TABLE IF NOT EXISTS adj_factor (
            ts_code     TEXT NOT NULL,
            trade_date  TEXT NOT NULL,
            adj_factor  REAL,
            PRIMARY KEY (ts_code, trade_date)
        )
    """,
    'trade_cal': """
        CREATE TABLE IF NOT EXISTS trade_cal (
            exchange    TEXT NOT NULL,
            cal_date    TEXT NOT NULL,
            is_open     INTEGER,
            pretrade_date TEXT,
            PRIMARY KEY (exchange, cal_date)
        )
    """,
}

# 索引
CREATE_INDEXES = {
    'idx_stock_daily_ts_code': 'CREATE INDEX IF NOT EXISTS idx_stock_daily_ts_code ON stock_daily(ts_code)',
    'idx_stock_daily_date': 'CREATE INDEX IF NOT EXISTS idx_stock_daily_date ON stock_daily(trade_date)',
    'idx_daily_basic_ts_code': 'CREATE INDEX IF NOT EXISTS idx_daily_basic_ts_code ON daily_basic(ts_code)',
    'idx_adj_factor_ts_code': 'CREATE INDEX IF NOT EXISTS idx_adj_factor_ts_code ON adj_factor(ts_code)',
    'idx_ths_daily_ts_code': 'CREATE INDEX IF NOT EXISTS idx_ths_daily_ts_code ON ths_daily(ts_code)',
    'idx_ths_member_con_code': 'CREATE INDEX IF NOT EXISTS idx_ths_member_con_code ON ths_member(con_code)',
    'idx_ths_index_type': 'CREATE INDEX IF NOT EXISTS idx_ths_index_type ON ths_index(type)',
    'idx_index_daily_ts_code': 'CREATE INDEX IF NOT EXISTS idx_index_daily_ts_code ON index_daily(ts_code)',
}


class TushareDB:
    """Tushare SQLite 数据库封装

    Args:
        db_path: SQLite 文件路径，默认 data/tushare.db
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(DATA_DIR, 'tushare.db')
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=OFF")
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        """建表+建索引"""
        for sql in CREATE_TABLES.values():
            self.conn.execute(sql)
        for sql in CREATE_INDEXES.values():
            self.conn.execute(sql)
        self.conn.commit()

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

    def upsert_many_from_dicts(self, table: str, records: List[dict]) -> int:
        """从 dict 列表批量写入

        Args:
            table: 表名
            records: [{col: val}, ...]

        Returns:
            写入行数
        """
        if not records:
            return 0
        if table not in CREATE_TABLES:
            raise ValueError(f"未知表名: {table}")

        # 获取列名（取第一个记录的 keys）
        cols = list(records[0].keys())
        placeholders = ','.join(['?' for _ in cols])
        col_names = ','.join(cols)

        sql = f"INSERT OR REPLACE INTO {table} ({col_names}) VALUES ({placeholders})"

        # 组织数据
        rows_data = []
        for rec in records:
            row = []
            for col in cols:
                val = rec.get(col)
                # 处理 NaN / None
                if val is None or (isinstance(val, float) and (val != val)):  # NaN 检测
                    row.append(None)
                elif isinstance(val, (int, float)):
                    row.append(float(val) if isinstance(val, float) else val)
                else:
                    row.append(str(val) if val is not None else None)
            rows_data.append(tuple(row))

        self.conn.executemany(sql, rows_data)
        self.conn.commit()
        return len(rows_data)

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
        where = ' AND '.join([f"{k}=?" for k in conditions])
        vals = list(conditions.values())
        sql = f"SELECT * FROM {table} WHERE {where} LIMIT 1"
        cur = self.conn.execute(sql, vals)
        row = cur.fetchone()
        if row is None:
            return None
        return dict(row)

    def query_many(self, table: str, where: str = None,
                   params: list = None, order_by: str = None,
                   limit: int = None) -> List[dict]:
        """批量查询

        Args:
            table: 表名
            where: WHERE 子句（不含 WHERE 关键字）
            params: 参数列表
            order_by: ORDER BY 子句
            limit: LIMIT

        Returns:
            [{col: val}, ...]
        """
        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        cur = self.conn.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]

    # ════════════════════════════════════════════════════════════
    # 元数据查询
    # ════════════════════════════════════════════════════════════

    def get_table_names(self) -> List[str]:
        """获取所有表名"""
        cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        return [r[0] for r in cur.fetchall()]

    def get_index_names(self, table: str) -> List[str]:
        """获取指定表上的索引名"""
        cur = self.conn.execute(f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=? ORDER BY name", (table,))
        return [r[0] for r in cur.fetchall()]

    # ════════════════════════════════════════════════════════════
    # 个股日线查询
    # ════════════════════════════════════════════════════════════

    def query_stock_daily(self, ts_code: str, limit: int = 60) -> List[dict]:
        """查询个股日线（按日期倒序），返回兼容现有 Kline 合约

        输出格式: [{date, open, close, high, low, volume}, ...]
        """
        rows = self.query_many(
            'stock_daily',
            where='ts_code=?',
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

    def query_daily_basic(self, ts_code: str, trade_date: str) -> Optional[dict]:
        """查询每日指标（PE/PB/市值等）"""
        return self.query_one('daily_basic', ts_code=ts_code, trade_date=trade_date)

    # ════════════════════════════════════════════════════════════
    # 指数查询
    # ════════════════════════════════════════════════════════════

    def get_index_klines(self, ts_code: str, limit: int = 500) -> List[dict]:
        """获取指数K线（按日期倒序）

        输出格式: [{date, open, close, high, low, volume}, ...]
        """
        rows = self.query_many(
            'index_daily',
            where='ts_code=?',
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
        """获取板块K线（按日期倒序）

        Args:
            sector_name: 板块中文名
            sector_type: 'industry' 或 'concept'
            limit: 最多返回条数

        Returns:
            [{date, open, close, high, low, volume}, ...]
        """
        ts_code = self.query_ths_code_by_name(sector_name)
        if not ts_code:
            return []

        # 验证 type 匹配
        info = self.query_one('ths_index', ts_code=ts_code)
        if info:
            expected = 'I' if sector_type == 'industry' else 'N'
            if info['type'] != expected:
                return []

        rows = self.query_many(
            'ths_daily',
            where='ts_code=?',
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
        row = self.query_many(
            table,
            order_by='trade_date DESC',
            limit=1,
        )
        if row:
            return row[0].get('trade_date')
        return None

    # ════════════════════════════════════════════════════════════
    # Token 管理
    # ════════════════════════════════════════════════════════════

    @property
    def token_low(self) -> str:
        """2000积分账号（日常用）"""
        return TUSHARE_TOKEN

    @property
    def token_high(self) -> str:
        """15000积分账号（回填用，没有则回退到 low）"""
        return TUSHARE_TOKEN_HIGH or TUSHARE_TOKEN

    def close(self):
        self.conn.close()
