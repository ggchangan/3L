#!/usr/bin/env python3
"""
3L Daily Achievements Web Server + Review API
"""
import os, json, signal, sys, mimetypes, urllib.parse, time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from http.server import ThreadingHTTPServer
from urllib.parse import quote
from backend import config
from backend.services.logger import get_logger

log = get_logger('server')

PORT = config.SERVER_PORT
WWW_DIR = config.WWW_DIR

# 前端构建输出目录（结构对齐原生开发：WWW_DIR/server/frontend/dist）
FE_DIR = os.path.join(WWW_DIR, 'server', 'frontend', 'dist')
if not os.path.isdir(FE_DIR):
    FE_DIR = WWW_DIR

REVIEW_DATA = {}
DATA_FILE = config.REVIEW_DATA_PATH


class RouteRegistry:
    """注册式路由表：路径模式 → 处理器
    支持三种模式:
      - 'data': 直接返回数据对象
      - 'method': 调用 Handler 类的方法
      - 'func': 调用函数 (handler_self, path) → json
    """
    def __init__(self):
        self._exact = {}   # path -> (kind, value)

    def exact(self, path, handler=None, data=None, func=None):
        if handler:
            self._exact[path] = ('method', handler)
        elif data is not None:
            self._exact[path] = ('data', data)
        elif func:
            self._exact[path] = ('func', func)
        return self

    def dispatch(self, handler_self, path):
        if path in self._exact:
            kind, value = self._exact[path]
            if kind == 'data':
                handler_self.send_json(value)
                return True
            elif kind == 'func':
                value(handler_self, handler_self.path)
                return True
            elif kind == 'method':
                getattr(handler_self, value)()
                return True
        return False


ROUTES = RouteRegistry()

# ══════════════════════════════════════════════════
# API 路由注册（从 backend/api/ 模块加载）
# ══════════════════════════════════════════════════

def register_api_routes(routes):
    """注册所有 API 路由模块"""
    import importlib
    api_modules = [
        'backend.api.market', 'backend.api.review',
        'backend.api.monitor', 'backend.api.watchlist',
        'backend.api.stock', 'backend.api.industry',
        'backend.api.trend', 'backend.api.tips',
        'backend.api.holdings', 'backend.api.system',
        'backend.api.top_gainers', 'backend.api.macro',
        'backend.api.directions', 'backend.api.workbench',
        'backend.api.alarms',
        'backend.api.wxpush',
        'backend.api.logic_tracking',
        'backend.api.plan_tracking',
        'backend.api.market_health',
        'backend.api.concept_wave',
        'backend.api.strong_trend',
    ]
    for mod_name in api_modules:
        mod = importlib.import_module(mod_name)
        mod.register_routes(routes)

register_api_routes(ROUTES)

# 外围美股映射数据
import json
EXTERNAL_MAPPING_PATH = os.path.join(config.DATA_DIR, 'public', 'external_mapping.json')
if os.path.isfile(EXTERNAL_MAPPING_PATH):
    try:
        with open(EXTERNAL_MAPPING_PATH) as f:
            ROUTES.exact('/api/external-mapping', data=json.load(f))
    except Exception:
        pass

def load_review_data():
    global REVIEW_DATA
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: 
                loaded = json.load(f)
                REVIEW_DATA.clear()
                REVIEW_DATA.update(loaded)
            log.info(f'load_review: loaded from %s, keys=%s, size=%d', DATA_FILE, list(REVIEW_DATA.keys())[:5], len(REVIEW_DATA))
            return
        except Exception as e:
            log.error('加载复盘缓存失败: %s', e)
def save_review_data():
    global REVIEW_DATA
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    config.atomic_json_dump(REVIEW_DATA, DATA_FILE, indent=2)

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FE_DIR, **kwargs)

    def handle_market(self):
        self.send_json(REVIEW_DATA.get('market', {}))

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

        # --- Download endpoint (force attachment) ---
        if path.startswith('/download/'):
            rel = os.path.basename(urllib.parse.unquote(path[len('/download/'):]))
            fp = os.path.join(WWW_DIR, 'files', rel)
            if not os.path.isfile(fp):
                self.send_error(404)
                return
            self._serve_file(fp, as_attachment=True)
            return

        # --- API 路由表分发 ---
        if ROUTES.dispatch(self, path):
            return

        # --- 旧 .html 路由（302 跳转到短路径） ---
        html_redirects = {
            '/monitor.html': '/monitor', '/review.html': '/review',
            '/stock_analysis.html': '/stock_analysis',
            '/holdings.html': '/holdings', '/industry.html': '/industry',
            '/macro.html': '/macro', '/top_gainers.html': '/top_gainers',
            '/tips.html': '/tips', '/simulation.html': '/simulation',
            '/skills.html': '/skills', '/journal.html': '/workbench',
            '/watchlist.html': '/watchlist',
            '/trend_candidates.html': '/trend_candidates',
            '/workbench.html': '/workbench',
            '/plan-tracking.html': '/plan-tracking',
        }
        if path in html_redirects:
            self.send_response(302)
            self.send_header('Location', html_redirects[path])
            self.end_headers()
            return

        # --- SPA 内部别名（直接返回 react.html，让 BrowserRouter 处理路由）---
        spa_routes = {
            '/monitor', '/review', '/stock_analysis',
            '/holdings', '/industry', '/macro',
            '/top_gainers', '/tips', '/simulation',
            '/skills', '/journal', '/workbench',
            '/watchlist', '/trend_candidates',
            '/logic-tracking', '/alarm-sounds',
            '/plan-tracking',
            '/concept-wave',
            '/strong-trend-candidates',
        }
        if path in spa_routes:
            self.path = '/react.html'
            path = self.path

        # --- 首页别名 ---
        if path == '/':
            self.path = '/react.html'
            path = self.path

        # --- 静态文件（HTML/JS 不缓存）---
        if path.endswith('.sh') or path.endswith('.html') or path.endswith('.js'):
            # 优先 FE_DIR（构建输出），不存在则回退 WWW_DIR（项目根）
            fp = os.path.join(FE_DIR, path.lstrip('/'))
            if not os.path.isfile(fp) and FE_DIR != WWW_DIR:
                fp = os.path.join(WWW_DIR, path.lstrip('/'))
            if os.path.isfile(fp):
                ct, _ = mimetypes.guess_type(fp)
                self._serve_file(fp, ct, no_cache=True)
                return

        # --- 后端生成的公开文件（/pub/ → data/public/）---
        if path.startswith('/pub/'):
            rel = urllib.parse.unquote(path[len('/pub/'):]).lstrip('/')
            fp = os.path.join(config.PUBLIC_DIR, rel)
            if os.path.isdir(fp):
                # 目录 → 返回 JSON 文件列表
                try:
                    files = sorted(f for f in os.listdir(fp) if not f.startswith('.'))
                    self.send_json({'files': files})
                except Exception as e:
                    self.send_json({'files': [], 'error': str(e)})
                return
            if os.path.isfile(fp):
                ct, _ = mimetypes.guess_type(fp)
                self._serve_file(fp, ct)
                return
            self.send_error(404)
            return

        super().do_GET()

    def do_POST(self):
        cl = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(cl).decode() if cl > 0 else '{}'
        import importlib
        post_routes = {
            '/api/review/save': ('backend.api.review', '_handle_review_save'),
            '/api/watchlist/save': ('backend.api.watchlist', '_handle_watchlist_save'),
            '/api/watchlist/add-stock': ('backend.api.watchlist', '_handle_watchlist_add_stock'),
            '/api/tips/save-journal': ('backend.api.tips', '_handle_save_journal'),
            '/api/update': ('backend.api.system', '_handle_update'),
            # 方向管理（独立模块）
            '/api/directions/add': ('backend.api.directions', '_handle_add'),
            '/api/directions/remove': ('backend.api.directions', '_handle_remove'),
            '/api/directions/toggle': ('backend.api.directions', '_handle_set_active'),
            '/api/directions/reorder': ('backend.api.directions', '_handle_reorder'),
            '/api/workbench/save': ('backend.api.workbench', '_handle_save'),
            '/api/alarms/remove': ('backend.api.alarms', '_handle_remove'),
            '/api/alarms/dismiss': ('backend.api.alarms', '_handle_dismiss'),
            '/api/alarms/reenable': ('backend.api.alarms', '_handle_reenable'),
            '/api/monitor/add-watched-industry': ('backend.api.monitor', '_handle_add_watched'),
            '/api/monitor/remove-watched-industry': ('backend.api.monitor', '_handle_remove_watched'),
            '/api/alarm-sounds/upload': ('backend.api.alarms', '_handle_upload'),
            '/api/holdings/save': ('backend.api.holdings', '_handle_save'),
            '/api/logic-tracking/tags/add': ('backend.api.logic_tracking', '_handle_add_tag'),
            '/api/logic-tracking/tags/update': ('backend.api.logic_tracking', '_handle_update_tag'),
            '/api/logic-tracking/tags/delete': ('backend.api.logic_tracking', '_handle_delete_tag'),
            '/api/logic-tracking/entries/add': ('backend.api.logic_tracking', '_handle_add_entry'),
            '/api/logic-tracking/entries/delete': ('backend.api.logic_tracking', '_handle_delete_entry'),
            '/api/logic-tracking/forecasts/add': ('backend.api.logic_tracking', '_handle_add_forecast'),
            '/api/logic-tracking/forecasts/delete': ('backend.api.logic_tracking', '_handle_delete_forecast'),
            '/api/logic-tracking/feed/process': ('backend.api.logic_tracking', '_handle_feed_process'),
            '/api/logic-tracking/feed/save': ('backend.api.logic_tracking', '_handle_feed_save'),
            '/api/logic-tracking/verify/run': ('backend.api.logic_tracking', '_handle_trigger_verify'),
            '/api/wxpush/config': ('backend.api.wxpush', '_handle_config'),
            '/api/plan-tracking/annotate': ('backend.api.plan_tracking', '_handle_annotate'),
            '/api/plan-tracking/refresh': ('backend.api.plan_tracking', '_handle_refresh'),
        }
        if self.path in post_routes:
            mod_name, func_name = post_routes[self.path]
            mod = importlib.import_module(mod_name)
            getattr(mod, func_name)(self, self.path, body)
        else:
            self.send_json({'status': 'error'}, 404)

    def send_json(self, data, status=200):
        # 递归将 NaN 转为 None（兼容 JSON 规范）
        def _clean(obj):
            if isinstance(obj, float):
                return None if obj != obj else obj  # NaN != NaN
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [_clean(v) for v in obj]
            return obj
        body = json.dumps(_clean(data), ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        # 仅允许同源跨域（检查请求 Origin 是否匹配服务器地址）
        origin = self.headers.get('Origin', '')
        if origin and ('127.0.0.1' in origin or 'localhost' in origin or origin.startswith('http://43.136.177.133')):
            self.send_header('Access-Control-Allow-Origin', origin)
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, fmt, *args):
        log.info('%s - %s', self.client_address[0], fmt % args)
    def log_error(self, fmt, *args):
        log.error('%s - %s', self.client_address[0], fmt % args)


def main():
    # 支持 --host 参数（Docker 环境需要 0.0.0.0）
    import argparse
    parser = argparse.ArgumentParser(description='3L 交易系统服务')
    parser.add_argument('--host', default=config.SERVER_HOST, help='绑定地址（默认 %(default)s）')
    args = parser.parse_args()
    host = args.host

    load_review_data()
    config.cleanup_cache()  # 启动时清理过期缓存

    # 启动后端独立报警检测线程（30秒间隔，浏览器关闭时仍可推微信）
    try:
        from backend.services.check_alerts import start_alert_checker
        start_alert_checker(interval=30)
        log.info('报警检测线程已启动（30秒间隔）')
    except Exception:
        log.warning('报警检测线程启动失败', exc_info=True)

    os.chdir(FE_DIR)
    server = ThreadingHTTPServer((host, PORT), Handler)
    log.info('服务启动 http://%s:%d', host, PORT)
    signal.signal(signal.SIGTERM, lambda s, f: (log.info('收到SIGTERM'), sys.exit(0)))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info('收到 KeyboardInterrupt，关闭服务')
        server.server_close()

if __name__ == '__main__':
    main()
