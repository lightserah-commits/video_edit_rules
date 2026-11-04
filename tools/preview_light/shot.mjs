// node shot.mjs <page.html> <出力フォルダ> <秒,秒,...> [js式] : 指定の時刻のテロップを透明の PNG に描く
import { spawn } from "node:child_process"; import { mkdtempSync, writeFileSync, mkdirSync } from "node:fs"; import { tmpdir } from "node:os"; import { join, resolve } from "node:path"; import { pathToFileURL } from "node:url";
const [page,outDir,times,pre]=process.argv.slice(2); mkdirSync(outDir,{recursive:true});
const PORT=9300+Math.floor(Math.random()*500);const prof=mkdtempSync(join(tmpdir(),"pv-"));
const chrome=spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",["--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1","--allow-file-access-from-files",`--remote-debugging-port=${PORT}`,`--user-data-dir=${prof}`,"--window-size=1920,1080","about:blank"],{stdio:"ignore"});
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));let wsu;for(let i=0;i<100;i++){try{const l=await(await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();const p=l.find(t=>t.type==="page");if(p){wsu=p.webSocketDebuggerUrl;break}}catch{}await sleep(100)}
const ws=new WebSocket(wsu);await new Promise(r=>ws.addEventListener("open",r,{once:true}));let id=0;const w=new Map();ws.addEventListener("message",e=>{const m=JSON.parse(e.data);if(m.id&&w.has(m.id)){const x=w.get(m.id);w.delete(m.id);m.error?x.n(new Error(JSON.stringify(m.error))):x.o(m.result)}});
const cdp=(me,pa={})=>new Promise((o,n)=>{const i=++id;w.set(i,{o,n});ws.send(JSON.stringify({id:i,method:me,params:pa}))});
const ev=async(x)=>{const r=await cdp("Runtime.evaluate",{expression:x,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value};
try{await cdp("Page.enable");await cdp("Page.navigate",{url:pathToFileURL(resolve(page)).href});for(let i=0;i<100&&!(await ev("window.__ready===true"));i++)await sleep(100);
await cdp("Emulation.setDefaultBackgroundColorOverride",{color:{r:0,g:0,b:0,a:0}});await cdp("Emulation.setDeviceMetricsOverride",{width:1920,height:1080,deviceScaleFactor:1,mobile:false});if(pre)await ev(pre);
for(const t of times.split(",")){const need=await ev(`renderAt(${t})`);const s=await cdp("Page.captureScreenshot",{format:"png",clip:{x:0,y:0,width:1920,height:1080,scale:1}});writeFileSync(join(outDir,`t_${(+t).toFixed(2)}.png`),Buffer.from(s.data,"base64"));console.log(t,need.join(","))}
}finally{chrome.kill();ws.close()}
