"""
PreToolUse: 证据加权防 fix-loop 系统

核心: 追踪编辑证据链，多信号加权评估，分级响应。
不是贝叶斯——是带滑动窗口的多信号评分。

信号: S1同区集中度 / S2连续同类错误 / S3区域多样性 / S4时间密度
响应: warn(提醒) → nudge(强制根因) → block(封锁)
"""
import json, sys, os, time, re, sqlite3
from collections import Counter

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

DB = os.path.expanduser('~/.claude/edit-guard-v2.db')
CALIB_FILE = os.path.expanduser('~/.claude/edit-guard-calibrated')
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

def get_db():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('''CREATE TABLE IF NOT EXISTS evidence (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, tool TEXT,
        zone_key TEXT, file_path TEXT, outcome TEXT, error_sig TEXT,
        score_before REAL, score_after REAL
    )''')
    db.execute('''CREATE TABLE IF NOT EXISTS state (
        key TEXT PRIMARY KEY, value TEXT, updated REAL
    )''')
    db.execute('CREATE INDEX IF NOT EXISTS idx_evidence_ts ON evidence(ts)')
    return db

def get_zone_key():
    fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
    if tool == 'Bash':
        cmd = ti.get('command', '')
        for pat in [r'(?:python|node|npm)\s+(\S+\.py|\S+\.js|\S+\.ts)',
                     r'git\s+(\S+)\s+(\S*)', r'docker\s+(\S+)', r'pip\s+install\s+(\S+)']:
            m = re.search(pat, cmd)
            if m: return f'bash:{m.group(1)[:80]}'
        m = re.search(r'>\s*(\S+)', cmd)
        if m: return 'bash:' + m.group(1).replace('\\', '/')[:120]
        return f'bash:{cmd[:50]}'
    if tool == 'Write': return f'write:{fp}'
    if tool == 'Edit':
        old = ti.get('old_string', '')
        if old:
            zone = re.sub(r'\s+', ' ', old[:50] + '...' + old[-50:] if len(old) > 110 else old).strip()
            if len(zone) >= 10: return f'edit:{fp}:{zone[:120]}'
        return f'edit:{fp}'
    return ''

zone_key = get_zone_key()
if not zone_key: sys.exit(0)

fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
db = get_db()

# 清理 >30min
db.execute('DELETE FROM evidence WHERE ts < ?', (now - 1800,))
db.commit()

# ———— 校准检查 ————
if os.path.exists(CALIB_FILE):
    calib_age = (now - os.path.getmtime(CALIB_FILE)) / 86400
else:
    os.makedirs(os.path.dirname(CALIB_FILE), exist_ok=True)
    json.dump({'ts': now, 'auto': True, 'note': 'initial'}, open(CALIB_FILE, 'w'))
    calib_age = 0

if calib_age > 45:
    log_event('block_calibration', f'age={calib_age:.0f}d')
    print(json.dumps({"decision": "block",
        "reason": f"edit-guard 已 {calib_age:.0f} 天未校准。touch ~/.claude/edit-guard-calibrated 解除。"}))
    db.close(); sys.exit(0)

# ———— 证据链评分 ————
last = db.execute('SELECT score_after, outcome FROM evidence ORDER BY id DESC LIMIT 1').fetchone()
prior_score = last[0] if last and last[1] != 'pending' else 0.7

rows = db.execute(
    'SELECT zone_key, outcome, error_sig, file_path FROM evidence WHERE ts > ? ORDER BY ts DESC LIMIT 10',
    (now - 900,)).fetchall()

current_score = prior_score

if rows and len(rows) >= 2:
    recent_zones = [r[0] for r in rows]
    zone_counts = Counter(recent_zones)
    max_zone_ratio = max(zone_counts.values()) / len(recent_zones)

    # 连续同类错误
    consecutive_same = 0
    last_sig = None
    for r in rows:
        if r[1] and 'same_error' in r[1]:
            if last_sig is None or r[2] == last_sig:
                consecutive_same += 1; last_sig = r[2]
            else:
                consecutive_same = 1; last_sig = r[2]
        else:
            consecutive_same = 0; last_sig = None

    diversity = len(set(recent_zones)) / len(recent_zones)

    # 证据权重 (hand-tuned, calibrated by calibration guard)
    if consecutive_same >= 3 and max_zone_ratio > 0.5:
        weight = 0.2
    elif consecutive_same >= 2 and max_zone_ratio > 0.4:
        weight = 0.4
    elif len([r for r in rows if r[1] and 'error' in r[1]]) / len(rows) > 0.3 and max_zone_ratio > 0.5:
        weight = 0.55
    elif diversity > 0.7:
        weight = 1.8
    elif all(r[1] == 'success' for r in rows[:3]):
        weight = 1.5
    else:
        weight = 1.0

    posterior = (prior_score * weight) / (prior_score * weight + (1 - prior_score))
    current_score = round(min(0.95, max(0.05, posterior)), 3)

db.execute('INSERT INTO evidence (ts, tool, zone_key, file_path, outcome, score_before, score_after) VALUES (?, ?, ?, ?, ?, ?, ?)',
           (now, tool, zone_key, fp, 'pending', prior_score, current_score))
db.commit()

# ———— 分级响应 ————
THRESH_FILE = os.path.expanduser('~/.claude/edit-guard-thresholds.json')
WARN, NUDGE, BLOCK = 0.4, 0.25, 0.15
try:
    custom = json.load(open(THRESH_FILE))
    WARN = custom.get('score_warn', 0.4)
    NUDGE = custom.get('score_nudge', 0.25)
    BLOCK = custom.get('score_block', 0.15)
except: pass

if current_score < BLOCK:
    log_event('block', f'score={current_score}')
    print(json.dumps({"decision": "block",
        "reason": f"证据评分 {current_score:.2f} < {BLOCK}。连续同类错误 {consecutive_same if 'consecutive_same' in dir() else 0} 次。写根因分析到 {CHECKPOINT} 解除。"}))
    db.close(); sys.exit(0)

elif current_score < NUDGE:
    log_event('nudge', f'score={current_score}')
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext": f"评分 {current_score:.2f} — 编辑前先输出 ROOT CAUSE。含'可能/大概'→不动代码。"}}))

elif current_score < WARN:
    log_event('warn', f'score={current_score}')
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext": f"评分 {current_score:.2f} — 确认有明确根因再继续。"}}))

if calib_age > 30:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext": f"edit-guard 已 {calib_age:.0f} 天未校准。"}}))

db.close()
