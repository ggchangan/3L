# 3L交易系统 — Docker 镜像（仅用于开发/测试）
# 生产环境使用 systemd + nginx（见 deploy/ 目录）
#
# 构建: docker build -t 3l-server .
# 运行: docker run -p 8080:8080 -v /home/ubuntu/data/3l:/data 3l-server

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wkhtmltopdf \
    librsvg2-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装依赖（精确锁定，与系统环境一致）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/private /data/knowledge_base /data/cache

ENV WWW_DIR=/app
ENV DATA_DIR=/data
ENV PORT=8080
ENV LOG_LEVEL=INFO
ENV LOG_DIR=/app/logs

EXPOSE 8080

# Docker 环境需要绑定 0.0.0.0，systemd 生产环境绑定 127.0.0.1（通过 nginx 反代）
CMD ["python", "server.py", "--host", "0.0.0.0"]
