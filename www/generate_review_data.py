#!/usr/bin/env python3
"""
3L 每日复盘数据生成器（完整版）
生成5大项复盘数据：
  ① 大盘周期 — 波峰波谷判定（4维度评分）
  ② 动量主线 — 评分/持续性/轮动
  ③ 最强逻辑 — 个股归主线+板块内排名+选股说明
  ④ 量价择时 — 买点验证/关键点/止损止盈
  ⑤ 每日交易计划 — 基于前4项生成

输出：JSON → REVIEW_ARCHIVE_DIR/{date}.json
"""
import json, os, sys, requests, math
from scripts.data_layer import (
    ALL_STOCKS_PATH, INDUSTRY_MAP_PATH, LATEST_SCAN_PATH, REVIEW_ARCHIVE_DIR,
    WWW_DIR, DATA_DIR, get_all_stocks, get_latest_scan, save_review_archive,
    get_review_archive, load_cache, save_cache, get_cache_path, get_watchlist
)
os.environ['TQDM_DISABLE'] = '1'  # 关akshare进度条
from datetime import datetime, timedelta

# ====== 路径（从 scripts.data_layer 导入） ======
# WWW_DIR, DATA_DIR, REVIEW_ARCHIVE_DIR 已从 data_layer 导入
SCRIPTS_DIR = '/home/ubuntu/scripts'

# ====== 辅助函数 ======

def load_cached_data(path):
    """加载缓存JSON"""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_market_quote():
    """获取中证全指(000985)实时行情"""
    try:
        r = requests.get(
            'https://qt.gtimg.cn/q=sh000985',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
            timeout=10
        )
        txt = r.text
        parts = txt.split('~')
        if len(parts) > 5:
            name = parts[1]
            cur_price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else cur_price
            chg_pct = (cur_price - prev_close) / prev_close * 100 if prev_close else 0
            return {
                'price': cur_price,
                'change': round(chg_pct, 2),
                'name': name
            }
    except Exception as e:
        print(f"[WARN] 获取中证全指行情失败: {e}")
    return None

def to_yyyymmdd(d):
    """统一日期格式为 YYYY-MM-DD"""
    if not d:
        return ''
    d = d.strip().replace('/', '-')
    # 已是 YYYY-MM-DD
    if len(d) == 10 and d[4] == '-':
        return d
    return d

def fetch_index_klines(days=60):
    """获取中证全指K线（腾讯财经）"""
    try:
        r = requests.get(
            f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,{days},qfq',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
            timeout=10
        )
        data = r.json()
        klines = data.get('data', {}).get('sh000985', {}).get('qfqday', []) or \
                 data.get('data', {}).get('sh000985', {}).get('day', []) or []
        return [{'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                 'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5])}
                for k in klines if len(k) >= 6]
    except Exception as e:
        print(f"[WARN] 获取K线失败: {e}")
        return []

# ====== ① 大盘周期判定（V5：基于供需本质的置信度打分） ======

def judge_peak_valley(klines):
    """
    三维度大盘波峰波谷判定
    基于乖离率趋势转折 + 乖离率位置 + 量价信号
    返回 5档：偏波峰/波中偏上/波中/波中偏下/偏波谷
    """
    if len(klines) < 70:
        return _fallback_cycle(klines)

    # 构建DataFrame
    import pandas as pd
    import numpy as np

    df = pd.DataFrame(klines)
    for ma in [5, 10, 20, 60]:
        df[f'MA{ma}'] = df['close'].rolling(ma).mean()
        df[f'bias_{ma}'] = (df['close'] - df[f'MA{ma}']) / df[f'MA{ma}'] * 100
    df['bias20_chg_3d'] = df['bias_20'].diff(3)
    df['bias20_chg_5d'] = df['bias_20'].diff(5)
    df['vol_ma20'] = df['volume'].rolling(20).mean()

    i = len(df) - 1
    r = df.iloc[i]
    if pd.isna(r['bias_20']) or pd.isna(r['bias20_chg_5d']):
        return _fallback_cycle(klines)

    bias20 = r['bias_20']
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    bias_early = r['bias_20'] - df.iloc[i - 10]['bias_20'] if i >= 10 else 0

    # --- 量价信号 ---
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    ls_pct = (min(r['open'], r['close']) - r['low']) / r['open'] * 100
    us_pct = (r['high'] - max(r['open'], r['close'])) / r['open'] * 100
    gain = (r['close'] - r['open']) / r['open'] * 100

    last5 = df.iloc[max(0, i - 4):i + 1]

    # 波峰信号
    peak_sig = 0
    if vol_ratio > 1.3 and body_pct < 0.8:
        peak_sig += 1
    if us_pct > 1.5 and gain < 0:
        peak_sig += 1
    if len(last5) >= 5:
        gains = [(last5.iloc[j]['close'] - last5.iloc[j - 1]['close']) / last5.iloc[j - 1]['close'] * 100
                 for j in range(1, len(last5))]
        avg_g = np.mean([g for g in gains if not np.isnan(g)] or [0])
        tg = (r['close'] - last5.iloc[-2]['close']) / last5.iloc[-2]['close'] * 100
        if avg_g > 0.5 and tg < avg_g * 0.3:
            peak_sig += 1
        yang = sum(1 for j in range(1, len(last5)) if last5.iloc[j]['close'] > last5.iloc[j - 1]['close'])
        if yang >= 3 and vol_ratio > 1.5 and body_pct < 0.6:
            peak_sig += 1

    # 波谷信号
    valley_sig = 0
    if gain < -1.5 and vol_ratio > 1.3 and ls_pct > body_pct * 1.5 and ls_pct > 0.5:
        valley_sig += 1
    if ls_pct > 1.0 and body_pct < ls_pct:
        valley_sig += 1
    if len(last5) >= 4:
        down = sum(1 for j in range(1, len(last5)) if last5.iloc[j]['close'] < last5.iloc[j - 1]['close'])
        if down >= 4 and vol_ratio < 0.8:
            valley_sig += 1
        p4 = all(last5.iloc[j]['close'] < last5.iloc[j - 1]['close'] for j in range(1, 4))
        if p4 and body_pct < 0.8 and gain > 0:
            valley_sig += 1

    # --- 趋势转折 ---
    peak_turn = bias_early > 0.5 and bias_chg_5d < 0.3
    valley_turn = bias_early < -0.8 and bias_chg_5d > -0.3

    # --- pk_score / vl_score ---
    pk_score = 0
    if peak_turn: pk_score += 1
    if bias20 > 1.5: pk_score += 1
    if peak_sig >= 1: pk_score += 1
    if bias_chg_3d < 0: pk_score += 1
    if bias20 > 8: pk_score = max(pk_score, 3)

    vl_score = 0
    if valley_turn: vl_score += 1
    if bias20 < -1.5: vl_score += 1
    if valley_sig >= 1: vl_score += 1
    if bias_chg_3d > 0: vl_score += 1
    if bias20 < -8: vl_score = max(vl_score, 3)

    # --- 5档判定 + 仓位策略 ---
    if pk_score >= 4:
        position = '偏波峰'
        pct = '五成'
        strategy = '控制仓位，收紧止盈'
        bps = 5
    elif pk_score >= 3:
        position = '波中偏上'
        pct = '六至七成'
        strategy = '正常交易，注意减仓信号'
        bps = 5
    elif vl_score >= 4:
        position = '偏波谷'
        pct = '五至八成'
        strategy = '积极寻找买点，止损换股补回'
        bps = 10
    elif vl_score >= 3:
        position = '波中偏下'
        pct = '五至七成'
        strategy = '谨慎选股，收紧止损'
        bps = 5
    else:
        position = '波中'
        pct = '七至八成'
        strategy = '正常交易，积极选股'
        bps = 5

    score = pk_score - vl_score

    chg_10d = (klines[-1]['close'] - klines[-11]['close']) / klines[-11]['close'] * 100 if len(klines) >= 11 else 0
    ma20_val = float(df['MA20'].iloc[-1]) if not pd.isna(df['MA20'].iloc[-1]) else 0
    ma60_val = float(df['MA60'].iloc[-1]) if not pd.isna(df['MA60'].iloc[-1]) else 0

    return {
        'score': round(score, 1),
        'position': position,
        'pk_score': pk_score,
        'vl_score': vl_score,
        'bias20': round(bias20, 2),
        'bias20_chg_3d': round(bias_chg_3d, 2),
        'ma20': round(ma20_val, 2),
        'ma60': round(ma60_val, 2),
        'vol_ratio': round(vol_ratio, 2),
        'chg_10d': round(chg_10d, 2),
        'chg_10d_raw': round(chg_10d, 2),
        'strategy': strategy,
        'position_pct': pct,
        'build_per_stock_pct': bps,
        'peak_sig': peak_sig,
        'valley_sig': valley_sig,
        # 保留旧字段兼容review.html显示
        'ma_score': 0, 'vol_score': 0, 'trend_score': 0, 'amp_score': 0,
    }


def _fallback_cycle(klines):
    """数据不足时的兜底方案"""
    if len(klines) < 10:
        return {'score': 0, 'position': '波中', 'strategy': '正常交易',
                'position_pct': '七至八成', 'build_per_stock_pct': 5}
    chg = (klines[-1]['close'] - klines[-6]['close']) / klines[-6]['close'] * 100
    if chg > 5:
        return {'score': 0.5, 'position': '波中偏上', 'strategy': '正常交易，注意减仓信号',
                'position_pct': '六至七成', 'build_per_stock_pct': 5}
    elif chg < -5:
        return {'score': -0.5, 'position': '波中偏下', 'strategy': '谨慎选股，收紧止损',
                'position_pct': '五至七成', 'build_per_stock_pct': 5}
    else:
        return {'score': 0, 'position': '波中', 'strategy': '正常交易',
                'position_pct': '七至八成', 'build_per_stock_pct': 5}

# ====== ② 动量主线评判 ======

def get_industry_rankings():
    """获取同花顺行业板块排行（当日实时）—— 仅用于页面展示"""
    import akshare as ak
    try:
        df = ak.stock_board_industry_summary_ths()
        df = df.sort_values('涨跌幅', ascending=False)
        result = []
        for _, row in df.head(15).iterrows():
            result.append({
                'name': row['板块'],
                'change': row['涨跌幅'],
                'net_inflow': row['净流入'],
                'up_count': row['上涨家数'],
                'down_count': row['下跌家数'],
                'leader': row['领涨股'],
                'leader_change': row['领涨股-涨跌幅'],
            })
        return result
    except Exception as e:
        print(f"[WARN] 获取行业排行失败: {e}")
        return []

def _calc_board_20d(ind_name):
    """计算单板块20日涨幅"""
    import akshare as ak
    try:
        df = ak.stock_board_industry_index_ths(symbol=ind_name, start_date="20260415", end_date=datetime.now().strftime('%Y%m%d'))
        if len(df) < 15:
            return None
        recent = df.tail(20) if len(df) >= 20 else df.tail(len(df))
        if len(recent) < 10:
            return None
        chg_20d = (recent.iloc[-1]['收盘价'] / recent.iloc[0]['收盘价'] - 1) * 100
        return {
            'name': ind_name,
            'chg_20d': round(chg_20d, 2),
        }
    except:
        return None

def get_mainline_data(date_str):
    """三梯队：前5=主线，6~10=次级主线，其余=非主线"""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import akshare as ak
    
    try:
        name_df = ak.stock_board_industry_name_ths()
        industries = name_df['name'].tolist()
    except Exception as e:
        print(f"[WARN] 获取板块名称失败: {e}")
        return {'lines': [], 'secondary': [], 'industries': get_industry_rankings()}
    
    scores = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        fut_map = {pool.submit(_calc_board_20d, ind): ind for ind in industries}
        for fut in as_completed(fut_map):
            r = fut.result()
            if r:
                scores.append(r)
    
    scores.sort(key=lambda x: x['chg_20d'], reverse=True)
    daily_rankings = get_industry_rankings()
    
    main_lines = scores[:5]
    secondary_lines = scores[5:10]
    
    return {
        'lines': main_lines,           # 主线（前5）
        'secondary': secondary_lines,   # 次级主线（6~10）
        'industries': daily_rankings,   # 今日行业排行（展示用）
        'all_ranked': scores,           # 全排序（供参考）
    }

def track_mainline_persistence(date_str, current_lines):
    """主线持续性跟踪（占位）"""
    return [{'name': l['name'], 'days': 1, 'status': '持续'} for l in current_lines]

# ====== ③ 最强逻辑归类 ======

def classify_stocks_by_mainline(mainline_data, holdings, buy_signals):
    """将持仓/候选归入主线/次级主线/非主线（精确匹配同花顺行业）"""
    lines = [l['name'] for l in mainline_data.get('lines', [])]
    secondary = [l['name'] for l in mainline_data.get('secondary', [])]
    result = {'mainline': [], 'secondary': [], 'non_mainline': []}

    def get_tier(stock):
        sec = stock.get('sector', stock.get('direction', ''))
        if sec in lines:
            return 'mainline', sec
        if sec in secondary:
            return 'secondary', sec
        return 'non_mainline', sec

    for h in holdings:
        tier, sec = get_tier(h)
        entry = {'name': h.get('name', '?'), 'code': h.get('code', ''), 'sector': sec}
        result[tier].append(entry)

    for s in buy_signals:
        tier, sec = get_tier(s)
        entry = {'name': s.get('name', '?'), 'code': s.get('code', ''), 'sector': sec}
        if tier == 'mainline' or tier == 'secondary':
            result[tier].append(entry)

    return result

# ====== ④ 量价择时（全量扫描） ======

def get_buy_sell_signals(holdings, buy_signals):
    """量价择时分析 — 从全量扫描结果中提取持仓股买点"""
    signals = {'holdings': [], 'signals': buy_signals}
    bs_by_code = {s.get('code', ''): s for s in buy_signals}
    
    # 从缓存读取持仓股数据
    cache = {}
    try:
        sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/trading/ema10-trend-judgment/scripts')
        from ema_utils import get_ema_arrangement, get_structure, get_stage
        import json as _json
        with open(ALL_STOCKS_PATH) as f:
            _data = _json.load(f)
        _stocks = _data.get('stocks', {})
        for _sec, _ss in _stocks.items():
            for _code, _kls in _ss.items():
                if _kls and len(_kls) >= 2:
                    last = _kls[-1]
                    prev = _kls[-2]
                    chg = round((last['close'] - prev['close']) / prev['close'] * 100, 2) if prev['close'] else 0
                    closes_60 = [k['close'] for k in _kls]
                    highs_60 = [k['high'] for k in _kls]
                    lows_60 = [k['low'] for k in _kls]
                    vols_60 = [k.get('volume', k.get('vol', 0)) for k in _kls]
                    _structure = get_structure(closes_60)
                    _stage = get_stage(closes_60, _structure, highs_60, lows_60, volumes=vols_60)
                    _vol_analysis = '--'
                    if len(vols_60) >= 13 and all(v > 0 for v in vols_60[-13:]):
                        _vl3 = sum(vols_60[-3:]) / 3
                        _vp10 = sum(vols_60[-13:-3]) / 10
                        _vr = _vl3 / _vp10 if _vp10 > 0 else 1
                        if _vr < 0.8:
                            _vol_analysis = f'缩量{_vr:.0%}'
                        elif _vr > 1.5:
                            _vol_analysis = f'放量{_vr:.0%}'
                        else:
                            _vol_analysis = f'量能正常{_vr:.0%}'
                    cache[_code] = {
                        'close': last['close'], 'change': chg, 'date': last['date'],
                        'ema': get_ema_arrangement(closes_60),
                        'structure': _structure,
                        'stage': _stage,
                        'vol_analysis': _vol_analysis,
                    }
    except Exception:
        pass
    
    for h in holdings:
        code = h.get('code', '')
        name = h.get('name', '?')
        bs = bs_by_code.get(code)
        close_price = bs.get('price', 0) if bs else 0
        if not bs or close_price == 0:
            close_price = cache.get(code, {}).get('close', 0)
        chg_val = bs.get('change', 0) if bs else 0
        if not bs:
            chg_val = cache.get(code, {}).get('change', 0)
        action = f"{bs.get('buy_point', '')} {bs.get('flags', '')}" if bs else '持有观察'
        signals['holdings'].append({
            'name': name, 'code': code,
            'action': action.strip(),
            'close': close_price,
            'zhongji': bs.get('flags', '') if bs else '',
            'tupo': '',
            'change': chg_val,
            'structure': cache.get(code, {}).get('structure', '--'),
            'stage': cache.get(code, {}).get('stage', '--'),
            'ema': cache.get(code, {}).get('ema', '--'),
            'vol_analysis': cache.get(code, {}).get('vol_analysis', '--'),
        })
    return signals, cache, bs_by_code

# ====== ⑤ 每日交易计划 ======

def generate_trading_plan(market_cycle, mainline_data, logic_classify, signals_data, existing_holdings,
                          holdings_review=None, buy_signals_review=None):
    """综合前4项生成次日交易计划（3L体系标准）
    
    3L交易计划规范（源自教材6.6-6.7）：
    - 大盘定仓位 → market_cycle决定总仓位水位
    - 主线定方向 → mainline_data决定选股方向
    - 个股定操作 → holdings_review的signal/stage决定每只操作
    - 买点定机会 → buy_signals_review的优先级决定关注顺序
    """
    plan = {
        'overall_strategy': market_cycle.get('strategy', '正常交易'),
        'position_level': market_cycle.get('position_pct', '半仓'),
        'build_per_stock_pct': f"{market_cycle.get('build_per_stock_pct', 5)}%/只",
        'main_lines': [],
        'position_detail': '',
        'holdings_action': [],  # 个股操作建议
        'buy_priority': [],     # 买点优先级
        'risk_items': [],       # 风险项
    }

    # 主线方向
    for line in (mainline_data.get('lines', [])[:3]):
        plan['main_lines'].append(f"{line['name']}({line['chg_20d']}%)")

    # 3L仓位规则说明
    pos = market_cycle.get('position', '波中')
    plan['position_detail'] = {
        '偏波峰': '偏波峰仓位五成，建仓5%/只。大盘偏高位，控制总仓位，收紧止盈线',
        '波中偏上': '波中偏上仓位六至七成，建仓5%/只。正常交易，注意减仓信号',
        '波中': '波中仓位七至八成，建仓5%/只。正常交易，积极选股',
        '波中偏下': '波中偏下仓位五至七成，建仓5%/只。谨慎选股，收紧止损',
        '偏波谷': '偏波谷仓位五至八成，建仓10%/只。积极寻找买点，止损后换股补回',
    }.get(pos, '正常仓位管理')

    # 个股操作建议（用 holdings_review 的 signal + stage）
    if holdings_review:
        for h in holdings_review:
            name = f"{h['name']}({h['code']})"
            sig = h.get('signal', 'hold')
            stage = h.get('stage', '')
            struct = h.get('structure', '')
            
            if sig == 'sell':
                plan['holdings_action'].append({
                    'stock': name, 'action': '卖出', 'reason': f'{struct}·{stage}', 'priority': '高'
                })
            elif sig == 'buy':
                buy_pt = h.get('buy_point', '买点')
                plan['holdings_action'].append({
                    'stock': name, 'action': f'执行{buy_pt}', 'reason': f'{struct}·{stage}', 'priority': '高'
                })
            elif stage == '加速':
                plan['holdings_action'].append({
                    'stock': name, 'action': '持有·关注止盈', 'reason': f'{struct}·{stage}，关注放量滞涨/加速变缓', 'priority': '中'
                })
            elif stage == '缩量整理':
                plan['holdings_action'].append({
                    'stock': name, 'action': '持有·可加仓', 'reason': f'{struct}·{stage}，供应枯竭等待放量', 'priority': '中'
                })
            elif stage == '上行':
                plan['holdings_action'].append({
                    'stock': name, 'action': '持有不动', 'reason': f'{struct}·{stage}，趋势健康', 'priority': '低'
                })
            elif stage == '滞涨':
                plan['holdings_action'].append({
                    'stock': name, 'action': '警惕·考虑减仓', 'reason': f'{struct}·{stage}，EMA10走平', 'priority': '高'
                })
            elif stage == '转弱':
                plan['holdings_action'].append({
                    'stock': name, 'action': '关注·可换股', 'reason': f'{struct}·{stage}，EMA10拐头向下', 'priority': '高'
                })
            elif stage == '区间底部':
                plan['holdings_action'].append({
                    'stock': name, 'action': '支撑位·可加仓', 'reason': f'{struct}·{stage}，区底企稳', 'priority': '中'
                })
            elif stage == '区间顶部':
                plan['holdings_action'].append({
                    'stock': name, 'action': '压力位·注意减仓', 'reason': f'{struct}·{stage}，区顶受阻', 'priority': '高'
                })
            elif stage == '区间中段':
                plan['holdings_action'].append({
                    'stock': name, 'action': '等待方向', 'reason': f'{struct}·{stage}，无明确方向', 'priority': '低'
                })

    # 买点优先级（主线突破 > 主线中继 > 非主线）
    if buy_signals_review:
        for s in buy_signals_review:
            is_main = s.get('sector', '') in [l.split('(')[0] for l in plan['main_lines']]
            pm1 = s.get('profit_model1', False)
            trend = s.get('trend_stock', False)
            priority = 0
            if is_main and s['buy_point'] == '突破买点' and pm1: priority = 1
            elif is_main and s['buy_point'] == '突破买点': priority = 2
            elif is_main and s['buy_point'] == '中继买点' and pm1: priority = 3
            elif is_main and s['buy_point'] == '中继买点': priority = 4
            elif s['buy_point'] == '突破买点': priority = 5
            else: priority = 6
            plan['buy_priority'].append({
                'name': s['name'], 'code': s['code'], 'sector': s.get('sector', ''),
                'buy_point': s['buy_point'], 'is_main': is_main,
                'profit_model1': pm1, 'trend_stock': trend, 'priority': priority,
                'change': s.get('change', 0),
            })
        plan['buy_priority'].sort(key=lambda x: x['priority'])
        # 同级内部按change降序（涨幅优先）
        plan['buy_priority'] = sorted(plan['buy_priority'], key=lambda x: (x['priority'], -x['change']))
        plan['buy_priority'] = plan['buy_priority'][:10]  # TOP10

    # 风险项
    # ① 大盘风险
    score = market_cycle.get('score', 0)
    if score >= 0.8:
        plan['risk_items'].append('🔴 大盘偏波峰，控制总仓位，收紧止盈')
    elif score <= -0.5:
        plan['risk_items'].append('🟢 大盘偏波谷，积极寻找买点机会')
    
    # ② 个股风险
    if holdings_review:
        sell_stocks = [h for h in holdings_review if h.get('signal') == 'sell']
        weak_stocks = [h for h in holdings_review if h.get('stage') in ('转弱', '滞涨') and h.get('signal') != 'sell']
        accel_stocks = [h for h in holdings_review if h.get('stage') == '加速']
        
        if sell_stocks:
            names = '、'.join([h['name'] for h in sell_stocks])
            plan['risk_items'].append(f'🔴 {names} 触发卖出信号，严格按计划执行')
        if weak_stocks:
            names = '、'.join([h['name'] for h in weak_stocks])
            plan['risk_items'].append(f'⚠️ {names} 趋势转弱/滞涨，关注止损位')
        if accel_stocks:
            names = '、'.join([h['name'] for h in accel_stocks])
            plan['risk_items'].append(f'📈 {names} 处于加速阶段，关注左侧止盈信号')

    # ③ 仓位集中度风险
    if holdings_review and len(holdings_review) <= 3:
        plan['risk_items'].append(f'💡 持仓集中度较高（仅{len(holdings_review)}只），考虑分散风险')
    elif holdings_review and len(holdings_review) >= 10:
        plan['risk_items'].append(f'💡 持仓较为分散（{len(holdings_review)}只），可聚焦主线精简持仓')

    if not plan['risk_items']:
        plan['risk_items'].append('✅ 整体风险可控，按正常节奏交易')

    # 个股操作按优先级排序：高→中→低
    pri_order = {'高': 0, '中': 1, '低': 2}
    plan['holdings_action'].sort(key=lambda x: pri_order.get(x['priority'], 9))

    return plan

# ====== 盈利模式检查 ======

def load_market_data_for_profit_check():
    return get_all_stocks()  # 与扫描同源，确保最新


# 公共函数从 buy_point_detection 导入
from scripts.buy_point_detection import check_profit_model1_on_signals, check_trend_stock_on_signals

# ====== 主流程 ======

def generate_daily_review(date_str=None):
    """生成完整每日复盘数据"""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    print(f"[3L复盘] 生成 {date_str} 复盘数据...")

    # 已有存档
    existing = load_cached_data(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'))
    if not existing:
        existing = {
            'date': date_str,
            'holdings': [],
            'buy_signals': [],
            'stocks': {'stocks': []}
        }
        print(f"[3L复盘] 新建存档")
    else:
        print(f"[3L复盘] 载入已有存档")

    # 获取大盘K线数据并过滤到指定日期
    index_klines = fetch_index_klines(120)
    index_klines = [k for k in index_klines if k['date'] <= date_str]
    today_quote = fetch_market_quote()

    print(f"[3L复盘] K线数据: 共{len(index_klines)}天, 最新={index_klines[-1]['date'] if index_klines else '无'}")
    
    # 如果过滤后无数据，按指定日期向前取
    if not index_klines:
        index_klines = fetch_index_klines(120)
        index_klines = [k for k in index_klines if k['date'] <= date_str]
    
    # ① 大盘周期判定
    print("[3L复盘] ① 判定大盘周期(V5)...")
    market_cycle = judge_peak_valley(index_klines)
    # 使用K线收盘价（按指定日期）
    if index_klines:
        last = index_klines[-1]
        prev = index_klines[-2] if len(index_klines) >= 2 else None
        market_cycle['price'] = f"{last['close']:.2f}"
        if prev:
            chg_pct = (last['close'] - prev['close']) / prev['close'] * 100
            market_cycle['change'] = round(chg_pct, 2)
        else:
            market_cycle['change'] = 0
        market_cycle['data_date'] = last.get('date', date_str)

    # ② 动量主线评判
    print("[3L复盘] ② 计算动量主线...")
    mainline_data = get_mainline_data(date_str)
    if mainline_data['lines']:
        persistence = track_mainline_persistence(date_str, mainline_data['lines'])
        mainline_data['persistence'] = persistence

    # ③ 最强逻辑归类
    print("[3L复盘] ③ 归类最强逻辑...")
    # 从 holdings.json 读取最新持仓数据（来源：持仓管理页面）
    holdings_file = os.path.join(WWW_DIR, 'private', 'holdings.json')
    live_holdings = []
    if os.path.isfile(holdings_file):
        try:
            with open(holdings_file) as f:
                hdata = json.load(f)
            live_holdings = hdata.get('holdings', [])
        except:
            pass
    holdings = live_holdings or existing.get('holdings', []) or existing.get('stocks', {}).get('stocks', [])
    buy_signals = existing.get('buy_signals', [])

    # 优先从最新扫描结果读取（已应用中继买点缩量硬性条件等最新阈值）
    latest_scan_path = LATEST_SCAN_PATH
    if os.path.isfile(latest_scan_path):
        try:
            with open(latest_scan_path) as _f:
                _scan = json.load(_f)
            _scan_results = _scan.get('results', [])
            if _scan_results:
                _scan_date = _scan.get('scan_date', '')
                print(f"[3L复盘] 📡 使用最新扫描结果: {_scan_date} ({len(_scan_results)}条)")
                buy_signals = []
                for r in _scan_results:
                    buy_signals.append({
                        'name': r.get('name', r['code']),
                        'code': r['code'],
                        'sector': r['sector'],
                        'buy_point': r['buy_type'],
                        'price': r.get('close', 0),
                        'change': r.get('gain', 0),
                        'score': r['score'],
                        'flags': r['flags'],
                        'profit_model1': False,
                        'trend_stock': False,
                    })
        except Exception as e:
            print(f"[3L复盘] ⚠️ 读取最新扫描结果失败: {e}")

    # 盈利模式1检查：在归类前给买点信号打上标记
    print("[3L复盘] 🔍 检查盈利模式1...")
    all_stocks = load_market_data_for_profit_check()
    buy_signals = check_profit_model1_on_signals(buy_signals, all_stocks, date_str)
    # 趋势股检查（6条件）：沿EMA5上行的趋势票标记
    print("[3L复盘] 🔍 检查趋势股...")
    buy_signals = check_trend_stock_on_signals(buy_signals, all_stocks, date_str)

    logic_classify = classify_stocks_by_mainline(mainline_data, holdings, buy_signals)

    # ④ 量价择时
    print("[3L复盘] ④ 量价择时分析...")

    # 如果 buy_signals 为空，从全量自选股扫描买点信号
    if not buy_signals:
        try:
            sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from buy_point_detection import format_buy_signals
            # 加载 all_stocks_60d.json（buy_point_detection需要这个格式）
            as60_path = ALL_STOCKS_PATH
            if os.path.isfile(as60_path):
                with open(as60_path) as f:
                    as60_data = json.load(f)
                all_stocks_60d = as60_data.get('stocks', {})
                # 找数据中最新可用日期
                latest_date = ''
                for sec, stocks in all_stocks_60d.items():
                    for code, kls in stocks.items():
                        if kls and kls[-1]['date'] > latest_date:
                            latest_date = kls[-1]['date']
                
                # 如果最新日期 < 今天，拉持仓股的最新K线（补全到最新交易日）
                today_yyyymmdd = date_str.replace('-', '')
                if latest_date and latest_date < today_yyyymmdd:
                    try:
                        import requests as req
                        hdrs = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'}
                        # 只补拉持仓股的：从holdings.json读代码
                        hf = os.path.join(WWW_DIR, 'private', 'holdings.json')
                        if os.path.isfile(hf):
                            with open(hf) as f:
                                hdata = json.load(f)
                            for h in hdata.get('holdings', []):
                                code = h.get('code', '')
                                if not code:
                                    continue
                                mkt = 'sz' if code.startswith(('0', '3')) else 'sh'
                                url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,5,qfq'
                                r = req.get(url, headers=hdrs, timeout=5)
                                d = r.json()
                                day_data = d.get('data', {}).get(f'{mkt}{code}', {}).get('day', [])
                                if not day_data:
                                    day_data = d.get('data', {}).get(f'{mkt}{code}', {}).get('qfqday', [])
                                if day_data:
                                    latest_k = day_data[-1]
                                    if len(latest_k) >= 6:
                                        new_rec = {
                                            'date': latest_k[0].replace('-', ''),
                                            'open': float(latest_k[1]),
                                            'close': float(latest_k[2]),
                                            'high': float(latest_k[3]),
                                            'low': float(latest_k[4]),
                                            'volume': int(float(latest_k[5]) * 100),  # 腾讯财经单位是手→股
                                        }
                                        # 追加到对应方向下该股票的缓存
                                        for sec_name2, stocks2 in all_stocks_60d.items():
                                            if code in stocks2:
                                                # 去重：如果最新日期已存在就不加
                                                existing_dates = {k['date'] for k in stocks2[code]}
                                                if new_rec['date'] not in existing_dates:
                                                    stocks2[code].append(new_rec)
                    except Exception as e:
                        print(f"[3L复盘] 补拉持仓数据失败: {e}")
                    # 重新找最新日期
                    latest_date = ''
                    for sec, stocks in all_stocks_60d.items():
                        for code, kls in stocks.items():
                            if kls and kls[-1]['date'] > latest_date:
                                latest_date = kls[-1]['date']
                
                scan_date = latest_date if latest_date else today_yyyymmdd
                ml_names = [l['name'] for l in mainline_data.get('lines', [])]
                # 加载自选股名单，只扫自选股
                wl = get_watchlist()
                wl_codes = set(s['code'] for s in wl)
                scan_result = format_buy_signals(scan_date, all_stocks_60d, ml_names, top_n=20, market_position=market_cycle.get('position', ''), watchlist_codes=wl_codes)
            # 合并主线/非主线候选
            seen = set()
            for key in ['zhongji_main', 'zhongji_nonmain', 'tupo_main', 'tupo_nonmain']:
                for s in scan_result.get(key, []):
                    if s['code'] not in seen:
                        seen.add(s['code'])
                        buy_signals.append({
                            'name': s.get('name', s['code']),
                            'code': s['code'],
                            'sector': s['sector'],
                            'buy_point': '中继买点' if key.startswith('zhongji') else '突破买点',
                            'price': s.get('close', 0), 'change': s['gain'],
                            'score': s['score'],
                            'flags': s['flags'],
                            'profit_model1': False,
                        })
            print(f"[3L复盘] 全量扫描: {len(buy_signals)} 个买点信号")
        except Exception as e:
            print(f"[3L复盘] 全量扫描跳过: {e}")

    # 从最新 buy_signals 生成持仓信号（必须在扫描之后）
    timing_signals, stock_cache, bs_by_code = get_buy_sell_signals(holdings, buy_signals)

    # 构建 holdings_data 字典便于查询
    holdings_data = {h.get('code', ''): h for h in holdings}

    # 生成持仓个股复盘（从实时买点检测结果）
    holdings_review = []
    # 引入统一信号判断
    import sys as _sys
    _sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/trading/stock-action-judgment/scripts')
    from judge_signal import judge_signal
    for h in timing_signals.get('holdings', []):
        d = holdings_data.get(h.get('code', ''), {})
        structure = h.get('structure', '')
        stage = h.get('stage', '--')
        # 区间震荡：用关键点支撑位重算stage
        if structure == '区间震荡':
            try:
                with open(ALL_STOCKS_PATH) as _f:
                    _all = json.load(_f)
                code = h.get('code', '')
                for _sec, _ss in _all.get('stocks', {}).items():
                    if code in _ss and _ss[code] and len(_ss[code]) >= 15:
                        _kls = _ss[code]
                        _highs = [k['high'] for k in _kls]
                        _lows = [k['low'] for k in _kls]
                        _closes = [k['close'] for k in _kls]
                        _opens = [k['open'] for k in _kls]
                        _all_supports = sorted([
                            max(_highs[i-10:i])
                            for i in range(10, len(_kls))
                            if _closes[i] > max(_highs[i-10:i]) and _closes[i] > _opens[i]
                            and max(_highs[i-10:i]) < _closes[-1]
                        ], reverse=True)
                        _resistance = max(_highs[-15:])
                        _support = None
                        for _s in _all_supports:
                            if (_closes[-1] - _s) / _closes[-1] >= 0.015:
                                _support = _s
                                break
                        _support = _support or min(_lows[-20:])
                        if _resistance > _support:
                            _pct = (_closes[-1] - _support) / (_resistance - _support) * 100
                            if _pct < 30: stage = '区间底部'
                            elif _pct > 70: stage = '区间顶部'
                            else: stage = '区间中段'
                        break
            except Exception:
                pass
        code_sig, signal_text, _ = judge_signal(
            structure=structure, stage=stage, buy_point=h['action'],
        )
        # 买点仅在信号为buy时保留，只显示类型名不显示flags
        buy_point = h['action'].split()[0] if code_sig == 'buy' and h['action'] else ''
        # 查找盈利模式1标记
        bs_lookup = bs_by_code.get(h.get('code', ''), {})
        pm1 = bs_lookup.get('profit_model1', False)
        trend = bs_lookup.get('trend_stock', False)
        holdings_review.append({
            'name': h['name'], 'code': h['code'],
            'sector': d.get('direction', ''),
            'price': h.get('close', 0),
            'change': h.get('change', 0),
            'buy_point': buy_point,
            'structure': structure,
            'stage': stage,
            'key_level': '--',
            'stop_loss': '',
            'signal': code_sig,
            'ema': h.get('ema', '--'),
            'vol_analysis': h.get('vol_analysis', '--'),
            'profit_model1': pm1,
            'trend_stock': trend,
        })
    # 按结构优先排序：上涨趋势 > 区间震荡 > 下降趋势
    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}
    holdings_review.sort(key=lambda x: struct_priority.get(x['structure'], 3))
    
    # 生成候选买点信号review（与第④部分相同判定逻辑）
    buy_signals_review = []
    for s in buy_signals:
        code = s.get('code', '')
        sc = stock_cache.get(code, {})
        structure = sc.get('structure', '上涨趋势')
        stage = sc.get('stage', '--')
        # 区间震荡：用关键点支撑位重算stage（同holdings逻辑）
        if structure == '区间震荡':
            try:
                with open(ALL_STOCKS_PATH) as _f:
                    _all = json.load(_f)
                for _sec, _ss in _all.get('stocks', {}).items():
                    if code in _ss and _ss[code] and len(_ss[code]) >= 15:
                        _kls = _ss[code]
                        _highs = [k['high'] for k in _kls]
                        _lows = [k['low'] for k in _kls]
                        _closes = [k['close'] for k in _kls]
                        _opens = [k['open'] for k in _kls]
                        _all_supports = sorted([
                            max(_highs[i-10:i])
                            for i in range(10, len(_kls))
                            if _closes[i] > max(_highs[i-10:i]) and _closes[i] > _opens[i]
                            and max(_highs[i-10:i]) < _closes[-1]
                        ], reverse=True)
                        _resistance = max(_highs[-15:])
                        _support = None
                        for _s in _all_supports:
                            if (_closes[-1] - _s) / _closes[-1] >= 0.015:
                                _support = _s
                                break
                        _support = _support or min(_lows[-20:])
                        if _resistance > _support:
                            _pct = (_closes[-1] - _support) / (_resistance - _support) * 100
                            if _pct < 30: stage = '区间底部'
                            elif _pct > 70: stage = '区间顶部'
                            else: stage = '区间中段'
                        break
            except Exception:
                pass
        code_sig, _, _ = judge_signal(
            structure=structure, stage=stage,
            buy_point=s.get('buy_point', ''),
        )
        # 第⑤部分只展示买入信号
        if code_sig != 'buy':
            continue
        buy_point_display = s.get('buy_point', '')
        ema = sc.get('ema', '--')
        vol_analysis = sc.get('vol_analysis', '--')
        buy_signals_review.append({
            'name': s.get('name', '?'), 'code': code,
            'sector': s.get('sector', s.get('direction', '')),
            'buy_point': buy_point_display,
            'price': s.get('price', 0), 'change': s.get('change', 0),
            'profit_model1': s.get('profit_model1', False),
            'trend_stock': s.get('trend_stock', False),
            'structure': structure,
            'stage': stage,
            'signal': code_sig,
            'ema': ema,
            'vol_analysis': vol_analysis,
        })
    # 按结构优先排序
    buy_signals_review.sort(key=lambda x: struct_priority.get(x['structure'], 3))

    # ⑤ 每日交易计划
    print("[3L复盘] ⑤ 生成交易计划...")
    trading_plan = generate_trading_plan(market_cycle, mainline_data, logic_classify, timing_signals, holdings,
                                         holdings_review=holdings_review, buy_signals_review=buy_signals_review)

    # 组装（含动量和行业地图，用于历史复盘时展示）
    review = {
        'date': date_str,
        'market': {
            **market_cycle,
            'date': date_str,
        },
        'mainline': mainline_data,
        'logic_classify': logic_classify,
        'timing_signals': timing_signals,
        'trading_plan': trading_plan,
        'holdings': holdings,
        'buy_signals': buy_signals,
        'holdings_review': holdings_review,
        'buy_signals_review': buy_signals_review,
    }

    # 保存动量数据（涨停/新高）到存档
    try:
        mom_cache = os.path.join(WWW_DIR, 'data', 'cache', f'momentum_{date_str}.json')
        if os.path.isfile(mom_cache):
            with open(mom_cache) as _f:
                review['momentum'] = json.load(_f)
        else:
            # 尝试运行 fetch_momentum.py 现拉
            mom_script = os.path.join(WWW_DIR, 'fetch_momentum.py')
            if os.path.isfile(mom_script):
                import subprocess
                r = subprocess.run([sys.executable, mom_script], capture_output=True, text=True, timeout=90)
                if r.returncode == 0:
                    review['momentum'] = json.loads(r.stdout)
    except Exception as e:
        print(f"[3L复盘] 保存动量数据失败: {e}")

    # 保存行业地图（供历史复盘展示最强逻辑）
    try:
        im_path = INDUSTRY_MAP_PATH
        if os.path.isfile(im_path):
            with open(im_path) as _f:
                raw_map = json.load(_f)
            # 按 ths_industry 分组（同前端 loadLogicMap 逻辑）
            industry_groups = {}
            for code, info in raw_map.items():
                ind = info.get('ths_industry', '') or '未知'
                if ind in ('未知', '获取失败') or ind.startswith('ERROR:'):
                    continue
                if ind not in industry_groups:
                    industry_groups[ind] = []
                industry_groups[ind].append({
                    'code': code,
                    'name': info.get('name', info.get('direction', '')),
                    'direction': info.get('direction', ''),
                })
            review['industry_map_archive'] = {
                'groups': dict(sorted(industry_groups.items(), key=lambda x: -len(x[1]))),
                'total': sum(len(v) for v in industry_groups.values()),
            }
    except Exception as e:
        print(f"[3L复盘] 保存行业地图失败: {e}")

    # 保存行业板块排行（同花顺90个行业今日涨跌幅，供历史复盘板块排行展示）
    try:
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        review['industry_boards_archive'] = df.fillna('').to_dict('records')
    except Exception as e:
        print(f"[3L复盘] 保存行业板块排行失败: {e}")

    # 保存
    save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), review)
    # 同步到 review_data.json（server读取源）
    save_json(os.path.join(WWW_DIR, 'private', 'review_data.json'), review)
    print(f"[3L复盘] ✅ 已保存 {date_str} 复盘数据")

    # 补充生成买点信号的关键点图
    try:
        bp_script = os.path.join(os.path.dirname(__file__), '..', '.hermes', 'profiles', '3l', 'skills',
                                  'research', 'daily-3l-review', 'scripts', 'batch_gen_charts.py')
        if not os.path.exists(bp_script):
            bp_script = '/home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/batch_gen_charts.py'
        if os.path.isfile(bp_script):
            import subprocess
            subprocess.run([sys.executable, bp_script], timeout=120, capture_output=True)
            print("[3L复盘] 🎨 关键点图已更新")
    except Exception as e:
        print(f"[3L复盘] 🎨 生成关键点图跳过: {e}")

    # 生成资金流向图（传入复盘日期，确保图表日期正确）
    try:
        import subprocess
        ff_script = os.path.join(WWW_DIR, 'gen_fund_flow_chart.py')
        if os.path.isfile(ff_script):
            subprocess.run([sys.executable, ff_script, date_str], timeout=120, capture_output=True)
            print("[3L复盘] 💰 资金流向图已生成")
    except Exception as e:
        print(f"[3L复盘] 💰 生成资金流向图跳过: {e}")

    # 归档图表（按日期目录隔离，名称不变）
    try:
        import shutil
        chart_archive_dir = os.path.join(WWW_DIR, 'review_charts', 'archive', date_str)
        os.makedirs(chart_archive_dir, exist_ok=True)
        src_charts = [
            (os.path.join(WWW_DIR, 'review_charts', 'zzqz_v2.svg'), 'zzqz_v2.svg'),
            (os.path.join(WWW_DIR, 'charts', 'fund_flow_chart.png'), 'fund_flow_chart.png'),
        ]
        for src, basename in src_charts:
            if os.path.isfile(src):
                dst = os.path.join(chart_archive_dir, basename)
                shutil.copy2(src, dst)
                print(f"[3L复盘] 📊 图表已归档: archive/{date_str}/{basename}")
        # 在存档JSON中记录图表路径（供历史前端加载）
        review['charts'] = {
            'index_chart': f'/review_charts/archive/{date_str}/zzqz_v2.svg',
            'fund_flow': f'/review_charts/archive/{date_str}/fund_flow_chart.png',
        }
        # 重新保存存档（更新chart路径）
        save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), review)
    except Exception as e:
        print(f"[3L复盘] 📊 图表归档失败: {e}")

    # ====== Step 5: 生成每日成果PDF ======
    try:
        generate_daily_achievements_pdf(date_str)
    except Exception as e:
        print(f"[3L复盘] 📄 生成每日成果PDF失败: {e}")

    return review

def generate_daily_achievements_pdf(date_str):
    """生成每日成果PDF（每日成果_YYYYMMDD.pdf），自动跳过已存在的"""
    pdf_name = f'每日成果_{date_str.replace("-", "")}.pdf'
    pdf_path = os.path.join(WWW_DIR, 'files', pdf_name)
    # 如果已存在则跳过（防止每天重复生成覆盖内容）
    if os.path.isfile(pdf_path):
        print(f"[3L复盘] 📄 每日成果PDF已存在: {pdf_name}")
        return
    
    # 解析日期
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    weekdays = ['一','二','三','四','五','六','日']
    wd = weekdays[dt.weekday()]
    
    # 获取复盘数据中的摘要信息
    review_file = os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json')
    market_cycle = '未知'
    mainline_count = 0
    if os.path.isfile(review_file):
        try:
            with open(review_file) as f:
                rd = json.load(f)
            mc = rd.get('market_cycle', {})
            if isinstance(mc, dict):
                market_cycle = mc.get('position', '未知')
            ml = rd.get('mainlines', {})
            if isinstance(ml, dict):
                ml_list = ml.get('main_lines', ml.get('sectors', []))
                if isinstance(ml_list, list):
                    mainline_count = len(ml_list)
        except: pass
    
    # 生成HTML
    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>3L每日成果 · {date_str}</title>
<style>
body{{font-family:'Noto Sans CJK SC','WenQuanYi Zen Hei',sans-serif;color:#333;margin:40px;background:#fff}}
h1{{font-size:22px;color:#2563eb;border-bottom:2px solid #2563eb;padding-bottom:10px;margin-bottom:20px}}
.meta{{color:#888;font-size:13px;margin-bottom:24px}}
.section{{margin-bottom:28px}}
.section-title{{font-size:16px;color:#1e40af;background:#eff6ff;padding:10px 14px;border-left:4px solid #2563eb;margin-bottom:12px}}
.section-title .num{{display:inline-flex;width:24px;height:24px;background:#2563eb;color:#fff;border-radius:50%;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-right:8px}}
.item{{padding:8px 14px;margin-bottom:6px;border-left:3px solid #e5e7eb}}
.item .title{{font-weight:600;color:#333}}
.item .desc{{color:#666;font-size:13px;margin-top:4px;line-height:1.6}}
.tag{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;margin-left:8px}}
.tag-blue{{background:#dbeafe;color:#2563eb}}
</style></head>
<body>
<h1>📊 3L 每日复盘 · {date_str} 星期{wd}</h1>
<div class="meta">自动生成 · 复盘数据概要</div>
<div class="section">
<div class="section-title"><span class="num">1</span> 大盘周期</div>
<div class="item"><div class="title">当前判定：{market_cycle}</div></div>
</div>
<div class="section">
<div class="section-title"><span class="num">2</span> 动量主线</div>
<div class="item"><div class="title">主线板块数量：{mainline_count} <span class="tag tag-blue">得分≥15</span></div></div>
</div>
<div class="section">
<div class="section-title"><span class="num">3</span> 关键变更备注</div>
<div class="item"><div class="title">本复盘由3L每日复盘系统自动生成</div><div class="desc">数据源：腾讯API(中证全指) + akshare(同花顺行业板块) + 全量创新高扫描。</div></div>
</div>
</body></html>'''
    
    html_path = os.path.join(WWW_DIR, 'files', f'每日成果_{date_str.replace("-", "")}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    import subprocess
    result = subprocess.run(
        ['wkhtmltopdf', '--encoding', 'utf-8', '--page-size', 'A4', html_path, pdf_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(f"[3L复盘] 📄 每日成果PDF已生成: {pdf_name}")
    else:
        print(f"[3L复盘] ⚠️ PDF生成失败: {result.stderr[-200:]}")
    # 清理临时HTML（PDF已生成）
    try: os.remove(html_path)
    except: pass

def update_historical_archives():
    """为所有历史存档补充新字段"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return
    for fname in sorted(os.listdir(REVIEW_ARCHIVE_DIR)):
        if not fname.endswith('.json'):
            continue
        date_str = fname[:-5]
        fp = os.path.join(REVIEW_ARCHIVE_DIR, fname)
        try:
            with open(fp) as f:
                data = json.load(f)
            changed = False
            if 'market_cycle' not in data:
                if 'market' in data and isinstance(data['market'], dict):
                    data['market_cycle'] = data['market']
                    changed = True
            if changed:
                save_json(fp, data)
                print(f"[3L复盘] 更新历史存档: {date_str}")
        except:
            continue

if __name__ == '__main__':
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    update_historical_archives()
    generate_daily_review(date_arg)
