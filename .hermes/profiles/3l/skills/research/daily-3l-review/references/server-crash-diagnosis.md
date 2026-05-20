# server.py SYN Flood 崩溃诊断

## 现象

2026-05-21 用户反馈复盘页面无法访问。排查发现：

1. `ss -tlnp | grep 8080` → 无输出（端口未监听）
2. `ps aux | grep server.py` → 无进程
3. 内核日志：`dmesg -T | grep '8080'`
   ```
   May 20 19:04:38 kernel: TCP: request_sock_TCP: Possible SYN flooding on port 0.0.0.0:8080. Sending cookies.
   ```

## 根因

`server.py` 使用 `ThreadingHTTPServer`（import from `http.server`），每个HTTP请求创建一个新线程。当遭遇SYN flood（大量TCP连接请求）时：

1. 内核触发SYN cookie保护（防止被淹没）
2. 但 Python 的 `ThreadingHTTPServer` 仍会为每个完成的连接创建线程
3. 数千个线程同时运行，线程栈（默认8MB/线程）耗尽虚拟内存
4. 进程被OOM killer杀死或自身崩溃退出

## 复现验证

```bash
# 在被攻击状态下
ss -tlnp | grep 8080   # 可能还活着但极慢
ps aux | grep python    # 看线程数（TH count）
dmesg -T | grep -i 'OOM\|killed\|8080\|SYN\|flood'
```

## 快速修复

```bash
bash /home/ubuntu/.hermes/profiles/3l/skills/research/daily-3l-review/scripts/restart_server.sh
```

## 加固方案（待实施）

1. **gunicorn** 替代 ThreadingHTTPServer
   - 固定worker进程池（如4 workers）
   - 连接限流：`--worker-connections 100`
   - 自动重启：`--max-requests 10000`

2. **systemd 自动重启**
   ```
   [Unit]
   Description=3L Web Server
   [Service]
   ExecStart=/usr/bin/python3 /home/ubuntu/www/server.py
   Restart=on-failure
   RestartSec=5
   User=ubuntu
   ```

3. **iptables 限流**
   ```bash
   iptables -A INPUT -p tcp --dport 8080 -m connlimit --connlimit-above 50 -j REJECT
   ```

## 记忆要点

- 服务器挂了先做：查端口→查进程→查内核日志→重启
- 不用问用户要不要重启，直接做（用户曾明确同意）
- 重启后验证 `curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/review.html` 返回200
