"""幂等增加持仓建仓信号与止损生命周期字段。"""
from backend.data_access.tushare_db import TushareDB


COLUMNS = {
    'entry_signal_type': "VARCHAR(32) NULL COMMENT '建仓买点类型'",
    'entry_signal_date': "DATE NULL COMMENT '建仓信号日期'",
    'entry_anchor_price': "DECIMAL(10,2) NULL COMMENT '初始止损锚点'",
    'stop_loss_source': "VARCHAR(32) NULL COMMENT '当前止损来源'",
    'original_stop_loss_price': "DECIMAL(10,2) NULL COMMENT '建仓初始止损'",
}


def migrate(db=None):
    db = db or TushareDB()
    rows = db.execute_raw("SHOW COLUMNS FROM holdings")
    existing = {row['Field'] for row in rows}
    added = []
    for name, definition in COLUMNS.items():
        if name not in existing:
            db.execute_raw(f"ALTER TABLE holdings ADD COLUMN {name} {definition}")
            added.append(name)
    return added


def main():
    added = migrate()
    print('holdings migration ready' + (f': added {", ".join(added)}' if added else ''))


if __name__ == '__main__':
    main()
