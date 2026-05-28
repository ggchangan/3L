#!/usr/bin/env python3
"""
3L 全回归测试系统 — 统一测试运行器

测试分级：
  CRITICAL → 必须通过，否则构建失败
  WARNING  → 报告但不阻塞（风格漂移、设计覆盖率下降）
  INFO     → 仅日志（视觉回归结果）

用法:
  python3 scripts/run_full_regression.py                  # 标准模式（运行所有）
  python3 scripts/run_full_regression.py --ci             # CI模式（只跑CRITICAL，失败退出码=1）
  python3 scripts/run_full_regression.py --report         # 只生成报告，不运行测试
  python3 scripts/run_full_regression.py --update-snapshots  # 更新截图基线
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(PROJECT_DIR, 'frontend')
VENV_PYTHON = sys.executable

# ══════════════════════════════════════════════
# 测试配置
# ══════════════════════════════════════════════

TESTS = [
    # (id, 名称, 命令, 工作目录, 等级, 超时秒)
    {
        'id': 'frontend-vitest',
        'name': '前端组件渲染测试',
        'cmd': ['npx', 'vitest', 'run', '--reporter=verbose'],
        'cwd': FRONTEND_DIR,
        'tier': 'CRITICAL',
        'timeout': 120,
    },
    {
        'id': 'backend-pytest-unit',
        'name': '后端单元测试',
        'cmd': [VENV_PYTHON, '-m', 'pytest', 'tests/', '--ignore=tests/test_api.py', '-v', '--tb=short'],
        'cwd': PROJECT_DIR,
        'tier': 'CRITICAL',
        'timeout': 60,
    },
    {
        'id': 'design-cross-check',
        'name': '设计文档交叉检查',
        'cmd': [VENV_PYTHON, 'scripts/check_design_vs_code.py'],
        'cwd': PROJECT_DIR,
        'tier': 'WARNING',
        'timeout': 15,
    },
    {
        'id': 'ui-consistency',
        'name': 'UI风格一致性审计',
        'cmd': [VENV_PYTHON, 'scripts/audit_ui_consistency.py'],
        'cwd': PROJECT_DIR,
        'tier': 'WARNING',
        'timeout': 15,
    },
    {
        'id': 'backend-api-contract',
        'name': '后端API合约测试（需服务运行）',
        'cmd': [VENV_PYTHON, '-m', 'pytest', 'tests/test_api.py::TestLeaderDashboard', '-v', '--tb=short'],
        'cwd': PROJECT_DIR,
        'tier': 'WARNING',
        'timeout': 30,
    },
]

# ══════════════════════════════════════════════
# 结果存储
# ══════════════════════════════════════════════

REPORT_DIR = os.path.join(PROJECT_DIR, 'tests', 'reports')
os.makedirs(REPORT_DIR, exist_ok=True)


class TestResult:
    def __init__(self, test_config):
        self.id = test_config['id']
        self.name = test_config['name']
        self.tier = test_config['tier']
        self.passed = False
        self.output = ''
        self.error = ''
        self.duration = 0
        self.summary = ''


def run_test(test_config):
    """运行一个测试，返回 TestResult"""
    result = TestResult(test_config)
    start = time.time()

    try:
        r = subprocess.run(
            test_config['cmd'],
            cwd=test_config['cwd'],
            capture_output=True,
            text=True,
            timeout=test_config['timeout'],
        )
        result.output = r.stdout
        result.error = r.stderr
        result.passed = (r.returncode == 0)
        # 提取关键摘要
        lines = (r.stdout + r.stderr).split('\n')
        for line in lines:
            if 'passed' in line.lower() and ('failed' in line.lower() or 'error' in line.lower()):
                result.summary = line.strip()
            if 'FAILED' in line or 'PASSED' in line:
                if not result.summary:
                    result.summary = line.strip()
        if not result.summary:
            result.summary = f'exit code: {r.returncode}'
    except subprocess.TimeoutExpired:
        result.error = f'TIMEOUT ({test_config["timeout"]}s)'
        result.summary = '超时'
    except Exception as e:
        result.error = str(e)
        result.summary = f'异常: {e}'

    result.duration = round(time.time() - start, 1)
    return result


# ══════════════════════════════════════════════
# 报告生成
# ══════════════════════════════════════════════

def generate_report(all_results, mode):
    """生成markdown报告"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report = []
    report.append(f'# 3L 全回归测试报告')
    report.append(f'')
    report.append(f'> 时间: {now} | 模式: {mode}')
    report.append(f'')
    report.append(f'## 总览')
    report.append(f'')
    report.append(f'| 等级 | 通过 | 失败 | 总计 |')
    report.append(f'|:---|:---:|:---:|:---:|')

    tiers = {'CRITICAL': [0, 0], 'WARNING': [0, 0], 'INFO': [0, 0]}
    for r in all_results:
        if r.passed:
            tiers[r.tier][0] += 1
        else:
            tiers[r.tier][1] += 1

    for t in ['CRITICAL', 'WARNING', 'INFO']:
        p, f = tiers[t]
        icon = '🔴' if f > 0 else '✅' if p > 0 else '⬜'
        report.append(f'| {icon} **{t}** | {p} | {f} | {p+f} |')

    report.append(f'')
    report.append(f'## 详细结果')
    report.append(f'')
    report.append(f'| # | 测试 | 等级 | 结果 | 耗时 | 摘要 |')
    report.append(f'|:---:|:---|:---:|:---:|:---:|:---|')

    for i, r in enumerate(all_results):
        icon = '✅' if r.passed else '❌'
        tier_icon = '🔴' if r.tier == 'CRITICAL' else '🟡' if r.tier == 'WARNING' else '🔵'
        report.append(f'| {i+1} | {r.name} | {tier_icon}{r.tier} | {icon} | {r.duration}s | {r.summary} |')

    # 失败详情
    failures = [r for r in all_results if not r.passed]
    if failures:
        report.append(f'')
        report.append(f'## 失败详情')
        report.append(f'')
        for r in failures:
            report.append(f'### ❌ {r.name} ({r.tier})')
            report.append(f'')
            report.append(f'```')
            report.append(r.error[:500] if r.error else r.output[:500])
            report.append(f'```')
            report.append(f'')

    # UI一致性审计附加报告
    ui_result = next((r for r in all_results if r.id == 'ui-consistency'), None)
    if ui_result and ui_result.output:
        # 提取"低频色"数量
        for line in ui_result.output.split('\n'):
            if '低频色' in line:
                report.append(f'> ⚠️ UI审计: {line.strip()}')
            if '输入框风格不一致' in line:
                report.append(f'> ⚠️ UI审计: {line.strip()}')

    report_text = '\n'.join(report)

    # 保存报告
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(REPORT_DIR, f'regression_{ts}.md')
    with open(report_path, 'w') as f:
        f.write(report_text)

    # 最新报告（覆盖）
    latest_path = os.path.join(REPORT_DIR, 'latest.md')
    with open(latest_path, 'w') as f:
        f.write(report_text)

    print(f'  报告已保存: {report_path}')
    print(f'  最新报告: {latest_path}')

    return report_text


def main():
    mode = 'standard'
    if '--ci' in sys.argv:
        mode = 'ci'
    if '--report' in sys.argv:
        mode = 'report'

    print()
    print('═' * 60)
    print(f'  3L 全回归测试 — 模式: {mode}')
    print('═' * 60)
    print()

    # 筛选要运行的测试
    active_tests = TESTS
    if mode == 'ci':
        active_tests = [t for t in TESTS if t['tier'] == 'CRITICAL']

    all_results = []

    for test_config in active_tests:
        # 跳过需要服务运行的测试（CI模式下）
        if mode == 'ci' and '需服务运行' in test_config['name']:
            continue

        tier_icon = '🔴' if test_config['tier'] == 'CRITICAL' else '🟡' if test_config['tier'] == 'WARNING' else '🔵'
        print(f'  [{tier_icon}] {test_config["name"]}...', end=' ', flush=True)

        result = run_test(test_config)
        all_results.append(result)

        icon = '✅' if result.passed else '❌'
        print(f'{icon} ({result.duration}s)')
        if not result.passed and result.tier == 'CRITICAL':
            print(f'     {result.error[:200]}')

    print()
    report = generate_report(all_results, mode)

    # 计算退出码
    critical_failures = [r for r in all_results if not r.passed and r.tier == 'CRITICAL']
    if critical_failures:
        print(f'\n  ❌ CRITICAL测试失败: {len(critical_failures)}项')
        if mode == 'ci':
            sys.exit(1)

    # WARNING失败也提示但不退出
    warning_failures = [r for r in all_results if not r.passed and r.tier == 'WARNING']
    if warning_failures:
        print(f'\n  ⚠️ WARNING测试失败: {len(warning_failures)}项（不阻塞构建）')

    print(f'\n  ✅ 回归测试完成')
    print('═' * 60)
    print()


if __name__ == '__main__':
    main()
