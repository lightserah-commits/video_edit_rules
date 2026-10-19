#!/usr/bin/env python3
"""書き出した動画を、出先のスマホで見るために YouTube（個人のチャンネル）へ「非公開」で上げる（2026-10-16 ユーザー OK）。

なぜ：出先で Jump Desktop から版を見るのが不便。YouTube アプリなら読み込みながら見られる（自分のアカウントでログインしていれば非公開でも見られる）。
決まり：
  - 上げる先は個人のチャンネル。みかみCH には上げない（途中の版が Studio に並ぶ・誤って公開する・BGM の申し立てが付く）。
    許可の時にチャンネル名を控え、上げる時に同じチャンネルか確かめる。名前に「みかみ」「三上」「mikami」が入るチャンネルでは止める
  - 公開範囲は「非公開」だけ。この道具には公開・限定公開にする道が無い
    （審査前の Google Cloud のプロジェクトから API で上げた動画は、どのみち非公開に固定される。2020-07-28 以降に作ったプロジェクト）
  - 上げるのは外へ送ること。送る前に --dry で中身（ファイル・題名・チャンネル）をチャットに出し、ユーザーの OK をもらってから送る
  - 同じファイルを2回上げない（動画の横の <名前>.youtube.json があれば止める。上げ直す時は --again）
鍵：~/.video_edit_rules/youtube/（Git に入らない。iMac では iMac で許可し直す）
  client_secret.json … Google Cloud の Google Auth Platform →「クライアント」→ 種類「デスクトップ アプリ」で作った時の JSON
                       （鍵が取れるのは作った時だけ。無くしたらクライアントの画面の「Add Secret」で作り直す）
  token.json        … 許可でもらった鍵と、上げる先のチャンネル
  中身はチャットにも Addness にも書かない。Google Cloud の「対象」が「テスト中」のままだと7日ごとに許可し直しになる（「アプリを公開」にしておく）
ライブラリは使わない（Python の標準だけ。システムの python3 3.9 でも動く）。

使い方:
  python3 tools/youtube_upload.py auth --import ~/Downloads/client_secret_xxx.json   （初回。JSON を鍵の置き場へ移し、Chrome に許可の画面を出す）
  python3 tools/youtube_upload.py whoami                                              （上がる先のチャンネル）
  python3 tools/youtube_upload.py upload "<案件>/edit/v007/cproj_v007.mp4" --dry      （送らずに中身だけ見る）
  python3 tools/youtube_upload.py upload "<案件>/edit/v007/cproj_v007.mp4" [--title "..."] [--description "..."]
  python3 tools/youtube_upload.py status <動画ID> [--wait]                            （YouTube の処理が終わったか。--wait は終わるまで30秒ごと・30分まで）
  題名を渡さなければ「【プレビュー】<案件名> <ファイル名>（MM/DD HH:MM 書き出し）」。
  上げたら、動画の横に <名前>.youtube.json を書き、~/.video_edit_rules/youtube/uploads.jsonl に足す。
  途中で切れたら、同じコマンドをもう一度打つと続きから上げる（YouTube がもう受け付けなければ最初から）。
"""
import argparse
import base64
import datetime as dt
import hashlib
import http.client
import http.server
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KEY_DIR = os.path.expanduser("~/.video_edit_rules/youtube")
CLIENT_PATH = os.path.join(KEY_DIR, "client_secret.json")
TOKEN_PATH = os.path.join(KEY_DIR, "token.json")
PENDING_DIR = os.path.join(KEY_DIR, "pending")
LOG_PATH = os.path.join(KEY_DIR, "uploads.jsonl")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",  # チャンネル名と処理の状況を見るため
]
AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"
API = "https://www.googleapis.com/youtube/v3"
UPLOAD_URI = "https://www.googleapis.com/upload/youtube/v3/videos"
CHUNK = 32 * 1024 * 1024  # 256KB の倍数にする（YouTube の決まり）
NG_CHANNEL_WORDS = ("みかみ", "三上", "mikami")
PRIVACY = "private"  # 変えない（上の「決まり」）


def die(msg):
    print(f"止めた：{msg}", file=sys.stderr)
    sys.exit(1)


def write_secret(path, data):
    os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def load_client():
    if not os.path.exists(CLIENT_PATH):
        die(f"{CLIENT_PATH} が無い。先に auth --import <ダウンロードした JSON> を打つ")
    with open(CLIENT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    c = data.get("installed")
    if not c:
        die("client_secret.json が「デスクトップ アプリ」のものではない（installed が無い）。Google Cloud で種類「デスクトップ アプリ」のクライアントを作り直す")
    return c


def post_form(url, fields):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"error": str(e)}
        return {"_http_error": e.code, **err}


# ---- 許可 ----

def run_auth(import_path):
    if import_path:
        src = os.path.expanduser(import_path)
        if not os.path.exists(src):
            die(f"{src} が無い")
        with open(src, encoding="utf-8") as f:
            if "installed" not in json.load(f):
                die("この JSON は「デスクトップ アプリ」のものではない（installed が無い）")
        os.makedirs(KEY_DIR, mode=0o700, exist_ok=True)
        shutil.move(src, CLIENT_PATH)
        os.chmod(CLIENT_PATH, 0o600)
        print(f"鍵の JSON を移した：{CLIENT_PATH}")
    client = load_client()

    verifier = base64.urlsafe_b64encode(secrets.token_bytes(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    got = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if "code" not in q and "error" not in q:
                self.send_response(404)
                self.end_headers()
                return
            got.update({k: v[0] for k, v in q.items()})
            ok = "code" in q and q.get("state", [""])[0] == state
            msg = "許可を受け取りました。このタブは閉じてかまいません。" if ok else "許可を受け取れませんでした。チャットに戻ってください。"
            body = f"<html><meta charset='utf-8'><body style='font:20px sans-serif;padding:40px'>{msg}</body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    server.timeout = 5
    redirect = f"http://127.0.0.1:{server.server_port}/"
    url = AUTH_URI + "?" + urllib.parse.urlencode({
        "client_id": client["client_id"],
        "redirect_uri": redirect,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
    })
    print("ブラウザに Google の許可の画面を出した。個人のチャンネルを選んで「許可」を押してもらう（5分待つ）")
    print("「このアプリは Google で確認されていません」は、自分で作ったアプリなので出る。「詳細」→「…（安全ではないページ）に移動」で進む")
    print(f"開かなければこの URL：{url}")
    subprocess.run(["open", url], check=False)
    end = time.time() + 300
    while not got and time.time() < end:
        server.handle_request()
    server.server_close()
    if not got:
        die("5分のうちに許可が来なかった")
    if got.get("error"):
        die(f"Google が断った：{got['error']}")
    if got.get("state") != state:
        die("返ってきた state が合わない（別の画面からの返事かもしれない）")

    fields = {
        "code": got["code"],
        "client_id": client["client_id"],
        "redirect_uri": redirect,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    }
    if client.get("client_secret"):
        fields["client_secret"] = client["client_secret"]
    tok = post_form(client.get("token_uri", TOKEN_URI), fields)
    if "_http_error" in tok or "refresh_token" not in tok:
        die(f"鍵をもらえなかった：{tok.get('error')} {tok.get('error_description', '')}")
    granted = set(tok.get("scope", "").split())
    if SCOPES[0] not in granted:
        die("「動画のアップロード」の許可にチェックが入っていなかった。もう一度 auth を打ち、全部にチェックを入れて許可する")
    token = {
        "refresh_token": tok["refresh_token"],
        "access_token": tok["access_token"],
        "expires_at": time.time() + int(tok.get("expires_in", 3600)) - 60,
        "scope": tok.get("scope", ""),
        "authorized_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    write_secret(TOKEN_PATH, token)
    ch = my_channel(token)
    check_channel_name(ch["title"])
    token["channel_id"], token["channel_title"] = ch["id"], ch["title"]
    write_secret(TOKEN_PATH, token)
    print(f"許可できた。上がる先のチャンネル：{ch['title']}（{ch['id']}）")


def check_channel_name(title):
    low = title.lower()
    if any(w in low for w in NG_CHANNEL_WORDS):
        os.remove(TOKEN_PATH)
        die(f"「{title}」は みかみCH に見える。プレビューは個人のチャンネルに上げる。auth を打ち直し、個人のチャンネルを選ぶ")


def load_token():
    if not os.path.exists(TOKEN_PATH):
        die("まだ許可していない。auth を打つ")
    with open(TOKEN_PATH, encoding="utf-8") as f:
        return json.load(f)


def access_token(token, force=False):
    if not force and token.get("access_token") and time.time() < token.get("expires_at", 0):
        return token["access_token"]
    client = load_client()
    fields = {
        "refresh_token": token["refresh_token"],
        "client_id": client["client_id"],
        "grant_type": "refresh_token",
    }
    if client.get("client_secret"):
        fields["client_secret"] = client["client_secret"]
    tok = post_form(client.get("token_uri", TOKEN_URI), fields)
    if "_http_error" in tok:
        if tok.get("error") == "invalid_grant":
            die("鍵が切れた（7日で切れたなら Google Cloud の「対象」が「テスト中」のまま）。auth を打ち直す")
        die(f"鍵を新しくできなかった：{tok.get('error')} {tok.get('error_description', '')}")
    token["access_token"] = tok["access_token"]
    token["expires_at"] = time.time() + int(tok.get("expires_in", 3600)) - 60
    write_secret(TOKEN_PATH, token)
    return token["access_token"]


def api_get(token, path, params):
    url = f"{API}/{path}?" + urllib.parse.urlencode(params)
    for attempt in range(2):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token(token, force=attempt > 0)}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                continue
            die(f"YouTube が断った（{e.code}）：{e.read().decode()[:500]}")


def my_channel(token):
    res = api_get(token, "channels", {"part": "snippet", "mine": "true"})
    items = res.get("items") or []
    if not items:
        die("このアカウントには YouTube のチャンネルが無い。YouTube でチャンネルを作ってから auth を打ち直す")
    return {"id": items[0]["id"], "title": items[0]["snippet"]["title"]}


# ---- 上げる ----

def case_name(path):
    parts = os.path.abspath(path).split(os.sep)
    if "edit" in parts:
        i = len(parts) - 1 - parts[::-1].index("edit")
        if i > 0:
            return parts[i - 1]
    return ""


def clean_title(s):
    s = s.replace("<", "＜").replace(">", "＞").strip()  # YouTube は < > を受け付けない
    return s[:100]


def default_title(path):
    mtime = dt.datetime.fromtimestamp(os.path.getmtime(path))
    stem = os.path.splitext(os.path.basename(path))[0]
    case = case_name(path)
    head = f"{case} {stem}" if case else stem
    return clean_title(f"【プレビュー】{head}（{mtime:%m/%d %H:%M} 書き出し）")


def human(n):
    return f"{n / 1024 ** 3:.2f}GB" if n >= 1024 ** 3 else f"{n / 1024 ** 2:.0f}MB"


def pending_path(path, size, mtime):
    key = hashlib.sha1(f"{os.path.abspath(path)}|{size}|{mtime}".encode()).hexdigest()[:16]
    return os.path.join(PENDING_DIR, key + ".json")


def start_session(token, meta, size, ctype):
    q = urllib.parse.urlencode({"uploadType": "resumable", "part": "snippet,status", "notifySubscribers": "false"})
    body = json.dumps(meta, ensure_ascii=False).encode()
    for attempt in range(2):
        req = urllib.request.Request(f"{UPLOAD_URI}?{q}", data=body, method="POST", headers={
            "Authorization": f"Bearer {access_token(token, force=attempt > 0)}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Length": str(size),
            "X-Upload-Content-Type": ctype,
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                loc = r.headers.get("Location")
                if not loc:
                    die("YouTube が上げる先の URL を返さなかった")
                return loc
        except urllib.error.HTTPError as e:
            if e.code == 401 and attempt == 0:
                continue
            text = e.read().decode()[:800]
            if "quotaExceeded" in text or "uploadLimitExceeded" in text:
                die("今日の YouTube の上げられる量を使い切った。明日（太平洋時間の0時、日本の16時か17時）にやり直す")
            die(f"YouTube が断った（{e.code}）：{text}")


def put(session, token, headers, data=b""):
    """(状態コード, 受け取った所の終わり or None, 本文)。つながらない時は (None, None, 理由)"""
    u = urllib.parse.urlparse(session)
    h = {"Authorization": f"Bearer {access_token(token)}", "Content-Length": str(len(data)), **headers}
    try:
        conn = http.client.HTTPSConnection(u.netloc, timeout=300)
        conn.request("PUT", u.path + ("?" + u.query if u.query else ""), body=data, headers=h)
        r = conn.getresponse()
        body = r.read().decode(errors="replace")
        rng = r.getheader("Range")
        conn.close()
    except (OSError, http.client.HTTPException) as e:
        return None, None, str(e)
    end = int(rng.split("-")[-1]) if rng else None
    return r.status, end, body


def ask_offset(session, token, size):
    """YouTube がどこまで受け取ったか。(次に送る位置, 終わっていれば動画の情報, もう使えなければ True)"""
    st, end, body = put(session, token, {"Content-Range": f"bytes */{size}"})
    if st in (200, 201):
        return size, json.loads(body), False
    if st == 308:
        return (end + 1 if end is not None else 0), None, False
    if st in (404, 410):
        return 0, None, True
    return None, None, False


def upload(args):
    path = os.path.abspath(os.path.expanduser(args.file))
    if not os.path.isfile(path):
        die(f"{path} が無い")
    size = os.path.getsize(path)
    mtime = int(os.path.getmtime(path))
    ext = os.path.splitext(path)[1].lower()
    ctype = {".mp4": "video/mp4", ".mov": "video/quicktime", ".m4v": "video/x-m4v"}.get(ext)
    if not ctype:
        die(f"{ext} は上げない（mp4 か mov）")
    sidecar = os.path.splitext(path)[0] + ".youtube.json"
    if os.path.exists(sidecar) and not args.again:
        with open(sidecar, encoding="utf-8") as f:
            prev = json.load(f)
        die(f"このファイルはもう上げてある：{prev.get('url')}（上げ直すなら --again）")

    token = load_token()
    ch = my_channel(token)
    if ch["id"] != token.get("channel_id"):
        die(f"許可した時のチャンネル（{token.get('channel_title')}）と、今のチャンネル（{ch['title']}）が違う。auth を打ち直す")
    check_channel_name(ch["title"])

    title = clean_title(args.title) if args.title else default_title(path)
    exported = dt.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    desc = args.description if args.description is not None else (
        f"video_edit_rules のプレビュー（非公開）。\nファイル：{os.path.basename(path)}（{human(size)}）\n書き出し：{exported}")
    meta = {
        "snippet": {"title": title, "description": desc[:5000], "categoryId": "22"},
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False},
    }
    print(f"ファイル：{path}（{human(size)}・書き出し {exported}）")
    print(f"題名：{title}")
    print(f"チャンネル：{ch['title']}（{ch['id']}）")
    print(f"公開範囲：非公開（{PRIVACY}）")
    if args.dry:
        print("（--dry なので送っていない）")
        return

    os.makedirs(PENDING_DIR, mode=0o700, exist_ok=True)
    pend = pending_path(path, size, mtime)
    session, offset, done = None, 0, None
    if os.path.exists(pend):
        with open(pend, encoding="utf-8") as f:
            session = json.load(f)["session"]
        offset, done, gone = ask_offset(session, token, size)
        if gone or offset is None:
            session, offset = None, 0
        else:
            print(f"前の続きから上げる（{human(offset)} まで受け取り済み）")
    if session is None:
        session = start_session(token, meta, size, ctype)
        write_secret(pend, {"session": session, "file": path, "started": dt.datetime.now().isoformat(timespec="seconds")})

    t0, sent0, fails = time.time(), offset, 0
    with open(path, "rb") as f:
        while done is None:
            f.seek(offset)
            data = f.read(CHUNK)
            last = offset + len(data) - 1
            st, end, body = put(session, token, {"Content-Range": f"bytes {offset}-{last}/{size}", "Content-Type": ctype}, data)
            if st in (200, 201):
                done = json.loads(body)
                break
            if st == 308:
                offset = end + 1 if end is not None else 0
                fails = 0
                el = time.time() - t0
                speed = (offset - sent0) / el if el > 0 else 0
                rest = (size - offset) / speed if speed > 0 else 0
                print(f"  {human(offset)}/{human(size)}（{offset * 100 // size}%）・{speed / 1024 ** 2:.1f}MB/秒・残り 約{int(rest // 60)}分", flush=True)
                continue
            if st == 401:
                access_token(token, force=True)
                continue
            if st is not None and st < 500:
                die(f"YouTube が断った（{st}）：{body[:800]}")
            fails += 1
            if fails > 8:
                die(f"つながらないのが続いた（{body[:200]}）。同じコマンドをもう一度打つと続きから上げる")
            wait = min(2 ** fails, 120)
            print(f"  つながらなかった（{st or body[:80]}）。{wait}秒待ってやり直す", flush=True)
            time.sleep(wait)
            o, d, gone = ask_offset(session, token, size)
            if gone:
                os.remove(pend)
                die("YouTube がこの上げ途中を受け付けなくなった。同じコマンドをもう一度打つと最初から上げる")
            if d:
                done = d
            elif o is not None:
                offset = o

    os.remove(pend)
    vid = done["id"]
    rec = {
        "video_id": vid,
        "url": f"https://youtu.be/{vid}",
        "studio": f"https://studio.youtube.com/video/{vid}/edit",
        "title": title,
        "privacy": done.get("status", {}).get("privacyStatus", PRIVACY),
        "channel": ch["title"],
        "file": path,
        "size": size,
        "exported": exported,
        "uploaded_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(sidecar, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=1)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"上げた：{rec['url']}（{rec['privacy']}）。YouTube の処理が終わるまで見られないことがある → status {vid}")
    print(json.dumps(rec, ensure_ascii=False))


def status(args):
    token = load_token()
    end = time.time() + (1800 if args.wait else 0)
    while True:
        res = api_get(token, "videos", {"part": "status,processingDetails,snippet", "id": args.video_id})
        items = res.get("items") or []
        if not items:
            die("その動画が見つからない（ID が違うか、別のチャンネル）")
        v = items[0]
        s, p = v.get("status", {}), v.get("processingDetails", {})
        up, proc = s.get("uploadStatus"), p.get("processingStatus")
        line = f"{v['snippet']['title']}｜上げ：{up}｜処理：{proc or '-'}｜公開範囲：{s.get('privacyStatus')}"
        if s.get("failureReason") or s.get("rejectionReason"):
            line += f"｜理由：{s.get('failureReason') or s.get('rejectionReason')}"
        print(line, flush=True)
        if up in ("processed", "failed", "rejected", "deleted") or proc in ("succeeded", "failed", "terminated") or time.time() >= end:
            print(f"https://youtu.be/{args.video_id}")
            return
        time.sleep(30)


def main():
    ap = argparse.ArgumentParser(description="書き出した動画を YouTube（個人のチャンネル）へ非公開で上げる")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("auth", help="初回の許可")
    a.add_argument("--import", dest="import_path", help="ダウンロードした client_secret_….json（鍵の置き場へ移す）")
    sub.add_parser("whoami", help="上がる先のチャンネル")
    u = sub.add_parser("upload", help="非公開で上げる")
    u.add_argument("file")
    u.add_argument("--title")
    u.add_argument("--description")
    u.add_argument("--dry", action="store_true", help="送らずに中身だけ見る")
    u.add_argument("--again", action="store_true", help="上げたことがあっても上げ直す")
    s = sub.add_parser("status", help="YouTube の処理の状況")
    s.add_argument("video_id")
    s.add_argument("--wait", action="store_true", help="終わるまで30秒ごとに見る（30分まで）")
    args = ap.parse_args()
    if args.cmd == "auth":
        run_auth(args.import_path)
    elif args.cmd == "whoami":
        token = load_token()
        ch = my_channel(token)
        print(f"{ch['title']}（{ch['id']}）・許可 {token.get('authorized_at')}")
    elif args.cmd == "upload":
        upload(args)
    elif args.cmd == "status":
        status(args)


if __name__ == "__main__":
    main()
