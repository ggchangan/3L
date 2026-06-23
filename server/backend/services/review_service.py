"""
复盘存档服务 — 复盘数据的读取/写入/存档管理 + 编排执行

职责：
  存储层 — 存档的增删查改
  编排层 — 每日复盘流水线的编排执行（调用 review_compute_service 的计算函数）

不再通过 subprocess 调用 generate_review_data.py，改为直接 import。
"""
import json, os, sys, shutil, subprocess
from datetime import datetime
from backend.core.config import (
    REVIEW_ARCHIVE_DIR, REVIEW_DATA_PATH, REVIEW_CHARTS_DIR,
    WWW_DIR, PRIVATE_DIR, SCRIPTS_DIR, MOMENTUM_CACHE_PREFIX,
    CHARTS_DIR, DATA_DIR, INDUSTRY_MAP_PATH, MAINLINES_CACHE_PATH,
    BOARD_CONSTITUENTS_PATH,
)
from backend.core import config

# ── 局部路径常量（旧JSON已迁移至DB，保留供 fallback 读取）──
ALL_STOCKS_PATH = os.path.join(DATA_DIR, 'all_stocks_60d.json')

from backend.core.exceptions import DataError
from backend.core.logger import get_logger

log = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════
# 存储层
# ═══════════════════════════════════════════════════════════════

def load_review_data():
    """加载复盘内存缓存数据"""
    if os.path.isfile(REVIEW_DATA_PATH):
        with open(REVIEW_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'date': '', 'market': {}, 'mainline': {}, 'timing_signals': {},
            'trading_plan': {}, 'holdings': [], 'buy_signals': []}


def save_review_data(data):
    """保存复盘数据到文件"""
    os.makedirs(os.path.dirname(REVIEW_DATA_PATH), exist_ok=True)
    config.atomic_json_dump(data, REVIEW_DATA_PATH, indent=2)


def get_archive_dates():
    """获取所有复盘存档日期（倒序）"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return []
    files = sorted([f.replace('.json', '') for f in os.listdir(REVIEW_ARCHIVE_DIR)
                    if f.endswith('.json')], reverse=True)
    return files


def get_archive(date_str):
    """获取指定日期的复盘存档"""
    path = os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json')
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def get_latest_archive():
    """获取最新一份复盘存档"""
    dates = get_archive_dates()
    if dates:
        return get_archive(dates[0])
    return None


def save_review(data):
    """
    保存复盘数据到两个位置：
      1) data/review_archive/{date}.json（新格式目录）
      2) private/review_archive/{date}.json（兼容旧版）
    """
    date = data.get('date', '')
    if not date:
        return {'status': 'error', 'msg': 'missing date'}
    adir = os.path.join(os.path.dirname(REVIEW_ARCHIVE_DIR), 'data', 'review_archive')
    os.makedirs(adir, exist_ok=True)
    fp = os.path.join(adir, f'{date}.json')
    config.atomic_json_dump(data, fp, indent=2)
    pdir = REVIEW_ARCHIVE_DIR
    os.makedirs(pdir, exist_ok=True)
    pf = os.path.join(pdir, f'{date}.json')
    config.atomic_json_dump(data, pf, indent=2)
    return {'status': 'ok'}


def get_mainline_archive():
    """获取主线数据（包括次级主线）"""
    archive = get_latest_archive()
    if archive and 'mainline' in archive:
        return archive['mainline']
    return {}


# ═══════════════════════════════════════════════════════════════
# 文件辅助
# ═══════════════════════════════════════════════════════════════

def load_cached_data(path):
    """加载缓存JSON"""
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    """保存JSON（自动创建目录）"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════════════
# 编排层 — 复盘数据加载与扫描
# ═══════════════════════════════════════════════════════════════

def load_review_data(date_str, existing, ww_dir):
    """加载持仓数据、扫描结果，检查盈利模式和趋势股

    Returns: (holdings, buy_signals, all_stocks)
    """
    from backend.services.direction_service import get_active as get_active_dirs
    from backend.data_access.data_layer import get_all_stocks, get_holdings

    # 从 DB 读取持仓（user_id=1 默认用户）
    live_holdings = get_holdings(1)
    holdings = live_holdings or existing.get('holdings', []) or existing.get('stocks', {}).get('stocks', [])

    buy_signals = []
    all_stocks = get_all_stocks()

    return holdings, buy_signals, all_stocks


def scan_buy_signals_if_needed(buy_signals, all_stocks_60d, date_str,
                                ww_dir, all_stocks_path, mainline_data,
                                market_cycle, wl_func, holdings_codes=None):
    """扫描/过滤买点信号

    始终按当前已启用方向过滤 buy_signals，
    按 holdings_codes + 启用方向自选股限定扫描范围。

    直接使用 get_stock_card（权威源）判定，不再依赖 format_buy_signals 预过滤。

    Returns: (buy_signals, all_stocks_60d)
    """
    # ── 加载 watchlist 并按已启用方向过滤 ──────────────
    from backend.services.direction_service import get_active as get_active_dirs
    active_dirs = get_active_dirs()
    wl = wl_func() if callable(wl_func) else []
    wl = [s for s in wl if s.get('direction', '其他') in active_dirs]
    wl_codes = set(s['code'] for s in wl)
    # 合并持仓股代码，确保持仓股也被扫描
    if holdings_codes:
        wl_codes |= holdings_codes

    if not wl_codes:
        return [], all_stocks_60d

    # ── 加载 K线缓存 ──
    if all_stocks_60d is None:
        if os.path.isfile(all_stocks_path):
            with open(all_stocks_path) as f:
                as60_data = json.load(f)
            all_stocks_60d = as60_data.get('stocks', {})

    if not all_stocks_60d:
        return [], all_stocks_60d

    # ── 方向映射 ──
    wl_dir_map = {s['code']: s.get('direction', '') for s in wl}

    # ── 用 get_stock_card 逐一扫描 ──
    from backend.services.stock_card_service import get_stock_card
    seen = set()
    ml_names = [l['name'] for l in mainline_data.get('lines', [])]
    scan_date = date_str.replace('-', '')

    for code in wl_codes:
        # 找该股票的K线
        kls = None
        for sec, ss in all_stocks_60d.items():
            if code in ss:
                kls = ss[code]
                break
        if not kls or len(kls) < 30:
            continue

        direction = wl_dir_map.get(code, '')
        try:
            card = get_stock_card(
                code=code, date_str=scan_date,
                market_position=market_cycle.get('position', ''),
                main_lines=ml_names,
                direction=direction,
                klines=kls,
            )
        except Exception:
            continue

        if card.get('signal') != 'buy':
            continue
        if card.get('buy_point') in ('', None):
            continue
        if code in seen:
            continue

        seen.add(code)
        # 直接保存完整卡片格式，generate_buy_signals_review 直接复用无需再调
        buy_signals.append({
            'code': card['code'],
            'name': card['name'],
            'sector': card['sector'],
            'direction': direction,
            'price': card['price'],
            'change': card['change'],
            'score': card['score'],
            'buy_point': card['buy_point'],
            'stop_loss': card['stop_loss'],
            'stop_loss_pct': card['stop_loss_pct'],
            'structure': card['structure'],
            'stage': card['stage'],
            'signal': card['signal'],
            'profit_model1': card['profit_model1'],
            'trend_stock': card.get('trend_stock', False),
            'trading_system': card['trading_system'],
            'trading_reason': card.get('trading_reason', ''),
            'trend_buy_type': card.get('trend_buy_type', ''),
            'trend_bias': card.get('trend_bias', ''),
            'mainline_level': card.get('mainline_level', ''),
            'flags': '',
            'vol_analysis': card.get('vol_analysis', '--'),
            'triggered_signals': card.get('triggered_signals', []),
            'fusion_type': card.get('fusion_type', ''),
            'fusion_reason': card.get('fusion_reason', ''),
            'wave_position': card.get('wave_position', ''),
            'action_type': card.get('action_type', '持有'),
            'action_signal': card.get('action_signal', ''),
            'action_priority': card.get('action_priority', '中'),
            'action_reason': card.get('action_reason', ''),
            'ema': card.get('ema', ''),
        })

    print(f"[3L复盘] StockCard扫描: {len(buy_signals)} 个买点信号")

    # ── 盈利模式1 + 趋势股补充扫描 ──
    try:
        from backend.core.buy_point_detection import check_profit_model1_on_signals, check_trend_stock_on_signals
        pm1 = check_profit_model1_on_signals([], all_stocks_60d, date_str)
        trend = check_trend_stock_on_signals([], all_stocks_60d, date_str)
        extra = pm1 + trend
        if extra:
            for s in extra:
                if s['code'] not in seen:
                    seen.add(s['code'])
                    buy_signals.append(s)
            print(f"[3L复盘] 补充扫描: {len(extra)} 个额外信号 (盈利模式1+趋势股)")
    except Exception as _e:
        print(f"[3L复盘] 补充扫描跳过: {_e}")

    return buy_signals, all_stocks_60d





# ═══════════════════════════════════════════════════════════════
# 编排层 — 每日复盘主流程
# ═══════════════════════════════════════════════════════════════

def generate_daily_review(date_str=None):
    """生成完整每日复盘数据"""
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    from backend.services.review_compute_service import (
        is_trading_day, fetch_index_klines, fetch_market_quote,
        judge_peak_valley, get_mainline_data, get_concept_mainline_data, track_mainline_persistence,
        generate_trading_plan, get_buy_sell_signals, load_market_data_for_profit_check,
    )
    from backend.core.review_analysis import generate_holdings_review, generate_buy_signals_review
    from backend.core.scan_buy_signals import get_main_lines
    from backend.data_access.data_layer import get_watchlist

    if not is_trading_day(date_str):
        print(f"[3L复盘] ⚠️ {date_str} 非A股交易日，跳过")
        return

    print(f"[3L复盘] 生成 {date_str} 复盘数据...")

    existing = load_cached_data(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'))
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
    index_klines = fetch_index_klines(120)
    index_klines = [k for k in index_klines if k['date'] <= date_str]
    if not index_klines:
        index_klines = fetch_index_klines(120)
        index_klines = [k for k in index_klines if k['date'] <= date_str]
    today_quote = fetch_market_quote()

    print(f"[3L复盘] K线数据: 共{len(index_klines)}天, 最新={index_klines[0]['date'] if index_klines else '无'}")

    # ① 大盘周期判定
    print("[3L复盘] ① 判定大盘周期(V5)...")
    market_cycle = judge_peak_valley(index_klines)
    if index_klines:
        last = index_klines[0]
        prev = index_klines[1] if len(index_klines) >= 2 else None
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

    # 概念主线
    print("[3L复盘] ② 计算概念主线...")
    concept_mainline_data = get_concept_mainline_data(date_str)
    mainline_data['concept_mainline'] = concept_mainline_data

    # ③ 加载数据
    print("[3L复盘] ③ 加载数据...")
    holdings, buy_signals, all_stocks = load_review_data(
        date_str, existing, WWW_DIR
    )

    print("[3L复盘] ③ 量价择时分析...")
    buy_signals, all_stocks_60d = scan_buy_signals_if_needed(
        buy_signals, all_stocks if 'all_stocks' in dir() else None,
        date_str, WWW_DIR, ALL_STOCKS_PATH,
        mainline_data, market_cycle, get_watchlist,
    )

    # 从最新 buy_signals 生成持仓信号
    timing_signals, stock_cache, bs_by_code = get_buy_sell_signals(
        holdings, buy_signals, date_str, all_stocks_data=all_stocks_60d
    )

    # 确保 all_stocks_60d 已加载
    if 'all_stocks_60d' not in dir() or not all_stocks_60d:
        try:
            if os.path.isfile(ALL_STOCKS_PATH):
                with open(ALL_STOCKS_PATH) as _f:
                    all_stocks_60d = json.load(_f).get('stocks', {})
        except:
            all_stocks_60d = {}

    # 计算趋势主线列表
    _trend_mainlines = get_main_lines()
    if not _trend_mainlines:
        try:
            _trend_mainlines = [l['name'] for l in (mainline_data.get('lines', []) + mainline_data.get('secondary', []))]
        except:
            _trend_mainlines = None

    struct_priority = {'上涨趋势': 0, '区间震荡': 1, '下降趋势': 2}

    holdings_review = generate_holdings_review(
        holdings=holdings, stocks=all_stocks_60d,
        buy_signals=buy_signals,
        timing_signals_holdings=timing_signals.get('holdings', []),
        bs_by_code=bs_by_code,
        date_str=date_str, mainlines=mainline_data,
        trend_mainlines=_trend_mainlines,
    )

    # 买点方向映射（从 watchlist 取）
    _wl = get_watchlist()
    _wl_stocks = _wl.get('stocks', _wl) if isinstance(_wl, dict) else _wl
    _dir_map = {s['code']: s.get('direction', '') for s in _wl_stocks if isinstance(s, dict) and s.get('code')}

    buy_signals_review = generate_buy_signals_review(
        buy_signals=buy_signals, stocks=all_stocks_60d,
        stock_cache=stock_cache,
        date_str=date_str, mainlines=mainline_data,
        trend_mainlines=_trend_mainlines,
        direction_map=_dir_map,
    )

    # ④ 每日交易计划
    print("[3L复盘] ④ 生成交易计划...")
    trading_plan = generate_trading_plan(market_cycle, mainline_data, timing_signals, holdings,
                                         holdings_review=holdings_review, buy_signals_review=buy_signals_review)

    # 组装
    review = {
        'date': date_str,
        'market': {
            **market_cycle,
            'date': date_str,
        },
        'mainline': mainline_data,
        'timing_signals': timing_signals,
        'trading_plan': trading_plan,
        'holdings': holdings,
        'buy_signals': buy_signals,
        'holdings_review': holdings_review,
        'buy_signals_review': buy_signals_review,
    }

    # 保存动量数据
    try:
        mom_cache = os.path.join(WWW_DIR, 'data', 'cache', f'momentum_{date_str}.json')
        if os.path.isfile(mom_cache):
            with open(mom_cache) as _f:
                review['momentum'] = json.load(_f)
        else:
            mom_script = os.path.join(WWW_DIR, 'fetch_momentum.py')
            if os.path.isfile(mom_script):
                r = subprocess.run([sys.executable, mom_script], capture_output=True, text=True, timeout=90)
                if r.returncode == 0:
                    review['momentum'] = json.loads(r.stdout)
    except Exception as e:
        print(f"[3L复盘] 保存动量数据失败: {e}")

    # 保存行业地图
    try:
        im_path = INDUSTRY_MAP_PATH
        if os.path.isfile(im_path):
            with open(im_path) as _f:
                raw_map = json.load(_f)
            industry_groups = {}
            for code, info in raw_map.items():
                ind = info.get('ths_industry', '') or '未知'
                if ind in ('未知', '获取失败') or ind.startswith('ERROR:'):
                    continue
                if ind not in industry_groups:
                    industry_groups[ind] = []
                industry_groups[ind].append({
                    'code': code,
                    'name': info.get('name', info.get('direction', '')),
                    'direction': info.get('direction', ''),
                })
            review['industry_map_archive'] = {
                'groups': dict(sorted(industry_groups.items(), key=lambda x: -len(x[1]))),
                'total': sum(len(v) for v in industry_groups.values()),
            }
    except Exception as e:
        print(f"[3L复盘] 保存行业地图失败: {e}")

    # 保存行业板块排行
    try:
        import akshare as ak
        df = ak.stock_board_industry_summary_ths()
        review['industry_boards_archive'] = df.fillna('').to_dict('records')
    except Exception as e:
        print(f"[3L复盘] 保存行业板块排行失败: {e}")

    # 保存存档
    save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), review)
    save_json(REVIEW_DATA_PATH, review)
    print(f"[3L复盘] ✅ 已保存 {date_str} 复盘数据")

    # 写入主线缓存（含行业+概念主线）
    _cm = mainline_data.get('concept_mainline', {})
    _mainlines_cache = {
        'lines': [l['name'] for l in mainline_data.get('lines', [])],
        'secondary': [l['name'] for l in mainline_data.get('secondary', [])],
        'concept_mainline': {
            'lines': [l['name'] for l in _cm.get('lines', [])],
            'secondary': [l['name'] for l in _cm.get('secondary', [])],
        },
    }
    save_json(MAINLINES_CACHE_PATH, _mainlines_cache)

    # 生成买点信号的关键点图
    try:
        bp_script = os.path.join(config.SCRIPTS_DIR, 'batch_gen_charts.py')
        if os.path.isfile(bp_script):
            subprocess.run([sys.executable, bp_script], timeout=120, capture_output=True)
            print("[3L复盘] 🎨 关键点图已更新")
    except Exception as e:
        print(f"[3L复盘] 🎨 生成关键点图跳过: {e}")

    # 生成资金流向图
    try:
        ff_script = os.path.join(WWW_DIR, 'gen_fund_flow_chart.py')
        if os.path.isfile(ff_script):
            subprocess.run([sys.executable, ff_script, date_str],
                           timeout=120, capture_output=True, cwd=WWW_DIR)
            print("[3L复盘] 💰 资金流向图已生成")
    except Exception as e:
        print(f"[3L复盘] 💰 生成资金流向图跳过: {e}")

    # 归档图表
    try:
        chart_archive_dir = os.path.join(CHARTS_DIR, 'archive', date_str)
        os.makedirs(chart_archive_dir, exist_ok=True)
        src_charts = [
            (os.path.join(CHARTS_DIR, 'sz000985.svg'), 'sz000985.svg'),
            (os.path.join(CHARTS_DIR, 'zzqz_key_points.svg'), 'zzqz_key_points.svg'),
            (os.path.join(CHARTS_DIR, 'fund_flow_chart.png'), 'fund_flow_chart.png'),
        ]
        for src, basename in src_charts:
            if os.path.isfile(src):
                dst = os.path.join(chart_archive_dir, basename)
                shutil.copy2(src, dst)
                print(f"[3L复盘] 📊 图表已归档: archive/{date_str}/{basename}")
        review['charts'] = {
            'index_chart': f'/pub/charts/archive/{date_str}/zzqz_key_points.svg',
            'fund_flow': f'/pub/charts/archive/{date_str}/fund_flow_chart.png',
        }
        save_json(os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json'), review)
    except Exception as e:
        print(f"[3L复盘] 📊 图表归档失败: {e}")

    # 生成每日成果PDF
    try:
        generate_daily_achievements_pdf(date_str)
    except Exception as e:
        print(f"[3L复盘] 📄 生成每日成果PDF失败: {e}")

    return review


def compute_review_real_time(date_str=None):
    """纯实时计算复盘数据，不读写存档、不生成文档/图表

    返回完整的 review dict，供 /api/review/today 实时调用。
    无缓存，每次重新读取本地文件实时计算。
    """
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')

    from backend.services.review_compute_service import (
        is_trading_day,
        judge_peak_valley, get_mainline_data, get_concept_mainline_data, track_mainline_persistence,
        generate_trading_plan, get_buy_sell_signals, load_market_data_for_profit_check,
    )
    from backend.core.review_analysis import generate_holdings_review, generate_buy_signals_review
    from backend.core.scan_buy_signals import get_main_lines
    from backend.data_access.data_layer import get_watchlist, get_all_stocks, get_index_klines, get_concept_list, get_stock_concept_map

    print(f"[3L复盘实时] 计算 {date_str} 复盘数据...")

    # 获取大盘K线数据（本地，17:00 cron 已更新）
    index_klines = get_index_klines()
    if isinstance(index_klines, list):
        index_klines = [k for k in index_klines if k['date'] <= date_str.replace('-', '')]
    else:
        index_klines = []

    # ① 大盘周期判定
    market_cycle = judge_peak_valley(index_klines)
    if index_klines:
        last = index_klines[0]
        prev = index_klines[1] if len(index_klines) >= 2 else None
        market_cycle['price'] = f"{last['close']:.2f}"
        if prev:
            chg_pct = (last['close'] - prev['close']) / prev['close'] * 100
            market_cycle['change'] = round(chg_pct, 2)
        else:
            market_cycle['change'] = 0
        market_cycle['data_date'] = last.get('date', date_str)

    # ② 动量主线
    mainline_data = get_mainline_data(date_str)
    if mainline_data.get('lines'):
        persistence = track_mainline_persistence(date_str, mainline_data['lines'])
        mainline_data['persistence'] = persistence

    # 概念主线
    concept_mainline_data = get_concept_mainline_data(date_str)
    mainline_data['concept_mainline'] = concept_mainline_data

    # ③ 扫描买点信号（只扫持仓股 + 启用方向自选股）
    all_stocks = get_all_stocks()
    # get_all_stocks() 返回 {方向: {code: [kline,...]}, 'last_updated': '...'}
    # 过滤掉非 dict 字段（如 last_updated）
    all_stocks_60d = {k: v for k, v in all_stocks.items()
                      if isinstance(v, dict)} if isinstance(all_stocks, dict) else {}
    if not all_stocks_60d:
        if os.path.isfile(ALL_STOCKS_PATH):
            with open(ALL_STOCKS_PATH) as _f:
                all_stocks_60d = json.load(_f).get('stocks', {})

    # 先加载持仓股，合并到扫描范围
    from backend.data_access.data_layer import get_holdings
    holdings = get_holdings(1)

    buy_signals, all_stocks_60d = scan_buy_signals_if_needed(
        [], all_stocks_60d,
        date_str, WWW_DIR, ALL_STOCKS_PATH,
        mainline_data, market_cycle, get_watchlist,
        holdings_codes={h['code'] for h in holdings if h.get('code')},
    )

    timing_signals, stock_cache, bs_by_code = get_buy_sell_signals(
        holdings, buy_signals, date_str, all_stocks_data=all_stocks_60d
    )

    # 趋势主线列表
    _trend_mainlines = get_main_lines()
    if not _trend_mainlines:
        try:
            _trend_mainlines = [l['name'] for l in (mainline_data.get('lines', []) + mainline_data.get('secondary', []))]
        except:
            _trend_mainlines = None

    # 持仓复盘 + 买点信号复盘
    holdings_review = generate_holdings_review(
        holdings=holdings, stocks=all_stocks_60d,
        buy_signals=buy_signals,
        timing_signals_holdings=timing_signals.get('holdings', []),
        bs_by_code=bs_by_code,
        date_str=date_str, mainlines=mainline_data,
        trend_mainlines=_trend_mainlines,
    )

    # 买点方向映射（从 watchlist 取）
    _wl = get_watchlist()
    _wl_stocks = _wl.get('stocks', _wl) if isinstance(_wl, dict) else _wl
    _dir_map = {s['code']: s.get('direction', '') for s in _wl_stocks if isinstance(s, dict) and s.get('code')}

    buy_signals_review = generate_buy_signals_review(
        buy_signals=buy_signals, stocks=all_stocks_60d,
        stock_cache=stock_cache,
        date_str=date_str, mainlines=mainline_data,
        trend_mainlines=_trend_mainlines,
        direction_map=_dir_map,
    )

    # 从 backend.services.direction_service import get_all_ordered 移到函数头
    from backend.services.direction_service import get_all_ordered

    # 构建行业/概念 → 机会类型映射（在生成交易计划之前）
    opp_map = {}
    for entry in mainline_data.get('all_ranked', []):
        opp_map[entry['name']] = entry.get('opportunity', '--')
    for entry in concept_mainline_data.get('all_ranked', []):
        opp_map[entry['name']] = entry.get('opportunity', '--')

    # ④ 交易计划
    trading_plan = generate_trading_plan(market_cycle, mainline_data, timing_signals, holdings,
                                         holdings_review=holdings_review, buy_signals_review=buy_signals_review,
                                         opportunity_map=opp_map)

    # 写入主线缓存（供趋势候选页读，含行业+概念主线）
    _cm = mainline_data.get('concept_mainline', {})
    _mainlines_cache = {
        'lines': [l['name'] for l in mainline_data.get('lines', [])],
        'secondary': [l['name'] for l in mainline_data.get('secondary', [])],
        'concept_mainline': {
            'lines': [l['name'] for l in _cm.get('lines', [])],
            'secondary': [l['name'] for l in _cm.get('secondary', [])],
        },
    }
    save_json(MAINLINES_CACHE_PATH, _mainlines_cache)

    # ── 板块领涨股（为每个行业/概念板块加 leaders 字段） ──
    try:
        # 加载 THS 行业板块 → 成分股 映射（由 build_board_mapping.py 生成）
        _board_data = {}
        if os.path.isfile(BOARD_CONSTITUENTS_PATH):
            with open(BOARD_CONSTITUENTS_PATH) as _f:
                _bc = json.load(_f)
            _board_data = _bc.get('boards', {})

        # 从数据库 stock_daily 构建 K线索引（覆盖全量股票）
        _kline_index = {}
        _stock_names = {}
        try:
            from backend.data_access.tushare_db import TushareDB
            _tdb = TushareDB()

            # 股票名称从 stock_basic 取
            try:
                _sb_rows = _tdb.query_many('stock_basic')
                for _r in _sb_rows:
                    _stock_names[_r['ts_code']] = _r.get('name', '')
            except Exception:
                pass

            _conn = _tdb._get_conn()
            _cur = _conn.cursor()
            _cur.execute("SELECT DISTINCT trade_date FROM stock_daily ORDER BY trade_date DESC LIMIT 5")
            _recent_dates = sorted([list(r.values())[0] for r in _cur.fetchall()])
            _cur.close()
            _conn.close()

            if _recent_dates:
                _rows = _tdb.query_many('stock_daily',
                    where='trade_date IN (%s)' % ','.join(['%s'] * len(_recent_dates)),
                    params=_recent_dates)
                for _r in _rows:
                    _tc = _r['ts_code']
                    if _tc not in _kline_index:
                        _kline_index[_tc] = []
                    _kline_index[_tc].append({
                        'date': str(_r['trade_date']),
                        'close': float(_r['close']),
                        'open': float(_r['open']),
                        'high': float(_r['high']),
                        'low': float(_r['low']),
                        'volume': float(_r['vol']),
                    })
                # 按日期升序
                for _tc in _kline_index:
                    _kline_index[_tc].sort(key=lambda x: x['date'])
        except Exception as _e:
            print(f'[3L复盘] 数据库加载K线失败: {_e}')
            import traceback; traceback.print_exc()

        def _calc_stock_leaders(stock_codes, kline_index, stock_names, top_n=5):
            _candidates = []
            for _c in stock_codes:
                _kls = kline_index.get(_c)
                if not _kls or len(_kls) < 5:
                    continue
                _close_now = _kls[-1]['close']
                _close_1d = _kls[-2]['close'] if len(_kls) >= 2 else _close_now
                _close_5d = _kls[-5]['close'] if len(_kls) >= 5 else _close_now
                _chg_1d = round((_close_now - _close_1d) / _close_1d * 100, 1)
                _chg_5d = round((_close_now - _close_5d) / _close_5d * 100, 1)
                _name = stock_names.get(_c, _c)
                _tag = '🏆领涨' if _chg_5d >= 5 else ('💪中军' if _chg_1d > 0 else '')
                _candidates.append({
                    'code': _c, 'name': _name or _c,
                    'chg_1d': _chg_1d, 'chg_5d': _chg_5d, 'tag': _tag,
                })
            _candidates.sort(key=lambda x: -x['chg_5d'])
            return _candidates[:top_n]

        _concept_list = get_concept_list()

        if mainline_data.get('all_ranked'):
            for _entry in mainline_data['all_ranked']:
                _sname = _entry.get('name', '')
                _codes = _board_data.get(_sname, [])
                _entry['leaders'] = _calc_stock_leaders(_codes, _kline_index, _stock_names)

        _cm = mainline_data.get('concept_mainline', {})
        if _cm.get('all_ranked'):
            for _entry in _cm['all_ranked']:
                _cname = _entry.get('name', '')
                _ccode = None
                for _cc, _ci in _concept_list.items():
                    if _ci.get('name') == _cname:
                        _ccode = _cc
                        break
                _concept_stocks = _concept_list.get(_ccode, {}).get('stocks', []) if _ccode else []
                _entry['leaders'] = _calc_stock_leaders(_concept_stocks, _kline_index, _stock_names)
    except Exception as e:
        print(f'[3L复盘] ⚠️ 板块领涨股计算失败: {e}')
        import traceback; traceback.print_exc()

    # ── 检查板块数据时效性 ──
    _data_stale = False
    try:
        from backend.data_access.data_layer import get_sector_daily
        _sd = get_sector_daily()
        _lu = _sd.get('last_updated', '') if isinstance(_sd, dict) else ''
        _today_yyyymmdd = date_str.replace('-', '')
        if _lu and _lu < _today_yyyymmdd:
            _data_stale = True
    except:
        pass

    review = {
        'date': date_str,
        'market': {**market_cycle, 'date': date_str},
        'mainline': mainline_data,
        'data_stale': _data_stale,
        'timing_signals': timing_signals,
        'trading_plan': trading_plan,
        'holdings': holdings,
        'buy_signals': buy_signals,
        'holdings_review': holdings_review,
        'buy_signals_review': buy_signals_review,
        'direction_order': get_all_ordered(),
        'opportunity_map': opp_map,
    }

    return review


def generate_daily_achievements_pdf(date_str):
    """生成每日成果PDF，自动跳过已存在的"""
    pdf_name = f'每日成果_{date_str.replace("-", "")}.pdf'
    pdf_path = os.path.join(WWW_DIR, 'files', pdf_name)
    if os.path.isfile(pdf_path):
        print(f"[3L复盘] 📄 每日成果PDF已存在: {pdf_name}")
        return

    dt = datetime.strptime(date_str, '%Y-%m-%d')
    weekdays = ['一','二','三','四','五','六','日']
    wd = weekdays[dt.weekday()]

    review_file = os.path.join(REVIEW_ARCHIVE_DIR, f'{date_str}.json')
    market_cycle = '未知'
    mainline_count = 0
    if os.path.isfile(review_file):
        try:
            with open(review_file) as f:
                rd = json.load(f)
            mc = rd.get('market_cycle', {})
            if isinstance(mc, dict):
                market_cycle = mc.get('position', '未知')
            ml = rd.get('mainlines', {})
            if isinstance(ml, dict):
                ml_list = ml.get('main_lines', ml.get('sectors', []))
                if isinstance(ml_list, list):
                    mainline_count = len(ml_list)
        except:
            pass

    html_content = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>3L每日成果 · {date_str}</title>
<style>
body{{font-family:'Noto Sans CJK SC','WenQuanYi Zen Hei',sans-serif;color:#333;margin:40px;background:#fff}}
h1{{font-size:22px;color:#2563eb;border-bottom:2px solid #2563eb;padding-bottom:10px;margin-bottom:20px}}
.meta{{color:#888;font-size:13px;margin-bottom:24px}}
.section{{margin-bottom:28px}}
.section-title{{font-size:16px;color:#1e40af;background:#eff6ff;padding:10px 14px;border-left:4px solid #2563eb;margin-bottom:12px}}
.section-title .num{{display:inline-flex;width:24px;height:24px;background:#2563eb;color:#fff;border-radius:50%;align-items:center;justify-content:center;font-size:12px;flex-shrink:0;margin-right:8px}}
.item{{padding:8px 14px;margin-bottom:6px;border-left:3px solid #e5e7eb}}
.item .title{{font-weight:600;color:#333}}
.item .desc{{color:#666;font-size:13px;margin-top:4px;line-height:1.6}}
.tag{{display:inline-block;padding:1px 8px;border-radius:10px;font-size:11px;margin-left:8px}}
.tag-blue{{background:#dbeafe;color:#2563eb}}
</style></head>
<body>
<h1>📊 3L 每日复盘 · {date_str} 星期{wd}</h1>
<div class="meta">自动生成 · 复盘数据概要</div>
<div class="section">
<div class="section-title"><span class="num">1</span> 大盘周期</div>
<div class="item"><div class="title">当前判定：{market_cycle}</div></div>
</div>
<div class="section">
<div class="section-title"><span class="num">2</span> 动量主线</div>
<div class="item"><div class="title">主线板块数量：{mainline_count} <span class="tag tag-blue">得分≥15</span></div></div>
</div>
<div class="section">
<div class="section-title"><span class="num">3</span> 关键变更备注</div>
<div class="item"><div class="title">本复盘由3L每日复盘系统自动生成</div><div class="desc">数据源：腾讯API(中证全指) + akshare(同花顺行业板块) + 全量创新高扫描。</div></div>
</div>
</body></html>'''

    html_path = os.path.join(WWW_DIR, 'files', f'每日成果_{date_str.replace("-", "")}.html')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    result = subprocess.run(
        ['wkhtmltopdf', '--encoding', 'utf-8', '--page-size', 'A4', html_path, pdf_path],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode == 0:
        print(f"[3L复盘] 📄 每日成果PDF已生成: {pdf_name}")
    else:
        print(f"[3L复盘] ⚠️ PDF生成失败: {result.stderr[-200:]}")
    try:
        os.remove(html_path)
    except OSError:
        pass


def update_historical_archives():
    """为所有历史存档补充新字段"""
    if not os.path.isdir(REVIEW_ARCHIVE_DIR):
        return
    for fname in sorted(os.listdir(REVIEW_ARCHIVE_DIR)):
        if not fname.endswith('.json'):
            continue
        date_str = fname[:-5]
        fp = os.path.join(REVIEW_ARCHIVE_DIR, fname)
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


# ═══════════════════════════════════════════════════════════════
# 编排层 — API 入口（直接 import，不再 subprocess）
# ═══════════════════════════════════════════════════════════════

def run_daily_review():
    """运行每日复盘完整流水线（cron调用），返回日志列表"""
    from backend.services.review_compute_service import is_trading_day

    DATE = datetime.now().strftime('%Y-%m-%d')
    logs = []

    def run_script(desc, cmd, cwd=None):
        logs.append(f'[{datetime.now().strftime("%H:%M:%S")}] {desc}...')
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=cwd)
            if r.returncode == 0:
                logs.append(f'  ✅成功 ({len(r.stdout)}B)')
            else:
                logs.append(f'  ⚠️失败(code={r.returncode}): {r.stderr[-200:]}')
        except Exception as e:
            logs.append(f'  ❌异常: {str(e)}')

    if not is_trading_day(DATE):
        logs.append(f'[3L复盘] {DATE} 非交易日，跳过')
        return {'status': 'skipped', 'date': DATE, 'logs': logs}

    # 清理旧缓存
    for f in ['review_data.json', f'review_archive/{DATE}.json']:
        fp = os.path.join(PRIVATE_DIR, f)
        if os.path.isfile(fp):
            os.remove(fp)

    run_script('Step1 更新数据+扫买点',
        [sys.executable, f'{SCRIPTS_DIR}/update_stock_data.py'], cwd=WWW_DIR)
    run_script('Step3a 中证全指图',
        [sys.executable, os.path.join(WWW_DIR, 'gen_index_chart.py')])
    try:
        shutil.copy2(os.path.join(CHARTS_DIR, 'sz000985.svg'),
                     os.path.join(CHARTS_DIR, 'zzqz_v2.svg'))
        logs.append(f'  ✅SVG已复制')
    except Exception as e:
        logs.append(f'  ⚠️SVG复制失败: {e}')
    run_script('Step3b 批量个股图',
        [sys.executable, f'{SCRIPTS_DIR}/batch_gen_charts.py'])
    mom_cache = f'{MOMENTUM_CACHE_PREFIX}{DATE}.json'
    if os.path.isfile(mom_cache):
        os.remove(mom_cache)
    run_script('Step4a 拉取动量数据',
        [sys.executable, os.path.join(WWW_DIR, 'fetch_momentum.py')])
    run_script('Step4b 生成复盘',
        [sys.executable, os.path.join(WWW_DIR, 'generate_review_data.py'), DATE])

    return {'status': 'ok', 'date': DATE, 'logs': logs}


def generate_review(date_arg=None):
    """单独生成复盘数据（通过 /api/review/generate 调用）— 直接 import"""
    try:
        result = generate_daily_review(date_arg)
        if result is None:
            return {'status': 'skipped', 'msg': f'{date_arg or "today"} 非交易日'}
        return {'status': 'ok', 'date': result.get('date', '')}
    except Exception as e:
        raise DataError(f"复盘服务异常: {e}") from e
