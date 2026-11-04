// node shot_items.mjs <page.html> <秒の一覧.json> <出力.jsonl> : 各時刻のテロップを1つずつ切り抜いて JSON 行で書く
import { spawn } from "node:child_process"; import { mkdtempSync, appendFileSync, writeFileSync, readFileSync } from "node:fs"; import { tmpdir } from "node:os"; import { join, resolve } from "node:path"; import { pathToFileURL } from "node:url";
const [page,list,out]=process.argv.slice(2);const times=JSON.parse(readFileSync(list,'utf8'));writeFileSync(out,'');
const PORT=9300+Math.floor(Math.random()*500);const prof=mkdtempSync(join(tmpdir(),"pv-"));
const chrome=spawn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",["--headless=new","--disable-gpu","--hide-scrollbars","--force-device-scale-factor=1","--allow-file-access-from-files",`--remote-debugging-port=${PORT}`,`--user-data-dir=${prof}`,"about:blank"],{stdio:"ignore"});
const sleep=(ms)=>new Promise(r=>setTimeout(r,ms));let wsu;for(let i=0;i<100;i++){try{const l=await(await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();const p=l.find(t=>t.type==="page");if(p){wsu=p.webSocketDebuggerUrl;break}}catch{}await sleep(100)}
const ws=new WebSocket(wsu);await new Promise(r=>ws.addEventListener("open",r,{once:true}));let id=0;const w=new Map();ws.addEventListener("message",e=>{const m=JSON.parse(e.data);if(m.id&&w.has(m.id)){const x=w.get(m.id);w.delete(m.id);m.error?x.n(new Error(JSON.stringify(m.error))):x.o(m.result)}});
const cdp=(me,pa={})=>new Promise((o,n)=>{const i=++id;w.set(i,{o,n});ws.send(JSON.stringify({id:i,method:me,params:pa}))});
const ev=async(x)=>{const r=await cdp("Runtime.evaluate",{expression:x,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails).slice(0,600));return r.result.value};
try{await cdp("Page.enable");await cdp("Page.navigate",{url:pathToFileURL(resolve(page)).href});for(let i=0;i<100&&!(await ev("window.__ready===true"));i++)await sleep(100);
let n=0;for(const t of times){const items=await ev(`itemsAt(${t})`);appendFileSync(out,JSON.stringify({t,items})+"\n");n+=items.length;if(((times.indexOf(t)+1)%100)==0)console.log(times.indexOf(t)+1,n)}console.log('done',n)
}finally{chrome.kill();ws.close()}
