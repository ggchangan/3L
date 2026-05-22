#!/usr/bin/env python3
"""德明利(001309)3L回测 v2 — 多维评分突破 + 3%止损缓冲 + 买回机制"""
import json, sys, os
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)
for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from buy_point_detection import detect_buy_point, _find_support_levels, _breakout_score
from ema_utils import get_structure, get_stage, get_ema_arrangement

print("="*80)
print("德明利(001309) 3L回测 v2")
print(f"数据: {len(kls)}条K线  {kls[0]['date'][:4]}-{kls[0]['date'][4:6]}-{kls[0]['date'][6:8]} → {kls[-1]['date'][:4]}-{kls[-1]['date'][4:6]}-{kls[-1]['date'][6:8]}")
print("规则: 突破多维评分≥5 | 止损=关键点×0.97 | 盘中破即触发 | 拉回关键点+阳线可买回")
print("="*80)

# ── 找所有买点 ──
buy_signals = []
for i in range(30, len(kls)):
    date_str = str(kls[i]['date']).replace('-', '')
    date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    
    bt = detect_buy_point('001309', date_fmt, raw, market_position='波中', main_lines={'半导体'})
    if bt:
        prev_10d_high = max(kls[i-j]['high'] for j in range(1, 11)) if i >= 10 else None
        support = _find_support_levels(kls, i)
        
        buy_signals.append({
            'idx': i, 'date': date_fmt, 'type': bt['buy_type'],
            'close': bt['close'], 'vol_ratio': bt['vol_ratio'],
            'structure': bt['structure'], 'stage': bt['stage'],
            'prev_10d_high': round(prev_10d_high, 2) if prev_10d_high else None,
            'support': round(support, 2) if support else None,
            'breakout_score': bt.get('detail', {}).get('breakout_score', 0),
            'breakout_detail': bt.get('detail', {}).get('breakout_detail', {}),
        })

print(f"\n共 {len(buy_signals)} 个买点信号:\n")
for s in buy_signals:
    emoji = '📗' if s['type'] == '中继买点' else '📘'
    bs = f" 评分{s['breakout_score']}" if s['type'] == '突破买点' else ''
    print(f"  {emoji} {s['date']} | {s['type']}{bs} | 入场={s['close']} | 支撑={s['support']} 前10高={s['prev_10d_high']}")

# ── 退出检测函数 ──
def check_acceleration(kls, start_idx, current_idx):
    if current_idx - start_idx < 3:
        return False, ''
    bodies = []
    for j in range(current_idx - 2, current_idx + 1):
        if j >= len(kls): break
        o, c = kls[j]['open'], kls[j]['close']
        if c > o:
            bodies.append((c - o) / o * 100)
        else:
            return False, ''
    if len(bodies) < 3:
        return False, ''
    avg_body = sum(bodies) / 3
    if all(b > 0 for b in bodies) and avg_body > 3.0 and bodies[-1] >= bodies[0] * 1.1:
        return True, f"加速({round(bodies[0],1)}%→{round(bodies[-1],1)}%)"
    return False, ''

def check_volume_stagnation(kls, current_idx):
    if current_idx < 5:
        return False, ''
    vol = kls[current_idx].get('volume', kls[current_idx].get('vol', 0))
    if vol <= 0:
        return False, ''
    vols = [kls[current_idx-4+i].get('volume', kls[current_idx-4+i].get('vol', 0)) for i in range(5)]
    vma5 = sum(vols) / 5 if all(v > 0 for v in vols) else 1
    vr = vol / vma5
    if vr > 1.5:
        o, c = kls[current_idx]['open'], kls[current_idx]['close']
        body = abs(c - o)
        rng = kls[current_idx]['high'] - kls[current_idx]['low']
        if rng > 0 and body / rng < 0.3:
            return True, f"放量滞涨(量比{round(vr,1)})"
    return False, ''

def check_power_fading(kls, current_idx, entry_idx):
    if current_idx - entry_idx < 3:
        return False, ''
    recent_vols = [kls[max(0,current_idx-2)+j].get('volume', kls[max(0,current_idx-2)+j].get('vol', 0)) for j in range(3)]
    if all(v > 0 for v in recent_vols) and recent_vols[0] > 0:
        if recent_vols[1] < recent_vols[0] * 0.95 and recent_vols[2] < recent_vols[1] * 0.95:
            recent_highs = [kls[j]['high'] for j in range(max(0, current_idx-5), current_idx+1)]
            if len(recent_highs) >= 3 and recent_highs[-1] == max(recent_highs):
                return True, "动力减弱(价新高量递减)"
    return False, ''

def check_reverse(kls, current_idx, key_point):
    """右侧止盈：阴包阳(放量走/缩量观察) OR 大阴线反转"""
    if current_idx < 1:
        return False, ''
    k, kp = kls[current_idx], kls[current_idx-1]
    c, o, h, l = k['close'], k['open'], k['high'], k['low']
    cp_, op_ = kp['close'], kp['open']
    
    # 量比计算
    vol = k.get('volume', 0)
    prev_vols = [kls[current_idx-j-1].get('volume', 0) for j in range(1, 6)]
    avg_vol = sum(prev_vols) / len(prev_vols) if prev_vols else 0
    vol_ratio = vol / avg_vol if avg_vol > 0 else 0
    
    # 条件1：阴包阳（前阳+本阴+本收≤前开）
    if cp_ >= op_ and c < o and c <= op_:
        if vol_ratio < 0.8:
            # 缩量阴包阳 → 观察一天，不触发
            return False, f"缩量阴包阳(量{vol_ratio:.1f}x,观察)"
        else:
            # 放量或均量阴包阳 → 走
            return True, f"阴包阳(昨{op_:.0f}→{cp_:.0f},今{o:.0f}→{c:.0f},量{vol_ratio:.1f}x)"
    
    # 条件2：大阴线反转（实体≥前5日均值×1.5 + 收盘在低位30%）
    if c < o:
        body = o - c
        bodies = [abs(kls[j]['close']-kls[j]['open']) for j in range(max(0,current_idx-5),current_idx)]
        avg_b = sum(bodies)/len(bodies) if bodies else 0
        rng_ = h-l if h>l else 1
        if avg_b > 0 and body >= avg_b*1.5 and (c-l)/rng_ < 0.3:
            return True, f"大阴线反转(体{body:.0f}≥均{avg_b:.0f}×1.5)"
    return False, ''

STOP_BUFFER = 0.97   # 3%缓冲
MAX_DAYS = 60

print("\n" + "="*80)
print("二、逐信号跟踪")
print("="*80)

all_trades = []

for sig_idx, s in enumerate(buy_signals):
    i, entry_date = s['idx'], s['date']
    entry_price = s['close']
    buy_type = s['type']
    
    # 关键点
    if buy_type == '突破买点':
        key_point = s['prev_10d_high']
    else:
        key_point = s['support']
    
    if key_point is None:
        print(f"\n  [{entry_date}] ⚠ 无法确定关键点，跳过")
        continue
    
    stop_price = round(key_point * STOP_BUFFER, 2)
    
    print(f"\n  {'='*60}")
    print(f"  {sig_idx+1}. [{entry_date}] {buy_type} 入场={entry_price}")
    print(f"     关键点={key_point} → 止损位=跌破{stop_price}（{STOP_BUFFER}×关键点）")
    
    # 跟踪
    day_idx = i + 1
    stop_triggered = False
    stop_day = None
    stop_loss_price = None
    buy_back_price = None
    buy_back_day = None
    re_entry_idx = None  # 买回后的新起始索引
    
    max_gain_pct = 0
    max_loss_pct = 0
    exit_reason = None
    exit_day = None
    exit_price = None
    daily_log = []
    in_stop_observation = False
    
    while day_idx < min(i + MAX_DAYS + 1, len(kls)):
        k = kls[day_idx]
        hp, lp, cp, op = k['high'], k['low'], k['close'], k['open']
        
        if re_entry_idx is not None:
            # 买回后，相对买回价计算盈亏
            base_price = buy_back_price
        else:
            base_price = entry_price
        
        gain_pct = round((cp - base_price) / base_price * 100, 2)
        max_gain_pct = max(max_gain_pct, gain_pct)
        if not stop_triggered:
            max_loss_pct = min(max_loss_pct, gain_pct)
        
        day_date = str(k['date']).replace('-', '')
        day_fmt = f"{day_date[:4]}-{day_date[4:6]}-{day_date[6:8]}"
        log = f"    第{(day_idx-i)}天({day_fmt}): O={op} H={hp} L={lp} C={cp}"
        
        # === 止损检测（未触发且非观察期） ===
        if not stop_triggered and not in_stop_observation:
            if lp < stop_price:
                stop_triggered = True
                stop_day = day_idx
                # 止损亏损按触发价算
                stop_loss_price = min(cp, stop_price)
                stop_loss_pct = round((stop_loss_price - entry_price) / entry_price * 100, 2)
                log += f" ← ⚡止损触发(L{lp}<停{stop_price}) 亏{stop_loss_pct}%"
                in_stop_observation = True
                daily_log.append(log)
                day_idx += 1
                continue
        
        # === 买回检测（观察期中） ===
        if in_stop_observation:
            # 检查是否拉回关键点上方 + 阳线
            if cp > key_point and cp > op:
                buy_back_price = cp
                buy_back_day = day_idx
                in_stop_observation = False
                re_entry_idx = day_idx
                entry_date_new = day_fmt
                log += f" ← 🔄 买回！(C{cp}>关键点{key_point} 阳线) 价={buy_back_price}"
                daily_log.append(log)
                day_idx += 1
                continue
            
            # 检查是否触发了止盈（观察期也不错过止盈）
            accel, ar = check_acceleration(kls, i if re_entry_idx is None else re_entry_idx, day_idx)
            if accel:
                exit_reason = f"左侧止盈-{ar}(止损后)"
                exit_day = day_idx - i
                exit_price = cp
                daily_log.append(log + f" ← 🟢 {exit_reason}")
                break
            
            # 观察期继续
            daily_log.append(log + f" [观察中...]")
            day_idx += 1
            continue
        
        # === 正常跟踪中的退出检测 ===
        # 左侧止盈
        accel, ar = check_acceleration(kls, i if re_entry_idx is None else re_entry_idx, day_idx)
        if accel:
            exit_reason = f"左侧止盈-{ar}"
            exit_day = day_idx - i
            exit_price = cp
            daily_log.append(log + f" ← 🟢 {exit_reason}")
            break
        
        stag, sr = check_volume_stagnation(kls, day_idx)
        if stag:
            exit_reason = f"左侧止盈-{sr}"
            exit_day = day_idx - i
            exit_price = cp
            daily_log.append(log + f" ← 🟡 {exit_reason}")
            break
        
        fade, fr = check_power_fading(kls, day_idx, i if re_entry_idx is None else re_entry_idx)
        if fade:
            exit_reason = f"左侧止盈-{fr}"
            exit_day = day_idx - i
            exit_price = cp
            daily_log.append(log + f" ← 🟡 {exit_reason}")
            break
        
        # 右侧止盈
        rev, rr = check_reverse(kls, day_idx, key_point)
        if rev:
            exit_reason = f"右侧止盈-{rr}"
            exit_day = day_idx - i
            exit_price = cp
            daily_log.append(log + f" ← 🟡 {exit_reason}")
            break
        
        daily_log.append(log)
        day_idx += 1
    
    # 输出结果
    if exit_reason:
        for log in daily_log:
            print(log)
        print(f"     {'='*50}")
        emoji = '✅' if exit_price > base_price else '❌'
        # 如果有买回，显示两段
        if buy_back_price:
            buy_back_gain = round((buy_back_price - entry_price) / entry_price * 100, 2)
            trade_gain = round((exit_price - buy_back_price) / buy_back_price * 100, 2)
            total_gain = round((exit_price - entry_price) / entry_price * 100, 2)
            print(f"     结果: ⚡止损亏{stop_loss_pct:+.2f}% → 🔄买回价{buy_back_price} → {emoji} {exit_reason}")
            print(f"     买回后盈亏={trade_gain:+.2f}% | 合计={total_gain:+.2f}% | {exit_day}天")
            all_trades.append({'gain': total_gain, 'stop_loss': stop_loss_pct, 'bought_back': True})
        else:
            trade_gain = round((exit_price - entry_price) / entry_price * 100, 2)
            print(f"     结果: {emoji} {exit_reason} | 盈亏={trade_gain:+.2f}% | {exit_day}天")
            all_trades.append({'gain': trade_gain, 'stop_loss': stop_loss_pct if stop_triggered else None, 'bought_back': False})
    elif stop_triggered and not buy_back_price:
        # 触发了止损但没有买回
        for log in daily_log:
            print(log)
        print(f"     {'='*50}")
        print(f"     结果: ❌ 止损(未买回) | 亏{stop_loss_pct:+.2f}%")
        all_trades.append({'gain': stop_loss_pct, 'stop_loss': stop_loss_pct, 'bought_back': False})
    else:
        # 数据耗尽
        final_cp = kls[-1]['close']
        base = buy_back_price if buy_back_price else entry_price
        pnl = round((final_cp - base) / base * 100, 2)
        print(f"     ⏱ 数据范围结束")
        for log in daily_log:
            print(log)
        print(f"     {'='*50}")
        print(f"     结果: ⏱ 数据耗尽 | 持仓浮盈={pnl}%")
        all_trades.append({'gain': pnl, 'stop_loss': stop_loss_pct if stop_triggered else None, 'bought_back': bool(buy_back_price)})

# ── 汇总 ──
print("\n\n" + "="*80)
print("三、汇总")
print("="*80)
print(f"\n总信号: {len(all_trades)}")
wins = [t for t in all_trades if t['gain'] > 0]
losses = [t for t in all_trades if t['gain'] <= 0]
print(f"盈利: {len(wins)}次  亏损: {len(losses)}次")
if wins:
    print(f"平均盈利: {sum(t['gain'] for t in wins)/len(wins):+.2f}%")
if losses:
    print(f"平均亏损: {sum(t['gain'] for t in losses)/len(losses):+.2f}%")
if all_trades:
    print(f"总收益(等权): {sum(t['gain'] for t in all_trades)/len(all_trades):+.2f}%")

buybacks = [t for t in all_trades if t['bought_back']]
print(f"\n触发买回: {len(buybacks)}次")
for t in buybacks:
    print(f"  止损{t['stop_loss']:+.2f}% → 最终{t['gain']:+.2f}%")
