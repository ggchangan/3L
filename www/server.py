#!/usr/bin/env python3
"""
3L Daily Achievements Web Server + Review API
"""
import os, json, signal, sys, base64, mimetypes, urllib.parse, time
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from scripts.data_layer import INDUSTRY_MAP_PATH, INDUSTRY_LEADERS_PATH

PORT = 8080
WWW_DIR = '/home/ubuntu/www'
AUTH_USER = 'ggchangan'
AUTH_PASS = '19891121'
PROTECTED_PREFIX = '/private/'

REVIEW_DATA = {}
DATA_FILE = os.path.join(WWW_DIR, 'private', 'review_data.json')
ARCHIVE_DIR = os.path.join(WWW_DIR, 'private', 'review_archive')

def load_review_data():
    global REVIEW_DATA
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: REVIEW_DATA = json.load(f)
            return
        except: pass
    # fallback: 加载最新复盘存档
    if os.path.isdir(ARCHIVE_DIR):
        archives = sorted([f for f in os.listdir(ARCHIVE_DIR) if f.endswith('.json')])
        if archives:
            latest = archives[-1]
            try:
                with open(os.path.join(ARCHIVE_DIR, latest)) as f:
                    REVIEW_DATA = json.load(f)
            except: pass
def save_review_data():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w') as f: json.dump(REVIEW_DATA, f, ensure_ascii=False, indent=2)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WWW_DIR, **kwargs)

    def send_error(self, code, message=None, explain=None):
        if code == 401:
            raw = (
                'HTTP/1.1 401 Unauthorized\r\n'
                'WWW-Authenticate: Basic realm="私密持仓"\r\n'
                'Content-Type: text/plain\r\n'
                'Content-Length: 19\r\n'
                'Connection: close\r\n'
                '\r\n'
                '401 Unauthorized Login'
            ).encode()
            self.wfile.write(raw)
            self.close_connection = True
            return
        super().send_error(code, message, explain)

    def _serve_file(self, fp, ct=None, no_cache=False, as_attachment=False):
        """Serve a file with proper headers."""
        with open(fp, 'rb') as f:
            data = f.read()
        if ct is None:
            ct, _ = mimetypes.guess_type(fp)
        self.send_response(200)
        if as_attachment:
            fn = os.path.basename(fp)
            try:
                fn_ascii = fn.encode('ascii').decode()
            except:
                fn_ascii = 'download'
            disp = f'attachment; filename="{fn_ascii}"; filename*=UTF-8\'\'{quote(fn)}'
            self.send_header('Content-Disposition', disp)
        if ct and ct.startswith('text/html'):
            ct = ct + '; charset=utf-8'
        self.send_header('Content-Type', ct or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        if no_cache:
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(data)
        self.wfile.flush()

    def do_GET(self):
        load_review_data()
        path = self.path.split('?')[0]  # strip query string

        # --- Protected paths with auth ---
        if path.startswith(PROTECTED_PREFIX):
            auth = self.headers.get('Authorization', '')
            ok = False
            if auth.startswith('Basic '):
                try:
                    d = base64.b64decode(auth[6:]).decode()
                    u, p = d.split(':', 1)
                    ok = (u == AUTH_USER and p == AUTH_PASS)
                except: pass
            if not ok:
                self.send_error(401)
                return

            # Authed - serve the file (no-cache for HTML pages)
            rel = path.lstrip('/')
            fp = os.path.join(WWW_DIR, rel)
            if not os.path.isfile(fp):
                self.send_error(404)
                return
            ct, _ = mimetypes.guess_type(fp)
            no_cache = ct == 'text/html'
            self._serve_file(fp, ct, no_cache=no_cache)
            return

        # --- Download endpoint (force attachment) ---
        if path.startswith('/download/'):
            rel = path[len('/download/'):]
            # URL decode to get actual filename
            rel = os.path.basename(rel)  # strip any trailing path
            rel = urllib.parse.unquote(rel)
            fp = os.path.join(WWW_DIR, 'files', rel)
            if not os.path.isfile(fp):
                self.send_error(404)
                return
            self._serve_file(fp, as_attachment=True)
            return

        # --- Public API ---
        if path == '/api/holdings':
            fp = os.path.join(WWW_DIR, 'private', 'holdings.json')
            if os.path.isfile(fp):
                with open(fp, 'r', encoding='utf-8') as f:
                    return self.send_json(json.load(f))
            return self.send_json({'holdings': []})

        if path == '/api/trades':
            fp = os.path.join(WWW_DIR, 'private', 'trades.json')
            if os.path.isfile(fp):
                with open(fp, 'r', encoding='utf-8') as f:
                    return self.send_json(json.load(f))
            return self.send_json({'trades': []})

        if path == '/api/market':
            return self.send_json(REVIEW_DATA.get('market', {}))
        if path == '/api/mainlines':
            return self.send_json(REVIEW_DATA.get('mainlines', {}))
        if path == '/api/stocks':
            return self.send_json(REVIEW_DATA.get('stocks', {}))
        if path == '/api/review':
            return self.send_json(REVIEW_DATA)
        
        # /api/review/YYYY-MM-DD → 返回对应存档
        if path.startswith('/api/review/') and len(path) > 12:
            date_str = path[12:]  # strip '/api/review/'
            if date_str == 'dates':
                # 返回可用日期列表
                dates = []
                if os.path.isdir(ARCHIVE_DIR):
                    import re
                    dates = sorted([
                        f[:-5] for f in os.listdir(ARCHIVE_DIR)
                        if f.endswith('.json') and re.match(r'^\d{4}-\d{2}-\d{2}\.json$', f)
                    ])
                return self.send_json({'dates': dates})
            fp = os.path.join(ARCHIVE_DIR, f'{date_str}.json')
            if os.path.isfile(fp):
                self._serve_file(fp, 'application/json; charset=utf-8')
            else:
                self.send_json({'error': 'not found', 'date': date_str})
            return

        # --- 个股分析API ---
        if path == '/api/stock-analysis':
            parsed = urllib.parse.urlparse(self.path)
            q = urllib.parse.parse_qs(parsed.query).get('q', [''])[0].strip()
            if not q:
                self.send_json({'error': '请输入股票代码或名称'})
                return

            from scripts.data_layer import get_all_stocks, get_watchlist, get_review_archive
            from scripts.buy_point_detection import (
                detect_buy_point, check_trend_stock, check_profit_model1,
                detect_huicai_buy_point, find_idx, _ema_list, _resolve_code,
                _find_support_levels,
            )
            from ema_utils import get_structure, get_stage

            stocks = get_all_stocks()
            wl = get_watchlist()
            wl_codes = set(s['code'] for s in wl)

            # 搜索股票：先精确匹配code，再模糊匹配code，再模糊匹配name
            matched_code = None
            matched_direction = None
            matched_name = None

            # 精确code匹配
            for sec, ss in stocks.items():
                if q in ss:
                    matched_code, matched_direction = q, sec
                    matched_name = ss[q][0].get('name', q) if ss[q] else q
                    break

            if not matched_code:
                # 模糊匹配code（部分输入）
                for sec, ss in stocks.items():
                    for code in ss:
                        if q in code or code.endswith(q):
                            matched_code, matched_direction = code, sec
                            matched_name = ss[code][0].get('name', code) if ss[code] else code
                            break
                    if matched_code:
                        break

            if not matched_code:
                # 模糊匹配name
                for sec, ss in stocks.items():
                    for code, kls in ss.items():
                        name = kls[0].get('name', '') if kls else ''
                        if q in name:
                            matched_code, matched_direction = code, sec
                            matched_name = name
                            break
                    if matched_code:
                        break

            if not matched_code:
                self.send_json({'error': f'未找到股票: {q}'})
                return

            # 获取K线
            kls = stocks[matched_direction][matched_code]
            if not kls or len(kls) < 30:
                self.send_json({'error': f'{matched_name} 数据不足30条'})
                return

            today_str = kls[-1]['date']
            today_fmt = today_str[:4] + '-' + today_str[4:6] + '-' + today_str[6:8]

            # 构建all_stocks子集（只含这只股票，detect_buy_point需要这个格式）
            sub_stocks = {matched_direction: {matched_code: kls}}

            # 分析
            bt = detect_buy_point(matched_code, today_fmt, sub_stocks)
            trend = bool(check_trend_stock(matched_code, today_fmt, sub_stocks))
            hc = detect_huicai_buy_point(matched_code, today_fmt, sub_stocks)
            pm1 = check_profit_model1(matched_code, today_fmt, sub_stocks)

            # 结构/阶段
            closes = [k['close'] for k in kls]
            structure = get_structure(closes)
            highs = [k['high'] for k in kls]
            lows = [k['low'] for k in kls]
            vols = [k.get('volume', k.get('vol', 0)) for k in kls]
            stage = get_stage(closes, structure, highs, lows, volumes=vols)

            # EMA
            ema5 = _ema_list(closes, 5)
            ema10 = _ema_list(closes, 10)
            ema20 = _ema_list(closes, 20)
            ema30 = _ema_list(closes, 30)

            cur_close = kls[-1]['close']
            cur_ema5 = ema5[-1] if ema5[-1] else 0
            deviation = (cur_close - cur_ema5) / cur_ema5 * 100 if cur_ema5 > 0 else 0

            is_watchlist = matched_code in wl_codes

            # 生成SVG图表（查看 review_charts/{code}.svg 是否存在，不存在则生成）
            svg_path = f'/review_charts/{matched_code}.svg'
            svg_abs = f'/home/ubuntu/www/review_charts/{matched_code}.svg'
            if not os.path.exists(svg_abs):
                try:
                    from a_stock_kline_keypoint_chart import gen_svg
                    from scripts.buy_point_detection import _find_support_levels
                    idx = find_idx(today_fmt, kls)
                    kps = []
                    if idx >= 10:
                        supports = _find_support_levels(kls, idx)
                        kps = [{'label': '突', 'y': s} for s in supports[-10:]]
                    gen_svg(matched_name, matched_code, kls, kps, svg_abs)
                except Exception:
                    pass  # SVG生成失败不影响页面

            # 量比分析
            vol_ratio = 0
            if len(kls) >= 5:
                recent_vols = [k.get('volume', k.get('vol', 0)) for k in kls[-5:]]
                vma5 = sum(recent_vols) / 5 if all(v > 0 for v in recent_vols) else 0
                cur_vol = kls[-1].get('volume', kls[-1].get('vol', 0))
                vol_ratio = round(cur_vol / vma5, 2) if vma5 > 0 else 0

            result = {
                'code': matched_code,
                'name': matched_name,
                'direction': matched_direction,
                'is_watchlist': is_watchlist,
                'price': round(cur_close, 2),
                'change': round((cur_close - kls[-2]['close']) / kls[-2]['close'] * 100, 2) if len(kls) >= 2 else 0,
                'date': today_fmt,
                'structure': structure,
                'stage': stage,
                'ema5': round(cur_ema5, 2) if cur_ema5 else None,
                'ema10': round(ema10[-1], 2) if ema10[-1] else None,
                'ema20': round(ema20[-1], 2) if ema20[-1] else None,
                'ema30': round(ema30[-1], 2) if ema30[-1] else None,
                'deviation_pct': round(deviation, 2),
                'vol_ratio': vol_ratio,
                'trend_stock': trend,
                'profit_model1': bool(pm1 and pm1['match']) if pm1 else False,
                'buy_point': bt.get('buy_type', '') if bt else '',
                'buy_score': bt.get('score', 0) if bt else 0,
                'buy_detail': bt.get('detail', {}) if bt else None,
                'huicai_detail': hc.get('detail', {}) if hc else None,
                'has_chart': os.path.exists(svg_abs),
                'signal': 'buy' if bt else ('hold' if structure == '上涨趋势' else 'warn'),
                # 止损位推荐
                'stop_loss': None,
                'stop_loss_pct': None,
                # 盈亏比
                'risk_reward_ratio': None,
                # 综合成功率
                'success_rate': None,
            }

            # 计算止损位+盈亏比+成功率（用最后一天索引）
            _last_idx = find_idx(today_fmt, kls)
            _bt_results_path = '/home/ubuntu/www/files/buy_signal_backtest_results.json'
            _bt_cache = None
            if os.path.exists(_bt_results_path):
                try:
                    with open(_bt_results_path) as _f:
                        _bt_cache = json.load(_f)
                except Exception:
                    pass

            if _last_idx >= 10:
                # 止损：支撑价下方2%
                _support = _find_support_levels(kls, _last_idx)
                if _support is not None:
                    _sl = round(_support * 0.98, 2)
                    result['stop_loss'] = _sl
                    result['stop_loss_pct'] = round((cur_close - _sl) / cur_close * 100, 2)
                    
                    # 盈亏比：找最近压力位（前高）
                    _highs = [k['high'] for k in kls[:_last_idx+1]]
                    _resistance = None
                    for _i in range(_last_idx, max(0, _last_idx-30), -1):
                        if _highs[_i] > cur_close * 1.02:  # 比当前高2%以上
                            _resistance = _highs[_i]
                            break
                    if _resistance and result['stop_loss']:
                        _risk = cur_close - result['stop_loss']
                        if _risk > 0:
                            _reward = _resistance - cur_close
                            result['risk_reward_ratio'] = round(_reward / _risk, 2)

                # 综合成功率
                _buy_type = bt.get('buy_type', '') if bt else ''
                if _buy_type and _bt_cache:
                    _bt_data = _bt_cache.get('by_type', {}).get(_buy_type, {})
                    _base_wr = _bt_data.get('win_rate', 50) / 100.0
                    
                    # 市场环境系数
                    _mkt_map = {'偏波峰': 0.85, '波中偏上': 0.92, '波中': 1.0,
                                '波中偏下': 1.08, '偏波谷': 1.15}
                    # 获取大盘位置（从review_data或默认）
                    _mkt_factor = 1.0
                    try:
                        _rd = get_review_archive(today_fmt)
                        if _rd and 'cycle' in _rd:
                            _pos = _rd['cycle'].get('position', '波中')
                            _mkt_factor = _mkt_map.get(_pos, 1.0)
                    except Exception:
                        pass
                    
                    # 结构系数
                    _struct_map = {'上涨趋势': 1.2, '区间震荡': 1.0, '下降趋势': 0.6}
                    _struct_factor = _struct_map.get(structure, 1.0)
                    
                    # 主线系数
                    _ml_factor = 1.15 if is_watchlist else 0.85
                    
                    _final = _base_wr * _mkt_factor * _struct_factor * _ml_factor
                    result['success_rate'] = round(min(_final * 100, 95), 1)

            self.send_json(result)
            return

        # --- 行业板块数据（同花顺原始数据，按天缓存） ---
        if path == '/api/industry-boards':
            cache_dir = os.path.join(WWW_DIR, 'data', 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f'industry_boards_{datetime.now().strftime("%Y-%m-%d")}.json')
            # 10分钟TTL缓存，确保今日涨幅实时更新
            if os.path.isfile(cache_file):
                mtime = os.path.getmtime(cache_file)
                if (datetime.now().timestamp() - mtime) < 600:  # 10分钟
                    self._serve_file(cache_file, 'application/json; charset=utf-8')
                    return
            import threading, akshare as ak
            result = []
            err = None
            def fetch():
                nonlocal result, err
                try:
                    df = ak.stock_board_industry_summary_ths()
                    result = df.fillna('').to_dict('records')
                except Exception as e:
                    err = str(e)
            t = threading.Thread(target=fetch)
            t.start()
            t.join(timeout=30)
            if err:
                return self.send_json({'error': err, 'data': []})
            # 写入缓存
            cache_data = {'data': result, 'count': len(result)}
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False)
            return self.send_json(cache_data)

        if path == '/api/concept-boards':
            import threading, akshare as ak
            result = []
            err = None
            def fetch():
                nonlocal result, err
                try:
                    df = ak.stock_board_concept_summary_ths()
                    result = df.fillna('').to_dict('records')
                except Exception as e:
                    err = str(e)
            t = threading.Thread(target=fetch)
            t.start()
            t.join(timeout=30)
            if err:
                return self.send_json({'error': err, 'data': []})
            return self.send_json({'data': result, 'count': len(result)})

        # --- 综合复盘数据生成API（必须放在 /api/review/{date} 前面） ---
        if path == '/api/review/generate':
            params = urllib.parse.parse_qs(self.path.split('?')[1] if '?' in self.path else '')
            date_arg = params.get('date', [None])[0]
            try:
                import subprocess
                cmd = [sys.executable, os.path.join(WWW_DIR, 'generate_review_data.py')]
                if date_arg:
                    cmd.append(date_arg)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    return self.send_json({'status': 'ok', 'output': result.stdout[-500:]})
                else:
                    return self.send_json({'status': 'error', 'output': result.stderr[-500:]})
            except Exception as e:
                return self.send_json({'status': 'error', 'msg': str(e)})

        # 复盘存档API
        if path.startswith('/api/review/'):
            parts = path.split('/')
            if len(parts) == 4 and parts[3] == 'dates':
                # GET /api/review/dates — 获取所有存档日期
                adir = os.path.join(WWW_DIR, 'private', 'review_archive')
                dates = []
                if os.path.isdir(adir):
                    for f in sorted(os.listdir(adir)):
                        if f.endswith('.json'):
                            dates.append(f[:-5])
                return self.send_json({'dates': dates})
            elif len(parts) == 4:
                # GET /api/review/YYYY-MM-DD — 获取某日复盘数据
                date_str = parts[3]
                fp = os.path.join(WWW_DIR, 'private', 'review_archive', f'{date_str}.json')
                if os.path.isfile(fp):
                    with open(fp, 'r') as f:
                        return self.send_json(json.load(f))
                return self.send_json({'error': 'not found'})


        # --- 个股回测API（支持代码/名称搜索） ---
        if path == '/api/stock-backtest':
            parsed = urllib.parse.urlparse(self.path)
            code_q = urllib.parse.parse_qs(parsed.query).get('code', [''])[0].strip()
            days = int(urllib.parse.parse_qs(parsed.query).get('days', ['60'])[0])
            if not code_q:
                self.send_json({'error': '请输入股票代码或名称'})
                return

            from scripts.data_layer import get_all_stocks
            from scripts.buy_point_detection import detect_buy_point, _resolve_code, find_idx, _volume_ratio, gen_trade_chart_svg, compute_trade_stats, simulate_trade
            from scripts.ema_utils import get_structure, get_stage

            stocks = get_all_stocks()

            # ----- 搜索股票（与 stock-analysis 相同逻辑，支持名称） -----
            matched_code = None
            matched_direction = None
            matched_name = None

            # 1. 精确code匹配
            for sec, ss in stocks.items():
                if code_q in ss:
                    matched_code, matched_direction = code_q, sec
                    matched_name = ss[code_q][0].get('name', code_q) if ss[code_q] else code_q
                    break
            if not matched_code:
                # 2. 模糊code匹配
                for sec, ss in stocks.items():
                    for code in ss:
                        if code_q in code or code.endswith(code_q):
                            matched_code, matched_direction = code, sec
                            matched_name = ss[code][0].get('name', code) if ss[code] else code
                            break
                    if matched_code:
                        break
            if not matched_code:
                # 3. 模糊名称匹配
                for sec, ss in stocks.items():
                    for code, kls in ss.items():
                        name = kls[0].get('name', '') if kls else ''
                        if code_q in name:
                            matched_code, matched_direction = code, sec
                            matched_name = name
                            break
                    if matched_code:
                        break

            if not matched_code:
                self.send_json({'error': f'未找到股票: {code_q}'})
                return

            resolved_code = matched_code
            stock_name = matched_name
            stock_direction = matched_direction
            kls = stocks[matched_direction][matched_code]
            sub = {stock_direction: {resolved_code: kls}}

            # 跑回测：每个K线节点检测买点，用真实3L退出规则
            signals = []
            start_idx = max(30, len(kls) - days)
            cum = 1.0
            i = start_idx
            while i < len(kls):
                d = str(kls[i]['date']).replace('-','')
                df = f"{d[:4]}-{d[4:6]}-{d[6:8]}"
                bt = detect_buy_point(resolved_code, df, sub, market_position='波中', main_lines={'半导体'})
                if bt:
                    entry = bt['close']
                    buy_type = bt['buy_type']
                    # 用真实3L退出规则模拟交易
                    trade = simulate_trade(kls, i, entry, buy_type, max_days=60)
                    if trade and trade['exit_idx'] is not None:
                        ei = trade['exit_idx']
                        exit_price = trade['exit_price']
                        gain = round((exit_price - entry) / entry * 100, 2)
                        cum *= (1 + gain/100)
                        signals.append({
                            'n': len(signals)+1,
                            'date': bt.get('date', df),
                            'type': buy_type,
                            'entry': entry,
                            'exit': exit_price if ei != i else None,
                            'exit_date': str(kls[ei]['date']).replace('-','')[:10] if ei != i else None,
                            'gain': gain,
                            'cum_gain': round((cum-1)*100, 2),
                            'days': trade['hold_days'],
                            'exit_reason': trade['exit_reason'],
                            'stop_triggered': trade['stop_triggered'],
                            'buy_back_price': trade.get('buy_back_price'),
                            'max_gain': trade.get('max_gain'),
                            'max_loss': trade.get('max_loss'),
                        })
                        # 跳到退出日之后，避免同区间重复信号
                        i = max(i + 1, ei + 1)
                        continue
                i += 1

            # 生成SVG图（使用共享函数）
            chart_path = f'/review_charts/bt_{resolved_code}.svg'
            chart_abs = f'/home/ubuntu/www/review_charts/bt_{resolved_code}.svg'
            has_chart = gen_trade_chart_svg(kls, signals, stock_name, resolved_code, chart_abs)

            stats = compute_trade_stats(signals)

            self.send_json({
                'code': resolved_code,
                'name': stock_name,
                'direction': stock_direction,
                'signals': signals,
                'chart_svg': f'/review_charts/bt_{resolved_code}.svg',
                'has_chart': has_chart,
                **stats,
            })
            return

        # --- 行业分类映射API ---
        if path == '/api/industry-map':
            fp = INDUSTRY_MAP_PATH
            if os.path.isfile(fp):
                self._serve_file(fp, 'application/json; charset=utf-8', no_cache=True)
            else:
                return self.send_json({'error': 'no data'})
            return

        # --- 最强动量数据API（涨停+创新高，subprocess方式避免HTTP阻塞，拉一次缓存全天） ---
        if path == '/api/momentum':
            cache_dir = os.path.join(WWW_DIR, 'data', 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            today_str = datetime.now().strftime('%Y-%m-%d')
            cache_file = os.path.join(cache_dir, f'momentum_{today_str}.json')
            
            # 检查今天的缓存
            if os.path.isfile(cache_file):
                self._serve_file(cache_file, 'application/json; charset=utf-8', no_cache=True)
                return
            
            # 无缓存，拉取新数据
            import subprocess
            try:
                r = subprocess.run(
                    [sys.executable, os.path.join(WWW_DIR, 'fetch_momentum.py')],
                    capture_output=True, text=True, timeout=90
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    # 保存到缓存
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)
                    return self.send_json(data)
                else:
                    return self.send_json({'error': r.stderr[-300:]})
            except Exception as e:
                return self.send_json({'error': str(e)})

        # ==================== 盯盘 API ====================
        if path == '/api/monitor/volume':
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import get_volume_comparison
            return self.send_json(get_volume_comparison())

        if path == '/api/monitor/buy-signals':
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import get_existing_holdings
            # 扫描算力+半导体方向的买点信号
            scan_file = os.path.join(WWW_DIR, 'scripts', 'scan_buy_signals.py')
            cache_dir = os.path.join(WWW_DIR, 'data', 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, f'buy_signals_{datetime.now().strftime("%Y-%m-%d_%H")}.json')
            # 如果1小时内已有缓存，直接返回
            if os.path.isfile(cache_file):
                self._serve_file(cache_file, 'application/json; charset=utf-8')
                return
            # 超过1小时重新扫描
            import subprocess
            try:
                r = subprocess.run(
                    [_sys.executable, scan_file],
                    capture_output=True, text=True, timeout=120
                )
                if r.returncode == 0:
                    data = json.loads(r.stdout)
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False)
                    return self.send_json(data)
                else:
                    return self.send_json({'error': r.stderr[-300:], 'signals': []})
            except Exception as e:
                return self.send_json({'error': str(e), 'signals': []})

        if path == '/api/monitor/stop-loss':
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import get_existing_holdings
            holdings = get_existing_holdings()
            # 获取当前行情检查是否触发止损
            triggered = []
            for h in holdings:
                code = h.get('code', '')
                sl = h.get('stop_loss', '')
                if not code or not sl:
                    continue
                try:
                    sl_price = float(sl.replace('元', '').strip())
                except:
                    continue
                # 取实时行情
                try:
                    r = requests.get(f'https://qt.gtimg.cn/q={code}',
                                     headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.qq.com'},
                                     timeout=5)
                    line = r.text.strip()
                    fields = line.split('"')[1].split('~') if '"' in line else []
                    cur_price = float(fields[3]) if len(fields) > 3 else 0
                except:
                    continue
                if cur_price > 0 and cur_price <= sl_price:
                    triggered.append({
                        'code': code,
                        'name': h.get('name', code),
                        'current_price': cur_price,
                        'stop_loss': sl_price,
                        'loss_pct': round((cur_price - sl_price) / sl_price * 100, 2),
                        'reason': h.get('buy_reason', ''),
                    })
            return self.send_json({'triggered': triggered, 'count': len(triggered)})

        if path == '/api/monitor/sectors':
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import get_top_sectors_with_5d
            sectors = get_top_sectors_with_5d()
            return self.send_json(sectors)

        if path == '/api/monitor/leaders':
            """行业龙头数据（实时行情更新chg和price）"""
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import _batch_tencent_quotes, _norm_code

            # 短缓存：2分钟
            _leaders_cache = getattr(self, '_leaders_cache_data', None)
            _leaders_time = getattr(self, '_leaders_cache_time', 0)
            now_ts = time.time()
            if _leaders_cache and (now_ts - _leaders_time) < 120:
                return self.send_json(_leaders_cache)

            try:
                with open(INDUSTRY_LEADERS_PATH, 'r') as f:
                    leaders = json.load(f)
            except:
                return self.send_json({'count': 0, 'by_industry': {}, 'error': '数据文件未找到'})

            # 收集所有股票代码（去重）
            code_set = set()
            for ind, stocks in leaders.get('by_industry', {}).items():
                for s in stocks:
                    qcode = _norm_code(s['code'])
                    code_set.add(qcode)
            codes_list = sorted(code_set)

            # 批量获取实时行情
            quotes = _batch_tencent_quotes(codes_list)

            # 用实时数据更新每个股票的chg和price
            for ind, stocks in leaders.get('by_industry', {}).items():
                for s in stocks:
                    qcode = _norm_code(s['code'])
                    q = quotes.get(qcode)
                    if q and q['price'] > 0:
                        chg = q['change_pct']
                        s['chg'] = f"{'+' if chg >= 0 else ''}{chg:.2f}%"
                        s['price'] = str(q['price'])

            self._leaders_cache_data = leaders
            self._leaders_cache_time = now_ts
            return self.send_json(leaders)

        if path == '/api/monitor/market-leaders':
            """市场龙头动态扫描"""
            import sys as _sys
            _sys.path.insert(0, os.path.join(WWW_DIR, 'scripts'))
            from monitor_data import get_market_leaders
            data = get_market_leaders()
            return self.send_json(data)

        if path.startswith('/api/sector-chart'):
            params = urllib.parse.parse_qs(self.path.split('?')[1] if '?' in self.path else '')
            name = params.get('name', [None])[0]
            if not name:
                return self.send_json({'error': 'missing name param'})
            
            # 检查缓存
            cache_dir = os.path.join(WWW_DIR, 'data', 'cache')
            os.makedirs(cache_dir, exist_ok=True)
            chart_file = os.path.join(WWW_DIR, 'review_charts', f'sector_{name}.svg')
            
            if not os.path.isfile(chart_file) or (datetime.now().timestamp() - os.path.getmtime(chart_file)) > 3600:
                # 生成板块关键点图
                try:
                    import akshare as ak
                    from datetime import timedelta
                    
                    # 获取60日K线
                    now = datetime.now()
                    start_d = now - timedelta(days=90)
                    start_date = start_d.strftime('%Y%m%d')
                    end_date = now.strftime('%Y%m%d')
                    df = ak.stock_board_industry_index_ths(symbol=name, start_date=start_date, end_date=end_date)
                    
                    if df is None or len(df) < 10:
                        return self.send_json({'error': 'insufficient data'})
                    
                    data = []
                    for _, row in df.iterrows():
                        data.append({
                            'day': str(row['日期']),
                            'open': float(row['开盘价']),
                            'high': float(row['最高价']),
                            'low': float(row['最低价']),
                            'close': float(row['收盘价']),
                            'volume': float(row['成交量']),
                        })
                    
                    # 关键点识别
                    closes = [k['close'] for k in data]
                    highs = [k['high'] for k in data]
                    lows = [k['low'] for k in data]
                    opens = [k['open'] for k in data]
                    volumes = [k['volume'] for k in data]
                    n = len(data)
                    kps = []
                    for i in range(5, n):
                        if highs[i] == max(highs[max(0,i-10):i+1]) and i > 0:
                            kps.append({'idx': i, 'type': 1, 'label': '前高', 'y': highs[i]})
                        if lows[i] == min(lows[max(0,i-10):i+1]) and i > 0:
                            kps.append({'idx': i, 'type': 1, 'label': '前低', 'y': lows[i]})
                        if i >= 10:
                            vw = volumes[i-10:i]
                            if len(vw) > 0 and max(vw) > 0:
                                if volumes[i] >= max(vw) * 1.5:
                                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
                                elif volumes[i] <= min(vw) * 0.5 and volumes[i] > 0:
                                    kps.append({'idx': i, 'type': 1, 'label': '量', 'y': highs[i] + (highs[i]-lows[i])*0.5})
                        if i >= 10:
                            ph = max(highs[i-10:i])
                            if closes[i] > ph and closes[i] > opens[i]:
                                kps.append({'idx': i, 'type': 2, 'label': '突', 'y': highs[i]})
                            if i >= 1 and closes[i] > opens[i] and closes[i-1] < opens[i-1] and closes[i] > opens[i-1] and opens[i] < closes[i-1]:
                                kps.append({'idx': i, 'type': 2, 'label': '反', 'y': lows[i]})
                    
                    # 生成SVG
                    W, H = 800, 400
                    pl, pr, pt, pb = 60, 20, 30, 55
                    mx, mn = max(highs[-60:]), min(lows[-60:])
                    rg = mx - mn if mx != mn else 1
                    nd = min(n, 60)
                    data_60 = data[-nd:]
                    cw = (W - pl - pr) / nd
                    bv = H - pb
                    
                    def px(i): return pl + i * cw + cw / 2
                    def py(v): return pt + (mx - v) / rg * (H - pt - pb)
                    
                    c60 = [k['close'] for k in data_60]
                    h60 = [k['high'] for k in data_60]
                    l60 = [k['low'] for k in data_60]
                    o60 = [k['open'] for k in data_60]
                    v60 = [k['volume'] for k in data_60]
                    vm = max(v60) if max(v60) > 0 else 1
                    
                    # 计算支撑线（突破点下方）和压力线（近15日最高）
                    cur_close = c60[-1]
                    bk_pts_chart = sorted([kp for kp in kps if kp['label'] == '突' and kp['y'] < cur_close and kp['idx'] >= n-nd],
                                          key=lambda x: x['y'], reverse=True)
                    nd15 = min(15, len(c60))
                    hi_15 = max(h60[-nd15:])
                    
                    def ema(d, p):
                        r = [None]*len(d); m = 2/(p+1)
                        for i in range(len(d)):
                            if i == 0: r[i] = d[i]
                            elif r[i-1] is not None: r[i] = (d[i]-r[i-1])*m+r[i-1]
                        return r
                    
                    e5 = ema(c60, 5)
                    e10 = ema(c60, 10)
                    e20 = ema(c60, 20)
                    
                    sv = []
                    sv.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
                    sv.append(f'<rect width="{W}" height="{H}" fill="#1a1a2e"/>')
                    sv.append(f'<text x="{W/2}" y="20" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#ffffff" font-weight="bold">{name} 关键点图</text>')
                    for i in range(6):
                        yv = mx - i * rg / 5
                        yp = py(yv)
                        sv.append(f'<line x1="{pl}" y1="{yp}" x2="{W-pr}" y2="{yp}" stroke="#2a2a4e" stroke-width="0.5"/>')
                        sv.append(f'<text x="{pl-5}" y="{yp+3}" text-anchor="end" font-family="sans-serif" font-size="8" fill="#666666">{yv:.1f}</text>')
                    sv.append(f'<line x1="{pl}" y1="{bv}" x2="{W-pr}" y2="{bv}" stroke="#2a2a4e" stroke-width="0.5"/>')
                    for i in range(nd):
                        x = px(i) - cw * 0.35
                        w = max(cw * 0.6, 1)
                        vh = v60[i] / vm * 40
                        is_up = c60[i] >= o60[i]
                        vc = '#ff4444' if is_up else '#44aa44'
                        sv.append(f'<rect x="{x}" y="{bv-vh}" width="{w}" height="{max(vh, 0.5)}" fill="{vc}" opacity="0.3"/>')
                    for ev, clr in [(e5, '#ffd700'), (e10, '#ff6b6b'), (e20, '#4ecdc4')]:
                        pts = []
                        for i in range(nd):
                            if ev[i] is not None:
                                pts.append(f'{px(i)},{py(ev[i])}')
                        if pts:
                            sv.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{clr}" stroke-width="0.8" opacity="0.7"/>')
                    for i in range(nd):
                        x = px(i)
                        w = max(cw * 0.5, 1)
                        hi, lo, op, cl = h60[i], l60[i], o60[i], c60[i]
                        yh, yl = py(hi), py(lo)
                        yo, yc = py(op), py(cl)
                        is_up = cl >= op
                        clr = '#ff4444' if is_up else '#44aa44'
                        sv.append(f'<line x1="{x}" y1="{yh}" x2="{x}" y2="{yl}" stroke="{clr}" stroke-width="0.5" opacity="0.6"/>')
                        bt, bb = min(yo, yc), max(yo, yc)
                        sv.append(f'<rect x="{x-w/2}" y="{bt}" width="{w}" height="{max(bb-bt, 0.5)}" fill="{clr}" opacity="0.8"/>')
                    sz = 4
                    for kp in kps:
                        if kp['idx'] < n - nd:
                            continue
                        ai = kp['idx'] - (n - nd)
                        xp = px(ai)
                        yp = py(kp['y'])
                        clr = '#ff9800' if kp['type'] == 1 else '#2196f3'
                        sv.append(f'<rect x="{xp-sz}" y="{yp-sz}" width="{sz*2}" height="{sz*2}" fill="{clr}" opacity="0.85"/>')
                        sv.append(f'<text x="{xp}" y="{yp-sz-2}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="{clr}">{kp["label"]}</text>')
                    # 支撑线（突破点）和压力线（前高）
                    if bk_pts_chart:
                        sy = py(bk_pts_chart[0]['y'])
                        sv.append(f'<line x1="{pl}" y1="{sy}" x2="{W-pr}" y2="{sy}" stroke="#4caf50" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>')
                        sv.append(f'<text x="{pl+4}" y="{sy-4}" font-family="sans-serif" font-size="9" fill="#4caf50" font-weight="bold">支撑 {bk_pts_chart[0]["y"]:.0f}</text>')
                    if hi_15:
                        ry = py(hi_15)
                        sv.append(f'<line x1="{pl}" y1="{ry}" x2="{W-pr}" y2="{ry}" stroke="#f44336" stroke-width="1.5" stroke-dasharray="6,3" opacity="0.7"/>')
                        sv.append(f'<text x="{pl+4}" y="{ry-4}" font-family="sans-serif" font-size="9" fill="#f44336" font-weight="bold">压力 {hi_15:.0f}</text>')
                    for i in range(0, nd, 6):
                        dt = data_60[i]['day']
                        xd = px(i)
                        sv.append(f'<text x="{xd}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-40,{xd},{bv+14})">{dt[5:7]}/{dt[8:10]}</text>')
                    ldi = data_60[-1]['day']
                    sv.append(f'<text x="{px(nd-1)}" y="{bv+14}" text-anchor="middle" font-family="sans-serif" font-size="8" fill="#666666" transform="rotate(-40,{px(nd-1)},{bv+14})">{ldi[5:7]}/{ldi[8:10]}</text>')
                    ly2 = bv + 8
                    for idx2, (clr2, lbl) in enumerate([('#ff9800','第1类'),('#2196f3','第2类'),('#ffd700','EMA5'),('#ff6b6b','EMA10'),('#4ecdc4','EMA20')]):
                        lx = 50 + idx2 * 130
                        sv.append(f'<rect x="{lx}" y="{ly2}" width="8" height="8" fill="{clr2}" opacity="0.8" rx="1"/>')
                        sv.append(f'<text x="{lx+11}" y="{ly2+7}" font-family="sans-serif" font-size="10" fill="#888888">{lbl}</text>')
                    sv.append('</svg>')
                    
                    os.makedirs(os.path.dirname(chart_file), exist_ok=True)
                    with open(chart_file, 'w') as f:
                        f.write('\n'.join(sv))
                    
                    # === 保存60日K线数据JSON（供区间位置判断复用） ===
                    kline_cache = os.path.join(WWW_DIR, 'review_charts', f'sector_{name}_kline.json')
                    kline_data = {
                        'closes': [round(x,2) for x in c60],
                        'highs': [round(x,2) for x in h60],
                        'lows': [round(x,2) for x in l60],
                        'volumes': [round(x,2) for x in v60],
                        'key_points': [
                            {'idx': k['idx']-(n-nd), 'type': k['type'], 'label': k['label'], 'y': k['y']}
                            for k in kps if k['idx'] >= n-nd
                        ],
                        'high_60': round(max(h60), 2),
                        'low_60': round(min(l60), 2),
                        'close_now': round(c60[-1], 2),
                    }
                    try:
                        with open(kline_cache, 'w') as f:
                            json.dump(kline_data, f, ensure_ascii=False)
                    except:
                        pass
                    
                    # === 形态法判断结构（使用近15日数据，与monitor_data一致） ===
                    c15 = c60[-15:] if len(c60) >= 15 else c60
                    e15 = ema(c15, 10)
                    up = sum(1 for i in range(1,len(e15)) if e15[i] > e15[i-1])
                    dn = sum(1 for i in range(1,len(e15)) if e15[i] < e15[i-1])
                    r = up / (up+dn)
                    if r >= 0.7:
                        structure = '📈 上涨趋势'
                    elif r <= 0.3:
                        structure = '📉 下降趋势'
                    else:
                        structure = '➡ 区间震荡'
                    
                    # === 线性回归检测加速/滞涨 ===
                    def reg_slope_y(y_list):
                        n = len(y_list)
                        xs = list(range(n))
                        mx = sum(xs)/n; my = sum(y_list)/n
                        num = sum((xs[i]-mx)*(y_list[i]-my) for i in range(n))
                        den = sum((xs[i]-mx)**2 for i in range(n))
                        return num/den if den else 0
                    
                    half = len(e15) // 2
                    s1 = reg_slope_y(e15[:half])
                    s2 = reg_slope_y(e15[half:])
                    
                    if structure == '📈 上涨趋势':
                        if s1 > 0 and s2 > 0:
                            ratio = s2 / s1 if s1 != 0 else 999
                            if ratio > 1.8: phase = '🚀 加速'
                            elif ratio < 0.4: phase = '⚠️ 滞涨'
                            else: phase = '↑ 上行'
                        elif s1 > 0 and s2 <= 0:
                            phase = '🔻 转跌'
                        elif s1 <= 0 and s2 > 0:
                            phase = '🟢 转涨'
                        else:
                            phase = ''
                    elif structure == '📉 下降趋势':
                        if s1 <= 0 and s2 <= 0:
                            ratio = s2 / s1 if s1 != 0 else 0
                            if ratio > 1.8: phase = '📉 加速跌'
                            else: phase = '↓ 下行'
                        elif s1 <= 0 and s2 > 0:
                            phase = '🟢 转涨'
                        else:
                            phase = ''
                    else:  # 区间震荡 — 用关键点定支撑/压力：支撑=突破点，压力=前高
                        if os.path.isfile(kline_cache):
                            try:
                                with open(kline_cache) as f:
                                    kd = json.load(f)
                                c60 = kd.get('closes', [])
                                h60 = kd.get('highs', [])
                                l60 = kd.get('lows', [])
                                kps = kd.get('key_points', [])
                                cur = c60[-1] if c60 else 0
                                
                                # 支撑线 = 最近的突破点（下方）
                                bk_pts = sorted([kp for kp in kps if kp['label'] == '突' and kp['y'] < cur],
                                                key=lambda x: x['y'], reverse=True)
                                # 压力线 = 近15日最高价
                                nd15 = min(15, len(c60))
                                hi_15 = max(h60[-nd15:])
                                
                                # 取最近20日高低点作为备用边界
                                n20 = min(20, len(c60))
                                hi_fallback = max(h60[-n20:]) if len(h60) >= n20 else max(h60)
                                lo_fallback = min(l60[-n20:]) if len(l60) >= n20 else min(l60)
                                
                                hi = hi_15 if hi_15 else hi_fallback
                                lo = bk_pts[0]['y'] if bk_pts else lo_fallback
                                
                                if hi and lo and hi != lo:
                                    pct = (cur - lo) / (hi - lo) * 100
                                    if pct < 30: phase = '区间底部'
                                    elif pct > 70: phase = '区间顶部'
                                    else: phase = '区间中段'
                                else:
                                    phase = ''
                            except:
                                phase = ''
                        else:
                            phase = ''
                    
                    # 写入结构缓存
                    struct_cache = os.path.join(CACHE_DIR, 'sector_structure.json')
                    struct_data = {}
                    if os.path.isfile(struct_cache):
                        try:
                            with open(struct_cache) as f:
                                struct_data = json.load(f)
                        except:
                            pass
                    struct_data[name] = {'structure': structure, 'phase': phase, 'updated': str(datetime.now())}
                    try:
                        with open(struct_cache, 'w') as f:
                            json.dump(struct_data, f, ensure_ascii=False)
                    except:
                        pass
                except Exception as e:
                    return self.send_json({'error': str(e)})
            
            self._serve_file(chart_file, 'image/svg+xml')
            return

        # --- 交易技巧API ---
        if path == '/api/tips':
            tips_dir = '/home/ubuntu/data/3l/knowledge_base/trading_tips'
            tips = []
            if os.path.isdir(tips_dir):
                for f in sorted(os.listdir(tips_dir)):
                    if not f.endswith('.md'):
                        continue
                    fp = os.path.join(tips_dir, f)
                    title = f.replace('.md', '')
                    desc = ''
                    try:
                        with open(fp, 'r', encoding='utf-8') as fh:
                            content = fh.read()
                            title_m = __import__('re').search(r'^# (.+)$', content, __import__('re').MULTILINE)
                            if title_m: title = title_m.group(1)
                            desc_m = __import__('re').search(r'^> (.+)$', content, __import__('re').MULTILINE)
                            if desc_m: desc = desc_m.group(1)
                            if not desc:
                                # 取前150字非空内容
                                clean = __import__('re').sub(r'[#>\-\*\n\r]', '', content)[:150].strip()
                                desc = clean[:120] + '...' if len(clean) > 120 else clean
                            date_m = __import__('re').search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                            date_added = date_m.group(1) if date_m else ''
                    except: pass
                    tips.append({
                        'id': f.replace('.md', ''),
                        'title': title,
                        'desc': desc,
                        'file': f,
                        'is_journal': f == '交易日志的重要性.md',
                        'date_added': date_added
                    })
            return self.send_json({'tips': tips})

        if path == '/api/tips/journal-entries':
            jf = os.path.join(WWW_DIR, 'private', 'journal_entries.json')
            if os.path.isfile(jf):
                with open(jf, 'r', encoding='utf-8') as f:
                    return self.send_json(json.load(f))
            return self.send_json({'entries': []})

        if path == '/api/tips/content':
            parsed = urllib.parse.urlparse(self.path)
            file_name = urllib.parse.parse_qs(parsed.query).get('file', [''])[0]
            if not file_name:
                return self.send_json({'error': 'missing file param'})
            fp = '/home/ubuntu/data/3l/knowledge_base/trading_tips/' + file_name
            if not os.path.isfile(fp):
                return self.send_json({'error': 'file not found'})
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.send_json({'title': file_name.replace('.md',''), 'content': content})

        # --- 通用知识库 API ---
        if path == '/api/kb/list':
            kb_type = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get('type', [''])[0]
            kb_map = {'tips': 'trading_tips', 'industry': 'industry_tracking'}
            subdir = kb_map.get(kb_type, '')
            if not subdir:
                return self.send_json({'error': 'invalid type', 'items': []})
            kb_dir = '/home/ubuntu/data/3l/knowledge_base/' + subdir
            items = []
            if os.path.isdir(kb_dir):
                if kb_type == 'tips':
                    # flat: read .md files directly
                    for f in sorted(os.listdir(kb_dir)):
                        if not f.endswith('.md'): continue
                        fp = os.path.join(kb_dir, f)
                        title = f.replace('.md', '')
                        desc = ''
                        try:
                            with open(fp, 'r', encoding='utf-8') as fh:
                                content = fh.read()
                                title_m = __import__('re').search(r'^# (.+)$', content, __import__('re').MULTILINE)
                                if title_m: title = title_m.group(1)
                                desc_m = __import__('re').search(r'^> (.+)$', content, __import__('re').MULTILINE)
                                if desc_m: desc = desc_m.group(1)
                                if not desc:
                                    clean = __import__('re').sub(r'[#>\\-\\*\\n\\r]', '', content)[:150].strip()
                                    desc = clean[:120] + '...' if len(clean) > 120 else clean
                                date_m = __import__('re').search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                                if date_m: date_added = date_m.group(1)
                        except:
                            pass
                        # Extract date from content or use variable
                        date_added = ''
                        items.append({'id': f.replace('.md', ''), 'title': title, 'desc': desc, 'file': f, 'category': 'tips', 'date_added': date_added})
                else:
                    # industry: read subdirectories (公司/行业/研报)
                    cat_order = ['公司', '行业', '研报']
                    for cat in cat_order:
                        cat_dir = os.path.join(kb_dir, cat)
                        if not os.path.isdir(cat_dir): continue
                        cat_label = cat  # '公司', '行业', '研报'
                        for f in sorted(os.listdir(cat_dir)):
                            if not f.endswith('.md'): continue
                            fp = os.path.join(cat_dir, f)
                            title = f.replace('.md', '')
                            desc = ''
                            try:
                                with open(fp, 'r', encoding='utf-8') as fh:
                                    content = fh.read()
                                    title_m = __import__('re').search(r'^# (.+)$', content, __import__('re').MULTILINE)
                                    if title_m: title = title_m.group(1)
                                    desc_m = __import__('re').search(r'^> (.+)$', content, __import__('re').MULTILINE)
                                    if desc_m: desc = desc_m.group(1)
                                    if not desc:
                                        clean = __import__('re').sub(r'[#>\-\*\n\r]', '', content)[:150].strip()
                                        desc = clean[:120] + '...' if len(clean) > 120 else clean
                                    date_m = __import__('re').search(r'收录日期[：:]\s*(\d{4}-\d{2}-\d{2})', content)
                                    date_added = date_m.group(1) if date_m else ''
                            except: pass
                            items.append({
                                'id': f.replace('.md', ''),
                                'title': title, 'desc': desc,
                                'file': f'{cat}/{f}',
                                'category': cat_label,
                                'date_added': date_added
                            })
            return self.send_json({'items': items})

        if path == '/api/kb/content':
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            file_name = params.get('file', [''])[0]
            kb_type = params.get('type', ['tips'])[0]
            kb_map = {'tips': 'trading_tips', 'industry': 'industry_tracking'}
            subdir = kb_map.get(kb_type, 'trading_tips')
            if not file_name: return self.send_json({'error': 'missing file param'})
            fp = '/home/ubuntu/data/3l/knowledge_base/' + subdir + '/' + file_name
            if not os.path.isfile(fp): return self.send_json({'error': 'file not found'})
            with open(fp, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.send_json({'title': file_name.replace('.md', ''), 'content': content})

        if path in ('/review', '/review.html'):
            self.path = '/review.html'
        elif path in ('/monitor', '/monitor.html'):
            self.path = '/monitor.html'
        elif path in ('/', ''):
            self.path = '/index.html'

        # Serve HTML files with no-cache
        if self.path.endswith('.html'):
            fp = os.path.join(WWW_DIR, self.path.lstrip('/'))
            if os.path.isfile(fp):
                ct, _ = mimetypes.guess_type(fp)
                self._serve_file(fp, ct, no_cache=True)
                return

        super().do_GET()

    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(cl).decode() if cl > 0 else '{}'
        if self.path == '/api/review/save':
            try:
                data = json.loads(body)
                date = data.get('date', '')
                if date:
                    # 保存到 data/review_archive（新格式目录）
                    adir = os.path.join(WWW_DIR, 'data', 'review_archive')
                    os.makedirs(adir, exist_ok=True)
                    fp = os.path.join(adir, f'{date}.json')
                    with open(fp, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    # 也复制一份到private兼容旧版
                    pdir = os.path.join(WWW_DIR, 'private', 'review_archive')
                    os.makedirs(pdir, exist_ok=True)
                    pf = os.path.join(pdir, f'{date}.json')
                    with open(pf, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self.send_json({'status': 'ok'})
                else:
                    self.send_json({'status': 'error', 'msg': 'missing date'})
            except Exception as e:
                self.send_json({'status': 'error', 'msg': str(e)})
            return
        if self.path == '/api/tips/save-journal':
            try:
                entry = json.loads(body)
                jf = os.path.join(WWW_DIR, 'private', 'journal_entries.json')
                entries = {'entries': []}
                if os.path.isfile(jf):
                    with open(jf, 'r', encoding='utf-8') as f:
                        entries = json.load(f)
                entry['id'] = entry.get('date', datetime.now().strftime('%Y%m%d')) + '_' + str(len(entries['entries']))
                entry['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                entries['entries'].insert(0, entry)
                with open(jf, 'w', encoding='utf-8') as f:
                    json.dump(entries, f, ensure_ascii=False, indent=2)
                self.send_json({'status': 'ok', 'id': entry['id']})
            except Exception as e:
                self.send_json({'status': 'error', 'msg': str(e)})
            return
        if self.path == '/api/update':
            try:
                data = json.loads(body)
                for k in ('market', 'mainlines', 'stocks'):
                    if k in data: REVIEW_DATA[k] = data[k]
                save_review_data()
                self.send_json({'status': 'ok'})
            except Exception as e:
                self.send_json({'status': 'error', 'message': str(e)}, 400)
        else:
            self.send_json({'status': 'error'}, 404)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, fmt, *args):
        print(f'[WEB] {self.client_address[0]} - {fmt % args}')

def main():
    load_review_data()
    os.chdir(WWW_DIR)
    server = ThreadingHTTPServer(('0.0.0.0', PORT), Handler)
    print(f'\n  Server: http://localhost:{PORT}')
    print(f'  Private: /private/ (auth required)\n')
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__ == '__main__':
    main()
