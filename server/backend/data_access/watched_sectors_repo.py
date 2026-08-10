"""关注板块/概念仓库 — watched_sectors 表纯 MySQL CRUD。

按 user_id 隔离（对应 users.id）。所有函数必须 try/finally 关闭连接：
_get_conn() 每次新建连接，不关闭会耗尽 MySQL max_connections（历史 DoS 教训）。

用法:
    from backend.data_access.watched_sectors_repo import get_watched_by_user, add_watched, remove_watched
"""
from pymysql.cursors import DictCursor
from backend.core.logger import get_logger

log = get_logger(__name__)

FIELDS = 'id, user_id, sector_type, ts_code, name, created_at'


def _get_db():
    from backend.data_access.data_source import _get_tushare_db
    db = _get_tushare_db()
    if not db:
        raise RuntimeError('DB unavailable')
    return db


def get_watched_by_user(user_id: int) -> list:
    """当前用户关注的全部板块/概念行。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                f"SELECT {FIELDS} FROM watched_sectors WHERE user_id=%s "
                "ORDER BY sector_type, created_at",
                [user_id],
            )
            return list(cur.fetchall() or [])
    except Exception as e:
        log.warning('get_watched_by_user failed: %s', e)
        return []
    finally:
        conn.close()


def add_watched(user_id: int, sector_type: str, ts_code: str, name: str) -> bool:
    """新增关注；已存在（唯一键冲突）返回 False 不报错。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT IGNORE INTO watched_sectors "
                "(user_id, sector_type, ts_code, name) VALUES (%s, %s, %s, %s)",
                [user_id, sector_type, ts_code, name],
            )
            return cur.rowcount > 0
    except Exception as e:
        log.warning('add_watched failed: %s', e)
        return False
    finally:
        conn.close()


def remove_watched(user_id: int, ts_code: str) -> bool:
    """取消关注；不存在返回 False。"""
    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM watched_sectors WHERE user_id=%s AND ts_code=%s",
                [user_id, ts_code],
            )
            return cur.rowcount > 0
    except Exception as e:
        log.warning('remove_watched failed: %s', e)
        return False
    finally:
        conn.close()
