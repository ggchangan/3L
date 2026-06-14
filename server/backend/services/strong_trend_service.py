"""强势趋势追踪 — 从强势板块筛选趋势完好的个股"""
import os, json
from typing import List, Tuple, Optional

from backend.core.config import DATA_DIR

# ── 数据加载 ──

def load_sector_daily() -> dict:
    """读取板块K线数据（通过 data_layer 统一接口）"""
    try:
        from backend.core.data_layer import get_sector_daily
        return get_sector_daily()
    except Exception:
        import json
        path = os.path.join(DATA_DIR, 'sector_daily.json')
        if os.path.isfile(path):
            with open(path) as f:
                return json.load(f)
        return {'industries': {}, 'concepts': {}}


def load_all_stocks() -> dict:
    """读取个股K线数据（展平为 {code: klines}）"""
    path = os.path.join(DATA_DIR, 'all_stocks_60d.json')
    if not os.path.isfile(path):
        return {}
    with open(path) as f:
        data = json.load(f)

    # 格式1: {stocks: {code: klines}} 或 {all: {code: klines}}
    if 'stocks' in data and isinstance(data['stocks'], dict):
        stocks = data['stocks']
    elif 'all' in data and isinstance(data['all'], dict):
        stocks = data['all']
    else:
        stocks = data

    # 格式2: 按方向分组 {方向名: {code: klines}}
    flat = {}
    for key, val in stocks.items():
        if isinstance(val, dict):
            # 检查是否是 {code: klines} 格式
            sample = next(iter(val.values()), None)
            if sample and isinstance(sample, list) and len(sample) > 0 and isinstance(sample[0], dict) and 'close' in sample[0]:
                # 是 {code: klines} 格式
                flat.update(val)
    if flat:
        return flat
    return stocks


def get_stock_industry(code: str) -> str:
    """查个股所属行业"""
    path = os.path.join(DATA_DIR, 'stock_industry_map.json')
    if not os.path.isfile(path):
        return ''
    with open(path) as f:
        imap = json.load(f)
    info = imap.get(code, {})
    return info.get('ths_industry', '') if isinstance(info, dict) else ''


def get_stock_concepts(code: str) -> list:
    """查个股所属概念列表"""
    path = os.path.join(DATA_DIR, 'map', 'stock_concept.json')
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        cmap = json.load(f)
    info = cmap.get(code, {})
    if isinstance(info, dict):
        return info.get('concept_names', [])
    return []


# ── 板块强度排名 ──

def get_top_sectors(sectors: dict, window_days: int = 20, top_n: int = 8) -> List[Tuple[str, float]]:
    """返回涨幅TOP N的板块列表 (name, chg_pct)"""
    results = []
    for name, klines in sectors.items():
        if not klines or len(klines) < window_days + 1:
            continue
        recent_close = klines[-1]['close']
        past_idx = max(0, len(klines) - window_days - 1)
        past_close = klines[past_idx]['close']
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

    prices = [k['close'] for k in klines]
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
    recent_high = max(k['high'] for k in recent)
    recent_low = min(k['low'] for k in recent)
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
    all_stocks = load_all_stocks()

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

    # 3. 遍历自选股（all_stocks_60d 中的），检查是否属于强势板块
    code_set = set()
    code_to_sectors = {}  # {code: [{type, name, chg_20d, chg_5d}]}

    # 预加载行业/概念涨幅查找表
    ind_chg20_map = dict(get_top_sectors(industries, 20, 100))
    ind_chg5_map = dict(get_top_sectors(industries, 5, 100))
    con_chg20_map = dict(get_top_sectors(concepts, 20, 100))
    con_chg5_map = dict(get_top_sectors(concepts, 5, 100))

    for code in all_stocks:
        score_this = False
        # 查行业
        ind = get_stock_industry(code)
        if ind and ind in strong_industries:
            code_to_sectors.setdefault(code, []).append({
                'type': 'industry', 'name': ind,
                'chg_20d': ind_chg20_map.get(ind, 0),
                'chg_5d': ind_chg5_map.get(ind, 0),
            })
            score_this = True
        # 查概念
        for con in get_stock_concepts(code):
            if con in strong_concepts:
                code_to_sectors.setdefault(code, []).append({
                    'type': 'concept', 'name': con,
                    'chg_20d': con_chg20_map.get(con, 0),
                    'chg_5d': con_chg5_map.get(con, 0),
                })
                score_this = True
        if score_this:
            code_set.add(code)

    # 4. 对每只候选股评分
    from backend.services.stock_card_service import get_stock_card
    today_str = datetime.date.today().strftime('%Y%m%d')
    candidates = []
    for code in code_set:
        klines = all_stocks[code]
        st = score_stock(klines)
        if st['score'] < min_score:
            continue

        # 取板块信息（综合评分用板块强度加成）
        best_sector = max(code_to_sectors[code], key=lambda s: max(abs(s['chg_20d']), abs(s['chg_5d'])))
        # 板块强度加分
        max_sector_chg = max(abs(s['chg_20d']) for s in code_to_sectors[code])
        sector_bonus = min(2.0, max_sector_chg / 10.0)
        total_score = round(min(10.0, st['score'] + sector_bonus), 1)

        # 取股票名
        aas_path = os.path.join(DATA_DIR, 'all_a_stocks.json')
        name = code
        if os.path.isfile(aas_path):
            with open(aas_path) as f:
                aas = json.load(f)
            name = aas.get(code, code)

        # 取信号数据（用已有的 K 线避免重复读文件）
        card = get_stock_card(code, today_str, klines=klines)

        candidates.append({
            'code': code,
            'name': name,
            'price': klines[-1]['close'],
            'chg_1d': round((klines[-1]['close'] - klines[-2]['close']) / klines[-2]['close'] * 100, 2) if len(klines) >= 2 else 0,
            'chg_5d': round((klines[-1]['close'] - klines[-6]['close']) / klines[-6]['close'] * 100, 2) if len(klines) >= 6 else 0,
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

    # 5. 排序
    candidates.sort(key=lambda x: -x['score'])

    return {
        'date': datetime.date.today().strftime('%Y%m%d'),
        'top_industries': top_industries_list,
        'hot_industries': hot_industries_list,
        'top_concepts': top_concepts_list,
        'hot_concepts': hot_concepts_list,
        'candidates': candidates[:limit],
    }
