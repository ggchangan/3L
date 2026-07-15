#!/usr/bin/env python3
"""
数据修复脚本 — 修复已验证到的数据问题

用法：
    python3 fix-data.py status                 # 检测数据问题
    python3 fix-data.py fix-weekend-dates       # 修正周末日期 → 前一个交易日
    python3 fix-data.py fix-concept-snapshot    # 全量拉取概念快照
    python3 fix-data.py fix-concept-kline       # 补拉过期概念K线
    python3 fix-data.py fix-all                 # 依次执行全部修复

每次操作前自动备份，操作后运行 L0 验证确认修复效果。
不修改数据管线逻辑（那是另一件事）。
"""
import argparse
import json
import os
import sys
import shutil
from datetime import datetime, timedelta

# 项目路径
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_DIR, 'server'))

from backend.core.config import SECTOR_DAILY_PATH
from backend.data_access.data_source import (
    verify_data_coverage, _last_trading_day, _is_trading_day,
    _days_between,
)

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')


def log(msg):
    print(f'[fix-data] {msg}')


def backup_file(path):
    """自动备份文件，返回备份路径"""
    if not os.path.isfile(path):
        log(f'⚠️  {path} 不存在，跳过备份')
        return None
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = f'{path}.bak.{ts}'
    shutil.copy2(path, bak)
    log(f'📦  备份 → {bak}')
    return bak


def load_sector_data():
    """加载 sector_daily.json"""
    if not os.path.isfile(SECTOR_DAILY_PATH):
        log(f'❌  {SECTOR_DAILY_PATH} 不存在')
        return None
    with open(SECTOR_DAILY_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_sector_data(data, backup_first=True):
    """保存 sector_daily.json，可选先备份"""
    if backup_first:
        backup_file(SECTOR_DAILY_PATH)
    os.makedirs(os.path.dirname(SECTOR_DAILY_PATH), exist_ok=True)
    with open(SECTOR_DAILY_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    log(f'💾  已写入 {SECTOR_DAILY_PATH}')


# ════════════════════════════════════════════════════════════
# 子命令：status
# ════════════════════════════════════════════════════════════

def cmd_status():
    """运行 L0 覆盖度验证，列出所有问题"""
    log('🔍  运行 L0 覆盖度验证...')
    backup_file(SECTOR_DAILY_PATH)  # 只是一个备份，不改变数据
    result = verify_data_coverage(verbose=True)
    print()
    log(f'状态: {result["status"]}')
    log(f'通过: {result["pass_count"]}, 失败: {result["fail_count"]}, 警告: {result["warn_count"]}')
    return result['status'] != 'fail'


# ════════════════════════════════════════════════════════════
# 子命令：fix-weekend-dates
# ════════════════════════════════════════════════════════════

def cmd_fix_weekend_dates():
    """将K线中的周末日期改为前一个交易日"""
    data = load_sector_data()
    if data is None:
        return False

    lt = _last_trading_day()
    fixed_industries = 0
    fixed_concepts = 0

    for dtype, dkey in [('行业', 'industries'), ('概念', 'concepts')]:
        items = data.get(dkey, {})
        for name, klines in items.items():
            if not isinstance(klines, list):
                continue
            for k in klines:
                if not isinstance(k, dict):
                    continue
                d = k.get('date', '')
                if d and not _is_trading_day(d):
                    k['date'] = lt
                    if dtype == '行业':
                        fixed_industries += 1
                    else:
                        fixed_concepts += 1

    total = fixed_industries + fixed_concepts
    if total == 0:
        log('✅  没有周末日期需要修复')
        return True

    save_sector_data(data)
    log(f'🔧  已修正 {fixed_industries}条行业K线 + {fixed_concepts}条概念K线 ({total}条) 的日期: 非交易日 → {lt}')

    # 重新验证
    log('📋  运行 L0 验证确认...')
    result = verify_data_coverage(verbose=False)
    weekend_checks = [c for c in result['checks']
                      if '周末' in c.get('check', '')]
    remaining = [c for c in weekend_checks if not c['pass']]
    if remaining:
        log(f'⚠️  仍有 {len(remaining)} 项周末日期问题未清除')
        for c in remaining:
            log(f'     ❌ {c["check"]}: {c["detail"]}')
        return False
    log('✅  周末日期全部修复通过')
    return True


# ════════════════════════════════════════════════════════════
# 子命令：fix-concept-snapshot
# ════════════════════════════════════════════════════════════

def cmd_fix_concept_snapshot():
    """从 push2test 全量拉取概念快照

    覆盖 _push2test.concepts，当前只有5条，应拉取所有概念的日快照。
    """
    data = load_sector_data()
    if data is None:
        return False

    import requests
    url = 'https://push2test.eastmoney.com/api/qt/clist/get'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/',
    }
    ut = 'bd1d9ddb04089700cf9c27f6f7426281'
    today = _last_trading_day()

    log('📡  从 push2test 全量拉取概念数据...')
    params = {
        'pn': '1', 'pz': '2000', 'po': '1', 'np': '1',
        'ut': ut, 'fltt': '2', 'invt': '2',
        'fs': 'm:90+t:3',
        'fields': 'f2,f3,f12,f14,f15,f16,f17,f18,f5,f6',
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=25)
        items = r.json().get('data', {}).get('diff', [])
    except Exception as e:
        log(f'❌  push2test请求失败: {e}')
        return False

    log(f'📡  push2test返回 {len(items)} 条概念')

    # 建立全量概念映射
    concept_snapshot = {}
    for item in items:
        name = (item.get('f14') or '').strip()
        if not name:
            continue
        clean = name.replace('Ⅱ', '').replace('Ⅲ', '').replace('D', '').strip()
        close = float(item.get('f2', 0) or 0)
        high = float(item.get('f15', close) or close)
        low = float(item.get('f16', close) or close)
        open_ = float(item.get('f17', close) or close)
        volume = int(float(item.get('f5', 0) or 0))
        change_pct = float(item.get('f3', 0) or 0)
        prev_close = float(item.get('f18', 0) or 0)
        concept_snapshot[clean] = {
            'date': today,
            'open': round(open_, 2),
            'close': round(close, 2),
            'high': round(high, 2),
            'low': round(low, 2),
            'volume': volume,
            'change_pct': round(change_pct, 2),
            'prev_close': round(prev_close, 2),
        }

    # 写入 _push2test
    p2t = data.get('_push2test', {})
    p2t['concepts'] = concept_snapshot
    p2t['_push2test_updated'] = today
    data['_push2test'] = p2t
    data['_push2test_updated'] = today
    save_sector_data(data)

    log(f'🔧  概念快照: {len(concept_snapshot)} 条已保存 (之前5条)')

    # 验证
    log('📋  运行 L0 验证确认...')
    result = verify_data_coverage(verbose=False)
    count_checks = [c for c in result['checks']
                    if c.get('type') == 'concept_snapshot'
                    and '计数' in c.get('check', '')]
    if count_checks:
        ck = count_checks[0]
        if ck['pass']:
            log(f'✅  概念快照计数验证通过: {ck["detail"]}')
        else:
            log(f'⚠️  概念快照计数仍不足: {ck["detail"]}')

    # 检查培育钻石
    diamond = concept_snapshot.get('培育钻石')
    if diamond:
        log(f'💎  培育钻石: chg={diamond["change_pct"]}%, close={diamond["close"]}')
    else:
        # push2test 可能没有培育钻石这个概念名（名称不标准）
        log('⚠️  培育钻石不在 push2test 返回的概念列表中，可能名称不同')
        for n in sorted(concept_snapshot.keys()):
            if '培育' in n or '钻石' in n:
                log(f'  疑似: {n} → chg={concept_snapshot[n]["change_pct"]}%')
                break
        else:
            log('  未找到任何含"培育"/"钻石"的概念')

    return True


# ════════════════════════════════════════════════════════════
# 子命令：fix-concept-kline
# ════════════════════════════════════════════════════════════

def cmd_fix_concept_kline():
    """补拉过期概念K线 — 只从同花顺 THS 补拉

    概念K线181条过期（停在20260601等）。
    使用 stock_board_concept_index_ths() 逐个拉取已映射概念的日历K线。
    仅拉取名称映射表中存在的概念，未映射的跳过。

    重复调用安全（按date去重）。
    """
    data = load_sector_data()
    if data is None:
        return False

    today = _last_trading_day()
    concepts = data.get('concepts', {})
    if not concepts:
        log('⚠️  没有概念K线数据')
        return True

    # 加载名称映射
    import json as _json
    name_map_path = os.path.join(DATA_DIR, 'map', 'concept_name_mapping.json')
    if os.path.exists(name_map_path):
        name_map = _json.load(open(name_map_path))
    else:
        name_map = {}
    log(f'📋  名称映射: {len(name_map)}条（同花顺 THS）')

    # 通过 data_layer 获取概念K线（走当前数据源：THS）
    from backend.data_access.data_layer import get_concept_klines
    today_klines = get_concept_klines(list(concepts.keys()))

    appended = 0
    skipped_already = 0
    skipped_unmapped = 0

    for name, klines in concepts.items():
        if not isinstance(klines, list):
            continue

        # 检查是否已有今天数据
        existing_dates = set()
        for k in klines:
            if isinstance(k, dict):
                existing_dates.add(k.get('date', ''))
        if today in existing_dates:
            skipped_already += 1
            continue

        # 从 data_layer 获取的数据中查找
        td = today_klines.get(name)
        if td is None:
            if not name_map.get(name):
                skipped_unmapped += 1
            else:
                log(f'  ⚠️  概念「{name}」THS拉取失败')
            continue

        klines.append(td)
        appended += 1

    save_sector_data(data)
    log(f'🔧  追加 {appended}条概念K线 (跳过已有{skipped_already}条、无映射{skipped_unmapped}条)')

    # 验证
    log('📋  运行 L0 验证确认...')
    result = verify_data_coverage(verbose=False)
    stale_checks = [c for c in result['checks']
                    if '过期' in c.get('check', '') and c.get('type') == 'concept_kline']
    if stale_checks:
        ck = stale_checks[0]
        if ck['pass']:
            log(f'✅  概念K线大面积过期检测通过: {ck["detail"]}')
        else:
            log(f'⚠️  仍有概念K线过期: {ck["detail"]}')

    # 检查培育钻石时效性
    diamond_check = [c for c in result['checks']
                     if '培育钻石' in c.get('check', '')
                     and '时效' in c.get('check', '')]
    if diamond_check:
        dc = diamond_check[0]
        if dc['pass']:
            log(f'💎  {dc["check"]}: {dc["detail"]}')
        else:
            log(f'❌  {dc["check"]}: {dc["detail"]}')

    return True


# ════════════════════════════════════════════════════════════
# 子命令：fix-all
# ════════════════════════════════════════════════════════════

def cmd_fix_all():
    """依次执行全部修复"""
    ok = True

    log('═' * 50)
    log('🔄  开始全量修复')
    log('═' * 50)

    steps = [
        ('修正周末日期', cmd_fix_weekend_dates),
        ('全量拉取概念快照', cmd_fix_concept_snapshot),
        ('补拉过期概念K线', cmd_fix_concept_kline),
    ]

    for i, (name, fn) in enumerate(steps, 1):
        log(f'\n[{i}/{len(steps)}] {name}...')
        try:
            step_ok = fn()
            if step_ok:
                log(f'  ✅  {name} 完成')
            else:
                log(f'  ❌  {name} 失败')
                ok = False
        except Exception as e:
            log(f'  ❌  {name} 异常: {e}')
            ok = False

    # 最终验证
    log('\n' + '═' * 50)
    log('📊  最终 L0 覆盖度验证')
    log('═' * 50)
    result = verify_data_coverage(verbose=True)
    log(f'\n最终状态: {result["status"]}')
    log(f'通过: {result["pass_count"]}, 失败: {result["fail_count"]}, 警告: {result["warn_count"]}')

    if result['status'] == 'pass':
        log('✅  全部数据修复完毕，验证通过')
    else:
        log(f'⚠️  仍有 {result["fail_count"]} 项问题未解决')

    return ok and result['status'] != 'fail'


# ════════════════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description='数据修复脚本 — 修复已验证到的数据问题',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        'command',
        nargs='?',
        choices=['status', 'fix-weekend-dates', 'fix-concept-snapshot',
                 'fix-concept-kline', 'fix-all'],
        default='status',
        help='修复命令 (默认: status)',
    )
    args = parser.parse_args()

    cmds = {
        'status': cmd_status,
        'fix-weekend-dates': cmd_fix_weekend_dates,
        'fix-concept-snapshot': cmd_fix_concept_snapshot,
        'fix-concept-kline': cmd_fix_concept_kline,
        'fix-all': cmd_fix_all,
    }

    fn = cmds[args.command]
    ok = fn()
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
