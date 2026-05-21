#!/usr/bin/env python3
"""V5 清晰版准确率报告"""
import requests, pandas as pd, numpy as np, os, json
OUTPUT_DIR = '/home/ubuntu/www/files'

def judge(df, i):
    if i < 70: return {'pk':0,'vl':0}
    r=df.iloc[i]; b20=r['bias_20']
    b5=r['bias20_chg_5d']; b3=r['bias20_chg_3d']
    be=b20-df.iloc[i-10]['bias_20']
    
    l5=df.iloc[max(0,i-4):i+1]; vr=r['volume']/r['vol_ma20'] if r['vol_ma20']>0 else 1
    bp=abs(r['close']-r['open'])/r['open']*100
    ls=(min(r['open'],r['close'])-r['low'])/r['open']*100
    us=(r['high']-max(r['open'],r['close']))/r['open']*100
    g=(r['close']-r['open'])/r['open']*100
    ps=0
    if vr>1.3 and bp<0.8: ps+=1
    if us>1.5 and g<0: ps+=1
    if len(l5)>=5:
        gs=[(l5.iloc[j]['close']-l5.iloc[j-1]['close'])/l5.iloc[j-1]['close']*100 for j in range(1,len(l5))]
        ag=np.mean([x for x in gs if not np.isnan(x)] or [0])
        tg=(r['close']-l5.iloc[-2]['close'])/l5.iloc[-2]['close']*100
        if ag>0.5 and tg<ag*0.3: ps+=1
        yang=sum(1 for j in range(1,len(l5)) if l5.iloc[j]['close']>l5.iloc[j-1]['close'])
        if yang>=3 and vr>1.5 and bp<0.6: ps+=1
    vs=0
    if g<-1.5 and vr>1.3 and ls>bp*1.5 and ls>0.5: vs+=1
    if ls>1.0 and bp<ls: vs+=1
    if len(l5)>=4:
        dn=sum(1 for j in range(1,len(l5)) if l5.iloc[j]['close']<l5.iloc[j-1]['close'])
        if dn>=4 and vr<0.8: vs+=1
        p4=all(l5.iloc[j]['close']<l5.iloc[j-1]['close'] for j in range(1,4))
        if p4 and bp<0.8 and g>0: vs+=1
    pk_s=0
    if be>0.5 and b5<0.3: pk_s+=1
    if b20>1.5: pk_s+=1
    if ps>=1: pk_s+=1
    if b3<0: pk_s+=1
    if b20>8: pk_s=max(pk_s,3)
    vl_s=0
    if be<-0.8 and b5>-0.3: vl_s+=1
    if b20<-1.5: vl_s+=1
    if vs>=1: vl_s+=1
    if b3>0: vl_s+=1
    if b20<-8: vl_s=max(vl_s,3)
    return {'pk':pk_s,'vl':vl_s}

def get_data(code):
    url=f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,1000,qfq'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com'})
    raw=r.json()['data'][code]['day']
    rows=[{'date':d[0],'open':float(d[1]),'close':float(d[2]),'high':float(d[3]),'low':float(d[4]),'volume':float(d[5])} for d in raw]
    df=pd.DataFrame(rows); df['date']=pd.to_datetime(df['date']).sort_values().reset_index(drop=True)
    for ma in [5,10,20,60]:
        df[f'MA{ma}']=df['close'].rolling(ma).mean()
        df[f'bias_{ma}']=(df['close']-df[f'MA{ma}'])/df[f'MA{ma}']*100
    df['bias20_chg_3d']=df['bias_20'].diff(3)
    df['bias20_chg_5d']=df['bias_20'].diff(5)
    df['vol_ma20']=df['volume'].rolling(20).mean()
    return df

def get_swings(df, w=20, amp=8):
    s=df['close']; p=pd.Series(False,index=s.index); v=pd.Series(False,index=s.index)
    for i in range(w,len(s)-w):
        seg=s.iloc[i-w:i+w+1]
        if s.iloc[i]==max(seg): p.iloc[i]=True
        if s.iloc[i]==min(seg): v.iloc[i]=True
    tp=set(df[p].index); tv=set(df[v].index)
    mp=set(); mv=set()
    for i in tp:
        pv=max([j for j in tv if j<i], default=None)
        if pv and (df.iloc[i]['close']-df.iloc[pv]['close'])/df.iloc[pv]['close']*100>amp: mp.add(i)
    for i in tv:
        pp=max([j for j in tp if j<i], default=None)
        if pp and (df.iloc[pp]['close']-df.iloc[i]['close'])/df.iloc[pp]['close']*100>amp: mv.add(i)
    return mp, mv

indices = [('sh000985','中证全指'),('sh000300','沪深300'),('sz399006','创业板指')]

for code, name in indices:
    print(f"\n{'='*55}")
    print(f"  {name}")
    print(f"{'='*55}")
    df=get_data(code)
    mp, mv=get_swings(df)
    
    # 逐日判定
    preds = []
    for i in range(120, len(df)):
        j=judge(df,i)
        preds.append({'idx':i,'date':df.iloc[i]['date'],'pk':j['pk'],'vl':j['vl'],
                      'tp':i in mp,'tv':i in mv})
    dfr=pd.DataFrame(preds)
    print(f"  数据: {len(dfr)}天  真实波峰:{len(mp)}个  真实波谷:{len(mv)}个")
    
    print(f"\n  {'='*50}")
    print(f"  {'阈值':<8} {'含义':<10} {'真实峰':<6} {'命中(容差5d)':<14} {'召回率':<8} {'误报天数':<10} {'误报/日':<8}")
    print(f"  {'='*50}")
    
    for th, label in [(4,'PEAK'),(3,'NEAR'),(2,'WIDE')]:
        # 波峰
        pk_hit_5d = sum(1 for pi in mp 
            if any(dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]['pk']>=th))
        pk_recall = pk_hit_5d/max(1,len(mp))*100
        pk_fp = (dfr['pk']>=th).sum()  # 总天数
        # 减去真实峰附近的命中（在峰±5天内的判定不算误报）
        true_zone = set()
        for pi in mp:
            true_zone.update(range(max(0,pi-5), min(len(df),pi+6)))
        pk_fp_adjusted = dfr[dfr['pk']>=th]['idx'].apply(lambda x: x not in true_zone).sum()
        
        # 波谷
        vl_hit_5d = sum(1 for vi in mv
            if any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['vl']>=th))
        vl_recall = vl_hit_5d/max(1,len(mv))*100
        vl_fp_adjusted = dfr[dfr['vl']>=th]['idx'].apply(lambda x: x not in true_zone).sum()
        
        rate_p = pk_fp_adjusted/len(dfr)*100
        rate_v = vl_fp_adjusted/len(dfr)*100
        
        print(f"  峰{th:<6} {label:<10} {len(mp):<6} {f'{pk_hit_5d}/{len(mp)}':<14} {pk_recall:<7.0f}% {pk_fp_adjusted:<10} {rate_p:<7.1f}%")
        print(f"  谷{th:<6} {label:<10} {len(mv):<6} {f'{vl_hit_5d}/{len(mv)}':<14} {vl_recall:<7.0f}% {vl_fp_adjusted:<10} {rate_v:<7.1f}%")
    
    print(f"\n  [判定天数统计]")
    for th in [4,3,2]:
        print(f"  pk>={th}: {(dfr['pk']>=th).sum()}天  vl>={th}: {(dfr['vl']>=th).sum()}天")
    
    # 漏报明细
    print(f"\n  [漏报明细]")
    missed_p = [i for i in mp if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['pk']>=3)]
    missed_v = [i for i in mv if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['vl']>=3)]
    if missed_p:
        print(f"  波峰漏报({len(missed_p)}):")
        for i in missed_p:
            r=df.iloc[i]; print(f"    {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}% chg5d={r['bias20_chg_5d']:.1f}%")
    if missed_v:
        print(f"  波谷漏报({len(missed_v)}):")
        for i in missed_v:
            r=df.iloc[i]; print(f"    {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}% chg5d={r['bias20_chg_5d']:.1f}%")
    if not missed_p and not missed_v:
        print(f"  全部命中！")
