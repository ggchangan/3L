"""API 路由模块共享工具"""
import urllib.parse
import sys


def parse_query(path):
    """从完整路径中解析 query string"""
    qs = urllib.parse.urlparse(path).query
    return urllib.parse.parse_qs(qs)


def get_server():
    """获取主 server 模块（python server.py 启动时注册为 __main__）"""
    mod = sys.modules.get('__main__')
    if mod is None:
        raise RuntimeError('__main__ module not found')
    return mod
