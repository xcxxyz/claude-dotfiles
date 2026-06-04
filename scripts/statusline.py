"""Claude Code statusline"""
import sys, json, os, time

sys.stdout.reconfigure(encoding='utf-8')

try:
    raw = sys.stdin.read()
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        d = json.loads(raw.replace('\\', '/'))

    model = d.get('model', {}).get('display_name', 'DeepSeek')
    if 'opus' in model.lower():
        model = 'DeepSeek-v4-pro[1m]'

    pct = int(float(d.get('context_window', {}).get('used_percentage', 0) or 0))
    ws = d.get('workspace', {}).get('current_dir', '').replace('\\', '/')

    filled = pct * 10 // 100
    bar = '\033[42m' + ' ' * filled + '\033[0m\033[48;5;238m' + ' ' * (10 - filled) + '\033[0m'

    bal = '--'
    cf = os.path.expanduser('~/.claude/balance')
    if os.path.exists(cf) and time.time() - os.path.getmtime(cf) < 300:
        try:
            v = open(cf, encoding='utf-8').read().strip()
            bal = v
        except:
            pass

    print(f'{ws} | {model} | {bar} {pct}% | {bal}')
except Exception:
    print('-- | -- | [loading] | --')
