import time, json, os, urllib.request

CACHE = os.path.expanduser('~/.claude/balance')
while True:
    try:
        r = json.load(open(os.path.expanduser('~/.claude/recovered-config.json')))
        k = r['deepseek_provider']['settings']['ANTHROPIC_API_KEY']
        q = urllib.request.Request('https://api.deepseek.com/user/balance')
        q.add_header('Authorization', f'Bearer {k}')
        b = json.loads(urllib.request.urlopen(q, timeout=5).read())
        for x in b.get('balance_infos', []):
            if x.get('currency') == 'CNY':
                bal = 'Y{:.2f}'.format(float(x['total_balance']))
                with open(CACHE, 'w') as f:
                    f.write(bal)
                break
    except:
        pass
    time.sleep(30)
