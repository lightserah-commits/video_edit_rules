"""Premiere の MCP Bridge が簡単な命令（読むだけ）に答えるようになるまで、1分ごとに確かめる（最大3時間）。答えたら前面のプロジェクト名を出して終わる"""
import os, sys, time
sys.path.insert(0, os.path.expanduser("~/Desktop/video_edit_rules/tools"))
from premiere_bridge import run
end = time.time() + 3 * 3600
while time.time() < end:
    try:
        r = run('(function(){return JSON.stringify({front:app.project.name,seq:app.project.activeSequence?app.project.activeSequence.name:null,n:app.projects.numProjects});})()', timeout=30)
        print("PREMIERE_OK", r, time.strftime("%H:%M:%S")); sys.exit(0)
    except Exception as e:
        print("wait", time.strftime("%H:%M:%S"), str(e)[:60], flush=True)
    time.sleep(60)
print("PREMIERE_TIMEOUT"); sys.exit(1)
