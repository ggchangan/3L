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

# 主线内标记缓存（10 分钟 TTL）：get_tracked_concept_names 是全量概念×个股映射循环，
# 每次请求重算约 1s+，用户反复开关页面会重复计算。
import time as _time
_IN_MAINLINE_CACHE = {}  # {sector_type: (expire_ts, frozenset(names))}
_IN_MAINLINE_TTL = 600


def _get_in_mainline_names(sector_type: str) -> set:
    """主线内板块名集合（行业=ths_daily 确认范围，概念=追踪概念门槛），带 TTL 缓存。"""
    now = _time.time()
    cached = _IN_MAINLINE_CACHE.get(sector_type)
    if cached and cached[0] > now:
        return cached[1]
    try:
        if sector_type == 'industry':
            from backend.data_access.data_layer import get_ths_daily_update_confirmation
            names = set(get_ths_daily_update_confirmation().get('industry_names', []))
        else:
            from backend.data_access.data_layer import get_tracked_concept_names
            names = set(get_tracked_concept_names(min_related_stocks=6))
    except Exception as e:
        log.warning('_get_in_mainline_names failed: %s', e)
        names = cached[1] if cached else set()
    _IN_MAINLINE_CACHE[sector_type] = (now + _IN_MAINLINE_TTL, frozenset(names))
    return names


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

    原子切换（无读-判-写竞态）：先 INSERT IGNORE，rowcount>0=新增关注；
    rowcount=0=已关注 → DELETE 取消。DB 异常上抛（防"假成功"）。

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

    added = add_watched(user_id, sector_type, ts_code, name)
    if added:
        return {'success': True, 'watched': True, 'name': name, 'type': sector_type}
    removed = remove_watched(user_id, ts_code)
    if not removed:
        return {'success': False, 'error': f'关注状态切换失败: {ts_code}'}
    return {'success': True, 'watched': False, 'name': name, 'type': sector_type}


def get_all_sectors(sector_type: str, user_id: int = None) -> dict:
    """可关注的板块/概念全列表（ths_index 同源）。

    返回: {'type': sector_type, 'count': N, 'in_mainline': M, 'sectors': [
        {name, ts_code, count, in_mainline, watched}
    ]}
    """
    if sector_type not in TYPE_MAP:
        return {'type': sector_type, 'count': 0, 'in_mainline': 0, 'sectors': []}
    ths_type = TYPE_MAP[sector_type]

    # 主线内标记：行业=ths_daily 确认范围，概念=追踪概念门槛（TTL 缓存）
    in_mainline_names = _get_in_mainline_names(sector_type)

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


def _compute_sector_strength(name: str, sector_type: str) -> dict:
    """关注但不在主线 all_ranked 的板块/概念：从本地 ths_daily 计算强度。

    场景：新概念（K线<20条，如 MLCC概念/玻璃基板）不在主线排名，
    或数据源停更被排除追踪（如 华为盘古）。只要有K线就展示强度，
    避免关注 Tab 大量「暂无数据」。

    ⚠️ 必须查本地 ths_daily（与主线 all_ranked 同源）：data_source 的
    get_sector_klines 走外部在线 API 链路（Tushare/同花顺直连），离线/限流时
    拿不到数据；且按名查不区分类型会串（家用电器 I/N 同名）。这里按
    name + type 精确匹配 ths_index → ths_daily。

    sector_type: 'industry' / 'concept'
    """
    from pymysql.cursors import DictCursor
    ths_type = TYPE_MAP.get(sector_type)
    if not ths_type:
        return {'name': name, 'matched': False}

    db = _get_db()
    conn = db._get_conn()
    try:
        with conn.cursor(DictCursor) as cur:
            cur.execute(
                "SELECT ts_code FROM ths_index WHERE name=%s AND type=%s LIMIT 1",
                [name, ths_type],
            )
            row = cur.fetchone()
            if not row:
                return {'name': name, 'matched': False}
            cur.execute(
                "SELECT trade_date, close FROM ths_daily WHERE ts_code=%s "
                "ORDER BY trade_date ASC",
                [row['ts_code']],
            )
            klines = list(cur.fetchall() or [])
    finally:
        conn.close()
    if len(klines) < 2:
        return {'name': name, 'matched': False}

    chg_1d = (klines[-1]['close'] / klines[-2]['close'] - 1) * 100
    chg_20d = None
    if len(klines) >= 20:
        chg_20d = (klines[-1]['close'] / klines[-20]['close'] - 1) * 100

    stage, vl_score = '--', 0
    try:
        if len(klines) >= 20:
            from backend.services.concept_wave_service import judge_concept_wave
            wave = judge_concept_wave(klines)
            stage = wave.get('stage', '--')
            vl_score = wave.get('vl_score', 0)
    except Exception:
        pass

    return {
        'name': name,
        'matched': True,
        'chg_1d': round(chg_1d, 2),
        'chg_20d': round(chg_20d, 2) if chg_20d is not None else None,
        'stage': stage,
        'vl_score': vl_score,
        'data_date': str(klines[-1].get('trade_date', '')),
    }


def build_watched_sector_items(mainline_data: dict, concept_mainline_data: dict,
                               user_id: int = None) -> dict:
    """组装复盘页「关注行业/关注概念」数据。

    - 命中 all_ranked 的条目带完整强度字段（与强度候选同格式）+ matched=True
    - 未命中的条目从 ths_daily 独立计算强度（见 _compute_sector_strength），
      完全无K线才 matched=False（前端显示"暂无数据"）
    - 排序与强度候选一致：按 chg_20d 降序；无20日数据（新概念/暂无数据）排最后
    """
    watched = get_watched_sectors(user_id)

    def _build(names, ranked, sector_type):
        by_name = {e['name']: e for e in ranked}
        items = []
        for n in names:
            entry = by_name.get(n)
            if entry is not None:
                items.append({**entry, 'matched': True})
            else:
                items.append(_compute_sector_strength(n, sector_type))
        # 排序：chg_20d 有值按降序（与强度候选相同）；无值(新概念/暂无数据)排最后
        items.sort(key=lambda x: (x.get('chg_20d') is None, -(x.get('chg_20d') or 0)))
        return items

    return {
        'industries': _build(watched.get('industries', []),
                             (mainline_data or {}).get('all_ranked', []),
                             'industry'),
        'concepts': _build(watched.get('concepts', []),
                           (concept_mainline_data or {}).get('all_ranked', []),
                           'concept'),
    }
