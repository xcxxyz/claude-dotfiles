"""PostToolUse: 错误检测 + gate 管理 + HARD GATE 纪律注入"""
import json, sys, os, time, re

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
tool_response = data.get('tool_response', {})

STATE_FILE = os.path.expanduser('~/.claude/post-edit-error-state.json')
GATE_FILE = os.path.expanduser('~/.claude/post-edit-gate.json')
CHECKPOINT_FILE = os.path.expanduser('~/.claude/root-cause-checkpoint.md')
LOG_FILE = os.path.expanduser('~/.claude/edit-guard-log.jsonl')

ERROR_PATTERNS = [
    r'BadUserNameOrPassword', r'BadUserOrPassword', r'BadAuth',
    r'IdReject', r'IdentifierRejected',
    r'Connection refused', r'ConnectionRefused',
    r'error\s*:\s*CS\d{4}', r'error\s*MSB\d{4}',
    r'Unhandled exception', r'fatal error',
    r'Exit code [1-9]',
    r'FAIL:', r'FAIL\b',
    r'失败', r'错误',
]

def log_event(action, detail=''):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            json.dump({'ts': time.time(), 'action': action, 'detail': detail}, f)
            f.write('\n')
    except:
        pass

def is_error(resp):
    if resp.get('ok') or resp.get('success'):
        return False
    if resp.get('error'):
        return True
    text = str(resp)
    for pat in ERROR_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

def load_state():
    try:
        s = json.load(open(STATE_FILE))
        if time.time() - s.get('ts', 0) > 300:
            return {'errors': [], 'ts': time.time()}
        return s
    except:
        return {'errors': [], 'ts': time.time()}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(s, open(STATE_FILE, 'w'))

# ============================================================
# Write 到 checkpoint 文件 → 清除 gate
# ============================================================
ti = data.get('tool_input', {})
fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')

if tool == 'Write' and fp == CHECKPOINT_FILE.replace('\\', '/'):
    log_event('gate_clear', 'checkpoint written')
    try:
        json.dump({'gate': False, 'ts': time.time()}, open(GATE_FILE, 'w'))
    except:
        pass
    sys.exit(0)

# ============================================================
# 非错误 → 退出
# ============================================================
if not is_error(tool_response):
    sys.exit(0)

# ============================================================
# 错误处理
# ============================================================
state = load_state()

# 提取错误签名
err_text = str(tool_response.get('error', tool_response))
err_sig = re.sub(r'\d+', 'N', err_text[:120])
state['errors'].append({'sig': err_sig, 'time': time.time()})
state['ts'] = time.time()

recent = [e for e in state['errors'] if time.time() - e['time'] < 300]
same_count = sum(1 for e in recent if e['sig'] == err_sig)
unique_sigs = set(e['sig'] for e in recent)

# 同错误 ≥ 2 次 → 设置 gate
if same_count >= 2:
    log_event('gate_set', f'same_error={same_count} sig={err_sig[:60]}')
    try:
        os.makedirs(os.path.dirname(GATE_FILE), exist_ok=True)
        json.dump({'gate': True, 'ts': time.time(), 'error': err_sig[:80]},
                  open(GATE_FILE, 'w'))
    except:
        pass

save_state(state)

# ============================================================
# 注入纪律消息
# ============================================================
msg = ""

if same_count >= 3:
    msg = (
        f"CRITICAL: 相同错误模式 {same_count} 次（5 分钟内）。fix-loop 确认。\n\n"
        "HARD GATE 检查清单:\n"
        "1. ROOT CAUSE 是什么？（不含'可能/大概/或许'）\n"
        "2. 当前假设哪些是 [已验证]，哪些是 [猜测]？\n"
        "3. [猜测] 的先验证，不要再改代码\n"
        "4. ≥2 轮 → 停手\n"
        "5. 先排除环境/配置/版本，再考虑代码 bug\n\n"
        f"请将分析写入 {CHECKPOINT_FILE} 以解除编辑限制。"
    )
elif same_count >= 2:
    msg = (
        f"WARNING: 相同错误出现了 {same_count} 次（5 分钟内）。\n"
        "停下来检查假设。确定根因后再改代码。\n"
        f"如需解除编辑限制，写根因分析到 {CHECKPOINT_FILE}。"
    )
elif len(unique_sigs) >= 2:
    msg = (
        f"提示: 5 分钟内出现 {len(unique_sigs)} 种不同错误。\n"
        "可能在不相关的方向分散调试。聚焦一个错误。"
    )

if msg:
    log_event('inject_discipline', f'same={same_count} unique={len(unique_sigs)}')
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": msg
        }
    }))
