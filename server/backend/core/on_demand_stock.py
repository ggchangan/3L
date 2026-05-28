"""
按需个股数据拉取 — 为个股分析页面提供未缓存股票的K线数据。

缓存策略：独立文件 stock_on_demand_cache.json，TTL=1天，最多保留30只。
cron 17:00 不碰此文件，不污染 all_stocks_60d.json。
"""
import json
import os
import warnings
from datetime import datetime, timedelta

from backend.config import ON_DEMAND_CACHE_PATH, DATA_DIR

# 缓存限制
MAX_CACHED_STOCKS = 30
CACHE_TTL_HOURS = 24


def get_or_fetch_stock_data(code):
    """获取单只股票的K线数据（缓存命中→akshare按需拉取）

    Returns:
        (klines_list, direction_str, name_str) 或 (None, None, None)
    """
    # 1. 检查主数据文件是否已有（cron拉过的）
    from backend.core.data_layer import get_all_stocks
    stocks = get_all_stocks()
    for sec, ss in stocks.items():
        if code in ss:
            name = ss[code][0].get('name', code) if ss[code] else code
            return ss[code], sec, name

    # 2. 检查按需缓存
    cache = _load_cache()
    entry = _check_cache(cache, code)
    if entry is not None:
        return entry['klines'], entry['direction'], entry.get('name', code)

    # 3. akshare 拉取
    klines = _fetch_klines_akshare(code)
    if klines is None or len(klines) < 30:
        return None, None, None

    # 4. 查方向
    direction = _get_direction(code)

    # 5. 取名字
    name = _get_name(code) or code

    # 6. 写入缓存
    _save_to_cache(code, {
        'klines': klines,
        'direction': direction,
        'name': name,
    })

    return klines, direction, name


def _fetch_klines_akshare(code):
    """通过 akshare 拉取单只股票最近60天K线

    回退方案：akshare 失败时尝试 mootdx（通达信）
    返回格式与 mootdx 一致（不含 name 字段）:
    [{date, open, close, high, low, volume}, ...]
    """
    warnings.filterwarnings('ignore')

    # 方案1: akshare（东方财富）
    klines = _fetch_via_akshare(code)
    if klines is not None and len(klines) >= 30:
        return klines[-60:]

    # 方案2: mootdx（通达信，与 cron 同源）
    klines = _fetch_via_mootdx(code)
    if klines is not None and len(klines) >= 30:
        return klines[-60:]

    return None


def _fetch_via_akshare(code):
    """通过 akshare（东方财富）拉取单只股票K线"""
    try:
        import akshare as ak
        end = datetime.now()
        start = end - timedelta(days=90)
        df = ak.stock_zh_a_hist(
            symbol=code[-6:],
            period='daily',
            start_date=start.strftime('%Y%m%d'),
            end_date=end.strftime('%Y%m%d'),
            adjust='qfq',
            timeout=10,
        )
        if df is None or df.empty:
            return None
        klines = []
        for _, row in df.iterrows():
            date_val = row['日期']
            date_str = date_val.strftime('%Y%m%d') if hasattr(date_val, 'strftime') else str(date_val)
            klines.append({
                'date': date_str,
                'open': round(float(row['开盘']), 2),
                'close': round(float(row['收盘']), 2),
                'high': round(float(row['最高']), 2),
                'low': round(float(row['最低']), 2),
                'volume': int(float(row['成交量'])),
            })
        return klines
    except Exception:
        return None


def _fetch_via_mootdx(code):
    """通过 mootdx（通达信）拉取单只股票K线

    与 cron 17:00 使用相同的数据源，确保数据一致性。
    """
    try:
        from mootdx.quotes import Quotes
        from backend.core.update_stock_data import _ensure_mootdx_config

        _ensure_mootdx_config()
        client = Quotes.factory(market='std')
        # 先尝试取200条，再截取最近60天
        bars = client.bars(symbol=code[-6:], frequency=9, start=0, count=200, fq=True)
        if bars is None or len(bars) == 0:
            return None
        records = []
        for _, row in bars.iterrows():
            records.append({
                'date': row['datetime'][:10].replace('-', ''),
                'open': round(float(row['open']), 2),
                'close': round(float(row['close']), 2),
                'high': round(float(row['high']), 2),
                'low': round(float(row['low']), 2),
                'volume': int(float(row['volume'])) * 100,  # mootdx 单位是手 → 股
            })
        return records
    except Exception:
        return None


def _get_direction(code):
    """从行业映射查股票的方向（方向名）

    优先匹配 watchlist 中的方向名称。
    """
    from backend.core.data_layer import get_industry_map
    imap = get_industry_map()
    info = imap.get(code, {})
    if not isinstance(info, dict):
        return '其他'

    industry = info.get('ths_industry', '') or info.get('industry', '')
    if not industry:
        return '其他'

    # 从现有方向名中找匹配
    _KNOWN_DIRECTIONS = [
        '算力', '半导体', '机器人', '新能源', '军工信息',
        '人工智能', '医药', '消费电子', '其他',
    ]
    # 简单的行业→方向关键词匹配
    industry_lower = industry.lower()
    if any(kw in industry_lower for kw in ['算力', '光模块', '服务器', '芯片']):
        return '算力'
    if any(kw in industry_lower for kw in ['半导体', '集成电路', '封测', '晶圆']):
        return '半导体'
    if any(kw in industry_lower for kw in ['机器人', '自动化', '机器视觉']):
        return '机器人'
    if any(kw in industry_lower for kw in ['新能源', '锂电池', '光伏', '风电', '储能']):
        return '新能源'
    if any(kw in industry_lower for kw in ['军工', '航空', '航天', '船舶']):
        return '军工信息'
    if any(kw in industry_lower for kw in ['人工智能', 'ai', '大模型', '数据']):
        return '人工智能'
    if any(kw in industry_lower for kw in ['医药', '医疗', '生物', '制药']):
        return '医药'
    if any(kw in industry_lower for kw in ['消费电子', '手机', '智能穿戴']):
        return '消费电子'
    return '其他'


def _get_name(code):
    """从 all_a_stocks.json 取股票名称"""
    aas_path = os.path.join(DATA_DIR, 'all_a_stocks.json')
    if not os.path.exists(aas_path):
        return None
    try:
        with open(aas_path) as f:
            name_map = json.load(f)
            return name_map.get(code)
    except Exception:
        return None


# ====== 缓存管理 ======


def _load_cache():
    """加载按需缓存文件"""
    if not os.path.exists(ON_DEMAND_CACHE_PATH):
        return {}
    try:
        with open(ON_DEMAND_CACHE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_cache(cache):
    """保存按需缓存文件（自动裁剪超过MAX）"""
    stocks = cache.get('stocks', {})
    if len(stocks) > MAX_CACHED_STOCKS:
        # 按 cached_at 排序，保留最新的
        sorted_codes = sorted(
            stocks.keys(),
            key=lambda c: stocks[c].get('cached_at', ''),
            reverse=True,
        )
        pruned = {c: stocks[c] for c in sorted_codes[:MAX_CACHED_STOCKS]}
        cache['stocks'] = pruned

    tmp = ON_DEMAND_CACHE_PATH + '.tmp'
    try:
        with open(tmp, 'w') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        os.replace(tmp, ON_DEMAND_CACHE_PATH)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)


def _check_cache(cache, code):
    """检查缓存是否有效（未过期+命中）

    Returns:
        cache entry dict or None
    """
    cached_at = cache.get('cached_at', '')
    if not cached_at:
        return None

    # 解析缓存时间
    try:
        cache_dt = datetime.strptime(cached_at, '%Y%m%d%H%M%S')
    except ValueError:
        try:
            cache_dt = datetime.strptime(cached_at, '%Y%m%d')
        except ValueError:
            return None

    # TTL 检查
    if datetime.now() - cache_dt > timedelta(hours=CACHE_TTL_HOURS):
        return None

    entry = cache.get('stocks', {}).get(code)
    if entry is None:
        return None
    return entry


def _save_to_cache(code, entry):
    """将一只股票的数据写入按需缓存"""
    cache = _load_cache()
    now_str = datetime.now().strftime('%Y%m%d%H%M%S')
    if 'stocks' not in cache:
        cache['stocks'] = {}
    cache['cached_at'] = now_str
    entry['cached_at'] = now_str
    cache['stocks'][code] = entry
    _save_cache(cache)
