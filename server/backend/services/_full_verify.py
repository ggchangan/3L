#!/usr/bin/env python3
"""全量数据层验证 + 数据模型 + 上层概念数据"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'server'))
os.environ['TQDM_DISABLE'] = '1'

print('=' * 60)
print('1. verify_data_sources（50项检查）')
print('=' * 60)
from backend.services.data_source import verify_data_sources
r1 = verify_data_sources(verbose=False)
pass1 = sum(1 for c in r1['checks'] if c['pass'])
fail1 = sum(1 for c in r1['checks'] if not c['pass'])
print(f'  通过: {pass1}/{len(r1["checks"])}  失败: {fail1}')
for c in r1['checks']:
    if not c['pass']:
        print(f'    ❌ {c["check"]}: {c["detail"]}')

print()
print('=' * 60)
print('2. L0 覆盖度验证（21项）')
print('=' * 60)
from backend.services.data_source import verify_data_coverage
r2 = verify_data_coverage(verbose=False)
print(f'  通过: {r2["pass_count"]}/{len(r2["checks"])}  失败: {r2["fail_count"]}  警告: {r2["warn_count"]}')
for c in r2['checks']:
    if not c['pass']:
        print(f'    ❌ {c["check"]}: {c["detail"]}')

print()
print('=' * 60)
print('3. data_models 合约验证')
print('=' * 60)
from backend.core.data_models import (
    SectorPush2Test, ThsIndustrySnapshot, Push2TestConceptSnapshot,
)

# 测试概念数据通过合约正确读取
from backend.core.data_layer import get_sector_push2test
spt = get_sector_push2test()
print(f'  SectorPush2Test 类型: {type(spt).__name__}')
print(f'  industries 类型: {type(spt.industries).__name__}, 条目: {len(spt.industries)}')
print(f'  concepts 类型: {type(spt.concepts).__name__}, 条目: {len(spt.concepts)}')

# 验证概念数据中的关键字段
if '培育钻石' in spt.concepts:
    cd = spt.concepts['培育钻石']
    print(f'  培育钻石 type: {type(cd).__name__}')
    print(f'  培育钻石: chg={cd.change_pct}%')
    assert cd.change_pct is not None
    assert cd.date is not None
    print(f'  ✅ 培育钻石数据通过')
else:
    print(f'  ❌ 培育钻石不在 concepts 中')
    print(f'  前10个: {list(spt.concepts.keys())[:10]}')

# 验证行业数据
if '电子化学品' in spt.industries:
    ind = spt.industries['电子化学品']
    print(f'  电子化学品 type: {type(ind).__name__}')
    print(f'  电子化学品: chg={ind.change_pct}%')
    assert ind.change_pct is not None
    print(f'  ✅ 电子化学品数据通过')

print()
print('=' * 60)
print('4. 上层 get_mainline_data 概念主线数据')
print('=' * 60)
from backend.services.review_compute_service import get_mainline_data
from datetime import datetime
today = datetime.now().strftime('%Y%m%d')
mainlines = get_mainline_data(date_str=today)
print(f'  返回类型: {type(mainlines).__name__}')
if isinstance(mainlines, dict):
    print(f'  顶层keys: {list(mainlines.keys())[:5]}')
    # 概念主线
    con_lines = mainlines.get('concept_lines', []) or mainlines.get('concepts', [])
    if not con_lines and 'mainline' in mainlines:
        con_lines = mainlines['mainline'].get('concepts', [])
    if con_lines:
        print(f'  概念主线条目: {len(con_lines)}')
        for l in con_lines[:5]:
            print(f'    {l.get("name","?")}: chg_1d={l.get("chg_1d","?")}%  chg_20d={l.get("chg_20d","?")}%')
        # 验证培育钻石
        diamond = [l for l in con_lines if '培育钻石' in str(l.get('name',''))]
        if diamond:
            d = diamond[0]
            print(f'  💎 培育钻石: chg_1d={d.get("chg_1d")}% (应≈-3.3%)')
            assert abs(float(d.get('chg_1d', 0) or 0) - (-3.3)) < 1.0, f'培育钻石chg偏差过大: {d.get("chg_1d")}%'
            print(f'  ✅ 培育钻石 chg_1d 正确!')
        else:
            print(f'  ⚠️ 培育钻石不在概念主线中')
    else:
        print(f'  ⚠️ 未找到概念主线数据')
    # 行业主线
    ind_lines = mainlines.get('mainline', {}).get('lines', [])
    if not ind_lines:
        ind_lines = mainlines.get('mainlines', [])
    if ind_lines:
        print(f'  行业主线条目: {len(ind_lines)}')
        for l in ind_lines[:3]:
            print(f'    {l.get("name","?")}: chg_1d={l.get("chg_1d","?")}%')
