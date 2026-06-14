#!/usr/bin/env python3
"""从 SQLite 迁移全部数据到 MySQL"""
import os, sys, sqlite3, time
import pymysql

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
SQLITE_PATH = os.path.join(DATA_DIR, 'tushare.db')

MYSQL_CFG = {
    'host': 'localhost',
    'user': 'tushare',
    'password': 'tushare_pass',
    'database': 'tushare',
    'charset': 'utf8mb4',
}

TABLES = [
    'stock_basic',
    'trade_cal',
    'ths_index',
    'ths_member',
    'stock_daily',
    'daily_basic',
    'adj_factor',
    'index_daily',
    'ths_daily',
]

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def get_sqlite_columns(cursor, table):
    cursor.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cursor.fetchall()]

def get_mysql_columns(cursor, table):
    cursor.execute(f"SHOW COLUMNS FROM `{table}`")
    return [r[0] for r in cursor.fetchall()]

def migrate_table(table):
    sqlite = sqlite3.connect(SQLITE_PATH)
    sqlite.row_factory = sqlite3.Row
    sc = sqlite.cursor()

    mysql = pymysql.connect(**MYSQL_CFG)
    mc = mysql.cursor()

    sqlite_cols = get_sqlite_columns(sc, table)
    mysql_cols = get_mysql_columns(mc, table)
    common_cols = [c for c in sqlite_cols if c in mysql_cols]

    if not common_cols:
        log(f"  {table}: 无公共列，跳过")
        sc.close(); mc.close(); sqlite.close(); mysql.close()
        return 0

    sc.execute(f"SELECT * FROM {table}")
    rows = sc.fetchall()
    total = len(rows)
    if total == 0:
        log(f"  {table}: 空表")
        sc.close(); mc.close(); sqlite.close(); mysql.close()
        return 0

    col_names = sorted(common_cols)
    placeholders = ','.join(['%s'] * len(col_names))
    quoted_cols = ','.join([f'`{c}`' for c in col_names])
    sql = f"REPLACE INTO `{table}` ({quoted_cols}) VALUES ({placeholders})"

    batch_size = 5000
    inserted = 0
    batch = []
    for row in rows:
        vals = tuple(row[c] for c in col_names)
        batch.append(vals)
        if len(batch) >= batch_size:
            mc.executemany(sql, batch)
            mysql.commit()
            inserted += len(batch)
            batch = []
            log(f"  {table}: {inserted}/{total} ({inserted*100//total}%)")

    if batch:
        mc.executemany(sql, batch)
        mysql.commit()
        inserted += len(batch)

    sc.close(); mc.close(); sqlite.close(); mysql.close()
    log(f"  {table}: ✅ {inserted} 行迁移完成")
    return inserted


if __name__ == '__main__':
    if not os.path.isfile(SQLITE_PATH):
        print(f"SQLite 文件不存在: {SQLITE_PATH}")
        sys.exit(1)

    log(f"SQLite: {SQLITE_PATH}")
    log(f"MySQL: {MYSQL_CFG['host']}/{MYSQL_CFG['database']}")
    log(f"开始迁移 {len(TABLES)} 张表...\n")

    started = time.time()
    totals = {}
    for table in TABLES:
        log(f"迁移 {table} ...")
        totals[table] = migrate_table(table)
        log("")

    elapsed = time.time() - started
    log("=" * 50)
    log(f"迁移完成！耗时 {elapsed:.0f} 秒")
    for t, n in totals.items():
        log(f"  {t}: {n} 行")
    total_rows = sum(totals.values())
    log(f"  总计: {total_rows} 行")
