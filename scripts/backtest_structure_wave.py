"""
大盘波峰波谷判定回测 — 新方案 vs 旧方案对比

滚动窗口回测：从第80天开始逐日判定，对比5/10/20日后涨跌幅。

用法:
    cd /home/ubuntu/3l-server && PYTHONPATH=server python3 scripts/backtest_structure_wave.py
"""

import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import statistics
from collections import defaultdict

from backend.core.structure_wave import judge_structure_wave


DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')


def load_index_klines():
    """加载中证全指K线（从多指数格式 index_sh_data.json）"""
    path = os.path.join(DATA_DIR, 'index_sh_data.json')
    with open(path) as f:
        data = json.load(f)
    indices = data.get('indices', {})
    info = indices.get('000985', {})
    return info.get('klines', [])


def judge_peak_valley_old(klines):
    """引用旧版 judge_peak_valley（直接调用）"""
    from backend.services.review_compute_service import judge_peak_valley as old_func
    return old_func(klines)


def backtest(klines, start_day=80, hold_periods=(5, 10, 20)):
    """滚动窗口回测"""
    results = {
        'new': {'pk': defaultdict(list), 'vl': defaultdict(list)},
        'old': {'pk': defaultdict(list), 'vl': defaultdict(list)},
    }

    n = len(klines)
    for i in range(start_day, n - max(hold_periods)):
        window = klines[:i + 1]
        cur_close = klines[i]['close']

        # 旧方案
        try:
            old_r = judge_peak_valley_old(window)
        except Exception:
            old_r = {'position': '波中'}

        # 新方案
        new_r = judge_structure_wave(window)

        for tag, result in [('new', new_r), ('old', old_r)]:
            pos = result.get('position', '波中')

            if pos == '偏波谷' or pos.startswith('波谷'):
                for h in hold_periods:
                    if i + h < n:
                        fwd = (klines[i + h]['close'] - cur_close) / cur_close * 100
                        results[tag]['vl'][h].append(fwd)

            if pos == '偏波峰' or pos.startswith('波峰'):
                for h in hold_periods:
                    if i + h < n:
                        fwd = (klines[i + h]['close'] - cur_close) / cur_close * 100
                        results[tag]['pk'][h].append(fwd)

    return results


def print_stats(label, data, direction):
    """打印统计结果"""
    print(f'\n{"="*60}')
    print(f'  {label}')
    print(f'{"="*60}')
    for pos_type, periods in [('波谷(vl)', 'vl'), ('波峰(pk)', 'pk')]:
        print(f'\n  {pos_type} 信号')
        if periods not in data or not data[periods]:
            print('    无信号触发')
            continue
        for h, returns in sorted(data[periods].items()):
            if not returns:
                continue
            win = sum(1 for r in returns if (direction == 'long' and r > 0) or (direction == 'short' and r < 0))
            total = len(returns)
            wr = win / total * 100
            avg = statistics.mean(returns)
            best = max(returns)
            worst = min(returns)
            print(f'    {h}日: {total}次 胜率{wr:.1f}% 均{avg:+.2f}% 最好{best:+.2f}% 最差{worst:+.2f}%')


def main():
    klines = load_index_klines()
    print(f'中证全指K线: {len(klines)}条')
    print(f'  日期: {klines[0]["date"]} ~ {klines[-1]["date"]}')
    print(f'  最新价: {klines[-1]["close"]}')

    results = backtest(klines, start_day=80, hold_periods=(5, 10, 20))

    print_stats('🆕 新方案 (structure-aware wave)', results['new'], 'long')
    print_stats('🆕 新方案 波峰(跌=赢)', results['new'], 'short')

    print_stats('🗑️ 旧方案 (BIAS20 judge_peak_valley)', results['old'], 'long')
    print_stats('🗑️ 旧方案 波峰(跌=赢)', results['old'], 'short')

    # 新旧对比摘要
    print(f'\n{"="*60}')
    print(f'  新旧方案对比摘要')
    print(f'{"="*60}')
    for pos_key, pos_name in [('vl', '波谷(看涨)'), ('pk', '波峰(看跌)')]:
        print(f'\n  {pos_name}:')
        for h in [5, 10]:
            old_list = results['old'].get(pos_key, {}).get(h, [])
            new_list = results['new'].get(pos_key, {}).get(h, [])
            old_wr = sum(1 for r in old_list if r > 0) / len(old_list) * 100 if old_list else 0
            new_wr = sum(1 for r in new_list if r > 0) / len(new_list) * 100 if new_list else 0
            old_avg = statistics.mean(old_list) if old_list else 0
            new_avg = statistics.mean(new_list) if new_list else 0
            print(f'    {h}日 旧: {len(old_list)}次 WR{old_wr:.1f}% 均{old_avg:+.2f}%')
            print(f'    {h}日 新: {len(new_list)}次 WR{new_wr:.1f}% 均{new_avg:+.2f}%')
            if old_list and new_list:
                delta_wr = new_wr - old_wr
                delta_avg = new_avg - old_avg
                print(f'       差值: WR{delta_wr:+.1f}% 收益{delta_avg:+.2f}%')


if __name__ == '__main__':
    main()
