#!/usr/bin/env python3
"""make_zukai.py を図解ごとに順に回し、止まった（Chrome が固まった）時は止めてやり直す（3回まで。1つ 420秒で打ち切り）。どの案件でも使える道具。
元：環境設定 v004 の _work/run_zukai.py。
  python3 tools/zukai/run_zukai.py --ver <edit/vNNN> Z1 Z2 I03 [--name=auto]   （--ver 以外の make_zukai.py の引数もそのまま渡す）
  打ち切った時は、描いている Chrome（render_frames.mjs・headless=new）を止める。同じ Mac でほかに図解を描いていないか先に見る
"""
import subprocess
import sys
import time
from pathlib import Path

MAKE = Path(__file__).resolve().parent / "make_zukai.py"


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return
    opts, keys, i = [], [], 0
    while i < len(args):
        x = args[i]
        if x.startswith("--"):
            opts.append(x)
            if "=" not in x and x not in ("--check", "--previews") and i + 1 < len(args):
                opts.append(args[i + 1])
                i += 1
        else:
            keys.append(x)
        i += 1
    for k in keys:
        for attempt in range(3):
            try:
                r = subprocess.run([sys.executable, str(MAKE), *opts, k], capture_output=True, text=True, timeout=420)
                last = [ln for ln in r.stdout.splitlines() if ln.startswith(("== ", "-- ")) or "!!" in ln]
                print(k, "ok" if r.returncode == 0 else f"err {r.returncode}", last[-1] if last else (r.stderr[-300:] if r.stderr else ""), flush=True)
                if r.returncode == 0:
                    break
            except subprocess.TimeoutExpired:
                subprocess.run(["pkill", "-f", "render_frames.mjs"])
                subprocess.run(["pkill", "-f", "headless=new"])
                print(k, f"止まった（{attempt + 1}回目）→ やり直す", flush=True)
                time.sleep(2)


if __name__ == "__main__":
    main()
