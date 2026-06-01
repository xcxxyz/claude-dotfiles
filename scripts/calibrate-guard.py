"""读 edit-guard 日志，自动校准阈值。每 30 天由 SessionStart hook 触发。"""
import json, os, sys, time
from collections import defaultdict

LOG_FILE = os.path.expanduser('~/.claude/edit-guard-log.jsonl')
CALIB_FILE = os.path.expanduser('~/.claude/edit-guard-calibrated')
STATE_FILE = os.path.expanduser('~/.claude/edit-guard-state.json')
GATE_STATE = os.path.expanduser('~/.claude/post-edit-error-state.json')

THRESHOLDS = {
    'same_zone_90s': 3,      # 同区 90s 最大编辑次数
    'same_zone_5min': 5,     # 同区 5min 最大编辑次数
    'total_edits_5min': 8,   # 全场 5min 最大编辑次数
}

def load_logs():
    if not os.path.exists(LOG_FILE):
        return []
    logs = []
    with open(LOG_FILE) as f:
        for line in f:
            try: logs.append(json.loads(line))
            except: pass
    return logs

logs = load_logs()
if not logs:
    print("no logs yet")
    sys.exit(0)

now = time.time()
recent = [l for l in logs if now - l['ts'] < 30 * 86400]

# --- 统计 ---
blocks = [l for l in recent if l['action'].startswith('block_')]
warns = [l for l in recent if l['action'].startswith('warn_')]
gate_sets = [l for l in recent if l['action'] == 'gate_set']
gate_clears = [l for l in recent if l['action'] == 'gate_clear']

# 代理指标：gate set 后多久 clear
gate_pairs = []
for gs in gate_sets:
    clears = [gc for gc in gate_clears
              if 0 < gc['ts'] - gs['ts'] < 600]  # 10min 内
    if clears:
        gate_pairs.append(min(c['ts'] for c in clears) - gs['ts'])

# gate 设置后 2min 内未 clear = 可能真的在写根因分析（有效阻断）
# gate 设置后 20s 内 clear = 可能绕过（无效阻断）
quick_clears = sum(1 for d in gate_pairs if d < 20)
valid_gates = sum(1 for d in gate_pairs if d >= 20)

# 总编辑次数 vs 阻断次数
total_edits_30d = sum(
    len([t for t in e.get('times', []) if now - t < 30 * 86400])
    for e in [{}] + []  # placeholder — 实际需要读 STATE_FILE 历史
)
# 简化：用日志里的 block 次数估算
block_rate = len(blocks) / max(len(recent), 1)

# --- 自动调整规则 ---
adjustments = {}

# 1. 如果 block_rate > 30%（每3次编辑被拦1次 = 太多误拦）
if block_rate > 0.3 and len(blocks) >= 10:
    # 放宽全局阈值
    adjustments['total_edits_5min'] = THRESHOLDS['total_edits_5min'] + 2
    adjustments['same_zone_5min'] = THRESHOLDS['same_zone_5min'] + 1

# 2. 如果有过多"快速绕过"（gate set 后 20s 内 clear = 没写根因就解除了）
bypass_rate = quick_clears / max(valid_gates + quick_clears, 1)
if bypass_rate > 0.5 and len(gate_pairs) >= 5:
    # gate 机制被绕过了 → 警示（自动调不了这个，需要人工）
    adjustments['_alert'] = f'gate 绕过率 {bypass_rate:.0%}，需人工检查'

# --- 写结果 ---
result = {
    'ts': now,
    'period_days': 30,
    'logs_analyzed': len(recent),
    'blocks': len(blocks),
    'warns': len(warns),
    'gate_sets': len(gate_sets),
    'gate_clears': len(gate_clears),
    'gate_median_clear_time': sorted(gate_pairs)[len(gate_pairs)//2] if gate_pairs else None,
    'block_rate': round(block_rate, 3),
    'bypass_rate': round(bypass_rate, 3),
    'auto_adjustments': adjustments,
}

# 写入校准状态
os.makedirs(os.path.dirname(CALIB_FILE), exist_ok=True)
json.dump({'ts': now, 'auto': True, 'stats': result},
          open(CALIB_FILE, 'w'))

# 如果有自动调整，写入新阈值
if any(k in THRESHOLDS for k in adjustments):
    new_thresholds = dict(THRESHOLDS)
    for k, v in adjustments.items():
        if k in THRESHOLDS:
            new_thresholds[k] = v
    print(json.dumps({
        'adjusted': {k: v for k, v in new_thresholds.items()
                     if v != THRESHOLDS[k]},
        'current': THRESHOLDS
    }))
    # 写新阈值供 edit-guard 读取
    thresh_file = os.path.expanduser('~/.claude/edit-guard-thresholds.json')
    json.dump(new_thresholds, open(thresh_file, 'w'))

print(json.dumps(result, indent=2))
