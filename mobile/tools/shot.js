#!/usr/bin/env node
/**
 * shot.js — 手机视口下的 APK HTML 真实交互截图（CDP，Node 22 内置 WebSocket）
 *   node tools/shot.js <outDir>
 *   场景清单 = 本文件 SCEN 一处，条数不写在注释里；docs/shots/ 落盘同一批名字。
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(__dirname, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const OUT = process.argv[2] || 'shots';
const W = 412, H = 892, DPR = 2;
const PORT = 9700 + Math.floor(Math.random() * 200);
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function main(){
  fs.mkdirSync(OUT, { recursive: true });
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), 'apkshot-'));
  const chrome = spawn(CHROME, [
    '--headless=new', `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
    `--window-size=${W},${H}`, `--force-device-scale-factor=${DPR}`,
    '--hide-scrollbars', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-gpu', '--mute-audio', '--allow-file-access-from-files',
    'about:blank'
  ], { stdio: 'ignore' });

  let wsUrl = null;
  for (let i = 0; i < 80 && !wsUrl; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const p = list.find(t => t.type === 'page');
      if (p) wsUrl = p.webSocketDebuggerUrl;
    } catch (e) {}
    if (!wsUrl) await sleep(250);
  }
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  let id = 0; const wait = new Map(); const events = [];
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && wait.has(m.id)) { const r = wait.get(m.id); wait.delete(m.id); r(m.result); }
    else if (m.method) events.push(m);
  });
  const send = (method, params) => new Promise(res => { const i = ++id; wait.set(i, res); ws.send(JSON.stringify({ id: i, method, params: params || {} })); });
  const evalJS = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true, userGesture: true });
    if (r.exceptionDetails) throw new Error('JS ' + (r.exceptionDetails.exception?.description || r.exceptionDetails.text));
    return r.result.value;
  };
  const shot = async (name) => {
    const r = await send('Page.captureScreenshot', { format: 'png' });
    fs.writeFileSync(path.join(OUT, name), Buffer.from(r.data, 'base64'));
    console.log('  ' + name + '  ' + Math.round(fs.statSync(path.join(OUT, name)).size / 1024) + 'KB');
  };

  try {
    await send('Page.enable'); await send('Runtime.enable'); await send('Log.enable');
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: DPR, mobile: true });
    await send('Page.navigate', { url: FILE });
    await sleep(900);
    for (let i = 0; i < 40; i++) {
      const ok = await evalJS('!!(window.state && state.lib && state.weeks)').catch(() => false);
      if (ok) break; await sleep(250);
    }
    console.log('STATE ' + await evalJS(`JSON.stringify({w:state.week,d:state.day,lang:state.lang,theme:state.theme,
      lib:libTotal(),cats:state.lib.cats.length,doms:state.lib.domains.length,acts:state.lib.cats[0].acts.length})`));

    /* 图版三张截图得有真数据：新装账号 e1RM 账本为空、一组都没勾完，
       四张图会全走空态 —— 空态本身由 v3v X16 把关，文档图要的是成图的样子。
       这里只在内存里改 state，不调 save()，装机不受影响；随机数一律不用，图可复现。 */
    const FIGS_FIX = [
      '(function(){',
      " var K=['sq','bp','dl'], L={sq:150,bp:100,dl:180}, C={sq:'S.Main',bp:'B.Main',dl:'D.Main'};",
      ' var log=[];',
      " K.forEach(function(k,ki){ for(var w=1;w<=13;w+=2){ var ld=L[k]+w*2.5;",
      "   log.push({id:'SH'+k+w,lift:k,week:w,day:'A',row:0,date:'2026-0'+(1+(w%9))+'-0'+(1+(w%9)),",
      "     mode:'T1.Mod',cat:C[k],mv:'shot '+k,load:ld,reps:5,rpe:6+(((w/2)|0)%4),e1rm:ld*(1+12/30)}); } });",
      ' state.e1rmLog=log;',
      ' Object.keys(state.weeks).forEach(function(w){ var wk=state.weeks[w];',
      "   Object.keys(wk).forEach(function(d){ var dd=wk[d]; if(!dd||!dd.exercises) return;",
      "     if(+w>14) return;",
      "     dd.exercises.forEach(function(e,i){ var a=anchorOf(e.cat);",
      '       e.done=true;',
      // 下周建议要的是「完成率」，光有 done 不够：补上真实做过的组数（与 done 隐含的同一个值，图版不受影响）
      '       e.doneSets=setsOf(e.mode);',
      "       if(!(+e.load>0)) e.load=a?(L[a]-(+w)*2):(40+i*2.5);",
      "       if(!(+e.reps>0)) e.reps=3+(i%5);",
      "       if(!(+e.rpe>0)) e.rpe=6+(i%4); }); }); });",
      ' return 1;})()'
    ].join('\n');

    /* 下周建议那三张得真有「加 / 保持 / 减」的分布：FIGS_FIX 把实 RPE 留在目标值上，
       整表全是保持，截图看不出这屏在干什么。这里按行号把 RPE 拉开——
       每七行一次超硬顶（该减）、每三行一次低于目标（该加）、其余贴目标（该保持）。 */
    const ADVICE_RPE = [
      '(function(){',
      ' Object.keys(state.weeks).forEach(function(w){ if(+w>14) return; var wk=state.weeks[w];',
      '  Object.keys(wk).forEach(function(d){ var dd=wk[d]; if(!dd||!dd.exercises) return;',
      '   dd.exercises.forEach(function(e,i){ if(!(+e.targetRpe>0)) return;',
      '     e.rpe=(i%7===0)?9.7:((i%3===0)?(+e.targetRpe-1.5):+e.targetRpe); }); }); });',
      ' return 1;})()'
    ].join('\n');

    const SCEN = [
      ['01-dark', 0],
      ['02-light', `setTheme('light')`],
      ['03-en', `setLang('en')`],
      ['04-browse', `setLang('zh');openBrowse('pick')`],
      ['05-browse2', `brGo(1,'T1.Main')`],
      ['06-browse3', `brGo(2,'T1.Main','S.Main')`],
      ['07-picked', `pickAct('S.Main','Low-bar Squat')`],
      ['08-editor', `openEditor(0)`],
      ['09-lib', `closeSheet('edSheet');openLibrary()`],
      ['10-libcat', `brGo(2,'T1.Main','S.Main')`],
      ['11-actform', `openAct('Low-bar Squat')`],
      ['12-settings', `closeAllSheets();openSettings()`],
      ['13-light-pro', `closeAllSheets();setTheme('light')`],
      ['14-light-browse', `openBrowse('pick');brGo(1,'T1.Main');brGo(2,'T1.Main','S.Main')`],
      ['15-aux', `closeSheet('brSheet');setDay('AUX')`],
      ['16-nature', `closeAllSheets();setDay('A');setTheme('nature')`],
      ['17-nature-settings', `openSettings()`],
      ['18-nature-browse', `closeAllSheets();openBrowse('pick');brGo(1,'T1.Main')`],
      ['19-back-dark', `closeAllSheets();setTheme('dark')`],
      ['20-figs-dark', `${FIGS_FIX};openFigsSheet()`],
      ['21-figs-light', `setTheme('light')`],
      ['22-figs-nature', `setTheme('nature')`],
      ['23-figs-adh', `setTheme('dark');document.querySelectorAll('#figsSheet .fig-card')[3].scrollIntoView({block:'start'})`],
      // 计划库：v0.15 的种子给每条计划补了 canon（出处路径）， chip 只显示文件名——留这张是为了「数据侧变长」时看得出来
      ['24-proglib', `closeAllSheets();openProgLibSheet()`],
      // 记录流反馈：先把当天全部撤勾，再逐组勾满 —— 最后一组落下时「本日全部完成」的 toast 与卡闪同帧
      ['25-daycomplete', `closeAllSheets();(function(){var l=(day().exercises||[]);`
        + `l.forEach(function(e){e.done=false;});renderExercises();`
        + `l.forEach(function(e,i){toggleDone(i);});})()`],
      // 下周建议（只读引擎）：三主题各一张。周对固定 W7→W8 —— 这是内置 8 周模板里「对比周」
      // 下拉的最后一对（可选源周到末周−1 为止），且 W8 是减载周，正好把拒绝标记也截进来。
      ['26-advice-dark', `closeAllSheets();setTheme('dark');${FIGS_FIX};${ADVICE_RPE};openAdviceSheet();`
        + `document.getElementById('advWeek').value='7';renderAdviceTable()`],
      ['27-advice-light', `setTheme('light')`],
      ['28-advice-nature', `setTheme('nature')`],
      // 写回四档（v0.25）：只建议那三张上面已经有了，这里补「能落笔」的样子与两个反动作。
      // 全部走真接线（setAdvTier / advApplyAll 两次点击 / advUndoLast），不直接改 state，
      // 否则截的是「我以为的界面」而不是用户点出来的界面。
      ['29-advice-confirm', `setTheme('dark');setAdvTier('confirm')`],
      ['30-advice-applied', `advApplyAll();advApplyAll()`],
      ['31-advice-undo', `setTheme('light');advUndoLast()`],
      ['32-advice-off', `setTheme('nature');setAdvTier('off')`],
      // 环境配置 hub（v0.26）：配片库存 + 按周×日的地点网格。
      // 34 故意点掉三片并填两处地名 —— 库存少一片时 edSheet 的配平条会跟着变，
      // 只截「全套空态」等于没截到这屏真正要给人看的东西。
      ['33-env-dark', `closeAllSheets();setTheme('dark');setAdvTier('suggest');openEnvSheet()`],
      ['34-env-stock-loc', `(function(){[25,20,15].forEach(function(k){togglePlateKg(k);});`
        + `var w=state.week,ds=dayIds();`
        + `ds.slice(0,2).forEach(function(d,i){setDayLoc(w,d,i?'铁馆 B 区':'铁馆 A 区');});`
        + `renderEnvSheet();})()`],
      ['35-env-light', `setTheme('light')`],
      ['36-tool-load', `closeAllSheets();setTheme('dark');openToolLoad()`],
      ['37-tool-load-loaded', `(function(){var s=document.getElementById('toolLoadType');s.value='loaded';`
        + `s.dispatchEvent(new Event('change'));})()`],
      ['38-tool-coef', `closeSheet('toolLoadSheet');openToolCoef()`],
      /* v0.27 阈值回测：出厂空账是一张空态卡，记满两周才看得到那张 11 行的表 */
      ['39-calib-empty', `closeAllSheets();openCalibSheet()`],
      ['40-calib-table', `(function(){
        var rec=function(wn){var wk=state.weeks[String(wn)];if(!wk)return;
          Object.keys(wk).forEach(function(d){((wk[d]||{}).exercises||[]).forEach(function(e,i){
            var pr=prescriptionOf(e),st=(+pr.sets||1),rp=(+pr.reps||1),tr=(+e.targetRpe||7);
            e.doneSets=(i%3===2)?Math.max(1,Math.floor(st/2)):st;e.done=e.doneSets>=st;
            e.reps=(i%3===0)?rp:Math.max(1,rp-1);e.targetRpe=tr;
            e.rpe=(i%4===0)?Math.max(1,tr-1):((i%4===1)?tr:((i%4===2)?tr+0.8:9.8));});});};
        rec(2);rec(3);renderCalib();})()`],
      ['41-calib-light', `closeSheet('calibSheet');setTheme('light');openCalibSheet()`]
    ];
    for (const [name, js] of SCEN) {
      if (js) await evalJS(js);
      await sleep(420);
      await shot(name + '.png');
    }

    /* 收口回「暗色 + 主屏」：AUDIT 量的是主屏的溢出与字号，图版面板开着量出来就不是同一件事了。
       截图已经落盘，这里不影响上面那批。 */
    await evalJS(`closeAllSheets();setTheme('dark')`).catch(() => {});
    await sleep(300);

    const errs = events.filter(e => e.method === 'Log.entryAdded' && e.params.entry.level === 'error')
      .map(e => '[err] ' + e.params.entry.text);
    const exc = events.filter(e => e.method === 'Runtime.exceptionThrown')
      .map(e => e.params.exceptionDetails.exception?.description || e.params.exceptionDetails.text);
    console.log('\nCONSOLE: ' + (errs.length ? '\n  ' + errs.join('\n  ') : 'clean'));
    if (exc.length) console.log('EXCEPTIONS:\n  ' + exc.join('\n  '));

    const audit = await evalJS(`(()=>{const o={over:[],small:[]};
      document.querySelectorAll('body *').forEach(e=>{
        if(e.scrollWidth>e.clientWidth+2 && e.clientWidth>0){
          const s=getComputedStyle(e); if(s.overflowX!=='auto'&&s.overflowX!=='scroll'&&s.textOverflow!=='ellipsis') o.over.push((e.className||e.tagName)+' '+e.scrollWidth+'>'+e.clientWidth);
        }
        const fs=parseFloat(getComputedStyle(e).fontSize);
        if(e.children.length===0 && e.textContent.trim() && fs<7) o.small.push((e.className||e.tagName)+' '+fs);
      });
      return JSON.stringify(o);})()`);
    console.log('AUDIT ' + audit);
  } finally {
    try { chrome.kill(); } catch (e) {}
    await sleep(300);
    try { fs.rmSync(profile, { recursive: true, force: true }); } catch (e) {}
  }
}
main().catch(e => { console.error('FAIL ' + e.message); process.exitCode = 1; });
