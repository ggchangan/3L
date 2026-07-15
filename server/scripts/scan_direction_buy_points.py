#!/usr/bin/env python3
"""按用户方向扫描买点 — 聚焦热点方向内的买点股"""
import json, os, sys, urllib.request
from datetime import datetime

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, '..'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

DATA_DIR = os.environ['DATA_DIR']
WATCHLIST = os.path.join(DATA_DIR, 'watchlist.json')

def tencent_quotes(codes):
    result = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        prefixed = ['sh'+c if c.startswith(('6','9')) else ('bj'+c if c.startswith('8') else 'sz'+c) for c in batch]
        url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        for line in resp.read().decode('gbk').strip().split(';'):
            if not line.strip() or '=' not in line or '"' not in line: continue
            key = line.split('=')[0].split('_')[-1]
            vals = line.split('"')[1].split('~')
            if len(vals) < 53: continue
            code = key[2:]
            try:
                result[code] = {'name': vals[1], 'price': float(vals[3]) if vals[3] else 0,
                    'change_pct': float(vals[32]) if vals[32] else 0,}
            except: continue
    return result

def main():
    print('📊 热点方向买点扫描...', file=sys.stderr)
    
    with open(WATCHLIST) as f:
        wl = json.load(f)
    
    # 按方向分组
    direction_groups = {}
    for s in wl.get('stocks', []):
        d = s.get('direction', '其他')
        direction_groups.setdefault(d, []).append(s)
    
    print(f'📝 共{len(direction_groups)}个方向, {sum(len(v) for v in direction_groups.values())}只股', file=sys.stderr)
    
    all_codes = [s['code'] for stocks in direction_groups.values() for s in stocks]
    quotes = tencent_quotes(all_codes)
    print(f'📡 实时行情: {len(quotes)}只', file=sys.stderr)
    
    # 导入检测
    from backend.services.stock_card_service import get_stock_card
    from backend.core.buy_point_detection import get_realtime_kline
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    main_lines = ['元件', '煤炭开采加工', '电子化学品', '非金属材料', '自动化设备']
    market_position = '波中'
    
    results = {}
    
    for direction, stocks in sorted(direction_groups.items()):
        buy_in_dir = []
        for s in stocks:
            code = s['code']
            q = quotes.get(code, {})
            chg = q.get('change_pct', 0)
            if chg > 3: continue  # 不追高
            
            try:
                klines = get_realtime_kline(code, direction)
                if len(klines) < 30: continue
                card = get_stock_card(code=code, date_str=today_str,
                    market_position=market_position, main_lines=main_lines,
                    direction=direction, klines=klines)
                if card.get('signal') != 'buy': continue
                buy_in_dir.append({
                    'code': code, 'name': card.get('name', q.get('name', code)),
                    'price': card.get('price', 0), 'change_pct': chg,
                    'buy_type': card.get('buy_point', '') or '信号确认',
                    'structure': card.get('structure', ''),
                    'stage': card.get('stage', ''),
                    'sector': card.get('sector', ''),
                    'score': card.get('score', 0),
                    'vol_analysis': card.get('vol_analysis', ''),
                    'stop_loss': card.get('stop_loss'),
                    'stop_loss_pct': card.get('stop_loss_pct'),
                })
            except Exception as e:
                print(f'  ⚠️ {code}: {str(e)[:80]}', file=sys.stderr)
        
        if buy_in_dir:
            buy_in_dir.sort(key=lambda x: -(x.get('score', 0) or 0))
            results[direction] = buy_in_dir
    
    print('\n' + '=' * 80)
    print(f'✅ 扫描完成 — 热点方向买点股汇总')
    print(f'   时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'   含买点的方向: {len(results)}个')
    print('=' * 80)
    
    total = 0
    for direction, items in sorted(results.items()):
        total += len(items)
        print(f'\n🔥 {direction} ({len(items)}只):')
        for c in items:
            action = f'🔴 {c["buy_type"]}' if c['buy_type'] != '信号确认' else f'🟡 信号确认'
            print(f'  {action} {c["name"]}({c["code"]}) chg={c["change_pct"]:+.2f}% score={c["score"]} {c["structure"]}/{c["stage"]}')
            if c.get('vol_analysis') and c['vol_analysis'] != '--':
                print(f'        {c["vol_analysis"]}  止损:{c["stop_loss"]}({c["stop_loss_pct"]:.1f}%)')
    
    if total == 0:
        print('\n❌ 没有找到符合条件的买点股')

if __name__ == '__main__':
    main()
