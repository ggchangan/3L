#!/usr/bin/env python3
"""
趋势股交易系统模块 v3.0（最终方案）

两大趋势系统 + 乖离率位置判断：
1. 5日趋势系统：EMA5斜率 > 2%
   用BIAS5判断位置：<0%买入 / 0~2%买入 / 2~8%持有 / 8~12%警戒 / >12%卖出（仅参考，不做止盈）

2. 10日趋势系统：上涨结构(EMA10极值法) + EMA10斜率 > 1.5%
   用BIAS10判断位置：<3%买入 / 3~10%持有 / 10~15%警戒 / >15%卖出（仅参考，不做止盈）

3. 止损：仅-5%浮亏兜底止损（无斜率止损）

4. 止盈：跟踪止盈（从买入后最高点回落10%卖出，至少赚5%才启动）
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from ema_utils import ema_list, get_structure


def ema_slope(values, n_days=5):
    """计算EMA斜率：最近N天变化百分比"""
    if len(values) < n_days + 1:
        return 0
    return (values[-1] - values[-n_days-1]) / values[-n_days-1] * 100


# ==================== 趋势判定 ====================

def is_5day_trend(klines, idx):
    """判定5日趋势：EMA5斜率(5日) > 2%"""
    if idx < 9 or len(klines) <= idx:
        return False
    closes = [k['close'] for k in klines[:idx+1]]
    ema5 = [v for v in ema_list(closes, 5) if v is not None]
    if len(ema5) < 6:
        return False
    slope = ema_slope(ema5, 5)
    return slope > 2.0


def is_10day_trend(klines, idx):
    """判定10日趋势：上涨结构(EMA10极值法) + EMA10斜率(5日) > 1.5%"""
    if idx < 29 or len(klines) <= idx:
        return False
    closes = [k['close'] for k in klines[:idx+1]]
    structure = get_structure(closes)
    if structure != '上涨趋势':
        return False
    ema10 = [v for v in ema_list(closes, 10) if v is not None]
    if len(ema10) < 6:
        return False
    slope = ema_slope(ema10, 5)
    return slope > 1.5


# ==================== 乖离率位置判断 ====================

def get_bias5_zone(klines, idx):
    """基于BIAS5判断位置区域 (买入/持有/警戒/卖出, bias5值)"""
    if idx < 4 or len(klines) <= idx:
        return ('--', 0)
    closes = [k['close'] for k in klines[:idx+1]]
    ema5 = ema_list(closes, 5)
    if ema5[-1] is None or ema5[-1] == 0:
        return ('--', 0)
    close = klines[idx]['close']
    bias5 = (close - ema5[-1]) / ema5[-1] * 100
    if bias5 < 0:
        return ('买入', round(bias5, 2))
    elif bias5 <= 2:
        return ('买入', round(bias5, 2))
    elif bias5 <= 8:
        return ('持有', round(bias5, 2))
    elif bias5 <= 12:
        return ('警戒', round(bias5, 2))
    else:
        return ('卖出', round(bias5, 2))


def get_bias10_zone(klines, idx):
    """基于BIAS10判断位置区域 (买入/持有/警戒/卖出, bias10值)"""
    if idx < 9 or len(klines) <= idx:
        return ('--', 0)
    closes = [k['close'] for k in klines[:idx+1]]
    ema10 = ema_list(closes, 10)
    if ema10[-1] is None or ema10[-1] == 0:
        return ('--', 0)
    close = klines[idx]['close']
    bias10 = (close - ema10[-1]) / ema10[-1] * 100
    if bias10 < 3:
        return ('买入', round(bias10, 2))
    elif bias10 <= 10:
        return ('持有', round(bias10, 2))
    elif bias10 <= 15:
        return ('警戒', round(bias10, 2))
    else:
        return ('卖出', round(bias10, 2))


# ==================== 止损 ====================

def check_stop_loss(buy_price, cur_price):
    """
    止损检查（最终方案：仅-5%浮亏兜底）
    返回: (是否触发, 说明)
    """
    if buy_price <= 0:
        return (False, '')
    cur_ret = (cur_price - buy_price) / buy_price * 100
    if cur_ret < -5:
        return (True, f'浮亏{cur_ret:.2f}%触发-5%止损')
    return (False, '')


# ==================== 止盈 ====================

def check_trailing_take_profit(buy_price, cur_price, peak_price):
    """
    跟踪止盈检查（最终方案）
    条件：从买入后最高点回落10%卖出，且至少赚5%才启动
    返回: (是否触发, 说明)
    """
    if buy_price <= 0 or peak_price <= 0:
        return (False, '')
    peak_ret = (peak_price - buy_price) / buy_price * 100
    cur_ret = (cur_price - buy_price) / buy_price * 100
    if peak_ret > 5 and (peak_ret - cur_ret) > 10:
        return (True, f'跟踪止盈(峰值{peak_ret:.1f}%，回落至{cur_ret:.1f}%)')
    return (False, '')


# ==================== 综合接口 ====================

def check_trend_type(klines, idx):
    """
    综合判断趋势类型
    返回值: {
        'trend_type': '5日趋势' / '10日趋势' / '双趋势' / None,
        'trend_5d': bool,
        'trend_10d': bool,
        'bias5_zone': '买入'/'持有'/'警戒'/'卖出',
        'bias10_zone': '买入'/'持有'/'警戒'/'卖出',
        'bias5': float,
        'bias10': float,
        'ema5_slope': float,
        'ema10_slope': float,
    }
    """
    if idx < 29 or len(klines) <= idx:
        return {'trend_type': None, 'trend_5d': False, 'trend_10d': False}
    
    closes = [k['close'] for k in klines[:idx+1]]
    ema5_vals = [v for v in ema_list(closes, 5) if v is not None]
    ema10_vals = [v for v in ema_list(closes, 10) if v is not None]
    
    t5 = is_5day_trend(klines, idx)
    t10 = is_10day_trend(klines, idx)
    
    b5z, b5 = get_bias5_zone(klines, idx)
    b10z, b10 = get_bias10_zone(klines, idx)
    
    if t5 and t10:
        trend_type = '双趋势'
    elif t5:
        trend_type = '5日趋势'
    elif t10:
        trend_type = '10日趋势'
    else:
        trend_type = None
    
    e5_slope = ema_slope(ema5_vals, 5) if len(ema5_vals) >= 6 else 0
    e10_slope = ema_slope(ema10_vals, 5) if len(ema10_vals) >= 6 else 0
    
    return {
        'trend_type': trend_type,
        'trend_5d': t5,
        'trend_10d': t10,
        'bias5_zone': b5z,
        'bias5': b5,
        'bias10_zone': b10z,
        'bias10': b10,
        'ema5_slope': round(e5_slope, 2),
        'ema10_slope': round(e10_slope, 2),
    }
    
    
# ==================== 平滑趋势检测（3L失效场景） ====================

def is_smooth_trend(code, date_str, data):
    """
    判断股票是否属于"沿EMA5走"的平滑趋势（3L失效场景）
    
    当3L的突破买点/中继买点都抓不住信号时，
    趋势交易的乖离率买入(B5<2%)可以作为补充。
    
    条件（全部满足）：
    1. 结构=上涨趋势
    2. 最近15天BIAS5无严格峰谷循环
    3. BIAS5范围 < 10%
    4. 持有区(2~6%)占比 > 40%
    5. 警戒区(>6%)占比 < 20%
    
    返回: {'is_smooth': bool, 'details': dict}
    """
    # 找到数据
    for sec, stocks in data.items():
        klines = None
        if code in stocks:
            klines = stocks[code]
        else:
            raw = code[-6:] if len(code) >= 6 else code
            if raw in stocks:
                klines = stocks[raw]
        if klines:
            break
    else:
        return {'is_smooth': False, 'details': {'reason': '找不到股票'}}
    
    if not klines or len(klines) < 30:
        return {'is_smooth': False, 'details': {'reason': f'数据不足{len(klines) if klines else 0}'}}
    
    n = len(klines)
    closes = [k['close'] for k in klines]
    ema5 = ema_list(closes, 5)
    
    # 第1条件：结构=上涨趋势
    structure = get_structure(closes)
    if structure != '上涨趋势':
        return {'is_smooth': False, 'details': {'reason': f'结构={structure}', 'structure': structure}}
    
    # 最近15天BIAS5分析
    l15 = list(range(max(0, n-15), n))
    bias5_l15 = []
    for i in l15:
        if ema5[i] and ema5[i] > 0:
            b5 = (closes[i] - ema5[i]) / ema5[i] * 100
        else:
            b5 = 0
        bias5_l15.append(round(b5, 2))
    
    # 去重
    dedup = []
    for b in bias5_l15:
        if not dedup or abs(b - dedup[-1]) > 0.001:
            dedup.append(b)
    bias5_seq = dedup
    
    # 第2条件：无严格峰谷循环
    in_sell = False
    cycles = 0
    for b in bias5_seq:
        if in_sell and b < 2:
            cycles += 1
            in_sell = False
        elif not in_sell and b >= 6:
            in_sell = True
    
    # 第3条件：BIAS5范围 < 10%
    b_min = min(bias5_seq)
    b_max = max(bias5_seq)
    b_range = b_max - b_min
    
    # 第4条件：持有区(2~6%)占比
    hold_count = sum(1 for b in bias5_seq if 2 <= b <= 6)
    hold_ratio = hold_count / len(bias5_seq) if bias5_seq else 0
    
    # 第5条件：警戒区(>6%)占比
    warn_count = sum(1 for b in bias5_seq if b > 6)
    warn_ratio = warn_count / len(bias5_seq) if bias5_seq else 0
    
    # 综合判定
    is_smooth = (cycles == 0 and b_range < 10 and hold_ratio > 0.4 and warn_ratio < 0.2)
    
    details = {
        'structure': structure,
        'cycles': cycles,
        'b_range': round(b_range, 1),
        'hold_ratio': round(hold_ratio, 2),
        'warn_ratio': round(warn_ratio, 2),
        'bias5_min': round(b_min, 2),
        'bias5_max': round(b_max, 2),
    }
    
    return {'is_smooth': is_smooth, 'details': details}


# ==================== 手动指定趋势交易 ====================

from backend import config
MANUAL_TREND_PATH = config.MANUAL_TREND_PATH
_manual_trend_cache = None

def _load_manual_trend():
    """加载手动指定的趋势交易股票列表"""
    try:
        with open(MANUAL_TREND_PATH) as f:
            return set(json.load(f))
    except:
        return set()


def decide_system(code, date_str, data, main_lines=None):
    """
    判断该股票应用趋势交易还是3L交易
    
    逻辑：
    - 在 manual_trend_stocks.json 手动列表中的 → 趋势交易
    - 不在列表中的 → 3L
    
    返回: 'trend' | '3l'
    """
    manual_trend = _load_manual_trend()
    if code in manual_trend:
        return 'trend'
    return '3l'


def decide_system_with_detail(code, date_str, data, main_lines=None):
    """
    判断该股票应用趋势交易还是3L交易（含详细原因）
    
    逻辑：
    - 在 manual_trend_stocks.json 手动列表中的 → 趋势交易
    - 不在列表中的 → 3L（无论结构/斜率/主线）
    
    返回: {'system': 'trend'|'3l', 'reason': str, 'details': dict}
    """
    # 查找股票信息（用于details展示）
    direction = ''
    for sec, stocks in data.items():
        if code in stocks:
            direction = sec
            break
        raw = code[-6:] if len(code) >= 6 else code
        if raw in stocks:
            direction = sec
            break
    
    details = {'direction': direction}
    
    manual_trend = _load_manual_trend()
    if code in manual_trend:
        return {'system': 'trend', 'reason': '手动指定为趋势交易', 'details': {**details, 'manual': True}}
    
    return {'system': '3l', 'reason': '默认3L交易', 'details': {**details, 'manual': False}}


# ==================== 趋势买点检测 ====================

def detect_trend_buy(code, date_str, data, main_lines=None):
    """
    检测趋势股的乖离率买点
    
    返回: {
        'has_buy': bool,
        'buy_type': 'BIAS5乖离率买入' | 'BIAS10乖离率买入' | None,
        'bias5': float,
        'bias10': float,
        'bias5_zone': str,
        'bias10_zone': str,
        'price': float,
        'reason': str,
    } or None
    """
    # 先判断是否该用趋势交易
    sys_result = decide_system_with_detail(code, date_str, data, main_lines)
    if sys_result['system'] != 'trend':
        return None
    
    # 找到数据
    for sec, stocks in data.items():
        klines = None
        if code in stocks:
            klines = stocks[code]
        else:
            raw = code[-6:] if len(code) >= 6 else code
            if raw in stocks:
                klines = stocks[raw]
        if klines:
            break
    
    if not klines:
        return None
    
    date_clean = date_str.replace('-', '')
    idx = -1
    for i, k in enumerate(klines):
        if str(k.get('date', '')).replace('-', '') == date_clean:
            idx = i
            break
    if idx < 30:
        return None
    
    t = check_trend_type(klines, idx)
    if t['trend_type'] is None:
        return None
    
    # 5日趋势用BIAS5，10日趋势用BIAS10，双趋势用BIAS5优先
    if t['trend_5d']:
        zone5 = get_bias5_zone(klines, idx)
        if zone5[0] == '买入':
            return {
                'has_buy': True,
                'buy_type': 'BIAS5乖离率买入',
                'bias5': zone5[1],
                'bias10': t['bias10'],
                'bias5_zone': zone5[0],
                'bias10_zone': t['bias10_zone'],
                'price': klines[idx]['close'],
                'reason': f'BIAS5={zone5[1]:.2f}%，处于买入区，属于{t["trend_type"]}',
                'trend_type': t['trend_type'],
                'system_reason': sys_result['reason'],
            }
    
    if t['trend_10d']:
        zone10 = get_bias10_zone(klines, idx)
        if zone10[0] == '买入':
            return {
                'has_buy': True,
                'buy_type': 'BIAS10乖离率买入',
                'bias5': t['bias5'],
                'bias10': zone10[1],
                'bias5_zone': t['bias5_zone'],
                'bias10_zone': zone10[0],
                'price': klines[idx]['close'],
                'reason': f'BIAS10={zone10[1]:.2f}%，处于买入区，属于{t["trend_type"]}',
                'trend_type': t['trend_type'],
                'system_reason': sys_result['reason'],
            }
    
    return None


# ==================== 单股回测 ====================

def simulate_trend_trade(klines, buy_idx):
    """
    模拟一次趋势交易
    买入价 = 当天close
    卖出逻辑：跟踪10%止盈 or -5%止损 or 趋势消失 or 满60天
    返回: {'ret': float, 'exit_reason': str, 'hold_days': int, 'peak_ret': float}
    """
    buy_price = klines[buy_idx]['close']
    peak_price = buy_price
    n = len(klines)
    
    for hold in range(1, min(61, n - buy_idx)):
        idx = buy_idx + hold
        cur = klines[idx]['close']
        
        if cur > peak_price:
            peak_price = cur
        
        # 止损检查
        sl, sl_reason = check_stop_loss(buy_price, cur)
        if sl:
            ret = (cur - buy_price) / buy_price * 100
            return {'ret': round(ret, 2), 'exit_reason': '止损', 'hold_days': hold, 'peak_ret': round((peak_price - buy_price) / buy_price * 100, 2)}
        
        # 止盈检查
        tp, tp_reason = check_trailing_take_profit(buy_price, cur, peak_price)
        if tp:
            ret = (cur - buy_price) / buy_price * 100
            return {'ret': round(ret, 2), 'exit_reason': '跟踪止盈', 'hold_days': hold, 'peak_ret': round((peak_price - buy_price) / buy_price * 100, 2)}
        
        # 趋势消失
        tr = check_trend_type(klines, idx)
        if tr['trend_type'] is None:
            ret = (cur - buy_price) / buy_price * 100
            return {'ret': round(ret, 2), 'exit_reason': '趋势消失', 'hold_days': hold, 'peak_ret': round((peak_price - buy_price) / buy_price * 100, 2)}
    
    # 持满60天
    last = min(buy_idx + 60, n - 1)
    ret = (klines[last]['close'] - buy_price) / buy_price * 100
    return {'ret': round(ret, 2), 'exit_reason': '持满60天', 'hold_days': 60, 'peak_ret': round((peak_price - buy_price) / buy_price * 100, 2)}


def scan_trend_buys(date_str, data, main_lines=None):
    """
    批量扫描所有股票的趋势买点
    返回: [{'code': str, 'name': str, 'direction': str, ...}, ...]
    """
    results = []
    for sec, stocks in data.items():
        for code, klines in stocks.items():
            if not klines or len(klines) < 30:
                continue
            try:
                bt = detect_trend_buy(code, date_str, {sec: {code: klines}}, main_lines)
                if bt and bt.get('has_buy'):
                    name = klines[0].get('name', code)
                    bt['code'] = code
                    bt['name'] = name
                    bt['direction'] = sec
                    results.append(bt)
            except Exception:
                continue
    return results


def check_trend_stock_v2(code, date_str, all_stocks):
    """公开接口：检查个股的趋势状态"""
    for sec, stocks in all_stocks.items():
        klines = None
        if code in stocks:
            klines = stocks[code]
        else:
            raw = code[-6:] if len(code) >= 6 else code
            if raw in stocks:
                klines = stocks[raw]
        if klines:
            break
    else:
        return None
    
    date_clean = date_str.replace('-', '')
    idx = -1
    for i, k in enumerate(klines):
        if str(k.get('date', '')).replace('-', '') == date_clean:
            idx = i
            break
    if idx < 30:
        return None
    
    result = check_trend_type(klines, idx)
    result['is_trend'] = result['trend_type'] is not None
    return result
