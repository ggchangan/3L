#!/usr/bin/env python3
"""检查 .wechat_alerts 文件，去重后输出新内容（供 cron no_agent 投递）"""
import os

ALERTS_FILE = '/home/ubuntu/data/3l/private/.wechat_alerts'
OFFSET_FILE = '/home/ubuntu/data/3l/private/.last_wechat_offset'
DEDUP_FILE = '/home/ubuntu/data/3l/private/.wechat_dedup'


def main():
    if not os.path.isfile(ALERTS_FILE):
        return

    offset = 0
    if os.path.isfile(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            try:
                offset = int(f.read().strip())
            except (ValueError, OSError):
                offset = 0

    current_size = os.path.getsize(ALERTS_FILE)
    if current_size <= offset:
        return

    with open(ALERTS_FILE, 'r', encoding='utf-8') as f:
        f.seek(offset)
        new_content = f.read()

    if not new_content.strip():
        return

    # 已发送的报警 ID（去重）
    sent_ids = set()
    if os.path.isfile(DEDUP_FILE):
        with open(DEDUP_FILE) as f:
            sent_ids = set(line.strip() for line in f if line.strip())

    # 解析每条报警，生成唯一 ID
    lines = new_content.split('\n')
    deduped_lines = []
    current_id = None
    for line in lines:
        if line.startswith('--- '):
            # 新一组报警
            current_id = line
            if current_id not in sent_ids:
                deduped_lines.append(line)
        elif line.startswith('🔴 '):
            # 止损条目：提取股票代码作为去重 key
            stock_code = ''
            if '(' in line and ')' in line:
                stock_code = line.split('(')[1].split(')')[0]
            entry_id = f'{current_id}|{stock_code}' if stock_code else line
            if entry_id not in sent_ids:
                deduped_lines.append(line)
        elif line.strip():
            deduped_lines.append(line)

    if not deduped_lines:
        # 无新内容，更新偏移但不输出
        with open(OFFSET_FILE, 'w') as f:
            f.write(str(current_size))
        return

    output = '\n'.join(deduped_lines)
    print(output)

    # 更新已发送 ID
    for line in deduped_lines:
        if line.startswith('--- '):
            sent_ids.add(line)
        elif '止' in line and '(' in line and ')' in line:
            stock_code = line.split('(')[1].split(')')[0]
            entry_id = f'{line.split("---")[0]}|{stock_code}'
            sent_ids.add(entry_id)

    with open(DEDUP_FILE, 'w') as f:
        f.write('\n'.join(sorted(sent_ids)))

    # 更新偏移
    with open(OFFSET_FILE, 'w') as f:
        f.write(str(current_size))


if __name__ == '__main__':
    main()
