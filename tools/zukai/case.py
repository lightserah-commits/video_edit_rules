"""動く図解の道具（tools/zukai/）が、どの案件・どの版を相手にするかを決める（案件名・版の番号を道具の中に書かない）。

版のフォルダ（edit/vNNN）を --ver か環境変数 ZUKAI_VER で渡す。ほかは版のフォルダから決まる（違う所にあれば1つずつ渡す）：
  図解のフォルダ   --zukai    ZUKAI_DIR       既定 <版>/zukai（<KEY>/page.html・diagram.json、assets/、out/ を置く所。build・make が out/ を読む）
  カット           --cuts     ZUKAI_CUTS      既定 <版>/_work/cuts_vNNN.json
  字幕             --captions ZUKAI_CAPTIONS  既定 <版>/_work/captions_vNNN.json
  土台の表         --map      ZUKAI_MAP       既定 <版>/_work/base_vNNN_map.json（画面を映す区間。無くてもよい）
  文字起こし       --asr      ZUKAI_ASR       既定 <edit>/analysis/asr/asr_camera.json（語の時刻）
  カメラ           --cam      ZUKAI_CAM       既定 <edit>/media/camera_CFR2997.mov（29.97fps の作業用コピー）
"""
import os
import re
from pathlib import Path

TOOLS = Path(__file__).resolve().parent                       # ~/Desktop/video_edit_rules/tools/zukai
ROOT = Path(os.path.expanduser("~/Desktop/video_edit_rules"))


def add_args(ap):
    g = ap.add_argument_group("案件と版（省くと環境変数 ZUKAI_*）")
    g.add_argument("--ver", default=os.environ.get("ZUKAI_VER"), help="版のフォルダ edit/vNNN（環境変数 ZUKAI_VER）")
    g.add_argument("--zukai", default=os.environ.get("ZUKAI_DIR"), help="図解のフォルダ（既定 <版>/zukai）")
    for k in ("cuts", "captions", "map", "asr", "cam"):
        g.add_argument(f"--{k}", default=os.environ.get(f"ZUKAI_{k.upper()}"))
    return ap


class Case:
    def __init__(self, a):
        if not a.ver:
            raise SystemExit("版のフォルダを --ver か環境変数 ZUKAI_VER で渡してください（例 --ver \"~/Desktop/みかみ案件依頼書/<案件>/edit/v005\"）")
        self.ver = Path(os.path.expanduser(a.ver)).resolve()
        m = re.search(r"v(\d{3})$", self.ver.name)
        self.tag = m.group(1) if m else None
        self.edit = self.ver.parent
        self.zukai = Path(os.path.expanduser(a.zukai)).resolve() if a.zukai else self.ver / "zukai"
        self.out = self.zukai / "out"

        def pick(given, *default):
            if given:
                return Path(os.path.expanduser(given))
            if default[0] is None:
                return None
            return Path(*default)
        w = self.ver / "_work"
        t = self.tag
        self.cuts = pick(a.cuts, w if t else None, f"cuts_v{t}.json")
        self.captions = pick(a.captions, w if t else None, f"captions_v{t}.json")
        self.map = pick(a.map, w if t else None, f"base_v{t}_map.json")
        self.asr = pick(a.asr, self.edit / "analysis" / "asr" / "asr_camera.json")
        self.cam = pick(a.cam, self.edit / "media" / "camera_CFR2997.mov")
        for k in ("cuts", "captions"):
            p = getattr(self, k)
            if p is None or not p.exists():
                raise SystemExit(f"{k} が見つからない（{p}）。--{k} で場所を渡す")

    def ensure_lib(self):
        """ページは ../lib/zukai.css・../lib/zukai.js を読む。図解のフォルダに lib が無ければ tools/zukai/lib へのリンクを作る
        （前の案件のように lib を写して持っている時は、そちらを使う）"""
        lib = self.zukai / "lib"
        if not lib.exists():
            self.zukai.mkdir(parents=True, exist_ok=True)
            lib.symlink_to(TOOLS / "lib", target_is_directory=True)
            print(f"  {lib} → {TOOLS / 'lib'}（リンクを作った）")
        elif not lib.resolve() == (TOOLS / "lib").resolve():
            print(f"  注意：{lib} は案件の中の lib（tools/zukai/lib ではない）")
        return lib.resolve()
