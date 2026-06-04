"""SessionStart: 全量修复被 CC Switch 清掉的 settings（从备份恢复）"""
import json, os

SETTINGS = os.path.expanduser('~/.claude/settings.json')
BACKUP = os.path.expanduser('~/.claude/settings-repair-backup.json')

def has_full_config(d):
    hooks = d.get('hooks', {})
    return (
        'statusLine' in d
        and all(k in hooks for k in ['SessionStart', 'PreToolUse', 'PostToolUse', 'Stop', 'PreCompact'])
    )

try:
    d = json.load(open(SETTINGS, encoding='utf-8'))

    if has_full_config(d):
        # 完好 → 更新备份（不含 env，保留 CC Switch 管理的部分）
        backup = {k: v for k, v in d.items()
                  if k not in ('env', 'includeCoAuthoredBy')}
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        json.dump(backup, open(BACKUP, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    else:
        # 被洗掉 → 恢复
        if os.path.exists(BACKUP):
            backup = json.load(open(BACKUP, encoding='utf-8'))
            # 保留 env 和 includeCoAuthoredBy（CC Switch 管理的）
            env = d.get('env', {})
            coauth = d.get('includeCoAuthoredBy', False)
            d.update(backup)
            d['env'] = env
            d['includeCoAuthoredBy'] = coauth
            json.dump(d, open(SETTINGS, 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
            print(json.dumps({
                "systemMessage": "Settings auto-restored. statusLine + all hooks recovered."
            }))
except:
    pass
