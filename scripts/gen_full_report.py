#!/usr/bin/env python3
"""波峰波谷判断 + 完整报告HTML生成"""
import json, os, glob

DATA = "/home/ubuntu/data/3l/all_stocks_60d.json"
OUT = "/home/ubuntu/data/3l/simulation/v3"
CHART_DIR = os.path.join(OUT, "charts")

with open(DATA) as f:
    raw = json.load(f)
ALL = raw["stocks"]

KL = lambda c: next((stocks[c] for sec,stocks in ALL.items() if c in stocks), None)
DI = lambda d,kl: next((i for i,k in enumerate(kl) if k["date"]==d), -1)

# ═══ 波峰波谷判断 ═══
def judge_peak_trough(date_str):
    """综合评分法判断大盘波峰波谷"""
    # 用所有自选股均值近似大盘
    prices = []; mas = []; vols = []; bodies = []
    
    for sec, stocks in ALL.items():
        for code in stocks:
            kl = KL(code)
            if not kl: continue
            idx = DI(date_str, kl)
            if idx < 20: continue
            C = [k["close"] for k in kl]
            V = [k["volume"] for k in kl]
            
            prices.append(C[idx])
            ma20 = sum(C[idx-19:idx+1]) / 20
            mas.append(ma20)
            
            # 量比
            vs = sorted([k["volume"] for k in kl[idx-29:idx+1]])
            lb = sum(vs[:max(3, len(vs)//5)]) / max(3, len(vs)//5)
            vols.append(V[idx] / lb if lb > 0 else 1)
            
            # K线实体
            body = abs(C[idx] - kl[idx]["open"])
            avg_body = sum(abs(C[j] - kl[j]["open"]) for j in range(idx-4, idx+1)) / 5
            bodies.append(body / avg_body if avg_body > 0 else 1)
    
    avg_price = sum(prices) / len(prices) if prices else 0
    avg_ma20 = sum(mas) / len(mas) if mas else 0
    avg_vol = sum(vols) / len(vols) if vols else 0
    avg_body_ratio = sum(bodies) / len(bodies) if bodies else 0
    
    score = 0
    details = {}
    
    # ① 趋势结构
    if avg_price > avg_ma20 * 1.05:
        score += 1; details["趋势"] = "+1 (价格>MA20 5%以上)"
    elif avg_price < avg_ma20 * 0.95:
        score -= 1; details["趋势"] = "-1 (价格<MA20 5%以下)"
    else:
        details["趋势"] = "0 (价格在MA20附近)"
    
    # ② 量能位置
    if avg_vol > 3:
        score += 1; details["量能"] = f"+1 (高潮量比{avg_vol:.2f}x)"
    elif avg_vol < 1.3:
        score -= 1; details["量能"] = f"-1 (地量量比{avg_vol:.2f}x)"
    else:
        details["量能"] = f"0 (正常量比{avg_vol:.2f}x)"
    
    # ③ 量价形态：检查加速和恐慌
    has_accel = False; has_panic = False
    for sec, stocks in ALL.items():
        for code in stocks:
            kl = KL(code)
            if not kl: continue
            idx = DI(date_str, kl)
            if idx < 5: continue
            C = [k["close"] for k in kl]
            V = [k["volume"] for k in kl]
            # 加速：近3天涨幅扩大+量放大
            if idx >= 3:
                chgs = [(C[j]-C[j-1])/C[j-1]*100 for j in range(idx-2, idx+1)]
                if all(chgs[j] > 0 and chgs[j] > chgs[j-1] for j in range(1,3)):
                    if V[idx] > sum(V[idx-4:idx+1])/5:
                        has_accel = True
                        break
            # 恐慌：放量暴跌+下影线
            if C[idx] < kl[idx]["open"] and V[idx] > sum(V[idx-4:idx+1])/5*1.5:
                low_pct = (kl[idx]["low"] - C[idx]) / C[idx]
                if abs(low_pct) < 0.03:  # 远离低点收，有下影线
                    has_panic = True
    
    if has_accel:
        score += 1; details["形态"] = "+1 (检测到加速信号)"
    elif has_panic:
        score -= 1; details["形态"] = "-1 (检测到恐慌信号)"
    else:
        details["形态"] = "0 (无异常信号)"
    
    # ④ 波动率
    if avg_body_ratio > 1.1:
        score += 1; details["波动"] = f"+1 (实体放大{avg_body_ratio:.2f}x)"
    elif avg_body_ratio < 0.9:
        score -= 1; details["波动"] = f"-1 (实体收窄{avg_body_ratio:.2f}x)"
    else:
        details["波动"] = f"0 (实体正常{avg_body_ratio:.2f}x)"
    
    # 解读
    if score >= 3: result = "波峰区域"
    elif score >= 1: result = "偏波峰"
    elif score <= -3: result = "波谷区域"
    elif score <= -1: result = "偏波谷"
    else: result = "波中"
    
    pos_strategy = {
        "波谷区域": "重仓80%-100%：止损后主动补回",
        "偏波谷": "偏进攻：留意买点，适当加重仓位",
        "波中": "正常交易：按买卖点信号操作",
        "偏波峰": "偏防守：收紧止盈，卖出可不补",
        "波峰区域": "控仓：可买可不买不买，卖出不补",
    }
    
    return result, score, details, pos_strategy.get(result, "")

# ═══ 执行判断 ═══
result, score, details, strategy = judge_peak_trough("20260407")
print(f"波峰波谷判断 (2026-04-07):")
print(f"  评分: {score} → {result}")
print(f"  策略: {strategy}")
for k, v in details.items():
    print(f"  {k}: {v}")

# ═══ 生成报告 ═══
# SVG→PNG
for svg_file in glob.glob(os.path.join(CHART_DIR, "*.svg")):
    png_file = svg_file.replace(".svg", ".png")
    os.system(f"rsvg-convert -f png -o '{png_file}' '{svg_file}' 2>/dev/null")

# 生成HTML
charts_html = ""
chart_order = [
    ("300503", "昊志机电", "机器人"),
    ("300054", "鼎龙股份", "半导体"),
    ("301128", "强瑞技术", "算力"),
    ("688131", "皓元医药", "创新药"),
    ("002192", "融捷股份", "资源股"),
    ("603716", "塞力医疗", "AI应用"),
    ("688010", "福光股份", "商业航天"),
]
for code, name, sector in chart_order:
    svg_path = os.path.join(CHART_DIR, f"{code}_{name}.svg")
    if os.path.exists(svg_path):
        with open(svg_path) as f:
            svg_content = f.read()
        # 去除xml声明和svg标签外的内容
        svg_content = svg_content.replace('<?xml version="1.0" encoding="UTF-8"?>', '')
        charts_html += f'<div style="margin:8px 0;border:1px solid #e5e7eb;border-radius:4px;padding:4px;">{svg_content}</div>\n'

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Noto Sans CJK SC','WenQuanYi Zen Hei',sans-serif;font-size:11px;color:#1a1a1a;padding:20px;line-height:1.7}}
.report-header{{text-align:center;margin-bottom:14px}}
.report-title{{font-size:20px;font-weight:bold;color:#2563eb}}
.report-subtitle{{font-size:14px;color:#666;margin-top:2px}}
.report-divider{{border:none;border-top:2px solid #2563eb;opacity:0.4;margin:6px 0}}
.part{{margin-top:18px}}
.part-header{{font-size:15px;font-weight:bold;color:#1e40af;background:#eff6ff;padding:5px 10px;border-radius:4px;margin-bottom:8px;border-left:4px solid #2563eb}}
.part-number{{display:inline-block;background:#2563eb;color:white;border-radius:50%;width:22px;height:22px;text-align:center;line-height:22px;font-size:12px;margin-right:6px}}
table{{width:100%;border-collapse:collapse;font-size:11px;margin:6px 0}}
th{{background:#f3f4f6;padding:4px 5px;text-align:center;font-weight:bold;border-bottom:1.5px solid #d1d5db;white-space:nowrap}}
td{{padding:3px 5px;border-bottom:1px solid #f0f0f0;text-align:center;white-space:nowrap}}
tr:last-child td{{border-bottom:2px solid #d1d5db}}
td.left,th.left{{text-align:left}}
.pos{{color:#16a34a;font-weight:bold}}
.neg{{color:#dc2626;font-weight:bold}}
.kpi-group{{margin:6px 0}}
.kpi-row{{display:inline-block;margin:3px 12px 3px 0;background:#f9fafb;padding:4px 10px;border-radius:4px}}
.kpi-label{{font-size:10px;color:#888}}
.kpi-value{{font-size:16px;font-weight:bold}}
.highlight-box{{background:#f0fdf4;border:1px solid #86efac}}
.detail-box{{background:#fafafa;border:1px solid #e5e7eb;border-radius:4px;padding:8px 12px;margin:6px 0;font-size:11px}}
.tag-main{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#dbeafe;color:#1e40af}}
.tag-nonmain{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#f3f4f6;color:#666}}
.tag-hold{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#e0e7ff;color:#3730a3}}
.tag-left{{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;background:#fef3c7;color:#92400e}}
</style></head>
<body>

<div class="report-header">
    <div class="report-title">v3 第1周交易报告</div>
    <div class="report-subtitle">2026-04-07 ~ 2026-04-10 | 含波峰波谷判断+关键点图</div>
    <hr class="report-divider">
</div>

<!-- Part 0: 波峰波谷判断 -->
<div class="part">
<div class="part-header"><span class="part-number">0</span> 大盘波峰波谷判断</div>
<div class="kpi-group">
    <span class="kpi-row" style="background:#{"f0fdf4" if score>=0 else "fef2f2"}"><span class="kpi-label">综合评分</span><br><span class="kpi-value" style="color:{"#16a34a" if score>=0 else "#dc2626"}">{score}分</span></span>
    <span class="kpi-row"><span class="kpi-label">判断结果</span><br><span class="kpi-value">{result}</span></span>
    <span class="kpi-row" class="highlight-box"><span class="kpi-label">仓位策略</span><br><span class="kpi-value">{strategy}</span></span>
</div>
<table>
<tr><th>维度</th><th>评分</th><th class="left">判断依据</th></tr>
<tr><td>① 趋势结构</td><td>{details["趋势"].split()[0]}</td><td class="left">{details["趋势"]}</td></tr>
<tr><td>② 量能位置</td><td>{details["量能"].split()[0]}</td><td class="left">{details["量能"]}</td></tr>
<tr><td>③ 量价形态</td><td>{details["形态"].split()[0]}</td><td class="left">{details["形态"]}</td></tr>
<tr><td>④ 波动率</td><td>{details["波动"].split()[0]}</td><td class="left">{details["波动"]}</td></tr>
</table>
<div class="detail-box">
    <b>综合评分法v1</b>（skill:market-peak-trough），4维度评分。-4~+4：≤-3=波谷区域重仓80-100%，≥+3=波峰区域控仓。<br>
    <b>4/7判断：</b>总评分{score} → {result}。{strategy}
</div>
</div>

<!-- Part 1-6: 原有的6部分 -->
<div class="part">
<div class="part-header"><span class="part-number">1</span> 大盘判强弱</div>
<div class="kpi-group">
    <span class="kpi-row"><span class="kpi-label">大盘阶段</span><br><span class="kpi-value">低迷期</span></span>
    <span class="kpi-row"><span class="kpi-label">平均量比</span><br><span class="kpi-value">1.33x</span></span>
</div>
<div class="detail-box">
    大盘判强弱用于<b>选择买点类型</b>（低迷期适合恐慌/反转买点），不用于算仓位系数。<br>
    仓位由<b>波峰波谷</b>决定（当前{result}，{strategy}）。
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">2</span> 主线/非主线判定</div>
<div class="detail-box">
    按20日涨幅排序：创新药+19.1% > 新能源+2.9% > 算力+2.3% > 半导体-4.3% > 机器人-8.0% > 资源股-10.3% > 商业航天-11.4% > AI应用-14.2%
</div>
<table><tr><th>主线方向</th><th>系数</th><th>非主线方向</th><th>系数</th></tr>
<tr><td>算力·半导体·机器人·AI应用</td><td class="pos">×1.2</td><td>创新药·新能源·资源股·商业航天</td><td>×0.8</td></tr>
</table>
</div>

<div class="part">
<div class="part-header"><span class="part-number">3</span> 选股过程与仓位计算</div>
<div class="detail-box">
    <b>选股条件：</b>非下降趋势(MA10斜率) + 收MA20上方 + 缩量 + 回踩支撑 + 涨幅<4%<br>
    <b>结构过滤：</b>239只中上升89只/震荡19只/下降139只剔除 → 25只通过中继买点 → 按方向去重选7只<br>
    <b>个股仓位：</b>正常5%，特别看好10%。单方向上限20%。
</div>
<table>
<tr><th>#</th><th class="left">股票</th><th>方向</th><th>走势</th><th>仓位</th><th>缩量</th><th>波段</th><th>行业</th></tr>
<tr><td>1</td><td class="left">昊志机电</td><td>机器人</td><td><span class="tag-hold">上升趋势</span></td><td class="pos">10.0%</td><td>优秀</td><td>鱼身</td><td><span class="tag-main">主线</span></td></tr>
<tr><td>2</td><td class="left">皓元医药</td><td>创新药</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>优秀</td><td>鱼身</td><td><span class="tag-nonmain">非主线</span></td></tr>
<tr><td>3</td><td class="left">融捷股份</td><td>资源股</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>优秀</td><td>鱼身</td><td><span class="tag-nonmain">非主线</span></td></tr>
<tr><td>4</td><td class="left">鼎龙股份</td><td>半导体</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>标准</td><td>鱼身</td><td><span class="tag-main">主线</span></td></tr>
<tr><td>5</td><td class="left">强瑞技术</td><td>算力</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>标准</td><td>鱼身</td><td><span class="tag-main">主线</span></td></tr>
<tr><td>6</td><td class="left">塞力医疗</td><td>AI应用</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>不足</td><td>鱼头</td><td><span class="tag-main">主线</span></td></tr>
<tr><td>7</td><td class="left">福光股份</td><td>商业航天</td><td><span class="tag-hold">上升趋势</span></td><td>5.0%</td><td>优秀</td><td>鱼头</td><td><span class="tag-nonmain">非主线</span></td></tr>
</table>
</div>

<div class="part">
<div class="part-header"><span class="part-number">4</span> 交易明细</div>
<table>
<tr><th>日期</th><th>操作</th><th class="left">名称</th><th>方向</th><th>数量</th><th>单价</th><th>金额</th><th>个股仓位</th><th>总仓位*</th><th class="left">理由</th></tr>
<tr><td>04-07</td><td>买入</td><td class="left">昊志机电</td><td>机器人</td><td>1,900</td><td>52.31</td><td>99,389</td><td>10.0%</td><td>10.0%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">皓元医药</td><td>创新药</td><td>700</td><td>70.40</td><td>49,280</td><td>5.0%</td><td>14.9%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">融捷股份</td><td>资源股</td><td>700</td><td>71.28</td><td>49,896</td><td>5.0%</td><td>19.9%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">鼎龙股份</td><td>半导体</td><td>1,000</td><td>49.50</td><td>49,500</td><td>5.0%</td><td>24.9%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">强瑞技术</td><td>算力</td><td>300</td><td>147.19</td><td>44,157</td><td>5.0%</td><td>29.3%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">塞力医疗</td><td>AI应用</td><td>2,100</td><td>23.34</td><td>49,014</td><td>5.0%</td><td>34.2%</td><td class="left">中继买点|上升趋势</td></tr>
<tr><td>04-07</td><td>买入</td><td class="left">福光股份</td><td>商业航天</td><td>1,600</td><td>30.05</td><td>48,080</td><td>5.0%</td><td>39.0%</td><td class="left">中继买点|上升趋势</td></tr>
</table>
<div class="detail-box">
    <b>*总仓位 = 持仓总额 ÷ 总资产，逐笔累加。</b><br>
    <b>本周期货仓（评分{score}→{result}）：</b>{strategy}。当前总仓位39.0%，低于波谷80%目标。<br>
    注：因无卖出的第1周，按中继买点正常操作。数据从v3.2版本取，个股仓位已调整为5%/10%。
</div>
</div>

<div class="part">
<div class="part-header"><span class="part-number">5</span> 个股关键点分析</div>
{charts_html}
</div>

<div class="part">
<div class="part-header"><span class="part-number">6</span> 本周表现</div>
<div class="kpi-group">
    <span class="kpi-row"><span class="kpi-label">期初资产</span><br><span class="kpi-value">1,000,000</span></span>
    <span class="kpi-row highlight-box"><span class="kpi-label">波峰波谷</span><br><span class="kpi-value">{result}</span></span>
    <span class="kpi-row"><span class="kpi-label">总仓位</span><br><span class="kpi-value">39.0%</span></span>
</div>
<div class="detail-box">
    <b>第1周为建仓周</b>，{result}环境。按5%/10%个股仓位建仓7只，覆盖7个方向。<br>
    关键点图展示了每只股近24根K线及7种关键点标注（橙色=第1类参考点，蓝色=第2类买卖点）。<br>
    买入点以蓝色标记标出，止损设在下方关键支撑处。
</div>
</div>

</body>
</html>'''

with open(os.path.join(OUT, "第1周_完整版.html"), "w") as f:
    f.write(html)
print(f"✅ 报告已生成")
