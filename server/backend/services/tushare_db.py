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

from backend.config import TUSHARE_TOKEN, TUSHARE_TOKEN_HIGH, TUSHARE_PROXY_URL, DATA_DIR


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

    # 表字段缓存: {table: set(column_names)}
    _COLUMN_CACHE: Dict[str, set] = {}

    def get_table_columns(self, table: str) -> set:
        """获取表的所有字段名（带缓存）"""
        if table not in self._COLUMN_CACHE:
            cur = self.conn.execute(f"PRAGMA table_info({table})")
            self._COLUMN_CACHE[table] = {r[1] for r in cur.fetchall()}
        return self._COLUMN_CACHE[table]

    def _ensure_columns(self, table: str, record: dict):
        """动态添加列：如果 record 包含表中不存在的字段，ALTER TABLE ADD COLUMN

        全量保留 API 返回字段，不丢数据。
        """
        existing = self.get_table_columns(table)
        new_cols = set(record.keys()) - existing
        for col in new_cols:
            # 跳过主键列（已经在CREATE TABLE中定义）
            if col in ('ts_code', 'trade_date', 'symbol', 'con_code', 'name',
                       'exchange', 'cal_date'):
                continue
            try:
                # TEXT 兼容各种类型
                self.conn.execute(f"ALTER TABLE {table} ADD COLUMN \"{col}\" TEXT")
            except sqlite3.OperationalError:
                pass  # 可能并发添加，忽略重复列错误
        if new_cols:
            # 刷新缓存
            self._COLUMN_CACHE[table] = existing | new_cols

    def upsert_many_from_dicts(self, table: str, records: List[dict]) -> int:
        """从 dict 列表批量写入（INSERT OR REPLACE），支持动态列

        Args:
            table: 表名
            records: dict 列表

        Returns:
            写入行数
        """
        if not records:
            return 0

        # 确保所有列已存在
        for rec in records:
            self._ensure_columns(table, rec)

        # 获取当前表的列集
        cols = self.get_table_columns(table)
        # 只保留表中存在的列，并按列名排序保证一致性
        col_names = sorted(cols & set(records[0].keys()))
        if not col_names:
            return 0

        placeholders = ','.join(['?'] * len(col_names))
        quoted_cols = ','.join([f'"{c}"' for c in col_names])
        sql = f"INSERT OR REPLACE INTO {table} ({quoted_cols}) VALUES ({placeholders})"

        batch = []
        for rec in records:
            batch.append(tuple(rec.get(c) for c in col_names))

        self.conn.executemany(sql, batch)
        self.conn.commit()
        return len(batch)

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
            limit: 返回行数上限

        Returns:
            dict 列表
        """
        columns = '*'
        if isinstance(order_by, dict):
            # 兼容旧调用：columns 通过 dict 传入
            columns = order_by.get('columns', '*')
            order_by = order_by.get('order_by')

        sql = f"SELECT {columns} FROM {table}"
        if where:
            sql += f" WHERE {where}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit:
            sql += f" LIMIT {limit}"
        cur = self.conn.execute(sql, params or [])
        return [dict(r) for r in cur.fetchall()]

    def execute_raw(self, sql: str, params: list = None) -> List[dict]:
        """执行原始 SQL 查询，返回 dict 列表"""
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
            where='ts_code=?',
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
        latest_adj = 最近日期的复权因子（归一化基准）
        """
        dates = [r['trade_date'] for r in rows]
        placeholders = ','.join(['?'] * len(dates))
        adj_rows = self.query_many(
            'adj_factor',
            where=f'ts_code=? AND trade_date IN ({placeholders})',
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
        """6位纯代码 → ts_code (600519.SH)

        先查 stock_basic 表（精确匹配），再尝试按规则拼接。
        """
        # 直接查表
        row = self.query_one('stock_basic', symbol=code)
        if row:
            return row['ts_code']

        # 按市场规则拼接（回退）
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

        替代 get_all_stocks() 中逐个从 JSON 取 K线的逻辑。
        内部按 code 分组，结果 {code: [{date, open, ...}, ...]，按日期倒序。

        Args:
            codes: 6位纯代码列表 ['000062', '000066', ...]
            limit: 每只股票返回的K线数
            adj: 复权类型

        Returns:
            {code: [{date, open, close, high, low, volume}, ...], ...}
        """
        if not codes:
            return {}

        # 批量转 ts_code
        code_map = {}  # {ts_code: code}
        for code in codes:
            ts = self.code_to_ts_code(code)
            code_map[ts] = code

        # 去重后查重复的 ts_code
        ts_codes = list(code_map.keys())
        placeholders = ','.join(['?'] * len(ts_codes))
        sql = (f"SELECT ts_code, trade_date, open, high, low, close, vol "
               f"FROM stock_daily WHERE ts_code IN ({placeholders}) "
               f"ORDER BY ts_code, trade_date DESC")
        rows = self.execute_raw(sql, ts_codes)

        # 按 ts_code 分组
        raw_groups: Dict[str, list] = {}
        for r in rows:
            ts = r['ts_code']
            if ts not in raw_groups:
                raw_groups[ts] = []
            raw_groups[ts].append(r)

        # 格式化 + 限制条数 + 前复权
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
        rows = self.query_many(table, order_by='trade_date DESC', limit=1)
        return rows[0]['trade_date'] if rows else None
