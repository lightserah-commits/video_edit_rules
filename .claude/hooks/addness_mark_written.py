#!/usr/bin/env python3
"""PostToolUse フック：Addness に書いた時刻とゴールを記録する（SessionStart の「その後に更新された記録」に使う）。"""
import json
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__file__))
from addness_common import LAST_WRITE_JSON, WRITE_LOG, WRITE_TOOL_RE, save_json


def main():
    hook = json.load(sys.stdin)
    tool = hook.get("tool_name", "")
    if not WRITE_TOOL_RE.match(tool):
        return
    inp = hook.get("tool_input") or {}
    now = time.time()
    rec = {
        "epoch": now,
        "time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(now)),
        "tool": tool.rsplit("__", 1)[-1],
        "goal_id": inp.get("goal_id") or inp.get("parent_id") or "",
        "session_id": hook.get("session_id", ""),
    }
    save_json(LAST_WRITE_JSON, rec)
    with open(WRITE_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
