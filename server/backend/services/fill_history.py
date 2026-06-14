#!/usr/bin/env python3
"""
Tushare 数据回填脚本 — 双账号策略

用法:
    # 首次全量回填（用15000分 + 代理）
    python3 fill_history.py --full

    # 日常增量更新（用2000分 + 官方直连）
    python3 fill_history.py --daily

    # 指定时间段
    python3 fill_history.py --start=20240101 --end=20260601

    # 只拉指定表
    python3 fill_history.py --tables=stock_daily,daily_basic

双账号策略:
    15000分高积分账号 → 走代理回填历史数据（ths_daily 需独立权限）
    2000分普通账号 → 官方直连做日常增量（ths_daily 回退 akshare）
"""

import sys, os, time, argparse

# path fix
_test_dir = os.path.dirname(__file__)
_server_root = os.path.join(_test_dir, '..')
for p in [_server_root]:
    if p not in sys.path:
        sys.path.insert(0, p)

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from backend.config import TUSHARE_TOKEN, TUSHARE_TOKEN_HIGH, TUSHARE_PROXY_URL, DATA_DIR
from backend.services.tushare_db import TushareDB
from backend.core.logger import get_logger

log = get_logger(__name__)

# 回填起止日期
DEFAULT_START = '20240101'
DEFAULT_END = datetime.now().strftime('%Y%m%d')

# 每批次休息秒数（防限流）
FETCH_SLEEP = 0.6
COMMIT_INTERVAL = 5000  # 每 N 行提交一次


def create_proxy_api():
    """创建走代理的 15000 分 API 客户端"""
    from tushare.pro import client as _ts_client
    import tushare as ts
    if TUSHARE_PROXY_URL:
        _ts_client.DataApi._DataApi__http_url = TUSHARE_PROXY_URL
    return ts.pro_api(TUSHARE_TOKEN_HIGH or TUSHARE_TOKEN)


def create_direct_api():
    """创建官方直连的 2000 分 API 客户端"""
    import tushare as ts
    return ts.pro_api(TUSHARE_TOKEN)


def log_progress(msg: str, total: int = None, current: int = None):
    """输出进度日志"""
    if total and current is not None:
        pct = f" {current}/{total} ({current*100//total}%)"
    else:
        pct = ""
    log.info(f"[fill_history] {msg}{pct}")
    print(f"  {msg}{pct}")


def safe_fetch(fn, retries=3, delay=1.0, **kwargs):
    """带重试的 Tushare 请求
    
    Args:
        fn: pro.xxx 函数引用
        retries: 最大重试次数
        delay: 重试间隔（秒）
        **kwargs: 传给 fn 的参数
    Returns:
        DataFrame 或 None
    """
    last_err = None
    for attempt in range(retries):
        try:
            df = fn(**kwargs)
            if df is not None:
                return df
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                log.warning("  请求失败(attempt %d): %s，%ds后重试", attempt + 1, e, delay)
                time.sleep(delay)
            else:
                log.error("  请求失败已耗尽重试: %s", e)
    return None


def fetch_and_upsert(db: TushareDB, api, table: str, fn_name: str, **kwargs) -> int:
    """拉取 Tushare 数据并 upsert 到 DB

    Args:
        db: TushareDB 实例
        api: tushare pro_api 实例
        table: 目标表名
        fn_name: API 方法名（如 'daily'）
        **kwargs: 方法参数

    Returns:
        写入行数
    """
    fn = getattr(api, fn_name, None)
    if fn is None:
        log.error("API 方法 %s 不存在", fn_name)
        return 0

    df = safe_fetch(fn, **kwargs)
    if df is None or df.empty:
        return 0

    rows = db.upsert_many(table, df)
    time.sleep(FETCH_SLEEP)
    return rows


def batch_by_date(start: str, end: str, step_days: int = 1):
    """按日期分段"""
    s = datetime.strptime(start, '%Y%m%d')
    e = datetime.strptime(end, '%Y%m%d')
    d = s
    while d <= e:
        yield d.strftime('%Y%m%d')
        d += timedelta(days=step_days)


# ════════════════════════════════════════════════════════════
# 各表回填任务
# ════════════════════════════════════════════════════════════

def fill_stock_basic(db: TushareDB, api):
    """全量股票列表（一次性）"""
    log_progress("填充 stock_basic ...")
    rows = fetch_and_upsert(db, api, 'stock_basic', 'stock_basic')
    log_progress(f"  stock_basic 写入 {rows} 行")
    return rows


def fill_trade_cal(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """交易日历"""
    log_progress(f"填充 trade_cal ({start}~{end}) ...")
    rows = fetch_and_upsert(db, api, 'trade_cal', 'trade_cal',
                            exchange='SSE', start_date=start, end_date=end)
    log_progress(f"  trade_cal 写入 {rows} 行")
    return rows


def fill_stock_daily(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """个股日线 — 按日期逐天拉取"""
    log_progress(f"填充 stock_daily ({start}~{end}) ...")
    total = 0
    dates = list(batch_by_date(start, end))
    count = len(dates)

    for i, trade_date in enumerate(dates):
        rows = fetch_and_upsert(db, api, 'stock_daily', 'daily',
                                trade_date=trade_date)
        if rows:
            total += rows
        if (i + 1) % 10 == 0:
            log_progress(f"  stock_daily 进度", total=count, current=i + 1)

    log_progress(f"  stock_daily 完成，共写入 {total} 行")
    return total


def fill_daily_basic(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """每日指标 — 按日期逐天拉取"""
    log_progress(f"填充 daily_basic ({start}~{end}) ...")
    total = 0
    dates = list(batch_by_date(start, end))
    count = len(dates)

    for i, trade_date in enumerate(dates):
        rows = fetch_and_upsert(db, api, 'daily_basic', 'daily_basic',
                                trade_date=trade_date)
        if rows:
            total += rows
        if (i + 1) % 10 == 0:
            log_progress(f"  daily_basic 进度", total=count, current=i + 1)

    log_progress(f"  daily_basic 完成，共写入 {total} 行")
    return total


def fill_index_daily(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """指数日线"""
    log_progress(f"填充 index_daily ({start}~{end}) ...")
    index_codes = [
        '000001.SH',  # 上证指数
        '000688.SH',  # 科创50
        '000985.SH',  # 中证全指(用 000985.CSI 或 000985.SH)
        '399006.SZ',  # 创业板指
    ]
    total = 0
    for code in index_codes:
        rows = fetch_and_upsert(db, api, 'index_daily', 'index_daily',
                                ts_code=code, start_date=start, end_date=end)
        if rows:
            log_progress(f"  {code}: {rows} 行")
            total += rows
        time.sleep(FETCH_SLEEP)

    log_progress(f"  index_daily 完成，共写入 {total} 行")
    return total


def fill_adj_factor(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """复权因子 — 按日期逐天拉取（比按股票代码快10倍）"""
    log_progress(f"填充 adj_factor ({start}~{end}) ...")
    total = 0
    dates = list(batch_by_date(start, end))
    count = len(dates)

    for i, trade_date in enumerate(dates):
        rows = fetch_and_upsert(db, api, 'adj_factor', 'adj_factor',
                                trade_date=trade_date)
        if rows:
            total += rows
        if (i + 1) % 20 == 0:
            log_progress(f"  adj_factor 进度", total=count, current=i + 1)

    log_progress(f"  adj_factor 完成，共写入 {total} 行")
    return total


def fill_ths_index(db: TushareDB, api):
    """同花顺板块列表（一次性）"""
    log_progress("填充 ths_index ...")

    # ths_index API 不支持按 type 过滤，一次拉取所有类型
    df = safe_fetch(api.ths_index)
    if df is not None and not df.empty:
        rows = db.upsert_many('ths_index', df)
        log_progress(f"  ths_index 写入 {rows} 行")
        return rows

    log_progress("  ths_index 无数据")
    return 0


def fill_ths_daily(db: TushareDB, api, start=DEFAULT_START, end=DEFAULT_END):
    """同花顺板块日线 — 按板块拉全日期范围（比按日期快1700倍）"""
    log_progress(f"填充 ths_daily ({start}~{end}) ...")

    # 获取所有板块代码
    all_codes = db.get_all_ths_codes()
    if not all_codes:
        log_progress("  ths_index 为空，先填充...")
        fill_ths_index(db, api)
        all_codes = db.get_all_ths_codes()

    total = 0
    count = len(all_codes)
    for i, (ts_code, name, stype) in enumerate(all_codes):
        rows = fetch_and_upsert(db, api, 'ths_daily', 'ths_daily',
                                ts_code=ts_code, start_date=start, end_date=end)
        if rows:
            total += rows
        if (i + 1) % 100 == 0:
            log_progress(f"  ths_daily 进度", total=count, current=i + 1)
        # ths_daily 更频繁，可能触发限流，稍微多睡一点
        time.sleep(FETCH_SLEEP)

    log_progress(f"  ths_daily 完成，共写入 {total} 行")
    return total


def fill_ths_member(db: TushareDB, api):
    """板块成分股（一次性）"""
    log_progress("填充 ths_member ...")
    all_codes = db.get_all_ths_codes()
    if not all_codes:
        log_progress("  ths_index 为空，先填充...")
        fill_ths_index(db, api)
        all_codes = db.get_all_ths_codes()

    total = 0
    count = len(all_codes)
    for i, (ts_code, name, stype) in enumerate(all_codes):
        df = safe_fetch(api.ths_member, ts_code=ts_code)
        if df is not None and not df.empty:
            rows = db.upsert_many('ths_member', df)
            if rows:
                total += rows
        if (i + 1) % 50 == 0:
            log_progress(f"  ths_member 进度", total=count, current=i + 1)
        time.sleep(FETCH_SLEEP)

    log_progress(f"  ths_member 完成，共写入 {total} 行")
    return total


# ════════════════════════════════════════════════════════════
# 调度入口
# ════════════════════════════════════════════════════════════

# 回填任务注册表
BACKFILL_TASKS = {
    'stock_basic':   {'fn': fill_stock_basic,  'need_high': False, 'once': True},
    'trade_cal':     {'fn': fill_trade_cal,    'need_high': False, 'once': True},
    'stock_daily':   {'fn': fill_stock_daily,  'need_high': False, 'once': False},
    'daily_basic':   {'fn': fill_daily_basic,  'need_high': False, 'once': False},
    'index_daily':   {'fn': fill_index_daily,  'need_high': False, 'once': False},
    'adj_factor':    {'fn': fill_adj_factor,   'need_high': False, 'once': False},
    'ths_index':     {'fn': fill_ths_index,    'need_high': True,  'once': True},
    'ths_daily':     {'fn': fill_ths_daily,    'need_high': True,  'once': False},
    'ths_member':    {'fn': fill_ths_member,   'need_high': True,  'once': True},
}


def build_api(use_proxy: bool):
    """根据策略创建 API 客户端"""
    if use_proxy:
        if not TUSHARE_PROXY_URL:
            log.warning("未配置 TUSHARE_PROXY_URL，降级为官方直连")
            return create_direct_api()
        log.info("使用代理 API（15000分）: %s", TUSHARE_PROXY_URL)
        return create_proxy_api()
    else:
        log.info("使用官方直连 API（2000分）")
        return create_direct_api()


def main():
    parser = argparse.ArgumentParser(description='Tushare 数据回填')
    parser.add_argument('--full', action='store_true', help='全量回填（15000分走代理）')
    parser.add_argument('--daily', action='store_true', help='日常增量（2000分直连）')
    parser.add_argument('--start', default=DEFAULT_START, help='起始日期 YYYYMMDD')
    parser.add_argument('--end', default=DEFAULT_END, help='结束日期 YYYYMMDD')
    parser.add_argument('--tables', default='', help='指定表名，逗号分隔')
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Tushare 数据回填开始")
    log.info("  日期范围: %s ~ %s", args.start, args.end)
    log.info("  DATA_DIR: %s", DATA_DIR)
    log.info("=" * 60)

    # 初始化 DB
    db = TushareDB()

    if args.full:
        # 全量回填：15000分走代理
        api = build_api(use_proxy=True)
        mode = 'full'
    elif args.daily:
        # 日常增量：2000分直连
        api = build_api(use_proxy=False)
        mode = 'daily'
    else:
        print("请指定 --full 或 --daily")
        sys.exit(1)

    # 确定要执行的表
    if args.tables:
        table_list = [t.strip() for t in args.tables.split(',') if t.strip()]
    else:
        table_list = list(BACKFILL_TASKS.keys())

    # 按依赖顺序执行
    # 先执行一次性表，再做分日期表
    once_tables = [t for t in table_list if BACKFILL_TASKS[t]['once']]
    daily_tables = [t for t in table_list if not BACKFILL_TASKS[t]['once']]

    # 强依赖排序
    once_order = ['stock_basic', 'trade_cal', 'ths_index', 'ths_member']
    once_tables.sort(key=lambda t: once_order.index(t) if t in once_order else 99)

    total_rows = {}
    started_at = time.time()

    # === 一次性表 ===
    if once_tables:
        log.info("\n--- 一次性表 ---")
        for table in once_tables:
            info = BACKFILL_TASKS[table]
            if mode == 'daily' and info['need_high']:
                log.info("  跳过 %s（需要高积分，daily 模式不执行）", table)
                continue

            rows = info['fn'](db, api)
            total_rows[table] = rows

    # === 分日期表 ===
    if daily_tables:
        log.info("\n--- 分日期表 ---")
        for table in daily_tables:
            info = BACKFILL_TASKS[table]
            if mode == 'daily' and info['need_high']:
                log.info("  跳过 %s（需要高积分，daily 模式不执行）", table)
                continue

            rows = info['fn'](db, api, start=args.start, end=args.end)
            total_rows[table] = rows

    elapsed = time.time() - started_at
    log.info("\n" + "=" * 60)
    log.info("回填完成！耗时: %.1f 秒", elapsed)
    for table, rows in total_rows.items():
        log.info("  %s: %d 行", table, rows)
    log.info("=" * 60)


if __name__ == '__main__':
    main()
