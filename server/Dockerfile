# =============================================
# 3L交易系统 — Docker 镜像（多阶段构建）
# 目录结构对齐原生开发：
#   /app/server/          ← server.py + backend/ + frontend/
#   /app/core/            ← threel_core 包
#   /app/all_a_stocks.json   ← 种子数据
#   /app/pinyin_initials.json
#   /data/                ← 挂载卷（K线数据/配置）
# =============================================
#
# 构建: docker build -t 3l-server:latest -f server/Dockerfile .
# 运行: docker run -d -p 80:8080 \
#           -v /path/to/data:/data \
#           -e AUTH_USER=xxx -e AUTH_PASS=xxx \
#           --name 3l-server \
#           3l-server:latest

# ── Stage 1: 前端构建 ──
FROM node:20-bookworm AS build-fe

WORKDIR /build

COPY server/frontend/package.json server/frontend/package-lock.json ./
RUN npm ci

COPY server/frontend/ ./
RUN npm run build

# ── Stage 2: 运行环境 ──
FROM python:3.12-slim-bookworm

# ====== 系统依赖（使用国内镜像加速） ======
RUN sed -i 's|URIs: http://deb.debian.org/debian|URIs: http://mirrors.tuna.tsinghua.edu.cn/debian|g' /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|URIs: http://deb.debian.org/debian-security|URIs: http://mirrors.tuna.tsinghua.edu.cn/debian-security|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    librsvg2-bin \
    cron \
    tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/server

# ====== Python 依赖 ======
COPY server/requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# ====== 应用代码（保持 server/ 子目录结构） ======
COPY server/ /app/server/
# 安装本地 threel_core 包
COPY core/ /app/core/
RUN pip install -e /app/core/ --no-cache-dir
# 种子数据（股票名称对照表）
COPY all_a_stocks.json pinyin_initials.json /app/

# ====== 前端构建产物 ======
COPY --from=build-fe /build/dist/ /app/server/frontend/dist/

# ====== 运行时目录 ======
RUN mkdir -p /data/private /data/cache /data/charts /app/server/logs

# ====== 环境变量 ======
ENV WWW_DIR=/app
ENV DATA_DIR=/data
ENV PORT=8080
ENV LOG_LEVEL=INFO
ENV LOG_DIR=/app/server/logs
ENV AUTH_USER=
ENV AUTH_PASS=

# ====== 定时更新任务（交易日17:00） ======
RUN echo "0 17 * * 1-5 cd /app/server && python3 -m backend.core.update_stock_data >> /var/log/stock_update.log 2>&1" > /etc/cron.d/stock-update && \
    chmod 0644 /etc/cron.d/stock-update && \
    crontab /etc/cron.d/stock-update

EXPOSE 8080

# ====== 健康检查 ======
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/')" || exit 1

# ====== 启动 ======
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/server/docker-entrypoint.sh"]
