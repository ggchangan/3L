#!/usr/bin/env python3
"""生成PDF汇总报告: 封面 + 概览表 + 个股分析页"""
import subprocess, os, json, tempfile

DATA_DIR = "/home/ubuntu/data/3l"
CHART_DIR = os.path.join(DATA_DIR, "charts")
OUTPUT_PDF = os.path.join(DATA_DIR, "中继买点精选报告_20260518.pdf")

def xesc(s):
    """XML转义"""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# 加载分析结果
with open(os.path.join(DATA_DIR, "analysis_results.json")) as f:
    results = json.load(f)

# 按评分排序
sorted_stocks = sorted(results.items(), key=lambda x: x[1]["buy_signal"]["score"], reverse=True)

def svg_header(title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="700" viewBox="0 0 1000 700">
<rect width="1000" height="700" fill="#1a1a2e"/>
<text x="500" y="50" fill="#ffffff" font-size="24" font-weight="bold" text-anchor="middle">{title}</text>'''

def svg_footer():
    return '\n</svg>'

# ═══ 1. 封面 ═══
cover_svg = f'''{svg_header("")}
<rect x="100" y="200" width="800" height="300" rx="15" fill="#16213e" stroke="#e67e22" stroke-width="2"/>
<text x="500" y="280" fill="#e67e22" font-size="36" font-weight="bold" text-anchor="middle">A 股中继买点精选报告</text>
<text x="500" y="330" fill="#cccccc" font-size="20" text-anchor="middle">简放 3L 体系 · 量价择时</text>
<text x="500" y="370" fill="#4ecdc4" font-size="16" text-anchor="middle">2026年5月18日（周一）收盘</text>
<line x1="300" y1="400" x2="700" y2="400" stroke="#e67e22" stroke-width="1"/>
<text x="500" y="440" fill="#888888" font-size="14" text-anchor="middle">数据源：新浪日K线 · 30日量价结构分析</text>
{svg_footer()}'''

# ═══ 2. 概览表 ═══
rows = []
y = 180
for i, (name, data) in enumerate(sorted_stocks):
    score = data["buy_signal"]["score"]
    code = data["code"]
    closing = data["closing"]
    change = data["change_pct"]
    pass_n = data["buy_signal"]["pass"]
    total_n = data["buy_signal"]["total"]
    
    # 行背景
    bg = "#1a1a2e" if i % 2 == 0 else "#16213e"
    score_color = "#4caf50" if score >= 80 else ("#ff9800" if score >= 60 else "#f44336")
    
    rows.append(f'''<rect x="50" y="{y}" width="900" height="32" fill="{bg}"/>
<text x="65" y="{y+20}" fill="#ffffff" font-size="13">{i+1}. {xesc(name)}</text>
<text x="230" y="{y+20}" fill="#888888" font-size="11">{xesc(code)}</text>
<text x="380" y="{y+20}" fill="#cccccc" font-size="13" text-anchor="end">{closing}</text>
<text x="450" y="{y+20}" fill="{"#ff4444" if change > 0 else "#44aa44"}" font-size="13" text-anchor="end">{xesc(f"{change:+.2f}%")}</text>
<rect x="500" y="{y+6}" width="60" height="20" rx="10" fill="{score_color}"/>
<text x="530" y="{y+20}" fill="#ffffff" font-size="12" text-anchor="middle">{score:.0f}</text>
<text x="620" y="{y+20}" fill="#888888" font-size="11">{xesc("✓"*pass_n + "✗"*(total_n-pass_n))}</text>''')
    y += 32

summary_svg = f'''{svg_header("评分总览")}
<rect x="50" y="70" width="900" height="40" rx="8" fill="#e67e22"/>
<text x="65" y="95" fill="#ffffff" font-size="14" font-weight="bold">股票</text>
<text x="380" y="95" fill="#ffffff" font-size="14" font-weight="bold" text-anchor="end">收盘价</text>
<text x="470" y="95" fill="#ffffff" font-size="14" font-weight="bold" text-anchor="end">涨跌幅</text>
<text x="530" y="95" fill="#ffffff" font-size="14" font-weight="bold" text-anchor="middle">评分</text>
<text x="620" y="95" fill="#ffffff" font-size="14" font-weight="bold">明细</text>
{chr(10).join(rows)}
<text x="500" y="{y+40}" fill="#666666" font-size="12" text-anchor="middle">评分标准：价格>MA20 + 缩量 + 回踩支撑 + 上升趋势 + 未加速</text>
{svg_footer()}'''

# 保存临时SVG并转PDF
tmp_dir = tempfile.mkdtemp()
pages = []

for name, content in [("封面", cover_svg), ("概览", summary_svg)]:
    svg_path = os.path.join(tmp_dir, f"{name}.svg")
    pdf_path = os.path.join(tmp_dir, f"{name}.pdf")
    with open(svg_path, "w") as f:
        f.write(content)
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path], check=True)
    pages.append(pdf_path)
    print(f"  ✓ {name}.pdf")

# ═══ 3. 个股分析页（评分≥80选前15只） ═══
top_candidates = [(n, d) for n, d in sorted_stocks if d["buy_signal"]["score"] >= 80][:15]

for idx, (name, data) in enumerate(top_candidates):
    score = data["buy_signal"]["score"]
    code = data["code"]
    closing = data["closing"]
    change = data["change_pct"]
    support = data["buy_signal"]["support_level"]
    details = data["buy_signal"]["details"]
    key_pts = data["key_points"]
    
    # 详情文字
    detail_lines = []
    for j, d in enumerate(details):
        detail_lines.append(f'<text x="50" y="{120+j*22}" fill="{("#4caf50" if d.startswith("✓") else "#f44336")}" font-size="13">{xesc(d)}</text>')
    
    # 关键点列表
    kp_lines = []
    for j, kp in enumerate(key_pts[:6]):
        kp_lines.append(f'<text x="50" y="{300+j*22}" fill="{"#ff9800" if kp["color"]=="orange" else "#2196f3"}" font-size="12">● {xesc(kp["type"])} {kp["date"][4:6]}/{kp["date"][6:8]} {xesc(kp["reason"][:35])}</text>')
    
    support_text = f"支撑位: {support:.2f}" if support > 0 else "支撑位: N/A"
    
    page_svg = f'''{svg_header(f"#{idx+1} {xesc(name)}({xesc(code)})")}
<rect x="50" y="70" width="900" height="35" rx="8" fill="#16213e"/>
<text x="70" y="93" fill="#ffffff" font-size="16">收盘：{closing}  {xesc(f"{change:+.2f}%")}</text>
<text x="350" y="93" fill="#4caf50" font-size="16">评分：{score:.0f}/100</text>
<text x="550" y="93" fill="#4ecdc4" font-size="16">{support_text}</text>

<text x="50" y="140" fill="#e67e22" font-size="16" font-weight="bold">买入条件判断</text>
<line x1="50" y1="148" x2="400" y2="148" stroke="#e67e22" stroke-width="1"/>
{chr(10).join(detail_lines)}

<text x="50" y="320" fill="#e67e22" font-size="16" font-weight="bold">关键点标记</text>
<line x1="50" y1="328" x2="400" y2="328" stroke="#e67e22" stroke-width="1"/>
{chr(10).join(kp_lines)}

<text x="50" y="480" fill="#666666" font-size="11">参考关键点图见下页 →</text>
<rect x="50" y="500" width="20" height="20" rx="3" fill="#ff9800"/>
<text x="80" y="515" fill="#ff9800" font-size="11">第1类参考点（前高/前低/天量/地量）</text>
<rect x="250" y="500" width="20" height="20" rx="3" fill="#2196f3"/>
<text x="280" y="515" fill="#2196f3" font-size="11">第2类供需点（突破/反转/中继）</text>
{svg_footer()}'''
    
    svg_path = os.path.join(tmp_dir, f"{name}_info.svg")
    pdf_path = os.path.join(tmp_dir, f"{name}_info.pdf")
    with open(svg_path, "w") as f:
        f.write(page_svg)
    subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path], check=True)
    pages.append(pdf_path)
    
    # 然后附上关键点图
    chart_svg = os.path.join(CHART_DIR, f"{name}.svg")
    chart_pdf = os.path.join(tmp_dir, f"{name}_chart.pdf")
    if os.path.exists(chart_svg):
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", chart_pdf, chart_svg], check=True)
        pages.append(chart_pdf)
    
    print(f"  ✓ {name} (分析+图表)")

# ═══ 4. 合并PDF ═══
pdf_args = ["pdfunite"] + pages + [OUTPUT_PDF]
subprocess.run(pdf_args, check=True)
print(f"\nPDF生成成功: {OUTPUT_PDF}")
print(f"共 {len(pages)} 页 | {len(top_candidates)} 只个股")

# 清理
import shutil
shutil.rmtree(tmp_dir)
