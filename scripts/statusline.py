"""Claude Code statusline"""
import sys, json, os, time, re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

try:
    raw = sys.stdin.read().replace('\\', '/')
    d = json.loads(raw)

    model = d.get('model', {}).get('display_name', '--')

    # 去重末尾 [1m] — Claude Code 自动追加了一个
    model = re.sub(r'\[1m\]\[1m\]$', '[1m]', model)

    pct = int(float(d.get('context_window', {}).get('used_percentage', 0) or 0))
    ws = d.get('workspace', {}).get('current_dir', '')

    parts = [p for p in ws.split('/') if p]
    ws_short = '/'.join(parts[-2:]) if len(parts) >= 2 else (parts[-1] if parts else '--')

    filled = pct * 10 // 100
    # 绿色已用 + 深灰未用(256色)
    bar = '\033[42m' + ' ' * filled + '\033[0m\033[48;5;238m' + ' ' * (10 - filled) + '\033[0m'

    bal = '--'
    cf = os.path.expanduser('~/.claude/balance')
    if os.path.exists(cf) and time.time() - os.path.getmtime(cf) < 300:
        try:
            v = open(cf, encoding='utf-8').read().strip()
            if v.startswith('¥'): bal = v
        except: pass

    print(f'{ws_short} | {model} | {bar} {pct}% | {bal}')
except Exception:
    print('-- | -- | [loading] | --')
