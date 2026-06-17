#!/usr/bin/env python3
"""全量扫描买点 — 自选股+持仓+趋势股，过滤涨幅>3%的日内不追高"""
import json, os, sys, urllib.request, warnings
from datetime import datetime

# ── 确保能找到 backend 模块 ──
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
_SERVER_DIR = os.path.join(_SCRIPTS_DIR, '..')
sys.path.insert(0, _SERVER_DIR)
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

# ── 路径 ──
DATA_DIR = os.environ.get('DATA_DIR', '/home/ubuntu/data/3l')
WATCHLIST = os.path.join(DATA_DIR, 'watchlist.json')
TREND = os.path.join(DATA_DIR, 'private', 'manual_trend_stocks.json')

# ── 腾讯实时行情 ──
def tencent_quotes(codes):
    result = {}
    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i+batch_size]
        prefixed = []
        for c in batch:
            if c.startswith(('6', '9')):
                prefixed.append(f'sh{c}')
            elif c.startswith('8'):
                prefixed.append(f'bj{c}')
            else:
                prefixed.append(f'sz{c}')
        url = 'https://qt.gtimg.cn/q=' + ','.join(prefixed)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=15)
        data = resp.read().decode('gbk')
        for line in data.strip().split(';'):
            if not line.strip() or '=' not in line or '"' not in line:
                continue
            key = line.split('=')[0].split('_')[-1]
            vals = line.split('"')[1].split('~')
            if len(vals) < 53:
                continue
            code = key[2:]
            try:
                result[code] = {
                    'name': vals[1],
                    'price': float(vals[3]) if vals[3] else 0,
                    'change_pct': float(vals[32]) if vals[32] else 0,
                    'change_amt': float(vals[31]) if vals[31] else 0,
                    'high': float(vals[33]) if vals[33] else 0,
                    'low': float(vals[34]) if vals[34] else 0,
                    'amount_wan': float(vals[37]) if vals[37] else 0,
                    'turnover_pct': float(vals[38]) if vals[38] else 0,
                }
            except (ValueError, IndexError):
                continue
    return result

# ── 加载所有股票 ──
def load_all_stocks():
    codes = set()
    code_sources = {}
    
    with open(WATCHLIST) as f:
        wl = json.load(f)
    for s in wl.get('stocks', []):
        c = s['code']
        codes.add(c)
        code_sources.setdefault(c, []).append('自选股')
    
    from backend.services.holdings_service import get_holdings
    hl = get_holdings()
    for h in hl.get('holdings', []):
        c = h['code']
        codes.add(c)
        code_sources.setdefault(c, []).append('持仓')
    
    with open(TREND) as f:
        tr = json.load(f)
    for t in tr:
        c = t if isinstance(t, str) else t.get('code', '')
        if c:
            codes.add(c)
            code_sources.setdefault(c, []).append('趋势股')
    
    return sorted(codes), code_sources

# ── 买点检测 ──
def check_buy_signal(code):
    try:
        from backend.services.stock_card_service import get_stock_card
        from backend.core.buy_point_detection import get_realtime_kline
        
        klines = get_realtime_kline(code, '')
        if len(klines) < 30:
            return None
        
        today_str = datetime.now().strftime('%Y-%m-%d')
        market_position = '波中'
        main_lines = []
        try:
            from backend.core.config import MAINLINES_CACHE_PATH, REVIEW_ARCHIVE_DIR
            if os.path.isfile(MAINLINES_CACHE_PATH):
                with open(MAINLINES_CACHE_PATH) as f:
                    mc = json.load(f)
                main_lines = mc.get('lines', [])
            archive_dir = REVIEW_ARCHIVE_DIR
            if os.path.isdir(archive_dir):
                archives = sorted([f for f in os.listdir(archive_dir) if f.endswith('.json')])
                if archives:
                    with open(os.path.join(archive_dir, archives[-1])) as f:
                        rd = json.load(f)
                    market_position = rd.get('market', {}).get('position', '波中')
        except Exception:
            pass
        
        card = get_stock_card(
            code=code, date_str=today_str,
            market_position=market_position,
            main_lines=[l.strip() for l in main_lines if isinstance(l, str)],
            direction='', klines=klines,
        )
        return card if card.get('signal') == 'buy' else None
    except Exception as e:
        print(f'  ⚠️ {code} 检测失败: {str(e)[:100]}', file=sys.stderr)
        return None

# ── 主流程 ──
def main():
    print('📊 全量买点扫描...', file=sys.stderr)
    all_codes, code_sources = load_all_stocks()
    print(f'📝 总股票数: {len(all_codes)} 只', file=sys.stderr)
    
    quotes = tencent_quotes(all_codes)
    print(f'📡 实时行情: {len(quotes)} 只', file=sys.stderr)
    
    candidates = []
    for code in all_codes:
        q = quotes.get(code)
        if q is None:
            continue
        chg = q.get('change_pct', 0)
        if chg > 3:
            continue
        candidates.append(code)
    
    print(f'🔍 涨幅≤3%: {len(candidates)} 只', file=sys.stderr)
    
    buy_cards = []
    for i, code in enumerate(candidates):
        q = quotes.get(code, {})
        name = q.get('name', code)
        chg = q.get('change_pct', 0)
        print(f'  [{i+1}/{len(candidates)}] {name}({code}) chg={chg:+.2f}%...', file=sys.stderr)
        
        card = check_buy_signal(code)
        if not card:
            continue
        
        sources = ' '.join(code_sources.get(code, []))
        buy_cards.append({
            'code': code, 'name': card.get('name', name),
            'price': card.get('price', 0),
            'change_pct': chg,
            'change': card.get('change', 0),
            'signal': card.get('signal', 'buy'),
            'buy_type': card.get('buy_point', ''),
            'structure': card.get('structure', ''),
            'stage': card.get('stage', ''),
            'direction': card.get('direction', ''),
            'sector': card.get('sector', ''),
            'score': card.get('score', 0),
            'trading_system': card.get('trading_system', '3l'),
            'vol_analysis': card.get('vol_analysis', ''),
            'sources': sources,
            'stop_loss': card.get('stop_loss'),
            'stop_loss_pct': card.get('stop_loss_pct'),
            'action_type': card.get('action_type', ''),
            'action_signal': card.get('action_signal', ''),
            'action_priority': card.get('action_priority', ''),
            'action_reason': card.get('action_reason', ''),
        })
    
    # 排序
    buy_cards.sort(key=lambda x: (
        0 if x.get('action_type') == '买入' else 1,
        -(x.get('score', 0) or 0)
    ))
    
    # 输出 JSON
    result = {
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_scanned': len(all_codes),
        'candidates_after_filter': len(candidates),
        'buy_signals': len(buy_cards),
        'signals': buy_cards,
    }
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
