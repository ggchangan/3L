#!/usr/bin/env python3
"""5判定档位示意图 中文版"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import numpy as np
from matplotlib.lines import Line2D
import os

# 注册中文字体
font_paths = [
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc',
]
for fp in font_paths:
    if os.path.exists(fp):
        fm.fontManager.addfont(fp)

# 设置全局字体 - Noto Sans CJK
plt.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

fig, ax = plt.subplots(1, 1, figsize=(14, 7), facecolor='#1a1a2e')
ax.set_facecolor('#1e1e32')

# 生成一条模拟的市场曲线
x = np.linspace(0, 10, 200)
trend = np.sin(x * 0.8) * 30 + 10 + np.sin(x * 2) * 5
trend = trend - trend.min() + 50

ax.plot(x, trend, color='#4fc3f7', linewidth=3, zorder=5, alpha=0.9)

# 找峰谷位置
from scipy.signal import argrelextrema
peak_idx = argrelextrema(trend, np.greater, order=10)[0]
valley_idx = argrelextrema(trend, np.less, order=10)[0]

# 底色分区
for i in range(len(x)-1):
    d2p = min([abs(i - p) for p in peak_idx]) if len(peak_idx) > 0 else 999
    d2v = min([abs(i - v) for v in valley_idx]) if len(valley_idx) > 0 else 999
    
    color = None; az = 0
    if d2p < 1: color = '#ef5350'; az = 0.25
    elif d2p < 3: color = '#ffa726'; az = 0.15
    elif d2v < 1: color = '#26a69a'; az = 0.25
    elif d2v < 3: color = '#66bb6a'; az = 0.15
    
    if color:
        ax.axvspan(x[i], x[i+1], alpha=az, color=color, lw=0)

# 标记波峰
for p in peak_idx:
    ax.scatter(x[p], trend[p], color='#ef5350', s=150, marker='^', zorder=10,
               edgecolors='white', linewidths=1.5)
    ax.annotate('波峰\n(pk>=4)', (x[p], trend[p]),
                xytext=(0, 10), textcoords='offset points',
                ha='center', fontsize=9, color='#ef5350', fontweight='bold')

# 标记波谷
for v in valley_idx:
    ax.scatter(x[v], trend[v], color='#26a69a', s=150, marker='v', zorder=10,
               edgecolors='white', linewidths=1.5)
    ax.annotate('波谷\n(vl>=4)', (x[v], trend[v]),
                xytext=(0, -15), textcoords='offset points',
                ha='center', fontsize=9, color='#26a69a', fontweight='bold')

# 标注偏波峰区域
ax.annotate('偏波峰区域\n(pk_score=3)', (x[peak_idx[0]-5], trend[peak_idx[0]]+4),
            fontsize=9, color='#ffa726', ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e32', edgecolor='#ffa726', alpha=0.8))

# 标注偏波谷区域
ax.annotate('偏波谷区域\n(vl_score=3)', (x[valley_idx[-1]+5], trend[valley_idx[-1]]-8),
            fontsize=9, color='#66bb6a', ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e32', edgecolor='#66bb6a', alpha=0.8))

# 标注波中
mid_x = x[len(x)//2]
ax.annotate('波中 (MIDDLE)\npk<3 且 vl<3\n正常交易区域', (mid_x, trend[len(x)//2]),
            fontsize=10, color='#90a4ae', ha='center',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1e1e32', edgecolor='#90a4ae', alpha=0.8))

# 图例
legend_elements = [
    Line2D([0], [0], marker='^', color='w', markerfacecolor='#ef5350', markersize=12, label='波峰 (pk_score>=4)'),
    Line2D([0], [0], color='#ffa726', linewidth=6, alpha=0.4, label='偏波峰 (pk_score=3)'),
    Line2D([0], [0], color='#2a2a4e', linewidth=6, label='波中 (pk<3 且 vl<3)'),
    Line2D([0], [0], color='#66bb6a', linewidth=6, alpha=0.4, label='偏波谷 (vl_score=3)'),
    Line2D([0], [0], marker='v', color='w', markerfacecolor='#26a69a', markersize=12, label='波谷 (vl_score>=4)'),
]

ax.legend(handles=legend_elements, loc='upper right', fontsize=10,
          facecolor='#1e1e32', edgecolor='#333')

ax.set_xlim(0, 10)
ax.set_ylim(trend.min() - 15, trend.max() + 15)
ax.set_xticks([])
ax.set_yticks([])
ax.set_title('大盘波峰/波谷/波中 五档判定示意', fontsize=18, color='#e0e0e0', fontweight='bold', pad=20)

for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(colors='#e0e0e0', labelsize=9)

plt.tight_layout()
out = '/home/ubuntu/www/files/peak_valley_5_zones_cn.png'
fig.savefig(out, dpi=150, facecolor='#1a1a2e', bbox_inches='tight')
plt.close()
print(f"Saved: {out}")
