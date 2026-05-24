#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════
# 3L 交易系统 — 回滚脚本
# 用法: ./deploy/rollback.sh [标签名]
# 示例: ./deploy/rollback.sh v0.80   # 回滚到指定标签
#       ./deploy/rollback.sh          # 回滚到上一个标签
# ═══════════════════════════════════════════════

APP_DIR="/home/ubuntu/3l-server"
TAG="${1:-}"

cd "${APP_DIR}"

# 如果没有指定标签，回到上一个
if [ -z "${TAG}" ]; then
    TAG=$(git tag --sort=-creatordate | sed -n '2p')
    if [ -z "${TAG}" ]; then
        echo "[rollback] ❌ 没有找到上一个标签"
        exit 1
    fi
    echo "[rollback] 未指定标签，回到上一个: ${TAG}"
fi

# 检查标签是否存在
if ! git tag -l "${TAG}" | grep -q .; then
    echo "[rollback] ❌ 标签 '${TAG}' 不存在"
    echo "可用标签:"
    git tag --sort=-creatordate | head -10
    exit 1
fi

# 1. 先备份当前数据
echo "[rollback] 回滚前创建数据备份..."
bash deploy/backup.sh

# 2. 执行回滚
echo "[rollback] 回滚到 ${TAG}"
git checkout -f "${TAG}"

# 3. 重新安装依赖（如果 requirements.txt 变了）
echo "[rollback] 更新依赖..."
.venv/bin/pip install --quiet -r requirements.txt 2>/dev/null || true

# 4. 重启服务
echo "[rollback] 重启服务..."
sudo systemctl restart 3l-server.service

# 5. 验证
sleep 2
HEALTH=$(curl -s http://127.0.0.1:8080/api/health | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])" 2>/dev/null || echo "unreachable")

if [ "${HEALTH}" = "ok" ]; then
    echo "[rollback] ✅ 回滚成功 → ${TAG}"
else
    echo "[rollback] ⚠️  回滚后服务状态: ${HEALTH}"
fi
