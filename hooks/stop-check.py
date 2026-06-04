"""Stop hook: 会话结束前的内存写入提醒 — per-session tracking"""
import json, os, time

base = os.path.expanduser('~/.claude/projects')
session_marker = os.path.expanduser('~/.claude/.session-memory-marker')

# 记录本次 session 是否写过 memory
wrote_this_session = False
if os.path.exists(session_marker):
    try:
        marker_ts = os.path.getmtime(session_marker)
    except:
        marker_ts = 0
else:
    marker_ts = 0

cutoff = max(marker_ts, time.time() - 86400)
if os.path.exists(base):
    for proj in os.listdir(base):
        mem = os.path.join(base, proj, 'memory')
        if os.path.isdir(mem):
            for f in os.listdir(mem):
                if f == 'MEMORY.md':
                    continue
                fp = os.path.join(mem, f)
                if os.path.isfile(fp) and os.path.getmtime(fp) > cutoff:
                    wrote_this_session = True
                    break
        if wrote_this_session:
            break

msg = "Stop hook: 结束前确认 — 1) 测试通过 2) diff 匹配任务 3) 无静默跳过。"
if not wrote_this_session:
    msg += " 本次会话未写入 memory。如有经验教训或决策，请先写入再停止。"

# 校准提醒
calib_file = os.path.expanduser('~/.claude/edit-guard-calibrated')
if not os.path.exists(calib_file) or time.time() - os.path.getmtime(calib_file) > 30 * 86400:
    msg += " HOOK: edit-guard 需要校准复查。touch ~/.claude/edit-guard-calibrated 解除。"

# 更新 session marker
try:
    os.makedirs(os.path.dirname(session_marker), exist_ok=True)
    with open(session_marker, 'w') as f:
        f.write(str(time.time()))
except:
    pass

print(json.dumps({"systemMessage": msg}))
