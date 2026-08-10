#!/usr/bin/env python3
"""用 Tushare 15000分代理按 ts_code 补齐 ths_daily 历史数据。

适用场景：用户关注的行业/概念因不在追踪集合（自选股关联<6 / 数据停更）
从未进入每日更新范围，本地数据缺失或停更。此脚本按 ts_code 精确拉取
Tushare ths_daily 全历史并 REPLACE 写入，之后每日增量由 update_sectors
的关注板块强制纳入机制保证。

用法:
    python -m scripts.backfill_watched_ths_daily                # 默认三个已知缺失概念
    python -m scripts.backfill_watched_ths_daily 886094.TI 886111.TI
    python -m scripts.backfill_watched_ths_daily --start 20240101 --end 20260810
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.data_access.data_source import _call_ths_proxy, _get_tushare_db
from backend.core.logger import get_logger

log = get_logger('backfill_ths_daily')

DEFAULT_CODES = [
    ('886094.TI', '华为盘古'),   # 380条止于 2026-06-12（Tushare 有 6/12 后 43 条）
    ('886111.TI', '玻璃基板'),   # 本地 5 条（Tushare 全历史 32 条）
    ('886112.TI', 'MLCC概念'),   # 本地 3 条（Tushare 全历史 7 条）
]

FIELD_MAP = {
    'ts_code': 'ts_code',
    'trade_date': 'trade_date',
    'open': 'open',
    'high': 'high',
    'low': 'low',
    'close': 'close',
    'pre_close': 'pre_close',
    'change': 'change',
    'pct_change': 'pct_chg',   # Tushare 字段名 ≠ 表字段名
    'vol': 'vol',
    'amount': 'amount',
}


def backfill_one(db, ts_code: str, name: str, start: str, end: str) -> dict:
    """拉取单个板块全历史并写入 ths_daily，返回统计。"""
    rows = _call_ths_proxy('ths_daily', {
        'ts_code': ts_code,
        'start_date': start,
        'end_date': end,
    })
    if not rows:
        return {'code': ts_code, 'name': name, 'fetched': 0, 'written': 0,
                'range': '无数据'}

    records = []
    for row in rows:
        rec = {}
        for src_key, dst_key in FIELD_MAP.items():
            if src_key in row:
                rec[dst_key] = row[src_key]
        trade_date = str(rec.get('trade_date', '')).replace('-', '')
        rec['trade_date'] = trade_date
        # Tushare 新概念早期数据质量：close 缺失的行写入会污染 ths_daily
        # （覆盖率误判正式数据 + 强度计算崩溃），整行跳过。
        if rec.get('close') is None:
            continue
        records.append(rec)

    # 按 trade_date 去重（同一板块同一天只保留一条）
    seen = set()
    unique = []
    for rec in records:
        key = rec['trade_date']
        if key in seen:
            continue
        seen.add(key)
        unique.append(rec)
    unique.sort(key=lambda r: r['trade_date'])

    written = db.upsert_many_from_dicts('ths_daily', unique)
    return {
        'code': ts_code,
        'name': name,
        'fetched': len(rows),
        'written': written,
        'range': f"{unique[0]['trade_date']} ~ {unique[-1]['trade_date']} ({len(unique)}条)",
    }


def main():
    ap = argparse.ArgumentParser(description='Tushare 按 ts_code 补齐 ths_daily 历史')
    ap.add_argument('codes', nargs='*', help='ts_code 列表（缺省用已知三个缺失概念）')
    ap.add_argument('--start', default='20240101', help='起始日期 YYYYMMDD')
    ap.add_argument('--end', default=None, help='结束日期 YYYYMMDD（缺省=最新交易日）')
    args = ap.parse_args()

    from backend.data_access.data_source import get_last_completed_trading_day
    end = args.end or get_last_completed_trading_day().replace('-', '')

    if args.codes:
        db = _get_tushare_db()
        idx = db.execute_raw(
            "SELECT ts_code, name FROM ths_index WHERE ts_code IN (%s)"
            % ','.join(['%s'] * len(args.codes)),
            args.codes,
        )
        name_map = {r['ts_code']: r['name'] for r in idx}
        targets = [(c, name_map.get(c, c)) for c in args.codes]
    else:
        targets = DEFAULT_CODES

    db = _get_tushare_db()
    if not db:
        log.error('DB 不可用')
        sys.exit(1)

    log.info('补齐 %d 个板块: %s ~ %s', len(targets), args.start, end)
    for ts_code, name in targets:
        try:
            result = backfill_one(db, ts_code, name, args.start, end)
            log.info('✅ %s %s: %s', result['name'], result['code'], result['range'])
        except Exception as exc:
            log.error('❌ %s %s 补齐失败: %s', name, ts_code, exc)
    log.info('完成')


if __name__ == '__main__':
    main()
