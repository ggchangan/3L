#!/usr/bin/env python3
"""生成德明利完整交易记录图——红色买点+绿色卖点，一笔一笔标清"""
import json, sys, os, subprocess
sys.path.insert(0, '/home/ubuntu/3l-server')
sys.path.insert(0, '/home/ubuntu/3l-server/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)
for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from scripts.buy_point_detection import detect_buy_point, _find_support_levels

def _ema(data, period):
    r = [None]*len(data); m = 2/(period+1)
    for i in range(len(data)):
        if i==0: r[i]=data[i]
        elif r[i-1] is not None: r[i]=(data[i]-r[i-1])*m+r[i-1]
    return r

def find_keypoints(data):
    closes=[k['close'] for k in data]; highs=[k['high'] for k in data]
    lows=[k['low'] for k in data]; opens=[k['open'] for k in data]
    volumes=[k['volume'] for k in data]; n=len(data); kps=[]
    for i in range(5,n):
        if highs[i]==max(highs[max(0,i-10):i+1]): kps.append({'idx':i,'type':1,'label':'高','y':highs[i]})
        if lows[i]==min(lows[max(0,i-10):i+1]): kps.append({'idx':i,'type':1,'label':'低','y':lows[i]})
    return kps

# ── 动态获取买点（新规则6个信号） ──
buy_signals = []
for i in range(30, len(kls)):
    ds = str(kls[i]['date']).replace('-',''); df = f"{ds[:4]}-{ds[4:6]}-{ds[6:8]}"
    bt = detect_buy_point('001309', df, raw, market_position='波中', main_lines={'半导体'})
    if bt:
        support = _find_support_levels(kls, i)
        p10 = max(kls[i-j]['high'] for j in range(1,11)) if i>=10 else None
        buy_signals.append({
            'idx':i, 'date':df, 'type':bt['buy_type'], 'price':bt['close'],
            'key_point': round(support,2) if support else (round(p10,2) if p10 else 0),
        })

# ── 交易事件（新规则6笔交易） ──
# 格式: (buy_signal_index, buy_date, buy_price, [(event_type, date_str, price, label)])
trades_data = [
    (0, '04-10', 447.24, [('sell', '04-15', 501.20, '动力弱')]),
    (1, '04-21', 514.60, [('stop', '04-23', 494.69, '止损'), ('buyback', '04-24', 510.0, '买回'), ('sell', '04-27', 520.0, '加速')]),
    (2, '04-27', 488.15, [('sell', '05-06', 577.29, '突破')]),
    (3, '05-06', 577.29, [('sell', '05-08', 597.71, '阴包阳')]),
    (4, '05-13', 679.80, [('sell', '05-19', 699.16, '阴包阳')]),
    (5, '05-20', 695.96, [('stop', '05-21', 656.10, '止损')]),
]

# ── 找idx ──
date_to_idx = {}
for i, k in enumerate(kls):
    ds = str(k['date']).replace('-','')
    date_to_idx[ds[4:6]+'-'+ds[6:8]] = i

# ── SVG生成 ──
W,H = 1300, 750
pl,pr,pt,pb = 65,35,40,85
closes=[k['close'] for k in kls]; highs=[k['high'] for k in kls]
lows=[k['low'] for k in kls]; opens=[k['open'] for k in kls]
volumes=[k['volume'] for k in kls]
mx,mn = max(highs),min(lows); rg=mx-mn if mx!=mn else 1
n=len(kls); cw=(W-pl-pr)/n; bv=H-pb
px=lambda i: pl+i*cw+cw/2; py=lambda v: pt+(mx-v)/rg*(H-pt-pb)
ema5=_ema(closes,5); ema10=_ema(closes,10); ema20=_ema(closes,20)
vm=max(volumes) if max(volumes)>0 else 1

sv=[]
sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
sv.append(f'<text x="{W/2}" y="20" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#ffffff" font-weight="bold">德明利(001309) 3L回测 — 6笔交易全景</text>')
sv.append(f'<text x="{W/2}" y="33" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#888888">🔴买入 🟢卖出/止盈 🔵止损 🟡买回</text>')

for i in range(6):
    yv=mx-i*rg/5; yp=py(yv)
    sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
    sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#666666">{yv:.1f}</text>')
sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')

# ── 成交量 ──
for i in range(n):
    x=px(i)-cw*0.35; w=max(cw*0.55,1); vh=volumes[i]/vm*45
    is_up=closes[i]>=opens[i]; vc='#ff4444' if is_up else '#44aa44'
    sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh,0.5)}" fill="{vc}" opacity="0.25"/>')

# ── 均线 ──
for ev,clr,lab in [(ema5,'#ffd700','EMA5'),(ema10,'#ff6b6b','EMA10'),(ema20,'#4ecdc4','EMA20')]:
    pts=[]; [pts.append(f'{px(i)},{py(ev[i])}') for i in range(n) if ev[i] is not None]
    sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="1" opacity="0.7"/>')

# ── K线 ──
for i in range(15,n):
    x=px(i)-cw*0.28; w=cw*0.4; o,c,h,l = opens[i],closes[i],highs[i],lows[i]
    is_up=c>=o; kc='#ff4444' if is_up else '#44aa44'
    bt,bb=py(max(o,c)),py(min(o,c))
    sv.append(f'<rect x="{x}" y="{bt}" width="{w}" height="{max(bb-bt,1)}" fill="{kc}" opacity="0.8" rx="1"/>')
    sv.append(f'<line x1="{px(i)}" y1="{py(h)}" x2="{px(i)}" y2="{py(l)}" stroke="{kc}" stroke-width="1" opacity="0.8"/>')

# ── 关键点 ──
kps=find_keypoints(kls)
for kp in kps:
    if kp['idx']<n-50: continue
    xp=px(kp['idx']); yp=py(kp['y'])
    c1='#ff9800'
    sv.append(f'<rect x="{xp-4}" y="{yp-4}" width="8" height="8" fill="{c1}" opacity="0.6" rx="1"/>')
    sv.append(f'<text x="{xp}" y="{yp-6}" text-anchor="middle" font-family="sans-serif" font-size="7" fill="{c1}" opacity="0.7">{kp["label"]}</text>')

# ── 日期标签 ──
for i in range(0,n,5):
    ds=str(kls[i]['date']).replace('-',''); lab=f'{ds[4:6]}/{ds[6:8]}'
    sv.append(f'<text x="{px(i)}" y="{bv+32}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#555555" transform="rotate(-40,{px(i)},{bv+32})">{lab}</text>')

# ── 交易标注：买点(红) + 卖点(绿) + 止损(蓝) + 买回(橙) ──
all_marks = []

for t_idx, (bs_idx, bd, bp, events) in enumerate(trades_data):
    num = t_idx + 1
    bi = buy_signals[bs_idx]['idx']
    
    # 买点 → 红色
    xb = px(bi); yb = py(bp)
    bt_label = f"B{num} {bd} {bp:.0f}"
    all_marks.append((bi, '#e53935', bt_label, bp, 1, num))

    for etype, edate_str, eprice, elabel in events:
        if edate_str not in date_to_idx:
            continue
        ei = date_to_idx[edate_str]
        if etype == 'sell':
            clr = '#4caf50'
            label = f"S{num} {edate_str} ({elabel})"
            type_order = 2
        elif etype == 'stop':
            clr = '#2196f3'
            label = f"Stop{num} {edate_str}"
            type_order = 3
        elif etype == 'buyback':
            clr = '#ff9800'
            label = f"买回{num} {edate_str}"
            type_order = 4
        else:
            continue
        all_marks.append((ei, clr, label, eprice, type_order, num))

all_marks.sort(key=lambda x: (x[0], x[4]))

slot_used = {}
for mark in all_marks:
    idx = mark[0]
    slot = slot_used.get(idx, 0)
    slot_used[idx] = slot + 1
    
    xb = px(idx); yb = py(mark[3])
    clr = mark[1]; label = mark[2]
    
    y_slot = pt + 8 + slot * 14
    sv.append(f'<line x1="{xb}" y1="{yb}" x2="{xb}" y2="{y_slot+10}" stroke="{clr}" stroke-width="0.6" stroke-dasharray="3,3" opacity="0.5"/>')
    sv.append(f'<circle cx="{xb}" cy="{yb}" r="4" fill="{clr}" opacity="0.9" stroke="#fff" stroke-width="1"/>')
    tw = len(label)*7+12
    sv.append(f'<rect x="{xb-tw/2}" y="{y_slot}" width="{tw}" height="14" rx="3" fill="{clr}" opacity="0.85"/>')
    sv.append(f'<text x="{xb}" y="{y_slot+10}" text-anchor="middle" font-family="sans-serif" font-size="7.5" fill="white" font-weight="bold">{label}</text>')

# ── 图例 ──
lx=pl; ly2=bv+42
legends = [
    ('#e53935','买入'), ('#4caf50','卖出/止盈'), ('#2196f3','止损'),
    ('#ff9800','买回'), ('#ffd700','EMA5'), ('#ff6b6b','EMA10'),
    ('#4ecdc4','EMA20'), ('#ff9800','关键点'),
]
for i,(clr,lbl) in enumerate(legends):
    xl=lx+i*130
    sv.append(f'<rect x="{xl}" y="{ly2}" width="9" height="9" fill="{clr}" opacity="0.85" rx="1"/>')
    sv.append(f'<text x="{xl+12}" y="{ly2+8}" font-family="sans-serif" font-size="9" fill="#888888">{lbl}</text>')

sv.append('</svg>')

OUT = '/home/ubuntu/3l-server/review_charts/德明利_交易记录.svg'
with open(OUT, 'w') as f: f.write('\n'.join(sv))
png_out = OUT.replace('.svg', '.png')
subprocess.run(['rsvg-convert', '-w', '1600', '-f', 'png', OUT, '-o', png_out], check=True)
print(f"已生成: {png_out}")
print(f"已生成: {OUT}")
