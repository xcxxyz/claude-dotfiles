"""PreToolUse: 强制拦截 WebSearch，重定向到自部署 deep-search.py"""
import json, sys, os, shlex

data = json.load(sys.stdin)
tool = data.get('tool_name', '')

if tool != 'WebSearch':
    sys.exit(0)

query = data.get('tool_input', {}).get('query', data.get('tool_input', {}).get('searchTerm', ''))
# 安全转义查询字符串防止命令注入
safe_query = shlex.quote(query) if query else '""'

SCRIPT = 'C:/temp/deep-search.py'
script_exists = os.path.exists(SCRIPT)

msg = "禁止使用内置 WebSearch。请改用自部署深度搜索系统:\n"
if script_exists:
    msg += f"  /d/temp/dlc-env/Scripts/python {SCRIPT} {safe_query} 25\n"
else:
    msg += f"  搜索脚本缺失: {SCRIPT}\n"

print(json.dumps({
    "decision": "block",
    "reason": msg,
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "additionalContext": "WebSearch 已被拦截。使用 SearXNG 多引擎深度搜索(7引擎 + BM25 + SimHash + MMR + aiohttp)。"
    }
}))
