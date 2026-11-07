#!/usr/bin/env node
// xlsxv.js —— App 内工作簿引擎与 plan_xlsx.py 的逐格对账（C1）
//
// 为什么要单独一套：App 里的 inflate/zip/XML/计划表读写是 Python 那套引擎的第二实现，
// 「看起来能跑」和「每一格都一样」是两件事。fixture 由 tools/xlsx_parity.py 现造，
// 期望值也由它现算，本脚本不写死任何列名、行数或单元格值。
//
//   node tools/xlsxv.js            # 全跑（差异样本直接打在 PASS/FAIL 行尾）
const { spawn, spawnSync } = require('child_process');
const path = require('path');
const os = require('os');
const fs = require('fs');
const tmpclean = require('./tmpclean');

const HERE = __dirname;
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const PY = process.env.PYTHON || 'python';
const FILE = 'file:///' + path.resolve(HERE, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9860 + Math.floor(Math.random() * 15);

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
  if (r.code !== 0) {
    throw new Error(PY + ' ' + args.join(' ') + ' 退出码 ' + r.code + '\n' + (r.out || ''));
  }
  return r.out;
}
function pyRaw(args) {
  const r = spawnSync(PY, args, { cwd: path.resolve(HERE, '..'), encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  return { code: r.status, out: (r.stdout || '') + (r.stderr || '') };
}

// 键 = 表|行序|__row__|列；写侧比对去掉 __row__ 那一段（交出去的计划本来就没有行号）。
// dropEmpty 用于写侧：读回的工作簿把每列都补齐成 ""，而内存里的计划只带显式键 ——
// 空串与缺键在契约里是同一件事，两边都丢掉才可比。
function keyParts(k) { const p = k.split('|'); return p; }
function stripRow(map, dropEmpty) {
  const out = {};
  for (const k in map) {
    if (dropEmpty && map[k] === '') continue;
    const p = keyParts(k); out[p[0] + '|' + p[1] + '|' + p[3]] = map[k];
  }
  return out;
}
function diffCells(a, b, limit) {
  const ka = Object.keys(a), kb = Object.keys(b);
  const onlyA = ka.filter(k => !(k in b)), onlyB = kb.filter(k => !(k in a));
  const changed = ka.filter(k => (k in b) && a[k] !== b[k]);
  const samples = changed.slice(0, limit || 4).map(k => k + '：' + JSON.stringify(a[k]) + ' ≠ ' + JSON.stringify(b[k]));
  onlyA.slice(0, limit || 4).forEach(k => samples.push(k + '：只在一侧 = ' + JSON.stringify(a[k])));
  onlyB.slice(0, limit || 4).forEach(k => samples.push(k + '：只在另一侧 = ' + JSON.stringify(b[k])));
  return { n: changed.length + onlyA.length + onlyB.length, counts: [ka.length, kb.length], samples };
}
function stripVal(v, dropEmpty) { return stripRow(v.cells, dropEmpty); }
/* 顶层不比的两半：种子侧（proto 是 App 装载时 delete 的账本参考库、lib / source 由 Python
   pop、programLib / strategyLib 是只读参考库、schemaVer 是存档戳、auxWarnSeen 是页面一次性提示）
   在 W0 现取的本机侧（页面的 IMPORT_KEEP_KEYS 整份）由页面自己报出。
   名单外的单侧键就是真差异，让断言红 —— 名单不是白名单，它只能由页面的名单变大。 */
const APP_ONLY_SEED = ['proto', 'lib', 'source', 'programLib', 'strategyLib', 'schemaVer', 'auxWarnSeen'];
let APP_ONLY = null;
function stateStrip(s) {
  if (!APP_ONLY) throw new Error('APP_ONLY 还没从页面取到：拒绝用旧抄名单比对（W0 没跑过就是编排错了）');
  /* 展平成「点分路径 → 值串」：null / undefined / '' 在「这一项有没有值」上是同一件事，
     两侧都丢掉才可比。replacer 丢整键会连兄弟字段一起没，必须自写递归。 */
  if (s && typeof s === 'object') APP_ONLY.forEach(k => { delete s[k]; });
  const out = {};
  (function walk(v, p) {
    if (v === null || v === undefined || v === '') return;
    if (Array.isArray(v)) { if (!v.length) return; v.forEach((x, i) => walk(x, p + '.' + i)); return; }
    if (typeof v === 'object') { Object.keys(v).forEach(k => walk(v[k], p ? p + '.' + k : k)); return; }
    out[p] = JSON.stringify(v);
  })(s, '');
  return out;
}

const READ_CELLS = `(function(b64){
  var bin=atob(b64), u8=new Uint8Array(bin.length);
  for(var i=0;i<bin.length;i++) u8[i]=bin.charCodeAt(i);
  var r=planFromXlsxBytes(u8);
  var sch=PLAN_SCHEMA, cells={}, rows={}, order=sch.sheet_order;
  for(var k=0;k<order.length;k++){
    var nm=order[k], cols=sch.sheets[nm].columns, list=r.plan[nm]||[];
    rows[nm]=list.length;
    for(var i=0;i<list.length;i++){
      var row=list[i];
      for(var j=0;j<cols.length;j++){
        var c=cols[j];
        if(Object.prototype.hasOwnProperty.call(row,c)) cells[nm+'|'+i+'|'+row.__row__+'|'+c]=xCellKey(row[c]);
      }
    }
  }
  return JSON.stringify({cells:cells, rows:rows, errors:r.errors,
    val:(function(v){ var x=validatePlanDict(r.plan); return {ok:x.ok, errors:x.errors, warnings:x.warnings}; })()});
})`;

/* 契约校验：把一份计划（JSON 文本）交给页面里那份 validatePlanDict，取回判定三元组。
   Python 侧的期望值由 tools/xlsx_parity.py 用 plan_xlsx.validate_plan_dict 现算，
   error / warning 的**顺序**也逐条比 —— 判定顺序本身就是两边一致性的内容。 */
const VAL = `(function(planJson, strict){
  var r=validatePlanDict(JSON.parse(planJson), {strictConstraints: !!strict});
  return JSON.stringify({ok:r.ok, errors:r.errors, warnings:r.warnings});
})`;

function valDiff(want, got) {
  if (!want || !got) return '一边没拿到判定（want ' + (want ? '有' : '无') + ' / got ' + (got ? '有' : '无') + '）';
  if (want.ok !== got.ok) return 'ok：Python ' + want.ok + ' ≠ App ' + got.ok;
  const one = (key) => {
    const a = want[key] || [], b = got[key] || [];
    if (a.length !== b.length)
      return key + ' 条数 ' + a.length + ' ≠ ' + b.length + ' → ' + JSON.stringify((a.length > b.length ? a : b)[Math.min(a.length, b.length)]);
    for (let i = 0; i < a.length; i++)
      if (a[i] !== b[i]) return key + '[' + i + '] ' + JSON.stringify(a[i]) + ' ≠ ' + JSON.stringify(b[i]);
    return null;
  };
  return one('errors') || one('warnings');
}
function valCount(v) { return v ? ('err ' + v.errors.length + ' / warn ' + v.warnings.length) : '(无)'; }

/* Chrome 的一次性 profile 与 fixture 同在一个 tmp 根，必须一起回收：见 tmpclean.js。 */
let chrome = null, tmp = null;
async function main() {
  tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'rpl-xlsxv-'));
  py([path.join('tools', 'xlsx_parity.py'), 'fixtures', tmp]);
  const exp = JSON.parse(fs.readFileSync(path.join(tmp, 'expect.json'), 'utf8'));

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
  for (let i = 0; i < 40; i++) {
    const ready = await send(ws, id.v, 'Runtime.evaluate',
      { expression: '!!(state&&state.lib&&typeof planFromXlsxBytes==="function")', returnByValue: true })
      .then(r => r.result && r.result.value).catch(() => false);
    if (ready) break;
    await new Promise(r => setTimeout(r, 300));
  }

  const SECT = { s: 'bootstrap' };
  try {
    const lang = await evalIn(ws, id, 'state.lang');
    T('X0 页面就绪且语言为 zh（错误串要逐字比）', lang === 'zh', 'lang=' + lang);
    SECT.s = 'X1';
    const surface = await evalIn(ws, id,
      '["planFromXlsxBytes","xlsxBytesFromPlan","xCellKey","xInflate","xZipWrite","xStateToPlanDict","xPlanDictToState","planFromXlsxFileBytes","importPlanFromXlsxBytes","exportPlanXlsxBytes","xEffectiveOrder","xValidateGear","xApplyGear","xGearFromState","xGearCanonical"].map(function(f){return typeof window[f];}).join(",")');
    T('X1 引擎与换算入口都在（15 个：五表往返 + 版本路由 + Gear 四件套）',
      surface === Array(15).fill('function').join(','), surface);

    // ---- 读侧逐格对账 ----
    const got = {};
    for (const f of exp.fixtures) {
      SECT.s = '读 ' + f;
      const b64 = fs.readFileSync(path.join(tmp, f)).toString('base64');
      got[f] = JSON.parse(await evalIn(ws, id, READ_CELLS + '(' + JSON.stringify(b64) + ')'));
    }
    SECT.s = 'X2';
    for (const f of exp.fixtures) {
      const d = diffCells(exp.expect[f].cells, got[f].cells, 5);
      T('读 ' + f + '：' + Object.keys(exp.expect[f].cells).length + ' 格与 plan_xlsx 一致',
        d.n === 0, d.n ? (d.n + ' 格不同 / Python ' + d.counts[0] + ' vs App ' + d.counts[1] + ' → ' + d.samples.join(' ; ')) : '0 格差异');
      const rowsA = JSON.stringify(exp.expect[f].rows), rowsB = JSON.stringify(got[f].rows);
      T('读 ' + f + '：各表行数一致', rowsA === rowsB, rowsA + ' vs ' + rowsB);
      T('读 ' + f + '：表头对账错误逐字一致',
        JSON.stringify(exp.expect[f].errors) === JSON.stringify(got[f].errors),
        'Python ' + exp.expect[f].errors.length + ' 条 / App ' + got[f].errors.length + ' 条' +
        (got[f].errors.length ? ' → ' + got[f].errors[0] : ''));
    }

    // ---- 语义抽查：不依赖 Python，按 fixture 的构造事实断言 ----
    SECT.s = 'X3';
    const odd = got['odd.xlsx'];
    const oddCells = odd.cells;
    const valOf = (sheet, col, pred) => {
      const out = [];
      for (const k in oddCells) { const p = keyParts(k); if (p[0] === sheet && p[3] === col) out.push(oddCells[k]); }
      return out.filter(pred);
    };
    T('X3.1 富文本分段拼回一整串', valOf('Profile', 'field', v => v.indexOf('富') === 0).length === 1 &&
      valOf('Profile', 'field', v => v === '富文 & 本').length === 1, valOf('Profile', 'field', v => v.indexOf('富') === 0)[0]);
    T('X3.2 自定义 numFmt 的日期数值格 → ISO 日期串', valOf('Profile', 'value', v => v === '2026-11-02').length === 1,
      valOf('Profile', 'value', v => v.indexOf('2026') === 0).join('/'));
    T('X3.2b 共享字符串里的 &#45; 实体转义还原成连字符',
      valOf('Profile', 'field', v => v === '2026-11-02').length === 1,
      valOf('Profile', 'field', v => v.indexOf('2026') === 0).join('/'));
    T('X3.3 布尔格读成真假（不是 0/1 文本）', Object.keys(oddCells).some(k => keyParts(k)[0] === 'Profile' && oddCells[k] === 'FALSE'));
    T('X3.4 只有公式没有缓存值 → 空格子', Object.keys(oddCells).some(k => keyParts(k)[0] === 'Profile' && oddCells[k] === ''));
    T('X3.5 XML 注释里的假标签没被当成格子', !Object.keys(oddCells).some(k => oddCells[k] === 'Z9'));
    /* 表头行里有格子缺 r（靠列计数器顺延）：一旦错位，Profile 就不再被认成竖排（竖排的
       特征是每行都带着各自的源行号，横排则全是 1）、Blocks 的表头对账也会报错 ——
       用这两个后果来证明落位规则跟 openpyxl 一致。 */
    const profileRowNos = {};
    Object.keys(oddCells).forEach(k => { const p = keyParts(k); if (p[0] === 'Profile') profileRowNos[p[2]] = 1; });
    T('X3.6 缺 r 的格子按顺延列落位（Profile 认成竖排 / Blocks 表头零报错）',
      Object.keys(profileRowNos).length === odd.rows.Profile && odd.rows.Profile > 1 &&
      odd.errors.every(e => e.indexOf('Blocks') < 0 && e.indexOf('Profile') < 0),
      'Profile ' + odd.rows.Profile + ' 行 / 行号 ' + Object.keys(profileRowNos).join(',') + ' / 错误 ' + odd.errors.length + ' 条');
    T('X3.7 数字样字符串没有被强转（Blocks 表头行内串还原）',
      Object.keys(oddCells).some(k => keyParts(k)[0] === 'Blocks' && oddCells[k] === '<主项>"周"'));

    const hand = got['hand.xlsx'];
    const SHEET_N = await evalIn(ws, id, 'PLAN_SCHEMA.sheet_order.length');
    T('X3.8 Profile 横排两行也能读成 field|value', hand.rows.Profile === exp.expect['hand.xlsx'].rows.Profile &&
      Object.keys(hand.cells).some(k => keyParts(k)[0] === 'Profile' && hand.cells[k] === 'schema_ver'));
    T('X3.9 契约外的表整体忽略（契约表之外不多不少）',
      Object.keys(hand.rows).length === Number(SHEET_N) &&
      Object.keys(hand.cells).every(k => Object.keys(hand.rows).indexOf(keyParts(k)[0]) >= 0));
    T('X3.10 打乱的表序不影响寻址（按名解析，Workouts 仍是 400 行）',
      hand.rows.Workouts === exp.expect['hand.xlsx'].rows.Workouts && hand.rows.Workouts > 0, hand.rows.Workouts);
    T('X3.11 内建日期格式（numFmtId 14）同样读成 ISO 串',
      Object.keys(hand.cells).some(k => { const p = keyParts(k); return p[0] === 'Profile' && p[3] === 'value' && hand.cells[k] === '2026-11-02'; }));

    // ---- 写侧：App 写出的文件 Python 必须原样读回，并给出同样的契约判定 ----
    SECT.s = 'X4';
    const WRITE = `(function(planJson){ var u8=xlsxBytesFromPlan(JSON.parse(planJson));
      var bin=''; for(var i=0;i<u8.length;i++) bin+=String.fromCharCode(u8[i]); return btoa(bin); })`;
    const errLines = (txt) => txt.split(/\r?\n/).filter(l => l.indexOf('ERROR') === 0).sort().join('\n');
    const cases = [['canonical', exp.canonicalPlan, exp.canonicalCells], ['edge', exp.edgePlan, exp.edgeCells]];
    let canonVal = null;
    for (const [label, planJson, cells] of cases) {
      const b64 = await evalIn(ws, id, WRITE + '(' + JSON.stringify(JSON.stringify(planJson)) + ')');
      const out = path.join(tmp, 'js_' + label + '.xlsx');
      fs.writeFileSync(out, Buffer.from(b64, 'base64'));
      const back = JSON.parse(py([path.join('tools', 'xlsx_parity.py'), 'dump', out]));
      const filled = Object.keys(cells).filter(k => cells[k] !== '').length;
      const d = diffCells(stripRow(cells, true), stripRow(back.cells, true), 5);
      T('写 ' + label + '：Python 读回 ' + filled + ' 个非空格零差异',
        d.n === 0, d.n ? (d.n + ' 格不同 / 期望 ' + d.counts[0] + ' vs 实得 ' + d.counts[1] + ' → ' + d.samples.join(' ; ')) : '0 格差异');
      /* edge 这份计划本身就不合契约（必填列留空），所以判定标准不是「0 error」，
         而是「同一份计划由 openpyxl 写出来会得到一模一样的 error 清单」。 */
      const jsV = pyRaw([path.join('tools', 'plan_xlsx.py'), 'validate', out]);
      const pxV = pyRaw([path.join('tools', 'plan_xlsx.py'), 'validate', path.join(tmp, exp.pyWritten[label])]);
      if (label === 'canonical') canonVal = jsV;
      T('写 ' + label + '：契约判定与 openpyxl 写的同一份计划逐条相同',
        errLines(jsV.out) === errLines(pxV.out) && jsV.code === pxV.code,
        'App 写 error ' + (errLines(jsV.out).match(/ERROR/g) || []).length + ' 条 / openpyxl 写 ' +
        (errLines(pxV.out).match(/ERROR/g) || []).length + ' 条 / 退出码 ' + jsV.code + ' vs ' + pxV.code);
    }
    T('X4c 规范计划由 App 写出后 0 error（openpyxl 与 plan_xlsx 都认这个包）',
      canonVal !== null && errLines(canonVal.out) === '' && canonVal.code === 0,
      canonVal ? canonVal.out.split(/\r?\n/).slice(0, 3).join(' / ') : '(没跑到)');

    // ---- 自洽：自己写的自己读得回来，且逐字节可复现 ----
    SECT.s = 'X5';
    const SELF = `(function(planJson){
      var p=JSON.parse(planJson), u8=xlsxBytesFromPlan(p);
      var r=planFromXlsxBytes(u8), cols=PLAN_SCHEMA.sheet_order, cells={};
      for(var k=0;k<cols.length;k++){ var nm=cols[k], cc=PLAN_SCHEMA.sheets[nm].columns, list=r.plan[nm]||[];
        for(var i=0;i<list.length;i++){ var row=list[i];
          for(var j=0;j<cc.length;j++){ var c=cc[j];
            if(Object.prototype.hasOwnProperty.call(row,c)) cells[nm+'|'+i+'|'+c]=xCellKey(row[c]); } } }
      var u8b=xlsxBytesFromPlan(p), s1='', s2='';
      for(var i=0;i<u8.length;i++) s1+=String.fromCharCode(u8[i]);
      for(var i=0;i<u8b.length;i++) s2+=String.fromCharCode(u8b[i]);
      return JSON.stringify({cells:cells, same:s1===s2, bytes:u8.length});
    })`;
    const selfRead = JSON.parse(await evalIn(ws, id, SELF + '(' + JSON.stringify(JSON.stringify(exp.canonicalPlan)) + ')'));
    const selfCells = {};
    for (const k in selfRead.cells) if (selfRead.cells[k] !== '') selfCells[k] = selfRead.cells[k];
    const dSelf = diffCells(stripRow(exp.canonicalCells, true), selfCells, 4);
    T('X5.1 App 写 → App 读：逐格自洽', dSelf.n === 0, dSelf.n ? dSelf.n + ' 格不同 → ' + dSelf.samples.join(' ; ') : '0 格差异');
    T('X5.2 同一份计划两次导出逐字节相同（时间戳固定）', selfRead.same === true);
    T('X5.3 写出的工作簿非空', selfRead.bytes > 10000, selfRead.bytes + ' B');

    // ---- 坏输入必须响亮地失败，而不是静默给半份计划 ----
    SECT.s = 'X6';
    const badExpr = (bytes) => `(function(){ var b64=${JSON.stringify(bytes)};
       var bin=atob(b64), u8=new Uint8Array(bin.length);
       for(var i=0;i<bin.length;i++) u8[i]=bin.charCodeAt(i);
       try{ var r=planFromXlsxBytes(u8); return 'NO_THROW:'+JSON.stringify(r.errors); }
       catch(e){ return 'THROW:'+e.message; } })()`;
    const full = fs.readFileSync(path.join(tmp, 'app.xlsx'));
    const trials = [
      ['三个字节', Buffer.from([1, 2, 3]).toString('base64')],
      ['zip 尾部被截', full.subarray(0, Math.floor(full.length / 2)).toString('base64')],
      ['不是 zip 的文本', Buffer.from('<?xml version="1.0"?><hello/>', 'utf8').toString('base64')],
      ['空字节流', '']
    ];
    for (let i = 0; i < trials.length; i++) {
      const res = await evalIn(ws, id, badExpr(trials[i][1]));
      T('X6.' + (i + 1) + ' 坏输入「' + trials[i][0] + '」抛错而非静默',
        String(res).indexOf('THROW:') === 0, String(res).slice(0, 90));
    }

    // ---- 红线：引擎里不许有第二份列名 ----
    SECT.s = 'X7';
    const tpl = fs.readFileSync(path.join(HERE, 'template.html'), 'utf8');
    const from = tpl.indexOf('RPL-Plan-v2 工作簿引擎'), upto = tpl.indexOf('window.__handleBack');
    const engine = from > 0 && upto > from ? tpl.slice(from, upto) : '';
    const longCols = [];
    const schemaCols = JSON.parse(await evalIn(ws, id,
      'JSON.stringify(PLAN_SCHEMA.sheet_order.map(function(n){return PLAN_SCHEMA.sheets[n].columns;}))'));
    schemaCols.forEach(list => list.forEach(c => { if (String(c).length >= 8 && longCols.indexOf(c) < 0) longCols.push(c); }));
    /* 「第二次写列名」有两种：字面量字符串当列键用、直接对行对象取属性。
       但 role 键名与列名大量同名（title_zh、work_weeks…），按名字放行会连真泄漏一起放过 ——
       改为按**出现位置**放行：带引号的长名只允许坐在 `xRole(sch,'表','名')` /
       `xDayField(sch,'名')` 的末参位（传给契约查找的是 role 名，取出来才是列名，
       Python 权威同样只传 role 名）。判定用后向语境：命中串前面必须紧跟
       `xRole(sch,'…',` 或 `xDayField(sch,`，后面紧跟 `')`。别处的带引号长名，
       包括 `spec['work_weeks']` 这类方括号取键，一律算泄漏。行对象取属性照旧全量严查。 */
    const quoted = [];
    longCols.forEach(c => {
      const esc = c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const occ = new RegExp('(xRole\\(\\s*sch\\s*,\\s*\'[^\']*\'\\s*,|xDayField\\(\\s*sch\\s*,)\\s*([\'"`])' + esc + '\\2\\s*\\)', 'g');
      const hit = new RegExp('[\'"`]' + esc + '[\'"`]', 'g');
      const okHits = (engine.match(occ) || []).length;
      const allHits = (engine.match(hit) || []).length;
      if (allHits > okHits) quoted.push(c + '×' + allHits + '(role 位 ' + okHits + ')');
    });
    const re2 = longCols.map(c => new RegExp('\\b(row|r|data|rowA|rowB|planRow)\\.' + c.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b'));
    const dotted = longCols.filter((c, i) => re2[i].test(engine));
    const leaked = quoted.concat(dotted).filter((v, i, a) => a.indexOf(v.split('×')[0]) === i);
    T('X7 引擎段无硬编码列名（查 ' + longCols.length + ' 个 ≥8 字的列名；带引号只许出现在 role 查找末参位，行对象取属性全量严查）',
      engine.length > 2000 && leaked.length === 0,
      leaked.length ? '泄漏 ' + leaked.join(',') +
        (quoted.length ? '（字面量：' + quoted.join(',') + '）' : '') +
        (dotted.length ? '（取属性：' + dotted.join(',') + '）' : '') : '引擎段 ' + engine.length + ' 字符');

    SECT.s = 'X8';
    T('X8 表头对账确实会报错（hand.xlsx 有且只有 1 条）',
      got['hand.xlsx'].errors.length === 1 && exp.expect['hand.xlsx'].errors.length === 1,
      got['hand.xlsx'].errors[0] || '(空)');

    // ---- V：App 内契约校验 ↔ plan_xlsx.validate_plan_dict 逐条对账 ----
    SECT.s = 'V0';
    T('V0 校验入口在（validatePlanDict 是第二实现，不是复用）',
      (await evalIn(ws, id, 'typeof validatePlanDict')) === 'function');

    /* 读侧三份 fixture 的判定：解析出来的 plan 直接在页面里过契约。
       app.xlsx 是零判定的规范件，hand.xlsx / odd.xlsx 专门用来撞出成串的 error。 */
    SECT.s = 'V1';
    for (const f of exp.fixtures) {
      const d = valDiff(exp.expect[f].val, got[f].val);
      T('V1 读 ' + f + '：计划表判定逐条与 plan_xlsx 相同（Python ' + valCount(exp.expect[f].val) + '）',
        !d, d || ('0 条差异 / ' + valCount(got[f].val)));
    }

    // 两份写侧计划（canonical 全绿、edge 故意不合法）也要过同一条线。
    SECT.s = 'V2';
    for (const [label, planJson, want] of [['canonical', exp.canonicalPlan, exp.canonicalVal],
                                            ['edge', exp.edgePlan, exp.edgeVal]]) {
      const jsVal = JSON.parse(await evalIn(ws, id, VAL + '(' + JSON.stringify(JSON.stringify(planJson)) + ',0)'));
      const d = valDiff(want, jsVal);
      T('V2 校验 ' + label + ' 计划：判定逐条与 plan_xlsx 相同（Python ' + valCount(want) + '）',
        !d, d || ('0 条差异 / ' + valCount(jsVal)));
    }

    /* 逐用例：最小合法计划 + 一批「只坏一处」的变异，Python 侧保证每例至少一条判定，
       这里保证 App 给出**同样一串**判定（含顺序与 ok）。 */
    SECT.s = 'V3';
    for (const c of exp.vCases) {
      const jsVal = JSON.parse(await evalIn(ws, id, VAL + '(' + JSON.stringify(JSON.stringify(c.plan)) + ',' + (c.strict ? 1 : 0) + ')'));
      const d = valDiff(c, jsVal);
      T('V3 ' + c.label + '：判定与 plan_xlsx 相同（Python ' + valCount(c) + '）',
        !d, d || ('0 条差异 / ' + valCount(jsVal)));
    }

    /* ---- W：C4b 换算与导入链路的逐格对账 ----
       state→计划字典用 seed.json 当输入（页面刚加载、账本=种子），期望由 xlsx_parity.stateplan 现算；
       计划字典→state 走完整导入链（读字节→契约闸门→archivePush→装载），期望由 importstate 现算。
       W1 只收 **Python 判过且 0 error** 的载荷（xlsx_parity 的 IMPORT_LABELS 保证）；
       非法载荷不硬闯闸门 —— strict 档拒收单独测（W1s），edge 样本走无闸门的装载本体
       （对齐 Python _load_plan_state），专门撞 D4 冻结与缺列兜底（W1e）。
       整段结束后 state 与归档快照还原，页面回到进入 W 前的原样。 */
    SECT.s = 'W0';
    const snap = { state: await evalIn(ws, id, 'JSON.stringify(state)') };
    /* 「哪些顶层键不参与整份 state 对账」不再手抄：向页面现取 IMPORT_KEEP_KEYS ——
       那份名单就是「导入时必须原样带走的本机键」，正是 Python 转换器不会有、
       也不该有的那一族。v0.25 把 advAuto / advAudit 加进名单时这里没人同步，
       D8 一下长红四处（每加一把偏好键就红一次），红得毫无信息量。 */
    const keySets = JSON.parse(await evalIn(ws, id,
      'JSON.stringify({keep:IMPORT_KEEP_KEYS,owned:PLAN_OWNED_KEYS})'));
    APP_ONLY = APP_ONLY_SEED.concat(keySets.keep.filter(k => keySets.owned.indexOf(k) < 0));
    T('W0 对账名单从页面现取：IMPORT_KEEP_KEYS ' + keySets.keep.length + ' 键 ∪ 种子侧 ' +
      APP_ONLY_SEED.length + ' 键，与 PLAN_OWNED_KEYS 互不重叠',
      keySets.keep.length > 0 &&
      keySets.keep.filter(k => keySets.owned.indexOf(k) >= 0).length === 0 &&
      APP_ONLY.indexOf('advAuto') >= 0 && APP_ONLY.indexOf('schemaVer') >= 0,
      '本机侧 ' + keySets.keep.join('/') + ' ｜ 种子侧 ' + APP_ONLY_SEED.join('/'));
    const archBefore = await evalIn(ws, id, 'loadPlanArchive().items.length');
    const sDump = JSON.parse(await evalIn(ws, id, `(function(){
      var p=xStateToPlanDict(state), o=PLAN_SCHEMA.sheet_order, cells={};
      for(var k=0;k<o.length;k++){ var nm=o[k], cc=PLAN_SCHEMA.sheets[nm].columns, list=p[nm]||[];
        for(var i=0;i<list.length;i++){ var row=list[i];
          for(var j=0;j<cc.length;j++){ var c=cc[j];
            if(Object.prototype.hasOwnProperty.call(row,c)) cells[nm+'|'+i+'|'+(row.__row__===undefined?'':row.__row__)+'|'+c]=xCellKey(row[c]); } } }
      return JSON.stringify({cells:cells});
    })()`));
    const dW0 = diffCells(stripVal(exp.statePlan, false), stripVal(sDump, false), 5);
    T('W0 state→计划字典：与 plan_xlsx.state_to_plan_dict 对同一份种子逐格相同（' + Object.keys(exp.statePlan.cells).length + ' 格）',
      dW0.n === 0, dW0.n ? (dW0.n + ' 格不同 / Python ' + dW0.counts[0] + ' vs App ' + dW0.counts[1] + ' → ' + dW0.samples.join(' ; ')) : '0 格差异');

    SECT.s = 'W1';
    /* 顶层整键不比：proto（页面装载时已 delete，这里防旧 state 残留，500KB 也不至于过 CDP）、
       lib / source（Python 侧 import_state_cells 已 pop）。programLib.source 这类嵌套键照比，
       所以只能浅拷贝删顶层键，不能用按键名的 replacer。 */
    const STR = `(function(s){ var d={}, k;
      for(k in s) d[k]=s[k];
      delete d.proto; delete d.lib; delete d.source;
      var t=JSON.stringify(d); delete d; return t; })`;
    const CELLS_OF = `(function(p){ var o=PLAN_SCHEMA.sheet_order, cells={};
      for(var k=0;k<o.length;k++){ var nm=o[k], cc=PLAN_SCHEMA.sheets[nm].columns, list=p[nm]||[];
        for(var i=0;i<list.length;i++){ var row=list[i];
          for(var j=0;j<cc.length;j++){ var c=cc[j];
            if(Object.prototype.hasOwnProperty.call(row,c)) cells[nm+'|'+i+'|'+(row.__row__===undefined?'':row.__row__)+'|'+c]=xCellKey(row[c]); } } }
      return cells; })`;
    for (const c of exp.importCases) {
      const label = c.label, plan = c.plan, strict = c.strict;
      const b64 = await evalIn(ws, id, WRITE + '(' + JSON.stringify(JSON.stringify(plan)) + ')');
      const out = path.join(tmp, 'js_w_' + label + '.xlsx');
      fs.writeFileSync(out, Buffer.from(b64, 'base64'));
      const imp = JSON.parse(py([path.join('tools', 'xlsx_parity.py'), 'importstate', out]));
      /* 每例都从 W0 抓的种子快照起步：Python 侧 base_seed 恒为种子，
         连续导入会让第二例的 base 变成第一例的结果，对账就没有共同基线了。 */
      await evalIn(ws, id, 'state=JSON.parse(' + JSON.stringify(snap.state) + '); "ok"');
      const got = JSON.parse(await evalIn(ws, id, `(function(planB64, strict){
        var bin=atob(planB64), u8=new Uint8Array(bin.length);
        for(var i=0;i<bin.length;i++) u8[i]=bin.charCodeAt(i);
        var r=importPlanFromXlsxBytes(u8, strict);
        if(!r.ok) return JSON.stringify({ok:false, error:r.error});
        return JSON.stringify({ok:true, warn:(r.warnings||[]).length, cells:${CELLS_OF}(xStateToPlanDict(state)),
          state:${STR}(state), archId:(r.archived&&r.archived.id)||'',
          weeks:Object.keys(state.weeks).length, inactive:(state.structure.inactiveWeeks||[]).length});
      })(` + JSON.stringify(b64) + ',' + (strict ? 1 : 0) + ')'));
      T('W1 ' + label + '：导入成功（Python 判定 ' + valCount(imp.val) + '）',
        got.ok === true, got.ok ? '导入返回 ok' : ('被拦：' + String(got.error).replace(/\s+/g, ' ').slice(0, 120)));
      T('W1 ' + label + '：导入带回的告警条数与 plan_xlsx 相同',
        got.ok && got.warn === (imp.val.warnings || []).length,
        !got.ok ? '(没导入)' : ('App ' + got.warn + ' 条 / Python ' + (imp.val.warnings || []).length + ' 条'));
      const dS = diffCells(stateStrip(imp.state), stateStrip(JSON.parse(got.state || '{}')), 5);
      T('W1 ' + label + '：导入后的 state 与 plan_dict_to_state 去 null 后全等',
        got.ok && dS.n === 0, !got.ok ? '(没导入)' : (dS.n ? dS.n + ' 处不同 → ' + dS.samples.join(' ; ') : '0 差异'));
      const dC = diffCells(stripVal(imp.cells || {}, true), stripVal(got.cells || {}, true), 5);
      T('W1 ' + label + '：换算回计划字典与 Python 往返逐格相同（' + Object.keys(imp.cells || {}).length + ' 格）',
        got.ok && dC.n === 0, !got.ok ? '(没导入)' : (dC.n ? dC.n + ' 格不同 → ' + dC.samples.join(' ; ') : '0 差异'));
      if (label === 'canonical 全量计划') {
        /* 周数不写死：以这份计划 Workouts 里真实出现的周号个数为准（计划加周不该红）。 */
        const planWeeks = new Set((plan.Workouts || []).map(r => r.week)).size;
        T('W1 canonical：计划里的每一周都进账本且无冻结周', got.weeks === planWeeks && got.inactive === 0,
          'weeks=' + got.weeks + ' / 计划 ' + planWeeks + ' 周 / inactive=' + got.inactive);
      }
    }

    SECT.s = 'W1s';
    const strictCase = exp.vCases.find(cc => cc.label === '安全约束违规（strict）');
    const rejSnap = await evalIn(ws, id, 'JSON.stringify(state)');
    const sGot = JSON.parse(await evalIn(ws, id, `(function(planJson){
      var u8=xlsxBytesFromPlan(JSON.parse(planJson));
      var r=importPlanFromXlsxBytes(u8, true);
      return JSON.stringify(r.ok?{ok:true}:{ok:false, error:r.error});
    })(` + JSON.stringify(JSON.stringify(strictCase.plan)) + ')'));
    T('W1s 同一份计划在 strict 档整份拒收（非 strict 档刚在 W1 导入成功），且错误清单原文带回（' + strictCase.errors.length + ' 条）',
      sGot.ok === false && String(sGot.error).indexOf(strictCase.errors[0]) >= 0 &&
      (await evalIn(ws, id, 'JSON.stringify(state)')) === rejSnap,
      sGot.ok ? '竟然导入了' : String(sGot.error).replace(/\s+/g, ' ').slice(0, 110));

    SECT.s = 'W1e';
    /* edge 故意不合契约，进不了导入链；绕开闸门直接调装载本体（每步与
       xPlanDictToState 的 validate 之后段落同名同序），对账 Python 的 _load_plan_state。 */
    const b64e = await evalIn(ws, id, WRITE + '(' + JSON.stringify(JSON.stringify(exp.edgePlan)) + ')');
    const outedge = path.join(tmp, 'js_w_edge.xlsx');
    fs.writeFileSync(outedge, Buffer.from(b64e, 'base64'));
    const impE = JSON.parse(py([path.join('tools', 'xlsx_parity.py'), 'importstate', outedge]));
    const gotE = JSON.parse(await evalIn(ws, id, `(function(planJson){
      var sch=PLAN_SCHEMA, p=JSON.parse(planJson); xRequireProfileFields(sch);
      var so=clone(SEED);
      var vals=xValidateProfile(sch,p,xRes()); xApplyProfile(sch,vals,so);
      var blocks=xBlocksToState(sch,p), days=xDaysToState(sch,p), wcf=xWeekCountFields(sch), total=0;
      for(var i=0;i<blocks.length;i++) for(var k=0;k<wcf.length;k++) total+=blocks[i][wcf[k]]||0;
      xApplyOnMissing(sch,vals,so,total);
      var gpp=xGppDefsFromPlan(sch,p); if(!gpp.length) gpp=clone(SEED.gpp||[]); so.gpp=gpp;
      so.levelSnap=xLevelFromPlan(sch,p);
      delete so.aux;
      so.structure={version:structureVersion(), startDate:vals[PLAN_PROFILE_KEYS[0]], totalWeeks:total,
        daysPerWeek:days.length, blocks:blocks, dayDefs:days, recSetsOverride:recSetsFor()};
      so.weeks=xBlankWeeks(sch,total,days,vals,gpp);
      xApplyWorkouts(sch,p,so,SEED.proto,total); xApplyGear(sch,p,so); xApplyGpp(sch,p,so); xApplyTelemetry(sch,p,so);
      xFreezeExtraWeeks(so,SEED.weeks||{});
      delete so.proto;
      return JSON.stringify({cells:${CELLS_OF}(xStateToPlanDict(so)),
        state:${STR}(so),
        weeks:Object.keys(so.weeks).length, inactive:(so.structure.inactiveWeeks||[]).length});
    })(` + JSON.stringify(JSON.stringify(exp.edgePlan)) + ')'));
    const dSE = diffCells(stateStrip(impE.state), stateStrip(JSON.parse(gotE.state || '{}')), 5);
    T('W1e edge 无闸门装载：state 与 plan_xlsx._load_plan_state 去 null 后全等',
      dSE.n === 0, dSE.n ? dSE.n + ' 处不同 → ' + dSE.samples.join(' ; ') : '0 差异');
    const dCE = diffCells(stripVal(impE.cells || {}, true), stripVal(gotE.cells || {}, true), 5);
    T('W1e edge 换算回计划字典与 Python 往返逐格相同（' + Object.keys(impE.cells || {}).length + ' 格）',
      dCE.n === 0, dCE.n ? dCE.n + ' 格不同 → ' + dCE.samples.join(' ; ') : '0 差异');
    const eTotal = +impE.state.structure.totalWeeks;
    T('W1e edge：种子 ' + gotE.weeks + ' 周不删、超出 ' + eTotal + ' 周的 ' + (gotE.weeks - eTotal) + ' 周登记进 inactiveWeeks（D4 冻结）',
      gotE.weeks === Object.keys(impE.state.weeks).length && gotE.inactive === (impE.state.structure.inactiveWeeks || []).length
      && gotE.weeks > eTotal && gotE.inactive === gotE.weeks - eTotal,
      'weeks=' + gotE.weeks + ' / inactive=' + gotE.inactive);

    SECT.s = 'W1d';
    /* D10 反向验证（_sabotage_c4 第 1 组暴露的盲区）：fixture 全是自洽账本 ——
       load_kg ≡ mround(anchor×pct)，把 %1RM 覆写删掉，四段对账照样全绿。这里现场造冲突：
       同一份 canonical 字典拷两份，只在 B 上把首个锚点类目行的 pct 改成一个算出新值的数、
       load_kg 保持原值（哨兵）；两走无闸门入口 xPlanDictToState（对齐 W1e 的装载本体），
       取同一 rank 的动作对比 —— B 落 mround(anchor×新 pct) 才是覆写在岗。不加 fixture 不落盘。 */
    const canonPlan = exp.importCases.find(cc => cc.label.indexOf('canonical') >= 0).plan;
    const d10 = JSON.parse(await evalIn(ws, id, `(function(planJson){
      var sch=PLAN_SCHEMA, rc=sch.sheets.Workouts.role_columns;
      var pA=JSON.parse(planJson), pB=JSON.parse(planJson), i;
      var afs=xAnchorProfileFields(sch), rowsB=pB['Workouts'], idx=-1;
      for(i=0;i<rowsB.length;i++){ var r=rowsB[i];
        if(afs[r[rc.category]]!==undefined && xInt(r[rc.week])!==null && xText(r[rc.day])!==null){ idx=i; break; } }
      if(idx<0) return JSON.stringify({ok:false, why:'没有锚点类目的动作行'});
      var pickedB=rowsB[idx], pickedA=pA['Workouts'][idx];
      var wk=xInt(pickedB[rc.week]), day=xText(pickedB[rc.day]);
      var anchor=xNum(xGetPath(SEED, sch.sheets.Profile.fields[afs[pickedB[rc.category]]].path));
      if(!anchor) return JSON.stringify({ok:false, why:'锚点值为 0，mround 覆写分支进不去'});
      var L0=xNum(pickedB[rc.load]), pctPick=null, E=null;
      var cands=[0.5,0.63,0.37,0.42];
      for(i=0;i<cands.length;i++){ var e=mround(anchor*cands[i], sch.conflict_policy.round_step_kg);
        if(e!==L0){ pctPick=cands[i]; E=e; break; } }
      if(pctPick===null) return JSON.stringify({ok:false, why:'候选 pct 全部撞原 load'});
      /* rank：同 (week,day) 组内按 (seq,row) 排序后的位置，与 xApplyWorkouts 的入组规则同式 */
      function kx(r){ return [(xInt(r[rc.seq])||0),(xInt(r[rc.row])||0)]; }
      var grp=pA['Workouts'].filter(function(r){ return xInt(r[rc.week])===wk && xText(r[rc.day])===day; });
      grp.sort(function(a,b){ var ka=kx(a),kb=kx(b); return ka[0]-kb[0]||ka[1]-kb[1]; });
      var rank=grp.indexOf(pickedA);
      if(rank<0) return JSON.stringify({ok:false, why:'rank 找不到'});
      pickedB[rc.pct]=pctPick;   /* load 列不动：哨兵 = 原 L0 */
      var soA, soB;
      try{ soA=xPlanDictToState(pA,false,undefined); soB=xPlanDictToState(pB,false,undefined); }
      catch(e){ return JSON.stringify({ok:false, why:String(e&&e.message||e).slice(0,80)}); }
      var exsA=soA.weeks[String(wk)][day].exercises, exsB=soB.weeks[String(wk)][day].exercises;
      var exA=exsA[rank], exB=exsB[rank];
      return JSON.stringify({ok:true, wk:wk, day:day, rank:rank, pct:pctPick, L0:L0, E:E, anchor:anchor,
        cat:String(pickedB[rc.category]), aLoad:exA?exA.load:null, bLoad:exB?exB.load:null,
        aCat:exA?String(exA.cat):'', bCat:exB?String(exB.cat):'', nA:exsA.length, nB:exsB.length});
    })(` + JSON.stringify(JSON.stringify(canonPlan)) + ')'));
    T('W1d D10 冲突样本：改 pct 保 load 的字典仍过闸门，两份落定动作数与行次对齐（rank=' + d10.rank + '）',
      d10.ok === true && d10.nA === d10.nB && d10.aCat === d10.bCat,
      d10.ok ? 'nA=' + d10.nA + ' nB=' + d10.nB + ' cat=' + d10.cat : d10.why);
    T('W1d D10：冲突行落定 load = mround(anchor×新pct)=' + d10.E + '（表内哨兵 L0=' + d10.L0 + ' 被覆写；删掉 D10 这里就抓到）',
      d10.ok === true && d10.aLoad === d10.L0 && d10.bLoad === d10.E,
      '未改组 aLoad=' + d10.aLoad + ' / 冲突组 bLoad=' + d10.bLoad + ' / 期望 ' + d10.E);

    SECT.s = 'W2';
    const rej = exp.vCases.find(cc => cc.label === 'day 未定义');
    const snap2 = await evalIn(ws, id, 'JSON.stringify(state)');
    const rejGot = JSON.parse(await evalIn(ws, id, `(function(planJson){
      var u8=xlsxBytesFromPlan(JSON.parse(planJson));
      var r=importPlanFromXlsxBytes(u8, false);
      return JSON.stringify(r.ok?{ok:true}:{ok:false, error:r.error});
    })(` + JSON.stringify(JSON.stringify(rej.plan)) + ')'));
    T('W2 非 strict 也过不了契约的计划整份拒收，错误清单原文带回（' + rej.errors.length + ' 条）',
      rejGot.ok === false && rejGot.error === rej.errors.join('\n'),
      rejGot.ok ? '竟然导入了' : String(rejGot.error).replace(/\s+/g, ' ').slice(0, 110));
    T('W2b 被拒后账本没被动过（state 与 W2 前逐字节相同）',
      (await evalIn(ws, id, 'JSON.stringify(state)')) === snap2);

    SECT.s = 'W3';
    /* 归档取回链（设置页 restoreArchiveItem 本尊）：缺条目守卫 → archiveGet → 契约复检 → adoptImportedPlan。
       不变量是「取回落点 ≡ 存档当时」——不是「≡ 种子」：计划往返本身有契约内损失
       （Profile 只带表内字段、dayDefs 由表重建），拿种子当落点期望会把这些已知损失误判成漂移。
       存档素材现推（当前页 = W1 canonical 落点，种子换算 224KB < 320KB 单条上限，写得进）；
       落点期望在同一段里当场取 STR 原文，导入等价性本身由 W1 四例逐格钉死，这里不重复审。 */
    const W3 = JSON.parse(await evalIn(ws, id, `(function(){
      var pre=${STR}(state);
      var a=archivePush(xStateToPlanDict(state),{source:'parity'});
      var it=a.ok?archiveGet(a.id):null;
      return JSON.stringify({push:a, pre:pre, onShelf:!!it});
    })()`));
    const w3detail = '存档 ' + JSON.stringify(W3.push.ok ? {id:W3.push.id} : {reason:W3.push.reason}) + ' / 架上 ' + W3.onShelf;
    await evalIn(ws, id, 'state=JSON.parse(' + JSON.stringify(snap.state) + '); "ok"');
    await evalIn(ws, id, 'restoreArchiveItem(' + JSON.stringify(W3.push.id || 'x') + ')');
    const landStr = await evalIn(ws, id, `(function(){ return ${STR}(state); })()`);
    const dSeed = diffCells(stateStrip(JSON.parse(W3.pre)), stateStrip(JSON.parse(snap.state)), 3);
    T('W3 归档取回：落点与存档当场原文逐字节相同（对照非恒等：存档当时与种子有 ' + dSeed.n + ' 处不同）',
      W3.push.ok === true && W3.onShelf === true && dSeed.n > 0 && landStr === W3.pre,
      landStr === W3.pre ? '0 差异（逐字节）' : w3detail + ' / 对照 ' + dSeed.n + ' 处 / 落点' +
        (landStr === snap.state ? '仍是种子（取回没生效）' : '到了别处'));
    const minB = await evalIn(ws, id, 'JSON.stringify(state)');
    await evalIn(ws, id, 'restoreArchiveItem("pa-no-such-id")');
    const bogus = JSON.parse(await evalIn(ws, id, `(function(){
      return JSON.stringify({gone:!archiveGet('pa-no-such-id'),
        untouched:JSON.stringify(state)===${JSON.stringify(minB)}});
    })()`));
    T('W3 取回不存在的归档条目（已被淘汰/超字节上限被拒）：不写盘、账本一字不动',
      bogus.gone === true && bogus.untouched === true,
      bogus.untouched ? '(缺条目守卫跑通)' : '缺 id 取回竟动了账本');

    await evalIn(ws, id, 'state=JSON.parse(' + JSON.stringify(snap.state) + '); renderAll(); "ok"');
    const archAfter = await evalIn(ws, id, 'loadPlanArchive().items.length');
    T('W9 每次成功导入都把导入前的计划推进第四分片（归档只增不改，条数 ' + archBefore + ' → ' + archAfter + '）',
      archAfter > archBefore && archAfter <= 8, 'before ' + archBefore + ' / after ' + archAfter);
    await evalIn(ws, id, 'archiveClear(); "ok"');
    T('W9b 段末清场：state 与归档都回到进入 W 前的原样',
      (await evalIn(ws, id, 'JSON.stringify(state)')) === snap.state &&
      (await evalIn(ws, id, 'loadPlanArchive().items.length')) === archBefore);

    SECT.s = 'Y';
    /* Y 段：JSON 计划信封（v0.11 起交换唯一权威载体，v0.44 起现行契约是 Exchange-v3）。
       契约单源在 tools/schema/RPL-Exchange-v3.json：前端从注入的 EXCHANGE_SCHEMA 取键序/版本/文件名/MIME，
       Python 侧从同一份文件取 —— Y5 让两种实现互检同一份文本，谁硬编码第二份谁当场露馅。
       accepted 含 RPL-Plan-v1 → v1 信封仍可导入（Y14/Y15），导入后重导出升级为 v3（Y16）。 */
    const excDisk = JSON.parse(fs.readFileSync(path.join(HERE, 'schema', 'RPL-Exchange-v3.json'), 'utf8'));
    const excSpec = excDisk.plan_envelope;
    const excPage = JSON.parse(await evalIn(ws, id, 'JSON.stringify(EXCHANGE_SCHEMA.plan_envelope)'));
    T('Y1 注入的 EXCHANGE_SCHEMA.plan_envelope 与磁盘契约文件逐键相同（单源未分叉）',
      JSON.stringify(excPage) === JSON.stringify(excSpec),
      JSON.stringify(excPage) === JSON.stringify(excSpec) ? 'OK' : '页面 ' + JSON.stringify(excPage).slice(0, 120));

    const gradleVer = (fs.readFileSync(path.join(HERE, '..', 'app', 'build.gradle'), 'utf8')
      .match(/versionName\s*=\s*'([^']*)'/) || [])[1];
    const envFixed = JSON.parse(await evalIn(ws, id,
      'JSON.stringify(planEnvelope("2026-01-01T00:00:00"))'));
    T('Y2 信封头部键序 == 契约 key_order，schemaVersion == current，app.version == gradle 版本（' + gradleVer + '）',
      Object.keys(envFixed).join(',') === excSpec.key_order.join(',') &&
      envFixed[excSpec.schema_version_field] === excSpec.current &&
      envFixed.app && envFixed.app.version === gradleVer && envFixed.app.name === excSpec.app_name,
      Object.keys(envFixed).join(','));

    const y3 = await evalIn(ws, id, `(function(){
      var a=exportPlanJSONText('2026-01-01T00:00:00');
      var b=exportPlanJSONText('2026-01-01T00:00:00');
      var env=JSON.parse(a);
      return JSON.stringify({det:a===b, parse:!!env,
        same:JSON.stringify(env.plan)===JSON.stringify(xStateToPlanDict(state))});
    })()`);
    const y3r = JSON.parse(y3);
    T('Y3 导出文本确定性（同时间戳两次逐字节相同）且可解析', y3r.det && y3r.parse);
    T('Y4 信封 plan 载荷与 xStateToPlanDict(state) 全等（信封只是载体，不私改数据）', y3r.same);

    const envTxt = await evalIn(ws, id, 'exportPlanJSONText("2026-01-01T00:00:00")');
    const envPath = path.join(tmp, 'js_envelope.json');
    fs.writeFileSync(envPath, envTxt, 'utf8');
    const y5 = pyRaw(['tools/plan_xlsx.py', 'json', '--check', envPath]);
    T('Y5 前端产出的信封过 Python 侧 validate_envelope（两种实现互检同一份文本）',
      y5.code === 0, (y5.out || '').replace(/\s+/g, ' ').slice(-140));

    const y6 = await evalIn(ws, id, `(function(){
      READONLY=true;
      var r=doExportPlanJSON();
      READONLY=false;
      return JSON.stringify({blocked:r===false, back:doExportPlanJSON===undefined?'gone':'fn'});
    })()`);
    const y6r = JSON.parse(y6);
    T('Y6 READONLY 下 doExportPlanJSON 拒导出（返回 false），解除后函数仍在位',
      y6r.blocked && y6r.back === 'fn');

    /* Y7–Y13：JSONL 训练日志（只导不入）+ JSON 计划导入闭环（v0.12）。
       日志记录内容与 CSV 导出同源（unifiedRecords），Python 侧只独立校验不重建；
       导入闭环 = 导出信封 → 篡改/原样 → importPlanFromJSONText 整份替换 + 归档。 */
    const lj = JSON.parse(await evalIn(ws, id, `(function(){
      var txt=logJsonlText("2026-01-01T00:00:00");
      var lines=txt.split("\\n").filter(function(s){return s.trim()!=="";});
      var meta=JSON.parse(lines[0]);
      var L=EXCHANGE_SCHEMA.log_jsonl, H=L.header_record;
      var reqOk=H.required_keys.every(function(k){return meta[k]!==undefined;});
      var recs=unifiedRecords();
      var keysOk=true;
      for(var i=1;i<lines.length && keysOk;i++){
        var o=JSON.parse(lines[i]);
        if(Object.keys(o).length!==CSV_COLS.length){keysOk=false;break;}
        for(var j=0;j<CSV_COLS.length;j++){ if(o[CSV_COLS[j]]===undefined){keysOk=false;break;} }
      }
      return JSON.stringify({n:lines.length, recN:recs.length,
        type:meta[H.type_key]===H.type_value, sv:meta.schema_ver===L.current,
        proto:H.csv_protocol_accepted.indexOf(meta[H.schema_ver_value_field])>=0,
        ver:meta.app_version, reqOk:reqOk, keysOk:keysOk});
    })()`));
    T('Y7 JSONL 首行 META 头：type/schema_ver/csv_protocol/必带键齐 · app_version==gradle（' + gradleVer + '）· 行数==记录数+1',
      lj.type && lj.sv && lj.proto && lj.reqOk && lj.ver === gradleVer && lj.n === lj.recN + 1,
      'lines=' + lj.n + ' recs=' + lj.recN + ' ver=' + lj.ver);
    T('Y8 JSONL 每条数据记录恰好含 26 个 CSV_COLS 键（与冻结的 CSV 协议同键集）', lj.keysOk);

    const ljTxt = await evalIn(ws, id, 'logJsonlText("2026-01-01T00:00:00")');
    const ljPath = path.join(tmp, 'js_log.jsonl');
    fs.writeFileSync(ljPath, ljTxt, 'utf8');
    const y9 = pyRaw(['tools/plan_xlsx.py', 'logjsonl', '--check', ljPath]);
    T('Y9 前端产出的 JSONL 过 Python 侧 validate_log_jsonl（两种实现互检同一份文本）',
      y9.code === 0, (y9.out || '').replace(/\s+/g, ' ').slice(-140));

    const y10 = JSON.parse(await evalIn(ws, id, `(function(){
      var a=logJsonlText("2026-01-01T00:00:00"), b=logJsonlText("2026-01-01T00:00:00");
      return JSON.stringify({det:a===b});
    })()`));
    T('Y10 JSONL 导出确定性（同时间戳两次逐字节相同）', y10.det);

    const snapY = await evalIn(ws, id, 'JSON.stringify(state)');
    const archY0 = Number(await evalIn(ws, id, 'loadPlanArchive().items.length'));
    const impTxt = await evalIn(ws, id, 'exportPlanJSONText("2026-01-01T00:00:00")');
    const imp = JSON.parse(await evalIn(ws, id, `(function(t){
      var prePlan=JSON.stringify(xStateToPlanDict(state));
      var r=importPlanFromJSONText(t,false);
      return JSON.stringify({ok:r.ok===true,
        planSame:r.ok===true?(JSON.stringify(r.plan)===prePlan):false,
        err:r.ok===true?'':String(r.error||'')});
    })(` + JSON.stringify(impTxt) + `)`));
    const archY1 = Number(await evalIn(ws, id, 'loadPlanArchive().items.length'));
    T('Y11 JSON 导入闭环：导出的信封原样导回 ok，载荷与导出前逐字节相同，旧计划进归档（' + archY0 + '→' + archY1 + '）',
      imp.ok && imp.planSame && archY1 > archY0, imp.ok ? 'archived ' + archY1 : imp.err.slice(0, 110));

    const tampered = JSON.parse(await evalIn(ws, id, `(function(t){
      var env=JSON.parse(t); env.schemaVersion="RPL-Plan-v999";
      var before=JSON.stringify(state);
      var r=importPlanFromJSONText(JSON.stringify(env),false);
      return JSON.stringify({blocked:r.ok===false, reject:/不在接受清单/.test(String(r.error||'')),
        untouched:JSON.stringify(state)===before});
    })(` + JSON.stringify(impTxt) + `)`));
    T('Y12 未知 schemaVersion 的信封整份拒收（错误点名「不在接受清单」），账本一字不动',
      tampered.blocked && tampered.reject && tampered.untouched,
      tampered.blocked ? 'untouched=' + tampered.untouched : '竟然导入了');

    /* Y14–Y16 兼容腿：把导出的 v3 信封现场降级成 v1 形状（信封版本 + Profile!schema_ver 行 +
       删 Gear 表），导入必须照旧成功；导回后重导出应升级回 v3（导出永远只产现行版本）。 */
    const v1EnvTxt = await evalIn(ws, id, `(function(t){
      var sch=PLAN_SCHEMA, env=JSON.parse(t), pc=sch.sheets.Profile.columns;
      env.schemaVersion='RPL-Plan-v1';   /* 已有键原位赋值，头部键序不动 */
      var rows=env.plan.Profile||[];
      for(var i=0;i<rows.length;i++) if(String(rows[i][pc[0]])==='schema_ver') rows[i][pc[1]]='RPL-Plan-v1';
      delete env.plan.Gear;
      return JSON.stringify(env);
    })(` + JSON.stringify(impTxt) + `)`);
    const v1Path = path.join(tmp, 'js_envelope_v1.json');
    fs.writeFileSync(v1Path, v1EnvTxt, 'utf8');
    const v1r = JSON.parse(await evalIn(ws, id, `(function(t){
      var r=importPlanFromJSONText(t,false);
      var env=JSON.parse(t);
      return JSON.stringify({ok:r.ok===true, noGear:!Object.prototype.hasOwnProperty.call(env.plan,'Gear'),
        err:r.ok===true?'':String(r.error||'')});
    })(` + JSON.stringify(v1EnvTxt) + `)`));
    T('Y14 v1 信封（schemaVersion=RPL-Plan-v1 · Profile!schema_ver=v1 · 无 Gear 表）导入成功——legacy 六表分派在岗',
      v1r.ok && v1r.noGear, v1r.ok ? 'imported' : v1r.err.replace(/\s+/g, ' ').slice(0, 110));
    const y15 = pyRaw(['tools/plan_xlsx.py', 'json', '--check', v1Path]);
    T('Y15 同一份 v1 信封过 Python 侧 validate_envelope（双版本接受清单两侧一致）',
      y15.code === 0, (y15.out || '').replace(/\s+/g, ' ').slice(-140));
    const upg = JSON.parse(await evalIn(ws, id, `(function(){
      var txt=exportPlanJSONText("2026-01-01T00:00:00"), env=JSON.parse(txt);
      return JSON.stringify({sv:env.schemaVersion, hasGear:Object.prototype.hasOwnProperty.call(env.plan,'Gear'),
        verCell:(function(){var pc=PLAN_SCHEMA.sheets.Profile.columns,rows=env.plan.Profile||[];
          for(var i=0;i<rows.length;i++) if(String(rows[i][pc[0]])==='schema_ver') return String(rows[i][pc[1]]);
          return '';})()});
    })()`));
    const upgPath = path.join(tmp, 'js_envelope_upgraded.json');
    fs.writeFileSync(upgPath, await evalIn(ws, id, 'exportPlanJSONText("2026-01-01T00:00:00")'), 'utf8');
    const y16py = pyRaw(['tools/plan_xlsx.py', 'json', '--check', upgPath]);
    T('Y16 v1 导入后重导出升级为现行 v3 信封：schemaVersion==' + excSpec.current + ' · plan 带 Gear 表 · ' +
      'Profile!schema_ver==' + excSpec.current + ' · Python 侧互检通过',
      upg.sv === excSpec.current && upg.hasGear && upg.verCell === excSpec.current && y16py.code === 0,
      'sv=' + upg.sv + ' gear=' + upg.hasGear + ' cell=' + upg.verCell + ' py=' + y16py.code);

    await evalIn(ws, id, 'state=JSON.parse(' + JSON.stringify(snapY) + '); save(true); renderAll(); archiveClear(); "ok"');
    const y13 = JSON.parse(await evalIn(ws, id, `(function(){
      READONLY=true; var r=doExportLogJSONL(); READONLY=false;
      return JSON.stringify({blocked:r===false, back:typeof doExportLogJSONL});
    })()`));
    T('Y13 READONLY 下 doExportLogJSONL 拒导出（返回 false），解除后函数仍在位',
      y13.blocked && y13.back === 'function');
  } catch (e) {
    T('Z0 断言块在 ' + SECT.s + ' 段中途抛错（其后断言未执行）', false,
      String(e && e.message || e).replace(/\s+/g, ' ').slice(-300));
  }

  /* 断言总数闸门：与 v2v / v3v 同一理由 —— 少一条就是少一条，不能装作还是全绿。
     171 = X 段 37 + V 段 83（V0 入口 1 + V1 读侧三份 fixture + V2 写侧两份计划 + V3 逐用例 77）
           + W 段 35（W0 2 + W1 五例 ×4 + canonical 台账 1 + W1s strict 拒收 1
             + W1e 无闸门装载 3 + W1d D10 冲突样本 2 + W2/W2b 拒收 2 + W3 归档取回 2 + W9/W9b 归档 2）
           + Y 段 16（JSON 信封 6：单源 1 + 键序/版本 1 + 确定性/载荷 2 + Python 互检 1 + READONLY 1；
             JSONL+导入闭环 7：META 头 1 + 26 键 1 + Python 互检 1 + 确定性 1 + 导入闭环 1 + 拒收 1 + READONLY 1；
             v1 兼容腿 3：legacy 导入 1 + Python 互检 1 + 升级重导出 1）
     （W1 的条数由 xlsx_parity 的 IMPORT_LABELS + canonical 决定，V3 由 CASES 决定，
       加用例就要在这里重新数一遍）。 */
  const EXP_N = 171;
  if (PASS + FAIL !== EXP_N) {
    LINES.push('FAIL  Z1 断言总数漂移（实到 ' + (PASS + FAIL) + '，应 ' + EXP_N + '）');
    FAIL++;
  }
  console.log(LINES.join('\n'));
  const nP = LINES.filter(l => l.indexOf('PASS') === 0).length;
  const nF = LINES.filter(l => l.indexOf('FAIL') === 0).length;
  console.log('\n== xlsxv 汇总: ' + nP + ' PASS / ' + nF + ' FAIL （共 ' + (nP + nF) + ' 项）==');
  ws.close();
  /* 红了就留档：fixture 和 App 写出的 js_*.xlsx 全在里头，直接拿 plan_xlsx.py 单独复跑。
     清理失败不算失败 —— Chrome 还没退干净时 Windows 会短暂锁住目录，别让它盖掉判定。 */
  const cleaned = await tmpclean.close(chrome, tmp, FAIL > 0);
  if (FAIL > 0) console.log('现场保留在 ' + tmp);
  else if (!cleaned) console.log('临时目录没清掉：' + tmp);
  process.exit(FAIL > 0 ? 1 : 0);
}

main().catch(async e => {
  console.error('xlsxv 跑飞：' + (e && e.stack || e));
  await tmpclean.close(chrome, tmp);
  process.exit(2);
});
