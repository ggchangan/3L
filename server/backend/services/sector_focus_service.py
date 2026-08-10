"""关注板块/概念服务 — watched_sectors 表（MySQL）业务组装。

- 关注列表按 user_id 隔离（thread-local 无上下文默认 admin=1）
- 板块/概念元数据来自 ths_index（MySQL），与主线计算同源
- 复盘页「关注行业/关注概念」数据由 build_watched_sector_items() 组装
"""
from backend.core.auth import get_current_user_id
from backend.core.logger import get_logger

log = get_logger(__name__)

# 与 ths_index.type 对齐：industry=I / concept=N
TYPE_MAP = {'industry': 'I', 'concept': 'N'}
REVERSE_TYPE_MAP = {'I': 'industry', 'N': 'concept'}


def _get_db():
    from backend.data_access.data_source import _get_tushare_db
    db = _get_tushare_db()
    if not db:
        raise RuntimeError('DB unavailable')
    return db


def get_watched_sectors(user_id: int = None) -> dict:
    """当前用户关注列表 → {'industries': [名称], 'concepts': [名称]}。"""
    from backend.data_access.watched_sectors_repo import get_watched_by_user
    uid = user_id if user_id is not None else get_current_user_id()
    rows = get_watched_by_user(uid)
    result = {'industries': [], 'concepts': []}
    for r in rows:
        st = r.get('sector_type')
        if st == 'industry':
            result['industries'].append(r.get('name', ''))
        elif st == 'concept':
            result['concepts'].append(r.get('name', ''))
    return result


def get_watched_ts_codes(user_id: int = None) -> set:
    """当前用户已关注的全部 ts_code 集合（列表页勾选状态用）。"""
    from backend.data_access.watched_sectors_repo import get_watched_by_user
    uid = user_id if user_id is not None else get_current_user_id()
    return {r['ts_code'] for r in get_watched_by_user(uid)}


def toggle_watched_sector(user_id: int, sector_type: str, ts_code: str) -> dict:
    """关注/取消关注（切换）。ts_code 需在 ths_index 中存在且 type 匹配。

    返回: {'success': True, 'watched': bool, 'name': str, 'type': sector_type}
    """
    from backend.data_access.watched_sectors_repo import add_watched, remove_watched
    if sector_type not in TYPE_MAP:
        return {'success': False, 'error': f'未知类型: {sector_type}'}
    ths_type = TYPE_MAP[sector_type]

    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts_code, name FROM ths_index WHERE ts_code=%s AND type=%s LIMIT 1",
                [ts_code, ths_type],
            )
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return {'success': False, 'error': f'板块不存在或类型不匹配: {ts_code}'}
    name = row['name']

    watched_codes = get_watched_ts_codes(user_id)
    if ts_code in watched_codes:
        removed = remove_watched(user_id, ts_code)
        return {'success': True, 'watched': False, 'name': name, 'type': sector_type, 'removed': removed}
    added = add_watched(user_id, sector_type, ts_code, name)
    return {'success': True, 'watched': True, 'name': name, 'type': sector_type, 'added': added}


def get_all_sectors(sector_type: str, user_id: int = None) -> dict:
    """可关注的板块/概念全列表（ths_index 同源）。

    返回: {'type': sector_type, 'count': N, 'in_mainline': M, 'sectors': [
        {name, ts_code, count, in_mainline, watched}
    ]}
    """
    if sector_type not in TYPE_MAP:
        return {'type': sector_type, 'count': 0, 'in_mainline': 0, 'sectors': []}
    ths_type = TYPE_MAP[sector_type]

    # 主线内标记：行业=ths_daily 确认范围，概念=追踪概念门槛
    in_mainline_names = set()
    try:
        if sector_type == 'industry':
            from backend.data_access.data_layer import get_ths_daily_update_confirmation
            in_mainline_names = set(get_ths_daily_update_confirmation().get('industry_names', []))
        else:
            from backend.data_access.data_layer import get_tracked_concept_names
            in_mainline_names = set(get_tracked_concept_names(min_related_stocks=6))
    except Exception as e:
        log.warning('get_all_sectors in_mainline 标记失败: %s', e)

    watched_codes = get_watched_ts_codes(user_id)

    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts_code, name, count FROM ths_index WHERE type=%s ORDER BY name",
                [ths_type],
            )
            rows = list(cur.fetchall() or [])
    finally:
        conn.close()

    sectors = [{
        'name': r['name'],
        'ts_code': r['ts_code'],
        'count': r.get('count') or 0,
        'in_mainline': r['name'] in in_mainline_names,
        'watched': r['ts_code'] in watched_codes,
    } for r in rows]
    return {
        'type': sector_type,
        'count': len(sectors),
        'in_mainline': sum(1 for s in sectors if s['in_mainline']),
        'sectors': sectors,
    }


def build_watched_sector_items(mainline_data: dict, concept_mainline_data: dict,
                               user_id: int = None) -> dict:
    """组装复盘页「关注行业/关注概念」数据。

    从行业/概念 all_ranked 中按关注名称匹配：
    - 匹配到的条目带完整强度字段（与强度候选同格式）+ matched=True
    - 关注了但主线无数据的条目 {name, matched=False}（前端显示"暂无数据"）
    """
    watched = get_watched_sectors(user_id)

    def _match(names, ranked):
        by_name = {e['name']: e for e in ranked}
        items = []
        for n in names:
            entry = by_name.get(n)
            if entry is not None:
                items.append({**entry, 'matched': True})
            else:
                items.append({'name': n, 'matched': False})
        return items

    return {
        'industries': _match(watched.get('industries', []),
                             (mainline_data or {}).get('all_ranked', [])),
        'concepts': _match(watched.get('concepts', []),
                           (concept_mainline_data or {}).get('all_ranked', [])),
    }
