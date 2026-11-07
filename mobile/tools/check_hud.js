#!/usr/bin/env node
// check_hud.js — 顶栏品牌区与右侧操作区的像素间距检查（320/360/390/412）
// 新规范（v006）：无版本号胶囊、无 ☰ 按钮；.brand 右缘与 .hdr-actions 左缘 gap ≥ 8px；
// ExDark 花体字零裁切；右侧仅 3 个 .ico-btn 且间距均匀。
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const tmpclean = require('./tmpclean');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(__dirname, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9900 + Math.floor(Math.random() * 50);

function send(ws, id, method, params) {
  return new Promise((res, rej) => {
    const mid = ++id;
    const cb = (ev) => { const m = JSON.parse(ev.data); if (m.id === mid) { ws.removeEventListener('message', cb); m.error ? rej(m.error) : res(m.result); } };
    ws.addEventListener('message', cb);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
}

/* Chrome 的一次性 profile 必须回收：见 tmpclean.js。hoist 出来让每条退出路径都能清。 */
let chrome = null, profDir = null;
async function main() {
  profDir = path.join(os.tmpdir(), 'hudchk-' + Date.now());
  chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profDir}`,
    '--window-size=412,892', '--force-device-scale-factor=1', '--hide-scrollbars',
    '--no-first-run', '--allow-file-access-from-files', 'about:blank'
  ], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  let wsUrl = null;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json`).then(r => r.json());
      wsUrl = r.find(x => x.type === 'page').webSocketDebuggerUrl;
    } catch (e) { await new Promise(r => setTimeout(r, 200)); }
  }
  if (!wsUrl) { console.error('no ws'); await tmpclean.close(chrome, profDir); process.exit(2); }
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  let id = 0;
  await send(ws, id, 'Page.navigate', { url: FILE });
  /* 等真实就绪而不是固定睡 1800ms：慢机上 1800ms 可能还没 renderAll，快机上白等。 */
  let ready = false;
  for (let i = 0; i < 30 && !ready; i++) {
    ready = await send(ws, id, 'Runtime.evaluate',
      { expression: '!!(state&&state.lib)', returnByValue: true })
      .then(r => r.result && r.result.value).catch(() => false);
    if (!ready) await new Promise(r => setTimeout(r, 300));
  }
  if (!ready) { console.error('页面 9s 内未就绪'); await tmpclean.close(chrome, profDir); process.exit(2); }

  const evalJs = async (expr) => {
    const r = await send(ws, id, 'Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    return r.result && r.result.value;
  };

  let bad = 0;
  for (const w of [320, 360, 390, 412]) {
    await send(ws, id, 'Emulation.setDeviceMetricsOverride', { width: w, height: 892, deviceScaleFactor: 1, mobile: true });
    const r = await evalJs(`(function(){
      var h=document.getElementById('hdrTotal'); if(h) h.textContent='1025.5';
      var brand=document.querySelector('.brand');
      var acts=document.querySelector('.hdr-actions');
      if(!brand||!acts) return {err:'missing'};
      var b=brand.getBoundingClientRect(), a=acts.getBoundingClientRect();
      var gap=a.left-b.right;
      var h1=document.querySelector('.brand-line h1');
      var script=document.querySelector('.ex-script');
      var clip=h1?(h1.scrollWidth>h1.clientWidth):false;
      var inH1=true;
      if(h1&&script){
        var sr=script.getBoundingClientRect(), hr=h1.getBoundingClientRect();
        inH1=(sr.left>=hr.left-0.5 && sr.right<=hr.right+0.5);
      }
      var btns=acts.querySelectorAll('.ico-btn');
      var gaps=[];
      for(var i=1;i<btns.length;i++){
        gaps.push(+(btns[i].getBoundingClientRect().left-btns[i-1].getBoundingClientRect().right).toFixed(1));
      }
      var even=gaps.length?gaps.every(function(g){return g>=2; }):false;
      var rl=document.querySelector('#exList .rbox label');
      var rlOver=rl?(rl.scrollWidth>rl.clientWidth+1):false;
      return {brandRight:+b.right.toFixed(1), actsLeft:+a.left.toFixed(1), gap:+gap.toFixed(1),
              buttons:btns.length, clip:clip, inH1:inH1, btnGaps:gaps.join(','), rlOver:rlOver,
              ok:gap>=8 && !clip && inH1 && btns.length===3 && even && !rlOver};
    })()`);
    /* 原先 r 为空也照样 r.brandRight 取值，直接 TypeError 把整轮压测打死。 */
    if (!r || r.err) {
      bad++;
      console.log(`width=${w}px FAIL 取不到测量值：` + (r && r.err ? r.err : 'evaluate 无结果'));
      continue;
    }
    if (!r.ok) bad++;
    console.log(`width=${w}px brandRight=${r.brandRight} actsLeft=${r.actsLeft} gap=${r.gap} buttons=${r.buttons} clip=${r.clip} inH1=${r.inH1} btnGaps=${r.btnGaps} rboxOverflow=${r.rlOver} ${r.ok ? 'OK' : 'FAIL'}`);
  }
  await tmpclean.close(chrome, profDir);
  process.exit(bad ? 1 : 0);
}
main().catch(async e => {
  console.error(e);
  await tmpclean.close(chrome, profDir);
  process.exit(1);
});
