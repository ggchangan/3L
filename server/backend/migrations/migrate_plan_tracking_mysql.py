"""plan_tracking 迁移：SQLite → MySQL（一次性，幂等）

背景：plan_tracking 原本用独立 SQLite 文件（data/private/plan_tracking.db），
多用户登录后无 user_id 维度，跨用户混写。本脚本：

1. 在 MySQL 建 plan_records 表（含 user_id 列，UNIQUE(user_id, date, code)）
2. 将 SQLite 存量 1184 条记录迁入 MySQL（归属 admin=1）
3. 迁移完成后将 SQLite 文件重命名为 .migrated.bak（不删除，可追溯）

用法:
    cd server && python backend/migrations/migrate_plan_tracking_mysql.py

幂等：表已存在且已有数据时跳过写入；SQLite 文件不存在时跳过导入。
"""
import os
import sqlite3
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import DATA_DIR  # noqa: E402
from backend.data_access.tushare_db import TushareDB  # noqa: E402

SQLITE_PATH = os.path.join(DATA_DIR, 'private', 'plan_tracking.db')

# 与 SQLite 旧表结构一致的 MySQL 建表（额外加 user_id 用户维度）
PLAN_RECORDS_DDL = """
CREATE TABLE IF NOT EXISTS plan_records (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    user_id         INT NOT NULL DEFAULT 1 COMMENT '用户ID（多用户隔离）',
    date            VARCHAR(10) NOT NULL COMMENT '计划日期 YYYY-MM-DD',
    code            VARCHAR(10) NOT NULL COMMENT '6位股票代码',
    name            VARCHAR(50) DEFAULT '',
    source          VARCHAR(20) DEFAULT '',
    action          VARCHAR(50) DEFAULT '',
    reason          VARCHAR(200) DEFAULT '',
    structure       VARCHAR(50) DEFAULT '',
    stage           VARCHAR(50) DEFAULT '',
    buy_point       VARCHAR(50) DEFAULT '',
    is_main         TINYINT DEFAULT 0,
    priority        VARCHAR(20) DEFAULT '',
    stop_loss       DECIMAL(12,4) DEFAULT NULL,
    stop_loss_pct   DECIMAL(8,4) DEFAULT NULL,
    plan_close      DECIMAL(12,4) DEFAULT NULL,
    next_date       VARCHAR(10) DEFAULT NULL,
    next_open       DECIMAL(12,4) DEFAULT NULL,
    next_close      DECIMAL(12,4) DEFAULT NULL,
    next_high       DECIMAL(12,4) DEFAULT NULL,
    next_low        DECIMAL(12,4) DEFAULT NULL,
    change_pct      DECIMAL(10,4) DEFAULT NULL,
    max_gain        DECIMAL(10,4) DEFAULT NULL,
    max_loss        DECIMAL(10,4) DEFAULT NULL,
    hit_stop_loss   TINYINT DEFAULT 0,
    exit_date       VARCHAR(10) DEFAULT NULL,
    exit_price      DECIMAL(12,4) DEFAULT NULL,
    exit_reason     VARCHAR(50) DEFAULT '',
    holding_days    INT DEFAULT NULL,
    max_price       DECIMAL(12,4) DEFAULT NULL,
    min_price       DECIMAL(12,4) DEFAULT NULL,
    result          VARCHAR(20) DEFAULT '',
    executed        TINYINT DEFAULT NULL,
    user_note       VARCHAR(500) DEFAULT '',
    created_at      DATETIME DEFAULT NULL,
    updated_at      DATETIME DEFAULT NULL,
    UNIQUE KEY uk_user_date_code (user_id, date, code),
    KEY idx_date (date),
    KEY idx_result (result),
    KEY idx_source (source),
    KEY idx_buy_point (buy_point),
    KEY idx_structure (structure, stage),
    KEY idx_is_main (is_main)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作计划追踪（多用户）'
"""


def _to_mysql_value(v):
    """SQLite 值 → MySQL 兼容值（None 保持 None；datetime 字符串原样传）"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    return str(v)


def migrate():
    db = TushareDB()
    results = []

    # 1. 建表（幂等）
    db.execute_raw(PLAN_RECORDS_DDL)
    results.append('table: plan_records ready')

    # 2. 检查 MySQL 是否已有数据
    rows = db.execute_raw("SELECT COUNT(*) AS c FROM plan_records")
    existing = rows[0]['c'] if rows else 0
    if existing > 0:
        results.append(f'skip-import: MySQL 已有 {existing} 条记录')
    else:
        # 3. 从 SQLite 导入（若存在）
        if os.path.isfile(SQLITE_PATH):
            conn = sqlite3.connect(SQLITE_PATH)
            conn.row_factory = sqlite3.Row
            try:
                src = conn.execute("SELECT * FROM plan_records").fetchall()
                col_info = conn.execute("PRAGMA table_info(plan_records)").fetchall()
                cols = [c[1] for c in col_info]  # 第2列才是列名
                imported = 0
                # 单事务导入：中途失败整体回滚，避免残留部分数据导致下次跳过导入
                mconn = db._get_conn()
                try:
                    mconn.autocommit(False)
                    with mconn.cursor() as cur:
                        for r in src:
                            values = [_to_mysql_value(r[c]) for c in cols]
                            # 排除 id（自增），date/code 必需
                            insert_cols = [c for c in cols if c != 'id']
                            insert_vals = [values[cols.index(c)] for c in insert_cols]
                            placeholders = ', '.join(['%s'] * len(insert_cols))
                            col_list = ', '.join(insert_cols)
                            cur.execute(
                                f"INSERT INTO plan_records ({col_list}) VALUES ({placeholders})",
                                insert_vals,
                            )
                            imported += 1
                    mconn.commit()
                except Exception:
                    mconn.rollback()
                    raise
                finally:
                    mconn.close()
                results.append(f'import: SQLite → MySQL {imported} 条（归 admin=1）')
            finally:
                conn.close()
            # 重命名 SQLite（保留可追溯）
            bak = SQLITE_PATH + '.migrated.bak'
            if not os.path.exists(bak):
                os.rename(SQLITE_PATH, bak)
                results.append(f'sqlite: {os.path.basename(SQLITE_PATH)} → {os.path.basename(bak)}')
            else:
                results.append('sqlite: .migrated.bak 已存在，跳过重命名')
        else:
            results.append('sqlite: 文件不存在，跳过导入')

    return results


def main():
    for line in migrate():
        print(line)


if __name__ == '__main__':
    main()
