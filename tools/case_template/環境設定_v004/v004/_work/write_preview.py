"""premiere_preview.json を書く（Premiere で確認したことの記録。編集の依頼文.md の工程10）。
  python3 v004/_work/write_preview.py '<finish.py の結果の JSON>'"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
V = os.path.dirname(HERE)
res = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
jobs = json.load(open(os.path.join(HERE, "review_jobs.json"), encoding="utf-8"))
mp = json.load(open(os.path.join(HERE, "base_v004_map.json"), encoding="utf-8"))
out = {
    "project": os.path.join(V, "kankyo_v004.prproj"),
    "sequence": mp["sequence"],
    "premiere": "Adobe Premiere Pro 2026（ブリッジ経由）",
    "done": ["プロジェクトを開いた", "右上タイトルの最初にクロスディゾルブ 15フレーム", "保存", f"画像を {res.get('exported')} 枚書き出した（確認/）"],
    "offline_after_open": res.get("offline"),
    "export_errors": res.get("errs"),
    "frames": [{"timecode": j[0], "file": j[1] + ".png", "sec": j[2]} for j in jobs],
    "not_checked": ["音（AI はスピーカーから音を出さない。ユーザーのヘッドホンでの確認待ち＝未聴取）",
                    "動き（テロップのアニメーション・ディゾルブの動き）は静止画でしか見ていない",
                    "書き出した画像以外の時刻の見た目"],
}
json.dump(out, open(os.path.join(V, "premiere_preview.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok")
