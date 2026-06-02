#!/usr/bin/env python3
"""
3L 盯盘数据服务 - 数据采集模块
数据源协定优先级：
  1. mootdx（通达信）— 首选
  2. 腾讯财经 — 备选（mootdx不可用时）
"""
import os, json, time, requests, sys
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

from mootdx.quotes import Quotes

sys.path.insert(0, '/home/ubuntu/3l-server')
from backend.core.data_layer import CACHE_DIR as DL_CACHE_DIR, REVIEW_ARCHIVE_DIR, REVIEW_CHARTS_DIR, INDUSTRY_LEADERS_PATH, SCRIPTS_DIR

CACHE_DIR = DL_CACHE_DIR
os.makedirs(CACHE_DIR, exist_ok=True)

# 中证全指代码
INDEX_CODE = '000985'
# 有效指数价格范围（用于校验mootdx数据是否合理）
INDEX_PRICE_MIN = 1000  # 中证全指正常应在5000-8000

def _is_trading_time():
    """判断当前是否为A股交易时间（周一至五 9:30-15:00）"""
    now = datetime.now()
    if now.weekday() >= 5:  # 非交易日
        return False
    t = now.hour * 60 + now.minute
    return 9 * 60 + 30 <= t <= 15 * 60

# ========== 数据源工具 ==========

def _mootdx_quote():
    """[源1] 尝试从mootdx获取指数行情"""
    try:
        ctx = Quotes.factory(method='remote')
        # 获取日K线（最近1天），检查数据是否合理
        df = ctx.bars(symbol=INDEX_CODE, frequency=9, start=0, count=1)
        if df is not None and len(df) > 0:
            close = float(df['close'].iloc[-1])
            if close > INDEX_PRICE_MIN:
                return df, close
        return None, None
    except Exception as e:
        return None, None

def _tencent_quote_raw():
    """[源2] 腾讯财经原始行情字符串"""
    r = requests.get('https://qt.gtimg.cn/q=sh000985',
                    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                    timeout=10)
    r.encoding = 'gbk'
    line = r.text.strip()
    fields = line.split('"')[1].split('~') if '"' in line else line.split('~')
    return fields

def _tencent_daily_kline(days=5):
    """[源2] 腾讯财经日K线"""
    r = requests.get(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,{days},qfq',
                    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                    timeout=10)
    return r.json()

def _tencent_minute_data():
    """[源2] 腾讯财经今日分钟数据"""
    r = requests.get('https://ifzq.gtimg.cn/appstock/app/minute/query?code=sh000985',
                    headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                    timeout=10)
    return r.json()


# ========== 指数实时行情 ==========

def get_index_quote():
    """
    获取中证全指实时行情
    源1: mootdx（通达信）→ 校验价格合理性
    源2: 腾讯财经 → 备选
    """
    # --- 源1: mootdx ---
    try:
        ctx = Quotes.factory(method='remote')
        df = ctx.bars(symbol=INDEX_CODE, frequency=9, start=0, count=2)
        if df is not None and len(df) >= 2:
            last = df.iloc[-1]
            prev = df.iloc[-2]
            close = float(last['close'])
            if close > INDEX_PRICE_MIN:
                # mootdx数据合理, 取amount作为成交额
                amount = float(last['amount'])
                return {
                    'price': close,
                    'close': float(prev['close']),
                    'volume': int(last['vol']),
                    'amount_yuan': int(amount),
                    'change_pct': round((close / float(prev['close']) - 1) * 100, 2),
                    'change': round(close - float(prev['close']), 2),
                    'source': 'mootdx',
                }
    except Exception as e:
        pass  # fall through to腾讯

    # --- 源2: 腾讯财经 ---
    try:
        fields = _tencent_quote_raw()
        amount_yuan = 0
        if '/' in fields[35]:
            amt_parts = fields[35].split('/')
            if len(amt_parts) >= 3:
                amount_yuan = int(amt_parts[2])
        return {
            'price': float(fields[3]),
            'close': float(fields[4]),
            'volume': int(fields[6]) if fields[6].isdigit() else 0,
            'amount_yuan': amount_yuan,
            'change_pct': float(fields[32]) if fields[32] else 0,
            'change': float(fields[31]) if fields[31] else 0,
            'time': fields[30] if len(fields) > 30 else '',
            'high': float(fields[33]) if len(fields) > 33 else 0,
            'low': float(fields[34]) if len(fields) > 34 else 0,
            'source': 'tencent',
        }
    except Exception as e:
        return {'error': str(e)}


# ========== 昨日总数据 ==========

def get_yesterday_total():
    """
    获取昨日总成交量+总成交额
    源1: mootdx → 校验价格合理性
    源2: 腾讯财经日K线 → 备选
    """
    yesterday_date = None
    prev_date = get_previous_trading_day_str()
    
    # --- 源1: mootdx ---
    try:
        ctx = Quotes.factory(method='remote')
        df = ctx.bars(symbol=INDEX_CODE, frequency=9, start=0, count=5)
        if df is not None and len(df) >= 2:
            last = df.iloc[-1]
            close = float(last['close'])
            if close > INDEX_PRICE_MIN:
                # mootdx数据合理，取昨日数据
                yest = df.iloc[-2]
                yest_close = float(yest['close'])
                if INDEX_PRICE_MIN < yest_close < 20000:
                    return {
                        'date': prev_date,
                        'volume': int(yest['vol']),
                        'amount': float(yest['amount']),
                        'close': yest_close,
                        'source': 'mootdx',
                    }
    except:
        pass
    
    # --- 源2: 腾讯财经 ---
    try:
        data = _tencent_daily_kline(2)
        days = data.get('data', {}).get('sh000985', {}).get('day', [])
        if len(days) >= 2:
            yest = days[-2]
            # 日K线只有volume(手数)没有amount，需估算
            return {
                'date': yest[0],
                'volume': int(float(yest[5])),
                'close': float(yest[2]),
                'source': 'tencent',
            }
    except:
        pass
    
    return None


# ========== 工具函数 ==========

def today_str():
    return datetime.now().strftime('%Y-%m-%d')

def is_trading_hours():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    t = now.hour * 100 + now.minute
    return (915 <= t <= 1130) or (1300 <= t <= 1500)

def get_previous_trading_day_str():
    """获取上一个交易日字符串"""
    d = datetime.now()
    for _ in range(7):
        d -= timedelta(days=1)
        if d.weekday() < 5:
            return d.strftime('%Y-%m-%d')
    return None


# ========== 快照系统（缓存今日/昨日分时累计成交额） ==========

def record_volume_snapshot():
    """记录当前成交量快照（来自腾讯实时行情，mootdx无实时行情接口）"""
    quote = get_index_quote()
    if 'error' in quote:
        return
    today = today_str()
    snap_file = os.path.join(CACHE_DIR, f'volume_snapshots_{today}.json')
    
    snaps = []
    if os.path.isfile(snap_file):
        try:
            with open(snap_file) as f:
                snaps = json.load(f)
        except:
            snaps = []
    
    now = datetime.now()
    time_key = now.strftime('%H:%M')
    
    snaps = [s for s in snaps if s['time'] != time_key]
    snaps.append({
        'time': time_key,
        'amount_yuan': quote.get('amount_yuan', 0),
        'price': quote.get('price', 0),
        'timestamp': now.strftime('%Y-%m-%d %H:%M:%S')
    })
    snaps.sort(key=lambda x: x['time'])
    
    with open(snap_file, 'w') as f:
        json.dump(snaps[-480:], f)

def get_volume_snapshots(date_str=None):
    if date_str is None:
        date_str = today_str()
    snap_file = os.path.join(CACHE_DIR, f'volume_snapshots_{date_str}.json')
    if os.path.isfile(snap_file):
        try:
            with open(snap_file) as f:
                return json.load(f)
        except:
            return []
    return []


# ========== 今日分钟曲线（腾讯分钟API，mootdx无法提供实时分钟数据） ==========

def get_today_minute_curve():
    """
    获取今日每分钟累积成交额曲线
    说明：mootdx没有实时分钟数据接口，使用腾讯minute/query
    """
    try:
        data = _tencent_minute_data()
        minutes = data['data']['sh000985']['data']['data']
        curve = []
        for m in minutes:
            parts = m.split()
            if len(parts) >= 4:
                time_str = parts[0][:2] + ':' + parts[0][2:]
                amount = float(parts[3])
                curve.append({'time': time_str, 'amount': amount})
        return curve
    except Exception as e:
        print(f"[WARN] 获取分钟曲线失败: {e}")
        return []


# ========== 成交额对比（两日同一时间点） ==========

def get_volume_comparison():
    """
    两日成交额对比
    今日曲线：腾讯minute/query（实时分钟数据）
    昨日曲线：优先快照缓存 → 无缓存则用估算
    """
    # 先记录当前快照
    record_volume_snapshot()
    
    # 实时行情
    quote = get_index_quote()
    current_price = quote.get('price', 0)
    current_change = quote.get('change_pct', 0)
    current_time = quote.get('time', '')
    current_vol = quote.get('amount_yuan', 0) if 'error' not in quote else 0
    quote_source = quote.get('source', '')
    
    # 昨日总数据
    yesterday_info = get_yesterday_total()
    yesterday_date = yesterday_info['date'] if yesterday_info else ''
    yesterday_source = yesterday_info.get('source', '') if yesterday_info else ''
    
    # --- 今日曲线 ---
    today_curve = get_today_minute_curve()

    # --- 昨日总成交额（仅数值，不要分钟曲线） ---
    yesterday_total_amount = 0
    is_estimated = True
    yesterday_snaps = get_volume_snapshots(yesterday_date)
    if yesterday_snaps and len(yesterday_snaps) > 5:
        # 从昨日快照末条取总成交额
        last_snap = max(yesterday_snaps, key=lambda s: s.get('time', ''))
        yesterday_total_amount = last_snap.get('amount_yuan', last_snap.get('amount', last_snap.get('volume', 0)))
        is_estimated = False
    elif yesterday_date and yesterday_info.get('volume', 0) > 0:
        # 无快照 → 用腾讯volume估算（手×均价）
        vol = yesterday_info['volume']
        avg_price = current_price if current_price > 0 else 6500
        yesterday_total_amount = vol * avg_price * 100  # 手→股 × 均价
        is_estimated = True

    today_total_amount = today_curve[-1]['amount'] if today_curve else 0

    amount_ratio = None
    if yesterday_total_amount > 0 and today_total_amount > 0:
        amount_ratio = round(today_total_amount / yesterday_total_amount * 100, 1)

    result = {
        'today_amount_yuan': today_total_amount,
        'yesterday_amount_yuan': yesterday_total_amount,
        'yesterday_date': yesterday_date,
        'today_curve': today_curve,
        'yesterday_curve': [],  # 不再返回昨日分钟曲线（数据不可靠）
        'yesterday_is_estimated': is_estimated,
        'current_price': current_price,
        'current_change': current_change,
        'current_time': current_time,
        'is_trading': is_trading_hours(),
        'update_time': datetime.now().strftime('%H:%M:%S'),
        'data_source': {
            'quote': quote_source,
            'yesterday': yesterday_source,
            'yesterday_curve': 'none',  # 不再提供昨日曲线
        },
        'amount_ratio': amount_ratio,
    }

    return result


# ========== 原有函数（未改动） ==========

def _calc_trading_progress():
    now = datetime.now()
    t = now.hour * 60 + now.minute
    morning_start = 9 * 60 + 30
    morning_end = 11 * 60 + 30
    afternoon_start = 13 * 60
    afternoon_end = 15 * 60
    total = (morning_end - morning_start) + (afternoon_end - afternoon_start)
    if t < morning_start:
        return 0
    elif t <= morning_end:
        return (t - morning_start) / total
    elif t < afternoon_start:
        return (morning_end - morning_start) / total
    elif t <= afternoon_end:
        return ((morning_end - morning_start) + (t - afternoon_start)) / total
    else:
        return 1

def get_existing_holdings():
    holdings_file = os.path.join(REVIEW_ARCHIVE_DIR, today_str() + '.json')
    if not os.path.isfile(holdings_file):
        archive_dir = REVIEW_ARCHIVE_DIR
        os.makedirs(archive_dir, exist_ok=True)
        files = sorted([f for f in os.listdir(archive_dir) if f.endswith('.json')], reverse=True)
        if not files:
            return []
        holdings_file = os.path.join(archive_dir, files[0])
    try:
        with open(holdings_file) as f:
            data = json.load(f)
        return data.get('holdings', data.get('holdings_review', []))
    except:
        return []

def analyze_sector_structure(daily_chgs, closes, today_chg=0):
    """
    分析板块结构和阶段
    closes: list of close prices (从远到近, 索引0=最远, -1=最近)
    daily_chgs: list of daily change percentages (used for phase judgment)
    today_chg: 今日实时涨跌幅
    返回 (结构, 阶段)
    """
    n_close = len(closes)
    n_chg = len(daily_chgs)
    
    if n_close < 3:
        return '数据不足', ''
    
    # --- 结构判断（基于EMA10趋势，15天视角） ---
    def ema(data, p):
        r = [None]*len(data)
        m = 2/(p+1)
        for i in range(len(data)):
            if i == 0:
                r[i] = data[i]
            elif r[i-1] is not None:
                r[i] = (data[i]-r[i-1])*m+r[i-1]
        return r
    
    e10 = ema(closes, 10)
    
    if n_close >= 10 and e10[-1] is not None:
        # 统一用5天前的EMA10做对比（15天视角）
        if n_close >= 15 and e10[-6] is not None:
            slope = (e10[-1] - e10[-6]) / e10[-6] * 100
        elif e10[-3] is not None:
            slope = (e10[-1] - e10[-3]) / e10[-3] * 100
        else:
            slope = 0
        
        if slope > 0.3:
            structure = '📈 上涨趋势'
        elif slope < -0.3:
            structure = '📉 下降趋势'
        else:
            structure = '➡ 区间震荡'
    else:
        chg_5d = (closes[-1] / closes[0] - 1) * 100
        if chg_5d > 3:
            structure = '📈 上涨趋势'
        elif chg_5d < -3:
            structure = '📉 下降趋势'
        else:
            structure = '➡ 区间震荡'
    
    # --- 阶段判断 ---
    if n_chg < 2:
        return structure, ''
    
    last2_days = list(daily_chgs[-2:]) if n_chg >= 2 else list(daily_chgs)
    last3 = last2_days + [today_chg]
    prev3 = daily_chgs[-5:-2] if n_chg >= 5 else daily_chgs[:n_chg-2] if n_chg >= 3 else []
    
    avg_last3 = sum(last3) / len(last3) if last3 else 0
    avg_prev3 = sum(prev3) / len(prev3) if prev3 else 0
    
    all_positive_last3 = all(c > 0 for c in last3)
    all_negative_last3 = all(c < 0 for c in last3)
    
    if all_positive_last3 and avg_last3 > 1.5 and all(c > 0.5 for c in last3):
        phase = '🚀 加速'
    elif avg_prev3 > 1.0 and avg_last3 < 0.3:
        phase = '⚠️ 滞涨'
    elif avg_prev3 < -1.0 and avg_last3 > 1.5 and last3[-1] > 2:
        phase = '🔄 反转向上'
    elif avg_prev3 > 1.0 and avg_last3 < -1.5 and last3[-1] < -2:
        phase = '🔄 反转向下'
    elif avg_last3 > 0.8 and all_positive_last3:
        phase = '↑ 强势'
    elif avg_last3 < -0.8 and all_negative_last3:
        phase = '↓ 弱势'
    elif abs(avg_last3) < 0.3:
        phase = '— 横盘'
    else:
        phase = ''
    
    return structure, phase


def get_top_sectors_with_5d():
    """
    获取板块排行
    - 「今日涨幅TOP10」：今日涨跌幅前10
    - 「5日涨幅TOP10」：近5交易日累计涨幅前10
    流程：取今日涨幅TOP15 → 拉60日OHLCV → 统一计算结构/阶段/5日涨幅
    数据源：同花顺板块指数（akshare stock_board_industry_index_ths）
    """
    REVIEW_CHARTS = REVIEW_CHARTS_DIR
    os.makedirs(REVIEW_CHARTS, exist_ok=True)
    
    # --- 今日数据（交易时间10分钟刷新，非交易时间不刷新） ---
    today_cache_file = os.path.join(CACHE_DIR, f'industry_boards_{today_str()}.json')
    today_data = None
    
    if os.path.isfile(today_cache_file):
        cache_age = time.time() - os.path.getmtime(today_cache_file)
        if _is_trading_time():
            # 交易时间：10分钟TTL，过期重新拉取
            if cache_age < 600:
                with open(today_cache_file) as f:
                    raw = json.load(f)
                today_data = raw.get('data', raw) if isinstance(raw, dict) else raw
        else:
            # 非交易时间：直接用缓存，不刷新
            try:
                with open(today_cache_file) as f:
                    raw = json.load(f)
                today_data = raw.get('data', raw) if isinstance(raw, dict) else raw
            except (json.JSONDecodeError, FileNotFoundError):
                today_data = None
    
    if today_data is None:
        try:
            r = requests.get('http://127.0.0.1:8080/api/industry-boards',
                            headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            today_data = r.json().get('data', [])
            # 保存到缓存
            if today_data:
                try:
                    with open(today_cache_file, 'w') as f:
                        json.dump({'date': today_str(), 'data': today_data}, f, ensure_ascii=False)
                except:
                    pass
        except:
            return {'today_top5': [], 'chg5d_top5': []}
    
    today_sorted = sorted(today_data, key=lambda x: float(x.get('涨跌幅', 0) or 0), reverse=True)
    top15_names = [b['板块'] for b in today_sorted[:15]]
    
    # 今日实时涨跌幅查表
    today_chg_map = {b.get('板块', ''): float(b.get('涨跌幅', 0) or 0) for b in today_data}
    
    # --- 对TOP15拉60日OHLCV（或读缓存） ---
    def _fetch_60d(name):
        """拉60日K线并缓存为kline JSON，返回数据字典"""
        kf = os.path.join(REVIEW_CHARTS, f'sector_{name}_kline.json')
        if os.path.isfile(kf):
            cache_age = time.time() - os.path.getmtime(kf)
            if cache_age < 3600:  # 1小时TTL
                try:
                    with open(kf) as f:
                        return json.load(f)
                except:
                    pass
        
        # 需要重新拉取
        try:
            import akshare as ak
            now = datetime.now()
            start_d = now - timedelta(days=90)
            df = ak.stock_board_industry_index_ths(
                symbol=name, start_date=start_d.strftime('%Y%m%d'),
                end_date=now.strftime('%Y%m%d')
            )
            if df is None or len(df) < 10:
                return None
            
            closes = df['收盘价'].values.tolist()
            highs = df['最高价'].values.tolist()
            lows = df['最低价'].values.tolist()
            opens = df['开盘价'].values.tolist()
            volumes = df['成交量'].values.tolist() if '成交量' in df.columns else []
            
            # 计算突破点（第2类关键点）
            key_points = []
            for i in range(10, len(closes)):
                if highs[i] > max(highs[max(0,i-10):i]) and closes[i] > opens[i]:
                    key_points.append({'label': '突', 'y': highs[i]})
            
            kd = {
                'closes': closes, 'highs': highs, 'lows': lows,
                'opens': opens, 'volumes': volumes,
                'key_points': key_points,
                'close_now': closes[-1], 'high_60': max(highs), 'low_60': min(lows),
            }
            try:
                with open(kf, 'w') as f:
                    json.dump(kd, f, ensure_ascii=False)
            except:
                pass
            return kd
        except:
            return None
    
    # === 今日涨幅TOP10（用TOP15的60日数据计算结构/阶段/5日涨幅） ===
    # 并行拉取TOP15的60日数据
    import concurrent.futures
    s60d = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        fut = {executor.submit(_fetch_60d, name): name for name in top15_names}
        for f in concurrent.futures.as_completed(fut, timeout=120):
            name = fut[f]
            r = f.result()
            if r is not None:
                s60d[name] = r
    
    # === 5日涨幅：检查全部90个板块中已有缓存的数据 ===
    # 对今日涨幅TOP15之外的板块，只读缓存不算结构/阶段
    all_sector_names = [b['板块'] for b in today_data]
    for name in all_sector_names:
        if name in s60d:
            continue
        kf = os.path.join(REVIEW_CHARTS, f'sector_{name}_kline.json')
        if os.path.isfile(kf):
            try:
                with open(kf) as f:
                    kd = json.load(f)
                if kd and 'closes' in kd and len(kd['closes']) >= 6:
                    c60 = kd['closes']
                    cur = c60[-1]
                    chg5d = round((cur / c60[-6] - 1) * 100, 2)
                    s60d[name] = kd  # 加入s60d供_compute_one用
            except:
                pass
    
    # === 工具函数 ===
    def _ema_list(d, p):
        r = [None]*len(d); m = 2/(p+1)
        for i in range(len(d)):
            if i == 0: r[i] = d[i]
            elif r[i-1] is not None: r[i] = (d[i]-r[i-1])*m+r[i-1]
        return r
    
    def _reg_slope(y_list):
        n = len(y_list); xs = list(range(n))
        mx = sum(xs)/n; my = sum(y_list)/n
        num = sum((xs[i]-mx)*(y_list[i]-my) for i in range(n))
        den = sum((xs[i]-mx)**2 for i in range(n))
        return num/den if den else 0
    
    def _compute_one(name, chg_today):
        """计算单个板块的结构、阶段、5日涨幅"""
        kd = s60d.get(name)
        if not kd:
            return {'name': name, 'chg': chg_today, 'structure': '-', 'phase': '-'}
        
        c60 = kd['closes']
        h60 = kd['highs']
        l60 = kd['lows']
        kps = kd.get('key_points', [])
        cur = c60[-1]
        
        # 20日涨幅
        chg20d = 0
        if len(c60) >= 21:
            chg20d = round((cur / c60[-21] - 1) * 100, 2)
        
        # 结构（看EMA10极值位置，取最近15日）
        c15 = c60[-15:] if len(c60) >= 15 else c60
        e10 = _ema_list(c15, 10)
        n = len(e10)
        max_pos = max(range(n), key=lambda i: e10[i])
        min_pos = min(range(n), key=lambda i: e10[i])
        first_q = n // 4              # 前25%边界
        last_q = n - 1 - n // 4       # 后25%边界
        if max_pos >= last_q and min_pos <= first_q:
            structure = '📈 上涨趋势'
        elif min_pos >= last_q and max_pos <= first_q:
            structure = '📉 下降趋势'
        else:
            structure = '➡ 区间震荡'
        
        # 阶段（用EMA10半段斜率对比）
        half = max(1, len(e10) // 2)
        s1 = _reg_slope(e10[:half])
        s2 = _reg_slope(e10[half:])
        
        if structure == '📈 上涨趋势':
            if s1 > 0 and s2 > 0:
                ratio = s2 / s1 if s1 != 0 else 999
                if ratio > 1.8:    phase = '🚀 加速'
                elif ratio < 0.4:  phase = '⚠️ 滞涨'
                else:              phase = '↑ 上行'
            else:
                phase = ''
        elif structure == '📉 下降趋势':
            if s1 < 0 and s2 < 0:
                ratio = s2 / s1 if s1 != 0 else 0
                if ratio > 1.8:    phase = '📉 加速跌'
                else:              phase = '↓ 下行'
            else:
                phase = ''
        else:  # 区间震荡 — 支撑/压力位置
            bk_pts = sorted([kp for kp in kps if kp['label'] == '突' and kp['y'] < cur],
                            key=lambda x: x['y'], reverse=True)
            hi_15 = max(h60[-15:])
            lo = bk_pts[0]['y'] if bk_pts else min(l60[-15:])
            hi = hi_15 if hi_15 else max(h60[-15:])
            if hi and lo and hi != lo:
                pct = (cur - lo) / (hi - lo) * 100
                if pct < 30:   phase = '区间底部'
                elif pct > 70: phase = '区间顶部'
                else:          phase = '区间中段'
            else:
                phase = ''
        
        return {
            'name': name, 'chg': chg_today,
            'chg20d': chg20d,
            'structure': structure, 'phase': phase,
        }
    
    # === 计算TOP15所有结果（用于今日涨幅/结构/阶段） ===
    all_results = [_compute_one(name, today_chg_map.get(name, 0)) for name in top15_names]
    
    # === 20日涨幅：全量板块参与排序 ===
    # 所有在s60d中有数据的板块（含TOP15已计算的 + 其他有缓存的）
    all_with_20d = []
    seen_in_results = {r['name'] for r in all_results if r.get('chg20d') is not None}
    # TOP15的结果
    for r in all_results:
        if r.get('chg20d') is not None:
            all_with_20d.append(r)
    # 其他有缓存的板块（用缓存数据计算完整结构/阶段）
    for name in all_sector_names:
        if name in seen_in_results:
            continue
        kd = s60d.get(name)
        if not kd or 'closes' not in kd or len(kd['closes']) < 21:
            continue
        # 用缓存数据计算完整结构/阶段
        all_with_20d.append(_compute_one(name, today_chg_map.get(name, 0)))
    
    # 今日涨幅TOP10
    today_top10 = sorted(all_results, key=lambda x: x['chg'], reverse=True)[:10]
    
    # 20日涨幅TOP10（从全量有数据的板块中排）
    chg20d_top10 = sorted(all_with_20d, key=lambda x: x['chg20d'], reverse=True)[:10]
    
    # 昨日涨幅TOP10
    yesterday_top10 = sorted(all_results, key=lambda x: x.get('yesterday_chg', 0), reverse=True)[:10]
    
    return {
        'today_top5': today_top10,
        'chg20d_top10': chg20d_top10,
        'yesterday_top5': yesterday_top10,
    }

# ========== 市场龙头动态扫描 ==========

LEADERS_FILE = INDUSTRY_LEADERS_PATH
DAILY_KLINE_CACHE = os.path.join(CACHE_DIR, 'market_leaders_daily')

def _ensure_cache_dir():
    os.makedirs(DAILY_KLINE_CACHE, exist_ok=True)

def _batch_tencent_quotes(codes_list):
    """
    批量获取腾讯实时行情
    每批次最多100个代码，返回 {code: quote_dict} 字典
    code使用带前缀的格式（sh600008）作为key
    """
    results = {}
    batch_size = 100
    for i in range(0, len(codes_list), batch_size):
        batch = codes_list[i:i+batch_size]
        q_str = ','.join(batch)
        try:
            r = requests.get(f'https://qt.gtimg.cn/q={q_str}',
                            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                            timeout=10)
            lines = r.text.strip().split('\n')
            for line in lines:
                try:
                    fields = line.split('"')[1].split('~') if '"' in line else []
                    if len(fields) < 40:
                        continue
                    bare_code = fields[2]  # 裸代码 600519
                    # 找出这个代码对应的原始查询code（带前缀）
                    matched = None
                    for qc in batch:
                        if qc.endswith(bare_code):
                            matched = qc
                            break
                    if not matched:
                        continue
                    results[matched] = {
                        'code': matched,
                        'bare_code': bare_code,
                        'name': fields[1],
                        'price': float(fields[3]) if fields[3] else 0,
                        'close': float(fields[4]) if fields[4] else 0,
                        'open': float(fields[5]) if fields[5] else 0,
                        'volume': int(fields[6]) if fields[6].isdigit() else 0,
                        'high': float(fields[33]) if fields[33] else 0,
                        'low': float(fields[34]) if fields[34] else 0,
                        'change_pct': float(fields[32]) if fields[32] else 0,
                        'turnover_rate': float(fields[38]) if len(fields) > 38 and fields[38] else 0,
                        'turnover_amount': float(fields[37]) if len(fields) > 37 and fields[37] else 0,
                    }
                except:
                    continue
        except:
            continue
    return results

def _get_cached_daily_klines(code):
    """
    获取个股日K线（10日），缓存按天过期
    返回 [{date, close, volume, high, low}, ...]
    """
    _ensure_cache_dir()
    today = datetime.now().strftime('%Y%m%d')
    cache_file = os.path.join(DAILY_KLINE_CACHE, f'{code}_{today}.json')
    
    # 检查当日缓存
    if os.path.isfile(cache_file):
        try:
            with open(cache_file) as f:
                return json.load(f)
        except:
            pass
    
    # 没有缓存或已损坏，重新获取
    qcode = code
    if not code.startswith(('sh', 'sz', 'SH', 'SZ')):
        qcode = ('sh' if code.startswith(('6', '9')) else 'sz') + code
    
    try:
        r = requests.get(f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={qcode},day,,,10,qfq',
                        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                        timeout=10)
        data = r.json()
        klines = data.get('data', {}).get(qcode, {})
        day_data = klines.get('qfqday', klines.get('day', []))
        result = []
        for k in day_data:
            if len(k) >= 6:
                result.append({
                    'date': k[0],
                    'close': float(k[2]),
                    'volume': float(k[5]),
                    'high': float(k[3]),
                    'low': float(k[4]),
                })
        if result:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False)
        return result
    except:
        return []

def _norm_code(code):
    """统一转成腾讯格式（sh/sz前缀）"""
    code = code.strip()
    if code.startswith(('sh', 'sz', 'SH', 'SZ')):
        return code.lower()
    return ('sh' if code.startswith(('6', '9')) else 'sz') + code

def _calc_ma10_slope(klines):
    """判断MA10方向：用最近3天的MA10线性回归斜率"""
    if not klines or len(klines) < 10:
        return 0
    closes = [k['close'] for k in klines]
    # 计算MA10值列表
    ma10_list = []
    for i in range(len(closes)):
        start = max(0, i - 9)
        ma10_list.append(sum(closes[start:i+1]) / (i - start + 1))
    if len(ma10_list) < 11:
        # 数据不够10个MA值
        return 0
    # 取最近3天的MA10做线性回归
    recent = ma10_list[-3:] if len(ma10_list) >= 3 else ma10_list
    n = len(recent)
    xs = list(range(n))
    mx = sum(xs) / n
    my = sum(recent) / n
    num = sum((xs[i] - mx) * (recent[i] - my) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n))
    return num / den if den else 0

def _calc_5d_gain(klines, today_price):
    """
    计算近5日涨幅
    用日K线最近4个收盘价 + 今日实时价格
    返回 (gain_pct, total_turnover)
    """
    if not klines or len(klines) < 5:
        return 0, 0
    # 取日K线最近5个收盘价
    recent_closes = [k['close'] for k in klines[-5:]]
    # 今日涨跌幅 = (today_price / 昨收 - 1) * 100
    yesterday_close = recent_closes[-1]  # 最近一根日K线的收盘=昨收
    today_chg = (today_price / yesterday_close - 1) * 100 if yesterday_close > 0 else 0
    
    # 5日涨幅 = 从5天前的收盘到今天
    close_5d_ago = recent_closes[0]
    if close_5d_ago <= 0:
        return 0, 0
    # 这里其实需要往前数5个交易日
    # 但日K线是按交易日给的，所以倒数第5个就是5天前的收盘
    if len(klines) >= 6:
        price_5d_ago = klines[-6]['close']
        gain = (today_price / price_5d_ago - 1) * 100
    else:
        gain = today_chg
    
    # 5日成交额 = 前4天日成交额 + 今日成交额
    prev_turnover = sum(k['volume'] * (k['high'] + k['low']) / 2 for k in klines[-4:]) if len(klines) >= 4 else 0
    # 今日成交额从实时数据获取（已传参）
    
    return round(gain, 2), 0  # turnover从实时数据算

def get_market_leaders():
    """
    市场龙头动态扫描
    条件：近5日行业涨幅第一 + 近5日成交额行业第一 + MA10向上 + 换手率>3%
    缓存策略：交易日10分钟刷新，非交易日直接返回缓存
    """
    _ensure_cache_dir()
    cache_dir = DAILY_KLINE_CACHE
    
    # 检查主缓存
    today_str_date = datetime.now().strftime('%Y%m%d')
    main_cache = os.path.join(CACHE_DIR, f'market_leaders_{today_str_date}.json')
    
    # 非交易时间直接返回缓存
    if not _is_trading_time():
        if os.path.isfile(main_cache):
            with open(main_cache) as f:
                cached = json.load(f)
                if cached.get('leaders') or cached.get('scanned', []):
                    return cached
    else:
        # 交易时间：10分钟TTL
        if os.path.isfile(main_cache):
            cache_age = time.time() - os.path.getmtime(main_cache)
            if cache_age < 600:
                with open(main_cache) as f:
                    return json.load(f)
    
    # 加载行业龙头数据
    if not os.path.isfile(LEADERS_FILE):
        return {'leaders': [], 'count': 0, 'error': '行业龙头数据文件未找到'}
    
    with open(LEADERS_FILE) as f:
        ld = json.load(f)
    
    by_industry = ld.get('by_industry', {})
    all_stocks = ld.get('all_stocks', [])
    
    if not by_industry:
        return {'leaders': [], 'count': 0, 'error': '行业分类数据为空'}
    
    # 收集所有股票代码（去重）
    code_set = set()
    code_to_orig = {}
    for s in all_stocks:
        qcode = _norm_code(s['code'])
        code_set.add(qcode)
        code_to_orig[qcode] = s
    
    codes_list = sorted(code_set)
    
    # 批量获取实时行情
    quotes = _batch_tencent_quotes(codes_list)
    
    # 获取日K线（并行方式：逐个获取，缓存命中则跳过）
    daily_klines = {}
    for qcode in codes_list:
        if qcode in quotes and quotes[qcode]['price'] > 0:
            daily_klines[qcode] = _get_cached_daily_klines(qcode)
    
    # --- 逐行业计算排名 ---
    industry_results = {}
    for ind, stocks in by_industry.items():
        stock_metrics = []
        for s in stocks:
            qcode = _norm_code(s['code'])
            quote = quotes.get(qcode)
            klines = daily_klines.get(qcode, [])
            
            if not quote or quote['price'] <= 0:
                continue
            
            price = quote['price']
            
            # 换手率
            turnover_rate = quote.get('turnover_rate', 0)
            
            # MA10方向
            ma10_slope = _calc_ma10_slope(klines)
            
            # 5日涨幅
            gain_5d = 0
            if klines and len(klines) >= 6:
                price_5d_ago = klines[-6]['close']
                if price_5d_ago > 0:
                    gain_5d = round((price / price_5d_ago - 1) * 100, 2)
            
            # 5日成交额
            turnover_5d = 0
            if klines and len(klines) >= 5:
                # 前4天成交额（用均价近似）
                for k in klines[-4:]:
                    avg_price = (k['high'] + k['low']) / 2
                    turnover_5d += k['volume'] * avg_price
                # 今日成交额
                turnover_5d += quote.get('turnover_amount', 0)
            
            stock_metrics.append({
                'code': s['code'],
                'qcode': qcode,
                'name': s.get('name', quote.get('name', '')),
                'price': price,
                'change_pct': quote['change_pct'],
                'gain_5d': gain_5d,
                'turnover_5d': turnover_5d,
                'turnover_rate': turnover_rate,
                'ma10_slope': round(ma10_slope, 4),
                'ma10_up': ma10_slope > 0,
                'industry': ind,
            })
        
        if len(stock_metrics) < 1:
            continue
        
        # 按5日涨幅排名
        sorted_by_gain = sorted(stock_metrics, key=lambda x: x['gain_5d'], reverse=True)
        rank_gain_1st = sorted_by_gain[0]['gain_5d'] if sorted_by_gain else 0
        
        # 按5日成交额排名
        sorted_by_turnover = sorted(stock_metrics, key=lambda x: x['turnover_5d'], reverse=True)
        rank_turnover_1st = sorted_by_turnover[0]['turnover_5d'] if sorted_by_turnover else 0

        # 筛选条件：涨幅第一 AND 成交额第一 AND MA10向上 AND 换手率>3%
        for sm in stock_metrics:
            is_gain_1st = sm['gain_5d'] >= rank_gain_1st
            is_turnover_1st = sm['turnover_5d'] >= rank_turnover_1st
            sm['rank_gain'] = 1 if is_gain_1st else 99
            sm['rank_turnover'] = 1 if is_turnover_1st else 99
            if is_gain_1st and is_turnover_1st and sm['ma10_up'] and sm['turnover_rate'] > 3:
                industry_results[ind] = sm
    
    # 如果有行业没有满足全部条件，取涨幅第一的作为参考
    # 但只在返回中标记哪些是真正符合条件的
    
    leaders_list = list(industry_results.values())
    
    # 按5日涨幅降序排列
    leaders_list.sort(key=lambda x: x['gain_5d'], reverse=True)
    
    result = {
        'leaders': leaders_list,
        'count': len(leaders_list),
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'trading_time': _is_trading_time(),
        'total_industries': len(by_industry),
        'scanned_industries': len([v for v in industry_results.values()]),
    }
    
    # 写入缓存（无论是否交易时间，都保存最后一次结果）
    try:
        with open(main_cache, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False)
    except:
        pass
    
    return result


def get_top_concept_sectors_with_5d():
    """
    获取概念板块排行
    - 「今日涨幅TOP10」：今日涨跌幅前10
    - 「20日涨幅TOP10」：近20交易日累计涨幅前10
    数据源：sector_daily.json['concepts']（同花顺概念板块指数）
    与 get_top_sectors_with_5d() 复用同一套结构/阶段计算逻辑
    """
    from backend.core.data_layer import get_sector_daily

    sector_data = get_sector_daily()
    concepts_kline = sector_data.get('concepts', {})

    if not concepts_kline:
        return {'today_top5': [], 'chg20d_top5': []}

    # 工具函数（与 get_top_sectors_with_5d 保持一致）
    def _ema_list(d, p):
        r = [None]*len(d); m = 2/(p+1)
        for i in range(len(d)):
            if i == 0: r[i] = d[i]
            elif r[i-1] is not None: r[i] = (d[i]-r[i-1])*m+r[i-1]
        return r

    def _reg_slope(y_list):
        n = len(y_list); xs = list(range(n))
        mx = sum(xs)/n; my = sum(y_list)/n
        num = sum((xs[i]-mx)*(y_list[i]-my) for i in range(n))
        den = sum((xs[i]-mx)**2 for i in range(n))
        return num/den if den else 0

    def _compute_one(name, klines):
        """计算单个概念板块的结构、阶段、今日涨幅、20日涨幅"""
        closes = [k['close'] for k in klines]
        highs = [k['high'] for k in klines]
        lows = [k['low'] for k in klines]

        # 今日涨幅（最近两日收盘）
        chg_today = 0
        if len(closes) >= 2:
            chg_today = round((closes[-1] / closes[-2] - 1) * 100, 2)

        # 20日涨幅
        chg20d = 0
        if len(closes) >= 21:
            chg20d = round((closes[-1] / closes[-21] - 1) * 100, 2)

        # 结构（EMA10极值位置，同 get_top_sectors_with_5d）
        c15 = closes[-15:] if len(closes) >= 15 else closes
        e10 = _ema_list(c15, 10)
        n = len(e10)
        max_pos = max(range(n), key=lambda i: e10[i])
        min_pos = min(range(n), key=lambda i: e10[i])
        first_q = n // 4
        last_q = n - 1 - n // 4
        if max_pos >= last_q and min_pos <= first_q:
            structure = '📈 上涨趋势'
        elif min_pos >= last_q and max_pos <= first_q:
            structure = '📉 下降趋势'
        else:
            structure = '➡ 区间震荡'

        # 阶段
        half = max(1, len(e10) // 2)
        s1 = _reg_slope(e10[:half])
        s2 = _reg_slope(e10[half:])

        if structure == '📈 上涨趋势':
            if s1 > 0 and s2 > 0:
                ratio = s2 / s1 if s1 != 0 else 999
                if ratio > 1.8:    phase = '🚀 加速'
                elif ratio < 0.4:  phase = '⚠️ 滞涨'
                else:              phase = '↑ 上行'
            else:
                phase = ''
        elif structure == '📉 下降趋势':
            if s1 < 0 and s2 < 0:
                ratio = s2 / s1 if s1 != 0 else 0
                if ratio > 1.8:    phase = '📉 加速跌'
                else:              phase = '↓ 下行'
            else:
                phase = ''
        else:
            phase = ''

        return {
            'name': name,
            'chg': chg_today,
            'chg20d': chg20d,
            'structure': structure,
            'phase': phase,
        }

    # 计算所有概念板块
    all_results = []
    for name, klines in concepts_kline.items():
        if not klines or len(klines) < 5:
            continue
        all_results.append(_compute_one(name, klines))

    if not all_results:
        return {'today_top5': [], 'chg20d_top5': []}

    # 今日涨幅TOP10
    today_top10 = sorted(all_results, key=lambda x: x['chg'], reverse=True)[:10]

    # 20日涨幅TOP10
    chg20d_top10 = sorted(all_results, key=lambda x: x['chg20d'], reverse=True)[:10]

    return {
        'today_top5': today_top10,
        'chg20d_top10': chg20d_top10,
    }


if __name__ == '__main__':
    print("=== 测试数据源 ===\n")
    
    print("[数据源1] mootdx...")
    df, close = _mootdx_quote()
    if close:
        print(f"  ✅ 数据合理 (close={close})")
    else:
        print(f"  ❌ 数据无效或不可用")
    
    print("\n[数据源2] 腾讯财经...")
    try:
        fields = _tencent_quote_raw()
        print(f"  ✅ price={fields[3]}, vol={fields[6]}, amount={fields[35][:30]}")
    except Exception as e:
        print(f"  ❌ {e}")
    
    print("\n=== 成交量对比 ===")
    comp = get_volume_comparison()
    for k in ['today_amount_yuan','yesterday_amount_yuan','yesterday_date','yesterday_is_estimated',
              'amount_ratio','current_price','data_source']:
        v = comp.get(k, '')
        print(f"  {k}: {v}")
    print(f"  今日曲线: {len(comp.get('today_curve',[]))}点")
    print(f"  昨日曲线: {len(comp.get('yesterday_curve',[]))}点")
