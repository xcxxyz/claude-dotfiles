"""
PreToolUse: Edit前提醒是否读过文件 — 软提醒，不封锁
用户口头告知、Grep结果、上下文记忆都算"已知"
"""
import json, sys, os, time, sqlite3

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

if tool not in ('Edit', 'Write'):
    sys.exit(0)

fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
if not fp: sys.exit(0)
if tool == 'Write' and not os.path.exists(fp): sys.exit(0)

DB = os.path.expanduser('~/.claude/read-tracker.db')
try:
    db = sqlite3.connect(DB)
    row = db.execute('SELECT mtime, ts FROM reads WHERE file_path=?', (fp,)).fetchone()
    db.close()

    if row:
        tracked_mtime, read_ts = row
        try: current_mtime = os.path.getmtime(fp)
        except: sys.exit(0)
        if abs(tracked_mtime - current_mtime) <= 2:
            sys.exit(0)
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "additionalContext": f"文件已变更于 {time.time()-read_ts:.0f}s 前读取后。确认内容是否仍符合预期。"}}))
    else:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
            "additionalContext": f"未跟踪到此文件的读取记录。如不确定内容请先 Read。"}}))
except:
    pass
