#!/usr/bin/env python3
"""合う写真が無い所の絵を、OpenAI の画像 API で作る（02 の P13 generated。2026-10-05 ユーザー OK：OpenAI の画像 API は有料でも使ってよい、月 10ドルまで）。

キー：Mac のキーチェーンの「openai_api_key」から読む（無ければ環境変数 OPENAI_API_KEY）。キーはファイルにもチャットにも書かない。
  入れ方（ユーザーがキーをコピーしてからターミナルで打つ）：security add-generic-password -U -a "$USER" -s openai_api_key -w "$(pbpaste)"
    → そのあと pbcopy < /dev/null。-w だけで聞かれた所に貼ると 128文字で切れる（sk-proj- のキーは約164文字。2026-10-12 ほたて）
お金：作るたびに、かかった額（API が返すトークン数 × 公式の単価）を ~/.video_edit_rules/gen_image_log.csv に足す。
  その月の合計が MONTH_LIMIT（10ドル）を超えていたら作らない。OpenAI の画面の月の上限（10ドル）とは別の、手前の止め。
置き場所：--ver を渡すと <版>/zukai/assets/（tools/zukai の画像の置き場。ページからは ../assets/名前）。--out で直に指定してもよい。
  同じ名前があれば _2・_3 を付けて新しく書く（上書きしない。Premiere が読んでいるファイルを変えない）。
  置いたフォルダの 出どころ.md に「AI で作った絵」・モデル・大きさ・指示文を足す（名札には「（イメージ）」を付ける。02 の generated）。

使い方:
  python3 tools/gen_image.py --ver "<案件>/edit/v002" --name gold_rush "1849年のゴールドラッシュ。川で砂金を探す人々。写真風"
  python3 tools/gen_image.py --out <フォルダ> --name icon_x --background transparent --size 1024x1024 --prompt-file 指示.txt
  python3 tools/gen_image.py --month          （今月かかった額だけ見る）
  --quality low|medium|high（既定 medium。試しは low、仕上げは high）・--n 1〜4・--dry（送らずに中身だけ見る）
  --ref 顔.png（何枚でも）：参考の画像を渡して作る（images/edits）。演者の顔を似せる時（2026-10-12 小川さん「演者の顔を必要であれば参考元に」）。
    --fidelity は gpt-image-2.5-flare では使えない（既定 none）。参考の画像は OpenAI に送られるので、ユーザーが許した人の顔だけにする
  --mask 顔だけ透明.png：1枚目の --ref の絵の、透明にした所だけ描き直す（images/edits の mask。1枚目と同じ大きさの PNG。2026-10-28 1026 v005 顔の再現係）
  --moderation low|auto（既定 low＝API の検査を緩くする。2026-10-21 ユーザー「lowで行ける様にしてほしい」。auto は API の既定で、機種名だけで断られた 1017 v008）。
    --ref の時（images/edits）は API がこの設定を受け付けないので送らない（auto のまま）
"""
import argparse
import base64
import csv
import datetime as dt
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.openai.com/v1/images/generations"
API_EDIT = "https://api.openai.com/v1/images/edits"     # --ref（参考の画像を渡す）の時
LOG = Path(os.path.expanduser("~/.video_edit_rules/gen_image_log.csv"))
MONTH_LIMIT = 10.0       # ドル。ユーザー指示 2026-10-05「月の上限は10ドル」
MAX_N = 4
# 1M トークンあたりのドル（公式の料金表 developers.openai.com/api/docs/pricing、2026-10-05 確認）：文字の入力・画像の入力・画像の出力
PRICE = {
    "gpt-image-2.5-flare": (5.00, 8.00, 30.00),
    "gpt-image-2.5-sunburst": (5.00, 8.00, 30.00),
    "gpt-image-2": (5.00, 8.00, 30.00),
    "gpt-image-1.5": (5.00, 8.00, 32.00),
    "gpt-image-1-mini": (2.00, 2.50, 8.00),
}
FIELDS = ["日時", "モデル", "大きさ", "品質", "枚数", "入力トークン", "出力トークン", "ドル", "ファイル", "指示"]


def api_key():
    try:
        r = subprocess.run(["security", "find-generic-password", "-s", "openai_api_key", "-w"],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            if not r.stdout.strip().startswith("sk-"):
                raise SystemExit("キーチェーンの openai_api_key が API キー（sk- で始まる）ではない。ユーザーに入れ直してもらう：\n"
                                 '  security add-generic-password -U -a "$USER" -s openai_api_key -w "$(pbpaste)"（キーをコピーしてから）')
            return r.stdout.strip()
    except FileNotFoundError:
        pass
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    raise SystemExit("OpenAI の API キーが無い。ユーザーにターミナルで次を打ってもらう（聞かれたらキーを貼る）：\n"
                     '  security add-generic-password -U -a "$USER" -s openai_api_key -w "$(pbpaste)"（キーをコピーしてから）')


def month_total(now):
    if not LOG.exists():
        return 0.0
    ym = now.strftime("%Y-%m")
    with open(LOG, newline="") as f:
        return sum(float(r["ドル"] or 0) for r in csv.DictReader(f) if r["日時"].startswith(ym))


def cost(model, usage):
    """API の usage からドルを出す。分け方が返らない所は、入力は文字・出力は画像として数える"""
    t_in, i_in, i_out = PRICE.get(model, PRICE["gpt-image-2.5-flare"])
    d = usage.get("input_tokens_details") or {}
    txt = d.get("text_tokens", usage.get("input_tokens", 0) - d.get("image_tokens", 0))
    img = d.get("image_tokens", 0)
    out = usage.get("output_tokens", 0)
    return (txt * t_in + img * i_in + out * i_out) / 1e6


def free_path(folder, name, ext):
    p = folder / f"{name}.{ext}"
    k = 2
    while p.exists():
        p = folder / f"{name}_{k}.{ext}"
        k += 1
    return p


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("prompt", nargs="?", help="指示文（日本語でよい）")
    ap.add_argument("--prompt-file", help="指示文をファイルから読む")
    ap.add_argument("--name", help="ファイルの名前（拡張子なし。英数字と _ がよい）")
    ap.add_argument("--ver", help="版のフォルダ edit/vNNN（→ <版>/zukai/assets/）")
    ap.add_argument("--out", help="置くフォルダ（--ver の代わり）")
    ap.add_argument("--model", default="gpt-image-2.5-flare", choices=sorted(PRICE))
    ap.add_argument("--size", default="1536x1024", help="1536x1024（横・既定）・1024x1024・1024x1536 か 幅x高さ")
    ap.add_argument("--quality", default="medium", choices=["low", "medium", "high", "xhigh", "max", "auto"])
    ap.add_argument("--background", default="auto", choices=["auto", "transparent", "opaque"])
    ap.add_argument("--format", default="png", choices=["png", "webp", "jpeg"])
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--dry", action="store_true", help="送らずに、送る中身と今月の額だけ出す")
    ap.add_argument("--month", action="store_true", help="今月かかった額だけ出す")
    ap.add_argument("--ref", action="append", default=[], help="参考の画像（何回でも）。あれば images/edits で作る")
    ap.add_argument("--fidelity", default="none", choices=["high", "low", "none"], help="--ref の顔の寄せ方（none＝送らない。gpt-image-2.5-flare は受け付けない 2026-10-12）")
    ap.add_argument("--moderation", default="low", choices=["low", "auto"], help="API の検査の強さ（既定 low＝緩く。--ref の時は送らない）")
    ap.add_argument("--mask", help="描き直す所を透明にした PNG（1枚目の --ref と同じ大きさ。透明の所だけ描き直す。images/edits の mask）")
    a = ap.parse_args()

    now = dt.datetime.now()
    spent = month_total(now)
    if a.month:
        print(f"{now:%Y-%m} にかかった額：${spent:.3f}（手前の止め ${MONTH_LIMIT:.0f}）　記録：{LOG}")
        return
    prompt = Path(a.prompt_file).read_text().strip() if a.prompt_file else (a.prompt or "").strip()
    if not prompt or not a.name:
        ap.error("指示文と --name が要る")
    if not (a.ver or a.out):
        ap.error("--ver か --out が要る")
    if not 1 <= a.n <= MAX_N:
        ap.error(f"--n は 1〜{MAX_N}")
    if a.background == "transparent" and a.format == "jpeg":
        ap.error("透明は png か webp")
    folder = Path(os.path.expanduser(a.out)) if a.out else Path(os.path.expanduser(a.ver)) / "zukai" / "assets"
    if spent >= MONTH_LIMIT:
        raise SystemExit(f"今月はもう ${spent:.2f} かかっている（止め ${MONTH_LIMIT:.0f}）。続けるかユーザーに聞く")

    body = {"model": a.model, "prompt": prompt, "size": a.size, "quality": a.quality,
            "background": a.background, "output_format": a.format, "n": a.n}
    if not a.ref:
        body["moderation"] = a.moderation      # images/edits は受け付けない（公式の API の説明、2026-10-21 確認）
    if a.mask and not a.ref:
        ap.error("--mask は --ref（描き直す元の絵を1枚目に）と一緒に使う")
    if a.dry:
        print(json.dumps(dict(body, ref=a.ref, input_fidelity=a.fidelity, mask=a.mask), ensure_ascii=False, indent=2))
        print(f"置く所：{folder}　今月：${spent:.3f}")
        return

    if a.ref:
        import mimetypes
        import uuid as _uuid
        bnd = "----gen" + _uuid.uuid4().hex
        parts = []
        fields = dict(body)
        if a.fidelity != "none":
            fields["input_fidelity"] = a.fidelity
        for k, v in fields.items():
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        for rp in a.ref:
            rp = Path(os.path.expanduser(rp))
            mt = mimetypes.guess_type(rp.name)[0] or "image/png"
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="image[]"; filename="{rp.name}"\r\n'
                         f'Content-Type: {mt}\r\n\r\n'.encode() + rp.read_bytes() + b"\r\n")
        if a.mask:
            mp = Path(os.path.expanduser(a.mask))
            parts.append(f'--{bnd}\r\nContent-Disposition: form-data; name="mask"; filename="{mp.name}"\r\n'
                         f'Content-Type: image/png\r\n\r\n'.encode() + mp.read_bytes() + b"\r\n")
        parts.append(f"--{bnd}--\r\n".encode())
        req = urllib.request.Request(API_EDIT, data=b"".join(parts), method="POST",
                                     headers={"Authorization": f"Bearer {api_key()}", "Content-Type": f"multipart/form-data; boundary={bnd}"})
    else:
        req = urllib.request.Request(API, data=json.dumps(body).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {api_key()}", "Content-Type": "application/json"})
    print(f"作っている（{a.model}・{a.size}・{a.quality}・{a.n}枚）…", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            res = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e).get("error", {}).get("message", "")
        except Exception:
            msg = ""
        hint = ""
        if e.code == 401:
            hint = "\n  キーが違うか途中で切れている（入力の画面に貼ると 128文字で切れる）。キーをコピーして security … -w \"$(pbpaste)\" で入れ直してもらう"
        elif e.code == 429 and "credits" in msg:
            hint = "\n  OpenAI の API のクレジットが無い。ユーザーに platform.openai.com の Billing で足してもらう（ChatGPT の契約とは別）"
        raise SystemExit(f"API が断った（{e.code}）：{msg}{hint}")

    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for d in res.get("data", []):
        p = free_path(folder, a.name, a.format)
        p.write_bytes(base64.b64decode(d["b64_json"]))
        files.append(p)
    usage = res.get("usage") or {}
    usd = cost(a.model, usage)

    with open(folder / "出どころ.md", "a") as f:
        for p in files:
            f.write(f"- {p.name}：AI で作った絵（OpenAI {a.model}、{a.size}・{a.quality}、{now:%Y-%m-%d %H:%M}、tools/gen_image.py）。"
                    f"名札に「（イメージ）」を付ける。指示：「{prompt}」" + (f"。参考の画像：{', '.join(Path(r).name for r in a.ref)}" if a.ref else "") + "\n")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG.exists()
    with open(LOG, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({"日時": f"{now:%Y-%m-%d %H:%M:%S}", "モデル": a.model, "大きさ": a.size, "品質": a.quality, "枚数": len(files),
                    "入力トークン": usage.get("input_tokens", ""), "出力トークン": usage.get("output_tokens", ""),
                    "ドル": f"{usd:.4f}", "ファイル": " ".join(str(p) for p in files), "指示": prompt[:200]})
    for p in files:
        print(p)
    print(f"かかった額：${usd:.4f}（入力 {usage.get('input_tokens', '?')}・出力 {usage.get('output_tokens', '?')} トークン）"
          f"　今月の合計：${spent + usd:.3f}")


if __name__ == "__main__":
    main()
