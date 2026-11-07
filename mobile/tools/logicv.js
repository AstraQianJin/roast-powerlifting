#!/usr/bin/env node
// logicv.js —— App 内全部纯逻辑函数的高密度扫描（v0.10 全量逻辑测试）
//
// 与 xlsxv.js 的分工：xlsxv 钉「两份实现对不对得上」（逐格、逐条判定），本套钉
// 「一份实现对不对得起自己的定义」—— 配片是否真的最少、热身阶梯是否单调、
// 系数与段位是否覆盖全定义域、随机账本换算是否守得住不变量。参照系三条，
// 全部独立于被测函数：
//   N 段 Python oracle（tools/xlsx_parity.py numfmt，归一化串逐字比）
//   P 段 穷举 DP（在 harness 里另写一份，不复用被测的那份贪心）
//   E/J/S/F/C/A 段 定义式与性质（官方系数、契约边界、单调/幂等/收敛不变量）
//
//   node tools/logicv.js
const { spawn, spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const tmpclean = require('./tmpclean');

const HERE = __dirname;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PY = process.env.PYTHON || 'python';
const FILE = 'file:///' + path.resolve(HERE, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9830 + Math.floor(Math.random() * 15);

let PASS = 0, FAIL = 0, LINES = [];
function T(label, ok, detail) {
  PASS += ok ? 1 : 0; FAIL += ok ? 0 : 1;
  LINES.push((ok ? 'PASS  ' : 'FAIL  ') + label + (detail !== undefined ? '  [' + detail + ']' : ''));
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
function py(args) {
  const r = pyRaw(args);
  if (r.code !== 0) throw new Error(PY + ' ' + args.join(' ') + ' 退出码 ' + r.code + '\n' + (r.out || ''));
  return r.out;
}
function pyRaw(args) {
  const r = spawnSync(PY, args, { cwd: path.resolve(HERE, '..'), encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}
/* 与页面 mround 同式的独立参照：就近一律写成 floor(q+0.5)，不用 Math.round ——
   Python 侧 plan_xlsx.mround 就是这个式子，而 JS 的 round 在 0.49999999999999994 这类
   「加半格前刚好不到半」的数上会给不同答案。 */
function mroundRef(v, s) { return Math.floor(v / s + 0.5) * s; }

/* ============================ N 段：数值与格式 ============================
   契约的列类型只有 str / num / int / bool / date / enum，格子值的定义域就是这批标量。
   用例分两类：两边真会遇到的写法（千分位、百分号、空格、空串、布尔），和两边语言规则
   分叉的地方（inf/nan 字面量、1e400 溢出成 inf、1/128 的奇数倍 = 十进制第七位恰好半格、
   1e-5 与 1e21 这两个换指数写法的门槛、全角数字这类 float() 比 JS 宽的输入）。
   期望值一律由 Python 现算，本文件不写死任何一个归一化串。 */
const N_VALUES = [
  null, 0, -0, 1, -1, 24, 24.0, 2.5, -2.5, 0.1, 0.5, 1.5, 2.675,
  0.0078125, 0.0234375, 0.0390625, 0.0546875, 33.0078125, -0.0078125, 1 / 128, 127 / 128,
  1e-5, 1e-4, 9.99999e-5, 1e21, 1e20, 9007199254740992, 4503599627370496.5, 1 / 3,
  0.1 + 0.2, 1e16 + 0.5, -1e-5, 2.5e-7, 1234.5678905, 1234.5678915,
  '', '   ', '1', '1.0', '-0', '+3', '.5', '5.', '5.5', '1,234.5', '1_000', '1__0', '_1',
  '75%', ' 75 % ', '0.5%', '-25%', '%', '50 % extra', 'abc', 'NaN', 'nan', '-nan',
  'inf', 'Inf', '-INF', 'infinity', '-Infinity', 'Infinity', '1e400', '-1e400', '1e-400',
  '1e', 'e5', '0x1f', '1 2', '１２', '１２３４', '٣', 'TRUE', 'true', 'False', '是', '否',
  '√', '×', '开', '关', 'on', 'off', 'Y', 'n', '1\n2', '0.0', '-0.0', '00', '0.0000005',
  true, false, 75, 100, 999.999, -0.0000005, 0.0000004999, 25, 22.5, 87.5, 0.25, 1.25,
  1e308, 5e-324, 8.999999999999999e15, ' 1e21 ', '9007199254740993', '2.5%', '1,7%', '\t3\n'
];
const N_STEPS = [2.5, 0.5, 1, 5, 0.25, 2.25, 12.5];
let N_KEYS = [];

const N_RUN = `(function(values, steps){
  var out={cellkey:[],num:[],int:[],bool:[],datestr:[],f1:[],mround:{}};
  values.forEach(function(v){
    out.cellkey.push(xCellKey(v));
    out.num.push(xCellKey(xNum(v)));
    out.int.push(xCellKey(xInt(v)));
    out.bool.push(xCellKey(xAsBool(v)));
    out.datestr.push(xCellKey(xDateStr(v)));
    var n=xNum(v);
    /* f1 的定义式要 x*10 不溢出：与 Python 侧 numfmt_expect 同一个 1e307 门槛，两侧都留空才可比 */
    out.f1.push((typeof n==='number'&&isFinite(n)&&Math.abs(n)<=1e307)?xCellKey(xF1(n)):'');
  });
  steps.forEach(function(s){ out.mround[xCellKey(s)]=values.map(function(v){ return xCellKey(mround(v,s)); }); });
  out.idem=values.every(function(v){ var k=xCellKey(v); return k===''||k===xCellKey(k); });
  return JSON.stringify(out);
})`;

function diffList(a, b, limit) {
  const bad = [];
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) if (a[i] !== b[i]) bad.push(i);
  const show = (i) => { const k = N_KEYS[i]; return k === undefined ? '#' + i : k; };
  return { n: bad.length,
    samples: bad.slice(0, limit || 4).map(i => show(i) + '：Python ' + JSON.stringify(a[i]) +
      ' ≠ App ' + JSON.stringify(b[i])) };
}

/* ============================ P 段：配片 DP + 热身 ============================
   platesPerSide 是贪心（25→0.25 递降）。贪心是否最优是命题不是定义，所以在 harness 里
   另写一份完全背包 DP（同一片组、最少片数），逐目标比：片数不许输给 DP、
   片重加余数必须等于逐侧需求、exact 必须与「这个重量凑不凑得出 0.25 整数格」同判。 */
const P_PLATES = [25, 20, 15, 10, 5, 2.5, 1.25, 1, 0.75, 0.5, 0.25];
const P_BARS = [10, 15, 20, 25, 30, 35, 40];

const P_PROBE = `(function(barOpts, plateKgs, targets){
  var out=[], vid=venueIdOf(), savedInv=clone(venueInv());
  barOpts.forEach(function(bar){
    [false,true].forEach(function(col){
      venueInv().bar_kg=bar; venueInv().collar_on=col;
      targets.forEach(function(t){
        var r=platesPerSide(t,col);
        out.push({bar:bar, t:t, collars:col, n:r.plates.length,
          kg:r.plates.map(function(p){return p.kg;}), perSide:r.perSide,
          rem:r.remainder, exact:r.exact, note:r.note||''});
      });
    });
  });
  state.venues[vid].inventory=savedInv;
  var junk=[]; [0,12,21,-5,40.5,'20',null,NaN,25].forEach(function(v){ setBarKg(v); junk.push(barKg()); });
  setBarKg(savedInv.bar_kg||BAR_KG);
  var warm=targets.map(function(t){ return warmups(t).map(function(x){return [x.w,x.rep];}); });
  var wneg=[0,-5,NaN,null,undefined].map(function(v){ return warmups(v).map(function(x){return [x.w,x.rep];}); });
  return JSON.stringify({res:out, junk:junk, warm:warm, wneg:wneg, barOpts:BAR_OPTIONS.slice(),
    plateKgs:PLATES.map(function(p){return p.kg;}), collarPair:COLLAR_KG,
    barNow:barKg(), restored:JSON.stringify(venueInv())===JSON.stringify(savedInv)});
})`;

/* harness 侧独立算的最少片数：完全背包，0.25kg 粒度；凑不出整数格返回 null。 */
function dpMinPlates(perSideKg, plateKgs) {
  const unit = 0.25;
  const need = Math.round((perSideKg + 1e-9) / unit);
  if (!(need >= 0) || need > 20000) return undefined;
  if (Math.abs(need * unit - perSideKg) > 1e-6) return null;
  const INF = 1e9, best = new Array(need + 1).fill(INF);
  best[0] = 0;
  for (let s = 1; s <= need; s++)
    for (const p of plateKgs) {
      const pu = Math.round(p / unit);
      if (pu > 0 && pu <= s && best[s - pu] + 1 < best[s]) best[s] = best[s - pu] + 1;
    }
  return best[need] >= INF ? null : best[need];
}

/* ============================ E 段：e1RM / 系数 / 段位 ============================ */
const E_PROBE = `(function(){
  var e=[], gl=[], dots=[], wil=[], rank=[];
  var loads=[0,-10,20,60,100,142.5,200], reps=[0,-1,1,3,5,8,12,13,20,30],
      rpes=[0,4,4.9,5,6.5,7,9.5,10,10.5,'',null], trpes=[0,5,8,10,11,null];
  loads.forEach(function(L){ reps.forEach(function(R){ rpes.forEach(function(P){ trpes.forEach(function(TR){
    e.push([L,R,P,TR,e1rm(L,R,P,TR)]);
  }); }); }); });
  var bws=[0,34.9,34.99,35,36,39.99,40,47.5,59,74.5,83,93,105,120,149.9,149.99,150,150.01,
           150.94,150.95,150.96,200.5,200.94,200.95,200.96,209.99,210,210.01,211,300,-20];
  var totals=[0,100,300,500,600.5,900];
  ['M','F','X',null].forEach(function(g){ ['classic','equipped','weird',null].forEach(function(q){ [false,true].forEach(function(b){
    totals.forEach(function(T){ bws.forEach(function(B){ gl.push([T,B,g,q,b,calcIpfGl(T,B,g,q,b)]); }); });
  }); }); });
  ['M','F','x'].forEach(function(g){ totals.forEach(function(T){ bws.forEach(function(B){
    dots.push([T,B,g,calcDots(T,B,g)]); wil.push([T,B,g,calcWilks2(T,B,g)]); }); }); });
  var gls=[-100,-0.01,0,0.01,44.99,45,45.01,48,51,57,59.99,60,60.01,63,74.99,75,75.01,78,
           89.99,90,90.01,92,98,99,100,120,999,1e9,NaN,null,'x'];
  gls.forEach(function(v){ var r=calcGlRank(v);
    rank.push([v,r.id,r.stars,r.starsStr,r.nextStarGl,r.deltaNext,r.labelZh]); });
  /* 未取整判档的验证点（E3c）：真值 44.9972 → 青铜 5★，显示值 45.00 → 白银 1★。 */
  var raw328=calcIpfGlRaw(328.982,85,'M','classic',false);
  return JSON.stringify({e:e, gl:gl, dots:dots, wil:wil, rank:rank,
    g8:[raw328,calcIpfGl(328.982,85,'M','classic',false),calcGlRank(raw328).id,calcGlRank(raw328).stars,calcGlRank(45).id],
    tiers:GL_RANKS.map(function(t){return [t.id,t.min,t.step];})});
})`;

/* ============================ J 段：JTS 全域 + 恢复驱动组数 ============================ */
const J_PROBE = `(function(){
  var out={calc:[],band:[],weeks:[],step:[],legacy:null};
  var vals=[null,'',0,2.5,4,5,6,9,10,11,-1,'7'];
  /* 六维改版（D14）：样本喂新口径的六个键（sleep/stress/fatigue/soreness/motivation/energy），
     采集 jtsCalcV6 的 R / 计数 / 置信度 / 档位 / recBase / B_gpp / F_gpp / recMult / sick 与逐维归一值。
     字段索引固定：0 标签 1 sc(JSON) 2 R 3 missing 4 filled 5 confidence 6 recMult 7 recBase
     8 band 9 bGpp 10 fGpp 11 sick 12 crs 残留标记 13 dims(JSON)。 */
  function packRow(label,sc,v6){ out.calc.push([label,JSON.stringify(sc),v6.R,v6.missing,v6.filled,v6.confidence,
    v6.recMult,v6.recBase,v6.band,v6.bGpp,v6.fGpp,(v6.sick?1:0),
    (v6.crs===undefined?'undef':('crs='+v6.crs)),
    JSON.stringify((v6.dims||[]).map(function(d){return [d.k,d.v,d.n,(d.rev?1:0)];}))]); }
  vals.forEach(function(sv){ vals.forEach(function(st){ vals.forEach(function(fa){
    var sc={sleep:sv,stress:st,fatigue:fa,soreness:5,motivation:5,energy:5};
    packRow('G'+out.calc.length,sc,jtsCalcV6(sc,1));
  }); }); });
  var best={sleep:7,stress:1,fatigue:1,soreness:1,motivation:7,energy:7};
  var worst={sleep:1,stress:7,fatigue:7,soreness:7,motivation:1,energy:1};
  var mid={sleep:5,stress:5,fatigue:5,soreness:5,motivation:5,energy:5};
  var extra=[best,worst,{},mid,{sleep:7,stress:1},
             {sick:true,sleep:7,stress:1,fatigue:1,soreness:1,motivation:7,energy:7},
             {sleep:5,stress:5,fatigue:5}];
  extra.forEach(function(sc,i){ packRow('S'+i,sc,jtsCalcV6(sc,0)); });
  /* 档位判据独立探针：jtsBandOf 在 ready_at=[90,75,60,45] 各落点 + null + sick 强制末档。 */
  [null,-5,0,44.9,45,59.9,60,74.9,75,89.9,90,100,1e9,NaN].forEach(function(x){
    out.band.push([x,0,jtsBandOf(x,false)]); out.band.push([x,1,jtsBandOf(x,true)]); });
  for(var w=1;w<=16;w++){
    var r=computeRecommendedSets(w,'A');
    out.weeks.push([w,r.cycleType,r.readyIdx,r.sq.min,r.sq.rec,r.sq.max,r.sq.cur,r.sq.isCustom,
      r.bp.min,r.bp.rec,r.bp.max,r.bp.cur,r.dl.min,r.dl.rec,r.dl.max,r.dl.cur,
      r.sq.planned,r.sq.band.id,r.mult]);
  }
  /* 手调上限：不得低于 10，也不得高于模型本周 MRV 上限（高容量周模型建议本身会 >10，
     硬钳 10 会让「加一组」把 14 压回 10）。期望值由 computeRecommendedSets 现算，不在测试里抄数字。 */
  var capModel=computeRecommendedSets().sq;
  stepRecSet('sq',+9);  out.step.push(['hi',state.structure.recSetsOverride.sq,Math.max(10,capModel.max)]);
  stepRecSet('sq',-99); out.step.push(['lo',state.structure.recSetsOverride.sq,1]);
  resetRecSets();       out.step.push(['reset',JSON.stringify(state.structure.recSetsOverride)]);
  var savedJts=state.jts;
  state.jts={'5_B':{sleep:9,stress:1,health:9,drive:9,willingness:9,soreness:1}};
  var m=getWeekJts(5);
  out.legacy={keys:Object.keys(m).length, sleep:m.sleep, newKey:!!state.jts['W5']};
  state.jts=savedJts;
  return JSON.stringify(out);
})`;

/* jtsRef（三因子 + CRS）随六维改版（D14）删除：新的独立重算见文件下方 jtsDimsRef / jtsScoreRef / jtsBandRef。 */

/* ============================ S 段：时间线 + 冻结 ============================ */
const S_PROBE = `(function(cases){
  function mkFrozen(total){
    var so=clone(SEED);
    so.structure.totalWeeks=total; so.structure.inactiveWeeks=[];
    var keep={}; for(var w=1;w<=total;w++) if(so.weeks[String(w)]) keep[String(w)]=so.weeks[String(w)];
    so.weeks=keep;
    xFreezeExtraWeeks(so, SEED.weeks||{});
    return so;
  }
  var tl=cases.map(function(c){
    var r=compileTimeline({startDate:c.start, blocks:c.blocks});
    return {n:r.length, weeks:r.map(function(x){return x.week;}),
      block:r.map(function(x){return x.block;}), deload:r.map(function(x){return x.isDeload;}),
      range:r.map(function(x){return x.range;}), bi:r.map(function(x){return x.bi;})};
  });
  var freeze=[], act=[];
  var seedMax=Object.keys(SEED.weeks).map(Number).sort(function(a,b){return b-a;})[0];
  [1,3,4,12,15,16,17].forEach(function(total){
    var so=mkFrozen(total);
    freeze.push({total:total, kept:Object.keys(so.weeks).length,
      inactive:(so.structure.inactiveWeeks||[]).slice(),
      wLastSame:seedMax>0 && !!SEED.weeks[String(seedMax)] && JSON.stringify(so.weeks[String(seedMax)])===JSON.stringify(SEED.weeks[String(seedMax)])});
    var saved=state; state=so;
    var keys=activeWeekKeys(); state=saved;
    act.push({total:total, n:keys.length, first:keys[0], last:keys[keys.length-1],
      clean:keys.every(function(k){ return (so.structure.inactiveWeeks||[]).indexOf(+k)<0; })});
  });
  return JSON.stringify({tl:tl, freeze:freeze, act:act, seedMax:seedMax});
})`;

function mkBlocks(ww, dw) {
  return ww.map((n, i) => ({ id: 'B' + (i + 1), cycleType: 'Hyper', nameZh: 'b' + (i + 1),
    nameEn: 'B' + (i + 1), workWeeks: n, deloadWeeks: dw[i] || 0 }));
}

/* ============================ F 段：随机账本 ⇄ 六表 ============================
   随机造 state（周数 1..种子末周、每日 0–4 个动作、脏备注），走 导出换算 → 契约 → 回装 → 再导出。
   类别、模式、锚点一律从种子的导出结果现取，本段不写死任何一个动作名。 */
const F_SEEDS = [1, 2, 3, 7, 11, 42, 99, 1234, 20250, 777, 31337, 8675309, 60613, 99991, 2147483647];

const F_PROBE = `(function(seeds){
  var sch=PLAN_SCHEMA, rc=sch.sheets.Workouts.role_columns, first=sch.row_idx.first;
  var p0=xStateToPlanDict(clone(SEED)), modes=[], catSeen={};
  p0.Workouts.forEach(function(r){
    if(modes.indexOf(r[rc.mode])<0) modes.push(r[rc.mode]);
    catSeen[r[rc.category]]=1;
  });
  var catList=Object.keys(catSeen), afs=xAnchorProfileFields(sch), out=[];
  /* 随机周数封顶到种子周数：契约里 week 的合法区间由种子给出，越界的周本来就该被校验拦下，
     这一段测的是换算守恒，不是把非法周塞进导出件。 */
  var seedMax=Object.keys(SEED.weeks).map(Number).sort(function(a,b){return b-a;})[0];
  var cellsOf=function(pp){ var o=sch.sheet_order, c={}, mo={}, hole=0;
    for(var k=0;k<o.length;k++){ var nm=o[k], cc=sch.sheets[nm].columns, list=pp[nm]||[];
      for(var i=0;i<list.length;i++){ var rw=list[i];
        if(!rw){ hole++; continue; }
        var mm=Object.prototype.hasOwnProperty.call(rw,rc.mode)?xText(rw[rc.mode]):'';
        for(var j=0;j<cc.length;j++){ var col=cc[j];
          if(Object.prototype.hasOwnProperty.call(rw,col)){ var key=nm+'|'+i+'|'+col;
            c[key]=xCellKey(rw[col]); mo[key]=mm; } } } }
    return {c:c, mo:mo, hole:hole}; };
  function cmp(A,B){ var x=cellsOf(A), y=cellsOf(B), a=x.c, b=y.c, bad=[];
    Object.keys(a).forEach(function(k){ if(b[k]!==a[k]) bad.push({k:k,a:a[k],b:b[k],mo:x.mo[k]}); });
    Object.keys(b).forEach(function(k){ if(!(k in a)) bad.push({k:k,a:null,b:b[k],mo:y.mo[k]}); });
    return {bad:bad, hole:x.hole+y.hole}; }
  function holeCount(pp){ var n=0; sch.sheet_order.forEach(function(nm){ var list=pp[nm]||[];
    for(var i=0;i<list.length;i++) if(!list[i]) n++; }); return n; }
  /* 回装侧有两处「有意不守恒」，都是把空格补齐而不是改已有格：
     ① Workouts.rx_text 空 → 该模式的种子处方（template.html 7212 ex.rx = 格子值 || 模式处方）；
     ② 任何表的空格 → 契约 sheets.<表>.defaults 里该列的默认值（如 Blocks.base_rpe 空 → 7）。
     许可范围就此两类，且补出的串必须逐字等于①的处方表 / ②的默认值；其余任何格子改动都是缺陷。
     两类都只该发生在第一轮，第二轮是不动点（F4 连 soft 一起查）。
     模式随格子一起从 cellsOf 带出来，避免按行号回查（行号只对各自那份表成立）。 */
  function classify(diff){
    var hard=[], soft=0, softBad=[];
    diff.bad.forEach(function(d){
      /* 探针写在模板串里，反斜杠会被吞：这里用 [|] 与 [0-9] 而不是 \\| 和 \\d */
      var m=/^([A-Za-z]+)[|]([0-9]+)[|]([a-z_]+)$/.exec(d.k);
      if(d.a!==''||!m){ hard.push(d.k+' '+JSON.stringify(d.a)+'->'+JSON.stringify(d.b)); return; }
      var sheet=m[1], col=m[3];
      if(sheet==='Workouts'&&col==='rx_text'){
        var pr=(SEED.proto&&SEED.proto[d.mo])||{};
        var want=(pr.rx!==undefined)?String(pr.rx):'';
        if(d.b===want&&want!==''){ soft++; return; }
        softBad.push(d.k+'(模式 '+d.mo+')->'+JSON.stringify(d.b)+' 应 '+JSON.stringify(want));
        return;
      }
      var df=(sch.sheets[sheet].defaults||{})[col];
      if(df===undefined){ softBad.push(d.k+' 契约 '+sheet+' 没有列 '+col+' 的默认值'); return; }
      if(xCellKey(df)===d.b){ soft++; return; }
      softBad.push(d.k+'->'+JSON.stringify(d.b)+' 应等于契约默认 '+JSON.stringify(xCellKey(df)));
      return;
    });
    return {hard:hard, soft:soft, softBad:softBad, hole:diff.hole};
  }
  seeds.forEach(function(sd){
    var s=sd>>>0;
    var rnd=function(){ s=(s*1664525+1013904223)>>>0; return s/4294967296; };
    var st=clone(SEED), total=1+Math.floor(rnd()*seedMax);
    var days=(st.structure.dayDefs||[]).map(function(d){ return d.id; });
    st.structure=clone(SEED.structure);
    /* 块表必须与 totalWeeks 自洽：回装时 total 是按块表求和算出来的，块表留着种子那套周数
       就会造出「结构说 4 周、块表说种子总周数」的账本，回装白多出若干周的行（不是页面缺陷是我的用例不自洽）。 */
    var nb=Math.min(1+Math.floor(rnd()*3), total), spans=[], leftW=total;
    for(var bi=0;bi<nb;bi++){ var take=(bi===nb-1)?leftW:Math.max(1,Math.floor(leftW/(nb-bi))); spans.push(take); leftW-=take; }
    st.structure.blocks=spans.map(function(n,i){ var dl=Math.floor(n/4);
      return {id:'B'+(i+1), cycleType:'Hyper', nameZh:'块'+(i+1), nameEn:'B'+(i+1),
        workWeeks:n-dl, deloadWeeks:dl}; });
    st.structure.totalWeeks=total; st.structure.inactiveWeeks=[];
    st.profile.planWeeks=total;   /* 契约把 Profile.plan_weeks 与 Blocks 周数之和交叉校验，两处要一起改 */
    st.weeks={};
    for(var w=1;w<=total;w++){ var dayObj={};
      for(var di=0;di<days.length;di++){ var exs=[], n=Math.floor(rnd()*4);
        for(var j=0;j<n;j++){
          var cat=catList[Math.floor(rnd()*catList.length)];
          var mode=modes[Math.floor(rnd()*modes.length)];
          var anchor=afs[cat]!==undefined ? xNum(xGetPath(SEED, sch.sheets.Profile.fields[afs[cat]].path)) : 0;
          var load=anchor?mround(anchor*(0.5+rnd()*0.5),sch.conflict_policy.round_step_kg):Math.round(rnd()*40)*2.5;
          exs.push({mv:cat+' 动作', cat:cat, mode:mode, load:load, reps:Math.floor(rnd()*15),
            rx:rnd()<0.4?'':('自定'+j+'×3'), targetRpe:6+Math.round(rnd()*8)/2, rpe:rnd()<0.3?null:5+Math.round(rnd()*10)/2,
            done:rnd()<0.5?1:0, notes:rnd()<0.3?'带, 逗号"和引号"与换行':'',
            row:(first[days[di]]||9)+j});
        }
        dayObj[days[di]]={exercises:exs, bio:{}, post:{}, title:'', readiness:'', bw:st.profile.bw};
      }
      dayObj.auxDays=(SEED.aux||[]).map(function(){ return [false,false,false,false,false,false,false]; });
      st.weeks[String(w)]=dayObj;
    }
    xFreezeExtraWeeks(st, SEED.weeks||{});
    var p=xStateToPlanDict(st);
    var v=validatePlanDict(p,{strictConstraints:false});
    var back=xPlanDictToState(p,false,clone(SEED));
    var p2=xStateToPlanDict(back);
    var back2=xPlanDictToState(p2,false,clone(SEED));
    var p3=xStateToPlanDict(back2);
    var geoBad=[], seen={};
    p.Workouts.forEach(function(r){
      var d=r[rc.day], f=first[d];
      if(f===undefined){ geoBad.push('未知日 '+String(d)); return; }
      var rv=xInt(r[rc.row]);
      if(rv===null||rv<f||rv>=f+12) geoBad.push(d+' 行 '+xCellKey(r[rc.row])+' 不在 '+f+'..'+(f+11));
      var key=r[rc.week]+'|'+d+'|'+rv;
      if(seen[key]) geoBad.push('重复 (week,day,row) '+key); seen[key]=1;
    });
    var blk=0; (st.structure.blocks||[]).forEach(function(b){ blk+=(+b.workWeeks||0)+(+b.deloadWeeks||0); });
    out.push({seed:sd, total:total, days:days.length, sm:seedMax, blk:blk, pw:xNum(st.profile.planWeeks),
      inactive:(st.structure.inactiveWeeks||[]).slice(),
      errors:v.errors, warnings:v.warnings.length, rows:p.Workouts.length,
      d12:classify(cmp(p,p2)), d23:classify(cmp(p2,p3)), geo:geoBad, rowsB:p2.Workouts.length,
      holes:holeCount(p)+holeCount(p2)+holeCount(p3),
      weeksBack:Object.keys(back.weeks).length, backInactive:(back.structure.inactiveWeeks||[]).slice()});
  });
  return JSON.stringify(out);
})`;
/* E 段参照：e1RM 与三个系数在 harness 里独立写第二遍，段位用一张表外的区间表算。
   系数常数照官方表独立录入 —— 页面里抄错一个位就会被逐点差异抓到；多项式刻意保持与页面
   同样的嵌套（Horner）顺序，浮点没有结合律，这里要测的是常数与钳制/归零/两位小数，
   不是加括号的方式。 */
function e1rmRef(load, reps, rpe, targetRpe) {
  const L = +load || 0, R = +reps || 0, P = +rpe || 0;
  if (!(L > 0) || !(R > 0)) return 0;
  /* 与页面 effRpeOf 同构：1–4.99 夹到 5；5–10 原样；空/0/负数视为未记录。
     两者都没有 RPE 时按无 RPE 的 Epley 原式（rir=0），不补默认值。 */
  const usable = (v) => v >= 5 && v <= 10;
  const T = +targetRpe;
  const eff = (P >= 1 && P < 5) ? 5 : (usable(P) ? P : (usable(T) ? T : null));
  const rir = eff === null ? 0
    : (10 - eff > 5 ? 5 : (10 - eff < 0 ? 0 : 10 - eff));
  const repCap = R > 12 ? 12 : R;
  return Math.round(L * (1 + (repCap + rir) / 30) * 10) / 10;
}
/* IPF 系数表（GL，2020 版，2020-05-01 启用）：键 = 性别_装备_项，与页面 GL_COEF 同源不同抄。 */
const GL_REF = {
  M_CL_PL: [1199.72839, 1025.18162, 0.00921], M_EQ_PL: [1236.25115, 1449.21864, 0.01644],
  M_CL_BP: [320.98041, 281.40258, 0.01008], M_EQ_BP: [381.22073, 733.79378, 0.02398],
  F_CL_PL: [610.32796, 1045.59282, 0.03048], F_EQ_PL: [758.63878, 949.31382, 0.02435],
  F_CL_BP: [142.40398, 442.52671, 0.04724], F_EQ_BP: [221.82209, 357.00377, 0.02937]
};
function glRef(total, bw, gender, equip, isBench) {
  const T = +total || 0, B = +bw || 0;
  /* 与页面 GL_BW_FLOOR 同一口径：男子 40 / 女子 35 以下不给分。 */
  if (B < (gender === 'F' ? 35 : 40)) return 0;
  const key = (gender === 'F' ? 'F' : 'M') + '_' + (equip === 'equipped' ? 'EQ' : 'CL') +
    '_' + (isBench ? 'BP' : 'PL');
  const c = GL_REF[key] || GL_REF.M_CL_PL;
  const d = c[0] - c[1] * Math.exp(-c[2] * B);
  return d <= 0 ? 0 : +(T * 100 / d).toFixed(2);
}
const DOTS_REF = {
  M: [-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093],
  F: [-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -0.0000010706]
};
const WILKS_REF = {
  M: [47.46178854, 8.472061379, 0.07369410346, -0.001395833811, 7.07665973070743e-6, -1.20804336482315e-8],
  F: [-125.4255398, 13.71219419, -0.03307250631, -0.001050400051, 9.38773881462799e-6, -2.3334613884954e-8]
};
function poly(c, bw) {
  let s = 0;
  for (let i = c.length - 1; i >= 0; i--) s = c[i] + bw * s;   /* 与页面同序嵌套 */
  return s;
}
function dotsRef(total, bw, gender) {
  const T = +total || 0;
  const B = Math.max(40, Math.min(gender === 'F' ? 150 : 210, +bw || 0));
  const s = poly(DOTS_REF[gender === 'F' ? 'F' : 'M'], B);
  return s <= 0 ? 0 : +(T * 500 / s).toFixed(2);
}
function wilksRef(total, bw, gender) {
  const T = +total || 0;
  const B = Math.max(40, Math.min(gender === 'F' ? 150.95 : 200.95, +bw || 0));
  const s = poly(WILKS_REF[gender === 'F' ? 'F' : 'M'], B);
  return s <= 0 ? 0 : +(T * 600 / s).toFixed(2);
}
/* 段位区间表第二份：只写边界与步长（max 无读者，已删），星级与下一颗星门槛按定义重算。 */
const RANK_REF = [['bronze', 0, 9], ['silver', 45, 3], ['gold', 60, 3],
  ['diamond', 75, 3], ['master', 90, 2]];
function glRankRef(gl) {
  const s = Math.max(0, +gl || 0);
  let t = RANK_REF[0];
  for (let i = 0; i < RANK_REF.length; i++) if (s >= RANK_REF[i][1]) t = RANK_REF[i];
  const stars = Math.min(5, Math.floor((s - t[1]) / t[2]) + 1);
  const next = (t[0] === 'master' && stars === 5) ? null : +(t[1] + stars * t[2]).toFixed(2);
  return { id: t[0], stars: stars, nextStarGl: next,
    deltaNext: next === null ? 0 : Math.max(0, +(next - s).toFixed(2)) };
}

/* ============================ C 段：CSV 协议与往返 ============================
   CSV 是冻结的 26 列交换协议（禁区：改列），这一段不测「协议能不能改」，测的是
   列序列名与协议字面一致、逗号/引号/换行/emoji/空值五种脏写法写得出去也读得回来、
   真账本的每一条记录都是满 26 格、导出件重新导入零跳过。脏值在 harness 侧写，
   探针只调页面那套读写，不自己拼 CSV。 */
const C_DIRTY = [
  { movement: '深蹲, 宽距起步', notes: '带, 逗号', rx_text: '3×5' },
  { movement: '卧推"贴胸"', notes: '引号"和,逗号"混排', rx_text: '"4×6"' },
  { movement: '硬拉\n二段式', notes: '第一行\n第二行\n第三行', rx_text: '2×3' },
  { movement: '箱蹲 🙂 表情', notes: 'emoji 🙂🎉 与中文备注', rx_text: '×' },
  { movement: null, notes: undefined, rx_text: '' }
];

const C_PROBE = `(function(dirty){
  var base={schema_ver:'1', record_type:'EXERCISE', week:3, day:'A', row_idx:9, date:'2026-11-02',
            mode:'Top.Single', category:'SQ', load_kg:100, target_rpe:8, last_reps:5, done:0};
  var mk=function(d){ var o={}; Object.keys(base).forEach(function(k){ o[k]=base[k]; });
    Object.keys(d).forEach(function(k){ o[k]=d[k]; }); return o; };
  var iMv=CSV_COLS.indexOf('movement'), iNotes=CSV_COLS.indexOf('notes'),
      iRx=CSV_COLS.indexOf('rx_text'), iRow=CSV_COLS.indexOf('row_idx');
  /* 1) 行级：写出后按行解析，必须还是 26 格，三个脏列落回自己的列位 */
  var rows=dirty.map(function(d){
    var line=csvRow(mk(d)), cells=csvParseLine(line);
    return {n:cells.length, mv:cells[iMv], notes:cells[iNotes], rx:cells[iRx],
            phys:line.split('\\n').length};
  });
  /* 2) 文本级：表头 + 五行（含带换行的格子）整份交给 csvParse */
  var text=CSV_HEAD+'\\n'+dirty.map(function(d){ return csvRow(mk(d)); }).join('\\n');
  var pr=csvParse(text), badParse=[];
  for(var i=0;i<pr.length;i++){
    /* 记录数一旦多于脏值条数（引号里的换行把一条劈成两半就是这种），要说成「多了一条」而不是让探针崩在越界下标上 */
    if(i>=dirty.length){ badParse.push('第 '+(i+1)+' 条无源脏值：解析出 '+pr.length+' 条，应 '+dirty.length+' 条'); continue; }
    ['movement','notes','rx_text'].forEach(function(c){
      var want=dirty[i][c]===null||dirty[i][c]===undefined?'':String(dirty[i][c]);
      if(pr[i][c]!==want) badParse.push(i+'.'+c+'='+JSON.stringify(pr[i][c]));
    });
  }
  /* 3) 端到端：把第三种脏值（换行）塞进当前账本的一个动作，整本导出再读回 */
  var saved=clone(state);
  var keys=activeWeekKeys();
  var wk=state.weeks[keys[0]];
  var firstDay=dayIds().filter(function(d){ return wk && wk[d] && (wk[d].exercises||[]).length; })[0];
  var injected=false;
  if(wk && wk[firstDay]){
    wk[firstDay].exercises.push({mv:dirty[2].movement, cat:'SQ', mode:'Top.Single', load:100,
      reps:5, rx:dirty[2].rx_text, targetRpe:8, rpe:null, done:0, notes:dirty[2].notes, row:900});
    injected=true;
  }
  var dump=exportUnifiedCsv();
  var recs=csvRecords(dump), badRec=[];
  recs.forEach(function(r){ var n=csvParseLine(r.t).length; if(n!==CSV_COLS.length) badRec.push(r.n+':'+n); });
  var all=csvParse(dump), tally={};
  all.forEach(function(r){ tally[r.record_type]=(tally[r.record_type]||0)+1; });
  var mvBack=null, notesBack=null, dirtyRec=null;
  recs.forEach(function(r){ var c=csvParseLine(r.t);
    if(c[iRow]==='900'){ dirtyRec={n:c.length, mv:c[iMv], notes:c[iNotes], rx:c[iRx]}; } });
  all.forEach(function(r){ if(r.row_idx==='900'){ mvBack=r.movement; notesBack=stripCsvMarkers(r.notes); } });
  /* 4) 自己的导出件重新导入：跳过数必须为 0，四类必收记录都在 */
  var imp=importUnifiedCsv(dump);
  var weeksAfter=Object.keys(state.weeks).length;
  state=saved; renderAll();
  return JSON.stringify({
    cols:CSV_COLS.length, names:CSV_COLS.slice(), head:CSV_HEAD,
    headJoin:CSV_COLS.join(',')===CSV_HEAD, first:CSV_COLS[0], second:CSV_COLS[1], last:CSV_COLS[25],
    rows:rows, parseN:pr.length, badParse:badParse,
    dumpHead:dump.replace(/^\\uFEFF/,'').split('\\r\\n')[0], dumpBom:dump.charCodeAt(0)===0xFEFF,
    dumpCrlf:dump.indexOf('\\r\\n')>0, dumpTypes:tally, dumpRows:all.length,
    recBad:badRec, injected:injected, mvBack:mvBack, notesBack:notesBack, dirtyRec:dirtyRec,
    impOk:imp.ok, impStats:imp.stats, impErrors:imp.errors.slice(0,4),
    weeksBefore:Object.keys(saved.weeks).length, weeksAfter:weeksAfter});
})`;

/* ============================ A 段：归档环 ============================
   归档是「只增不改、环形淘汰」的本地计划库：最多 8 条、单条 ≤320KB、整片 ≤512KB，
   六表缺一张的条目一律不收。这一段拿真计划压环，再拿坏分片测读侧的「宁可不存」。 */
const A_PROBE = `(function(){
  var out={};
  var seedPlan=xStateToPlanDict(clone(SEED));
  var tagged=function(tag){ var p=clone(seedPlan); p.Profile.push({field:'logicv_tag', value:tag}); return p; };
  archiveClear();
  out.startCount=archiveList().length;
  out.pushes=[];
  for(var i=1;i<=12;i++){
    var r=archivePush(tagged('L'+i), {source:'logicv', label:'L'+i, totalWeeks:i});
    out.pushes.push({ok:r.ok, count:r.count===undefined?-1:r.count, dropped:(r.dropped||[]).length,
                     bytes:r.bytes, entryBytes:r.entryBytes, reason:r.reason||''});
  }
  out.labels=archiveList().map(function(it){ return it.label; });
  out.count=archiveList().length;
  var latest=archiveLatest();
  out.latestLabel=latest?latest.label:null;
  out.getEqual=latest?JSON.stringify(archiveGet(latest.id).plan)===JSON.stringify(tagged('L12')):false;
  out.getMissing=archiveGet('pa-no-such-id')===null;
  var onDisk=localStorage.getItem(LS_ARCHIVE)||'';
  out.tagsOnDisk=(onDisk.match(/logicv_tag/g)||[]).length;
  /* 超过单条上限：拒收，环长不变 */
  var pad=''; while(pad.length<ARCHIVE_ENTRY_CAP+4000) pad+='x';
  var big=clone(seedPlan); big.Profile.push({field:'pad', value:pad});
  var before=archiveList().length;
  var r4=archivePush(big, {source:'logicv', label:'BIG'});
  out.big={ok:r4.ok===false, reason:r4.reason, entryBytes:r4.bytes, need:ARCHIVE_ENTRY_CAP,
           before:before, after:archiveList().length};
  /* 坏分片 1：不是 JSON —— 按空归档处理，且不许改写磁盘原文 */
  var junk='{ 这不是 JSON';
  localStorage.setItem(LS_ARCHIVE, junk); _archiveCache=null;
  var s5=loadPlanArchive();
  out.corrupt={n:s5.items.length, warnYes:!!s5.warn, rawSame:localStorage.getItem(LS_ARCHIVE)===junk};
  /* 坏分片 2：是 JSON，但条目只有两张表 —— 条目丢弃、原文保留、给出提示 */
  var part=JSON.stringify({v:ARCHIVE_V, items:[{id:'pa-x', at:1, source:'logicv', label:'半件',
                              plan:{Profile:[], Blocks:[]}}]});
  localStorage.setItem(LS_ARCHIVE, part); _archiveCache=null;
  var s6=loadPlanArchive();
  out.partial={n:s6.items.length, warnYes:!!s6.warn, rawHas:(localStorage.getItem(LS_ARCHIVE)||'').indexOf('pa-x')>=0};
  /* 清场：环与缓存都回到进入 A 段之前 */
  localStorage.removeItem(LS_ARCHIVE); _archiveCache=null;
  out.afterClear={n:loadPlanArchive().items.length, warn:archiveWarn(),
                  gone:localStorage.getItem(LS_ARCHIVE)===null};
  out.readonly=READONLY;
  out.caps={max:ARCHIVE_MAX_ITEMS, entry:ARCHIVE_ENTRY_CAP, shard:ARCHIVE_CAP_BYTES};
  return JSON.stringify(out);
})`;

/* ---------- harness 侧的其余参照 ---------- */
/* P 段目标重量：整杆常见值 + 0.25 全域（凑不凑得出整数格）+ 1.25 细分 + 越界与脏值。 */
function pTargets() {
  const out = [], seen = {};
  const add = (v) => { const r = Math.round(v * 1000) / 1000; if (!seen[r]) { seen[r] = 1; out.push(r); } };
  [-100, -20, -0.001, 0, 0.1, 0.25, 0.5, 1, 1.25, 2.5, 2.675, 10, 20, 20.1, 22.5, 25, 37.5,
   40, 40.5, 42.5, 45, 47.5, 50, 60, 61.625, 62.3, 65, 70, 80, 82.5, 90, 92.5, 95, 100, 102.5,
   110, 120, 125, 135, 140, 142.5, 150, 160, 170, 175, 180, 190, 200, 210, 220, 225, 230, 240,
   250, 260, 270, 275, 280, 290, 300, 317.5, 320, 350, 400, 500].forEach(add);
  for (let v = 0.25; v <= 25.25; v += 0.25) add(v);
  for (let v = 10; v <= 62.5; v += 1.25) add(v);
  [11.11, 23.45, 45.678, 66.6, 88.88, 137.53125].forEach(add);
  return out;
}
/* 热身定义式：空杆 ×10 起，之后 50/70/85% 就近到步长倍数、不得低于空杆、与空杆同重的档不重复。 */
function warmRef(load, bar) {
  const rows = [[bar, '×10']];
  [[0.5, '×5'], [0.7, '×3'], [0.85, '×1']].forEach(function (p) {
    const w = Math.max(bar, mroundRef(load * p[0], 2.5));
    if (w !== bar) rows.push([w, p[1]]);
  });
  return rows;
}
/* 时间线周区间：按「起始日 + 7×(周-1) 天」算，UTC 计数不受本机夏令时影响 ——
   页面用的是本地时间加毫秒数，在有夏令时的时区会漂一天，这里代表正确的那个答案。 */
function rangeRef(startStr, weekIdx) {
  const d = String(startStr).split('-').map(Number);
  const p2 = (n) => ('0' + n).slice(-2);
  const s = new Date(Date.UTC(d[0], d[1] - 1, d[2]) + (weekIdx - 1) * 7 * 86400000);
  const e = new Date(s.getTime() + 6 * 86400000);
  return p2(s.getUTCMonth() + 1) + '/' + p2(s.getUTCDate()) + '–' +
    p2(e.getUTCMonth() + 1) + '/' + p2(e.getUTCDate());
}
/* JTS 线性分（0–100）定义式：六维、压力/酸痛反向、缺项按 5。
   取值按数值解释（与页面 jtsNum 同），解析不出有限数与缺项同判。 */
/* 六维改版（D14）独立重算：极性与键序取自契约 item_order（sleep↑ stress↓ fatigue↓ soreness↓ motivation↑ energy↑），
   公式与页面写法不同——先各自归一再求均值，归一按 (v−1)/6 / (7−v)/6 后钳到 [0,100]。 */
const JTS_DIMS_REF = [['sleep', false], ['stress', true], ['fatigue', true],
  ['soreness', true], ['motivation', false], ['energy', false]];
const JTS_READY_AT_REF = [90, 75, 60, 45];
const JTS_MIN_FILLED_REF = 3;
function jtsNumRef(x) {
  if (x === null || x === undefined || x === '') return null;
  const v = (typeof x === 'number') ? x : +x;
  return isFinite(v) ? v : null;
}
function jtsNormRef(v, rev) {
  if (v === null) return null;
  const t = Math.max(0, Math.min(1, (v - 1) / 6));
  return Math.max(0, Math.min(100, (rev ? (1 - t) : t) * 100));
}
function jtsDimsRef(sc) {
  return JTS_DIMS_REF.map(function (d) {
    const v = jtsNumRef(sc[d[0]]);
    return [d[0], v, jtsNormRef(v, d[1]), d[1] ? 1 : 0];
  });
}
function jtsScoreRef(sc) {
  let sum = 0, miss = 0, filled = 0;
  jtsDimsRef(sc).forEach(function (x) {
    if (x[1] === null) { miss++; return; }
    sum += x[2]; filled++;
  });
  const R = (filled >= JTS_MIN_FILLED_REF) ? Math.max(0, Math.min(100, Math.round(sum / filled))) : null;
  return { R: R, score: R, missing: miss, filled: filled, confidence: Math.round(filled / 6 * 100) };
}
function jtsBandRef(R, sick) {
  if (sick) return 4;
  if (R === null || !isFinite(+R)) return 1;
  for (let i = 0; i < JTS_READY_AT_REF.length; i++) if (+R >= JTS_READY_AT_REF[i]) return i;
  return 4;
}

/* ============================ 跑 ============================ */
const FN_NEEDED = ['xCellKey', 'xNum', 'xInt', 'xAsBool', 'xDateStr', 'xF1', 'xPyRepr', 'xRound6Py',
  'mround', 'e1rm', 'calcIpfGl', 'calcDots', 'calcWilks2', 'calcGlRank', 'platesPerSide', 'barKg',
  'setBarKg', 'warmups', 'compileTimeline', 'activeWeekKeys', 'xFreezeExtraWeeks', 'xBlankWeeks',
  'computeRecommendedSets', 'stepRecSet', 'resetRecSets', 'getWeekJts', 'jtsCalc', 'jtsCalcV6',
  'jtsToReady', 'csvRow', 'csvEscape', 'csvParseLine', 'csvRecords', 'csvParse', 'exportUnifiedCsv',
  'importUnifiedCsv', 'xStateToPlanDict', 'xPlanDictToState', 'validatePlanDict', 'clone', 'dayIds',
  'archivePush', 'archiveList', 'archiveGet', 'archiveLatest', 'archiveClear', 'archiveWarn',
  'archiveItemOk', 'archiveShardBytes', 'loadPlanArchive', 'writePlanArchive', 'utf8Len', 'proto', 'L'];
const CONST_NEEDED = ['CSV_COLS', 'CSV_HEAD', 'PLATES', 'BAR_OPTIONS', 'COLLAR_KG', 'GL_COEF',
  'GL_RANKS', 'READY', 'PLAN_SCHEMA', 'SEED', 'state', 'LS_ARCHIVE', 'ARCHIVE_V',
  'ARCHIVE_ENTRY_CAP', 'ARCHIVE_CAP_BYTES', 'ARCHIVE_MAX_ITEMS', 'JTS_DIMS'];

let chrome = null, tmp = null;
async function main() {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'rpl-logicv-'));

  /* N 段期望值：先让 Python 把归一化串算好，页面只负责给出同一批串。 */
  const nPayload = { values: N_VALUES, steps: N_STEPS };
  const nFile = path.join(tmp, 'numfmt.json');
  fs.writeFileSync(nFile, JSON.stringify(nPayload));
  const nWant = JSON.parse(py([path.join('tools', 'xlsx_parity.py'), 'numfmt', nFile]));

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
      { expression: '!!(state&&state.lib&&typeof platesPerSide==="function"&&typeof csvRecords==="function")',
        returnByValue: true })
      .then(r => r.result && r.result.value).catch(() => false);
    if (ready) break;
    await new Promise(r => setTimeout(r, 300));
  }

  const SECT = { s: 'bootstrap' };
  const call = (probe, ...args) =>
    evalIn(ws, id, probe + '(' + args.map(a => JSON.stringify(a)).join(',') + ')');
  try {
    /* ---------------- A0：入口点名 ---------------- */
    SECT.s = 'A0';
    const a0 = JSON.parse(await evalIn(ws, id, `(function(){
      var f=${JSON.stringify(FN_NEEDED)}, c=${JSON.stringify(CONST_NEEDED)};
      var missF=f.filter(function(n){ try{ return typeof eval(n)!=='function'; }catch(e){ return true; } });
      var missC=c.filter(function(n){ try{ return typeof eval(n)==='undefined'; }catch(e){ return true; } });
      return JSON.stringify({missF:missF, missC:missC, ro:READONLY, lang:state.lang});
    })()`));
    T('A0 逻辑入口点名到齐（' + FN_NEEDED.length + ' 函数 + ' + CONST_NEEDED.length +
      ' 常量）且非只读', a0.missF.length === 0 && a0.missC.length === 0 && a0.ro === false,
      '缺函数 ' + (a0.missF.join(',') || '无') + ' / 缺常量 ' + (a0.missC.join(',') || '无') +
      ' / READONLY ' + a0.ro + ' / lang ' + a0.lang);

    /* ---------------- N：数值与格式对 Python ---------------- */
    SECT.s = 'N1';
    N_KEYS = N_VALUES.map(v => (v === null ? 'null' : typeof v === 'string' ? JSON.stringify(v) : String(v)));
    const nGot = JSON.parse(await evalIn(ws, id,
      N_RUN + '(' + JSON.stringify(N_VALUES) + ',' + JSON.stringify(N_STEPS) + ')'));
    const SERIES = [['cellkey', 'xCellKey 归一化串'], ['num', 'xNum（数字解析）'],
      ['int', 'xInt（整数解析）'], ['bool', 'xAsBool（布尔解析）'],
      ['datestr', 'xDateStr（日期列写法）'], ['f1', 'xF1（一位小数半进位）']];
    SERIES.forEach(([key, label], i) => {
      SECT.s = 'N' + (i + 1);
      const d = diffList(nWant[key], nGot[key], 4);
      T('N' + (i + 1) + ' ' + label + '：' + N_VALUES.length + ' 个值与 plan_xlsx 逐格相同',
        d.n === 0, d.n ? d.n + ' 处不同 → ' + d.samples.join(' ; ') : '0 处差异');
    });
    SECT.s = 'N7';
    const mKeys = Object.keys(nWant.mround);
    const mbad = [];
    mKeys.forEach(k => {
      const d = diffList(nWant.mround[k], (nGot.mround || {})[k] || [], 2);
      if (d.n) mbad.push('step ' + k + '：' + d.n + ' 处 → ' + d.samples.join(' ; '));
    });
    T('N7 mround：' + mKeys.length + ' 个步长 × ' + N_VALUES.length + ' 值与 plan_xlsx 同结果',
      mbad.length === 0 && mKeys.length === N_STEPS.length, mbad.slice(0, 3).join(' / ') || '0 处差异');
    SECT.s = 'N8';
    T('N8 xCellKey 幂等（归一化串再过一次不变）', nGot.idem === true, String(nGot.idem));
    SECT.s = 'N9';
    const lenOk = SERIES.every(([k]) => (nGot[k] || []).length === N_VALUES.length &&
      (nWant[k] || []).length === N_VALUES.length) &&
      mKeys.length === N_STEPS.length &&
      mKeys.every(k => nWant.mround[k].length === N_VALUES.length &&
        ((nGot.mround || {})[k] || []).length === N_VALUES.length);
    T('N9 定义域闭合：契约六种列类型的标量全覆盖，两侧条数一致（' +
      SERIES.map(([k]) => (nGot[k] || []).length).join('/') + '）', lenOk,
      '值 ' + N_VALUES.length + ' 个 / 步长 ' + N_STEPS.length + ' 个 / Python 侧无抛错');

    /* ---------------- P：配片 DP 与热身阶梯 ---------------- */
    SECT.s = 'P1';
    const targets = pTargets();
    const pp = JSON.parse(await call(P_PROBE, P_BARS, P_PLATES, targets));
    const collar = pp.collarPair;
    const res = pp.res;
    const dpOf = (r) => dpMinPlates(r.perSide, pp.plateKgs);
    const blocked = (r) => !!r.collars && r.t < r.bar + collar;
    T('P1 片组常量：页面 PLATES 就是 25→0.25 的十一档',
      JSON.stringify(pp.plateKgs) === JSON.stringify(P_PLATES), pp.plateKgs.join(','));
    T('P2 杆重常量：BAR_OPTIONS 与用例同集（' + pp.barOpts.join('/') + '），夹板一对 ' + collar + 'kg',
      JSON.stringify(pp.barOpts) === JSON.stringify(P_BARS), pp.barOpts.join(','));
    SECT.s = 'P3';
    const lose = res.filter(r => { const d = dpOf(r); return typeof d === 'number' && r.n > d; });
    T('P3 贪心不输最优：' + res.length + ' 组（杆重×赛扣×目标）的片数一律 ≥ 完全背包最少片数',
      lose.length === 0, lose.length ? lose.length + ' 组被 DP 打败 → ' +
        lose.slice(0, 3).map(r => r.bar + 'kg 杆 目标 ' + r.t + '：贪心 ' + r.n + ' 片 vs DP ' + dpOf(r)).join(' ; ')
        : '0 组');
    /* 余数是「还剩多少没配上」的展示值，页面按三位小数写（Math.round(rem*1000)/1000），
       所以片和+余 与逐侧需求的差最坏就是半分位 0.0005，再加浮点尾差 —— 用 6e-4 而不是 1e-6。 */
    const sumBad = res.filter(r => Math.abs(r.kg.reduce((a, b) => a + b, 0) + r.rem - r.perSide) > 6e-4);
    T('P4 配得平：每组的片重加余数都等于逐侧需求（误差 <6e-4，余数本身按三位小数展示）',
      sumBad.length === 0, sumBad.length ? sumBad.length + ' 组不平 → ' +
        sumBad.slice(0, 3).map(r => r.bar + '/' + r.t + '：片和 ' + r.kg.reduce((a, b) => a + b, 0) +
          ' + 余 ' + r.rem + ' ≠ ' + r.perSide).join(' ; ') : '0 组');
    SECT.s = 'P5';
    const solvBad = res.filter(r => {
      if (blocked(r)) return false;
      const d = dpOf(r);
      return r.exact !== (typeof d === 'number');
    });
    T('P5 exact 与「凑不凑得出 0.25 整数格」同判（DP 可解 ⇔ exact）',
      solvBad.length === 0, solvBad.length ? solvBad.length + ' 组判反 → ' +
        solvBad.slice(0, 3).map(r => r.bar + '/' + r.t + '：exact=' + r.exact + ' DP=' + JSON.stringify(dpOf(r))).join(' ; ')
        : '0 组');
    const structBad = res.filter(r => {
      for (let i = 1; i < r.kg.length; i++) if (r.kg[i] > r.kg[i - 1]) return true;
      return r.kg.some(k => pp.plateKgs.indexOf(k) < 0);
    });
    T('P6 贪心结构：逐侧片从重到轻不回升，且只用片组里的重量',
      structBad.length === 0, structBad.length ? structBad.slice(0, 3).map(r => r.bar + '/' + r.t + ' ' + r.kg.join('+')).join(' ; ') : '0 组');
    SECT.s = 'P7';
    const collarBad = res.filter(r => {
      const should = blocked(r), has = r.note.indexOf('赛扣') >= 0;
      if (should !== has) return true;
      return should && !(r.n === 0 && r.exact === false && r.note.indexOf(String(r.bar + collar)) >= 0);
    });
    T('P7 赛扣分支：总重不足 bar+' + collar + ' 时只出提示、不出片，且说明里带的门槛数字对得上',
      collarBad.length === 0, collarBad.length ? collarBad.slice(0, 3).map(r => r.bar + '/' + r.t + ' note=' + r.note).join(' ; ')
        : res.filter(blocked).length + ' 组命中该分支');
    const belowBad = res.filter(r => {
      const should = !r.collars && r.t < r.bar, has = r.note.indexOf('空杆') >= 0;
      if (should !== has) return true;
      return should && !(r.n === 0 && r.exact === true && r.rem === 0);
    });
    T('P8 低于空杆：不开赛扣时 t<bar 一律 exact=true + 空片 + 「低于空杆」说明',
      belowBad.length === 0, belowBad.length ? belowBad.slice(0, 3).map(r => r.bar + '/' + r.t + ' note=' + r.note + ' exact=' + r.exact).join(' ; ') : '0 组');
    SECT.s = 'P9';
    const junkExp = [20, 20, 20, 20, 20, 20, 20, 20, 25];
    T('P9 非法杆重一律回落 20kg（0/12/21/-5/40.5/"20"/null/NaN 八个脏值），合法值 25 才收',
      JSON.stringify(pp.junk) === JSON.stringify(junkExp), pp.junk.join(','));
    const bar = pp.barNow;
    const warmBad = [];
    targets.forEach((t, i) => {
      const want = t > 0 ? warmRef(t, bar) : [[0, '×15'], [0, '×8'], [0, '×5']];
      const got = pp.warm[i];
      if (JSON.stringify(got) !== JSON.stringify(want)) warmBad.push(t + '：' + JSON.stringify(got) + ' ≠ ' + JSON.stringify(want));
    });
    const wnegBad = pp.wneg.filter(a => !(a.length === 3 && a.every(x => x[0] === 0)));
    T('P10 热身阶梯 = 空杆 + 50/70/85% 就近到 2.5kg（且不低过空杆、与空杆同重的档不重复）；' +
      '零/负/NaN/null 走自重三档',
      warmBad.length === 0 && wnegBad.length === 0,
      warmBad.length ? warmBad.slice(0, 3).join(' ; ') : '杆重 ' + bar + 'kg / 自重样本 ' + pp.wneg.length + ' 组');
    SECT.s = 'P11';
    T('P11 探针跑完不留痕：当前场地库存原样、当前杆重仍在选项内',
      pp.restored === true && pp.barOpts.indexOf(pp.barNow) >= 0,
      'barNow ' + pp.barNow + ' / restored ' + pp.restored);

    /* ---------------- E：e1RM / 系数 / 段位 ---------------- */
    SECT.s = 'E1';
    const ee = JSON.parse(await evalIn(ws, id, E_PROBE + '()'));
    const eBad = [];
    ee.e.forEach(r => {
      const w = e1rmRef(r[0], r[1], r[2], r[3]);
      if (Math.abs(w - r[4]) > 1e-9) eBad.push(r.slice(0, 4).join('/') + '：参照 ' + w + ' ≠ 页面 ' + r[4]);
    });
    T('E1 e1RM（Epley+RPE，>12 次软截断）与定义式逐点相同 · ' + ee.e.length + ' 点',
      eBad.length === 0, eBad.length ? eBad.length + ' 点不同 → ' + eBad.slice(0, 3).join(' ; ') : '0 点差异');
    const zeroBad = ee.e.filter(r => (!(r[0] > 0) || !(r[1] > 0)) && r[4] !== 0);
    const idx4 = new Map();
    ee.e.forEach(r => idx4.set(JSON.stringify(r.slice(0, 4)), r[4]));
    let capBad = 0, rpeBad = 0;
    /* RPE 单调性只在有重量的行上成立：L≤0 恒归零，10 与 5 同为 0 不是反例 */
    [20, 60, 100, 142.5, 200].forEach(L => ['', 4, 5, 6.5, 7, 9.5, 10, null].forEach(P =>
      [0, 5, 8, 10, null].forEach(TR => {
        const a = idx4.get(JSON.stringify([L, 12, P, TR])), b = idx4.get(JSON.stringify([L, 13, P, TR]));
        if (a !== undefined && b !== undefined && a !== b) capBad++;
        const lo = idx4.get(JSON.stringify([L, 5, 10, TR])), hi = idx4.get(JSON.stringify([L, 5, 5, TR]));
        if (lo !== undefined && hi !== undefined && !(hi > lo)) rpeBad++;
      })));
    T('E2 e1RM 边界：非正重量/次数归零（' + zeroBad.length + ' 处违例）、' +
      '13 次与 12 次同值、RPE 越低估值越高',
      zeroBad.length === 0 && capBad === 0 && rpeBad === 0,
      '截断不一致 ' + capBad + ' / 单调反例 ' + rpeBad + ' / 归零反例 ' + zeroBad.length);
    /* G3：1–4.99 夹到 5，是平台不是跳变（4.9 与 5 必须同值） */
    let clampBad = 0;
    [20, 60, 100, 142.5, 200].forEach(L => [0, 5, null].forEach(TR => {
      const a = idx4.get(JSON.stringify([L, 5, 4, TR]));
      const b = idx4.get(JSON.stringify([L, 5, 5, TR]));
      const c = idx4.get(JSON.stringify([L, 5, 4.9, TR]));
      if (a !== b || c !== b) clampBad++;
    }));
    T('E2b RPE 夹取：1–4.99 与同点 5 同值（曲线左侧是平台，不跳变）',
      clampBad === 0, '反例 ' + clampBad);
    /* G2：唯一判定口 effRpeOf 的分支表 */
    const er = JSON.parse(await evalIn(ws, id,
      'JSON.stringify([effRpeOf(4.5,null),effRpeOf(0,null),effRpeOf(-1,null),effRpeOf(null,null),effRpeOf("",null),effRpeOf(10.5,7),effRpeOf(null,5),effRpeOf(null,11),effRpeOf(7,null)])'));
    T('E2c effRpeOf 分支：1–4.99→5；空/null/0/负数仍为未记录；target 只在显式 5–10 时生效',
      er[0].rpe === 5 && er[0].clamped === true && er[0].src === 'actual'
      && er[1].rpe === null && er[2].rpe === null && er[3].rpe === null && er[4].rpe === null
      && er[5].rpe === 7 && er[5].src === 'target'
      && er[6].rpe === 5 && er[6].src === 'target'
      && er[7].rpe === null && er[8].rpe === 7,
      JSON.stringify(er));
    /* G4：逐点验证「所有 1–4.99 与同点 5 相同」，覆盖整张探针矩阵 */
    const g4Bad = ee.e.filter(r => {
      const P = +r[2];
      if (!(P >= 1 && P < 5)) return false;
      return r[4] !== idx4.get(JSON.stringify([r[0], r[1], 5, r[3]]));
    });
    T('E2d 逐点 G4：' + ee.e.filter(r => +r[2] >= 1 && +r[2] < 5).length +
      ' 个 RPE<5 点与同点 5 完全同值', g4Bad.length === 0, '反例 ' + g4Bad.length);
    SECT.s = 'E3';
    const glBad = [];
    ee.gl.forEach(r => {
      const w = glRef(r[0], r[1], r[2], r[3], r[4]);
      if (Math.abs(w - r[5]) > 1e-9) glBad.push(r.slice(0, 5).join('/') + '：参照 ' + w + ' ≠ 页面 ' + r[5]);
    });
    T('E3 IPF GL 与官方系数表独立重算逐点相同 · ' + ee.gl.length + ' 点（性别×装备×项×总量×体重）',
      glBad.length === 0, glBad.length ? glBad.length + ' 点不同 → ' + glBad.slice(0, 3).join(' ; ') : '0 点差异');
    /* G1：系数常量逐位比对（24 个数字） */
    const COEF_EXP = '{"M_CL_PL":[1199.72839,1025.18162,0.00921],"M_EQ_PL":[1236.25115,1449.21864,0.01644],'
      + '"M_CL_BP":[320.98041,281.40258,0.01008],"M_EQ_BP":[381.22073,733.79378,0.02398],'
      + '"F_CL_PL":[610.32796,1045.59282,0.03048],"F_EQ_PL":[758.63878,949.31382,0.02435],'
      + '"F_CL_BP":[142.40398,442.52671,0.04724],"F_EQ_BP":[221.82209,357.00377,0.02937]}';
    const coefGot = await evalIn(ws, id, 'JSON.stringify(GL_COEF)');
    T('E3b GL 系数表 24 个常量与 2020 版（2020-05-01 启用）独立值逐位相同',
      coefGot === COEF_EXP, coefGot === COEF_EXP ? '8 组 × 3 = 24 个' : '常量不同 → ' + coefGot.slice(0, 80));
    /* G8：判档用未取整真值；显示才取两位小数 */
    T('E3c 判档用未取整真值：44.9972→青铜 5★，显示 45.00→白银 1★',
      ee.g8[0] < 45 && ee.g8[0] > 44.99 && Math.abs(ee.g8[1] - 45) < 1e-9
      && ee.g8[2] === 'bronze' && ee.g8[3] === 5 && ee.g8[4] === 'silver',
      JSON.stringify(ee.g8));
    const glKey = (a) => JSON.stringify([a[0], a[1], a[2], a[3], a[4]]);
    const glMap = new Map();
    ee.gl.forEach(r => glMap.set(glKey(r), r[5]));
    const fbBad = ee.gl.filter(r => {
      if ((r[2] === 'X' || r[2] === null) && r[5] !== glMap.get(glKey([r[0], r[1], 'M', r[3], r[4]]))) return true;
      if ((r[3] === 'weird' || r[3] === null) && r[5] !== glMap.get(glKey([r[0], r[1], r[2], 'classic', r[4]]))) return true;
      return false;
    });
    const floorBad = ee.gl.filter(r => {
      const g = r[2] === 'F' ? 'F' : 'M', B = +r[1] || 0, fl = g === 'F' ? 35 : 40;
      return B < fl && r[5] !== 0;
    });
    let monoBad = 0;
    [[0, 'M', 'classic', false], [500, 'F', 'equipped', true], [600.5, 'M', 'classic', true]].forEach(base => {
      let prev = null;
      ee.gl.filter(r => r[0] === base[0] && r[2] === base[1] && r[3] === base[2] && r[4] === base[3]
        && r[1] >= (r[2] === 'F' ? 35 : 40))
        .forEach(r => { if (prev !== null && r[5] > prev) monoBad++; prev = r[5]; });
    });
    T('E4 GL 边界：体重低于性别下限归零（男 40 / 女 35，' + floorBad.length + ' 处违例）、' +
      '未知性别/装备回落男·classic·全举，同总量下随体重不升',
      fbBad.length === 0 && floorBad.length === 0 && monoBad === 0,
      '回落反例 ' + fbBad.length + ' / 低于下限反例 ' + floorBad.length + ' / 单调反例 ' + monoBad);
    /* G7：下限四个点必须恰好卡在 40 / 35 */
    const g7 = [glMap.get(glKey([500, 39.99, 'M', 'classic', false])),
      glMap.get(glKey([500, 40, 'M', 'classic', false])),
      glMap.get(glKey([500, 34.99, 'F', 'classic', false])),
      glMap.get(glKey([500, 35, 'F', 'classic', false]))];
    T('E4b GL 性别下限：男 39.99 不给分 / 40 起给分；女 34.99 不给分 / 35 起给分',
      g7[0] === 0 && g7[1] > 0 && g7[2] === 0 && g7[3] > 0, g7.join('/'));
    SECT.s = 'E5';
    const dotsBad = [];
    ee.dots.forEach(r => {
      const w = dotsRef(r[0], r[1], r[2]);
      if (Math.abs(w - r[3]) > 1e-9) dotsBad.push(r.slice(0, 3).join('/') + '：参照 ' + w + ' ≠ 页面 ' + r[3]);
    });
    const dotsMap = new Map();
    ee.dots.forEach(r => dotsMap.set(JSON.stringify(r.slice(0, 3)), r[3]));
    const dotsClampBad = ee.dots.filter(r => {
      const cap = r[2] === 'F' ? 150 : 210, floor = 40;
      const bound = r[1] > cap ? cap : (r[1] < floor ? floor : r[1]);
      return r[3] !== dotsMap.get(JSON.stringify([r[0], bound, r[2]]));
    });
    T('E5 DOTS 与官方系数独立重算逐点相同（' + ee.dots.length + ' 点），体重按 40..' +
      (210) + ' / 女子 40..150 钳到边界同值',
      dotsBad.length === 0 && dotsClampBad.length === 0,
      dotsBad.length ? dotsBad.slice(0, 2).join(' ; ') : '钳制反例 ' + dotsClampBad.length);
    /* G5：DOTS 上下界逐点——149.99/150/150.01 与 209.99/210/210.01 三连必须同值 */
    const dsB = (T, B, g) => dotsMap.get(JSON.stringify([T, B, g]));
    T('E5b DOTS 钳制逐点：女 149.99=150=150.01、男 209.99=210=210.01',
      dsB(500, 149.99, 'F') === dsB(500, 150, 'F') && dsB(500, 150.01, 'F') === dsB(500, 150, 'F')
      && dsB(500, 209.99, 'M') === dsB(500, 210, 'M') && dsB(500, 210.01, 'M') === dsB(500, 210, 'M'),
      [dsB(500, 149.99, 'F'), dsB(500, 150, 'F'), dsB(500, 150.01, 'F'), dsB(500, 209.99, 'M'), dsB(500, 210, 'M'), dsB(500, 210.01, 'M')].join('/'));
    SECT.s = 'E6';
    const wilBad = [];
    ee.wil.forEach(r => {
      const w = wilksRef(r[0], r[1], r[2]);
      if (Math.abs(w - r[3]) > 1e-9) wilBad.push(r.slice(0, 3).join('/') + '：参照 ' + w + ' ≠ 页面 ' + r[3]);
    });
    const wilMap = new Map();
    ee.wil.forEach(r => wilMap.set(JSON.stringify(r.slice(0, 3)), r[3]));
    const wilClampBad = ee.wil.filter(r => {
      const cap = r[2] === 'F' ? 150.95 : 200.95;
      const bound = r[1] > cap ? cap : (r[1] < 40 ? 40 : r[1]);
      return r[3] !== wilMap.get(JSON.stringify([r[0], bound, r[2]]));
    });
    T('E6 Wilks 2 与官方系数独立重算逐点相同（' + ee.wil.length + ' 点），体重钳到 40..200.95 / 女子 ..150.95',
      wilBad.length === 0 && wilClampBad.length === 0,
      wilBad.length ? wilBad.slice(0, 2).join(' ; ') : '钳制反例 ' + wilClampBad.length);
    /* G6：Wilks 2 钳制逐点——上下界三连同值 */
    const wsB = (T, B, g) => wilMap.get(JSON.stringify([T, B, g]));
    T('E6b Wilks 2 钳制逐点：女 150.94=150.95=150.96、男 200.94=200.95=200.96',
      wsB(500, 150.94, 'F') === wsB(500, 150.95, 'F') && wsB(500, 150.96, 'F') === wsB(500, 150.95, 'F')
      && wsB(500, 200.94, 'M') === wsB(500, 200.95, 'M') && wsB(500, 200.96, 'M') === wsB(500, 200.95, 'M'),
      [wsB(500, 150.94, 'F'), wsB(500, 150.95, 'F'), wsB(500, 150.96, 'F'), wsB(500, 200.94, 'M'), wsB(500, 200.95, 'M'), wsB(500, 200.96, 'M')].join('/'));
    SECT.s = 'E7';
    const rankBad = [];
    ee.rank.forEach(r => {
      const w = glRankRef(r[0]);
      if (r[1] !== w.id || r[2] !== w.stars || String(r[4]) !== String(w.nextStarGl) ||
        Math.abs((+r[5]) - w.deltaNext) > 1e-9)
        rankBad.push(r[0] + '：参照 ' + JSON.stringify([w.id, w.stars, w.nextStarGl, w.deltaNext]) +
          ' ≠ 页面 ' + JSON.stringify([r[1], r[2], r[4], r[5]]));
    });
    T('E7 段位与星级与区间表独立重算逐点相同（' + ee.rank.length + ' 个 GL 值，含 NaN/null/字符串）',
      rankBad.length === 0, rankBad.length ? rankBad.slice(0, 3).join(' ; ') : '0 处差异');
    /* G6（段位部分）：0..500 / 0.01 全扫，区间归属单调、星级与门槛差自洽 */
    let sweepBad = 0, sweepN = 0;
    for (let g = 0; g <= 500; g += 0.01) {
      sweepN++;
      const a = glRankRef(g);
      const g2 = Math.round((g + 1e-9) * 100) / 100;
      const b = glRankRef(g2);
      const ia = RANK_REF.findIndex(t => t[0] === a.id), ib = RANK_REF.findIndex(t => t[0] === b.id);
      if (ib < ia) sweepBad++;
      if (!(a.stars >= 1 && a.stars <= 5)) sweepBad++;
      if (a.nextStarGl !== null && !(a.nextStarGl > g)) sweepBad++;
      if (a.nextStarGl !== null && !(a.deltaNext >= 0 && a.deltaNext <= 9.0000001)) sweepBad++;
    }
    T('E7b 段位全扫 0..500（步长 0.01）：区间只升不降、stars∈1..5、nextGL>当前、Δ∈[0,step] · ' + sweepN + ' 点',
      sweepBad === 0, '反例 ' + sweepBad);
    const tiersExp = JSON.stringify(RANK_REF.map(r => [r[0], r[1], r[2]]));
    const selfBad = ee.rank.filter(r => {
      const stars = r[2], next = r[4], delta = r[5];
      if (!(stars >= 1 && stars <= 5)) return true;
      if (r[3] !== '★'.repeat(stars) + '☆'.repeat(5 - stars)) return true;
      if (!new RegExp(' ' + stars + '★$').test(r[6])) return true;
      if (next === null) return delta !== 0;
      const g = Math.max(0, +r[0] || 0);
      return Math.abs(+(next - g).toFixed(2) - delta) > 1e-9;
    });
    T('E8 段位表常量与 harness 第二份表逐字段相同；starsStr 恒 5 个符号、labelZh 以「N★」结尾、' +
      '门槛差 = nextGL − 当前 GL',
      JSON.stringify(ee.tiers) === tiersExp && selfBad.length === 0,
      JSON.stringify(ee.tiers) === tiersExp ? '自洽反例 ' + selfBad.length : '表不同 → ' + JSON.stringify(ee.tiers));

    /* ---------------- J：JTS 全域与恢复驱动组数 ---------------- */
    SECT.s = 'J1';
    const jj = JSON.parse(await evalIn(ws, id, J_PROBE + '()'));
    const near = (a, b) => Math.abs(a - b) < 1e-12;
    const fBad = [];
    jj.calc.forEach(r => {
      const sc = JSON.parse(r[1]);
      const gd = JSON.parse(r[13]);
      const rd = jtsDimsRef(sc);
      if (gd.length !== rd.length) { fBad.push(r[0] + '：维度数 ' + gd.length + '≠' + rd.length); return; }
      for (let i = 0; i < rd.length; i++) {
        if (gd[i][0] !== rd[i][0]) { fBad.push(r[0] + '：键序 ' + gd[i][0] + '≠' + rd[i][0]); break; }
        if (gd[i][3] !== rd[i][3]) { fBad.push(r[0] + '#' + rd[i][0] + ' 极性 ' + gd[i][3] + '≠' + rd[i][3]); break; }
        const pv = gd[i][2], rv = rd[i][2];
        if (!(pv === null ? rv === null : (rv !== null && near(pv, rv))))
          { fBad.push(r[0] + '#' + rd[i][0] + ' 参照 ' + rv + ' ≠ 页面 ' + pv); break; }
      }
    });
    T('J1 JTS 六维归一（D14）：逐维独立重算 1–7 → 0–100 正/反向、键序与极性与页面逐点相同 · ' + jj.calc.length + ' 组样本',
      fBad.length === 0, fBad.length ? fBad.length + ' 组不同 → ' + fBad.slice(0, 2).join(' ; ') : '0 组差异');
    const sBad = [];
    jj.calc.forEach(r => {
      const sc = JSON.parse(r[1]); const w = jtsScoreRef(sc);
      const pR = (r[2] === null ? null : r[2]);
      if (!(pR === null ? w.R === null : pR === w.R) || r[3] !== w.missing || r[4] !== w.filled || r[5] !== w.confidence)
        sBad.push(r[0] + '：参照 ' + JSON.stringify([w.R, w.missing, w.filled, w.confidence]) +
          ' ≠ 页面 ' + JSON.stringify([pR, r[3], r[4], r[5]]));
    });
    T('J2 R=已填维均值（未填剔除、不当中性 5）与缺项/置信度逐点相同，缺项+已填=6',
      sBad.length === 0, sBad.length ? sBad.length + ' 组不同 → ' + sBad.slice(0, 2).join(' ; ') : '0 组差异');
    SECT.s = 'J3';
    const boundBad = jj.calc.filter(r => {
      const R = r[2];
      const rOk = (R === null) || (Number.isInteger(R) && R >= 0 && R <= 100);
      return !rOk || !(r[5] >= 0 && r[5] <= 100) || !(r[6] >= 0.55 && r[6] <= 1.25) ||
        !(r[7] >= 0.75 && r[7] <= 1.25) || !(r[9] >= 0 && r[9] <= 0.08) || !(r[10] >= 0 && r[10] <= 0.06) ||
        r[3] + r[4] !== 6;
    });
    const crsBad = jj.calc.filter(r => r[12] !== 'undef');
    T('J3 全域界限（D14）：R 为空或 0–100 整数、confidence∈0–100、recMult∈[0.55,1.25]、recBase∈[0.75,1.25]、' +
      'B_gpp≤0.08、F_gpp≤0.06、缺项+已填=6，且 CRS 字段已退役',
      boundBad.length === 0 && crsBad.length === 0,
      '越界 ' + boundBad.length + ' / CRS 残留 ' + crsBad.length);
    const rdBad = [];
    jj.calc.forEach(r => {
      const want = jtsBandRef(r[2], r[11] === 1);
      if (r[8] !== want) rdBad.push(r[0] + '：R=' + r[2] + ' sick=' + r[11] + '→' + r[8] + '(应 ' + want + ')');
    });
    const bdBad = [];
    jj.band.forEach(r => { const want = jtsBandRef(r[0], !!r[1]); if (r[2] !== want) bdBad.push(r[0] + '/sick' + r[1] + '→' + r[2] + '(应 ' + want + ')'); });
    T('J4 档位取自 ready_at=[90,75,60,45]：jtsBandOf 逐点与独立重算一致（含边界 44.9/45/89.9/90）、R=null 归默认档 1、sick 强制末档 4',
      rdBad.length === 0 && bdBad.length === 0 && jj.band.every(r => r[2] >= 0 && r[2] <= 4),
      rdBad.length ? rdBad.slice(0, 4).join(' ; ') : bdBad.length ? bdBad.slice(0, 4).join(' ; ') : jj.band.length + ' 个档位探针点 + ' + jj.calc.length + ' 组逐点全覆盖');
    SECT.s = 'J5';
    const BANDS = ['submv', 'under', 'optimal', 'high', 'over'];
    const recBad = jj.weeks.filter(r => {
      const trip = [[3, 4, 5, 6], [8, 9, 10, 11], [12, 13, 14, 15]];
      for (const t of trip) {
        if (!(r[t[0]] >= 1 && r[t[0]] <= r[t[1]] && r[t[1]] < r[t[2]])) return true;
        if (r[t[3]] !== r[t[1]]) return true;
      }
      return r[7] !== false || !(r[2] >= 0 && r[2] <= 4) || BANDS.indexOf(r[17]) < 0 ||
        !(typeof r[18] === 'number' && r[18] > 0 && r[18] <= 2) || !isFinite(r[16]) ||
        typeof r[1] !== 'string' || !r[1];
    });
    T('J5 恢复驱动推荐组数 W1–16：min≥1 ≤ rec < max（max 至少比 rec 多 1）、无手调时 cur=rec 且 isCustom=false、' +
      'readyIdx 0–4、band 在五个区间内、容量系数为正',
      recBad.length === 0, recBad.length ? recBad.slice(0, 2).map(r => 'W' + r[0] + ' ' + JSON.stringify(r.slice(3, 8))).join(' ; ')
        : jj.weeks.length + ' 周全过 / deload 周 ' + jj.weeks.filter(r => r[1] === 'Deload').length + ' 个');
    SECT.s = 'J6';
    const stepOk = jj.step[0][1] === jj.step[0][2] && jj.step[0][2] >= 10 &&
      jj.step[1][1] === 1 &&
      jj.step[2][1] === JSON.stringify({ sq: null, bp: null, dl: null });
    T('J6 手调组数钳在 1–max(10, 模型 MRV)（+9 顶到模型上限、−99 压到 1），一键恢复把三栏都清回 null',
      stepOk, jj.step.map(x => x[0] + '=' + x[1] + (x[2] !== undefined ? '(上限' + x[2] + ')' : '')).join(' / '));
    T('J7 旧版日级 JTS 键自动迁移：读到 "5_B" 后按 W5 返回同一份六维样本，并写回新键',
      jj.legacy.keys === 6 && jj.legacy.sleep === 9 && jj.legacy.newKey === true,
      JSON.stringify(jj.legacy));
    const rows = jj.calc.filter(r => /^S\d+$/.test(String(r[0])));
    T('J8 六维锚点（D14）：全最佳=100 / 全 5 分（3 正 3 反）=50 / 恰 3 维（1 正 2 反）=44 且缺项 3、全最差=0、空样本与仅 2 维 R=null 且缺项+已填=6、sick 强制末档',
      rows.length >= 7 && rows[0][2] === 100 && rows[1][2] === 0 && rows[2][2] === null && rows[3][2] === 50 &&
      rows[3][4] === 6 && rows[6][2] === 44 && rows[6][3] === 3 &&
      rows[4][2] === null && rows[4][3] === 4 && rows[0][3] === 0 && rows[2][4] === 0 &&
      rows[5][2] === 100 && rows[5][8] === 4 && rows[5][11] === 1,
      'S0..S6=' + rows.slice(0, 7).map(r => String(r[2]) + '/m' + r[3]).join(' '));

    /* ---------------- S：时间线 property 与冻结对账 ---------------- */
    SECT.s = 'S1';
    const sCases = [
      { name: '三块 4+1', start: '2026-11-02', blocks: mkBlocks([4, 4, 4], [1, 1, 1]) },
      { name: '单块 1+1', start: '2026-11-02', blocks: mkBlocks([1], [1]) },
      { name: '无减载 12 周', start: '2026-01-05', blocks: mkBlocks([12], [0]) },
      { name: '跨年', start: '2026-12-30', blocks: mkBlocks([3], [1]) },
      { name: '缺起始日走默认', start: '', blocks: mkBlocks([2], [1]) },
      { name: '闰日起点 2028-02-21', start: '2028-02-21', blocks: mkBlocks([4], [0]) },
      { name: '空块表', start: '2026-11-02', blocks: [] },
      { name: '零周块', start: '2026-11-02', blocks: mkBlocks([0], [0]) },
      { name: '混合 6+6 只有第一块减载', start: '2027-03-02', blocks: mkBlocks([6, 6], [1, 0]) }
    ];
    const ss = JSON.parse(await call(S_PROBE, sCases));
    const seqBad = [];
    sCases.forEach((c, i) => {
      const want = [], block = [], deload = [], bi = [];
      c.blocks.forEach((b, k) => {
        for (let x = 0; x < b.workWeeks; x++) { block.push(b.id); deload.push(false); bi.push(k); }
        for (let x = 0; x < b.deloadWeeks; x++) { block.push(b.id); deload.push(true); bi.push(k); }
      });
      for (let w = 1; w <= block.length; w++) want.push(w);
      const g = ss.tl[i];
      if (g.n !== want.length || JSON.stringify(g.weeks) !== JSON.stringify(want) ||
        JSON.stringify(g.block) !== JSON.stringify(block) ||
        JSON.stringify(g.deload) !== JSON.stringify(deload) ||
        JSON.stringify(g.bi) !== JSON.stringify(bi))
        seqBad.push(c.name + '：' + JSON.stringify({ n: g.n, want: want.length }));
    });
    T('S1 compileTimeline 的周号恒为 1..N 连续、块归属与减载位与块表定义一致（9 例，含空表与零周块）',
      seqBad.length === 0, seqBad.length ? seqBad.join(' ; ') : sCases.reduce((a, c) => a + c.blocks.reduce((x, b) => x + b.workWeeks + b.deloadWeeks, 0), 0) + ' 周覆盖');
    const rangeBad = [];
    sCases.forEach((c, i) => {
      const st = c.start || '2026-11-02';
      ss.tl[i].range.forEach((r, k) => {
        const w = rangeRef(st, k + 1);
        if (r !== w) rangeBad.push(c.name + ' W' + (k + 1) + '：' + r + ' ≠ ' + w);
      });
    });
    T('S2 每周日期区间串 = 起始日 + 7×(周−1) 天（跨月 / 跨年 / 闰日 / 缺起始日用默认都对得上）',
      rangeBad.length === 0, rangeBad.length ? rangeBad.slice(0, 4).join(' ; ') : '共 ' + ss.tl.reduce((a, x) => a + x.n, 0) + ' 条区间');
    SECT.s = 'S3';
    const seedMax = ss.seedMax;
    const frzBad = [];
    ss.freeze.forEach(x => {
      const want = [];
      for (let w = x.total + 1; w <= seedMax; w++) want.push(w);
      /* 冻结把 total 之后的种子周原样克隆回来，所以最后一种子周恒在；total 已越过种子末尾时无事可冻 */
      if (x.kept !== seedMax || JSON.stringify(x.inactive) !== JSON.stringify(want) ||
        x.wLastSame !== true) frzBad.push('total ' + x.total + '：kept ' + x.kept +
          ' inactive ' + JSON.stringify(x.inactive) + ' 应 ' + JSON.stringify(want) +
          ' 第 ' + seedMax + ' 周逐字保留 ' + x.wLastSame);
    });
    T('S3 决策 D4 冻结：超出新周数的既有周不删，原样克隆回来并登记 inactiveWeeks（种子 ' + seedMax +
      ' 周，7 个新总周数）',
      frzBad.length === 0, frzBad.length ? frzBad.slice(0, 3).join(' ; ') : '第 ' + seedMax + ' 周内容逐字保留 = ' + ss.freeze.every(x => x.wLastSame));
    const actBad = ss.act.filter(x => {
      const wantN = Math.min(x.total, seedMax);   /* 账本里只存在种子的 1..seedMax 周，周数写更大也不会凭空多出周 */
      return x.n !== wantN || x.first !== '1' || x.last !== String(wantN) || x.clean !== true;
    });
    T('S4 activeWeekKeys 与 inactiveWeeks 严格互补：条数 = min(新总周数, 种子周数)、首 ' + "'1'" +
      ' 尾 = 该值，且不含任何冻结周',
      actBad.length === 0, actBad.length ? actBad.map(x => 'total ' + x.total + ' → ' + x.n).join(' ; ')
        : ss.act.map(x => x.total).join('/'));

    /* ---------------- F：随机账本 ⇄ 六表往返 ---------------- */
    SECT.s = 'F1';
    const ff = JSON.parse(await call(F_PROBE, F_SEEDS));
    const fErr = ff.filter(x => x.errors.length);
    const fMax = Math.max.apply(null, ff.map(x => x.total));
    T('F1 ' + ff.length + ' 份随机账本（周数 1..' + fMax + '、每日 0–4 个动作、脏备注）导出六表后契约 0 error（warning ' +
      ff.reduce((a, x) => a + x.warnings, 0) + ' 条全是四条约束规则）',
      fErr.length === 0, fErr.length ? '种子 ' + fErr[0].seed + ' → ' + fErr[0].errors.slice(0, 2).join(' / ')
        : '随机件共 ' + ff.reduce((a, x) => a + x.rows, 0) + ' 行 Workouts');
    const fGeo = ff.filter(x => x.geo.length || x.holes);
    T('F2 行几何守恒：每个 Workouts 行的 row_idx 落在该日的 12 行窗内、(week,day,row) 全局唯一，' +
      '且六表数组稠密（length 里没有空洞行）',
      fGeo.length === 0, fGeo.length ? '种子 ' + fGeo[0].seed + ' → ' +
        fGeo[0].geo.concat(['空洞 ' + fGeo[0].holes]).slice(0, 2).join(' / ')
        : ff.reduce((a, x) => a + x.rows, 0) + ' 行零违例');
    const f12 = ff.filter(x => x.d12.hard.length + x.d12.softBad.length);
    const rxTotal = ff.reduce((a, x) => a + x.d12.soft, 0);
    T('F3 导出 → 回装 → 再导出逐格相同（' + ff.length + ' 份随机件，含百分比/小数重量、自定义处方与多语备注）；' +
      '只许可两类补格：空处方格按模式补种子处方、空格按契约 defaults 补默认值，补出的串逐格对得上',
      f12.length === 0, f12.length ? '种子 ' + f12[0].seed + '：' +
        f12[0].d12.hard.concat(f12[0].d12.softBad).slice(0, 3).join(' ; ')
        : '0 格硬差异 / 补格 ' + rxTotal + ' 处 / Workouts 行数 导出 ' +
          ff.reduce((a, x) => a + x.rows, 0) + ' → 回装再导出 ' + ff.reduce((a, x) => a + x.rowsB, 0));
    const f23 = ff.filter(x => x.d23.hard.length + x.d23.softBad.length + x.d23.soft);
    T('F4 第二次往返是不动点（换算本身收敛，不逐轮漂移；补过处方之后不再有格子改动）',
      f23.length === 0, f23.length ? '种子 ' + f23[0].seed + '：' +
        f23[0].d23.hard.concat(f23[0].d23.softBad).slice(0, 3).join(' ; ') : '0 格差异');
    const fBack = ff.filter(x => {
      const want = []; for (let w = x.total + 1; w <= x.sm; w++) want.push(w);
      return x.blk !== x.total || x.pw !== x.total ||
        x.weeksBack !== x.sm || JSON.stringify(x.backInactive) !== JSON.stringify(want) ||
        JSON.stringify(x.inactive) !== JSON.stringify(want);
    });
    T('F5 回装闭合与 D4 复原：块表求和与 plan_weeks 都等于新总周数；回装后账本正好是种子的 1..' +
      '末周，冻结周恰好是 新总周数+1..末周（导出侧与回装侧登记的一样）',
      fBack.length === 0, fBack.length ? fBack.slice(0, 2).map(x => '种子 ' + x.seed + ' total ' + x.total +
        ' 块和 ' + x.blk + ' plan_weeks ' + x.pw + ' 回装 ' + x.weeksBack + ' 周 / 冻结 ' +
        JSON.stringify(x.backInactive) + ' 应 ' + JSON.stringify(x.inactive)).join(' ; ')
        : '总周数 ' + ff.map(x => x.total).join('/'));

    /* ---------------- C：CSV 协议与往返 ---------------- */
    SECT.s = 'C1';
    const cc = JSON.parse(await call(C_PROBE, C_DIRTY));
    /* 括号不能省：`'a' + 'b'.split(',')` 只对最后一段字面量做 split，整个表达式仍是字符串 */
    const NAMES = ('schema_ver,record_type,week,day,row_idx,date,mode,category,movement,load_kg,rx_text,' +
      'target_rpe,last_reps,actual_rpe,e1rm_kg,done,notes,readiness,bw_kg,sleep_h,rhr_bpm,hrv_ms,' +
      'fuel_strategy,exec_status,duration_min,aux_week_mask').split(',');
    T('C1 交换协议字面未漂移：26 列、列名与列序逐字相同、首两列是 schema_ver/record_type、末列 aux_week_mask、' +
      'CSV_HEAD 就是列名拼接',
      cc.cols === 26 && NAMES.length === 26 && cc.head === NAMES.join(',') &&
      JSON.stringify(cc.names) === JSON.stringify(NAMES) &&
      cc.first === 'schema_ver' && cc.second === 'record_type' && cc.last === 'aux_week_mask' && cc.headJoin === true,
      cc.cols + ' 列 / 首 ' + cc.first + ' / 末 ' + cc.last);
    const wantOf = (i, k) => (C_DIRTY[i][k] === null || C_DIRTY[i][k] === undefined ? '' : String(C_DIRTY[i][k]));
    const rowBad = [];
    cc.rows.forEach((r, i) => {
      if (r.n !== 26) rowBad.push('第 ' + (i + 1) + ' 行 ' + r.n + ' 格');
      ['movement', 'notes', 'rx_text'].forEach(k => {
        const got = k === 'movement' ? r.mv : k === 'notes' ? r.notes : r.rx;
        if (got !== wantOf(i, k)) rowBad.push('第 ' + (i + 1) + ' 行 ' + k + '=' + JSON.stringify(got));
      });
    });
    const multiline = cc.rows[2].phys > 1;
    SECT.s = 'C2';
    T('C2 行级脏值：逗号 / 双引号 / 换行 / emoji / 空值五种写法经 csvRow→csvParseLine 原样回来，' +
      '每行仍是 26 格（换行那行的确被引号包住跨了 ' + cc.rows[2].phys + ' 个物理行）',
      rowBad.length === 0 && multiline, rowBad.length ? rowBad.slice(0, 4).join(' ; ') : '5 行 × 26 格');
    SECT.s = 'C3';
    T('C3 文本级往返：表头 + 五条脏记录整份交给 csvParse，恰好回来 5 条记录（跨物理行的引号格子不把记录劈开）' +
      '且三个脏列逐字相同',
      cc.parseN === C_DIRTY.length && cc.badParse.length === 0,
      cc.badParse.length ? cc.badParse.slice(0, 4).join(' ; ') : '解析出 ' + cc.parseN + ' 条');
    const need = ['PROFILE', 'STRUCTURE', 'TELEMETRY', 'EXERCISE'];
    SECT.s = 'C4';
    T('C4 全账本导出结构：带 Excel BOM、行间 CRLF、首行是 CSV_HEAD、四类必收记录都在、' +
      '每一条记录（含跨行的那条）都是满 26 格',
      cc.dumpBom === true && cc.dumpCrlf === true && cc.dumpHead === cc.head &&
      need.every(t => (cc.dumpTypes[t] || 0) > 0) && cc.recBad.length === 0,
      '记录 ' + cc.dumpRows + ' 条 / BOM ' + cc.dumpBom + ' / 首行 ' + JSON.stringify(cc.dumpHead) +
      ' / 类型 ' + JSON.stringify(cc.dumpTypes) +
      (cc.recBad.length ? ' / 空格数 ' + cc.recBad.slice(0, 3).join(' ; ') : ''));
    SECT.s = 'C5';
    T('C5 端到端：把带换行的动作名与备注塞进账本再整本导出，读回的 movement / notes 逐字相同',
      cc.injected === true && cc.dirtyRec && cc.dirtyRec.n === 26 &&
      cc.mvBack === wantOf(2, 'movement') && cc.notesBack === wantOf(2, 'notes'),
      cc.injected ? '回读 ' + JSON.stringify(cc.mvBack) + ' / 备注 ' + JSON.stringify(cc.notesBack) : '(没能注入动作)');
    SECT.s = 'C6';
    T('C6 自己的导出件重新导入：零跳过、四类记录条数与导出时一致、周键数不变',
      cc.impOk === true && cc.impStats.skipped === 0 && cc.impStats.profile === 1 &&
      cc.impStats.structure === 1 && cc.impStats.exercises === (cc.dumpTypes.EXERCISE || 0) &&
      cc.weeksAfter === cc.weeksBefore,
      '动作 ' + cc.impStats.exercises + ' / telemetry ' + cc.impStats.telemetry +
      ' / 跳过 ' + cc.impStats.skipped + ' / 错误 ' + cc.impErrors.slice(0, 2).join(' ; '));

    /* ---------------- A：归档环与坏分片 ---------------- */
    SECT.s = 'A1';
    const aa = JSON.parse(await evalIn(ws, id, A_PROBE + '()'));
    const cap = aa.caps.max;
    const pushBad = [];
    aa.pushes.forEach((r, i) => {
      if (!r.ok) pushBad.push('第 ' + (i + 1) + ' 次压入被拒：' + r.reason);
      if (r.count > cap) pushBad.push('第 ' + (i + 1) + ' 次后条数 ' + r.count + ' 越 ' + cap + ' 条上限');
      if (r.bytes > aa.caps.shard) pushBad.push('第 ' + (i + 1) + ' 次后整片 ' + r.bytes + ' 越字节上限');
    });
    const droppedSum = aa.pushes.reduce((x, r) => x + r.dropped, 0);
    T('A1 环形淘汰守界：12 次压入全部收下，任一次后条数 ≤' + cap + '、整片 ≤' +
      (aa.caps.shard / 1024).toFixed(0) + 'KB，累计淘汰 = 12 − 最终条数',
      pushBad.length === 0 && aa.count <= cap && aa.startCount === 0 &&
      droppedSum === 12 - aa.count && aa.count === aa.labels.length,
      pushBad.length ? pushBad.slice(0, 3).join(' ; ') : '最终 ' + aa.count + ' 条 / 单条 ' +
        (aa.pushes[0].entryBytes / 1024).toFixed(1) + 'KB / 整片 ' +
        (aa.pushes[aa.pushes.length - 1].bytes / 1024).toFixed(1) + 'KB');
    const orderBad = aa.labels[0] !== 'L12' ||
      aa.labels.map(x => +x.slice(1)).some((v, i, arr) => i > 0 && v >= arr[i - 1]);
    T('A2 新条目永远在环首（archiveLatest = 最新一次压入），列表按新旧降序',
      orderBad === false && aa.latestLabel === 'L12' && aa.labels.length === aa.count,
      aa.labels.join(' → '));
    T('A3 按 id 取回的计划与压入时逐字节相同，未知 id 返回 null 而不是半条',
      aa.getEqual === true && aa.getMissing === true,
      '取回逐字节 ' + aa.getEqual + ' / 缺 id → null ' + aa.getMissing);
    T('A4 单条超过 ' + (aa.caps.entry / 1024).toFixed(0) + 'KB 直接拒收（reason=too_big），环长与盘上条目数都不变',
      aa.big.ok === true && aa.big.reason === 'too_big' && aa.big.entryBytes > aa.big.need &&
      aa.big.before === aa.big.after && aa.tagsOnDisk === aa.count,
      '条目 ' + (aa.big.entryBytes / 1024).toFixed(0) + 'KB / 拒收前 ' + aa.big.before + ' 条 → 拒收后 ' + aa.big.after + ' 条');
    T('A5 归档分片不是 JSON：按空归档处理并给提示，磁盘原文一字不改（不静默覆盖用户数据）',
      aa.corrupt.n === 0 && aa.corrupt.warnYes === true && aa.corrupt.rawSame === true,
      '条目 ' + aa.corrupt.n + ' / 提示 ' + (aa.corrupt.warnYes ? '有' : '无') + ' / 原文保留 ' + aa.corrupt.rawSame);
    T('A6 条目六表不全（只有 Profile/Blocks）：整条丢弃并给提示，原文里的 id 仍在；清场后环与盘都回到进段前',
      aa.partial.n === 0 && aa.partial.warnYes === true && aa.partial.rawHas === true &&
      aa.afterClear.n === 0 && aa.afterClear.gone === true,
      '半件丢弃 ' + aa.partial.n + ' 条 / 提示 ' + (aa.partial.warnYes ? '有' : '无') + ' / 清场 ' + JSON.stringify(aa.afterClear));
  } catch (e) {
    if (e && e.stack) console.error('Z0 现场栈：\n' + e.stack);
    T('Z0 断言块在 ' + SECT.s + ' 段中途抛错（其后断言未执行）', false,
      String((e && e.message) || e).replace(/\s+/g, ' ').slice(-300));
  }

  /* 断言总数闸门：与 v2v / v3v / xlsxv 同一理由 —— 少一条就是少一条，不能装作还是全绿。
     58 = A0 点名 1 + N 数值格式 9（六条函数序列 + mround + 幂等 + 定义域）
          + P 配片热身 11（两个常量 + DP 最优/配平/exact/结构 + 两个说明分支 + 杆重回落
            + 热身阶梯 + 无留痕）+ E 系数 8（e1RM 逐点/边界、GL 逐点/边界、DOTS、Wilks、
            段位逐点、段位自洽与常量表）+ J 恢复 8（三因子、线性分、界限、阈值、
            推荐组数、手调钳制、legacy 迁移、缺项与反向）+ S 时间线 4（周序、区间、
            冻结、activeWeekKeys）+ F 往返 5（契约、行几何、往返、不动点、回装闭合）
          + C 交换 6（协议、行级、文本级、导出结构、端到端、重导入）
          + A 归档 6（环界、顺序、取回、超限、坏 JSON、缺表条目）。 */
  const EXP_N = 67;
  if (PASS + FAIL !== EXP_N) {
    LINES.push('FAIL  Z1 断言总数漂移（实到 ' + (PASS + FAIL) + '，应 ' + EXP_N + '）');
    FAIL++;
  }
  console.log(LINES.join('\n'));
  const nP = LINES.filter(l => l.indexOf('PASS') === 0).length;
  const nF = LINES.filter(l => l.indexOf('FAIL') === 0).length;
  console.log('\n== logicv 汇总: ' + nP + ' PASS / ' + nF + ' FAIL （共 ' + (nP + nF) + ' 项）==');
  ws.close();
  const cleaned = await tmpclean.close(chrome, tmp, FAIL > 0);
  if (FAIL > 0) console.log('现场保留在 ' + tmp);
  else if (!cleaned) console.log('临时目录没清掉：' + tmp);
  process.exit(FAIL > 0 ? 1 : 0);
}

main().catch(async e => {
  console.error('logicv 跑飞：' + (e && e.stack || e));
  await tmpclean.close(chrome, tmp);
  process.exit(2);
});
