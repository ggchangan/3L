#!/usr/bin/env python3
"""
设计文档 vs 代码实现 交叉检查脚本

解析 docs/product-design-v1.md 第6节（龙头观测重构方案）的功能需求，
扫描代码中是否有对应的实现，报告缺失项。

用法: python3 scripts/check_design_vs_code.py
"""
import os
import re
import sys
import json

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN_DOC = os.path.join(PROJECT_DIR, 'docs', 'product-design-v1.md')

# 设计需求 → 预期代码路径/关键字的映射
REQUIREMENTS = [
    # (需求描述, 预期的代码标识, 优先级)
    ('关注的行业列表', ['watched', 'watched_industries'], 'P0'),
    ('关注的行业三数据源：持仓sector', ['SECTOR_TO_INDUSTRY_MAP', 'watched_from_holdings'], 'P0'),
    ('关注的行业三数据源：涨幅前3行业', ['watched_from_top3', 'get_top_sectors_with_5d'], 'P0'),
    ('关注的行业三数据源：手动添加', ['watched_from_manual', 'WATCHED_INDUSTRIES_PATH', 'add_watched_industry', 'remove_watched_industry'], 'P0'),
    ('领涨领跌异动（surge/plunge）', ["'surge'", "'plunge'", 'sorted_desc', 'sorted_asc'], 'P0'),
    ('龙头切换检测（#2/#3超越#1）', ["'switching'", 'switch_events', 'diff > 3'], 'P0'),
    ('标记类型：🚀突破', ["'🚀突破'"], 'P1'),
    ('标记类型：⚠️领跌', ["'⚠️领跌'"], 'P1'),
    ('标记类型：📊放量', ["'📊放量'"], 'P1'),
    ('标记类型：🔄挑战', ["'🔄挑战'"], 'P1'),
    ('标记类型：⚡背离', ["'⚡背离'"], 'P1'),
    ('API端点：/api/monitor/leader-dashboard', ['leader-dashboard', 'leader_dashboard'], 'P0'),
    ('API端点：add-watched-industry', ['add-watched-industry', '_handle_add_watched', 'add_watched_industry'], 'P0'),
    ('API端点：remove-watched-industry', ['remove-watched-industry', '_handle_remove_watched', 'remove_watched_industry'], 'P0'),
    ('前端组件：LeaderMonitor.tsx', ['LeaderMonitor', 'WatchedIndustryItem'], 'P0'),
    ('前端类型：LeaderDashboardData', ['LeaderDashboardData', 'WatchedIndustryItem', 'AnomalyData'], 'P0'),
    ('前端API：fetchLeaderDashboard', ['fetchLeaderDashboard', 'leader-dashboard'], 'P0'),
    ('前端手动添加关注行业UI', ['AddIndustry', '添加关注行业', 'handleAddIndustry'], 'P1'),
    ('设计文档第6节', ['## 6.', '龙头观测重构方案'], 'P0'),
    ('技术可行性评估表', ['技术可行性汇总', '难度', '现有数据', '需新增数据'], 'P0'),
]

# 代码文件扫描清单
SCAN_FILES = [
    ('后端服务', os.path.join(PROJECT_DIR, 'backend', 'services', 'monitor_service.py')),
    ('后端API', os.path.join(PROJECT_DIR, 'backend', 'api', 'monitor.py')),
    ('服务端路由', os.path.join(PROJECT_DIR, 'server.py')),
    ('前端组件', os.path.join(PROJECT_DIR, 'frontend', 'src', 'components', 'LeaderMonitor.tsx')),
    ('前端API层', os.path.join(PROJECT_DIR, 'frontend', 'src', 'lib', 'api.ts')),
    ('前端类型', os.path.join(PROJECT_DIR, 'frontend', 'src', 'lib', 'types.ts')),
    ('设计文档', DESIGN_DOC),
]


def load_files():
    """加载所有代码文件内容"""
    files = {}
    for label, path in SCAN_FILES:
        if os.path.isfile(path):
            with open(path, 'r') as f:
                files[label] = f.read()
        else:
            files[label] = ''
    return files


def check_requirement(req_desc, keywords, priority, files):
    """检查一个需求是否在代码中实现"""
    found = False
    found_in = []
    missing_kw = []

    for kw in keywords:
        kw_found = False
        for label, content in files.items():
            if kw in content:
                kw_found = True
                if label not in found_in:
                    found_in.append(label)
        if not kw_found:
            missing_kw.append(kw)

    if missing_kw and len(missing_kw) == len(keywords):
        return False, f'全部关键字未找到: {missing_kw[:3]}...'
    if missing_kw:
        return True, f'部分匹配 (缺{missing_kw}), 在: {", ".join(found_in[:3])}'
    return True, f'✅ 在: {", ".join(found_in[:3])}'


def main():
    files = load_files()

    print('═' * 60)
    print('  设计文档 vs 代码实现 交叉检查')
    print('═' * 60)
    print()

    results = {'PASS': 0, 'PARTIAL': 0, 'MISSING': 0, 'total': len(REQUIREMENTS)}
    priorities = {'P0': [], 'P1': [], 'P2': [], 'P3': []}

    for req_desc, keywords, priority in REQUIREMENTS:
        ok, detail = check_requirement(req_desc, keywords, priority, files)
        status = 'PASS' if ok and not '部分' in detail else ('PARTIAL' if ok else 'MISSING')
        priorities.setdefault(priority, []).append((req_desc, status, detail))

        if status == 'PASS':
            results['PASS'] += 1
        elif status == 'PARTIAL':
            results['PARTIAL'] += 1
        else:
            results['MISSING'] += 1

    # 按优先级输出
    for pri in ['P0', 'P1', 'P2', 'P3']:
        items = priorities.get(pri, [])
        if not items:
            continue
        print(f'  [{pri}]')
        for desc, status, detail in items:
            icon = {'PASS': '✅', 'PARTIAL': '⚠️', 'MISSING': '❌'}.get(status, '❓')
            print(f'    {icon} {desc}')
            print(f'       {detail}')
        print()

    # 汇总
    print('═' * 60)
    print(f'  汇总: {results["PASS"]} 通过 / {results["PARTIAL"]} 部分 / {results["MISSING"]} 缺失 / 共{results["total"]}项')
    coverage = (results['PASS'] + results['PARTIAL'] * 0.5) / results['total'] * 100
    print(f'  实现覆盖率: {coverage:.0f}%')
    print('═' * 60)

    # 文件状态
    print()
    print('  文件状态:')
    for label, path in SCAN_FILES:
        status = '✅' if os.path.isfile(path) else '❌'
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        print(f'    {status} {label}: {size:,} bytes')

    return 0 if results['MISSING'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
