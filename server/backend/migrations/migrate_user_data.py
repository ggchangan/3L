"""存量个人数据迁移：config/*.json → config/users/1/（admin）。

多用户隔离上线后，个人数据按 config/users/<uid>/ 组织。
本脚本把迁移前的全局个人数据文件复制到主用户 admin(id=1) 目录：
  watchlist.json / directions.json / trades.json / manual_trend.json /
  alarms.json / journals.json / watched_industries.json / review_data.json /
  holdings.json（旧JSON回退副本）/ review_archive/*.json

幂等：目标已存在则跳过（不覆盖）。plan_tracking 已迁 MySQL（见 migrate_plan_tracking_mysql.py），不再有全局 SQLite。
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core import config  # noqa: E402

FILES = [
    'watchlist.json', 'directions.json', 'trades.json',
    'manual_trend.json', 'alarms.json', 'journals.json',
    'watched_industries.json', 'review_data.json', 'holdings.json',
    'journal_entries.json',
]

# alarms.json 在 private/ 下，其余在 config/ 下
PRIVATE_FILES = {'alarms.json', 'journal_entries.json'}


def migrate():
    target_dir = os.path.join(config.CONFIG_DIR, 'users', '1')
    os.makedirs(target_dir, exist_ok=True)
    moved = []

    for fname in FILES:
        src = os.path.join(config.PRIVATE_DIR if fname in PRIVATE_FILES else config.CONFIG_DIR, fname)
        dst = os.path.join(target_dir, fname)
        if os.path.isfile(src) and not os.path.isfile(dst):
            shutil.copy2(src, dst)
            moved.append(f'{src} → {dst}')

    # 复盘存档目录
    src_archive = config.REVIEW_ARCHIVE_DIR  # private/review_archive
    dst_archive = os.path.join(target_dir, 'review_archive')
    if os.path.isdir(src_archive):
        os.makedirs(dst_archive, exist_ok=True)
        for f in sorted(os.listdir(src_archive)):
            if f.endswith('.json') and not os.path.isfile(os.path.join(dst_archive, f)):
                shutil.copy2(os.path.join(src_archive, f), os.path.join(dst_archive, f))
                moved.append(f'review_archive/{f}')

    return moved


def main():
    moved = migrate()
    if moved:
        print('migrated to users/1/:')
        for m in moved:
            print('  ', m)
    else:
        print('no files to migrate (already done or nothing found)')


if __name__ == '__main__':
    main()
