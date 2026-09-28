#!/usr/bin/env python3
"""Premiere Pro に入っている「MCP Bridge (CEP)」パネル経由で、Premiere のスクリプト（ExtendScript）を実行する。

仕組み:
  パネルは共有フォルダ（既定 /tmp/premiere-mcp-bridge）を見張っていて、command-<id>.json を見つけると
  中の script を Premiere 内で実行し、結果を response-<id>.json に書き戻す。
  動いている間は bridge-heartbeat.json を更新し続ける（started: true ならブリッジ開始済み）。
  これは premiere-mcp（MCPサーバー）が内部でやっているのと同じやり取り。

使い方（Pythonから）:
  from premiere_bridge import run
  result = run('(function(){ return JSON.stringify({name: app.project.name}); })();')

使い方（コマンドラインから）:
  python3 premiere_bridge.py status
  python3 premiere_bridge.py run script.jsx
  python3 premiere_bridge.py clear-stale   … 送った側がもう待っていない古い命令を stale/ へ移す

古い命令について:
  パネルは命令を実行し終えてから command-<id>.json を消す。送った側が途中で止まる（Premiere が落ちた・中断した）と
  ファイルが残り、次にパネルが動いた時（ユーザーがプロジェクトを開いた時）に実行される。
  「保存して閉じる」命令が残ると、開くたびに閉じる（2026-09-27 v009）。status と preflight が知らせる。
"""
import json
import os
import sys
import time
import uuid

BRIDGE_DIR = os.environ.get("PREMIERE_BRIDGE_DIR", "/tmp/premiere-mcp-bridge")
HEARTBEAT = "bridge-heartbeat.json"


def heartbeat():
    """パネルの生存確認。(新しい, 開始済み) を返す。"""
    try:
        with open(os.path.join(BRIDGE_DIR, HEARTBEAT)) as f:
            beat = json.load(f)
        fresh = (time.time() * 1000 - beat.get("t", 0)) < 2500
        return fresh, bool(beat.get("started"))
    except (OSError, ValueError):
        return False, False


def premiere_processes():
    """起動中の Premiere 本体（例: "Adobe Premiere Pro 2026"）の一覧"""
    import subprocess
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,command="], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    found = []
    for line in out.splitlines():
        pid, _, cmd = line.strip().partition(" ")
        tail = cmd.split("/Contents/MacOS/")[-1] if "/Contents/MacOS/" in cmd else ""
        if tail.startswith("Adobe Premiere Pro") and cmd.split("/Contents/MacOS/")[0].endswith(tail + ".app"):
            found.append({"pid": int(pid), "app": tail})
    return found


def heartbeat_writers(seconds=2.0):
    """心拍ファイルを書いているパネルの数の見積もり。パネルは250msごとに書くので、1秒あたりの書き込み回数から数える。"""
    stamps, end = set(), time.time() + seconds
    while time.time() < end:
        try:
            with open(os.path.join(BRIDGE_DIR, HEARTBEAT)) as f:
                stamps.add(json.load(f).get("t"))
        except (OSError, ValueError):
            pass
        time.sleep(0.02)
    return round(len(stamps) / (seconds * 4))


STALE_MARGIN = 10  # 送った側の待ち時間を過ぎてから、残りものと見なすまでの秒数


def pending_commands():
    """共有フォルダに残っている命令の一覧。送った側の待ち時間（timeoutMs）を過ぎても残っているものは stale（誰も待っていない）。"""
    import re
    found = []
    try:
        names = sorted(os.listdir(BRIDGE_DIR))
    except OSError:
        return found
    for name in names:
        if not (name.startswith("command-") and name.endswith(".json")):
            continue
        path = os.path.join(BRIDGE_DIR, name)
        try:
            age = time.time() - os.path.getmtime(path)
            with open(path, encoding="utf-8") as f:
                cmd = json.load(f)
        except (OSError, ValueError):
            continue
        script = str(cmd.get("script", ""))
        projs = [p for p in re.findall(r'"([^"]+\.prproj)"', script) if "..." not in p]  # 補助関数の説明の例は除く
        found.append({"file": name, "sent": cmd.get("timestamp"), "age_sec": round(age),
                      "stale": age > cmd.get("timeoutMs", 60000) / 1000 + STALE_MARGIN,
                      "prproj": projs[0] if projs else None,
                      "closes_project": "closeDocument" in script})
    return found


def stale_warning(cmds):
    stale = [c for c in cmds if c["stale"]]
    if not stale:
        return None
    closing = [c for c in stale if c["closes_project"]]
    return (f"送った側がもう待っていない命令が{len(stale)}件残っています。次にプロジェクトを開いた時に実行されます"
            + (f"（うち{len(closing)}件はプロジェクトを閉じる命令。開いた直後に閉じる原因になる）" if closing else "")
            + "。中身を確かめてから python3 tools/premiere_bridge.py clear-stale で片付けてください")


def clear_stale():
    """stale な命令を BRIDGE_DIR/stale/ へ移す（パネルは直下の command-*.json しか読まない）。消さないので戻せる。"""
    dest = os.path.join(BRIDGE_DIR, "stale")
    moved = []
    for c in pending_commands():
        if c["stale"]:
            os.makedirs(dest, exist_ok=True)
            os.rename(os.path.join(BRIDGE_DIR, c["file"]), os.path.join(dest, c["file"]))
            moved.append(c)
    return {"moved_to": dest, "moved": moved}


def preflight(allow_multiple=False):
    """操作の前に、Premiere が1つだけで、ブリッジのパネルも1つだけか、古い命令が残っていないかを確かめる。
    2つ以上あると、同じ命令が両方の Premiere で実行される（パネルは命令を実行し終えてから消すため）。"""
    procs = premiere_processes()
    writers = heartbeat_writers()
    info = {"premiere": procs, "bridge_panels": writers}
    if not allow_multiple and (len(procs) > 1 or writers > 1):
        apps = "、".join(f"{p['app']}（pid {p['pid']}）" for p in procs)
        raise RuntimeError(f"Premiere が複数起動しているか、MCP Bridge パネルが複数動いています（{apps}／パネル約{writers}個）。"
                           "同じ命令が両方で実行されるので、使わない方の Premiere を閉じるか、そのパネルの Stop Bridge を押してから実行してください")
    warning = stale_warning(pending_commands())
    if warning:
        raise RuntimeError(warning)
    return info


def run(script, timeout=60):
    """スクリプトを実行し、結果（JSONならパース済み）を返す。失敗したら例外。"""
    fresh, started = heartbeat()
    if not fresh:
        raise RuntimeError("MCP Bridge パネルが動いていません（Premiereでウィンドウ > エクステンション > MCP Bridge (CEP) を開く）")
    if not started:
        raise RuntimeError("MCP Bridge パネルは開いていますが開始されていません（パネルの Start Bridge を押す）")
    cid = str(uuid.uuid4())
    staging = os.path.join(BRIDGE_DIR, f".tmp-{cid}.json")
    command = os.path.join(BRIDGE_DIR, f"command-{cid}.json")
    response = os.path.join(BRIDGE_DIR, f"response-{cid}.json")
    try:
        with open(staging, "w", encoding="utf-8") as f:
            json.dump({"id": cid, "script": script, "timeoutMs": int(timeout * 1000),
                       "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}, f, ensure_ascii=False)
        os.rename(staging, command)
        end = time.time() + timeout
        while time.time() < end:
            if os.path.exists(response):
                try:
                    with open(response, encoding="utf-8") as f:
                        data = json.load(f)
                except ValueError:
                    time.sleep(0.15)
                    continue
                if isinstance(data, dict) and data.get("success") is False:
                    raise RuntimeError(data.get("error"))
                if isinstance(data, dict) and "error" in data and len(data) <= 2:
                    raise RuntimeError(data["error"])
                return data.get("result", data) if isinstance(data, dict) else data
            time.sleep(0.15)
        raise TimeoutError(f"{timeout}秒以内に Premiere から応答がありません")
    finally:
        for p in (staging, command, response):
            try:
                os.unlink(p)
            except OSError:
                pass


WITH_PROJECT_JS = r'''
function __withProject(projectName, sequenceName, body) {
  // 作業中のユーザーのプロジェクトとシーケンスを覚えておき、終わったら戻す
  var prevProject = app.project, prevSeq = null;
  try { prevSeq = app.project.activeSequence; } catch (e0) {}
  var target = null;
  for (var i = 0; i < app.projects.numProjects; i++) { try { if (String(app.projects[i].name) === projectName) target = app.projects[i]; } catch (e1) {} }
  if (!target) return JSON.stringify({error: "project not open: " + projectName});
  var seq = null;
  for (var j = 0; j < target.sequences.numSequences; j++) {
    var sq = target.sequences[j];
    if (String(sq.name) === sequenceName && (!seq || sq.videoTracks.numTracks > seq.videoTracks.numTracks)) seq = sq;
  }
  if (!seq) return JSON.stringify({error: "sequence not found: " + sequenceName});
  var result;
  try {
    target.openSequence(seq.sequenceID);
    if (String(app.project.name) !== projectName) return JSON.stringify({error: "could not activate " + projectName});
    result = body(target, seq);
  } finally {
    try { if (prevSeq && String(prevProject.name) !== projectName) prevProject.openSequence(prevSeq.sequenceID); } catch (e2) {}
  }
  return result;
}
'''


def run_in_project(project_name, sequence_name, body_js, timeout=300):
    """project_name の sequence_name を一時的に前面にして body_js（function(project, seq){...} の本体）を実行し、
    終わったらユーザーが開いていたプロジェクト・シーケンスに戻す。"""
    script = (WITH_PROJECT_JS + "\n(function(){ try { return __withProject(" + json.dumps(project_name, ensure_ascii=False) + ", "
              + json.dumps(sequence_name, ensure_ascii=False) + ", function(project, seq){\n" + body_js
              + "\n}); } catch (e) { return JSON.stringify({err: String(e), line: e.line}); } })();")
    return run(script, timeout=timeout)


def timecode(frame, fps=29.97, drop=True):
    """フレーム番号 → Premiereに渡すタイムコード文字列。29.97fpsのドロップフレームは「;」区切り。"""
    if abs(fps - 29.97) < 0.01 and drop:
        d, m = divmod(frame, 17982)
        adj = 18 * d + (2 * ((m - 2) // 1798) if m >= 2 else 0)
        f = frame + adj
        return f"{f // 108000:02d};{(f // 1800) % 60:02d};{(f // 30) % 60:02d};{f % 30:02d}"
    n = round(fps)
    return f"{frame // (n * 3600):02d}:{(frame // (n * 60)) % 60:02d}:{(frame // n) % 60:02d}:{frame % n:02d}"


def seconds_to_frame(sec, fps=29.97):
    rate = 30000 / 1001 if abs(fps - 29.97) < 0.01 else (60000 / 1001 if abs(fps - 59.94) < 0.01 else fps)
    return int(round(sec * rate))


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("status", "run", "clear-stale"):
        print(__doc__)
        sys.exit(1)
    if sys.argv[1] == "status":
        fresh, started = heartbeat()
        cmds = pending_commands()
        info = {"bridge_dir": BRIDGE_DIR, "panel_alive": fresh, "bridge_started": started,
                "premiere": premiere_processes(), "bridge_panels": heartbeat_writers(), "pending_commands": cmds}
        warning = stale_warning(cmds)
        if warning:
            info["warning"] = warning
        print(json.dumps(info, ensure_ascii=False))
        return
    if sys.argv[1] == "clear-stale":
        print(json.dumps(clear_stale(), ensure_ascii=False, indent=1))
        return
    script = open(sys.argv[2], encoding="utf-8").read()
    print(json.dumps(run(script), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
