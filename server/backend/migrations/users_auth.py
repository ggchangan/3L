"""用户认证迁移：users 表加密码字段，预置 admin + user2~user5。

- users 表新增 password_hash / password_salt 列（幂等）
- default 用户(id=1)改名为 admin（保留其持仓/数据归属）
- 预置 admin + user2~user5 五个常用用户，默认密码 123456
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.data_access.tushare_db import TushareDB  # noqa: E402

DEFAULT_PASSWORD = '123456'

PRESET_USERS = [
    ('admin', '管理员'),
    ('user2', '用户2'),
    ('user3', '用户3'),
    ('user4', '用户4'),
    ('user5', '用户5'),
]


def _hash_password(password, salt):
    import hashlib
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest()


def migrate(db=None):
    db = db or TushareDB()
    added = []

    # 1. 加密码列（幂等）
    rows = db.execute_raw("SHOW COLUMNS FROM users")
    existing = {row['Field'] for row in rows}
    if 'password_hash' not in existing:
        db.execute_raw("ALTER TABLE users ADD COLUMN password_hash VARCHAR(128) NULL COMMENT '密码哈希(sha256+salt)'")
        added.append('password_hash')
    if 'password_salt' not in existing:
        db.execute_raw("ALTER TABLE users ADD COLUMN password_salt VARCHAR(32) NULL COMMENT '密码盐'")
        added.append('password_salt')

    # 2. default(id=1) → admin（保留存量持仓/自选股归属）
    db.execute_raw(
        "UPDATE users SET username='admin' WHERE id=1 AND username='default'"
    )

    # 3. 预置5用户（不存在才插入）
    for username, display_name in PRESET_USERS:
        row = db.execute_raw("SELECT id FROM users WHERE username=%s", [username])
        if not row:
            salt = os.urandom(16).hex()
            pwd_hash = _hash_password(DEFAULT_PASSWORD, salt)
            db.execute_raw(
                "INSERT INTO users (username, display_name, password_hash, password_salt) "
                "VALUES (%s, %s, %s, %s)",
                [username, display_name, pwd_hash, salt],
            )
            added.append(f'user:{username}')

    # 4. 停用残留的 default 空账号（测试遗留，无数据归属，不应可登录）
    db.execute_raw(
        "UPDATE users SET is_active=0 WHERE username='default'"
    )

    # 5. 预置用户没有密码的，补默认密码（只限白名单，避免给任意 NULL 密码用户开门）
    preset_names = {u[0] for u in PRESET_USERS}
    placeholders = ','.join(['%s'] * len(preset_names))
    rows = db.execute_raw(
        f"SELECT id, username FROM users WHERE username IN ({placeholders}) "
        "AND (password_hash IS NULL OR password_hash='')",
        list(preset_names),
    )
    for row in rows:
        salt = os.urandom(16).hex()
        pwd_hash = _hash_password(DEFAULT_PASSWORD, salt)
        db.execute_raw(
            "UPDATE users SET password_hash=%s, password_salt=%s WHERE id=%s",
            [pwd_hash, salt, row['id']],
        )
        added.append(f'password-fill:{row["username"]}')

    return added


def main():
    added = migrate()
    if added:
        print('users auth migration: ' + ', '.join(added))
    else:
        print('users auth migration ready (no changes)')


if __name__ == '__main__':
    main()
