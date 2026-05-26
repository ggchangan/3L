#!/usr/bin/env python3
"""生成中证全指资金流向图（全市场主力净流入+中证全指涨跌幅）
用法: python3 gen_fund_flow_chart.py [date]
      date: YYYY-MM-DD 格式，默认当天
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from backend.config import PUBLIC_DIR
os.environ['TQDM_DISABLE'] = '1'
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

OUTPUT = os.path.join(PUBLIC_DIR, 'charts', 'fund_flow_chart.png')

def get_fund_flow(end_date=None):
    """获取全市场主力资金流向"""
    df = ak.stock_market_fund_flow()
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期').reset_index(drop=True)
    # 主力净流入-净额（元→亿元）
    df['主力净流入_亿'] = df['主力净流入-净额'] / 1e8
    if end_date:
        cutoff = pd.to_datetime(end_date)
        df = df[df['日期'] <= cutoff]
    return df.tail(20).reset_index(drop=True)

def get_zzqz_pct(end_date=None):
    """获取中证全指涨跌幅"""
    df = ak.stock_zh_index_daily_tx(symbol='sh000985')
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    df['change_pct'] = df['close'].pct_change() * 100
    df = df[['date', 'change_pct']]
    if end_date:
        cutoff = pd.to_datetime(end_date)
        df = df[df['date'] <= cutoff]
    return df.tail(20).reset_index(drop=True)

def main(date_arg=None):
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False

    # 转回 YYYY-MM-DD（main接收的是YYYYMMDD或None）
    date_str = None
    if date_arg:
        ds = str(date_arg)
        date_str = f'{ds[:4]}-{ds[4:6]}-{ds[6:8]}' if len(ds) == 8 else ds

    df_flow = get_fund_flow(date_str)
    df_zz = get_zzqz_pct(date_str)

    if df_flow is None or len(df_flow) < 5:
        print("[资金流向] ❌ 资金流向数据不足")
        return

    dates = df_flow['日期']
    net_flow = df_flow['主力净流入_亿'].values

    # 对齐中证全指涨跌幅
    zz_pct = np.zeros(len(dates))
    for i, d in enumerate(dates):
        mask = df_zz['date'] == d
        if mask.any():
            zz_pct[i] = df_zz.loc[mask, 'change_pct'].values[0]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(13, 9),
                                    gridspec_kw={'height_ratios': [2, 1]})
    fig.patch.set_facecolor('#1a1a2e')

    # ---- 上：主力净流入柱状图 ----
    ax1.set_facecolor('#1a1a2e')
    colors = ['#4CAF50' if v < 0 else '#e94560' for v in net_flow]  # 红涨绿跌
    bars = ax1.bar(range(len(dates)), net_flow, color=colors, width=0.6, edgecolor='none')
    ax1.axhline(0, color='#444', linewidth=0.5)

    ax1.set_xticks(range(len(dates)))
    ax1.set_xticklabels([d.strftime('%m-%d') for d in dates], fontsize=8, color='#999')
    ax1.tick_params(colors='#888')
    for spine in ax1.spines.values():
        spine.set_color('#333')

    latest = dates.iloc[-1].strftime('%m-%d')
    ax1.set_title(f'中证全指资金流向（亿元） {latest}',
                  color='white', fontsize=13, fontweight='bold', pad=14)

    # 数值标签
    for i, v in enumerate(net_flow):
        if v > 10:
            ax1.text(i, v/2, f'+{v:.0f}', ha='center', va='center',
                    fontsize=8, color='white', fontweight='bold')
        elif v < -10:
            ax1.text(i, v/2, f'{v:.0f}', ha='center', va='center',
                    fontsize=8, color='white', fontweight='bold')
        elif v > 0:
            ax1.text(i, v+8, f'+{v:.0f}', ha='center', fontsize=7, color='#e94560')
        elif v < 0:
            ax1.text(i, v-8, f'{v:.0f}', ha='center', fontsize=7, color='#4CAF50')

    # ---- 下：中证全指涨跌幅折线 ----
    ax2.set_facecolor('#1a1a2e')
    line_color = '#ffd700'
    ax2.plot(range(len(dates)), zz_pct, color=line_color, linewidth=2, marker='o', markersize=4)
    ax2.axhline(0, color='#444', linewidth=0.5)
    ax2.set_xticks(range(len(dates)))
    ax2.set_xticklabels([d.strftime('%m-%d') for d in dates], fontsize=8, color='#999')
    ax2.set_title('中证全指涨跌幅', color='white', fontsize=11, pad=8)

    for i, v in enumerate(zz_pct):
        offset = 0.15 if v >= 0 else -0.35
        ax2.text(i, v + offset, f'{v:+.2f}%', ha='center', fontsize=7.5, color=line_color)

    ax2.tick_params(colors='#888')
    for spine in ax2.spines.values():
        spine.set_color('#333')

    plt.tight_layout(pad=2.5)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    plt.savefig(OUTPUT, dpi=150, bbox_inches='tight', facecolor='#1a1a2e')
    plt.close()
    print(f"[资金流向] ✅ 已生成: {OUTPUT}")

if __name__ == '__main__':
    date_arg = None
    if len(sys.argv) > 1:
        date_arg = sys.argv[1].replace('-', '')  # YYYY-MM-DD → YYYYMMDD
    main(date_arg)
