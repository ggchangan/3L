#!/usr/bin/env python3
"""快速修复：将 _push2test.concepts 从旧 push2test 数据替换为 THS 数据"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'server'))

from datetime import datetime
from backend.config import SECTOR_DAILY_PATH
from backend.core.data_layer import get_concept_snapshots, load_sector_daily_uncached

today = datetime.now().strftime('%Y%m%d')

# 1. 加载 sector_daily.json
data = load_sector_daily_uncached()
if not isinstance(data, dict) or not data:
    print('❌  sector_daily.json 读取失败')
    sys.exit(1)

print(f'📋  sector_daily.json 加载成功')

# 2. 查看当前 _push2test 
p2t = data.get('_push2test', {})
old_concepts = p2t.get('concepts', {})
print(f'旧 _push2test.concepts: {len(old_concepts)} 条')
if '培育钻石' in old_concepts:
    print(f'  培育钻石: chg={old_concepts["培育钻石"].get("change_pct")}%')

# 3. 用 THS 拉取所有已映射概念的快照数据
print(f'\n📡  从同花顺 THS 拉取概念快照...')
ths_data = get_concept_snapshots()  # 拉取所有已映射概念
print(f'THS 数据: {len(ths_data)} 条')
if '培育钻石' in ths_data:
    print(f'  培育钻石: chg={ths_data["培育钻石"].get("change_pct")}%')

# 4. 写入 _push2test.concepts
p2t['concepts'] = ths_data
p2t['_push2test_updated'] = today
data['_push2test'] = p2t
data['_push2test_updated'] = today

# 5. 保存
os.makedirs(os.path.dirname(SECTOR_DAILY_PATH), exist_ok=True)
# 备份
bak = SECTOR_DAILY_PATH + f'.bak.push2test-fix.{today}'
import shutil
shutil.copy2(SECTOR_DAILY_PATH, bak)
print(f'📦  备份 → {bak}')

with open(SECTOR_DAILY_PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f'💾  _push2test.concepts 已更新: {len(ths_data)} 条（THS 数据）')
print(f'📊  培育钻石: chg={ths_data.get("培育钻石", {}).get("change_pct", "?")}%')
print('✅  完成！重启服务后复盘页应显示正确数据')
