"""
概念板块5阶段回测 — 跑完后输出报告
"""
import json, os, sys, statistics
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

from backend.services.concept_wave_service import judge_concept_wave
from backend.core.config import SECTOR_DAILY_PATH

# 加载数据
d = json.load(open(SECTOR_DAILY_PATH, encoding='utf-8'))
concepts = d.get('concepts', {})

print(f"共 {len(concepts)} 个概念板块，每个 {len(list(concepts.values())[0])} 根K线")
print()

# 回测参数
MIN_KLINES = 60
PREDICT_DAYS = 5  # 预测窗口

# 阶段定义
STAGES = ['波谷', '波峰', '上涨', '下跌', '波中']

# 每个阶段：某个阶段的信号 → 成功条件
SUCCESS_CRITERIA = {
    '波谷': lambda next_5d: next_5d > 0,      # 波谷之后应该涨
    '波峰': lambda next_5d: next_5d < 0,      # 波峰之后应该跌
    '上涨': lambda next_5d: next_5d > 0,      # 上涨趋势应该继续涨
    '下跌': lambda next_5d: next_5d < 0,      # 下跌趋势应该继续跌
    '波中': lambda next_5d: True,              # 波中不判断
}

# 汇总
all_results = {s: [] for s in STAGES}
# 分概念存储，用于看概念间差异
per_concept = {}

tested = 0
skipped = 0

for name, klines in concepts.items():
    if len(klines) < MIN_KLINES:
        skipped += 1
        continue
    
    concept_results = []
    
    # 从第20根K线开始（满足BIAS20计算），预留PREDICT_DAYS验证
    for i in range(20, len(klines) - PREDICT_DAYS):
        segment = klines[:i + 1]
        try:
            score = judge_concept_wave(segment)
        except Exception as e:
            continue
        
        stage = score['stage']
        close_now = klines[i]['close']
        next_close = klines[i + PREDICT_DAYS]['close']
        chg_5d = (next_close - close_now) / close_now * 100
        
        # 5日最大涨幅/最大回撤
        prices_5d = [k['close'] for k in klines[i + 1:i + PREDICT_DAYS + 1]]
        max_5d = max(prices_5d)
        min_5d = min(prices_5d)
        max_gain = (max_5d - close_now) / close_now * 100
        max_loss = (min_5d - close_now) / close_now * 100
        
        record = {
            'concept': name,
            'date': klines[i]['date'],
            'close': close_now,
            'stage': stage,
            'vl_score': score['vl_score'],
            'pk_score': score['pk_score'],
            'bias20': score['bias20'],
            'bias5': score['bias5'],
            'volume_ratio': score['volume_ratio'],
            'ema10_slope': score['ema10_slope'],
            'next_5d': round(chg_5d, 2),
            'max_5d': round(max_gain, 2),
            'min_5d': round(max_loss, 2),
        }
        
        all_results[stage].append(record)
        concept_results.append(record)
        tested += 1
    
    per_concept[name] = concept_results

# ── 报告 ──
print("=" * 80)
print("   概念板块5阶段 V5 回测报告")
print(f"   测试日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"   概念数量: {len(concepts)}（有效: {len(concepts) - skipped}, 跳过: {skipped}）")
print(f"   总测试点: {tested}")
print(f"   预测窗口: {PREDICT_DAYS}个交易日")
print("=" * 80)
print()
print(f"{'阶段':<8} {'信号数':>8} {'胜率':>8} {'均收益':>8} {'均最大收益':>10} {'均最大亏损':>10} {'日均收益':>8}")
print("-" * 70)

grand_total = 0
grand_hits = 0

for stage in STAGES:
    recs = all_results[stage]
    if not recs:
        print(f"{stage:<8} {'-':>8} {'-':>8} {'-':>8} {'-':>10} {'-':>10} {'-':>8}")
        continue
    
    n = len(recs)
    success_fn = SUCCESS_CRITERIA[stage]
    hits = sum(1 for r in recs if success_fn(r['next_5d']))
    hit_rate = hits / n * 100
    avg_5d = statistics.mean([r['next_5d'] for r in recs]) if recs else 0
    avg_max_gain = statistics.mean([r['max_5d'] for r in recs]) if recs else 0
    avg_max_loss = statistics.mean([r['min_5d'] for r in recs]) if recs else 0
    avg_daily = avg_5d / PREDICT_DAYS
    
    grand_total += n
    grand_hits += hits
    
    print(f"{stage:<8} {n:>8} {hit_rate:>7.1f}% {avg_5d:>+7.2f}% {avg_max_gain:>+9.2f}% {avg_max_loss:>+9.2f}% {avg_daily:>+7.2f}%")

print("-" * 70)
print(f"{'合计':<8} {grand_total:>8} {grand_hits/grand_total*100:>7.1f}%")
print()

# ── 各阶段详细分析 ──
print()
print("=" * 80)
print("   各阶段详情")
print("=" * 80)

for stage in STAGES:
    recs = all_results[stage]
    if not recs:
        continue
    
    # 按 vl_score 分组查看波谷质量
    if stage == '波谷':
        print()
        print(f"▶ {stage} — 按 vl_score 分档")
        for vl in [3, 4, 5]:
            subset = [r for r in recs if r['vl_score'] == vl]
            if not subset:
                continue
            hits = sum(1 for r in subset if SUCCESS_CRITERIA[stage](r['next_5d']))
            avg = statistics.mean([r['next_5d'] for r in subset])
            print(f"   vl={vl}: {len(subset):>5}次 胜率{hits/len(subset)*100:>6.1f}% 均收益{avg:>+7.2f}%")
    
    # 按 bias20 分组
    if stage in ('波谷', '下跌'):
        print(f"▶ {stage} — 按 BIAS20 分档")
        for b_range, label in [((-20, -10), '<-10%'), ((-10, -8), '-10%~-8%'), ((-8, -5), '-8%~-5%'), ((-5, 0), '-5%~0%')]:
            subset = [r for r in recs if b_range[0] < r['bias20'] <= b_range[1]]
            if not subset:
                continue
            hits = sum(1 for r in subset if SUCCESS_CRITERIA[stage](r['next_5d']))
            avg = statistics.mean([r['next_5d'] for r in subset])
            print(f"   {label}: {len(subset):>5}次 胜率{hits/len(subset)*100:>6.1f}% 均收益{avg:>+7.2f}%")

# ── 分概念统计（只看波谷） ──
print()
print("=" * 80)
print("   各概念波谷信号胜率（TOP 20 / BOTTOM 10）")
print("=" * 80)

concept_stats = []
for name, recs in per_concept.items():
    valley_recs = [r for r in recs if r['stage'] == '波谷']
    if len(valley_recs) < 5:
        continue
    hits = sum(1 for r in valley_recs if r['next_5d'] > 0)
    avg = statistics.mean([r['next_5d'] for r in valley_recs])
    concept_stats.append((name, len(valley_recs), hits/len(valley_recs)*100, avg))

concept_stats.sort(key=lambda x: -x[2])

print()
print("TOP 20（波谷信号最准的概念）:")
print(f"{'概念':<16} {'信号数':>6} {'胜率':>8} {'均收益':>8}")
for name, n, rate, avg in concept_stats[:20]:
    print(f"  {name:<16} {n:>6} {rate:>7.1f}% {avg:>+7.2f}%")

print()
print("BOTTOM 10（波谷信号最不准的概念）:")
print(f"{'概念':<16} {'信号数':>6} {'胜率':>8} {'均收益':>8}")
for name, n, rate, avg in concept_stats[-10:]:
    print(f"  {name:<16} {n:>6} {rate:>7.1f}% {avg:>+7.2f}%")

# ── 最优参数分析：什么样的波谷信号最准？ ──
print()
print("=" * 80)
print("   波谷信号质量分析")
print("=" * 80)

valley_recs = all_results['波谷']
if valley_recs:
    # 切入窗口 vs 非切入窗口
    # 由于 backtest 不返回 entry_window，我们用近似：vl_score>=3 + bias20在-5~-8 + 缩量
    qualified = [r for r in valley_recs if -8 <= r['bias20'] <= -5]
    qualified_hits = sum(1 for r in qualified if r['next_5d'] > 0)
    unqualified = [r for r in valley_recs if not (-8 <= r['bias20'] <= -5)]
    unqualified_hits = sum(1 for r in unqualified if r['next_5d'] > 0)
    
    if qualified:
        print(f"  BIAS20在-5%~-8%范围: {len(qualified):>5}次 胜率{qualified_hits/len(qualified)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in qualified]):>+7.2f}%")
    if unqualified:
        print(f"  其他:                  {len(unqualified):>5}次 胜率{unqualified_hits/len(unqualified)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in unqualified]):>+7.2f}%")
    
    # 缩量 vs 非缩量
    shrink = [r for r in valley_recs if r['volume_ratio'] < 0.7]
    shrink_hits = sum(1 for r in shrink if r['next_5d'] > 0)
    noshrink = [r for r in valley_recs if r['volume_ratio'] >= 0.7]
    noshrink_hits = sum(1 for r in noshrink if r['next_5d'] > 0)
    
    if shrink:
        print(f"  缩量(量比<0.7):        {len(shrink):>5}次 胜率{shrink_hits/len(shrink)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in shrink]):>+7.2f}%")
    if noshrink:
        print(f"  未缩量:                 {len(noshrink):>5}次 胜率{noshrink_hits/len(noshrink)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in noshrink]):>+7.2f}%")
    
    # 拐头 vs 未拐头
    turn = [r for r in valley_recs if r['ema10_slope'] > -0.3]
    turn_hits = sum(1 for r in turn if r['next_5d'] > 0)
    noturn = [r for r in valley_recs if r['ema10_slope'] <= -0.3]
    noturn_hits = sum(1 for r in noturn if r['next_5d'] > 0)
    
    if turn:
        print(f"  EMA10走平/拐头(斜率>-0.3): {len(turn):>5}次 胜率{turn_hits/len(turn)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in turn]):>+7.2f}%")
    if noturn:
        print(f"  EMA10继续向下:          {len(noturn):>5}次 胜率{noturn_hits/len(noturn)*100:>6.1f}% 均收益{statistics.mean([r['next_5d'] for r in noturn]):>+7.2f}%")

# ── 结论 ──
print()
print("=" * 80)
print("   初步结论")
print("=" * 80)
print()
# 简单结论
best_stage = max(STAGES, key=lambda s: (
    sum(1 for r in all_results[s] if SUCCESS_CRITERIA[s](r['next_5d'])) / len(all_results[s])
    if all_results[s] else 0
))
worst_stage = min(STAGES, key=lambda s: (
    sum(1 for r in all_results[s] if SUCCESS_CRITERIA[s](r['next_5d'])) / len(all_results[s])
    if all_results[s] else 0
))

for stage in STAGES:
    recs = all_results[stage]
    if recs:
        hits = sum(1 for r in recs if SUCCESS_CRITERIA[stage](r['next_5d']))
        avg = statistics.mean([r['next_5d'] for r in recs])
        print(f"  {stage}: {len(recs)}次, 胜率{hits/len(recs)*100:.1f}%, 均收益{avg:+.2f}% — {'✅' if hits/len(recs) > 0.5 else '❌'} 预期{'正确' if hits/len(recs) > 0.5 else '需修正'}")
