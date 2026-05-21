#!/usr/bin/env python3
"""
波峰波谷新判定 V3 - 基于趋势转折检测
核心：不是看"有多高"，而是看"是不是在掉头"
"""
import requests, pandas as pd, numpy as np
import matplotlib, os, json
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter

OUTPUT_DIR = '/home/ubuntu/www/files'

def judge_market_cycle_v3(df, date_idx=-1):
    """
    基于趋势转折的三维度判定
    Returns: {position, score, details}
    """
    if date_idx == -1: date_idx = len(df) - 1
    if date_idx < 70: return {'position':'middle','score':0,'details':{}}
    
    # 数据
    r = df.iloc[date_idx]
    bias20 = r['bias_20']
    
    # 过去5天和10天的bias变化
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    
    # 更早（5-10天前）的趋势
    bias_trend_early = df.iloc[date_idx-5]['bias_20'] - df.iloc[date_idx-10]['bias_20'] if date_idx >= 10 else 0
    
    # ========== 维度1：趋势状态 ==========
    # 最近趋势方向
    if bias_chg_5d > 1.5: recent_trend = 'strong_up'
    elif bias_chg_5d > 0.5: recent_trend = 'up'
    elif bias_chg_5d > -0.5: recent_trend = 'flat'
    elif bias_chg_5d > -1.5: recent_trend = 'down'
    else: recent_trend = 'strong_down'
    
    # 早期趋势方向
    if bias_trend_early > 1.5: early_trend = 'strong_up'
    elif bias_trend_early > 0.5: early_trend = 'up'
    elif bias_trend_early > -0.5: early_trend = 'flat'
    elif bias_trend_early > -1.5: early_trend = 'down'
    else: early_trend = 'strong_down'
    
    # ========== 维度2：趋势转折检测 ==========
    turn_score = 0
    
    # 波峰转折：之前上升 + 现在变慢/掉头
    # 早期上升(5-10d前上升) + 近期平/下降(3-5d平或下降)
    if early_trend in ('up','strong_up') and recent_trend in ('flat','down','strong_down'):
        turn_score += 1.5
        turning = 'peak_turn'
    elif early_trend in ('up','strong_up') and bias_chg_3d < 0:
        turn_score += 0.8
        turning = 'peak_slow'
    else:
        turning = None
    
    # 波谷转折：之前下降 + 现在变慢/上升
    if early_trend in ('down','strong_down') and recent_trend in ('flat','up','strong_up'):
        turn_score -= 1.5
        turning = 'valley_turn'
    elif early_trend in ('down','strong_down') and bias_chg_3d > 0:
        turn_score -= 0.8
        turning = 'valley_slow'
    
    # ========== 维度3：乖离率位置 ==========
    if bias20 > 5: level_score = +1.5
    elif bias20 > 2.5: level_score = +0.5
    elif bias20 > 1.0: level_score = +0.2
    elif bias20 > -1.0: level_score = 0
    elif bias20 > -3.0: level_score = -0.2
    elif bias20 > -5.0: level_score = -0.5
    else: level_score = -1.5
    
    # 极端值自动升级
    if bias20 > 8:
        turn_score = max(turn_score, 2.0)
        turning = 'peak_extreme'
    elif bias20 < -8:
        turn_score = min(turn_score, -2.0)
        turning = 'valley_extreme'
    
    # ========== 维度4：量价信号 ==========
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    ls_pct = (min(r['open'],r['close']) - r['low']) / r['open'] * 100
    us_pct = (r['high'] - max(r['open'],r['close'])) / r['open'] * 100
    
    sig_score = 0
    signals = []
    i = date_idx
    last5 = df.iloc[max(0,i-4):i+1]
    
    # --- 波峰信号 ---
    # 放量滞涨：量>1.3x + 实体<0.8%
    if vol_ratio > 1.3 and body_pct < 0.8 and bias20 > 1:
        sig_score += 1.0; signals.append('churn')
    
    # 长上影冲高回落
    if us_pct > 1.5 and range_pct > 2.0 and vol_ratio > 1.2 and (r['close'] - r['open']) < 0:
        sig_score += 0.8; signals.append('rejection')
    
    # 加速后滞涨：前5天涨得多，今天涨不动
    if len(last5) >= 5:
        prev_gains = [(last5.iloc[j]['close'] - last5.iloc[j-1]['close'])/last5.iloc[j-1]['close']*100 
                      for j in range(1, len(last5))]
        avg_gain = np.mean(prev_gains)
        today_gain = (r['close'] - last5.iloc[-2]['close'])/last5.iloc[-2]['close']*100 if len(last5)>=2 else 0
        if avg_gain > 0.8 and today_gain < avg_gain * 0.5 and vol_ratio > 1.0:
            sig_score += 0.8; signals.append('exhaustion')
    
    # --- 波谷信号 ---
    # 恐慌出清（大盘版）
    if (r['close'] - r['open']) / r['open'] < -0.015:
        if vol_ratio > 1.3 and ls_pct > body_pct * 1.5 and ls_pct > 0.5:
            sig_score -= 1.0; signals.append('panic')
    
    # 锤子线/下影线
    if ls_pct > 1.0 and body_pct < ls_pct and (r['close'] - r['open']) > 0:
        if bias20 < -1:
            sig_score -= 0.8; signals.append('hammer_up')
    
    # 连续阴跌后缩量
    if len(last5) >= 5:
        days_down = sum(1 for j in range(1, len(last5)) if last5.iloc[j]['close'] < last5.iloc[j-1]['close'])
        if days_down >= 4 and vol_ratio < 0.8:
            sig_score -= 0.6; signals.append('slide_fade')
    
    # ========== 综合评分 ==========
    # 权重：转折40% + 位置20% + 信号40%
    final_score = turn_score * 0.40 + level_score * 0.20 + sig_score * 0.40
    
    # 位置映射
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
            'level_score': round(level_score, 2),
            'sig_score': round(sig_score, 2),
            'bias20': round(bias20, 2),
            'chg_5d': round(bias_chg_5d, 2),
            'early_trend': early_trend,
            'recent_trend': recent_trend,
            'turning': turning,
            'vol_ratio': round(vol_ratio, 2),
            'signals': signals
        }
    }


# ============================
# 回测
# ============================
print("=== 波峰波谷V3 回测 ===")

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
    df[f'bias_{ma}'] = (df['close'] - df[f'MA{ma}']) / df[f'MA{ma}'] * 100

df['bias20_chg_3d'] = df['bias_20'].diff(3)
df['bias20_chg_5d'] = df['bias_20'].diff(5)
df['vol_ma20'] = df['volume'].rolling(20).mean()
print(f"数据: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天")

# --- 真实峰谷 ---
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
    if pv is not None:
        ch = (df.iloc[i]['close']-df.iloc[pv]['close'])/df.iloc[pv]['close']*100
        if ch > 8: major_p.add(i)

major_v = set()
for i in tv:
    pp = max([j for j in tp if j<i], default=None)
    if pp is not None:
        ch = (df.iloc[pp]['close']-df.iloc[i]['close'])/df.iloc[pp]['close']*100
        if ch > 8: major_v.add(i)

print(f"重要波峰: {len(major_p)}, 波谷: {len(major_v)}")

# --- 逐日 ---
results = []
for i in range(120, len(df)):
    j = judge_market_cycle_v3(df, i)
    results.append({
        'idx': i, 'date': df.iloc[i]['date'], 'close': df.iloc[i]['close'],
        'position': j['position'], 'score': j['score'],
        'is_true_peak': i in major_p, 'is_true_valley': i in major_v,
        'pred_peak': j['position'] in ('peak','near_peak'),
        'pred_valley': j['position'] in ('valley','near_valley'),
        'details': j['details']
    })

dfr = pd.DataFrame(results)
print(f"回测: {len(dfr)}天")

# --- 评估 ---
def m(y_t, y_p):
    tp=sum(1 for a,b in zip(y_t,y_p) if a and b)
    fp=sum(1 for a,b in zip(y_t,y_p) if not a and b)
    fn=sum(1 for a,b in zip(y_t,y_p) if a and not b)
    tn=sum(1 for a,b in zip(y_t,y_p) if not a and b)
    return {'TP':tp,'FP':fp,'FN':fn,
            'precision':tp/max(1,tp+fp)*100,'recall':tp/max(1,tp+fn)*100,
            'F1':2*tp/max(1,2*tp+fp+fn)*100}

print(f"\n=== 波峰 ===")
pk = m(dfr['is_true_peak'], dfr['pred_peak'])
for k,v in pk.items(): print(f"  {k}: {v}")

print(f"\n=== 波谷 ===")
vl = m(dfr['is_true_valley'], dfr['pred_valley'])
for k,v in vl.items(): print(f"  {k}: {v}")

# 容差
pk5 = sum(1 for pi in major_p 
    if any(dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]['pred_peak']))
vl5 = sum(1 for vi in major_v
    if any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['pred_valley']))
print(f"\n=== 容差5天 ===")
print(f"波峰: {pk5}/{len(major_p)} ({pk5/max(1,len(major_p))*100:.0f}%)")
print(f"波谷: {vl5}/{len(major_v)} ({vl5/max(1,len(major_v))*100:.0f}%)")

# 分布
print(f"\n=== 分布 ===")
for p in ['valley','near_valley','middle','near_peak','peak']:
    c=(dfr['position']==p).sum()
    print(f"  {p}: {c}天 ({c/len(dfr)*100:.1f}%)")

# 信号
print(f"\n=== 信号 ===")
sc = Counter()
for _, row in dfr.iterrows(): sc.update(row['details']['signals'])
for s,c in sc.most_common(): print(f"  {s}: {c}次")

# 转折类型
print(f"\n=== 转折类型 ===")
for t in ['peak_turn','peak_slow','peak_extreme','valley_turn','valley_slow','valley_extreme']:
    c=(dfr['details'].apply(lambda x:x.get('turning')==t)).sum()
    print(f"  {t}: {c}次")

# 漏报分析
missed_p = [i for i in major_p if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['pred_peak'])]
print(f"\n=== 漏报波峰 ===")
for mi in missed_p:
    r=df.iloc[mi]
    print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}%")

missed_v = [i for i in major_v if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['pred_valley'])]
print(f"\n=== 漏报波谷 ===")
for mi in missed_v:
    r=df.iloc[mi]
    print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}%")

# 误报分析
fp = dfr[dfr['pred_peak'] & ~dfr['is_true_peak']]
if len(fp)>0:
    print(f"\n=== 误报波峰(抽样) ===")
    for _, row in fp.iloc[::max(1,len(fp)//10)].iterrows():
        d=row['details']
        print(f"  {row['date'].date()} score={row['score']:.1f} turn={d['turning']} sig={d['signals']}")

# === 画图 ===
print(f"\n画图...")
BG='#1a1a2e'; TX='#e0e0e0'
fig = plt.figure(figsize=(20,14),facecolor=BG)
fig.suptitle('V3 Backtest: Bias Trend-Turn Detection',fontsize=14,color=TX,fontweight='bold',y=0.98)

ax1 = fig.add_subplot(4,1,(1,2),facecolor='#1e1e32')
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

ax2 = fig.add_subplot(4,1,3,facecolor='#1e1e32')
ax2.grid(True,alpha=0.15,color='#2a2a3e')
ax2.plot(dfr['date'],dfr['score'],color='#ce93d8',lw=1.5,label='Score')
for y,c in [(0.6,'#ffa726'),(-0.6,'#66bb6a'),(1.8,'#ef5350'),(-1.8,'#66bb6a')]:
    ax2.axhline(y=y,color=c,lw=0.6,ls='--',alpha=0.4)
ax2.fill_between(dfr['date'],-0.6,0.6,alpha=0.08,color='#888')
ax2.set_ylabel('Score',color=TX,fontsize=10)
ax2.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
plt.setp(ax2.get_xticklabels(),visible=False)

ax3 = fig.add_subplot(4,1,4,facecolor='#1e1e32')
ax3.grid(True,alpha=0.15,color='#2a2a3e')
w=10
ax3.plot(dfr['date'],dfr['details'].apply(lambda x:x['turn_score']).rolling(w).mean(),
         color='#ffa726',lw=1,alpha=0.7,label='Turn(MA10)')
ax3.plot(dfr['date'],dfr['details'].apply(lambda x:x['sig_score']).rolling(w).mean(),
         color='#ab47bc',lw=1,alpha=0.7,label='Signal(MA10)')
ax3.plot(dfr['date'],dfr['details'].apply(lambda x:x['level_score']).rolling(w).mean(),
         color='#4fc3f7',lw=1,alpha=0.7,label='Level(MA10)')
ax3.axhline(y=0,color='#666',lw=0.8,ls='--',alpha=0.5)
ax3.set_ylabel('Dim(MA10)',color=TX,fontsize=10)
ax3.legend(loc='upper left',fontsize=8,facecolor='#1e1e32',edgecolor='#333')
ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

plt.tight_layout(rect=[0,0,1,0.96])
out=os.path.join(OUTPUT_DIR, 'bias_v3_backtest_chart.png')
fig.savefig(out,dpi=150,facecolor=BG,bbox_inches='tight')
plt.close()
print(f"图表: {out}")
print(f"\n=== 完成 ===")
