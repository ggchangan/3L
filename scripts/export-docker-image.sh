#!/bin/bash
# 3L交易系统 — Docker 镜像导出脚本
#
# 用途：把 Docker 镜像导出为 tar 文件，直接传给同学服务器加载
# 适合没有镜像仓库的场景
#
# 用法：
#   1. 在本机运行: sudo bash scripts/export-docker-image.sh
#   2. 把生成的 3l-server.tar.gz 传给同学
#   3. 同学服务器上: sudo docker load -i 3l-server.tar
#   4. 然后按 docs/deployment-guide.md 运行

set -e

IMAGE_NAME="3l-server:latest"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/.."
OUTPUT_FILE="${OUTPUT_DIR}/3l-server.tar"

echo "=== 导出 Docker 镜像 ==="
echo "镜像: ${IMAGE_NAME}"
echo "输出: ${OUTPUT_FILE}.gz"
echo ""

# 检查镜像是否存在
if ! docker image inspect ${IMAGE_NAME} > /dev/null 2>&1; then
    echo "❌ 镜像 ${IMAGE_NAME} 不存在，请先构建"
    echo "   cd ${OUTPUT_DIR} && sudo docker build -t ${IMAGE_NAME} ."
    exit 1
fi

# 导出
echo "正在导出..."
docker save -o ${OUTPUT_FILE} ${IMAGE_NAME}

# 压缩
echo "正在压缩..."
gzip -f ${OUTPUT_FILE}
OUTPUT_FILE="${OUTPUT_FILE}.gz"

echo ""
echo "✅ 导出完成"
echo "   文件: ${OUTPUT_FILE}"
echo "   大小: $(ls -lh ${OUTPUT_FILE} | awk '{print $5}')"
echo ""
echo "=== 传给同学后执行 ==="
echo "  gunzip 3l-server.tar.gz"
echo "  sudo docker load -i 3l-server.tar"
echo "  # 然后按 docs/deployment-guide.md 运行"
