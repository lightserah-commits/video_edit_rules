#!/usr/bin/env python3
"""SessionStart フック：開始・再開・要約の後に【Addness】の案内を出す（標準出力がAIの文脈に入る）。

出すもの：全体と案件のゴールID／前回 Addness に書いた後に更新されたローカルの記録／
ゴールの無い案件フォルダ／動いていそうな別のセッション。
"""
import json
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__file__))
from addness_common import (ADDNESS_DIR, GOALS_JSON, LAST_WRITE_JSON, case_dirs, load_goals, load_json, local_records,
                            local_time, projects_log_dir)

INBOX_MD = ADDNESS_DIR / "inbox.md"


def main():
    try:
        hook = json.load(sys.stdin)
    except Exception:
        hook = {}
    session_id = hook.get("session_id", "")
    goals = load_goals()
    last = load_json(LAST_WRITE_JSON, {})

    lines = ["【Addness】このフォルダの仕事は Addness に残す（Addnessと働く.md）。"]
    root = goals.get("root_goal") or {}
    if root.get("id"):
        lines.append(f"- 全体のゴール：{root.get('title', '')}（{root['id']}）")
    else:
        lines.append("- 全体のゴールがまだ無い。" + (goals.get("pending") or "置き場をユーザーと決めて作る"))
        parent = (goals.get("parent_goal") or {}).get("id")
        if parent:
            lines.append(f"  → get_goal で {parent} を見て、「閲覧のみ」の注意が消えていたら .claude/addness/起票待ち.md のとおりに作る")
    cases = goals.get("cases") or {}
    for name, g in cases.items():
        lines.append(f"- 案件 {name}：{g.get('title', '')}（{g.get('id', '')}）")
    for key, g in (goals.get("others") or {}).items():
        lines.append(f"- {key}：{g.get('title', '')}（{g.get('id', '')}）")

    not_cases = set(goals.get("not_cases") or [])
    missing = [d for d in case_dirs() if d not in cases and d not in not_cases]
    if missing:
        lines.append("- ゴールの無い案件フォルダ：" + "、".join(missing) + "（案件なら全体のゴールの下に作り、goals.json に足す）")

    last_ts = last.get("epoch")
    if last_ts:
        lines.append(f"- 最後に Addness へ書いた時刻：{local_time(last_ts)}（{last.get('tool', '')}）")
        stale = [(rel, m) for rel, m in local_records() if m > last_ts + 60]
        if stale:
            stale.sort(key=lambda x: -x[1])
            shown = "、".join(f"{rel}（{local_time(m)[11:]}）" for rel, m in stale[:8])
            more = f" ほか{len(stale) - 8}件" if len(stale) > 8 else ""
            lines.append(f"- その後に更新されたローカルの記録：{shown}{more}"
                         "。中身を見て、Addness に無い決定・版・未確認があれば addness-kiroku をバックグラウンドで呼んで反映する")
    else:
        lines.append("- まだ一度も Addness へ書いた記録が無い（.claude/addness/last_write.json）")

    # Addness から拾った未対応の依頼（定期の実行が inbox.md に足す）
    pending_items = []
    try:
        section = None
        for line in INBOX_MD.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                section = line[3:].strip()
            elif section == "未対応" and line.strip().startswith(("-", "*")):
                pending_items.append(line.strip().lstrip("-* ").strip())
    except Exception:
        pass
    if pending_items:
        lines.append(f"- Addness から拾った未対応の依頼 {len(pending_items)}件（.claude/addness/inbox.md）：")
        lines.extend(f"  - {t[:120]}" for t in pending_items[:5])

    # 動いていそうな別のセッション（15分以内に会話の記録が更新されたもの）
    others = []
    log_dir = projects_log_dir()
    if log_dir.is_dir():
        now = time.time()
        for p in log_dir.glob("*.jsonl"):
            if p.stem == session_id:
                continue
            age = now - p.stat().st_mtime
            if age < 15 * 60:
                others.append(f"{p.stem[:8]}（{int(age // 60)}分前）")
    if others:
        lines.append("- 動いていそうな別のセッション：" + "、".join(others)
                     + "。同じ案件フォルダ・同じ Premiere を触る前に確かめる")

    lines.append("最初に：依頼に対応するゴールを get_goal_context と list_goal_memories で読む。"
                 "list_notifications（count_only）と list_todays_goals で、動画編集の新しい依頼や指示が来ていないか見る。")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # フックの失敗で作業を止めない
        print(f"【Addness】案内の作成に失敗（{e}）。Addnessと働く.md に従う。")
