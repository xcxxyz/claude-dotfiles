"""DeepSeek 余额缓存 — httpx + 5min缓存 + 错误处理"""
import json, os, time, sys

CACHE = os.path.expanduser('~/.claude/balance')
if os.path.exists(CACHE) and time.time() - os.path.getmtime(CACHE) < 300:
    sys.exit()

rec_path = os.path.expanduser('~/.claude/recovered-config.json')
if not os.path.exists(rec_path):
    sys.exit()

try:
    with open(rec_path, encoding='utf-8') as f:
        rc = json.load(f)
    prov = rc.get('deepseek_provider', {}).get('settings', {})
    key = prov.get('ANTHROPIC_API_KEY', '') or prov.get('ANTHROPIC_AUTH_TOKEN', '')
    if not key:
        sys.exit()

    import urllib.request
    req = urllib.request.Request('https://api.deepseek.com/user/balance')
    req.add_header('Authorization', f'Bearer {key}')
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode('utf-8'))

    for info in data.get('balance_infos', []):
        if info.get('currency') == 'CNY':
            bal = '¥{:.2f}'.format(float(info['total_balance']))
            with open(CACHE, 'w', encoding='utf-8') as f:
                f.write(bal)
            break
except Exception:
    pass  # 静默失败，不影响正常使用
