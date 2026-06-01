"""PreToolUse: 防 fix-loop — 编辑频率控制 + 强制根因检查点 + 校准机制"""
import json, sys, os, time, re

data = json.load(sys.stdin)
tool = data.get('tool_name', '')
ti = data.get('tool_input', {})

STATE_FILE = os.path.expanduser('~/.claude/edit-guard-state.json')
GATE_FILE = os.path.expanduser('~/.claude/post-edit-gate.json')
CALIB_FILE = os.path.expanduser('~/.claude/edit-guard-calibrated')
CHECKPOINT_FILE = os.path.expanduser('~/.claude/root-cause-checkpoint.md')
LOG_FILE = os.path.expanduser('~/.claude/edit-guard-log.jsonl')

def log_event(action, detail=''):
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, 'a') as f:
            json.dump({'ts': time.time(), 'action': action, 'detail': detail}, f)
            f.write('\n')
    except:
        pass

def load_state():
    try:
        s = json.load(open(STATE_FILE))
        now = time.time()
        # 清理 >10 分钟的旧条目（_calib 保留）
        cleaned = {}
        for k, v in s.items():
            if k.startswith('_calib'):
                cleaned[k] = v
            elif now - v.get('last', 0) < 600:
                cleaned[k] = v
        return cleaned
    except:
        return {}

def save_state(s):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    json.dump(s, open(STATE_FILE, 'w'))

def get_target():
    fp = (ti.get('file_path') or ti.get('filePath') or '').replace('\\', '/')
    if tool == 'Bash':
        cmd = ti.get('command', '')
        if ('python' in cmd) and ('open(' in cmd or 'write(' in cmd):
            return 'bash:python_write'
        m = re.search(r'>\s*(\S+)', cmd)
        if m: return 'bash:' + m.group(1).replace('\\', '/')
        m = re.search(r'sed\s+-i\s+\S+\s+(\S+)', cmd)
        if m: return 'bash:' + m.group(1).replace('\\', '/')
        return ''
    return fp

target = get_target()
if not target:
    sys.exit(0)

old = ti.get('old_string', '') or ''
if old and tool == 'Edit':
    zone = old[:60] + '...' + old[-60:] if len(old) > 130 else old
    zone_key = re.sub(r'\s+', ' ', zone).strip()
    if len(zone_key) < 10:
        zone_key = target
else:
    zone_key = target

state = load_state()
now = time.time()

# ============================================================
# 1. 校准过期检查
# ============================================================
calib_age = None
if os.path.exists(CALIB_FILE):
    calib_age = (now - os.path.getmtime(CALIB_FILE)) / 86400
else:
    calib_age = 999

if calib_age and calib_age > 45:
    log_event('block_calibration', f'age={calib_age:.0f}d')
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"edit-guard 已 {calib_age:.0f} 天未校准。\n"
            "必须复查: 全局8次/同区3次是否误拦？gate 机制是否有效？\n"
            "复查后: touch ~/.claude/edit-guard-calibrated"
        )
    }))
    sys.exit(0)

if calib_age and calib_age > 30:
    if zone_key not in state.get('_calib_warned_', {}):
        state.setdefault('_calib_warned_', {})[zone_key] = True
        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": (
                    f"edit-guard 已 {calib_age:.0f} 天未校准。"
                    " 复查后 touch ~/.claude/edit-guard-calibrated。"
                )
            }
        }))

# ============================================================
# 2. 硬检查点：错误后必须写根因分析
# ============================================================
gate_active = False
try:
    gate = json.load(open(GATE_FILE))
    if gate.get('gate') and time.time() - gate.get('ts', 0) < 600:
        gate_active = True
        # 只允许 Write 到 checkpoint 文件来解除 gate
        if tool == 'Write' and target.replace('\\', '/') == CHECKPOINT_FILE.replace('\\', '/'):
            pass  # 允许写 checkpoint
        elif tool == 'Write':
            pass  # 允许 Write 到其他文件（至少换个思路）
        else:
            log_event('block_gate', 'non-write tool blocked by gate')
            print(json.dumps({
                "decision": "block",
                "reason": (
                    "HARD GATE: 上一轮出现错误。不允许 Edit/Bash。\n"
                    f"请将根因分析写入 {CHECKPOINT_FILE} 以解除。\n"
                    "说清楚: 问题/根因/已验证的假设/下一步验证方案。"
                )
            }))
            sys.exit(0)
except:
    pass

# ============================================================
# 3. 编辑频率控制
# ============================================================
entry = state.get(zone_key, {'times': [], 'total': 0})
entry['times'].append(now)
entry['total'] = entry.get('total', 0) + 1
entry['last'] = now
state[zone_key] = entry

same_zone_90s = len([t for t in entry['times'] if now - t < 90])
same_zone_5min = len([t for t in entry['times'] if now - t < 300])
total_edits_5min = sum(
    len([t for t in e['times'] if now - t < 300])
    for e in state.values()
)

save_state(state)

# 读取自动校准的阈值（如果存在）
THRESH_FILE = os.path.expanduser('~/.claude/edit-guard-thresholds.json')
try:
    custom = json.load(open(THRESH_FILE))
    TH_SZ_90 = custom.get('same_zone_90s', 3)
    TH_SZ_5M = custom.get('same_zone_5min', 5)
    TH_TOT_5M = custom.get('total_edits_5min', 8)
except:
    TH_SZ_90, TH_SZ_5M, TH_TOT_5M = 3, 5, 8

if same_zone_90s >= TH_SZ_90:
    log_event('block_same_zone_90s', f'{zone_key[:60]} x{same_zone_90s}')
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"同区 fix-loop: 90s 内编辑 '{zone_key[:80]}' {same_zone_90s} 次。"
            " 停止 → 验证假设 → 确定根因后再改。"
        )
    }))
    sys.exit(0)

if same_zone_5min >= TH_SZ_5M:
    log_event('block_same_zone_5min', f'{zone_key[:60]} x{same_zone_5min}')
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"同区 fix-loop: 5min 内编辑 '{zone_key[:80]}' {same_zone_5min} 次。"
            " 先输出 ROOT CAUSE。"
        )
    }))
    sys.exit(0)

if total_edits_5min >= TH_TOT_5M:
    log_event('block_global', f'total={total_edits_5min}')
    print(json.dumps({
        "decision": "block",
        "reason": (
            f"全场散弹 fix-loop: 5min 内跨文件编辑了 {total_edits_5min} 次。"
            " 同一未解决问题 → 停手 → 列出假设 → 验证 → 确定根因。"
        )
    }))
    sys.exit(0)

if same_zone_90s >= 2:
    log_event('warn_same_zone', f'{zone_key[:60]} x{same_zone_90s}')
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                f"WARNING: 90s 内同区编辑了 {same_zone_90s} 次。"
                " 确认不是 fix-loop。"
            )
        }
    }))

# === 每次 Edit 前注入 HARD GATE（arXiv:2510.05106 "hot reloading"） ===
# === 每次 Edit 前注入 HARD GATE ===
# 依据: Liu et al., "Lost in the Middle" (TACL 2024) — LLM U型注意力偏差,
# 上下文中间的信息被忽略; 规则放在结尾(recency bias)恢复注意力。
# 业界称 "Sticky Note Pattern"。
if tool == 'Edit':
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": (
                "HARD GATE (最高优先级 — arXiv:2510.05106 hot reload):\n"
                "在任何改动之前，先输出 ROOT CAUSE: [一句话]。\n"
                "含'可能/大概/或许/likely/possibly' → 根因未确定 → 不动代码。\n"
                "≥3 文件或 >20 行的改动 → 必须先 spawn challenger 审查。\n"
                "列出 ≥3 个当前假设，标注 [已验证] 或 [猜测]。[猜测] 先验证。\n"
                "不行动也是成功。问题不存在或假设被证伪，走开就是正确。\n"
                "调试: 改两轮还不行 → 立刻停手。先排除环境/配置/版本。\n"
                "验证脚本的 OK 不等于真成功 — 确认返回码/状态码是真正的成功值。"
            )
        }
    }))
