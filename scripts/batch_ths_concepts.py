#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量拉取THS概念数据写入_push2test"""
import json, os, sys, shutil, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))
os.environ['TQDM_DISABLE'] = '1'
os.environ['PYTHONUNBUFFERED'] = '1'

from backend.core.config import SECTOR_DAILY_PATH
from backend.data_access.data_source import _fetch_ths_concept_snapshots, _load_concept_name_mapping

# 只拉已映射的
name_map = _load_concept_name_mapping()
mapped_names = list(name_map.keys())
print(f'待拉取: {len(mapped_names)}个已映射概念', flush=True)

all_data = {}
batch_size = 50
for i in range(0, len(mapped_names), batch_size):
    batch = mapped_names[i:i+batch_size]
    print(f'批次 {i//batch_size+1}/{len(mapped_names)//batch_size+1}: 开始', flush=True)
    batch_data = _fetch_ths_concept_snapshots(batch)
    all_data.update(batch_data)
    print(f'  批次 {i//batch_size+1}: {len(batch_data)}个 (累计{len(all_data)})', flush=True)
    time.sleep(1)

print(f'THS概念快照总数: {len(all_data)}', flush=True)

# 写入
data = json.load(open(SECTOR_DAILY_PATH))
p2t = data.get('_push2test', {})
p2t['concepts'] = all_data
p2t['_push2test_updated'] = '20260605'
data['_push2test'] = p2t
data['_push2test_updated'] = '20260605'

bak = SECTOR_DAILY_PATH + '.bak.pre-ths-concept-v2'
shutil.copy2(SECTOR_DAILY_PATH, bak)
print(f'备份: {bak}', flush=True)

with open(SECTOR_DAILY_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'已写入 {len(all_data)}条THS概念数据', flush=True)
if '培育钻石' in all_data:
    print(f'培育钻石 chg={all_data["培育钻石"].get("change_pct")}%', flush=True)
print('完成！', flush=True)
