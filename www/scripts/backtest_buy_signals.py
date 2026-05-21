#!/usr/bin/env python3
"""
历史买点成功率回测 — 遍历所有自选股历史数据
使用 buy_point_detection.py 的真实 detect_buy_point 函数
统计按买点类型(中继/突破)的历史胜率、盈亏比

输出：JSON缓存 + HTML报告 → PDF挂到成果页
"""
import json, os, sys, math, time
from collections import defaultdict
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

ALL_STOCKS_PATH = '/home/ubuntu/data/3l/all_stocks_60d.json'
OUTPUT_JSON = '/home/ubuntu/www/files/buy_signal_backtest_results.json'
OUTPUT_HTML = '/home/ubuntu/www/files/buy_signal_backtest_report.html'

LOOKBACK_DAYS = 5
R_MULTIPLIER = 2.0
STOP_BUFFER = 0.98


def analyze_stock(args):
    """分析一只股票的全部历史买点"""
    direction, code, klines = args
    if len(klines) < 35:
        return []
    
    from buy_point_detection import detect_buy_point, _find_support_levels
    
    name = klines[0].get('name', code) if klines else code
    all_stocks_sub = {direction: {code: klines}}
    results = []
    
    for i in range(30, len(klines) - LOOKBACK_DAYS):
        date_str = str(klines[i].get('date', '')).replace('-', '')
        date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) >= 8 else date_str
        
        try:
            bt = detect_buy_point(code, date_fmt, all_stocks_sub, market_position='波中', main_lines=set())
        except Exception:
            continue
        
        if not bt:
            continue
        
        entry_price = bt['close']
        buy_type = bt['buy_type']
        
        # 找支撑→止损
        support = _find_support_levels(klines, i)
        if support is None:
            # 回退到前20日最低
            support = min(k['low'] for k in klines[max(0, i-20):i+1])
        
        stop_loss = round(support * STOP_BUFFER, 2)
        risk = entry_price - stop_loss
        
        if risk <= 0:
            continue
        
        target = entry_price + risk * R_MULTIPLIER
        
        # 跟踪后续走势
        max_gain, max_loss = 0, 0
        outcome = None
        
        for day in range(i + 1, min(i + LOOKBACK_DAYS + 1, len(klines))):
            k = klines[day]
            hp, lp, cp = k['high'], k['low'], k['close']
            
            gain_pct = round((cp - entry_price) / entry_price * 100, 2)
            loss_pct = round((cp - entry_price) / entry_price * 100, 2)
            max_gain = max(max_gain, gain_pct)
            max_loss = min(max_loss, loss_pct)
            
            if lp <= stop_loss:
                r = round((stop_loss - entry_price) / risk, 2)
                outcome = {
                    'exit_reason': 'stop_loss', 'exit_day': day - i,
                    'gain_pct': round((stop_loss - entry_price) / entry_price * 100, 2),
                    'r_multiple': r, 'max_gain_pct': max_gain, 'max_loss_pct': max_loss,
                }
                break
            
            if hp >= target:
                r = round((target - entry_price) / risk, 2)
                outcome = {
                    'exit_reason': 'take_profit', 'exit_day': day - i,
                    'gain_pct': round((target - entry_price) / entry_price * 100, 2),
                    'r_multiple': r, 'max_gain_pct': max_gain, 'max_loss_pct': max_loss,
                }
                break
        
        if outcome is None:
            final = klines[min(i + LOOKBACK_DAYS, len(klines) - 1)]['close']
            r = round((final - entry_price) / risk, 2)
            outcome = {
                'exit_reason': 'timeout', 'exit_day': LOOKBACK_DAYS,
                'gain_pct': round((final - entry_price) / entry_price * 100, 2),
                'r_multiple': r, 'max_gain_pct': max_gain, 'max_loss_pct': max_loss,
            }
        
        results.append({
            'code': code, 'name': name, 'direction': direction,
            'date': date_fmt, 'buy_type': buy_type,
            'entry_price': entry_price, 'support': support,
            'stop_loss': stop_loss, 'structure': bt.get('structure', ''),
            'stage': bt.get('stage', ''), 'score': bt.get('score', 0),
            **outcome,
        })
    
    return results


def run():
    print("加载数据...")
    with open(ALL_STOCKS_PATH) as f:
        raw = json.load(f)
    all_stocks = raw.get('stocks', raw)
    
    tasks = []
    for direction, stocks in all_stocks.items():
        if not isinstance(stocks, dict):
            continue
        for code, klines in stocks.items():
            tasks.append((direction, code, klines))
    
    print(f"共 {len(tasks)} 只股票，开始回测...")
    
    nw = min(os.cpu_count() or 4, 8)
    print(f"使用 {nw} 进程并行...")
    
    all_results = []
    with ProcessPoolExecutor(max_workers=nw) as pool:
        futs = {pool.submit(analyze_stock, t): t for t in tasks}
        done = 0
        for f in as_completed(futs):
            done += 1
            if done % 40 == 0:
                print(f"  进度: {done}/{len(tasks)}")
            try:
                all_results.extend(f.result())
            except Exception as e:
                print(f"  ✗ {futs[f][1]}: {e}")
    
    print(f"\n回测完成! 共 {len(all_results)} 个买点信号")
    
    # 统计
    by_type = defaultdict(lambda: {'total': 0, 'tp': 0, 'sl': 0, 'to': 0,
                                     'gains': [], 'r_vals': []})
    by_dir = defaultdict(lambda: {'total': 0, 'tp': 0, 'sl': 0})
    
    for r in all_results:
        bt = r['buy_type']
        by_type[bt]['total'] += 1
        by_dir[r['direction']]['total'] += 1
        
        if r['exit_reason'] == 'take_profit':
            by_type[bt]['tp'] += 1
            by_dir[r['direction']]['tp'] += 1
        elif r['exit_reason'] == 'stop_loss':
            by_type[bt]['sl'] += 1
            by_dir[r['direction']]['sl'] += 1
        else:
            by_type[bt]['to'] += 1
        
        by_type[bt]['gains'].append(r['gain_pct'])
        by_type[bt]['r_vals'].append(r['r_multiple'])
    
    for bt in by_type:
        d = by_type[bt]
        d['win_rate'] = round(d['tp'] / max(d['total'], 1) * 100, 1)
        d['avg_gain'] = round(sum(d['gains']) / max(len(d['gains']), 1), 2)
        d['avg_r'] = round(sum(d['r_vals']) / max(len(d['r_vals']), 1), 2)
        # 只统计成功交易的盈亏比
        tp_r = [r['r_multiple'] for r in all_results if r['buy_type'] == bt and r['exit_reason'] == 'take_profit']
        d['avg_win_r'] = round(sum(tp_r) / max(len(tp_r), 1), 2)
    
    # 保存JSON
    with open(OUTPUT_JSON, 'w') as f:
        json.dump({
            'total_signals': len(all_results),
            'by_type': {k: {kk: vv for kk, vv in dict(v).items() if kk not in ('gains', 'r_vals')}
                       for k, v in by_type.items()},
            'generated_at': datetime.now().isoformat(),
        }, f, ensure_ascii=False, indent=2)
    
    # 生成HTML
    gen_html(len(all_results), by_type, by_dir, all_results)
    print(f"JSON: {OUTPUT_JSON}")
    print(f"HTML: {OUTPUT_HTML}")


def gen_html(total, by_type, by_dir, all_results):
    rows = ''
    for bt, d in sorted(by_type.items(), key=lambda x: -x[1]['total']):
        sr = '🟢' if d['win_rate'] >= 50 else '🔴'
        rows += f'''
        <tr>
            <td><strong>{bt}</strong></td>
            <td>{d['total']}</td>
            <td style="color:#4caf50;">{d['tp']}</td>
            <td style="color:#e53935;">{d['sl']}</td>
            <td style="color:#888;">{d['to']}</td>
            <td style="font-weight:bold;">{sr} {d['win_rate']}%</td>
            <td>{d['avg_gain']}%</td>
            <td>{d['avg_r']}R</td>
            <td>{d.get('avg_win_r', 0)}R</td>
        </tr>'''
    
    # 方向排名
    ds = sorted(by_dir.items(), key=lambda x: -x[1]['total'])[:10]
    dir_rows = ''
    for direction, d in ds:
        wr = round(d['tp'] / max(d['total'], 1) * 100, 1)
        sr = '🟢' if wr >= 50 else '🔴'
        dir_rows += f'<tr><td>{direction}</td><td>{d["total"]}</td><td>{d["tp"]}</td><td style="font-weight:bold;">{sr} {wr}%</td></tr>'
    
    # 最新信号
    recent = sorted(all_results, key=lambda x: x.get('date', ''), reverse=True)[:15]
    rec_rows = ''
    for r in recent:
        em = '🟢' if r['exit_reason'] == 'take_profit' else ('🔴' if r['exit_reason'] == 'stop_loss' else '⚪')
        rec_rows += f'<tr><td>{r["date"]}</td><td>{r["name"]}({r["code"]})</td><td>{r["buy_type"]}</td><td>{r["gain_pct"]}%</td><td>{r["r_multiple"]}R</td><td>{em} {r["exit_reason"]}</td></tr>'
    
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
body{{font-family:'Noto Sans SC','Microsoft YaHei',sans-serif;margin:20px;}}
h1{{color:#d32f2f;border-bottom:2px solid #d32f2f;padding-bottom:5px;}}
h2{{color:#1976d2;margin-top:25px;}}
table{{border-collapse:collapse;width:100%;margin:10px 0;font-size:13px;}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:center;}}
th{{background:#f5f5f5;font-weight:bold;}}
tr:nth-child(even){{background:#fafafa;}}
.summary{{background:#f0f8ff;border:1px solid #b0d4f1;padding:15px;border-radius:8px;margin:10px 0;}}
.note{{background:#fff3e0;border-left:4px solid #ff9800;padding:8px 12px;margin:10px 0;font-size:13px;}}
</style></head><body>
<h1>📊 3L买点信号历史回测报告</h1>
<p style="color:#666;">生成: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 数据: 328只自选股60天历史 | 跟踪{LOOKBACK_DAYS}天</p>
<div class="summary"><p><b>{total}</b> 个买点信号 · 止损: 支撑位×0.98 · 止盈: <b>{int(R_MULTIPLIER)}R</b></p></div>
<h2>按买点类型</h2>
<table>
<tr><th>类型</th><th>总数</th><th>止盈</th><th>止损</th><th>超时</th><th>胜率</th><th>平均涨幅</th><th>平均R</th><th>平均盈利R</th></tr>
{rows}
</table>
<div class="note"><b>说明：</b>胜率=止盈数/总数。止盈=先触{int(R_MULTIPLIER)}R目标，止损=先触支撑下方2%。超时=5天内未触止损未触止盈。</div>
<h2>方向排名TOP10</h2>
<table><tr><th>方向</th><th>信号数</th><th>成功</th><th>胜率</th></tr>{dir_rows}</table>
<h2>最新信号示例</h2>
<table><tr><th>日期</th><th>股票</th><th>类型</th><th>收益</th><th>R</th><th>结果</th></tr>{rec_rows}</table>
<h2>局限</h2>
<ul><li>仅60天数据，样本有限</li><li>大盘统一"波中"未区分</li><li>未用板块主线阈值调整</li></ul>
<p style="color:#888;font-size:12px;text-align:center;margin:30px 0;">3L交易体系 · 历史回测数据仅供研究参考</p>
</body></html>'''
    
    with open(OUTPUT_HTML, 'w') as f:
        f.write(html)


if __name__ == '__main__':
    t0 = time.time()
    run()
    print(f"耗时: {time.time()-t0:.1f}秒")
