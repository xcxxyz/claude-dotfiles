import sys, json, os, re, urllib.request

# --- parse stdin ---
data = sys.stdin.read()
data = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', data)
d = json.loads(data)

m = d.get('model', {}).get('display_name', '')
p = int(float(d.get('context_window', {}).get('used_percentage', 0) or 0))
n = os.path.basename(d.get('workspace', {}).get('current_dir', ''))

# --- ANSI progress bar ---
w, f = 10, p * 10 // 100
bar = '\033[42m' + ' ' * f + '\033[0m\033[100m' + ' ' * (w - f) + '\033[0m'

# --- balance (call API, 2s timeout) ---
bal = '--'
try:
    r = json.load(open(os.path.expanduser('~/.claude/recovered-config.json')))
    k = r['deepseek_provider']['settings']['ANTHROPIC_API_KEY']
    q = urllib.request.Request('https://api.deepseek.com/user/balance')
    q.add_header('Authorization', f'Bearer {k}')
    b = json.loads(urllib.request.urlopen(q, timeout=2).read())
    for x in b.get('balance_infos', []):
        if x.get('currency') == 'CNY':
            bal = f'Y{float(x["total_balance"]):.2f}'
except:
    pass

print(f'{n} | {m} | {bar} {p}% | {bal}')
