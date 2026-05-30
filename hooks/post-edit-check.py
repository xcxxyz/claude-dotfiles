"""PostToolUse: 编辑后安全网 — 检测错误模式，注入调试纪律"""
import json, sys

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
tool_response = data.get('tool_response', {})

if tool not in ('Write', 'Edit', 'MultiEdit'):
    sys.exit(0)

# 编辑成功，不做额外检查
if tool_response.get('success') or tool_response.get('ok'):
    sys.exit(0)

# 编辑失败或有错误 → 注入调试纪律
error_msg = tool_response.get('error', tool_response.get('message', ''))
if error_msg:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": (
                "编辑操作失败: " + str(error_msg)[:200] + "\n"
                "调试纪律:\n"
                "1. 先完整阅读错误信息，不要改代码\n"
                "2. 列出 >=3 种可能的根因\n"
                "3. 通过搜索/测试/日志逐一排除\n"
                "4. 确定根因后再动手\n"
                "5. 一次只改一处"
            )
        }
    }))
