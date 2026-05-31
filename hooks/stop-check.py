import json, os, time

# 检查所有项目 memory 目录是否有今天的更新
base = os.path.expanduser('~/.claude/projects')
today = False
cutoff = time.time() - 86400
if os.path.exists(base):
    for proj in os.listdir(base):
        mem = os.path.join(base, proj, 'memory')
        if os.path.isdir(mem):
            for f in os.listdir(mem):
                fp = os.path.join(mem, f)
                if os.path.isfile(fp) and os.path.getmtime(fp) > cutoff:
                    today = True
                    break
        if today: break

msg = "Stop hook: 结束前确认 — 1) 测试通过 2) diff 匹配任务 3) 无静默跳过。"
if not today:
    msg += " WARNING: 今天所有项目 memory/ 无更新。如有经验教训，请先写入再停止。"

print(json.dumps({"systemMessage": msg}))
