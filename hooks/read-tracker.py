"""
PostToolUse: 追踪所有文件查看操作 (Read/Grep/Glob)
Grep 和 Glob 同样暴露了文件内容，应被视为"已查看"
"""
import json, sys, os, time, sqlite3

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})
resp = data.get('tool_response', {})

DB = os.path.expanduser('~/.claude/read-tracker.db')
now = time.time()

def record(fp):
    try:
        mtime = os.path.getmtime(fp) if os.path.exists(fp) else now
    except:
        mtime = now
    try:
        os.makedirs(os.path.dirname(DB), exist_ok=True)
        db = sqlite3.connect(DB)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS reads (file_path TEXT PRIMARY KEY, mtime REAL, ts REAL)')
        db.execute('INSERT OR REPLACE INTO reads VALUES (?, ?, ?)', (fp, mtime, now))
        db.commit()
        db.close()
    except: pass

if tool == 'Read':
    fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
    if fp and not resp.get('error'):
        record(fp)

elif tool == 'Grep':
    path = (ti.get('path') or '.')
    if os.path.isfile(path):
        record(path.replace('\\', '/'))

elif tool == 'Glob':
    pattern = ti.get('pattern', '')
    path = ti.get('path', '.')
    # 精确文件匹配 → 记录目录下的所有文件
    if pattern and not ('*' in pattern or '?' in pattern) and os.path.exists(os.path.join(path, pattern)):
        fp = os.path.join(path, pattern)
        if os.path.isfile(fp):
            record(fp.replace('\\', '/'))
