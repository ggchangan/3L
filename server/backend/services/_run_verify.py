#!/usr/bin/env python3
"""全量数据层验证"""
import os
os.environ['TQDM_DISABLE'] = '1'
import sys
sys.path.insert(0, 'server')

print("=" * 60)
print("1. verify_data_sources（50项检查）")
print("=" * 60)
from backend.data_access.data_source import verify_data_sources
result = verify_data_sources(verbose=False)
print(f'\n状态: {result["status"]}')
pass_c = sum(1 for c in result['checks'] if c['pass'])
fail_c = sum(1 for c in result['checks'] if not c['pass'])
print(f'通过: {pass_c}/{len(result["checks"])}')
print(f'失败: {fail_c}')
warn_c = sum(1 for c in result['checks'] if c.get('warn', False))
print(f'警告: {warn_c}')

fails = [c for c in result['checks'] if not c['pass']]
if fails:
    print(f'\n=== {len(fails)} 项失败 ===')
    for c in fails:
        print(f'  ❌ {c["check"]}: {c["detail"]}')

print('\n' + "=" * 60)
print("2. L0 覆盖度验证（21项）")
print("=" * 60)
from backend.data_access.data_source import verify_data_coverage as verify_data_coverage_l0
l0 = verify_data_coverage_l0(verbose=False)
print(f'\n状态: {l0["status"]}')
print(f'通过: {l0["pass_count"]}/{len(l0["checks"])}')
print(f'失败: {l0["fail_count"]}')
print(f'警告: {l0["warn_count"]}')

l0_fails = [c for c in l0['checks'] if not c['pass']]
if l0_fails:
    print(f'\n=== {len(l0_fails)} 项失败 ===')
    for c in l0_fails:
        print(f'  ❌ {c["check"]}: {c["detail"]}')

print('\n' + "=" * 60)
print("3. 测试 THS 概念快照批量拉取效果")
print("=" * 60)
from backend.core.data_layer import get_ths_concept_snapshots

# 测试一批概念
test_concepts = ['培育钻石', 'AI手机', '人形机器人', '华为概念', '半导体概念',
                 '芯片概念', '存储芯片', '光刻机(胶)', 'CPO概念', '新能源汽车']
ths_data = get_ths_concept_snapshots(test_concepts)
print(f'\n请求: {len(test_concepts)} 个')
print(f'成功: {len(ths_data)} 个')
for name in test_concepts:
    if name in ths_data:
        d = ths_data[name]
        print(f'  ✅ {name}: chg={d.get("change_pct")}% up={d.get("up_count")} down={d.get("down_count")}')
    else:
        print(f'  ❌ {name}: 未在THS中找到')
