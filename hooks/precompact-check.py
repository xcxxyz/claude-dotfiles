"""PreCompact hook: 压缩前确认 — 使用 session marker 追踪"""
import json, os, time

session_marker = os.path.expanduser('~/.claude/.session-memory-marker')
base = os.path.expanduser('~/.claude/projects')

cutoff = time.time() - 86400
if os.path.exists(session_marker):
    try:
        cutoff = max(os.path.getmtime(session_marker), cutoff)
    except:
        pass

found = False
if os.path.exists(base):
    for proj in os.listdir(base):
        mem = os.path.join(base, proj, 'memory')
        if os.path.isdir(mem):
            for f in os.listdir(mem):
                if f == 'MEMORY.md':
                    continue
                fp = os.path.join(mem, f)
                if os.path.isfile(fp) and os.path.getmtime(fp) > cutoff:
                    found = True
                    break
        if found:
            break

if not found:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreCompact",
            "additionalContext": (
                "PreCompact: 本次会话尚未写入 memory。"
                "如有重要进展或经验教训，请先写入 memory 再压缩。"
            )
        }
    }))
