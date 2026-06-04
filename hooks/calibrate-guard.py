"""
自动校准 edit-guard 贝叶斯阈值 — 信号检测论

指标:
  FPR = 误拦率 (blocks where user immediately bypassed)
  FNR ≈ 漏拦率 (fix-loop chains NOT interrupted)
  cost = α * FPR + β * FNR  (α=2: 误拦代价2倍于漏拦)

调整:
  高FPR → 收紧阈值 (更难触发拦截)
  高FNR → 放宽阈值 (更容易触发拦截)
  低事件率 → 衰减至默认值
"""
import json, os, sys, time, sqlite3

LOG_FILE = os.path.expanduser('~/.claude/edit-guard-log.jsonl')
CALIB_FILE = os.path.expanduser('~/.claude/edit-guard-calibrated')
DB = os.path.expanduser('~/.claude/edit-guard-v2.db')
THRESH_FILE = os.path.expanduser('~/.claude/edit-guard-thresholds.json')
DEFAULT = {'score_warn': 0.4, 'score_nudge': 0.25, 'score_block': 0.15}
ALPHA, BETA = 2.0, 1.0  # 误拦代价2倍于漏拦
SIGNIFICANCE = 5  # 最少事件数才触发调整

def load_logs():
    if not os.path.exists(LOG_FILE): return []
    logs = []
    with open(LOG_FILE) as f:
        for line in f:
            try: logs.append(json.loads(line))
            except: pass
    return logs

def load_evidence():
    try:
        db = sqlite3.connect(DB)
        rows = db.execute(
            "SELECT ts, outcome, error_sig, file_path, score_before, score_after FROM evidence WHERE ts > ? ORDER BY id",
            (time.time() - 30 * 86400,)).fetchall()
        db.close()
        return rows
    except: return []

logs = load_logs()
evidence = load_evidence()
now = time.time()

recent_logs = [l for l in logs if now - l['ts'] < 30 * 86400]
blocks = [l for l in recent_logs if l['action'].startswith('block_')]
gate_sets = [l for l in recent_logs if l['action'] == 'gate_set']
gate_clears = [l for l in recent_logs if l['action'] == 'gate_clear']

# ———— 门禁配对 (时间排序匹配) ————
sorted_gates = sorted(gate_sets, key=lambda x: x['ts'])
sorted_clears = sorted(gate_clears, key=lambda x: x['ts'])
gate_pairs = []
ci = 0
for gs in sorted_gates:
    while ci < len(sorted_clears) and sorted_clears[ci]['ts'] <= gs['ts']:
        ci += 1
    if ci < len(sorted_clears) and sorted_clears[ci]['ts'] - gs['ts'] < 600:
        gate_pairs.append(sorted_clears[ci]['ts'] - gs['ts'])
        ci += 1

# 误拦: 30s内清除
false_positives = sum(1 for d in gate_pairs if d < 30)
true_positives = sum(1 for d in gate_pairs if d >= 30)

# ———— 漏拦检测 (从evidence链) ————
missed_runs = 0
if evidence:
    streak = 0
    last_sig = None
    for e in evidence:
        outcome = e[1]
        sig = e[2]
        if outcome and 'error' in outcome:
            if sig == last_sig:
                streak += 1
            else:
                if streak >= 3:  # 3次同错误未被拦截 = 漏拦
                    missed_runs += 1
                streak = 0
                last_sig = sig
        elif outcome == 'success':
            streak = 0
            last_sig = None
    if streak >= 3:
        missed_runs += 1

total_error_events = len([e for e in evidence if e[1] and 'error' in e[1]])
total_interventions = false_positives + true_positives

# ———— 信号检测指标 ————
fpr = false_positives / max(total_interventions, 1)
fnr = missed_runs / max(total_interventions + missed_runs, 1)
block_rate = len(blocks) / max(len(recent_logs), 1)

# 代价函数
cost = ALPHA * fpr + BETA * fnr

# ———— 阈值调整 ————
current = dict(DEFAULT)
try: current.update(json.load(open(THRESH_FILE)))
except: pass

adjustments = {}

# FPR优先: 高FPR + 高FNR同时出现 → 先收紧(减少误拦)，用更小的步长调FNR
if fpr > 0.4 and missed_runs >= 2:
    # 两个条件都触发，用折中值
    adjustments['score_block'] = round(max(0.05, current['score_block'] - 0.02), 2)
    adjustments['score_nudge'] = round(max(0.1, current['score_nudge'] - 0.01), 2)
elif fpr > 0.4 and total_interventions >= SIGNIFICANCE:
    adjustments['score_block'] = round(max(0.05, current['score_block'] - 0.05), 2)
    adjustments['score_nudge'] = round(max(0.1, current['score_nudge'] - 0.03), 2)
elif missed_runs >= 2 and total_interventions >= SIGNIFICANCE:
    adjustments['score_block'] = round(min(0.3, current['score_block'] + 0.05), 2)
    adjustments['score_nudge'] = round(min(0.4, current['score_nudge'] + 0.03), 2)

# 长期低block_rate + 充足样本 → 衰减至默认
if block_rate < 0.02 and len(recent_logs) > 100:
    for k in DEFAULT:
        if current.get(k, 0) != DEFAULT[k]:
            adjustments[k] = round(current[k] + (DEFAULT[k] - current[k]) * 0.3, 2)

# ———— 写结果 ————
result = {
    'ts': now, 'period_days': 30,
    'evidence_count': len(evidence),
    'logs_analyzed': len(recent_logs),
    'interventions': total_interventions,
    'false_positives': false_positives, 'true_positives': true_positives,
    'missed_fix_loop_runs': missed_runs,
    'fpr': round(fpr, 3), 'fnr': round(fnr, 3),
    'cost': round(cost, 3), 'alpha': ALPHA, 'beta': BETA,
    'block_rate': round(block_rate, 3),
    'adjustments': adjustments,
}

os.makedirs(os.path.dirname(CALIB_FILE), exist_ok=True)
json.dump({'ts': now, 'auto': True, 'algorithm': 'signal_detection_theory_v2', 'stats': result},
          open(CALIB_FILE, 'w'))

if adjustments:
    new_thresh = dict(current)
    new_thresh.update({k: v for k, v in adjustments.items() if k in DEFAULT})
    json.dump(new_thresh, open(THRESH_FILE, 'w'))
    print(json.dumps({'cost_before': round(cost, 3), 'adjusted': adjustments, 'new': new_thresh}))
else:
    print("no adjustments needed")

print(json.dumps(result, indent=2))
