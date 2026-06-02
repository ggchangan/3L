#!/usr/bin/env python3
"""更新关键点颜色映射 + 上涨趋势EMA支撑线"""
import re

with open('server/backend/services/stock_chart_service.py', 'r') as f:
    content = f.read()

# 1. 更新颜色映射
old1 = "clr_map = {'突': '#2196f3', '量': '#ff9800', '前高': '#ff9800', '前低': '#4caf50'}"
new1 = "clr_map = {'突': '#2196f3', '前高': '#ff9800', '前低': '#4caf50', '放↑': '#ff5722', '放↓': '#9c27b0', '缩': '#607d8b', '↯': '#ff9800'}"
c1 = content.count(old1)
print(f'颜色映射: {c1} occurances')
if c1 == 1:
    content = content.replace(old1, new1)

# 2. 上涨趋势EMA支撑线（接在压力线之后）
# 找 # 5j. 压力线 和 # 5k 之间的内容
old2 = """    # 5j. 压力线
    if hi_15:
        ry = py_price(hi_15)
        sv.append(
            f'<line x1=\\\"{pl}\\\" y1=\\\"{ry}\\\" x2=\\\"{W - pr}\\\" y2=\\\"{ry}\\\" '
            f'stroke=\\\"#f44336\\\" stroke-width=\\\"1.5\\\" stroke-dasharray=\\\"6,3\\\" opacity=\\\"0.7\\\"/>'
        )
        sv.append(
            f'<text x=\\\"{pl + 4}\\\" y=\\\"{ry - 4}\\\" font-family=\\\"sans-serif\\\" '
            f'font-size=\\\"9\\\" fill=\\\"#f44336\\\" font-weight=\\\"bold\\\">'
            f'压力 {hi_15:.2f}</text>'
        )

    # 5k. 今日蜡烛"""

new2 = """    # 5j. 压力线
    if hi_15:
        ry = py_price(hi_15)
        sv.append(
            f'<line x1=\\\"{pl}\\\" y1=\\\"{ry}\\\" x2=\\\"{W - pr}\\\" y2=\\\"{ry}\\\" '
            f'stroke=\\\"#f44336\\\" stroke-width=\\\"1.5\\\" stroke-dasharray=\\\"6,3\\\" opacity=\\\"0.7\\\"/>'
        )
        sv.append(
            f'<text x=\\\"{pl + 4}\\\" y=\\\"{ry - 4}\\\" font-family=\\\"sans-serif\\\" '
            f'font-size=\\\"9\\\" fill=\\\"#f44336\\\" font-weight=\\\"bold\\\">'
            f'压力 {hi_15:.2f}</text>'
        )

    # 5j2. 上涨趋势EMA支撑线
    if stock_structure == '上涨趋势' and e10 and len(e10) > 5:
        e10v = e10[-1]
        if e10v:
            ey = py_price(e10v)
            sv.append(
                f'<line x1=\\\"{pl}\\\" y1=\\\"{ey}\\\" x2=\\\"{W - pr}\\\" y2=\\\"{ey}\\\" '
                f'stroke=\\\"#2196f3\\\" stroke-width=\\\"1.0\\\" stroke-dasharray=\\\"3,3\\\" opacity=\\\"0.5\\\"/>'
            )
            sv.append(
                f'<text x=\\\"{W - pr - 4}\\\" y=\\\"{ey - 4}\\\" font-family=\\\"sans-serif\\\" '
                f'font-size=\\\"8\\\" fill=\\\"#2196f3\\\">'
                f'EMA10 {e10v:.2f}</text>'
            )

    # 5k. 今日蜡烛"""

c2 = content.count(old2)
print(f'EMA支撑线: {c2} occurances')
if c2 == 1:
    content = content.replace(old2, new2)
    print('替换完成')
else:
    print(f'Unexpected count: {c2}')
    # Fallback: try without escaped quotes
    old2b = old2.replace('\\"', '"')
    c2b = content.count(old2b)
    print(f'Without escape: {c2b}')
    if c2b == 1:
        new2b = new2.replace('\\"', '"')
        content = content.replace(old2b, new2b)
        print('替换完成(无转义)')

with open('server/backend/services/stock_chart_service.py', 'w') as f:
    f.write(content)
print('文件已保存')
