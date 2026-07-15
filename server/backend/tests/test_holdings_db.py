"""测试 — 持仓数据库操作（users + holdings 表）"""
import os, sys
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..', '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

import pytest
from backend.data_access.tushare_db import TushareDB, is_db_available


@pytest.fixture
def db():
    return TushareDB()


@pytest.mark.skipif(not is_db_available(), reason="MySQL not available in CI")
class TestHoldingsDB:

    def test_create_tables_and_default_user(self, db):
        """建表 + 默认用户后，应能查到 default 用户"""
        # 执行建表SQL
        db.execute_raw("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                display_name VARCHAR(100) DEFAULT '',
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        db.execute_raw("""
            CREATE TABLE IF NOT EXISTS holdings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                code VARCHAR(10) NOT NULL COMMENT '6位股票代码',
                name VARCHAR(50) NOT NULL COMMENT '股票名称',
                direction VARCHAR(100) NOT NULL DEFAULT '' COMMENT '方向，如 算力硬件.CPO',
                target_ratio DECIMAL(5,2) DEFAULT 0 COMMENT '目标仓位比例%',
                cost_price DECIMAL(10,2) DEFAULT NULL COMMENT '成本价',
                stop_loss_price DECIMAL(10,2) DEFAULT NULL COMMENT '止损价',
                sector VARCHAR(50) DEFAULT '' COMMENT '行业',
                is_active TINYINT(1) DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_user_code (user_id, code),
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        # 插入或忽略默认用户
        db.execute_raw(
            "INSERT IGNORE INTO users(username, display_name) VALUES(%s, %s)",
            ['default', '默认用户']
        )

        # 验证用户存在
        rows = db.execute_raw("SELECT id, username FROM users WHERE username=%s", ['default'])
        assert len(rows) == 1, "应有一个 default 用户"
        assert rows[0]['username'] == 'default'

        # 验证 holdings 表存在且可查询
        rows2 = db.execute_raw("SHOW TABLES LIKE 'holdings'")
        assert len(rows2) == 1, "holdings 表应存在"

    def test_insert_and_read_holdings(self, db):
        """插入持仓数据后应能正确读回"""
        # 清空测试数据
        db.execute_raw("DELETE FROM holdings WHERE user_id=999")
        db.execute_raw("DELETE FROM users WHERE username='test_user'")

        # 插入测试用户
        db.execute_raw(
            "INSERT INTO users(username, display_name) VALUES(%s, %s)",
            ['test_user', '测试用户']
        )
        rows = db.execute_raw("SELECT id FROM users WHERE username=%s", ['test_user'])
        uid = rows[0]['id']

        # 插入持仓
        db.execute_raw(
            "INSERT INTO holdings(user_id, code, name, direction, target_ratio, cost_price, stop_loss_price, sector) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
            [uid, '300620', '光库科技', '算力硬件.CPO', 6.86, 343.05, 288.21, '通信设备']
        )

        # 读取验证
        rows2 = db.execute_raw(
            "SELECT code, name, direction, target_ratio, cost_price, stop_loss_price, sector "
            "FROM holdings WHERE user_id=%s AND is_active=1",
            [uid]
        )
        assert len(rows2) == 1
        assert rows2[0]['code'] == '300620'
        assert rows2[0]['name'] == '光库科技'
        assert rows2[0]['direction'] == '算力硬件.CPO'
        assert float(rows2[0]['target_ratio']) == 6.86
        assert float(rows2[0]['cost_price']) == 343.05
        assert float(rows2[0]['stop_loss_price']) == 288.21

    def test_unique_constraint(self, db):
        """同一用户下不能重复插入同一股票"""
        rows = db.execute_raw("SELECT id FROM users WHERE username=%s", ['test_user'])
        uid = rows[0]['id']
        # 尝试插入相同 code
        with pytest.raises(Exception):
            db.execute_raw(
                "INSERT INTO holdings(user_id, code, name, direction, target_ratio) "
                "VALUES(%s, %s, %s, %s, %s)",
                [uid, '300620', '光库科技', '算力硬件.CPO', 5.0]
            )

    def test_cash_ratio_auto_calc(self, db):
        """现金比例 = 100% - sum(target_ratio) 可在应用层验证"""
        rows = db.execute_raw("SELECT id FROM users WHERE username=%s", ['test_user'])
        uid = rows[0]['id']
        rows2 = db.execute_raw(
            "SELECT SUM(target_ratio) as total FROM holdings WHERE user_id=%s AND is_active=1",
            [uid]
        )
        total = float(rows2[0]['total']) if rows2[0]['total'] else 0
        cash = round(100 - total, 2)
        assert cash >= 0, f"现金比例不应为负: {cash}"
