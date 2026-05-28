#!/usr/bin/env python3
"""3L-analysis — 独立个股分析服务"""
import os, json, sys, signal, mimetypes, urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

# 确保 threel_core 可导入
os.environ.setdefault('DATA_DIR', '/home/ubuntu/data/3l')

PORT = int(os.environ.get('PORT', '9090'))
FE_DIR = os.path.join(os.path.dirname(__file__), 'frontend')

# ── API 处理器 ──

def handle_analysis(query):
    """处理个股分析请求"""
    from threel_analysis.analysis import search_and_analyze
    return search_and_analyze(query)


# ── HTTP 服务器 ──

class AnalysisHandler(SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        params = urllib.parse.parse_qs(parsed.query)

        # API 路由
        if path == '/api/stock-analysis':
            q = params.get('q', [''])[0].strip()
            if not q:
                self.send_json({'error': '请输入股票代码或名称'})
                return
            result = handle_analysis(q)
            self.send_json(result)
            return

        # 前端页面 — 根路径 / 或 /stock_analysis 或 /stock-analysis 返回前端页面
        if path == '/' or path == '/stock_analysis' or path == '/stock_analysis.html' or path == '/stock-analysis' or path == '/stock-analysis.html':
            self.serve_frontend('index.html')
            return

        # 静态文件
        self.serve_static(path)

    def send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_frontend(self, filename):
        path = os.path.join(FE_DIR, filename)
        if not os.path.isfile(path):
            self.send_error(404, 'Not Found')
            return
        ctype = self.guess_type(path)
        body = open(path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def serve_static(self, path):
        # 去掉前导 /
        rel = path.lstrip('/')
        full = os.path.join(FE_DIR, rel)
        if not os.path.isfile(full):
            self.send_error(404, 'Not Found')
            return
        ctype = self.guess_type(full)
        body = open(full, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    server = HTTPServer(('0.0.0.0', PORT), AnalysisHandler)
    print(f'3L-analysis 服务启动 → http://0.0.0.0:{PORT}')
    print(f'  数据分析: http://localhost:{PORT}/stock_analysis')

    def shutdown(sig, frame):
        print('\n关闭服务...')
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    server.serve_forever()


if __name__ == '__main__':
    main()
