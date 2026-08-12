#!/usr/bin/env python3
"""
唯一数据更新脚本 — 支持收盘当日更新与次日完整更新
范围 = 个股K线 + 中证全指 + 行业/概念板块日K线
所有文件I/O通过 backend.data_access.data_layer 完成

用法:
    python -m backend.core.update_stock_data --phase close
    python -m backend.core.update_stock_data --phase full
"""

import argparse, json, os, subprocess, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# ⚠️ 注意: file 在 server/backend/core/ 下
# dirname×1=core/  ×2=backend/  ×3=server/（backend 包所在位置）
from backend.core.config import DATA_DIR, ALL_CODES_PATH, CONCEPT_LIST_PATH
from backend.data_access.data_layer import (
    load_all_stocks_uncached,
    get_last_updated,
    get_industry_map,
    save_industry_map,
    save_all_stocks,
    save_index_data,
    get_index_data,
    fetch_stock_klines_from_db,
    get_stock_names_from_db,
    get_stock_daily_latest_date,
    get_tracked_concept_names,
    get_tracked_concept_universe,
)
from backend.data_access.data_layer import (
    get_concept_list,
    get_stock_concept_map,
    save_concept_list,
    save_stock_concept_map,
)
from backend.data_access.data_layer import (
    get_ths_index_names,
    fetch_ths_daily_klines_akshare,
    build_industry_map_from_db,
    build_concept_maps_from_db,
    tushare_fetch_daily_incremental,
    get_ths_daily_update_coverage,
    retry_missing_ths_concepts,
    retry_missing_ths_industries,
    save_ths_daily_update_confirmation,
    refresh_sector_close_snapshot,
)

CACHE_DIR = os.path.join(DATA_DIR, '.cache')
ISOLATED_STAGE_MARKER = '__3L_STAGE_RESULT__='

# native 子进程（akshare/pandas 等 C 扩展）被信号终止是低概率环境问题，
# 重跑同阶段即可恢复；非信号错误（退出码非0/缺标记）是代码缺陷，不重试。
STAGE_RETRY_INTERVAL = 30
STAGE_MAX_ATTEMPTS = 3


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {msg}')


# ════════════════════════════════════════════════════════════════
# 个股
# ════════════════════════════════════════════════════════════════

def _get_stock_name(code):
    """从 Tushare/MySQL 股票基础信息获取名称。"""
    try:
        from backend.data_access.data_layer import get_stock_names_from_db
        return get_stock_names_from_db([code]).get(code)
    except Exception:
        log('获取股票名称失败')
        pass
    return None


def _flatten_stocks(sector_map):
    """{sector: {code: [klines]}} → {code: {sector, klines, name}}"""
    result = {}
    for sector, codes in sector_map.items():
        if not isinstance(codes, dict):
            continue
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            result[code] = {'sector': sector, 'klines': klines, 'name': name}
    return result


def _all_users_stock_codes():
    """所有活跃用户自选股的并集（K线数据全局共享，各用户盯盘都有行情）"""
    from backend.data_access.users_repo import list_users
    from backend.core.config import get_user_config_path
    import json as _json
    codes = set()
    for u in list_users():
        try:
            with open(get_user_config_path('watchlist.json', u['id']), encoding='utf-8') as f:
                wl_data = _json.load(f)
            for s in wl_data.get('stocks', []):
                c = (s.get('code') or '')[-6:]
                if c:
                    codes.add(c)
        except Exception:
            continue
    return sorted(codes)


def update_stocks():
    """更新个股K线 — 从 stock_daily DB 批量拉取，不再用 mootdx"""
    codes = _all_users_stock_codes()
    if not codes:
        log('⚠️  自选股列表为空，跳过个股更新')
        return (0, 0, 0)

    industry_map = get_industry_map()
    existing_sector_map = load_all_stocks_uncached()
    existing = _flatten_stocks(existing_sector_map)
    last_updated = get_last_updated()
    db_latest = get_stock_daily_latest_date()

    # 判断是否需要更新
    need_update = False
    for code in codes:
        if code not in existing:
            need_update = True
            break
    if not need_update and last_updated and db_latest:
        if db_latest <= last_updated.replace('-', ''):
            log('✅  个股数据已最新，跳过')
            return (0, 0, 0)

    # 从 stock_daily 批量拉取最新60天K线
    klines_map = fetch_stock_klines_from_db(codes, limit=60)
    name_map = get_stock_names_from_db(codes)

    # 清除缓存
    try:
        os.remove(os.path.join(CACHE_DIR, 'all_stocks.json'))
    except (FileNotFoundError, OSError):
        pass

    updated = 0
    new_added = 0
    names_fixed = 0

    for code in codes:
        klines = klines_map.get(code, [])
        if not klines:
            log(f'  ⚠️ {code}: 无K线数据')
            continue

        if code in existing:
            existing_dates = {k['date'] for k in existing[code]['klines']}
            has_new = any(k['date'] not in existing_dates for k in klines)
            if has_new:
                existing[code]['klines'] = sorted(klines, key=lambda x: x['date'])[-60:]
                updated += 1
        else:
            im = industry_map.get(code, {})
            if isinstance(im, dict):
                name = im.get('name', '') or name_map.get(code, '')
            else:
                name = name_map.get(code, '')
            if not name:
                name = _get_stock_name(code)
                if name:
                    names_fixed += 1

            klines = sorted(klines, key=lambda x: x['date'])[-60:]
            for r in klines:
                r['name'] = name or code

            ths_industry = '未知'
            if isinstance(im, dict) and im.get('ths_industry'):
                ths_industry = im['ths_industry']

            existing[code] = {
                'sector': ths_industry,
                'klines': klines,
                'name': name or code,
            }
            new_added += 1

    # 组装 sector_map
    sector_map = {}
    for code, info in existing.items():
        if code in codes:
            sec = info.get('sector', '未知')
            if sec not in sector_map:
                sector_map[sec] = {}
            klines = info['klines']
            name = info.get('name', '')
            if name and klines:
                for k in klines:
                    k['name'] = name
            klines.sort(key=lambda x: x['date'])
            while len(klines) > 60:
                klines.pop(0)
            sector_map[sec][code] = klines

    save_all_stocks(sector_map, last_updated=db_latest)

    # ── 生成 all_stocks_60d.json 缓存（性能优化，避免每次297次MySQL查询）──
    try:
        _cache_path = os.path.join(DATA_DIR, 'all_stocks_60d.json')
        _cache_data = {
            'stocks': sector_map,
            'last_updated': db_latest or datetime.now().strftime('%Y-%m-%d'),
        }
        with open(_cache_path, 'w', encoding='utf-8') as _f:
            json.dump(_cache_data, _f, ensure_ascii=False)
        _stock_count = sum(len(c) for c in sector_map.values())
        log(f'📁  缓存: 已写入 {os.path.basename(_cache_path)} ({len(sector_map)}个板块, {_stock_count}只股票)')
    except Exception as _e:
        log(f'⚠️  缓存写入失败: {_e}')

    stats = f'{updated}只更新, {new_added}只新增, {names_fixed}只补名'
    log(f'📈  个股: {stats}')
    return (updated, new_added, names_fixed)


# ════════════════════════════════════════════════════════════════
# 指数（中证全指 000985 + 上证 000001 + 科创50 000688）
# ════════════════════════════════════════════════════════════════

def update_index():
    """从 index_daily DB 重建指数缓存（替代 akshare→JSON 旧路径）

    经 Phase 1 的 Tushare 增量拉取，index_daily DB 已有最新数据。
    这里直接从 DB 读取并保存到缓存。
    """
    data = get_index_data()
    indices = data.get('indices', {})
    if not indices:
        log('⚠️  指数数据为空')
        return (0, '')

    total = 0
    last_date = data.get('last_updated', '')
    for code, info in indices.items():
        klines = info.get('klines', [])
        name = info.get('name', code)
        total += len(klines)
        if klines:
            log(f'📈  {name}: {len(klines)}条, 最新{klines[0]["date"]}')

    save_index_data(data)
    log(f'📈  指数合计: {total}条, 最新{last_date}')
    return (total, last_date)


# ════════════════════════════════════════════════════════════════
# 板块（行业+概念）数据源：同花顺 THS
# ════════════════════════════════════════════════════════════════


def update_sectors():
    """更新行业+概念板块日K线

    数据源：
    - 行业（industries）：同花顺 THS（stock_board_industry_summary_ths）
    - 概念（concepts）：同花顺 THS（stock_board_concept_info_ths）

    失败率>50%告警，全部失败抛异常
    """
    import warnings
    warnings.filterwarnings('ignore')

    # 按“目标交易日”而非“当前是否周末”决定更新。
    # 同花顺的周五正式板块日线在周六才齐，因此周六是必需的回填时窗。
    from backend.data_access.data_source import get_last_completed_trading_day
    today = get_last_completed_trading_day()
    log(f'📋  目标日期: {today}')

    # 板块清单同步（Tushare 15000分）：新板块自动进表；失败不阻断主流程
    try:
        from backend.data_access.data_source import (
            sync_ths_index_from_tushare, sync_ths_member_from_tushare,
        )
        synced = sync_ths_index_from_tushare()
        if synced:
            log(f'📋  板块清单同步: {synced} 条')
        members = sync_ths_member_from_tushare()
        if members:
            log(f'📋  概念成分同步: {members} 条')
    except Exception as e:
        log(f'⚠️  板块清单同步失败(不阻断): {e}')

    # ── 确定追踪中的概念 ──
    try:
        concept_universe = get_tracked_concept_universe(
            min_related_stocks=6,
            reference_date=today,
        )
        tracked_concepts = concept_universe['names']
        log(f'📋  追踪概念: {len(tracked_concepts)}个（自选股关联≥6只）')
        excluded = concept_universe.get('excluded', {})
        if excluded:
            reason_counts = {}
            for detail in excluded.values():
                reason = detail.get('reason', 'unknown')
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
            log(f'🧹  概念主线排除: {len(excluded)}个 {reason_counts}')
    except Exception as e:
        log(f'⚠️  计算追踪概念失败: {e}，回退到全量更新')
        tracked_concepts = set()

    # ── 构建要更新的板块列表（通过 data_layer 获取行业名 + 追踪中的概念）──
    names_to_update = []
    try:
        industry_names = get_ths_index_names('I')
        ind_today = [n for n, _ in industry_names]
        for name in ind_today:
            names_to_update.append((name, 'industry'))
        if tracked_concepts:
            for name in tracked_concepts:
                names_to_update.append((name, 'concept'))
    except Exception as e:
        log(f'⚠️  获取板块列表失败: {e}')
        names_to_update = []

    # ── 强制纳入用户关注的行业/概念（无论是否满足追踪门槛）──
    # 关注列表是用户明确指定的重点板块，必须每天增量更新；
    # 否则新概念（关联自选股<6）或数据停更概念永远不会进入更新范围，形成死循环。
    # ⚠️ 解析一律以 ts_code 为准（LEFT JOIN ths_index 取 canonical name）：
    # watched_sectors.name 是关注时刻快照，Tushare 改名后（如 数据中心→数据中心(AIDC)）
    # 快照过期，按名字匹配会静默跳过；ths_index 无匹配的跳过且不进门禁分母。
    watched_concepts = set()  # 尽力而为集合：缺失不拉低 coverage 门禁（防停更概念误伤）
    try:
        from backend.data_access.watched_sectors_repo import get_all_watched
        from backend.data_access.data_source import get_ths_index_canonical_names
        watched_rows = get_all_watched()
        existing = set(names_to_update)
        if watched_rows:
            ts_codes = [r.get('ts_code') for r in watched_rows if r.get('ts_code')]
            canonical = get_ths_index_canonical_names(ts_codes)
            type_map = {'I': 'industry', 'N': 'concept'}
            for row in watched_rows:
                info = canonical.get(row.get('ts_code', ''))
                if not info:
                    log(f'⚠️  关注板块跳过（ths_index 无匹配）: {row.get("ts_code")} '
                        f'{row.get("name")}')
                    continue
                wtype = type_map.get(info.get('type', ''))
                wname = info.get('name', '')
                if not wtype or not wname:
                    continue
                if (wname, wtype) not in existing:
                    names_to_update.append((wname, wtype))
                    existing.add((wname, wtype))
                # 仅「追踪集合之外」的关注概念才是尽力而为（optional）：
                # 追踪概念（自选股关联≥6）必须严格门禁，缺失要暴露；
                # 额外强加的关注概念（新概念/停更概念）缺失不拉低门禁。
                if wtype == 'concept' and wname not in tracked_concepts:
                    watched_concepts.add(wname)
            log(f'⭐  关注板块强制纳入: {len(watched_rows)}个（含新概念/停更概念）')
    except Exception as e:
        log(f'⚠️  关注板块纳入失败(不阻断): {e}')

    ind_saved = len(ind_today) if 'ind_today' in dir() else 0
    con_saved = len(tracked_concepts)

    # ── 写 K 线到 ths_daily DB（通过 data_layer）──
    try:
        written, requested = fetch_ths_daily_klines_akshare(names_to_update, today)
        log(f'📊  板块K线写入DB: {written}条 (请求{requested}个板块)')
    except Exception as e:
        log(f'🚨 板块K线写入DB失败: {e}')
        import traceback
        for line in traceback.format_exc().splitlines():
            log(f'  {line}')

    coverage = get_ths_daily_update_coverage(
        names_to_update, today, optional_concepts=watched_concepts,
    )
    missing_industries = coverage.get('industry', {}).get('missing', [])
    if missing_industries:
        try:
            retry = retry_missing_ths_industries(today, missing_industries)
            log(
                '🔁  缺失行业同源重试: '
                f'{retry.get("covered", 0)}/{retry.get("requested", 0)}'
            )
            if retry.get('covered', 0):
                coverage = get_ths_daily_update_coverage(
                    names_to_update, today, optional_concepts=watched_concepts,
                )
        except Exception as exc:
            log(f'⚠️  缺失行业同源重试失败，保留部分正式状态: {exc}')
    missing_concepts = coverage.get('concept', {}).get('missing', [])
    if missing_concepts:
        try:
            retry = retry_missing_ths_concepts(today, missing_concepts)
            log(
                '🔁  缺失概念同源重试: '
                f'{retry.get("covered", 0)}/{retry.get("requested", 0)}'
            )
            if retry.get('covered', 0):
                coverage = get_ths_daily_update_coverage(
                    names_to_update, today, optional_concepts=watched_concepts,
                )
        except Exception as exc:
            log(f'⚠️  缺失概念同源重试失败，保留部分正式状态: {exc}')
    ind_cov = coverage.get('industry', {})
    con_cov = coverage.get('concept', {})
    log(
        '📋  板块目标日覆盖: '
        f'行业{ind_cov.get("covered", 0)}/{ind_cov.get("expected", 0)}, '
        f'概念{con_cov.get("covered", 0)}/{con_cov.get("expected", 0)}'
    )
    if coverage.get('optional_missing'):
        log(f'💤  关注概念尽力而为未覆盖(不阻塞): {coverage["optional_missing"]}')
    if not coverage.get('ready'):
        missing = coverage.get('missing', [])[:10]
        raise RuntimeError(f'板块数据覆盖不足，缺失示例: {missing}')
    save_ths_daily_update_confirmation(today, coverage)

    log(f'📈  板块: 行业{ind_saved}个, 概念{con_saved}个 (K线已写入DB)')
    return (ind_saved, con_saved)


# ════════════════════════════════════════════════════════════════
# 行业映射（Tushare/MySQL ths_member + ths_index）
# ════════════════════════════════════════════════════════════════

def _normalize_industry(name):
    """去掉申万二级分类的'Ⅱ'后缀（如'电机Ⅱ'→'电机'）"""
    if not name:
        return name
    return name.replace('Ⅱ', '').strip()

def update_industry_map():
    """从 ths_member + ths_index DB 重建行业映射

    通过 data_layer → data_source 访问 DB，不直接调 TushareDB。
    一只股票可能属于多个同花顺行业，取名称最长的。
    输出写入 stock_industry_map.json。
    """
    result = build_industry_map_from_db()
    if result:
        save_industry_map(result)
        log(f'🏭  行业映射: DB重建完成 ({len(result)}只)')
    return len(result)


# ════════════════════════════════════════════════════════════════
# 概念板块映射（stock→concept + concept→stocks）
# ════════════════════════════════════════════════════════════════

def update_concept_maps():
    """从 ths_index + ths_member DB 重建概念映射

    通过 data_layer → data_source 访问 DB，不直接调 TushareDB。
    输出：concept_list.json + stock_concept_map.json
    """
    concept_list, stock_concept_data = build_concept_maps_from_db()
    if concept_list or stock_concept_data:
        save_concept_list(concept_list)
        save_stock_concept_map(stock_concept_data)
        concept_cnt = sum(1 for c in concept_list.values() if c.get('stocks')) if concept_list else 0
        log(f'  ✅ 概念映射: {concept_cnt}个有成分股, {len(stock_concept_data)}只有概念')
    else:
        log('⚠️  概念映射DB重建失败或为空')
    return (len(concept_list) if concept_list else 0,
            len(stock_concept_data) if stock_concept_data else 0)


# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# 概念板块K线增量更新（仅拉取追踪中的概念）
# ════════════════════════════════════════════════════════════════

def update_concept_klines():
    """
    从 sector_daily.json 提取概念板块K线，按 tracked_concepts 筛选保存。
    目前 sector_daily.json 已由 refresh_sectors.py 全量更新，此处只做提取。

    未来可优化为：只拉取追踪中的概念（减少请求量）
    """
    t0 = time.time()
    # 从 DB 读概念K线
    from backend.data_access.data_layer import get_ths_industry_klines
    concepts_kline = get_ths_industry_klines(ths_type='N')
    if not concepts_kline:
        log('⚠️  板块数据中无概念K线')
        return 0

    log(f'📊  概念K线: {len(concepts_kline)}个有数据')
    log(f'    ✅ 概念K线就绪 ({time.time()-t0:.0f}s)')
    return len(concepts_kline)


# ════════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════
# Tushare 增量拉取 — 将最新交易日数据写入 DB
# ════════════════════════════════════════════════════════════════

def _fetch_tushare_daily_incremental():
    """Tushare 增量拉取最新交易日数据到 stock_daily + index_daily"""
    tushare_fetch_daily_incremental()


def _ensure_all_stock_codes():
    """确保搜索使用的全量 A 股代码表存在。"""
    if os.path.isfile(ALL_CODES_PATH):
        return
    log('📋  生成 all_stock_codes.json（全量A股代码表）...')
    try:
        import akshare as ak
        df = ak.stock_info_a_code_name()
        codes = dict(zip(df['code'], df['name']))
        with open(ALL_CODES_PATH, 'w', encoding='utf-8') as f:
            json.dump(codes, f, ensure_ascii=False)
        log(f'✅  已生成 ({len(codes)}只)')
    except Exception as e:
        log(f'⚠️  生成失败: {e}')


def _daily_data_freshness(target_date):
    """检查收盘复盘必需的个股和全部指数是否已到目标交易日。"""
    stock_date = str(get_stock_daily_latest_date() or '').replace('-', '')
    index_data = get_index_data()
    indices = index_data.get('indices', {})
    index_dates = {}
    for code, info in indices.items():
        klines = info.get('klines', [])
        index_dates[code] = str(klines[0].get('date', '') if klines else '').replace('-', '')

    expected_index_codes = {'000001', '000688', '000985', '399006'}
    missing_indices = sorted(
        code for code in expected_index_codes
        if index_dates.get(code, '') < target_date
    )
    ready = stock_date >= target_date and not missing_indices
    return {
        'ready': ready,
        'target_date': target_date,
        'stock_date': stock_date,
        'index_dates': index_dates,
        'missing_indices': missing_indices,
    }


def _market_temperature_data_freshness(target_date):
    """市场温度辅助表允许降级展示，但未到齐时收盘任务应继续重试。"""
    try:
        from backend.data_access.data_source import (
            _daily_table_count, _expected_stock_daily_count, _get_tushare_db,
        )
        db = _get_tushare_db()
        if not db:
            return {'ready': False, 'stock_count': 0, 'adj_count': 0, 'limit_count': 0}
        stock_count = _daily_table_count(
            db, 'stock_daily', target_date,
            'pct_chg IS NOT NULL AND high IS NOT NULL AND low IS NOT NULL',
        )
        expected = _expected_stock_daily_count(db, target_date)
        adj_count = _daily_table_count(db, 'adj_factor', target_date, 'adj_factor IS NOT NULL')
        limit_count = _daily_table_count(
            db, 'stk_limit', target_date, 'up_limit IS NOT NULL AND down_limit IS NOT NULL',
        )
        return {
            'ready': bool(expected and stock_count >= expected * 0.98
                          and adj_count >= expected * 0.98
                          and limit_count >= expected * 0.98),
            'stock_count': stock_count,
            'expected_stock_count': expected,
            'adj_count': adj_count,
            'limit_count': limit_count,
        }
    except Exception as exc:
        return {'ready': False, 'stock_count': 0, 'adj_count': 0, 'limit_count': 0, 'error': str(exc)}


def _refresh_review_cache(target_date):
    """同步生成复盘缓存，保证命令退出前页面已经可用。"""
    from backend.services.review_service import (
        compute_review_real_time, review_refresh_file_lock, save_review_data,
        save_review_snapshot,
    )
    from backend.services.market_temperature_service import invalidate_market_temperature_cache

    date_str = datetime.strptime(target_date, '%Y%m%d').strftime('%Y-%m-%d')
    log(f'━━━ 生成当日复盘缓存 ({date_str}) ━━━')
    with review_refresh_file_lock():
        # 日线/复权/涨跌停或历史窗口可能刚被回补，不复用旧温度。
        invalidate_market_temperature_cache(target_date)
        review = compute_review_real_time(date_str)
        review['cache_generated_at'] = datetime.now().isoformat(timespec='seconds')
        save_review_data(review)
        save_review_snapshot(review)
    log('✅  当日复盘缓存已生成')


def _clear_mainline_cache():
    """删除依赖板块日期/快照的主线计算缓存。"""
    cache_path = os.path.join(DATA_DIR, '.cache', 'mainline_full.json')
    if os.path.isfile(cache_path):
        os.remove(cache_path)
        log(f'🧹  已清除过期缓存: {os.path.basename(cache_path)}')


def run_close_phase():
    """收盘阶段：只更新当日可获得的数据，并生成复盘缓存。

    返回 True 表示个股、全部指数和当日板块预估快照均已就绪；False 表示
    仍有数据源未就绪，调用方可以稍后重试。即使板块快照暂缺，也会先生成
    一份沿用最近确认主线的降级复盘，保证页面可用。
    """
    from backend.data_access.data_source import get_last_completed_trading_day

    target_date = get_last_completed_trading_day()
    log(f'🌆 收盘更新目标交易日: {target_date}')
    if target_date != datetime.now().strftime('%Y%m%d'):
        log('⏭️  今天不是交易日，跳过收盘更新')
        return True
    _fetch_tushare_daily_incremental()

    freshness = _daily_data_freshness(target_date)
    if not freshness['ready']:
        log(
            '⏳ 当日数据尚未到齐: '
            f'个股={freshness["stock_date"] or "无"}, '
            f'缺少指数={freshness["missing_indices"]}'
        )
        return False

    _ensure_all_stock_codes()
    log('━━━ 行业映射 ━━━')
    update_industry_map()
    log('━━━ 概念映射 ━━━')
    update_concept_maps()
    log('━━━ 个股更新 ━━━')
    update_stocks()
    log('━━━ 指数更新 ━━━')
    update_index()
    snapshot_ready = False
    try:
        snapshot = refresh_sector_close_snapshot(target_date)
        stats = snapshot.get('coverage', {}).get('industry', {})
        log(
            '📊  收盘板块快照: '
            f'{stats.get("covered", 0)}/{stats.get("expected", 0)} '
            f'({stats.get("ratio", 0):.1%})'
        )
        snapshot_ready = True
    except Exception as exc:
        log(f'⚠️  收盘板块快照未就绪，先生成降级复盘并继续重试: {exc}')
    _clear_mainline_cache()
    _refresh_review_cache(target_date)
    temperature_freshness = _market_temperature_data_freshness(target_date)
    if not temperature_freshness['ready']:
        log(
            '⏳ 市场温度辅助数据尚未到齐: '
            f'stock={temperature_freshness.get("stock_count", 0)}, '
            f'adj_factor={temperature_freshness.get("adj_count", 0)}, '
            f'stk_limit={temperature_freshness.get("limit_count", 0)}'
        )
    return snapshot_ready and temperature_freshness['ready']


def run_full_phase():
    """原有完整管线，供次日 06:00 补齐板块数据。"""
    t0 = time.time()

    # 全局关闭 tqdm 进度条（在 akshare 首次导入前生效）
    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    # ── Tushare 增量拉取（先确保 stock_daily / index_daily 有最新数据）──
    _fetch_tushare_daily_incremental()

    _ensure_all_stock_codes()

    # 行业映射（全量更新，～1-2秒）
    log('━━━ 行业映射 ━━━')
    update_industry_map()

    # 概念映射（东方财富 f103 + 名称映射表，~1秒）
    log('━━━ 概念映射 ━━━')
    update_concept_maps()

    # 阶段1: 个股
    log('━━━ 个股更新 ━━━')
    s1 = update_stocks()

    # 指数与板块依赖不同的网络/原生库，分别放进干净子进程。生产曾出现
    # 指数阶段结束时 native segfault，不能让它直接跳过后续正式板块补数。
    log('━━━ 指数更新 ━━━')
    failures = []
    try:
        s2 = _run_full_stage_isolated('index')
    except Exception as exc:
        s2 = (0, '')
        failures.append(f'指数更新: {exc}')
        log(f'🚨 指数更新子进程失败，继续尝试板块更新: {exc}')

    log('━━━ 板块更新 ━━━')
    try:
        s3 = _run_full_stage_isolated('sectors')
    except Exception as exc:
        s3 = (0, 0)
        failures.append(f'板块更新: {exc}')
        log(f'🚨 板块更新子进程失败: {exc}')

    if any(item.startswith('板块更新:') for item in failures):
        # 正式板块失败时不能生成伪装成完整的复盘。
        raise RuntimeError('; '.join(failures))

    # 板块数据更新后，清除依赖的主线缓存（避免页面读到过期数据）
    _clear_mainline_cache()

    from backend.data_access.data_source import get_last_completed_trading_day
    _refresh_review_cache(get_last_completed_trading_day())

    if failures:
        # 板块已恢复且复盘已刷新；仍用非零退出码暴露指数子进程异常。
        raise RuntimeError('; '.join(failures))

    elapsed = time.time() - t0
    log(f'{"━"*30}')
    log(f'📊 汇总: 个股{s1[0]+s1[1]}只变动 | 指数{s2[0]}条新增 | 板块{s3[0]+s3[1]}只变动')
    log(f'⏱️  总耗时 {elapsed:.1f}s')


def _run_full_stage_isolated(stage, max_attempts=None, retry_interval=None):
    """在全新解释器中运行易受 native 依赖影响的阶段并取回结构化结果。

    native 子进程被信号终止（如 akshare/pandas 的 SIGSEGV）时自动重跑同阶段；
    退出码非0或缺少结果标记属于代码缺陷，直接失败不重试。
    """
    max_attempts = STAGE_MAX_ATTEMPTS if max_attempts is None else max_attempts
    retry_interval = STAGE_RETRY_INTERVAL if retry_interval is None else retry_interval

    last_detail = ''
    for attempt in range(1, max_attempts + 1):
        completed = subprocess.run(
            [sys.executable, '-m', 'backend.core.update_stock_data', '--isolated-stage', stage],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            capture_output=True, text=True,
        )
        for line in completed.stdout.splitlines():
            if not line.startswith(ISOLATED_STAGE_MARKER):
                print(line, flush=True)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end='', flush=True)
        marker = next(
            (line[len(ISOLATED_STAGE_MARKER):] for line in reversed(completed.stdout.splitlines())
             if line.startswith(ISOLATED_STAGE_MARKER)),
            '',
        )
        if completed.returncode != 0:
            signal = -completed.returncode if completed.returncode < 0 else None
            detail = f'被信号 {signal} 终止' if signal else f'退出码 {completed.returncode}'
            if signal is not None and attempt < max_attempts:
                log(
                    f'⚠️ {stage} 子进程{detail}，'
                    f'{retry_interval}s 后重试 (第{attempt}/{max_attempts - 1}次重试)'
                )
                time.sleep(retry_interval)
                continue
            raise RuntimeError(f'{stage} 子进程{detail}')
        if not marker:
            raise RuntimeError(f'{stage} 子进程缺少结果标记')
        result = json.loads(marker)
        return tuple(result)
    raise RuntimeError(f'{stage} 子进程{last_detail}')


def main(argv=None):
    parser = argparse.ArgumentParser(description='3L 数据更新管线')
    parser.add_argument(
        '--phase', choices=('close', 'full'), default='full',
        help='close=收盘后当日复盘；full=次日完整更新（默认）',
    )
    parser.add_argument('--max-attempts', type=int, default=1, help='close 阶段最大尝试次数')
    parser.add_argument('--retry-interval', type=int, default=900, help='重试间隔秒数')
    parser.add_argument('--isolated-stage', choices=('index', 'sectors'), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    if args.isolated_stage:
        result = update_index() if args.isolated_stage == 'index' else update_sectors()
        print(f'{ISOLATED_STAGE_MARKER}{json.dumps(result, ensure_ascii=False)}', flush=True)
        return 0

    if args.phase == 'full':
        run_full_phase()
        return 0

    attempts = max(1, args.max_attempts)
    for attempt in range(1, attempts + 1):
        log(f'收盘更新尝试 {attempt}/{attempts}')
        try:
            if run_close_phase():
                return 0
        except Exception as exc:
            log(f'⚠️  收盘更新异常，将按计划重试: {type(exc).__name__}: {exc}')
        if attempt < attempts:
            log(f'将在 {args.retry_interval} 秒后重试')
            time.sleep(max(0, args.retry_interval))
    log('🚨 达到最大重试次数，当日数据仍未到齐')
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
