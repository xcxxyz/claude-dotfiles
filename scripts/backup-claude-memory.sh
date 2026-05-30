#!/bin/bash
# Claude Code 记忆与配置备份脚本
# 备份: settings.json, .claude.json, memory/

BACKUP_DIR="C:/Users/夏/.claude/backups"
SRC_DIR="C:/Users/夏/.claude"
MEMORY_DIR="${SRC_DIR}/projects/D----Documents-First-CC/memory"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "${BACKUP_DIR}"

# 备份 settings.json
cp "${SRC_DIR}/settings.json" "${BACKUP_DIR}/settings.json.bak.${TIMESTAMP}" 2>/dev/null

# 备份 .claude.json
cp "${SRC_DIR}/.claude.json" "${BACKUP_DIR}/.claude.json.bak.${TIMESTAMP}" 2>/dev/null

# 备份记忆目录
if [ -d "${MEMORY_DIR}" ] && [ "$(ls -A "${MEMORY_DIR}" 2>/dev/null)" ]; then
  mkdir -p "${BACKUP_DIR}/memory/"
  cp -r "${MEMORY_DIR}/"* "${BACKUP_DIR}/memory/"
fi

# 清理旧备份，只保留最近5个
for prefix in settings.json .claude.json; do
  ls -t "${BACKUP_DIR}/${prefix}.bak."* 2>/dev/null | tail -n +6 | xargs rm -f 2>/dev/null
done

echo "Backup done: ${TIMESTAMP}"
