#!/usr/bin/env python3
"""
3L Daily Achievements Web Server + Review API
"""
import os, json, signal, sys, base64, mimetypes, urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote

PORT = 8080
WWW_DIR = '/home/ubuntu/www'
AUTH_USER = 'ggchangan'
AUTH_PASS = '19891121'
PROTECTED_PREFIX = '/private/'

REVIEW_DATA = {}
DATA_FILE = os.path.join(WWW_DIR, 'private', 'review_data.json')

def load_review_data():
    global REVIEW_DATA
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE) as f: REVIEW_DATA = json.load(f)
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
                self._serve_file(fp, 'application/json; charset=utf-8')
            else:
                self.send_json({'error': 'no data'})
            return

        if path == '/api/market':
            return self.send_json(REVIEW_DATA.get('market', {}))
        if path == '/api/mainlines':
            return self.send_json(REVIEW_DATA.get('mainlines', {}))
        if path == '/api/stocks':
            return self.send_json(REVIEW_DATA.get('stocks', {}))
        if path == '/api/review':
            return self.send_json(REVIEW_DATA)

        # --- 行业板块数据（同花顺原始数据） ---
        if path == '/api/industry-boards':
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
            return self.send_json({'data': result, 'count': len(result)})

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

        if path in ('/review', '/review.html'):
            self.path = '/review.html'
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
                    adir = os.path.join(WWW_DIR, 'private', 'review_archive')
                    os.makedirs(adir, exist_ok=True)
                    fp = os.path.join(adir, f'{date}.json')
                    with open(fp, 'w', encoding='utf-8') as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    self.send_json({'status': 'ok'})
                else:
                    self.send_json({'status': 'error', 'msg': 'missing date'})
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
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()

    def log_message(self, fmt, *args):
        print(f'[WEB] {self.client_address[0]} - {fmt % args}')

def main():
    load_review_data()
    os.chdir(WWW_DIR)
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    print(f'\n  Server: http://localhost:{PORT}')
    print(f'  Private: /private/ (auth required)\n')
    signal.signal(signal.SIGTERM, lambda s,f: sys.exit(0))
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__ == '__main__':
    main()
