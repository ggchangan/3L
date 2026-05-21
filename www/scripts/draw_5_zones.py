#!/usr/bin/env python3
"""Illustration of 5 peak/valley positions"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

fig, ax = plt.subplots(1, 1, figsize=(14, 7), facecolor='#1a1a2e')
ax.set_facecolor('#1e1e32')

x = np.linspace(0, 10, 200)
trend = np.sin(x * 0.8) * 30 + 10 + np.sin(x * 2) * 5
trend = trend - trend.min() + 50

ax.plot(x, trend, color='#4fc3f7', linewidth=3, zorder=5, alpha=0.9)

# Find peaks/valleys using local extrema
from scipy.signal import argrelextrema
peak_idx = argrelextrema(trend, np.greater, order=10)[0]
valley_idx = argrelextrema(trend, np.less, order=10)[0]

# Color zones
for i in range(len(x)-1):
    d2p = min([abs(i - p) for p in peak_idx]) if len(peak_idx) > 0 else 999
    d2v = min([abs(i - v) for v in valley_idx]) if len(valley_idx) > 0 else 999
    
    color = None
    alpha_z = 0
    if d2p < 1:
        color = '#ef5350'; alpha_z = 0.25  # peak
    elif d2p < 3:
        color = '#ffa726'; alpha_z = 0.15  # near_peak
    elif d2v < 1:
        color = '#26a69a'; alpha_z = 0.25  # valley
    elif d2v < 3:
        color = '#66bb6a'; alpha_z = 0.15  # near_valley
    
    if color:
        ax.axvspan(x[i], x[i+1], alpha=alpha_z, color=color, lw=0)

# Mark peaks and valleys
for p in peak_idx:
    ax.scatter(x[p], trend[p], color='#ef5350', s=150, marker='^', zorder=10,
               edgecolors='white', linewidths=1.5)
    ax.annotate('PEAK\n(pk>=4)', (x[p], trend[p]),
                xytext=(0, 10), textcoords='offset points',
                ha='center', fontsize=9, color='#ef5350', fontweight='bold')

for v in valley_idx:
    ax.scatter(x[v], trend[v], color='#26a69a', s=150, marker='v', zorder=10,
               edgecolors='white', linewidths=1.5)
    ax.annotate('VALLEY\n(vl>=4)', (x[v], trend[v]),
                xytext=(0, -15), textcoords='offset points',
                ha='center', fontsize=9, color='#26a69a', fontweight='bold')

# Annotate zones
ax.annotate('near_peak (pk=3)', (x[peak_idx[0]-5], trend[peak_idx[0]]+4),
            fontsize=8, color='#ffa726', ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e32', edgecolor='#ffa726', alpha=0.8))

ax.annotate('near_valley (vl=3)', (x[valley_idx[-1]+5], trend[valley_idx[-1]]-8),
            fontsize=8, color='#66bb6a', ha='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#1e1e32', edgecolor='#66bb6a', alpha=0.8))

mid_x = x[len(x)//2]
ax.annotate('MIDDLE (波中)\npk<3 且 vl<3\n正常交易区域', (mid_x, trend[len(x)//2]),
            fontsize=10, color='#90a4ae', ha='center',
            bbox=dict(boxstyle='round,pad=0.5', facecolor='#1e1e32', edgecolor='#90a4ae', alpha=0.8))

# Legend
legend_elements = [
    Line2D([0], [0], marker='^', color='w', markerfacecolor='#ef5350', markersize=12, label='PEAK (pk_score>=4)'),
    Line2D([0], [0], color='#ffa726', linewidth=6, alpha=0.4, label='near_peak (pk_score=3)'),
    Line2D([0], [0], color='#2a2a4e', linewidth=6, label='MIDDLE (pk_score<3 & vl_score<3)'),
    Line2D([0], [0], color='#66bb6a', linewidth=6, alpha=0.4, label='near_valley (vl_score=3)'),
    Line2D([0], [0], marker='v', color='w', markerfacecolor='#26a69a', markersize=12, label='VALLEY (vl_score>=4)'),
]

ax.legend(handles=legend_elements, loc='upper right', fontsize=9,
          facecolor='#1e1e32', edgecolor='#333')

ax.set_xlim(0, 10)
ax.set_ylim(trend.min() - 15, trend.max() + 15)
ax.set_xticks([])
ax.set_yticks([])
ax.set_title('5判定档位示意图', fontsize=16, color='#e0e0e0', fontweight='bold', pad=20)

for spine in ax.spines.values():
    spine.set_visible(False)
ax.tick_params(colors='#e0e0e0', labelsize=9)

plt.tight_layout()
out = '/home/ubuntu/www/files/peak_valley_5_zones.png'
fig.savefig(out, dpi=150, facecolor='#1a1a2e', bbox_inches='tight')
plt.close()
print(f"Saved: {out}")
