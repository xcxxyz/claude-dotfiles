#!/bin/bash
# Claude Code 自优化配置安装脚本
# 用法: bash install.sh

set -e
echo "=== Claude Code Self-Optimization Install ==="

# 1. 全局配置
cp CLAUDE.md ~/.claude/CLAUDE.md
cp .claudeignore ~/.claude/.claudeignore
cp agents/challenger.md ~/.claude/agents/challenger.md
echo "✓ CLAUDE.md + agent + .claudeignore"

# 2. Hooks (纯英文路径避开 Claude Code 中文路径 bug)
mkdir -p /c/temp
cp hooks/edit-guard.py /c/temp/edit-guard.py
cp hooks/post-edit-check.py /c/temp/post-edit-check.py
cp hooks/hook-repair.py /c/temp/hook-repair.py
echo "✓ Hooks installed"

# 3. 脚本
cp scripts/statusline.py ~/statusline.py
cp scripts/balance-refresh.py ~/balance-refresh.py
cp scripts/balance-daemon.py ~/balance-daemon.py
cp scripts/clipboard-vision.py ~/clipboard-vision.py
echo "✓ Scripts installed"

# 4. 敏感配置（需先 clone 私有仓库）
echo ""
echo "下一步: 从私有仓库拷贝敏感配置"
echo "  git clone git@github.com:xcxxyz/claude-dotfiles-private.git"
echo "  cp claude-dotfiles-private/settings.json ~/.claude/"
echo "  cp claude-dotfiles-private/recovered-config.json ~/.claude/"
echo ""
echo "=== 完成 ==="
echo "重启 Claude Code 生效"
