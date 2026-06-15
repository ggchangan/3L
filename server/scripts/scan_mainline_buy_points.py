#!/usr/bin/env python3
"""主线买点扫描 — 只聚焦当前主线板块+主线概念内的买点股"""
import json, os, sys, urllib.request, glob
from datetime import datetime

_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_SCRIPTS_DIR, '..'))
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

DATA_DIR = os.environ['DATA_DIR']
WATCHLIST = os.path.join(DATA_DIR, 'watchlist.json')

# ── 当前主线板块 ──
MAIN_LINE_SECTORS = {
    # 行业主线TOP10
    '元件', '煤炭开采加工', '电子化学品', '非金属材料', '自动化设备',
    '银行', '光学光电子', '金属新材料', '电机', '其他电子',
    # 概念主线TOP10
    '半导体', 'PCB', '消费电子', '先进封装', 'MiniLED',
    'OLED', '光刻机', '国家大基金',
}

# ── 腾讯实时行情 ──
def tencent_quotes(codes):
    result = {}
    for i in range(0, len(codes), 50):
        batch = codes[i:i+50]
        prefixed = []
        for c in batch:
            if c.startswith(('6','9')): prefixed.append(f'sh{c}')
            elif c.startswith('8'): prefixed.append(f'bj{c}')
            else: prefixed.append(f'sz{c}')
        url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode('gbk')
        for line in data.strip().split(';'):
            if not line.strip() or '=' not in line or '"' not in line: continue
            key = line.split('=')[0].split('_')[-1]
            vals = line.split('"')[1].split('~')
            if len(vals) < 53: continue
            code = key[2:]
            try:
                result[code] = {
                    'name': vals[1], 'price': float(vals[3]) if vals[3] else 0,
                    'change_pct': float(vals[32]) if vals[32] else 0,
                    'amount_wan': float(vals[37]) if vals[37] else 0,
                    'turnover_pct': float(vals[38]) if vals[38] else 0,
                }
            except: continue
    return result

# ── 主流程 ──
def main():
    print('📊 主线买点扫描...', file=sys.stderr)
    
    # 1. 加载自选股
    with open(WATCHLIST) as f:
        wl = json.load(f)
    stocks = wl.get('stocks', [])
    print(f'📝 自选股: {len(stocks)}只', file=sys.stderr)
    
    # 2. 按方向/板块筛选主线股
    mainline_stocks = []
    for s in stocks:
        direction = s.get('direction', '')
        sector_info = s.get('sector', '')
        # 检查方向或板块是否命中主线
        is_mainline = False
        for ml in MAIN_LINE_SECTORS:
            if ml in direction or ml in sector_info:
                is_mainline = True
                break
        if is_mainline:
            mainline_stocks.append(s)
    
    print(f'🔍 主线相关自选股: {len(mainline_stocks)}只', file=sys.stderr)
    for s in mainline_stocks:
        print(f'   {s["code"]} {s["name"]} dir={s.get("direction","")}', file=sys.stderr)
    
    # 3. 获取实时行情
    codes = [s['code'] for s in mainline_stocks]
    quotes = tencent_quotes(codes)
    
    # 4. 涨幅≤3%的候选
    candidates = [s for s in mainline_stocks if quotes.get(s['code'], {}).get('change_pct', 0) <= 3]
    print(f'🔍 涨幅≤3%: {len(candidates)}只', file=sys.stderr)
    
    # 5. 逐只检测买点
    from backend.services.stock_card_service import get_stock_card
    from backend.core.buy_point_detection import get_realtime_kline
    from backend.core.config import MAINLINES_CACHE_PATH, REVIEW_ARCHIVE_DIR
    
    today_str = datetime.now().strftime('%Y-%m-%d')
    market_position = '波中'
    main_lines = ['元件', '煤炭开采加工', '电子化学品', '非金属材料', '自动化设备']
    
    buy_cards = []
    for i, s in enumerate(candidates):
        code = s['code']
        name = s['name']
        direction = s.get('direction', '')
        chg = quotes.get(code, {}).get('change_pct', 0)
        print(f'  [{i+1}/{len(candidates)}] {name}({code}) chg={chg:+.2f}%...', file=sys.stderr)
        
        try:
            klines = get_realtime_kline(code, direction)
            if len(klines) < 30: continue
            
            card = get_stock_card(
                code=code, date_str=today_str,
                market_position=market_position,
                main_lines=main_lines,
                direction=direction,
                klines=klines,
            )
            if card.get('signal') != 'buy': continue
            
            buy_cards.append({
                'code': code, 'name': card.get('name', name),
                'price': card.get('price', 0),
                'change_pct': chg,
                'buy_type': card.get('buy_point', '') or '信号确认',
                'structure': card.get('structure', ''),
                'stage': card.get('stage', ''),
                'direction': direction,
                'sector': card.get('sector', ''),
                'score': card.get('score', 0),
                'vol_analysis': card.get('vol_analysis', ''),
                'stop_loss': card.get('stop_loss'),
                'stop_loss_pct': card.get('stop_loss_pct'),
                'action_type': card.get('action_type', ''),
                'action_signal': card.get('action_signal', ''),
                'action_priority': card.get('action_priority', ''),
                'action_reason': card.get('action_reason', ''),
            })
        except Exception as e:
            print(f'    ⚠️ {str(e)[:80]}', file=sys.stderr)
    
    # 排序
    buy_cards.sort(key=lambda x: (
        0 if x.get('structure') == '上涨趋势' else 1,
        0 if x.get('stage') in ('区间底部', '波谷') else 1,
        -(x.get('score', 0) or 0)
    ))
    
    # 输出JSON
    result = {
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_mainline_stocks': len(mainline_stocks),
        'candidates_after_filter': len(candidates),
        'buy_signals': len(buy_cards),
        'mainlines': list(MAIN_LINE_SECTORS),
        'signals': buy_cards,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
