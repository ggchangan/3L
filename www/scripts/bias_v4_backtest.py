#!/usr/bin/env python3
"""
波峰波谷V4 - 趋势转折 + 位置过滤 + 信号确认
"""
import requests, pandas as pd, numpy as np
import matplotlib, os, json
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter

OUTPUT_DIR = '/home/ubuntu/www/files'

def judge_market_cycle_v4(df, date_idx=-1):
    if date_idx == -1: date_idx = len(df) - 1
    if date_idx < 70: return {'position':'middle','score':0,'details':{}}
    
    r = df.iloc[date_idx]
    bias20 = r['bias_20']
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    bias_early = r['bias_20'] - df.iloc[date_idx-10]['bias_20'] if date_idx >= 10 else 0
    bias_mid = df.iloc[date_idx-3]['bias_20'] - df.iloc[date_idx-8]['bias_20'] if date_idx >= 8 else 0
    
    # ========== 量价信号（大盘版） ==========
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    ls_pct = (min(r['open'],r['close']) - r['low']) / r['open'] * 100
    us_pct = (r['high'] - max(r['open'],r['close'])) / r['open'] * 100
    gain_pct = (r['close'] - r['open']) / r['open'] * 100
    
    signals = []
    i = date_idx
    last5 = df.iloc[max(0,i-4):i+1]
    
    # 波峰信号
    peak_sig = 0
    if vol_ratio > 1.3 and body_pct < 0.8 and bias20 > 0.5:
        peak_sig += 1; signals.append('churn')
    if us_pct > 1.5 and range_pct > 2.0 and gain_pct < 0:
        peak_sig += 1; signals.append('rejection')
    if len(last5) >= 5:
        gains = [(last5.iloc[j]['close']-last5.iloc[j-1]['close'])/last5.iloc[j-1]['close']*100 for j in range(1,len(last5))]
        avg_g = np.mean(gains)
        today_g = (r['close']-last5.iloc[-2]['close'])/last5.iloc[-2]['close']*100
        if avg_g > 0.5 and today_g < avg_g * 0.3 and vol_ratio > 1.0:
            peak_sig += 1; signals.append('exhaust')
    # 连阳后放量滞涨
    if len(last5) >= 3:
        yang = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close'] > last5.iloc[j-1]['close'])
        if yang >= 3 and vol_ratio > 1.5 and body_pct < 0.6:
            peak_sig += 1; signals.append('yang_churn')
    
    # 波谷信号
    valley_sig = 0
    if gain_pct < -0.015 and vol_ratio > 1.3 and ls_pct > body_pct * 1.5 and ls_pct > 0.5:
        valley_sig += 1; signals.append('panic')
    if ls_pct > 1.0 and body_pct < ls_pct and gain_pct > 0 and bias20 < -0.5:
        valley_sig += 1; signals.append('hammer')
    if len(last5) >= 5:
        down = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close'] < last5.iloc[j-1]['close'])
        if down >= 4 and vol_ratio < 0.8:
            valley_sig += 1; signals.append('fade')
    # 连续下跌后出现十字星或小阳
    if len(last5) >= 4:
        prev4_down = all(last5.iloc[j]['close'] < last5.iloc[j-1]['close'] for j in range(1,4))
        if prev4_down and body_pct < 0.6 and gain_pct > 0:
            valley_sig += 1; signals.append('doji_reversal')
    
    # ========== 转折检测 + 过滤 ==========
    # 核心改变：转折只在合理位置 + 有信号时才触发
    turn_score = 0
    
    # 波峰转折：之前10天内上升>1% + 最近5天平/下降 + 位置>1.5% + 至少一个信号
    if bias_early > 1.0 and bias_chg_5d < 0.3 and bias20 > 1.5:
        if peak_sig >= 1:  # 信号确认
            turn_score += 2.0
            signals.append('peak_confirmed')
        elif peak_sig > 0:
            turn_score += 0.8
            signals.append('peak_possible')
    
    # 波谷转折：之前10天内下降>1.5% + 最近5天平/上升 + 位置<-1.5% + 至少一个信号
    if bias_early < -1.5 and bias_chg_5d > -0.3 and bias20 < -1.5:
        if valley_sig >= 1:  # 信号确认
            turn_score -= 2.0
            signals.append('valley_confirmed')
        elif valley_sig > 0:
            turn_score -= 0.8
            signals.append('valley_possible')
    
    # 极端乖离率自动升级
    if bias20 > 8:
        turn_score = max(turn_score, 2.5)
        signals.append('extreme_high')
    elif bias20 < -8:
        turn_score = min(turn_score, -2.5)
        signals.append('extreme_low')
    
    # ========== 位置得分（辅助） ==========
    if bias20 > 5: level_s = 1.0
    elif bias20 > 2.5: level_s = 0.5
    elif bias20 > 1.0: level_s = 0.2
    elif bias20 > -1.0: level_s = 0
    elif bias20 > -3.0: level_s = -0.2
    elif bias20 > -5.0: level_s = -0.5
    else: level_s = -1.0
    
    # ========== 综合 ==========
    final_score = turn_score * 0.6 + level_s * 0.2 + (peak_sig - valley_sig) * 0.2
    
    if final_score >= 1.8: position = 'peak'
    elif final_score >= 0.6: position = 'near_peak'
    elif final_score <= -1.8: position = 'valley'
    elif final_score <= -0.6: position = 'near_valley'
    else: position = 'middle'
    
    return {
        'position': position,
        'score': round(final_score, 2),
        'details': {
            'turn_score': round(turn_score, 2),
            'level_score': round(level_s, 2),
            'peak_sig': peak_sig,
            'valley_sig': valley_sig,
            'bias20': round(bias20, 2),
            'bias_early_chg': round(bias_early, 2),
            'recent_chg': round(bias_chg_5d, 2),
            'vol_ratio': round(vol_ratio, 2),
            'signals': signals
        }
    }


# ============================
print("=== V4 回测 ===")

url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,1000,qfq'
r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com'})
data = r.json()
raw = data['data']['sh000985']['day']

rows = []
for d in raw:
    rows.append({'date':d[0],'open':float(d[1]),'close':float(d[2]),
                 'high':float(d[3]),'low':float(d[4]),'volume':float(d[5])})
df = pd.DataFrame(rows)
df['date'] = pd.to_datetime(df['date']).sort_values()
df = df.reset_index(drop=True)

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
    j = judge_market_cycle_v4(df, i)
    results.append({'idx':i,'date':df.iloc[i]['date'],'close':df.iloc[i]['close'],
        'position':j['position'],'score':j['score'],
        'is_true_peak':i in major_p,'is_true_valley':i in major_v,
        'pred_peak':j['position'] in ('peak','near_peak'),
        'pred_valley':j['position'] in ('valley','near_valley'),
        'details':j['details']})
dfr = pd.DataFrame(results)
print(f"回测: {len(dfr)}天")

def m(y_t, y_p):
    tp=sum(1 for a,b in zip(y_t,y_p) if a and b)
    fp=sum(1 for a,b in zip(y_t,y_p) if not a and b)
    fn=sum(1 for a,b in zip(y_t,y_p) if a and not b)
    tn=sum(1 for a,b in zip(y_t,y_p) if not a and b)
    return {'TP':tp,'FP':fp,'FN':fn,'TN':tn,
            'precision':round(tp/max(1,tp+fp)*100,1),
            'recall':round(tp/max(1,tp+fn)*100,1),
            'F1':round(2*tp/max(1,2*tp+fp+fn)*100,1),
            'accuracy':round((tp+tn)/max(1,tp+tn+fp+fn)*100,1)}

print(f"\n=== 波峰 ===")
for k,v in m(dfr['is_true_peak'],dfr['pred_peak']).items(): print(f"  {k}: {v}")
print(f"\n=== 波谷 ===")
for k,v in m(dfr['is_true_valley'],dfr['pred_valley']).items(): print(f"  {k}: {v}")

pk5=sum(1 for pi in major_p if any(dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]['pred_peak']))
vl5=sum(1 for vi in major_v if any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['pred_valley']))
print(f"\n=== 容差5天 ===")
print(f"波峰: {pk5}/{len(major_p)} = {pk5/max(1,len(major_p))*100:.0f}%")
print(f"波谷: {vl5}/{len(major_v)} = {vl5/max(1,len(major_v))*100:.0f}%")

print(f"\n=== 分布 ===")
for p in ['valley','near_valley','middle','near_peak','peak']:
    c=(dfr['position']==p).sum()
    print(f"  {p}: {c}天 ({c/len(dfr)*100:.1f}%)")

print(f"\n=== 信号 ===")
sc = Counter()
for _, row in dfr.iterrows(): sc.update(row['details']['signals'])
for s,c in sc.most_common(): print(f"  {s}: {c}次")

# 漏报
missed_p = [i for i in major_p if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['pred_peak'])]
print(f"\n漏报波峰: {len(missed_p)}")
for mi in missed_p:
    r=df.iloc[mi]
    print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}%")
missed_v = [i for i in major_v if not any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['pred_valley'])]
print(f"漏报波谷: {len(missed_v)}")
for mi in missed_v:
    r=df.iloc[mi]
    print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}%")

# === 画图 ===
print(f"\n画图...")
BG='#1a1a2e'; TX='#e0e0e0'
fig = plt.figure(figsize=(20,14),facecolor=BG)
fig.suptitle('V4 Backtest: Turn + Level Filter + Signal Confirm',fontsize=13,color=TX,fontweight='bold',y=0.98)

ax1 = fig.add_subplot(5,1,(1,2),facecolor='#1e1e32')
ax1.grid(True,alpha=0.15,color='#2a2a3e')
ax1.plot(dfr['date'],dfr['close'],color='#4fc3f7',lw=1.5,alpha=0.7)
ax1.scatter([df.iloc[i]['date'] for i in major_p],[df.iloc[i]['close'] for i in major_p],
            color='#ef5350',s=130,marker='s',zorder=5,edgecolors='white',lw=0.5,label='True Peak')
ax1.scatter([df.iloc[i]['date'] for i in major_v],[df.iloc[i]['close'] for i in major_v],
            color='#66bb6a',s=130,marker='s',zorder=5,edgecolors='white',lw=0.5,label='True Valley')
pk_df=dfr[dfr['pred_peak']]; vl_df=dfr[dfr['pred_valley']]
ax1.scatter(pk_df['date'],pk_df['close'],color='#ffa726',s=15,alpha=0.3,zorder=3,label='Pred Peak')
ax1.scatter(vl_df['date'],vl_df['close'],color='#81c784',s=15,alpha=0.3,zorder=3,label='Pred Valley')
ax1.set_ylabel('Price',color=TX,fontsize=10)
ax1.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
plt.setp(ax1.get_xticklabels(),visible=False)

ax2 = fig.add_subplot(5,1,3,facecolor='#1e1e32')
ax2.grid(True,alpha=0.15,color='#2a2a3e')
ax2.plot(dfr['date'],dfr['score'],color='#ce93d8',lw=1.5,label='Score')
for y,c in [(0.6,'#ffa726'),(-0.6,'#66bb6a'),(1.8,'#ef5350'),(-1.8,'#66bb6a')]:
    ax2.axhline(y=y,color=c,lw=0.6,ls='--',alpha=0.4)
ax2.fill_between(dfr['date'],-0.6,0.6,alpha=0.08,color='#888')
ax2.set_ylabel('Score',color=TX,fontsize=10)
ax2.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
plt.setp(ax2.get_xticklabels(),visible=False)

ax3 = fig.add_subplot(5,1,4,facecolor='#1e1e32')
ax3.grid(True,alpha=0.15,color='#2a2a3e')
w=10
dfr['turn_s']=dfr['details'].apply(lambda x:x['turn_score']).rolling(w).mean()
dfr['sig_net']=(dfr['details'].apply(lambda x:x['peak_sig'])-dfr['details'].apply(lambda x:x['valley_sig'])).rolling(w).mean()
ax3.plot(dfr['date'],dfr['turn_s'],color='#ffa726',lw=1,alpha=0.7,label='Turn(MA10)')
ax3.plot(dfr['date'],dfr['sig_net'],color='#ab47bc',lw=1,alpha=0.7,label='Signal Net(MA10)')
ax3.axhline(y=0,color='#666',lw=0.8,ls='--',alpha=0.5)
ax3.set_ylabel('Dim(MA10)',color=TX,fontsize=10)
ax3.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
plt.setp(ax3.get_xticklabels(),visible=False)

ax4 = fig.add_subplot(5,1,5,facecolor='#1e1e32')
ax4.grid(True,alpha=0.15,color='#2a2a3e')
ax4.plot(dfr['date'],dfr['details'].apply(lambda x:x['bias20']),color='#4fc3f7',lw=1,alpha=0.6)
ax4.axhline(y=0,color='#666',lw=0.8,ls='--',alpha=0.5)
sig_colors={'peak_confirmed':'#ef5350','peak_possible':'#ffa726','valley_confirmed':'#66bb6a','valley_possible':'#81c784'}
for sig,c in sig_colors.items():
    pts=dfr[dfr['details'].apply(lambda x: sig in x.get('signals',[]))]
    if len(pts)>0: ax4.scatter(pts['date'],pts['details'].apply(lambda x:x['bias20']),color=c,s=20,alpha=0.6,label=sig)
ax4.set_ylabel('Bias20%',color=TX,fontsize=10)
ax4.set_ylim(-15,15)
ax4.legend(loc='upper left',fontsize=7,facecolor='#1e1e32',edgecolor='#333',ncol=2)
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

plt.tight_layout(rect=[0,0,1,0.96])
out=os.path.join(OUTPUT_DIR, 'bias_v4_backtest_chart.png')
fig.savefig(out,dpi=150,facecolor=BG,bbox_inches='tight')
plt.close()
print(f"图表: {out}")
print(f"\n=== 完成 ===")
