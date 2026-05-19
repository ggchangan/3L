#!/usr/bin/env python3
"""
每日更新脚本 - 将新生成的PDF复制到Web目录
用法: python3 /home/ubuntu/www/daily_update.py
"""
import os
import shutil
from datetime import datetime

WWW_FILES = '/home/ubuntu/www/files'
TODAY = datetime.now().strftime('%Y%m%d')

# 需要同步到Web的目录
SOURCE_DIRS = {
    '/home/ubuntu/.hermes/profiles/3l/tmp': '*.pdf',
    '/home/ubuntu/data/3l/simulation/v3': '*.pdf',
}

copied = 0
for src_dir, pattern in SOURCE_DIRS.items():
    if not os.path.exists(src_dir):
        continue
    for fname in os.listdir(src_dir):
        if fname.endswith('.pdf') or fname.endswith('.md'):
            src = os.path.join(src_dir, fname)
            dst = os.path.join(WWW_FILES, fname)
            if os.path.isfile(src) and (not os.path.exists(dst) or os.path.getmtime(src) > os.path.getmtime(dst)):
                shutil.copy2(src, dst)
                copied += 1
                print(f'  Copy: {fname}')

print(f'Done. {copied} files synced.')
