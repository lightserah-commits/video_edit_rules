#!/usr/bin/env python3
"""Stop フック：このターンでファイルを変えたのに Addness に書いていなければ、1回だけ止めて記録を促す。

- 「書いた」＝ Addness の書き込みツール（WRITE_TOOL_RE）か、記録係 addness-kiroku を呼んだ
- 「ファイルを変えた」＝ プロジェクト内への Edit/Write、または Bash を使ったターンでプロジェクト内のファイルが更新された
  （別のセッションの変更も混ざるので、止めるのは1ターンに1回まで。記録が要らなければ一言添えて終えてよい）
"""
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from addness_common import (GOALS_JSON, PROJECT, RECORDER_AGENT, STATE_DIR, WRITE_TOOL_RE, changed_since, load_json,
                            save_json)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def is_real_user(row):
    if row.get("type") != "user" or row.get("isMeta"):
        return False
    c = (row.get("message") or {}).get("content")
    if isinstance(c, str):
        return bool(c.strip())
    if isinstance(c, list):
        return any(isinstance(x, dict) and x.get("type") in ("text", "image") for x in c) and not any(
            isinstance(x, dict) and x.get("type") == "tool_result" for x in c)
    return False


def parse_ts(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def main():
    hook = json.load(sys.stdin)
    if hook.get("stop_hook_active") or hook.get("agent_id"):
        return 0
    if not (load_json(GOALS_JSON, {}).get("root_goal") or {}).get("id"):
        return 0  # ゴールの置き場が決まるまでは止めない
    path = hook.get("transcript_path")
    if not path or not os.path.isfile(path):
        return 0
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    start = None
    for i in range(len(rows) - 1, -1, -1):
        if is_real_user(rows[i]):
            start = i
            break
    if start is None:
        return 0
    turn_id = rows[start].get("uuid", str(start))
    turn_ts = parse_ts(rows[start].get("timestamp", ""))

    recorded, edited, bash = False, [], 0
    for row in rows[start + 1:]:
        if row.get("type") != "assistant":
            continue
        for x in (row.get("message") or {}).get("content") or []:
            if not isinstance(x, dict) or x.get("type") != "tool_use":
                continue
            name, inp = x.get("name", ""), x.get("input") or {}
            if WRITE_TOOL_RE.match(name):
                recorded = True
            elif name in ("Agent", "Task") and inp.get("subagent_type") == RECORDER_AGENT:
                recorded = True
            elif name in EDIT_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path") or ""
                if fp.startswith(str(PROJECT) + os.sep) and os.sep + ".claude" + os.sep not in fp:
                    edited.append(os.path.relpath(fp, PROJECT))
            elif name == "Bash":
                bash += 1
    if recorded:
        return 0
    changed = sorted(set(edited))
    if bash and turn_ts:
        changed = sorted(set(changed) | set(changed_since(turn_ts, limit=200)))
    if not changed:
        return 0

    state_file = STATE_DIR / f"stop_{hook.get('session_id', 'unknown')}.json"
    state = load_json(state_file, {})
    if state.get("blocked_turn") == turn_id:
        return 0
    save_json(state_file, {"blocked_turn": turn_id})

    shown = "、".join(changed[:6]) + (f" ほか{len(changed) - 6}件" if len(changed) > 6 else "")
    sys.stderr.write(
        "【Addness】このターンでファイルが変わったが、Addness にまだ記録していない（" + shown + "）。\n"
        "決まったこと・分かったこと・できた版と場所・未確認・次の作業を、該当ゴールの本文か AIメモリに書いてから終える"
        "（ゴールIDは .claude/addness/goals.json。重い整理は addness-kiroku をバックグラウンドで呼ぶ）。\n"
        "記録するほどでない変更（試し・下書き）や、別のセッションの変更だけなら、その旨をユーザーへの返事に一言添えて終えてよい。\n"
    )
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
