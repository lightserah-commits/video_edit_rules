#!/usr/bin/env python3
"""画面の寄り（07 の zoom）：赤枠で囲んだ所を、画面録画のクリップ自体を寄せて、大きく・字幕より上に見せる（どの案件でも使える道具）。
元：grok bots v002 の _work/screen_zoom.py（2026-10-17 確かめ係 C2・C6・C10 から作り、v002 で納品）。1017 v001〜v009・1018 v001 は
それを写して案件の値だけ替えて使っていた（計算は同じ）。2026-10-19 に tools へ（案件の値は settings の JSON に出した）。

  python3 tools/red_frames/screen_zoom.py --ver <edit/vNNN> --screen-size 3456x2234 [--settings <版>/_work/screen_zoom.json] [--dry]

  段：build（土台 XML）→ tools/red_frames/place.py（赤枠の時刻と PNG）→ これ → Premiere の読み込み（place_stills）→ 組み立て（make）
  寄せるのは画面録画のクリップ（V2）だけ（ワイプ・札・字幕は寄せない）。寄り・戻しは 0.3秒（9コマ）でなめらかに。
    1. 画面の区間ごとに、赤枠の箱が「横 1250px・縦 500px まで・下の端が 860px より上」に見える倍率と位置を決める（最大 2.0倍）
       スライドの区間（slide_labels）は、赤枠が無い間もスライドを横いっぱいにする（見える範囲はスライドの内側に止める）
       Chrome の区間（chrome_labels）は、上の帯（タブ・アドレス欄・ブックマーク）が映らない大きさに寄せたままにする（ぼかしではない）
       赤枠と赤枠の間が 2秒未満なら前の寄りのまま、2秒以上なら元の大きさ（スライド・Chrome の区間はその大きさ）へ戻す。1.5秒より短い寄りは付けない
    2. 寄りが変わる所は、次の字幕の頭で寄りきるように 9コマ前から動かす（字幕と赤枠は寄りきってから出る）
    3. 土台 XML の有効な画面のクリップ（--clip。既定 screen_CFR2997.mp4）の Basic Motion に、大きさ・位置のキーフレームを書く
       （Premiere は XML の Center を素材の大きさを単位に読む：横 1＝素材の幅の px。grok v002 の確認の画像で分かった）
    4. 赤枠を寄りに合わせて描き直す（<版>/_work/red_frames/zf_*.png と red_frames.json）。寄りが動く間にかかる赤枠は、その手前で消す。
       寄せた画面の外へはみ出して（ほぼ）空になる枠は描かない
  寄せない所：skip_labels の区間／寄せると private の文字（人名・社内の数字）が画面に入る所（字幕ごとの画面の文字認識
    <edit>/analysis/赤枠_vNNN/batch_*_in.json で探す。ぼかすかは小川さんが決める）／画面の左 left_cut・上 top_cut にかかる箱
  画面は「高さ 1080 に合わせて真ん中」に置いてある前提（place.py の --disp を省いた時・build の画面と同じ）。

  案件の値（settings。JSON。省くと <版>/_work/screen_zoom.json。札は plan_vNNN.py の SCREEN の3列目＝plan_parts/dNN_SCREEN.txt の札）：
    chrome_labels  上の帯を映さない大きさに寄せたままにする区間の札（Chrome などブラウザの画面）
    skip_labels    寄せない区間の札（社内の人名・お客さん・社内の数字が大きく映る所）
    chrome_ids・skip_ids  上の2つを、札でなく字幕の範囲 [[最初の字幕ID, 最後の字幕ID], …]（台本の順）で書く。1つの札の区間の途中で画面が替わる時に。
                   skip の所の赤枠は描くが、寄りの計算に入れない。2026-10-26 1025 v004：288「これでこうやってやって」で
                   Addness の右のメニューを開くのに、284〜287 の寄りが続いてメニューが端で切れた（小川さん「全体を見れるように」）→ 288 を両方に
    slide_labels   スライドの区間の札（無ければ []）。ある時は slide_rect（スライドの所。画面の 0〜1 の [x0, y0, x1, y1]）も
    private        寄せた時に画面に入ると困る文字（人名・社内の数字・アカウント名・決済の URL など。部分一致）
    top_cut        寄せた時に映さない画面の上の割合（既定 0.12＝メニューバー・アドレス欄）
    left_cut       寄せた時に映さない画面の左の割合（既定 0.165＝左の一覧＝会話の履歴など）。箱がここにかかる時は寄せない
    burned_face    画面録画に焼き込まれた顔の丸（Loom の顔の丸など）。[真ん中 x, 真ん中 y, 半径]（画面録画の素材の px）。書いた時は、寄せた画面で
                   その丸が「寄せていない時の丸の所」の外に見える寄せ方を避ける（倍率を 0.05 ずつ下げ、だめなら寄せない）。顔は別に重ねる
                   （AI動画編集 v006 の _work/face_overlay.py：顔の丸だけを抜いた映像を V11 に）。2026-10-20 AI動画編集 v006 から
    memo           何でも（道具は読まない）
  一度寄せた red_frames.json はもう一度寄せない（赤枠が二重に寄る）。place.py を流し直してから（rebuild の順のまま流せばよい）。
"""
import argparse
import glob
import importlib.util
import json
import os
import re
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as RC  # noqa: E402

FPS = 30000 / 1001
FT = RC.FT
ZMAX = 2.0
ZMIN_USE = 1.12                                # これより小さい寄りは付けない（ほぼ変わらないのに動くだけになる）
BOX_W, BOX_H, BOTTOM = 1250, 500, 860          # 箱の大きさの上限と、下の端（字幕の上）
TARGET = (960, 430)                            # 箱の真ん中を置きたい所
RAMP = 9                                       # 0.3秒
HEAD_TOL = 12                                  # 区間の頭がカットへ前にそろえられる分（build の SNAP・make の [35] は 12コマまで）
HOLD_GAP = round(2.0 * FPS)
MIN_STATE = round(1.5 * FPS)                   # これより短い寄りは付けない（前の寄りのまま）。1秒ごとに寄りが変わると目が回る
STROKE, COLOR = 8, (255, 30, 30, 255)
NO_ZOOM = (1.0, 0.0, 0.0)
KEYS = {"chrome_labels", "skip_labels", "chrome_ids", "skip_ids", "slide_labels", "slide_rect", "private", "top_cut", "left_cut", "memo", "burned_face"}
FACE_PEEK_MAX = 300                            # burned_face：寄せた顔の丸が元の丸の外に見えてよい広さ（px²。端の数 px まで）


class Screen:
    """画面録画（sw×sh）を高さ 1080 に合わせて真ん中に置いた時の寄りの計算。params は (倍率 z, 中心のずれ cx, cy〈px〉)"""

    def __init__(self, sw, sh, top_cut=0.12, left_cut=0.165):
        self.sw, self.sh = sw, sh
        self.scale = 1080 / sh * 100                   # 土台の画面の Scale（%）
        self.disp_w = sw * 1080 / sh                   # 画面の幅（元の大きさ。3456×2234 なら 1671px）
        self.off_x = (1920 - self.disp_w) / 2
        if self.disp_w > 1920.5:
            raise SystemExit(f"画面 {sw}x{sh} は 16:9 より横長：高さに合わせて置く前提の計算なので使えない")
        self.v_min, self.u_min = top_cut, left_cut

    def rect01(self, r):
        """画面の 0〜1 の [x0, y0, x1, y1] → 元の大きさの出力の px"""
        return (self.off_x + r[0] * self.disp_w, r[1] * 1080, self.off_x + r[2] * self.disp_w, r[3] * 1080)

    def limits(self, z):
        w, h = self.disp_w * z, 1080 * z
        lx = (w - 1920) / 2 if w >= 1920 else (1920 - w) / 2
        ly = (h - 1080) / 2
        return lx, ly

    def face_peek(self, p, face):
        """burned_face：params p で、焼き込みの顔の丸が「寄せていない時の丸」の外に見える広さ（出力の px²）"""
        if not face or p is None:
            return 0
        z, cx, cy = p
        k = 1080 / self.sh
        X0, Y0, R0 = self.off_x + face[0] * k, face[1] * k, face[2] * k
        dx, dy, dr = 960 + cx + (X0 - 960) * z, 540 + cy + (Y0 - 540) * z, R0 * z
        x0, x1, y0, y1 = max(0, int(dx - dr)), min(1920, int(dx + dr) + 1), max(0, int(dy - dr)), min(1080, int(dy + dr) + 1)
        n, st = 0, 4
        for yy in range(y0, y1, st):
            for xx in range(x0, x1, st):
                if (xx - dx) ** 2 + (yy - dy) ** 2 <= dr * dr and (xx - X0) ** 2 + (yy - Y0) ** 2 > (R0 + 2) ** 2:
                    n += 1
        return n * st * st

    def place(self, rect, zmin=1.0, fit=None, bounds=None, zmax=ZMAX):
        """箱 rect（元の大きさの出力の px）を見せる倍率と位置 (z, cx, cy)。左・上の帯にかかって寄せられない時は None（zmin が 1 なら元の大きさ）"""
        x0, y0, x1, y1 = rect
        w, h = max(x1 - x0, 1), max(y1 - y0, 1)
        if fit:
            z = min(fit[0] / w, fit[1] / h)
            tx, ty = 960, 540
        else:
            z = min(zmax, BOX_W / w, BOX_H / h)
            tx, ty = TARGET
        z = max(z, zmin)
        if not fit and ((x0 - self.off_x) / self.disp_w < self.u_min or y0 / 1080 < self.v_min):
            return NO_ZOOM if zmin <= 1.0 else None
        fx, fy = (x0 + x1) / 2, (y0 + y1) / 2
        for _ in range(20):
            lx, ly = self.limits(z)
            cx_max = lx if z <= 1.0 else min(lx, -960 - z * (self.off_x + self.u_min * self.disp_w - 960))   # 左の一覧を映さない
            cx = min(max(tx - 960 - (fx - 960) * z, -lx), cx_max)
            cy_max = ly if z <= 1.0 else min(ly, -540 - z * (self.v_min * 1080 - 540))   # 上の帯を映さない
            cy = min(max(ty - 540 - (fy - 540) * z, -ly), cy_max)
            if bounds:                                   # grok v002 2回目 R6：見える範囲をこの箱（スライド）の内側に止める（スライドの外の暗い所を映さない）
                bx0, by0, bx1, by1 = bounds
                lo_x, hi_x = 960 - z * (bx1 - 960), -960 - z * (bx0 - 960)
                lo_y, hi_y = 540 - z * (by1 - 540), -540 - z * (by0 - 540)
                cx = min(max(cx, lo_x), hi_x) if lo_x <= hi_x else (lo_x + hi_x) / 2
                cy = min(max(cy, lo_y), hi_y) if lo_y <= hi_y else (lo_y + hi_y) / 2
                cx, cy = min(max(cx, -lx), lx), min(max(cy, -ly), ly)
            if fit or 540 + cy + (y1 - 540) * z <= BOTTOM or z >= zmax:
                break
            z = min(zmax, z + 0.1)
        if not fit and z < ZMIN_USE and 540 + (y1 - 540) <= BOTTOM and zmin <= 1.0:
            return NO_ZOOM
        return (round(z, 4), round(cx, 1), round(cy, 1))

    def visible(self, p):
        """params p で画面に映る、画面録画の範囲（0〜1 の u0, v0, u1, v1）"""
        z, cx, cy = p
        u = [((X - 960 - cx) / z + 960 - self.off_x) / self.disp_w for X in (0, 1920)]
        v = [((Y - 540 - cy) / z + 540) / 1080 for Y in (0, 1080)]
        return u[0], v[0], u[1], v[1]


def tr(p, pt):
    """元の大きさの出力の点 pt が、params p で映る所"""
    z, cx, cy = p
    return (960 + cx + (pt[0] - 960) * z, 540 + cy + (pt[1] - 540) * z)


def load_settings(path):
    if not os.path.exists(path):
        raise SystemExit(f"案件の値の JSON が無い：{path}\n  書き方は --help の「案件の値」と tools/red_frames/README.md の「画面の寄り」（例 tools/red_frames/screen_zoom_example.json）")
    s = json.load(open(path, encoding="utf-8"))
    bad = sorted(set(s) - KEYS)
    if bad:
        raise SystemExit(f"{path} に知らない鍵 {bad}（使える鍵 {sorted(KEYS)}）")
    if s.get("slide_labels") and not s.get("slide_rect"):
        raise SystemExit(f"{path}：slide_labels がある時は slide_rect（スライドの所。画面の 0〜1 の [x0, y0, x1, y1]）も書く")
    return s


def load_screen_table(plan_path):
    """plan_vNNN.py の SCREEN（[(最初の字幕ID, 最後の字幕ID, 札, 理由), …]）"""
    sys.path.insert(0, os.path.dirname(plan_path))
    spec = importlib.util.spec_from_file_location(os.path.splitext(os.path.basename(plan_path))[0], plan_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.SCREEN


def private_boxes(ocr_dir, private):
    """字幕ID → private の文字が出ている所（画面の 0〜1 の中心）の一覧"""
    out = {}
    if not private:
        return out
    files = glob.glob(os.path.join(ocr_dir, "batch_*_in.json"))
    if not files:
        raise SystemExit(f"private があるのに、字幕ごとの画面の文字認識（batch_*_in.json）が無い：{ocr_dir}（--ocr-dir で場所を渡す）")
    for f in files:
        for it in json.load(open(f, encoding="utf-8"))["items"]:
            for fr in it["frames"]:
                for x in fr["ocr"]:
                    if any(n in x["text"] for n in private):
                        out.setdefault(it["id"], []).append((x["x"] + x["w"] / 2, x["y"] + x["h"] / 2))
    return out


def write_text(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description="赤枠の所へ画面録画のクリップを寄せる（土台 XML と赤枠を書き直す）", epilog=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    RC.add_case_args(ap, cuts=False)
    ap.add_argument("--screen-size", required=True, help="画面録画の大きさ WxH（例 3456x2234。place.py と同じ値）")
    ap.add_argument("--settings", help="案件の値の JSON（省くと <版>/_work/screen_zoom.json）")
    ap.add_argument("--plan", help="SCREEN の表を持つ plan_vNNN.py（省くと <版>/plan_vNNN.py）")
    ap.add_argument("--xml", help="土台 XML（省くと <版>/_work/base_vNNN.xml）")
    ap.add_argument("--frames", help="place.py が書いた red_frames.json（省くと <版>/_work/red_frames.json。PNG はその横の red_frames/）")
    ap.add_argument("--ocr-dir", help="字幕ごとの画面の文字認識 batch_*_in.json のフォルダ（省くと <edit>/analysis/赤枠_vNNN）")
    ap.add_argument("--clip", default="screen_CFR2997.mp4", help="土台 XML の画面のクリップの名前（既定 screen_CFR2997.mp4）")
    ap.add_argument("--dry", action="store_true", help="計算して数だけ出す（XML・red_frames.json・PNG・土台の表を書かない）")
    args = ap.parse_args()
    if args.ver:
        args.ver = os.path.abspath(os.path.expanduser(args.ver))
    RC.resolve(args, need=("map", "captions"))
    m = re.search(r"v(\d{3})$", os.path.basename(os.path.normpath(args.ver))) if args.ver else None
    tag = m.group(1) if m else None

    def pick(given, what, *default):
        if given:
            return os.path.abspath(os.path.expanduser(given))
        if not tag:
            raise SystemExit(f"--{what} か --ver（vNNN のフォルダ）を渡してください")
        return os.path.join(*default)
    work = os.path.join(args.ver, "_work") if args.ver else None
    settings_p = pick(args.settings, "settings", work or "", "screen_zoom.json")
    plan_p = pick(args.plan, "plan", args.ver or "", f"plan_v{tag}.py")
    xml_p = pick(args.xml, "xml", work or "", f"base_v{tag}.xml")
    rfj_p = pick(args.frames, "frames", work or "", "red_frames.json")
    ocr_dir = pick(args.ocr_dir, "ocr-dir", os.path.dirname(args.ver or ""), "analysis", f"赤枠_v{tag}")
    for p in (plan_p, xml_p, rfj_p):
        if not os.path.exists(p):
            raise SystemExit(f"{p} が無い")
    cfg = load_settings(settings_p)
    sw, sh = (int(v) for v in args.screen_size.lower().split("x"))
    S = Screen(sw, sh, cfg.get("top_cut", 0.12), cfg.get("left_cut", 0.165))
    chrome_labels, skip_labels = set(cfg.get("chrome_labels", [])), set(cfg.get("skip_labels", []))
    slide_labels = set(cfg.get("slide_labels", []))
    slide_rect = S.rect01(cfg["slide_rect"]) if cfg.get("slide_rect") else None
    private = cfg.get("private", [])
    face = cfg.get("burned_face")
    face_fixed = []

    screen_table = load_screen_table(plan_p)
    known = {lab.strip() for _, _, lab, _ in screen_table}
    unknown = sorted((chrome_labels | skip_labels | slide_labels) - known)
    if unknown:
        print(f"！ settings の札のうち plan の SCREEN に無いもの（効かない）：{unknown}")
    mp = json.load(open(args.map, encoding="utf-8"))
    capj = json.load(open(args.captions, encoding="utf-8"))
    rfj = json.load(open(rfj_p, encoding="utf-8"))
    if "zoom" in rfj:
        if not args.dry:
            raise SystemExit(f"{rfj_p} はもう寄せてある（もう一度寄せると赤枠が二重に寄る）。place.py を流し直してから")
        print("！ この red_frames.json はもう寄せてある：下の数は、寄せた赤枠をもう一度寄せた時のもの（--dry なので書かない）")
    ctl = mp["caption_tl"]
    _, nxt = RC.caption_order(mp, capj)
    order = [c["id"] for c in capj["captions"]] if isinstance(capj, dict) else [c["id"] for c in capj]   # タイムラインの順ではなく字幕の表（台本）の順。SCREEN の範囲は継ぎ目をまたがない
    bad_ids = [r for r in cfg.get("chrome_ids", []) + cfg.get("skip_ids", []) if len(r) != 2 or r[0] not in order or r[1] not in order]
    if bad_ids:
        print(f"！ settings の chrome_ids・skip_ids のうち字幕の表に無い範囲（効かない）：{bad_ids}")
    zoom_skip = set()
    for first, last, label, _why in screen_table:          # 寄せない区間の字幕
        if label.strip() in skip_labels and first in order and last in order:
            zoom_skip.update(order[order.index(first):order.index(last) + 1])
    for r in cfg.get("skip_ids", []):
        if r not in bad_ids:
            zoom_skip.update(order[order.index(r[0]):order.index(r[1]) + 1])
    slides, chromes = [], []
    for first, last, label, _why in screen_table:
        if first in ctl and last in nxt:
            if label.strip() in slide_labels:
                slides.append((ctl[first], nxt[last]))
            if label.strip() in chrome_labels:
                chromes.append((ctl[first], nxt[last]))
    for r in cfg.get("chrome_ids", []):
        if r not in bad_ids and r[0] in ctl and r[1] in nxt:
            chromes.append((ctl[r[0]], nxt[r[1]]))
    base_slide = S.place(slide_rect, fit=(1920 * 0.98, 1080)) if slide_rect else None
    # grok v002 2回目 R2：Chrome の画面は、上の帯（アドレス欄の共有 URL・ブックマークバー）が映らない大きさに寄せたままにする（ぼかしではない）
    base_chrome = S.place((S.off_x, S.v_min * 1080, S.off_x + S.disp_w, 1080), fit=(1920, 1080))
    frames = sorted(rfj["frames"], key=lambda f: f["start"])
    states_all, ramps_all = [], []
    priv = private_boxes(ocr_dir, private)
    skipped = []
    for A, B in mp["screen_spans"]:
        def base_at(f):
            # 区間の頭はカットの切れ目へ数コマ前にそろえられる（build）ので、表の字幕の頭より 12コマ前までは同じ区間として扱う（grok v002 8:15 の2コマ）
            if any(a - HEAD_TOL <= f < b for a, b in slides):
                return base_slide
            if any(a - HEAD_TOL <= f < b for a, b in chromes):
                return base_chrome
            return NO_ZOOM
        tg = []                                          # (s, e, params, lift)
        for fr in frames:
            s, e = fr["start"] // FT, fr["end"] // FT
            if e <= A or s >= B:
                continue
            if fr["id_from"] in zoom_skip or fr["id_to"] in zoom_skip:
                continue
            zmin = base_at(s)[0]
            in_slide = any(a <= s < b for a, b in slides)
            pz = S.place(fr["rect_px"], zmin=zmin, bounds=slide_rect if in_slide else None)
            if pz is None:                               # 左の一覧にかかる箱：寄せず、その所の元の寄り（スライドの大きさ）のまま
                pz = base_at(s)
            if face and pz != NO_ZOOM and S.face_peek(pz, face) > FACE_PEEK_MAX:
                # burned_face（AI動画編集 v006）：寄せると焼き込みの顔の丸が元の丸の外にはみ出して見える → 倍率を下げる。だめなら寄せない
                alt, zt = None, round(pz[0] - 0.05, 4)
                while zt >= ZMIN_USE:
                    q = S.place(fr["rect_px"], zmin=zmin, bounds=slide_rect if in_slide else None, zmax=zt)
                    if q is None:
                        break
                    if q == NO_ZOOM or S.face_peek(q, face) <= FACE_PEEK_MAX:
                        alt = q
                        break
                    zt = round(zt - 0.05, 4)
                face_fixed.append((s, fr.get("id_from"), pz[0], alt[0] if alt else None))
                pz = alt if alt is not None else base_at(s)
            tg.append((max(s, A), min(e, B), pz, fr["rect_px"][3] > BOTTOM))   # 最後＝字幕の下の箱を持ち上げる寄り
        if tg and tg[0][0] - A <= HEAD_TOL:              # 区間の頭から 12コマ以内に始まる赤枠の寄りは、区間の頭から（寄る前の画が数コマ映らないように）
            tg[0] = (A,) + tg[0][1:]
        # 状態の並び（フレーム → params）。赤枠の間が短ければ前の寄りのまま
        st = []                                          # [start, params, lift]
        cur = A
        for s, e, p, lift in tg:
            if s > cur:
                gap_p = base_at(cur)
                if st and s - cur < HOLD_GAP:
                    gap_p = st[-1][1]
                st.append([cur, gap_p, False])
            st.append([s, p, lift])
            cur = e
        if cur < B:
            st.append([cur, base_at(cur) if not (st and B - cur < HOLD_GAP) else st[-1][1], False])
        if not st:
            st = [[A, base_at(A), False]]
        # スライド・Chrome の区間の切れ目（赤枠の無い所）でも base が変わる
        for a, b in slides + chromes:
            for f in (a, b):
                if A < f < B:
                    i = max(j for j, x in enumerate(st) if x[0] <= f)
                    if st[i][0] != f and not any(s <= f < e for s, e, _, _ in tg):
                        st.insert(i + 1, [f, base_at(f), False])
        # 短い寄りは前の寄りのまま（最初の状態は除く）
        for k in range(1, len(st)):
            e_ = st[k + 1][0] if k + 1 < len(st) else B
            if e_ - st[k][0] < MIN_STATE and not st[k][2]:     # 字幕の下の箱を持ち上げる寄りは短くても付ける（grok C6）
                st[k][1] = st[k - 1][1]
        # 寄せると人名・社内の数字が大きく映る所は寄せない（ぼかすかは小川さんが決める。元の大きさのまま）
        for k in range(len(st)):
            if st[k][1] == NO_ZOOM:
                continue
            e_ = st[k + 1][0] if k + 1 < len(st) else B
            ids = [c for c, f_ in ctl.items() if st[k][0] - 3 <= f_ < e_]
            u0, v0, u1, v1 = S.visible(st[k][1])
            hit = [c for c in ids for (x_, y_) in priv.get(c, []) if u0 <= x_ <= u1 and v0 <= y_ <= v1]
            if hit:
                skipped.append((st[k][0], sorted(set(hit))[:3]))
                st[k][1] = NO_ZOOM
        # 同じ params が続く所はまとめる
        merged = []
        for f, p, _lift in st:
            if merged and merged[-1][1] == p:
                continue
            merged.append([f, p])
        for k, (f, p) in enumerate(merged):
            e = merged[k + 1][0] if k + 1 < len(merged) else B
            states_all.append((f, e, p))
            if k > 0:
                r0 = max(merged[k - 1][0] + 1, f - RAMP)
                ramps_all.append((r0, f, merged[k - 1][1], p))
    states_all.sort()
    ramps_all.sort()

    def params_at(f):
        for r0, r1, p0, p1 in ramps_all:
            if r0 <= f < r1:
                t = (f - r0) / (r1 - r0)
                return tuple(a + (b - a) * t for a, b in zip(p0, p1))
        for a, b, p in states_all:
            if a <= f < b:
                return p
        return NO_ZOOM

    # ---- XML：有効な画面のクリップにキーフレーム ----
    xml = open(xml_p, encoding="utf-8").read()
    pat = re.compile(r'(<clipitem id="clip-\d+"><name>' + re.escape(args.clip) + r'</name><enabled>TRUE</enabled>.*?<start>(\d+)</start><end>(\d+)</end><in>(\d+)</in>.*?)'
                     r'(<filter><effect><name>Basic Motion</name>.*?</effect></filter>)(</clipitem>)', re.S)
    n_kf = 0

    def motion_kf(points):
        sc = "".join(f"<keyframe><when>{w}</when><value>{S.scale * p[0]:.4f}</value></keyframe>" for w, p in points)
        ce = "".join(f"<keyframe><when>{w}</when><value><horiz>{p[1] / S.sw:.6f}</horiz><vert>{p[2] / S.sh:.6f}</vert></value></keyframe>" for w, p in points)
        p0 = points[0][1]
        return ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory>"
                "<effecttype>motion</effecttype><mediatype>video</mediatype>"
                f'<parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><valuemin>0</valuemin><valuemax>1000</valuemax>'
                f"<value>{S.scale * p0[0]:.4f}</value>{sc}</parameter>"
                f'<parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name><value><horiz>{p0[1] / S.sw:.6f}</horiz>'
                f"<vert>{p0[2] / S.sh:.6f}</vert></value>{ce}</parameter></effect></filter>")

    def static(p):
        return ("<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory>"
                "<effecttype>motion</effecttype><mediatype>video</mediatype>"
                f'<parameter authoringApp="PremierePro"><parameterid>scale</parameterid><name>Scale</name><value>{S.scale * p[0]:.4f}</value></parameter>'
                f'<parameter authoringApp="PremierePro"><parameterid>center</parameterid><name>Center</name><value><horiz>{p[1] / S.sw:.6f}</horiz>'
                f"<vert>{p[2] / S.sh:.6f}</vert></value></parameter></effect></filter>")

    def repl(m):
        nonlocal n_kf
        s, e, cin = int(m.group(2)), int(m.group(3)), int(m.group(4))
        pts = sorted({s, e - 1} | {x for r0, r1, _, _ in ramps_all for x in (r0, r1) if s <= x < e})
        vals = [(f, params_at(f)) for f in pts]
        if all(v[1] == NO_ZOOM for v in vals):
            return m.group(0)
        if len({v[1] for v in vals}) == 1:
            return m.group(1) + static(vals[0][1]) + m.group(6)
        n_kf += 1
        return m.group(1) + motion_kf([(cin + (f - s), p) for f, p in vals]) + m.group(6)   # when はクリップの素材の時刻（in 点から）
    xml2, n = pat.subn(repl, xml)
    # ---- 赤枠を寄りに合わせて描き直す ----
    out_dir = os.path.join(os.path.dirname(rfj_p), "red_frames")
    new, trimmed, dropped, draw = [], 0, [], []
    for k, fr in enumerate(frames):
        s, e = fr["start"] // FT, fr["end"] // FT
        s = max([s] + [r1 for r0, r1, _, _ in ramps_all if r0 < s < r1])     # 寄りが動いている間に始まる赤枠は、寄りきってから
        cut = [r0 for r0, r1, _, _ in ramps_all if s < r0 < e]
        if cut:
            e = min(cut)
            trimmed += 1
        if e - s < 6:
            continue
        p = params_at(s)
        x0, y0 = tr(p, fr["rect_px"][:2])
        x1, y1 = tr(p, fr["rect_px"][2:])
        rect = [max(8, x0), max(8, y0), min(1912, x1), min(1072, y1)]
        if rect[2] - rect[0] < 24 or rect[3] - rect[1] < 16:          # 寄せた画面の外へはみ出して（ほぼ）空になる枠は描かない（1017）
            dropped.append(fr["id_from"])
            continue
        png = os.path.join(out_dir, f"zf_{k:03d}_{fr['id_from'].replace('+', 'p')}.png")
        draw.append((png, rect))
        new.append(dict(fr, png=png, rect_px=[round(v) for v in rect], start=s * FT, end=e * FT, zoom=list(p) if p != NO_ZOOM else None))
    zoom_rec = {"how": f"tools/red_frames/screen_zoom.py --settings {settings_p}",
                "states": [[a_, b_, list(p)] for a_, b_, p in states_all if p != NO_ZOOM],
                "ramps": [[a_, b_] for a_, b_, _, _ in ramps_all], "skipped_private": [[a_, h] for a_, h in skipped],
                "face_fixed": [[a_, i_, z0_, z1_] for a_, i_, z0_, z1_ in face_fixed]}
    zs = [x for x in states_all if x[2] != NO_ZOOM]
    if face:
        print(f"焼き込みの顔の丸がはみ出すので倍率を下げた・寄せなかった所 {len(face_fixed)}：" + "、".join(
            f"{a_ / FPS // 60:.0f}:{a_ / FPS % 60:04.1f}（{i_} {z0_:.2f}→{('寄せない' if z1_ is None else f'{z1_:.2f}')}）" for a_, i_, z0_, z1_ in face_fixed[:20]))
    print(f"人名・社内の数字が入るので寄せなかった所 {len(skipped)}：" + "、".join(f"{a_ / FPS // 60:.0f}:{a_ / FPS % 60:04.1f}{h}" for a_, h in skipped[:12]))
    print(f"画面の寄り：寄せた所 {len(zs)}（{sum(b_ - a_ for a_, b_, _ in zs) / FPS / 60:.1f}分）・動き {len(ramps_all)}・"
          f"キーフレームを書いたクリップ {n_kf}／画面のクリップ {n}・赤枠 {len(new)}（寄りが動く前で切った {trimmed}・寄せた画面の外で描かない {len(dropped)} {dropped}）")
    if args.dry:
        print("（--dry：XML・red_frames.json・PNG・土台の表は書いていない）")
        return
    write_text(xml_p, xml2)
    for f in os.listdir(out_dir):
        if f.startswith("zf_"):
            os.remove(os.path.join(out_dir, f))
    for png, rect in draw:
        img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        ImageDraw.Draw(img).rounded_rectangle(rect, 12, outline=COLOR, width=STROKE)
        img.save(png)
    rfj["frames"] = new
    rfj["zoom"] = zoom_rec
    write_text(rfj_p, json.dumps(rfj, ensure_ascii=False, indent=1))
    mp["screen_zoom"] = zoom_rec
    write_text(args.map, json.dumps(mp, ensure_ascii=False, indent=1))
    print(f"書いた：{xml_p}・{rfj_p}・{args.map}・{out_dir}/zf_*.png")


if __name__ == "__main__":
    main()
