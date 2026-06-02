#!/usr/bin/env python3
"""3L放量滞涨—按原文重新实现+回测

原文(量价原理5.6节):
"成交量放大，但是股价已经不再上涨。放量滞涨...
  供需双方在一个狭窄的价格区间内产生大量换手"
条件: 放量 + 价不涨 + 窄幅 + 上涨趋势中
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')
DATA_DIR = os.environ['DATA_DIR']
from threel_core.ema_utils import ema_list, _reg_slope, get_structure

def load_stocks():
    with open(os.path.join(DATA_DIR, 'all_stocks_60d.json')) as f:
        data = json.load(f)
    stocks = data.get('stocks', data)
    result = []
    for sector, codes in stocks.items():
        for code, klines in codes.items():
            name = klines[0].get('name', '') if klines else ''
            result.append((code, name, klines))
    return result

stocks = load_stocks()
print(f'{len(stocks)} 只股票')

# ── 1. 旧的滞涨 vs 新的放量滞涨 ──
def old_stagnation(closes, volumes):
    """旧: 斜率低 + 量不萎缩"""
    if len(closes) < 15:
        return False
    e10 = ema_list(closes, 10)
    e10_last = [v for v in e10[-15:] if v is not None]
    if len(e10_last) < 5: return False
    s1 = _reg_slope(e10_last)
    s2 = _reg_slope(e10_last[-3:]) if len(e10_last) >= 3 else 0
    if not (s1 > 0 and s2 > 0): return False
    ratio = s2 / s1 if abs(s1) > 1e-8 else 1.0
    if ratio >= 0.4: return False
    # 检查量：不满足缩量整理 → 滞涨
    if volumes and len(volumes) >= 13 and closes[-1] > e10_last[-1]:
        v3 = sum(volumes[-3:]) / 3
        v10 = sum(volumes[-13:-3]) / 10
        if v10 > 0 and v3 / v10 < 0.8:
            return False  # 缩量整理，不是滞涨
    return True

def new_stagnation_3l(closes, volumes, opens_p, highs, lows,
                       vol_ratio_min=1.3, body_max=0.015, amp_max=0.03):
    """新(按原文): 放量滞涨
    条件:
    1. 上涨趋势中（外部判断）
    2. 放量: 近3日均量 / 前10日均量 > vol_ratio_min
    3. 价不涨: 实体占比小(收盘-开盘)/收盘 < body_max
    4. 窄幅: (最高-最低)/收盘 < amp_max
    5. (可选) 出现在加速后
    """
    if not closes or len(closes) < 13:
        return False
    
    cur = closes[-1]
    op = opens_p[-1] if opens_p else cur
    hi = highs[-1] if highs else cur
    lo = lows[-1] if lows else cur
    
    # 2. 放量 - 成交量放大
    v3 = sum(volumes[-3:]) / 3 if len(volumes) >= 3 else 0
    v10 = sum(volumes[-13:-3]) / 10 if len(volumes) >= 13 else 0
    if v10 <= 0 or v3 / v10 < vol_ratio_min:
        return False
    
    # 3. 价不涨 - 实体小
    body_pct = abs(cur - op) / op
    if body_pct > body_max:
        return False
    
    # 4. 窄幅 - 全天振幅小
    amp = (hi - lo) / lo
    if amp > amp_max:
        return False
    
    return True


# ── 2. 回测对比 ──
print(f'\n{"="*70}')
print(f'旧滞涨 vs 新放量滞涨 — 回测对比')
print(f'上涨趋势中, 预测5日收益')
print(f'{"="*70}')

for label, is_stag_fn, params in [
    ('旧滞涨(斜率<0.4+量不萎缩)', 
     lambda c,v,o,h,l: old_stagnation(c, v), {}),
    ('新放量滞涨(量>1.3x+实体<1.5%+振幅<3%)', 
     lambda c,v,o,h,l: new_stagnation_3l(c,v,o,h,l,1.3,0.015,0.03), {}),
    ('新放量滞涨(量>1.5x+实体<1%+振幅<2.5%)',
     lambda c,v,o,h,l: new_stagnation_3l(c,v,o,h,l,1.5,0.01,0.025), {}),
    ('新放量滞涨(量>1.2x+实体<2%+振幅<3.5%)',
     lambda c,v,o,h,l: new_stagnation_3l(c,v,o,h,l,1.2,0.02,0.035), {}),
]:
    stag_bad = 0; stag_total = 0; stag_returns = []
    all_bad = 0; all_total = 0
    
    for code, name, klines in stocks:
        if len(klines) < 35:
            continue
        closes = [k['close'] for k in klines]
        volumes = [k['volume'] for k in klines]
        opens_p = [k['open'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]
        
        for i in range(25, len(klines) - 5):
            wc = closes[:i+1]
            struct = get_structure(wc)
            if struct != '上涨趋势':
                continue
            
            all_total += 1
            fwd_ret = (closes[i+5] - closes[i]) / closes[i] * 100
            if fwd_ret < 0:
                all_bad += 1
            
            if not is_stag_fn(wc, volumes[:i+1], opens_p[:i+1], highs[:i+1], lows[:i+1]):
                continue
            
            stag_total += 1
            stag_returns.append(fwd_ret)
            if fwd_ret < 0:
                stag_bad += 1
    
    all_loss = all_bad / all_total * 100 if all_total > 0 else 0
    stag_loss = stag_bad / stag_total * 100 if stag_total > 0 else 0
    avg_ret = sum(stag_returns) / len(stag_returns) if stag_returns else 0
    
    print(f'\n{label}')
    print(f'  总样本: {all_total}次上涨趋势, 5日走弱率{all_loss:.1f}%')
    print(f'  滞涨样本: {stag_total}次({stag_total/all_total*100:.1f}%), '
          f'5日走弱率{stag_loss:.1f}%({stag_bad}/{stag_total}), '
          f'均收益{avg_ret:+.2f}%')
    uplift = stag_loss - all_loss
    print(f'  提升: {uplift:+.1f}% (走弱率提升)')

# ── 3. 参数扫描 ──
print(f'\n{"="*70}')
print(f'参数扫描 — 放量滞涨各条件')
print(f'{"="*70}')

for vol_min in [1.1, 1.2, 1.3, 1.5, 1.8]:
    for body_max in [0.005, 0.01, 0.015, 0.02, 0.03]:
        for amp_max in [0.015, 0.02, 0.03, 0.04]:
            stag_bad = 0; stag_total = 0; stag_ret = []
            
            for code, name, klines in stocks:
                if len(klines) < 35: continue
                closes = [k['close'] for k in klines]
                volumes = [k['volume'] for k in klines]
                opens_p = [k['open'] for k in klines]
                highs = [k['high'] for k in klines]
                lows = [k['low'] for k in klines]
                
                for i in range(25, len(klines) - 5):
                    wc = closes[:i+1]
                    struct = get_structure(wc)
                    if struct != '上涨趋势': continue
                    if not new_stagnation_3l(wc, volumes[:i+1], opens_p[:i+1], highs[:i+1], lows[:i+1],
                                             vol_min, body_max, amp_max):
                        continue
                    stag_total += 1
                    fwd = (closes[i+5] - closes[i]) / closes[i] * 100
                    stag_ret.append(fwd)
                    if fwd < 0: stag_bad += 1
            
            if stag_total >= 10:
                loss = stag_bad / stag_total * 100
                avg = sum(stag_ret) / len(stag_ret)
                print(f'  量>{vol_min}x 实体<{body_max*100:.1f}% 振幅<{amp_max*100:.1f}%: '
                      f'走弱{loss:.1f}%({stag_bad}/{stag_total}) 均收益{avg:+.2f}%')
