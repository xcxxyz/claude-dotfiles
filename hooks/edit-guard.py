"""PreToolUse: Write/Edit/Bash 拦截 — 同文件重复编辑 + 大范围改动强制审查"""
import json, sys, os, time, re

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

STATE_FILE = os.path.expanduser('~/.claude/edit-guard-state.json')
WARN_AT, BLOCK_AT, WINDOW = 2, 4, 300  # 同文件阈值

def load_state():
    try:
        s = json.load(open(STATE_FILE))
        return {k: v for k, v in s.items() if time.time() - v['time'] < WINDOW}
    except:
        return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(s, open(STATE_FILE, 'w'))

def get_target():
    fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
    if tool == 'Bash':
        cmd = ti.get('command', '')
        m = re.search(r'(?:sed\s+-i|tee\s+|echo\s+.*>|cat\s+.*>|cp\s+-f|mv\s+|dd\s+.*of=|perl\s+-i)\s*["\047]?([^\s"'\''>|&]+)', cmd)
        if m: return 'bash:' + m.group(1).replace('\\', '/')
        if ('python' in cmd or 'python3' in cmd) and ('open(' in cmd or 'write(' in cmd): return 'bash:python_write'
        if '>' in cmd: return 'bash:redirect'
        return ''
    return fp

target = get_target()
if not target:
    sys.exit(0)

state = load_state()

# === 检查 1: 同文件重复编辑 ===
entry = state.get(target, {'count': 0, 'time': 0})
entry['count'] += 1
entry['time'] = time.time()
state[target] = entry
save_state(state)
c = entry['count']

if c > BLOCK_AT:
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"HARD BLOCK: 在 {WINDOW//60} 分钟内连续对 '{target}' 操作了 {c} 次。\n"
            "HARD GATE 规则——立即停止修改。先输出 ROOT CAUSE（不含猜测词）。"
        )
    }))
    sys.exit(0)

if c > WARN_AT:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"WARNING: 已对 '{target}' 操作 {c}/{BLOCK_AT} 次。"
                "如根因未确定——立即停止，先搜索/排查。"
            )
        }
    }))

# scope check removed: cross-task files triggered false positives
