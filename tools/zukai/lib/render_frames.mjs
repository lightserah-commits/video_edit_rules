// HTML の図解を 1 フレームずつ透明背景の PNG に描く（Chrome ヘッドレス＋DevTools Protocol。追加の道具なし）
// 使い方: node render_frames.mjs <page.html> <出力フォルダ> <フレーム数> [<から> <まで>]（範囲を分けて何本も同時に走らせられる）
//   ページには window.__ZUKAI_ENV = {root, illust}（ルールと道具の場所・素材のイラストの場所。ユーザー名を書かない）を先に入れる。
//   root は環境変数 ZUKAI_ROOT か ~/Desktop/video_edit_rules。Chrome は ZUKAI_CHROME で替えられる
//   から＝0 の時は、準備ができた所で window.__measure() の結果を <出力フォルダ>/../measure.json に書く
// ページ側の約束: window.__ready が true になったら描ける。window.render(f) は f フレーム目の見た目にして、
//                 前のフレームと見た目が同じなら false を返す（その時は前の PNG を使い回す）
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync, copyFileSync, mkdtempSync } from "node:fs";
import { tmpdir, homedir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const CHROME = process.env.ZUKAI_CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const ROOT = process.env.ZUKAI_ROOT || join(homedir(), "Desktop", "video_edit_rules");
const ENV = { root: pathToFileURL(ROOT).href + "/", illust: pathToFileURL(join(ROOT, "素材", "イラスト")).href + "/" };
const [page, outDir, nStr, aStr, bStr] = process.argv.slice(2);
const N = parseInt(nStr, 10);
const FA = aStr ? parseInt(aStr, 10) : 0, FB = bStr ? parseInt(bStr, 10) : N;
mkdirSync(outDir, { recursive: true });
const PORT = 9300 + Math.floor(Math.random() * 500);
const prof = mkdtempSync(join(tmpdir(), "zukai-chrome-"));
const chrome = spawn(CHROME, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
  "--allow-file-access-from-files", `--remote-debugging-port=${PORT}`, `--user-data-dir=${prof}`, "about:blank"],
  { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function target() {
  for (let i = 0; i < 100; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = list.find((t) => t.type === "page");
      if (p) return p.webSocketDebuggerUrl;
    } catch {}
    await sleep(100);
  }
  throw new Error("Chrome が起動しない");
}

const ws = new WebSocket(await target());
await new Promise((r) => ws.addEventListener("open", r, { once: true }));
let id = 0;
const waiting = new Map();
ws.addEventListener("message", (e) => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) {
    const { ok, ng } = waiting.get(m.id);
    waiting.delete(m.id);
    m.error ? ng(new Error(JSON.stringify(m.error))) : ok(m.result);
  }
});
const cdp = (method, params = {}) => new Promise((ok, ng) => {
  const i = ++id;
  waiting.set(i, { ok, ng });
  ws.send(JSON.stringify({ id: i, method, params }));
});
const evaluate = async (expr) => (await cdp("Runtime.evaluate", { expression: expr, returnByValue: true, awaitPromise: true })).result.value;

try {
  await cdp("Page.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1920, height: 1080, deviceScaleFactor: 1, mobile: false });
  await cdp("Emulation.setDefaultBackgroundColorOverride", { color: { r: 0, g: 0, b: 0, a: 0 } });
  await cdp("Page.addScriptToEvaluateOnNewDocument", { source: `window.__ZUKAI_ENV = ${JSON.stringify(ENV)};` });
  await cdp("Page.navigate", { url: pathToFileURL(resolve(page)).href });
  for (let i = 0; i < 300 && !(await evaluate("window.__ready === true")); i++) await sleep(100);
  if (!(await evaluate("window.__ready === true"))) {
    const why = await evaluate("JSON.stringify({rs: document.readyState, err: window.__err || null, fonts: document.fonts.status, imgs: [...document.images].map(i => [decodeURI(i.src).slice(-24), i.complete, i.naturalWidth])})");
    throw new Error("ページの準備ができない " + why);
  }
  if (FA === 0) {
    const ms = await evaluate("window.__measure ? JSON.stringify(window.__measure()) : null");
    if (ms) writeFileSync(join(outDir, "..", "measure.json"), ms);
  }
  let prev = null, shots = 0;
  if (FA > 0) await evaluate(`window.render(${FA - 1})`);
  for (let f = FA; f < FB; f++) {
    const changed = await evaluate(`window.render(${f})`);
    const png = join(outDir, `${String(f).padStart(5, "0")}.png`);
    if (changed || prev === null) {
      await evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))");
      const { data } = await cdp("Page.captureScreenshot", { format: "png", fromSurface: true });
      writeFileSync(png, Buffer.from(data, "base64"));
      shots++;
    } else {
      copyFileSync(prev, png);
    }
    prev = png;
  }
  console.log(JSON.stringify({ frames: FB - FA, from: FA, shots }));
} finally {
  ws.close();
  chrome.kill();
}
