"""用户仓库 — users 表纯 MySQL CRUD。

用法:
    from backend.data_access.users_repo import get_user_by_username, create_user, ...

⚠️ 所有函数必须 try/finally 关闭连接：_get_conn() 每次新建连接，
不关闭会在登录/注册被刷时耗尽 MySQL max_connections（历史 DoS 教训）。
"""
from pymysql.cursors import DictCursor
from backend.core.logger import get_logger

log = get_logger(__name__)

USER_FIELDS = 'id, username, display_name, password_hash, password_salt, is_active'


def _get_db():
    from backend.data_access.data_source import _get_tushare_db
    db = _get_tushare_db()
    if not db:
        raise RuntimeError('DB unavailable')
    return db


def _row_to_user(r):
    if not r:
        return None
    return {
        'id': r['id'],
        'username': r['username'],
        'display_name': r['display_name'] or r['username'],
        'password_hash': r['password_hash'],
        'password_salt': r['password_salt'],
        'is_active': bool(r['is_active']),
    }


def get_user_by_username(username: str):
    """按用户名查用户（不区分大小写）。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                f"SELECT {USER_FIELDS} FROM users WHERE username=%s LIMIT 1",
                [username],
            )
            return _row_to_user(cur.fetchone())
    except Exception as e:
        log.warning('get_user_by_username failed: %s', e)
        return None
    finally:
        conn.close()


def get_user_by_id(user_id: int):
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                f"SELECT {USER_FIELDS} FROM users WHERE id=%s LIMIT 1",
                [user_id],
            )
            return _row_to_user(cur.fetchone())
    except Exception as e:
        log.warning('get_user_by_id failed: %s', e)
        return None
    finally:
        conn.close()


def username_exists(username: str) -> bool:
    return get_user_by_username(username) is not None


def create_user(username: str, password_hash: str, password_salt: str,
                display_name: str = '') -> dict:
    """创建用户，返回新用户 dict（不含敏感字段）。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (username, display_name, password_hash, password_salt) "
                "VALUES (%s, %s, %s, %s)",
                [username, display_name or username, password_hash, password_salt],
            )
            user_id = cur.lastrowid
        conn.commit()
        return {'id': user_id, 'username': username, 'display_name': display_name or username}
    finally:
        conn.close()


def update_password(user_id: int, password_hash: str, password_salt: str):
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s, password_salt=%s, "
                "updated_at=CURRENT_TIMESTAMP WHERE id=%s",
                [password_hash, password_salt, user_id],
            )
        conn.commit()
        return True
    except Exception as e:
        log.warning('update_password failed: %s', e)
        return False
    finally:
        conn.close()


def list_users():
    """列出所有活跃用户（不含密码字段）。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT id, username, display_name FROM users WHERE is_active=1 ORDER BY id"
            )
            return [
                {'id': r['id'], 'username': r['username'],
                 'display_name': r['display_name'] or r['username']}
                for r in cur.fetchall()
            ]
    except Exception as e:
        log.warning('list_users failed: %s', e)
        return []
    finally:
        conn.close()
