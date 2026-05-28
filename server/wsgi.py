"""
Gunicorn WSGI 入口。
用法: gunicorn -w 4 -b 0.0.0.0:8080 wsgi:app
"""
from server import Handler
from backend.services.logger import setup_logging

# Gunicorn 的 WSGI 应用
# 需要一个 callable: environ, start_response -> iterable
# 这里用 server.Handler 不兼容 WSGI，所以封装 web.py
 
# 实际部署仍通过 server.py 的 main() 启动
# 此文件为未来 WSGI 迁移预留

def app(environ, start_response):
    """WSGI application placeholder"""
    from server import REVIEW_DATA
    if environ['PATH_INFO'] == '/api/health':
        data = b'{"status":"ok","service":"3l-server","version":"3.0.0"}'
        start_response('200 OK', [('Content-Type', 'application/json')])
        return [data]
    start_response('404 Not Found', [('Content-Type', 'text/plain')])
    return [b'Not Found']
