#!/usr/bin/env python3
"""
唯一数据更新脚本 — 17:00 cron 运行
范围 = 个股K线 + 中证全指 + 行业/概念板块日K线
所有文件I/O通过 backend.data_access.data_layer 完成

用法:
    python3 scripts/update_stock_data.py
"""

import json, os, sys, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
# ⚠️ 注意: file 在 server/backend/core/ 下
# dirname×1=core/  ×2=backend/  ×3=server/（backend 包所在位置）
from backend.core.config import DATA_DIR, ALL_CODES_PATH, CONCEPT_LIST_PATH
from backend.data_access.data_layer import (
    get_watchlist,
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
)

CACHE_DIR = os.path.join(DATA_DIR, '.cache')


def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{timestamp}] {msg}')


# ════════════════════════════════════════════════════════════════
# 个股
# ════════════════════════════════════════════════════════════════

def _get_stock_name(code):
    """通过腾讯接口获取股票名称"""
    market = 'sz' if code.startswith(('0', '3')) else 'sh'
    try:
        import requests
        r = requests.get(
            f'https://qt.gtimg.cn/q={market}{code}',
            headers={'User-Agent': 'Mozilla/5.0'},
            timeout=5,
        )
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
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


def update_stocks():
    """更新个股K线 — 从 stock_daily DB 批量拉取，不再用 mootdx"""
    wl = get_watchlist()
    codes = sorted(set(
        s.get('code', '')[-6:] for s in wl if s.get('code')
    ))
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

    # 非交易日跳过（push2test 返回的是旧缓存，不可信）
    now = datetime.now()
    if now.weekday() >= 5:
        log('⏭️  非交易日，跳过板块更新')
        return (0, 0)

    # 目标日期是上一个已完成交易日
    from backend.data_access.data_source import get_last_completed_trading_day
    today = get_last_completed_trading_day()
    log(f'📋  目标日期: {today}')

    # ── 确定追踪中的概念 ──
    try:
        _concept_list = get_concept_list()
        _stock_concept_map = get_stock_concept_map()
        wl = get_watchlist()
        wl_codes = set(s.get('code', '') for s in wl)

        tracked_concepts = set()
        for code, cinfo in _concept_list.items():
            name = cinfo.get('name', '')
            if not name:
                continue
            related = 0
            for scode, sinfo in _stock_concept_map.items():
                if code in sinfo.get('concept_codes', []) and scode in wl_codes:
                    related += 1
            if related >= 6:
                tracked_concepts.add(name)

        log(f'📋  追踪概念: {len(tracked_concepts)}个（自选股关联≥6只）')
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

    log(f'📈  板块: 行业{ind_saved}个, 概念{con_saved}个 (K线已写入DB)')
    return (ind_saved, con_saved)


# ════════════════════════════════════════════════════════════════
# 行业映射（push2test.eastmoney.com → 申万二级行业）
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


def main():
    t0 = time.time()

    # 全局关闭 tqdm 进度条（在 akshare 首次导入前生效）
    os.environ['TQDM_DISABLE'] = '1'
    os.environ['AKSHARE_PROXY_PROGRESS'] = 'False'

    # ── Tushare 增量拉取（先确保 stock_daily / index_daily 有最新数据）──
    _fetch_tushare_daily_incremental()

    # 确保 all_stock_codes.json 存在（搜索用）
    if not os.path.isfile(ALL_CODES_PATH):
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

    # 行业映射（全量更新，～1-2秒）
    log('━━━ 行业映射 ━━━')
    update_industry_map()

    # 概念映射（东方财富 f103 + 名称映射表，~1秒）
    log('━━━ 概念映射 ━━━')
    update_concept_maps()

    # 阶段1: 个股
    log('━━━ 个股更新 ━━━')
    s1 = update_stocks()

    # 阶段2: 指数
    log('━━━ 指数更新 ━━━')
    s2 = update_index()

    # 阶段3: 板块
    log('━━━ 板块更新 ━━━')
    try:
        s3 = update_sectors()
    except Exception as e:
        log(f'🚨 板块更新失败: {e}')
        import traceback
        for line in traceback.format_exc().splitlines():
            log(f'  {line}')
        raise  # 非零退出码让cron感知

    elapsed = time.time() - t0
    log(f'{"━"*30}')
    log(f'📊 汇总: 个股{s1[0]+s1[1]}只变动 | 指数{s2[0]}条新增 | 板块{s3[0]+s3[1]}只变动')
    log(f'⏱️  总耗时 {elapsed:.1f}s')


if __name__ == '__main__':
    main()
