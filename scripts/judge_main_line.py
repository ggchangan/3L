#!/usr/bin/env python3
"""动态主线判定模块 — 方案B（20日涨幅×0.6 + MA20覆盖率×0.4）

用法:
    from judge_main_line import get_main_lines
    main_lines = get_main_lines("20260407", ALL_DATA, top_n=3, min_score=15)
    # 返回: ["算力", "半导体", "新能源"]
"""

import json
import sys

sys.path.insert(0, '/home/ubuntu/www/scripts')
from data_layer import ALL_STOCKS_PATH

def find_idx(date_str, klines):
    """返回日期在K线数据中的索引"""
    for i,k in enumerate(klines):
        if k['date'] == date_str:
            return i
    return -1

def get_main_lines(date_str, all_stocks, top_n=3, gain_weight=0.6, breadth_weight=0.4, min_score=15):
    """
    计算各板块动量评分，返回Top N主线板块列表

    参数:
        date_str: 日期字符串，格式YYYYMMDD
        all_stocks: 全市场数据字典，格式 {板块: {代码: [{date,open,close,high,low,volume},...]}}
        top_n: 返回的主线数量上限
        gain_weight: 20日涨幅权重（默认0.6）
        breadth_weight: MA20站上比例权重（默认0.4）
        min_score: 最低评分阈值，低于此分不纳入主线（默认15）

    返回:
        list: 主线板块名称列表，按评分降序
        dict: 各板块详细评分数据
    """
    results = {}
    for sec, stocks in all_stocks.items():
        gains = []
        above_ma20 = 0
        total = 0
        for code in stocks:
            kls = stocks[code]
            idx = find_idx(date_str, kls)
            if idx < 20:
                continue
            p20 = kls[idx-20]['close']
            pc = kls[idx]['close']
            gain = (pc - p20) / p20 * 100
            gains.append(gain)
            ma20 = sum(k['close'] for k in kls[idx-19:idx+1]) / 20
            if pc > ma20:
                above_ma20 += 1
            total += 1

        if gains:
            avg_gain = sum(gains) / len(gains)
            above_pct = above_ma20 / total * 100 if total > 0 else 0
            score = avg_gain * gain_weight + above_pct * breadth_weight
            results[sec] = {
                'avg_gain_20d': round(avg_gain, 2),
                'above_ma20_pct': round(above_pct, 1),
                'total_stocks': total,
                'above_ma20_count': above_ma20,
                'score': round(score, 2),
            }

    sorted_results = dict(sorted(results.items(), key=lambda x: -x[1]['score']))
    qualified = [sec for sec, data in sorted_results.items() if data['score'] >= min_score]
    main_lines = qualified[:top_n]
    return main_lines, sorted_results


def format_report(ranking):
    """将评分结果格式化为报告用的文字"""
    lines = []
    lines.append("板块  | 20日涨幅 | MA20占比 | 评分")
    lines.append("------|----------|----------|------")
    for sec, data in ranking.items():
        lines.append(f"{sec:<8} | {data['avg_gain_20d']:>+7.2f}% | {data['above_ma20_pct']:>6.1f}% | {data['score']:>7.2f}")
    return '\n'.join(lines)


if __name__ == '__main__':
    DATA_FILE = ALL_STOCKS_PATH
    with open(DATA_FILE) as f:
        raw = json.load(f)
    ALL = raw['stocks']

    test_dates = ["20260407", "20260410", "20260417", "20260424", "20260430", "20260518"]
    for d in test_dates:
        main_lines, ranking = get_main_lines(d, ALL, top_n=3, min_score=15)
        print(f"\n=== {d} ===")
        print(f"主线板块 ({len(main_lines)}个): {', '.join(main_lines) if main_lines else '无（评分均低于15）'}")
        print(f"全排名:")
        print(format_report(ranking))
