#!/usr/bin/env python3
"""根据K线数据计算每只持仓股的合理止损位"""
import json, os, sys
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, '..'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

DATA_DIR = os.environ['DATA_DIR']
from backend.services.holdings_service import get_holdings
holdings = get_holdings()['holdings']

from backend.core.buy_point_detection import get_realtime_kline

for h in holdings:
    code = h['code']
    name = h['name']
    curr_sl = h.get('stop_loss_price')
    curr_pct = h.get('stop_loss_pct')
    curr_price = h.get('price')
    struct = h.get('structure', '--')
    stage = h.get('stage', '--')
    
    # 获取K线
    try:
        klines = get_realtime_kline(code, h.get('direction', ''))
    except Exception as e:
        print(f'\n{name}({code}): K线获取失败 - {e}')
        continue
    
    if len(klines) < 30:
        print(f'\n{name}({code}): K线不足({len(klines)})')
        continue
    
    last = klines[-1]
    close = last['close']
    
    # 计算EMA20
    closes = [k['close'] for k in klines]
    ema20 = closes[0]
    k = 2/21
    for c in closes[1:]:
        ema20 = c * k + ema20 * (1 - k)
    
    # 找近20根K线最低点（关键支撑）
    recent_lows = [k['low'] for k in klines[-20:]]
    support = min(recent_lows)
    
    # 找近10根K线最低点（更近的支撑）
    recent_10_lows = [k['low'] for k in klines[-10:]]
    support_10 = min(recent_10_lows)
    
    # 根据结构推荐止损
    if struct == '上涨趋势':
        # 趋势股：EMA20×0.97 或 近20日最低×0.97
        sl_by_ema = round(ema20 * 0.97, 2)
        sl_by_support = round(support * 0.97, 2)
        suggested_sl = min(sl_by_ema, sl_by_support)  # 取较紧的
        suggested_pct = round((suggested_sl - close) / close * 100, 2)
        sl_source = f'EMA20={ema20:.2f}×0.97={sl_by_ema} / 支撑={support}×0.97={sl_by_support}'
    elif struct == '区间震荡':
        if stage == '区间顶部':
            # 顶部：用EMA20或支撑位，但收紧
            sl_by_ema = round(ema20 * 0.97, 2)
            sl_by_support = round(support_10 * 0.97, 2)  # 用更近的10日支撑
            suggested_sl = min(sl_by_ema, sl_by_support)
            suggested_pct = round((suggested_sl - close) / close * 100, 2)
            sl_source = f'EMA20={ema20:.2f}×0.97={sl_by_ema} / 近10日支撑={support_10}×0.97={sl_by_support}'
        elif stage == '区间底部':
            # 底部：用区间下沿×0.97，稍微宽一点
            sl_by_ema = round(ema20 * 0.97, 2)
            sl_by_support = round(support * 0.97, 2)
            suggested_sl = max(sl_by_ema, sl_by_support)  # 取较宽的
            suggested_pct = round((suggested_sl - close) / close * 100, 2)
            sl_source = f'EMA20={ema20:.2f}×0.97={sl_by_ema} / 20日支撑={support}×0.97={sl_by_support}'
        else:
            # 中段：用EMA20或20日支撑
            sl_by_ema = round(ema20 * 0.97, 2)
            sl_by_support = round(support * 0.97, 2)
            suggested_sl = min(sl_by_ema, sl_by_support)
            suggested_pct = round((suggested_sl - close) / close * 100, 2)
            sl_source = f'EMA20={ema20:.2f}×0.97={sl_by_ema} / 20日支撑={support}×0.97={sl_by_support}'
    elif struct == '下降趋势':
        # 下降趋势按较紧的止损
        sl_by_ema = round(ema20 * 0.97, 2)
        sl_by_support = round(support_10 * 0.97, 2)
        suggested_sl = min(sl_by_ema, sl_by_support)
        suggested_pct = round((suggested_sl - close) / close * 100, 2)
        sl_source = f'EMA20={ema20:.2f}×0.97={sl_by_ema} / 近10日支撑={support_10}×0.97={sl_by_support}'
    else:
        # 结构缺失：用EMA20或支撑位兜底
        sl_by_ema = round(ema20 * 0.97, 2) if ema20 else None
        if sl_by_ema:
            suggested_sl = sl_by_ema
            suggested_pct = round((suggested_sl - close) / close * 100, 2)
            sl_source = f'EMA20={ema20:.2f}×0.97'
        else:
            suggested_sl = round(close * 0.95, 2)
            suggested_pct = -5.0
            sl_source = '无数据，按现价-5%'
    
    # 判断是否需要调整
    need_adjust = False
    reason = ''
    if curr_sl is None:
        need_adjust = True
        reason = '无止损'
    elif curr_pct is not None and abs(curr_pct) > 12:
        need_adjust = True
        reason = f'止损过宽({curr_pct}%)'
    elif struct == '区间顶部' and curr_pct is not None and abs(curr_pct) > 8:
        need_adjust = True
        reason = f'区间顶部，建议收紧'
    elif struct == '下降趋势' and curr_pct is not None and abs(curr_pct) > 5:
        need_adjust = True
        reason = f'下降趋势，止损需收紧'
    
    print(f'\n{"="*60}')
    print(f'{name}({code})')
    print(f'  当前价: {close:.2f}  结构: {struct}/{stage}')
    print(f'  当前止损: {curr_sl} ({curr_pct}%)')
    print(f'  建议止损: {suggested_sl} ({suggested_pct}%)')
    print(f'  计算依据: {sl_source}')
    if need_adjust:
        print(f'  🔴 需要调整: {reason}')
    else:
        print(f'  ✅ 合理范围')
