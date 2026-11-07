const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path'); const os = require('os');
const tmpclean = require('./tmpclean');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(__dirname, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9880 + Math.floor(Math.random()*10);
function send(ws,id,method,params){return new Promise((res,rej)=>{const mid=++id;const cb=(ev)=>{const m=JSON.parse(ev.data);if(m.id===mid){ws.removeEventListener('message',cb);m.error?rej(m.error):res(m.result);}};ws.addEventListener('message',cb);ws.send(JSON.stringify({id:mid,method,params:params||{}}));});}
/* Chrome 的一次性 profile 必须回收：见 tmpclean.js。hoist 出来让崩掉的那条路也能清。 */
let chrome = null, profDir = null;
(async()=>{
  profDir = fs.mkdtempSync(path.join(os.tmpdir(), 'v2v-'));
  chrome=spawn(CHROME,['--headless=new',`--remote-debugging-port=${PORT}`,`--user-data-dir=${profDir}`,'--window-size=412,892','--force-device-scale-factor=1','--hide-scrollbars','--no-first-run','--allow-file-access-from-files','about:blank'],{stdio:'ignore'});
  await new Promise(r=>setTimeout(r,800));
  let wsUrl=null; for(let i=0;i<60&&!wsUrl;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json`).then(r=>r.json());wsUrl=r.find(x=>x.type==='page').webSocketDebuggerUrl;}catch(e){await new Promise(r=>setTimeout(r,200));}}
  const ws=new WebSocket(wsUrl); await new Promise((res,rej)=>{ws.addEventListener('open',res);ws.addEventListener('error',rej);});
  let id=0; await send(ws,id,'Page.enable'); await send(ws,id,'Runtime.enable');
  await send(ws,id,'Page.navigate',{url:FILE});
  for(let i=0;i<25;i++){const ok=await send(ws,id,'Runtime.evaluate',{expression:'!!(state&&state.lib)',returnByValue:true}).then(r=>r.result&&r.result.value).catch(()=>false);if(ok)break;await new Promise(r=>setTimeout(r,300));}
  const expr=`(function(){
    var o=[],P=0,F=0,T=function(n,c,x){P+=(c?1:0);F+=(c?0:1);o.push((c?'PASS  ':'FAIL  ')+n+(x!==undefined?('  ['+x+']'):''));};
    /* 断言总数闸门：与 v3v 同一理由 —— 少一条就是少一条，不能装作还是全绿。 */
    var EXP_N=47;
    /* 与 v3v 同：整块包 try，一处抛错不再带走全部已跑结果，改为报出中断段。 */
    var SECT='init';
    try{
    SECT='V02-01'; // V02-01 配片 + 赛扣
    var a=platesPerSide(100,false), b=platesPerSide(100,true);
    T('配片 100kg 关赛扣 = 25+15', a.plates.map(function(p){return p.kg;}).join('+')==='25+15', a.plates.map(function(p){return p.kg;}).join('+'));
    T('配片 100kg 开赛扣 = 25+10+2.5', b.plates.map(function(p){return p.kg;}).join('+')==='25+10+2.5', b.plates.map(function(p){return p.kg;}).join('+'));
    T('赛扣每侧重量 = 37.5', Math.abs(b.perSide-37.5)<0.001, b.perSide);
    var c=platesPerSide(101.3,false);
    T('101.3kg 出现余量提示', c.remainder>0 && !!c.note, c.remainder+' '+c.note);
    var d=platesPerSide(22,true);
    T('22kg+赛扣 → 不足提示', !!(d.note&&d.note.indexOf('赛扣')>=0), d.note);
    var e=platesPerSide(25,true);
    T('25kg+赛扣 合法无提示', e.plates.length===0 && !e.note, e.note);
    T('PLATES 含 1/0.75/0.5/0.25', [1,0.75,0.5,0.25].every(function(k){return PLATES.some(function(p){return p.kg===k;});}));
    SECT='V02-02'; // V02-02 目标 RPE 位置
    var tb=document.getElementById('edTgtRpeBtn');
    T('目标 RPE 胶囊在组策略/疲劳双框内', !!tb && tb.closest('.two-box')!==null && tb.closest('.tbox')!==null);
    T('目标 RPE 胶囊在 .rr-grid 之外', !!tb && tb.closest('.rr-grid')===null);
    T('ACTUAL RPE 框内已无目标胶囊', document.querySelector('.rr-box .chip-s')===null);
    SECT='V02-03'; // V02-03 Day 命名
    var dd=state.structure.dayDefs;
    /* 原来 dd[1]/dd[2]/dd[3] 裸取下标：训练日一旦少于 4 个，抛错会带走整块断言，
       屏幕只剩一条「求值失败」而不是「Day D 不见了」。 */
    var dayAt=function(i){ return (dd&&dd[i])?dd[i]:null; };
    T('Day 定义至少有 A/B/C/D 四个', !!(dayAt(0)&&dayAt(1)&&dayAt(2)&&dayAt(3)), dd?dd.length:0);
    var dB=dayAt(1), dC=dayAt(2), dD=dayAt(3);
    T('Day B 中文名取自计划 Days.title_zh（非旧内置名）',
      !!dB && dB.titleZh==='卧推主项 · 实力推 · 引体 · 双杠 · 节奏卧推 · 侧平举/面拉', dB&&dB.titleZh);
    T('Day C 中文名取自计划 Days.title_zh（非旧内置名）',
      !!dC && dC.titleZh==='硬拉主项 · 节奏深蹲 3×3 · 杠铃划船 · 举腿', dC&&dC.titleZh);
    T('constraints 用 upperOnly 且旧键已清', !!dd && dd.length>0 && dd.every(function(x){return !!x.constraints && typeof x.constraints.upperOnly==='boolean' && !x.constraints.focusBenchOnly;}));
    T('Day D 约束位随计划 Days.forbid_heavy_sbd（本计划为 false）',
      !!dD && !!dD.constraints && dD.constraints.forbidHeavySbd===false,
      dD&&dD.constraints&&dD.constraints.forbidHeavySbd);
    SECT='V02-04'; // V02-04 配置页
    var sw=document.getElementById('stWeeks');
    T('总周数输入为 readonly', sw && sw.hasAttribute('readonly'));
    SECT='V02-05'; // V02-05 JTS（六维改版 D14：R=归一均值、未填剔除、档位取 ready_at）
    var JB={sleep:7,stress:1,fatigue:1,soreness:1,motivation:7,energy:7};   /* 每维最佳（正向 7 / 反向 1） */
    var JW={sleep:1,stress:7,fatigue:7,soreness:7,motivation:1,energy:1};   /* 每维最差 */
    var JM={sleep:5,stress:5,fatigue:5,soreness:5,motivation:5,energy:5};   /* 全 5 分 */
    T('JTS 六维键序取自契约 item_order', JTS_DIMS.length===6 && JTS_DIMS.map(function(x){return x.k;}).join(',')==='sleep,stress,fatigue,soreness,motivation,energy', JTS_DIMS.map(function(x){return x.k;}).join(','));
    T('JTS 反向维=压力/疲劳/酸痛', JTS_DIMS.filter(function(x){return x.rev;}).map(function(x){return x.k;}).join(',')==='stress,fatigue,soreness', JTS_DIMS.filter(function(x){return x.rev;}).map(function(x){return x.k;}).join(','));
    T('JTS 全最佳 → R=100', jtsCalc(JB).score===100, jtsCalc(JB).score);
    T('JTS 全 5 分 → R=50', jtsCalc(JM).score===50, jtsCalc(JM).score);
    T('JTS 全最差 → R=0', jtsCalc(JW).score===0, jtsCalc(JW).score);
    T('JTS 已填<3 → R=null（未填剔除、不再中性 5→58）', jtsCalc({sleep:7,stress:1}).score===null, jtsCalc({sleep:7,stress:1}).score);
    T('JTS 档位映射取 ready_at=[90,75,60,45]', jtsToReady(95)===READY[0] && jtsToReady(49)===READY[3] && jtsToReady(44)===READY[4], jtsToReady(95).s+'/'+jtsToReady(49).s+'/'+jtsToReady(44).s);
    SECT='V02-06'; // V02-06 TELEMETRY
    /* 状态监控面板现在默认关着（入口在设置页·我的档案）。这一组测的是面板里的格子，
       所以先按「用户已经打开」进门；关门那条腿由 v3v 的 TM 段单独测。 */
    state.teleOn=true;
    openTeleSheet();
    var rows=document.querySelectorAll('#teleFields .tf-row');
    T('遥测 10 个字段行', rows.length===10, rows.length);
    T('遥测全部默认启用', Array.prototype.every.call(rows,function(r){return !r.classList.contains('off');}));
    T('遥测初始值为空(占位 —)', Array.prototype.every.call(rows,function(r){var i=r.querySelector('input');return !i||i.value==='';}));
    T('遥测每行有开关', document.querySelectorAll('#teleFields .tf-sw').length===10);
    SECT='V02-07'; // V02-07 周栏
    var pills=document.querySelectorAll('#weekRail .pill');
    T('周栏药丸数 = totalWeeks', pills.length===state.structure.totalWeeks, pills.length);
    T('周栏无 ·DL 文字', !Array.prototype.some.call(pills,function(p){return p.textContent.indexOf('·DL')>=0;}));
    var pillAt=function(i){ return pills[i]?pills[i]:null; };
    T('W1 属 Hyper 色类', !!pillAt(0) && pillAt(0).className.indexOf('ct-hyper')>=0, pillAt(0)&&pillAt(0).className);
    T('W4 属 Strength 色类（v0.42 减重保力：B2 从 W4 起，种子里不再有减载周）', !!pillAt(3) && pillAt(3).className.indexOf('ct-strength')>=0, pillAt(3)&&pillAt(3).className);
    T('W7 属 Peak 色类', !!pillAt(6) && pillAt(6).className.indexOf('ct-peak')>=0, pillAt(6)&&pillAt(6).className);
    /* Transmute / Deload 两档不在内置 8 周 3 Block 模板里，改由一份临时的 4 块结构点亮（末块带 1 个减载周）：
       进段留克隆，出段还原并重绘，后面的段落不受影响（同 v3v Q 段的套路）。 */
    var VBAK=clone(state), VSNAP=JSON.stringify(state);
    var vblocks=['Hyper','Transmute','Peak','Strength'].map(function(c,i){
      return {id:'B'+(i+1),cycleType:c,nameZh:'色类'+c,nameEn:'ct'+c,workWeeks:2,deloadWeeks:i===3?1:0}; });
    applyStructure({startDate:VBAK.structure.startDate,blocks:vblocks,dayDefs:clone(VBAK.structure.dayDefs)});
    renderAll();
    var vp=document.querySelectorAll('#weekRail .pill');
    var vcls=function(i){ return vp[i]?String(vp[i].className):''; };
    T('临时 4 块 9 周结构：W3=ct-transmute / W5=ct-peak / W7=ct-strength / W9=ct-deload（色类跟 cycleType 与减载走，不跟周号走）',
      vp.length===9 && vcls(2).indexOf('ct-transmute')>=0 && vcls(4).indexOf('ct-peak')>=0 && vcls(6).indexOf('ct-strength')>=0 && vcls(8).indexOf('ct-deload')>=0,
      vcls(2)+' | '+vcls(4)+' | '+vcls(6)+' | '+vcls(8));
    state=VBAK; renderAll();
    T('V02-07 出段还原：周栏回到内置模板的周数，且本段没把共享对象改脏',
      document.querySelectorAll('#weekRail .pill').length===VBAK.structure.totalWeeks && JSON.stringify(state)===VSNAP,
      '胶囊='+document.querySelectorAll('#weekRail .pill').length);
    SECT='V02-08'; // V02-08 标题区
    var h2=document.getElementById('dayTitle');
    var meta=document.querySelector('.tele-meta');
    T('标题节点存在且 nowrap + ellipsis', !!h2 && getComputedStyle(h2).whiteSpace==='nowrap' && getComputedStyle(h2).textOverflow==='ellipsis');
    T('状态胶囊组存在且 nowrap', !!meta && getComputedStyle(meta).flexWrap==='nowrap');
    SECT='V02-09'; // V02-09 About
    openAboutSheet();
    var p1=document.getElementById('aboutP1'), p2=document.getElementById('aboutP2');
    var aboutTxt=function(el){ return el?String(el.textContent):''; };
    T('About 面板已打开', document.getElementById('aboutSheet').classList.contains('on'));
    T('About 含「钱进」', aboutTxt(p1).indexOf('钱进')>=0);
    T('About 含 GZCLP/JTS/RTS', ['GZCLP','JTS','RTS'].every(function(k){return aboutTxt(p1).indexOf(k)>=0;}));
    T('About 含 AI 制作', aboutTxt(p1).indexOf('AI')>=0);
    T('About 含纯本地无联网', aboutTxt(p2).indexOf('纯本地')>=0 && aboutTxt(p2).indexOf('无联网')>=0);
    T('About 徽章渲染', document.querySelectorAll('#aboutBadges .about-badge').length>=4);
    closeSheet('aboutSheet'); closeSheet('teleSheet');
    SECT='V02-10'; // V02-10 版本 / 迁移
    T('state.schemaVer = 本机盖章版本', state.schemaVer===SCHEMA_STAMP, state.schemaVer);
    T('场地库存默认关赛扣（旧全局 plateCfg 已退役，库存归场地）',
      !state.plateCfg && !!state.venues && collarsOn()===false
      && state.activeVenueId===GEAR_SCHEMA.venues.id_legacy
      && Object.keys(state.venues).length===1,
      'collarsOn=' + collarsOn() + ' plateCfg在否=' + (!!state.plateCfg));
    T('teleFields 10 项全 true', !!state.teleFields && Object.keys(state.teleFields).length===10 && Object.keys(state.teleFields).every(function(k){return state.teleFields[k]===true;}), state.teleFields&&Object.keys(state.teleFields).length);
    T('jts 已初始化', !!state.jts);
    }catch(ZERR){
      T('Z0 断言块在 '+SECT+' 段中途抛错（其后断言未执行）', false,
        ZERR.name+': '+String(ZERR.message).slice(0,90));
    }
    T('Z1 断言总数无漂移', P+F+1===EXP_N, '实到 '+(P+F+1)+' 应 '+EXP_N);
    return o.join('\\n');})()`;
  const r=await send(ws,id,'Runtime.evaluate',{expression:expr,returnByValue:true});
  /* 判定：v2v 原先无条件 exit(0)，45 项断言写错也永远「全绿」。
     取不到结果（求值抛异常 / 页面没就绪）同样算失败，不能当通过。 */
  const out=(r&&r.result&&typeof r.result.value==='string')?r.result.value:null;
  if(out===null){
    console.log('FAIL  整个 v2v 断言块求值失败：'+JSON.stringify(r&&(r.exceptionDetails||r.result)||{}).slice(0,300));
  }
  /* 原先两个分支各打印一次 out，屏幕上的 45 行其实输了两遍。 */
  const failed=out===null||/^FAIL/m.test(out);
  if(out!==null){
    const nP=(out.match(/^PASS/gm)||[]).length, nF=(out.match(/^FAIL/gm)||[]).length;
    console.log(out+'\n\n== v2v 汇总: '+nP+' PASS / '+nF+' FAIL （共 '+(nP+nF)+' 项）==');
  }
  await tmpclean.close(chrome, profDir);
  process.exit(failed?1:0);
})().catch(async e=>{
  console.error(e);
  await tmpclean.close(chrome, profDir);
  process.exit(1);
});
