#!/usr/bin/env python3
"""买点检测模块 — 基于系统B（EMA10趋势分析）

完全基于3L教材的买点定义：
- 中继买点：上升趋势中缩量回踩关键点 / 区间底部缩量企稳
- 突破买点：整理平台放量突破前高关键阻力

不使用独立于系统B的任何机械条件（已废弃check_zhongji/check_tupo）。
"""
import json, sys, os

# 导入系统B：EMA10趋势分析
_EMA_UTILS_PATH = os.path.join(
    os.path.dirname(__file__), '..', '..', '..',
    'trading', 'ema10-trend-judgment', 'scripts')
sys.path.insert(0, _EMA_UTILS_PATH)
from ema_utils import get_ema_arrangement, get_structure, get_stage, ema_list

def find_idx(date_str, klines):
    """找K线中指定日期的索引"""
    date_clean = date_str.replace('-', '')
    for i, k in enumerate(klines):
        k_date = str(k["date"]).replace('-', '')
        if k_date == date_clean:
            return i
    return -1

def _resolve_code(code, all_stocks):
    """统一code格式，返回(code, klines)"""
    for sec, stocks in all_stocks.items():
        if code in stocks:
            return code, stocks[code]
        # 去掉前缀再试
        raw = code
        for p in ['SH', 'SZ', 'sh', 'sz']:
            if code.startswith(p):
                raw = code[len(p):]
                break
        if raw in stocks:
            return raw, stocks[raw]
        # 6位纯数字
        raw_final = code[-6:] if len(code) >= 6 else code
        if raw_final in stocks:
            return raw_final, stocks[raw_final]
    return None, None

def _volume_ratio(klines, idx, field='volume'):
    """计算当日量/MA5均量的比值"""
    vols = [klines[idx-4+i].get(field, klines[idx-4+i].get('vol', 0)) for i in range(5)]
    vma5 = sum(vols) / 5 if all(v > 0 for v in vols) else 0
    vol = klines[idx].get(field, klines[idx].get('vol', 0))
    return vol / vma5 if vma5 > 0 else 0

def _find_support_levels(klines, idx):
    """找最近的关键支撑位（从突破点计算）"""
    highs = [k['high'] for k in klines[:idx+1]]
    closes = [k['close'] for k in klines[:idx+1]]
    opens = [k['open'] for k in klines[:idx+1]]
    
    # 找所有"突"关键点：close突破前10日最高
    supports = []
    for i in range(10, idx+1):
        if closes[i] > max(highs[i-10:i]) and closes[i] > opens[i]:
            support_price = max(highs[i-10:i])
            if support_price < closes[-1]:
                supports.append(support_price)
    
    # 从高到低排序，取距收盘≥1.5%的最近支撑
    supports = sorted(set(supports), reverse=True)
    for s in supports:
        if (closes[-1] - s) / closes[-1] >= 0.015:
            return s
    return min(highs[-20:]) if len(highs) >= 20 else None

def _layer2_factor(is_main_line=True):
    """第2层：板块主线系数调整
    主线板块（动量评分领先）：资金聚集，供应衰竭可信 → 放宽5%（×1.05）
    非主线板块：不被资金关注，缩量不可靠 → 大幅收紧（×0.80）
    """
    return 1.05 if is_main_line else 0.80


def _shrink_threshold(market_position='', is_main_line=True):
    """根据市场环境和板块主线动态调整缩量阈值
    
    三层递进：
      第1层 大盘 → 基准阈值（0.70~0.85）
      第2层 板块 → 系数调整（主线×1.05 / 非主线×0.95）
      第3层 个股 → 不调阈值，只决定买点类型
    """
    mapping = {
        '波峰': 0.85, '波中偏上': 0.85,
        '波中': 0.80,
        '波中偏下': 0.75,
        '波谷': 0.70,
    }
    base = mapping.get(market_position, 0.80)
    factor = _layer2_factor(is_main_line)
    return round(base * factor, 2)


def _surge_threshold(market_position='', is_main_line=True):
    """放量阈值 — 含板块系数调整
    主线：阈值更低（易达标），非主线：阈值更高（需更强放量）
    """
    mapping = {
        '波峰': 1.2, '波中偏上': 1.25,
        '波中': 1.3,
        '波中偏下': 1.4,
        '波谷': 1.5,
    }
    base = mapping.get(market_position, 1.3)
    factor = _layer2_factor(is_main_line)
    # 主线放宽(base变小)，非主线收紧(base变大)
    return round(base / factor, 2)


def _ema_list(data, period):
    """计算EMA列表"""
    r = [None] * len(data)
    m = 2 / (period + 1)
    for i in range(len(data)):
        if i == 0:
            r[i] = data[i]
        elif r[i-1] is not None:
            r[i] = (data[i] - r[i-1]) * m + r[i-1]
    return r


def _is_trend_with_ema5(klines, idx):
    """判断是否为沿EMA5上行的趋势票

    条件：
    1. 上涨趋势（structure == '上涨趋势'）
    2. 阶段为'上行'或'缩量整理'（排除加速/滞涨/转弱）
    3. 末15根K线中 ≥60%收盘在EMA5上方（贴着EMA5走）
    4. 最近3天收盘不能跌破EMA10（站在10线上）
    5. EMA5/10/20/30多头排列并向上发散
    6. 末30根最低点起涨幅≥30%
    """
    closes = [k['close'] for k in klines[:idx+1]]
    if len(closes) < 30:
        return False

    structure = get_structure(closes)
    if structure != '上涨趋势':
        return False

    highs_60 = [k['high'] for k in klines[:idx+1]]
    lows_60 = [k['low'] for k in klines[:idx+1]]
    vols_60 = [k.get('volume', k.get('vol', 0)) for k in klines[:idx+1]]
    stage = get_stage(closes, structure, highs_60, lows_60, volumes=vols_60)
    if stage not in ('上行', '缩量整理'):
        return False

    # 计算EMA5/10/20/30
    ema5 = _ema_list(closes, 5)
    ema10 = ema_list(closes, 10)
    ema20 = ema_list(closes, 20)
    ema30 = ema_list(closes, 30)

    last15_close = closes[-15:]
    last15_ema5 = [v for v in ema5[-15:] if v is not None]
    last15_ema10 = [v for v in ema10[-15:] if v is not None]

    if len(last15_ema5) < 15 or len(last15_ema10) < 15:
        return False

    # 条件：≥60%的K线收盘在EMA5上方
    above_count = sum(1 for i in range(15) if last15_close[i] > last15_ema5[i])
    if above_count / 15 < 0.60:
        return False

    # 条件：最近3天收盘不能跌破EMA10
    for i in range(-3, 0):
        if last15_close[i] < last15_ema10[i]:
            return False

    # 条件：EMA5/10/20/30多头排列并向上发散
    # 多头排列：E5 > E10 > E20 > E30
    # 向上发散：各EMA斜率都为正（末3根上升）
    e5v, e10v, e20v, e30v = ema5[-1], ema10[-1], ema20[-1], ema30[-1]
    if not all([e5v, e10v, e20v, e30v]):
        return False
    if not (e5v > e10v > e20v > e30v):
        return False

    # 各EMA末3根斜率向上
    for ema in [ema5, ema10, ema20, ema30]:
        e_last3 = [v for v in ema[-3:] if v is not None]
        if len(e_last3) < 3:
            return False
        if e_last3[-1] <= e_last3[0]:
            return False

    # 条件：涨幅足够大（从阶段最低点起至少30%）
    low_30 = min(closes[-30:])
    gain_30 = (closes[-1] - low_30) / low_30 * 100
    if gain_30 < 30:
        return False

    return True


def detect_huicai_buy_point(code, date_str, all_stocks):
    """盈利模式2 — 趋势票回踩EMA5买点

    条件：
    1. 趋势票（_is_trend_with_ema5）
    2. 当前收盘在EMA5附近（±1.5%范围内）= 回踩到了
    3. 评分固定5分，不考虑大盘/主线系数调整

    返回 dict 或 None
    """
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None

    idx = find_idx(date_str, kls)
    if idx < 30:
        return None

    if not _is_trend_with_ema5(kls, idx):
        return None

    closes = [k['close'] for k in kls[:idx+1]]
    ema5 = _ema_list(closes, 5)
    cur_ema5 = ema5[-1]
    cur_close = kls[idx]['close']

    if not cur_ema5 or cur_ema5 <= 0:
        return None

    # 当前收盘在EMA5附近 ±1.5%
    deviation = (cur_close - cur_ema5) / cur_ema5 * 100
    if abs(deviation) > 1.5:
        return None

    return {
        'code': resolved_code,
        'buy_type': '回踩买点',
        'score': 5,
        'close': round(cur_close, 2),
        'gain': round((cur_close - kls[idx-1]['close']) / kls[idx-1]['close'] * 100, 2) if idx > 0 else 0,
        'structure': '上涨趋势',
        'stage': '沿EMA5趋势',
        'ema_arrangement': get_ema_arrangement(closes),
        'detail': {
            'reason': '趋势票回踩EMA5',
            'ema5': round(cur_ema5, 2),
            'deviation_pct': round(deviation, 2),
        },
        'flags': '回踩买点',
    }


def scan_huicai_buy_points(date_str, all_stocks):
    """批量扫描盈利模式2 — 回踩买点"""
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            try:
                bt = detect_huicai_buy_point(code, date_str, all_stocks)
                if bt:
                    name = stocks[code][0].get('name', code) if stocks[code] else code
                    bt['name'] = name
                    bt['sector'] = sec_name
                    results.append(bt)
            except Exception:
                continue
    results.sort(key=lambda x: -x['score'])
    return results


def detect_buy_point(code, date_str, all_stocks, market_position='', main_lines=None):
    """基于系统B判断买点 — 返回 dict 或 None
    
    三层递进判定框架：
      第1层 大盘 -> market_position 决定基准阈值
      第2层 板块 -> main_lines 决定系数调整（+5%/-5%）
      第3层 个股 -> EMA10结构/阶段 决定买点类型
    """
    main_line_set = set(main_lines) if main_lines else set()
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None
    
    idx = find_idx(date_str, kls)
    if idx < 30:
        return None
    
    k = kls[idx]
    close = k['close']
    vol = k.get('volume', k.get('vol', 0))
    high = k['high']
    low = k['low']
    prev_close = kls[idx-1]['close']
    gain = (close - prev_close) / prev_close * 100 if prev_close else 0
    
    # ====== 系统B分析 ======
    closes_60 = [k['close'] for k in kls[:idx+1]]
    highs_60 = [k['high'] for k in kls[:idx+1]]
    lows_60 = [k['low'] for k in kls[:idx+1]]
    vols_60 = [k.get('volume', k.get('vol', 0)) for k in kls[:idx+1]]
    
    structure = get_structure(closes_60)
    stage = get_stage(closes_60, structure, highs_60, lows_60, volumes=vols_60)
    ema_arr = get_ema_arrangement(closes_60)
    
    # ====== 量能分析（三层递进：大盘→基准，板块→系数，个股→不调） ======
    vol_ratio = _volume_ratio(kls, idx)
    # 第2层：此股票所属板块是否是主线
    # 使用同花顺行业板块（与主线评分一致的口径）判断
    is_main_line = False
    try:
        if main_line_set and resolved_code:
            _imd = getattr(detect_buy_point, '_ind_map', None)
            if _imd is None:
                _im_path = '/home/ubuntu/data/3l/stock_industry_map.json'
                if os.path.isfile(_im_path):
                    with open(_im_path) as _f:
                        _imd = json.load(_f)
                    detect_buy_point._ind_map = _imd
            if _imd and resolved_code in _imd:
                stock_ind = _imd[resolved_code]
                ths_ind = stock_ind.get('ths_industry', '') if isinstance(stock_ind, dict) else ''
                if ths_ind in main_line_set:
                    is_main_line = True
    except Exception:
        # 回退到按方向判断
        for sec_name, sec_stocks in all_stocks.items():
            if resolved_code in sec_stocks and sec_name in main_line_set:
                is_main_line = True
                break
    shrink_th = _shrink_threshold(market_position, is_main_line)
    surge_th = _surge_threshold(market_position, is_main_line)
    is_shrink = vol_ratio < shrink_th
    is_surge = vol_ratio > surge_th
    
    # ====== 支撑/阻力 ======
    prev_10d_high = max(kls[idx-j]['high'] for j in range(1, 11)) if idx >= 10 else None
    is_breakout = prev_10d_high and close > prev_10d_high  # 突破前10日最高
    
    # ====== 买点判定 ======
    buy_type = None
    score = 0
    detail = {}
    
    if structure == '上涨趋势':
        if stage in ('上行', '缩量整理') and is_shrink:
            # 上升趋势缩量回踩 → 中继买点
            buy_type = '中继买点'
            score = 3
            detail = {
                'reason': '上升趋势缩量回踩',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'shrink': True,
            }
        
        if is_breakout and is_surge:
            # 放量突破前高 → 突破买点（有更高的优先级，覆盖中继）
            buy_type = '突破买点'
            score = 4
            detail = {
                'reason': '放量突破前高',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'breakout_pct': round((close - prev_10d_high) / prev_10d_high * 100, 2),
            }
    
    elif structure == '区间震荡':
        if stage == '区间底部' and is_shrink:
            # 区间底部缩量企稳 → 中继买点
            buy_type = '中继买点'
            score = 3
            detail = {
                'reason': '区间底部缩量企稳',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'shrink': True,
            }
        
        if stage == '区间顶部' and is_breakout and is_surge:
            # 区顶放量突破 → 突破买点
            buy_type = '突破买点'
            score = 4
            detail = {
                'reason': '区顶放量突破',
                'structure': structure,
                'stage': stage,
                'vol_ratio': round(vol_ratio, 2),
                'breakout_pct': round((close - prev_10d_high) / prev_10d_high * 100, 2),
            }
    
    if not buy_type:
        return None
    
    return {
        'code': resolved_code,
        'buy_type': buy_type,
        'score': score,
        'close': round(close, 2),
        'gain': round(gain, 2),
        'vol_ratio': round(vol_ratio, 2),
        'structure': structure,
        'stage': stage,
        'ema_arrangement': ema_arr,
        'detail': detail,
        'flags': buy_type,  # 兼容接口
    }


def scan_all_stocks(date_str, all_stocks, market_position='', main_lines=None):
    """扫描所有自选股，返回买点列表
    
    参数:
        main_lines: 主线板块名单（用于第2层阈值调整）
    """
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            try:
                bt = detect_buy_point(code, date_str, all_stocks, market_position=market_position, main_lines=main_lines)
                if bt:
                    name = stocks[code][0].get('name', code) if stocks[code] else code
                    bt['name'] = name
                    bt['sector'] = sec_name
                    results.append(bt)
            except Exception:
                continue
    
    # 排序：突破买点优先于中继，同类型按score
    results.sort(key=lambda x: (0 if x['buy_type'] == '突破买点' else 1, -x['score']))
    return results


def format_buy_signals(date_str, all_stocks, main_lines, top_n=5, market_position=''):
    """格式化输出买点信号（按主线板块优先，三层阈值感知）"""
    scan_results = scan_all_stocks(date_str, all_stocks, market_position=market_position, main_lines=main_lines)
    ml_set = set(main_lines) if main_lines else set()
    
    result = {"date": date_str}
    
    zhongji = [x for x in scan_results if x['buy_type'] == '中继买点']
    tupo = [x for x in scan_results if x['buy_type'] == '突破买点']
    
    result['zhongji_main'] = [x for x in zhongji if x['sector'] in ml_set][:top_n]
    result['zhongji_nonmain'] = [x for x in zhongji if x['sector'] not in ml_set][:top_n]
    result['tupo_main'] = [x for x in tupo if x['sector'] in ml_set][:top_n]
    result['tupo_nonmain'] = [x for x in tupo if x['sector'] not in ml_set][:top_n]
    
    return result


def check_profit_model1(code, date_str, all_stocks):
    """盈利模式1检查 — MA10朝上 + 近10日涨停 + 回踩买点 + 业绩好"""
    resolved_code, kls = _resolve_code(code, all_stocks)
    if not kls:
        return None
    
    idx = find_idx(date_str, kls)
    if idx < 15:
        return None
    
    k = kls[idx]
    close = k["close"]
    
    # ① MA10持续朝上
    ma10_now = sum(kls[idx-9+i]["close"] for i in range(10)) / 10
    ma10_5ago = sum(kls[idx-14+i]["close"] for i in range(10)) / 10
    ma10_up = ma10_now > ma10_5ago
    
    # ② 近10日涨停过
    has_limit_up = False
    for j in range(1, 11):
        if idx - j < 0:
            break
        prev = kls[idx-j-1]["close"] if idx-j-1 >= 0 else kls[idx-j]["open"]
        d_gain = (kls[idx-j]["close"] - prev) / prev * 100 if prev > 0 else 0
        if d_gain >= 9.5:
            has_limit_up = True
            break
    
    # ③ 回踩买点（用系统B检测）
    bt = detect_buy_point(code, date_str, all_stocks, main_lines=None)
    has_huicai = bt and bt['buy_type'] in ('中继买点', '突破买点')
    
    # ④ 业绩好
    try:
        from profit_quality_check import check_profit_quality
        perf_res = check_profit_quality(resolved_code)
        has_perf = perf_res['pass']
    except ImportError:
        try:
            cache_path = '/home/ubuntu/data/3l/profit_quality_results.json'
            if os.path.exists(cache_path):
                cache = json.load(open(cache_path))
                has_perf = resolved_code in cache.get('passed_codes', [])
            else:
                has_perf = True
        except:
            has_perf = True
    
    conditions = {
        "ma10_up": ma10_up,
        "has_limit_up": has_limit_up,
        "has_huicai": has_huicai,
        "has_perf": has_perf,
    }
    score_val = sum(1 for v in conditions.values() if v)
    
    return {
        "match": score_val >= 4,
        "score": score_val,
        "total": 4,
        "conditions": conditions,
        "detail": {
            "ma10_now": round(ma10_now, 2),
            "ma10_5ago": round(ma10_5ago, 2),
            "limit_up": "有" if has_limit_up else "无",
            "has_perf": has_perf,
        },
        "model": "盈利模式1",
    }


def scan_profit_model1(date_str, all_stocks, only_watchlist=None):
    """批量扫描盈利模式1（保持接口兼容）"""
    results = []
    for sec_name, stocks in all_stocks.items():
        for code in stocks:
            if only_watchlist and code not in only_watchlist:
                continue
            name = stocks[code][0].get("name", code) if stocks[code] else code
            res = check_profit_model1(code, date_str, all_stocks)
            if res and res["match"]:
                results.append({"code": code, "name": name, "sector": sec_name, **res})
    return results

# ====== 数据获取（共享函数） ======

STOCKS_FILE = '/home/ubuntu/data/3l/all_stocks_60d.json'

def get_realtime_kline(code, direction):
    """从all_stocks_60d.json缓存读已有K线，再追加今日腾讯实时行情
    统一单位：缓存(mootdx)=股，腾讯实时(手→×100→股)
    返回 [{date, open, close, high, low, volume}, ...]
    """
    import requests
    from datetime import datetime

    klines = []
    if os.path.isfile(STOCKS_FILE):
        try:
            with open(STOCKS_FILE) as f:
                data = json.load(f)
            stocks = data.get('stocks', data) if isinstance(data, dict) else data
            sec_stocks = stocks.get(direction, {}) if isinstance(stocks, dict) else {}
            if code in sec_stocks:
                cached = sec_stocks[code]
                if isinstance(cached, list):
                    klines = list(cached)  # 复制，不修改原缓存
        except:
            pass

    qcode = code
    if not code.startswith(('sh', 'sz', 'SH', 'SZ')):
        qcode = ('sh' if code.startswith(('6', '9')) else 'sz') + code
    try:
        r = requests.get(f'https://qt.gtimg.cn/q={qcode}',
                         headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                         timeout=5)
        line = r.text
        try:
            line = line.decode('gbk')
        except:
            pass
        fields = line.split('"')[1].split('~') if '"' in line else []
        if len(fields) >= 40:
            today_str = datetime.now().strftime('%Y-%m-%d')
            # 腾讯fields[6]单位是手，缓存单位是股，×100统一
            today_vol = (int(fields[6]) if fields[6].isdigit() else 0) * 100
            if klines and str(klines[-1].get('date', '')).replace('-', '') == datetime.now().strftime('%Y%m%d'):
                klines[-1]['close'] = float(fields[3]) if fields[3] else klines[-1]['close']
                klines[-1]['high'] = max(float(fields[33]) if fields[33] else 0, klines[-1]['high'])
                klines[-1]['low'] = min(float(fields[34]) if fields[34] else float('inf'), klines[-1]['low'])
                klines[-1]['volume'] = today_vol or klines[-1]['volume']
            else:
                last_close = klines[-1]['close'] if klines else 0
                klines.append({
                    'date': today_str,
                    'open': float(fields[5]) if fields[5] else last_close,
                    'close': float(fields[3]) if fields[3] else last_close,
                    'high': float(fields[33]) if fields[33] else last_close,
                    'low': float(fields[34]) if fields[34] else last_close,
                    'volume': today_vol or 0,
                })
    except:
        pass

    return klines
