#!/usr/bin/env python3
"""途中の版の軽い mp4（…_light.mp4）をブラウザで見て、時刻つきの直しを書くページ。自分の PC の中だけで動く（外へ送らない）。
2026-11-02 小川さん「ブラウザだけで確認できて、最後の版だけ書き出すのが理想」。Addness bfa3aa1e-b76b-481d-a2e2-07da9739d8ca

  python3 tools/review_server.py [--port 8780] [--root ~/Desktop/みかみ案件依頼書]
  http://localhost:8780 を開く

- 一覧：<root>/<案件>/edit/v*/ の …_light.mp4（tools/premiere_case/export.py --light の出力）を新しい順に出す
- 直し：mp4 の隣の <名前>_直し.json に保存する（AI はこれを読む）。書いたらすぐ保存し、開き直しても残る
- 音は自動で鳴らさない（再生は人が押した時だけ）
"""
import argparse
import glob
import hashlib
import json
import os
import re
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

CHUNK = 1024 * 1024
MAX_NOTES_BYTES = 2 * 1024 * 1024
WRITING_SEC = 30  # 最後に書かれてからこれより短い mp4 は書き出しの途中とみなして一覧に出さない

PAGE = r"""<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>版の確認</title>
<style>
:root{--bg:#fff;--fg:#1a1a1a;--sub:#666;--line:#ddd;--box:#f5f5f5;--accent:#1f5fd0;--danger:#b3261e}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--sub:#aaa;--line:#3a3a3a;--box:#222;--accent:#7aa7ff;--danger:#ff8a80}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.6 -apple-system,"Hiragino Sans",sans-serif}
header{display:flex;gap:12px;align-items:center;padding:10px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:16px;margin:0}select{font:inherit;padding:4px 6px;max-width:100%;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px}
main{display:grid;grid-template-columns:minmax(0,1fr) 360px;gap:16px;padding:16px;align-items:start}
@media (max-width:900px){main{grid-template-columns:minmax(0,1fr)}}
video{width:100%;background:#000;border-radius:6px;display:block;cursor:pointer}#seek{width:100%;margin:8px 0 0}
.bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0}
button{font:inherit;padding:4px 10px;background:var(--box);color:var(--fg);border:1px solid var(--line);border-radius:6px;cursor:pointer}
button.on{border-color:var(--accent);color:var(--accent)}button.main{background:var(--accent);border-color:var(--accent);color:#fff}
@media (prefers-color-scheme:dark){button.main{color:#111}}
.time{font-variant-numeric:tabular-nums;font-weight:600}.sub{color:var(--sub);font-size:13px}
textarea{width:100%;font:inherit;padding:8px;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:6px;min-height:72px}
ol{list-style:none;margin:8px 0 0;padding:0}li{border-top:1px solid var(--line);padding:8px 0;display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:start}
li p{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}li button{padding:0 8px}.del{color:var(--danger)}
.empty{color:var(--sub);padding:24px 16px}
</style></head><body>
<header><h1>版の確認</h1><select id="pick" aria-label="見る版"></select><span id="info" class="sub"></span></header>
<div id="none" class="empty" hidden>軽い書き出し（…_light.mp4）がまだありません。</div>
<main id="main" hidden>
<section>
<video id="v" preload="metadata" playsinline></video>
<input id="seek" type="range" min="0" max="1000" value="0" step="any" aria-label="再生の位置">
<div class="bar"><button id="play" class="main">再生</button><span class="time"><span id="now">0:00.00</span> / <span id="dur">0:00</span></span>
<label class="sub">音量 <input id="vol" type="range" min="0" max="1" step="0.05" value="1" aria-label="音量"></label><button id="full">全画面</button></div>
<div class="bar"><button data-j="-5">−5秒</button><button data-j="-1">−1秒</button><button data-j="1">+1秒</button><button data-j="5">+5秒</button>
<button data-r="1" class="on">1倍</button><button data-r="1.5">1.5倍</button><button data-r="2">2倍</button></div>
<div class="sub">キー：スペース＝再生と止める／← →＝1秒／, .＝1コマ／n＝今の時刻で直しを書く</div>
</section>
<aside>
<div class="bar"><span>直しを書く時刻 <span class="time" id="at">0:00.00</span></span><button id="setAt">今の時刻にする</button></div>
<textarea id="text" placeholder="直したいことを書く（⌘+Enter で追加）"></textarea>
<div class="bar"><button id="add" class="main">追加</button><span id="saved" class="sub"></span></div>
<ol id="notes"></ol>
</aside>
</main>
<script>
var FPS=29.97,items=[],cur=null,notes=[],at=0,$=function(i){return document.getElementById(i)},v=$('v');
function fmt(t){t=Math.max(0,t||0);var h=Math.floor(t/3600),m=Math.floor(t/60)%60,s=t%60,ss=s.toFixed(2).padStart(5,'0');return (h?h+':'+String(m).padStart(2,'0'):m)+':'+ss}
function setAt(t){at=t;$('at').textContent=fmt(t)}
function draw(){var o=$('notes');o.textContent='';notes.slice().sort(function(a,b){return a.t-b.t}).forEach(function(n){var li=document.createElement('li');
 var b=document.createElement('button');b.textContent=fmt(n.t);b.onclick=function(){v.currentTime=n.t;setAt(n.t)};
 var p=document.createElement('p');p.textContent=n.text;
 var d=document.createElement('button');d.textContent='消す';d.className='del';d.onclick=function(){notes.splice(notes.indexOf(n),1);save();draw()};
 li.append(b,p,d);o.append(li)})}
function save(){$('saved').textContent='保存中…';fetch('/notes?id='+cur.id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({notes:notes})}).then(function(r){if(!r.ok)throw r.status;$('saved').textContent='保存しました（'+notes.length+'件）'}).catch(function(){$('saved').textContent='保存できませんでした'})}
function open(it){cur=it;v.pause();v.src='/video?id='+it.id;$('info').textContent=it.size+'・'+it.when;notes=[];setAt(0);draw();$('saved').textContent='';location.hash=it.id;
 fetch('/notes?id='+it.id).then(function(r){return r.json()}).then(function(d){notes=d.notes||[];draw()})}
function jump(d){v.currentTime=Math.max(0,v.currentTime+d)}
function add(){var t=$('text').value.trim();if(!t)return;notes.push({t:at,text:t});$('text').value='';save();draw();setAt(v.currentTime)}
fetch('/list').then(function(r){return r.json()}).then(function(d){items=d.items;if(!items.length){$('none').hidden=false;return}
 $('main').hidden=false;items.forEach(function(it){var o=document.createElement('option');o.value=it.id;o.textContent=it.label;$('pick').append(o)});
 var h=location.hash.slice(1),it=items.filter(function(x){return x.id===h})[0]||items[0];$('pick').value=it.id;open(it)});
$('pick').onchange=function(){open(items.filter(function(x){return x.id===$('pick').value})[0])};
var dragging=false;
function shown(){$('now').textContent=fmt(v.currentTime);if(!dragging&&v.duration)$('seek').value=v.currentTime/v.duration*1000}
function toggle(){v.paused?v.play():v.pause()}
v.onclick=toggle;$('play').onclick=toggle;v.onplay=function(){$('play').textContent='止める'};
v.onloadedmetadata=function(){$('dur').textContent=fmt(v.duration).replace(/\.\d+$/,'');shown()};
$('seek').oninput=function(){dragging=true;if(v.duration)v.currentTime=this.value/1000*v.duration};
$('seek').onchange=function(){dragging=false};
$('vol').oninput=function(){v.volume=+this.value};
$('full').onclick=function(){v.requestFullscreen&&v.requestFullscreen()};
v.ontimeupdate=shown;
v.onseeked=function(){shown();if(document.activeElement!==$('text'))setAt(v.currentTime)};
v.onpause=function(){$('play').textContent='再生';if(document.activeElement!==$('text'))setAt(v.currentTime)};
document.querySelectorAll('[data-j]').forEach(function(b){b.onclick=function(){jump(+b.dataset.j)}});
document.querySelectorAll('[data-r]').forEach(function(b){b.onclick=function(){v.playbackRate=+b.dataset.r;document.querySelectorAll('[data-r]').forEach(function(x){x.classList.toggle('on',x===b)})}});
$('setAt').onclick=function(){setAt(v.currentTime)};$('add').onclick=add;
$('text').onfocus=function(){setAt(v.currentTime);v.pause()};
$('text').onkeydown=function(e){if(e.key==='Enter'&&(e.metaKey||e.ctrlKey)){e.preventDefault();add()}};
document.onkeydown=function(e){var t=e.target.tagName;if(t==='TEXTAREA'||t==='SELECT'||(t==='BUTTON'&&e.key===' ')||e.metaKey||e.ctrlKey)return;
 if(e.key===' '){e.preventDefault();toggle()}else if(e.key==='ArrowLeft'){e.preventDefault();jump(-1)}else if(e.key==='ArrowRight'){e.preventDefault();jump(1)}
 else if(e.key===','){v.pause();jump(-1/FPS)}else if(e.key==='.'){v.pause();jump(1/FPS)}else if(e.key==='n'){e.preventDefault();v.pause();setAt(v.currentTime);$('text').focus()}};
</script></body></html>"""


def scan(root):
    """見られる mp4 の一覧。送ってよいのはこの一覧にあるファイルだけ（道のりを URL から受け取らない）"""
    out = {}
    for path in glob.glob(os.path.join(glob.escape(root), "*", "edit", "v*", "*_light.mp4")):
        st = os.stat(path)
        if time.time() - st.st_mtime < WRITING_SEC:
            continue
        rel = os.path.relpath(path, root).split(os.sep)
        out[hashlib.sha1(path.encode()).hexdigest()[:16]] = {
            "path": path, "mtime": st.st_mtime, "bytes": st.st_size,
            "label": f"{rel[0]} ／ {os.path.basename(path)[:-len('_light.mp4')]}",
        }
    return out


def notes_path(mp4):
    return re.sub(r"\.mp4$", "_直し.json", mp4)


class Handler(BaseHTTPRequestHandler):
    root = ""

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def item(self, url):
        return scan(self.root).get((parse_qs(url.query).get("id") or [""])[0])

    def same_origin(self):
        """ほかのサイトから直しを書き換えられないように、自分のページからの保存だけ受ける"""
        host = self.headers.get("Host", "")
        origin = self.headers.get("Origin")
        return re.fullmatch(r"(localhost|127\.0\.0\.1):\d+", host) and (origin is None or origin == f"http://{host}")

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self.send(200, PAGE.encode(), "text/html; charset=utf-8")
        if url.path == "/list":
            items = [{"id": k, "label": v["label"], "size": f"{v['bytes'] / 2**30:.2f}GB",
                      "when": datetime.fromtimestamp(v["mtime"]).strftime("%m/%d %H:%M"), "mtime": v["mtime"]}
                     for k, v in scan(self.root).items()]
            items.sort(key=lambda x: -x["mtime"])
            return self.send(200, json.dumps({"items": items}, ensure_ascii=False).encode())
        it = self.item(url)
        if url.path == "/notes":
            if not it:
                return self.send(404, b"{}")
            p = notes_path(it["path"])
            body = open(p, "rb").read() if os.path.exists(p) else b'{"notes": []}'
            return self.send(200, body)
        if url.path == "/video":
            return self.video(it) if it else self.send(404, b"{}")
        self.send(404, b"{}")

    def video(self, it):
        size = it["bytes"]
        start, end, code = 0, size - 1, 200
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:
                start = max(0, size - int(m.group(2)))
            if start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        try:
            with open(it["path"], "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    data = f.read(min(CHUNK, left))
                    if not data:
                        break
                    self.wfile.write(data)
                    left -= len(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        url = urlparse(self.path)
        it = self.item(url)
        if url.path != "/notes" or not it:
            return self.send(404, b"{}")
        if not self.same_origin():
            return self.send(403, b"{}")
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_NOTES_BYTES:
            return self.send(413, b"{}")
        try:
            notes = json.loads(self.rfile.read(n))["notes"]
            clean = [{"t": round(float(x["t"]), 3), "text": str(x["text"])} for x in notes]
        except (ValueError, KeyError, TypeError):
            return self.send(400, b"{}")
        clean.sort(key=lambda x: x["t"])
        p = notes_path(it["path"])
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"mp4": os.path.basename(it["path"]), "saved": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "notes": clean},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
        self.send(200, b'{"ok": true}')


def main():
    ap = argparse.ArgumentParser(description="途中の版の軽い mp4 をブラウザで見て直しを書くページ")
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--root", default=os.path.expanduser("~/Desktop/みかみ案件依頼書"))
    a = ap.parse_args()
    Handler.root = os.path.abspath(a.root)
    print(f"http://localhost:{a.port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
