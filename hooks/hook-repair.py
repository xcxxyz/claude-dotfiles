"""SessionStart: 检测并修复被 CC Switch 清掉的 hooks"""
import json, os

SETTINGS = os.path.expanduser('~/.claude/settings.json')

REQUIRED_HOOK = {
    "PreToolUse": [{
        "matcher": "Write|Edit|Bash",
        "hooks": [{"type": "command", "command": "python C:/temp/edit-guard.py", "timeout": 10}]
    }],
    "PostToolUse": [{
        "matcher": "Write|Edit|MultiEdit",
        "hooks": [{"type": "command", "command": "python C:/temp/post-edit-check.py", "timeout": 10}]
    }]
}

try:
    d = json.load(open(SETTINGS, encoding='utf-8'))
    hooks = d.get('hooks', {})
    repaired = False

    for key, value in REQUIRED_HOOK.items():
        if key not in hooks:
            hooks[key] = value
            repaired = True

    if repaired:
        d['hooks'] = hooks
        json.dump(d, open(SETTINGS, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
except:
    pass
