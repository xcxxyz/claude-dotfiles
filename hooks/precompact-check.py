"""PreCompact hook: 压缩前检查是否有新的 memory 更新，没有则提醒"""
import json, os, time

# 检查最近 10 分钟是否有 memory 写入
base = os.path.expanduser('~/.claude/projects')
cutoff = time.time() - 600
found = False
if os.path.exists(base):
    for proj in os.listdir(base):
        mem = os.path.join(base, proj, 'memory')
        if os.path.isdir(mem):
            for f in os.listdir(mem):
                fp = os.path.join(mem, f)
                if os.path.isfile(fp) and os.path.getmtime(fp) > cutoff:
                    found = True
                    break
        if found: break

if not found:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": (
                "PreCompact: 最近 10 分钟无 memory 更新。"
                "如有重要进展或经验教训，请先写入 memory 再进行压缩。"
            )
        }
    }))
