#!/usr/bin/env python3
"""
管理每日成果Web服务器
用法:
  python3 manage.py start   启动服务器
  python3 manage.py stop    停止服务器
  python3 manage.py restart 重启服务器
  python3 manage.py status  查看状态
"""
import os
import sys
import signal
import subprocess

PID_FILE = '/home/ubuntu/www/server.pid'
WWW_DIR = '/home/ubuntu/www'
PORT = 8080


def get_pid():
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            return int(f.read().strip())
    return None


def is_running(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start():
    pid = get_pid()
    if pid and is_running(pid):
        print(f'Server already running (PID {pid})')
        return

    proc = subprocess.Popen(
        ['python3', 'server.py'],
        cwd=WWW_DIR,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    with open(PID_FILE, 'w') as f:
        f.write(str(proc.pid))
    print(f'Server started (PID {proc.pid})')
    print(f'Access: http://43.136.177.133:{PORT}')


def stop():
    pid = get_pid()
    if not pid:
        print('Not running')
        return
    if is_running(pid):
        os.kill(pid, signal.SIGTERM)
        print(f'Server stopped (PID {pid})')
    if os.path.exists(PID_FILE):
        os.remove(PID_FILE)


def restart():
    stop()
    start()


def status():
    pid = get_pid()
    if pid and is_running(pid):
        print(f'Server RUNNING (PID {pid})')
        print(f'URL: http://43.136.177.133:{PORT}')
        files = os.listdir(os.path.join(WWW_DIR, 'files'))
        print(f'Files: {len(files)} PDFs')
    else:
        print('Server STOPPED')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    globals()[cmd]()
