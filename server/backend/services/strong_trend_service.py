"""强势趋势追踪 — 从强势板块筛选趋势完好的个股"""
import os, json
from typing import List, Tuple, Optional

from backend.core.config import DATA_DIR, INDUSTRY_MAP_PATH

# ── 数据加载（DB / JSON 统一入口）──

def load_sector_daily() -> dict:
    """读取板块K线数据（通过 data_layer 统一接口）"""
    from backend.data_access.data_layer import get_sector_daily
    return get_sector_daily()


def load_all_stocks() -> dict:
    """从行业映射+DB加载个股K线，返回 {code: [升序K线]}

    只加载行业映射中存在的股票（全市场数据），K线从DB批量拉取。
    """
    imap = _load_industry_map()
    if not imap:
        return {}
    codes = []
    for code, info in imap.items():
        if isinstance(info, dict) and info.get('ths_industry'):
            codes.append(code)
    if not codes:
        return {}
    # 批量从DB拉K线
    from threel_core.db import query_stock_klines
    lookup = [_ensure_suffix(c) for c in codes]
    ts_map = {_ensure_suffix(c): c for c in codes}
    raw = query_stock_klines(lookup, limit=90)
    result = {}
    for ts, kls in raw.items():
        code = ts_map.get(ts, ts)
        if kls:
            result[code] = sorted(kls, key=lambda x: x['date'])
    return result


def _load_industry_map() -> dict:
    """加载行业映射（兼容 JSON 和 config 路径）"""
    path = INDUSTRY_MAP_PATH
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # fallback
    fallback = os.path.join(DATA_DIR, 'stock_industry_map.json')
    if os.path.isfile(fallback):
        try:
            with open(fallback, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _ensure_suffix(code):
    if '.' in code:
        return code
    if code.startswith('6'):
        return f'{code}.SH'
    return f'{code}.SZ'


def get_stock_industry(code: str) -> str:
    """查个股所属行业（从 INDUSTRY_MAP_PATH）"""
    imap = _load_industry_map()
    info = imap.get(code, {})
    return info.get('ths_industry', '') if isinstance(info, dict) else ''


def get_stock_concepts(code: str) -> list:
    """查个股所属概念列表"""
    cmap = _load_concept_map()
    info = cmap.get(code, {})
    if isinstance(info, dict):
        return info.get('concept_names', [])
    return []


def _load_concept_map() -> dict:
    """预加载概念映射（内存缓存，避免每次打开文件）"""
    _cache = getattr(_load_concept_map, '_cache', None)
    if _cache is not None:
        return _cache
    path = os.path.join(DATA_DIR, 'map', 'stock_concept.json')
    _cache = {}
    if os.path.isfile(path):
        try:
            with open(path) as f:
                _cache = json.load(f)
        except Exception:
            pass
    _load_concept_map._cache = _cache
    return _cache


# ── 板块强度排名 ──

def get_top_sectors(sectors: dict, window_days: int = 20, top_n: int = 8) -> List[Tuple[str, float]]:
    """返回涨幅TOP N的板块列表 (name, chg_pct)

    sectors: {name: [升序K线]} 预期 K 线升序排列（旧→新）
    """
    results = []
    for name, klines in sectors.items():
        if not klines or len(klines) < window_days + 1:
            continue
        # klines 为升序，klines[-1] = 最新
        recent_close = float(klines[-1]['close'])
        # 取 window_days 天前的收盘价
        past_idx = max(0, len(klines) - window_days - 1)
        past_close = float(klines[past_idx]['close'])
        if past_close <= 0:
            continue
        chg = round((recent_close - past_close) / past_close * 100, 2)
        results.append((name, chg))

    results.sort(key=lambda x: -x[1])
    return results[:top_n]


# ── EMA 计算 ──

def calc_ema(klines_close: list, period: int) -> list:
    """计算EMA"""
    ema = []
    multiplier = 2.0 / (period + 1)
    for i, price in enumerate(klines_close):
        if i == 0:
            ema.append(price)
        else:
            ema.append((price - ema[-1]) * multiplier + ema[-1])
    return ema


# ── 个股趋势评分 ──

def score_stock(klines: list) -> dict:
    """对个股K线计算趋势质量评分"""
    if not klines or len(klines) < 20:
        return {
            'score': 0, 'ema_alignment': 'insufficient_data',
            'ema5_slope': 0, 'max_drawdown_10d': 0,
            'max_consecutive_down_10d': 0, 'price_vs_ema20_pct': 0,
        }

    prices = [float(k['close']) for k in klines]
    ema5 = calc_ema(prices, 5)
    ema10 = calc_ema(prices, 10)
    ema20 = calc_ema(prices, 20)

    idx = -1  # 最新日

    # 1. EMA多头排列
    bullish = ema5[idx] > ema10[idx] > ema20[idx]

    # 2. EMA5斜率（近3日EMA5变化 / 最新价%）
    ema5_slope = 0
    ema10_slope = 0
    if len(klines) >= 4:
        ema5_slope = (ema5[-1] - ema5[-4]) / klines[-1]['close'] * 100
        ema10_slope = (ema10[-1] - ema10[-4]) / klines[-1]['close'] * 100

    # 3. 近10日调整深度
    recent = klines[-10:]
    recent_high = max(float(k['high']) for k in recent)
    recent_low = min(float(k['low']) for k in recent)
    max_drawdown = round((recent_low - recent_high) / recent_high * 100, 2) if recent_high > 0 else 0

    # 4. 近10日连跌天数
    consec_down = 0
    max_consec = 0
    for k in recent:
        if k['close'] < k['open']:
            consec_down += 1
            max_consec = max(max_consec, consec_down)
        else:
            consec_down = 0

    # 5. 价格相对EMA20位置
    price_vs_ema20 = round((klines[idx]['close'] - ema20[idx]) / ema20[idx] * 100, 2) if ema20[idx] > 0 else 0

    # ── 评分 ──
    score = 0.0

    # 趋势对齐 (0~3分)
    if bullish:
        score += 3.0
    elif ema5[idx] > ema20[idx]:
        score += 1.5

    # EMA5斜率 (0~3分)
    score += min(3.0, max(0, ema5_slope * 2))

    # 调整质量 (0~3分)
    drawdown_score = 3.0 if max_drawdown >= -2.0 else (2.0 if max_drawdown >= -4.0 else 0.5 if max_drawdown >= -8.0 else 0)
    score += drawdown_score

    # 连跌 (0~1分)
    if max_consec <= 1:
        score += 1.0
    elif max_consec <= 2:
        score += 0.5

    score = round(min(10.0, max(0, score)), 1)

    return {
        'score': score,
        'ema_alignment': 'bullish' if bullish else ('partial' if ema5[idx] > ema20[idx] else 'bearish'),
        'ema5_slope': round(ema5_slope, 2),
        'ema10_slope': round(ema10_slope, 2),
        'ema5': round(ema5[idx], 2),
        'ema10': round(ema10[idx], 2),
        'ema20': round(ema20[idx], 2),
        'max_drawdown_10d': max_drawdown,
        'max_consecutive_down_10d': max_consec,
        'price_vs_ema20_pct': price_vs_ema20,
    }


# ── 主流程 ──

def get_strong_trend_candidates(
    top_industries: int = 8,
    hot_industries: int = 8,
    top_concepts: int = 8,
    hot_concepts: int = 8,
    limit: int = 30,
    min_score: float = 5.0,
) -> dict:
    """获取强势趋势候选股"""
    import datetime

    sector_data = load_sector_daily()
    industries = sector_data.get('industries', {})
    concepts = sector_data.get('concepts', {})

    # 1. 双窗口筛选强势板块
    strong_industries = set()
    for name, _ in get_top_sectors(industries, 20, top_industries):
        strong_industries.add(name)
    for name, _ in get_top_sectors(industries, 5, hot_industries):
        strong_industries.add(name)

    strong_concepts = set()
    for name, _ in get_top_sectors(concepts, 20, top_concepts):
        strong_concepts.add(name)
    for name, _ in get_top_sectors(concepts, 5, hot_concepts):
        strong_concepts.add(name)

    # 2. 构建板块TOP列表
    all_ind_pairs = get_top_sectors(industries, 20, top_industries + hot_industries)
    all_con_pairs = get_top_sectors(concepts, 20, top_concepts + hot_concepts)

    top_industries_list = [{'name': n, 'chg_20d': c} for n, c in all_ind_pairs[:top_industries]]
    hot_industries_list = [{'name': n, 'chg_5d': c} for n, c in get_top_sectors(industries, 5, hot_industries)]
    top_concepts_list = [{'name': n, 'chg_20d': c} for n, c in all_con_pairs[:top_concepts]]
    hot_concepts_list = [{'name': n, 'chg_5d': c} for n, c in get_top_sectors(concepts, 5, hot_concepts)]

    # 预加载行业/概念涨幅查找表
    ind_chg20_map = dict(get_top_sectors(industries, 20, 100))
    ind_chg5_map = dict(get_top_sectors(industries, 5, 100))
    con_chg20_map = dict(get_top_sectors(concepts, 20, 100))
    con_chg5_map = dict(get_top_sectors(concepts, 5, 100))

    # 3. 从行业映射中查找候选股代码（不拉K线，纯JSON）
    imap = _load_industry_map()
    candiate_codes = []
    code_to_sectors = {}
    for code, info in imap.items():
        if not isinstance(info, dict):
            continue
        ind = info.get('ths_industry', '')
        matched = False
        if ind and ind in strong_industries:
            code_to_sectors.setdefault(code, []).append({
                'type': 'industry', 'name': ind,
                'chg_20d': ind_chg20_map.get(ind, 0),
                'chg_5d': ind_chg5_map.get(ind, 0),
            })
            matched = True
        # 查概念
        for con in get_stock_concepts(code):
            if con in strong_concepts:
                code_to_sectors.setdefault(code, []).append({
                    'type': 'concept', 'name': con,
                    'chg_20d': con_chg20_map.get(con, 0),
                    'chg_5d': con_chg5_map.get(con, 0),
                })
                matched = True
        if matched:
            candiate_codes.append(code)

    if not candiate_codes:
        return {
            'date': datetime.date.today().strftime('%Y%m%d'),
            'top_industries': top_industries_list,
            'hot_industries': hot_industries_list,
            'top_concepts': top_concepts_list,
            'hot_concepts': hot_concepts_list,
            'candidates': [],
        }

    # 4. 批量拉取候选股的K线（只拉候选，不拉全市场）
    from threel_core.db import query_stock_klines
    lookup = [_ensure_suffix(c) for c in candiate_codes]
    ts_map = {_ensure_suffix(c): c for c in candiate_codes}
    raw = query_stock_klines(lookup, limit=90)
    all_stocks = {}
    for ts, kls in raw.items():
        code = ts_map.get(ts, ts)
        if kls:
            all_stocks[code] = sorted(kls, key=lambda x: x['date'])

    # 5. 对每只候选股评分
    from backend.services.stock_card_service import get_stock_card
    today_str = datetime.date.today().strftime('%Y%m%d')
    candidates = []
    # 预加载股票名称
    name_map = {}
    aas_path = os.path.join(DATA_DIR, 'all_a_stocks.json')
    if os.path.isfile(aas_path):
        try:
            with open(aas_path) as f:
                name_map = json.load(f)
        except Exception:
            pass

    for code in candiate_codes:
        klines = all_stocks.get(code, [])
        if not klines or len(klines) < 20:
            continue
        st = score_stock(klines)
        if st['score'] < min_score:
            continue

        best_sector = max(code_to_sectors[code], key=lambda s: max(abs(s['chg_20d']), abs(s['chg_5d'])))
        max_sector_chg = max(abs(s['chg_20d']) for s in code_to_sectors[code])
        sector_bonus = min(2.0, max_sector_chg / 10.0)
        total_score = round(min(10.0, st['score'] + sector_bonus), 1)

        name = name_map.get(code, code)

        card = get_stock_card(code, today_str, klines=klines)

        candidates.append({
            'code': code,
            'name': name,
            'price': float(klines[-1]['close']),
            'chg_1d': round((float(klines[-1]['close']) - float(klines[-2]['close'])) / float(klines[-2]['close']) * 100, 2) if len(klines) >= 2 else 0,
            'chg_5d': round((float(klines[-1]['close']) - float(klines[-6]['close'])) / float(klines[-6]['close']) * 100, 2) if len(klines) >= 6 else 0,
            'sectors': code_to_sectors[code],
            'trend_metrics': {k: st[k] for k in ['ema_alignment', 'ema5_slope', 'ema10_slope', 'ema5', 'ema10', 'ema20', 'price_vs_ema20_pct']},
            'adjustment_quality': {k: st[k] for k in ['max_drawdown_10d', 'max_consecutive_down_10d']},
            'score': total_score,
            'score_breakdown': {
                'sector_strength': round(sector_bonus, 1),
                'trend': round(st['score'], 1),
            },
            'signal': card.get('signal', 'hold'),
            'signal_text': card.get('signal_text', ''),
            'buy_point': card.get('buy_point', ''),
            'stop_loss': card.get('stop_loss'),
            'stop_loss_pct': card.get('stop_loss_pct'),
            'trading_system': card.get('trading_system', '3l'),
            'triggered_signals': card.get('triggered_signals', []),
            'fusion_type': card.get('fusion_type', ''),
            'mainline_level': card.get('mainline_level', ''),
            'conclusion': card.get('conclusion', ''),
        })

    # 6. 排序
    candidates.sort(key=lambda x: -x['score'])

    return {
        'date': datetime.date.today().strftime('%Y%m%d'),
        'top_industries': top_industries_list,
        'hot_industries': hot_industries_list,
        'top_concepts': top_concepts_list,
        'hot_concepts': hot_concepts_list,
        'candidates': candidates[:limit],
    }
