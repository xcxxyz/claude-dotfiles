"""SessionStart: 从备份恢复被 CC Switch 清掉的 settings"""
import json, os, sys

SETTINGS = os.path.expanduser('~/.claude/settings.json')
BACKUP = os.path.expanduser('~/.claude/settings-repair-backup.json')
LOG = os.path.expanduser('~/.claude/hook-repair.log')

def log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(f'[{__import__("time").strftime("%Y-%m-%d %H:%M:%S")}] {msg}\n')
    except: pass

def has_full_config(d):
    """验证 hooks 存在且有实质内容"""
    hooks = d.get('hooks', {})
    required = ['SessionStart', 'PreToolUse', 'PostToolUse', 'Stop', 'PreCompact']
    if 'statusLine' not in d:
        return False
    for k in required:
        v = hooks.get(k)
        if not v or not isinstance(v, list) or len(v) == 0:
            return False
    return True

try:
    with open(SETTINGS, encoding='utf-8') as f:
        current = json.load(f)

    if has_full_config(current):
        # 完好 → 更新备份
        backup = {k: v for k, v in current.items()
                  if k not in ('env', 'includeCoAuthoredBy')}
        with open(BACKUP, 'w', encoding='utf-8') as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)
    else:
        # 损坏 → 恢复
        if os.path.exists(BACKUP):
            with open(BACKUP, encoding='utf-8') as f:
                backup = json.load(f)
            env = current.get('env', {})
            coauth = current.get('includeCoAuthoredBy', False)
            current.update(backup)
            current['env'] = env
            current['includeCoAuthoredBy'] = coauth
            with open(SETTINGS, 'w', encoding='utf-8') as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            log('Settings restored from backup')
            print(json.dumps({"systemMessage": "Settings auto-restored."}))
except Exception as e:
    log(f'Error: {e}')
