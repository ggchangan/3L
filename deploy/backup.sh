#!/usr/bin/env bash
set -euo pipefail

# ═══════════════════════════════════════════════
# 3L 交易系统 — 自动备份脚本
# 用法: ./deploy/backup.sh
# 可通过 cron 每日执行
# ═══════════════════════════════════════════════

BACKUP_DIR="${BACKUP_DIR:-/home/ubuntu/data/3l/backups}"
DATA_DIR="${DATA_DIR:-/home/ubuntu/data/3l}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/3l-backup-${TIMESTAMP}.tar.gz"

mkdir -p "${BACKUP_DIR}"

echo "[backup] 开始备份 → ${BACKUP_FILE}"

# 备份数据目录（排除缓存）
TMP_FILE="$(mktemp /tmp/3l-backup-XXXXXX.tar.gz)"
tar --exclude="cache" \
    --exclude="backups" \
    -czf "${TMP_FILE}" \
    -C "${DATA_DIR}" .
mv "${TMP_FILE}" "${BACKUP_FILE}"

# 备份 .env 配置文件（单独存，避免包含在数据目录备份中）
if [ -f "/home/ubuntu/3l-server/.env" ]; then
    cp "/home/ubuntu/3l-server/.env" "${BACKUP_DIR}/env-${TIMESTAMP}.bak"
    echo "[backup] .env 已备份"
fi

echo "[backup] 完成: $(du -h "${BACKUP_FILE}" | cut -f1)"

# 清理旧备份，只保留 RETENTION_DAYS 天
find "${BACKUP_DIR}" -name "3l-backup-*.tar.gz" -mtime +${RETENTION_DAYS} -delete
find "${BACKUP_DIR}" -name "env-*.bak" -mtime +${RETENTION_DAYS} -delete
echo "[backup] 已清理 ${RETENTION_DAYS} 天前的旧备份"

# 列出当前备份
echo "[backup] 当前备份列表:"
ls -lh "${BACKUP_DIR}"/*.tar.gz 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
