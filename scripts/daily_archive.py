#!/usr/bin/env python3
"""
每日成果换日归档脚本
每天0点cron运行：
1. 提取上一日的"今日完成"内容 → 生成 archive/YYYY-MM-DD.html
2. 清空 index.html 的"今日完成"列表（待办任务不动）
3. 更新 fileDesc 和历史列表
"""
import re, os, sys
from datetime import datetime, timedelta

WWW_DIR = '/home/ubuntu/www'
INDEX_FILE = os.path.join(WWW_DIR, 'index.html')
ARCHIVE_DIR = os.path.join(WWW_DIR, 'archive')

def get_yesterday():
    """取上一完整交易日（简化：取前一天日期）"""
    yesterday = datetime.now() - timedelta(days=1)
    return yesterday.strftime('%Y-%m-%d')

def extract_done_items(html):
    """从 index.html 提取今日完成的所有 `<li>` 条目"""
    # 找到 doneList 内的所有 li
    pattern = r'<ul class="file-list" id="doneList">(.*?)</ul>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return [], html
    
    list_content = match.group(1)
    # 提取每个 li 条目
    items = re.findall(r'<li>.*?</li>', list_content, re.DOTALL)
    
    # 清空 doneList（只保留空的 ul）
    new_list = '<ul class="file-list" id="doneList">\n            </ul>'
    new_html = html[:match.start()] + new_list + html[match.end():]
    
    return items, new_html

def extract_pending_items(html):
    """提取当前待办列表的内容"""
    pattern = r'<ul class="file-list" id="pendingList">(.*?)</ul>'
    match = re.search(pattern, html, re.DOTALL)
    if not match:
        return [], html
    list_content = match.group(1)
    items = re.findall(r'<li>.*?</li>', list_content, re.DOTALL)
    return items

def get_title_from_li(li_html):
    """从 li 中提取标题文字（用于archive页展示）"""
    m = re.search(r'class="file-name"[^>]*>(.*?)</span>', li_html)
    if m:
        text = m.group(1)
        # 去掉 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()
    return ''

def get_desc_from_li(li_html):
    """从 li 中提取描述文字"""
    m = re.search(r'<div style="color:#888; font-size:12px; margin-top:4px;">(.*?)</div>', li_html, re.DOTALL)
    if m:
        text = m.group(1).strip()
        # 去除 &nbsp; 和多余空格
        text = text.replace('&nbsp;', ' ')
        text = re.sub(r'\s+', ' ', text)
        return text
    return ''

def get_status_from_li(li_html):
    """从 li 中提取状态标签文字"""
    m = re.search(r'<span[^>]*>(✅.*?)</span>', li_html)
    if m:
        return m.group(1)
    return ''

def generate_archive_html(date_str, done_items, pending_items):
    """生成 archive 页面的 HTML"""
    weekdays = ['一','二','三','四','五','六','日']
    dt = datetime.strptime(date_str, '%Y-%m-%d')
    wd = weekdays[dt.weekday()]
    
    # 构建完成卡片
    done_cards = ''
    for item in done_items:
        title = get_title_from_li(item)
        desc = get_desc_from_li(item)
        status = get_status_from_li(item)
        done_cards += f'''    <div class="card-today">
        <div style="font-size:16px; color:#e94560; margin-bottom:8px; font-weight:600;">{title}</div>
        <p style="font-size:13px; color:#ccc; line-height:1.8;">{desc}</p>
        <p style="margin-top:8px"><span class="tag-done" style="display:inline-block;padding:4px 12px;border-radius:6px;font-size:11px;background:#064e3b;color:#4ecdc4;">{status}</span></p>
    </div>
'''
    
    # 构建待办列表
    pending_html = ''
    for item in pending_items:
        # 保持原样
        pending_html += f'            {item}\n'
    
    # 取第一个完成项的简短摘要
    first_title = get_title_from_li(done_items[0]) if done_items else ''
    short_summary = first_title[:30] + '...' if len(first_title) > 30 else first_title
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>3L 交易体系 · 每日成果 {date_str}</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC','Microsoft YaHei',sans-serif;background:#0f0f1a;color:#e0e0e0;min-height:100vh}}
.header{{background:linear-gradient(135deg,#1a1a2e 0%,#16213e 50%,#0f3460 100%);border-bottom:2px solid #e94560;padding:30px 20px;text-align:center}}
.header h1{{font-size:28px;color:#fff;letter-spacing:4px}}
.header .subtitle{{color:#a0a0b0;font-size:14px;margin-top:8px}}
.container{{max-width:960px;margin:0 auto;padding:30px 20px}}
.section-title{{font-size:18px;color:#4ecdc4;margin:32px 0 16px;padding-bottom:8px;border-bottom:1px solid #2a2a4e}}
.card-today{{background:linear-gradient(135deg,#1a1a2e,#16213e);border:1px solid #2a2a4e;border-radius:16px;padding:30px;margin-bottom:24px;position:relative;overflow:hidden}}
.card-today::before{{content:'';position:absolute;top:0;right:0;width:200px;height:200px;background:radial-gradient(circle,rgba(233,69,96,0.08) 0%,transparent 70%);pointer-events:none}}
.card-today .card-title{{font-size:20px;color:#e94560;margin-bottom:12px}}
.card-today .card-meta{{color:#888;font-size:13px;margin-bottom:16px}}
.file-list{{list-style:none}}
.file-list li{{padding:10px 14px;background:rgba(255,255,255,0.04);border:1px solid #2a2a4e;border-radius:10px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between}}
.file-list li:hover{{background:rgba(255,255,255,0.08)}}
.file-name{{font-size:14px}}
.tag-done{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;background:#064e3b;color:#4ecdc4}}
.tag-pending{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;background:#451a03;color:#ffd700}}
.footer{{text-align:center;padding:30px;color:#555;font-size:12px;border-top:1px solid #1a1a2e;margin-top:40px}}
a{{color:#4ecdc4}}
</style>
</head>
<body>
<div class="header">
    <h1>📊 3L 交易体系 · 每日成果</h1>
    <div class="subtitle">{date_str} 星期{wd} | {short_summary}</div>
    <div style="margin-top:10px;" id="nav-top"></div>
</div>
<div class="container">
    <div class="section-title">📄 当日报告</div>
    <div class="card-today">
        <div class="card-title">📄 报告文件</div>
        <ul class="file-list">
            <li><a href="/files/每日成果_{date_str.replace("-", "")}.pdf" target="_blank" style="color:#4ecdc4; text-decoration:none;">每日成果_{date_str.replace("-", "")}.pdf</a></li>
        </ul>
    </div>

    <div class="section-title">✅ 当日完成</div>
{done_cards}
    <div class="section-title">⏳ 当日待办</div>
    <div class="card-today" style="padding:20px;">
        <ul class="file-list">
{pending_html}        </ul>
    </div>
</div>
<div id="nav-bottom"></div>
<div class="footer">3L 交易体系 · Hermes Agent · 2026</div>
<script src="/nav.js"></script>
</body>
</html>'''

def update_file_desc(html, date_str):
    """将新archive页对应的PDF描述加入 fileDesc"""
    # 检查是否已有
    pdf_name = f'每日成果_{date_str.replace("-", "")}.pdf'
    if pdf_name in html:
        return html  # 已有描述，跳过
    
    # 找到 fileDesc 的结束位置，在最后一项前插入
    pattern = r"(\s*'[^']+\.pdf': '[^']+',\n)(\s*);"
    match = re.search(pattern, html)
    if match:
        last_entry = match.group(1)
        closing = match.group(2)
        new_entry = f"            '{pdf_name}': '3L每日成果记录 · {date_str}',\n"
        html = html.replace(last_entry + closing, last_entry + new_entry + closing)
    
    return html

def main():
    date_str = sys.argv[1] if len(sys.argv) > 1 else get_yesterday()
    
    # 读取 index.html
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 检查 archive 是否已存在
    archive_file = os.path.join(ARCHIVE_DIR, f'{date_str}.html')
    if os.path.isfile(archive_file):
        print(f"[archive] 归档已存在: {date_str}")
        return
    
    # 提取今日完成 + 清空
    done_items, new_html = extract_done_items(html)
    if not done_items:
        print(f"[archive] {date_str} 今日完成为空，跳过归档")
        return
    
    # 提取待办（不动）
    pending_items = extract_pending_items(new_html)
    
    # 生成 archive 页面
    archive_html = generate_archive_html(date_str, done_items, pending_items)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    with open(archive_file, 'w', encoding='utf-8') as f:
        f.write(archive_html)
    print(f"[archive] ✅ 归档已生成: {archive_file}")
    
    # 更新 index.html（已清空的 doneList）
    new_html = update_file_desc(new_html, date_str)
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f"[archive] ✅ index.html 已更新（今日完成已清空，待办保留）")

if __name__ == '__main__':
    main()
