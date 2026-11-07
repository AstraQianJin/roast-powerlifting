#!/usr/bin/env node
// gearv.js —— 配重引擎（Load Resolver）专属回归 · v0.31 节点③b / D12
//
// 与既有套件的分工：logicv 的 P 段钉的是「杠铃口径下贪心配片是否最优」，v3v/uiv 钉的是
// 「首页/编辑器长什么样、点下去有没有反应」。这套钉的是 Resolver 自己：六类 kind 的
// effective / step / recipe / warnings、库存变化如何改步长、调用点是否真的改道到 Effective 层。
// 参照系一律独立于被测函数：契约 JSON 的 step_rule 在 harness 侧重算一遍，配片用「片和+余数
// == 逐侧需求」的定义式，不用页面那份贪心当自己的答案。
//
//   node tools/gearv.js
const { spawn } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const tmpclean = require('./tmpclean');

const HERE = __dirname;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(HERE, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9880 + Math.floor(Math.random() * 20);

/* 契约里步长公式的独立读法：本文件不复制数值，只从同一份 JSON 取规则名，
   数值参照在 harness 侧按「min_plate / posts / increment × sides / gcd / unit」重算。 */
const RULE = JSON.parse(fs.readFileSync(path.join(HERE, 'schema', 'RPL-Gear-v2.json'), 'utf8'));

let PASS = 0, FAIL = 0, LINES = [];
function T(id, name, ok, detail) {
  PASS += ok ? 1 : 0; FAIL += ok ? 0 : 1;
  LINES.push((ok ? 'PASS  ' : 'FAIL  ') + id + ' ' + name +
    (detail !== undefined ? '  [' + detail + ']' : ''));
}

function send(ws, id, method, params) {
  return new Promise((res, rej) => {
    const mid = ++id;
    const cb = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id !== mid) return;
      ws.removeEventListener('message', cb);
      m.error ? rej(m.error) : res(m.result);
    };
    ws.addEventListener('message', cb);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
}
async function evalIn(ws, idRef, expr) {
  const r = await send(ws, idRef.v, 'Runtime.evaluate',
    { expression: expr, returnByValue: true, awaitPromise: false });
  if (r.exceptionDetails) {
    throw new Error('页面求值失败：' + ((r.exceptionDetails.exception && r.exceptionDetails.exception.description) ||
      r.exceptionDetails.text));
  }
  return r.result.value;
}

/* 一次性量具：入段拍下 state 与四路分片，出段按快照整体还原。
   G3 里 quickLoad / setGearBarKg 是真的落账（合法写），不还原就会污染 K 段那类不变量。 */
const HELP = `(function(){
  var K=[LS_PREFS,LS_WORK,LS_LIB,LS_ARCHIVE];
  function d(s){var h=5381;for(var i=0;i<s.length;i++){h=((h<<5)+h+s.charCodeAt(i))|0;}return (h>>>0).toString(16);}
  window.__gearv={
    save:function(){
      window.__gearv._st=JSON.stringify(state);
      window.__gearv._sh=K.map(function(k){return localStorage.getItem(k);});
      return true;
    },
    restore:function(){
      K.forEach(function(k,i){var v=window.__gearv._sh[i];if(v===null)localStorage.removeItem(k);else localStorage.setItem(k,v);});
      state=JSON.parse(window.__gearv._st);
      try{renderAll();}catch(e){}
      return true;
    },
    hash:function(){return d(JSON.stringify(state))+'|'+K.map(function(k){return d(localStorage.getItem(k)||'');}).join('|');}
  };
  return true;
})()`;

/* ---------------- G1：六类 kind 的 effective / step / recipe / warnings ----------------
   每个用例都显式给全 e.gear 的关键字段，避免场地默认与 gearDefaults 掺进来；
   ctx.inventory 一律现造，所以结果与本机存档无关。 */
const G1 = `(function(){
  var ALL=[25,20,15,10,5,2.5,1.25,1,0.75,0.5,0.25];
  var COARSE=[25,20,15,10,5,2.5,1.25];
  function inv(list, extra){
    var p={}; list.forEach(function(kg){p[kg]=null;});
    var o={bar_kg:20,collar_on:true,collar_pair_kg:5,plates:p,dumbbells:null};
    if(extra) Object.keys(extra).forEach(function(k){o[k]=extra[k];});
    return o;
  }
  function E(kind,load,gear,mv){
    var g={kind:kind}; if(gear) Object.keys(gear).forEach(function(k){g[k]=gear[k];});
    return {mv:(mv||'GEARV_PROBE'),cat:'S.Squat',mode:'T1.Mod',load:load,reps:5,gear:g};
  }
  function V(e,bw,iv){
    var v=solveLoad(e,{bw:bw,inventory:iv});
    return {kind:v.kind,eff:v.effectiveKg,achieved:v.achievedKg,step:v.stepKg,exact:v.exact,
            warn:v.warnings.slice(),recipe:v.recipe};
  }
  var bg={barKg:20,collarOn:true,collarPairKg:5};
  var pg={posts:2,baseKg:20};
  /* 插片档位表已改为器械资料（record.stack.ladders，绝对 kg）。夹具显式登记两台表：
     A 栈 20 起每档 2.5（9 档）、B 栈 20 起每档 5（5 档）；销位仍是动作行 e.gear.stackPins。 */
  var rec=gearRecordAt(resolveVenueId({mv:'GEARV_PROBE'}),'GEARV_PROBE',true);
  rec.kind='stack';
  rec.stack={v:1,ladders:[
    {v:1,levels:[20,22.5,25,27.5,30,32.5,35,37.5,40],updatedAt:'2026-01-01T00:00:00.000Z'},
    {v:1,levels:[20,25,30,35,40],updatedAt:'2026-01-01T00:00:00.000Z'}]};
  /* 非等差夹具：前段 2.5、后段 3.5，独占一台机器，避免覆盖双栈那条。 */
  var mix=gearRecordAt(resolveVenueId({mv:'GEARV_PROBE_MIX'}),'GEARV_PROBE_MIX',true);
  mix.kind='stack';
  mix.stack={v:1,ladders:[{v:1,levels:[20,22.5,25,28.5,32,35.5,39],updatedAt:'2026-01-01T00:00:00.000Z'}]};
  var sg={stacks:2,stackPins:[8,4]};
  var dg={sides:2,incrementKg:2.5};
  var wg={lever:1};
  var spg={unitKg:24,count:2};
  var o={
    bb:    V(E('barbell',100,bg),87.5,inv(ALL)),
    bbRem: V(E('barbell',105.3,bg),87.5,inv(ALL)),
    bbLow: V(E('barbell',10,bg),87.5,inv(ALL)),
    pl:    V(E('plate',100,pg),87.5,inv(ALL)),
    plRem: V(E('plate',101,pg),87.5,inv(COARSE)),
    st:    V(E('stack',80,sg),87.5,inv(ALL)),
    stOff: V(E('stack',85,sg),87.5,inv(ALL)),
    stNo:  V(E('stack',80,sg,'GEARV_PROBE_NO'),87.5,inv(ALL)),
    stMix: V(E('stack',32,{stacks:1},'GEARV_PROBE_MIX'),87.5,inv(ALL)),
    db:    V(E('dumbbell',24,dg),87.5,inv(ALL)),
    dbSnap:V(E('dumbbell',24,dg),87.5,inv(ALL,{dumbbells:[20,22,25,30]})),
    bwPlus:V(E('bw',25,wg),87.5,inv(ALL)),
    bwPure:V(E('bw',0,wg),87.5,inv(ALL)),
    bwAsst:V(E('bw',-30,wg),87.5,inv(ALL)),
    bwOver:V(E('bw',-100,wg),87.5,inv(ALL)),
    bwMiss:V(E('bw',25,wg),0,inv(ALL)),
    sp:    V(E('special',0,spg),87.5,inv(ALL)),
    spMan: V(E('special',0,{unitKg:24,count:2,manualKg:50}),87.5,inv(ALL))
  };
  /* solveLoad 只收 (e, ctx)：步长必须把造好的 inventory 塞进 ctx，
     直接把 bw / inv 当第二、三参数传会让 Resolver 回落当前场地，测的就不是「换个场地」了。 */
  o.steps={
    bbFine:V(E('barbell',100,bg),87.5,inv(ALL)).step,
    bbCoarse:V(E('barbell',100,bg),87.5,inv([2.5])).step,
    bbEmpty:V(E('barbell',100,bg),87.5,inv([])).step,
    plate:V(E('plate',100,{posts:2,baseKg:0}),87.5,inv(ALL)).step,
    plate4:V(E('plate',100,{posts:4,baseKg:0}),87.5,inv(COARSE)).step,
    dumbbell:V(E('dumbbell',24,dg),87.5,inv(ALL)).step,
    stack:V(E('stack',80,sg),87.5,inv(ALL)).step,
    bw:V(E('bw',0,wg),87.5,inv(ALL)).step,
    special:V(E('special',0,spg),87.5,inv(ALL)).step
  };
  o.fallback=GEAR_SCHEMA.step_rule.no_stock_fallback;
  o.kinds=GEAR_KINDS.slice();
  /* 夹具登记了两条档位表记录；量完即还原，G0.2 靠快照哈希复核零副作用。 */
  window.__gearv.restore();
  return JSON.stringify(o);
})()`;

/* ---------------- G2：处方解析的现行语义 ----------------
   §4 交接文档写明 v0.32⑥ 会重写 prescriptionOf 为逐组结构；在那一版之前，
   本段只钉现行不变量（sets 恒等于 setsOf / Top 系逐组串 / 标签分流 / backoff 默认 10%）。
   v0.32 完成时把这一批替换成逐组断言，不要直接删掉。 */
const G2 = `(function(){
  var modes=['Top.Set','Top.Single','Top.Test','T1.Mod','RTS.Mod','T3.Mod','T1.Mod.DL','T2.5x5'];
  var rows=modes.map(function(m){
    var sc=prescriptionOf({mode:m,reps:5});
    return {mode:m,sets:sc.sets,of:setsOf(m),rx:sc.rx,tag:sc.tag,backoff:sc.backoff,amrap:sc.amrap};
  });
  return JSON.stringify({rows:rows,backoffOpts:BACKOFF_OPTIONS.slice(),backoffDefault:BACKOFF_DEFAULT});
})()`;

/* ---------------- G3：调用点改道的不变量（真点按钮 / 真开编辑器） ----------------
   整段在一个探针里：出段前 recover 到 G0 快照，由 G0.2 复核账本与四路分片零差异。 */
const G3 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var bar={mv:'W1_A_GEARV_BB',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
           gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  var stk={mv:'W1_A_GEARV_ST',cat:'S.Squat',mode:'T1.Mod',load:80,reps:5,rpe:8,
           gear:{kind:'stack',stacks:2,stackPins:[8,4]}};
  var recS=gearRecordAt(resolveVenueId(stk),stk.mv,true);
  recS.kind='stack';
  recS.stack={v:1,ladders:[
    {v:1,levels:[20,22.5,25,27.5,30,32.5,35,37.5,40],updatedAt:'2026-01-01T00:00:00.000Z'},
    {v:1,levels:[20,25,30,35,40],updatedAt:'2026-01-01T00:00:00.000Z'}]};
  d.exercises=[bar,stk];
  renderExercises();
  var arts=[].slice.call(document.querySelectorAll('#exList article.ex'));
  out.nArt=arts.length;
  out.bbHtml=arts[0]?arts[0].innerHTML:'';
  out.stHtml=arts[1]?arts[1].innerHTML:'';
  out.cardBtns=arts[0]?[].slice.call(arts[0].querySelectorAll('.stepper button')).map(function(b){return b.textContent;}):[];
  out.cardStep=fmtStep(stepOf(bar));
  /* 真点一颗 +step，再点 −step 回原值 */
  var before=+d.exercises[0].load, st=stepOf(bar);
  quickLoad(null,0,1);  var afterPlus=+d.exercises[0].load;
  quickLoad(null,0,-1); var afterBack=+d.exercises[0].load;
  out.quick={before:before,step:st,plus:afterPlus,back:afterBack};
  /* 编辑器：动作级杆重、六 chip、四颗步进按钮、赛扣开关 */
  openEditor(0);
  out.edBar=document.getElementById('edBar').value;
  out.gearBar=gearOf(d.exercises[0]).barKg;
  out.chips=document.getElementById('gearChips').querySelectorAll('button').length;
  out.kinds=GEAR_KINDS.length;
  out.edBtns=['edStepM2','edStepM1','edStepP1','edStepP2'].map(function(id){
    var b=document.getElementById(id);return b?b.textContent:null;});
  var stEd=stepOf(d.exercises[0]);
  out.edStep=[fmtStep(2*stEd),fmtStep(stEd)];
  var venueBarBefore=venueInv().bar_kg;
  setGearBarKg(15);
  out.bar15={eBar:d.exercises[0].gear.barKg,
             def:(function(){var r=gearRecordOf(d.exercises[0]);
               return (r&&r.params&&r.params.barKg!=null)?r.params.barKg:null;})(),
             venueBefore:venueBarBefore,venueAfter:venueInv().bar_kg};
  var coBefore=d.exercises[0].gear.collarOn;
  toggleGearCollars();
  out.collar={before:coBefore,after:d.exercises[0].gear.collarOn};
  /* 非杠铃编辑器：不画杆、不摆片配置行 */
  openEditor(1);
  var row=document.getElementById('plateCfgRow');
  out.nonBar={display:row?row.style.display:null,
              sleeve:document.querySelectorAll('#edPlateBar .pv-sleeve').length,
              hasBar:!!document.getElementById('edPlateBar')};
  closeAllSheets();
  /* 热身双形态：bw 恒回自重激活三连；数字路径仍从空杆起步 */
  var wb=warmups({mv:'W1_C_Dip',cat:'S.Squat',mode:'T2.Def',load:0,reps:8,gear:{kind:'bw',lever:1}});
  var wn=warmups(100);
  out.warmBw=wb.map(function(x){return x.w;});
  out.warmNumStart=wn.length?wn[0].w:null;
  out.barKg=barKg();
  /* e1RM 与吨位必须吃 Effective：纯自重行 load=0，净负荷 = BW × lever */
  var savePb=state.profile.bw, saveDb=d.bw, saveLog=state.e1rmLog;
  state.profile.bw=87.5; d.bw=87.5; state.e1rmLog=[];
  /* cat 必须以 .Main 结尾，anchorOf 才认得（否则 logT1MainE1rm 直接 return，探针会误判成口径错）。 */
  var pure={mv:'W1_C_GEARV_BW',cat:'S.Squat.Main',mode:'T1.Mod',load:0,reps:5,rpe:8,done:true,row:9,
            gear:{kind:'bw',lever:1}};
  var want=e1rm(87.5,5,8,undefined);
  logT1MainE1rm(state.week,state.day,pure);
  out.e1={want:want,got:state.e1rmLog.length?state.e1rmLog[0].e1rm:null,
          eff:effectiveLoad(pure),n:state.e1rmLog.length};
  /* 把本周其余日清空，让周吨位完全由这一条纯自重行贡献。别的动作会把「Effective 口径」
     的缺陷盖住：注入把 gv.effectiveKg 换回 e.load 时周吨位照样 > 0，断言就恒真了。 */
  var ww=state.weeks[String(state.week)]||{}, savedDays={};
  dayIds().forEach(function(did){
    savedDays[did]=ww[did]?ww[did].exercises:null;
    if(ww[did]) ww[did].exercises=[];
  });
  if(!ww[state.day]) ww[state.day]={exercises:[]};
  ww[state.day].exercises=[pure];
  out.posterTon=computePosterData('week',state.week,state.day).weekTonnage;
  dayIds().forEach(function(did){ if(ww[did]) ww[did].exercises=savedDays[did]||[]; });
  state.profile.bw=savePb; d.bw=saveDb; state.e1rmLog=saveLog;
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G4：定义式性质（20 目标 × 7 杆重 × 赛扣开关） ---------------- */
const BARS = [10, 15, 20, 25, 30, 35, 40];
const TARGETS = [20, 37.5, 40, 42.5, 60, 100, 100.1, 105.3, 140, 142.5,
  150, 175, 200, 222.5, 250, 317.5, 320, 350, 400, 500];
const G4 = `(function(bars,targets){
  var p={}; [25,20,15,10,5,2.5,1.25,1,0.75,0.5,0.25].forEach(function(kg){p[kg]=null;});
  var inv={bar_kg:20,collar_on:true,collar_pair_kg:5,plates:p,dumbbells:null};
  var rows=[];
  bars.forEach(function(b){ targets.forEach(function(t){ [false,true].forEach(function(c){
    var r=platesPerSide(t,c,b,5,inv);
    rows.push({bar:b,t:t,c:c,sum:r.plates.reduce(function(a,x){return a+x.kg;},0)+r.remainder,
      per:r.perSide,exact:r.exact,rem:r.remainder,n:r.plates.length,note:r.note||''});
  }); }); });
  return JSON.stringify({rows:rows,collarPair:COLLAR_KG});
})`;

function gcdRef(list) {
  const v = list.filter(x => x > 0).map(x => Math.round(x * 1000));
  if (!v.length) return 0;
  const g = (a, b) => b ? g(b, a % b) : a;
  return v.reduce((a, x) => g(a, x), v[0]) / 1000;
}
/* ---------------- G5：v7 迁移的三条语义闸门 ----------------
   反向验证 _sabotage_g1.py 的 7/8/9 号注入必须有 witness，而既有套件只在 A0 点名
   migrateStateV7、没有行为断言。这里直接喂最小自洽账本给两个子函数，不写 state。 */
const G5 = `(function(){
  function inv(){ var p={}; [25,20,15,10,5,2.5,1.25,1,0.75,0.5,0.25].forEach(function(k){p[k]=null;});
    return {bar_kg:20,collar_on:false,collar_pair_kg:5,plates:p,dumbbells:null}; }
  function rep(){ return {net2ext:[],dbSide:[],pending:[],kinds:{},
    deriveChanged:0,deriveSame:0,deriveSkipped:0,deriveSample:[]}; }
  function mk(bw, rows, logs){
    return {schemaVer:6,profile:{bw:bw},activeVenueId:'legacy',
      venues:{legacy:{id:'legacy',inventory:inv()}},gearDefaults:{},
      weeks:{'1':{A:{bw:bw,exercises:rows}}},e1rmLog:logs||[]};
  }
  /* v7GearKind 只认 gearDefaults / equip 推断，不看 e.gear —— 夹具必须把 kind 登记进默认表。 */
  var sA=mk(87.5,[
    {mv:'GV_PURE',cat:'S.Squat.Main',mode:'T1.Mod',load:0,reps:5,row:9,gear:{kind:'bw',lever:1}},
    {mv:'GV_NET', cat:'S.Squat.Main',mode:'T1.Mod',load:112.5,reps:5,row:10,gear:{kind:'bw',lever:1}},
    {mv:'GV_DB',  cat:'S.Squat.Main',mode:'T1.Mod',load:24,reps:5,row:11,gear:{kind:'dumbbell',sides:2}}
  ]);
  sA.gearDefaults={GV_PURE:{kind:'bw'},GV_NET:{kind:'bw'},GV_DB:{kind:'dumbbell'}};
  var rA=rep(), bA=[]; v7ConvertLoads(sA,bA,rA);
  var sB=mk(0,[{mv:'GV_NOBW',cat:'S.Squat.Main',mode:'T1.Mod',load:110,reps:5,row:9,
                gear:{kind:'bw',lever:1}}]);
  sB.gearDefaults={GV_NOBW:{kind:'bw'}};
  var rB=rep(), bB=[]; v7ConvertLoads(sB,bB,rB);
  var exC={mv:'GV_NET',cat:'S.Squat.Main',mode:'T1.Mod',load:25,reps:5,rpe:8,row:9,
           gear:{kind:'bw',lever:1}};
  var want=+e1rm(112.5,5,8).toFixed(2);
  var sC=mk(87.5,[exC],[{id:'W1_A_9_GV_NET',week:1,day:'A',mv:'GV_NET',load:112.5,
                          reps:5,rpe:8,e1rm:want}]);
  sC.gearDefaults={GV_NET:{kind:'bw'}};
  var rC=rep(), bC=[]; v7RewriteDerived(sC,bC,rC);
  return JSON.stringify({
    a:{loads:sA.weeks['1'].A.exercises.map(function(e){return e.load;}),
       conv:sA.weeks['1'].A.exercises.map(function(e){return e.conv||null;}),
       n2:rA.net2ext.length,db:rA.dbSide.length,pend:rA.pending.length,bk:bA.length},
    b:{load:sB.weeks['1'].A.exercises[0].load,
       pending:!!sB.weeks['1'].A.exercises[0].gearPending,
       pendN:rB.pending.length,n2:rB.net2ext.length},
    c:{same:rC.deriveSame,changed:rC.deriveChanged,bk:bC.length,
       e1:sC.e1rmLog[0].e1rm,want:want}
  });
})()`;

/* ---------------- G6：§5 处方逐组解析（节点⑥新增 —— rx 原文是唯一权威） ----------------
   钉三件事：真实处方串解析正确；认不出的原文只回落、不谎称权威；
   运行时确实有一条种子 Top.Set 行走权威路径（证明旧「sets×reps 猜测污染 e.rx」这条链真的断了）。 */
const G6 = `(function(){
  function P(rx,mode){
    var s=prescriptionOf({mode:(mode||'T1.Mod'),reps:5,rx:rx});
    return {fromRx:!!s.fromRx, invalid:!!s.invalid, sets:s.sets, reps:s.reps, rx:s.rx, tag:s.tag,
            backoff:+(s.backoff||0).toFixed(3), amrap:!!s.amrap, n:(s.groups||[]).length,
            g:(s.groups||[]).map(function(x){ return x.sets+'x'+x.reps+'@'+x.factor; })};
  }
  var ts=P('1×3 + 2×5@-10%','Top.Set');
  var tp=P('1×1 + 1×4@-10%','Top.Single');
  var am=P('4×12+','T3.Mod');
  var st=P('5×5','T1.Mod');
  /* 计划里真实出现过的写法（2026-11-09 起的新 8 周计划）：无空格 +、全角减号、绝对强度、单段多组、段注。 */
  var ds=P('1×3+2×3−5%','Top.Set');
  var ab=P('2×5 @60%','T1.Mod');
  var b3=P('3×2','T2.5x5');
  var r15=P('2×15','T3.Mod');
  var cm=P('1×1 · 第 1 把','Top.Test');
  var zh=P('1×3 顶组 + 2×3 减 5% 补组','Top.Set');
  /* sets 列驱动组数：计划写的 sets 优先于 rx 拆出来的组数；缺省才回到 rx / proto。 */
  var own=prescriptionOf({mode:'T1.Mod',reps:5,rx:'5×5',sets:3});
  var ownS={fromRx:!!own.fromRx,invalid:!!own.invalid,sets:own.sets,reps:own.reps,tag:own.tag};
  var bad=P('乱七八糟','Custom');
  var empty=P('','T1.Mod');
  /* 全表扫一条真能解析的 Top.* 种子行：只读，不动 state（出段快照靠 G0.2 复核零副作用）。 */
  var live=null;
  Object.keys(state.weeks).forEach(function(w){
    var wd=state.weeks[w];
    Object.keys(wd).forEach(function(d){
      var exs=(wd[d]&&wd[d].exercises)||[];
      for(var i=0;i<exs.length;i++){
        var x=exs[i];
        if(!live && /^Top\\./.test(String(x.mode||'')) && parseRx(x.rx).parsed)
          live={mode:x.mode, rx:x.rx, p:P(x.rx,x.mode)};
      }
    });
  });
  var L=140, S=2.5, boW=mround(L*0.9,S);
  return JSON.stringify({ts:ts,tp:tp,am:am,st:st,bad:bad,empty:empty,live:live,
                         ds:ds,ab:ab,b3:b3,r15:r15,cm:cm,zh:zh,own:ownS,
                         so7:setsOf('T1.Mod',7),so0:setsOf('T1.Mod',0),
                         boW:boW,delta:Math.abs(L*0.9-boW)});
})()`;

/* ---------------- G7：首页载荷格按器械口径显示（节点⑦⑧新增） ----------------
   钉两条不变量：自重主数字必须吃 effectiveKg（净负荷），不是 e.load 原值（那是带符号外载，
   顶上去会把「加重 25」显示成 25 而不是 112.5）；哑铃主数字仍是单边输入、灰后缀补 ×边=总重。
   渲染只读 .lbox / .plate-strip 的文本，出段前 restore 到 G0 快照，由 G0.2 复核零副作用。 */
const G7 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises, savedBw=d.bw, savedPbw=state.profile.bw;
  state.profile.bw=87.5; d.bw=87.5;
  var rPlus ={mv:'G7_PLUS', cat:'S.Squat',mode:'T1.Mod',load:25, reps:5,rpe:8,gear:{kind:'bw',lever:1}};
  var rAssist={mv:'G7_ASSIST',cat:'S.Squat',mode:'T1.Mod',load:-30,reps:5,rpe:8,gear:{kind:'bw',lever:1}};
  var rDumb ={mv:'G7_DUMB', cat:'S.Squat',mode:'T1.Mod',load:24, reps:5,rpe:8,gear:{kind:'dumbbell',sides:2,incrementKg:2.5}};
  d.exercises=[rPlus,rAssist,rDumb];
  renderExercises();
  function read(i){
    var a=document.querySelectorAll('#exList article.ex')[i];
    if(!a) return {lab:'',b:'',strip:'',html:''};
    var lab=a.querySelector('.lbox label'), b=a.querySelector('.lbox b'), st=a.querySelector('.plate-strip');
    return {lab:lab?lab.textContent:'', b:b?b.textContent:'', strip:st?st.textContent:'',
            html:st?st.innerHTML:''};
  }
  out.r0=read(0); out.r1=read(1); out.r2=read(2);
  out.eff=[effectiveLoad(rPlus),effectiveLoad(rAssist),effectiveLoad(rDumb)];
  d.exercises=savedEx; d.bw=savedBw; state.profile.bw=savedPbw;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G8：节点⑨⑩ 挂片位编辑器 + 首页 gear-strip 前四形态 ----------------
   引擎（G1.4/1.5/1.15）已钉挂片数学；这组只钉 UI 接线与「均衡装载可视化」本身——
   posts 选择行从契约派生、网格每位一叠同配方片、史密斯独立于杠铃杆、首页 strip 给挂片可数形态。
   全部走真点（openEditor + setGear*），出段 restore 到 G0 快照，由 G0.2 复核零副作用。 */
const G8 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var pl={mv:'W1_A_GEARV_PL',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'plate',posts:2,baseKg:20,variant:'standard'}};
  var sm={mv:'W1_A_GEARV_SM',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'plate',posts:4,baseKg:25,variant:'smith'}};
  var bb={mv:'W1_A_GEARV_BB8',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  d.exercises=[pl,sm,bb];
  renderExercises();
  var arts=[].slice.call(document.querySelectorAll('#exList article.ex'));
  out.plHtml=arts[0]?arts[0].innerHTML:'';
  out.smHtml=arts[1]?arts[1].innerHTML:'';
  function stripTxt(i){ var s=arts[i]&&arts[i].querySelector('.plate-strip'); return s?s.textContent:''; }
  function postCnt(i){ return arts[i]?arts[i].querySelectorAll('.plate-strip [data-gz="horn"]').length:0; }
  out.plStripText=stripTxt(0); out.smStripText=stripTxt(1);
  out.plPosts=postCnt(0); out.smPosts=postCnt(1);
  out.smStrip=gearStripText(gearViewOf(sm));
  /* 编辑器：挂片位配置行 + 均衡网格 */
  openEditor(0);
  var cfg=document.getElementById('gearPlateCfg');
  out.cfgShown=cfg?cfg.style.display:null;
  out.postOpts=(function(){var s=document.getElementById('edPosts');return s?s.options.length:-1;})();
  out.expPostOpts=POSTS_OPTIONS.length;
  var bar=document.getElementById('edPlateBar');
  out.postBlocks=(bar.innerHTML.match(/data-gz="horn"/g)||[]).length;
  out.discBlocks=(bar.innerHTML.match(/data-gz="disc"/g)||[]).length;
  out.sleeveBar=bar.querySelectorAll('.pv-sleeve').length;
  out.noSleeveBar=bar.classList.contains('no-sleeve');
  /* posts 写回：合法 4 生效、非法 3 拒 */
  setGearPosts(4);
  out.post4=d.exercises[0].gear.posts;
  out.blocksAfter4=(document.getElementById('edPlateBar').innerHTML.match(/data-gz="horn"/g)||[]).length;
  setGearPosts(3);
  out.postAfterBad=d.exercises[0].gear.posts;
  /* 史密斯开关 + 基数写回（下限 0） */
  toggleGearSmith();
  out.variant1=d.exercises[0].gear.variant;
  out.baseInShown=document.getElementById('edBaseKg').value;
  setGearBaseKg(25);
  out.base=d.exercises[0].gear.baseKg;
  setGearBaseKg(-5);
  out.baseAfterBad=d.exercises[0].gear.baseKg;
  /* 杠铃对照：配置行隐藏、套管轴在（证明 no-sleeve 双向切） */
  openEditor(2);
  var cfg2=document.getElementById('gearPlateCfg');
  out.cfgHiddenBar=cfg2?cfg2.style.display:null;
  out.sleeveOnBar=document.getElementById('edPlateBar').querySelectorAll('.pv-sleeve').length;
  closeAllSheets();
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G9：节点⑪⑫ 插片/特殊编辑器 + 档位表面板 + 竖向配重堆 ----------------
   引擎数学（G1.6/1.7/1.13/1.14/1.17/1.18）已钉；这组钉接线：栈数从契约派生、档位表逐机编辑、
   销位只写动作行、旧 base/inc 字段不再存在、龙门架开关、特殊类手填覆盖。全部真点，出段 restore。 */
const G9 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var st={mv:'W1_A_GEARV_ST9',cat:'S.Squat',mode:'T1.Mod',load:80,reps:5,rpe:8,
          gear:{kind:'stack',stacks:1,variant:'standard',stackPins:[8]}};
  var recSt=gearRecordAt(resolveVenueId(st),st.mv,true);
  recSt.kind='stack';
  recSt.stack={v:1,ladders:[{v:1,levels:[20,22.5,25,27.5,30,32.5,35,37.5,40],
                             updatedAt:'2026-01-01T00:00:00.000Z'}]};
  var sp={mv:'W1_A_GEARV_SP9',cat:'S.Squat',mode:'T1.Mod',load:0,reps:5,rpe:8,
          gear:{kind:'special',label:'壶铃',unitKg:16,count:3}};
  var spm={mv:'W1_A_GEARV_SPM9',cat:'S.Squat',mode:'T1.Mod',load:0,reps:5,rpe:8,
           gear:{kind:'special',label:'药球',unitKg:24,count:2,manualKg:46}};
  var bb={mv:'W1_A_GEARV_BB9',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  d.exercises=[st,sp,spm,bb];
  renderExercises();
  function art(i){ return document.querySelectorAll('#exList article.ex')[i]; }
  function lb(i){ var b=art(i)&&art(i).querySelector('.lbox b'); return b?b.textContent:''; }
  function strip(i){ var s=art(i)&&art(i).querySelector('.plate-strip'); return s?s.textContent:''; }
  function stripHtml(i){ var s=art(i)&&art(i).querySelector('.plate-strip'); return s?s.innerHTML:''; }
  out.stStrip=strip(0); out.stHtml=art(0)?art(0).innerHTML:'';
  out.stStripHtml=stripHtml(0);
  out.sp0B=lb(1); out.sp0Strip=strip(1); out.sp0StripHtml=stripHtml(1);
  out.sp1B=lb(2); out.sp1Strip=strip(2); out.sp1StripHtml=stripHtml(2);
  /* 插片编辑器：配置行 + 竖向配重堆（9 档 ≤14 全画，销位 8 在最底档、0..8 全实心） */
  openEditor(0);
  var sc=document.getElementById('gearStackCfg');
  out.cfgShown=sc?sc.style.display:null;
  out.stackOpts=(function(){var s=document.getElementById('edStacks');return s?s.options.length:-1;})();
  out.expStackOpts=STACKS_OPTIONS.length;
  out.cableChip=!!(sc&&sc.querySelector('.chip-s'));
  out.spHiddenInStack=(document.getElementById('gearSpecialCfg')||{}).style.display;
  var bar=document.getElementById('edPlateBar');
  out.cols=(bar.innerHTML.match(/class="gz-stack-col"/g)||[]).length;
  out.winBlocks=bar.querySelectorAll('.gz-block').length;
  out.onBlocks=bar.querySelectorAll('.gz-block[data-engaged="1"]').length;
  out.hasPin=!!bar.querySelector('[data-gz="pin"]');
  out.sleeveStack=bar.querySelectorAll('.pv-sleeve').length;
  out.noSleeveStack=bar.classList.contains('no-sleeve');
  /* 栈数写回：合法 2 生效，但第二栈没有档位表 → 只出「未登记」提示，不画假刻度 */
  setGearStacks(2);
  out.stacks2=d.exercises[0].gear.stacks;
  out.cfgRows=(sc.innerHTML.match(/class="gp-cfg-row"/g)||[]).length;
  out.noTableTxt=/未登记档位表/.test(sc.textContent);
  out.colsAfter2=(function(){var h=document.getElementById('edPlateBar').innerText||'';
    var b=document.getElementById('edPlateBar');
    return (b.innerHTML.match(/class="gz-stack-col"/g)||[]).length;})();
  /* 销位只写动作行 + 区间钳制（上限从契约读） */
  setGearStackField(0,'pin',10);
  out.pin0=d.exercises[0].gear.stackPins[0];
  setGearStackField(0,'pin',999);
  out.pinAfterBad=d.exercises[0].gear.stackPins[0];
  /* 旧模型字段不再被接受：字段写到器械资料 params 也不再含 baseKg/incKg，动作行无 stackCfg */
  setGearStackField(1,'incKg',7);
  var rr=gearRecordOf(d.exercises[0])||{};
  out.oldKeys=['stackCfg','baseKg','incKg'].filter(function(k){
    return ((d.exercises[0].gear||{})[k]!==undefined)||(((rr.params)||{})[k]!==undefined);
  }).join(',');
  out.cfg2inc=!(('incKg' in ((rr.params)||{})) || ('incKg' in ((d.exercises[0].gear||{}))));
  out.loadStackUntouched=d.exercises[0].load;
  /* 档位表逐机编辑（走面板保存路径）：前段 2.5、后段 3.5 原样入库 */
  setGearStacks(1);
  setGearStackPin(0,8);
  openStackSheet(0);
  stackDraft.byStack[0]=[20,22.5,25,28.5,32,35.5,39].map(String);
  renderStackSheet();
  stackSheetSave();
  var lad=stackLadderOf(st);
  out.savedLevels=lad.ok?lad.ladders[0].join(','):'ERR';
  out.savedCount=(rr.stack&&rr.stack.ladders&&rr.stack.ladders[0].levels.length)||0;
  out.savedStep=stackStepKg(lad.ok?lad.ladders:null,0);
  setGearStackPin(0,4);
  out.pinAfterSave=d.exercises[0].gear.stackPins[0];
  /* 非等差 ± 走相邻可达档：28.5 → 32（+3.5），不是 +2.5 */
  var nx=nextReachable(st,28.5,1,1);
  out.next={load:nx?nx.load:null,pins:nx?nx.pins.join(','):null};
  /* 龙门架开关：variant 来回翻 */
  toggleGearCable();
  out.variantC=d.exercises[0].gear.variant;
  out.chipOn=/class="chip-s on"/.test(document.getElementById('gearStackCfg').innerHTML);
  toggleGearCable();
  out.variantBack=d.exercises[0].gear.variant;
  /* 非法栈数放最后：失守时不污染上面各腿的夹具形态 */
  setGearStacks(3);
  out.stacksAfterBad=d.exercises[0].gear.stacks;
  /* 特殊编辑器：算术串 + 下限把关 */
  out.strip1=gearStripText(gearViewOf(d.exercises[1]));
  openEditor(1);
  out.spCfgShown=(document.getElementById('gearSpecialCfg')||{}).style.display;
  out.stackHiddenInSp=(document.getElementById('gearStackCfg')||{}).style.display;
  out.spSleeve=(function(){var b=document.getElementById('edPlateBar');
    return b.querySelectorAll('.pv-sleeve').length;})();
  out.spNoSleeve=document.getElementById('edPlateBar').classList.contains('no-sleeve');
  out.spCellsEdit=(document.getElementById('edPlateBar').innerHTML.match(/class="gz-unit"/g)||[]).length;
  out.unitInShown=document.getElementById('edSpUnit').value;
  setGearUnitKg(-1);  out.unitAfterBad=d.exercises[1].gear.unitKg;
  setGearCount(0);    out.countAfterBad=d.exercises[1].gear.count;
  setGearLabel('');   out.labelAfterBad=d.exercises[1].gear.label;
  /* 手填覆盖 + 杠铃对照（两张配置行都藏） */
  out.manEff=effectiveLoad(d.exercises[2]);
  out.manStrip=gearStripText(gearViewOf(d.exercises[2]));
  openEditor(3);
  out.stackHiddenInBar=(document.getElementById('gearStackCfg')||{}).style.display;
  out.spHiddenInBar=(document.getElementById('gearSpecialCfg')||{}).style.display;
  closeAllSheets();
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;


/* ---------------- G10：节点⑫ 日程→场地引用 + equip→kind 推断的设置页修正 ----------------
   临时场地 gymX 只有 20/10 片 ⇒ 杠铃步长 2×10=20，与 legacy 的 0.5 拉开一个可判的差。
   四条回落腿钉「指针没设/指到不存在的场地 ⇒ 一律当前激活场地，绝不崩成 0」；
   setGearGuess 只写器械资料 record.kind（gearOf 单轨认它），非法 kind 不落残条目。 */
const G10 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  state.venues.gymX={id:'gymX',name:'GymX',kind:'gym',
    inventory:{bar_kg:20,collar_on:false,collar_pair_kg:5,
               plates:{'20':null,'10':null},dumbbells:null}};
  function E(gear,src){
    var e={mv:'W1_A_GEARV_BB10',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,gear:gear};
    if(src) e.gearSource=src;
    return e;
  }
  var gB={kind:'barbell',barKg:20};
  out.stepLocalDay=stepOf(E(Object.assign({},gB,{dayVenueId:'gymX',defVenueId:'gymX'}),'local'));
  out.stepPlanDef=stepOf(E(Object.assign({},gB,{defVenueId:'gymX'}),'plan'));
  out.stepPlanNone=stepOf(E(Object.assign({},gB),'plan'));
  out.stepLocalNoDay=stepOf(E(Object.assign({},gB,{defVenueId:'gymX'}),'local'));
  out.stepUnknownVenue=stepOf(E(Object.assign({},gB,{dayVenueId:'nope'}),'local'));
  var eUntouched=E(Object.assign({},gB,{dayVenueId:'gymX'}),'local');
  out.loadUntouched=eUntouched.load===100;
  /* 逐 mv 修正：器械资料 record.kind 写入 + gearOf 认得；非法 kind 不留残 */
  setGearGuess('G10_GUESS','dumbbell');
  out.defKind=(gearRecordOf({mv:'G10_GUESS'})||{}).kind;
  out.guessKind=gearOf({mv:'G10_GUESS'}).kind;
  setGearGuess('G10_BAD','nope');
  out.badRejected=!gearRecordOf({mv:'G10_BAD'});
  /* 设置页推断清单：真 mv 行、六 chip、点一下来源翻「已修正」 */
  renderEnvSheet();
  var items=[].slice.call(document.querySelectorAll('#gearGuessRow .gg-item'));
  out.items=items.length;
  out.chips0=items.length?items[0].querySelectorAll('.gg-chip').length:-1;
  out.kinds=GEAR_SCHEMA.kinds.length;
  if(items.length){
    var mv0=_ggMvList[0];
    setGearGuessAt(0,'stack');
    out.stackApplied=(gearRecordOf({mv:mv0})||{}).kind==='stack';
    out.srcFixed=/已修正|set/.test(document.querySelector('#gearGuessRow .gg-item .gg-src').textContent);
  }
  closeAllSheets();
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G11：中文动作名定向 + 首页六类形状语言 ----------------
   gearKindGuess 旧实现只读 equip 英文，门店里「设备名=Machine/器械」的动作会全兜成 barbell；
   这里钉住中文名先定向，并核对首页每类都发出自己的 glyph（不再是一根杠 + 一句话）。 */
const G11 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var bb={mv:'W1_A_G11BB',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  var pl={mv:'W1_A_G11PL',cat:'S.Squat',mode:'T1.Mod',load:60,reps:8,rpe:8,
          gear:{kind:'plate',posts:2,variant:'standard',baseKg:0}};
  var sm={mv:'W1_A_G11SM',cat:'S.Squat',mode:'T1.Mod',load:80,reps:8,rpe:8,
          gear:{kind:'plate',posts:4,variant:'smith',baseKg:20}};
  var st={mv:'W1_A_G11ST',cat:'S.Squat',mode:'T1.Mod',load:60,reps:8,rpe:8,
          gear:{kind:'stack',stacks:1,variant:'cable',stackPins:[6]}};
  var recG=gearRecordAt(resolveVenueId(st),st.mv,true);
  recG.kind='stack';
  recG.stack={v:1,ladders:[{v:1,levels:[0,5,10,15,20,25,30,35,40,45,50,55],
                           updatedAt:'2026-01-01T00:00:00.000Z'}]};
  var db={mv:'W1_A_G11DB',cat:'S.Squat',mode:'T1.Mod',load:48,reps:8,rpe:8,
          gear:{kind:'dumbbell',sides:2,incrementKg:2.5}};
  var bw={mv:'W1_A_G11BW',cat:'S.Squat',mode:'T1.Mod',load:0,reps:8,rpe:8,
          gear:{kind:'bw',lever:1}};
  var sp={mv:'W1_A_G11SP',cat:'S.Squat',mode:'T1.Mod',load:0,reps:8,rpe:8,
          gear:{kind:'special',label:'壶铃',unitKg:16,count:2}};
  d.exercises=[bb,pl,sm,st,db,bw,sp];
  /* 杠铃条的片叠取决于场地库存：先把常用片备齐，否则「没库存＝空杠」会让形状断言随本机状态漂。 */
  if(typeof plateOn==='function'){
    [25,20,15,10,5,2.5,1.25].forEach(function(k){ if(!plateOn(k)) togglePlateKg(k); });
  }
  renderExercises();
  function art(i){ return document.querySelectorAll('#exList article.ex')[i]; }
  function html(i){ return art(i)?art(i).innerHTML:''; }
  function k(i){ var s=art(i)&&art(i).querySelector('.plate-strip'); return s?s.getAttribute('data-k'):''; }
  function horn(i){ return art(i)?art(i).querySelectorAll('.plate-strip [data-gz="horn"]').length:0; }
  out.kinds=[k(0),k(1),k(2),k(3),k(4),k(5),k(6)].join(',');
  out.plHorns=horn(1); out.smHorns=horn(2);
  out.bb=html(0); out.pl=html(1); out.sm=html(2); out.st=html(3);
  out.db=html(4); out.bw=html(5); out.sp=html(6);
  out.h1=gearKindGuess('插片高位下拉');
  out.h2=gearKindGuess('挂片跪姿单腿弯举');
  out.h3=gearKindGuess('坐姿器械髋外展');
  out.h4=gearKindGuess('杠铃划船');
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G14：逐机档位表（允许非等差）+ 跨动作隔离 ----------------
   新模型每一台插片机各自一把档位表，动作只存销位。这里同时钉三件事：
   ① 绝对 kg 表原样入库（2.5 与 3.5 混排不是等差）；② 两台机器的表互不覆盖、销位互不串；
   ③ 坏表（降序/越界）只让 solver 退回 exact=false，绝不改写用户存的原文。 */
const G14 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var A={mv:'W1_A_GEARV_LAD_A',cat:'S.Squat',mode:'T1.Mod',load:25,reps:5,rpe:8,
         gear:{kind:'stack',stacks:1,variant:'standard'}};
  var B={mv:'W1_A_GEARV_LAD_B',cat:'S.Squat',mode:'T1.Mod',load:20,reps:5,rpe:8,
         gear:{kind:'stack',stacks:1,variant:'standard'}};
  d.exercises=[A,B];
  stackLadderWrite(A,0,[20,22.5,25,28.5,32,35.5,39]);
  stackLadderWrite(B,0,[10,15,20,25,30]);
  savePrefsOnly();
  var vA=solveLoad(A), vB=solveLoad(B);
  out.a={ach:vA.achievedKg,exact:vA.exact,step:vA.stepKg,pin:vA.recipe.stacks[0].pin,
         levels:vA.recipe.stacks[0].levels.join(',')};
  out.b={ach:vB.achievedKg,exact:vB.exact,step:vB.stepKg,pin:vB.recipe.stacks[0].pin,
         levels:vB.recipe.stacks[0].levels.join(',')};
  out.nextA=nextReachable(A,28.5,1,1);
  out.nextB=nextReachable(B,10,1,1);
  /* 只在 A 上点销位：A 的实配变 32，B 的销位与实配一字不动 */
  writeExercisePins(A,[4]);
  var vA2=solveLoad(A);
  out.aPin={load:vA2.achievedKg,pins:A.gear.stackPins.join(','),
            bPins:(B.gear&&B.gear.stackPins)?B.gear.stackPins.join(','):'none',
            bAch:solveLoad(B).achievedKg};
  var ra=gearRecordOf(A), rb=gearRecordOf(B);
  out.recA=(ra&&ra.stack&&ra.stack.ladders[0].levels||[]).join(',');
  out.recB=(rb&&rb.stack&&rb.stack.ladders[0].levels||[]).join(',');
  /* 坏表（降序）：不改原文、solver 明确 exact=false + 警告 */
  stackLadderWrite(B,0,[25,20,15]);
  var vBbad=solveLoad(B);
  out.bad={ok:stackLadderOf(B).ok,exact:vBbad.exact,ach:vBbad.achievedKg,
           warn:vBbad.warnings.join(' '),
           kept:(gearRecordOf(B).stack.ladders[0].levels||[]).join(',')};
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G15：器械图形的可判性质（销位单调 / 零文字 / 挂片余量 / 尺寸 / 窗口） ----------------
   图形重画后旧类名全部退役，这里只盯新钩子：data-gz / data-pin / data-engaged / data-mode。
   每条都走真渲染（renderExercises / openEditor），出段 restore 到 G0 快照，由 G0.2 复核零副作用。 */
const G15 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var LV9=[20,22.5,25,27.5,30,32.5,35,37.5,40];
  var LV20=[];
  for(var k=0;k<20;k++) LV20.push(20+k*2.5);
  function mkStack(mv,pin,levels){
    var e={mv:mv,cat:'S.Squat',mode:'T1.Mod',load:20,reps:5,rpe:8,
           gear:{kind:'stack',stacks:1,variant:'standard',stackPins:[pin]}};
    var rec=gearRecordAt(resolveVenueId(e),e.mv,true);
    rec.kind='stack';
    rec.stack={v:1,ladders:[{v:1,levels:levels,updatedAt:'2026-01-01T00:00:00.000Z'}]};
    return e;
  }
  function cardSvg(i,sel){
    var a=document.querySelectorAll('#exList article.ex')[i];
    return a?a.querySelector('.plate-strip '+sel):null;
  }
  /* 15.1 销位单调：9 档、pin 0..8，卡上 data-pin 与实心块数必须严格递增。 */
  var st=mkStack('W1_A_GEARV_PIN15',0,LV9);
  d.exercises=[st];
  openEditor(0);
  out.mono=[];
  for(var p=0;p<9;p++){
    setGearStackPin(0,p); renderExercises();
    var sv=cardSvg(0,'[data-gz="stack"]');
    out.mono.push(sv?{pin:+sv.getAttribute('data-pin'),
      eng:sv.querySelectorAll('[data-engaged="1"]').length}:(null));
  }
  /* 15.2 六类条内零文字：每个 .gz-svg 无 textContent / 无 <text>，特殊单元同理。 */
  var bb={mv:'W1_A_GEARV_TX15_BB',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  var pl={mv:'W1_A_GEARV_TX15_PL',cat:'S.Squat',mode:'T1.Mod',load:60,reps:8,rpe:8,
          gear:{kind:'plate',posts:2,variant:'standard',baseKg:20}};
  var st2=mkStack('W1_A_GEARV_TX15_ST',4,LV9);
  var db={mv:'W1_A_GEARV_TX15_DB',cat:'S.Squat',mode:'T1.Mod',load:24,reps:8,rpe:8,
          gear:{kind:'dumbbell',sides:2,incrementKg:2.5}};
  var bw={mv:'W1_A_GEARV_TX15_BW',cat:'S.Squat',mode:'T1.Mod',load:0,reps:8,rpe:8,
          gear:{kind:'bw',lever:1}};
  var sp={mv:'W1_A_GEARV_TX15_SP',cat:'S.Squat',mode:'T1.Mod',load:0,reps:8,rpe:8,
          gear:{kind:'special',label:'壶铃',unitKg:16,count:3}};
  d.exercises=[bb,pl,st2,db,bw,sp];
  renderExercises();
  out.tx={svg:0,text:0,poly:0,special:0,sBad:0};
  [].slice.call(document.querySelectorAll('#exList article.ex .plate-strip')).forEach(function(s){
    var svgs=s.querySelectorAll('.gz-svg');
    out.tx.svg+=svgs.length;
    svgs.forEach(function(v){
      if(v.textContent!=='') out.tx.text++;
      if(v.querySelectorAll('text').length) out.tx.poly++;
    });
    var spn=s.querySelectorAll('.gz-special');
    out.tx.special+=spn.length;
    spn.forEach(function(x){ if(x.textContent!=='') out.tx.sBad++; });
  });
  /* 15.3 挂片空轴/余量：低于基数与粗库存余数都要画出 ghost，卡片不写「无片」。 */
  state.venues.gymC={id:'gymC',name:'GymC',kind:'gym',
    inventory:{bar_kg:20,collar_on:false,collar_pair_kg:5,plates:{'20':null,'10':null},dumbbells:null}};
  var low={mv:'W1_A_GEARV_GH15_LOW',cat:'S.Squat',mode:'T1.Mod',load:12,reps:8,rpe:8,
           gear:{kind:'plate',posts:2,variant:'standard',baseKg:20}};
  var coarse={mv:'W1_A_GEARV_GH15_C',cat:'S.Squat',mode:'T1.Mod',load:101,reps:8,rpe:8,
              gearSource:'local',gear:{kind:'plate',posts:2,variant:'standard',baseKg:20,dayVenueId:'gymC'}};
  d.exercises=[low,coarse];
  renderExercises();
  function plateInfo(i){
    var a=document.querySelectorAll('#exList article.ex')[i];
    var sv=a?a.querySelector('.plate-strip [data-gz="plate"]'):null;
    return {ghost:sv?sv.querySelectorAll('[data-gz="ghost"]').length:0,
            txt:a?a.querySelector('.plate-strip').textContent:''};
  }
  out.ghostLow=plateInfo(0); out.ghostCoarse=plateInfo(1);
  /* 15.4 挂片尺寸：大图 48px，小图 26px（不是 40px）。 */
  d.exercises=[coarse];
  renderExercises();
  var small=cardSvg(0,'[data-gz="plate"]');
  out.smallH=small?small.style.height:'';
  openEditor(0);
  var ed=document.getElementById('edPlateBar');
  var big=ed?ed.querySelector('[data-gz="plate"]'):null;
  out.bigH=big?big.style.height:'';
  closeAllSheets();
  /* 15.5 插片窗口：20 档、pin 15 → 只画 14 块，窗口 lo=6..19，engaged=10。 */
  var st3=mkStack('W1_A_GEARV_WIN15',15,LV20);
  d.exercises=[st3];
  openEditor(0); setGearStackPin(0,15); renderExercises();
  var wsv=cardSvg(0,'[data-gz="stack"]');
  out.win=null;
  if(wsv){
    var idxs=[].slice.call(wsv.querySelectorAll('.gz-block')).map(function(b){return +b.getAttribute('data-idx');});
    out.win={pin:+wsv.getAttribute('data-pin'),blocks:idxs.length,
      min:Math.min.apply(null,idxs),max:Math.max.apply(null,idxs),
      eng:wsv.querySelectorAll('[data-engaged="1"]').length,
      hasPin:!!wsv.querySelector('[data-gz="pin"]')};
  }
  closeAllSheets();
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

/* ---------------- G16：器械身份分层（品牌 / 系列 / 名称） ----------------
   部件表从契约派生：插片/自重 → machine；挂片 → machine+plates；杠铃 → bar+plates+support；
   哑铃 → dumbbell(+bench 可选)。身份落在 record.identity，不写回动作行；
   两台机器各存各的，换动作不串味。 */
const G16 = `(function(){
  var out={};
  var d=day(), savedEx=d.exercises;
  var bb={mv:'W1_A_GEARV_ID_BB',cat:'S.Squat',mode:'T1.Mod',load:100,reps:5,rpe:8,
          gear:{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5}};
  var db={mv:'W1_A_GEARV_ID_DB',cat:'S.Squat',mode:'T1.Mod',load:24,reps:5,rpe:8,
          gear:{kind:'dumbbell',sides:2,incrementKg:2.5}};
  var st={mv:'W1_A_GEARV_ID_ST',cat:'S.Squat',mode:'T1.Mod',load:40,reps:5,rpe:8,
          gear:{kind:'stack',stacks:1,variant:'cable',stackPins:[4]}};
  var pl={mv:'W1_A_GEARV_ID_PL',cat:'S.Squat',mode:'T1.Mod',load:60,reps:5,rpe:8,
          gear:{kind:'plate',posts:2,variant:'standard',baseKg:0}};
  d.exercises=[bb,db,st,pl];
  function ids(kind){ return gearIdentityParts(kind).map(function(p){ return p.id; }).join(','); }
  out.parts={bb:ids('barbell'),db:ids('dumbbell'),st:ids('stack'),pl:ids('plate')};
  /* 杠铃三段各自品牌/系列/名称，走身份面板保存 */
  openEditor(0); openIdentitySheet();
  identityDraftSet('bar','brand','Eleiko');
  identityDraftSet('bar','series','Powerlifting');
  identityDraftSet('bar','name','Öppen 20kg');
  identityDraftSet('plates','brand','Rogue');
  identityDraftSet('plates','series','Calibrated');
  identityDraftSet('plates','name','训练片');
  identityDraftSet('support','brand','SBD');
  identityDraftSet('support','name','比赛架');
  identityDraftSet('support','type','combo');
  identitySave();
  var rb=gearRecordOf(bb);
  out.bbSaved=JSON.stringify(rb.identity);
  out.bbSum=gearIdentitySummary(bb).text;
  out.bbInGear=!!(bb.gear&&bb.gear.identity);
  /* 哑铃只写一段；不填凳就不留 bench 残条目 */
  openEditor(1); openIdentitySheet();
  identityDraftSet('dumbbell','brand','Bowflex');
  identityDraftSet('dumbbell','name','552');
  identitySave();
  var rd=gearRecordOf(db);
  out.dbSaved=JSON.stringify(rd.identity);
  out.dbSum=gearIdentitySummary(db).text;
  out.dbBench=!!(rd.identity&&rd.identity.bench);
  /* 插片机器登记后：只有它自己的摘要变，杠铃仍只有自己的三段 */
  openEditor(2); openIdentitySheet();
  identityDraftSet('machine','brand','Life Fitness');
  identityDraftSet('machine','name','Cable Column');
  identitySave();
  var rs=gearRecordOf(st);
  out.stRecord=JSON.stringify(rs.identity);
  out.stSum=gearIdentitySummary(st).text;
  out.bbAfter=gearIdentitySummary(bb).text;
  closeAllSheets();
  d.exercises=savedEx;
  window.__gearv.restore();
  return JSON.stringify(out);
})()`;

async function main() {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'rpl-gearv-'));
  chrome = spawn(CHROME, ['--headless=new', '--remote-debugging-port=' + PORT,
    '--user-data-dir=' + path.join(tmp, 'profile'), '--window-size=412,892', '--no-first-run',
    '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 900));
  let wsUrl = null;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    try {
      const list = await fetch('http://127.0.0.1:' + PORT + '/json').then(r => r.json());
      const page = list.find(x => x.type === 'page');
      if (page) wsUrl = page.webSocketDebuggerUrl;
    } catch (e) { await new Promise(r => setTimeout(r, 200)); }
  }
  if (!wsUrl) { chrome.kill(); throw new Error('起不了 headless Chrome'); }
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  const id = { v: 0 };
  await send(ws, id.v, 'Page.enable');
  await send(ws, id.v, 'Runtime.enable');
  await send(ws, id.v, 'Page.navigate', { url: FILE });
  for (let i = 0; i < 60; i++) {
    const ready = await send(ws, id.v, 'Runtime.evaluate',
      { expression: '!!(state&&GEAR_SCHEMA&&typeof solveLoad==="function"&&typeof gearViewOf==="function")',
        returnByValue: true })
      .then(r => r.result && r.result.value).catch(() => false);
    if (ready) break;
    await new Promise(r => setTimeout(r, 300));
  }
  const SECT = { s: 'bootstrap' };
  const call = (probe, ...args) =>
    evalIn(ws, id, probe + '(' + args.map(a => JSON.stringify(a)).join(',') + ')');
  try {
    /* ---------------- G0：入口与快照 ---------------- */
    SECT.s = 'G0';
    await evalIn(ws, id, HELP);
    const entry = await evalIn(ws, id, `(function(){
      var f=['solveLoad','gearViewOf','gearOf','stepKgOf','stepOf','effectiveLoad','platesPerSide',
             'gearStripText','renderGearChips','fmtStep','quickLoad','stepLoad','setGearBarKg',
             'toggleGearCollars','warmups','prescriptionOf','computePosterData','logT1MainE1rm',
             'renderExercises','refreshConsole','venueInv','clone','mround',
             'setGearStacks','setGearStackField','toggleGearCable','renderGearStackCfg',
             'renderGearSpecialCfg','setGearGuess','resolveVenueId'];
      return JSON.stringify({miss:f.filter(function(n){try{return typeof eval(n)!=='function';}catch(e){return true;}}),
        kinds:GEAR_KINDS.slice(),stamp:SCHEMA_STAMP});
    })()`);
    const ent = JSON.parse(entry);
    T('G0.1', 'Resolver 入口点名齐（' + (30 - ent.miss.length) + '/30）且六类词表在位',
      ent.miss.length === 0 && ent.kinds.length === 6,
      '缺函数 ' + (ent.miss.join(',') || '无') + ' / kinds ' + ent.kinds.join(','));
    await evalIn(ws, id, '__gearv.save()');
    var snap0 = await evalIn(ws, id, '__gearv.hash()');

    /* ---------------- G1 ---------------- */
    SECT.s = 'G1';
    const g1 = JSON.parse(await evalIn(ws, id, G1));
    const bb = g1.bb;
    T('G1.1', '杠铃 100kg / 20kg 杆 / 开赛扣：逐侧 37.5kg、实配 100kg、exact、无警告',
      bb.recipe.perSide === 37.5 && bb.achieved === 100 && bb.exact === true &&
      bb.recipe.collars === true && bb.warn.length === 0 && bb.recipe.plates.length > 0,
      'perSide ' + bb.recipe.perSide + ' / achieved ' + bb.achieved + ' / 片 ' +
      bb.recipe.plates.map(p => p.kg).join('+') + ' / warn ' + JSON.stringify(bb.warn));
    T('G1.2', '杠铃 105.3kg 不可达：exact=false 且说明带余数文案',
      g1.bbRem.exact === false && /余|Remainder/.test(g1.bbRem.warn.join(' ') + (g1.bbRem.recipe.note || '')),
      'exact ' + g1.bbRem.exact + ' / rem ' + g1.bbRem.recipe.remainder + ' / ' + JSON.stringify(g1.bbRem.warn));
    T('G1.3', '杠铃 10kg 低于空杆+赛扣：只出提示、不出片、说明含「赛扣」',
      g1.bbLow.exact === false && g1.bbLow.recipe.plates.length === 0 &&
      /赛扣|collars/i.test(g1.bbLow.warn.join(' ') + ' ' + (g1.bbLow.recipe.note || '')),
      JSON.stringify(g1.bbLow.warn) + ' / 片 ' + g1.bbLow.recipe.plates.length);
    T('G1.4', '挂片 posts=2 / base=20 / 100kg：每位 40kg、实配 100kg、exact',
      g1.pl.recipe.posts === 2 && g1.pl.recipe.perPost === 40 && g1.pl.achieved === 100 && g1.pl.exact === true,
      'perPost ' + g1.pl.recipe.perPost + ' / achieved ' + g1.pl.achieved + ' / rem ' + g1.pl.recipe.remainder);
    T('G1.5', '挂片 101kg 且最小片 1.25：每位余 0.5kg、exact=false、有警告',
      g1.plRem.recipe.remainder === 0.5 && g1.plRem.exact === false && g1.plRem.warn.length > 0,
      'rem ' + g1.plRem.recipe.remainder + ' / warn ' + JSON.stringify(g1.plRem.warn));
    T('G1.6', '插片双栈按档位表：A 栈第 8 档 40kg + B 栈第 4 档 40kg = 实配 80kg、步长 gcd=2.5',
      g1.st.achieved === 80 && g1.st.recipe.count === 2 && g1.st.step === 2.5,
      'achieved ' + g1.st.achieved + ' / step ' + g1.st.step + ' / ' + JSON.stringify(g1.st.recipe.stacks));
    T('G1.7', '插片目标 85 与插销实际 80 不符：警告里带实际值',
      g1.stOff.warn.length > 0 && /80/.test(g1.stOff.warn.join(' ')),
      JSON.stringify(g1.stOff.warn));
    T('G1.8', '哑铃无库存档：单边 24 → effective 48（双边）、recipe.sideKg=24、exact',
      g1.db.eff === 48 && g1.db.recipe.sideKg === 24 && g1.db.recipe.sides === 2 && g1.db.exact === true,
      'eff ' + g1.db.eff + ' / sideKg ' + g1.db.recipe.sideKg + ' / exact ' + g1.db.exact);
    T('G1.9', '哑铃有库存档 [20,22,25,30]：吸附到 25、实配 50、出警告，effective 仍按输入 48',
      g1.dbSnap.recipe.snapKg === 25 && g1.dbSnap.achieved === 50 &&
      g1.dbSnap.exact === false && g1.dbSnap.warn.length > 0 && g1.dbSnap.eff === 48,
      'snap ' + g1.dbSnap.recipe.snapKg + ' / achieved ' + g1.dbSnap.achieved + ' / eff ' + g1.dbSnap.eff);
    T('G1.10', '自重三态（BW 87.5 / lever 1）：+25→112.5、0→87.5、−30→57.5，mode 分流正确',
      g1.bwPlus.eff === 112.5 && g1.bwPure.eff === 87.5 && g1.bwAsst.eff === 57.5 &&
      g1.bwPlus.recipe.mode === 'plus' && g1.bwPure.recipe.mode === 'pure' && g1.bwAsst.recipe.mode === 'assist',
      [g1.bwPlus.eff, g1.bwPure.eff, g1.bwAsst.eff].join('/') + ' · ' +
      [g1.bwPlus.recipe.mode, g1.bwPure.recipe.mode, g1.bwAsst.recipe.mode].join('/'));
    T('G1.11', '辅助 −100 超过 BW×lever：净负荷钳 0 且警告，不许出负数',
      g1.bwOver.eff === 0 && g1.bwOver.warn.length > 0,
      'eff ' + g1.bwOver.eff + ' / warn ' + JSON.stringify(g1.bwOver.warn));
    T('G1.12', 'BW 缺失（两处都拿不到）：必出「先填当日体重 / SET A BW FIRST」警告，不静默按 0 记有效',
      g1.bwMiss.warn.length > 0 && /体重|BW FIRST/i.test(g1.bwMiss.warn.join(' ')),
      JSON.stringify(g1.bwMiss.warn));
    T('G1.13', '特殊 24kg×2 = 48kg，effective 与 achieved 同值',
      g1.sp.eff === 48 && g1.sp.achieved === 48 && g1.sp.recipe.count === 2,
      'eff ' + g1.sp.eff + ' / achieved ' + g1.sp.achieved);
    T('G1.14', '特殊 manualKg=50 覆盖总重并出警告',
      g1.spMan.achieved === 50 && g1.spMan.eff === 50 && g1.spMan.warn.length > 0,
      'achieved ' + g1.spMan.achieved + ' / warn ' + JSON.stringify(g1.spMan.warn));
    const wantStep = {
      bbFine: 2 * 0.25, bbCoarse: 2 * 2.5, bbEmpty: RULE.step_rule.no_stock_fallback,
      plate: 2 * 0.25, plate4: 4 * 1.25,
      dumbbell: 2.5 * 2, stack: gcdRef([2.5, 5]), bw: 0.25, special: 24
    };
    const stepBad = Object.keys(wantStep).filter(k => Math.abs(g1.steps[k] - wantStep[k]) > 1e-9);
    T('G1.15', '六类步长按契约公式独立重算（含 0.25→0.5、无 1.25→5、posts×min、gcd、unitKg）',
      stepBad.length === 0,
      stepBad.length ? stepBad.map(k => k + ' 页面 ' + g1.steps[k] + ' ≠ 参照 ' + wantStep[k]).join(' ; ')
        : Object.keys(wantStep).map(k => k + '=' + g1.steps[k]).join(' '));
    T('G1.16', '库存清空时步长回落 no_stock_fallback（' + g1.fallback + '），不是 0 也不是凭空造片',
      g1.steps.bbEmpty === g1.fallback && g1.steps.bbEmpty > 0,
      'bbEmpty ' + g1.steps.bbEmpty + ' / fallback ' + g1.fallback);
    T('G1.17', '插片未登记档位表：exact=false、警告点名「未登记配重档位表」、实配仍等于输入（不假装等差）',
      g1.stNo.exact === false && g1.stNo.warn.length > 0 &&
      /未登记配重档位表/.test(g1.stNo.warn.join(' ')) && g1.stNo.achieved === 80,
      'exact ' + g1.stNo.exact + ' / achieved ' + g1.stNo.achieved + ' / ' + JSON.stringify(g1.stNo.warn));
    T('G1.18', '非等差档位表（前段 2.5、后段 3.5）逐档参与求解：32kg 命中、步长取最小差 2.5',
      g1.stMix.exact === true && g1.stMix.achieved === 32 && g1.stMix.step === 2.5 &&
      g1.stMix.recipe.stacks[0].levels.join(',') === '20,22.5,25,28.5,32,35.5,39',
      'achieved ' + g1.stMix.achieved + ' / step ' + g1.stMix.step + ' / levels ' +
      g1.stMix.recipe.stacks[0].levels.join(','));

    /* ---------------- G2 ---------------- */
    SECT.s = 'G2';
    const g2 = JSON.parse(await evalIn(ws, id, G2));
    const setBad = g2.rows.filter(r => r.sets !== r.of);
    T('G2.1', '现行 prescriptionOf：8 个模式的 sets 恒等于 setsOf(mode)（v0.32⑥ 前语义，届时替换本批）',
      setBad.length === 0 && g2.rows.length === 8,
      setBad.length ? setBad.map(r => r.mode + ':' + r.sets + '≠' + r.of).join(' ; ') : '8 模式全等');
    const byMode = {}; g2.rows.forEach(r => { byMode[r.mode] = r; });
    T('G2.2', 'Top 系处方是逐组串「1×N + …」而不是 sets×reps 的猜测',
      /^1×.*\+/.test(byMode['Top.Set'].rx) && /^1×.*\+/.test(byMode['Top.Single'].rx) &&
      byMode['Top.Test'].rx === '1×1',
      'Top.Set ' + byMode['Top.Set'].rx + ' / Top.Single ' + byMode['Top.Single'].rx +
      ' / Top.Test ' + byMode['Top.Test'].rx);
    T('G2.3', '标签分流：RTS→AUTOREG、.DL→DELOAD、Top.Set→TOP+BACKOFF',
      byMode['RTS.Mod'].tag === 'AUTOREG' && byMode['T1.Mod.DL'].tag === 'DELOAD' &&
      byMode['Top.Set'].tag === 'TOP+BACKOFF',
      g2.rows.map(r => r.mode + '=' + r.tag).join(' '));
    T('G2.4', 'BackOff 三档 5/10/15 且默认 10%；Top.Set 的 backoff 就是 0.10',
      JSON.stringify(g2.backoffOpts) === JSON.stringify([5, 10, 15]) && g2.backoffDefault === 10 &&
      Math.abs(byMode['Top.Set'].backoff - 0.10) < 1e-9,
      'opts ' + g2.backoffOpts.join('/') + ' / default ' + g2.backoffDefault +
      ' / Top.Set ' + byMode['Top.Set'].backoff);

    /* ---------------- G3 ---------------- */
    SECT.s = 'G3';
    const g3 = JSON.parse(await evalIn(ws, id, G3));
    T('G3.1', '首页卡片：杠铃行画 .pb 片条与赛扣，stack 行只有口径摘要、不出现杠铃片 DOM',
      g3.nArt === 2 && g3.bbHtml.indexOf('class="pb"') >= 0 &&
      g3.bbHtml.indexOf('pv-clamp') >= 0 && g3.stHtml.indexOf('class="pb"') < 0 &&
      g3.stHtml.indexOf('pv-clamp') < 0,
      '卡片 ' + g3.nArt + ' / 杠铃 pb ' + (g3.bbHtml.indexOf('class="pb"') >= 0) +
      ' / stack pb ' + (g3.stHtml.indexOf('class="pb"') >= 0));
    T('G3.2', '首页步进按钮文案由 fmtStep(stepOf(e)) 现写（无 2.5 字面量）',
      g3.cardBtns.length === 2 && g3.cardBtns[0] === '+' + g3.cardStep &&
      g3.cardBtns[1] === '−' + g3.cardStep,
      JSON.stringify(g3.cardBtns) + ' / 期望 ±' + g3.cardStep);
    T('G3.3', '真点 quickLoad(+1/−1)：载荷恰好 ±step，往返回原值',
      Math.abs(g3.quick.plus - g3.quick.before - g3.quick.step) < 1e-9 &&
      Math.abs(g3.quick.back - g3.quick.before) < 1e-9,
      JSON.stringify(g3.quick));
    T('G3.4', '编辑器 #edBar 取动作级 gearOf(ex).barKg，不是场地默认',
      +g3.edBar === g3.gearBar,
      'edBar ' + g3.edBar + ' / gearOf ' + g3.gearBar);
    T('G3.5', '编辑器四颗步进按钮文案 = −2·step / −step / +step / +2·step',
      JSON.stringify(g3.edBtns) === JSON.stringify([
        '−' + g3.edStep[0], '−' + g3.edStep[1], '+' + g3.edStep[1], '+' + g3.edStep[0]]),
      JSON.stringify(g3.edBtns) + ' / step ' + g3.edStep.join(','));
    T('G3.6', 'setGearBarKg(15)：动作行与器械资料 params 都变 15，场地默认 bar_kg 一字不动',
      g3.bar15.eBar === 15 && g3.bar15.def === 15 &&
      g3.bar15.venueAfter === g3.bar15.venueBefore,
      JSON.stringify(g3.bar15));
    T('G3.7', 'toggleGearCollars 只翻 e.gear.collarOn（取反成立）',
      g3.collar.after === !g3.collar.before,
      JSON.stringify(g3.collar));
    T('G3.8', '六类 chip 数 == GEAR_SCHEMA.kinds 长度（不手抄六键）',
      g3.chips === g3.kinds && g3.kinds === 6,
      'chips ' + g3.chips + ' / kinds ' + g3.kinds);
    T('G3.9', '非杠铃编辑器：#plateCfgRow 隐藏、#edPlateBar 不画杆（无 .pv-sleeve）',
      g3.nonBar.display === 'none' && g3.nonBar.sleeve === 0 && g3.nonBar.hasBar === true,
      JSON.stringify(g3.nonBar));
    T('G3.10', 'warmups 双形态：bw 恒回自重三连（w 全 0）；数字路径仍从 barKg() 起步',
      g3.warmBw.length === 3 && g3.warmBw.every(w => w === 0) &&
      g3.warmNumStart === g3.barKg,
      'bw ' + JSON.stringify(g3.warmBw) + ' / 数字首档 ' + g3.warmNumStart + ' / barKg ' + g3.barKg);
    T('G3.11', 'e1RM 落账吃 Effective：纯自重行 e1rm = e1rm(BW×lever,…) 而不是 0',
      g3.e1.n === 1 && g3.e1.eff > 0 && Math.abs(g3.e1.got - g3.e1.want) < 1e-9 && g3.e1.got > 0,
      JSON.stringify(g3.e1));
    T('G3.12', '海报周吨位吃 Effective：账本只剩一条纯自重行（load=0）时仍为正',
      g3.posterTon > 0, 'weekTonnage ' + g3.posterTon);

    /* ---------------- G4 ---------------- */
    SECT.s = 'G4';
    const g4 = JSON.parse(await call(G4, BARS, TARGETS));
    const sumBad = g4.rows.filter(r => Math.abs(r.sum - r.per) > 6e-4);
    T('G4.1', '配片守恒：' + g4.rows.length + ' 组（7 杆重 × 20 目标 × 赛扣开关）片重和+余数 == 逐侧需求',
      sumBad.length === 0,
      sumBad.length ? sumBad.length + ' 组不平 → ' + sumBad.slice(0, 3).map(r =>
        r.bar + '/' + r.t + '：' + r.sum + ' ≠ ' + r.per).join(' ; ') : '0 组不平');
    const blocked = r => r.c && r.t < r.bar + g4.collarPair;
    const exBad = g4.rows.filter(r => !blocked(r) && r.exact !== (r.rem < 0.0005));
    T('G4.2', 'exact 与「余数 < 0.0005」同判（赛扣门槛分支单独排除，它本就不可配）',
      exBad.length === 0,
      exBad.length ? exBad.slice(0, 3).map(r => r.bar + '/' + r.t + ' exact=' + r.exact + ' rem=' + r.rem).join(' ; ')
        : g4.rows.filter(blocked).length + ' 组命中赛扣门槛分支');
    const monoBad = g4.rows.filter(r => {
      // 片序列结构由页面返回，这里只验「不可配时不凭空造片」这一条独立性质
      return blocked(r) && r.n > 0;
    });
    T('G4.3', '总重不足以容纳赛扣时一片都不造（' + g4.rows.filter(blocked).length + ' 组）',
      monoBad.length === 0 && g4.rows.filter(blocked).length > 0,
      monoBad.length ? monoBad.slice(0, 3).map(r => r.bar + '/' + r.t + ' 造了 ' + r.n + ' 片').join(' ; ')
        : '0 组违例');

    /* ---------------- G5：v7 迁移语义 ---------------- */
    SECT.s = 'G5';
    const g5 = JSON.parse(await evalIn(ws, id, G5));
    T('G5.1', '迁移换算：纯自重 load=0 原样不动；净重 112.5→外载 25；哑铃标单边；报告计数对得上',
      g5.a.loads[0] === 0 && g5.a.conv[0] === null &&
      g5.a.loads[1] === 25 && g5.a.n2 === 1 && g5.a.db === 1 && g5.a.pend === 0,
      JSON.stringify(g5.a));
    T('G5.2', 'BW 缺失不猜：只标 gearPending 与 pending 报告，load 不动、不做 net2ext 换算',
      g5.b.load === 110 && g5.b.pending === true && g5.b.pendN === 1 && g5.b.n2 === 0,
      JSON.stringify(g5.b));
    T('G5.3', '派生指标回写有 ≥0.005 门槛：重算值相同就只盖章 deriveSame，不进备份也不覆写',
      g5.c.same === 1 && g5.c.changed === 0 && g5.c.bk === 0 && g5.c.e1 === g5.c.want,
      JSON.stringify(g5.c));

    /* ---------------- G6：§5 处方逐组 ---------------- */
    SECT.s = 'G6';
    const g6 = JSON.parse(await evalIn(ws, id, G6));
    T('G6.1', '处方 1×3 + 2×5@-10%：两段、Σsets=3、顶 1.0 退 0.9、tag TOP+BACKOFF、backoff 10%',
      g6.ts.fromRx && g6.ts.n === 2 && g6.ts.sets === 3 && g6.ts.tag === 'TOP+BACKOFF'
      && g6.ts.g.join('|') === '1x3@1|2x5@0.9' && Math.abs(g6.ts.backoff - 0.10) < 1e-6,
      JSON.stringify(g6.ts));
    T('G6.2', '处方 1×1 + 1×4@-10%：两段、Σsets=2、退阶段 reps 4 @0.9',
      g6.tp.fromRx && g6.tp.n === 2 && g6.tp.sets === 2 && g6.tp.g.join('|') === '1x1@1|1x4@0.9',
      JSON.stringify(g6.tp));
    T('G6.3', '处方 4×12+：单段、段尾裸「+」判为 AMRAP、rx 原样保留含 +',
      g6.am.fromRx && g6.am.n === 1 && g6.am.amrap && g6.am.sets === 4 && g6.am.rx === '4×12+',
      JSON.stringify(g6.am));
    T('G6.4', '处方 5×5：单段恒重组、非 AMRAP、sets 5',
      g6.st.fromRx && g6.st.n === 1 && !g6.st.amrap && g6.st.sets === 5 && g6.st.tag === 'STRAIGHT SETS',
      JSON.stringify(g6.st));
    T('G6.5', '非空坏原文：显式 invalid、原文照留、不换处方（不再静默回落 proto）',
      !g6.bad.fromRx && g6.bad.invalid === true && g6.bad.rx === '乱七八糟',
      JSON.stringify(g6.bad));
    T('G6.6', '空 rx：回落单组猜测、fromRx=false、绝不凭空造多段',
      !g6.empty.fromRx && g6.empty.n === 1,
      JSON.stringify(g6.empty));
    T('G6.9', '计划写法 1×3+2×3−5%（无空格 +、全角减号）：两段 Σsets=3、退阶 5%',
      g6.ds.fromRx && g6.ds.invalid === false && g6.ds.n === 2 && g6.ds.sets === 3
      && g6.ds.tag === 'TOP+BACKOFF' && Math.abs(g6.ds.backoff - 0.05) < 1e-6,
      JSON.stringify(g6.ds));
    T('G6.10', '计划写法 2×5 @60%：绝对强度按 0.60 计、单段 sets 2 reps 5',
      g6.ab.fromRx && g6.ab.n === 1 && g6.ab.sets === 2 && g6.ab.reps === 5
      && g6.ab.g[0] === '2x5@0.6', JSON.stringify(g6.ab));
    T('G6.11', '计划写法 3×2 / 2×15：单段组数与次数按原文（高次数不擅自判 AMRAP）',
      g6.b3.fromRx && g6.b3.sets === 3 && g6.b3.reps === 2 && !g6.b3.amrap
      && g6.r15.fromRx && g6.r15.sets === 2 && g6.r15.reps === 15 && !g6.r15.amrap,
      JSON.stringify(g6.b3) + ' / ' + JSON.stringify(g6.r15));
    T('G6.12', '计划写法 1×1 · 第 1 把：注释只解释用途、不改组次，原文照留',
      g6.cm.fromRx && g6.cm.sets === 1 && g6.cm.reps === 1 && g6.cm.rx === '1×1 · 第 1 把',
      JSON.stringify(g6.cm));
    T('G6.13', '中文段注写法 1×3 顶组 + 2×3 减 5% 补组：两段 Σsets=3、退阶 5%',
      g6.zh.fromRx && g6.zh.n === 2 && g6.zh.sets === 3 && g6.zh.tag === 'TOP+BACKOFF'
      && Math.abs(g6.zh.backoff - 0.05) < 1e-6, JSON.stringify(g6.zh));
    T('G6.14', 'sets 列驱动组数：计划 sets=3 压过 rx 拆出的 5，缺省时 setsOf 回 proto',
      g6.own.fromRx && g6.own.sets === 3 && g6.own.reps === 5
      && g6.so7 === 7 && g6.so0 > 0, JSON.stringify(g6.own) + ' so7=' + g6.so7 + ' so0=' + g6.so0);
    T('G6.7', '运行时真有一条种子 Top.Set 行走权威路径：rx 解析成功且 prescriptionOf.rx == 原 rx（旧污染已消除）',
      !!g6.live && g6.live.p.fromRx && g6.live.p.invalid === false
      && g6.live.p.rx === String(g6.live.rx).replace(/\s+/g, ' ').trim(),
      g6.live ? JSON.stringify(g6.live) : '没找到可解析的 Top.* 种子行');
    T('G6.8', 'BackOff 取整性质：140×0.9=126 不在 2.5 步长格上 → 吸附到最近可达 125，且 |target−achieved|=1 ≤ step',
      g6.boW === 125 && Math.abs(g6.boW % 2.5) < 1e-9 && g6.delta <= 2.5 && Math.abs(g6.delta - 1) < 1e-9,
      'boW ' + g6.boW + ' Δ ' + g6.delta);

    /* ---------------- G7：载荷格按器械口径显示 ---------------- */
    SECT.s = 'G7';
    const g7 = JSON.parse(await evalIn(ws, id, G7));
    T('G7.1', '自重卡：主数字=净负荷(87.5±外载) 非原值、标签「净负荷/NET LOAD」、plus 显加重、assist 显辅助；配重条只出人形图形、零文本',
      /^112\.5/.test(g7.r0.b) && /净负荷|NET LOAD/.test(g7.r0.lab) && /加重|ADDED/.test(g7.r0.b)
      && /^57\.5/.test(g7.r1.b) && /辅助|ASSIST/.test(g7.r1.b)
      && g7.r0.strip === '' && /class="gz-svg gz-bw"/.test(g7.r0.html)
      && /data-gz="bw" data-mode="plus"/.test(g7.r0.html)
      && g7.eff[0] === 112.5 && g7.eff[1] === 57.5,
      JSON.stringify(g7));
    T('G7.2', '哑铃卡：主数字=单边 24、灰后缀 ×2=48、标签「载荷/LOAD」不顶替；配重条只出哑铃图形（双边两组、每组各一枚头）、零文本',
      /^24/.test(g7.r2.b) && /×2=48/.test(g7.r2.b) && /载荷|LOAD/.test(g7.r2.lab)
      && g7.r2.strip === '' && /data-gz="dumb"/.test(g7.r2.html)
      && (g7.r2.html.match(/data-side="/g) || []).length === 2
      && (g7.r2.html.match(/gz-dhead/g) || []).length === 4
      && g7.eff[2] === 48,
      JSON.stringify(g7));

    /* ---------------- G8：挂片位编辑器 + 首页前四形态 ---------------- */
    SECT.s = 'G8';
    const g8 = JSON.parse(await evalIn(ws, id, G8));
    T('G8.1', '挂片编辑器出配置行：#gearPlateCfg 可见、posts 选项数 == POSTS_OPTIONS（契约派生，不手抄）；杠铃行该行隐藏',
      g8.cfgShown !== 'none' && g8.postOpts === g8.expPostOpts && g8.expPostOpts === 5 &&
      g8.cfgHiddenBar === 'none',
      'cfgShown ' + g8.cfgShown + ' / opts ' + g8.postOpts + ' vs ' + g8.expPostOpts + ' / bar ' + g8.cfgHiddenBar);
    T('G8.2', '均衡装载网格：挂片轴数 == posts(2)、每位同配方 ⇒ 圆片数 == 每位片数 × 轴数(4)',
      g8.postBlocks === 2 && g8.discBlocks === 4,
      'postBlocks ' + g8.postBlocks + ' / discBlocks ' + g8.discBlocks);
    T('G8.3', '挂片不套杠铃套管轴：plate 视图 #edPlateBar 有 no-sleeve 且无 .pv-sleeve；杠铃对照仍有 .pv-sleeve',
      g8.sleeveBar === 0 && g8.noSleeveBar === true && g8.sleeveOnBar >= 1,
      'plate sleeve ' + g8.sleeveBar + ' noSleeve ' + g8.noSleeveBar + ' / barbell sleeve ' + g8.sleeveOnBar);
    T('G8.4', 'setGearPosts：合法 4 生效且网格同步长到 4 位；非法 3（不在枚举）被拒、原值不动',
      g8.post4 === 4 && g8.blocksAfter4 === 4 && g8.postAfterBad === 4,
      'post4 ' + g8.post4 + ' / blocksAfter4 ' + g8.blocksAfter4 + ' / afterBad ' + g8.postAfterBad);
    T('G8.5', '史密斯开关 + 基数写回：toggle→variant smith、基数输入显 20；setGearBaseKg(25) 生效、(-5) 被拒（下限 0）',
      g8.variant1 === 'smith' && String(g8.baseInShown) === '20' &&
      g8.base === 25 && g8.baseAfterBad === 25,
      'variant ' + g8.variant1 + ' / baseInShown ' + g8.baseInShown + ' / base ' + g8.base + ' / afterBad ' + g8.baseAfterBad);
    T('G8.6', '首页 gear-strip 前四形态：挂片卡画挂片图形（轴数 == posts(2/4)）且不借杠铃片，史密斯卡摘要带品牌与基数；两条内零文本（位数不再写成 ×N）',
      g8.plHtml.indexOf('data-gz="plate"') >= 0 && g8.plHtml.indexOf('class="pb"') < 0 &&
      g8.plPosts === 2 && g8.plStripText === '' &&
      g8.smHtml.indexOf('data-gz="plate"') >= 0 && g8.smHtml.indexOf('class="pb"') < 0 &&
      g8.smPosts === 4 && g8.smStripText === '' &&
      /史密斯|SMITH/.test(g8.smStrip) && /18\.75/.test(g8.smStrip) && /每侧|PER SIDE/.test(g8.smStrip),
      'pl plate ' + (g8.plHtml.indexOf('data-gz="plate"') >= 0) + ' posts ' + g8.plPosts +
      ' / sm plate ' + (g8.smHtml.indexOf('data-gz="plate"') >= 0) + ' posts ' + g8.smPosts +
      ' / strip ' + JSON.stringify([g8.plStripText, g8.smStripText]) + ' / ' + g8.smStrip);

    /* ---------------- G9：插片双栈编辑器 + 特殊收口 ---------------- */
    SECT.s = 'G9';
    const g9 = JSON.parse(await evalIn(ws, id, G9));
    T('G9.1', '插片编辑器出配置行：#gearStackCfg 可见、#edStacks 选项数 == STACKS_OPTIONS（契约派生）、龙门架按钮在位；同屏特殊行隐藏、杠铃对照两行皆藏',
      g9.cfgShown !== 'none' && g9.stackOpts === g9.expStackOpts && g9.expStackOpts === 2 &&
      g9.cableChip === true && g9.spHiddenInStack === 'none' &&
      g9.stackHiddenInBar === 'none' && g9.spHiddenInBar === 'none',
      'cfg ' + g9.cfgShown + ' / opts ' + g9.stackOpts + ' vs ' + g9.expStackOpts +
      ' / cable ' + g9.cableChip + ' / bar ' + g9.stackHiddenInBar + ',' + g9.spHiddenInBar);
    T('G9.2', '竖向配重堆：列数 == stacks(1)、9 档全画（≤14 不截窗、销位 8 落在底档）且全在档上、有销位标记、栈不套杠铃套管轴',
      g9.cols === 1 && g9.winBlocks === 9 && g9.onBlocks === 9 && g9.hasPin === true &&
      g9.sleeveStack === 0 && g9.noSleeveStack === true,
      'cols ' + g9.cols + ' / win ' + g9.winBlocks + ' / on ' + g9.onBlocks + ' / pin ' + g9.hasPin +
      ' / sleeve ' + g9.sleeveStack + ' noSleeve ' + g9.noSleeveStack);
    T('G9.3', 'setGearStacks(2)：stacks==2、配置长出两行且第二栈明说「未登记档位表」不画假刻度；非法 3（不在枚举）被拒、停回当前 1 栈',
      g9.stacks2 === 2 && g9.cfgRows === 2 && g9.noTableTxt === true && g9.colsAfter2 === 0 &&
      g9.stacksAfterBad === 1,
      'stacks2 ' + g9.stacks2 + ' / rows ' + g9.cfgRows + ' / noTable ' + g9.noTableTxt +
      ' / cols ' + g9.colsAfter2 + ' / afterBad ' + g9.stacksAfterBad);
    T('G9.4', 'setGearStackField 只认销位：pin 10 生效、999 被拒（上限从契约读）、incKg/baseKg/stackCfg 一个都写不进；load 一字不动',
      g9.pin0 === 10 && g9.pinAfterBad === 10 && g9.oldKeys === '' && g9.cfg2inc === true &&
      g9.loadStackUntouched === 80,
      'pin0 ' + g9.pin0 + ' / afterBad ' + g9.pinAfterBad + ' / oldKeys「' + g9.oldKeys +
      '」/ noInc ' + g9.cfg2inc + ' / load ' + g9.loadStackUntouched);
    T('G9.5', '龙门架开关：toggle→variant cable 且 chip 亮、再 toggle 回 standard',
      g9.variantC === 'cable' && g9.chipOn === true && g9.variantBack === 'standard',
      'var ' + g9.variantC + '→' + g9.variantBack + ' / chipOn ' + g9.chipOn);
    T('G9.6', '特殊类把关：strip「16×3=48」；setGearUnitKg(-1)/setGearCount(0)/setGearLabel(空) 全被拒，原值不动；编辑器计数格 == count(3)',
      /16×3=48/.test(g9.strip1) && g9.unitAfterBad === 16 && g9.countAfterBad === 3 &&
      g9.labelAfterBad === '壶铃' && g9.spCellsEdit === 3,
      'strip ' + g9.strip1 + ' / unit ' + g9.unitAfterBad + ' / count ' + g9.countAfterBad +
      ' / label ' + g9.labelAfterBad + ' / cells ' + g9.spCellsEdit);
    T('G9.7', '形态收口：单栈卡 strip 只出配重堆图形（data-gz=stack + 销位、零文本、不画 .pb）；特殊卡主数字 48/手填 46、strip 只出单元方块零文本；特殊编辑器关套管轴',
      g9.stStrip === '' && g9.stStripHtml.indexOf('data-gz="stack"') >= 0 &&
      g9.stHtml.indexOf('class="pb"') < 0 &&
      /^48/.test(g9.sp0B) && g9.sp0Strip === '' && g9.sp0StripHtml.indexOf('class="gz-unit"') >= 0 &&
      /^46/.test(g9.sp1B) && g9.sp1Strip === '' &&
      /手填|MANUAL/.test(g9.manStrip) && g9.manEff === 46 && g9.spNoSleeve === true && g9.spSleeve === 0,
      'st ' + JSON.stringify(g9.stStrip) + ' / sp0 ' + g9.sp0B + ' ' + JSON.stringify(g9.sp0Strip) +
      ' / sp1 ' + g9.sp1B + ' / man ' + g9.manStrip + ' / sleeve ' + g9.spSleeve);
    T('G9.8', '档位表逐机编辑（走面板保存）：7 档非等差 20/22.5/25/28.5/32/35.5/39 原样入库，步长取最小差 2.5，销位写回 4',
      g9.savedLevels === '20,22.5,25,28.5,32,35.5,39' && g9.savedCount === 7 &&
      g9.savedStep === 2.5 && g9.pinAfterSave === 4,
      'levels ' + g9.savedLevels + ' / n ' + g9.savedCount + ' / step ' + g9.savedStep +
      ' / pin ' + g9.pinAfterSave);
    T('G9.9', '非等差 ± 走相邻可达档：28.5 → 32（+3.5 档），不按最小差 2.5 硬套',
      g9.next.load === 32 && g9.next.pins === '4',
      'next ' + JSON.stringify(g9.next));

    /* ---------------- G10：日程→场地 + 推断修正 ---------------- */
    SECT.s = 'G10';
    const g10 = JSON.parse(await evalIn(ws, id, G10));
    T('G10.1', '场地指针生效：local+dayVenueId 与 plan+defVenueId 都吃 gymX 库存（片 10/20 ⇒ 步长 2×10=20），且绝不改 e.load',
      g10.stepLocalDay === 20 && g10.stepPlanDef === 20 && g10.loadUntouched === true,
      'local ' + g10.stepLocalDay + ' / plan ' + g10.stepPlanDef + ' / load ' + g10.loadUntouched);
    T('G10.2', '回落腿全指回激活场地（legacy ⇒ 0.5），不崩 0：plan 无 def / local 无 day / 指到不存在的场地',
      g10.stepPlanNone === 0.5 && g10.stepLocalNoDay === 0.5 && g10.stepUnknownVenue === 0.5,
      'plan∅ ' + g10.stepPlanNone + ' / local∅ ' + g10.stepLocalNoDay + ' / ∃? ' + g10.stepUnknownVenue);
    T('G10.3', 'setGearGuess 写器械资料 record.kind 且 gearOf 认得（单轨，不开第二份状态）；非法 kind 拒、不留残条目',
      g10.defKind === 'dumbbell' && g10.guessKind === 'dumbbell' && g10.badRejected === true,
      'record ' + g10.defKind + ' / gearOf ' + g10.guessKind + ' / bad ' + g10.badRejected);
    T('G10.4', '设置页推断清单：行数 ≥1、每行 chip 数 == kinds(6)；setGearGuessAt(0,stack) 生效且该行来源翻「已修正」',
      g10.items >= 1 && g10.chips0 === g10.kinds && g10.kinds === 6 &&
      g10.stackApplied === true && g10.srcFixed === true,
      'items ' + g10.items + ' / chips ' + g10.chips0 + ' vs ' + g10.kinds +
      ' / applied ' + g10.stackApplied + ' / src ' + g10.srcFixed);

    /* ---------------- G11：中文动作名定向 + 首页形状语言 ---------------- */
    SECT.s = 'G11';
    const g11 = JSON.parse(await evalIn(ws, id, G11));
    T('G11.1', '中文动作名定向：插片→stack、挂片→plate、坐姿器械→stack、杠铃→barbell（不再一兜 barbell）',
      g11.h1 === 'stack' && g11.h2 === 'plate' && g11.h3 === 'stack' && g11.h4 === 'barbell',
      'h1 ' + g11.h1 + ' / h2 ' + g11.h2 + ' / h3 ' + g11.h3 + ' / h4 ' + g11.h4);
    T('G11.2', '首页形状语言：strip 带 data-k，六类各出专属图形（杠铃片/挂片图形 2、4 轴/插片块列+滑轮/哑铃头/自重人形/特殊单元）',
      g11.kinds === 'barbell,plate,plate,stack,dumbbell,bw,special' &&
      g11.bb.indexOf('class="pb"') >= 0 &&
      g11.pl.indexOf('data-gz="plate"') >= 0 && g11.plHorns === 2 &&
      g11.sm.indexOf('data-gz="plate"') >= 0 && g11.smHorns === 4 &&
      g11.st.indexOf('data-gz="stack"') >= 0 && g11.st.indexOf('class="gz-pulley"') >= 0 &&
      g11.db.indexOf('data-gz="dumb"') >= 0 && g11.db.indexOf('class="gz-dhead"') >= 0 &&
      g11.bw.indexOf('data-gz="bw"') >= 0 && g11.bw.indexOf('gz-bw') >= 0 &&
      g11.sp.indexOf('class="gz-unit"') >= 0,
      'kinds ' + g11.kinds + ' / horns ' + g11.plHorns + ',' + g11.smHorns
      + ' / bbpb=' + (g11.bb.indexOf('class="pb"') >= 0)
      + ' / pl=' + (g11.pl.indexOf('data-gz="plate"') >= 0)
      + ' / st=' + (g11.st.indexOf('data-gz="stack"') >= 0)
      + ' / stpill=' + (/gz-pulley/.test(g11.st || ''))
      + ' / db=' + (g11.db.indexOf('data-gz="dumb"') >= 0) + '/' + (g11.db.indexOf('class="gz-dhead"') >= 0)
      + ' / bw=' + (g11.bw.indexOf('data-gz="bw"') >= 0) + '/' + (g11.bw.indexOf('class="gz-bw"') >= 0)
      + ' / sp=' + (g11.sp.indexOf('class="gz-unit"') >= 0));

    /* ---------------- G12：四档窄屏，配重条零文本、图形不被裁、卡片不顶破 ----------------
       先把首页动作换成六类装备的夹具（G11 逐类只验形状、验完即还原），这样四档宽度
       量到的是挂片/插片/哑铃/自重/特殊全部五类非杠铃条，而不是当天恰好排到的两三条。 */
    const g12f = JSON.parse(await evalIn(ws, id, `(function(){
      var d=day(); window.__gearv.save();
      var rec=gearRecordAt(resolveVenueId({mv:'W1_A_G12ST'}),'W1_A_G12ST',true);
      rec.kind='stack';
      rec.stack={v:1,ladders:[{v:1,levels:[0,5,10,15,20,25,30,35,40,45,50,55],
                               updatedAt:'2026-01-01T00:00:00.000Z'}]};
      var mk=function(i,g,load){return {mv:'W1_A_G12'+i,cat:'S.Squat',mode:'T1.Mod',load:load,reps:5,rpe:null,gear:g};};
      d.exercises=[
        mk('BB',{kind:'barbell',barKg:20,collarOn:true,collarPairKg:5},100),
        mk('PL',{kind:'plate',posts:2,variant:'standard',baseKg:0},60),
        mk('SM',{kind:'plate',posts:4,variant:'smith',baseKg:20},80),
        mk('ST',{kind:'stack',stacks:1,variant:'cable',stackPins:[6]},60),
        mk('DB',{kind:'dumbbell',sides:2,incrementKg:2.5},48),
        mk('BW',{kind:'bw',lever:1},0),
        mk('SP',{kind:'special',label:'壶铃',unitKg:16,count:2},0)
      ];
      renderExercises();
      return JSON.stringify({kinds:Array.prototype.map.call(
        document.querySelectorAll('#exList article.ex .plate-strip'),
        function(s){return s.getAttribute('data-k');})});
    })()`));
    T('G12.0', '首页六类夹具就位（杠铃 1 + 非杠铃 5：挂片×2/插片/哑铃/自重/特殊）',
      g12f.kinds.length === 7 &&
      g12f.kinds.filter(function(k){return k !== 'barbell';}).length === 6,
      g12f.kinds.join(','));
    for (const w of [320, 360, 390, 412]) {
      SECT.s = 'G12 ' + w;
      await send(ws, id.v, 'Emulation.setDeviceMetricsOverride',
        { width: w, height: 892, deviceScaleFactor: 1, mobile: true });
      await new Promise(r => setTimeout(r, 160));
      const gw = JSON.parse(await evalIn(ws, id, `(function(){
        var arts=document.querySelectorAll('#exList article.ex'), n=0, txt=0, ov=0, minW=9999, cardOvf=0, minK='';
        var vw=window.innerWidth, cMax=0, cInfo='', cNon=0;
        for(var i=0;i<arts.length;i++){
          var a=arts[i], st=a.querySelector('.plate-strip');
          if(st){
            n++;
            if(st.textContent.replace(/\\s+/g,'')!=='') txt++;
            var d=st.scrollWidth-st.clientWidth; if(d>ov) ov=d;
            var sw=st.getBoundingClientRect().width;
            if(sw<minW){ minW=sw; minK=st.getAttribute('data-k')||''; }
            /* 非杠铃图形必须在条内水平居中：左右留白差 = |第一块到左边 / 右边到最后一块|。
               挂片/插片/哑铃/自重是内联 .gz-svg、特殊是 .gz-special 单元、杠铃是 .pb 片块，三种都要算进来；
               杠铃保持原样（横轴从 4px 起画），空杆条没有内容元素，两者都不进这条判据。 */
            var gegs=st.querySelectorAll('.gz-svg,.gz-special,.pb');
            if(st.getAttribute('data-k')!=='barbell' && !st.classList.contains('empty') && gegs.length){
              cNon++;
              var sr=st.getBoundingClientRect();
              var fr=gegs[0].getBoundingClientRect(), lr=gegs[gegs.length-1].getBoundingClientRect();
              var lg=fr.left-sr.left, rg=sr.right-lr.right, df=Math.abs(lg-rg);
              if(df>cMax){ cMax=df; cInfo=st.getAttribute('data-k')+' '+lg.toFixed(1)+'/'+rg.toFixed(1); }
            }
          }
          var r=a.getBoundingClientRect();
          if(r.right>vw+0.5) cardOvf=Math.max(cardOvf, Math.round(r.right-vw));
        }
        return JSON.stringify({n:n,txt:txt,ov:Math.round(ov),minW:Math.round(minW),minK:minK,cardOvf:cardOvf,
          cNon:cNon,cMax:+cMax.toFixed(2),cInfo:cInfo,
          docOvf:Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)-vw});
      })()`));
      T('G12 ' + w + 'px',
        '配重条四档收口：' + gw.n + ' 条全部零文本、内裁 ' + gw.ov + 'px、最窄 ' + gw.minW +
        'px、卡片越界 ' + gw.cardOvf + 'px、整页横滚 ' + gw.docOvf + 'px',
        gw.n >= 6 && gw.txt === 0 && gw.ov <= 1 && gw.cardOvf <= 1 && gw.docOvf <= 1, JSON.stringify(gw));
      T('G12c ' + w + 'px',
        '非杠铃配重图形条内居中：' + gw.cNon + ' 条，最大左右留白差 ' + gw.cMax + 'px（' + gw.cInfo + '）',
        gw.cNon >= 6 && gw.cMax <= 0.6, JSON.stringify({cNon:gw.cNon,cMax:gw.cMax,cInfo:gw.cInfo}));
    }
    /* 夹具用完还原：后面的 G13 与 G0.2 副作用哈希必须回到真实日程（含档位表记录）。 */
    await evalIn(ws, id, `(function(){
      window.__gearv.restore(); renderExercises(); return 'ok';
    })()`);
    await send(ws, id.v, 'Emulation.setDeviceMetricsOverride',
      { width: 412, height: 892, deviceScaleFactor: 1, mobile: true });
    await new Promise(r => setTimeout(r, 160));

    /* ---------------- G13：pin=0 不许画成空白 ---------------- */
    SECT.s = 'G13';
    const g13 = JSON.parse(await evalIn(ws, id, `(function(){
      var h=gearGlyph({kind:'stack',recipe:{stacks:[{pin:0,kg:0}],variant:'standard'}});
      return JSON.stringify({h:h,stack:h.indexOf('data-gz="stack"')>=0,
        pin:h.indexOf('data-gz="pin"')>=0,dpin:/data-pin="0"/.test(h),
        eng:(h.match(/data-engaged="1"/g)||[]).length,
        blocks:(h.match(/data-idx="/g)||[]).length,len:h.length});
    })()`));
    T('G13', '插片 pin=0：条内仍画出配重堆与销位（0→1 档实心），不是空白条',
      g13.stack && g13.pin && g13.dpin && g13.eng === 1 && g13.blocks === 1 && g13.len > 40,
      JSON.stringify(g13));

    /* ---------------- G14：逐机档位表（非等差）+ 跨动作隔离 ---------------- */
    SECT.s = 'G14';
    const g14 = JSON.parse(await evalIn(ws, id, G14));
    T('G14.1', '每台插片机各存一把绝对 kg 档位表：A 前 2.5 后 3.5（非等差）7 档、B 5 档；步长各取自己的最小差',
      g14.a.levels === '20,22.5,25,28.5,32,35.5,39' && g14.a.step === 2.5 &&
      g14.b.levels === '10,15,20,25,30' && g14.b.step === 5,
      'A ' + g14.a.levels + '@' + g14.a.step + ' / B ' + g14.b.levels + '@' + g14.b.step);
    T('G14.2', '各自按自己的表求最近档：A 目标 25 命中第 3 档、B 目标 20 命中第 3 档，均 exact',
      g14.a.ach === 25 && g14.a.exact === true && g14.a.pin === 2 &&
      g14.b.ach === 20 && g14.b.exact === true && g14.b.pin === 2,
      'A ' + g14.a.ach + '/' + g14.a.pin + ' / B ' + g14.b.ach + '/' + g14.b.pin);
    T('G14.3', '非等差 ± 按相邻可达档走：A 28.5→32（+3.5）、B 10→15（+5），不是最小差硬套',
      g14.nextA && g14.nextA.load === 32 && g14.nextA.pins.join(',') === '4' &&
      g14.nextB && g14.nextB.load === 15 && g14.nextB.pins.join(',') === '1',
      'A ' + JSON.stringify(g14.nextA) + ' / B ' + JSON.stringify(g14.nextB));
    T('G14.4', '跨动作隔离：只在 A 点销位 → A 实配 32；B 无 stackPins、实配仍 20；两条 record 各是各的表',
      g14.aPin.load === 32 && g14.aPin.pins === '4' && g14.aPin.bPins === 'none' &&
      g14.aPin.bAch === 20 && g14.recA !== g14.recB,
      JSON.stringify(g14.aPin) + ' / recA ' + g14.recA + ' / recB ' + g14.recB);
    T('G14.5', '坏表（降序）不改用户原文：stackLadderOf=false、solver exact=false + 警告、record 仍是 25,20,15',
      g14.bad.ok === false && g14.bad.exact === false && g14.bad.warn.length > 0 &&
      g14.bad.kept === '25,20,15',
      JSON.stringify(g14.bad));

    /* ---------------- G15：器械图形的新钩子（销位单调 / 零文字 / 挂片余量 / 尺寸 / 窗口） ---------------- */
    SECT.s = 'G15';
    const g15 = JSON.parse(await evalIn(ws, id, G15));
    T('G15.1', '销位单调：9 档 ladder 上 pin 0..8 依次落销，卡上 data-pin 与实心块数严格递增 1..9',
      g15.mono.length === 9 &&
      g15.mono.every(function(x,i){ return x && x.pin === i && x.eng === i + 1; }),
      JSON.stringify(g15.mono));
    T('G15.2', '条内零文字：六类每个 .gz-svg 的 textContent 为空且无 <text>，特殊单元也零文字',
      g15.tx.svg >= 4 && g15.tx.special === 1 &&
      g15.tx.text === 0 && g15.tx.poly === 0 && g15.tx.sBad === 0,
      JSON.stringify(g15.tx));
    T('G15.3', '挂片空轴/余量：12kg 低于基数、101kg 粗库存余 0.5kg 都画出 ghost，卡片不写「无片」',
      g15.ghostLow.ghost > 0 && g15.ghostCoarse.ghost > 0 &&
      !/无片/.test(g15.ghostLow.txt) && !/无片/.test(g15.ghostCoarse.txt),
      JSON.stringify([g15.ghostLow, g15.ghostCoarse]));
    T('G15.4', '挂片尺寸分档：编辑器大图高 48px，首页 strip 小图高 26px（小图不用 40px）',
      g15.bigH === '48px' && g15.smallH === '26px' && g15.smallH !== '40px',
      'big ' + g15.bigH + ' / small ' + g15.smallH);
    T('G15.5', '插片窗口：20 档、pin 15 → 只画 14 块（lo=6..19），销位在窗内且 engaged=pin−lo+1=10',
      !!g15.win && g15.win.pin === 15 && g15.win.blocks === 14 &&
      g15.win.min === 6 && g15.win.max === 19 && g15.win.eng === 10 && g15.win.hasPin === true,
      JSON.stringify(g15.win));

    /* ---------------- G16：器械身份分层 + 跨动作不串味 ---------------- */
    SECT.s = 'G16';
    const g16 = JSON.parse(await evalIn(ws, id, G16));
    T('G16.1', '身份部件按契约派生、不手抄名单：杠铃 bar+plates+support、挂片 machine+plates、插片/自重 machine、哑铃 dumbbell+bench',
      g16.parts.bb === 'bar,plates,support' && g16.parts.pl === 'machine,plates' &&
      g16.parts.st === 'machine' && g16.parts.db === 'dumbbell,bench',
      JSON.stringify(g16.parts));
    T('G16.2', '杠铃三段各写品牌/系列/名称：identity 存在器械资料 record（不进动作行），support.type 保留，摘要三段都在',
      /Eleiko/.test(g16.bbSaved) && /Rogue/.test(g16.bbSaved) && /SBD/.test(g16.bbSaved) &&
      /"combo"/.test(g16.bbSaved) && g16.bbInGear === false &&
      /Eleiko/.test(g16.bbSum) && /Rogue/.test(g16.bbSum) && /SBD/.test(g16.bbSum),
      g16.bbSaved + ' / ' + g16.bbSum);
    T('G16.3', '哑铃只写一段、凳可选：只填哑铃时 identity 里没有 bench 残条目，摘要只出一段',
      /Bowflex/.test(g16.dbSaved) && g16.dbBench === false && /Bowflex/.test(g16.dbSum),
      g16.dbSaved + ' / bench ' + g16.dbBench + ' / ' + g16.dbSum);
    T('G16.4', '身份逐动作不串味：插片机登记 Life Fitness 后只有它自己的摘要变，杠铃摘要仍只有原三段',
      /Life Fitness/.test(g16.stRecord) && /Life Fitness/.test(g16.stSum) &&
      !/Life Fitness/.test(g16.bbAfter) && /Eleiko/.test(g16.bbAfter),
      'st ' + g16.stSum + ' / bb ' + g16.bbAfter);

    /* ---------------- G0 出段 ---------------- */
    SECT.s = 'G0';
    await new Promise(r => setTimeout(r, 650));   // 等可能的防抖写盘，别让晚到的写骗过快照
    const snap1 = await evalIn(ws, id, '__gearv.hash()');
    T('G0.2', '整轮零副作用：账本与四路分片哈希回到入段前',
      snap0 === snap1, snap0 === snap1 ? snap1 : ('前 ' + snap0 + ' → 后 ' + snap1));
  } catch (e) {
    if (e && e.stack) console.error('Z0 现场栈：\n' + e.stack);
    T('Z0', '断言块在 ' + SECT.s + ' 段中途抛错（其后断言未执行）', false,
      String((e && e.message) || e).replace(/\s+/g, ' ').slice(-300));
  }

  /* 断言总数闸门：少一条就是少一条，不能装作还是全绿。
     103 = G0 2 + G1 18 + G2 4 + G3 12 + G4 3 + G5 3 + G6 14 + G7 2 + G8 6 + G9 9 + G10 4 + G11 2 + G12 9 + G13 1 + G14 5 + G15 5 + G16 4. */
  const EXP_N = 103;
  if (PASS + FAIL !== EXP_N) {
    LINES.push('FAIL  Z1 断言总数漂移（实到 ' + (PASS + FAIL) + '，应 ' + EXP_N + '）');
    FAIL++;
  }
  console.log(LINES.join('\n'));
  const nP = LINES.filter(l => l.indexOf('PASS') === 0).length;
  const nF = LINES.filter(l => l.indexOf('FAIL') === 0).length;
  console.log('\n== gearv 汇总: ' + nP + ' PASS / ' + nF + ' FAIL （共 ' + (nP + nF) + ' 项）==');
  ws.close();
  const cleaned = await tmpclean.close(chrome, tmp, FAIL > 0);
  if (FAIL > 0) console.log('现场保留在 ' + tmp);
  else if (!cleaned) console.log('临时目录没清掉：' + tmp);
  process.exit(FAIL > 0 ? 1 : 0);
}

main().catch(async e => {
  console.error('gearv 跑飞：' + (e && e.stack || e));
  await tmpclean.close(chrome, tmp);
  process.exit(2);
});
