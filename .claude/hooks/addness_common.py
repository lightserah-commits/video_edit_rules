"""Addness のフックで共通に使うもの（ゴールIDの表・最後に書いた時刻・ローカルの記録）。

標準ライブラリだけ（Python 3.9）。フックは失敗しても作業を止めないよう、呼ぶ側で例外を握りつぶす。
"""
import json
import os
import re
import time
from pathlib import Path

PROJECT = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
ADDNESS_DIR = PROJECT / ".claude" / "addness"
GOALS_JSON = ADDNESS_DIR / "goals.json"
CASES_LOCAL_JSON = ADDNESS_DIR / "cases_local.json"   # その Mac で足した案件（Git に入れない。2026-09-28 iMac と共有するため）


def load_goals():
    """goals.json（Git で共有）に、その Mac の cases_local.json の案件を足したもの"""
    try:
        g = json.load(open(GOALS_JSON, encoding="utf-8"))
    except (OSError, ValueError):
        g = {}
    try:
        local = json.load(open(CASES_LOCAL_JSON, encoding="utf-8"))
    except (OSError, ValueError):
        local = {}
    cases = dict(g.get("cases") or {})
    cases.update(local.get("cases") or local)
    g["cases"] = {k: v for k, v in cases.items() if isinstance(v, dict)}
    return g
LAST_WRITE_JSON = ADDNESS_DIR / "last_write.json"
WRITE_LOG = ADDNESS_DIR / "write_log.jsonl"
STATE_DIR = ADDNESS_DIR / "state"

# Addness に「書いた」とみなすツール（サーバー名は環境で違うので末尾で見る）
WRITE_TOOL_RE = re.compile(
    r"^mcp__.+__(write_goal_detail|edit_goal_detail|append_goal_memory|update_goal|create_goal|complete_goal)$"
)
RECORDER_AGENT = "addness-kiroku"

# ローカルの記録（Addness に反映すべき中身が書かれるファイル）
RULE_FILES = [
    "作業状況.md", "編集の依頼文.md", "README.md", "00_上司ルールとの対応表.md", "01_判断フロー.md",
    "02_演出パターン.yaml", "03_SEカタログ.yaml", "04_ズーム・BGM・テンポ.yaml", "05_アニメーション.yaml",
    "06_テロップの大きさ.yaml", "07_画面共有とワイプ.yaml", "08_カットと字幕の追加ルール.yaml", "09_図解.md",
    "見本/README.md", "見本/型一覧.md",
]

# 変更を数えないもの（素材・Premiere の副産物・フックの状態）
SKIP_DIRS = {".claude", "みかみ案件", "recording", "__pycache__", "Adobe Premiere Pro Audio Previews",
             "Adobe Premiere Pro Auto-Save", ".git"}
SKIP_SUFFIXES = (" Masks",)
SKIP_FILES = {".DS_Store"}


def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def local_time(ts):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(ts))


def case_edit_dirs():
    """案件名 → AI の作業場（Path）。.claude/addness/goals.json の cases[].edit（案件フォルダの中の edit/）。
    書かれていない古い案件は work/（案件置き場へのリンク）の下を見る（2026-09-28）"""
    out = {}
    g = load_goals()
    cases, skip = g.get("cases", {}), set(g.get("not_cases", []))
    for name, c in cases.items():
        if isinstance(c, dict) and c.get("edit") and Path(c["edit"]).expanduser().is_dir():
            out[name] = Path(c["edit"]).expanduser()
    work = PROJECT / "work"
    if work.is_dir():
        for p in work.iterdir():
            if p.is_dir() and not p.name.startswith((".", "_")) and p.name not in out and p.name not in skip:
                out[p.name] = p
    return out


def case_dirs():
    return sorted(case_edit_dirs())


def local_records():
    """Addness に反映すべき中身が書かれるローカルのファイル（パス, 更新時刻）。"""
    out = []
    for rel in RULE_FILES:
        p = PROJECT / rel
        if p.is_file():
            out.append((rel, p.stat().st_mtime))
    for name, base in case_edit_dirs().items():
        for p in [base / "00_案件メモ.md"] + sorted(base.glob("v*/確認_v*.md")):
            if p.is_file():
                out.append((f"[{name}] {p.relative_to(base)}", p.stat().st_mtime))   # 案件の記録は「[案件ID] 作業場の中のパス」
    return out


def changed_since(ts, limit=None):
    """ts より後に更新されたプロジェクト内のファイル（素材・副産物・.claude は除く）。"""
    found = []
    for root, dirs, files in os.walk(PROJECT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES)]
        for fn in files:
            if fn in SKIP_FILES:
                continue
            p = os.path.join(root, fn)
            try:
                if os.stat(p).st_mtime > ts:
                    found.append(os.path.relpath(p, PROJECT))
            except OSError:
                pass
        if limit and len(found) >= limit:
            break
    # work は案件置き場（~/Movies/video_edit_cases/）へのリンクで os.walk は入らないので、案件の記録（00_案件メモ.md・確認_vNNN.md）だけ見る
    for rel, mt in local_records():
        if rel.startswith("[") and mt > ts and rel not in found:
            found.append(rel)
    return found


def projects_log_dir():
    slug = re.sub(r"[^A-Za-z0-9]", "-", str(PROJECT))
    return Path.home() / ".claude" / "projects" / slug
