#!/usr/bin/env python3
"""
每日更新脚本 - 将新生成的PDF复制到Web目录
用法: python3 daily_update.py
"""
import os, shutil
from datetime import datetime

WWW_DIR = os.environ.get('WWW_DIR', '/home/ubuntu/3l-server')
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
WWW_FILES = os.path.join(WWW_DIR, 'files')
TODAY = datetime.now().strftime('%Y%m%d')

# 需要同步到Web的目录
SOURCE_DIRS = {
    os.path.join(DATA_DIR, 'simulation', 'v3'): '*.pdf',
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
