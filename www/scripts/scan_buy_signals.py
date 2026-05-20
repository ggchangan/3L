#!/usr/bin/env python3
"""
盘中买点扫描 - 每1小时运行一次
重点扫描 算力 + 半导体 方向的个股
"""
import json, os, sys, requests
from datetime import datetime, timedelta

# 自选股数据
STOCKS_FILE = '/home/ubuntu/data/3l/all_stocks_60d.json'
# 方向过滤：算力+半导体
FOCUS_DIRECTIONS = ['算力', '半导体']

def load_stocks():
    """加载自选股"""
    if not os.path.isfile(STOCKS_FILE):
        return []
    with open(STOCKS_FILE) as f:
        data = json.load(f)
    stocks = data.get('stocks', data) if isinstance(data, dict) else data
    # 格式: {方向: {代码: {info}, ...}, ...}
    focused = []
    if isinstance(stocks, dict):
        for direction, codes in stocks.items():
            if direction not in FOCUS_DIRECTIONS:
                continue
            if isinstance(codes, dict):
                for code, info in codes.items():
                    if isinstance(info, dict):
                        info['code'] = info.get('code', code)
                        info['direction'] = direction
                        focused.append(info)
                    else:
                        focused.append({'code': code, 'direction': direction, 'name': str(info)})
    return focused

def get_real_time_quote(code):
    """获取个股实时行情"""
    try:
        # 统一加前缀
        qcode = code
        if not code.startswith(('sh', 'sz', 'SH', 'SZ')):
            qcode = ('sh' if code.startswith(('6', '9')) else 'sz') + code
        r = requests.get(f'https://qt.gtimg.cn/q={qcode}',
                        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                        timeout=5)
        line = r.text.strip()
        fields = line.split('"')[1].split('~') if '"' in line else []
        if len(fields) < 40:
            return None
        return {
            'name': fields[1],
            'code': fields[2],
            'price': float(fields[3]),
            'close': float(fields[4]),
            'open': float(fields[5]),
            'volume': int(fields[6]) if fields[6].isdigit() else 0,
            'high': float(fields[33]) if fields[33] else 0,
            'low': float(fields[34]) if fields[34] else 0,
            'change_pct': float(fields[32]) if fields[32] else 0,
            'change': float(fields[31]) if fields[31] else 0,
        }
    except:
        return None

def check_zhongji_buy(quote, klines):
    """简化的中继买点检查——盘中实时版
    条件：回踩MA20 + 缩量 + MA5交叉MA10上方
    """
    if not quote or not klines or len(klines) < 20:
        return False
    
    price = quote['price']
    ma20 = sum(k['close'] for k in klines[-20:]) / 20
    ma10 = sum(k['close'] for k in klines[-10:]) / 10
    ma5 = sum(k['close'] for k in klines[-5:]) / 5
    
    # 条件1: 价格在MA20上方（回踩中）
    if price < ma20 * 0.98:
        return False
    
    # 条件2: MA5 > MA10（短期趋势向上）
    if ma5 <= ma10:
        return False
    
    # 条件3: 缩量（今日量 < MA5日均量×1.2）
    vol_ma5 = sum(k['volume'] for k in klines[-5:]) / 5
    today_vol = quote['volume']
    if vol_ma5 > 0 and today_vol > vol_ma5 * 1.2:
        return False
    
    # 条件4: 不追高（涨幅不过大）
    if quote['change_pct'] > 5:
        return False
    
    return True

def get_60d_klines(code):
    """获取60日K线"""
    qcode = code
    if not code.startswith(('sh', 'sz', 'SH', 'SZ')):
        qcode = ('sh' if code.startswith(('6', '9')) else 'sz') + code
    try:
        r = requests.get(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={qcode},day,,,60,qfq',
                        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                        timeout=10)
        data = r.json()
        klines = data.get('data', {}).get(qcode, {})
        day_data = klines.get('qfqday', klines.get('day', []))
        return [{'date': k[0], 'close': float(k[2]), 'volume': float(k[5])} 
                for k in day_data if len(k) >= 6]
    except:
        return []

def main():
    stocks = load_stocks()
    print(f"加载自选股: {len(stocks)}只 (方向={FOCUS_DIRECTIONS})", file=sys.stderr)
    
    signals = []
    for s in stocks:
        code = s.get('code', '')
        name = s.get('name', code)
        direction = s.get('direction', '')
        
        # 获取实时行情
        quote = get_real_time_quote(code)
        if not quote:
            continue
        
        # 获取K线数据
        klines = get_60d_klines(code)
        
        # 检查中继买点
        if check_zhongji_buy(quote, klines):
            signals.append({
                'code': code,
                'name': quote.get('name', name),
                'price': quote['price'],
                'change_pct': quote['change_pct'],
                'direction': direction,
                'type': '中继买点',
            })
    
    # 按涨幅排序（回调越深优先级越高）
    signals.sort(key=lambda x: abs(x['change_pct']))
    
    result = {
        'signals': signals,
        'count': len(signals),
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'focused_directions': FOCUS_DIRECTIONS,
        'stocks_scanned': len(stocks),
    }
    
    print(json.dumps(result, ensure_ascii=False))

if __name__ == '__main__':
    main()
