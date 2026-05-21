#!/usr/bin/env python3
"""
V5 多指数验证：中证全指 + 沪深300 + 创业板指
"""
import requests, pandas as pd, numpy as np
import matplotlib, os, json
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from collections import Counter

OUTPUT_DIR = '/home/ubuntu/www/files'

def judge_v5(df, date_idx=-1):
    if date_idx == -1: date_idx = len(df) - 1
    if date_idx < 70: return {'pk_score':0,'vl_score':0}
    
    r = df.iloc[date_idx]
    bias20 = r['bias_20']
    bias_chg_5d = r['bias20_chg_5d']
    bias_chg_3d = r['bias20_chg_3d']
    bias_early = r['bias_20'] - df.iloc[date_idx-10]['bias_20'] if date_idx >= 10 else 0
    
    i = date_idx
    last5 = df.iloc[max(0,i-4):i+1]
    
    # 信号
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close']-r['open'])/r['open']*100
    ls_pct = (min(r['open'],r['close'])-r['low'])/r['open']*100
    us_pct = (r['high']-max(r['open'],r['close']))/r['open']*100
    gain = (r['close']-r['open'])/r['open']*100
    
    peak_sig = 0
    if vol_ratio > 1.3 and body_pct < 0.8: peak_sig += 1
    if us_pct > 1.5 and gain < 0: peak_sig += 1
    if len(last5) >= 5:
        gains = [(last5.iloc[j]['close']-last5.iloc[j-1]['close'])/last5.iloc[j-1]['close']*100 for j in range(1,len(last5))]
        avg_g = np.mean([g for g in gains if not np.isnan(g)] or [0])
        tg = (r['close']-last5.iloc[-2]['close'])/last5.iloc[-2]['close']*100
        if avg_g > 0.5 and tg < avg_g*0.3: peak_sig += 1
        yang = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close']>last5.iloc[j-1]['close'])
        if yang >= 3 and vol_ratio > 1.5 and body_pct < 0.6: peak_sig += 1
    
    valley_sig = 0
    if gain < -1.5 and vol_ratio > 1.3 and ls_pct > body_pct*1.5 and ls_pct > 0.5: valley_sig += 1
    if ls_pct > 1.0 and body_pct < ls_pct: valley_sig += 1
    if len(last5) >= 4:
        down = sum(1 for j in range(1,len(last5)) if last5.iloc[j]['close']<last5.iloc[j-1]['close'])
        if down >= 4 and vol_ratio < 0.8: valley_sig += 1
        p4 = all(last5.iloc[j]['close']<last5.iloc[j-1]['close'] for j in range(1,4))
        if p4 and body_pct < 0.8 and gain > 0: valley_sig += 1
    
    # 转折检测
    peak_turn = bias_early > 0.5 and bias_chg_5d < 0.3
    valley_turn = bias_early < -0.8 and bias_chg_5d > -0.3
    
    pk_s = 0
    if peak_turn: pk_s += 1
    if bias20 > 1.5: pk_s += 1
    if peak_sig >= 1: pk_s += 1
    if bias_chg_3d < 0: pk_s += 1
    if bias20 > 8: pk_s = max(pk_s, 3)
    
    vl_s = 0
    if valley_turn: vl_s += 1
    if bias20 < -1.5: vl_s += 1
    if valley_sig >= 1: vl_s += 1
    if bias_chg_3d > 0: vl_s += 1
    if bias20 < -8: vl_s = max(vl_s, 3)
    
    return {'pk_score': pk_s, 'vl_score': vl_s,
            'peak_turn': peak_turn, 'valley_turn': valley_turn,
            'peak_sig': peak_sig, 'valley_sig': valley_sig,
            'bias20': round(bias20,2), 'bias_early': round(bias_early,2)}


def fetch_index(code, name):
    """获取指数数据"""
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,1000,qfq'
    r = requests.get(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.qq.com'})
    raw = r.json()['data'][code]['day']
    rows = [{'date':d[0],'open':float(d[1]),'close':float(d[2]),
             'high':float(d[3]),'low':float(d[4]),'volume':float(d[5])} for d in raw]
    df = pd.DataFrame(rows)
    df['date'] = pd.to_datetime(df['date']).sort_values().reset_index(drop=True)
    for ma in [5,10,20,60]:
        df[f'MA{ma}'] = df['close'].rolling(ma).mean()
        df[f'bias_{ma}'] = (df['close']-df[f'MA{ma}'])/df[f'MA{ma}']*100
    df['bias20_chg_3d'] = df['bias_20'].diff(3)
    df['bias20_chg_5d'] = df['bias_20'].diff(5)
    df['vol_ma20'] = df['volume'].rolling(20).mean()
    return df


def find_major_swings(df, w=20, amp=8):
    """找重要峰谷"""
    series = df['close']
    p = pd.Series(False,index=series.index)
    v = pd.Series(False,index=series.index)
    for i in range(w,len(series)-w):
        seg = series.iloc[i-w:i+w+1]
        if series.iloc[i] == max(seg): p.iloc[i] = True
        if series.iloc[i] == min(seg): v.iloc[i] = True
    tp = set(df[p].index.tolist())
    tv = set(df[v].index.tolist())
    major_p = set()
    for i in tp:
        pv = max([j for j in tv if j<i], default=None)
        if pv and (df.iloc[i]['close']-df.iloc[pv]['close'])/df.iloc[pv]['close']*100 > amp:
            major_p.add(i)
    major_v = set()
    for i in tv:
        pp = max([j for j in tp if j<i], default=None)
        if pp and (df.iloc[pp]['close']-df.iloc[i]['close'])/df.iloc[pp]['close']*100 > amp:
            major_v.add(i)
    return major_p, major_v


def run_backtest(name, df):
    """对一个指数跑回测"""
    major_p, major_v = find_major_swings(df)
    results = []
    for i in range(120, len(df)):
        j = judge_v5(df, i)
        results.append({'idx':i, 'date':df.iloc[i]['date'],
            'close':df.iloc[i]['close'],
            'is_true_peak':i in major_p,'is_true_valley':i in major_v,
            **j})
    dfr = pd.DataFrame(results)
    
    # 多重阈值评估
    report = {'name': name, 'days': len(dfr), 'peaks': len(major_p), 'valleys': len(major_v)}
    
    for pk_min, vl_min, label in [(4,4,'peak'),(3,3,'near'),(2,2,'wide')]:
        pk5 = sum(1 for pi in major_p 
            if any(dfr[(dfr['idx']>=pi-5)&(dfr['idx']<=pi+5)]['pk_score'] >= pk_min))
        vl5 = sum(1 for vi in major_v
            if any(dfr[(dfr['idx']>=vi-5)&(dfr['idx']<=vi+5)]['vl_score'] >= vl_min))
        
        pk_fp = (dfr['pk_score'] >= pk_min).sum()
        vl_fp = (dfr['vl_score'] >= vl_min).sum()
        pk_hit = sum(1 for i in major_p if dfr.iloc[i-120]['pk_score']>=pk_min)
        vl_hit = sum(1 for i in major_v if dfr.iloc[i-120]['vl_score']>=vl_min)
        
        report[f'{label}_pk5'] = f"{pk5}/{len(major_p)}"
        report[f'{label}_vl5'] = f"{vl5}/{len(major_v)}"
        report[f'{label}_pk_recall'] = f"{pk5/max(1,len(major_p))*100:.0f}%"
        report[f'{label}_vl_recall'] = f"{vl5/max(1,len(major_v))*100:.0f}%"
        report[f'{label}_pk_days_detected'] = pk_fp - pk_hit
        report[f'{label}_vl_days_detected'] = vl_fp - vl_hit
    
    # 分布
    report['pk4_days'] = (dfr['pk_score']>=4).sum()
    report['pk3_days'] = (dfr['pk_score']>=3).sum()
    report['vl4_days'] = (dfr['vl_score']>=4).sum()
    report['vl3_days'] = (dfr['vl_score']>=3).sum()
    
    # 漏报明细
    missed_peaks = [i for i in major_p 
        if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['pk_score']>=3)]
    missed_valleys = [i for i in major_v
        if not any(dfr[(dfr['idx']>=i-5)&(dfr['idx']<=i+5)]['vl_score']>=3)]
    report['missed_peaks'] = [(df.iloc[i]['date'].strftime('%Y-%m-%d'), 
                               df.iloc[i]['close'], 
                               df.iloc[i]['bias_20']) for i in missed_peaks]
    report['missed_valleys'] = [(df.iloc[i]['date'].strftime('%Y-%m-%d'), 
                                 df.iloc[i]['close'], 
                                 df.iloc[i]['bias_20']) for i in missed_valleys]
    
    return report, dfr


# ====== 主流程 ======
indices = [
    ('sh000985', '中证全指'),
    ('sh000300', '沪深300'),
    ('sz399006', '创业板指'),
]

all_reports = []
all_data = {}

print("=" * 60)
print("V5 多指数回测结果")
print("=" * 60)

for code, name in indices:
    print(f"\n--- {name}({code}) ---")
    df = fetch_index(code, name)
    report, dfr = run_backtest(name, df)
    all_reports.append(report)
    all_data[name] = (df, dfr)
    
    print(f"数据: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天")
    print(f"波峰: {report['peaks']}, 波谷: {report['valleys']}")
    
    print(f"\n  精度 NEAR(pk>=3,vl>=3):")
    print(f"    峰容差5d: {report['near_pk5']} ({report['near_pk_recall']})")
    print(f"    谷容差5d: {report['near_vl5']} ({report['near_vl_recall']})")
    print(f"    near_peak天数: {report['pk3_days']}天")
    print(f"    near_valley天数: {report['vl3_days']}天")
    
    print(f"  精度 WIDE(pk>=2,vl>=2):")
    print(f"    峰容差5d: {report['wide_pk5']} ({report['wide_pk_recall']})")
    print(f"    谷容差5d: {report['wide_vl5']} ({report['wide_vl_recall']})")
    
    if report['missed_peaks']:
        print(f"  漏报波峰({len(report['missed_peaks'])}个):")
        for d, c, b in report['missed_peaks']:
            print(f"    {d} close={c:.0f} bias20={b:.1f}%")
    if report['missed_valleys']:
        print(f"  漏报波谷({len(report['missed_valleys'])}个):")
        for d, c, b in report['missed_valleys']:
            print(f"    {d} close={c:.0f} bias20={b:.1f}%")

# ====== 对比表 ======
print(f"\n{'='*60}")
print(f"{'指数':<12} {'波峰':<4} {'波谷':<4} {'NEAR峰(3)':<14} {'NEAR谷(3)':<14} {'峰天数':<8} {'谷天数':<8}")
print(f"{'-'*12} {'-'*4} {'-'*4} {'-'*14} {'-'*14} {'-'*8} {'-'*8}")
for r in all_reports:
    print(f"{r['name']:<12} {r['peaks']:<4} {r['valleys']:<4} {r['near_pk_recall']:<14} {r['near_vl_recall']:<14} {r['pk3_days']:<8} {r['vl3_days']:<8}")


# ====== 画图对比 ======
print(f"\n画图...")
BG='#1a1a2e'; TX='#e0e0e0'
fig, axes = plt.subplots(3, 2, figsize=(20, 14), facecolor=BG)
fig.suptitle('V5 Multi-Index Backtest: Confidence Score Results', fontsize=14, color=TX, fontweight='bold', y=0.98)

for idx, (name, (df, dfr)) in enumerate(all_data.items()):
    # 左侧：价格图
    ax1 = axes[idx][0]
    ax1.set_facecolor('#1e1e32')
    ax1.grid(True, alpha=0.15, color='#2a2a3e')
    ax1.plot(dfr['date'], dfr['close'], color='#4fc3f7', lw=1.5, alpha=0.7)
    
    # 真实峰谷
    major_p, major_v = find_major_swings(df)
    ax1.scatter([df.iloc[i]['date'] for i in major_p], [df.iloc[i]['close'] for i in major_p],
                color='#ef5350', s=100, marker='s', zorder=5, edgecolors='white', lw=0.5, label='Peak')
    ax1.scatter([df.iloc[i]['date'] for i in major_v], [df.iloc[i]['close'] for i in major_v],
                color='#66bb6a', s=100, marker='s', zorder=5, edgecolors='white', lw=0.5, label='Valley')
    
    # 预测标记
    c4 = dfr[dfr['pk_score']>=4]
    c3 = dfr[dfr['pk_score']==3]
    v4 = dfr[dfr['vl_score']>=4]
    v3 = dfr[dfr['vl_score']==3]
    ax1.scatter(c4['date'], c4['close'], color='#ff1744', s=35, marker='^', zorder=4, label='Pk(4)')
    ax1.scatter(c3['date'], c3['close'], color='#ff9100', s=20, marker='^', alpha=0.5, zorder=3, label='Pk(3)')
    ax1.scatter(v4['date'], v4['close'], color='#00e676', s=35, marker='v', zorder=4, label='Vl(4)')
    ax1.scatter(v3['date'], v3['close'], color='#69f0ae', s=20, marker='v', alpha=0.5, zorder=3, label='Vl(3)')
    
    ax1.set_title(f'{name}', color=TX, fontsize=11)
    ax1.set_ylabel('Price', color=TX, fontsize=9)
    if idx < 2: plt.setp(ax1.get_xticklabels(), visible=False)
    else: ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    if idx == 0: ax1.legend(loc='upper left', fontsize=7, facecolor='#1e1e32', edgecolor='#333', ncol=2)
    
    # 右侧：评分图
    ax2 = axes[idx][1]
    ax2.set_facecolor('#1e1e32')
    ax2.grid(True, alpha=0.15, color='#2a2a3e')
    ax2.plot(dfr['date'], dfr['pk_score'], color='#ff7043', lw=1, alpha=0.8, label='Peak Score')
    ax2.plot(dfr['date'], -dfr['vl_score'], color='#66bb6a', lw=1, alpha=0.8, label='-Valley Score')
    ax2.axhline(y=3, color='#ffa726', lw=0.6, ls='--', alpha=0.4)
    ax2.axhline(y=-3, color='#81c784', lw=0.6, ls='--', alpha=0.4)
    ax2.fill_between(dfr['date'], -2, 2, alpha=0.06, color='#888')
    ax2.set_ylabel('Score', color=TX, fontsize=9)
    if idx < 2: plt.setp(ax2.get_xticklabels(), visible=False)
    else: ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    if idx == 0: ax2.legend(loc='upper left', fontsize=7, facecolor='#1e1e32', edgecolor='#333')

plt.tight_layout(rect=[0,0,1,0.95])
out=os.path.join(OUTPUT_DIR, 'bias_v5_multi_index.png')
fig.savefig(out, dpi=150, facecolor=BG, bbox_inches='tight')
plt.close()
print(f"图表: {out}")
print(f"\n=== 完成 ===")
