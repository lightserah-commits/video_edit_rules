// page.html を Chrome（ヘッドレス）で1コマずつ描いて JPEG にする。何本かの Chrome で区間を分けて並行に描く。
// 使い方: node render.mjs <page.html> <出力フォルダ> <フレーム数> [並行数=4] [--only 10,20,30]
// ページ側の約束: window.__ready が true になったら描ける。await window.render(f) で f コマ目の絵になる。
// zukai_anime の tools/render_frames.mjs（透明 PNG）を元に、背景つきの JPEG・並行・非同期の render に変えた。
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const args = process.argv.slice(2);
const onlyIdx = args.indexOf("--only");
const only = onlyIdx >= 0 ? args[onlyIdx + 1].split(",").map((x) => parseInt(x, 10)) : null;
const [page, outDir, nStr, jStr] = args.filter((a, i) => !(onlyIdx >= 0 && (i === onlyIdx || i === onlyIdx + 1)));
const N = parseInt(nStr, 10), J = parseInt(jStr || "4", 10);
mkdirSync(outDir, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function worker(frames, wi) {
  const PORT = 9400 + wi * 7 + Math.floor(Math.random() * 300);
  const prof = mkdtempSync(join(tmpdir(), "hl-chrome-"));
  const chrome = spawn(CHROME, ["--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
    "--allow-file-access-from-files", "--disable-web-security", `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`, "about:blank"],
    { stdio: "ignore" });
  let wsUrl = null;
  for (let i = 0; i < 150 && !wsUrl; i++) {
    try { const l = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json(); const p = l.find((t) => t.type === "page"); if (p) wsUrl = p.webSocketDebuggerUrl; } catch {}
    if (!wsUrl) await sleep(100);
  }
  if (!wsUrl) throw new Error("Chrome が起動しない");
  const ws = new WebSocket(wsUrl);
  await new Promise((r) => ws.addEventListener("open", r, { once: true }));
  let id = 0; const waiting = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && waiting.has(m.id)) { const { ok, ng } = waiting.get(m.id); waiting.delete(m.id); m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result); } });
  const cdp = (method, params = {}) => new Promise((ok, ng) => { const i = ++id; waiting.set(i, { ok, ng }); ws.send(JSON.stringify({ id: i, method, params })); });
  const evaluate = async (expr) => { const r = await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 800)); return r.result.value; };
  try {
    await cdp("Page.enable");
    await cdp("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
    await cdp("Page.navigate", { url: pathToFileURL(resolve(page)).href });
    for (let i = 0; i < 300 && !(await evaluate("window.__ready === true").catch(() => false)); i++) await sleep(100);
    if (!(await evaluate("window.__ready === true"))) throw new Error("ページの準備ができない");
    let subs = 0;
    for (const f of frames) {
      subs += await evaluate(`window.render(${f})`);
      const { data } = await cdp("Page.captureScreenshot", { format: "jpeg", quality: 94, fromSurface: true });
      writeFileSync(join(outDir, `${String(f).padStart(5, "0")}.jpg`), Buffer.from(data, "base64"));
    }
    return subs;
  } finally { ws.close(); chrome.kill(); }
}

const all = only || [...Array(N).keys()];
const parts = [...Array(J)].map(() => []);
all.forEach((f, i) => parts[Math.floor(i * J / all.length)].push(f));   // 続いた区間ごとに分ける（背景の読み込みが続けて当たる）
const t0 = Date.now();
const subs = await Promise.all(parts.filter((p) => p.length).map((p, i) => worker(p, i)));
console.log(JSON.stringify({ frames: all.length, sec: Math.round((Date.now() - t0) / 1000), subframes: subs.reduce((a, b) => a + b, 0) }));
