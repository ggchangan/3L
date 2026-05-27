# 3L交易系统 — Docker 镜像
# 用途：给同学部署用，无需源码可执行
#
# 构建: docker build -t 3l-server:latest .
# 运行: docker run -d -p 8080:8080 \
#           -v /path/to/data:/data \
#           -e AUTH_USER=xxx -e AUTH_PASS=xxx \
#           --name 3l-server \
#           3l-server:latest

FROM python:3.12-slim-bookworm

# ====== 系统依赖（使用国内 Debian 镜像加速） ======
RUN sed -i 's|URIs: http://deb.debian.org/debian|URIs: http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|URIs: http://deb.debian.org/debian-security|URIs: http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    librsvg2-bin \
    cron \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ====== Python 依赖（先 copy requirements 利用 Docker 缓存） ======
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# ====== 应用代码 ======
COPY . .

# ====== 运行时目录 ======
RUN mkdir -p /data/private /data/cache /data/charts /app/logs

# ====== 环境变量 ======
ENV WWW_DIR=/app
ENV DATA_DIR=/data
ENV PORT=8080
ENV LOG_LEVEL=INFO
ENV LOG_DIR=/app/logs
# 以下两个必须通过 -e 传入，否则启动失败
ENV AUTH_USER=
ENV AUTH_PASS=

# ====== 定时更新任务（交易日17:00） ======
RUN echo "0 17 * * 1-5 cd /app && PYTHONPATH=. python3 -m backend.core.update_stock_data >> /var/log/stock_update.log 2>&1" > /etc/cron.d/stock-update && \
    chmod 0644 /etc/cron.d/stock-update && \
    crontab /etc/cron.d/stock-update

EXPOSE 8080

# ====== 健康检查 ======
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# ====== 启动 ======
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/docker-entrypoint.sh"]
