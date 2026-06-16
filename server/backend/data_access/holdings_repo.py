"""持仓 DB 仓库 — 纯 MySQL CRUD，不包含缓存/组装/回退逻辑

用法:
    from backend.data_access.holdings_repo import get_holdings, save_holdings

职责：原始数据的持久化，返回 dict list（与 DB 行一一对应）。
组装、缓存、回退由上层 data_layer.py 负责。
"""
from pymysql.cursors import DictCursor
from backend.core.logger import get_logger

log = get_logger(__name__)


def _get_db():
    """获取 DB 连接（内部懒加载，方便 repo 自包含）"""
    from backend.data_access.data_source import _get_tushare_db
    db = _get_tushare_db()
    if not db:
        raise RuntimeError('DB unavailable')
    return db


def get_holdings(user_id: int = 1) -> list:
    """从 DB 读取持仓列表

    Args:
        user_id: 用户 ID（默认 1）

    Returns:
        [{code, name, direction, target_ratio, cost_price?, stop_loss_price?, sector?}, ...]
        查询失败返回空列表
    """
    try:
        db = _get_db()
        conn = db._get_conn()
        try:
            with conn.cursor(DictCursor) as cur:
                cur.execute(
                    "SELECT code, name, direction, target_ratio, cost_price, stop_loss_price, sector "
                    "FROM holdings WHERE user_id=%s AND is_active=1 ORDER BY code",
                    [user_id]
                )
                rows = cur.fetchall()
                result = []
                for r in rows:
                    item = {
                        'code': r['code'],
                        'name': r['name'],
                        'direction': r['direction'],
                        'target_ratio': float(r['target_ratio']) if r['target_ratio'] else 0,
                    }
                    if r['cost_price'] is not None:
                        item['cost_price'] = float(r['cost_price'])
                    if r['stop_loss_price'] is not None:
                        item['stop_loss_price'] = float(r['stop_loss_price'])
                    if r.get('sector'):
                        item['sector'] = r['sector']
                    result.append(item)
                return result
        finally:
            conn.close()
    except Exception as e:
        log.error('holdings_repo.get_holdings 失败: %s', e)
        return []


def save_holdings(user_id: int, holdings_list: list) -> bool:
    """保存持仓列表到 DB（先删后插，全量替换）

    Args:
        user_id: 用户 ID
        holdings_list: [{code, name, direction, target_ratio, cost_price?, stop_loss_price?, sector?}, ...]

    Returns:
        True=成功, False=失败
    """
    try:
        db = _get_db()
        conn = db._get_conn()
        try:
            with conn.cursor() as cur:
                # 删除旧持仓
                cur.execute("DELETE FROM holdings WHERE user_id=%s", [user_id])
                # 插入新持仓
                for h in holdings_list:
                    cur.execute(
                        "INSERT INTO holdings(user_id, code, name, direction, target_ratio, "
                        "cost_price, stop_loss_price, sector) "
                        "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                        [
                            user_id,
                            h.get('code', ''),
                            h.get('name', ''),
                            h.get('direction', ''),
                            h.get('target_ratio', 0),
                            h.get('cost_price') or None,
                            h.get('stop_loss_price') or None,
                            h.get('sector', ''),
                        ]
                    )
                conn.commit()
        finally:
            conn.close()
        return True
    except Exception as e:
        log.error('holdings_repo.save_holdings 失败: %s', e)
        return False
