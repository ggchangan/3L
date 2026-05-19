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
            'https://qt.gtimg.cn/q=sz000985',
            headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
            timeout=10
        )
        txt = r.text
        # 解析: v_sz000985="1~中证全指~18.91~-0.37~..."
        parts = txt.split('~')
        if len(parts) > 3:
            name = parts[1]
            price = parts[3]
            chg_pct = parts[4] if parts[4] else parts[32]
            return {
                'price': price,
                'change': float(chg_pct) if chg_pct else 0,
                'name': name
            }
    except Exception as e:
        print(f"[WARN] 获取中证全指行情失败: {e}")
    return None

def fetch_index_klines(days=60):
    """获取中证全指日K线用于波峰波谷判断"""
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol='sz000985')
        return df.tail(days).to_dict('records')
    except:
        return []

# ====== ① 大盘周期判定 ======

def judge_market_cycle(klines, today_quote=None):
    """
    综合评分法判断大盘周期（4维度）
    返回: {score, position, detail}
    """
    if not klines or len(klines) < 20:
        return {'score': 0, 'position': 'mid', 'position_cn': '波中',
                'detail': {'trend': 0, 'volume': 0, 'pattern': 0, 'volatility': 0}}

    closes = [k['close'] for k in klines]
    volumes = [k.get('volume', 0) or k.get('vol', 0) for k in klines]
    latest = klines[-1]
    price = latest['close']

    # ① 趋势结构
    ma20 = sum(closes[-20:]) / 20
    ma10 = sum(closes[-10:]) / 10
    ma_rising = ma10 > sum(closes[-20:-10]) / 10

    price_vs_ma20 = (price - ma20) / ma20 * 100
    if price_vs_ma20 > 5 and ma_rising:
        trend_score = 1
    elif price_vs_ma20 < -5 and not ma_rising:
        trend_score = -1
    else:
        trend_score = 0

    # ② 量能位置
    recent_vol = volumes[-1] if volumes else 0
    avg_vol = sum(volumes[-10:-1]) / 9 if len(volumes) >= 10 else sum(volumes) / len(volumes)
    vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1

    if vol_ratio > 3:
        vol_score = 1
    elif vol_ratio < 1.3:
        vol_score = -1
    else:
        vol_score = 0

    # ③ 量价形态（简化版）
    # 检查最近5天是否有连续大阳
    gains_5d = []
    for i in range(max(0, len(closes)-6), len(closes)-1):
        g = (closes[i+1] - closes[i]) / closes[i] * 100
        gains_5d.append(g)
    recent_gains = gains_5d[-5:] if len(gains_5d) >= 5 else gains_5d

    consecutive_big = 0
    for g in reversed(recent_gains):
        if g > 2:
            consecutive_big += 1
        else:
            break

    if consecutive_big >= 3:
        pattern_score = 1  # 加速
    elif consecutive_big == 0 and (min(recent_gains) if recent_gains else 0) < -3:
        pattern_score = -1  # 恐慌
    else:
        pattern_score = 0

    # ④ 波动率
    bodies = []
    for i in range(max(0, len(klines)-10), len(klines)):
        o = klines[i].get('open', 0)
        c = klines[i]['close']
        bodies.append(abs(c - o) / o * 100 if o else 0)
    avg_body = sum(bodies) / len(bodies) if bodies else 0
    baseline_body = sum(bodies[:5]) / 5 if len(bodies) >= 5 else avg_body

    if avg_body > baseline_body * 1.5 and baseline_body > 0:
        vola_score = 1  # 波动放大
    elif avg_body < baseline_body * 0.7 and baseline_body > 0:
        vola_score = -1  # 波动收窄
    else:
        vola_score = 0

    total = trend_score + vol_score + pattern_score + vola_score

    # 波峰波谷映射
    if total >= 3:
        pos = 'peak'
        pos_cn = '波峰区域'
        strategy = '降低仓位·防守为主，卖出可不补'
        pct = '轻仓(20-40%)'
        build_pct = 5
    elif total >= 1:
        pos = 'bias_peak'
        pos_cn = '偏波峰'
        strategy = '控制仓位·逢高减仓，收紧止盈'
        pct = '轻仓(40-60%)'
        build_pct = 5
    elif total == 0:
        pos = 'mid'
        pos_cn = '波中'
        strategy = '中等仓位·精选个股，不主跌也维持重仓'
        pct = '半仓以上(60-80%)'
        build_pct = 5
    elif total >= -2:
        pos = 'bias_trough'
        pos_cn = '偏波谷'
        strategy = '逐步加仓·逢低布局，卖出当日换股补回'
        pct = '重仓(80%)'
        build_pct = 10
    else:
        pos = 'trough'
        pos_cn = '波谷区域'
        strategy = '积极布局·加大仓位，止损后立即补回'
        pct = '重仓(80-100%)'
        build_pct = 10

    return {
        'score': total,
        'position': pos,
        'position_cn': pos_cn,
        'strategy': strategy,
        'position_pct': pct,
        'build_per_stock_pct': build_pct,
        'detail': {
            'trend': {'score': trend_score, 'price_vs_ma20': round(price_vs_ma20, 2), 'ma_rising': ma_rising},
            'volume': {'score': vol_score, 'vol_ratio': round(vol_ratio, 2)},
            'pattern': {'score': pattern_score, 'consecutive_big_candles': consecutive_big},
            'volatility': {'score': vola_score, 'avg_body_pct': round(avg_body, 2)},
        }
    }

# ====== ② 动量主线判定 ======

def find_available_date(all_stocks, target_date):
    """在股票数据中找到不超过target_date的最新日期"""
    max_date = ''
    for sec, codes in all_stocks.items():
        for code, kls in codes.items():
            if kls and kls[-1]['date'] > max_date:
                max_date = kls[-1]['date']
    if max_date and max_date <= target_date:
        return max_date
    return None

def get_mainline_data(date_str):
    """调用主线判定模块获取当日主线"""
    try:
        sys.path.insert(0, os.path.join(SCRIPTS_DIR))
        from judge_main_line import get_main_lines

        data_file = os.path.join(DATA_DIR, 'all_stocks_60d.json')
        if not os.path.exists(data_file):
            return {'lines': [], 'ranking': {}, 'error': '无数据文件'}

        with open(data_file) as f:
            raw = json.load(f)
        all_stocks = raw.get('stocks', raw)

        # date_str是yyyy-mm-dd格式，数据文件是yyyymmdd格式
        lookup = date_str.replace('-', '')

        # 找到数据文件中可用的最新日期（不超过lookup）
        available_date = find_available_date(all_stocks, lookup)
        if not available_date:
            return {'lines': [], 'ranking': {}, 'error': f'无可用数据(≤{lookup})'}

        main_lines, ranking = get_main_lines(available_date, all_stocks, top_n=3, min_score=15)

        # 格式化输出
        formatted_lines = []
        for name, data in ranking.items():
            formatted_lines.append({
                'name': name,
                'score': data['score'],
                'avg_gain_20d': data['avg_gain_20d'],
                'above_ma20_pct': data['above_ma20_pct'],
                'is_main': name in main_lines
            })
        return {'lines': formatted_lines, 'ranking': ranking, 'main_lines': main_lines, 'data_date': available_date}
    except Exception as e:
        return {'lines': [], 'ranking': {}, 'error': str(e)}

def track_mainline_persistence(date_str, current_lines):
    """跟踪主线持续性：读取历史存档计算Δ"""
    archive_files = sorted([f for f in os.listdir(ARCHIVE_DIR) if f.endswith('.json')])
    persistence = {
        'current_top3': [l['name'] for l in current_lines[:3]],
        'consecutive_days': {},
        'score_trend': {},  # 评分变化
        'rotation': None     # 轮动信号
    }

    # 往前看5个交易日
    lookback = archive_files[-6:-1] if len(archive_files) >= 6 else archive_files[:-1]
    prev_main_sets = []
    for af in lookback:
        fp = os.path.join(ARCHIVE_DIR, af)
        try:
            with open(fp) as f:
                d = json.load(f)
            if 'mainline' in d and d['mainline'].get('lines'):
                prev_lines = [l['name'] for l in d['mainline']['lines'][:3]]
                prev_main_sets.append(prev_lines)
        except:
            continue

    # 计算持续天数
    for line in persistence['current_top3']:
        days = 1
        for prev in reversed(prev_main_sets):
            if line in prev:
                days += 1
            else:
                break
        persistence['consecutive_days'][line] = days

    # 检测轮动：当前top3与昨天比变化
    if prev_main_sets:
        yesterday = prev_main_sets[-1] if prev_main_sets else []
        new_entries = [l for l in persistence['current_top3'] if l not in yesterday]
        disappeared = [l for l in yesterday if l not in persistence['current_top3']]
        if new_entries or disappeared:
            persistence['rotation'] = {
                'new': new_entries,
                'gone': disappeared,
                'signal': '有轮动' if new_entries else '无变化'
            }

    return persistence

# ====== ③ 最强逻辑 — 个股归类/排名 ======

def classify_stocks_by_mainline(mainline_data, holdings, watchlist_signals):
    """
    将持仓个股和买点信号股归类到主线/非主线
    返回每个股的逻辑排名
    """
    ranking = mainline_data.get('ranking', {})
    main_lines_set = set(mainline_data.get('main_lines', []))

    # 加载自选股行业映射
    sector_map = {}
    data_file = os.path.join(DATA_DIR, 'all_stocks_60d.json')
    if os.path.exists(data_file):
        with open(data_file) as f:
            all_stocks = json.load(f)
        for direction, stocks in all_stocks.items():
            for code in stocks:
                sector_map[code] = direction

    def classify_stock(stock):
        code = stock.get('code', '')
        name = stock.get('name', '')
        direction = sector_map.get(code, '未知')
        is_main = direction in main_lines_set

        # 板块内排名（基于涨幅）
        rank_info = {}
        if direction in ranking and ranking[direction].get('total_stocks', 0) > 0:
            rank_info = ranking[direction]

        return {
            'name': name,
            'code': code,
            'direction': direction,
            'is_main': is_main,
            'sector_score': rank_info.get('score', 0),
            'sector_rank': rank_info.get('avg_gain_20d', 0),
            'sector_total': rank_info.get('total_stocks', 0),
        }

    result = {}
    if holdings:
        result['holdings'] = [classify_stock(s) for s in holdings]
    if watchlist_signals:
        result['signals'] = [classify_stock(s) for s in watchlist_signals]
    return result

# ====== ④ 量价择时 — 买点/关键点/止损止盈 ======

def get_buy_sell_signals(holdings, watchlist_signals):
    """
    分析持仓和候选的买卖点信号
    返回关键点、止损位、止盈信号
    """
    result = {'holdings': [], 'signals': []}

    # 对于每个持仓，加载关键点数据
    kp_dir = '/home/ubuntu/.hermes/profiles/3l/data/key_points'
    for stock in (holdings or []):
        code = stock.get('code', '')
        name = stock.get('name', '')
        kp_file = os.path.join(kp_dir, f'{name}_{code}.json')
        kp_data = load_cached_data(kp_file)

        result['holdings'].append({
            'name': name,
            'code': code,
            'buy_point': stock.get('buy_point', '--'),
            'key_points_count': len(kp_data.get('key_points', [])) if kp_data else 0,
            'stop_loss': kp_data.get('stop_loss', '--'),
            'stop_loss_price': kp_data.get('stop_loss_price', '--'),
            'has_stop_loss': bool(kp_data.get('stop_loss')),
            'ema_status': stock.get('ema', '--'),
        })

    for stock in (watchlist_signals or []):
        result['signals'].append({
            'name': stock.get('name', ''),
            'code': stock.get('code', ''),
            'buy_point': stock.get('buy_point', '--'),
            'price': stock.get('price', '--'),
            'change': stock.get('change', 0),
        })

    return result

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

    # 主线方向
    for line in (mainline_data.get('lines', [])[:3]):
        plan['main_lines'].append(f"{line['name']}(评分{line['score']})")

    # 持仓处理建议
    for h in (signals_data.get('holdings', []) or []):
        if h.get('has_stop_loss'):
            plan['action_items'].append(f"🔴 {h['name']} 止损{h['stop_loss_price']} — 严格按止损执行")
        elif not h.get('ema_status') or '多头' not in h.get('ema_status', ''):
            plan['watch_items'].append(f"⚠️ {h['name']} EMA{h.get('ema_status','?')} — 关注趋势是否走坏")

    # 买点信号
    signals = signals_data.get('signals', [])
    if signals:
        plan['action_items'].append(f"📌 发现{len(signals)}个买点信号，关注调整后入场机会")

    # 风险提醒
    if market_cycle.get('score', 0) >= 1:
        plan['risk_reminder'] = '大盘偏波峰，控制仓位，收紧止盈'
    elif market_cycle.get('score', 0) < 0:
        plan['risk_reminder'] = '大盘偏波谷，积极寻找买点，止损后换股补回'
    else:
        plan['risk_reminder'] = '大盘波中，按正常节奏交易，不主跌维持重仓'

    return plan

# ====== 主流程 ======

def generate_daily_review(date_str=None):
    """生成完整每日复盘数据"""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    print(f"[3L复盘] 生成 {date_str} 复盘数据...")

    # 已有存档（带持仓/买点信号等人工数据）
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

    # 获取大盘K线数据
    index_klines = fetch_index_klines(60)
    today_quote = fetch_market_quote()

    # ① 大盘周期判定
    print("[3L复盘] ① 判定大盘周期...")
    market_cycle = judge_market_cycle(index_klines, today_quote)
    if today_quote:
        market_cycle['price'] = today_quote['price']
        market_cycle['change'] = today_quote['change']

    # ② 动量主线评判
    print("[3L复盘] ② 计算动量主线...")
    mainline_data = get_mainline_data(date_str)
    if mainline_data['lines']:
        persistence = track_mainline_persistence(date_str, mainline_data['lines'])
        mainline_data['persistence'] = persistence

    # ③ 最强逻辑归类
    print("[3L复盘] ③ 归类最强逻辑...")
    holdings = existing.get('holdings', []) or existing.get('stocks', {}).get('stocks', [])
    buy_signals = existing.get('buy_signals', [])
    logic_classify = classify_stocks_by_mainline(mainline_data, holdings, buy_signals)

    # ④ 量价择时
    print("[3L复盘] ④ 量价择时分析...")
    timing_signals = get_buy_sell_signals(holdings, buy_signals)

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
        # 保留原有字段
        'holdings': holdings,
        'buy_signals': buy_signals,
        'holdings_review': existing.get('holdings_review', []),
        'buy_signals_review': existing.get('buy_signals', []),
    }

    # 保存
    save_json(os.path.join(ARCHIVE_DIR, f'{date_str}.json'), review)
    print(f"[3L复盘] ✅ 已保存 {date_str} 复盘数据")
    return review

def update_historical_archives():
    """为所有历史存档补充新字段（不破坏已有数据）"""
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
            if 'market_cycle' not in data:  # 旧格式补充
                # 尝试补充
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
