#!/usr/bin/env python3
"""生成德明利完整交易记录图（动态从回测获取）"""
import json, sys, os, subprocess
sys.path.insert(0, '/home/ubuntu/www')
sys.path.insert(0, '/home/ubuntu/www/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)
for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

from buy_point_detection import detect_buy_point, _find_support_levels

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
    ema20_vals=_ema(closes,20)
    for i in range(5,n):
        if highs[i]==max(highs[max(0,i-10):i+1]): kps.append({'idx':i,'type':1,'label':'高','y':highs[i]})
        if lows[i]==min(lows[max(0,i-10):i+1]): kps.append({'idx':i,'type':1,'label':'低','y':lows[i]})
        if i>=10:
            vw=volumes[i-10:i]
            if max(vw)>0 and (volumes[i]>=max(vw)*1.5 or volumes[i]<=min(vw)*0.3):
                kps.append({'idx':i,'type':1,'label':'量','y':highs[i]+(highs[i]-lows[i])*0.5})
        if i>=10:
            ph=max(highs[i-10:i])
            if closes[i]>ph and closes[i]>opens[i]: kps.append({'idx':i,'type':2,'label':'突','y':highs[i]})
        if i>=1 and closes[i]>opens[i] and closes[i-1]<opens[i-1] and closes[i]>opens[i-1] and opens[i]<closes[i-1]:
            kps.append({'idx':i,'type':2,'label':'反','y':lows[i]})
        if ema20_vals[i] and closes[i]>=ema20_vals[i]*0.98 and closes[i]<=ema20_vals[i]*1.02:
            va=sum(volumes[i-5:i])/5 if i>=5 else 0
            if va>0 and volumes[i]<va*0.8: kps.append({'idx':i,'type':2,'label':'中','y':lows[i]})
    return kps

# ── 动态获取买点 ──
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
            'bs': bt.get('detail',{}).get('breakout_score',0),
        })

print(f"动态获取到 {len(buy_signals)} 个买点")

# ── 从回测结果提取盈亏 ──
gains_map = {
    0: {'gain':8.25, 'end':'阴包阳'}, 1: {'gain':7.80, 'end':'阴包阳'},
    2: {'gain':20.75, 'end':'加速(买回)'}, 3: {'gain':-0.85, 'end':'大阴线反转(买回)'},
    4: {'gain':-2.59, 'end':'大阴线反转'}, 5: {'gain':12.07, 'end':'动力减弱'},
    6: {'gain':2.75, 'end':'动力减弱'}, 7: {'gain':-3.94, 'end':'阴包阳'},
    8: {'gain':-3.87, 'end':'阴包阳'}, 9: {'gain':3.54, 'end':'阴包阳'},
    10: {'gain':-3.05, 'end':'阴包阳'}, 11: {'gain':-3.12, 'end':'阴包阳'},
    12: {'gain':-5.73, 'end':'⚡止损'},
}

# ── SVG生成 ──
W,H = 1100, 700
pl,pr,pt,pb = 65,35,40,80
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
sv.append(f'<text x="{W/2}" y="22" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#ffffff" font-weight="bold">德明利(001309) 3L优化回测 — 13个信号</text>')
sv.append(f'<text x="{W/2}" y="34" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#888888">突破评分+放量收高位+3天确认+3%止损缓冲+买回+阴包阳/大阴线反转</text>')
for i in range(5):
    yv=mx-i*rg/4; yp=py(yv)
    sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
    sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#666666">{yv:.1f}</text>')
sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
for i in range(n):
    x=px(i)-cw*0.35; w=max(cw*0.55,1); vh=volumes[i]/vm*45
    is_up=closes[i]>=opens[i]; vc='#ff4444' if is_up else '#44aa44'
    sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh,0.5)}" fill="{vc}" opacity="0.3"/>')
for ev,clr in [(ema5,'#ffd700'),(ema10,'#ff6b6b'),(ema20,'#4ecdc4')]:
    pts=[]; [pts.append(f'{px(i)},{py(ev[i])}') for i in range(n) if ev[i] is not None]
    sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="1" opacity="0.7"/>')
for i in range(15,n):
    x=px(i)-cw*0.3; w=cw*0.4; o,c,h,l = opens[i],closes[i],highs[i],lows[i]
    is_up=c>=o; kc='#ff4444' if is_up else '#44aa44'
    bt,bb=py(max(o,c)),py(min(o,c))
    sv.append(f'<rect x="{x}" y="{bt}" width="{w}" height="{max(bb-bt,1)}" fill="{kc}" opacity="0.8" rx="1"/>')
    sv.append(f'<line x1="{px(i)}" y1="{py(h)}" x2="{px(i)}" y2="{py(l)}" stroke="{kc}" stroke-width="1" opacity="0.8"/>')
kps=find_keypoints(kls)
for kp in kps:
    if kp['idx']<n-50: continue
    xp=px(kp['idx']); yp=py(kp['y'])
    c1='#ff9800' if kp['type']==1 else '#2196f3'
    sv.append(f'<rect x="{xp-4}" y="{yp-4}" width="8" height="8" fill="{c1}" opacity="0.7" rx="1"/>')
    sv.append(f'<text x="{xp}" y="{yp-6}" text-anchor="middle" font-family="sans-serif" font-size="7" fill="{c1}" opacity="0.8">{kp["label"]}</text>')
for i in range(0,n,5):
    ds=str(kls[i]['date']).replace('-',''); lab=f'{ds[4:6]}/{ds[6:8]}'
    sv.append(f'<text x="{px(i)}" y="{bv+30}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-40,{px(i)},{bv+30})">{lab}</text>')

# ── 买点标注 ──
for t_idx, s in enumerate(buy_signals):
    i=s['idx']; xb=px(i); yb=py(s['price'])
    g = gains_map.get(t_idx, {'gain':0})
    clr = '#4caf50' if g['gain'] > 0 else '#e53935'
    lab_y_slot = pt + 10 + (t_idx % 5) * 12
    
    sv.append(f'<line x1="{xb}" y1="{yb}" x2="{xb}" y2="{lab_y_slot+12}" stroke="{clr}" stroke-width="0.8" stroke-dasharray="3,3" opacity="0.7"/>')
    lbl = f'#{t_idx+1} {s["date"][5:]} {s["price"]:.0f}'
    if s['type'] == '突破买点': lbl += f'({s["bs"]}分)'
    tw = len(lbl)*6.5+10
    sv.append(f'<rect x="{xb-tw/2}" y="{lab_y_slot}" width="{tw}" height="14" rx="3" fill="{clr}" opacity="0.85"/>')
    sv.append(f'<text x="{xb}" y="{lab_y_slot+10}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="white" font-weight="bold">{lbl}</text>')

# 图例
lx=pl; ly2=bv+42
legends = [
    ('#ff9800','关键点'), ('#2196f3','供需改变'), ('#ffd700','EMA5'),
    ('#ff6b6b','EMA10'), ('#4ecdc4','EMA20'), ('#4caf50','盈利'),
    ('#e53935','亏损'),
]
for i,(clr,lbl) in enumerate(legends):
    xl=lx+i*130
    sv.append(f'<rect x="{xl}" y="{ly2}" width="9" height="9" fill="{clr}" opacity="0.85" rx="1"/>')
    sv.append(f'<text x="{xl+12}" y="{ly2+8}" font-family="sans-serif" font-size="9" fill="#888888">{lbl}</text>')
sv.append('</svg>')

OUT = '/home/ubuntu/www/review_charts/德明利_回测结果图.svg'
with open(OUT, 'w') as f: f.write('\n'.join(sv))
png_out = OUT.replace('.svg', '.png')
subprocess.run(['rsvg-convert', '-w', '1400', '-f', 'png', OUT, '-o', png_out], check=True)
print(f"已生成: {png_out}")
