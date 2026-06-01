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

# 检查 hook 参数是否需要校准
guard_file = os.path.expanduser('~/.claude/edit-guard-state.json')
calib_file = os.path.expanduser('~/.claude/edit-guard-calibrated')
need_calib = True
if os.path.exists(calib_file):
    try:
        age = time.time() - os.path.getmtime(calib_file)
        need_calib = age > 30 * 86400  # 30 天
    except:
        pass

if need_calib:
    msg += (
        " HOOK-CALIBRATE: edit-guard 阈值需要复查（上次校准"
        f" {'超过30天' if need_calib else '未知'}）。"
        " 检查: 全局8次阈值是否误拦过？120s gate 是否太长？"
        " 复查后 touch ~/.claude/edit-guard-calibrated 解除提醒。"
    )

print(json.dumps({"systemMessage": msg}))
