"""
PreToolUse: 强制保护 settings.json — 禁止Write/MultiEdit, 禁止Edit触碰API key
修复: MultiEdit检测 + Windows大小写折叠 + 审计日志
"""
import json, sys, os, time

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})
now = time.time()

LOG_FILE = os.path.expanduser('~/.claude/settings-guard-log.jsonl')

def log_block(reason, detail=''):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            json.dump({'ts': now, 'tool': tool, 'reason': reason, 'detail': detail[:200]}, f)
            f.write('\n')
    except Exception:
        pass

def normalize_path(path):
    return path.replace('\\', '/').lower()

def is_settings_json(path):
    """Windows大小写折叠 + 排除.local.json"""
    p = normalize_path(path)
    return p.endswith('.claude/settings.json') and not p.endswith('.local.json')

def check_text(old_text, new_text):
    """检查编辑内容是否包含API key"""
    text = (old_text or '') + (new_text or '')
    if 'ANTHROPIC_API_KEY' in text or 'sk-ant-' in text:
        return True
    return False

# 处理 MultiEdit: 遍历 edits[] 数组
if tool == 'MultiEdit':
    edits = ti.get('edits', [])
    for edit in edits:
        fp = normalize_path(edit.get('file_path', edit.get('filePath', '')))
        if is_settings_json(fp):
            if check_text(edit.get('old_string', ''), edit.get('new_string', '')):
                log_block('MultiEdit_API_key', fp)
                print(json.dumps({
                    "decision": "block",
                    "reason": "禁止在 settings.json 中编辑 API key。API key 已隔离在 settings.local.json。"
                }))
                sys.exit(0)
    sys.exit(0)

# 单文件操作
fp = (ti.get('file_path') or ti.get('filePath') or '')

if not is_settings_json(fp):
    sys.exit(0)

if tool == 'Write':
    log_block('Write', fp)
    print(json.dumps({
        "decision": "block",
        "reason": (
            "禁止 Write 重写 settings.json。只能使用 Edit 修改单个字段。\n"
            "API key 已隔离在 settings.local.json 中，Write settings.json 不会覆盖 key，"
            "但可能触发 Cursor 代理接管导致未登录。"
        )
    }))
    sys.exit(0)

if tool == 'Edit':
    old = ti.get('old_string', '')
    new = ti.get('new_string', '')
    if check_text(old, new):
        log_block('Edit_API_key', fp)
        print(json.dumps({
            "decision": "block",
            "reason": (
                "禁止在 settings.json 中编辑 API key。"
                "API key 已隔离在 settings.local.json，如需修改请直接编辑该文件。"
            )
        }))
        sys.exit(0)
