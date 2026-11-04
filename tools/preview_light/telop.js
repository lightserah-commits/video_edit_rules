// テロップをキャンバスに描く（確認用の映像の上に重ねる）。Premiere の値をそのまま読む
const TelopView = (() => {
  const lerp = (p, t, def) => {
    if (!p) return def;
    if (p.v) return p.v;
    const k = p.k;
    if (t <= k[0][0]) return k[0][1];
    for (let i = 1; i < k.length; i++) if (t <= k[i][0]) {
      const a = (t - k[i - 1][0]) / (k[i][0] - k[i - 1][0]);
      return k[i][1].map((v, j) => k[i - 1][1][j] + (v - k[i - 1][1][j]) * a);
    }
    return k[k.length - 1][1];
  };
  const css = (c, a = 1) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  const cache = new Map();
  function sprite(l) {
    if (l._s) return l._s;
    const st = l.style;
    const lines = [[]];
    for (const r of st.runs) {
      if (!r.font) continue;
      const parts = r.text.split(/\r\n|\r|\n/);
      parts.forEach((p, i) => { if (i) lines.push([]); if (p) lines[lines.length - 1].push({ ...r, text: p }); });
    }
    const size0 = Math.max(...st.runs.map((r) => r.size || 0), 1);
    const leading = size0 * TelopView.LEAD;
    const cv = document.createElement("canvas");
    const m = cv.getContext("2d");
    const widths = lines.map((ln) => ln.reduce((a, r) => { m.font = `${r.size}px "${r.font}"`; m.letterSpacing = "0px"; return a + m.measureText(r.text).width; }, 0));
    const tw = Math.max(...widths, 1);
    const pad = 80;
    const th = leading * lines.length + size0;
    cv.width = Math.ceil(tw + pad * 2); cv.height = Math.ceil(th + pad * 2);
    const c = cv.getContext("2d");
    c.lineJoin = "round"; c.miterLimit = 2; c.textBaseline = "alphabetic";
    const asc = size0;
    const baseY = (i) => pad + asc + leading * i;
    const lineX = (i) => st.halign === 2 ? pad + (tw - widths[i]) / 2 : (st.halign === 1 ? pad + tw - widths[i] : pad);
    if (st.bg && st.bg.on) {
      const p = st.bg.pad || 0;
      c.fillStyle = css(st.bg.color, (st.bg.opacity ?? 100) / 100);
      c.fillRect(pad - p, baseY(0) - size0 * TelopView.BG_TOP - p, tw + p * 2, leading * (lines.length - 1) + size0 * (TelopView.BG_TOP + TelopView.BG_BOT) + p * 2);
    }
    const each = (fn) => lines.forEach((ln, i) => { let x = lineX(i); for (const r of ln) { c.font = `${r.size}px "${r.font}"`; fn(r, x, baseY(i)); x += c.measureText(r.text).width; } });
    const drawOutline = (ctxFn) => each(ctxFn);
    // 影（ぼかし）：外の縁の下に敷く
    if (st.shadow && st.shadow.on && (st.shadow.blur || st.shadow.dist)) {
      c.save(); c.shadowColor = css(st.shadow.color, (st.shadow.opacity ?? 100) / 100 * (TelopView.SHADOW_A));
      c.shadowBlur = (st.shadow.blur || 0) * TelopView.SHADOW_K;
      const ang = ((st.shadow.angle || 0) - 90) * Math.PI / 180, d = st.shadow.dist || 0;
      c.shadowOffsetX = Math.cos(ang) * d; c.shadowOffsetY = Math.sin(ang) * d;
      c.strokeStyle = css(st.shadow.color, (st.shadow.opacity ?? 100) / 100); c.lineWidth = (st.shadow.size || 0);
      drawOutline((r, x, y) => { c.strokeText(r.text, x, y); c.fillStyle = css(st.shadow.color); c.fillText(r.text, x, y); });
      c.restore();
    }
    // 縁：太い方から順に。Premiere の縁は文字の輪郭の外側に幅ぶん出るので、線の太さは幅の2倍
    const strokes = [];
    for (const r of st.runs) {
      if (!r.font) continue;
      (r.strokes || []).forEach((s) => { if (s.on && s.width) strokes.push([css(s.color), s.width]); });
      if (r.x5 && r.f6) strokes.push([css(r.c4 || [255, 255, 255]), r.f6]);
      break;
    }
    strokes.sort((a, b) => b[1] - a[1]);
    for (const [col, w] of strokes) { c.strokeStyle = col; c.lineWidth = w * 2; drawOutline((r, x, y) => c.strokeText(r.text, x, y)); }
    drawOutline((r, x, y) => { c.fillStyle = css(r.fill || [255, 255, 255]); c.fillText(r.text, x, y); });
    l._s = { cv, pad, tw, lines: lines.length, leading, size0, asc };
    return l._s;
  }
  // レイヤーの置き方。align：左右、valign：上下。枠つきの文字は枠の中で揃える
  function layerOrigin(l, s) {
    const st = l.style;
    let ax, ay;  // キャンバス上の、Premiere の「位置」に当たる点
    const box = st.box && st.box[0] != null;
    if (box) {
      // 枠の左上が「位置」
      ax = s.pad - (st.halign === 2 ? (st.box[0] - s.tw) / 2 : 0);
      const lastBase = s.pad + s.asc + s.leading * (s.lines - 1);
      ay = lastBase - st.box[1] + (TelopView.BOX_BOT);
    } else {
      ax = st.halign === 2 ? s.pad + s.tw / 2 : (st.halign === 1 ? s.pad + s.tw : s.pad);
      const lineN = st.valign === 2 ? s.lines - 1 : 0;
      ay = s.pad + s.asc + s.leading * lineN;
    }
    return [ax, ay];
  }
  function drawItem(c, it, t) {
    const lt = t - it.start;
    let alpha = 1;
    const W = 1920, H = 1080;
    // 上の段から書いてあるので、下の層（後ろ）から描く
    for (let li = it.layers.length - 1; li >= 0; li--) {
      const l = it.layers[li];
      // 章の札：青い札の裏の文字は Premiere でも見えない
      if (!l.shape && li > 0 && it.layers.some((x) => x.shape)) continue;
      const s = l.shape ? null : sprite(l);
      if (!l.shape && !s) continue;
      c.save();
      // 外側から順に掛ける：モーション → 効果（後ろから）→ グループ → 文字の層
      const apply = (x, isGeo) => {
        if (!x) return;
        const pos = lerp(x.pos, lt, [0.5, 0.5]), an = lerp(x.anchor, lt, [0.5, 0.5]), sc = lerp(x.scale, lt, [100])[0] / 100;
        const rot = lerp(x.rot, lt, [0])[0];
        c.translate(pos[0] * W, pos[1] * H); if (rot) c.rotate(rot * Math.PI / 180); c.scale(sc, sc); c.translate(-an[0] * W, -an[1] * H);
        if (x.opacity) alpha *= lerp(x.opacity, lt, [100])[0] / 100;
      };
      alpha = 1;
      for (const [a, b, kind] of it.fades || []) if (t >= a && t <= b) alpha *= kind === "in" ? (t - a) / (b - a) : 1 - (t - a) / (b - a);
      apply(it.motion);
      for (let i = it.effects.length - 1; i >= 0; i--) apply(it.effects[i], true);
      apply(it.group);
      const lx = l.x, pos = lerp(lx.pos, lt, [0.5, 0.5]), sc = lerp(lx.scale, lt, [100])[0] / 100;
      if (lx.opacity) alpha *= lerp(lx.opacity, lt, [100])[0] / 100;
      c.translate(pos[0] * W, pos[1] * H); c.scale(sc, sc);
      c.globalAlpha = Math.max(0, Math.min(1, alpha));
      if (l.shape) {
        const an = lerp(lx.anchor, lt, [0, 0]), b = l.shape.bbox;
        // 章の札の図形。色は図形の値（無ければ決め打ち）。小さい札は一番上の1枚だけ見える（下の灰色の札は Premiere の画像でも見えない）
        const col = l.shape.fill ? `rgb(${l.shape.fill.join(",")})` : "rgb(255,255,255)";
        c.fillStyle = (b[2] - b[0]) < 500 ? (li === 1 ? col : "rgba(0,0,0,0)") : col;
        c.fillRect(b[0] - an[0] * W, b[1] - an[1] * H, b[2] - b[0], b[3] - b[1]);
      } else {
        const [ax, ay] = layerOrigin(l, s);
        c.drawImage(s.cv, -ax, -ay);
      }
      c.restore();
    }
  }
  function drawOne(c, it, t) { drawItem(c, it, t); }
  function draw(c, items, t, over) {
    if (over && over.some(([a, b]) => t >= a && t < b)) return;
    for (const it of items) if (t >= it.start && t < it.end) drawItem(c, it, t);
  }
  return { draw, drawOne, LEAD: 1.2, BG_TOP: 0.88, BG_BOT: 0.24, SHADOW_K: 1.0, SHADOW_A: 1.0, BOX_BOT: 0 };
})();
