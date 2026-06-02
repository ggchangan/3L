"""
波峰波谷统一判定回测v2 — 概念板块全量回测

用375个概念板块×241天数据做滚动窗口回测，验证：
1. 波谷判定是否真的在跌后能抓反弹
2. 波峰判定是否真的在涨后能预测回调
3. 结构分层是否合理（上涨/下降/震荡各一套规则）

用法:
    cd /home/ubuntu/3l-server && PYTHONPATH=server python3 scripts/backtest_structure_wave_v2.py
"""

import json, os, sys, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

import statistics
from collections import defaultdict

from backend.core.structure_wave import judge_structure_wave

DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')


def load_concept_data(max_boards=375):
    """加载概念板块K线数据"""
    path = os.path.join(DATA_DIR, 'sector_daily.json')
    with open(path) as f:
        data = json.load(f)
    concepts = data.get('concepts', {})
    print(f'Total concept boards: {len(concepts)}')
    # 过滤：至少60根K线
    valid = {k: v for k, v in concepts.items() if len(v) >= 60}
    print(f'Valid (>=60 klines): {len(valid)}')
    # 抽样或全量
    items = list(valid.items())
    if max_boards and max_boards < len(items):
        items = random.sample(items, max_boards)
    return items


def backtest_board(klines, start_ratio=0.3, hold_periods=(5, 10, 20)):
    """单板块滚动回测"""
    n = len(klines)
    start = int(n * start_ratio)
    results = {'vl': defaultdict(list), 'pk': defaultdict(list), 'totals': 0}

    for i in range(start, n - max(hold_periods)):
        window = klines[:i + 1]
        cur_close = klines[i]['close']
        r = judge_structure_wave(window)
        pos = r['position']
        struct = r['structure']

        results['totals'] += 1

        for h in hold_periods:
            if i + h >= n:
                continue
            fwd = (klines[i + h]['close'] - cur_close) / cur_close * 100

            if pos == '偏波谷':
                results['vl'][h].append((fwd, struct))
            elif pos == '偏波峰':
                results['pk'][h].append((fwd, struct))

    return results


def print_signal_stats(label, data, direction='long'):
    """打印信号统计"""
    pos_name = '波谷(看涨)' if direction == 'long' else '波峰(看跌)'
    if not data:
        print(f'\n  {label} {pos_name}: 无信号')
        return
    print(f'\n  {label} {pos_name}:')
    for h, items in sorted(data.items()):
        if not items:
            continue
        returns = [x[0] for x in items]
        win = sum(1 for r in returns if (direction == 'long' and r > 0) or (direction == 'short' and r < 0))
        total = len(returns)
        wr = win / total * 100
        avg = statistics.mean(returns)
        median_r = statistics.median(returns)
        print(f'    {h}日: {total:,}次 胜率{wr:.1f}% 均{avg:+.2f}% 中位{median_r:+.2f}%')

        # 按结构分层
        by_struct = defaultdict(list)
        for r_val, struct in items:
            by_struct[struct].append(r_val)
        for struct, r_list in sorted(by_struct.items()):
            if len(r_list) < 5:
                continue
            s_win = sum(1 for r in r_list if (direction == 'long' and r > 0) or (direction == 'short' and r < 0))
            s_wr = s_win / len(r_list) * 100
            s_avg = statistics.mean(r_list)
            print(f'      [{struct}] {len(r_list):,}次 胜率{s_wr:.1f}% 均{s_avg:+.2f}%')


def main():
    print('=== 波峰波谷判定回测v2 — 概念板块全量 ===\n')

    concepts = load_concept_data(max_boards=375)
    print(f'Testing {len(concepts)} boards...')

    # 累计结果
    all_vl = {5: [], 10: [], 20: []}
    all_pk = {5: [], 10: [], 20: []}
    board_counts = {'vl': 0, 'pk': 0}

    for name, klines in concepts:
        r = backtest_board(klines, start_ratio=0.3, hold_periods=(5, 10, 20))
        for h in [5, 10, 20]:
            all_vl[h].extend(r['vl'].get(h, []))
            all_pk[h].extend(r['pk'].get(h, []))
        if any(r['vl'].values()):
            board_counts['vl'] += 1
        if any(r['pk'].values()):
            board_counts['pk'] += 1

    print(f'\n{"="*60}')
    print(f'  回测结果（{len(concepts)}个概念板块）')
    print(f'  {board_counts["vl"]}个板块触发过波谷, {board_counts["pk"]}个板块触发过波峰')
    print(f'{"="*60}')

    print_signal_stats('🆕 新方案', all_vl, 'long')
    print_signal_stats('🆕 新方案', all_pk, 'short')


if __name__ == '__main__':
    main()
