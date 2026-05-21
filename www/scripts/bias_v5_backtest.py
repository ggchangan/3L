#!/usr/bin/env python3
"""
波峰波谷V5 - 置信度分层方案
宽松检测转折，按信号强度分层置信度
"""
import requests, pandas as pd, numpy as np
import matplotlib, os, json
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter

OUTPUT_DIR = '/home/ubuntu/www/files'

def judge_market_cycle_v5(df, date_idx=-1):
    if date_idx == -1: date_idx = len(df) - 1
    if date_idx < 70: return {'position':'middle','score':0,'details':{}}
    
    r = df.iloc[date_idx]
    bias20 = r['bias_20']
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    bias_early = r['bias_20'] - df.iloc[date_idx-10]['bias_20'] if date_idx >= 10 else 0

    # ========== 量价信号 ==========
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    ls_pct = (min(r['open'],r['close']) - r['low']) / r['open'] * 100
    us_pct = (r['high'] - max(r['open'],r['close'])) / r['open'] * 100
    gain = (r['close'] - r['open']) / r['open'] * 100

    i = date_idx
    last5 = df.iloc[max(0,i-4):i+1]
    signals = []

    # 波峰信号
    peak_sig = 0
    if vol_ratio > 1.3 and body_pct < 0.8:
        peak_sig += 1; signals.append('churn')
    if us_pct > 1.5 and gain < 0:
        peak_sig += 1; signals.append('reject')
    if len(last5) >= 5:
        gains = [(last5.iloc[j]['close']-last5.iloc[j-1]['close'])/last5.iloc[j-1]['close']*100 
                 for j in range(1,len(last5))]
        avg = np.mean([g for g in gains if not np.isnan(g)] or [0])
        tg = (r['close']-last5.iloc[-2]['close'])/last5.iloc[-2]['close']*100
        if avg > 0.5 and tg < avg*0.3:
            peak_sig += 1; signals.append('exhaust')
        yang = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close']>last5.iloc[j-1]['close'])
        if yang >= 3 and vol_ratio > 1.5 and body_pct < 0.6:
            peak_sig += 1; signals.append('yang_churn')

    # 波谷信号
    valley_sig = 0
    if gain < -1.5 and vol_ratio > 1.3 and ls_pct > body_pct*1.5 and ls_pct > 0.5:
        valley_sig += 1; signals.append('panic')
    if ls_pct > 1.0 and body_pct < ls_pct:
        valley_sig += 1; signals.append('hammer')
    if len(last5) >= 4:
        down = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close']<last5.iloc[j-1]['close'])
        if down >= 4 and vol_ratio < 0.8:
            valley_sig += 1; signals.append('fade')
        prev4 = all(last5.iloc[j]['close']<last5.iloc[j-1]['close'] for j in range(1,4))
        if prev4 and body_pct < 0.8 and gain > 0:
            valley_sig += 1; signals.append('doji_rev')

    # ========== 趋势转折检测（宽松版） ==========
    # 波峰：之前10天上升>0.5% + 最近5天平/降
    peak_turn = bias_early > 0.5 and bias_chg_5d < 0.3
    
    # 波谷：之前10天下降>0.8% + 最近5天平/升  
    valley_turn = bias_early < -0.8 and bias_chg_5d > -0.3

    # ========== 置信度分层 ==========
    # 用4个条件打分：趋势转折 + 乖离率位置 + 量价信号
    # 波峰得分(0~4)
    pk_score = 0
    if peak_turn: pk_score += 1
    if bias20 > 1.5: pk_score += 1
    if peak_sig >= 1: pk_score += 1
    if bias_chg_3d < 0: pk_score += 1  # 趋势明确掉头

    # 波谷得分(0~4)
    vl_score = 0
    if valley_turn: vl_score += 1
    if bias20 < -1.5: vl_score += 1
    if valley_sig >= 1: vl_score += 1
    if bias_chg_3d > 0: vl_score += 1

    # 极端值自动触发
    if bias20 > 8: pk_score = max(pk_score, 3)
    if bias20 < -8: vl_score = max(vl_score, 3)

    # ========== 位置映射 ==========
    # 总倾向得分：正=波峰，负=波谷
    total = pk_score - vl_score
    
    # peak: 4项全满足或极端值
    if pk_score >= 4: position = 'peak'; signals.append('peak_4')
    # near_peak: 3项满足
    elif pk_score >= 3: position = 'near_peak'; signals.append('peak_3')
    # valley: 4项全满足
    elif vl_score >= 4: position = 'valley'; signals.append('valley_4')
    # near_valley: 3项满足
    elif vl_score >= 3: position = 'near_valley'; signals.append('valley_3')
    else: position = 'middle'

    # 数值标准化到 -4~+4
    score = (pk_score - vl_score) * 1.0

    return {
        'position': position,
        'score': round(score, 1),
        'details': {
            'pk_score': pk_score,
            'vl_score': vl_score,
            'bias20': round(bias20, 2),
            'bias_early': round(bias_early, 2),
            'chg_5d': round(bias_chg_5d, 2),
            'peak_turn': peak_turn,
            'valley_turn': valley_turn,
            'peak_sig': peak_sig,
            'valley_sig': valley_sig,
            'vol_ratio': round(vol_ratio, 2),
            'signals': signals
        }
    }


# ============================
print("=== V5 回测 ===")

url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,1000,qfq'
r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com'})
raw = r.json()['data']['sh000985']['day']

rows = []
for d in raw:
    rows.append({'date':d[0],'open':float(d[1]),'close':float(d[2]),
                 'high':float(d[3]),'low':float(d[4]),'volume':float(d[5])})
df = pd.DataFrame(rows)
df['date'] = pd.to_datetime(df['date']).sort_values().reset_index(drop=True)

for ma in [5,10,20,60]:
    df[f'MA{ma}'] = df['close'].rolling(ma).mean()
    df[f'bias_{ma}'] = (df['close']-df[f'MA{ma}'])/df[f'MA{ma}']*100
df['bias20_chg_3d'] = df['bias_20'].diff(3)
df['bias20_chg_5d'] = df['bias_20'].diff(5)
df['vol_ma20'] = df['volume'].rolling(20).mean()
print(f"数据: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天")

def find_swings(series, w=20):
    p=pd.Series(False,index=series.index); v=pd.Series(False,index=series.index)
    for i in range(w,len(series)-w):
        seg=series.iloc[i-w:i+w+1]
        if series.iloc[i]==max(seg): p.iloc[i]=True
        if series.iloc[i]==min(seg): v.iloc[i]=True
    return p,v

peaks, valleys = find_swings(df['close'], 20)
tp = set(df[peaks].index.tolist()); tv = set(df[valleys].index.tolist())

major_p = set()
for i in tp:
    pv = max([j for j in tv if j<i], default=None)
    if pv and (df.iloc[i]['close']-df.iloc[pv]['close'])/df.iloc[pv]['close']*100>8: major_p.add(i)
major_v = set()
for i in tv:
    pp = max([j for j in tp if j<i], default=None)
    if pp and (df.iloc[pp]['close']-df.iloc[i]['close'])/df.iloc[pp]['close']*100>8: major_v.add(i)
print(f"波峰: {len(major_p)}, 波谷: {len(major_v)}")

results = []
for i in range(120, len(df)):
    j = judge_market_cycle_v5(df, i)
    results.append({'idx':i,'date':df.iloc[i]['date'],'close':df.iloc[i]['close'],
        'position':j['position'],'score':j['score'],
        'is_true_peak':i in major_p,'is_true_valley':i in major_v,
        'pred_peak':j['position'] in ('peak','near_peak'),
        'pred_valley':j['position'] in ('valley','near_valley'),
        'details':j['details']})
dfr = pd.DataFrame(results)
print(f"回测: {len(dfr)}天")

# === 评估函数（多重阈值） ===
def eval_at_threshold(dfr, min_pk_score, min_vl_score, label):
    pred_p = dfr['details'].apply(lambda x: x['pk_score'] >= min_pk_score)
    pred_v = dfr['details'].apply(lambda x: x['vl_score'] >= min_vl_score)
    tp_p = sum(1 for i,(a,b) in enumerate(zip(dfr['is_true_peak'],pred_p)) if a and b)
    fp_p = sum(1 for i,(a,b) in enumerate(zip(dfr['is_true_peak'],pred_p)) if not a and b)
    fn_p = dfr['is_true_peak'].sum() - tp_p
    tp_v = sum(1 for i,(a,b) in enumerate(zip(dfr['is_true_valley'],pred_v)) if a and b)
    fp_v = sum(1 for i,(a,b) in enumerate(zip(dfr['is_true_valley'],pred_v)) if not a and b)
    fn_v = dfr['is_true_valley'].sum() - tp_v
    
    # 容差5天
    pk5 = sum(1 for pi in major_p if any(dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]['details'].apply(lambda x:x['pk_score']>=min_pk_score)))
    vl5 = sum(1 for vi in major_v if any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['details'].apply(lambda x:x['vl_score']>=min_vl_score)))
    
    print(f"\n--- {label}(pk>={min_pk_score}, vl>={min_vl_score}) ---")
    print(f"波峰: TP={tp_p} FP={fp_p} FN={fn_p} 精={tp_p/max(1,tp_p+fp_p)*100:.0f}% 召={tp_p/max(1,tp_p+fn_p)*100:.0f}%")
    print(f"波谷: TP={tp_v} FP={fp_v} FN={fn_v} 精={tp_v/max(1,tp_v+fp_v)*100:.0f}% 召={tp_v/max(1,tp_v+fn_v)*100:.0f}%")
    print(f"容差5d 峰:{pk5}/{len(major_p)} 谷:{vl5}/{len(major_v)}")
    return {'min_pk':min_pk_score,'min_vl':min_vl_score,'peak_recall':tp_p/max(1,tp_p+fn_p),
            'peak_prec':tp_p/max(1,tp_p+fp_p),'valley_recall':tp_v/max(1,tp_v+fn_v),
            'valley_prec':tp_v/max(1,tp_v+fp_v),'pk5':pk5,'vl5':vl5}

thresholds = [
    (4, 4, "PEAK/VALLEY"),
    (3, 3, "NEAR"),
    (3, 4, "NEAR_PEAK+VALLEY"),
    (4, 3, "PEAK+NEAR_VALLEY"),
    (2, 2, "WIDE"),
    (1, 1, "SUPER_WIDE"),
]
all_results = []
for pk_min, vl_min, label in thresholds:
    all_results.append(eval_at_threshold(dfr, pk_min, vl_min, label))

# 分布
print(f"\n=== 分布 ===")
for p in ['valley','near_valley','middle','near_peak','peak']:
    c=(dfr['position']==p).sum()
    print(f"  {p}: {c}天 ({c/len(dfr)*100:.1f}%)")

# 信号频率
print(f"\n=== 信号频率 ===")
sc = Counter()
for _, row in dfr.iterrows(): sc.update(row['details']['signals'])
for s,c in sc.most_common(): print(f"  {s}: {c}次")

# 漏报分析（3分以下）
print(f"\n=== pk_score<3时漏报波峰 ===")
for pi in major_p:
    region = dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]
    max_pk = region['details'].apply(lambda x:x['pk_score']).max() if len(region)>0 else 0
    if max_pk < 3:
        r=df.iloc[pi]
        print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}% max_pk={max_pk}")

print(f"\n=== vl_score<3时漏报波谷 ===")
for vi in major_v:
    region = dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]
    max_vl = region['details'].apply(lambda x:x['vl_score']).max() if len(region)>0 else 0
    if max_vl < 3:
        r=df.iloc[vi]
        print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}% max_vl={max_vl}")

# === 画图 ===
print(f"\n画图...")
BG='#1a1a2e'; TX='#e0e0e0'
fig = plt.figure(figsize=(20,14),facecolor=BG)
fig.suptitle('V5 Backtest: Loose Turn + Confidence Scoring',fontsize=13,color=TX,fontweight='bold',y=0.98)

ax1 = fig.add_subplot(4,1,(1,2),facecolor='#1e1e32')
ax1.grid(True,alpha=0.15,color='#2a2a3e')
ax1.plot(dfr['date'],dfr['close'],color='#4fc3f7',lw=1.5,alpha=0.7)
ax1.scatter([df.iloc[i]['date'] for i in major_p],[df.iloc[i]['close'] for i in major_p],
            color='#ef5350',s=130,marker='s',zorder=5,edgecolors='white',lw=0.5,label='True Peak')
ax1.scatter([df.iloc[i]['date'] for i in major_v],[df.iloc[i]['close'] for i in major_v],
            color='#66bb6a',s=130,marker='s',zorder=5,edgecolors='white',lw=0.5,label='True Valley')

# 不同置信度颜色
c4=dfr[dfr['details'].apply(lambda x:x['pk_score']>=4)]
c3=dfr[(dfr['details'].apply(lambda x:x['pk_score']==3))]
v4=dfr[dfr['details'].apply(lambda x:x['vl_score']>=4)]
v3=dfr[(dfr['details'].apply(lambda x:x['vl_score']==3))]
ax1.scatter(c4['date'],c4['close'],color='#ff1744',s=40,marker='^',zorder=4,label='Peak(4)')
ax1.scatter(c3['date'],c3['close'],color='#ff9100',s=25,marker='^',alpha=0.5,zorder=3,label='NearPeak(3)')
ax1.scatter(v4['date'],v4['close'],color='#00e676',s=40,marker='v',zorder=4,label='Valley(4)')
ax1.scatter(v3['date'],v3['close'],color='#69f0ae',s=25,marker='v',alpha=0.5,zorder=3,label='NearValley(3)')
ax1.set_ylabel('Price',color=TX,fontsize=10)
ax1.legend(loc='upper left',fontsize=7,facecolor='#1e1e32',edgecolor='#333',ncol=2)
plt.setp(ax1.get_xticklabels(),visible=False)

ax2 = fig.add_subplot(4,1,3,facecolor='#1e1e32')
ax2.grid(True,alpha=0.15,color='#2a2a3e')
dfr['pk_s']=dfr['details'].apply(lambda x:x['pk_score'])
dfr['vl_s']=dfr['details'].apply(lambda x:x['vl_score'])
ax2.plot(dfr['date'],dfr['pk_s'],color='#ff7043',lw=1,alpha=0.8,label='Peak Score')
ax2.plot(dfr['date'],-dfr['vl_s'],color='#66bb6a',lw=1,alpha=0.8,label='-Valley Score')
ax2.axhline(y=3,color='#ffa726',lw=0.6,ls='--',alpha=0.4)
ax2.axhline(y=-3,color='#81c784',lw=0.6,ls='--',alpha=0.4)
ax2.set_ylabel('Score',color=TX,fontsize=10)
ax2.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
plt.setp(ax2.get_xticklabels(),visible=False)

ax3 = fig.add_subplot(4,1,4,facecolor='#1e1e32')
ax3.grid(True,alpha=0.15,color='#2a2a3e')
ax3.plot(dfr['date'],dfr['details'].apply(lambda x:x['bias20']),color='#4fc3f7',lw=1,alpha=0.6)
ax3.axhline(y=0,color='#666',lw=0.8,ls='--',alpha=0.5)
for y,c in [(-1.5,'#66bb6a'),(1.5,'#ffa726')]:
    ax3.axhline(y=y,color=c,lw=0.5,ls=':',alpha=0.3)
sig_colors={'peak_4':'#ff1744','peak_3':'#ff9100','valley_4':'#00e676','valley_3':'#69f0ae'}
for sig,c in sig_colors.items():
    pts=dfr[dfr['details'].apply(lambda x: sig in x.get('signals',[]))]
    if len(pts)>0: ax3.scatter(pts['date'],pts['details'].apply(lambda x:x['bias20']),color=c,s=15,alpha=0.5,label=sig)
ax3.set_ylabel('Bias20%',color=TX,fontsize=10)
ax3.set_ylim(-15,15)
ax3.legend(loc='upper left',fontsize=7,facecolor='#1e1e32',edgecolor='#333',ncol=2)
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

plt.tight_layout(rect=[0,0,1,0.96])
out=os.path.join(OUTPUT_DIR, 'bias_v5_backtest_chart.png')
fig.savefig(out,dpi=150,facecolor=BG,bbox_inches='tight')
plt.close()
print(f"图表: {out}")
print(f"\n=== 完成 ===")
