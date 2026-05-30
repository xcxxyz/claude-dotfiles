---
name: self-optimization-baseline
description: 当前防惯性/防推测修复系统的配置基线——未来升级的起点
metadata: 
  node_type: memory
  type: reference
  originSessionId: 2b311dec-eaf8-4bdd-bb84-ba0b01f0a0fb
---

## 当前防线（2026-05-30 部署）

| 层 | 文件 | 作用 |
|---|------|------|
| CLAUDE.md HARD GATE | `~/.claude/CLAUDE.md` | 改代码前强制 ROOT CAUSE，禁猜测词 |
| Challenger Agent | `~/.claude/agents/challenger.md` | ≥3文件或>20行改动→独立审查 |
| PreToolUse | `~/.claude/settings.json` hooks | Write/Edit/Bash 同文件≥2次警告≥4次硬拦截 |
| PostToolUse | 同上 | 编辑失败→注入调试纪律；余额刷新 |
| SessionStart | 同上 | 自动修复 CC Switch 破坏的 hooks |

## 已知漏洞（无法靠配置修复）

1. **子代理绕过** (Issue #43772) — subagent 不继承 PreToolUse hooks
2. **自我修改** — 模型可改 settings.json/hooks，SessionStart 自动修复但窗口期短暂
3. **散文遵守率 ~66%** — CLAUDE.md 在生产中有 ~34% 非遵守率

## 升级待办

- [ ] 平台修复 Issue #43772 后 → 子代理自动继承 hooks
- [ ] RFC #45427 实现后 → 部署确定性 tool gate
- [ ] MCP wait tool 可用后 → 物理暂停文本生成
- [ ] 考虑自动触发 challenger agent（目前手动）
