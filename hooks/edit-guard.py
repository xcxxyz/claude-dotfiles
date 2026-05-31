"""PreToolUse: 拦截同文件短时间密集编辑（fix-loop 模式），正常迭代不误伤"""
import json, sys, os, time, re

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

STATE_FILE = os.path.expanduser('~/.claude/edit-guard-state.json')
# 阈值：密集度判断——同一文件短时间内多次改动
RAPID_WARN  = 2   # 60s 内 2 次 → 警告
RAPID_BLOCK = 3   # 60s 内 3 次 → 拦截
SLOW_BLOCK  = 5   # 300s 内 5 次 → 拦截（任何密度）
RAPID_WIN   = 60  # "密集"时间窗口
SLOW_WIN    = 300 # "长期"时间窗口

def load_state():
    try:
        s = json.load(open(STATE_FILE))
        now = time.time()
        return {k: v for k, v in s.items() if now - v.get('last', 0) < SLOW_WIN}
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
now = time.time()
entry = state.get(target, {'times': [], 'total': 0})

# 记录每次编辑时间
entry['times'].append(now)
entry['total'] = entry.get('total', 0) + 1
entry['last'] = now
state[target] = entry

# 统计密集窗口内的编辑次数
recent = [t for t in entry['times'] if now - t < RAPID_WIN]
all_slow = len([t for t in entry['times'] if now - t < SLOW_WIN])

save_state(state)

# 密集编辑检测（60s 内）
if len(recent) >= RAPID_BLOCK:
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"HARD BLOCK: {RAPID_WIN}s 内对 '{target}' 编辑了 {len(recent)} 次。\n"
            "这是 fix-loop 模式——立即停止。先搜索/排查，确定根因后再动手。"
        )
    }))
    sys.exit(0)

if len(recent) >= RAPID_WARN:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"WARNING: {RAPID_WIN}s 内编辑 '{target}' {len(recent)} 次。"
                "确认不是 fix-loop。如不确定，先搜索/排查。"
            )
        }
    }))

# 长期多编辑（300s 内累积）
if all_slow >= SLOW_BLOCK:
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"HARD BLOCK: {SLOW_WIN//60} 分钟内对 '{target}' 编辑了 {all_slow} 次。\n"
            "停止修改，先输出 ROOT CAUSE 确认不是循环修复。"
        )
    }))
    sys.exit(0)
