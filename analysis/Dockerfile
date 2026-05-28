FROM python:3.12-slim

WORKDIR /app

# 安装 threel-core 共享包（从构建上下文中复制）
COPY core/ /app/core/
RUN pip install --upgrade pip && pip install --no-cache-dir -e /app/core/

# 安装 3l-analysis 服务
COPY analysis/ /app/analysis/
# 去掉 pyproject.toml 中的 file:// 路径依赖（threel-core 已在前一步安装）
RUN sed -i '/threel-core.*file:\/\//d' /app/analysis/pyproject.toml && \
    pip install --no-cache-dir -e /app/analysis/

EXPOSE 9090

ENV DATA_DIR=/data/3l
ENV PORT=9090

CMD ["python", "/app/analysis/server.py"]
