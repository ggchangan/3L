#!/usr/bin/env python3
"""
3L 每日复盘数据生成器（完整版）
生成5大项复盘数据：
  ① 大盘周期 — 波峰波谷判定（4维度评分）
  ② 动量主线 — 评分/持续性/轮动
  ③ 最强逻辑 — 个股归主线+板块内排名+选股说明
  ④ 量价择时 — 买点验证/关键点/止损止盈
  ⑤ 每日交易计划 — 基于前4项生成

输出：JSON → /home/ubuntu/www/private/review_archive/{date}.json
"""
import json, os, sys, requests, math
from datetime import datetime, timedelta

# ====== 路径 ======
WWW_DIR = '/home/ubuntu/www'
ARCHIVE_DIR = os.path.join(WWW_DIR, 'private', 'review_archive')
SCRIPTS_DIR = '/home/ubuntu/scripts'
DATA_DIR = '/home/ubuntu/data/3l'

# ====== 辅助函数 ======

def load_cached_data(path):
    """加载缓存JSON"""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def fetch_market_quote():
    """获取中证全指(000985)实时行情"""
    try:
        r = requests.get(
            'https://qt.gtimg.cn/q=sh000985',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
            timeout=10
        )
        txt = r.text
        parts = txt.split('~')
        if len(parts) > 5:
            name = parts[1]
            cur_price = float(parts[3]) if parts[3] else 0
            prev_close = float(parts[4]) if parts[4] else cur_price
            chg_pct = (cur_price - prev_close) / prev_close * 100 if prev_close else 0
            return {
                'price': cur_price,
                'change': round(chg_pct, 2),
                'name': name
            }
    except Exception as e:
        print(f"[WARN] 获取中证全指行情失败: {e}")
    return None

def to_yyyymmdd(d):
    """统一日期格式为 YYYY-MM-DD"""
    if not d:
        return ''
    d = d.strip().replace('/', '-')
    # 已是 YYYY-MM-DD
    if len(d) == 10 and d[4] == '-':
        return d
    return d

def fetch_index_klines(days=60):
    """获取中证全指K线（腾讯财经）"""
    try:
        r = requests.get(
            f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh000985,day,,,{days},qfq',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
            timeout=10
        )
        data = r.json()
        klines = data.get('data', {}).get('sh000985', {}).get('qfqday', []) or \
                 data.get('data', {}).get('sh000985', {}).get('day', []) or []
        return [{'date': k[0], 'open': float(k[1]), 'close': float(k[2]),
                 'high': float(k[3]), 'low': float(k[4]), 'volume': float(k[5])}
                for k in klines if len(k) >= 6]
    except Exception as e:
        print(f"[WARN] 获取K线失败: {e}")
        return []

# ====== ① 大盘周期判定 ======

def judge_market_cycle(klines, quote=None):
    """4维度评分判定大盘波峰/波谷/波中"""
    if len(klines) < 30:
        return {'score': 0, 'position': '数据不足', 'strategy': '正常交易',
                'position_pct': '半仓', 'build_per_stock_pct': 5}

    # 维度1: 均线位置 (40%)
    ma20 = sum(k['close'] for k in klines[-20:]) / 20
    ma60 = sum(k['close'] for k in klines[-60:]) / 60
    cur = klines[-1]['close']
    ma_score = 0
    if cur > ma20 > ma60:
        ma_score = 2  # 多头排列 → 偏波峰
    elif cur > ma20 and ma20 < ma60:
        ma_score = 0  # 短期突破但长期压制 → 波中
    elif cur < ma20 and ma20 > ma60:
        ma_score = -1  # 短期跌破 → 偏波谷
    elif cur < ma20 < ma60:
        ma_score = -2  # 空头排列
    else:
        ma_score = -1

    # 维度2: 成交量 (30%) — 取20日均量对比60日均量
    v20 = sum(k['volume'] for k in klines[-20:]) / 20
    v60 = sum(k['volume'] for k in klines[-60:]) / 60
    vol_ratio = v20 / v60 if v60 > 0 else 1
    if vol_ratio > 1.8:
        vol_score = 2  # 放量高潮
    elif vol_ratio > 1.2:
        vol_score = 1  # 温和放量
    elif vol_ratio > 0.8:
        vol_score = 0  # 正常
    else:
        vol_score = -1  # 缩量低迷

    # 维度3: 近期涨跌幅 (20%)
    if len(klines) >= 10:
        chg_10d = (klines[-1]['close'] - klines[-11]['close']) / klines[-11]['close'] * 100
    else:
        chg_10d = 0
    if chg_10d > 8:
        trend_score = 2
    elif chg_10d > 3:
        trend_score = 1
    elif chg_10d > -3:
        trend_score = 0
    elif chg_10d > -8:
        trend_score = -1
    else:
        trend_score = -2

    # 维度4: 波动率 (10%) — 近期振幅
    if len(klines) >= 10:
        amp = max((k['high'] - k['low']) / k['low'] * 100 for k in klines[-10:])
        if amp > 6:
            amp_score = 1  # 高波动
        elif amp > 3:
            amp_score = 0  # 正常
        else:
            amp_score = -1  # 低波动
    else:
        amp_score = 0

    score = ma_score * 0.4 + vol_score * 0.3 + trend_score * 0.2 + amp_score * 0.1

    # 判定位置
    if score >= 1:
        position = '偏波峰'
        pct = '五成'
        strategy = '控制仓位，收紧止盈'
        bps = 5
    elif score >= 0.3:
        position = '波中偏上'
        pct = '六至七成'
        strategy = '正常交易，注意减仓信号'
        bps = 5
    elif score >= -0.3:
        position = '波中'
        pct = '七至八成'
        strategy = '正常交易，积极选股'
        bps = 5
    elif score >= -1:
        position = '波中偏下'
        pct = '五至七成'
        strategy = '谨慎选股，收紧止损'
        bps = 5
    else:
        position = '偏波谷'
        pct = '五至八成'
        strategy = '积极寻找买点，止损换股补回'
        bps = 10

    return {
        'score': round(score, 2),
        'position': position,
        'ma_score': ma_score,
        'vol_score': vol_score,
        'trend_score': trend_score,
        'amp_score': amp_score,
        'ma20': round(ma20, 2),
        'ma60': round(ma60, 2),
        'vol_ratio': round(vol_ratio, 2),
        'chg_10d': round(chg_10d, 2),
        'strategy': strategy,
        'position_pct': pct,
        'build_per_stock_pct': bps,
        'chg_10d_raw': round(chg_10d, 2),
    }

# ====== ② 动量主线评判 ======

def get_industry_rankings():
    """获取同花顺行业板块排行（当日实时）"""
    import akshare as ak
    try:
        df = ak.stock_board_industry_summary_ths()
        df = df.sort_values('涨跌幅', ascending=False)
        result = []
        for _, row in df.head(15).iterrows():
            result.append({
                'name': row['板块'],
                'change': row['涨跌幅'],
                'net_inflow': row['净流入'],
                'up_count': row['上涨家数'],
                'down_count': row['下跌家数'],
                'leader': row['领涨股'],
                'leader_change': row['领涨股-涨跌幅'],
            })
        return result
    except Exception as e:
        print(f"[WARN] 获取行业排行失败: {e}")
        return []

def get_mainline_data(date_str):
    """获取主线板块数据（从行业排行中提取前N名）"""
    industries = get_industry_rankings()
    lines = []
    for ind in industries[:10]:
        score = round(ind['change'] * 10, 1)
        if score >= 15:
            lines.append({
                'name': ind['name'],
                'score': score,
                'change': ind['change'],
                'leader': ind['leader'],
            })
    return {'lines': lines[:5], 'industries': industries}

def track_mainline_persistence(date_str, current_lines):
    """主线持续性跟踪（占位）"""
    return [{'name': l['name'], 'days': 1, 'status': '持续'} for l in current_lines]

# ====== ③ 最强逻辑归类 ======

def classify_stocks_by_mainline(mainline_data, holdings, buy_signals):
    """将持仓/候选归入主线/非主线"""
    lines = [l['name'] for l in mainline_data.get('lines', [])]
    result = {'mainline': [], 'non_mainline': []}

    def find_sector(stock):
        sec = stock.get('sector', '')
        for line in lines:
            if line in sec or sec in line:
                return line
        return sec

    for h in holdings:
        line = find_sector(h)
        entry = {'name': h.get('name', '?'), 'code': h.get('code', ''), 'sector': line}
        if line in lines:
            result['mainline'].append(entry)
        else:
            result['non_mainline'].append(entry)

    for s in buy_signals:
        line = find_sector(s)
        entry = {'name': s.get('name', '?'), 'code': s.get('code', ''), 'sector': line}
        if line in lines:
            result['mainline'].append(entry)

    return result

# ====== ④ 量价择时（全量扫描） ======

def get_buy_sell_signals(holdings, buy_signals):
    """量价择时分析 — 从全量扫描结果中提取持仓股买点"""
    signals = {'holdings': [], 'signals': buy_signals}
    bs_by_code = {s.get('code', ''): s for s in buy_signals}
    
    # 从缓存读取持仓股数据
    cache = {}
    try:
        sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/trading/ema10-trend-judgment/scripts')
        from ema_utils import get_ema_arrangement, get_structure, get_stage
        import json as _json
        with open('/home/ubuntu/data/3l/all_stocks_60d.json') as f:
            _data = _json.load(f)
        _stocks = _data.get('stocks', {})
        for _sec, _ss in _stocks.items():
            for _code, _kls in _ss.items():
                if _kls and len(_kls) >= 2:
                    last = _kls[-1]
                    prev = _kls[-2]
                    chg = round((last['close'] - prev['close']) / prev['close'] * 100, 2) if prev['close'] else 0
                    closes_60 = [k['close'] for k in _kls]
                    highs_60 = [k['high'] for k in _kls]
                    lows_60 = [k['low'] for k in _kls]
                    vols_60 = [k.get('volume', k.get('vol', 0)) for k in _kls]
                    _structure = get_structure(closes_60)
                    _stage = get_stage(closes_60, _structure, highs_60, lows_60, volumes=vols_60)
                    _vol_analysis = '--'
                    if len(vols_60) >= 13 and all(v > 0 for v in vols_60[-13:]):
                        _vl3 = sum(vols_60[-3:]) / 3
                        _vp10 = sum(vols_60[-13:-3]) / 10
                        _vr = _vl3 / _vp10 if _vp10 > 0 else 1
                        if _vr < 0.8:
                            _vol_analysis = f'缩量{_vr:.0%}'
                        elif _vr > 1.5:
                            _vol_analysis = f'放量{_vr:.0%}'
                        else:
                            _vol_analysis = f'量能正常{_vr:.0%}'
                    cache[_code] = {
                        'close': last['close'], 'change': chg, 'date': last['date'],
                        'ema': get_ema_arrangement(closes_60),
                        'structure': _structure,
                        'stage': _stage,
                        'vol_analysis': _vol_analysis,
                    }
    except Exception:
        pass
    
    for h in holdings:
        code = h.get('code', '')
        name = h.get('name', '?')
        bs = bs_by_code.get(code)
        close_price = bs.get('price', 0) if bs else 0
        if not bs or close_price == 0:
            close_price = cache.get(code, {}).get('close', 0)
        chg_val = bs.get('change', 0) if bs else 0
        if not bs:
            chg_val = cache.get(code, {}).get('change', 0)
        action = f"{bs.get('buy_point', '')} {bs.get('flags', '')}" if bs else '持有观察'
        signals['holdings'].append({
            'name': name, 'code': code,
            'action': action.strip(),
            'close': close_price,
            'zhongji': bs.get('flags', '') if bs else '',
            'tupo': '',
            'change': chg_val,
            'structure': cache.get(code, {}).get('structure', '--'),
            'stage': cache.get(code, {}).get('stage', '--'),
            'ema': cache.get(code, {}).get('ema', '--'),
            'vol_analysis': cache.get(code, {}).get('vol_analysis', '--'),
        })
    return signals, cache, bs_by_code

# ====== ⑤ 每日交易计划 ======

def generate_trading_plan(market_cycle, mainline_data, logic_classify, signals_data, existing_holdings):
    """综合前4项生成次日交易计划"""
    plan = {
        'overall_strategy': market_cycle.get('strategy', '正常交易'),
        'position_level': market_cycle.get('position_pct', '半仓'),
        'build_per_stock_pct': f"{market_cycle.get('build_per_stock_pct', 5)}%/只",
        'main_lines': [],
        'action_items': [],
        'watch_items': [],
        'risk_reminder': ''
    }

    for line in (mainline_data.get('lines', [])[:3]):
        plan['main_lines'].append(f"{line['name']}(评分{line['score']})")

    for h in (signals_data.get('holdings', []) or []):
        if h.get('has_stop_loss') and h.get('stop_loss'):
            plan['action_items'].append(f"🔴 {h['name']} 止损{h['stop_loss']} — 严格按止损执行")
        elif not h.get('ema_status') or '多头' not in h.get('ema_status', ''):
            plan['watch_items'].append(f"⚠️ {h['name']} EMA{h.get('ema_status','?')} — 关注趋势是否走坏")

    signals = signals_data.get('signals', [])
    if signals:
        plan['action_items'].append(f"📌 发现{len(signals)}个买点信号，关注调整后入场机会")

    if market_cycle.get('score', 0) >= 1:
        plan['risk_reminder'] = '大盘偏波峰，控制仓位，收紧止盈'
    elif market_cycle.get('score', 0) < 0:
        plan['risk_reminder'] = '大盘偏波谷，积极寻找买点，止损后换股补回'
    else:
        plan['risk_reminder'] = '大盘波中，按正常节奏交易，不主跌维持重仓'

    return plan

# ====== 盈利模式检查 ======

def load_market_data_for_profit_check():
    """加载market_data.json并转换为buy_point_detection所需格式"""
    mdata_path = '/home/ubuntu/.hermes/profiles/3l/data/market_data.json'
    if not os.path.exists(mdata_path):
        print("[WARN] market_data.json 不存在，跳过盈利模式检查")
        return None
    
    with open(mdata_path) as f:
        raw = json.load(f)
    
    sectors = raw.get('sectors', {})
    all_stocks = {}
    for sec_name, stocks in sectors.items():
        all_stocks[sec_name] = {}
        for code, stock in stocks.items():
            kls = stock.get('klines', [])
            # 反转：market_data按最新到最旧，buy_point_detection需要最旧到最新
            kls_reversed = list(reversed(kls))
            converted = []
            for k in kls_reversed:
                converted.append({
                    'date': k.get('d', ''),
                    'open': k.get('o', 0),
                    'close': k.get('c', 0),
                    'high': k.get('h', 0),
                    'low': k.get('l', 0),
                    'volume': k.get('v', 0),
                    'name': stock.get('name', code),
                })
            if converted:
                all_stocks[sec_name][code] = converted
    return all_stocks


def find_latest_date_in_data(all_stocks, default_date):
    """找到all_stocks中所有K线的最大日期"""
    latest = ''
    for sec_name, stocks in all_stocks.items():
        for code, kls in stocks.items():
            if kls:
                d = kls[-1].get('date', '')
                if d > latest:
                    latest = d
    return latest if latest else default_date


def check_profit_model1_on_signals(buy_signals, all_stocks, check_date):
    """对每个买点信号检查是否符合盈利模式1，添加标记"""
    if not all_stocks:
        return buy_signals
    
    # 找到数据中实际最新的日期
    actual_date = find_latest_date_in_data(all_stocks, check_date)
    if actual_date != check_date:
        print(f"[盈利模式1] 使用数据中最新日期: {actual_date} (原请求: {check_date})")
    
    sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts')
    try:
        from buy_point_detection import check_profit_model1
    except ImportError:
        print("[WARN] 无法导入 buy_point_detection.check_profit_model1")
        return buy_signals
    
    updated = []
    for sig in buy_signals:
        code = sig.get('code', '')
        if not code:
            updated.append(sig)
            continue
        full_code = code
        if not any(code.startswith(p) for p in ['SH', 'SZ', 'sh', 'sz']):
            if code.startswith('6') or code.startswith('9'):
                full_code = 'SH' + code
            else:
                full_code = 'SZ' + code
        
        res = check_profit_model1(full_code, actual_date, all_stocks)
        sig['profit_model1'] = bool(res and res['match'])
        updated.append(sig)
    
    return updated


# ====== 主流程 ======

def generate_daily_review(date_str=None):
    """生成完整每日复盘数据"""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    print(f"[3L复盘] 生成 {date_str} 复盘数据...")

    # 已有存档
    existing = load_cached_data(os.path.join(ARCHIVE_DIR, f'{date_str}.json'))
    if not existing:
        existing = {
            'date': date_str,
            'holdings': [],
            'buy_signals': [],
            'stocks': {'stocks': []}
        }
        print(f"[3L复盘] 新建存档")
    else:
        print(f"[3L复盘] 载入已有存档")

    # 获取大盘K线数据并过滤到指定日期
    index_klines = fetch_index_klines(60)
    index_klines = [k for k in index_klines if k['date'] <= date_str]
    today_quote = fetch_market_quote()

    print(f"[3L复盘] K线数据: 共{len(index_klines)}天, 最新={index_klines[-1]['date'] if index_klines else '无'}")
    
    # 如果过滤后无数据，按指定日期向前取
    if not index_klines:
        index_klines = fetch_index_klines(60)
        index_klines = [k for k in index_klines if k['date'] <= date_str]
    
    # ① 大盘周期判定
    print("[3L复盘] ① 判定大盘周期...")
    market_cycle = judge_market_cycle(index_klines, today_quote)
    # 使用K线收盘价（按指定日期）
    if index_klines:
        last = index_klines[-1]
        prev = index_klines[-2] if len(index_klines) >= 2 else None
        market_cycle['price'] = f"{last['close']:.2f}"
        if prev:
            chg_pct = (last['close'] - prev['close']) / prev['close'] * 100
            market_cycle['change'] = round(chg_pct, 2)
        else:
            market_cycle['change'] = 0
        market_cycle['data_date'] = last.get('date', date_str)

    # ② 动量主线评判
    print("[3L复盘] ② 计算动量主线...")
    mainline_data = get_mainline_data(date_str)
    if mainline_data['lines']:
        persistence = track_mainline_persistence(date_str, mainline_data['lines'])
        mainline_data['persistence'] = persistence

    # ③ 最强逻辑归类
    print("[3L复盘] ③ 归类最强逻辑...")
    # 从 holdings.json 读取最新持仓数据（来源：持仓管理页面）
    holdings_file = os.path.join(WWW_DIR, 'private', 'holdings.json')
    live_holdings = []
    if os.path.isfile(holdings_file):
        try:
            with open(holdings_file) as f:
                hdata = json.load(f)
            live_holdings = hdata.get('holdings', [])
        except:
            pass
    holdings = live_holdings or existing.get('holdings', []) or existing.get('stocks', {}).get('stocks', [])
    buy_signals = existing.get('buy_signals', [])

    # 盈利模式1检查：在归类前给买点信号打上标记
    print("[3L复盘] 🔍 检查盈利模式1...")
    all_stocks = load_market_data_for_profit_check()
    buy_signals = check_profit_model1_on_signals(buy_signals, all_stocks, date_str)

    logic_classify = classify_stocks_by_mainline(mainline_data, holdings, buy_signals)

    # ④ 量价择时
    print("[3L复盘] ④ 量价择时分析...")

    # 如果 buy_signals 为空，从全量自选股扫描买点信号
    if not buy_signals:
        try:
            sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/research/main-line-judgment/scripts')
            from buy_point_detection import format_buy_signals
            # 加载 all_stocks_60d.json（buy_point_detection需要这个格式）
            as60_path = '/home/ubuntu/data/3l/all_stocks_60d.json'
            if os.path.isfile(as60_path):
                with open(as60_path) as f:
                    as60_data = json.load(f)
                all_stocks_60d = as60_data.get('stocks', {})
                # 找数据中最新可用日期
                latest_date = ''
                for sec, stocks in all_stocks_60d.items():
                    for code, kls in stocks.items():
                        if kls and kls[-1]['date'] > latest_date:
                            latest_date = kls[-1]['date']
                
                # 如果最新日期 < 今天，拉持仓股的最新K线（补全到最新交易日）
                today_yyyymmdd = date_str.replace('-', '')
                if latest_date and latest_date < today_yyyymmdd:
                    try:
                        import requests as req
                        hdrs = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'}
                        # 只补拉持仓股的：从holdings.json读代码
                        hf = os.path.join(WWW_DIR, 'private', 'holdings.json')
                        if os.path.isfile(hf):
                            with open(hf) as f:
                                hdata = json.load(f)
                            for h in hdata.get('holdings', []):
                                code = h.get('code', '')
                                if not code:
                                    continue
                                mkt = 'sz' if code.startswith(('0', '3')) else 'sh'
                                url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={mkt}{code},day,,,5,qfq'
                                r = req.get(url, headers=hdrs, timeout=5)
                                d = r.json()
                                day_data = d.get('data', {}).get(f'{mkt}{code}', {}).get('day', [])
                                if not day_data:
                                    day_data = d.get('data', {}).get(f'{mkt}{code}', {}).get('qfqday', [])
                                if day_data:
                                    latest_k = day_data[-1]
                                    if len(latest_k) >= 6:
                                        new_rec = {
                                            'date': latest_k[0].replace('-', ''),
                                            'open': float(latest_k[1]),
                                            'close': float(latest_k[2]),
                                            'high': float(latest_k[3]),
                                            'low': float(latest_k[4]),
                                            'volume': int(float(latest_k[5]) * 100),  # 腾讯财经单位是手→股
                                        }
                                        # 追加到对应方向下该股票的缓存
                                        for sec_name2, stocks2 in all_stocks_60d.items():
                                            if code in stocks2:
                                                # 去重：如果最新日期已存在就不加
                                                existing_dates = {k['date'] for k in stocks2[code]}
                                                if new_rec['date'] not in existing_dates:
                                                    stocks2[code].append(new_rec)
                    except Exception as e:
                        print(f"[3L复盘] 补拉持仓数据失败: {e}")
                    # 重新找最新日期
                    latest_date = ''
                    for sec, stocks in all_stocks_60d.items():
                        for code, kls in stocks.items():
                            if kls and kls[-1]['date'] > latest_date:
                                latest_date = kls[-1]['date']
                
                scan_date = latest_date if latest_date else today_yyyymmdd
                ml_names = [l['name'] for l in mainline_data.get('lines', [])]
                scan_result = format_buy_signals(scan_date, all_stocks_60d, ml_names, top_n=20)
            # 合并主线/非主线候选
            seen = set()
            for key in ['zhongji_main', 'zhongji_nonmain', 'tupo_main', 'tupo_nonmain']:
                for s in scan_result.get(key, []):
                    if s['code'] not in seen:
                        seen.add(s['code'])
                        buy_signals.append({
                            'name': s.get('name', s['code']),
                            'code': s['code'],
                            'sector': s['sector'],
                            'buy_point': '中继买点' if key.startswith('zhongji') else '突破买点',
                            'price': s.get('close', 0), 'change': s['gain'],
                            'score': s['score'],
                            'flags': s['flags'],
                            'profit_model1': False,
                        })
            print(f"[3L复盘] 全量扫描: {len(buy_signals)} 个买点信号")
        except Exception as e:
            print(f"[3L复盘] 全量扫描跳过: {e}")

    # 从最新 buy_signals 生成持仓信号（必须在扫描之后）
    timing_signals, stock_cache, bs_by_code = get_buy_sell_signals(holdings, buy_signals)

    # 构建 holdings_data 字典便于查询
    holdings_data = {h.get('code', ''): h for h in holdings}

    # 生成持仓个股复盘（从实时买点检测结果）
    holdings_review = []
    # 引入统一信号判断
    import sys as _sys
    _sys.path.insert(0, '/home/ubuntu/.hermes/profiles/3l/skills/trading/stock-action-judgment/scripts')
    from judge_signal import judge_signal
    for h in timing_signals.get('holdings', []):
        d = holdings_data.get(h.get('code', ''), {})
        structure = h.get('structure', '')
        stage = h.get('stage', '--')
        # 区间震荡：用关键点支撑位重算stage
        if structure == '区间震荡':
            try:
                with open('/home/ubuntu/data/3l/all_stocks_60d.json') as _f:
                    _all = json.load(_f)
                code = h.get('code', '')
                for _sec, _ss in _all.get('stocks', {}).items():
                    if code in _ss and _ss[code] and len(_ss[code]) >= 15:
                        _kls = _ss[code]
                        _highs = [k['high'] for k in _kls]
                        _lows = [k['low'] for k in _kls]
                        _closes = [k['close'] for k in _kls]
                        _opens = [k['open'] for k in _kls]
                        _all_supports = sorted([
                            max(_highs[i-10:i])
                            for i in range(10, len(_kls))
                            if _closes[i] > max(_highs[i-10:i]) and _closes[i] > _opens[i]
                            and max(_highs[i-10:i]) < _closes[-1]
                        ], reverse=True)
                        _resistance = max(_highs[-15:])
                        _support = None
                        for _s in _all_supports:
                            if (_closes[-1] - _s) / _closes[-1] >= 0.015:
                                _support = _s
                                break
                        _support = _support or min(_lows[-20:])
                        if _resistance > _support:
                            _pct = (_closes[-1] - _support) / (_resistance - _support) * 100
                            if _pct < 30: stage = '区间底部'
                            elif _pct > 70: stage = '区间顶部'
                            else: stage = '区间中段'
                        break
            except Exception:
                pass
        code_sig, signal_text, _ = judge_signal(
            structure=structure, stage=stage, buy_point=h['action'],
        )
        # 买点仅在信号为buy时保留，只显示类型名不显示flags
        buy_point = h['action'].split()[0] if code_sig == 'buy' and h['action'] else ''
        # 查找盈利模式1标记
        bs_lookup = bs_by_code.get(h.get('code', ''), {})
        pm1 = bs_lookup.get('profit_model1', False)
        holdings_review.append({
            'name': h['name'], 'code': h['code'],
            'sector': d.get('direction', ''),
            'price': h.get('close', 0),
            'change': h.get('change', 0),
            'buy_point': buy_point,
            'structure': structure,
            'stage': stage,
            'key_level': '--',
            'stop_loss': '',
            'signal': code_sig,
            'ema': h.get('ema', '--'),
            'vol_analysis': h.get('vol_analysis', '--'),
            'profit_model1': pm1,
        })
    # 按结构优先排序：上涨趋势 > 区间震荡 > 下降趋势
    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}
    holdings_review.sort(key=lambda x: struct_priority.get(x['structure'], 3))
    
    # 生成候选买点信号review（与第④部分相同判定逻辑）
    buy_signals_review = []
    for s in buy_signals:
        code = s.get('code', '')
        sc = stock_cache.get(code, {})
        structure = sc.get('structure', '上涨趋势')
        stage = sc.get('stage', '--')
        # 区间震荡：用关键点支撑位重算stage（同holdings逻辑）
        if structure == '区间震荡':
            try:
                with open('/home/ubuntu/data/3l/all_stocks_60d.json') as _f:
                    _all = json.load(_f)
                for _sec, _ss in _all.get('stocks', {}).items():
                    if code in _ss and _ss[code] and len(_ss[code]) >= 15:
                        _kls = _ss[code]
                        _highs = [k['high'] for k in _kls]
                        _lows = [k['low'] for k in _kls]
                        _closes = [k['close'] for k in _kls]
                        _opens = [k['open'] for k in _kls]
                        _all_supports = sorted([
                            max(_highs[i-10:i])
                            for i in range(10, len(_kls))
                            if _closes[i] > max(_highs[i-10:i]) and _closes[i] > _opens[i]
                            and max(_highs[i-10:i]) < _closes[-1]
                        ], reverse=True)
                        _resistance = max(_highs[-15:])
                        _support = None
                        for _s in _all_supports:
                            if (_closes[-1] - _s) / _closes[-1] >= 0.015:
                                _support = _s
                                break
                        _support = _support or min(_lows[-20:])
                        if _resistance > _support:
                            _pct = (_closes[-1] - _support) / (_resistance - _support) * 100
                            if _pct < 30: stage = '区间底部'
                            elif _pct > 70: stage = '区间顶部'
                            else: stage = '区间中段'
                        break
            except Exception:
                pass
        code_sig, _, _ = judge_signal(
            structure=structure, stage=stage,
            buy_point=s.get('buy_point', ''),
        )
        # 第⑤部分只展示买入信号
        if code_sig != 'buy':
            continue
        buy_point_display = s.get('buy_point', '')
        ema = sc.get('ema', '--')
        vol_analysis = sc.get('vol_analysis', '--')
        buy_signals_review.append({
            'name': s.get('name', '?'), 'code': code,
            'sector': s.get('sector', s.get('direction', '')),
            'buy_point': buy_point_display,
            'price': s.get('price', 0), 'change': s.get('change', 0),
            'profit_model1': s.get('profit_model1', False),
            'structure': structure,
            'stage': stage,
            'signal': code_sig,
            'ema': ema,
            'vol_analysis': vol_analysis,
        })
    # 按结构优先排序
    buy_signals_review.sort(key=lambda x: struct_priority.get(x['structure'], 3))

    # ⑤ 每日交易计划
    print("[3L复盘] ⑤ 生成交易计划...")
    trading_plan = generate_trading_plan(market_cycle, mainline_data, logic_classify, timing_signals, holdings)

    # 组装
    review = {
        'date': date_str,
        'market': {
            **market_cycle,
            'date': date_str,
        },
        'mainline': mainline_data,
        'logic_classify': logic_classify,
        'timing_signals': timing_signals,
        'trading_plan': trading_plan,
        'holdings': holdings,
        'buy_signals': buy_signals,
        'holdings_review': holdings_review,
        'buy_signals_review': buy_signals_review,
    }

    # 保存
    save_json(os.path.join(ARCHIVE_DIR, f'{date_str}.json'), review)
    # 同步到 review_data.json（server读取源）
    save_json(os.path.join(WWW_DIR, 'private', 'review_data.json'), review)
    print(f"[3L复盘] ✅ 已保存 {date_str} 复盘数据")
    return review

def update_historical_archives():
    """为所有历史存档补充新字段"""
    if not os.path.isdir(ARCHIVE_DIR):
        return
    for fname in sorted(os.listdir(ARCHIVE_DIR)):
        if not fname.endswith('.json'):
            continue
        date_str = fname[:-5]
        fp = os.path.join(ARCHIVE_DIR, fname)
        try:
            with open(fp) as f:
                data = json.load(f)
            changed = False
            if 'market_cycle' not in data:
                if 'market' in data and isinstance(data['market'], dict):
                    data['market_cycle'] = data['market']
                    changed = True
            if changed:
                save_json(fp, data)
                print(f"[3L复盘] 更新历史存档: {date_str}")
        except:
            continue

if __name__ == '__main__':
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    update_historical_archives()
    generate_daily_review(date_arg)
