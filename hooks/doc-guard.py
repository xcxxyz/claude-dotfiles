"""
PreToolUse: 陌生库检测 → 提醒查文档
修复: 缓存扫描结果、移除dead code、精确正则、Python版本兼容
"""
import json, sys, os, re, glob, time

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

# ———— 缓存机制 (60秒内不重扫) ————
CACHE_FILE = os.path.expanduser('~/.claude/doc-guard-cache.json')
KNOWN_LIBS = set()
PROJECT_DIR = os.getcwd()

def scan_known_libs():
    now = time.time()
    try:
        if os.path.exists(CACHE_FILE):
            cache = json.load(open(CACHE_FILE))
            if now - cache.get('ts', 0) < 60:
                return set(cache.get('libs', []))
    except: pass

    libs = set()
    # requirements.txt / package.json
    for pat in ['**/requirements*.txt', '**/package.json']:
        for f in glob.iglob(pat, recursive=True):
            try:
                fp = os.path.join(PROJECT_DIR, f)
                with open(fp, encoding='utf-8', errors='ignore') as fh:
                    content = fh.read()
                if f.endswith('.txt'):
                    for m in re.finditer(r'^([a-zA-Z_][\w\-_]+)', content, re.M):
                        libs.add(m.group(1))
                elif f.endswith('.json'):
                    deps = json.loads(content).get('dependencies', {})
                    libs.update(deps.keys())
                    dev = json.loads(content).get('devDependencies', {})
                    libs.update(dev.keys())
            except: pass

    # 项目内import (只扫描.py文件的前100行，够用且快)
    for f in glob.iglob('**/*.py', recursive=True):
        try:
            with open(os.path.join(PROJECT_DIR, f), encoding='utf-8', errors='ignore') as fh:
                for i, line in enumerate(fh):
                    if i > 100: break
                    if line.strip().startswith('#'): continue
                    if '"""' in line or "'''" in line: continue
                    m = re.match(r'^\s*(?:import|from)\s+(\w+)', line)
                    if m and not m.group(1).startswith('_'):
                        libs.add(m.group(1))
        except: pass

    # 标准库 + 常见库
    libs.update(['os','sys','re','json','time','datetime','collections','itertools',
                  'functools','typing','math','random','pathlib','subprocess','hashlib',
                  'urllib','http','sqlite3','csv','io','logging','argparse','threading',
                  'asyncio','concurrent','socket','email','xml','html','unittest','pytest',
                  'numpy','pandas','torch','tensorflow','sklearn','flask','django',
                  'requests','aiohttp','jieba','bs4','trafilatura','yaml','toml'])

    # 写缓存
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        json.dump({'ts': now, 'libs': sorted(libs)}, open(CACHE_FILE, 'w'))
    except: pass

    return libs

KNOWN_LIBS = scan_known_libs()

# ———— 检测（仅在 pip/npm install 时触发，导入不触发——减少噪音） ————
text = ''
if tool == 'Bash':
    text = ti.get('command', '')

if not text:
    sys.exit(0)

found = set()
for m in re.finditer(r'(?:pip|pip3|python\s+-m\s+pip)\s+(?:install|add)\s+(\S+)', text):
    pkg = re.split(r'[=<>!~\[\s]', m.group(1))[0].strip()
    if pkg and pkg not in KNOWN_LIBS: found.add(pkg)
for m in re.finditer(r'(?:npm|pnpm|yarn)\s+(?:install|add)\s+(\S+)', text):
    pkg = re.split(r'[@\s]', m.group(1))[0].strip()
    if pkg and pkg not in KNOWN_LIBS: found.add(pkg)

new_libs = found - {'os','sys','re','json','time','datetime','collections','itertools',
                     'functools','typing','math','random','pathlib','subprocess','hashlib'}

if new_libs:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "additionalContext": f"陌生库: [{', '.join(sorted(new_libs)[:5])}]。建议先查文档或搜索用法再安装。"}}))
