#!/usr/bin/env python3
"""
每日成果页面更新工具
每次完成任务后调用，自动更新 index.html 的"今日完成"区域 + fileDesc
用法:
  python3 update_achievements.py add "标题" "描述" --tag "✅ 已完成"
  python3 update_achievements.py pdf "每日成果_20260521.pdf" "描述文字"
  python3 update_achievements.py archive       # 手动触发换日归档
"""
import re, sys, os, json
from datetime import datetime

WWW_DIR = '/home/ubuntu/www'
INDEX_FILE = os.path.join(WWW_DIR, 'index.html')

def today():
    return datetime.now().strftime('%Y-%m-%d')

def read_index():
    with open(INDEX_FILE, 'r', encoding='utf-8') as f:
        return f.read()

def write_index(html):
    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

def cmd_add(title, description, tag='✅ 已完成'):
    """向今日完成列表最前面添加一条记录"""
    html = read_index()
    
    # 构建新条目
    new_item = f'''                <li>
                    <div style="flex:1">
                        <span class="file-name" style="color:#4ecdc4;">{title}</span>
                        <div style="color:#888; font-size:12px; margin-top:4px;">{description}</div>
                    </div>
                    <span style="color:#4ecdc4; font-size:12px; white-space:nowrap; margin-left:12px;">{tag}</span>
                </li>
'''
    # 在 <ul id="doneList"> 之后、第一个 <li> 之前插入
    marker = '<ul class="file-list" id="doneList">\n'
    idx = html.find(marker)
    if idx == -1:
        print('[update] ⚠️ 未找到 doneList')
        return False
    insert_pos = idx + len(marker)
    html = html[:insert_pos] + new_item + html[insert_pos:]
    
    write_index(html)
    print(f'[update] ✅ 已添加: {title}')
    return True

def cmd_pdf(pdf_name, description):
    """向 fileDesc 添加PDF描述映射"""
    html = read_index()
    entry = f"'{pdf_name}': '{description}'"
    if entry in html:
        print(f'[update] ⚠️ 已存在: {pdf_name}')
        return True
    
    # 在 fileDesc 花括号内追加（最后一个条目之前或 }; 之前）
    marker = "': '"
    # 找 fileDesc 的最后一个条目行 + }; 的结束位置
    pattern = r"('[^']+\.pdf': '[^']+',)\n(\s*)\};"
    match = re.search(pattern, html)
    if match:
        last_entry_line = match.group(1)
        indent = match.group(2)
        new_line = f"{last_entry_line}\n{indent}'{pdf_name}': '{description}',"
        html = html.replace(last_entry_line + '\n' + indent + '};', new_line + '\n' + indent + '};')
        write_index(html)
        print(f'[update] ✅ fileDesc 已添加: {pdf_name}')
        return True
    
    print('[update] ⚠️ 未找到 fileDesc 匹配位置')
    return False

def cmd_list():
    """列出今日已完成条目"""
    html = read_index()
    items = re.findall(r'<span class="file-name"[^>]*>(.*?)</span>', 
                       html[html.index('id="doneList"'):html.index('id="pendingList"')])
    print(f'今日完成 ({len(items)} 项):')
    for i, item in enumerate(items, 1):
        print(f'  {i}. {re.sub(r"<[^>]+>", "", item).strip()}')
    return items

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'add':
        if len(sys.argv) < 4:
            print('用法: update_achievements.py add "标题" "描述" [--tag "标签"]')
            sys.exit(1)
        title = sys.argv[2]
        desc = sys.argv[3]
        tag = '✅ 已完成'
        if '--tag' in sys.argv:
            idx = sys.argv.index('--tag')
            if idx + 1 < len(sys.argv):
                tag = sys.argv[idx + 1]
        cmd_add(title, desc, tag)
    
    elif command == 'pdf':
        if len(sys.argv) < 4:
            print('用法: update_achievements.py pdf "文件名.pdf" "描述文字"')
            sys.exit(1)
        cmd_pdf(sys.argv[2], sys.argv[3])
    
    elif command == 'list':
        cmd_list()
    
    else:
        print(f'未知命令: {command}')
        print(__doc__)
