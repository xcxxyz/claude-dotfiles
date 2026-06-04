"""
PostToolUse: 编辑后即时语法验证
修复: JSONC处理、bare except、node超时
"""
import json, sys, os, ast, subprocess

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})
resp = data.get('tool_response', {})

if tool not in ('Edit', 'Write') or resp.get('error'):
    sys.exit(0)

fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
if not fp or not os.path.exists(fp):
    sys.exit(0)

ext = os.path.splitext(fp)[1].lower()
errors = []

try:
    if ext == '.py':
        with open(fp, encoding='utf-8') as f:
            ast.parse(f.read())
    elif ext == '.json':
        with open(fp, encoding='utf-8') as f:
            json.loads(f.read())
    elif ext == '.jsonc':
        # JSONC = 含注释JSON — 跳过语法检查(正则去注释会破坏URL等字符串)
        sys.exit(0)
    elif ext in ('.js',):
        result = subprocess.run(['node', '--check', fp], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            errors.append(result.stderr.strip()[:200])
except SyntaxError as e:
    errors.append(f"L{e.lineno}: {e.msg}")
except json.JSONDecodeError as e:
    errors.append(f"L{e.lineno}: {e.msg}")
except subprocess.TimeoutExpired:
    pass
except FileNotFoundError:
    pass  # node 未安装
except Exception:
    pass  # 非预期错误，不中断主流程

if errors:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse",
        "additionalContext": f"SYNTAX: {os.path.basename(fp)} — {'; '.join(errors)}"}}))
