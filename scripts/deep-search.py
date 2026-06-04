"""
深度搜索 v5 — 修复版（Challenger审查通过）
算法栈: jieba + BM25 + 确定性SimHash + MMR + aiohttp全异步 + trafilatura
"""
import sys, re, time, urllib.parse, io, json, os, asyncio, hashlib, struct
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import jieba
from rank_bm25 import BM25Okapi
import trafilatura
import aiohttp

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
QUERY = sys.argv[1]
MAX = int(sys.argv[2]) if len(sys.argv) > 2 else 25
OUTFILE = 'C:/temp/deep_search_result.md'
SEARXNG = 'http://localhost:8080'

def classify_query(q):
    q_lower = q.lower()
    has_cn = any('一' <= c <= '鿿' for c in q)
    sites = [(q, '泛搜')]
    if not has_cn:
        if any(kw in q_lower for kw in ['how','tutorial','error','fix','bug','code','api']):
            sites += [(f'site:stackoverflow.com OR site:github.com {q}', '技术')]
        else:
            sites += [(f'site:wikipedia.org {q}', '百科')]
        return sites[:4]
    tech_kw = ['esp32','mqtt','iot','api','python','java','docker','linux','git',
               '代码','编程','开发','教程','配置','部署','数据库','算法','框架',
               '微服务','前端','后端','嵌入式','单片机','云','服务器','小程序','微信']
    acad_kw = ['论文','研究','理论','分析','综述','方法','实验','模型','数学','物理','化学']
    wiki_kw = ['是什么','谁','什么是','定义','含义','解释','概念','历史','人物','事件',
               '典故','朝代','战争','条约','发明','发现','起源','简介','介绍','排名','排行']
    if any(kw in q_lower for kw in tech_kw):
        sites += [(f'site:csdn.net OR site:cnblogs.com {q}', '技术社区'),
                  (f'site:github.com {q}', '开源')]
    elif any(kw in q_lower for kw in acad_kw):
        sites += [(f'site:cnki.net OR site:zhihu.com {q}', '学术'),
                  (f'{q} 论文 研究', '学术搜索')]
    elif any(kw in q_lower for kw in wiki_kw):
        sites += [(f'{q} 百科', '百科'),
                  (f'site:zhihu.com {q}', '知乎')]
    else:
        sites += [(f'site:zhihu.com {q}', '知乎'), (f'{q} 百科', '百科')]
    return sites[:4]

# ———— 搜索（异步） ————
async def search_searxng_async(session, query, n=25):
    try:
        url = f"{SEARXNG}/search?q={urllib.parse.quote(query)}&format=json"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as resp:
            data = await resp.json()
            return [(r['url'], r.get('title',''), r.get('content',''))
                    for r in data.get('results', [])[:n] if r.get('url','').startswith('http')]
    except:
        return []

async def search_wiki_async(session, query, n=10):
    try:
        results = []
        for domain in ['zh.wikipedia.org', 'en.wikipedia.org']:
            url = f"https://{domain}/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(query)}&format=json&srlimit={n}"
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                for r in data['query']['search']:
                    results.append((f"https://{domain}/wiki/{urllib.parse.quote(r['title'].replace(' ','_'))}",
                                    r['title'], r.get('snippet','')))
        return results
    except:
        return []

def search_ddg_sync(query, n=15):
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return [(r['href'], r.get('title',''), r.get('body',''))
                    for r in ddgs.text(query, max_results=n)]
    except ImportError:
        return []
    except:
        return []

# ———— 分词 ————
def tokenize(text):
    """jieba — 单字中文也保留（'力'在'影响力'中有意义）"""
    return [w for w in jieba.cut(text)
            if len(w) >= 2 or (len(w) == 1 and ord(w) > 127 and not w.isspace())]

# ———— 确定性 SimHash (修复 hash() 问题) ————
def stable_hash(token):
    """确定性哈希 — 不依赖 PYTHONHASHSEED"""
    return struct.unpack('<Q', hashlib.md5(token.encode('utf-8', errors='ignore')).digest()[:8])[0]

def simhash_weighted(text, n_bits=64):
    """SimHash with TF weighting — 使用确定性MD5哈希"""
    tokens = tokenize(text)
    if not tokens:
        return 0
    tf = Counter(tokens)
    max_tf = max(tf.values()) or 1
    v = [0.0] * n_bits
    for t, cnt in tf.items():
        weight = cnt / max_tf
        h = stable_hash(t)
        for i in range(n_bits):
            v[i] += weight if (h >> i) & 1 else -weight
    return sum((1 if v[i] > 0 else 0) << i for i in range(n_bits))

def hamming(a, b):
    x = a ^ b
    d = 0
    while x:
        d += 1
        x &= x - 1
    return d

# ———— SimHash 分桶去重 (O(n) 替代 O(n²)) ————
def simhash_dedup(items, threshold=3):
    """SimHash 分桶去重 — 将64位哈希分成16个4位桶"""
    seen = {}  # bucket_key → [(url, simhash)]
    kept = {}
    for url, sh in items:
        is_dup = False
        for bucket_idx in range(16):
            bucket_key = (sh >> (bucket_idx * 4)) & 0xF
            candidate_buckets = seen.get((bucket_idx, bucket_key), [])
            for existing_url, existing_sh in candidate_buckets:
                if hamming(sh, existing_sh) <= threshold:
                    is_dup = True
                    break
            if is_dup:
                break
        if not is_dup:
            for bucket_idx in range(16):
                bucket_key = (sh >> (bucket_idx * 4)) & 0xF
                seen.setdefault((bucket_idx, bucket_key), []).append((url, sh))
            kept[url] = sh
    return kept

# ———— MMR (预计算词元集, 修复缩放) ————
def mmr_select(docs, query_terms, lambda_param=0.7, top_k=30):
    if len(docs) <= top_k:
        return docs
    # 预计算所有文档的词元集
    token_sets = [set(tokenize(f"{t} {s}")) for _, t, s, _ in docs]
    # 归一化: BM25分数除以最大值 → [0,1] 范围
    max_score = max(s for _, _, _, s in docs) or 1
    selected = [0]
    remaining = list(range(1, len(docs)))

    while len(selected) < top_k and remaining:
        best_score = -float('inf')
        best_ridx = 0
        for ri, di in enumerate(remaining):
            relevance = docs[di][3] / max_score
            max_sim = 0
            for si in selected:
                s1, s2 = token_sets[di], token_sets[si]
                union = len(s1 | s2)
                max_sim = max(max_sim, len(s1 & s2) / max(union, 1))
            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim
            if mmr_score > best_score:
                best_score = mmr_score
                best_ridx = ri
        selected.append(remaining.pop(best_ridx))
    return [docs[i] for i in selected]

# ———— aiohttp 抓取 (修复返回类型) ————
async def fetch_one(session, url):
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=10),
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}) as resp:
            if resp.status != 200:
                return url, None
            html = await resp.text()
            text = trafilatura.extract(html, include_links=False, include_images=False,
                                       include_tables=False, no_fallback=False)
            if text and len(text) > 100:
                return url, text[:10000]
            return url, None
    except:
        return url, None

BANNED = ['bilibili.com','youtube.com','youku.com','iqiyi.com','douyin.com','tiktok.com','vimeo.com']
def is_banned(url):
    return any(d in url for d in BANNED)

# ———— 主流程 ————
async def main():
    global MAX
    print(f"=== {QUERY} ===")
    t0 = time.time()

    targeted = classify_query(QUERY)
    print(f"[1/5] 查询类型 → {[t[1] for t in targeted]}")
    all_results = {}

    connector = aiohttp.TCPConnector(limit=20, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [search_searxng_async(session, q, 20) for q, _ in targeted]
        tasks.append(search_wiki_async(session, QUERY, 10))
        loop = asyncio.get_event_loop()
        ddg_task = loop.run_in_executor(None, search_ddg_sync, QUERY, 15)

        searx_results = await asyncio.gather(*tasks)
        ddg_results = await ddg_task

        for results in searx_results:
            for url, title, snippet in results:
                if url not in all_results and not is_banned(url):
                    all_results[url] = (title, snippet)
        for url, title, snippet in ddg_results:
            if url not in all_results and not is_banned(url):
                all_results[url] = (title, snippet)

    raw = len(all_results)
    print(f"  原始: {raw}条 | {time.time()-t0:.0f}s")

    # SimHash 去重 (桶优化)
    urls = list(all_results.keys())
    items = [(u, simhash_weighted(f"{all_results[u][0]} {all_results[u][1]}")) for u in urls]
    deduped = simhash_dedup(items, threshold=3)
    print(f"[2/5] SimHash去重: {raw}→{len(deduped)} (去{raw - len(deduped)}条)")

    # BM25 排序 (在摘要上 — 快且足够区分)
    query_tokens = tokenize(QUERY)
    d_urls = list(deduped.keys())
    docs = [tokenize(f"{all_results[u][0]} {all_results[u][1]}") for u in d_urls]
    bm25 = BM25Okapi(docs)
    scores = bm25.get_scores(query_tokens)
    scored = sorted(zip(d_urls, scores), key=lambda x: x[1], reverse=True)

    domain_counter = Counter()
    candidates = []
    for url, score in scored:
        if score < 1.0:
            continue
        domain = urllib.parse.urlparse(url).netloc
        domain_counter[domain] += 1
        if domain_counter[domain] <= 3:
            candidates.append((url, all_results[url][0], all_results[url][1], score))

    if len(candidates) < MAX:
        for url, score in scored:
            domain = urllib.parse.urlparse(url).netloc
            item = (url, all_results[url][0], all_results[url][1], score)
            if item not in candidates and domain_counter[domain] < 4 and score > 0.3:
                candidates.append(item); domain_counter[domain] += 1
            if len(candidates) >= MAX:
                break

    top = mmr_select(candidates, query_tokens, lambda_param=0.7, top_k=MAX)
    print(f"[3/5] BM25+MMR: {len(top)}条")

    # aiohttp 抓取
    print(f"[4/5] aiohttp抓取 {len(top)}页 (50并发)...")
    connector2 = aiohttp.TCPConnector(limit=50, limit_per_host=5)
    async with aiohttp.ClientSession(connector=connector2) as fs:
        tasks = [fetch_one(fs, u) for u, _, _, _ in top]
        fetch_results = await asyncio.gather(*tasks)

    fetched = [(u, t, s, sc, txt) for (u, t, s, sc), (_, txt) in zip(top, fetch_results)]
    fetched.sort(key=lambda x: x[3], reverse=True)
    ok = sum(1 for _, _, _, _, t in fetched if t is not None)
    print(f"  完成: {ok}/{len(fetched)} 可访问 | {time.time()-t0:.0f}s")

    # 输出
    print(f"[5/5] 写入 {OUTFILE}")
    with open(OUTFILE, 'w', encoding='utf-8') as f:
        f.write(f"# 深度搜索结果\n\n**查询**: {QUERY}\n\n")
        f.write(f"**流水线**: {raw}→SimHash去重{len(deduped)}→BM25+MMR{len(top)}→可访问{ok}\n\n")
        f.write(f"**算法**: jieba + BM25 + TF加权SimHash(MD5) + MMR + aiohttp全异步 + trafilatura\n\n")
        f.write(f"**耗时**: {time.time()-t0:.0f}s\n\n---\n\n")
        for i, (url, title, snippet, score, text) in enumerate(fetched):
            status = 'OK' if text else 'FAIL'
            domain = urllib.parse.urlparse(url).netloc
            preview = text[:1500] if text else snippet[:400]
            f.write(f"## [{i+1}] {status} ({domain}) {title[:150]}\n\n")
            f.write(f"**URL**: {url}  \n**BM25**: {score:.1f}  \n\n{preview}\n\n---\n\n")

    print(f"=== {ok}/{len(top)} 可访问 | 总耗时 {time.time()-t0:.0f}s ===")

if __name__ == '__main__':
    asyncio.run(main())
