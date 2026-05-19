#!/usr/bin/env python3
"""将模拟交易报告转为PDF格式"""
import subprocess, os, tempfile

REPORT_DIR = "/home/ubuntu/data/3l/simulation"
OUTPUT_DIR = os.path.join(REPORT_DIR, "pdf")
os.makedirs(OUTPUT_DIR, exist_ok=True)

def xesc(s):
    return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;")

def text2svg(text, title, width=1000, height=700):
    """文本报告转SVG"""
    lines = []
    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
    lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')
    lines.append(f'<text x="30" y="40" fill="#e67e22" font-size="20" font-weight="bold">{xesc(title)}</text>')
    lines.append(f'<line x1="30" y1="55" x2="700" y2="55" stroke="#e67e22" stroke-width="1"/>')
    
    y = 85
    for line in text.strip().split("\n"):
        if not line.strip():
            y += 8
            continue
        
        # 判断颜色和字号
        if line.startswith("════════"):
            continue
        elif line.startswith("第") and "周报告" in line:
            color = "#4ecdc4"
            font_size = 16
        elif line.startswith("📊") or line.startswith("💼") or line.startswith("📝") or line.startswith("📈") or line.startswith("🏆") or line.startswith("📉"):
            color = "#e67e22"
            font_size = 14
        elif line.startswith("  · 🟢"):
            color = "#4caf50"
            font_size = 11
        elif line.startswith("  · 🔴") or line.startswith("  · ⚠️"):
            color = "#f44336"
            font_size = 11
        elif line.startswith("  ["):
            color = "#cccccc"
            font_size = 11
        elif line.strip().startswith("  "):
            color = "#aaaaaa"
            font_size = 11
        else:
            color = "#ffffff"
            font_size = 12
        
        # 换页处理（内容超出页面）
        if y > height - 50:
            lines.append('</svg>')
            contents = "\n".join(lines)
            yield contents
            # 新页
            lines = []
            lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">')
            lines.append(f'<rect width="{width}" height="{height}" fill="#1a1a2e"/>')
            lines.append(f'<text x="30" y="30" fill="#666666" font-size="12">{xesc(title)} (续)</text>')
            y = 55
        
        lines.append(f'<text x="30" y="{y}" fill="{color}" font-size="{font_size}" font-family="monospace">{xesc(line.rstrip())}</text>')
        y += font_size + 4
    
    lines.append('</svg>')
    contents = "\n".join(lines)
    yield contents

# 处理每个报告文件
report_files = sorted([f for f in os.listdir(REPORT_DIR) if f.endswith(".txt")])
all_pdfs = []

for rf in report_files:
    filepath = os.path.join(REPORT_DIR, rf)
    with open(filepath) as f:
        content = f.read()
    
    title = rf.replace(".txt","").replace("_"," ")
    pdf_pages = []
    tmp = tempfile.mkdtemp()
    
    for page_num, svg_content in enumerate(text2svg(content, title)):
        svg_path = os.path.join(tmp, f"page_{page_num}.svg")
        pdf_path = os.path.join(tmp, f"page_{page_num}.pdf")
        with open(svg_path, "w") as f:
            f.write(svg_content)
        subprocess.run(["rsvg-convert", "-f", "pdf", "-o", pdf_path, svg_path], check=True)
        pdf_pages.append(pdf_path)
    
    # 合并多页
    if len(pdf_pages) > 1:
        output = os.path.join(OUTPUT_DIR, rf.replace(".txt",".pdf"))
        subprocess.run(["pdfunite"] + pdf_pages + [output], check=True)
    else:
        output = pdf_pages[0]
        import shutil
        shutil.move(pdf_pages[0], os.path.join(OUTPUT_DIR, rf.replace(".txt",".pdf")))
    
    all_pdfs.append(output)
    print(f"  ✓ {rf.replace('.txt','.pdf')} ({len(pdf_pages)}页)")
    import shutil
    shutil.rmtree(tmp)

# 合并成一本总报告
if len(all_pdfs) > 1:
    # 收集所有实际存在的PDF路径（在OUTPUT_DIR下的）
    existing_pdfs = sorted([os.path.join(OUTPUT_DIR, f) for f in os.listdir(OUTPUT_DIR) if f.endswith(".pdf") and f != "模拟交易全报告.pdf"])
    if existing_pdfs:
        merged = os.path.join(OUTPUT_DIR, "模拟交易全报告.pdf")
        subprocess.run(["pdfunite"] + existing_pdfs + [merged], check=True)
        print(f"\n✅ 合并本: {merged}")

print(f"\n总 {len(all_pdfs)} 个PDF文件已生成")
