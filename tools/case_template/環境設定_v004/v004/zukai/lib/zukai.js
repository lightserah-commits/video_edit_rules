// 環境設定 v002 の「AI が描く動く図解」の共通の動き（dots v002 の図解 make_zukai.py のページと同じ動き・同じ数字）。
// 1コマずつ決まった絵にする（CSS のアニメーション・transition・setTimeout は使わない）。render_frames.mjs が window.render(f) を呼んで撮る。
//
// ページの書き方（zukai/README.md に詳しく）：
//   <head> に <link rel="stylesheet" href="../lib/zukai.css"> と <script src="../lib/zukai.js"></script>（先に読む。Z の道具が使える）
//   <body> に <div id="board"></div>（黒い板 80%。最初から最後まで）と部品：
//   <div class="part" id="head" data-f0="0" data-m="slide" style="left:120px;top:70px"><div class="in">…</div></div>
//   最後に <script>window.ZUKAI = { frames: 900 }; /* Z.stk などで部品の中身を作ってよい */</script>
//   部品の走査は DOMContentLoaded（body の script が全部動いた後）。
// 部品の属性：
//   data-f0  出るコマ（図解の頭からのコマ）。data-f1 消えるコマ（省略で最後まで＝全部の部品が同じコマで消える）
//   data-m   出方：slide（右から流れてくる・指向性ブラー。既定）／slideL（左から）／pop（その場に出る）／bounce（その場で弾む）／
//            fade（data-dur コマで出る）／grow（中の .arr の矢印が伸びる）／draw（中の .draw の線を引く）／type（中の .type の字を1字ずつ）／none
//   data-dur 動きのコマ数（bounce 6・fade 8・grow 10・draw 12・type＝字数×2）
//   data-out "fade:8" … 消える前の 8コマで薄くなる（既定は同じコマでパッと消える。09 の共通の決まり）
//   data-dim "a-b:0.45,c-d:0.45" … そのコマの間、明るさ 0.45・彩度 0.55 に暗くする（話していない側。不透明のまま）
//   .fill の要素（data-a・data-b）… a〜b コマで幅 0→100%（カードが満ちる など）
// ページ独自の動き：window.ZUKAI.custom = (f) => 文字列（そのコマの見た目をページが変え、その印を返す。同じなら前のコマを使い回す）

// ───── 部品づくりの道具（ページの <script> から使う）
window.Z = {
  // 縁取りの文字（縁を何重にも重ねる。strokes=[[色, 太さ], ...] 外側から）
  stk(text, { size = 64, fill = "#fff", strokes = [["#000", 14]], font = "Lbl", lh = 1.12, align = "left" } = {}) {
    const t = text.replace(/\n/g, "<br>");
    const pad = Math.max(0, ...strokes.map(s => s[1])) / 2;
    const layers = strokes.map(([c, w]) => `<span style="left:${pad}px;top:${pad}px;-webkit-text-stroke:${w}px ${c};color:${c}">${t}</span>`).join("");
    return `<div class="stk" style="font-family:${font};font-size:${size}px;line-height:${lh};text-align:${align};padding:${pad}px">` +
      `<span style="position:relative;visibility:hidden">${t}</span>${layers}<span style="left:${pad}px;top:${pad}px;color:${fill}">${t}</span></div>`;
  },
  // 札（色の板に文字）
  plate(text, { size = 56, bg = "#1b5fd1", fg = "#fff", pad = "6px 26px 12px", font = "Lbl", radius = 0 } = {}) {
    return `<div class="plate" style="font-family:${font};font-size:${size}px;background:${bg};color:${fg};padding:${pad};border-radius:${radius}px">${text.replace(/\n/g, "<br>")}</div>`;
  },
  // 吹き出し（白・角丸。tail=down/up/left/right と、ずらし off px）
  bubble(text, { size = 48, tail = "down", off = 40, pad = "10px 24px 14px", font = "Lbl", width = null } = {}) {
    const t = { up: `left:${off}px;top:-26px;border-width:0 18px 28px 18px;border-color:transparent transparent #fff transparent`,
                down: `left:${off}px;bottom:-26px;border-width:28px 18px 0 18px;border-color:#fff transparent transparent transparent`,
                right: `right:-32px;top:${off}px;border-width:18px 0 18px 34px;border-color:transparent transparent transparent #fff`,
                left: `left:-32px;top:${off}px;border-width:18px 34px 18px 0;border-color:transparent #fff transparent transparent` }[tail];
    const w = width ? `width:${width}px;box-sizing:border-box;` : "";
    return `<div class="bub" style="${w}font-family:${font};font-size:${size}px;padding:${pad};line-height:1.2">${text.replace(/\n/g, "<br>")}` +
      `<div style="position:absolute;width:0;height:0;border-style:solid;${t}"></div></div>`;
  },
  // 矢印（伸びる。dir=right/left/down/up。len＝全長 px。data-m="grow" の部品の中に置く）
  _n: 0,
  arrow({ len = 300, dir = "right", color = "#e60000", shaft = 30, hl = 56, hw = 84 } = {}) {
    const v = dir === "down" || dir === "up";
    const W = v ? hw : len, H = v ? len : hw;
    const rot = { right: 0, down: 0, left: 180, up: 180 }[dir];
    const shaftR = v ? `<rect x="${(hw - shaft) / 2}" y="0" width="${shaft}" height="${len - hl + 2}" fill="${color}"/>`
                     : `<rect x="0" y="${(hw - shaft) / 2}" width="${len - hl + 2}" height="${shaft}" fill="${color}"/>`;
    const head = v ? `<polygon points="0,${len - hl} ${hw},${len - hl} ${hw / 2},${len}" fill="${color}"/>`
                   : `<polygon points="${len - hl},0 ${len},${hw / 2} ${len - hl},${hw}" fill="${color}"/>`;
    const id = "zac" + (++this._n);
    return `<svg class="arr" data-len="${len}" data-hl="${hl}" data-v="${v ? 1 : 0}" width="${W}" height="${H}" style="overflow:visible;display:block;transform:rotate(${rot}deg)">` +
      `<defs><clipPath id="${id}"><rect class="clip" x="0" y="0" width="${v ? W : 0}" height="${v ? 0 : H}"/></clipPath></defs>` +
      `<g clip-path="url(#${id})">${shaftR}</g><g class="head">${head}</g></svg>`;
  },
  img(src, { w = null, h = null, style = "" } = {}) {
    return `<img src="${src}" style="${w ? `width:${w}px;` : ""}${h ? `height:${h}px;` : ""}display:block;${style}">`;
  },
  // 素材のイラスト（~/Desktop/video_edit_rules/素材/イラスト/。名前は イラスト一覧.yaml）
  ILLUST: "file:///Users/yoshizawakouichi/Desktop/video_edit_rules/%E7%B4%A0%E6%9D%90/%E3%82%A4%E3%83%A9%E3%82%B9%E3%83%88/",
};

// ───── 1コマずつの描き方
function __zukaiInit() {
  const SLIDE = 5, BLUR = 6, DIST = 1560, BLUR_LEN = 90, GROW = 10;   // 05 の SLIDE_BLUR_RIGHT（dots v002・試作 make_v001.py と同じ）
  const cfg = window.ZUKAI || {};
  if (!cfg.frames) { window.__err = "window.ZUKAI.frames が無い"; return; }
  const N = cfg.frames;
  const svgns = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(svgns, "svg");
  defs.setAttribute("width", "0"); defs.setAttribute("height", "0"); defs.style.position = "absolute";
  document.body.appendChild(defs);

  const parts = [];
  [...document.querySelectorAll(".part, #board")].forEach((e, i) => {
    const f0 = parseInt(e.dataset.f0 || "0", 10);
    const f1 = (e.dataset.f1 && e.dataset.f1 !== "END") ? parseInt(e.dataset.f1, 10) : N;
    const m = e.id === "board" ? "none" : (e.dataset.m || "slide");
    const p = { e, i, f0, f1, m, dur: e.dataset.dur ? parseInt(e.dataset.dur, 10) : null, out: e.dataset.out || null, dim: [] };
    if (!(f0 >= 0 && f1 <= N && f0 < f1)) window.__err = `${e.id || "部品" + i} の f0/f1 がおかしい（${f0}〜${f1}、全部で ${N}）`;
    if (e.dataset.dim) for (const s of e.dataset.dim.split(",")) {
      const [r, o] = s.split(":"); const [a, b] = r.split("-").map(Number); p.dim.push([a, b, parseFloat(o)]);
    }
    if (m === "slide" || m === "slideL") {
      const f = document.createElementNS(svgns, "filter");
      f.setAttribute("id", "zb" + i); f.setAttribute("x", "-150%"); f.setAttribute("y", "-50%"); f.setAttribute("width", "400%"); f.setAttribute("height", "200%");
      const g = document.createElementNS(svgns, "feGaussianBlur"); g.setAttribute("stdDeviation", "0 0"); f.appendChild(g); defs.appendChild(f);
      p.blur = g;
    }
    if (m === "type") {
      for (const t of e.querySelectorAll(".type")) {
        const txt = t.textContent; t.textContent = "";
        for (const ch of txt) { const s = document.createElement("span"); s.textContent = ch; s.style.visibility = "hidden"; t.appendChild(s); }
      }
      p.chars = [...e.querySelectorAll(".type span")];
      if (!p.dur) p.dur = Math.max(1, p.chars.length * 2);
    }
    if (m === "draw") {
      p.paths = [...e.querySelectorAll(".draw")].map(d => { const L = d.getTotalLength ? d.getTotalLength() : 1000; d.style.strokeDasharray = `${L} ${L}`; return [d, L]; });
    }
    p.fills = [...e.querySelectorAll(".fill")].map(x => [x, parseFloat(x.dataset.a), parseFloat(x.dataset.b)]);
    parts.push(p);
  });

  // 矢印：<svg class="arr" data-len data-hl data-v> の中の .head（頭）と .clip（軸を見せる幅）
  function setArrow(svg, q) {
    const L = parseFloat(svg.dataset.len), hl = parseFloat(svg.dataset.hl), v = svg.dataset.v === "1";
    const hx = Math.max(0, q * L - hl), off = hx - (L - hl), cw = hx + hl / 2 + 10;
    for (const g of svg.querySelectorAll(".head")) g.setAttribute("transform", v ? `translate(0,${off})` : `translate(${off},0)`);
    const r = svg.querySelector(".clip");
    if (r) { if (v) r.setAttribute("height", cw); else r.setAttribute("width", cw); }
  }
  let last = null;
  function draw(f) {
    const st = [];
    for (const p of parts) {
      const e = p.e, k = f - p.f0;
      if (k < 0 || f >= p.f1) { e.style.visibility = "hidden"; st.push("h"); continue; }
      e.style.visibility = "visible";
      const inn = e.firstElementChild || e;
      let op = 1;
      if (p.m === "slide" || p.m === "slideL") {
        const sgn = p.m === "slide" ? 1 : -1;
        const off = DIST * Math.max(0, 1 - k / SLIDE) * sgn, bl = BLUR_LEN * Math.max(0, 1 - k / BLUR);
        inn.style.transform = off !== 0 ? `translateX(${off}px)` : "none";
        p.blur.setAttribute("stdDeviation", `${bl / 3} 0`);
        inn.style.filter = bl > 0 ? `url(#zb${p.i})` : "none";
        st.push(off.toFixed(1) + "/" + bl.toFixed(1));
      } else if (p.m === "bounce") {
        const D = p.dur || 6, q = Math.min(1, (k + 1) / D);
        const s = q < 1 ? (q < 0.6 ? 0.55 + 0.75 * (q / 0.6) : 1.3 - 0.3 * ((q - 0.6) / 0.4)) : 1;
        inn.style.transform = s !== 1 ? `scale(${s})` : "none";
        st.push("b" + s.toFixed(3));
      } else if (p.m === "fade") {
        const D = p.dur || 8; op = Math.min(1, (k + 1) / D); st.push("o" + op.toFixed(3));
      } else if (p.m === "grow") {
        const D = p.dur || GROW, q = Math.min(1, (k + 1) / D);
        for (const a of e.querySelectorAll(".arr")) setArrow(a, q);
        st.push("g" + q.toFixed(3));
      } else if (p.m === "draw") {
        const D = p.dur || 12, q = Math.min(1, (k + 1) / D);
        for (const [d, L] of p.paths) d.style.strokeDashoffset = `${L * (1 - q)}`;
        st.push("d" + q.toFixed(3));
      } else if (p.m === "type") {
        const n = Math.min(p.chars.length, Math.floor((k + 1) / p.dur * p.chars.length + 1e-6));
        p.chars.forEach((c, j) => { c.style.visibility = j < n ? "visible" : "hidden"; });
        st.push("t" + n);
      } else st.push("v");
      if (p.out) {
        const n = parseInt(p.out.split(":")[1] || "8", 10), r = p.f1 - f;
        if (r <= n) op = Math.min(op, r / (n + 1));
      }
      e.style.opacity = op;
      let dimv = 1;
      for (const [a, b, o] of p.dim) if (f >= a && f < b) dimv = o;
      e.style.filter = dimv < 1 ? `brightness(${dimv}) saturate(0.55)` : "none";
      if (op < 1) st.push("op" + op.toFixed(3));
      if (dimv < 1) st.push("dm" + dimv);
      for (const [x, a, b] of p.fills) {
        const q = Math.max(0, Math.min(1, (f - a) / (b - a))); x.style.width = (q * 100).toFixed(3) + "%"; st.push("f" + q.toFixed(4));
      }
    }
    if (cfg.custom) st.push(String(cfg.custom(f)));
    const sig = st.join(",");
    const changed = sig !== last; last = sig; return changed;
  }
  window.render = (i) => draw(i);
  // 採寸：部品を一度見える状態にして、画面の中の箱 [x, y, w, h] を返す（make_zukai.py がワイプ・画面の外との重なりを見る）
  window.__measure = () => {
    const r = {};
    for (const p of parts) {
      if (p.e.id === "board") continue;
      const v = p.e.style.visibility; p.e.style.visibility = "visible";
      const inn = p.e.firstElementChild || p.e; const t = inn.style.transform; inn.style.transform = "none";
      const b = p.e.getBoundingClientRect();
      let x0 = b.left, y0 = b.top, x1 = b.right, y1 = b.bottom;
      for (const c of p.e.querySelectorAll("*")) {
        const q = c.getBoundingClientRect();
        if (q.width && q.height) { x0 = Math.min(x0, q.left); y0 = Math.min(y0, q.top); x1 = Math.max(x1, q.right); y1 = Math.max(y1, q.bottom); }
      }
      r[p.e.id || ("part" + p.i)] = { box: [Math.round(x0), Math.round(y0), Math.round(x1 - x0), Math.round(y1 - y0)], f0: p.f0, f1: p.f1, m: p.m };
      inn.style.transform = t; p.e.style.visibility = v;
    }
    return r;
  };
  (async () => {
    try {
      for (const fm of ["Lbl", "Tsk", "Jp", "Hv"]) { try { await document.fonts.load(`64px ${fm}`, "あ漢A"); } catch (e) {} }
      const used = new Set([...document.querySelectorAll("*")].map(x => getComputedStyle(x).fontFamily.split(",")[0].replace(/['"]/g, "").trim()));
      const bad = [...document.fonts].filter(f => used.has(f.family) && f.status !== "loaded");
      if (bad.length) throw new Error("フォントが読めない: " + bad.map(f => f.family).join(","));
      await Promise.all([...document.images].map(im => im.decode()));
      if (cfg.ready) await cfg.ready();
      if (!window.__err) window.__ready = true;
    } catch (e) { window.__err = String(e); }
  })();
}
document.addEventListener("DOMContentLoaded", __zukaiInit);
