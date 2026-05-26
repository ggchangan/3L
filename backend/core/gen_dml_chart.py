#!/usr/bin/env python3
"""生成德明利90天关键点图 + 买点信号标注"""
import json, sys, os
sys.path.insert(0, '/home/ubuntu/3l-server/scripts')

DATA = json.load(open('/home/ubuntu/data/3l/all_stocks_60d.json'))
raw = DATA.get('stocks', DATA)

for sec, stocks in raw.items():
    if '001309' in stocks:
        kls = stocks['001309']
        break

# ── 关键点识别 ──
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
        if highs[i]==max(highs[max(0,i-10):i+1]):
            kps.append({'idx':i,'type':1,'label':'前高','y':highs[i]})
        if lows[i]==min(lows[max(0,i-10):i+1]):
            kps.append({'idx':i,'type':1,'label':'前低','y':lows[i]})
        if i>=10:
            vw=volumes[i-10:i]
            if max(vw)>0:
                if volumes[i]>=max(vw)*1.5:
                    kps.append({'idx':i,'type':1,'label':'量','y':highs[i]+(highs[i]-lows[i])*0.5})
                elif volumes[i]<=min(vw)*0.3:
                    kps.append({'idx':i,'type':1,'label':'量','y':highs[i]+(highs[i]-lows[i])*0.5})
        if i>=10:
            ph=max(highs[i-10:i])
            if closes[i]>ph and closes[i]>opens[i]:
                kps.append({'idx':i,'type':2,'label':'突','y':highs[i],'support_price':ph})
        if i>=1 and closes[i]>opens[i] and closes[i-1]<opens[i-1] and closes[i]>opens[i-1] and opens[i]<closes[i-1]:
            kps.append({'idx':i,'type':2,'label':'反','y':lows[i]})
        if ema20_vals[i] and closes[i]>=ema20_vals[i]*0.98 and closes[i]<=ema20_vals[i]*1.02:
            va=sum(volumes[i-5:i])/5 if i>=5 else 0
            if va>0 and volumes[i]<va*0.8:
                kps.append({'idx':i,'type':2,'label':'中','y':lows[i]})
    return kps

kps = find_keypoints(kls)

# ── 之前的10个买点信号 ──
# 从test_demingli_3l.py的运行结果提取
buy_signals = [
    {'idx': None, 'date':'2026-03-16','type':'突破买点','price':352.06},
    {'idx': None, 'date':'2026-03-20','type':'中继买点','price':331.52},
    {'idx': None, 'date':'2026-03-27','type':'中继买点','price':381.89},
    {'idx': None, 'date':'2026-04-10','type':'突破买点','price':447.24},
    {'idx': None, 'date':'2026-04-15','type':'中继买点','price':501.20},
    {'idx': None, 'date':'2026-04-20','type':'中继买点','price':515.00},
    {'idx': None, 'date':'2026-04-21','type':'中继买点','price':514.60},
    {'idx': None, 'date':'2026-05-06','type':'中继买点','price':577.29},
    {'idx': None, 'date':'2026-05-07','type':'突破买点','price':616.51},
    {'idx': None, 'date':'2026-05-20','type':'中继买点','price':695.96},
]
# 把日期映射到K线索引
for s in buy_signals:
    d = s['date'].replace('-','')
    for i,k in enumerate(kls):
        if str(k['date']).replace('-','') == d:
            s['idx'] = i
            break

# 标注在图上时按盈利/亏损给颜色
results = ['亏','亏','亏','盈','亏','亏','亏','盈','盈','亏']
for s,r in zip(buy_signals, results):
    s['result'] = r

# ── SVG生成 ──
W,H = 1000,600
pl,pr,pt,pb = 65,30,36,70
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
# 背景
sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
sv.append(f'<text x="{W/2}" y="24" text-anchor="middle" font-family="sans-serif" font-size="16" fill="#ffffff" font-weight="bold">德明利(001309) 关键点图 + 买点信号</text>')
sv.append(f'<text x="{W/2}" y="34" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#888888">90天数据 {kls[0]["date"][:4]}-{kls[0]["date"][4:6]}-{kls[0]["date"][6:8]} → {kls[-1]["date"][:4]}-{kls[-1]["date"][4:6]}-{kls[-1]["date"][6:8]}</text>')
# 网格
for i in range(5):
    yv=mx-i*rg/4; yp=py(yv)
    sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
    sv.append(f'<text x="{pl-4}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="9" fill="#666666">{yv:.1f}</text>')
sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
# 量能柱
for i in range(n):
    x=px(i)-cw*0.35; w=max(cw*0.55,1)
    vh=volumes[i]/vm*45
    is_up=closes[i]>=opens[i]; vc='#ff4444' if is_up else '#44aa44'
    sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh,0.5)}" fill="{vc}" opacity="0.35"/>')
# 均线
for ev,clr in [(ema5,'#ffd700'),(ema10,'#ff6b6b'),(ema20,'#4ecdc4')]:
    pts=[]
    for i in range(n):
        if ev[i] is not None:
            pts.append(f'{px(i)},{py(ev[i])}')
    sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="1" opacity="0.7"/>')
# K线
skip_body = 15  # 避免前15天蜡烛太密
for i in range(n):
    if i < skip_body:
        continue
    x=px(i)-cw*0.3; w=cw*0.4
    o,c,h,l = opens[i],closes[i],highs[i],lows[i]
    is_up=c>=o; kc='#ff4444' if is_up else '#44aa44'
    bt,bb=py(max(o,c)),py(min(o,c))
    sv.append(f'<rect x="{x}" y="{bt}" width="{w}" height="{max(bb-bt,1)}" fill="{kc}" opacity="0.8" rx="1"/>')
    sv.append(f'<line x1="{px(i)}" y1="{py(h)}" x2="{px(i)}" y2="{py(l)}" stroke="{kc}" stroke-width="1" opacity="0.8"/>')

# 关键点标注（只标后40根）
kps_visible = [kp for kp in kps if kp['idx'] >= n-40]
for kp in kps_visible:
    i=kp['idx']; xp=px(i); yp=py(kp['y']); sz=5
    c1='#ff9800' if kp['type']==1 else '#2196f3'
    sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{c1}" opacity="0.85" rx="1"/>')
    sv.append(f'<text x="{xp}" y="{yp-sz-3}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="{c1}">{kp["label"]}</text>')

# 日期标签
for i in range(0,n,5):
    ds=str(kls[i]['date']).replace('-','')
    lab=f'{ds[4:6]}/{ds[6:8]}'
    sv.append(f'<text x="{px(i)}" y="{bv+32}" text-anchor="middle" font-family="sans-serif" font-size="9" fill="#666666" transform="rotate(-40,{px(i)},{bv+32})">{lab}</text>')

# 买点信号标注
for s in buy_signals:
    if s['idx'] is None:
        continue
    i=s['idx']; xb=px(i); yb=py(s['price'])
    clr='#4caf50' if s['result']=='盈' else '#e53935'
    # 买入标签 - 从K线位置画虚线到顶部
    lab_y=pt-2
    sv.append(f'<line x1="{xb}" y1="{yb}" x2="{xb}" y2="{lab_y+20}" stroke="{clr}" stroke-width="1" stroke-dasharray="4,3"/>')
    # 标签框
    txt = f'买{s["date"][5:]}({s["price"]:.0f})'
    tw=len(txt)*7+16
    sv.append(f'<rect x="{xb-tw/2}" y="{lab_y}" width="{tw}" height="20" rx="4" fill="{clr}" opacity="0.9"/>')
    sv.append(f'<text x="{xb}" y="{lab_y+14}" text-anchor="middle" font-family="sans-serif" font-size="10" fill="white" font-weight="bold">{txt}</text>')

# 图例
legends=[
    ('#ff9800','第1类参考点'),
    ('#2196f3','第2类供需改变'),
    ('#ffd700','EMA5'),
    ('#ff6b6b','EMA10'),
    ('#4ecdc4','EMA20'),
    ('#4caf50','买点-盈利'),
    ('#e53935','买点-亏损'),
]
lx=pl; ly2=bv+46
for i,(clr,lbl) in enumerate(legends):
    xl=lx+i*140
    sv.append(f'<rect x="{xl}" y="{ly2}" width="10" height="10" fill="{clr}" opacity="0.85" rx="1"/>')
    sv.append(f'<text x="{xl+14}" y="{ly2+9}" font-family="sans-serif" font-size="10" fill="#888888">{lbl}</text>')

sv.append('</svg>')
svg_content = '\n'.join(sv)

OUT = '/home/ubuntu/3l-server/data/public/charts/德明利_关键点图.svg'
with open(OUT, 'w') as f:
    f.write(svg_content)
print(f"已生成: {OUT}")
print(f"关键点: {len(kps)}个 (显示后40根中的{len(kps_visible)}个)")
print(f"买点信号: {len(buy_signals)}个")
