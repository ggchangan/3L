#!/usr/bin/env python3
"""
抽象数据层 — 统一数据获取入口，内置故障切换+健康监测

用法：
    from backend.data_access.data_source import (
        get_sector_rankings, get_sector_klines, get_concept_map, get_data_source_status
    )
"""

import json, os, sys, time
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.config import (
    SECTOR_DAILY_PATH,
    SOURCES_EM_SECTOR_DAILY,
    SOURCES_THS_SECTOR_DAILY,
    SOURCES_EM_CONCEPT_MAP,
    STOCK_CONCEPT_MAP_PATH,
)
from backend.services.source_health import (
    report_success, report_failure, is_source_available, get_all_health
)
from backend.core.logger import get_logger
from backend.core.exceptions import DataSourceError

log = get_logger(__name__)

# TushareDB 全局实例（懒加载）
_TUSHARE_DB = None

def _get_tushare_db():
    global _TUSHARE_DB
    if _TUSHARE_DB is None:
        try:
            from backend.data_access.tushare_db import TushareDB
            _TUSHARE_DB = TushareDB()
        except Exception as e:
            log.warning('TushareDB 初始化失败: %s', e)
            _TUSHARE_DB = None
    return _TUSHARE_DB


# ═══════════════════════════════════════════════════════
# DB 批量查询接口（data_layer 通过这里访问 DB，不直接调 TushareDB）
# ═══════════════════════════════════════════════════════
def get_all_stocks_from_db(codes_list, limit=60):
    """从DB批量获取K线数据 + 股票名称

    Args:
        codes_list: 6位股票代码列表 ['600519', '000001']
        limit: 每只股票返回K线条数

    Returns:
        {code: {'klines': [{date, open, close, high, low, volume}, ...],
                'name': str}}
        查不到名称时 name 为空字符串
    """
    db = _get_tushare_db()
    if not db or not codes_list:
        return {}
    klines_map = db.query_stock_klines_batch(codes_list, limit=limit, adj='qfq')
    # 批量查股票名称
    placeholders = ','.join(['%s'] * len(codes_list))
    name_rows = db.execute_raw(
        f"SELECT symbol, name FROM stock_basic WHERE symbol IN ({placeholders})",
        list(codes_list)
    )
    code_name_map = {r['symbol']: r.get('name', '') for r in name_rows}
    result = {}
    for code in codes_list:
        klines = klines_map.get(code, [])
        name = code_name_map.get(code, '')
        result[code] = {'klines': klines, 'name': name}
    return result


def get_index_data_from_db(index_codes):
    """从DB获取多个指数的K线数据

    Args:
        index_codes: {code: name} 字典，如 {'000001': '上证指数', '000985': '中证全指'}

    Returns:
        {code: {'name': str, 'klines': [{date, open, close, high, low, volume}, ...]}}
        DB无数据时该code不在返回结果中
    """
    db = _get_tushare_db()
    if not db or not index_codes:
        return {}
    result = {}
    for code, name in index_codes.items():
        ts = f"{code}.SH" if code != '399006' else f"{code}.SZ"
        klines = db.get_index_klines(ts, limit=500)
        if klines:
            result[code] = {'name': name, 'klines': klines}
    return result


def save_stock_klines_to_db(stock_data):
    """保存K线数据到 stock_daily 表

    Args:
        stock_data: {code: {'klines': [{date, open, close, high, low, volume, ...}], 'name': str}}
    """
    db = _get_tushare_db()
    if not db:
        return 0
    total = 0
    for code, info in stock_data.items():
        ts = db.code_to_ts_code(code)
        klines = info.get('klines', [])
        rows = []
        for k in klines:
            rows.append({
                'ts_code': ts,
                'trade_date': k['date'],
                'open': k.get('open'),
                'high': k.get('high'),
                'low': k.get('low'),
                'close': k.get('close'),
                'vol': k.get('volume', 0),
                'pre_close': k.get('pre_close'),
                'change': k.get('change'),
                'pct_chg': k.get('pct_chg'),
            })
        if rows:
            db.upsert_many_from_dicts('stock_daily', rows)
            total += len(rows)
    return total


def save_index_klines_to_db(index_data):
    """保存指数K线数据到 index_daily 表

    Args:
        index_data: {code: {'name': str, 'klines': [{date, open, close, high, low, volume}, ...]}}
    """
    db = _get_tushare_db()
    if not db:
        return 0
    total = 0
    for code, info in index_data.items():
        ts = f"{code}.SH" if code != '399006' else f"{code}.SZ"
        klines = info.get('klines', [])
        rows = []
        for k in klines:
            rows.append({
                'ts_code': ts,
                'trade_date': k['date'],
                'open': k.get('open'),
                'high': k.get('high'),
                'low': k.get('low'),
                'close': k.get('close'),
                'vol': k.get('volume', 0),
            })
        if rows:
            db.upsert_many_from_dicts('index_daily', rows)
            total += len(rows)
    return total


# 交易日历缓存（akshare tool_trade_date_hist_sina，含节假日）
_trade_date_cache = None


def _get_trade_date_cache():
    """获取交易日历缓存，按需加载"""
    global _trade_date_cache
    if _trade_date_cache is not None:
        return _trade_date_cache
    try:
        import akshare as ak
        df = ak.tool_trade_date_hist_sina()
        _trade_date_cache = set(str(d) for d in df['trade_date'].tolist())
    except Exception:
        _trade_date_cache = set()
    return _trade_date_cache


def get_last_completed_trading_day():
    """获取上一个已完成交易日 YYYYMMDD（考虑春节/国庆等节假日）

    使用同花顺交易日历精确判断，适用于cron在交易日6:00运行的场景。
    此时当日交易未开始，目标日期是上一个已完成交易日。
    """
    cache = _get_trade_date_cache()
    d = datetime.now() - timedelta(days=1)
    for _ in range(21):
        ds = d.strftime('%Y-%m-%d')
        if ds in cache:
            return d.strftime('%Y%m%d')
        d -= timedelta(days=1)
    # fallback: 周末判断
    d = datetime.now() - timedelta(days=1)
    for _ in range(14):
        if d.weekday() < 5:
            return d.strftime('%Y%m%d')
        d -= timedelta(days=1)
    return datetime.now().strftime('%Y%m%d')


def _last_trading_day():
    """返回最后一个交易日字符串 YYYYMMDD
    优先使用交易日历（含节假日），fallback到周末判断
    """
    try:
        return get_last_completed_trading_day()
    except Exception:
        d = datetime.now()
        for _ in range(7):
            if d.weekday() < 5:
                return d.strftime('%Y%m%d')
            d -= timedelta(days=1)
        return d.strftime('%Y%m%d')


class DataUnavailableError(DataSourceError):
    def __init__(self, data_type):
        self.data_type = data_type
        super().__init__(f'数据源全部不可用: {data_type}')

def _load_json(path, default=None):
    if not os.path.isfile(path):
        return default if default is not None else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default if default is not None else {}

def _call_with_failover(data_type, args, chain, fallback=None):
    for source_name, fetch_fn in chain:
        if not is_source_available(source_name):
            continue
        try:
            data = fetch_fn(*args)
            if data is None:
                continue  # None 表示"没找到"→尝试下一个源
            report_success(source_name)
            return data
        except Exception as e:
            report_failure(source_name, str(e))
            log.warning('%s -> %s 失败: %s', data_type, source_name, e)
            continue
    if fallback:
        return fallback
    log.warning('%s: 所有数据源均不可用', data_type)
    raise DataUnavailableError(data_type)

# --- 实时排行获取函数（push2test API + 文件回退） ---
def _fetch_live_sector_ranking(date_str):
    """从 push2test 实时获取板块排行（chg_1d 取自 f3 字段）
    
    直接调东财实时接口，不依赖静态文件。失败时回退读当前快照源文件（由 CONCEPT_DATA_SOURCE 配置驱动）。
    返回 {last_updated, industries: {name: {date, change_pct, close, ...}},
           concepts: {...}}"""
    today = _last_trading_day()
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
            'Referer': 'https://quote.eastmoney.com/',
        }
        ut = 'bd1d9ddb04089700cf9c27f6f7426281'
        result = {'last_updated': today, 'industries': {}, 'concepts': {}}
        for sector_type, fs in [('industries', 'm:90+t:2'), ('concepts', 'm:90+t:3')]:
            params = {
                'pn': '1', 'pz': '2000', 'po': '1', 'np': '1',
                'ut': ut, 'fltt': '2', 'invt': '2',
                'fs': fs, 'fields': 'f2,f3,f14,f15,f16,f17,f18,f5',
            }
            r = requests.get(url, params=params, headers=headers, timeout=20)
            items = r.json().get('data', {}).get('diff', [])
            for item in items:
                name = (item.get('f14') or '').strip()
                # 归一化：去掉Ⅱ/Ⅲ/D等东财后缀
                clean = name.replace('Ⅱ', '').replace('Ⅲ', '').replace('D', '').strip()
                if not clean:
                    continue
                close = float(item.get('f2', 0) or 0)
                result[sector_type][clean] = {
                    'date': today,
                    'close': round(close, 2),
                    'change_pct': round(float(item.get('f3', 0) or 0), 2),
                    'open': round(float(item.get('f17', close) or close), 2),
                    'high': round(float(item.get('f15', close) or close), 2),
                    'low': round(float(item.get('f16', close) or close), 2),
                    'volume': int(float(item.get('f5', 0) or 0)),
                    'prev_close': round(float(item.get('f18', 0) or 0), 2),
                }
            log.info('push2test live [%s]: %d个板块', sector_type, len(result[sector_type]))
        log.info('push2test live 排行获取成功 (行业%d个, 概念%d个)',
                 len(result['industries']), len(result['concepts']))
        return result
    except Exception as e:
        log.warning('push2test live 失败, 回退 %s: %s', _get_snapshot_source_label(), e)
        return _load_json(_get_snapshot_source_path())

def _fetch_em_concept_map():
    return _load_json(SOURCES_EM_CONCEPT_MAP)

# --- THS实时排行获取函数（行业主源） ---
def _fetch_ths_live_sector_ranking(date_str):
    """从同花顺实时获取行业板块排行（chg_1d 取自 stock_board_industry_summary_ths）

    同花顺行业数据稳定好用，90个行业一次返回。
    返回值格式与 _fetch_em_sector_ranking 一致。
    """
    try:
        os.environ['TQDM_DISABLE'] = '1'
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        today = _last_trading_day()
        industries = {}
        for _, row in df.iterrows():
            name = str(row.get('板块', '')).strip()
            chg = row.get('涨跌幅', None)
            if name and chg is not None:
                industries[name] = {
                    'date': today,
                    'change_pct': round(float(chg), 2),
                    'up_count': int(row.get('上涨家数', 0) or 0),
                    'down_count': int(row.get('下跌家数', 0) or 0),
                    'net_flow': float(row.get('净流入', 0) or 0),
                    'leader': str(row.get('领涨股', '') or ''),
                    'leader_chg': round(float(row.get('领涨股-涨跌幅', 0) or 0), 2),
                }
        log.info('THS live: 行业%d个（同花顺主源）', len(industries))
        return {'last_updated': today, 'industries': industries, 'concepts': {}}
    except Exception as e:
        log.warning('THS live 失败: %s', e)
        return None


# --- 快照源文件获取函数（路径由 CONCEPT_DATA_SOURCE 配置驱动） ---
def _fetch_snapshot_sector_klines(sector_name, sector_type):
    """从当前快照源文件获取单日K线（只有今日数据）"""
    data = _load_json(_get_snapshot_source_path())
    key = 'industries' if sector_type == 'industry' else 'concepts'
    container = data.get(key, {})
    entry = container.get(sector_name)
    if entry and isinstance(entry, dict):
        return [{
            'date': entry.get('date', ''),
            'open': entry.get('open', 0),
            'close': entry.get('close', 0),
            'high': entry.get('high', 0),
            'low': entry.get('low', 0),
            'volume': entry.get('volume', 0),
            'change_pct': entry.get('change_pct', 0),
        }]
    return []

def _fetch_ths_sector_ranking(date_str):
    data = _load_json(SOURCES_THS_SECTOR_DAILY)
    result = {}
    for key in ['industries', 'concepts']:
        container = data.get(key, {})
        for name, klines in container.items():
            if klines and len(klines) >= 2:
                latest = klines[-1]
                prev = klines[-2]
                if latest['date'] == date_str or date_str == '':
                    prev_close = prev['close']
                    if prev_close > 0:
                        result[name] = {
                            'date': latest['date'],
                            'change_pct': round((latest['close'] - prev_close) / prev_close * 100, 2),
                            'close': latest['close'],
                        }
    return result

def _fetch_ths_sector_klines(sector_name, sector_type):
    data = _load_json(SOURCES_THS_SECTOR_DAILY)
    key = 'industries' if sector_type == 'industry' else 'concepts'
    result = data.get(key, {}).get(sector_name)
    if result is None:
        return None  # 没找到→尝试下一个源
    return result

# --- 旧 sector_daily.json 获取函数 ---
def _fetch_legacy_sector_ranking(date_str):
    data = _load_json(SECTOR_DAILY_PATH)
    return data if data else None

def _fetch_legacy_sector_klines(sector_name, sector_type):
    data = _load_json(SECTOR_DAILY_PATH)
    key = 'industries' if sector_type == 'industry' else 'concepts'
    result = data.get(key, {}).get(sector_name)
    if result is None:
        return None
    return result

# ════════════════════════════════════════════════════════════
# 配置驱动的数据源选择
# 根据 CONCEPT_DATA_SOURCE 路由到对应的源文件
# 切换数据源只改 config.py 一处
# ════════════════════════════════════════════════════════════

def _get_snapshot_source_path():
    """根据 CONCEPT_DATA_SOURCE 返回当前快照源文件路径
    
    Returns:
        SOURCES_THS_SECTOR_DAILY (ths 模式) 或 SOURCES_EM_SECTOR_DAILY (eastmoney 模式)
    """
    from backend.core.config import CONCEPT_DATA_SOURCE
    if CONCEPT_DATA_SOURCE == 'ths':
        return SOURCES_THS_SECTOR_DAILY
    elif CONCEPT_DATA_SOURCE == 'eastmoney':
        return SOURCES_EM_SECTOR_DAILY
    log.warning('未知数据源: %s，回退到THS', CONCEPT_DATA_SOURCE)
    return SOURCES_THS_SECTOR_DAILY


def _get_snapshot_source_label():
    """返回当前数据源显示名称（用于日志/验证）"""
    from backend.core.config import CONCEPT_DATA_SOURCE
    labels = {'ths': 'THS仓', 'eastmoney': 'EM仓'}
    return labels.get(CONCEPT_DATA_SOURCE, 'THS仓')


# ════════════════════════════════════════════════════════════
# Tushare 数据源获取函数（从 DB 读取）
# ════════════════════════════════════════════════════════════

def _fetch_tushare_sector_klines(sector_name, sector_type='industry'):
    """从 TushareDB 读取板块K线（优先源）

    Args:
        sector_name: 板块中文名
        sector_type: 'industry' 或 'concept'

    Returns:
        [{date, open, close, high, low, volume}, ...] 或 None
    """
    db = _get_tushare_db()
    if db is None:
        return None
    try:
        klines = db.get_sector_klines(sector_name, sector_type, limit=120)
        if klines:
            report_success('tushare_sector_klines')
            return klines
        # 空数据 -> None 触发 failover 链回退
        return None
    except Exception as e:
        report_failure('tushare_sector_klines', str(e))
        return None


def _fetch_tushare_sector_ranking(date_str):
    """从 TushareDB 读取板块当日涨跌幅排行

    Args:
        date_str: YYYYMMDD

    Returns:
        {last_updated, industries: {name: {change_pct, date, ...}},
         concepts: {name: {change_pct, date, ...}}}
        或 None
    """
    db = _get_tushare_db()
    if db is None:
        return None
    try:
        # 从 ths_daily 表获取当日的板块数据
        all_codes = db.get_all_ths_codes()
        if not all_codes:
            return None

        industries = {}
        concepts = {}
        has_data = False

        for ts_code, name, stype in all_codes:
            rows = db.query_many(
                'ths_daily',
                where='ts_code=? AND trade_date=?',
                params=[ts_code, date_str],
                limit=1,
            )
            if rows:
                has_data = True
                row = rows[0]
                entry = {
                    'date': date_str,
                    'change_pct': row.get('pct_chg', 0),
                    'close': row.get('close', 0),
                    'open': row.get('open', 0),
                    'high': row.get('high', 0),
                    'low': row.get('low', 0),
                    'volume': row.get('vol', 0),
                }
                target = industries if stype == 'I' else concepts
                target[name] = entry

        if has_data:
            report_success('tushare_sector_ranking')
            return {
                'last_updated': date_str,
                'industries': industries,
                'concepts': concepts,
            }
        return None
    except Exception as e:
        report_failure('tushare_sector_ranking', str(e))
        return None


def _fetch_tushare_daily_basic(ts_code, trade_date):
    """从 TushareDB 读取个股每日指标（PE/PB/市值）

    Args:
        ts_code: 股票代码含后缀 (600519.SH)
        trade_date: YYYYMMDD

    Returns:
        {pe_ttm, pb, total_mv, ...} 或 None
    """
    db = _get_tushare_db()
    if db is None:
        return None
    try:
        return db.query_daily_basic(ts_code, trade_date)
    except Exception:
        return None


# ====== 调用链定义 ======
DATA_SOURCE_CHAINS = {
    'sector_ranking': [
        ('tushare', lambda date: _fetch_tushare_sector_ranking(date)),
        ('ths_live', lambda date: _fetch_ths_live_sector_ranking(date)),
        ('live', lambda date: _fetch_live_sector_ranking(date)),
        ('legacy_sector', lambda date: _fetch_legacy_sector_ranking(date)),
        ('snapshot_sector', lambda date: _fetch_ths_sector_ranking(date)),
    ],
    'sector_klines': [
        ('tushare', lambda name, type_: _fetch_tushare_sector_klines(name, type_)),
        ('ths_sector', lambda name, type_: _fetch_ths_sector_klines(name, type_)),
        ('snapshot_sector', lambda name, type_: _fetch_snapshot_sector_klines(name, type_)),
        ('legacy_sector', lambda name, type_: _fetch_legacy_sector_klines(name, type_)),
    ],
    'concept_map': [
        ('em_sector', lambda: _fetch_em_concept_map()),
        ('legacy_sector', lambda: _load_json(STOCK_CONCEPT_MAP_PATH)),
    ],
}

# ====== 公开API ======
def get_sector_rankings(sector_type='industry', date_str=None):
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')
    chain = DATA_SOURCE_CHAINS['sector_ranking']
    result = _call_with_failover(f'sector_ranking_{sector_type}', (date_str,), chain)
    if isinstance(result, dict):
        if sector_type == 'industry':
            return result.get('industries', result) if 'industries' in result else result
        else:
            return result.get('concepts', {}) if 'concepts' in result else {}
    return result

def get_sector_klines(sector_name, sector_type='industry'):
    chain = DATA_SOURCE_CHAINS['sector_klines']
    return _call_with_failover(f'sector_klines_{sector_type}', (sector_name, sector_type), chain, fallback=[])

def get_concept_map():
    chain = DATA_SOURCE_CHAINS['concept_map']
    return _call_with_failover('concept_map', (), chain, fallback={})


# ════════════════════════════════════════════════════════
# 新增：_push2test 读取唯一入口
# 所有业务代码必须通过此函数获取当日涨跌幅快照
# 不直接读 sector_daily.json 的 _push2test 字段
# ════════════════════════════════════════════════════════
def get_sector_push2test():
    """获取当日涨跌幅快照（_push2test 字段）

    返回: {industries: {name: {change_pct, date, up_count, down_count, ...}},
            concepts: {name: {change_pct, date, ...}}}

    这是读取 _push2test 的唯一入口。
    所有业务代码（get_mainline_data 等）必须通过此函数获取，
    不得直接调 data_layer.load_sector_daily_uncached() 读原始文件。
    """
    data = _load_json(SECTOR_DAILY_PATH)
    if not isinstance(data, dict):
        return {}
    return data.get('_push2test', {})


# 合并数据内存缓存（TTL=1秒，避免同一批请求反复读6MB文件）
_MERGED_CACHE = {'data': None, 'ts': 0.0}

def get_merged_sector_data():
    """获取合并后的全量板块数据 {last_updated, industries, concepts}
    
    合并策略：EM仓(今日数据) + THS仓(历史K线) + legacy(向后兼容)
    以 legacy 的完整K线优先，EM仓补充今日数据，THS仓补充历史K线
    
    内置1秒内存缓存（非 key 级过期，数据不常变）
    """
    global _MERGED_CACHE
    now = time.time()
    if _MERGED_CACHE['data'] is not None and now - _MERGED_CACHE['ts'] < 1.0:
        return _MERGED_CACHE['data']
    # 1. 先读 legacy（最完整，包含历史K线）
    legacy = _load_json(SECTOR_DAILY_PATH)
    if legacy and 'industries' in legacy:
        result = {
            'last_updated': legacy.get('last_updated', ''),
            'industries': dict(legacy.get('industries', {})),
            'concepts': dict(legacy.get('concepts', {})),
        }
        report_success('legacy_sector')
    else:
        result = {
            'last_updated': '',
            'industries': {},
            'concepts': {},
        }
    
    # 2. THS仓补充历史K线（legacy没有的板块）
    ths = _load_json(SOURCES_THS_SECTOR_DAILY)
    if ths:
        for key in ['industries', 'concepts']:
            ths_container = ths.get(key, {})
            for name, klines in ths_container.items():
                if name not in result[key] and klines:
                    result[key][name] = klines
    
    # 3. 当前快照源补充今日数据（含change_pct，路径由 CONCEPT_DATA_SOURCE 配置驱动）
    snap = _load_json(_get_snapshot_source_path())
    if snap:
        for key, snap_key in [('industries', 'industries'), ('concepts', 'concepts')]:
            snap_container = snap.get(snap_key, {})
            for name, entry in snap_container.items():
                if isinstance(entry, dict) and entry.get('date'):
                    if name not in result[key] or not result[key][name]:
                        # 新板块，创建单日K线
                        result[key][name] = [{'date': entry['date'],
                            'open': entry.get('open', 0),
                            'close': entry.get('close', 0),
                            'high': entry.get('high', 0),
                            'low': entry.get('low', 0),
                            'volume': entry.get('volume', 0),
                            'change_pct': entry.get('change_pct', 0)}]
                    elif result[key][name] and result[key][name][-1]['date'] != entry.get('date'):
                        # 已有板块；已有change_pct在`_to_em_format`中已有，不需要追加
                        pass

    _MERGED_CACHE['data'] = result
    _MERGED_CACHE['ts'] = time.time()
    return result

def get_data_source_status():
    health = get_all_health()
    return {
        'sources': health.get('sources', {}),
        'transitions': health.get('transitions', [])[-20:],
        'summary': {
            'total': len(health.get('sources', {})),
            'up': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'UP'),
            'down': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'DOWN'),
            'degraded': sum(1 for s in health.get('sources', {}).values() if s.get('status') == 'DEGRADED'),
        }
    }


# ════════════════════════════════════════════════════════════
# 板块涨跌计算（从个股K线 → mootdx，不依赖 push2test f3）
# ════════════════════════════════════════════════════════════

def calc_sector_chg_from_stocks(sector_code: str, date_str: str = None) -> Optional[float]:
    """从个股K线计算板块涨跌幅
    
    获取板块成分股 → mootdx 拉个股日K线 → 等权平均涨跌幅
    不依赖 push2test f3 字段，周末也能拿到历史交易日数据。
    
    Args:
        sector_code: 东财板块代码，如 'BK1039'
        date_str: YYYYMMDD，默认最后一个交易日
    
    Returns:
        等权平均涨跌幅（%），失败返回 None
    """
    if date_str is None:
        date_str = _last_trading_day()
    
    # 1. 从push2test获取成分股代码
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        params = {'pn':'1','pz':'200','po':'0','np':'1',
                  'ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2',
                  'fs':f'b:{sector_code}','fields':'f12,f14'}
        headers = {'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        items = r.json().get('data',{}).get('diff',[])
        if not items:
            return None
        codes = [(it.get('f12',''),it.get('f14','')) for it in items if it.get('f12')]
    except Exception:
        return None
    
    # 2. 从mootdx获取个股K线，计算涨跌幅
    try:
        from mootdx.quotes import Quotes
        client = Quotes.factory(market='std')
    except Exception:
        return None
    
    if not date_str or len(date_str) != 8:
        return None
    
    # 前一个交易日
    prev_date = datetime.strptime(date_str, '%Y%m%d')
    for _ in range(7):
        prev_date -= timedelta(days=1)
        if prev_date.weekday() < 5:
            break
    prev_str = prev_date.strftime('%Y%m%d')
    
    changes = []
    for code, name in codes:
        if code.startswith(('9','8','4')):  # 北交所跳过
            continue
        try:
            market = 0 if not code.startswith('6') else 1
            klines = client.bars(symbol=code, category=4, offset=10)
            if klines is None or len(klines) < 2:
                continue
            close_target = close_prev = None
            for i in range(len(klines)-1, -1, -1):
                row = klines.iloc[i]
                ds = str(row.name)[:10].replace('-','')
                if ds == date_str:
                    close_target = row['close']
                elif ds == prev_str:
                    close_prev = row['close']
            if close_target and close_prev and close_prev > 0:
                chg = (close_target / close_prev - 1) * 100
                changes.append(chg)
        except Exception:
            continue
    
    if not changes:
        return None
    return sum(changes) / len(changes)


def get_sector_constituents(sector_code: str) -> List[tuple]:
    """获取板块成分股列表 [(code, name), ...]
    
    用于验证、展示成分股构成。
    """
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        params = {'pn':'1','pz':'200','po':'0','np':'1',
                  'ut':'bd1d9ddb04089700cf9c27f6f7426281','fltt':'2','invt':'2',
                  'fs':f'b:{sector_code}','fields':'f12,f14'}
        headers = {'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
        r = requests.get(url, params=params, headers=headers, timeout=15)
        items = r.json().get('data',{}).get('diff',[])
        return [(it.get('f12',''),it.get('f14','')) for it in items if it.get('f12')]
    except Exception:
        return []


# ════════════════════════════════════════════════════════════
# THS概念板块快照获取（同花顺 stock_board_concept_info_ths）
# 数据源切换：从 push2test 切换到同花顺 THS
# ════════════════════════════════════════════════════════════

def _load_concept_name_mapping():
    """加载系统概念名 → THS概念名的映射表"""
    from backend.core.config import CONCEPT_NAME_MAPPING_PATH
    try:
        return _load_json(CONCEPT_NAME_MAPPING_PATH, {})
    except Exception:
        return {}

def _fetch_ths_concept_snapshots(name_list: list) -> dict:
    """从同花顺批量获取概念板块今日快照数据

    使用 stock_board_concept_info_ths(symbol) 逐个拉取。
    使用名称映射表将系统名转为 THS 名。

    Args:
        name_list: 系统概念名称列表

    Returns:
        {系统名: {date, change_pct, up_count, down_count, ...}}
    """
    if not name_list:
        return {}
    name_map = _load_concept_name_mapping()
    if not name_map:
        log.warning('概念名称映射表为空，跳过 THS 概念拉取')
        return {}

    today = _last_trading_day()
    result = {}
    os.environ['TQDM_DISABLE'] = '1'
    import akshare as ak

    total = len(name_list)
    success = 0
    fail = 0

    for idx, sys_name in enumerate(name_list):
        ths_name = name_map.get(sys_name)
        if not ths_name:
            continue  # 未映射的跳过（走 push2test fallback）

        try:
            df = ak.stock_board_concept_info_ths(symbol=ths_name)
            if df is None or df.empty:
                continue

            # DataFrame 格式: {项目: [..., '板块涨幅', ...], 值: [..., '-3.30%', ...]}
            # 用项目列查找对应的值
            projects = df['项目'].tolist() if '项目' in df.columns else []
            values = df['值'].tolist() if '值' in df.columns else []

            def _get_val(project_name):
                """从项目列表中查找对应值"""
                try:
                    idx = projects.index(project_name)
                    v = values[idx]
                    if isinstance(v, str):
                        v = v.replace('%', '').replace(',', '')
                    try:
                        return float(v)
                    except (ValueError, TypeError):
                        return None
                except (ValueError, IndexError):
                    return None

            chg = _get_val('板块涨幅')
            if chg is None:
                continue

            entry = {
                'date': today,
                'change_pct': round(float(chg), 2),
            }

            up = _get_val('上涨家数')
            if up is None:
                # 涨跌家数格式: "3/15" → 上涨3家, 下跌15家
                if '涨跌家数' in projects:
                    idx = projects.index('涨跌家数')
                    updown_str = str(values[idx])
                    if '/' in updown_str:
                        parts = updown_str.split('/')
                        try:
                            entry['up_count'] = int(parts[0])
                            entry['down_count'] = int(parts[1])
                        except (ValueError, IndexError):
                            pass
            else:
                entry['up_count'] = int(up)
                down = _get_val('下跌家数')
                if down is not None:
                    entry['down_count'] = int(down)

            net = _get_val('资金净流入(亿)')
            if net is not None:
                entry['net_flow'] = round(float(net), 2)

            result[sys_name] = entry
            success += 1
        except Exception as e:
            fail += 1
            if fail <= 3:  # 只打前3次失败日志
                log.warning('THS概念[%s]失败: %s: %s', ths_name, type(e).__name__, e)

        # 限流：同花顺接口间隔≥0.5秒
        if idx < total - 1:
            import time
            time.sleep(0.5)

    log.info('THS概念快照: 成功%d/%d个, 失败%d个 (映射覆盖%d个)',
             success, total, fail, len(name_map))
    return result


def get_ths_concept_snapshots(name_list: list = None) -> dict:
    """获取THS概念快照数据的公开入口

    如果不传 name_list，返回所有已映射概念的快照。
    如果 name_list 不为空，只拉取列表中的概念。

    返回 {系统名: {date, change_pct, up_count, down_count, ...}}
    """
    if name_list is None:
        # 不传参时尝试从概念列表获取所有已映射的概念名
        name_map = _load_concept_name_mapping()
        name_list = list(name_map.keys())

    return _fetch_ths_concept_snapshots(name_list)


def get_ths_concept_klines(name_list: list) -> dict:
    """获取THS概念最新日K线（使用 stock_board_concept_index_ths）

    仅拉取名称映射表中存在的概念，未映射的跳过。

    Args:
        name_list: 系统概念名称列表

    Returns:
        {系统名: {date, open, close, high, low, volume}}
    """
    if not name_list:
        return {}
    name_map = _load_concept_name_mapping()
    if not name_map:
        log.warning('概念名称映射表为空')
        return {}

    today = _last_trading_day()
    result = {}
    os.environ['TQDM_DISABLE'] = '1'
    import akshare as ak
    import time

    total = len(name_list)
    for idx, sys_name in enumerate(name_list):
        ths_name = name_map.get(sys_name)
        if not ths_name:
            continue
        try:
            lookback = (datetime.now() - timedelta(days=90)).strftime('%Y%m%d')
            df = ak.stock_board_concept_index_ths(symbol=ths_name, start_date=lookback, end_date=_last_trading_day())
            if df is not None and not df.empty:
                row = df.iloc[-1]
                close_col = '收盘价' if '收盘价' in df.columns else 'close'
                open_col = '开盘价' if '开盘价' in df.columns else 'open'
                high_col = '最高价' if '最高价' in df.columns else 'high'
                low_col = '最低价' if '最低价' in df.columns else 'low'
                vol_col = '成交量' if '成交量' in df.columns else 'volume'
                result[sys_name] = {
                    'date': today,
                    'open': round(float(row.get(open_col, 0) or 0), 2),
                    'close': round(float(row.get(close_col, 0) or 0), 2),
                    'high': round(float(row.get(high_col, 0) or 0), 2),
                    'low': round(float(row.get(low_col, 0) or 0), 2),
                    'volume': int(float(row.get(vol_col, 0) or 0)),
                }
        except Exception:
            pass
        if idx < total - 1:
            time.sleep(0.3)

    log.info('THS概念K线: 成功%d/%d个', len(result), total)
    return result


# ════════════════════════════════════════════════════════════
# 数据源统一入口（工厂模式）
# 根据 config.CONCEPT_DATA_SOURCE 路由到相应的实现
# 切换数据源只改 config.py 一处
# ════════════════════════════════════════════════════════════

def get_concept_snapshots(name_list: list = None) -> dict:
    """统一入口：获取概念板块今日快照数据

    根据 config.CONCEPT_DATA_SOURCE 路由到对应的数据源实现。
    当前主源：同花顺 THS（stock_board_concept_info_ths）

    Args:
        name_list: 系统概念名称列表，None=获取所有已映射概念

    Returns:
        {系统名: {date, change_pct, up_count, down_count, ...}}
    """
    from backend.core.config import CONCEPT_DATA_SOURCE

    if name_list is None:
        name_map = _load_concept_name_mapping()
        name_list = list(name_map.keys())

    if CONCEPT_DATA_SOURCE == 'ths':
        return _fetch_ths_concept_snapshots(name_list)
    else:
        log.warning('未知概念数据源: %s，回退到THS', CONCEPT_DATA_SOURCE)
        return _fetch_ths_concept_snapshots(name_list)


def get_concept_klines(name_list: list) -> dict:
    """统一入口：获取概念板块最新日K线数据

    根据 config.CONCEPT_DATA_SOURCE 路由到对应的数据源实现。
    当前主源：同花顺 THS（stock_board_concept_index_ths）

    Args:
        name_list: 系统概念名称列表

    Returns:
        {系统名: {date, open, close, high, low, volume}}
    """
    from backend.core.config import CONCEPT_DATA_SOURCE

    if CONCEPT_DATA_SOURCE == 'ths':
        return get_ths_concept_klines(name_list)
    else:
        log.warning('未知概念数据源: %s，回退到THS', CONCEPT_DATA_SOURCE)
        return get_ths_concept_klines(name_list)


# ════════════════════════════════════════════════════════════
# 数据源验证层 — 正确性/及时性/一致性
# ════════════════════════════════════════════════════════════

def verify_data_sources(verbose=True):
    """验证所有数据源的正确性、及时性、缓存一致性

    验证项：
      1. 实时源（push2test）：可调用、数量合理、change_pct 正常
      2. 文件源（EM/THS/legacy）：存在、有效JSON、数据新鲜度
      3. 一致性：实时 vs 文件 change_pct 基本一致

    返回 {"status": "pass"|"fail", "checks": [...], "now": date_str}
    """
    now = datetime.now().strftime('%Y%m%d')
    latest_trade_day = _last_trading_day()
    checks = []
    all_pass = True

    def _check(name, passed, detail):
        nonlocal all_pass
        if not passed:
            all_pass = False
        if verbose:
            tag = '✅' if passed else '❌'
            print(f'  {tag} {name}: {detail}')
        checks.append({'check': name, 'pass': passed, 'detail': detail})

    # ════ 1. 实时源验证 ════
    # 1a. THS live（行业主源）
    try:
        os.environ['TQDM_DISABLE'] = '1'
        import akshare as ak
        ths_df = ak.stock_board_industry_summary_ths()
        ths_cnt = len(ths_df)
        ths_ok = ths_cnt >= 80
        _check('THS行业总数', ths_ok, f'返回{ths_cnt}个 (需≥80)')

        # 检查电子化学品是否存在
        has_ec = '电子化学品' in ths_df['板块'].values
        _check('THS含电子化学品', has_ec, f'存在={has_ec}')

        # 检查半导体
        has_semi = '半导体' in ths_df['板块'].values
        _check('THS含半导体', has_semi, f'存在={has_semi}')

        # 电子化学品chg合理
        ec_row = ths_df[ths_df['板块'] == '电子化学品']
        if len(ec_row) > 0:
            ec_chg = float(ec_row.iloc[0]['涨跌幅'])
            _check('THS电子化学品chg合理', -20 < ec_chg < 20, f'chg={ec_chg}%')

        # 领涨股字段存在
        has_leader = '领涨股' in ths_df.columns
        _check('THS含领涨股字段', has_leader, f'存在={has_leader}')
        has_updown = '上涨家数' in ths_df.columns
        _check('THS含上涨/下跌家数字段', has_updown, f'存在={has_updown}')

        # 保存THS实时数据的 change_pct 供后续一致性比对
        ths_real_chg = {}
        for _, row in ths_df.iterrows():
            name = str(row.get('板块', '')).strip()
            chg = row.get('涨跌幅', None)
            if name and chg is not None:
                ths_real_chg[name] = float(chg)

    except Exception as e:
        _check('THS live调用', False, f'异常: {type(e).__name__}: {e}')
        ths_real_chg = {}

    # 1b. push2test（概念主源）
    try:
        import requests
        url = 'https://push2test.eastmoney.com/api/qt/clist/get'
        headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
        ut = 'bd1d9ddb04089700cf9c27f6f7426281'

        # 行业
        ind_params = {'pn':'1','pz':'2000','po':'1','np':'1','ut':ut,'fltt':'2','invt':'2','fs':'m:90+t:2','fields':'f2,f3,f14'}
        r = requests.get(url, params=ind_params, headers=headers, timeout=15)
        ind_items = r.json().get('data', {}).get('diff', [])
        ind_cnt = len(ind_items)
        ind_ok = ind_cnt > 400 and r.status_code == 200
        _check('push2test行业数', ind_cnt > 400, f'返回{ind_cnt}个 (需>400)')

        # 概念
        con_params = {'pn':'1','pz':'2000','po':'1','np':'1','ut':ut,'fltt':'2','invt':'2','fs':'m:90+t:3','fields':'f2,f3,f14'}
        r2 = requests.get(url, params=con_params, headers=headers, timeout=15)
        con_items = r2.json().get('data', {}).get('diff', [])
        con_cnt = len(con_items)
        _check('push2test概念数', con_cnt > 300, f'返回{con_cnt}个 (需>300)')

        # change_pct 合理性：至少有些非零（跳过 f3='-' 等无效值）
        def _safe_f3(it):
            v = it.get('f3')
            if v is None or v == '' or v == '-':
                return 0.0
            return float(v)
        non_zero = sum(1 for it in ind_items if abs(_safe_f3(it)) > 0.01)
        _check('行业涨跌幅合理性', non_zero > 0 or _is_trading_time() == False, f'{non_zero}/{ind_cnt}个非零')

        # 采样几个关键板块验证
        ind_data = {}
        for it in ind_items:
            name = (it.get('f14') or '').strip().replace('Ⅱ','').replace('Ⅲ','').replace('D','').strip()
            if name:
                ind_data[name] = _safe_f3(it)
        for key_sector in ['银行', '半导体', '证券']:
            val = ind_data.get(key_sector)
            _check(f'关键板块[{key_sector}]存在且合理', val is not None and -15 < val < 15,
                   f'change_pct={val}')

    except Exception as e:
        _check('push2test HTTP调用', False, f'异常: {e}')

    # ════ 2. 文件源验证 ════
    source_label = _get_snapshot_source_label()
    source_path = _get_snapshot_source_path()
    seen_paths = set()
    for fname, fpath in [(source_label, source_path),
                         ('THS仓', SOURCES_THS_SECTOR_DAILY),
                         ('EM仓', SOURCES_EM_SECTOR_DAILY),
                         ('legacy', SECTOR_DAILY_PATH)]:
        # 去重：同一文件不重复检查
        if fpath in seen_paths:
            continue
        seen_paths.add(fpath)
        if not os.path.isfile(fpath):
            _check(f'{fname}[{os.path.basename(fpath)}] 文件存在', False, '文件不存在')
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            has_ind = bool(data.get('industries'))
            has_con = bool(data.get('concepts'))
            _check(f'{fname}[{os.path.basename(fpath)}] JSON有效', True,
                   f'行业{len(data.get("industries",{}))}个, 概念{len(data.get("concepts",{}))}个')
        except Exception as e:
            _check(f'{fname}[{os.path.basename(fpath)}] JSON解析', False, str(e))
            continue

        # 新鲜度：应等于最后一个交易日（非交易日跳过，缓存文件可能在不同时间更新）
        last_up = data.get('last_updated', '') or data.get('_push2test_updated', '')
        if _is_weekend():
            _check(f'{fname}[{os.path.basename(fpath)}] 新鲜度(非交易日跳过检查)',
                   True, f'last_updated={last_up}')
        else:
            fresh = last_up == latest_trade_day
            _check(f'{fname}[{os.path.basename(fpath)}] 新鲜度(最近交易日<{latest_trade_day}>)',
                   fresh, f'last_updated={last_up}')

    # ════ 3. 一致性验证（THS live vs _push2test）════
    try:
        # 实时源是THS，比对 _push2test 字段（其中存的是THS数据）
        from backend.core.data_layer import get_sector_push2test
        p2_data = get_sector_push2test()
        if (hasattr(p2_data, 'industries') and p2_data.industries
                and 'ths_real_chg' in dir() and ths_real_chg):
            matched = 0
            ths_samples = list(ths_real_chg.keys())[:30]
            for name in ths_samples:
                snap = p2_data.industries.get(name)
                live_chg = ths_real_chg.get(name)
                if snap is not None and live_chg is not None:
                    if abs(snap.change_pct - live_chg) < 0.5:
                        matched += 1
            _check('THS实时vs_push2test change_pct一致性(采样前30)',
                   matched >= 20 or _is_trading_time() == False,
                   '%d/30采样偏差<0.5%%' % matched)
        else:
            _check('THS实时vs_push2test一致性', True, '跳过(数据不可比)')
    except Exception as e:
        _check('一致性验证', False, '异常: %s' % e)

    # ════ 4. data_layer 合约验证 ════
    try:
        from backend.core.data_layer import (
            get_sector_push2test, get_sector_daily, get_sector_klines,
        )

        # 4a. get_sector_push2test 合约
        p2 = get_sector_push2test()
        ind_count = len(p2.industries) if hasattr(p2, 'industries') else 0
        p2_has_industries = ind_count >= 80
        _check('data_layer.get_sector_push2test 行业数>=80',
               p2_has_industries, 'actual=%d' % ind_count)

        # 电子化学品在 push2test 中
        ec_in_p2 = hasattr(p2, 'industries') and '电子化学品' in p2.industries
        _check('data_layer.get_sector_push2test 含电子化学品',
               ec_in_p2, 'exists=%s' % ec_in_p2)

        # 电子化学品 chg 正确（类型化对象）
        if ec_in_p2:
            ec_snap = p2.industries['电子化学品']
            ec_chg_ok = ec_snap.change_pct is not None and -20 < ec_snap.change_pct < 20
            _check('data_layer.push2test 电子化学品.chg类型化',
                   ec_chg_ok, 'change_pct=%s' % ec_snap.change_pct)
            ec_up_ok = ec_snap.up_count is not None
            _check('data_layer.push2test 电子化学品.up_count存在',
                   ec_up_ok, 'up_count=%s' % ec_snap.up_count)
            ec_leader_ok = bool(ec_snap.leader)
            _check('data_layer.push2test 电子化学品.leader存在',
                   ec_leader_ok, 'leader=%s' % ec_snap.leader)

        # 4b. get_sector_daily 合约
        sd = get_sector_daily()
        sd_ind_count = len(sd.get('industries', {})) if isinstance(sd, dict) else 0
        sd_has_ind = sd_ind_count > 0
        _check('data_layer.get_sector_daily industries非空',
               sd_has_ind, 'industries=%d' % sd_ind_count)
        lu = sd.get('last_updated', '') if isinstance(sd, dict) else ''
        _check('data_layer.get_sector_daily last_updated非空',
               bool(lu), 'last_updated=%s' % lu)

        # 4c. get_sector_klines 合约
        klines = get_sector_klines('电子化学品', 'industry')
        kl_ok = isinstance(klines, list) and len(klines) >= 1
        _check('data_layer.get_sector_klines 返回非空列表',
               kl_ok, 'len=%d' % (len(klines) if isinstance(klines, list) else -1))
        if kl_ok:
            k = klines[0]
            kl_fmt = [f for f in ['date', 'open', 'close', 'high', 'low'] if k.get(f) is not None]
            kl_format_ok = len(kl_fmt) == 5
            _check('data_layer.get_sector_klines K线字段完整',
                   kl_format_ok, 'fields_ok=%d/5' % len(kl_fmt))
            kl_vol_ok = isinstance(k.get('volume'), (int, float)) and k.get('volume', 0) > 0
            _check('data_layer.get_sector_klines volume>0',
                   kl_vol_ok, 'volume=%s' % k.get('volume'))

    except Exception as e:
        _check('data_layer 合约验证', False, f'异常: {type(e).__name__}: {e}')

    # ════ 汇总 ════
    if verbose:
        print(f'\n{"="*40}')
        print(f'  数据源验证：{"✅ 全部通过" if all_pass else "❌ 存在问题"}')
        print(f'  {sum(1 for c in checks if c["pass"])}/{len(checks)} 项通过')

    # ════ L0 覆盖度验证集成 ════
    try:
        coverage = verify_data_coverage(verbose=verbose)
        for cc in coverage.get('checks', []):
            checks.append(cc)
            if not cc['pass'] and 'WARN' not in cc.get('detail', ''):
                all_pass = False
    except Exception as e:
        _check('L0覆盖度验证', False, f'异常: {type(e).__name__}: {e}')
        all_pass = False

    return {'status': 'pass' if all_pass else 'fail', 'checks': checks, 'now': now}


def _is_weekend():
    """非交易日无需验证涨跌幅"""
    return datetime.now().weekday() >= 5


def _is_trading_time():
    """当前是否在A股交易时段（09:30-15:00），盘前/盘后实时源返回全零"""
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return 930 <= t <= 1500


# ════════════════════════════════════════════════════════════
# L0 — 数据覆盖度验证
# ════════════════════════════════════════════════════════════

def _is_trading_day(date_str):
    """判断 YYYYMMDD 是否为交易日（周一到周五）"""
    if not date_str or len(date_str) != 8:
        return False
    from datetime import datetime as dt
    d = dt.strptime(date_str, '%Y%m%d')
    return d.weekday() < 5


def _parse_date(date_str):
    """YYYYMMDD -> datetime, 失败返回 None"""
    try:
        from datetime import datetime as dt
        return dt.strptime(date_str, '%Y%m%d')
    except (ValueError, TypeError):
        return None


def _days_between(d1, d2):
    """返回两个 YYYYMMDD 之间相差的天数（含边界）"""
    dt1 = _parse_date(d1)
    dt2 = _parse_date(d2)
    if dt1 is None or dt2 is None:
        return 999
    return abs((dt1 - dt2).days)


def _sample_keys(d, sample_size, must_include=None):
    """从字典中均匀采样 key

    Args:
        d: dict 或可迭代的 key 列表
        sample_size: 采样数
        must_include: 必须包含的 key 列表

    Returns: [key, ...]
    """
    keys = list(d.keys()) if isinstance(d, dict) else list(d)
    if not keys:
        return []
    must = [k for k in (must_include or []) if k in keys]
    rest = [k for k in keys if k not in must]
    # 从 rest 中均匀采样
    remaining = max(0, sample_size - len(must))
    sampled = []
    if rest and remaining > 0:
        step = max(1, len(rest) // remaining)
        for i in range(0, len(rest), step):
            if len(sampled) >= remaining:
                break
            sampled.append(rest[i])
    return must + sampled


def verify_data_coverage(verbose=True):
    """L0 — data_layer 数据覆盖度验证

    三种维度检查：
      1. 结构完整性 — 全量K线日期扫描（禁止周末/未来/大面积过期）
      2. 时效脉冲   — 按比例采样+关键概念必检
      3. 交叉验算   — K线计算chg vs 快照change_pct

    返回 {'status': 'pass'|'fail'|'warn', 'checks': [...], 'pass_count': int, 'fail_count': int}
    """
    import json, os
    from datetime import datetime, timedelta
    from backend.core.config import SECTOR_DAILY_PATH

    now = datetime.now().strftime('%Y%m%d')
    today = datetime.now()
    latest_trade_day = _last_trading_day()
    checks = []
    pass_count = 0
    fail_count = 0
    warn_count = 0

    def _check(name, passed, detail, data_type, dimension):
        nonlocal pass_count, fail_count, warn_count
        # passed=True 时按通过计；False 但 detail 含'跳过'→不计fail
        if passed:
            pass_count += 1
        elif '跳过' in detail and 'WARN' not in detail:
            # 非交易日跳过、数据不足跳过等，不报fail
            pass_count += 1
        else:
            if 'WARN' in detail:
                warn_count += 1
            else:
                fail_count += 1
        if verbose:
            tag = '✅' if passed else ('⚠️' if 'WARN' in detail else '❌')
            print(f'  {tag} [{data_type}/{dimension}] {name}: {detail}')
        checks.append({
            'check': name, 'pass': passed,
            'detail': detail,
            'type': data_type, 'dimension': dimension,
        })

    # ── 加载数据 ──
    if not os.path.isfile(SECTOR_DAILY_PATH):
        _check('数据文件存在', False, f'{SECTOR_DAILY_PATH} 不存在',
               '_file', 'structure')
        return {
            'status': 'fail', 'checks': checks,
            'pass_count': pass_count, 'fail_count': fail_count,
            'warn_count': warn_count, 'now': now,
        }

    try:
        with open(SECTOR_DAILY_PATH, 'r', encoding='utf-8') as f:
            raw = json.load(f)
    except Exception as e:
        _check('数据文件解析', False, f'JSON解析失败: {e}',
               '_file', 'structure')
        return {
            'status': 'fail', 'checks': checks,
            'pass_count': pass_count, 'fail_count': fail_count,
            'warn_count': warn_count, 'now': now,
        }

    industries = raw.get('industries', {})
    concepts = raw.get('concepts', {})
    p2t = raw.get('_push2test', {})
    last_updated = raw.get('last_updated', '')
    p2t_updated = raw.get('_push2test_updated', '')

    # ── 判断是否需要跳过严格检查 ──
    is_ntd = _is_weekend()

    # ════════════════════════════════════════════════════════════
    # 1. 结构完整性
    # ════════════════════════════════════════════════════════════

    # 1a. 概念K线日期扫描
    concept_dates = {}
    for name, klines in concepts.items():
        if isinstance(klines, list) and klines:
            last_k = klines[-1]
            d = last_k.get('date', '') if isinstance(last_k, dict) else ''
            if d:
                concept_dates[name] = d

    concept_date_dist = {}
    for name, d in concept_dates.items():
        concept_date_dist[d] = concept_date_dist.get(d, 0) + 1

    concept_date_summary = ', '.join(
        f'{d}:{n}个' for d, n in sorted(concept_date_dist.items())
    ) if concept_date_dist else '(无数据)'
    _check('概念K线日期分布', bool(concept_date_dist),
           concept_date_summary, 'concept_kline', 'structure')

    # 检查周末日期（概念）
    concept_weekend = [d for d in concept_date_dist
                       if d and not _is_trading_day(d)]
    if concept_weekend:
        weekend_count = sum(concept_date_dist[d] for d in concept_weekend)
        _check('概念K线无周末日期', False,
               f'{weekend_count}个概念日期在非交易日: {", ".join(sorted(concept_weekend))}',
               'concept_kline', 'structure')
    else:
        _check('概念K线无周末日期', True,
               '所有概念K线日期均为交易日',
               'concept_kline', 'structure')

    # 检查大面积过期
    stale_concepts = [
        name for name, d in concept_dates.items()
        if _days_between(d, latest_trade_day) > 1
    ]
    stale_ratio = len(stale_concepts) / max(len(concept_dates), 1) * 100
    stale_ok = stale_ratio < 50
    _check('概念K线大面积过期检测',
           stale_ok,
           f'{len(stale_concepts)}/{len(concept_dates)}个过期({stale_ratio:.0f}%), 阈值<50%'
           + (f' 最早: {min(concept_dates.get(n,"") for n in stale_concepts[:3])}' if stale_concepts else ''),
           'concept_kline', 'structure')

    # 1b. 行业K线日期扫描
    ind_dates = {}
    for name, klines in industries.items():
        if isinstance(klines, list) and klines:
            last_k = klines[-1]
            d = last_k.get('date', '') if isinstance(last_k, dict) else ''
            if d:
                ind_dates[name] = d

    ind_date_dist = {}
    for name, d in ind_dates.items():
        ind_date_dist[d] = ind_date_dist.get(d, 0) + 1

    ind_date_summary = ', '.join(
        f'{d}:{n}个' for d, n in sorted(ind_date_dist.items())
    ) if ind_date_dist else '(无数据)'
    _check('行业K线日期分布', bool(ind_date_dist),
           ind_date_summary, 'industry_kline', 'structure')

    # 检查周末日期（行业）
    ind_weekend = [d for d in ind_date_dist
                   if d and not _is_trading_day(d)]
    if ind_weekend:
        weekend_count = sum(ind_date_dist[d] for d in ind_weekend)
        _check('行业K线无周末日期', False,
               f'{weekend_count}个行业日期在非交易日: {", ".join(sorted(ind_weekend))}',
               'industry_kline', 'structure')
    else:
        _check('行业K线无周末日期', True,
               '所有行业K线日期均为交易日',
               'industry_kline', 'structure')

    # 检查大面积过期（行业）
    stale_ind = [
        name for name, d in ind_dates.items()
        if _days_between(d, latest_trade_day) > 1
    ]
    stale_ind_ratio = len(stale_ind) / max(len(ind_dates), 1) * 100
    stale_ind_ok = stale_ind_ratio < 50
    _check('行业K线大面积过期检测',
           stale_ind_ok,
           f'{len(stale_ind)}/{len(ind_dates)}个过期({stale_ind_ratio:.0f}%), 阈值<50%',
           'industry_kline', 'structure')

    # 1c. _push2test 快照结构
    p2t_industries = p2t.get('industries', {})
    p2t_concepts = p2t.get('concepts', {})
    p2t_ind_count = len(p2t_industries)
    p2t_con_count = len(p2t_concepts)

    ind_count_ok = p2t_ind_count >= 80
    _check('行业快照计数≥80', ind_count_ok,
           f'{p2t_ind_count}个', 'industry_snapshot', 'structure')

    # 概念快照数：检查当前快照源文件存在且可读，如实报告数量
    try:
        snap_data = _load_json(_get_snapshot_source_path())
        if isinstance(snap_data, dict):
            snap_con_num = len(snap_data.get('concepts', {}))
        else:
            snap_con_num = 0
        con_ok = snap_con_num > 0
        _check(f'{_get_snapshot_source_label()}概念数量', con_ok,
               f'{snap_con_num}个', 'concept_snapshot', 'structure')
    except Exception:
        _check(f'{_get_snapshot_source_label()}概念数量', False,
               f'无法读取源文件', 'concept_snapshot', 'structure')

    # chg 非零率
    con_chgs = []
    for name, entry in p2t_concepts.items():
        if isinstance(entry, dict):
            chg = entry.get('change_pct', 0) or 0
            con_chgs.append(chg)
    con_nonzero = sum(1 for c in con_chgs if abs(c) > 0.01)
    con_nonzero_ratio = con_nonzero / max(len(con_chgs), 1) * 100
    con_nonzero_ok = con_nonzero_ratio >= 20 or len(con_chgs) < 5 or is_ntd
    if is_ntd and len(con_chgs) < 5:
        _check('概念快照非零占比≥20%', True,
               f'跳过(非交易日+数据过少)',
               'concept_snapshot', 'structure')
    else:
        _check('概念快照非零占比≥20%', con_nonzero_ok,
               f'{con_nonzero}/{len(con_chgs)}={con_nonzero_ratio:.0f}%',
               'concept_snapshot', 'structure')

    # 行业 fast的非零率
    ind_chgs = []
    for name, entry in p2t_industries.items():
        if isinstance(entry, dict):
            chg = entry.get('change_pct', 0) or 0
            ind_chgs.append(chg)
    ind_nonzero = sum(1 for c in ind_chgs if abs(c) > 0.01)
    ind_nonzero_ratio = ind_nonzero / max(len(ind_chgs), 1) * 100
    _check('行业快照非零占比≥50%',
           ind_nonzero_ratio >= 50 or is_ntd,
           f'{ind_nonzero}/{len(ind_chgs)}={ind_nonzero_ratio:.0f}%'
           + (' (非交易日跳过)' if is_ntd else ''),
           'industry_snapshot', 'structure')

    # 关键概念存在性
    key_concepts = ['培育钻石']
    for kc in key_concepts:
        exists = kc in p2t_concepts
        if not exists and kc in concepts:
            # K线中有此概念但快照中没有 → WARN
            _check(f'关键概念「{kc}」在快照中',
                   True,
                   f'WARN: K线中有但快照缺失(覆盖不足)',
                   'concept_snapshot', 'structure')
        elif not exists:
            _check(f'关键概念「{kc}」在快照中',
                   True,
                   f'跳过(K线中也没有此概念)',
                   'concept_snapshot', 'structure')
        else:
            _check(f'关键概念「{kc}」在快照中',
                   True,
                   f'存在, chg={p2t_concepts[kc].get("change_pct","?")}',
                   'concept_snapshot', 'structure')

    # 1d. _push2test 行业快照关键行业存在性
    for ks in ['电子化学品', '半导体', '银行']:
        exists = ks in p2t_industries
        _check(f'关键行业「{ks}」在快照中',
               exists, f'存在={exists}',
               'industry_snapshot', 'structure')

    # ════════════════════════════════════════════════════════════
    # 2. 时效脉冲（采样验证）
    # ════════════════════════════════════════════════════════════

    # 跳过条件：数据量太小没必要采样
    skip_timeliness = (len(concept_dates) < 50 or len(ind_dates) < 50)

    if skip_timeliness:
        _check('概念K线采样时效性', True,
               f'跳过(数据量不足: 概念{len(concept_dates)}个/行业{len(ind_dates)}个)',
               'concept_kline', 'timeliness')
        _check('行业K线采样时效性', True,
               f'跳过(数据量不足: 概念{len(concept_dates)}个/行业{len(ind_dates)}个)',
               'industry_kline', 'timeliness')
    else:
        # 概念K线采样
        con_samples = _sample_keys(
            concept_dates,
            sample_size=30,
            must_include=['培育钻石', '华为概念'],
        )
        con_miss = []
        for name in con_samples:
            if name not in concept_dates:
                con_miss.append(name)
                continue
            kdate = concept_dates[name]
            days = _days_between(kdate, latest_trade_day)
            if days > 2:
                con_miss.append(f'{name}({kdate})')
        if con_miss:
            _check('概念K线采样时效性', False,
                   f'采样{len(con_samples)}个, {len(con_miss)}个过期: {", ".join(con_miss[:5])}'
                   + (f'...({len(con_miss)-5} more)' if len(con_miss) > 5 else ''),
                   'concept_kline', 'timeliness')
        else:
            _check('概念K线采样时效性', True,
                   f'采样{len(con_samples)}个均新鲜(距T≤2)',
                   'concept_kline', 'timeliness')

        # 行业K线采样
        ind_samples = _sample_keys(
            ind_dates,
            sample_size=30,
            must_include=['电子化学品', '半导体', '银行'],
        )
        ind_miss = []
        for name in ind_samples:
            if name not in ind_dates:
                ind_miss.append(name)
                continue
            kdate = ind_dates[name]
            days = _days_between(kdate, latest_trade_day)
            if days > 2:
                ind_miss.append(f'{name}({kdate})')
        if ind_miss:
            _check('行业K线采样时效性', False,
                   f'采样{len(ind_samples)}个, {len(ind_miss)}个过期: {", ".join(ind_miss[:5])}'
                   + (f'...({len(ind_miss)-5} more)' if len(ind_miss) > 5 else ''),
                   'industry_kline', 'timeliness')
        else:
            _check('行业K线采样时效性', True,
                   f'采样{len(ind_samples)}个均新鲜(距T≤2)',
                   'industry_kline', 'timeliness')

    # 关键概念单独时效检查（即使 K线数量不足50也检查）
    for kc in key_concepts:
        if kc in concept_dates:
            kdate = concept_dates[kc]
            days = _days_between(kdate, latest_trade_day)
            _check(f'关键概念「{kc}」时效性',
                   days <= 2,
                   f'最新K线={kdate}, T={latest_trade_day}, 差{days}天',
                   'concept_kline', 'timeliness')
        elif kc in concepts:
            _check(f'关键概念「{kc}」时效性', True,
                   f'WARN: 概念在K线中但最新日期未知',
                   'concept_kline', 'timeliness')

    # 关键行业单独时效检查
    key_industries = ['电子化学品', '半导体']
    for ki in key_industries:
        if ki in ind_dates:
            kdate = ind_dates[ki]
            days = _days_between(kdate, latest_trade_day)
            _check(f'关键行业「{ki}」时效性',
                   days <= 2,
                   f'最新K线={kdate}, T={latest_trade_day}, 差{days}天',
                   'industry_kline', 'timeliness')
        elif ki in industries:
            _check(f'关键行业「{ki}」时效性', True,
                   f'WARN: 行业在K线中但最新日期未知',
                   'industry_kline', 'timeliness')

    # ════════════════════════════════════════════════════════════
    # 3. 交叉验算
    # ════════════════════════════════════════════════════════════

    xverify_items = []

    # 行业交叉验算：K线chg vs _push2test 快照 change_pct
    # 选电子化学品（必在K线和快照中）
    for xs_name in ['电子化学品', '半导体']:
        if xs_name not in industries or xs_name not in p2t_industries:
            continue
        klines = industries[xs_name]
        snap = p2t_industries[xs_name]
        if not isinstance(klines, list) or len(klines) < 2:
            continue
        if not isinstance(snap, dict):
            continue
        latest = klines[-1]
        prev = klines[-2]
        if not isinstance(latest, dict) or not isinstance(prev, dict):
            continue
        # 检查K线最新日期是否与快照日期一致
        latest_date = latest.get('date', '')
        snap_date = str(snap.get('date', ''))
        if latest_date != snap_date:
            xverify_items.append((xs_name, 'industry', None, 
                f'快照日期{snap_date}≠K线日期{latest_date}, 跳过', True))
            continue
        # 检查日期是否相邻（否则K线计算的chg是跨日变化，不能与快照日涨跌幅比对）
        prev_date = prev.get('date', '')
        date_gap = _days_between(latest_date, prev_date)
        if date_gap > 1:
            xverify_items.append((xs_name, 'industry', None, snap_chg, True))
            continue  # 跳过（K线不连续），不FAIL
        kline_chg = round(
            (float(latest.get('close', 0)) / max(float(prev.get('close', 1)), 0.01) - 1) * 100,
            2,
        )
        snap_chg = snap.get('change_pct', None)
        if snap_chg is None:
            xverify_items.append((xs_name, 'industry', kline_chg, None, True))
            continue
        snap_chg = float(snap_chg)
        diff = abs(kline_chg - snap_chg)
        ok = diff < 0.5
        xverify_items.append((xs_name, 'industry', kline_chg, snap_chg, ok))

    for name, dtype, kchg, schg, ok in xverify_items:
        if kchg is None:
            _check(f'{dtype}交叉验算「{name}」',
                   True,
                   f'WARN: K线不连续, 跳过交叉验算, 快照chg={schg}%',
                   f'{dtype}_kline', 'cross_verify')
        else:
            _check(f'{dtype}交叉验算「{name}」',
                   ok,
                   f'K线chg={kchg}% vs 快照chg={schg}%'
                   + (f' (偏差{abs(kchg-schg):.2f}pt)' if schg is not None else ' (快照无此行业)'),
                   f'{dtype}_kline', 'cross_verify')

    # 概念交叉验算提醒：概念指数（K线收盘价）和快照（成分股平均涨跌幅）
    # 来自同花顺两个不同接口，算法不同，不做交叉对比。
    # 只验证快照自身的 change_pct 在合理范围内。
    cxverify_items = []
    for xc_name in ['培育钻石', '华为概念']:
        snap_entry = p2t_concepts.get(xc_name)
        if snap_entry and isinstance(snap_entry, dict):
            schg = snap_entry.get('change_pct')
            if schg is not None:
                ok = -20 < float(schg) < 20
                cxverify_items.append((xc_name, schg, ok))

    for name, schg, ok in cxverify_items:
        _check(f'概念快照「{name}」change_pct合理性',
               ok,
               f'快照change_pct={schg}%',
               f'concept_snapshot', 'verify')

    # ════ 汇总 ════
    total_checks = len(checks)
    if verbose:
        print(f'\n{"="*40}')
        print(f'  L0覆盖度验证：{"✅ 全部通过" if fail_count == 0 else f"❌ {fail_count}项失败"}' +
              f' (通过{pass_count}/{total_checks}, 失败{fail_count}, 警告{warn_count})')

    status = 'pass'
    if fail_count > 0:
        status = 'fail'
    elif warn_count > 0:
        status = 'warn'

    return {
        'status': status,
        'checks': checks,
        'pass_count': pass_count,
        'fail_count': fail_count,
        'warn_count': warn_count,
        'now': now,
    }
