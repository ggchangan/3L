#!/usr/bin/env python3
"""构建系统概念名称到同花顺概念名称的映射表"""
import json, os, re
os.environ['TQDM_DISABLE'] = '1'
import akshare as ak

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
path = os.path.join(DATA_DIR, 'map', 'concept_list.json')
cl = json.load(open(path))

# 系统概念名称
sys_names = set()
for code, info in cl.items():
    if isinstance(info, dict) and 'name' in info:
        sys_names.add(info['name'])

# THS 概念名称
df = ak.stock_board_concept_name_ths()
ths_names = list(df['name'])

def normalize(name):
    """归一化名称用于模糊匹配"""
    n = name
    for suffix in ['概念', '板块', '行业', '主题', 'Ⅱ', 'Ⅲ', 'Ⅳ']:
        n = n.replace(suffix, '')
    n = n.strip()
    n = re.sub(r'\s+', '', n)
    return n

# 建映射：系统名 -> THS名
name_map = {}
ths_norm_map = {normalize(tn): tn for tn in ths_names}

# 直匹配
for sn in sys_names:
    if sn in ths_names:
        name_map[sn] = sn
        continue
    # 模糊匹配
    sn_norm = normalize(sn)
    if sn_norm in ths_norm_map:
        name_map[sn] = ths_norm_map[sn_norm]
        continue
    # 多对一：系统名也可能是THS名的子串
    for tn in ths_names:
        if sn_norm and tn and (sn_norm in normalize(tn) or normalize(tn) in sn_norm):
            name_map[sn] = tn
            break

unmatched = sorted(n for n in sys_names if n not in name_map)

print(f'=== 概念名称匹配统计 ===')
print(f'系统概念: {len(sys_names)}')
print(f'同花顺概念: {len(ths_names)}')
print(f'已匹配: {len(name_map)}')
print(f'未匹配: {len(unmatched)}')
print()
if unmatched:
    print('=== 未匹配概念（前50）===')
    for n in unmatched[:50]:
        print(f'  {n}')

# 写映射文件
out_dir = os.path.join(DATA_DIR, 'map')
os.makedirs(out_dir, exist_ok=True)
mapping_path = os.path.join(out_dir, 'concept_name_mapping.json')
json.dump(name_map, open(mapping_path, 'w'), ensure_ascii=False, indent=2)
print(f'\n映射表已保存: {mapping_path} ({len(name_map)}条)')

# 也保存未匹配清单用于后续分析
unmatched_path = os.path.join(out_dir, 'concept_name_unmatched.json')
json.dump(unmatched, open(unmatched_path, 'w'), ensure_ascii=False, indent=2)
print(f'未匹配清单已保存: {unmatched_path} ({len(unmatched)}条)')
