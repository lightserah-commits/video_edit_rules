// ---------- この動画（環境設定）で足した図形 ----------
function hexRgb(h) { h = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.substr(i, 2), 16)); }
function mixColor(a, b, p) { const x = hexRgb(a), y = hexRgb(b); return `rgb(${x.map((v, i) => Math.round(lerp(v, y[i], clamp(p)))).join(",")})`; }
function outAlpha(e, t, d = 0.12) { return t > e.t1 ? 1 - clamp((t - e.t1) / d) : 1; }
DRAW.tools = (g, e, t) => {   // 流行りの道具のカード（Orca・Obsidian）→ 赤い×
  const out = outAlpha(e, t); if (out <= 0) return;
  e.items.forEach((it, i) => {
    if (t < it.t) return;
    const p = (t - it.t) / 0.18, s = lerp(0.3, 1, eBack(p, 1.8)), a = clamp(p * 3);
    let dx = 0, dy = 0;
    const xa = e.xAt != null && t >= e.xAt;
    if (xa) { const k = clamp(1 - (t - e.xAt) / 0.3), fr = Math.floor(t * FPS * 2); dx = (rnd(fr * 1.3 + i * 7) - 0.5) * 40 * k; dy = (rnd(fr * 2.1 + i * 3) - 0.5) * 26 * k; }
    g.save(); g.globalAlpha = a * out;
    g.translate(it.x + it.w / 2 + dx, it.y + it.h / 2 + dy); g.rotate((it.rot || 0) * Math.PI / 180); g.scale(s, s); g.translate(-it.w / 2, -it.h / 2);
    g.shadowColor = "rgba(0,0,0,.55)"; g.shadowBlur = 34; g.shadowOffsetY = 14;
    const gr = g.createLinearGradient(0, 0, it.w, it.h); gr.addColorStop(0, it.c1); gr.addColorStop(1, it.c2);
    rr(g, 0, 0, it.w, it.h, 30); g.fillStyle = gr; g.fill(); g.shadowColor = "transparent";
    g.lineWidth = 4; g.strokeStyle = "rgba(255,255,255,.55)"; g.stroke();
    g.textAlign = "center"; g.textBaseline = "middle";
    g.font = `800 ${it.fs || 100}px 'Avenir Next Condensed'`; g.fillStyle = "#fff"; g.fillText(it.name, it.w / 2, it.h * 0.43);
    if (it.sub) { g.font = `800 ${it.sfs || 40}px 'Hiragino Sans'`; g.fillStyle = "rgba(255,255,255,.88)"; g.fillText(it.sub, it.w / 2, it.h * 0.78); }
    if (xa) {
      const q = clamp((t - e.xAt) / 0.15);
      g.fillStyle = `rgba(15,15,20,${0.5 * q})`; rr(g, 0, 0, it.w, it.h, 30); g.fill();
      const d1 = clamp((t - e.xAt - i * 0.05) / 0.09), d2 = clamp((t - e.xAt - i * 0.05 - 0.07) / 0.09), m = 34;
      g.strokeStyle = "#FF2D46"; g.lineWidth = 30; g.lineCap = "round"; g.shadowColor = "rgba(0,0,0,.6)"; g.shadowBlur = 16;
      if (d1 > 0) { g.beginPath(); g.moveTo(m, m); g.lineTo(lerp(m, it.w - m, eOut(d1)), lerp(m, it.h - m, eOut(d1))); g.stroke(); }
      if (d2 > 0) { g.beginPath(); g.moveTo(it.w - m, m); g.lineTo(lerp(it.w - m, m, eOut(d2)), lerp(m, it.h - m, eOut(d2))); g.stroke(); }
    }
    g.restore();
  });
};
DRAW.memo = (g, e, t) => {   // 付せんのメモ → 腐っていく（色が濁る・しみ・垂れる・しおれる）
  const out = outAlpha(e, t); if (out <= 0) return;
  const p = (t - e.t0) / 0.2, s = lerp(0.5, 1, eBack(p, 1.6)), a = clamp(p * 3);
  const r = e.rotAt != null ? clamp((t - e.rotAt) / (e.rotD || 1.2)) : 0, dr = eOut(r);
  g.save(); g.globalAlpha = a * out;
  g.translate(e.x + e.w / 2, e.y + e.h / 2); g.rotate(((e.rot || 0) + dr * 5) * Math.PI / 180); g.scale(s, s * (1 - 0.05 * dr)); g.translate(-e.w / 2, -e.h / 2);
  g.shadowColor = "rgba(0,0,0,.55)"; g.shadowBlur = 34; g.shadowOffsetY = 16;
  g.fillStyle = mixColor("#FFE55C", "#7a7436", dr); g.fillRect(0, 0, e.w, e.h); g.shadowColor = "transparent";
  // 折り目の影
  const fg = g.createLinearGradient(0, 0, 0, e.h); fg.addColorStop(0, "rgba(0,0,0,0.0)"); fg.addColorStop(1, `rgba(0,0,0,${0.12 + 0.2 * dr})`); g.fillStyle = fg; g.fillRect(0, 0, e.w, e.h);
  g.save(); g.translate(e.w / 2, 0); g.rotate(-0.05); g.fillStyle = "rgba(255,255,255,.6)"; g.fillRect(-80, -20, 160, 40); g.restore();
  // 罫線
  g.fillStyle = `rgba(0,0,0,${0.10 + 0.05 * dr})`; for (let k = 0; k < 3; k++) g.fillRect(48, e.h * 0.70 + k * 46, e.w - 96, 5);
  // 文字（手書き風ではなく太字）
  g.font = `800 ${e.size}px 'Hiragino Sans'`; g.textBaseline = "middle"; g.textAlign = "left";
  const chars = [...e.text]; const ws = chars.map((c) => g.measureText(c).width); const tw = ws.reduce((x, y) => x + y, 0);
  let x = (e.w - tw) / 2;
  chars.forEach((ch, i) => { const ct = e.ct ? e.ct[i] : e.t0; if (t >= ct) { const q = clamp((t - ct) / 0.08); g.save(); g.globalAlpha = a * out * q; g.fillStyle = mixColor("#1b1b1b", "#2d2610", dr); g.translate(x + ws[i] / 2, e.h * 0.40); g.scale(lerp(1.6, 1, eOut(q)), lerp(1.6, 1, eOut(q))); g.fillText(ch, -ws[i] / 2, 0); g.restore(); } x += ws[i]; });
  // しみ・カビ
  if (r > 0) {
    for (let k = 0; k < 18; k++) {
      const rs = clamp(r * 1.7 - rnd(k * 3.1) * 0.7); if (rs <= 0) continue;
      g.fillStyle = k % 3 ? `rgba(70,58,22,${0.55 * rs})` : `rgba(96,120,40,${0.6 * rs})`;
      const sx = rnd(k * 7.3) * e.w, sy = rnd(k * 5.1) * e.h, sr = (12 + rnd(k * 2.7) * 46) * rs;
      g.beginPath(); g.arc(sx, sy, sr, 0, Math.PI * 2); g.fill();
    }
    // 下へ垂れる
    for (let k = 0; k < 6; k++) {
      const rs = clamp(r * 1.4 - rnd(k * 9.7) * 0.5); if (rs <= 0) continue;
      const dx = 50 + rnd(k * 4.4) * (e.w - 100), len = rs * (60 + rnd(k * 1.9) * 140), wd = 14 + rnd(k * 6.6) * 14;
      g.fillStyle = "rgba(92,84,34,0.95)";
      g.beginPath(); g.moveTo(dx - wd / 2, e.h - 2); g.lineTo(dx - wd / 2, e.h + len); g.arc(dx, e.h + len, wd / 2, Math.PI, 0, true); g.lineTo(dx + wd / 2, e.h - 2); g.closePath(); g.fill();
    }
  }
  g.restore();
};
DRAW.gauge = (g, e, t) => {   // ゲージ（AIのスキル）。drainAt で from → to に減る
  const out = outAlpha(e, t); if (out <= 0) return;
  const p = eOut5((t - e.t0) / 0.18);
  const dv = e.drainAt != null ? eIO(clamp((t - e.drainAt) / (e.drainD || 0.35))) : 0;
  const v = lerp(e.from, e.to, dv);
  g.save(); g.globalAlpha = out * clamp((t - e.t0) / 0.08);
  g.translate(e.x, e.y); g.scale(lerp(0.6, 1, p), 1);
  glass(g, 0, 0, e.w, e.h + 92, 20, "rgba(255,255,255,.4)");
  g.font = "800 46px 'Hiragino Sans'"; g.fillStyle = "#fff"; g.textBaseline = "middle"; g.textAlign = "left"; g.fillText(e.label, 30, 46);
  const low = v < 0.2, blink = low && Math.floor((t - e.drainAt) * 8) % 2 === 0;
  g.font = "800 60px 'Avenir Next Condensed'"; g.textAlign = "right"; g.fillStyle = low ? "#FF2D46" : "#7CF7C1";
  g.fillText(`${Math.round(v * 100)}%`, e.w - 30, 48);
  g.fillStyle = "rgba(255,255,255,.14)"; rr(g, 30, 80, e.w - 60, e.h - 10, 10); g.fill();
  g.fillStyle = low ? (blink ? "#FF2D46" : "#b3172a") : "#19D38A"; rr(g, 30, 80, Math.max(12, (e.w - 60) * v), e.h - 10, 10); g.fill();
  for (let k = 1; k < 10; k++) { g.fillStyle = "rgba(0,0,0,.35)"; g.fillRect(30 + (e.w - 60) * k / 10 - 2, 80, 4, e.h - 10); }
  g.restore();
};
DRAW.layers = (g, e, t) => {   // 環境の層（下から積み上がる板）
  const out = outAlpha(e, t); if (out <= 0) return;
  e.items.forEach((it, i) => {
    if (t < it.t) return;
    const p = (t - it.t) / 0.16, dy = -300 * (1 - eOut5(p)), a = clamp(p * 3);
    const y = e.y + i * (e.bh + e.gap);
    g.save(); g.globalAlpha = a * out; g.translate(0, dy);
    const sk = 26;   // 斜めの上面
    g.fillStyle = mixColor(it.color, "#ffffff", 0.35);
    g.beginPath(); g.moveTo(e.x + sk, y - 16); g.lineTo(e.x + e.w + sk, y - 16); g.lineTo(e.x + e.w, y); g.lineTo(e.x, y); g.closePath(); g.fill();
    g.shadowColor = "rgba(0,0,0,.5)"; g.shadowBlur = 18; g.shadowOffsetY = 8;
    const gr = g.createLinearGradient(e.x, 0, e.x + e.w, 0); gr.addColorStop(0, it.color); gr.addColorStop(1, mixColor(it.color, "#000000", 0.35));
    g.fillStyle = gr; g.fillRect(e.x, y, e.w, e.bh); g.shadowColor = "transparent";
    g.fillStyle = mixColor(it.color, "#000000", 0.5); g.beginPath(); g.moveTo(e.x + e.w, y); g.lineTo(e.x + e.w + sk, y - 16); g.lineTo(e.x + e.w + sk, y + e.bh - 16); g.lineTo(e.x + e.w, y + e.bh); g.closePath(); g.fill();
    g.font = `800 ${e.fs || 40}px 'Hiragino Sans'`; g.fillStyle = "#fff"; g.textBaseline = "middle"; g.textAlign = "left";
    g.fillText(it.label, e.x + 28, y + e.bh / 2 + 2);
    g.font = "800 30px 'Avenir Next Condensed'"; g.textAlign = "right"; g.fillStyle = "rgba(255,255,255,.7)"; g.fillText(`LAYER ${String(i + 1).padStart(2, "0")}`, e.x + e.w - 24, y + e.bh / 2 + 2);
    g.restore();
  });
};
DRAW.pill = (g, e, t) => {   // 状態の札（▶ AIが再始動）
  const out = outAlpha(e, t); if (out <= 0) return;
  const p = (t - e.t0) / 0.18, s = lerp(0.4, 1, eBack(p, 2)), a = clamp(p * 3);
  g.save(); g.globalAlpha = a * out; g.font = `800 ${e.size}px 'Hiragino Sans'`;
  const tw = g.measureText(e.text).width, w = tw + e.size * 2.2, h = e.size * 1.7;
  g.translate(e.x + w / 2, e.y); g.scale(s, s);
  g.shadowColor = e.glow || "rgba(25,211,138,.8)"; g.shadowBlur = 30;
  rr(g, -w / 2, -h / 2, w, h, h / 2); g.fillStyle = e.color || "#14b877"; g.fill(); g.shadowColor = "transparent";
  // 回る印
  const ang = (t - e.t0) * 9; g.strokeStyle = "#fff"; g.lineWidth = e.size * 0.16; g.lineCap = "round";
  g.beginPath(); g.arc(-w / 2 + h / 2 + 4, 0, e.size * 0.36, ang, ang + 4.3); g.stroke();
  g.fillStyle = "#fff"; g.textBaseline = "middle"; g.textAlign = "left"; g.fillText(e.text, -w / 2 + h * 0.95, 2);
  g.restore();
};
DRAW.tapbtn = (g, e, t) => {   // ワンタップのボタン（指が来て押す → 波紋 → 完了）
  const out = outAlpha(e, t); if (out <= 0) return;
  const p = (t - e.t0) / 0.2, a = clamp(p * 3);
  const pressed = t >= e.tapAt, q = pressed ? (t - e.tapAt) : 0;
  let s = lerp(0.5, 1, eBack(p, 1.8)); if (pressed) s *= q < 0.06 ? lerp(1, 0.9, q / 0.06) : lerp(0.9, 1.04, eBack(clamp((q - 0.06) / 0.2), 2.5));
  const cx = e.x + e.w / 2, cy = e.y + e.h / 2;
  g.save(); g.globalAlpha = a * out;
  // 波紋
  if (pressed) for (let k = 0; k < 3; k++) { const rp = clamp((q - k * 0.1) / 0.5); if (rp <= 0 || rp >= 1) continue; g.strokeStyle = `rgba(255,210,63,${1 - rp})`; g.lineWidth = 14 * (1 - rp) + 2; g.beginPath(); g.ellipse(cx, cy, e.w / 2 + 220 * eOut(rp), e.h / 2 + 160 * eOut(rp), 0, 0, Math.PI * 2); g.stroke(); }
  g.translate(cx, cy); g.scale(s, s);
  g.shadowColor = pressed ? "rgba(255,210,63,.9)" : "rgba(0,0,0,.5)"; g.shadowBlur = pressed ? 50 : 30; g.shadowOffsetY = pressed ? 0 : 12;
  rr(g, -e.w / 2, -e.h / 2, e.w, e.h, e.h / 2); g.fillStyle = pressed ? "#FFD23F" : "#ffffff"; g.fill(); g.shadowColor = "transparent";
  g.font = `800 ${e.size}px 'Hiragino Sans'`; g.fillStyle = "#111"; g.textAlign = "center"; g.textBaseline = "middle";
  g.fillText(pressed ? (e.label2 || e.label) : e.label, 0, 3);
  g.restore();
  // 指（丸いカーソル）
  if (t >= e.handAt) {
    const hp = eOut5(clamp((t - e.handAt) / Math.max(0.05, e.tapAt - e.handAt)));
    const hx = lerp(cx + 420, cx + e.w * 0.18, hp), hy = lerp(cy + 300, cy + 18, hp);
    const hs = pressed ? (q < 0.08 ? 0.8 : lerp(0.8, 1, clamp((q - 0.08) / 0.15))) : 1;
    g.save(); g.globalAlpha = out * clamp((t - e.handAt) / 0.08);
    g.translate(hx, hy); g.scale(hs, hs);
    g.fillStyle = "rgba(255,255,255,.9)"; g.strokeStyle = "rgba(0,0,0,.45)"; g.lineWidth = 6;
    g.beginPath(); g.arc(0, 0, 46, 0, Math.PI * 2); g.fill(); g.stroke();
    g.fillStyle = "rgba(61,139,255,.9)"; g.beginPath(); g.arc(0, 0, 20, 0, Math.PI * 2); g.fill();
    g.restore();
  }
};
