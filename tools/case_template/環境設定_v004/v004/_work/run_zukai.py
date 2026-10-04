import subprocess, sys, time
keys = sys.argv[1:]
for k in keys:
    for attempt in range(3):
        try:
            r = subprocess.run(["python3", "zukai/make_zukai.py", k], capture_output=True, text=True, timeout=420)
            last = [l for l in r.stdout.splitlines() if l.startswith("== ") or "!!" in l]
            print(k, "ok" if r.returncode == 0 else f"err {r.returncode}", last[-1] if last else (r.stderr[-300:] if r.stderr else ""), flush=True)
            if r.returncode == 0:
                break
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-f", "render_frames.mjs"]); subprocess.run(["pkill", "-f", "headless=new"])
            print(k, f"止まった（{attempt + 1}回目）→ やり直す", flush=True)
            time.sleep(2)
