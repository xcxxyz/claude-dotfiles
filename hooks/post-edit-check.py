"""
PostToolUse: 语义错误分类 + 证据链回填 + 门禁管理

错误分级:
  L0: success
  L1: new_error (不同签名)
  L2: same_error (同签名，不同区域)
  L3: same_error_same_file (同签名+同文件 — fix-loop确认)
"""
import json, sys, os, time, re, sqlite3, hashlib

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})
resp = data.get('tool_response', {})

DB = os.path.expanduser('~/.claude/edit-guard-v2.db')
GATE_FILE = os.path.expanduser('~/.claude/post-edit-gate.json')
CHECKPOINT = os.path.expanduser('~/.claude/root-cause-checkpoint.md')
LOG_FILE = os.path.expanduser('~/.claude/edit-guard-log.jsonl')
now = time.time()

def log_event(action, detail=''):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            json.dump({'ts': now, 'action': action, 'detail': str(detail)[:200]}, f)
            f.write('\n')
    except: pass

# ———— 语义错误签名 (修复: 归一化路径) ————
def semantic_sig(text):
    s = str(text)[:500]
    # 路径归一化
    s = re.sub(r'File "([^"]+)"', lambda m: f'File "{os.path.basename(m.group(1))}"', s)
    s = re.sub(r'[A-Z]:/[^\s,;]+', lambda m: os.path.basename(m.group()), s)

    # Python Traceback — 优先异常类型
    m = re.search(r'(\w+(?:Error|Exception|Warning))\s*:?\s*(.+?)(?:\n|$)', s)
    if m:
        exc_msg = re.sub(r'0x[0-9a-fA-F]+', 'ADDR', m.group(2)[:60])
        exc_msg = re.sub(r'\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}', 'TS', exc_msg)
        exc_msg = re.sub(r'\d{10,13}', 'UNIXTIME', exc_msg)
        exc_msg = re.sub(r'\d{3,}', 'N', exc_msg)
        return f'py:{m.group(1)}:{exc_msg}'

    # Exit status
    m = re.search(r'Exit (?:code|status)\s*(\d+)', s, re.IGNORECASE)
    if m: return f'exit:{m.group(1)}'

    # C# errors
    m = re.search(r'(?:error|CS|MSB)\s*(\d{4,5})', s, re.IGNORECASE)
    if m: return f'cs:{m.group(1)}'

    # HTTP status (specific: 必须紧跟前缀词)
    m = re.search(r'(?:status|HTTP/[\d.]+\s+)(\d{3})', s, re.IGNORECASE)
    if m: return f'http:{m.group(1)}'

    # Command not found
    m = re.search(r'(\S+):\s*command not found', s, re.IGNORECASE)
    if m: return f'cmd:{m.group(1)}'

    # Permission
    if re.search(r'permission denied', s, re.IGNORECASE): return 'perm'

    # Connection
    if re.search(r'connection\s*(refused|reset|timed?\s*out)', s, re.IGNORECASE): return 'conn'

    # Docker
    if 'docker' in s.lower() and 'error' in s.lower(): return 'docker'

    # Fallback hash
    clean = re.sub(r'\d{3,}', 'N', re.sub(r'0x[0-9a-f]+', 'H', s[:100]))
    return f'gen:{hashlib.md5(clean.encode()).hexdigest()[:8]}'

def is_real_error(resp):
    """区分真错误和含'error'词的良性响应"""
    if resp.get('ok') or resp.get('success'):
        return False
    err_text = str(resp.get('error', ''))
    if err_text:
        return True
    # 检查 exit code
    text = str(resp)
    if re.search(r'Exit (?:code|status)\s*[1-9]', text):
        return True
    if re.search(r'Traceback \(most recent call last\)', text):
        return True
    if re.search(r'\w+(?:Error|Exception):', text):
        return True
    return False

# ———— Checkpoint写 → 清除gate + 恢复信念 ————
fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
if tool == 'Write' and fp == CHECKPOINT.replace('\\', '/'):
    log_event('gate_clear_checkpoint')
    try:
        db = sqlite3.connect(DB)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute("DELETE FROM state WHERE key='hard_gate'")
        db.commit(); db.close()
        json.dump({'gate': False, 'ts': now}, open(GATE_FILE, 'w'))
    except: pass
    sys.exit(0)

if tool not in ('Edit', 'Write', 'Bash'):
    sys.exit(0)

if not is_real_error(resp):
    # 更新 pending 为 success
    try:
        db = sqlite3.connect(DB)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute("UPDATE evidence SET outcome='success' WHERE outcome='pending' AND ts > ?",
                   (now - 10,))
        db.commit(); db.close()
    except: pass
    sys.exit(0)

# ———— 错误处理 ————
err_text = str(resp.get('error', resp))
error_sig = semantic_sig(err_text)
log_event('error', f'sig={error_sig}')

try:
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')

    # 找到最近的 pending 证据 (匹配工具类型和文件路径，避免跨工具错误归因)
    fp_norm = fp
    zone_prefix = 'edit:' if tool == 'Edit' else ('bash:' if tool == 'Bash' else 'write:')
    row = db.execute(
        "SELECT id, file_path FROM evidence WHERE outcome='pending' AND tool=? ORDER BY ts DESC LIMIT 1",
        (tool,)).fetchone()

    if not row:
        db.close(); sys.exit(0)

    evidence_id, ev_file_path = row[0], row[1]

    # 检查上一次错误签名（按时间倒序，跳过当前pending行）
    prev = db.execute(
        "SELECT error_sig, file_path FROM evidence WHERE id < ? AND outcome NOT IN ('success','pending') ORDER BY id DESC LIMIT 1",
        (evidence_id,)).fetchone()

    if prev and prev[0] == error_sig:
        if prev[1] == ev_file_path:
            final_outcome = 'same_error_same_file'  # L3: 同错误+同文件
        else:
            final_outcome = 'same_error'  # L2: 同错误,不同文件
    else:
        final_outcome = 'new_error'  # L1

    # 更新证据
    db.execute("UPDATE evidence SET outcome=?, error_sig=? WHERE id=?",
               (final_outcome, error_sig, evidence_id))

    # 连续同类错误计数（真正连续，跨越success重置）
    consecutive = 0
    for r in db.execute(
        "SELECT outcome, error_sig FROM evidence WHERE ts > ? ORDER BY id DESC",
        (now - 300,)).fetchall():
        if r[0] and 'same_error' in r[0] and r[1] == error_sig:
            consecutive += 1
        elif r[0] == 'success':
            break  # success中断连续
        elif r[0] and 'error' in r[0] and r[1] != error_sig:
            break  # 不同错误中断连续
        # pending: 跳过

    db.commit()

    # 连续2次 → 设置gate
    if consecutive >= 2:
        log_event('gate_set', f'consecutive={consecutive} sig={error_sig[:60]}')
        json.dump({'gate': True, 'ts': now, 'error': error_sig[:80]}, open(GATE_FILE, 'w'))

    if consecutive >= 3:
        msg = (f"信念降级: 连续 {consecutive} 次同类错误(L{'3' if final_outcome == 'same_error_same_file' else '2'})。\n"
               f"根因假设是什么？[已验证]还是[猜测]？写根因分析到 {CHECKPOINT}。")
    elif consecutive >= 2:
        msg = f"同类错误 {consecutive} 次。停下来检查根因。"
    else:
        msg = f"新错误: {error_sig[:80]}。"

    if msg:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
            "additionalContext": msg}}))

    db.close()

except Exception as e:
    log_event('db_error', str(e)[:100])
