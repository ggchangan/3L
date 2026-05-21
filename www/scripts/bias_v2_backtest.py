#!/usr/bin/env python3
"""
波峰波谷新判定函数 V2 - 信号阈值适配大盘
"""
import requests
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os, json
from collections import Counter

OUTPUT_DIR = '/home/ubuntu/www/files'

def judge_market_cycle_v2(df, date_idx=-1):
    """
    三维度波峰波谷判定（V2：信号参数适配大盘）
    Returns: {position, score, details}
    """
    if date_idx == -1:
        date_idx = len(df) - 1
    if date_idx < 60:
        return {'position': 'middle', 'score': 0, 'details': {}}

    r = df.iloc[date_idx]
    bias20 = r['bias_20']

    # ========== 维度1：乖离率绝对值 ==========
    if bias20 > 5.0:
        bias_score = +2
    elif bias20 > 3.0:
        bias_score = +1
    elif bias20 > 1.5:
        bias_score = +0.5
    elif bias20 > -1.5:
        bias_score = 0
    elif bias20 > -4.0:
        bias_score = -0.5
    elif bias20 > -6.0:
        bias_score = -1
    else:
        bias_score = -2

    # ========== 维度2：乖离率变化速度 ==========
    chg_3d = r['bias20_chg_3d']
    chg_5d = r['bias20_chg_5d']

    if chg_3d > 2.0:
        mom_score = +1.5
    elif chg_3d > 1.0:
        mom_score = +1
    elif chg_3d > 0.3:
        mom_score = +0.3
    elif chg_3d > -0.3:
        mom_score = 0
    elif chg_3d > -1.0:
        mom_score = -0.3
    elif chg_3d > -2.0:
        mom_score = -1
    else:
        mom_score = -1.5

    # ========== 维度3：量价信号（大盘版） ==========
    vol_ratio = r['volume'] / r['vol_ma20'] if r['vol_ma20'] > 0 else 1
    body_pct = abs(r['close'] - r['open']) / r['open'] * 100
    range_pct = (r['high'] - r['low']) / r['open'] * 100
    lower_shadow_pct = (min(r['open'], r['close']) - r['low']) / r['open'] * 100
    upper_shadow_pct = (r['high'] - max(r['open'], r['close'])) / r['open'] * 100
    
    i = date_idx
    last3 = df.iloc[max(0,i-2):i+1]
    last5 = df.iloc[max(0,i-4):i+1]
    
    signal_score = 0
    signals = []

    # --- 波谷信号（供应衰竭）---
    
    # 恐慌出清：日跌>1.5% + 放量1.3x + 下影线显著
    if (r['close'] - r['open']) / r['open'] < -0.015:
        if vol_ratio > 1.3 and lower_shadow_pct > body_pct * 1.5 and lower_shadow_pct > 0.5:
            signal_score -= 1.5
            signals.append('panic')

    # 缩量衰竭：量<70%MA20 + 窄幅<2% + 还在跌但跌不动了
    if vol_ratio < 0.7 and range_pct < 2.0:
        # 连续2天下跌后缩量
        if len(last3) >= 3 and all(last3.iloc[j]['close'] < last3.iloc[j-1]['close'] for j in range(1, len(last3))):
            signal_score -= 0.8
            signals.append('shrink_fail')
        elif bias20 < -2:
            signal_score -= 0.5
            signals.append('low_vol_narrow')

    # 地量：量<50%MA20
    if vol_ratio < 0.5 and range_pct < 1.5:
        signal_score -= 0.5
        signals.append('extreme_low_vol')

    # 连续阴跌后出现下影线（可能见底）
    if range_pct > 2.0 and lower_shadow_pct > 1.0:
        if bias20 < -2 and vol_ratio > 1.0:
            signal_score -= 0.8
            signals.append('hammer')

    # --- 波峰信号（需求透支）---

    # 加速：连续3阳 + 量放大
    if len(last5) >= 5:
        close_up = sum(1 for j in range(1, len(last5)) 
                      if last5.iloc[j]['close'] > last5.iloc[j-1]['close'])
        if close_up >= 4 and vol_ratio > 1.2:
            signal_score += 1.2
            signals.append('accel')
        elif close_up >= 3 and vol_ratio > 1.5:
            signal_score += 1.0
            signals.append('accel_mod')

    # 放量滞涨：高量 + 小实体
    if vol_ratio > 1.3 and body_pct < 0.8 and bias20 > 1:
        signal_score += 0.8
        signals.append('churning')

    # 量价背离：价创新高 + 量缩小
    if len(last5) >= 5:
        if r['close'] == last5['close'].max() and vol_ratio < 1.0:
            if bias20 > 1.5:
                signal_score += 0.8
                signals.append('divergence')

    # 长上影放量（冲高回落）
    if range_pct > 2.5 and upper_shadow_pct > 1.5 and vol_ratio > 1.2:
        if bias20 > 1:
            signal_score += 0.8
            signals.append('long_upper')
    
    # ========== 综合评分 ==========
    final_score = bias_score * 0.35 + mom_score * 0.30 + signal_score * 0.35
    
    # 极端乖离率自动升级
    if bias20 > 8:
        final_score = max(final_score, 3.0)
    elif bias20 < -8:
        final_score = min(final_score, -3.0)

    # 位置映射（降低阈值）
    if final_score >= 2.0:
        position = 'peak'
    elif final_score >= 0.8:
        position = 'near_peak'
    elif final_score <= -2.0:
        position = 'valley'
    elif final_score <= -0.8:
        position = 'near_valley'
    else:
        position = 'middle'

    return {
        'position': position,
        'score': round(final_score, 2),
        'details': {
            'bias_score': round(bias_score, 2),
            'mom_score': round(mom_score, 2),
            'signal_score': round(signal_score, 2),
            'bias20': round(bias20, 2),
            'chg_3d': round(chg_3d, 2),
            'vol_ratio': round(vol_ratio, 2),
            'signals': signals
        }
    }


# ============================================================
# 回测
# ============================================================
print("=== 波峰波谷新判定V2 回测 ===")

# --- 获取数据 ---
url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,1000,qfq'
r = requests.get(url, headers={
    'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'
})
data = r.json()
raw = data['data']['sh000985']['day']

rows = []
for d in raw:
    rows.append({'date': d[0], 'open': float(d[1]), 'close': float(d[2]),
                 'high': float(d[3]), 'low': float(d[4]), 'volume': float(d[5])})

df = pd.DataFrame(rows)
df['date'] = pd.to_datetime(df['date'])
df = df.sort_values('date').reset_index(drop=True)

for ma in [5, 10, 20, 60]:
    df[f'MA{ma}'] = df['close'].rolling(ma).mean()
    df[f'bias_{ma}'] = (df['close'] - df[f'MA{ma}']) / df[f'MA{ma}'] * 100

df['bias20_chg_3d'] = df['bias_20'].diff(3)
df['bias20_chg_5d'] = df['bias_20'].diff(5)
df['vol_ma20'] = df['volume'].rolling(20).mean()

print(f"数据: {df['date'].iloc[0].date()} ~ {df['date'].iloc[-1].date()}, {len(df)}天")

# --- 真实峰谷（波幅>8%才算重要） ---
def find_swing_points(series, window=20):
    peaks = pd.Series(False, index=series.index)
    valleys = pd.Series(False, index=series.index)
    for i in range(window, len(series) - window):
        seg = series.iloc[i-window:i+window+1]
        if series.iloc[i] == max(seg): peaks.iloc[i] = True
        if series.iloc[i] == min(seg): valleys.iloc[i] = True
    return peaks, valleys

peaks, valleys = find_swing_points(df['close'], window=20)
true_peaks = set(df[peaks].index.tolist())
true_valleys = set(df[valleys].index.tolist())

# 波幅过滤
major_peaks_set = set()
for i in true_peaks:
    prev_v = max([j for j in true_valleys if j < i], default=None)
    if prev_v is not None:
        change = (df.iloc[i]['close'] - df.iloc[prev_v]['close']) / df.iloc[prev_v]['close'] * 100
        if change > 8:
            major_peaks_set.add(i)

major_valleys_set = set()
for i in true_valleys:
    prev_p = max([j for j in true_peaks if j < i], default=None)
    if prev_p is not None:
        change = (df.iloc[prev_p]['close'] - df.iloc[i]['close']) / df.iloc[prev_p]['close'] * 100
        if change > 8:
            major_valleys_set.add(i)

print(f"重要波峰: {len(major_peaks_set)}, 重要波谷: {len(major_valleys_set)}")

# --- 逐日回测 ---
results = []
for i in range(120, len(df)):
    judge = judge_market_cycle_v2(df, i)
    results.append({
        'idx': i,
        'date': df.iloc[i]['date'],
        'close': df.iloc[i]['close'],
        'position': judge['position'],
        'score': judge['score'],
        'is_true_peak': i in major_peaks_set,
        'is_true_valley': i in major_valleys_set,
        'pred_peak': judge['position'] in ('peak', 'near_peak'),
        'pred_valley': judge['position'] in ('valley', 'near_valley'),
        'details': judge['details']
    })

df_result = pd.DataFrame(results)
print(f"回测天数: {len(df_result)}")

# --- 评估指标 ---
def calc_metrics(y_true, y_pred, label):
    tp = sum(1 for a, b in zip(y_true, y_pred) if a and b)
    fp = sum(1 for a, b in zip(y_true, y_pred) if not a and b)
    fn = sum(1 for a, b in zip(y_true, y_pred) if a and not b)
    tn = sum(1 for a, b in zip(y_true, y_pred) if not a and b)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
    accuracy = (tp + tn) / (tp + tn + fp + fn) if (tp + tn + fp + fn) > 0 else 0
    return {'TP': tp, 'FP': fp, 'FN': fn, 'TN': tn,
            'precision': round(precision*100,1), 'recall': round(recall*100,1),
            'F1': round(f1*100,1), 'accuracy': round(accuracy*100,1)}

print(f"\n=== 波峰检测 ===")
peak_m = calc_metrics(df_result['is_true_peak'], df_result['pred_peak'], 'Peak')
for k,v in peak_m.items(): print(f"  {k}: {v}")

print(f"\n=== 波谷检测 ===")
valley_m = calc_metrics(df_result['is_true_valley'], df_result['pred_valley'], 'Valley')
for k,v in valley_m.items(): print(f"  {k}: {v}")

# 容差±5天
tp_peak_tol = sum(1 for pi in major_peaks_set 
    if any(df_result[(df_result['idx']>=pi-5)&(df_result['idx']<=pi+5)]['pred_peak']))
tp_valley_tol = sum(1 for vi in major_valleys_set
    if any(df_result[(df_result['idx']>=vi-5)&(df_result['idx']<=vi+5)]['pred_valley']))

print(f"\n=== 容差±5天 ===")
print(f"波峰命中: {tp_peak_tol}/{len(major_peaks_set)} ({tp_peak_tol/max(1,len(major_peaks_set))*100:.0f}%)")
print(f"波谷命中: {tp_valley_tol}/{len(major_valleys_set)} ({tp_valley_tol/max(1,len(major_valleys_set))*100:.0f}%)")

# --- 位置分布 ---
print(f"\n=== 位置分布 ===")
for pos in ['valley','near_valley','middle','near_peak','peak']:
    cnt = (df_result['position']==pos).sum()
    print(f"  {pos}: {cnt}天 ({cnt/len(df_result)*100:.1f}%)")

# --- 维度贡献 ---
print(f"\n=== 信号频率 ===")
all_sigs = Counter()
for _, row in df_result.iterrows():
    all_sigs.update(row['details']['signals'])
for sig, cnt in all_sigs.most_common():
    print(f"  {sig}: {cnt}次 ({cnt/len(df_result)*100:.1f}%)")

# --- 错误分析 ---
print(f"\n=== 波峰检测错误分析 ===")
# 误报的天
false_peaks = df_result[df_result['pred_peak'] & ~df_result['is_true_peak']]
if len(false_peaks) > 0:
    print(f"误报 {len(false_peaks)} 天, 平均bias20={false_peaks['details'].apply(lambda x:x['bias20']).mean():.1f}%")
    # 误报集中在哪
    for _, row in false_peaks.iloc[::max(1,len(false_peaks)//8)].iterrows():
        d = row['details']
        print(f"  {row['date'].date()} bias={d['bias20']:.1f}% score={row['score']:.1f} sig={d['signals']}")

# 漏报
missed_peaks = [i for i in major_peaks_set if not any(df_result[(df_result['idx']>=i-5)&(df_result['idx']<=i+5)]['pred_peak'])]
if missed_peaks:
    print(f"\n漏报波峰 {len(missed_peaks)} 个:")
    for mi in missed_peaks:
        r = df.iloc[mi]
        print(f"  {r['date'].date()} close={r['close']:.0f} bias20={r['bias_20']:.1f}%")

# === 画图 ===
print(f"\n生成图表...")
BG = '#1a1a2e'
TX = '#e0e0e0'

fig = plt.figure(figsize=(20, 16), facecolor=BG)
fig.suptitle('Bias V2 Backtest: 中证全指(000985) Score & Signals', 
             fontsize=14, color=TX, fontweight='bold', y=0.98)

# 图1：价格+真实峰谷+预测
ax1 = fig.add_subplot(5,1,(1,2), facecolor='#1e1e32')
ax1.grid(True, alpha=0.15, color='#2a2a3e')
ax1.plot(df_result['date'], df_result['close'], color='#4fc3f7', lw=1.5, alpha=0.7)

# 真实峰谷
ax1.scatter([df.iloc[i]['date'] for i in major_peaks_set], [df.iloc[i]['close'] for i in major_peaks_set],
            color='#ef5350', s=130, marker='s', zorder=5, edgecolors='white', lw=0.5, label='True Peak')
ax1.scatter([df.iloc[i]['date'] for i in major_valleys_set], [df.iloc[i]['close'] for i in major_valleys_set],
            color='#66bb6a', s=130, marker='s', zorder=5, edgecolors='white', lw=0.5, label='True Valley')

# 预测（小半透明点）
pk = df_result[df_result['pred_peak']]
vl = df_result[df_result['pred_valley']]
ax1.scatter(pk['date'], pk['close'], color='#ffa726', s=15, alpha=0.25, zorder=3, label='Pred Peak')
ax1.scatter(vl['date'], vl['close'], color='#81c784', s=15, alpha=0.25, zorder=3, label='Pred Valley')
ax1.set_ylabel('Price', color=TX, fontsize=10)
ax1.legend(loc='upper left', fontsize=8, facecolor='#1e1e32', edgecolor='#333')
plt.setp(ax1.get_xticklabels(), visible=False)

# 图2：评分
ax2 = fig.add_subplot(5,1,3, facecolor='#1e1e32')
ax2.grid(True, alpha=0.15, color='#2a2a3e')
ax2.plot(df_result['date'], df_result['score'], color='#ce93d8', lw=1.5, label='Score')
for y, c in [(0.8,'#ffa726'),(-0.8,'#66bb6a'),(2.0,'#ef5350'),(-2.0,'#66bb6a')]:
    ax2.axhline(y=y, color=c, lw=0.6, ls='--', alpha=0.4)
ax2.fill_between(df_result['date'], -0.8, 0.8, alpha=0.08, color='#888')
ax2.text(df_result['date'].iloc[5], 2.1, 'PEAK', fontsize=8, color='#ef5350')
ax2.text(df_result['date'].iloc[5], -2.3, 'VALLEY', fontsize=8, color='#66bb6a')
ax2.set_ylabel('Score', color=TX, fontsize=10)
ax2.legend(loc='upper left', fontsize=8, facecolor='#1e1e32', edgecolor='#333')
plt.setp(ax2.get_xticklabels(), visible=False)

# 图3：三维度（MA10平滑）
ax3 = fig.add_subplot(5,1,4, facecolor='#1e1e32')
ax3.grid(True, alpha=0.15, color='#2a2a3e')
w=10
ax3.plot(df_result['date'], df_result['details'].apply(lambda x:x['bias_score']).rolling(w).mean(),
         color='#4fc3f7', lw=1, alpha=0.7, label='Bias')
ax3.plot(df_result['date'], df_result['details'].apply(lambda x:x['mom_score']).rolling(w).mean(),
         color='#ffa726', lw=1, alpha=0.7, label='Momentum')
ax3.plot(df_result['date'], df_result['details'].apply(lambda x:x['signal_score']).rolling(w).mean(),
         color='#ab47bc', lw=1, alpha=0.7, label='Signal')
ax3.axhline(y=0, color='#666', lw=0.8, ls='--', alpha=0.5)
ax3.set_ylabel('Dim (MA10)', color=TX, fontsize=10)
ax3.legend(loc='upper left', fontsize=8, facecolor='#1e1e32', edgecolor='#333')
plt.setp(ax3.get_xticklabels(), visible=False)

# 图4：bias20 + 信号标记
ax4 = fig.add_subplot(5,1,5, facecolor='#1e1e32')
ax4.grid(True, alpha=0.15, color='#2a2a3e')
ax4.plot(df_result['date'], df_result['details'].apply(lambda x:x['bias20']),
         color='#4fc3f7', lw=1, alpha=0.6, label='Bias20%')
ax4.axhline(y=0, color='#666', lw=0.8, ls='--', alpha=0.5)
for y in [3, -4]: ax4.axhline(y=y, color='#888', lw=0.5, ls=':', alpha=0.3)

# 信号点
sig_colors = {'panic':'#ef5350','shrink_fail':'#66bb6a','extreme_low_vol':'#4db6ac',
              'hammer':'#26a69a','accel':'#ff7043','accel_mod':'#ffa726',
              'churning':'#ff8a65','divergence':'#ab47bc','long_upper':'#ec407a'}
for sig, color in sig_colors.items():
    sig_pts = df_result[df_result['details'].apply(lambda x: sig in x.get('signals',[]))]
    if len(sig_pts) > 0:
        ax4.scatter(sig_pts['date'], sig_pts['details'].apply(lambda x:x['bias20']),
                   color=color, s=12, alpha=0.6, label=sig)

ax4.set_ylabel('Bias20%', color=TX, fontsize=10)
ax4.set_ylim(-15, 15)
ax4.legend(loc='upper left', fontsize=6, facecolor='#1e1e32', edgecolor='#333', ncol=3)
ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=3))

plt.tight_layout(rect=[0,0,1,0.96])
out = os.path.join(OUTPUT_DIR, 'bias_v2_backtest_chart.png')
fig.savefig(out, dpi=150, facecolor=BG, bbox_inches='tight')
plt.close()
print(f"图表: {out}")
print(f"\n=== 完成 ===")
