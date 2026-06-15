#!/usr/bin/env python3
"""
统一数据层 — 所有股票数据的单一入口（服务器侧）

共享函数从 threel_core.data_layer 转发（加缓存包装），
服务器特有函数（写入/指数/板块/概念等）原地实现。

架构：
  data_access/data_layer.py  ← 本次文件（门面）
         ↓
  threel_core/data_layer.py  ← 共享只读函数
  data_access/data_source.py  ← 多源路由
  data_access/tushare_db.py   ← MySQL驱动
"""
import json, os
from datetime import datetime
from backend.data_access.cache_layer import cache
from backend.core.logger import get_logger

log = get_logger(__name__)
from backend.core.config import (
    DATA_DIR, WWW_DIR, CACHE_DIR, PRIVATE_DIR,
    ALL_STOCKS_PATH, WATCHLIST_PATH, INDUSTRY_MAP_PATH,
    SUB_SECTOR_CLUSTERS_PATH, FINANCIAL_CACHE_PATH,
    PROFIT_QUALITY_PATH, INDEX_DATA_PATH, SECTOR_DAILY_PATH,
    INDUSTRY_LEADERS_PATH,
    LATEST_SCAN_PATH, ALL_CODES_PATH, KEY_POINTS_DIR,
    HOLDINGS_PATH, TRADES_PATH, REVIEW_ARCHIVE_DIR,
    REVIEW_CHARTS_DIR, SCRIPTS_DIR, SIMULATION_DIR,
    MAINLINES_CACHE_PATH,
    SIMULATION_V3_DIR as OUTPUT_DIR,
    CONCEPT_LIST_PATH, STOCK_CONCEPT_MAP_PATH,
    CHARTS_DIR,
)

# ====== 共享函数 — 从 threel_core 转发（加缓存）======

from threel_core.data_layer import (
    get_all_stocks as _threel_get_all_stocks,
    get_stock_klines as _threel_get_stock_klines,
    get_watchlist as _threel_get_watchlist,
    get_industry_map as _threel_get_industry_map,
    resolve_stock as _threel_resolve_stock,
    search_stock_full_market as _threel_search_stock_full_market,
    seen_local as _threel_seen_local,
    get_last_updated as _threel_get_last_updated,
)


def get_all_stocks():
    """主入口：从 MySQL 读取K线数据，按方向分组（缓存30s）"""
    try:
        return cache.get('all_stocks', _threel_get_all_stocks, ttl=30)
    except Exception as e:
        log.warning('获取K线失败(%s)，返回空', e)
        return {'last_updated': ''}


# 保留这个别名（update_stock_data.py 等使用）
get_all_stocks_db = _threel_get_all_stocks


def get_stock_klines(code, direction=None, stocks=None):
    """获取单只股票K线列表（优先从 stocks 参数找，回退DB）"""
    if stocks is None:
        stocks = get_all_stocks()
    if direction and direction in stocks and code in stocks[direction]:
        return stocks[direction][code]
    for sec, codes in stocks.items():
        if code in codes:
            return codes[code]
    # DB回退
    return _threel_get_stock_klines(code)


def get_watchlist():
    """返回自选股列表（缓存10s）"""
    return cache.get('watchlist', _threel_get_watchlist, ttl=10)


def get_watchlist_by_direction():
    """返回 {direction: [{'code':..., 'name':...}, ...]}"""
    from threel_core.data_layer import get_watchlist_by_direction
    return get_watchlist_by_direction()


def get_industry_map():
    """返回行业映射（缓存60s）"""
    return cache.get('industry_map', _threel_get_industry_map, ttl=60)


def get_last_updated():
    """返回最新交易日 YYYYMMDD"""
    return _threel_get_last_updated()


def resolve_stock(query, stocks=None):
    """搜索股票"""
    if stocks is None:
        stocks = get_all_stocks()
    return _threel_resolve_stock(query, stocks)


def search_stock_full_market(query, max_results=20):
    """全市场搜索"""
    return _threel_search_stock_full_market(query, max_results)


def seen_local(code, stocks_data):
    """检查股票是否在本地缓存中"""
    return _threel_seen_local(code, stocks_data)


# ====== 通用工具 ======

def _load_json(path, default=None):
    if not os.path.exists(path):
        return default if default is not None else {}
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        log.warning('读 %s 失败: %s', path, e)
        return default if default is not None else {}


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _atomic_save_json(path, data):
    """原子写入：临时文件 → rename"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    os.rename(tmp, path)


# ====== 写入K线 ======

def save_all_stocks(stocks, last_updated=None):
    """保存K线数据到DB（通过 data_source）"""
    from backend.data_access.data_source import save_stock_klines_to_db

    stock_data = {}
    for direction, codes in stocks.items():
        if direction == 'last_updated':
            continue
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            stock_data[code] = {'klines': klines, 'name': name}

    total = save_stock_klines_to_db(stock_data)
    cache.invalidate('all_stocks')
    _clear_stock_chart_svg_cache()
    if total:
        log.info('save_all_stocks: %d条写入DB', total)


def _clear_stock_chart_svg_cache():
    """清除所有个股SVG图表缓存"""
    try:
        if not os.path.isdir(CHARTS_DIR):
            return
        removed = 0
        for fname in os.listdir(CHARTS_DIR):
            if fname.startswith('zzqz_stock_chart_') and fname.endswith('.svg'):
                os.remove(os.path.join(CHARTS_DIR, fname))
                removed += 1
            elif fname.startswith('zzqz_trend_stock_chart_') and fname.endswith('.svg'):
                os.remove(os.path.join(CHARTS_DIR, fname))
                removed += 1
        if removed:
            log.info('已清除%d个SVG图表缓存', removed)
    except Exception:
        log.warning('SVG图表缓存清理异常')


# ====== 指数数据 ======

INDEX_CODE = '000985'
INDEX_CODES = {
    '000001': '上证指数',
    '000688': '科创50',
    '000985': '中证全指',
    '399006': '创业板指',
}


def get_index_data():
    """从 MySQL 读取指数数据（缓存60s）"""
    try:
        from backend.data_access.data_source import get_index_data_from_db
        indices = get_index_data_from_db(INDEX_CODES)
        if indices:
            latest = max((v['klines'][0]['date'] for v in indices.values() if v['klines']), default='')
            return {'last_updated': latest, 'indices': indices}
    except Exception as e:
        log.warning('DB获取指数失败(%s)', e)
    return {'last_updated': '', 'indices': {}}


def save_index_data(data):
    """保存指数数据到DB"""
    from backend.data_access.data_source import save_index_klines_to_db
    cache.invalidate('index_data')
    indices = data.get('indices', {})
    total = save_index_klines_to_db(indices)
    if total:
        log.info('save_index_data: %d条写入DB', total)


def get_index_klines(code=INDEX_CODE):
    """返回指定指数代码的K线列表"""
    data = get_index_data()
    indices = data.get('indices', {})
    info = indices.get(code, {})
    return info.get('klines', [])


# ====== 板块日K线 ======

def get_sector_daily():
    """返回 {last_updated, industries, concepts}（缓存60s）"""
    def _load_from_data_source():
        try:
            from backend.data_access.data_source import get_merged_sector_data
            return get_merged_sector_data()
        except Exception:
            return _load_json(SECTOR_DAILY_PATH, {})
    return cache.get('sector_daily', _load_from_data_source, ttl=60)


def save_sector_daily(data):
    """原子保存板块日K线数据"""
    _atomic_save_json(SECTOR_DAILY_PATH, data)
    cache.invalidate('sector_daily')


def load_sector_daily_uncached():
    """强制从磁盘读取（不走缓存）"""
    return _load_json(SECTOR_DAILY_PATH, {})


def get_sector_push2test():
    """获取当日涨跌幅快照（_push2test 字段）"""
    from backend.models.data_models import SectorPush2Test, ths_dict_to_snapshot, push2test_dict_to_snapshot
    data = _load_json(SECTOR_DAILY_PATH, {})
    raw = data.get('_push2test', {})
    if not isinstance(raw, dict):
        return SectorPush2Test()

    industries = {}
    for name, entry in raw.get('industries', {}).items():
        if isinstance(entry, dict):
            industries[name] = ths_dict_to_snapshot(entry)

    concepts = {}
    for name, entry in raw.get('concepts', {}).items():
        if isinstance(entry, dict):
            concepts[name] = push2test_dict_to_snapshot(entry)

    return SectorPush2Test(industries=industries, concepts=concepts)


def get_sector_klines(sector_name, sector_type='industry'):
    """获取单个板块历史K线数据"""
    try:
        from backend.data_access.data_source import get_sector_klines as _ds_klines
        return _ds_klines(sector_name, sector_type)
    except Exception:
        data = _load_json(SECTOR_DAILY_PATH, {})
        key = 'industries' if sector_type == 'industry' else 'concepts'
        return data.get(key, {}).get(sector_name, [])


# ====== 概念快照 ======

def get_concept_snapshots(name_list: list = None) -> dict:
    """获取概念板块今日快照数据"""
    try:
        from backend.data_access.data_source import get_concept_snapshots as _ds_get
        return _ds_get(name_list)
    except Exception as e:
        log.warning('get_concept_snapshots 失败: %s', e)
        return {}


def get_concept_klines(name_list: list) -> dict:
    """获取概念板块最新日K线数据"""
    try:
        from backend.data_access.data_source import get_concept_klines as _ds_klines
        return _ds_klines(name_list)
    except Exception as e:
        log.warning('get_concept_klines 失败: %s', e)
        return {}


def get_ths_industry_klines(ths_type='I', limit=120):
    """从 ths_daily 读取行业/概念K线数据

    Args:
        ths_type: 'I'=行业, 'N'=概念, 'BB'=板块
        limit: 每行业最多K线条数

    Returns:
        {name: [{date, open, close, high, low, volume}, ...], ...}
        名称与 sector_daily.json 的 industries/concepts 格式兼容
    """
    try:
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        if not db:
            return {}

        # 查 ths_index 获取 ts_code → name 映射
        idx_rows = db.execute_raw(
            "SELECT ts_code, name FROM ths_index WHERE type=%s ORDER BY name",
            [ths_type]
        )
        if not idx_rows:
            return {}

        ts_codes = [r['ts_code'] for r in idx_rows]
        name_map = {r['ts_code']: r['name'] for r in idx_rows}

        # 批量查 ths_daily
        placeholders = ','.join(['%s'] * len(ts_codes))
        rows = db.execute_raw(
            f"SELECT ts_code, trade_date, open, high, low, close, vol "
            f"FROM ths_daily WHERE ts_code IN ({placeholders}) "
            f"ORDER BY ts_code, trade_date DESC",
            ts_codes
        )

        # 按 ts_code 分组，每组取最新 limit 条
        raw_groups = {}
        for r in rows:
            tc = r['ts_code']
            if tc not in raw_groups:
                raw_groups[tc] = []
            if len(raw_groups[tc]) < limit:
                raw_groups[tc].append(r)

        # 转为 {name: [{date, open, close, high, low, volume}, ...]} 格式（升序）
        result = {}
        for tc, group in raw_groups.items():
            name = name_map.get(tc, tc)
            # 按 trade_date 升序（旧→新）
            group.sort(key=lambda x: x['trade_date'])
            klines = []
            for r in group:
                klines.append({
                    'date': r['trade_date'],
                    'open': float(r['open']) if r['open'] else 0,
                    'close': float(r['close']) if r['close'] else 0,
                    'high': float(r['high']) if r['high'] else 0,
                    'low': float(r['low']) if r['low'] else 0,
                    'volume': int(r['vol']) if r['vol'] else 0,
                })
            result[name] = klines

        return result
    except Exception as e:
        log.warning('get_ths_industry_klines 失败: %s', e)
        return {}


# ====== 数据源验证 ======

def verify_data_sources(verbose=False):
    """验证所有数据源的正确性、及时性、缓存一致性"""
    try:
        from backend.data_access.data_source import verify_data_sources as _ds_verify
        return _ds_verify(verbose=verbose)
    except Exception as e:
        return {'status': 'fail', 'error': str(e), 'checks': [], 'pass_count': 0, 'fail_count': 1}


# ====== 写入映射 ======

def save_industry_map(data):
    """原子保存行业映射"""
    _atomic_save_json(INDUSTRY_MAP_PATH, data)
    cache.invalidate('industry_map')


# ====== 概念板块映射 ======

def get_concept_list():
    """返回 {code: {name, stock_count, stocks}}（缓存60s）"""
    return cache.get('concept_list', lambda: _load_json(CONCEPT_LIST_PATH, {}), ttl=60)


def save_concept_list(data):
    """原子保存概念列表"""
    _atomic_save_json(CONCEPT_LIST_PATH, data)
    cache.invalidate('concept_list')


def get_stock_concept_map():
    """返回 {code: {code, name, concept_codes, concept_names}}（缓存60s）"""
    return cache.get('stock_concept_map', lambda: _load_json(STOCK_CONCEPT_MAP_PATH, {}), ttl=60)


def save_stock_concept_map(data):
    """原子保存个股概念映射"""
    _atomic_save_json(STOCK_CONCEPT_MAP_PATH, data)
    cache.invalidate('stock_concept_map')


# ====== 补数据 ======

def ensure_stock_data(code):
    """确保股票在本地缓存中有K线数据，没有则从腾讯接口拉取

    Returns: (success, message)
    """
    stocks_data = get_all_stocks()
    imap = get_industry_map()

    local_code = code
    for pfx in ['SH', 'SZ', 'sh', 'sz']:
        if code.startswith(pfx):
            local_code = code[len(pfx):]
            break
    local_code = local_code[-6:] if len(local_code) >= 6 else local_code

    for sec, codes in stocks_data.items():
        if local_code in codes:
            return (True, '已有数据')

    # 没有，拉取
    try:
        import requests
        prefix = 'sh' if local_code.startswith('6') else 'sz'
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{local_code},day,,,60,qfq'
        r = requests.get(url, timeout=15)
        raw = r.json()
        data_node = raw.get('data', {})
        if not isinstance(data_node, dict):
            return (False, f'API返回异常: data字段类型={type(data_node).__name__}')
        klines_raw = data_node.get(f'{prefix}{local_code}', {}).get('qfqday', [])
        if not klines_raw or len(klines_raw) < 5:
            return (False, f'数据不足: {len(klines_raw)}条')

        # 转格式
        klines = []
        for k in klines_raw:
            klines.append({
                'date': k[0].replace('-', ''),
                'open': float(k[1]), 'close': float(k[2]),
                'high': float(k[3]), 'low': float(k[4]),
                'volume': int(float(k[5])),
                'name': next((v['name'] for v in [imap.get(local_code, {})] if isinstance(v, dict) and v.get('name')), local_code),
            })

        return (True, f'已拉取{len(klines)}天数据')
    except Exception as e:
        return (False, f'拉取失败: {e}')


# ====== 财务数据 ======

def get_financial_cache():
    return _load_json(FINANCIAL_CACHE_PATH, {})


def save_financial_cache(data):
    _save_json(FINANCIAL_CACHE_PATH, data)


def get_profit_quality_results():
    return _load_json(PROFIT_QUALITY_PATH, {})


def save_profit_quality_results(data):
    _save_json(PROFIT_QUALITY_PATH, data)


# ====== 持仓与交易 ======

def get_holdings(user_id=1):
    """从DB读取持仓列表

    Args:
        user_id: 用户ID，默认1（default用户）

    Returns:
        [{code, name, direction, target_ratio, cost_price, stop_loss_price, sector}, ...]
    """
    try:
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        if db:
            rows = db.execute_raw(
                "SELECT code, name, direction, target_ratio, cost_price, stop_loss_price, sector "
                "FROM holdings WHERE user_id=%s AND is_active=1 ORDER BY code",
                [user_id]
            )
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
    except Exception as e:
        log.warning('get_holdings DB查询失败(%s)，回退JSON', e)
    # 回退：旧 JSON 路径
    return _load_json(HOLDINGS_PATH, [])


def save_holdings(user_id, holdings_list):
    """保存持仓列表到DB（先删后插）

    Args:
        user_id: 用户ID
        holdings_list: [{code, name, direction, target_ratio, cost_price, stop_loss_price, sector}, ...]
    """
    try:
        from backend.data_access.data_source import _get_tushare_db
        db = _get_tushare_db()
        if not db:
            raise RuntimeError('DB unavailable')
        conn = db._get_conn()
        try:
            with conn.cursor() as cur:
                # 删除旧持仓
                cur.execute("DELETE FROM holdings WHERE user_id=%s", [user_id])
                # 插入新持仓
                for h in holdings_list:
                    cur.execute(
                        "INSERT INTO holdings(user_id, code, name, direction, target_ratio, cost_price, stop_loss_price, sector) "
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
        log.warning('save_holdings DB写入失败(%s)，回退JSON', e)
        _save_json(HOLDINGS_PATH, holdings_list)
        return False


def get_trades():
    return _load_json(TRADES_PATH, [])


def save_trades(data):
    _save_json(TRADES_PATH, data)


# ====== 扫描结果 ======

def get_latest_scan():
    return _load_json(LATEST_SCAN_PATH, {})


def save_latest_scan(data):
    _save_json(LATEST_SCAN_PATH, data)


# ====== 复盘存档 ======

def get_review_archive(date_str=None):
    """date_str: YYYY-MM-DD 或 None（读取最新）"""
    if date_str:
        return _load_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), {})
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return {}
    files = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
    if not files:
        return {}
    return _load_json(os.path.join(REVIEW_ARCHIVE_DIR, files[-1]), {})


def save_review_archive(date_str, data):
    _save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), data)


def get_review_latest_date():
    """返回存档中最新复盘日期 YYYY-MM-DD"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return ''
    files = sorted([f for f in os.listdir(REVIEW_ARCHIVE_DIR) if f.endswith('.json')])
    return files[-1].replace('.json', '') if files else ''


# ====== 缓存工具 ======

def get_cache_path(name, date_str=None):
    """返回缓存文件路径"""
    if date_str:
        date_str = date_str.replace('-', '')
        return os.path.join(CACHE_DIR, f'{name}_{date_str}.json')
    return CACHE_DIR


def save_cache(name, data, date_str=None):
    path = get_cache_path(name, date_str)
    _save_json(path, data)


def load_cache(name, date_str=None):
    return _load_json(get_cache_path(name, date_str), {})


# ====== 关键点目录 ======

def get_key_points_dir():
    return KEY_POINTS_DIR


# ====== 辅助计算 ======

def calc_sector_leaders(stock_codes, kline_index, top_n=5):
    """计算板块领涨股（按5日涨跌幅排名）"""
    candidates = []
    for _c in stock_codes:
        _kls = kline_index.get(_c)
        if not _kls or len(_kls) < 5:
            continue
        _close_now = _kls[-1]['close']
        _close_1d = _kls[-2]['close'] if len(_kls) >= 2 else _close_now
        _close_5d = _kls[-5]['close'] if len(_kls) >= 5 else _close_now
        _chg_1d = round((_close_now - _close_1d) / _close_1d * 100, 1)
        _chg_5d = round((_close_now - _close_5d) / _close_5d * 100, 1)
        _name = _kls[0].get('name', _c) if isinstance(_kls[0], dict) else _c
        _tag = '🏆领涨' if _chg_5d >= 5 else ('💪中军' if _chg_1d > 0 else '')
        candidates.append({
            'code': _c,
            'name': _name or _c,
            'chg_1d': _chg_1d,
            'chg_5d': _chg_5d,
            'tag': _tag,
        })
    candidates.sort(key=lambda x: -x['chg_5d'])
    return candidates[:top_n]


def build_kline_index(all_stocks_data=None):
    """从 all_stocks 数据构建 {code: [kline,...]} 索引"""
    if all_stocks_data is None:
        all_stocks_data = get_all_stocks()
    index = {}
    for _dir, _ss in all_stocks_data.items():
        if isinstance(_ss, dict):
            for _code, _kls in _ss.items():
                index[_code] = _kls
    return index


def build_industry_stock_map(industry_map_data=None):
    """从行业映射构建 {行业名: [code,...]} 索引"""
    if industry_map_data is None:
        industry_map_data = get_industry_map()
    mapping = {}
    for _code, _info in industry_map_data.items():
        _ind = _info.get('ths_industry', '') if isinstance(_info, dict) else ''
        if _ind:
            mapping.setdefault(_ind, []).append(_code)
    return mapping


# 别名，保持向后兼容
load_all_stocks_uncached = _threel_get_all_stocks
load_index_data_uncached = get_index_data


# ====== 快速验证 ======
if __name__ == '__main__':
    stocks = get_all_stocks()
    print(f'方向数: {len(stocks)}')
    codes = set()
    for sec, ss in stocks.items():
        if isinstance(ss, dict):
            codes.update(ss.keys())
    print(f'股票数: {len(codes)}')
    print(f'最新日期: {get_last_updated()}')
    wl = get_watchlist()
    print(f'自选股: {len(wl)} 只')
    h = get_holdings()
    print(f'持仓: {len(h)} 只')
