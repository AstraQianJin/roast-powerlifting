/**
 * v3v.js — ExDark Pro 无头回归断言（条数由本文件的 EXP_N 闸门把关，不在注释里手抄）
 * 覆盖 v0.03/v0.05 基线 + v0.06 的顶栏/Poster/模式迁移/JTS 五模块/GL 段位/两套新资产/Profile 三 Tab
 * + v0.07 地基（A2 存档阻断层 / A3 迁移闸门）+ v0.08 契约（C1 xlsx / C2 结构闸门 / C3 归档分片）。
 * 与 v2v.js 并存双跑：v2v 守 47 项基础面，v3v 守新增面。
 *
 *   node tools/v3v.js
 *
 * 断言里的版本串从 app/build.gradle 的 versionName 读取，不在本文件手抄。
 */
const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const tmpclean = require('./tmpclean');
const CHROME = process.env.CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
const FILE = 'file:///' + path.resolve(__dirname, '../app/src/main/assets/index.html').replace(/\\/g, '/');
const PORT = 9890 + Math.floor(Math.random() * 10);

/* 唯一事实源：build.gradle 的 versionName（与 build_html.py 同一正则，纯版本号） */
const VER = (() => {
  const src = fs.readFileSync(path.resolve(__dirname, '../app/build.gradle'), 'utf8');
  const m = src.match(/versionName\s*=\s*'([^']*)'/);
  if (!m || !/^\d+\.\d{1,2}$/.test(m[1].trim())) {
    throw new Error('v3v.js：build.gradle 的 versionName 不可解析（应为纯版本号，如 0.07）');
  }
  return m[1].trim();
})();

function send(ws, id, method, params) {
  return new Promise((res, rej) => {
    const mid = ++id;
    const cb = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === mid) { ws.removeEventListener('message', cb); m.error ? rej(m.error) : res(m.result); }
    };
    ws.addEventListener('message', cb);
    ws.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
}

/* Chrome 的一次性 profile 必须回收：见 tmpclean.js。hoist 出来让崩掉的那条路也能清。 */
let chrome = null, profDir = null;
(async () => {
  profDir = fs.mkdtempSync(path.join(os.tmpdir(), 'v3v-'));
  chrome = spawn(CHROME, ['--headless=new', `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${profDir}`, '--window-size=412,892',
    '--force-device-scale-factor=1', '--hide-scrollbars', '--no-first-run',
    '--allow-file-access-from-files', 'about:blank'], { stdio: 'ignore' });
  await new Promise(r => setTimeout(r, 800));
  let wsUrl = null;
  for (let i = 0; i < 60 && !wsUrl; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json`).then(r => r.json());
      wsUrl = r.find(x => x.type === 'page').webSocketDebuggerUrl;
    } catch (e) { await new Promise(r => setTimeout(r, 200)); }
  }
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.addEventListener('open', res); ws.addEventListener('error', rej); });
  let id = 0;
  await send(ws, id, 'Page.enable');
  await send(ws, id, 'Runtime.enable');
  const waitReady = async () => {
    for (let i = 0; i < 30; i++) {
      const ok = await send(ws, id, 'Runtime.evaluate', { expression: '!!(state&&state.lib)', returnByValue: true })
        .then(r => r.result && r.result.value).catch(() => false);
      if (ok) return true;
      await new Promise(r => setTimeout(r, 300));
    }
    return false;
  };

  await send(ws, id, 'Page.navigate', { url: FILE });
  await waitReady();

  // 迁移前置：清空三路分片，只留一份「旧字段名 v=5」的单文件存档。
  // 之前它没清分片，boot() 优先读 workout，legacy 分支从未被真正走过（A6 恒真）。
  // 置空 state 是为了让 pagehide 的 flushSave 短路，别在重载瞬间把分片写回来。
  const lsKey = await send(ws, id, 'Runtime.evaluate',
    { expression: "(typeof LS!=='undefined')?LS:null", returnByValue: true })
    .then(r => r.result && r.result.value).catch(() => null);
  let legacyOK = false;
  if (lsKey) {
    legacyOK = await send(ws, id, 'Runtime.evaluate', {
      expression: `(function(){
        var s=JSON.parse(JSON.stringify(state));
        /* 仿旧要连口径一起仿：把自重类的新语义外载折回旧语义净重，
           否则 v7 net2ext 会拿真外载再减一遍体重，自重加载在 boot 后全变负数。 */
        if(typeof v7EachExercise==='function'){
          v7EachExercise(s,function(e,w,d,i,dd){
            if(e.conv||e.gearPending) return;
            if(v7GearKind(s,e.mv)!=='bw') return;
            var cur=+e.load||0; if(cur<=0) return;
            var bw=(+dd.bw)||(+s.profile&&+s.profile.bw)||0;
            if(bw>0) e.load=+(cur+bw*v7LeverOf(s,e.mv)).toFixed(2);
          });
        }
        s.v=5; delete s.schemaVer;
        var t=JSON.stringify(s);
        state=null;
        [LS_WORK,LS_PREFS,LS_LIB].forEach(function(k){ localStorage.removeItem(k); });
        localStorage.setItem(${JSON.stringify(lsKey)}, t);
        var q=JSON.parse(localStorage.getItem(${JSON.stringify(lsKey)}));
        return q.v===5 && q.schemaVer===undefined && !localStorage.getItem(LS_WORK);
      })()`, returnByValue: true
    }).then(r => r.result && r.result.value).catch(() => false);
    await send(ws, id, 'Page.reload');
    await waitReady();
  }

  /* 主断言块的期望条数（不含 R/S 重载轮）；增删断言时同步改这里。 */
  const EXP_N = 461;   /* v0.47 主页/HX 加 15；v0.48 分享图 PX 加 11；v0.49 设置页六段 E 改写 +3、六边形记录 HP 加 9；v0.54 视角/形态 HP10–13 加 4、伤病 HL1–4 加 4；v0.58 六轴重定义 HP14–15 加 2、最近训练模块退役 HX 减 1、计算器折叠 HX12 替换；本版打气模块删除 HX8/HX9/PX9 减 3；v0.70 设置独立页/返回栈 E12–E14 加 3 */
  const expr = `(function(){
    var o=[],P=0,F=0;
    /* 版本串来自本文件顶部的 VER（build.gradle 直读），此处不再手抄 */
    var EXP='${VER}';
    /* 断言总数闸门：任何一条 T() 被误删、或整段被 if 跳过（如 F 块缺函数），
       计数就会掉下这个数 —— 没有它，「150 全绿」可能只是「120 全绿」被默默接受。 */
    var EXP_N=${EXP_N};
    /* 旧存档（字段名 v）是否真的写进过存储 —— 由外层迁移前置步骤置位 */
    var LEGACY=${legacyOK ? 'true' : 'false'};
    var T=function(n,c,x){ if(c)P++;else F++; o.push((c?'PASS  ':'FAIL  ')+n+(x!==undefined?('  ['+x+']'):'')); };
    var HAN=new RegExp('[\\\\u4e00-\\\\u9fa5]');
    var txt=function(s){var e=document.getElementById(s);return e?e.textContent.trim():null;};

    /* 前置体检：本块直接调用了一串前端函数，只要有一个被改名/删掉，
       ReferenceError 会让后面 EXP_N 条断言一起消失，屏幕只剩一条「求值失败」。
       先点名报出缺的是谁，其余照常跑（缺的那段仍会被 Z1 抓到总数漂移）。 */
    var NEED=['openSettings','closeSheet','openProgLibSheet','openEditor','openPoster','openJtsSheet',
              'openProfile','openTeleSheet','openAboutSheet','openStructSheet','setLang','applyChrome',
              'setDay','setTheme','renderTelemetry','renderPoster','renderSettings','renderMigrateReport','toggleCollars',
              'teleOn','toggleTeleOn','bwSeries','renderBwHint',
              'openKitSheet','setKitTab','gearNew','gearSave','gearDel','gearEdit','gearCancel',
              'kitPickWear','kitPickCompliant','kitKindChange','gearWear',
              'kitPhotoKey','kitPhotoData','kitPhotoPick','kitPhotoDel','kitPhotoDone','renderKitPhoto','gearPhotoWipe',
              'venueNew','venueToggle','venueSetActive','venueApplyRename','venueDel','machAdd','machDel','gearDisp',
              'toggleFavProg','writeLevelSnap','levelSnapshotOf','snapDerived','renderLevelSnapTable','snapEdit','snapNoteEdit','refreshGlHero','resetRecSets','stepRecSet','doExportCsv','exportUnifiedCsv',
              'csvParse','dayIds','computePosterData','computeRecommendedSets','computeJtsVolume',
              'cardioDebt','jtsCalcV6','prescriptionOf','migrateStateV6','migrateStateV7','undoMigrateV7',
              'migrateStateV8','undoMigrateV8','undoMigrate','v8GppDef','v8GppDefs','v8GppDay','v8RenameDayTitles','v8RestoreTitles','blankGppDay',
              'v7SeedVenues','v7AdoptPlanPlateCfg','gearOf','solveLoad','effectiveLoad','stepOf','gearViewOf',
              'venueOf','venueInv','platesPerSide','modeOptions',
              'modeGroups','familyBadge','progRuleOf','planCapacity','strategyFitsMode','checkDayConstraint',
              'libTotal','clone','setsOf','bandOf','wRpeOf','calcGlRank','barKg','fmtLoad','day',
              'stratOf','stratBoundId','strategySource',
              'sbdFamilyOfCat','sbdChipCls','posterCatAgg',
              'applyStructure','activeWeekKeys','recomputeInactive','structureVersion',
              'archivePush','archiveList','archiveGet','archiveDrop','archiveClear','archiveWarn','loadPlanArchive','utf8Len',
              'openArchiveSheet','renderArchiveSheet','restoreArchiveItem','dropArchiveItem','clearArchiveSheet',
              'adoptImportedPlan','showPlanErrors','doExportPlanXlsx','onPlanXlsxFile','closeAllSheets','xStateToPlanDict',
              'planEnvelope','exportPlanJSONText','doExportPlanJSON',
              'unifiedRecords','logMetaRecord','logJsonlText','doExportLogJSONL',
              'validateEnvelope','importPlanFromJSONText','onPlanJSONFile',
              'applyTheme','themeId','paintThemeUI','themeBtnId','segThumb','cycleTheme',
              'markBootFatal','renderBootFail','exportBootStore',
              'readSlice','readLegacy','sliceProbe','unreadableSlices','boot',
              'figWeekList','openFigsSheet','renderFigs','figTicks','figStats','figQuant','figRollMean','figE1','figVolume','figCatVolume','figCatRows','figRpe','figAdh',
              'openEnvSheet','openSciSheet','openIoSheet','openAdvSetSheet','auditCycleGoal','renderGoalAudit','renderJtsInputs',
              'openChartHub','openTrendSheet','openCatVolSheet','openLogSheet','renderLogTable','logRows','fillLogFilters',
              'openAdviceSheet','renderAdviceTable','fillAdviceWeek','adviceSrcWeekOptions','nextWeekAdvice',
              'adviceWeekList','adviceChain','adviceNextStage','adviceStepKg','adviceClamp','adviceStruggle','autoregOf',
              'advTier','advTierName','advCanWrite','advGuard','advApply','advApplyRow','advApplyAll','advApplyAllLabel',
              'advUndo','advUndoLast','advRowAt','advSeqOf','advWriteLoad','advAuditOf','advHasSuffix',
              'advMvKey','advFlash','advPaintTools','advPaintAudit','setAdvTier','fillAdviceTier','onAdvWeekChange','advCurWeek',
              'toggleAdvSettings','topSheet',
              'flashCard','pingDayComplete','edChain','toggleDone','bumpSet','quickLoad','saveEditor','toast','stopTimer',
              'DEFAULT_PLATE_CFG','plateStock','plateSet','plateOn','togglePlateKg',
              'lcTypeOf','lcReset','lcNum','lcCount','lcTotal','lcFieldHtml','lcBodyFields','lcPickType',
              'lcApplyFold','lcToggle','lcPaintTog',
              'renderLoadCalc','readLoadCalc','paintLoadCalc','fillLoadFromCalc',
              'renderEnvSheet','renderEnvLoc','saveDayLoc','dayLoc','setDayLoc','activeWeekNums','renderLocLine',
              'withAutoreg','calibParamKeys','calibCand','calibOverride','calibGrade','calibRun',
              'calibSweep','calibVerdict','openCalibSheet','renderCalib',
              /* v0.28 逻辑债（LD 段）：这一串都是 LD 段直接调的，名字漂了整段会中途抛错 */
              'archMissNote','e1ByWeek','e1Usable','applyLatestE1','renderE1Trend','copyPrevTele',
              'strengthMult','profileCoefLine','setJts','clearJts','jtsKey','saveTele','saveProfile',
              'anchorOf','teleFieldOn','toggleTeleField','renderTeleFields','openTeleSheet',
              'importUnifiedCsv','stratCounts','openStratLibSheet','setStratView','tierColor','flushSave',
              'readyIndexFromScore','jtsToReady','matchReadyIndex','matchReadyPct','proto','defaultTimerCfg',
              'refreshLangSelects','writeSlice','writeError','watchStoreError','saveStructure',
              /* v0.29 动作选择链（B 段）：这一串都是 B 段直接调的；openBrowse 之外的那几个
                 名字只在 JS 拼串的 onclick 里出现，改错了浏览器只是点了没反应 */
              'openBrowse','brGo','brUp','brSearch','brSearchHits','pickAct','openAct','addExercise',
              'catLabel','domOf','mvLabel','actOf','renderAll','renderExercises','save',
              /* v0.47 HX 段（日历引擎 / 哑铃自重视觉）：这一段直接调的函数名单，
                 名字漂了整段会中途抛错，A0 先点名（const 名单 WD_ZH 不在此列，靠 Z0 段名抓） */
              'planPos','daysOnWd','sessionCode','todaySessions','nextSession',
              'saveNick','compileTimeline','weekInfo',
              'setGearKind','setGearField','setGearSides','refreshConsole','fmtStep','e1rm','prefsOf','workoutOf',
              /* v0.48 PX 段（日/周分享图单源/出货/e1RM 同口径）：这一段直接调的函数名单，名字漂了整段会中途抛错 */
              'posterTextBlocks','posterPaintPlan','posterShareName','posterSixLifts','posterIsAcc',
              'posterRowLine','posterFamList','posterFnList',
              'catShort','anchorDoneE1rm','deliverPosterPng','buildPosterCanvas','setPosterMode',
              /* v0.49 HP 段（六边形能力记录单源与评分）：这一段直接调的函数名单，名字漂了整段会中途抛错 */
              'currentGl','hprBuiltin','hprNormalize','hprComplete','hprAxisScore','hprRadarPoints',
              'hprGlValue','hprToday','hprItem','hprName','hprAxisLabel','hprTypeLabel',
              'hprBestText','hprTgtText','hprTryValue','addHprTry','hprToggleBinary','hprSetTarget','delHprItem','addHprCustom','hprItemHtml','renderHpr'];
    var miss=NEED.filter(function(n){ return typeof window[n]!=='function' && !new RegExp('function '+n+'\\\\b').test(document.documentElement.outerHTML); });
    if(miss.length) T('A0 依赖的前端 API 全部存在', false, '缺失: '+miss.join(','));

    /* 整块包一层 try：任何一段抛错（例如某前端函数被改名）过去会带走全部 EXP_N 条
       结果，页面只剩一条「求值失败」——已完成断言的通过/失败信息全部丢失。
       现在保留已跑出的结果，并把中断点报成一条带段名的 FAIL。 */
    var SECT='init';
    try{

    SECT='A'; /* ===== A. 身份与产物版本 ===== */
    T('A1 document.title 含 ExDark Pro', document.title.indexOf('ExDark Pro')>=0, document.title);
    T('A2 document.title 含 v'+EXP+' 且无旧前缀 RPL', document.title.indexOf('v'+EXP)>=0 && document.title.indexOf('RPL')<0, document.title);
    var lg=document.getElementById('logoBtn');
    T('A4 #logoBtn 为按钮且引用三段色阶 brandIcon', !!lg && lg.tagName==='BUTTON' && !!lg.querySelector('use') && !!document.getElementById('brandIcon'), lg&&lg.tagName);
    T('A5 顶栏无版本胶囊 / 无 ProMax / 无 ☰ / 仅 3 按钮',
      !document.querySelector('.chip-hud') && document.body.innerText.indexOf('ProMax')<0
      && document.body.innerText.indexOf('☰')<0 && document.querySelectorAll('.hdr-actions .ico-btn').length===3,
      document.querySelectorAll('.hdr-actions .ico-btn').length);
    T('A6 旧单文件存档(v=5)→三路分片迁移并盖章', LEGACY && state.schemaVer===SCHEMA_STAMP && state.v===undefined
      && (function(){ var q=JSON.parse(localStorage.getItem(LS_WORK)||'null');
                      return !!q && q.schemaVer===SCHEMA_STAMP && q.v===undefined; })(),
      state.schemaVer+'/legacy='+LEGACY);
    T('A7 存档含 lib.domains 五域', !!state.lib && Array.isArray(state.lib.domains) && state.lib.domains.length===5, state.lib&&state.lib.domains&&state.lib.domains.length);
    T('A8 五域顺序 T1.Main→Power', state.lib.domains.map(function(d){return d.id;}).join(',')==='T1.Main,Variation,SBD,Hyper,Power', state.lib.domains.map(function(d){return d.id;}).join(','));
    T('A9 SEED 源标识为 v'+EXP, txt('srcLine')!==null && txt('srcLine').indexOf('RPL_ExDark_v'+EXP)>=0, txt('srcLine'));

    var verNodes=[
      {k:'title', v:document.title},
      {k:'aboutVer', v:txt('aboutVer')||''},
      {k:'p-tag', v:(document.querySelector('.p-tag')||{}).textContent||''},
      {k:'setAboutS', v:txt('setAboutS')||''},
      {k:'srcLine', v:txt('srcLine')||''}
    ];
    var verBad=verNodes.filter(function(n){ return n.v.indexOf('v'+EXP)<0; });
    T('A10 五处版本串同源', verBad.length===0, verBad.length?('失配: '+verBad.map(function(n){return n.k;}).join(',')):('all v'+EXP));
    T('A11 无未替换版本 token', document.documentElement.outerHTML.indexOf('{{VER}}')<0);

    SECT='B'; /* ===== B. 载荷精度 fmtLoad ===== */
    T('B1 fmtLoad(92.5) = 92.5', fmtLoad(92.5)==='92.5', fmtLoad(92.5));
    T('B2 fmtLoad(91.25) = 91.25', fmtLoad(91.25)==='91.25', fmtLoad(91.25));
    T('B3 fmtLoad(100) = 100（无 .0）', fmtLoad(100)==='100', fmtLoad(100));
    T('B4 fmtLoad(90) = 90（无 .0）', fmtLoad(90)==='90', fmtLoad(90));
    T('B5 fmtLoad 无浮点尾巴', fmtLoad(0.1+0.2)==='0.3', fmtLoad(0.1+0.2));
    var boxes=document.querySelectorAll('#exList .lbox b');
    var exs=(day()&&day().exercises)||[];
    var bad=[];
    for(var i=0;i<boxes.length;i++){
      var want=fmtLoad(exs[i]?exs[i].load:0)+'kg';
      var got=boxes[i].textContent.replace(/\\s+/g,'');
      if(got!==want) bad.push(i+':'+got+'!='+want);
    }
    T('B6 卡片 LOAD 全部走 fmtLoad', boxes.length>0 && bad.length===0, boxes.length+'张 '+bad.slice(0,3).join(' '));
    /* 原先写成 /\\.\d0kg$/，只能抓到「两位小数且末位为 0」（如 92.50kg），
       对最常见的 90.0kg 尾巴完全无感 —— 等于恒真。改为 \d* 才能同时抓一/二位。 */
    T('B7 卡片无 .0 尾巴', !Array.prototype.some.call(boxes,function(b){return /\\.\\d*0kg$/.test(b.textContent.replace(/\\s+/g,''));}));

    SECT='C'; /* ===== C. 目标 RPE ===== */
    T('C1 #edTgtRpeBtn 在组策略/疲劳双框内', !!document.getElementById('edTgtRpeBtn') && !!document.getElementById('edTgtRpeBtn').closest('.two-box') && !!document.getElementById('edTgtRpeBtn').closest('.tbox'));
    var cWasOpen=document.getElementById('edSheet').classList.contains('on');
    if(!cWasOpen) openEditor(0);
    var Cboxes=Array.prototype.slice.call(document.querySelectorAll('#edSheet .two-box .tbox'));
    T('C1b 组策略与疲劳两框等高', Cboxes.length===2 && Cboxes[0].offsetHeight>0
      && Math.abs(Cboxes[0].offsetHeight-Cboxes[1].offsetHeight)<=1,
      Cboxes.map(function(b){return b.offsetHeight;}).join('/'));
    if(!cWasOpen) closeSheet('edSheet');
    T('C2 tgtFlow 中文文案', txt('tgtFlow')==='目标 → 执行 → 实际次数体感', txt('tgtFlow'));
    var tb=document.getElementById('edTgtRpeBtn');
    T('C3 中文静态胶囊 = 🎯 目标 RPE 7.5', !!tb && tb.textContent.indexOf('🎯 目标 RPE')>=0, tb&&tb.textContent);

    SECT='D'; /* ===== D. STATUS 仪表舱 ===== */
    T('D1 #teleBrief 为 STATUS 仪表舱', !!document.getElementById('teleBrief') && document.getElementById('teleBrief').classList.contains('status-pod') && (txt('statusSub')||'').length>0, txt('statusSub'));
    var bw=document.getElementById('bwCardLbl').closest('.stat');
    var dn=document.getElementById('doneCardLbl').closest('.stat');
    T('D2 BW 与 DONE 微卡等高', !!bw && !!dn && bw.offsetHeight===dn.offsetHeight, bw&&bw.offsetHeight+'/'+(dn&&dn.offsetHeight));
    T('D3 BW 与 DONE 顶部对齐', !!bw && !!dn && Math.abs(bw.getBoundingClientRect().top-dn.getBoundingClientRect().top)<0.6);
    T('D4 中文微卡标签', txt('bwCardLbl')==='体重' && txt('doneCardLbl')==='完成', txt('bwCardLbl')+'/'+txt('doneCardLbl'));

    SECT='E'; /* ===== E. 设置页七段：我的档案 / 我的训练 / 器械与场地 / 外观与提示 / 数据与报告 / 关于与帮助 / 高级 ===== */
    openSettings();
    var mainRows=Array.prototype.slice.call(document.querySelectorAll('#setSheet .set-row'));
    var heads=Array.prototype.slice.call(document.querySelectorAll('#setSheet .set-sec-hdr')).map(function(h){return h.id;});
    var rowIds=mainRows.map(function(r){ var b=r.querySelector('.sl b'); return b?b.id:''; });
    T('E1 设置主表 16 行', mainRows.length===16, mainRows.length);
    T('E2 七段标题顺序', heads.join(',')==='setProfileHdr,setTrainHdr,setEquipHdr,setAppearHdr,setDataHdr,setAboutHdr,setAdvHdr', heads.join(','));
    T('E3 我的档案 3 行（昵称·我的档案·每日状态）', rowIds.slice(0,3).join(',')==='setNickT,setProfT,setTeleT', rowIds.join(','));
    T('E4 我的训练 4 行（训练计划·自动调整·恢复评估·动作与计划库）', rowIds.slice(3,7).join(',')==='setStructT,setAdvT,setJtsT,setSciT', rowIds.join(','));
    T('E5 器械与场地 2 行', rowIds.slice(7,9).join(',')==='setEnvT,setKitT', rowIds.join(','));
    T('E6 外观与提示 3 行', rowIds.slice(9,12).join(',')==='setThemeT,setLangT,setTimerT', rowIds.join(','));
    T('E7 数据与报告 2 行', rowIds.slice(12,14).join(',')==='setIOT,setFigsT', rowIds.join(','));
    T('E8 关于 1 行 + 高级 1 行（高级默认折叠，数据修复住里面）', rowIds.slice(14).join(',')==='setAboutT,setAdvSetT'
      && document.getElementById('setAdvCard').classList.contains('collapsed'), rowIds.join(','));
    var PsetRect=document.querySelector('#setSheet .panel').getBoundingClientRect();
    T('E12 设置是独立页：sheet 带 page 类、无抽屉把手、面板铺满视口', 
      document.getElementById('setSheet').classList.contains('page')
      && !document.querySelector('#setSheet .grab')
      && PsetRect.top<=0.5 && PsetRect.bottom>=innerHeight-0.5 && PsetRect.width>=innerWidth-0.5,
      'rect='+PsetRect.top+','+PsetRect.bottom+'/'+innerHeight);
    closeAllSheets(); openSettings();
    document.getElementById('setProfGo').click();
    var PprofOn=document.getElementById('profSheet').classList.contains('on');
    T('E13 从设置进子页后，返回先回设置页（不是首页）',
      PprofOn && document.getElementById('setSheet').classList.contains('on')
      && window.__handleBack()===true
      && !document.getElementById('profSheet').classList.contains('on')
      && document.getElementById('setSheet').classList.contains('on'),
      'prof='+PprofOn);
    T('E14 设置页再返回才回首页', window.__handleBack()===true && !document.querySelector('.sheet.on'), '');
    T('E9 环境/科学/导入 hub 行数（环境含杆重/赛扣/配片库存/地点/器械推断五行）', document.querySelectorAll('#envSheet .set-row').length===5
      && document.querySelectorAll('#sciSheet .set-row').length===3
      && document.querySelectorAll('#ioSheet .set-row').length===5,
      document.querySelectorAll('#envSheet .set-row').length+'/'
      +document.querySelectorAll('#sciSheet .set-row').length+'/'
      +document.querySelectorAll('#ioSheet .set-row').length);
    T('E10 组策略库入口存在', !!document.getElementById('setStratLibT'), txt('setStratLibT'));
    /* Extra Dark（v0.39 改名，v0.44/F21 定双语名）：内部 id 仍是 nature —— 存量存档里的
       theme='nature' 不迁移。zh 态对外名是「咖啡纸感」（中文态不许再显示英文名），en 态保留
       「Extra Dark」。这一条钉「双语名各就各位 + 三枚按钮仍在」：名字漂了不会报错，只是按钮上写着旧名。 */
    var natBtn=document.getElementById('thNature');
    var e8Lang=state.lang||'zh';
    setLang('zh'); applyChrome();
    var e8Zh=txt('thNatureT'), e8ZhS=txt('setThemeS');
    setLang('en'); applyChrome();
    var e8En=txt('thNatureT');
    setLang(e8Lang); applyChrome();
    T('E11 三枚主题按钮齐全，nature 槽位 zh=咖啡纸感 / en=Extra Dark（F21：中文态不再显示英文名、无旧名残留、字形是 ☕）',
      !!document.getElementById('thDark') && !!document.getElementById('thLight') && !!natBtn
      && e8Zh==='咖啡纸感'
      && (e8ZhS||'').indexOf('咖啡纸感')>=0
      && ((e8ZhS||'')+(e8Zh||'')).indexOf('纸墨')<0
      && e8En==='Extra Dark'
      && (natBtn.textContent||'').indexOf('☕')>=0,
      e8Zh+' | en:'+e8En+' | '+(e8ZhS||'').slice(0,40));
    closeSheet('setSheet');

    SECT='F'; /* ===== F. 计划库导览（197 条） ===== */
    var okFn=typeof openProgLibSheet==='function';
    T('F1 openProgLibSheet 已定义', okFn);
    if(okFn){
      openProgLibSheet();
      T('F2 计划库面板已打开', document.getElementById('progLibSheet').classList.contains('on'));
      T('F3 计划库 197 条', document.querySelectorAll('#progLibList .prog-card').length===197, document.querySelectorAll('#progLibList .prog-card').length);
      T('F4 每卡有 ID 与库元标签', document.querySelectorAll('#progLibList .prog-star').length===197 && document.querySelectorAll('#progLibList .prog-meta').length===197);
      T('F5 导览横幅文案非空', (txt('progLibNote')||'').length>10, (txt('progLibNote')||'').slice(0,20));
      T('F6 筛选器齐备（家族/目标/自调节/GL/验证）', ['progLibFam','progLibGoal','progLibAuto','progLibGl','progLibVer'].every(function(i){return !!document.getElementById(i);}));
      T('F7 无「应用计划」按钮', !Array.prototype.some.call(document.querySelectorAll('#progLibSheet button'),function(b){return (b.textContent||'').indexOf('应用')>=0;}));
      closeSheet('progLibSheet');
      T('F8 关闭后无 on 状态', !document.getElementById('progLibSheet').classList.contains('on'));
    }
    T('F9 closeAllSheets 含库/环境/科学/导入面板', ['progLibSheet','stratLibSheet','envSheet','sciSheet','ioSheet'].every(function(id){return new RegExp(id).test(String(closeAllSheets));}));

    SECT='G'; /* ===== G. 标题同步接线 ===== */
    var d0=state.structure.dayDefs[0];
    var oldZh=d0.titleZh, oldEn=d0.titleEn;
    d0.titleZh='深蹲主项日测试';
    if(state.day!=='A'){ state.day='A'; }
    renderTelemetry();
    T('G1 dayDefs.titleZh → #dayTitle 同步', txt('dayTitle')==='深蹲主项日测试', txt('dayTitle'));
    d0.titleZh=oldZh; d0.titleEn=oldEn;
    renderTelemetry();
    T('G2 还原后标题回退', txt('dayTitle')!==null && txt('dayTitle').indexOf('深蹲主项日测试')<0, txt('dayTitle'));

    SECT='H'; /* ===== H. 日程标签与约束 ===== */
    T('H1 focusTags 8 个', DAY_FOCUS_TAGS.length===8, DAY_FOCUS_TAGS.length);
    T('H2 constraints 4 个', DAY_CON_DEFS.length===4, DAY_CON_DEFS.length);
    T('H3 含 upperOnly 不含 focusBenchOnly', DAY_CON_DEFS.some(function(c){return c.id==='upperOnly';}) && !DAY_CON_DEFS.some(function(c){return c.id==='focusBenchOnly';}), DAY_CON_DEFS.map(function(c){return c.id;}).join(','));
    /* every() 对空集合恒真，故所有「遍历式」断言先要求集合非空。 */
    T('H4 各日 constraints 已迁移为 upperOnly', state.structure.dayDefs.length>0 && state.structure.dayDefs.every(function(x){return !!x.constraints && typeof x.constraints.upperOnly==='boolean' && !x.constraints.focusBenchOnly;}), state.structure.dayDefs.length);
    T('H5 爆发体能标签存在', DAY_FOCUS_TAGS.some(function(t){return t.id==='tag_power_gpp';}));

    SECT='I'; /* ===== I. 恢复驱动建议组数 ===== */
    var wkKey=String(state.week);
    var dd=state.weeks[wkKey]&&state.weeks[wkKey][state.day];
    var oldReady=dd?dd.readiness:null;
    if(dd){
      resetRecSets();
      dd.readiness=READY[0].zh;
      var r95=computeRecommendedSets();
      T('I1 JTS 95 → readyIdx 0', r95.readyIdx===0, r95.readyIdx+'/'+r95.cycleType);
      T('I2 Total_Multiplier 与四项地标保序', r95.mult>=0.85 && ['sq','bp','dl','upperback'].every(function(k){return r95.lifts[k].mv<r95.lifts[k].mev && r95.lifts[k].mev<r95.lifts[k].mav && r95.lifts[k].mav<r95.lifts[k].mrv;}), r95.mult+'/'+JSON.stringify(r95.patches)+' '+r95.lifts.sq.mv+'<'+r95.lifts.sq.mev+'<'+r95.lifts.sq.mav+'<'+r95.lifts.sq.mrv);
      dd.readiness=READY[4].zh;
      var r45=computeRecommendedSets();
      T('I3 JTS 45 → readyIdx 4', r45.readyIdx===4, r45.readyIdx);
      T('I4 单次推荐 = 周 MAV ÷ 本周主项次数', ['sq','bp','dl'].every(function(k){var v=r45.lifts[k], d=Math.max(1,v.days); return r45[k].rec===Math.max(Math.max(1,Math.round(v.mv/d)),Math.round(v.mav/d));}), r45.sq.rec+' = round('+r45.lifts.sq.mav+'/'+r45.lifts.sq.days+')');
      T('I5 单日推荐落在 MV–MRV 内', ['sq','bp','dl'].every(function(k){return r45[k].rec>=r45[k].min && r45[k].rec<=r45[k].max && r45[k].max>=r45[k].rec+1;}), r45.sq.min+'/'+r45.sq.rec+'/'+r45.sq.max);
      var base=r45.sq.rec;
      stepRecSet('sq',1);
      var rOv=computeRecommendedSets();
      T('I6 stepRecSet 后不被重算覆盖', rOv.sq.cur===base+1 && rOv.sq.isCustom===true, rOv.sq.cur+'/'+rOv.sq.rec+'/'+rOv.sq.isCustom);
      resetRecSets();
      var rRs=computeRecommendedSets();
      T('I7 resetRecSets 清除人工覆盖', rRs.sq.isCustom===false && rRs.sq.cur===rRs.sq.rec, rRs.sq.cur+'/'+rRs.sq.rec);
      dd.readiness=oldReady;
    }

    SECT='J'; /* ===== J. 双语隔离 ===== */
    setLang('zh');
    applyChrome();
    T('J1 中文模式无 COLLLARS 笔误', document.body.textContent.indexOf('COLLLARS')<0);
    T('J2 中文模式无 · Language 残留', document.body.textContent.indexOf('· Language')<0);
    T('J3 中文模式无 · Theme 残留', document.body.textContent.indexOf('· Theme')<0);

    openEditor(0);
    T('J4 编辑器中文目标 RPE', (txt('edTgtRpeBtn')||'').indexOf('🎯 目标 RPE')>=0, txt('edTgtRpeBtn'));
    T('J4b 编辑器含组策略选择器', !!document.getElementById('edStratSel') && document.querySelectorAll('#edStratSel option').length===28, document.querySelectorAll('#edStratSel option').length);
    closeSheet('edSheet');

    setLang('en');
    applyChrome();
    openSettings();
    renderSettings();
    T('J5 EN: tgtFlow 文案', txt('tgtFlow')==='TARGET → RX → ACTUAL REPS & RPE', txt('tgtFlow'));
    var scan=['setProfileHdr','setTrainHdr','setEquipHdr','setAppearHdr','setDataHdr','setAboutHdr','setAdvHdr',
      'setProfT','setProfS','setNickT','setNickS','setAdvSetT','setAdvSetS','setJtsT','setJtsS',
      'setStructT','setStructS','setEnvT','setEnvS','setFigsT','setFigsS','setSciT','setSciS','setIOT','setIOS',
      'setLangT','setLangS','setThemeT','setThemeS','setTimerT','setTimerS',
      'setBarT','setBarS','setCollarT','setCollarS','setPlateT','setPlateS','setLocT','setLocS',
      'setLibT','setLibS','setProgLibT','setProgLibS','setStratLibT','setStratLibS',
      'setCsvT','setCsvS','setPlanT','setPlanS','setJsonT','setJsonS','setLogT','setLogS','setArchT','setArchS',
      'setAboutT','setAboutS','envTitle','sciTitle','ioTitle','envNote','sciNote','ioNote',
      'setNote','csvExpBtn','csvImpBtn'];
    var dirty=[];
    /* 原判定「if(v && HAN.test(v))」让「节点整个没了」也算通过；
       断言的对象是「这些标签存在且是英文」，缺节点必须算失配。 */
    scan.forEach(function(k){ var v=txt(k); if(!v){ dirty.push(k+'=<缺失>'); } else if(HAN.test(v)){ dirty.push(k+'='+v); } });
    T('J6 EN 设置页标签无汉字', dirty.length===0, dirty.slice(0,3).join(' | '));
    T('J7 EN 微卡标签为 BW/DONE', txt('bwCardLbl')==='BW' && txt('doneCardLbl')==='DONE', txt('bwCardLbl')+'/'+txt('doneCardLbl'));
    closeSheet('setSheet');

    openProgLibSheet();
    T('J8 EN 计划库 197 卡全量渲染', document.querySelectorAll('#progLibList .prog-card').length===197, document.querySelectorAll('#progLibList .prog-card').length);
    /* J9/J12 原来把「取不到节点」折成 'x' 再测汉字 —— 空串/缺失恒通过。
       现要求节点存在且有文本，再判汉字。 */
    T('J9 EN 导览横幅存在且无汉字', !!txt('progLibNote') && !HAN.test(txt('progLibNote')), (txt('progLibNote')||'').slice(0,30));
    T('J10 EN 关闭按钮文案', txt('progLibCloseBtn')==='CLOSE', txt('progLibCloseBtn'));
    closeSheet('progLibSheet');

    openEditor(0);
    T('J11 编辑器英文目标 RPE', (txt('edTgtRpeBtn')||'').indexOf('🎯 TARGET RPE')>=0, txt('edTgtRpeBtn'));
    T('J12 编辑器英文标签存在且无汉字', !!txt('edLoadLbl') && !!txt('edModeLbl') && !HAN.test(txt('edLoadLbl')) && !HAN.test(txt('edModeLbl')), txt('edLoadLbl')+'/'+txt('edModeLbl'));
    closeSheet('edSheet');

    setLang('zh');
    applyChrome();
    T('J13 切回中文生效', txt('tgtFlow')==='目标 → 执行 → 实际次数体感', txt('tgtFlow'));

    SECT='K'; /* ===== K. CSV 协议 ===== */
    var CSVN='RPL_ExDark_v'+EXP+'_export.csv';
    T('K1 导出文件名为 v'+EXP, String(doExportCsv).indexOf(CSVN)>=0);
    T('K2 两处落盘（Bridge + 浏览器）', (String(doExportCsv).split(CSVN).length-1)>=2, String(doExportCsv).split(CSVN).length-1);
    T('K3 CSV 仍为 26 列头', !!CSV_COLS && CSV_COLS.length===26, CSV_COLS&&CSV_COLS.length);
    var dw=state.weeks[String(state.week)][state.day];
    var oldPost=JSON.parse(JSON.stringify(dw.post||{}));
    if(!dw.post) dw.post={};
    dw.post.water=2.5; dw.post.duration=45; dw.post.sessionRpe=8; dw.post.joint=3;
    var csv=exportUnifiedCsv();
    var prs=csvParse(csv);
    var tel=prs.filter(function(r){return r.record_type==='TELEMETRY' && +r.week===state.week && r.day===state.day;})[0];
    T('K4 water 写入 rx_text', !!tel && tel.rx_text==='2.5', tel&&tel.rx_text);
    T('K5 duration/sessionRpe/joint 各归其列', !!tel && tel.duration_min==='45' && tel.actual_rpe==='8' && tel.notes==='3', tel&&[tel.duration_min,tel.actual_rpe,tel.notes].join('/'));
    T('K6 解析行键数 = 26', !!tel && (Object.keys(tel).length-1)===26, tel&&Object.keys(tel).length-1);
    dw.post=oldPost;
    /* 只读屏的「导出原始存档」是 JSON 文本，不能走 exportCsv——那条通道 MIME 写死 text/csv，
       系统保存面板会按 MIME 补扩展名（真机实测把 .txt 写成 .txt.csv）。S15 抓不到：
       exportCsv 在 Java 侧确有声明，错的是通道选择而不是方法名。 */
    var ebs=String(exportBootStore);
    T('K7 存档原文导出走 exportDoc + text/plain，不碰 CSV 通道',
      ebs.indexOf('AndroidBridge.exportDoc(')>=0 && ebs.indexOf("'text/plain'")>=0
      && ebs.indexOf('AndroidBridge.exportCsv(')<0,
      'exportDoc='+(ebs.indexOf('AndroidBridge.exportDoc(')>=0)+' plain='+(ebs.indexOf("'text/plain'")>=0)+' csvCall='+(ebs.indexOf('AndroidBridge.exportCsv(')>=0));
    T('K8 存档原文导出两处落盘名一致（Bridge 与浏览器兜底都是 .txt）',
      (ebs.split('exdark_store_backup.txt').length-1)===2, ebs.split('exdark_store_backup.txt').length-1);

    SECT='L'; /* ===== L. 动作库 ===== */
    T('L1 动作总数 260', libTotal()===260, libTotal());
    T('L2 分类数 33', state.lib.cats.length===33, state.lib.cats.length);
    T('L3 种子 8 周', state.structure.totalWeeks===8, state.structure.totalWeeks);
    T('L4 爆发体能域末位', state.lib.domains[4].id==='Power', state.lib.domains[4].id);

    SECT='M'; /* ===== M. v0.05 结构化能力 ===== */
    T('M1 杆重 7 档 10–40kg', BAR_OPTIONS.length===7 && BAR_OPTIONS[0]===10 && BAR_OPTIONS[6]===40, BAR_OPTIONS.join(','));
    T('M2 片种 11 档且视觉宽度严格递减', PLATES.length===11 && PLATES.every(function(p,i){return i===0||PLATES[i-1].cw>p.cw;}), PLATES.map(function(p){return p.kg+':'+p.cw;}).join(' '));
    var p5=PLATES.filter(function(p){return p.kg===5;})[0], p25=PLATES.filter(function(p){return p.kg===2.5;})[0];
    T('M3 5kg 宽度 = 2.5kg 的 1.67 倍', !!p5 && !!p25 && Math.abs(p5.cw/p25.cw-1.67)<0.02, (p5&&p5.cw)+'/'+(p25&&p25.cw));
    var sTop=prescriptionOf({mode:'Top.Single'});
    T('M4 Top.Single → 1×1 + 退阶，共 2 组', sTop.tag==='TOP+BACKOFF' && sTop.sets===2 && sTop.reps===1 && sTop.rx==='1×1 + 1×4' && sTop.backoff===0.10, sTop.rx+'/'+sTop.tag);
    T('M4b Top.Test → 单组 1×1，无退阶', (function(){var x=prescriptionOf({mode:'Top.Test'});return x.rx==='1×1' && x.sets===1 && x.backoff===0;})(), prescriptionOf({mode:'Top.Test'}).rx);
    T('M5 T1.Mod 5+ → AMRAP 徽章', prescriptionOf({mode:'T1.Mod'}).amrap===true && prescriptionOf({mode:'T1.Mod'}).tag==='AMRAP');
    T('M6 RTS → AUTOREG / .DL → DELOAD', prescriptionOf({mode:'RTS.2'}).tag==='AUTOREG' && prescriptionOf({mode:'T1.DL'}).tag==='DELOAD');
    /* AMRAP 唯一判据是协议表 rx 尾部的「+」：模板里那张手抄键名单删了，靠这三条盯住新键。 */
    T('M6b T1.Mod.2/Mod.3/Def/S2/S3 → AMRAP 且 rx 取自表', ['T1.Mod.2','T1.Mod.3','T1.Def','T1.S2','T1.S3'].every(function(m){var x=prescriptionOf({mode:m});return x.amrap===true&&x.tag==='AMRAP'&&/\\+$/.test(x.rx);}))
      && prescriptionOf({mode:'T1.Mod.2'}).rx==='4×3+' && prescriptionOf({mode:'T1.S3'}).rx==='10×1+';
    T('M6c T2.5x5 / T3.Tr / T1.6x6 直组不走 AMRAP', ['T2.5x5','T3.Tr','T1.6x6'].every(function(m){var x=prescriptionOf({mode:m});return x.amrap===false&&x.tag==='STRAIGHT SETS';}), ['T2.5x5','T3.Tr','T1.6x6'].map(function(m){return m+':'+prescriptionOf({mode:m}).rx;}).join(' '));
    /* v0.37 节点⑮ 组策略默认绑定：族表逐键能在库里解析、四类族各绑其名、
       Custom/未知族走兜底；auto 语义不许偷写 strategyId，rx 权威不被绑定触碰。 */
    T('MS1 族→库绑定逐 idx 真能在参考库解析（绑空=静默降级，S41 同腿）',
      Object.keys(STRAT_FAMILY_DEFAULT).every(function(f){return !!stratOf(String(STRAT_FAMILY_DEFAULT[f]));}) && !!stratOf(String(STRAT_FALLBACK_IDX)),
      Object.keys(STRAT_FAMILY_DEFAULT).map(function(f){return f+':'+STRAT_FAMILY_DEFAULT[f];}).join(' '));
    T('MS2 四族默认各绑其名（GZCLP→AMRAP / RTS→RPE 封顶 / TOP→顶重 / CLASSIC→恒重）',
      strategyName(stratBoundId({mode:'T1.Def'})).indexOf('AMRAP')>=0 && strategyName(stratBoundId({mode:'RTS.1'})).indexOf('RPE')>=0
      && stratBoundId({mode:'Top.Set'})===String(STRAT_FAMILY_DEFAULT.TOP) && stratBoundId({mode:'T1.3x3'})===String(STRAT_FAMILY_DEFAULT.CLASSIC),
      ['T1.Def','RTS.1','Top.Set','T1.3x3'].map(function(m){return m+'→'+strategyName(stratBoundId({mode:m}));}).join(' / '));
    T('MS3 Custom 也有默认且等于兜底（恒重组）；未知模式串不炸',
      stratBoundId({mode:'Custom'})===String(STRAT_FALLBACK_IDX) && stratBoundId({mode:'T1.6x6'})===String(STRAT_FAMILY_DEFAULT.GZCLP) && stratBoundId({mode:''})==='',
      stratBoundId({mode:'Custom'})+'|'+stratBoundId({mode:'T1.6x6'}));
    T('MS4 auto/explicit 语义：strategyId 为空判 auto、绑定只读不写回、手选即 explicit',
      (function(){var e={mode:'RTS.2',strategyId:''};var src=strategySource(e);var b=stratBoundId(e);var untouched=e.strategyId===''&&src==='auto'&&b===String(STRAT_FAMILY_DEFAULT.RTS);var f={mode:'RTS.2',strategyId:'1'};return untouched&&strategySource(f)==='explicit'&&stratBoundId(f)==='1';})());
    T('MS5 绑定不动处方权威：带策略 id 的动作与裸动作 rx/groups 一致',
      (function(){var e={mode:'T1.Mod',reps:5,load:100,rx:'3×5+'};var a=prescriptionOf(e);var b=prescriptionOf({mode:e.mode,reps:e.reps,load:e.load,strategyId:stratBoundId(e),rx:e.rx});return a.rx===b.rx&&a.totalSets===b.totalSets&&a.groups.length===b.groups.length;})());
    T('M7 bumpSet 已接 e1RM 账本', String(bumpSet).indexOf('logT1MainE1rm')>=0);
    T('M8 ARMOR 走独立看板（不回写 wk().A）', String(renderTelemetry).indexOf('renderArmorBoard')>=0 && String(openTeleSheet).indexOf('AUX')>=0, 'tele+teleSheet');
    T('M9 设置页分段器为 Tactile Pill', !!document.getElementById('langSeg') && !!document.getElementById('themeSeg'), 'langSeg/themeSeg');
    T('M10 四路分片键位齐全（PREF 13 / WORK 16 / archive 独立）｜档位、场地、装备库、状态监控开关、计算器折叠、昵称进 prefs、写回审计与迁移台账、六边形记录 hpr 与伤病台账 health 进账本；v8 的 gpp/levelSnap 进账本且旧 aux 键已清',
      PREF_KEYS.length===13 && WORK_KEYS.length===16
      && PREF_KEYS.indexOf('nick')>=0
      && PREF_KEYS.indexOf('lcOpen')>=0 && WORK_KEYS.indexOf('lcOpen')<0
      && WORK_KEYS.indexOf('gpp')>=0 && WORK_KEYS.indexOf('levelSnap')>=0 && WORK_KEYS.indexOf('aux')<0
      && WORK_KEYS.indexOf('hpr')>=0 && PREF_KEYS.indexOf('hpr')<0
      && WORK_KEYS.indexOf('health')>=0 && PREF_KEYS.indexOf('health')<0
      && PREF_KEYS.indexOf('advAuto')>=0 && WORK_KEYS.indexOf('advAudit')>=0
      && PREF_KEYS.indexOf('advAudit')<0 && WORK_KEYS.indexOf('advAuto')<0
      && PREF_KEYS.indexOf('venues')>=0 && PREF_KEYS.indexOf('activeVenueId')>=0
      && PREF_KEYS.indexOf('teleOn')>=0 && WORK_KEYS.indexOf('teleOn')<0
      && PREF_KEYS.indexOf('gearKit')>=0 && WORK_KEYS.indexOf('gearKit')<0
      && WORK_KEYS.indexOf('gearDefaults')>=0 && WORK_KEYS.indexOf('migrateBackup')>=0
      && PREF_KEYS.indexOf('gearDefaults')<0
      && Object.keys(LS_BY_KIND).join(',')==='prefs,workout,lib,archive' && LS_BY_KIND.archive===LS_ARCHIVE
      && typeof libDiffOf==='function' && typeof applyLibDiff==='function'
      && typeof archivePush==='function' && typeof loadPlanArchive==='function'
      && WORK_KEYS.indexOf('planArchive')<0 && PREF_KEYS.indexOf('planArchive')<0,
      PREF_KEYS.length+'|'+WORK_KEYS.length+'|'+Object.keys(LS_BY_KIND).join(','));
    T('M11 主题/语言只写轻量偏好', String(setTheme).indexOf('savePrefsOnly')>=0 && String(setLang).indexOf('savePrefsOnly')>=0, 'setTheme/setLang');
    T('M12 动作卡片含处方组次胶囊', document.querySelectorAll('#exList .rx-groups').length>0, document.querySelectorAll('#exList .rx-groups').length);
    /* 「|| .length===0」让面板未打开时也算通过，等于这条从没被测过。
       改为真的打开结构面板、渲染容量行，再逐行核对标注内容。 */
    openStructSheet();
    var vsub=document.querySelectorAll('#stRecSetsBox .vol-sub');
    T('M13 周容量行标注本周主项次数（3 大项 × ≥3 标注）',
      vsub.length===3 && Array.prototype.every.call(vsub,function(s){
        var t=s.textContent;
        return s.querySelectorAll('span').length>=3 && /本周主项/.test(t) && /单次推荐/.test(t) && /单次区间/.test(t);
      }), vsub.length+'行 '+(vsub[0]?vsub[0].textContent.trim().slice(0,24):'-'));
    closeSheet('structSheet');

    SECT='N'; /* ===== N. v0.06 专项 ===== */
    /* N1-N5 HOME / ICON */
    T('N1 顶栏无版本号节点', document.querySelectorAll('.hdr .chip-hud').length===0 && document.querySelector('.brand-line').textContent.indexOf('v'+EXP)<0, document.querySelector('.brand-line').textContent.trim());
    T('N2 可见文案无 ProMax', document.body.innerText.indexOf('ProMax')<0);
    T('N3 顶栏无 ☰ 设置按钮', document.body.innerText.indexOf('☰')<0);
    lg.click();
    T('N4 点 #logoBtn 打开设置页', document.getElementById('setSheet').classList.contains('on'));
    closeSheet('setSheet');
    var bi=document.getElementById('brandIcon');
    T('N5 #brandIcon 为三段色阶 SVG（无咖啡豆 ellipse）', !!bi && bi.querySelectorAll('rect').length===3 && bi.querySelectorAll('ellipse').length===0, bi&&bi.querySelectorAll('rect').length+'/ellipse '+ (bi&&bi.querySelectorAll('ellipse').length));

    /* POSTER N6-N9 */
    openPoster();
    T('N6a 默认日卡标题 W·DAY', txt('postTitle')==='W'+state.week+' · DAY '+(state.day==='AUX'?'A':state.day), txt('postTitle'));
    setPosterMode('week');
    T('N6b 切周卡标题 W·WEEK', txt('postTitle')==='W'+state.week+' · WEEK', txt('postTitle'));
    T('N6c 周卡按钮 on', document.getElementById('postModeWeek').classList.contains('on'));
    setPosterMode('day');
    T('N7 日卡每行含 rx-groups 与 rx-mode', document.querySelectorAll('#postList .p-row .rx-groups').length > 0 && document.querySelectorAll('#postList .p-row .rx-mode').length > 0, document.querySelectorAll('#postList .rx-groups').length+'/'+document.querySelectorAll('#postList .rx-mode').length);
    var wSum=dayIds().reduce(function(n,id){return n+computePosterData('day',state.week,id).tonnage;},0);
    var wData=computePosterData('week',state.week);
    T('N8 周卡吨位 = 各日吨位之和', Math.abs(wData.weekTonnage-wSum)<0.01, wData.weekTonnage+'='+wSum);
    T('N8b 周卡过滤空日不出现 0/0 行', wData.days.every(function(d){return d.totalCount>0;}), wData.days.length);
    var oldTheme=state.theme;
    setTheme('light'); renderPoster();
    var pbg=getComputedStyle(document.querySelector('.poster')).backgroundImage;
    T('N9 亮色主题 poster 背景非深色硬编码', pbg.indexOf('rgb(21, 26, 38)')<0 && pbg.indexOf('#151A26')<0, pbg.slice(0,60));
    setTheme(oldTheme); renderPoster();
    /* 周训练总结升级（三小项计数 + SBD.UpperBack 级功能标注 + 强调配色）：
       归类/类名/聚合是单源三件套，先在钉死的夹具上把算式算死，再拿种子周账验守恒，
       最后真点 DOM 数贴片 —— 配色掉令牌、标注掉类别码、聚合少一族，都会各掉一条。 */
    var P4SNAP=JSON.stringify(state);
    var wagg4=posterCatAgg([{cat:'S.Main',n:1,s:5},{cat:'B.Vari.End',n:1,s:3},{cat:'SBD.UpperBack',n:1,s:4},{cat:'Unmapped',n:1,s:2}]);
    T('N9b 三小项单源：归类四族 / 贴片类名兜底 / 夹具聚合守恒 / 顺序保留',
      sbdFamilyOfCat('S.Vari.End')==='S' && sbdFamilyOfCat('B.Main')==='B' && sbdFamilyOfCat('D.GluteHam')==='D'
      && sbdFamilyOfCat('SBD.UpperBack')==='X' && sbdFamilyOfCat('Hyper.Biceps')==='X' && sbdFamilyOfCat('')==='X'
      && sbdChipCls('S')==='pc-s' && sbdChipCls('Q')==='pc-x'
      && wagg4.fam.S.n===1 && wagg4.fam.B.n===1 && wagg4.fam.D.n===0 && wagg4.fam.X.n===2
      && wagg4.fam.S.s===5 && wagg4.fam.X.s===6
      && wagg4.seen.join('|')==='S.Main|B.Vari.End|SBD.UpperBack|Unmapped',
      'X.s='+wagg4.fam.X.s+' seen='+wagg4.seen.length);
    var N4D=computePosterData('week',state.week);
    var n4fam=['S','B','D','X'].reduce(function(t,f){return t+N4D.weekFam[f].n;},0);
    var n4days=N4D.days.reduce(function(t,d){return t+d.totalCount;},0);
    var n4fn=N4D.weekFnSeen.reduce(function(t,k){return t+N4D.weekFn[k].n;},0);
    var n4sets=['S','B','D','X'].reduce(function(t,f){return t+N4D.weekFam[f].s;},0);
    T('N9c 周数据聚合守恒：四族项数 = 标注项数和 = 全日行数和；组数 = weekPlanSets',
      n4fam===n4days && n4fn===n4days && n4sets===N4D.weekPlanSets && N4D.days.every(function(d){
        var s=0; d.fnSeen.forEach(function(k){ s+=d.fn[k].n; }); return s===d.totalCount;
      }),'fam='+n4fam+' fn='+n4fn+' days='+n4days);
    setPosterMode('week'); renderPoster();
    var LEGAL4={'pc-s':1,'pc-b':1,'pc-d':1,'pc-x':1};
    var famCh4=document.querySelectorAll('#postList .p-fam'), catCh4=document.querySelectorAll('#postList .p-cat');
    T('N9d 周卡贴片渲染：三小项行 + 功能标注逐码行；每片带四族配色之一、文本收在 ×n 且零原始类别码',
      famCh4.length>=4 && catCh4.length>=N4D.weekFnSeen.length
      && Array.prototype.every.call(catCh4,function(c){ var ks=c.className.split(/[ ,]+/);
          return ks.some(function(k){return LEGAL4[k];}); })
      && Array.prototype.every.call(catCh4,function(c){ return /×[0-9]+$/.test(c.textContent.trim()); })
      && Array.prototype.every.call(catCh4,function(c){ return !/[A-Za-z][.][A-Za-z]/.test(c.textContent); }),
      'fam='+famCh4.length+' cat='+catCh4.length+' 码种='+N4D.weekFnSeen.length);
    setPosterMode('day');
    var drow4=document.querySelectorAll('#postList .p-row:not(.p-sub)');
    T('N9e 日卡逐行功能标注：每行恰一片、类名合法、文本非空且零原始类别码',
      drow4.length>0 && drow4.length===document.querySelectorAll('#postList .p-row:not(.p-sub) .p-cat').length
      && Array.prototype.every.call(document.querySelectorAll('#postList .p-row:not(.p-sub) .p-cat'),function(c){
        var ks=c.className.split(/[ ,]+/);
        return c.textContent.trim().length>0 && ks.some(function(k){return LEGAL4[k];})
          && !/[A-Za-z][.][A-Za-z]/.test(c.textContent);
      }), drow4.length+'行');
    T('N9f 周总结纯只读：两轮渲染后 state 与打开前逐字节一致',
      JSON.stringify(state)===P4SNAP,'同='+(JSON.stringify(state)===P4SNAP));
    closeSheet('postSheet');

    /* POSTER PX（v0.48 单源 / 出货 / e1RM 同口径）：文字只从 posterTextBlocks 出一趟，
       DOM 预览与 canvas 各自消费同一份；类别码一律折成短标签（点内无码）；保存走桥剥 data: 前缀。
       本段纯只读：进出各存一份 state，收尾逐字节对账。 */
    var PXSNAP=JSON.stringify(state);
    var lang0=state.lang;
    state.lang='zh'; var csZ=catShort('S.Main');
    state.lang='en'; var csE=catShort('S.Main');
    state.lang='zh'; var csU=catShort('Nope.Xyz');
    state.lang=lang0;
    T('PX1 catShort 双语单源：已知码出短标签（点内无码）、未知码兜其它',
      csZ==='深蹲主项' && csE==='SQ MAIN' && csZ.indexOf('.')<0 && csU==='其它', csZ+'|'+csE+'|'+csU);

    setPosterMode('week'); renderPoster();
    var BWP=posterTextBlocks(computePosterData('week',state.week));
    T('PX2 文案单源：DOM 贴的字与 posterTextBlocks 出货串逐字节相等',
      txt('postTitle')===BWP.title && String(document.getElementById('postTon').textContent)===String(BWP.stats[0].v)
      && String(document.getElementById('postE1').textContent)===String(BWP.stats[1].v), txt('postTitle')+' | '+BWP.title);

    var planPX=posterPaintPlan(BWP);
    T('PX3 画布取字只走 paintPlan：首两行 tag/title、每行都不含原始类别码',
      planPX[0].k==='tag' && planPX[1].k==='title' && planPX[0].t===BWP.tag && planPX[1].t===BWP.title
      && planPX.every(function(p){ return !/[A-Za-z][.][A-Za-z]/.test(p.t); }), planPX.length+'行');

    setPosterMode('day'); renderPoster();
    var px4cv=[].slice.call(document.querySelectorAll('#postList .p-cat'));
    T('PX4 日卡功能标注零原始类别码（走 catShort 缩略口径）',
      px4cv.length>0 && px4cv.every(function(c){ return c.textContent.indexOf('.')<0; }), px4cv.length+'片');

    var nD5=posterShareName('day'), nW5=posterShareName('week');
    T('PX5 分享图文件名：日/周相异、跟随版本位、以 .png 收尾',
      nD5!==nW5 && /^RPL_ExDark_v[0-9]/.test(nD5) && /_share_day[.]png$/.test(nD5) && /_share_week[.]png$/.test(nW5), nD5+' | '+nW5);

    var oldB6=window.AndroidBridge; var cap6=null;
    window.AndroidBridge={exportDoc:function(n,m,b){ cap6={n:n,m:m,b:b}; }};
    var ok6=deliverPosterPng({toDataURL:function(){ return 'data:image/png;base64,QUJDRA=='; }});
    T('PX6 出货走桥：image/png + 剥 data: 前缀的裸 base64 + 桥点名一致',
      ok6===true && !!cap6 && cap6.m==='image/png' && cap6.b==='QUJDRA==' && cap6.b.indexOf(',')<0
      && /^RPL_ExDark_v[0-9].*_share_day[.]png$/.test(cap6.n), cap6?(cap6.m+' '+cap6.b):'null');
    window.AndroidBridge=oldB6;

    var six7=posterSixLifts();
    T('PX7 周卡六项来自档案单源：恰六项、标签值齐',
      six7.length===6 && six7.every(function(o){ return !!o.l && o.v!==undefined && String(o.v).length>0; }), six7.length);

    setPosterMode('day');
    var lang8=state.lang, nick8=state.nick;
    state.nick='测试者';
    var B8=posterTextBlocks(computePosterData('day',state.week));
    T('PX8 出货尾注恒为品牌串（打气模块已删除）、署名走 nickName',
      B8.foot===L('EXDARK PRO · 力量举训练日志','EXDARK PRO · IRON LOG') && B8.sign==='— 测试者', B8.foot+' | '+B8.sign);
    state.nick=nick8; state.lang=lang8;

    setPosterMode('week'); renderPoster();
    var dispW=document.getElementById('postBwBox').style.display;
    setPosterMode('day'); renderPoster();
    var dispD=document.getElementById('postBwBox').style.display;
    T('PX10 周图关 BW 格、日图恢复', dispW==='none' && dispD==='', dispW+' / '+dispD);
    T('PX11 分享图段纯只读：全程渲染后 state 与段首逐字节一致', JSON.stringify(state)===PXSNAP, String(JSON.stringify(state)===PXSNAP));

    /* ACT N10-N15 */
    /* N10 原来在赛扣关闭、编辑器未开时取样 —— NodeList 恒空，every() 恒真。
       现显式开赛扣、重渲染，确认节点真的存在，再判「无文字」。 */
    var collarWasOn=collarsOn();
    if(!collarWasOn) toggleCollars();
    var clamps=document.querySelectorAll('.pv-clamp');
    T('N10 赛扣视觉已渲染且无文字', clamps.length>0 && Array.prototype.every.call(clamps,function(x){return x.textContent.trim()==='';}), clamps.length+'个');
    if(!collarWasOn) toggleCollars();
    var hsl=function(h){
      var r=parseInt(h.slice(1,3),16)/255,g=parseInt(h.slice(3,5),16)/255,b=parseInt(h.slice(5,7),16)/255;
      var mx=Math.max(r,g,b),mn=Math.min(r,g,b),l=(mx+mn)/2,s=mx===mn?0:(mx-mn)/(1-Math.abs(2*l-1));
      return {l:l*100,s:s*100};
    };
    /* N11/N12：原来直接 PLATES.filter(...)[0].c —— 一旦这档片被删，取 .c 抛错会
       让整块 150 项断言一起消失（只剩一条「求值失败」）。改为先判存在。 */
    var p25c=PLATES.filter(function(p){return p.kg===2.5;})[0];
    T('N11 2.5kg 片存在且亮度 < 20%', !!p25c && hsl(p25c.c).l<20, p25c?hsl(p25c.c).l.toFixed(1):'2.5kg 片缺失');
    var micros=PLATES.filter(function(p){return p.kg<=1.25;});
    T('N12 ≤1.25kg 片存在且饱和度 < 8%', micros.length>0 && micros.every(function(p){return hsl(p.c).s<8;}), micros.map(function(p){return p.kg+':'+hsl(p.c).s.toFixed(1);}).join(' '));
    var rl=document.querySelector('#exList .rbox label');
    T('N13 .rbox label 字号 ≥10px', !!rl && parseFloat(getComputedStyle(rl).fontSize)>=10, rl&&getComputedStyle(rl).fontSize);
    var md=document.createElement('div'); md.innerHTML=modeOptions('');
    var groups=md.querySelectorAll('optgroup');
    var groupAt=function(name){
      for(var i=0;i<groups.length;i++) if(groups[i].label.indexOf(name)>=0) return groups[i];
      return null;
    };
    var valsOf=function(g){ return g?Array.prototype.map.call(g.querySelectorAll('option'),function(x){return x.value;}):[]; };
    /* 分组与顺序都从 SEED.proto 派生（模板里五张手抄 ORDER 数组已删）：
       这三条按「组名 + 组内键序」硬写期望，协议表加行/改序就会红 —— 那是有意的 witnesses。 */
    T('N13b modeOptions 渲染 7 组（TOP/T1/T2/T3/RTS/DL/CUSTOM）', groups.length===7, groups.length+'组:'+Array.prototype.map.call(groups,function(x){return x.label;}).join('|'));
    var allOpts=[]; Array.prototype.forEach.call(groups,function(g){ allOpts=allOpts.concat(valsOf(g)); });
    var protoKeys=Object.keys(SEED.proto);
    T('N13c 下拉选项 = SEED.proto 键集，不多不少不重复', allOpts.length===protoKeys.length && protoKeys.every(function(m){return allOpts.indexOf(m)>=0;}) && allOpts.filter(function(m,i){return allOpts.indexOf(m)!==i;}).length===0, allOpts.length+'/'+protoKeys.length);
    var T1_EXPECT='T1.Mod,T1.Mod.2,T1.Mod.3,T1.Def,T1.S2,T1.S3,T1.6x6,T1.3x3,T1.5x5';
    var t1vals=valsOf(groupAt('T1'));
    T('N14 T1 组序 Mod 1→2→3 → Def 1→2→3 → 6×6 → Classic 3×3/5×5', t1vals.join(',')===T1_EXPECT, t1vals.join(','));
    T('N15 各组首项 TOP=Top.Single / T2=T2.Mod / T3=T3.Mod / DL=T1.DL',
      valsOf(groupAt('TOP'))[0]==='Top.Single' && valsOf(groupAt('T2'))[0]==='T2.Mod'
      && valsOf(groupAt('T3'))[0]==='T3.Mod' && valsOf(groupAt('DELOAD'))[0]==='T1.DL',
      [valsOf(groupAt('TOP'))[0],valsOf(groupAt('T2'))[0],valsOf(groupAt('T3'))[0],valsOf(groupAt('DELOAD'))[0]].join('/'));
    T('N15b MODE_LABEL 与流派徽章覆盖全部 proto 键（缺一个就渲染成裸键名）', protoKeys.every(function(m){
      return typeof MODE_LABEL[m]==='string' && MODE_LABEL[m].length>0 && familyBadge(m)!=='';
    }), protoKeys.filter(function(m){return !MODE_LABEL[m]||familyBadge(m)==='';}).join(','));

    /* v0.24 T2/T3 完整分支 N28：协议表加了 T2.Mod.3 / T2.Def.2 / T2.Def.3 三行，
       键、组次、分支元数据、下拉组序、AMRAP 判定、契约进阶阈值六处都要跟上。
       少一条 witness 就意味着「加行只加了一半」，而那一半不会有任何报错。 */
    var v24=['T2.Mod.3','T2.Def.2','T2.Def.3'];
    T('N28a 三个新键进了 proto 且组次/tier/分支元数据与协议表一致',
      v24.every(function(m){return !!SEED.proto[m];})
      && SEED.proto['T2.Mod.3'].sets===4 && SEED.proto['T2.Mod.3'].reps===4 && SEED.proto['T2.Mod.3'].repBranch==='Mod' && SEED.proto['T2.Mod.3'].stage===3
      && SEED.proto['T2.Def.2'].sets===3 && SEED.proto['T2.Def.2'].reps===8 && SEED.proto['T2.Def.2'].repBranch==='Def' && SEED.proto['T2.Def.2'].stage===2
      && SEED.proto['T2.Def.3'].sets===3 && SEED.proto['T2.Def.3'].reps===6 && SEED.proto['T2.Def.3'].tier==='T2',
      v24.map(function(m){return m+'='+JSON.stringify(SEED.proto[m]||null);}).join(' '));
    var T2_EXPECT='T2.Mod,T2.Vol,T2.Mod.3,T2.Def,T2.Def.2,T2.Def.3,T2.Tr,T2.5x5';
    var T3_EXPECT='T3.Mod,T3.Def,T3.Tr,T3.Power,T3.Tech';
    var t2vals=valsOf(groupAt('T2')), t3vals=valsOf(groupAt('T3'));
    T('N28b T2 组序 Mod 1→2→3 → Def 1→2→3 → Tr → APP 5×5', t2vals.join(',')===T2_EXPECT, t2vals.join(','));
    T('N28c T3 组序 Mod→Def→Tr → APP 高翻/技术变式', t3vals.join(',')===T3_EXPECT, t3vals.join(','));
    T('N28d 三个新键都是直组（不走 AMRAP 徽章）',
      v24.every(function(m){return prescriptionOf({mode:m}).amrap!==true;}),
      v24.map(function(m){return m+':'+prescriptionOf({mode:m}).tag;}).join(' '));
    var prT3m=String(progRuleOf('T3.Mod')), prT3d=String(progRuleOf('T3.Def'));
    var prDef=String(progRuleOf('__no_such_mode__'));
    T('N28e T3 进阶阈值取自契约：Mod 18 次 / Def 25 次，三个新键各有规则（不落 _default）',
      prT3m.indexOf('>=18')>=0 && prT3d.indexOf('25')>=0 && prT3m.indexOf('>=15')<0
      && v24.every(function(m){var r=String(progRuleOf(m));return r.length>0 && r!==prDef;}),
      prT3m+' / '+prT3d);

    /* MIGRATION N16-N17 */
    var fake={
      structure:{blocks:[{workMode:'SS'}],dayDefs:[{id:'A'}]},
      weeks:{'1':{A:{exercises:[{mode:'SS',cat:'S.Main',reps:3,rx:'8×2 @RPE8 自定义'},{mode:'T1.Def.2',cat:'B.Main',reps:2},{mode:'T2.S3',cat:'D.Main',reps:1}]}}},
      jts:{'1_B':{sleep:8}},
      e1rmLog:[{id:'W1_A_9_Squat',mode:'SL',week:1,row:9,day:'A',e1rm:140}]
    };
    migrateStateV6(fake);
    var fakeModes=fake.weeks['1'].A.exercises.map(function(e){return e.mode;}).join(',');
    T('N16a 旧模式按新方向迁移 SS/T1.Def.2/T2.S3', fakeModes==='T1.3x3,T1.S2,T2.Tr', fakeModes);
    T('N16b 结构块 workMode 迁移', fake.structure.blocks[0].workMode==='T1.3x3', fake.structure.blocks[0].workMode);
    T('N16c JTS 日级键→周级键', !!fake.jts['W1'] && fake.jts['W1'].sleep===8, JSON.stringify(fake.jts));
    T('N17 e1RM 账本模式迁移且行/周/日/e1RM 不丢', fake.e1rmLog[0].mode==='T1.5x5' && fake.e1rmLog[0].row===9 && fake.e1rmLog[0].e1rm===140 && fake.e1rmLog[0].id==='W1_A_9_Squat', JSON.stringify(fake.e1rmLog[0]));
    T('N23 迁移只换模式键，不改写用户自定义 rx', fake.weeks['1'].A.exercises[0].rx==='8×2 @RPE8 自定义' && fake.weeks['1'].A.exercises[0].mode==='T1.3x3', fake.weeks['1'].A.exercises[0].rx);
    /* 反向：规范键必须原样穿过迁移表，否则「T1.Mod.2 被迁成别的」会把新计划自己写坏。 */
    var keep=['T1.Mod.2','T1.Mod.3','T1.Def','T1.S2','T1.S3','T2.5x5','T3.Power','T3.Tech','T1.Mod'];
    T('N16d 规范键不被二次迁移', keep.every(function(m){var f={structure:{blocks:[]},weeks:{'1':{A:{exercises:[{mode:m}]}}}};migrateStateV6(f);return f.weeks['1'].A.exercises[0].mode===m;}), keep.join(','));

    /* MIGRATION V8（F24：Armor→GPP + F2 日名 + Level 锚点）。migrateStateV8 是纯函数：吃一个
       state 就地变形并返回它，不碰真账本、不 save —— 所以能在假 v7 账本上直接跑。撤销腿单独验
       v8RestoreTitles（undoMigrateV8 会 save+renderAll，那是整机副作用，不进单元判据）。
       链条会先跑 migrateStateV7（内部串 V6）：假账本 exercises 为空，V7 只补场馆/派生、
       不动日名与 aux，故不干扰下面对 v8 的判定。 */
    var v8fake={
      schemaVer:7,
      aux:[
        {domain:'恢复', item:'负重引体', metricType:'load', target:20, targetUnit:'kg', intensity:'RPE7'},
        {domain:'恢复', item:'雪橇推行', rx:'4×20m', intensity:'轻松'}
      ],
      structure:{blocks:[], dayDefs:[
        {id:'A', titleZh:'重型三项', titleEn:'HEAVY SBD'},
        {id:'B', titleZh:'上肢推举', titleEn:'UPPER PUSH'},
        {id:'C', titleZh:'自定义日', titleEn:'My Custom'},
        {id:'D', titleZh:'弱链变式', titleEn:'VARIATION & RTS'}
      ]},
      weeks:{'1':{
        A:{exercises:[]},
        auxDays:[[true,true,false,false,false,false,false],[false,false,false,false,false,false,false]]
      }},
      profile:{}
    };
    migrateStateV8(v8fake);
    var v8gpp=v8fake.gpp||[], v8wk=v8fake.weeks['1'], v8dd=v8fake.structure.dayDefs;
    T('V8a aux 定义迁成 gpp 且 aux 键删除', v8gpp.length===2 && v8fake.aux===undefined, 'gpp='+v8gpp.length+' aux='+v8fake.aux);
    T('V8b target 文本回落进 rx，已有 rx 原样保留', v8gpp[0]&&v8gpp[0].rx==='20'&&v8gpp[0].item==='负重引体'&&v8gpp[1]&&v8gpp[1].rx==='4×20m', (v8gpp[0]||{}).rx+' / '+(v8gpp[1]||{}).rx);
    T('V8c auxDays 布尔行→gppDays 打卡格：done 位逐位保留、新实测字段留空、auxDays 删除',
      v8wk.auxDays===undefined && Array.isArray(v8wk.gppDays) && v8wk.gppDays.length===2
      && v8wk.gppDays[0].done[0]===true && v8wk.gppDays[0].done[1]===true && v8wk.gppDays[0].done[2]===false
      && v8wk.gppDays[0].actualValue==='' && v8wk.gppDays[0].actualRpe===null
      && v8wk.gppDays[1].done.every(function(b){return b===false;}),
      JSON.stringify(v8wk.gppDays[0]));
    T('V8d profile 水平锚点补 0、levelSnap 补空数组（不许 undefined 进 WORK_KEYS 序列化）',
      v8fake.profile.pullupAddedKg===0 && v8fake.profile.dipAddedKg===0 && Array.isArray(v8fake.levelSnap) && v8fake.levelSnap.length===0,
      v8fake.profile.pullupAddedKg+'/'+v8fake.profile.dipAddedKg+'/'+JSON.stringify(v8fake.levelSnap));
    T('V8e F2 日名：旧内置默认名换成 F2 名，用户自定义过的原样保留',
      v8dd[0].titleZh==='模拟赛日' && v8dd[0].titleEn==='Mock Day' && v8dd[1].titleZh==='卧推日' && v8dd[3].titleZh==='变式日'
      && v8dd[2].titleZh==='自定义日' && v8dd[2].titleEn==='My Custom',
      v8dd.map(function(d){return d.titleZh;}).join(','));
    var v8bk=(v8fake.migrateBackup||{}).v8||{}, v8rep=(v8fake.migrateReport||{}).v8||{};
    T('V8f 迁移台账：backup 存 aux 原文 + 改名记录，report 记 gppDefs/titlesRenamed/fresh',
      Array.isArray(v8bk.aux) && v8bk.aux.length===2 && Array.isArray(v8bk.titles) && v8bk.titles.length===3
      && v8rep.gppDefs===2 && v8rep.titlesRenamed===3 && v8rep.fresh===false,
      'bk.aux='+(v8bk.aux||[]).length+' bk.titles='+(v8bk.titles||[]).length+' gppDefs='+v8rep.gppDefs+' titlesRenamed='+v8rep.titlesRenamed);
    v8RestoreTitles(v8fake, v8bk.titles);
    T('V8g 撤销日名：F2 名放回旧内置名，用户自定义日不受影响',
      v8dd[0].titleZh==='重型三项' && v8dd[1].titleZh==='上肢推举' && v8dd[3].titleZh==='弱链变式' && v8dd[2].titleZh==='自定义日',
      v8dd.map(function(d){return d.titleZh;}).join(','));
    var v8fresh={
      schemaVer:7,
      aux:[{domain:'恢复', item:'农夫行走', rx:'3×40m'}],
      structure:{blocks:[], dayDefs:[{id:'A', titleZh:'重型三项', titleEn:'HEAVY SBD'}]},
      weeks:{'1':{A:{exercises:[]}}},
      profile:{}
    };
    migrateStateV8(v8fresh, true);
    var v8frep=(v8fresh.migrateReport||{}).v8||{};
    T('V8h fresh 首建跳过日名改名（titlesRenamed=0）但仍迁 aux→gpp',
      v8fresh.structure.dayDefs[0].titleZh==='重型三项' && v8frep.titlesRenamed===0 && v8frep.fresh===true && (v8fresh.gpp||[]).length===1,
      'title='+v8fresh.structure.dayDefs[0].titleZh+' renamed='+v8frep.titlesRenamed+' gpp='+(v8fresh.gpp||[]).length);

    /* 约束引擎契约化 N24：模板里那份手抄模式名单已删，判定读 PLAN_SCHEMA.constraint_rules，
       与导出侧 xValidateWorkouts / Python 的 _pred_hit 同一条判据。 */
    var oldDefs=clone(state.structure.dayDefs);
    state.structure.dayDefs=[
      {id:'A',constraints:{forbidHeavySbd:true},focusTags:[]},
      {id:'B',constraints:{deloadCap:true},focusTags:[]},
      {id:'C',constraints:{upperOnly:true},focusTags:[]},
      {id:'D',constraints:{},focusTags:['tag_deload_rec']}
    ];
    var cHeavy=checkDayConstraint('A',{cat:'S.Main',mode:'T1.Mod.2',targetRpe:7});
    var cTop=checkDayConstraint('A',{cat:'S.Main',mode:'Top.Set',targetRpe:6});
    var cPower=checkDayConstraint('A',{cat:'D.Vari.Power',mode:'T3.Power',targetRpe:8});
    var cTech=checkDayConstraint('A',{cat:'S.Vari.End',mode:'T3.Tech',targetRpe:9});
    var cRpe=checkDayConstraint('B',{cat:'Hyper.Pecks',mode:'T2.Mod',targetRpe:8});
    var cLow=checkDayConstraint('B',{cat:'Hyper.Pecks',mode:'T2.Mod',targetRpe:7});
    var cUpper=checkDayConstraint('C',{cat:'S.Vari.Top',mode:'T2.Mod',targetRpe:6});
    var cTag=checkDayConstraint('D',{cat:'B.Main',mode:'T3.Tech',targetRpe:6});
    var cMain=checkDayConstraint('D',{cat:'B.Main',mode:'T3.Tech',targetRpe:9});
    state.structure.dayDefs=oldDefs;
    var rule0=(PLAN_SCHEMA.constraint_rules||[])[0]||{};
    T('N24a 禁止 Heavy SBD：拦 T1.Mod.2 / 主项池 Top，放 T3.Power / T3.Tech', cHeavy.bad===true && cTop.bad===true && cPower.bad===false && cTech.bad===false, [cHeavy.bad,cTop.bad,cPower.bad,cTech.bad].join('/'));
    T('N24b 减载上限：RPE 8 拦、RPE 7 放（阈值只来自契约）', cRpe.bad===true && cLow.bad===false, cRpe.bad+'/'+cLow.bad);
    T('N24c 仅限上肢日：拦下肢 T2 容量组', cUpper.bad===true, String(cUpper.bad));
    T('N24d 减载标签日按 also_when_tag 生效，且只看 RPE', cTag.bad===false && cMain.bad===true, cTag.bad+'/'+cMain.bad);
    T('N24e 违规文案取自契约 why（模板不再手抄句子）', String(cHeavy.why).indexOf(rule0.why)>=0 && String(cHeavy.why).indexOf(rule0.when)>=0, cHeavy.why);

    T('N25 每个 proto 键都取到契约进阶规则（无一条落空），预览行已接 progRuleOf', protoKeys.every(function(m){return String(progRuleOf(m)).length>0;}) && String(paintRxPreview).indexOf('progRuleOf')>=0,
      protoKeys.filter(function(m){return String(progRuleOf(m)).length===0;}).join(','));
    var capN=planCapacity();
    T('N26a 计划容量读契约 capacity：周 1..52 / 块 1..16', capN.maxWeeks===52 && capN.maxBlocks===16 && capN.minWeeks===1 && capN.minBlocks===1, JSON.stringify(capN));
    T('N26b 编辑器容量接线：渲染与保存都取 planCapacity，不写死 8 块', String(renderStructSheet).indexOf('planCapacity')>=0 && String(saveStructure).indexOf('cap.maxBlocks')>=0 && String(saveStructure).indexOf('Math.min(8,')<0);
    T('N26c 三处「16 周下限」已改为跟随真实总周数', ['figTotalWeeks','statusSpark','statusCells'].every(function(f){return String(window[f]).indexOf('Math.max(16')<0;}), ['figTotalWeeks','statusSpark','statusCells'].map(function(f){return String(window[f]).indexOf('Math.max(16')>=0?f:'-';}).join(','));
    var sh1=stratItems().filter(function(x){return String(x.idx)==='1';})[0]||{};
    var sh1Hint=(sh1.modeHint||[]).join(',');
    T('N27a 策略库带上 mode_hint（组策略总表 J–L 进了种子）', stratItems().every(function(x){return Array.isArray(x.modeHint);}) && sh1Hint.indexOf('T1.Mod')>=0 && !!sh1.strategyId, JSON.stringify([sh1.strategyId,sh1.tierStd,sh1.modeHint]));
    T('N27b modeHint 前缀匹配：T1.Mod.2 命中 T1.Mod，T1.Modx 不命中', strategyFitsMode({modeHint:['T1.Mod']},'T1.Mod.2')===true && strategyFitsMode({modeHint:['T1.Mod']},'T1.Modx')===false && strategyFitsMode({modeHint:[]},'T1.Mod')===false);
    T('N27c 策略选择器按当前模式分组，27 条 + 无策略 一条不隐藏', (function(){
      renderStratOptions('', 'T1.Mod');
      var sel=document.getElementById('edStratSel');
      return sel && sel.querySelectorAll('optgroup').length>=1 && sel.querySelectorAll('option').length===stratItems().length+1;
    })(), (function(){var s=document.getElementById('edStratSel');return s?s.querySelectorAll('optgroup').length+'组/'+s.querySelectorAll('option').length+'项':'选择器缺失';})());

    /* JTS 五模块 N18-N21 */
    var oldJts=JSON.stringify(state.jts||{});
    if(!state.jts) state.jts={};
    state.jts['W'+state.week]={sleep:10,stress:0,health:10,drive:10,willingness:10,soreness:0};
    var oldDay=state.day;
    openJtsSheet();
    var s1=txt('jtsScore');
    T('N18a JTS 面板标题为周级', (txt('jtsWeekDay')||'').indexOf('DAY')<0 && (txt('jtsWeekDay')||'').indexOf('W'+state.week)>=0, txt('jtsWeekDay'));
    setDay('B');
    var s2=txt('jtsScore');
    T('N18b 切 DAY 不改变 #jtsScore', s1===s2 && s1!=='—', s1+'→'+s2);
    closeSheet('jtsSheet'); setDay(oldDay);
    /* 六维改版（D14）：M_sleep/M_stress/CRS 三因子已退役，R=归一均值、recMult=recBase+B_gpp−F_gpp。 */
    function sixD(over){ var b={sleep:4,stress:4,fatigue:4,soreness:4,motivation:4,energy:4}; for(var k in over) b[k]=over[k]; return jtsCalcV6(b); }
    var sa=sixD({sleep:1}), sb=sixD({sleep:4}), sc3=sixD({sleep:7});
    var so1=sixD({soreness:1}), so7=sixD({soreness:7});
    T('N19a 正向维（睡眠）升 → R 单调增；反向维（酸痛）升 → R 单调减',
      sa.R<sb.R && sb.R<sc3.R && so7.R<so1.R, 'sleep:'+sa.R+'/'+sb.R+'/'+sc3.R+' sore:'+so1.R+'/'+so7.R);
    var fa=sixD({fatigue:1}), f7=sixD({fatigue:7});
    var two=jtsCalcV6({sleep:7,stress:1}), three=jtsCalcV6({sleep:7,stress:1,fatigue:1});
    T('N19b 反向维（疲劳）升 → R 降；已填=2 → R=null（未填剔除），已填=3 → R 有数',
      f7.R<fa.R && two.R===null && typeof three.R==='number', 'fatigue:'+fa.R+'/'+f7.R+' two:'+two.R+' three:'+three.R);
    var worst6={sleep:1,stress:7,fatigue:7,soreness:7,motivation:1,energy:1};
    var best6={sleep:7,stress:1,fatigue:1,soreness:1,motivation:7,energy:7};
    var lo=jtsCalcV6(worst6), hi=jtsCalcV6(best6), empty=jtsCalc({});
    T('N19c REC 乘数夹在 [0.55,1.25]、R 钳在 0–100、CRS 已退役（不再返回 crs）',
      lo.R===0 && hi.R===100 && lo.recMult>=0.55 && lo.recMult<=1.25 && hi.recMult>=0.55 && hi.recMult<=1.25 && empty.crs===undefined,
      'R '+lo.R+'/'+hi.R+' REC '+lo.recMult+'/'+hi.recMult+' crs='+(empty.crs===undefined?'退役':'残留'));
    var wwx=state.weeks[String(state.week)];
    var oldGpp=JSON.stringify(wwx.gppDays||[]);
    function n20cell(mask){ return {done:mask.slice(),actualValue:'',actualUnit:'',actualRpe:null,note:''}; }
    var giById={}; (GPP_SCHEMA.items||[]).forEach(function(it){ giById[it.id]=it; });
    function menuRowOf(itemId){ var arr=GPP_SCHEMA.weekly_menu||[]; for(var i=0;i<arr.length;i++) if((arr[i].item_ids||[])[0]===itemId) return i; return -1; }
    var gd=clone(wwx.gppDays||[]);
    while(gd.length<GPP_SCHEMA.weekly_menu.length) gd.push(n20cell([0,0,0,0,0,0,0]));
    gd.forEach(function(c){ if(c&&c.done) c.done=c.done.map(function(){return 0;}); });
    gd[menuRowOf('zone2_walk')]=n20cell([1,1,0,0,0,0,0]);   /* Zone 2 快走 ×2（有上肢债） */
    gd[menuRowOf('neat_steps')]=n20cell([1,1,1,1,1,1,0]);   /* NEAT 步数 ×6（前 5 天免债 → 有效 1 天） */
    wwx.gppDays=gd;
    var cdx=cardioDebt(state.week);
    var z2=giById['zone2_walk'], nt=giById['neat_steps'];
    var wantLower=Number(((2*(+z2.debt_lower||0))+Math.max(0,6-(+nt.debt_free_days||0))*(+nt.debt_lower||0)).toFixed(3));
    var wantUpper=Number(((2*(+z2.debt_upper||0))+Math.max(0,6-(+nt.debt_free_days||0))*(+nt.debt_upper||0)).toFixed(3));
    T('N20 GPP 下肢债逐已完成项累加 debt_lower，NEAT 前 debt_free_days 天免债（契约现取，不写死）：Zone2×2 + NEAT×6 → '+wantLower,
      wantLower>0 && Math.abs(cdx.lower-wantLower)<0.001, cdx.lower+' vs '+wantLower);
    T('N20b GPP 上肢债走独立通道 debt_upper（不与下肢互算）：Zone2 带上肢债、NEAT 不带 → '+wantUpper,
      wantUpper>0 && Math.abs(cdx.upper-wantUpper)<0.001, cdx.upper+' vs '+wantUpper);
    wwx.gppDays=JSON.parse(oldGpp);
    T('N21a SRU 单组权重 RPE 5/7/8.5 → 0.76/1.00/1.18', Math.abs(wRpeOf({rpe:5})-0.76)<0.001 && Math.abs(wRpeOf({rpe:7})-1.0)<0.001 && Math.abs(wRpeOf({rpe:8.5})-1.18)<0.001, [wRpeOf({rpe:5}),wRpeOf({rpe:7}),wRpeOf({rpe:8.5})].join('/'));
    var setsBefore=setsOf('T2.Mod');
    var ee={mode:'T2.Mod',strategyId:'6'};
    T('N21b setsOf 不受 strategyId 影响', setsOf(ee.mode)===setsBefore && setsBefore===4, setsBefore);
    T('N21c bandOf 五档映射', ['submv','under','optimal','high','over'].every(function(id,i){return bandOf(10,12,14,16,[8,11,13,15,17][i]).id===id;}), [8,11,13,15,17].map(function(v){return bandOf(10,12,14,16,v).id;}).join(','));
    T('N21d SRU 不改变 setsOf（周地标仍由 setsOf 计算）', String(weekPlannedSets).indexOf('setsOf')>=0 && String(weekPlannedSru).indexOf('setsOf')>=0);
    state.jts=JSON.parse(oldJts);

    /* GL 段位 N22 */
    T('N22a 44.99 → 青铜 5★', calcGlRank(44.99).labelZh==='青铜 5★', calcGlRank(44.99).labelZh);
    T('N22b 45.00 → 白银 1★', calcGlRank(45.00).labelZh==='白银 1★', calcGlRank(45.00).labelZh);
    T('N22c 89.99 → 钻石 5★', calcGlRank(89.99).labelZh==='钻石 5★', calcGlRank(89.99).labelZh);
    T('N22d 90.00 → 王者 1★', calcGlRank(90.00).labelZh==='王者 1★', calcGlRank(90.00).labelZh);
    T('N22e 98.00 → 王者 5★', calcGlRank(98.00).labelZh==='王者 5★', calcGlRank(98.00).labelZh);

    SECT='P'; /* 新资产 / Profile */
    T('P1 programLib 197 条', SEED.programLib.items.length===197, SEED.programLib.items.length);
    T('P2 strategyLib 27 条', SEED.strategyLib.items.length===27, SEED.strategyLib.items.length);
    T('P3 适用性矩阵 27 行', SEED.strategyLib.matrix.length===27, SEED.strategyLib.matrix.length);
    T('P4 辅助动作库 209 条', SEED.strategyLib.auxActs.length===209, SEED.strategyLib.auxActs.length);
    var pid=SEED.programLib.items[0].id;
    toggleFavProg(pid);
    var pj=JSON.parse(localStorage.getItem(LS_PREFS)||'{}');
    T('P5 收藏计划持久化到 prefs', (pj.favProgs||[]).indexOf(pid)>=0 && state.favProgs.indexOf(pid)>=0, JSON.stringify(pj.favProgs||[]).slice(0,40));
    toggleFavProg(pid);
    T('P6 取消收藏后移除', state.favProgs.indexOf(pid)<0, state.favProgs.join(','));
    openProfile();
    document.getElementById('pSq').value='999';
    T('P7 水平页改单页全量表后仍不丢输入：改过的格子在重开页面里保持', document.getElementById('pSq').value==='999', document.getElementById('pSq').value);
    T('P8 全量表含身高 / 三小项 / 段位徽章等 17 行，#pHeight 与 #pPullup / #pDip 都在 #lvlTable 里',
      document.querySelectorAll('#lvlTable .lvl-row').length===17
      && !!document.getElementById('pHeight') && !!document.getElementById('pPullup') && !!document.getElementById('pDip')
      && document.getElementById('pHeight').closest('#lvlTable') && document.getElementById('pPullup').closest('#lvlTable'),
      document.querySelectorAll('#lvlTable .lvl-row').length+' 行');
    document.getElementById('pSq').value=state.profile.sq;
    T('P9 pEqClTxt = 无装且单行等高', txt('pEqClTxt')==='无装' && document.getElementById('pEqCl').offsetHeight===document.getElementById('pEqEq').offsetHeight, txt('pEqClTxt'));
    T('P10 GL 段位条渲染：条状徽章有 GL 数 / 段位 / 星 / 距离四件，圆形 medal 已退役',
      !!txt('glBarGl') && !!txt('glLabel') && txt('glStars').indexOf('★')>=0 && (txt('glInfo')||'').indexOf('IPF GL')>=0
      && !!txt('lvlRankVal') && document.querySelectorAll('.gl-medal').length===0 && !document.getElementById('glMedal'),
      txt('glBarGl')+' / '+txt('glLabel')+' / '+txt('lvlRankVal'));

    /* ---------- Lv 段：v0.46 运动员水平页（全量表 / 三小项 / 快照 / CSV 携带） ---------- */
    var LvSnap=JSON.stringify(state), LvPrefs=localStorage.getItem(LS_PREFS);
    var LvP=state.profile;
    /* Lv1 三小项读写：填 OHP / 引体 / 双杠 → 仅保存 → 三项都进 profile，且不动 S/B/D 处方。
       附加重量按契约 range [0,200]：负数输入夹到 0（不是 bug，是口径）。 */
    var LvBefore=JSON.stringify(state.weeks);
    document.getElementById('pOhp').value='62.5';
    document.getElementById('pPullup').value='12.5';
    document.getElementById('pDip').value='10';
    saveProfile(false);
    document.getElementById('pPullup').value='-12.5';
    saveProfile(false);
    T('Lv1 三小项进 profile：OHP 62.5 / 引体 12.5 / 双杠 10，负数附加夹到 0（range [0,200]），仅保存不动任何处方',
      state.profile.ohp===62.5 && state.profile.pullupAddedKg===0 && state.profile.dipAddedKg===10
      && JSON.stringify(state.weeks)===LvBefore,
      'ohp='+state.profile.ohp+' pull='+state.profile.pullupAddedKg+' dip='+state.profile.dipAddedKg);
    document.getElementById('pPullup').value='15';
    saveProfile(false);
    /* Lv2 三小项不触发 S/B/D 重算：改引体/双杠/OHP 后点「保存并重算主项」，处方一格不变 */
    var LvW2=JSON.stringify(state.weeks);
    document.getElementById('pOhp').value='70';
    document.getElementById('pPullup').value='15';
    document.getElementById('pDip').value='20';
    saveProfile(true);
    T('Lv2 三小项不触发主项重算：OHP/引体/双杠改数 + 保存并重算主项 → 周处方逐字节不动（重算只看 S/B/D 三个锚点）',
      JSON.stringify(state.weeks)===LvW2 && state.profile.ohp===70 && state.profile.pullupAddedKg===15 && state.profile.dipAddedKg===20,
      'ohp='+state.profile.ohp+' pull='+state.profile.pullupAddedKg+' dip='+state.profile.dipAddedKg);
    /* Lv3 段位不缺算：三小项为空（旧档没填）时 GL / 段位 / 快照 derived 仍算得出来 */
    var LvP3=clone(state.profile);
    delete state.profile.ohp; delete state.profile.pullupAddedKg; delete state.profile.dipAddedKg;
    openProfile();
    var LvGl=txt('glBarGl'), LvRank=txt('lvlRankVal');
    T('Lv3 三小项缺失不缺算：段位徽章与 GL 数照常渲染（它们只由 S/B/D + 体重 + 性别/装备决定）',
      /^[0-9.]+$/.test(String(LvGl)) && String(LvRank).indexOf('★')>=0 && isFinite(parseFloat(LvGl)),
      LvGl+' / '+LvRank);
    state.profile=LvP3; openProfile();
    /* Lv4 快照写入规矩：同一天第一次保存新增一行；同日再保存（值没变）不多写；变了才覆盖当日最后一行。
       前面 Lv1–Lv3 的保存已经落过今天一行，先清场再测「新增」这条腿（state 末尾整体还原）。 */
    var LvD=new Date().toISOString().slice(0,10);
    state.levelSnap=[];
    var LvN0=(state.levelSnap||[]).length;
    document.getElementById('pSq').value=String((+state.profile.sq||100)+2.5);
    saveProfile(false);
    var LvSnapA=state.levelSnap.filter(function(s){return s.date===LvD;});
    var LvN1=state.levelSnap.length;
    var LvSqA=LvSnapA[LvSnapA.length-1].sq;
    saveProfile(false);
    var LvSnapB=state.levelSnap.filter(function(s){return s.date===LvD;});
    document.getElementById('pSq').value=String((+state.profile.sq||100)+5);
    saveProfile(false);
    var LvSnapC=state.levelSnap.filter(function(s){return s.date===LvD;});
    T('Lv4 快照有变化才写、同一天只留最后一行：改值→新增/更新一行；同值再保存→不写；再改→同日行数仍 1 且值跟到手',
      LvN1>LvN0 && LvSnapB.length===LvSnapA.length && LvSnapC.length===1 && LvSnapC[0].sq===+document.getElementById('pSq').value,
      LvN0+'→'+LvN1+' / 同日行数 '+LvSnapA.length+'/'+LvSnapB.length+'/'+LvSnapC.length+' / sq='+LvSnapC[0].sq+' vs 输入 '+document.getElementById('pSq').value+'（第一次写前 '+LvSqA+'）');
    /* Lv5 快照行 derived 自洽：total/gl/dots/wilks/rankId/rankStars 都按契约 ranges 与系数函数现算 */
    var LvRow=state.levelSnap.filter(function(s){return s.date===LvD;})[0];
    var LvTot=(+LvRow.sq||0)+(+LvRow.bp||0)+(+LvRow.dl||0);
    var LvGlC=calcIpfGl(LvTot,+LvRow.bw||0,state.profile.gender||'M',state.profile.equip||'classic',false);
    var LvRk=calcGlRank(LvGlC);
    T('Lv5 快照行与系数单源自洽：total=S+B+D、gl=calcIpfGl、rankId/rankStars=calcGlRank、dots/wilks 同函数；列名与契约 Level.keys 对齐',
      LvRow.total===LvTot && Math.abs(LvRow.gl-+LvGlC.toFixed(2))<1e-9 && LvRow.rankId===LvRk.id && LvRow.rankStars===LvRk.stars
      && PLAN_SCHEMA.sheets.Level.keys.pullup_added_kg==='pullupAddedKg' && PLAN_SCHEMA.sheets.Level.keys.dip_added_kg==='dipAddedKg'
      && PLAN_SCHEMA.sheets.Level.keys.ohp_1rm==='ohp',
      'total '+LvRow.total+'/'+LvTot+' gl '+LvRow.gl+'/'+LvGlC+' rank '+LvRow.rankId+'/'+LvRk.id);
    /* Lv6 快照可编辑：改一行数值 → 当场按系数重算派生列并落盘 */
    var LvIdx=state.levelSnap.indexOf(LvRow), LvOldGl=LvRow.gl;
    document.getElementById('pSq').value=String((+state.profile.sq||100)+20);
    saveProfile(false);
    LvRow=state.levelSnap[LvIdx];
    var LvNewTot2=(+LvRow.sq||0)+(+LvRow.bp||0)+(+LvRow.dl||0);
    T('Lv6 快照同值不重复写：改 20kg 后同日仍一行，且该行随数值走（gl 变大 / total 跟手）',
      LvRow.gl!==LvOldGl && LvRow.gl>0 && LvRow.total===LvNewTot2
      && state.levelSnap.filter(function(s){return s.date===LvD;}).length===1,
      LvRow.gl+' → 同 total 行 '+LvRow.total);
    /* Lv7 CSV 携带：PROFILE notes 带三小项，导入后 profile 三值回来（往返零差）。
       csvParse 吃的是全文（首行必须是 CSV_HEAD），单行喂进去只会得到空对象。 */
    var LvCsv=exportUnifiedCsv();
    var LvProfRec=null;
    csvParse(LvCsv).forEach(function(r){ if(r.record_type==='PROFILE') LvProfRec=r; });
    var LvParsed=null;
    try{ LvParsed=JSON.parse((LvProfRec||{}).notes||'null'); }catch(e){}
    var LvHeadN=String(LvCsv.split('\\r\\n')[0]||'').split(',').length;
    T('Lv7 CSV PROFILE notes 带三小项：pullupAddedKg/dipAddedKg/ohp 在 notes JSON 里，且表头仍是 26 列协议',
      !!LvParsed && LvParsed.pullupAddedKg===15 && LvParsed.dipAddedKg===20 && LvParsed.ohp===70
      && LvHeadN===CSV_COLS.length && LvHeadN===26,
      'notes keys '+(LvParsed?Object.keys(LvParsed).join('/').slice(0,70):'-')+' / 表头列数 '+LvHeadN);
    /* Lv8 导出导入零差异（CSV 口径）：三小项字节级回来；levelSnap 不走 26 列 CSV，导入不得碰它 */
    var LvP8=JSON.stringify({pu:state.profile.pullupAddedKg,di:state.profile.dipAddedKg,oh:state.profile.ohp,sn:state.levelSnap});
    importUnifiedCsv(exportUnifiedCsv());
    T('Lv8 CSV 导出→导入零差异：profile 三小项逐字节回来，levelSnap 不经 CSV、一格不动',
      JSON.stringify({pu:state.profile.pullupAddedKg,di:state.profile.dipAddedKg,oh:state.profile.ohp,sn:state.levelSnap})===LvP8
      && state.profile.pullupAddedKg===15 && state.profile.dipAddedKg===20 && state.profile.ohp===70,
      'p='+JSON.stringify({pu:state.profile.pullupAddedKg,di:state.profile.dipAddedKg,oh:state.profile.ohp}));
    state=JSON.parse(LvSnap); localStorage.setItem(LS_PREFS,LvPrefs); save(true); renderAll();
    /* 阶段独立 UI（v0.39）：阶段从行网格搬出来，自己占一条胶囊横排（块数 >2 时行网格读不动）。
       三条腿：数据形状 → 真点 DOM（含 4 块夹具）→ 纯只读（不动账本、空结构不抛）。 */
    var PB=state.structure.blocks||[];
    var PBAK=clone(PB);
    var aud=auditCycleGoal(state.profile,state.structure);
    var four=[0,1,2,3].map(function(i){
      return {id:'X'+i,cycleType:['Hyper','Strength','Peak','Deload'][i],
              nameZh:'夹具'+i,nameEn:'RIG'+i,workWeeks:2,deloadWeeks:1};
    });
    T('P11 阶段不再挤进行网格：rows 里没有「阶段」，phases 与 blocks 一一对应（id/周数逐块相等），Peak 判据真在块里找',
      aud.status==='ok'
      && aud.rows.every(function(r){return r.zh!=='阶段'&&r.en!=='PHASE';})
      && aud.phases.length===PB.length
      && aud.phases.every(function(ph,i){return ph.id===String(PB[i].id)&&ph.work===+PB[i].workWeeks&&ph.deload===+PB[i].deloadWeeks;})
      && aud.hasPeak===true
      && auditCycleGoal(state.profile,{blocks:four,totalWeeks:12}).hasPeak===true,
      'rows='+aud.rows.map(function(r){return r.zh;}).join('/')+' phases='+aud.phases.length);
    var snapP=JSON.stringify(state), prefsP=localStorage.getItem(LS_PREFS);
    renderGoalAudit(state.profile);
    var wrapN=document.querySelectorAll('#goalAudit .ga-phase').length;
    var blkN=document.querySelectorAll('#goalAudit .ga-blk').length;
    var arrN=document.querySelectorAll('#goalAudit .ga-arrow').length;
    var peakN=document.querySelectorAll('#goalAudit .ga-peak').length;
    var gridTxt=(document.querySelector('#goalAudit .ga-grid')||{}).textContent||'';
    state.structure.blocks=four;
    renderGoalAudit(state.profile);
    var blk4=document.querySelectorAll('#goalAudit .ga-blk').length;
    var arr4=document.querySelectorAll('#goalAudit .ga-arrow').length;
    var peak4=document.querySelectorAll('#goalAudit .ga-peak').length;
    var fourNP=[0,1,2,3].map(function(i){
      return {id:'Y'+i,cycleType:['Hyper','Strength','Transmute','Deload'][i],
              nameZh:'夹具NP'+i,nameEn:'RIGNP'+i,workWeeks:2,deloadWeeks:1};
    });
    state.structure.blocks=fourNP;
    renderGoalAudit(state.profile);
    var peakNP=document.querySelectorAll('#goalAudit .ga-peak').length;
    state.structure.blocks=PBAK;
    renderGoalAudit(state.profile);
    T('P12 阶段条真点 DOM：一条横排外壳、种子 3 块 = 3 胶囊 + 2 箭头 + 有 Peak 不挂角标；换 4 块含 Peak 夹具 = 4 胶囊 + 3 箭头、角标仍无；换 4 块无 Peak 夹具 = 角标回来；行网格里读不到「阶段」二字',
      wrapN===1 && blkN===PB.length && arrN===PB.length-1 && peakN===0 && gridTxt.indexOf('阶段')<0
      && blk4===4 && arr4===3 && peak4===0 && peakNP===1,
      '壳 '+wrapN+' / 种子 '+blkN+'/'+arrN+'/'+peakN+' / 4块含Peak '+blk4+'/'+arr4+'/'+peak4+' / 4块无Peak角标 '+peakNP);
    T('P13 纯只读：整段前后账本与 prefs 逐字节不动；空 blocks 只出 missing，不抛错',
      JSON.stringify(state)===snapP && localStorage.getItem(LS_PREFS)===prefsP
      && (function(){ try{ return auditCycleGoal(state.profile,{blocks:[],totalWeeks:0}).status==='missing'; }catch(e){ return false; } })(),
      'state同='+(JSON.stringify(state)===snapP)+' prefs同='+(localStorage.getItem(LS_PREFS)===prefsP));
    closeSheet('profSheet');

    SECT='Q'; /* ===== Q. 结构写入唯一入口 + 决策 D4 冻结（C2） ===== */
    /* 这一段会真改 state：进段留一份克隆（用来还原）+ 一份文本快照（用来抓「共享对象被改脏」），
       出段还原并重绘，后面的 R/S 轮次不受影响。 */
    var QBAK=clone(state);
    var SNAP=JSON.stringify(state);
    var blocks16=clone(QBAK.structure.blocks), defs4=clone(QBAK.structure.dayDefs);
    var SEEDW=+QBAK.structure.totalWeeks;            /* 种子最后一周（当前 8）；冻结腿的对账上界 */
    var b0=clone(blocks16[0]);
    var w0=(+b0.workWeeks||0)+(+b0.deloadWeeks||0);
    var wantFrozen=[]; for(var qf=w0+1;qf<=SEEDW;qf++) wantFrozen.push(qf);
    var snap16=JSON.stringify(QBAK.weeks[String(SEEDW)]);
    var refW0=JSON.stringify(QBAK.weeks[String(w0)].A.exercises);
    applyStructure({startDate:'2026-11-02',blocks:[b0],dayDefs:defs4,totalWeeks:99,daysPerWeek:99,recSetsOverride:{sq:6,bp:null,dl:null}});
    T('Q1 缩到 '+w0+' 周后 totalWeeks 由 blocks 求、冻结周登记 inactiveWeeks',
      state.structure.totalWeeks===w0 && state.structure.inactiveWeeks.join(',')===wantFrozen.join(','),
      'total='+state.structure.totalWeeks+' inactive='+state.structure.inactiveWeeks.join(','));
    T('Q2 派生字段单一来源：raw 里手写的 daysPerWeek=99 被忽略（应为 len(dayDefs)）',
      state.structure.daysPerWeek===defs4.length, 'daysPerWeek='+state.structure.daysPerWeek);
    T('Q3 冻结周数据一字未删（W'+SEEDW+' 与缩期前逐字节相同）',
      SEEDW>w0 && !!snap16 && JSON.stringify(state.weeks[String(SEEDW)])===snap16, 'weeks 键数='+Object.keys(state.weeks).length);
    var qCsv=csvParse(exportUnifiedCsv());
    var qWk=qCsv.filter(function(r){return r.record_type==='EXERCISE';}).map(function(r){return +r.week;});
    T('Q4 冻结周不进交换文件（导出 CSV 的最大周 = '+w0+'）',
      qWk.length>0 && Math.max.apply(null,qWk)===w0 && qWk.indexOf(SEEDW)<0,
      qWk.length+' 行 / 最大周='+(qWk.length?Math.max.apply(null,qWk):'-'));
    renderAll();
    var railW0=document.querySelectorAll('#weekRail .pill').length;
    T('Q5 周轨只渲染本次计划周数（不再回落到硬编码 '+SEEDW+'）', railW0===w0, railW0+' 个胶囊');
    /* 参照周：删掉前几週后回填，只允许从未冻结的周复制，不许复制归档的 W'+SEEDW */
    for(var qd=1;qd<w0;qd++) delete state.weeks[String(qd)];   /* 留 W'+w0 当参照——写死删到 3 在 w0=3 的种子上会把参照本身删没 */
    applyStructure({startDate:'2026-11-02',blocks:[clone(b0)],dayDefs:defs4});
    var q6=JSON.stringify(state.weeks['1'].A.exercises);
    T('Q6 ensureWeeks 的参照周取自未冻结的 W'+w0+'，不是归档的 W'+SEEDW,
      q6===refW0 && q6!==snap16, 'W1.A 动作数='+state.weeks['1'].A.exercises.length);
    applyStructure({startDate:QBAK.structure.startDate,blocks:blocks16,dayDefs:defs4});
    renderAll();
    var railBack=document.querySelectorAll('#weekRail .pill').length;
    T('Q7 延长回 '+SEEDW+' 周自动解冻（inactiveWeeks 清空、周轨回到 '+SEEDW+'）',
      state.structure.inactiveWeeks.length===0 && state.structure.totalWeeks===SEEDW && railBack===SEEDW,
      'inactive='+state.structure.inactiveWeeks.length+' 胶囊='+railBack);
    /* 契约版本单源：structure.version 取自 PLAN_SCHEMA，不再各处写死 */
    var cVer=+(PLAN_SCHEMA.state_defaults_on_import||{})['structure.version'];
    T('Q8 structure.version 取自契约（非硬编码）',
      state.structure.version===cVer && cVer>0, 'v='+state.structure.version+' 契约='+cVer);
    /* CSV 的 STRUCTURE 行必须走同一个闸门：手写的 week=99 不算数，人工组数覆盖不许被抹掉 */
    state.structure.recSetsOverride={sq:7,bp:null,dl:null};
    var oneCsv=CSV_HEAD+'\\r\\n'+csvRow({schema_ver:'1',record_type:'STRUCTURE',week:99,date:'2026-11-02',
      notes:JSON.stringify({blocks:[clone(b0)],dayDefs:defs4})})+'\\r\\n';
    var qImp=importUnifiedCsv(oneCsv);
    T('Q9 CSV STRUCTURE 行走同一闸门（errors 0 / 周数取 blocks 之和 / 版本取契约）',
      qImp.errors.length===0 && qImp.stats.structure===1 && state.structure.totalWeeks===w0
      && state.structure.version===cVer,
      JSON.stringify(qImp.errors.slice(0,2))+' total='+state.structure.totalWeeks+' v='+state.structure.version);
    T('Q10 结构写入不抹掉人工组数覆盖（recSetsOverride 存活）',
      JSON.stringify(state.structure.recSetsOverride)==='{"sq":7,"bp":null,"dl":null}',
      JSON.stringify(state.structure.recSetsOverride));
    state=QBAK; renderAll();
    T('Q11 出段还原 + 本段没把共享对象改脏（进段文本快照对得上）',
      JSON.stringify(state)===SNAP, '长度 '+JSON.stringify(state).length+'/'+SNAP.length);

    SECT='U'; /* ===== U. 第四分片：计划归档 roast_plan_archive.json（C3） ===== */
    /* 这一段只碰归档分片与 localStorage，不动账本；出段把分片恢复原样。 */
    var UORDER=PLAN_SCHEMA.sheet_order;
    var UBAK_RAW=(function(){ try{ return localStorage.getItem(LS_ARCHIVE); }catch(e){ return null; } })();
    var UBAK_RO=READONLY;
    function uPlan(rowsN,padN){
      var p={},i,q,big='';
      for(q=0;q<padN;q++) big+='档';                 /* 一个汉字 UTF-8 三字节，用来把单份顶到上限附近 */
      for(i=0;i<UORDER.length;i++) p[UORDER[i]]=[];
      var sheet=p[UORDER[0]];                        /* 表名一律从契约取，归档只认「六表齐全」 */
      for(i=0;i<rowsN;i++) sheet.push({row_idx:i,payload:big});
      return p;
    }
    function uRaw(){ try{ return localStorage.getItem(LS_ARCHIVE); }catch(e){ return null; } }
    function uReload(){ _archiveCache=null; }        /* 强制从盘上重读，证明落盘而非内存自证 */
    localStorage.removeItem(LS_ARCHIVE); uReload();
    var uWorkBefore=localStorage.getItem(LS_WORK);
    T('U1 空分片：读出空归档、无告警、磁盘不落地',
      archiveList().length===0 && archiveWarn()==='' && uRaw()===null,
      'items='+archiveList().length+' warn="'+archiveWarn()+'" raw='+(uRaw()===null?'null':'有值'));
    var u2=archivePush(uPlan(3,20),{source:'regress',label:'16周基线',totalWeeks:16});
    uReload();
    var u2got=archiveGet(u2.id);
    T('U2 推一份六表计划：从盘上重读得到同一份原文、元数据齐',
      u2.ok===true && !!u2got && u2got.label==='16周基线' && u2got.source==='regress'
      && u2got.totalWeeks===16 && u2got.rows===3 && JSON.stringify(u2got.plan)===JSON.stringify(uPlan(3,20)),
      'id='+u2.id+' bytes='+u2.bytes+' rows='+(u2got?u2got.rows:-1));
    T('U3 归档不参与账本：推完 workout 分片一字未变、state 上没有 planArchive 键',
      localStorage.getItem(LS_WORK)===uWorkBefore && state.planArchive===undefined
      && Object.keys(state).indexOf('planArchive')<0,
      'workout 长度='+(uWorkBefore?uWorkBefore.length:0)+' state 键含 planArchive='+(Object.keys(state).indexOf('planArchive')>=0));
    var u4raw=uRaw();
    var u4=archivePush(uPlan(4,30000),{label:'过大'});
    T('U4 单份超上限：拒绝并回报字节，磁盘原文一字未改',
      u4.ok===false && u4.reason==='too_big' && u4.bytes>ARCHIVE_ENTRY_CAP && uRaw()===u4raw,
      u4.bytes+' > 单份上限 '+ARCHIVE_ENTRY_CAP);
    var u5plan=uPlan(2,5); delete u5plan[UORDER[UORDER.length-1]];
    var u5=archivePush(u5plan,{label:'缺表'});
    uReload();
    T('U5 六表少一张：not_a_plan 拒收，归档里仍只有上一份',
      u5.ok===false && u5.reason==='not_a_plan' && archiveList().length===1,
      u5.reason+' items='+archiveList().length);
    var uIds=[],u6=null;
    for(var u6i=0;u6i<ARCHIVE_MAX_ITEMS+1;u6i++){ u6=archivePush(uPlan(1,4),{label:'n'+u6i}); uIds.push(u6.id); }
    uReload();
    var u6list=archiveList();
    T('U6 条数上限：满 '+ARCHIVE_MAX_ITEMS+' 份后最旧的先出局、列表保持新→旧',
      u6.ok===true && u6list.length===ARCHIVE_MAX_ITEMS && u6list[0].id===uIds[uIds.length-1]
      && u6.dropped.indexOf(uIds[0])>=0
      && u6list.map(function(it){return it.id;}).indexOf(uIds[0])<0,
      '条数='+u6list.length+' 上限='+ARCHIVE_MAX_ITEMS+' 淘汰='+u6.dropped.join(','));
    var u7=null;
    for(var u7i=0;u7i<3;u7i++) u7=archivePush(uPlan(1,60000),{label:'big'+u7i});
    uReload();
    T('U7 字节上限：超 ARCHIVE_CAP_BYTES 就逐出最旧的，落盘文本实测不越线',
      u7.ok===true && u7.bytes<=ARCHIVE_CAP_BYTES && utf8Len(uRaw())<=ARCHIVE_CAP_BYTES
      && u7.dropped.length>0 && archiveList()[0].label==='big2',
      'bytes='+u7.bytes+'/'+ARCHIVE_CAP_BYTES+' 条数='+archiveList().length+' 淘汰='+u7.dropped.length);
    var u8good={v:1,items:[{id:'good1',at:1,source:'regress',label:'完好条目',totalWeeks:1,
      plan:(function(){ var p={},i; for(i=0;i<UORDER.length;i++) p[UORDER[i]]=[]; return p; })()}]};
    localStorage.setItem(LS_ARCHIVE,JSON.stringify(u8good)); uReload();
    var u8one=archiveList().length===1 && archiveGet('good1')!==null;
    localStorage.setItem(LS_ARCHIVE,'这不是 JSON');
    uReload();
    var u8empty=archiveList().length===0, u8warn=archiveWarn();   /* 先真读一次坏分片 */
    var u8after=uRaw();                                          /* 再回头看盘上还剩什么 */
    T('U8 分片坏了：完好条目收得下、坏文本按空归档处理并告警，且绝不回写覆盖磁盘原文',
      u8one && u8empty && u8warn.length>0 && u8after==='这不是 JSON',
      'warn="'+u8warn+'" 读后盘上现为 '+JSON.stringify(String(u8after).slice(0,16)));
    var u9seed=archivePush(uPlan(2,8),{label:'阻断态靶子'});
    uReload();
    var u9id=archiveList()[0].id, u9rawBefore=uRaw();
    READONLY=true;
    var u9push=archivePush(uPlan(1,4),{}), u9drop=archiveDrop(u9id), u9rawAfter=uRaw();
    READONLY=UBAK_RO; uReload();
    T('U9 阻断态（READONLY）下归档不写盘：push 报 readonly、drop 返回 false、磁盘文本不变',
      u9seed.ok===true && u9push.ok===false && u9push.reason==='readonly' && u9drop===false
      && u9rawAfter===u9rawBefore && archiveList()[0].id===u9id,
      'push.ok='+u9push.ok+' drop='+u9drop+' 盘变了='+(u9rawAfter!==u9rawBefore));
    var u10before=archiveList().length;
    var u10=archiveDrop(u9id);
    uReload();
    var u10left=archiveList();
    T('U10 显式删除某份归档：从盘上重读该条消失、其余保留',
      u10===true && u10left.length===u10before-1
      && u10left.map(function(it){return it.id;}).indexOf(u9id)<0,
      '删除前 '+u10before+' 份 → 剩 '+u10left.length+' 份');
    var u11push=archivePush(uPlan(1,6),{label:'待清空'});
    var u11n=archiveClear();
    var u11empty=uRaw();
    var u11bak='{"v":1,"items":[{"id":"old-arch","at":2,"source":"xlsx","label":"进段前就有的一份","totalWeeks":1,"plan":'
      +JSON.stringify(uPlan(1,1))+'}]}';
    localStorage.setItem(LS_ARCHIVE,u11bak); uReload();
    var u11restored=archiveList().map(function(it){return it.id;}).join(',');
    if(UBAK_RAW===null) localStorage.removeItem(LS_ARCHIVE); else localStorage.setItem(LS_ARCHIVE,UBAK_RAW);
    uReload();
    T('U11 显式清空返回份数并写回空分片；出段把进段前的分片原样放回',
      u11push.ok===true && u11n===1 && u11empty==='{"v":1,"items":[]}' && u11restored==='old-arch'
      && uRaw()===UBAK_RAW,
      'clear 返回 '+u11n+' 清空后='+u11empty+' 还原后='+u11restored);

    SECT='V'; /* ===== V. C5 UI 点击链路：计划工作簿行 + 归档面板（全走真 DOM click） ===== */
    /* S14 静态点名只证明「节点与函数都在」；onclick 字符串指向被改名的函数、面板从
       closeAllSheets 掉队这类两端漂移，浏览器里表现为点了没反应的静默故障——只有真点才能抓到。
       进段备份：账本文本 + 归档分片原文；出段逐字节放回，R/S 重载轮不受波及。
       刻意不点 #planImpBtn（会弹系统文件选择器把无头链路挂住），改查它的 onclick 指向与
       #planXlsxFile 的 accept；导出同理（浏览器兜底会触发 blob 下载），只查按钮接线字符串。 */
    var VSNAP=JSON.stringify(state);
    var VBAK=clone(state);
    var VRAW0=(function(){ try{ return localStorage.getItem(LS_ARCHIVE); }catch(e){ return null; } })();
    var vGo=document.getElementById('setArchGo').closest('button');
    function vBtn(fn,id){
      var bs=document.querySelectorAll('#archRows button'),i;
      for(i=0;i<bs.length;i++) if((bs[i].getAttribute('onclick')||'').indexOf(fn+"('"+id+"')")>=0) return bs[i];
      return null;
    }
    var v1=(function(){
      var ids=['setPlanT','planExpBtn','planImpBtn','planXlsxFile','setArchT','archSheet','archRows','planErrBox','archClearBtn'];
      for(var i=0;i<ids.length;i++) if(!document.getElementById(ids[i])) return 'missing#'+ids[i];
      if(!vGo) return 'missing#setArchGo 的宿主按钮';
      if((document.getElementById('planExpBtn').getAttribute('onclick')||'').indexOf('doExportPlanXlsx')<0) return '导出按钮 onclick 漂移';
      if((document.getElementById('planImpBtn').getAttribute('onclick')||'').indexOf('planXlsxFile')<0) return '导入按钮 onclick 漂移';
      if(document.getElementById('planXlsxFile').accept.indexOf('.xlsx')<0) return 'accept 漂移';
      if((vGo.getAttribute('onclick')||'').indexOf('openArchiveSheet')<0) return '查看行 onclick 漂移';
      return 'OK';
    })();
    T('V1 工作簿/归档 9 节点齐、按钮 onclick 全指向已定义的接线函数', v1==='OK', v1);
    localStorage.removeItem(LS_ARCHIVE); _archiveCache=null;
    var vDict=xStateToPlanDict(state);
    var vA=archivePush(vDict,{source:'regress',label:'V 靶子'});
    var vB=archivePush(uPlan(1,4),{source:'regress',label:'V 靶子小'});
    vGo.click();
    var v2=document.getElementById('archSheet').classList.contains('on')
      && document.querySelectorAll('#archRows button').length===4
      && !!vBtn('restoreArchiveItem',vA.id) && !!vBtn('dropArchiveItem',vB.id);
    T('V2 点设置页「查看」：archSheet 打开、两份归档渲染成 4 个动作按钮', v2,
      'on='+document.getElementById('archSheet').classList.contains('on')
      +' 按钮='+document.querySelectorAll('#archRows button').length+'/'+(archiveList().length*2));
    var vDate0=VBAK.structure.startDate;
    state.structure.startDate='2020-01-06';
    vBtn('restoreArchiveItem',vA.id).click();
    var vAuto=null,vLs=archiveList();
    for(var v3i=0;v3i<vLs.length;v3i++) if(vLs[v3i].source==='app'&&vLs[v3i].label==='2020-01-06') vAuto=vLs[v3i];
    T('V3 点条目「取回」：账本换回存档当时（起止日翻回 '+vDate0+'），被顶替的当前计划自动进架',
      vA.ok===true && vB.ok===true && state.structure.startDate===vDate0 && !!vAuto
      && document.querySelectorAll('#archRows button').length===archiveList().length*2,
      'startDate='+state.structure.startDate+' 自动归档='+(vAuto?vAuto.id:'无')
      +' 行数='+archiveList().length);
    /* 删除靶子现取最新一条（＝刚自动进架的那份）：vA/vB 可能已被 512KB 预算逐出，
       断言「哪条在架上」会随字典体积漂移；取 archiveList()[0] 则恒在——淘汰只 pop 最旧。 */
    var vT=(archiveList()[0]||{}).id;
    var vN1=archiveList().length;
    vBtn('dropArchiveItem',vT).click();
    var vN2=archiveList().length;
    T('V4 点条目「删除」：该条出局、其余保留、行同步重渲染',
      !!vT && vN2===vN1-1 && !archiveGet(vT)
      && document.querySelectorAll('#archRows button').length===vN2*2,
      vN1+' 份 → '+vN2+' 份 / 按钮='+document.querySelectorAll('#archRows button').length);
    showPlanErrors('V 段脏文本');
    var vBox=document.getElementById('planErrBox');
    var vErrShown=vBox.style.display==='block' && vBox.textContent==='V 段脏文本';
    document.getElementById('archClearBtn').click();
    var v5=localStorage.getItem(LS_ARCHIVE)==='{"v":1,"items":[]}' && archiveList().length===0
      && document.querySelectorAll('#archRows button').length===0;
    vGo.click();
    T('V5 点「清空归档」：分片写回空文本、行收成提示；重开面板顺带清掉错误框',
      v5 && vErrShown && vBox.style.display==='none',
      '清空后 raw='+String(localStorage.getItem(LS_ARCHIVE)).slice(0,48)+' 按钮='+document.querySelectorAll('#archRows button').length
      +' 错误框='+vBox.style.display);
    vBox.textContent='';
    /* 断言号连着编号：V6 = showPlanErrors 的显隐两态（上面 V5 只顺手验了「重开即清」那一半）。 */
    showPlanErrors('V6 契约回执');
    var v6a=vBox.style.display==='block' && vBox.textContent==='V6 契约回执';
    showPlanErrors('');
    var v6b=vBox.style.display==='none' && vBox.textContent==='';
    T('V6 showPlanErrors 双向：有文本就显、空文本即收（导入被拦时用户看得见原因）', v6a&&v6b,
      '显='+v6a+' 收='+v6b);
    var v7pre=document.getElementById('archSheet').classList.contains('on');
    var vBack=window.__handleBack();
    T('V7 返回键收口：__handleBack 关掉 archSheet（archSheet 确在 closeAllSheets 名单里）',
      v7pre && vBack===true && !document.getElementById('archSheet').classList.contains('on'),
      '点前 on='+v7pre+' 返回='+vBack+" 点后 on="+document.getElementById('archSheet').classList.contains('on'));
    state=VBAK; renderAll();
    if(VRAW0===null) localStorage.removeItem(LS_ARCHIVE); else localStorage.setItem(LS_ARCHIVE,VRAW0);
    _archiveCache=null;
    T('V8 出段还原：账本与归档分片都回到进段前逐字节原文（重载轮看不到本段痕迹）',
      JSON.stringify(state)===VSNAP && localStorage.getItem(LS_ARCHIVE)===VRAW0,
      '长度 '+JSON.stringify(state).length+'/'+VSNAP.length+' 分片='+(VRAW0===null?'null':String(VRAW0).length));

    SECT='W'; /* ===== W. 主题注册表（多主题 paint / mode 门控 / 回落 / 对比度） ===== */
    /* 这一段故意不写死主题名：名单从页面里的注册表读回来 —— 注册表与令牌块 /
       按钮 / i18n 任一处分叉，逐主题循环会当场报出是哪一个主题。 */
    var WID=window.THEME_IDS.slice();
    var WSNAP=JSON.stringify(state), WPREF=localStorage.getItem(LS_PREFS);
    var Wpx=function(k){ return getComputedStyle(document.documentElement).getPropertyValue(k).trim(); };
    var Wrgb=function(v){ v=String(v).trim();
      if(v.charAt(0)==='#'){ if(v.length===4) return [parseInt(v.charAt(1)+v.charAt(1),16),parseInt(v.charAt(2)+v.charAt(2),16),parseInt(v.charAt(3)+v.charAt(3),16)];
        return [parseInt(v.substr(1,2),16),parseInt(v.substr(3,2),16),parseInt(v.substr(5,2),16)]; }
      var q=v.replace('(',' ').replace(')',' ').split(/[ ,]+/);
      return [parseInt(q[1],10),parseInt(q[2],10),parseInt(q[3],10)]; };
    var Wlum=function(c){ var a=c.map(function(x){ x=x/255; return x<=0.03928? x/12.92 : Math.pow((x+0.055)/1.055,2.4); });
      return 0.2126*a[0]+0.7152*a[1]+0.0722*a[2]; };
    var Wcr=function(f,b){ var x=Wlum(Wrgb(f)), y=Wlum(Wrgb(b));
      return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05); };
    var Wbtn=function(t){ return document.getElementById('th'+t.charAt(0).toUpperCase()+t.slice(1)); };
    var WlabId=function(t){ return 'th'+t.charAt(0).toUpperCase()+t.slice(1)+'T'; };
    var Wset=function(t){ state.theme=t; applyTheme(); renderSettings(); };  /* 画 + 重绘设置页，不写盘 */

    T('W1 注册表自洽：三张映射表的键与名单一致、mode 只取 dark|light、且不止两档',
      WID.length>=3 && new Set(WID).size===WID.length
      && ['THEME_MODE','THEME_BG','THEME_GLYPH'].every(function(n){ var m=window[n];
           return !!m && Object.keys(m).length===WID.length
             && Object.keys(m).sort().join()===WID.slice().sort().join(); })
      && WID.every(function(t){ return window.THEME_MODE[t]==='dark'||window.THEME_MODE[t]==='light'; }),
      WID.map(function(t){ return t+'('+window.THEME_MODE[t]+')'; }).join('/'));

    var Wpaint=WID.map(function(t){ Wset(t); var r=document.documentElement;
      return {t:t, dtheme:r.dataset.theme, dmode:r.dataset.mode,
              meta:document.getElementById('metaTheme').getAttribute('content'),
              glyph:document.getElementById('themeBtn').textContent}; });
    T('W2 逐主题 applyTheme：theme/mode 标记 + meta theme-color + 顶栏图标四样一起跟上，且原样取自注册表',
      Wpaint.every(function(x){ return x.dtheme===x.t && x.dmode===window.THEME_MODE[x.t]
        && String(x.meta).toLowerCase()===String(window.THEME_BG[x.t]).toLowerCase()
        && x.glyph===window.THEME_GLYPH[x.t]; })
      && String(applyTheme).indexOf('setChrome')>=0,
      Wpaint.map(function(x){ return x.t+':'+x.dmode+' '+String(x.meta)+x.glyph; }).join(' | '));

    var Wtok={}; WID.forEach(function(t){ state.theme=t; applyTheme();
      Wtok[t]={card:Wpx('--card-a'), surf:Wpx('--surf-hi'), ink:Wpx('--ink'), danger:Wpx('--danger-fg')}; });
    var Wdup=[]; WID.forEach(function(a,A){ WID.forEach(function(b,B){
      if(A<B && JSON.stringify(Wtok[a])===JSON.stringify(Wtok[b])) Wdup.push(a+'/'+b); }); });
    /* 「light 档的底必须真的是亮底」用绝对亮度判，不用「比正文亮」判：
       令牌块少一个键时那个键回落到 :root 的暗色值，而暗色值往往也比很深的正文还亮一点点，
       相对判据会放过它，绝对判据不放（本条实测过 F2 注入：nature 缺 --surf-hi 即红）。 */
    var Wdir=WID.map(function(t){ var x=Wtok[t], L=function(v){ return Wlum(Wrgb(v)); };
      var surf=L(x.surf), card=L(x.card), ink=L(x.ink);
      var ok = window.THEME_MODE[t]==='light'
        ? (surf>=0.55 && card>=0.55 && ink<=0.25)
        : (surf<=0.12 && card<=0.12 && ink>=0.60);
      return {t:t, mode:window.THEME_MODE[t], ok:ok, s:surf.toFixed(3), c:card.toFixed(3), i:ink.toFixed(3)}; });
    T('W3 每档主题的令牌块都落地且明暗方向正确：令牌互不相同，light 档底为亮底、dark 档底为暗底',
      Wdup.length===0 && Wdir.every(function(x){ return x.ok; }),
      Wdir.map(function(x){ return x.t+'('+x.mode+') 底'+x.s+'/'+x.c+' 文'+x.i+' 合格='+x.ok; }).join(' | '));

    /* data-mode 门控能不能被「第三个纸底主题」复用，只看一件事：同一条规则对所有 light 档
       主题生效、对 dark 档不生效。写成 [data-theme=light] 的话第三个主题会静默丢掉这条阴影。 */
    /* 门控到底在 mode 上还是主题名上：把 data-mode 单独拨回 dark、主题名不动，
       那条规则必须跟着失效（阴影回落到基础值）。写成 [data-theme=light] 的话这里就红。
       同时要求 light 档不止一个主题 —— 只有两个主题时「按主题名写」和「按 mode 写」看不出差别。 */
    var Wshadow=function(){ var c=document.querySelector('.card'); return c?getComputedStyle(c).boxShadow:'none'; };
    var Wgate=WID.map(function(t){ state.theme=t; applyTheme();
      var r=document.documentElement, keep=r.dataset.mode, on=Wshadow();
      r.dataset.mode='dark'; var off=Wshadow(); r.dataset.mode=keep;
      return {t:t, mode:keep, on:on, off:off}; });
    var Wlt2=Wgate.filter(function(x){ return x.mode==='light'; });
    var Wdk=Wgate.filter(function(x){ return x.mode==='dark'; });
    T('W4 亮底规则挂在 data-mode 上：拨回 mode=dark 即失效、dark 档本来就不吃这条，且 light 档不止一个主题',
      Wlt2.length>=2 && Wdk.length>=1
      && Wlt2.every(function(x){ return x.on!==x.off; })
      && Wdk.every(function(x){ return x.on===x.off; }),
      Wgate.map(function(x){ return x.t+' mode='+x.mode+' 开关有效='+(x.on!==x.off); }).join(' | '));

    var Won=WID.map(function(t){ Wset(t); var n=0;
      WID.forEach(function(id){ var b=Wbtn(id); if(b && b.classList.contains('on')) n++; });
      var s=document.getElementById('themeSeg');
      return {t:t, n:n, si:s.style.getPropertyValue('--seg-i'),
              sn:s.style.getPropertyValue('--seg-n')}; });
    T('W5 paintThemeUI 是唯一绘制点：每个主题恰好一个按钮亮、滑块停在注册表里那一格（段数取自按钮数、格位取自主题序号）',
      Won.every(function(x){ return x.n===1 && Number(x.sn)===WID.length
        && Number(x.si)===WID.indexOf(x.t); }),
      Won.map(function(x){ return x.t+' 亮'+x.n+' 段'+x.sn+' 格'+x.si; }).join(' | '));

    var Worder=[]; Wset(WID[0]);
    for(var wi=0; wi<WID.length+1; wi++){ Worder.push(themeId()); cycleTheme(); }
    T('W6 cycleTheme 走完整张注册表再回到起点（不是老的两档对调）',
      Worder.slice(0,WID.length).join(',')===WID.join(',') && Worder[WID.length]===WID[0],
      Worder.join('→'));

    var Wbak=state.theme; setTheme('slate-not-registered');
    T('W7 setTheme 收到未注册的名字直接不办事：状态不动，也不静默切到别的主题',
      state.theme===Wbak && themeId()===Wbak,
      '请求 slate-not-registered 后 state.theme='+state.theme+'（应仍为 '+Wbak+'）');

    state.theme='antique-ovh'; var Wfb=themeId(); applyTheme();
    T('W8 存档里读回来一个不存在的主题名：paint 回落到暗档，不把野值写进 DOM',
      Wfb!=='antique-ovh' && window.THEME_MODE[Wfb]==='dark'
      && document.documentElement.dataset.theme===Wfb && document.documentElement.dataset.mode==='dark',
      'themeId()='+Wfb+' dataset='+document.documentElement.dataset.theme+'/'+document.documentElement.dataset.mode);

    var Wlab={}; ['zh','en'].forEach(function(l){ var bak=state.lang; state.lang=l; applyChrome();
      Wlab[l]=WID.map(function(t){ var e=document.getElementById(WlabId(t)); return e?e.textContent:null; });
      state.lang=bak; });
    applyChrome();
    T('W9 主题文案双语齐备：每档都有 zh/en 文本、同语言内不重名、切换后没有 null 空格',
      Wlab.zh.every(function(x){ return !!x; }) && Wlab.en.every(function(x){ return !!x; })
      && new Set(Wlab.zh).size===WID.length && new Set(Wlab.en).size===WID.length
      && Wlab.zh.join()!==Wlab.en.join(),
      'zh='+Wlab.zh.join('/')+' en='+Wlab.en.join('/'));

    var WW0=localStorage.getItem(LS_PREFS), WL0=localStorage.getItem(LS_WORK);
    WID.forEach(function(t){ setTheme(t); });
    T('W10 换主题只写偏好分片：账本分片逐字节不动（走一圈 = '+WID.length+' 次写盘，全落在 prefs）',
      localStorage.getItem(LS_WORK)===WL0
      && String(localStorage.getItem(LS_PREFS)).indexOf('"theme"')>=0,
      'work 未变='+(localStorage.getItem(LS_WORK)===WL0)+' prefs='+String(localStorage.getItem(LS_PREFS)).slice(0,44));

    /* 阻断层不跑 applyTheme（走到那儿时 state 还是 null），所以它那两套行内色必须自己跟注册表分档 */
    var Wlt=WID.filter(function(t){ return window.THEME_MODE[t]==='light'; })[0];
    markBootFatal('parse','W11 构造的失败原文','{"schemaVer":6}',null,'W 段');
    bootFatal.theme=Wlt; renderBootFail();
    var Wbf=document.getElementById('bootFail'), Wr=document.documentElement;
    T('W11 阻断层跟随注册表：主题标记是纸底档、状态栏取注册表底色、正文底色与该档一致',
      !!Wbf && Wr.dataset.theme===Wlt && Wr.dataset.mode==='light'
      && document.getElementById('metaTheme').getAttribute('content').toLowerCase()===String(window.THEME_BG[Wlt]).toLowerCase()
      && Wrgb(getComputedStyle(Wbf).backgroundColor).join()===Wrgb(String(window.THEME_BG[Wlt])).join(),
      'theme='+Wr.dataset.theme+' mode='+Wr.dataset.mode+' 底='+(Wbf?getComputedStyle(Wbf).backgroundColor:'无')+' 应='+window.THEME_BG[Wlt]);
    if(Wbf) Wbf.remove(); bootFatal=null; READONLY=false;

    var Wcon=WID.map(function(t){ state.theme=t; applyTheme();
      return {t:t, v:Wcr(Wpx('--ink'), Wpx('--card-a'))}; });
    T('W12 每档主题的正文对卡底对比度都 >= 4.5:1（文档那句「AA 正文档」的可复核版）',
      Wcon.every(function(x){ return x.v>=4.5; }),
      Wcon.map(function(x){ return x.t+' '+x.v.toFixed(2)+':1'; }).join('  '));

    /* 出段还原：主题 / 偏好 / 语言回到进段前，重载轮与其它段看不到 W 段痕迹 */
    state.theme=JSON.parse(WSNAP).theme;
    if(WPREF===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS, WPREF);
    applyTheme(); applyChrome(); renderAll();

    SECT='X'; /* ===== X. 图版（学术风 SVG：几何、类名单源、只读、对比度、双语） ===== */
    /* 这一段自己造账本：种子计划每天本就带 S.Main / B.Main / D.Main 三行处方，
       只需勾上「完成」，四张图就都有真数据 —— 不依赖前面哪一段把 state 改成了什么，
       也不会因为「新装账号还没练」让 X2–X5 变成空跑（空串当然不含 NaN，那是假绿）。 */
    var XBAK=clone(state), XSNAP=JSON.stringify(state);
    var XPREF=localStorage.getItem(LS_PREFS), XWORK=localStorage.getItem(LS_WORK), XLANG=state.lang;
    var XLOG=state.e1rmLog, Xtouch=[], Xn=0;
    function Xset(o,f,v){ Xtouch.push([o,f,o[f]]); o[f]=v; }
    figWeekList().forEach(function(w){ const wk=state.weeks[String(w)]; if(!wk) return;
      dayIds().forEach(function(d){ const dd=wk[d]; if(!dd) return;
        (dd.exercises||[]).forEach(function(e){ if(!anchorOf(e.cat)) return; Xset(e,'done',true); Xn++; }); }); });
    var Xe1=[];
    ['sq','bp','dl'].forEach(function(k,ki){ var base=[150,100,180][ki];
      for(var w=1;w<=13;w+=3){ Xe1.push({id:'XE'+k+w,lift:k,week:w,day:'A',row:0,date:'2026-01-01',
        mode:'T1.Mod',cat:({sq:'S.Main',bp:'B.Main',dl:'D.Main'})[k],mv:'X '+k,
        load:base+w*2.5,reps:5,rpe:8,e1rm:base+w*2.5*(1+7/30)}); } });
    state.e1rmLog=Xe1;

    var Xbad=function(s){ var out=[]; ['NaN','Infinity','undefined','null%','null,'].forEach(function(w){
      if(String(s).indexOf(w)>=0) out.push(w); }); return out.join(','); };
    var XhtmlOf=function(){ var b=document.getElementById('figsBody'); return b?b.innerHTML:''; };
    var XnameOk=new RegExp('[A-Za-z0-9_-]');
    var XcssOf=function(){ var st=document.querySelector('style'); return st?String(st.textContent):''; };
    /* 图里发出的 fx-* 类名（从 class="…" 里抠） */
    var Xused=function(html){ var out={},re=new RegExp('class="([^"]*)"','g'),m;
      while((m=re.exec(String(html)))){ String(m[1]).split(/[^A-Za-z0-9_-]+/).forEach(function(c){
        if(c.indexOf('fx-')===0) out[c]=1; }); }
      return Object.keys(out).sort(); };
    /* 样式表里定义的 fx-* 类名（indexOf 逐段读，不写反斜杠 —— 模板串里的反斜杠会被吞） */
    var Xdefined=function(css){ var out=[],i=0;
      while(true){ i=css.indexOf('.fx-',i); if(i<0) break;
        var j=i+4; while(j<css.length && XnameOk.test(css.charAt(j))) j++;
        var nm=css.slice(i,j); if(out.indexOf(nm)<0) out.push(nm); i=j; }
      return out.sort(); };
    var Xdiff=function(a,b){ return a.filter(function(x){ return b.indexOf(x)<0; }); };

    var Xf=[figE1(),figVolume(),figRpe(),figAdh()];
    T('X1 四张图在真实处方上全部出图（fig-no + fig-svg + 图注三件套齐）',
      Xf.every(function(s){ return s.indexOf('class="fig-svg"')>=0 && s.indexOf('class="fig-cap"')>=0
        && s.indexOf('class="fig-no"')>=0 && s.indexOf('fig-empty')<0; })
      && ['Fig.1','Fig.2','Fig.3','Fig.4'].every(function(n,i){ return Xf[i].indexOf(n)>=0; }),
      '主项完成组 '+Xn+' 行 · e1RM 记录 '+Xe1.length+' 条');

    T('X2 图串里不出现 NaN / Infinity / undefined / null%（缺测就少画一个元素，不画坏坐标）',
      Xf.every(function(s){ return Xbad(s)==''; }),
      Xf.map(function(s,i){ return 'Fig.'+(i+1)+'=['+Xbad(s)+']'; }).join(' '));

    T('X3 图内颜色零字面量：SVG 串里没有 # 色值、没有 rgb()/rgba()（颜色只在令牌块与 fx-* 规则里）',
      Xf.every(function(s){ return s.indexOf('#')<0 && s.indexOf('rgb(')<0 && s.indexOf('rgba(')<0; }),
      '四串长度 '+Xf.map(function(s){ return s.length; }).join('/'));

    var Xu=Xused(Xf.join('')), Xd=Xdefined(XcssOf());
    T('X4 图里发出的每个 fx-* 类名都有 CSS 定义（类名写错不是报错，是线画不出来 / 画成默认黑）',
      Xu.every(function(c){ return Xd.indexOf('.'+c)>=0; }),
      '用到 '+Xu.length+' 个 · 未命中 '+Xdiff(Xu.map(function(c){return '.'+c;}),Xd).join(','));

    /* 边缘夹具：把剩下五条只在某些数据形状下才走的画图分支踩一遍 ——
       辅助项色块、整天无处方、样本<5 只画均值、离群圈、减载底纹。
       X5 要的是「CSS 里没有一条没人画的规则」，只看默认数据永远踩不全。 */
    var Xmark=Xtouch.length, Xwk1=state.weeks[String(figWeekList()[0])];
    (function(){
      var exs=((Xwk1&&Xwk1.A)||{}).exercises||[];
      exs.forEach(function(e,i){ if(anchorOf(e.cat)) return;
        Xset(e,'done',true); Xset(e,'load',40); Xset(e,'reps',10); });
      var nBp=0;
      figWeekList().forEach(function(w){ const dd=state.weeks[String(w)]; if(!dd) return;
        dayIds().forEach(function(d){ const g=dd[d]; if(!g) return;
          (g.exercises||[]).forEach(function(e){ if(anchorOf(e.cat)==='bp'){ nBp++; if(nBp>2) Xset(e,'done',false); } }); }); });
      var sqDone=false;
      figWeekList().forEach(function(w){ const wk=state.weeks[String(w)]; if(!wk) return;
        dayIds().forEach(function(d){ const g=wk[d]; if(!g) return;
          (g.exercises||[]).forEach(function(e){ if(!sqDone && anchorOf(e.cat)==='sq'){ Xset(e,'rpe',1); sqDone=true; } }); }); });
      if(Xwk1&&Xwk1.B) Xset(Xwk1.B,'exercises',[]);
      (state.structure.blocks||[]).forEach(function(b,i){ if(i===0) Xset(b,'deloadWeeks',1); });
      Xset(state,'migrateReport',{v7:{fresh:false,atWeek:2}});   /* 逼 figE1 发 fx-mig，让 X5 的「定义必被用」踩全 */
    })();
    var Xg=[figE1(),figVolume(),figCatVolume(),figRpe(),figAdh()];
    var Xall=Xf.concat(Xg), XallU=Xused(Xall.join(''));
    Xtouch.slice(Xmark).reverse().forEach(function(t){ t[0][t[1]]=t[2]; });
    T('X5 反向也对：CSS 里的每条 fx-* 规则都被图用到（默认数据 + 边缘夹具合起来踩全分支）',
      Xd.length>=22 && Xdiff(Xd,XallU.map(function(c){ return '.'+c; })).length===0
      && Xall.every(function(s){ return Xbad(s)==''; }),
      '定义 '+Xd.length+' 个 · 没人用 '+Xdiff(Xd,XallU.map(function(c){return '.'+c;})).join(',')
      +' · 边缘态坏值 '+Xg.map(function(s){ return Xbad(s); }).filter(Boolean).join(','));

    /* X5b 口径分界线：v7 把自重/哑铃的 load 语义换过一次口径，分界周左侧的历史点是旧口径。
       只在「非首建 + 报告在 + atWeek 落在 [1,total]」这一条窄路径上画，其余一律不画（画错比不画坏）。 */
    var Xtw=figTotalWeeks(), XmrSave=state.migrateReport;
    function Xmig(mm){ if(mm===undefined) delete state.migrateReport; else state.migrateReport=mm; return figE1(); }
    var XmigOn=Xmig({v7:{fresh:false,atWeek:Math.min(3,Xtw)}}).indexOf('fx-mig')>=0;
    var XmigFresh=Xmig({v7:{fresh:true,atWeek:3}}).indexOf('fx-mig')<0;
    var XmigOut=Xmig({v7:{fresh:false,atWeek:Xtw+6}}).indexOf('fx-mig')<0;
    var XmigZero=Xmig({v7:{fresh:false,atWeek:0}}).indexOf('fx-mig')<0;
    var XmigNull=Xmig({v7:{fresh:false,atWeek:null}}).indexOf('fx-mig')<0;
    var XmigNone=Xmig(undefined).indexOf('fx-mig')<0;
    if(XmrSave===undefined) delete state.migrateReport; else state.migrateReport=XmrSave;
    T('X5b e1RM 口径分界线只在「非首建 v7 报告 + atWeek∈[1,total]」时出现；首建/越界/0/null/无报告都不画',
      XmigOn&&XmigFresh&&XmigOut&&XmigZero&&XmigNull&&XmigNone,
      '在='+XmigOn+' 首建='+XmigFresh+' 越界='+XmigOut+' 零='+XmigZero+' null='+XmigNull+' 无='+XmigNone+'（total='+Xtw+'）');

    openFigsSheet();
    T('X6 openFigsSheet 只画不写：偏好与账本两个分片逐字节不动',
      localStorage.getItem(LS_PREFS)===XPREF && localStorage.getItem(LS_WORK)===XWORK
      && document.getElementById('figsSheet').classList.contains('on'),
      'prefs 不变='+(localStorage.getItem(LS_PREFS)===XPREF)+' work 不变='+(localStorage.getItem(LS_WORK)===XWORK));
    T('X7 面板里真挂着四张 SVG + 五张卡（分类容量是表格，不是 SVG）',
      document.querySelectorAll('#figsSheet svg.fig-svg').length===4
      && document.querySelectorAll('#figsSheet .fig-card').length===5,
      'SVG '+document.querySelectorAll('#figsSheet svg.fig-svg').length+' · 卡 '+document.querySelectorAll('#figsSheet .fig-card').length);
    T('X7c 分类容量表有类别行与合计行', document.querySelectorAll('#figsSheet .cat-vol-table tbody tr').length>=2
      && !!document.querySelector('#figsSheet .cat-vol-table tr.total'),
      document.querySelectorAll('#figsSheet .cat-vol-table tbody tr').length);
    /* 图例走的是 .fig-lg.<键>，键名由数据拼出来，S20 查不动拼后的串 —— 这一条腿只能在运行时算样式：
       A) CSS 里每条 .fig-lg.<键> 规则都要真的上得了色（令牌名手抄错 → 色块是透明的，不报错）；
       B) 画图代码发出的每个键名都得在 CSS 里有定义（'ohp' 抄成 'oohp' 就是一个空白块）。
       夹具里必然出现辅助项那一格（X5 靠它踩 fx-fohp），所以 B 的键集不是空跑。 */
    var Xcls=function(html){ var out=[],re=new RegExp('class="([^"]*)"','g'),m;
      while((m=re.exec(String(html)))) out.push(String(m[1]).split(/[^A-Za-z0-9_-]+/)); return out; };
    var XlgUsed=function(html){ var o={}; Xcls(html).forEach(function(a){
      for(var i=0;i+1<a.length;i++) if(a[i]==='fig-lg') o[a[i+1]]=1; });
      return Object.keys(o).sort(); };
    var XlgKeys=function(css){ var out=[],i=0;
      while(true){ i=css.indexOf('.fig-lg.',i); if(i<0) break; var j=i+8;
        while(j<css.length && XnameOk.test(css.charAt(j))) j++;
        var k=css.slice(i+8,j); if(out.indexOf(k)<0) out.push(k); i=j; }
      return out.sort(); };
    var XlgWant=XlgKeys(XcssOf());
    var XlgGot=XlgUsed(Xall.join('')+XhtmlOf());
    var Xprobe=document.createElement('div');
    Xprobe.innerHTML=figLegend(XlgWant.map(function(k){ return [k,'']; }));
    document.body.appendChild(Xprobe);
    var Xblk=[].slice.call(Xprobe.querySelectorAll('.fig-lg')).filter(function(s){
      var i=s.querySelector('i'); if(!i) return true;
      var st=getComputedStyle(i), b=st.backgroundColor, bw=parseFloat(st.borderTopWidth)||0;
      return (b==='rgba(0, 0, 0, 0)'||b==='transparent'||b==='') && !(bw>0 && st.borderTopStyle!=='none'); });
    document.body.removeChild(Xprobe);
    T('X7b 图例两条腿：CSS 每条 .fig-lg.<键> 都上得了色，且画图发出的键都有定义',
      XlgWant.length>=5 && Xblk.length===0 && Xdiff(XlgGot,XlgWant).length===0,
      'CSS 键 '+XlgWant.join('/')+' · 发出 '+XlgGot.join('/')+' · 空白块 '+Xblk.length
      +' · 无定义键 '+Xdiff(XlgGot,XlgWant).join(','));
    closeSheet('figsSheet');

    var Xt=figTicks(3.2,97.4,4), Xstep=Xt.length>1?(Xt[1]-Xt[0]):0;
    var Xnice=(function(){ var k=0, x=Xstep; while(x>=10){ x/=10; k++; } while(x>0&&x<1){ x*=10; k--; }
      return Math.abs(x-1)<1e-9||Math.abs(x-2)<1e-9||Math.abs(x-5)<1e-9; })();
    T('X8 figTicks 只出 nice 步长（1/2/5 × 10^k）、等距单调、且不越出区间',
      Xnice && Xt.length>=3 && Xt.every(function(v,i){ return i===0||(v>Xt[i-1]&&Math.abs((v-Xt[i-1])-Xstep)<1e-9); })
      && Xt[0]>=3.2 && Xt[Xt.length-1]<=97.4, Xt.join(',')+' step='+Xstep+' nice='+Xnice);
    T('X8b figTicks 退化输入不炸：上下界相等 / 非数字都只回一个刻度',
      figTicks(5,5,4).length===1 && figTicks(NaN,10,4).length===1 && figTicks(0,0,4).length===1,
      figTicks(5,5,4).join('/')+' / '+figTicks(NaN,10,4).join('/'));

    var Xq=[1,2,3,4,5,6,7,8,9,10];
    T('X9 分位数是线性插值（R-7）：1..10 的 Q1 / 中位 / Q3 = 3.25 / 5.5 / 7.75',
      Math.abs(figQuant(Xq,.25)-3.25)<1e-9 && Math.abs(figQuant(Xq,.5)-5.5)<1e-9 && Math.abs(figQuant(Xq,.75)-7.75)<1e-9,
      [figQuant(Xq,.25),figQuant(Xq,.5),figQuant(Xq,.75)].join('/'));
    var Xst=figStats([4,5,5,6,6,6,7,7,8,20]);
    T('X10 Tukey 箱线自洽：Q1≤中位≤Q3、触须落在栅栏内的真实数据、20 被判为离群',
      Xst.q1<=Xst.med && Xst.med<=Xst.q3 && Xst.whLo>=Xst.q1-1.5*(Xst.q3-Xst.q1)
      && Xst.whHi<=Xst.q3+1.5*(Xst.q3-Xst.q1) && Xst.out.join()==='20' && Xst.n===10,
      'Q'+[Xst.q1,Xst.med,Xst.q3].join('/')+' 触须 '+Xst.whLo+'–'+Xst.whHi+' 离群 ['+Xst.out.join(',')+']');
    var Xrm=figRollMean([{x:1,y:10},{x:2,y:20},{x:3,y:30},{x:4,y:40},{x:5,y:50}],4);
    T('X11 滚动均值窗口对：前三点是累积均值，第五点滑掉最旧（(20+30+40+50)/4=35）',
      Xrm.length===5 && Math.abs(Xrm[2].y-20)<1e-9 && Math.abs(Xrm[3].y-25)<1e-9 && Math.abs(Xrm[4].y-35)<1e-9,
      Xrm.map(function(p){ return p.y; }).join('/'));

    var Xcon=[];
    WID.forEach(function(t){ state.theme=t; applyTheme();
      var v=['--fig-sq','--fig-bp','--fig-dl','--fig-ohp','--fig-ink','--fig-axis'].map(function(k){
        return {k:k, r:Wcr(Wpx(k),Wpx('--well'))}; });
      Xcon.push({t:t, low:v.reduce(function(m,x){ return x.r<m.r?x:m; },v[0]), v:v}); });
    T('X12 三档主题下图版配色都够读：系列色 / 刻度文字对画布底 ≥4.5:1（画布底 = --well）',
      Xcon.every(function(x){ return x.low.r>=4.5; }),
      Xcon.map(function(x){ return x.t+' 最低 '+x.low.r.toFixed(2)+':1('+x.low.k+')'; }).join('  '));
    state.theme=JSON.parse(XSNAP).theme; applyTheme();

    var Xen=(function(){ state.lang='en'; renderFigs(); var h=String(XhtmlOf()); state.lang='zh'; renderFigs();
      var z=String(XhtmlOf()); state.lang=XLANG; renderFigs();
      var han=new RegExp('[\\\\u4e00-\\\\u9fa5]');
      return {enLen:h.length,zhLen:z.length,enHan:han.test(h),zhHan:han.test(z),
              enTt:h.indexOf('WEEKLY e1RM TREND')>=0, zhTt:z.indexOf('逐周趋势')>=0}; })();
    T('X13 图版双语隔离：英文串里零汉字、中文串里有汉字，标题两种语言都在',
      !Xen.enHan && Xen.zhHan && Xen.enTt && Xen.zhTt && Xen.enLen>800 && Xen.zhLen>800,
      'en='+Xen.enLen+(Xen.enHan?' 含汉字':'')+' zh='+Xen.zhLen+(Xen.zhHan?'':' 缺汉字'));
    T('X13b 方法与口径说明随语言走且非空',
      (document.getElementById('figsNote').textContent||'').length>20,
      String(document.getElementById('figsNote').textContent||'').slice(0,16));

    T('X14 入口接线正确：setFigsGo 的 onclick 指向 openChartHub，图版与 hub 都在收口名单里',
      String(document.getElementById('setFigsGo').closest('button').getAttribute('onclick')||'').indexOf('openChartHub')>=0
      && String(closeAllSheets).indexOf('figsSheet')>=0 && !!document.getElementById('figsSheet')
      && String(closeAllSheets).indexOf('chartSheet')>=0,
      'onclick + closeAllSheets 双命中');
    T('X15 图版是纯 SVG：面板内没有 canvas，也没有任何外链协议串',
      document.querySelectorAll('#figsSheet canvas').length===0
      && String(XhtmlOf()).indexOf('http')<0 && String(XhtmlOf()).indexOf('canvas')<0,
      'canvas 0 · 串内无 http/canvas');

    /* HUB X21-X24（图表 hub：图版 / e1RM 趋势 / 分类容量 / 训练日志）
       趋势整块从档案页搬进 hub，档案 v0.46 起收为单页全量表；四条视图一律只读。 */
    T('X21 hub 四条入口各自指向对应面板，四个面板都在收口名单里',
      [['chartFigsGo','openFigsSheet','figsSheet'],['chartTrendGo','openTrendSheet','trendSheet'],
       ['chartCatGo','openCatVolSheet','catVolSheet'],['chartLogGo','openLogSheet','logSheet']]
      .every(function(x){
        const b=document.getElementById(x[0]);
        return !!b && String(b.closest('button').getAttribute('onclick')||'').indexOf(x[1])>=0
            && !!document.getElementById(x[2]) && String(closeAllSheets).indexOf(x[2])>=0;
      }),
      ['chartFigsGo','chartTrendGo','chartCatGo','chartLogGo'].map(function(id){
        const b=document.getElementById(id); return id+'='+(b?String(b.closest('button').getAttribute('onclick')||'').replace(/[^a-zA-Z]/g,'.'):-1);
      }).join(' '));
    T('X22 趋势已从档案页移出：profTabTrendBox / profTabTrend 不存在；v0.46 档案收为单页后整个 profSheet 内已无任何 profTab* 节点；趋势只活在 trendSheet',
      !document.getElementById('profTabTrendBox') && !document.getElementById('profTabTrend')
      && !!document.getElementById('trendSheet')
      && document.querySelectorAll('#profSheet [id^="profTab"]').length===0
      && String(document.getElementById('e1Trend').closest('.sheet').id)==='trendSheet',
      'e1Trend 宿主='+(document.getElementById('e1Trend')?String(document.getElementById('e1Trend').closest('.sheet').id):'-'));
    var Xh0=localStorage.getItem(LS_PREFS), Xw0=localStorage.getItem(LS_WORK);
    openChartHub(); closeSheet('chartSheet');
    openTrendSheet(); closeSheet('trendSheet');
    openCatVolSheet(); closeSheet('catVolSheet');
    openLogSheet();
    T('X23 四条视图只画不写：hub/趋势/分类容量/日志开合后两个分片逐字节不动',
      localStorage.getItem(LS_PREFS)===Xh0 && localStorage.getItem(LS_WORK)===Xw0
      && document.getElementById('logSheet').classList.contains('on'),
      'prefs 不变='+(localStorage.getItem(LS_PREFS)===Xh0)+' work 不变='+(localStorage.getItem(LS_WORK)===Xw0));
    var XlogAll=document.querySelectorAll('#logBody tbody tr').length;
    var Xwk=document.getElementById('logWeek').options[1]?document.getElementById('logWeek').options[1].value:'';
    document.getElementById('logWeek').value=Xwk; renderLogTable();
    var XlogOne=document.querySelectorAll('#logBody tbody tr').length;
    document.getElementById('logMv').value='__no_such_movement__'; renderLogTable();
    var XlogNone=!!document.querySelector('#logBody .log-empty');
    resetLogFilters();
    T('X24 日志筛选生效且可清除：全量 > 单周 > 零结果走空态，复位回到全量',
      XlogAll>0 && XlogOne>0 && XlogOne<=XlogAll && XlogNone
      && document.querySelectorAll('#logBody tbody tr').length===XlogAll
      && String(document.getElementById('logStat').textContent||'').length>4,
      '全 '+XlogAll+' / 周'+Xwk+' '+XlogOne+' / 空态 '+XlogNone);

    /* 空态放在最后：上面所有「有没有画出来」的判据都要吃真数据，先清空会把它们一起放走。
       这里把「已完成」全部关掉（前面的段确实会把某些组勾上，光还原本段的触点不等于新装账号）。 */
    state.e1rmLog=[];
    figWeekList().forEach(function(w){ const wk=state.weeks[String(w)]; if(!wk) return;
      dayIds().forEach(function(d){ const dd=wk[d]; if(!dd) return;
        (dd.exercises||[]).forEach(function(e){ if(e.done) Xset(e,'done',false); }); }); });
    var Xe=[figE1(),figVolume(),figRpe(),figAdh()];
    T('X16 新装账号（无 e1RM 账本、无完成组）：趋势 / 训练量 / 箱线三张走空态，依从性图照常出图',
      Xe[0].indexOf('fig-empty')>=0 && Xe[1].indexOf('fig-empty')>=0 && Xe[2].indexOf('fig-empty')>=0
      && Xe[3].indexOf('fig-svg')>=0 && Xbad(Xe.join(''))===''
      && Xe.every(function(s,i){ return s.indexOf('Fig.'+(i+1))>=0; }),
      '空态 '+Xe.map(function(s,i){ return s.indexOf('fig-empty')>=0?(i+1):''; }).filter(Boolean).join(',')
      +' · Fig.4 有处方即成图（全零也是数据）');
    /* 连处方都拔掉：第四张也该退成空态，而不是画一张 0×0 的网格 */
    figWeekList().forEach(function(w){ const wk=state.weeks[String(w)]; if(!wk) return;
      dayIds().forEach(function(d){ const dd=wk[d]; if(dd && (dd.exercises||[]).length) Xset(dd,'exercises',[]); }); });
    var Xe2=figAdh();
    T('X16b 处方也清空后，依从性图同样走空态（不画空网格、不抛错）',
      Xe2.indexOf('fig-empty')>=0 && Xe2.indexOf('fig-svg')<0 && Xbad(Xe2)==='', '长度 '+Xe2.length);

    /* 出段还原：造出来的 done / e1RM 账本、语言、主题、两个分片全部退回进段前 */
    Xtouch.forEach(function(t){ t[0][t[1]]=t[2]; });
    state.e1rmLog=XLOG; state.lang=XLANG;
    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(XBAK).forEach(function(k){ state[k]=XBAK[k]; });
    if(XPREF===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS, XPREF);
    if(XWORK===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, XWORK);
    var Xfb=document.getElementById('figsBody'); if(Xfb) Xfb.innerHTML='';
    applyTheme(); applyChrome(); renderAll();
    T('X17 出段还原：图版本段没把共享对象改脏，也没落盘（文本快照对得上）',
      JSON.stringify(state)===XSNAP && localStorage.getItem(LS_PREFS)===XPREF
      && localStorage.getItem(LS_WORK)===XWORK,
      '长度 '+JSON.stringify(state).length+'/'+XSNAP.length);

    /* ===== O. 下周建议（只读引擎）：分支优先级、判据单源、幅度夹取、零写盘 =====
       造三周夹具：W1 上周（只为「连续两周」判定而存在）、W2 账本源周、W3 下周处方。
       整块换掉 state.weeks 再还原 —— 期望值能在纸面上算死，不必赌种子里恰好有什么；
       15 行 = 分支表的全覆盖，任何一条分支被改坏都会掉下来一行、被 O1 抓住。
       （D6 起：自重行进加重档，另留一条非自重 load=0 行钉「空杆跳过」分支不被稀释。） */
    SECT='O';
    var OBAK=clone(state), OSNAP=JSON.stringify(state);
    var OPREF=localStorage.getItem(LS_PREFS), OWORK=localStorage.getItem(LS_WORK), OLANG=state.lang;
    var Oar=PLAN_SCHEMA.autoreg||{};
    var Oday=dayIds()[0];
    var Ospec=[
      {k:'up',     mode:'T1.Mod',   cat:'S.Main', mv:'O Up',    load:120, reps:6,  rpe:6.0, tr:7.0, ds:3},
      {k:'t3up',   mode:'T3.Def',   cat:'B.Main', mv:'O T3def', load:40,  reps:25, rpe:6.0, tr:8.0, ds:3},
      {k:'t3keep', mode:'T3.Mod',   cat:'B.Main', mv:'O T3mod', load:30,  reps:17, rpe:6.0, tr:8.0, ds:4},
      {k:'hard',   mode:'T2.5x5',   cat:'B.Main', mv:'O Hard',  load:100, reps:3,  rpe:9.6, tr:7.0, ds:5},
      {k:'strug',  mode:'T1.Mod',   cat:'S.Main', mv:'O Strug', load:100, reps:3,  rpe:8.0, tr:7.0, ds:3},
      {k:'rate',   mode:'T1.Def',   cat:'S.Main', mv:'O Rate',  load:90,  reps:3,  rpe:7.0, tr:7.0, ds:3},
      {k:'norpe',  mode:'T2.Mod',   cat:'B.Main', mv:'O NoRpe', load:60,  reps:8,  rpe:0,   tr:7.0, ds:4},
      {k:'cap',    mode:'T1.Mod',   cat:'S.Main', mv:'O Cap',   load:45,  reps:6,  rpe:6.0, tr:7.0, ds:3},
      {k:'dl',     mode:'T1.DL',    cat:'S.Main', mv:'O DL',    load:70,  reps:3,  rpe:6.0, tr:7.0, ds:2},
      {k:'test',   mode:'Top.Test', cat:'S.Main', mv:'O Test',  load:110, reps:1,  rpe:7.0, tr:9.0, ds:1},
      {k:'bar0',   mode:'T1.Mod',   cat:'S.Main', mv:'O Bar0',  load:0,   reps:5,  rpe:7.0, tr:7.0, ds:2},
      {k:'bw',     mode:'T1.Mod',   cat:'B.Acc',  mv:'O BW',    load:25,  reps:6,  rpe:6.0, tr:7.0, ds:3, gear:{kind:'bw',lever:1}},
      {k:'noset',  mode:'T1.Mod',   cat:'S.Main', mv:'O NoSet', load:80,  reps:5,  rpe:7.0, tr:7.0, ds:0},
      {k:'gone',   mode:'T2.Mod',   cat:'B.Main', mv:'O Gone',  load:55,  reps:8,  rpe:6.0, tr:7.0, ds:4, gone:1},
      {k:'swap',   mode:'T1.Mod',   cat:'D.Main', mv:'O Old',   load:95,  reps:5,  rpe:7.0, tr:7.0, ds:3, to:'O New'}
    ];
    var Omk=function(sp,i){ var o={row:100+i, mode:sp.mode, cat:sp.cat, mv:sp.mv, load:sp.load,
      reps:sp.reps, rpe:sp.rpe, targetRpe:sp.tr, doneSets:sp.ds, done:sp.ds>0, notes:''};
      if(sp.gear) o.gear=sp.gear; return o; };
    var Osrc=Ospec.map(Omk);
    var Oprev=clone(Osrc);
    var Odst=[];
    Ospec.forEach(function(sp,i){ if(sp.gone) return; var e=Omk(sp,i); if(sp.to) e.mv=sp.to; Odst.push(e); });
    var Owk=function(list){ var o={}; o[Oday]={title:'O FIX',exercises:list}; return o; };
    state.weeks={'1':Owk(Oprev),'2':Owk(Osrc),'3':Owk(Odst)};
    state.e1rmLog=[{id:'OA',lift:'sq',week:1,day:'A',row:0,date:'2026-01-01',mode:'T1.Mod',cat:'S.Main',mv:'O Up',load:130,reps:5,rpe:8,e1rm:140},
                   {id:'OB',lift:'sq',week:2,day:'A',row:0,date:'2026-01-08',mode:'T1.Mod',cat:'S.Main',mv:'O Up',load:133,reps:5,rpe:8,e1rm:142.5}];
    var OLOG=state.e1rmLog;
    var OIN=JSON.stringify(state);
    var Oall=nextWeekAdvice(2);
    var Oget=function(k){ var sp=Ospec.filter(function(s){return s.k===k;})[0]||{};
      return Oall.filter(function(r){ return r.mv===sp.mv; })[0]||null; };
    var Ocnt=function(v){ return Oall.filter(function(r){ return r.verdict===v; }).length; };
    var Orow=function(w){ return nextWeekAdvice(2).filter(function(r){ return r.mv===w; })[0]||null; };
    var Obad=function(s){ var out=[]; ['NaN','Infinity','undefined','null%','null,'].forEach(function(w){
      if(String(s).indexOf(w)>=0) out.push(w); }); return out.join(','); };
    var Odig=function(s){ var out=[]; '0123456789'.split('').forEach(function(c){
      if(String(s).indexOf(c)>=0) out.push(c); }); return out.join(''); };
    var Ou=Oget('up'), O3=Oget('t3up'), O3k=Oget('t3keep'), Oh=Oget('hard'), Os=Oget('strug');
    var Orate=Oget('rate'), Onr=Oget('norpe'), Ocap=Oget('cap'), Obw=Oget('bw');
    var Ochain=adviceChain('T1.Mod');

    T('O1 夹具 15 行全部落进分支表：加重 3 / 下调 2 / 保持 4 / 跳过 6，且每条都有依据、加减速差非零',
      Oall.length===15 && Ocnt('up')===3 && Ocnt('down')===2 && Ocnt('keep')===4 && Ocnt('skip')===6
      && Oall.every(function(r){ return r.why.length>0
          && ((r.verdict==='up'||r.verdict==='down') ? r.delta!==0 : r.delta===0); }),
      '共 '+Oall.length+' · up '+Ocnt('up')+' / down '+Ocnt('down')+' / keep '+Ocnt('keep')+' / skip '+Ocnt('skip'));

    T('O2 达标下肢行按契约步进加重（步进值取自 autoreg.step_up_kg.lower，不是模板里的常量）',
      !!Ou && Ou.verdict==='up' && Ou.delta===+(Oar.step_up_kg||{}).lower
      && Ou.nextLoad===Ou.load+Ou.delta && Ou.clamped===false && Ou.mode2===null,
      Ou ? (Ou.load+' → '+Ou.nextLoad+'（+'+Ou.delta+'；契约 lower='+Oar.step_up_kg.lower+'）') : '夹具行没算出来');

    T('O3 T3 行一律走契约最小步进：比上肢和下肢步进都小，与类别无关',
      !!O3 && O3.verdict==='up' && O3.delta===+Oar.t3_step_kg
      && O3.delta!==+Oar.step_up_kg.upper && O3.delta!==+Oar.step_up_kg.lower,
      O3 ? ('Δ'+O3.delta+'（T3 '+Oar.t3_step_kg+' vs 上肢 '+Oar.step_up_kg.upper+' / 下肢 '+Oar.step_up_kg.lower+'）') : '无行');

    T('O4 T3 干净次数闸门：末组差契约阈值一次也不加，退成保持',
      !!O3k && O3k.verdict==='keep' && O3k.delta===0
      && O3k.lastReps<+(Oar.clean_reps||{})[O3k.mode] && O3k.rate>=1,
      O3k ? ('末组 '+O3k.lastReps+' < 干净 '+Oar.clean_reps[O3k.mode]+'（'+O3k.mode+'）') : '无行');

    T('O5 实 RPE 超契约硬顶：直接按 regress_kg 下调，不再走两周判定、也不建议换阶',
      !!Oh && Oh.rpe>+Oar.rpe_hard_stop && Oh.verdict==='down'
      && Oh.delta===-(+Oar.regress_kg) && Oh.mode2===null && Oh.why.join(' ').indexOf('超硬顶')>=0,
      Oh ? ('rpe '+Oh.rpe+' > '+Oar.rpe_hard_stop+' → '+Oh.load+'→'+Oh.nextLoad) : '无行');

    T('O6 连续两周「RPE ≥ 目标+缺口 且末组未达标」→ 减 regress_kg 并建议进下一阶（阶段链从 seed.proto 派生）',
      !!Os && Os.verdict==='down' && Os.delta===-(+Oar.regress_kg)
      && Os.mode2===Ochain[1] && Ochain.join(',')==='T1.Mod,T1.Mod.2,T1.Mod.3'
      && Os.why.join(' ').indexOf('只给建议')>=0,
      Os ? (Os.load+'→'+Os.nextLoad+' · 阶段建议 '+Os.mode2+' · 链 '+Ochain.join('>')+' · '+Os.why.join('|')) : '无行');

    T('O7 完成率低于契约下限 → 保持（组数没跑满不给加重），依据里把百分比写给人看',
      !!Orate && Orate.verdict==='keep' && Orate.delta===0
      && Orate.rate<+Oar.min_completion && Orate.why.join(' ').indexOf('完成率 60%')>=0,
      Orate ? ('完成率 '+Math.round(Orate.rate*100)+'% < 下限 '+Math.round(Oar.min_completion*100)+'%') : '无行');

    T('O8 缺实 RPE 只给保持：不猜强度，也不硬凑进阶条件',
      !!Onr && Onr.verdict==='keep' && Onr.delta===0 && Onr.rpe===0
      && Onr.rate>=1 && Onr.why.join(' ').indexOf('缺实 RPE')>=0,
      Onr ? ('rpe='+Onr.rpe+' 组数 '+Onr.doneSets+'/'+Onr.planSets) : '无行');

    T('O9 单次幅度上限（±5% 或 ±5kg 取小）：小重量夹到不足一档就退成保持，大重量不受夹',
      !!Ocap && Ocap.verdict==='keep' && Ocap.delta===0 && Ocap.clamped===true
      && Ocap.why.join(' ').indexOf('不足一档')>=0
      && adviceClamp(45,5,5).delta===0 && adviceClamp(200,5,5).delta===5
      && adviceClamp(100,2.5,2.5).delta===2.5,
      Ocap ? ('45kg 的 5% = '+(45*Oar.cap_pct)+' 装不下一档 '+Oar.step_up_kg.lower) : '无行');

    var Osk=['dl','test','bar0','noset','gone','swap'].map(Oget);
    T('O10 六种跳过各自踩到分支：减载 / 测试 / 空杆 / 无完成组 / 下周无对应行 / 换动作，delta 全 0 且各给各的理由',
      Osk.every(function(r){ return !!r && r.verdict==='skip' && r.delta===0
        && r.nextLoad===r.load && r.why.length===1; })
      && Osk.map(function(r){ return r.why[0]; }).filter(function(x,i,a){ return a.indexOf(x)===i; }).length>=5
      && Osk[0].why[0]===Osk[1].why[0]
      && Osk[2].why[0].indexOf('未配重')>=0 && Osk[3].why[0].indexOf('没有完成组')>=0
      && Osk[4].why[0].indexOf('没有对应行')>=0 && Osk[5].why[0].indexOf('换动作')>=0,
      Osk.map(function(r){ return r?r.mv+'='+r.why[0]:'-'; }).join(' / '));

    var Olower=Oar.step_up_kg.lower;
    PLAN_SCHEMA.autoreg.step_up_kg.lower=2.5;
    var Omut=Orow('O Up');
    PLAN_SCHEMA.autoreg.step_up_kg.lower=Olower;
    T('O11 判据单源：把契约 lower 步进改成 2.5 再算一次，建议立刻跟着变（模板里没有第二个数）',
      Omut && Omut.delta===2.5 && Orow('O Up').delta===+Olower
      && adviceStepKg('T1.Mod','S.Main')===+Oar.step_up_kg.lower
      && adviceStepKg('T2.Mod','B.Main')===+Oar.step_up_kg.upper
      && adviceStepKg('T3.Mod','S.Main')===+Oar.t3_step_kg
      && String(autoregOf).indexOf('PLAN_SCHEMA.autoreg')>=0,
      Omut ? ('契约改写后 Δ'+Omut.delta+'，改回 Δ'+Orow('O Up').delta) : '无行');

    T('O11b 自重进自动加重（D6）：kind=bw 走既有上肢档位直接落，不被 ±5% 夹成保持（下一行 O12 仍证它无锚点不编趋势）',
      !!Obw && Obw.kind==='bw' && Obw.verdict==='up'
      && Obw.delta===+(Oar.step_up_kg.upper) && Obw.nextLoad===Obw.load+Obw.delta && Obw.clamped===false
      && adviceClamp(Obw.load, +Oar.step_up_kg.upper, +Oar.step_up_kg.upper).delta===0,
      Obw ? (Obw.kind+' '+Obw.verdict+' Δ'+Obw.delta+'：'+Obw.load+'→'+Obw.nextLoad
             +'（杠铃口径本会夹成 '+adviceClamp(Obw.load,+Oar.step_up_kg.upper,+Oar.step_up_kg.upper).delta+'）') : '无行');

    T('O12 e1RM 趋势只读账本最近两次的差；不足两次或类别无锚点一律不编数',
      !!Ou && !!Ou.trend && Math.abs(Ou.trend.delta-2.5)<0.001 && Ou.trend.to===2 && Ou.trend.from===1
      && !!Obw && Obw.trend===null && Orow('O Up') && (function(){ var g=state.e1rmLog;
        state.e1rmLog=[]; var r=Orow('O Up'); state.e1rmLog=g; return r && r.trend===null; })(),
      Ou ? ('sq 趋势 '+(Ou.trend? '+'+Ou.trend.delta : '—')+' · 无锚点 '+Obw.trend) : '无行');

    T('O13 接线与相邻周选择器：setAdvGo 指向 openAdviceSheet、面板在收口名单里、下拉只列 W 与 W+1 都在的周对',
      String(document.getElementById('setAdvGo').closest('button').getAttribute('onclick')||'').indexOf('openAdviceSheet')>=0
      && String(closeAllSheets).indexOf('adviceSheet')>=0 && !!document.getElementById('adviceSheet')
      && adviceSrcWeekOptions().join(',')==='1,2'
      && (fillAdviceWeek(), document.getElementById('advWeek').options.length===2),
      '周对='+adviceSrcWeekOptions().join(','));

    state.lang='zh'; applyChrome(); openAdviceSheet();
    var Otrs=document.querySelectorAll('#advBody tbody tr').length;
    var Oth=document.querySelectorAll('#advBody thead th').length;
    var Oup=document.querySelectorAll('#advBody tr.up').length;
    var Odn=document.querySelectorAll('#advBody tr.down').length;
    var ObodyStr=String(document.getElementById('advBody').innerHTML);
    var OstatZh=String(document.getElementById('advStat').textContent||'');
    var OnoteZh=String(document.getElementById('advNote').textContent||'');
    T('O14 表格真画出来：15 行 / 表头七列 / 当前→建议同格 / up·down 类名在位 / 汇总条四个计数齐，串里无 NaN·undefined',
      Otrs===15 && Oth===7 && Oup===3 && Odn===2
      && ObodyStr.indexOf('→')>=0 && ObodyStr.indexOf('class="nx"')>=0
      && OstatZh.indexOf('加重 3')>=0 && OstatZh.indexOf('保持 4')>=0
      && OstatZh.indexOf('下调 2')>=0 && OstatZh.indexOf('跳过 6')>=0
      && ObodyStr.indexOf('td class="why"')>=0 && Obad(ObodyStr+OstatZh)==='',
      Otrs+' 行 · 表头 '+Oth+' · '+OstatZh.slice(0,28));

    state.lang='en'; applyChrome(); openAdviceSheet();
    var ObodyEn=String(document.getElementById('advBody').innerHTML);
    var OstatEn=String(document.getElementById('advStat').textContent||'');
    var OnoteEn=String(document.getElementById('advNote').textContent||'');
    state.lang=OLANG; applyChrome();
    var OnoteNum=function(s){ return Odig(String(s).split('T1').join('').split('T2').join('').split('T3').join('')); };
    T('O15 双语隔离：英文表头/汇总/说明零汉字，中文态有汉字；两侧说明都不抄契约里的数（只有阶段名 T1/T2/T3）',
      ObodyEn.indexOf('WHY')>=0 && OstatEn.indexOf('skip 6')>=0
      && OnoteEn.indexOf('autoreg')>=0 && !HAN.test(OnoteEn+OstatEn) && HAN.test(OnoteZh+OstatZh)
      && OnoteNum(OnoteEn)==='' && OnoteNum(OnoteZh)==='',
      'en 表头='+/WHY/.test(ObodyEn)+' · 说明残留数字=['+OnoteNum(OnoteZh)+OnoteNum(OnoteEn)+']');

    var Op2=document.getElementById('advWeek');
    openAdviceSheet(); Op2.value='1'; renderAdviceTable(); Op2.value='2'; renderAdviceTable();
    closeAllSheets();
    T('O16 只读引擎零写盘：算一遍 + 开面板 + 换周重渲染 + 收口，state 与两个分片逐字节不动',
      JSON.stringify(state)===OIN && localStorage.getItem(LS_PREFS)===OPREF && localStorage.getItem(LS_WORK)===OWORK,
      'state 不变='+(JSON.stringify(state)===OIN)+' prefs 不变='+(localStorage.getItem(LS_PREFS)===OPREF)
      +' work 不变='+(localStorage.getItem(LS_WORK)===OWORK));

    /* 出段还原：夹具周表、e1RM 账本、语言全部退回进段前 */
    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(OBAK).forEach(function(k){ state[k]=OBAK[k]; });
    state.lang=OLANG;
    if(OPREF===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS, OPREF);
    if(OWORK===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, OWORK);
    applyChrome(); renderAll();
    T('O17 出段还原：三周夹具没把共享对象改脏，也没落盘（文本快照对得上）',
      JSON.stringify(state)===OSNAP && localStorage.getItem(LS_PREFS)===OPREF
      && localStorage.getItem(LS_WORK)===OWORK && adviceWeekList().length>3,
      '长度 '+JSON.stringify(state).length+'/'+OSNAP.length+' · 周数 '+adviceWeekList().length);
    /* 节点⑯ D13 门面重排：只改名字与顺序，adv* 函数与契约判据一个字都没动。 */
    T('O18 自动调整门面：标题双语 + PREVIEW 徽标在位 + 设置行同步改名',
      (function(){var t=document.getElementById('advTitle'),b=document.getElementById('advBadge'),s=document.getElementById('setAdvT');
        return !!t&&!!b&&!!s && t.textContent.indexOf('自动调整')>=0 && b.textContent==='PREVIEW'
          && s.textContent.indexOf('自动调整')>=0;})()
      && String(openAdviceSheet).indexOf('下周建议')<0, '');
    T('O19 引擎面板重排生效：批量工具条落在 advBody 之后（旧序为之前）',
      (function(){var body=document.getElementById('advBody'),tools=document.querySelector('.adv-tools');
        if(!body||!tools) return false;
        return !!(body.compareDocumentPosition(tools)&4);})());

    /* ===== P. 写回：四档梯子、四道闸、审计与逐字节撤销 =====
       下周那几行故意做成不同形状：等值的、越界的、已到位的、下周本身是减载的 ——
       拒绝分支只有真造得出形状才测得到护栏，光测「能写」等于没测。 */
    SECT='P';
    var PBAK=clone(state), PSNAP=JSON.stringify(state);
    var PPREF=localStorage.getItem(LS_PREFS), PWORK=localStorage.getItem(LS_WORK);
    var PLANG=state.lang, PTIER=state.advAuto;
    var Par=PLAN_SCHEMA.autoreg||{}, Pday=dayIds()[0];
    var Pspec=[
      {mv:'P Up',   mode:'T1.Mod',  cat:'S.Main', load:120, reps:6, rpe:6.0, tr:7.0, ds:3, dst:120},
      {mv:'P Hard', mode:'T2.5x5',  cat:'B.Main', load:100, reps:3, rpe:9.6, tr:7.0, ds:5, dst:100},
      {mv:'P Jump', mode:'T1.Mod',  cat:'S.Main', load:120, reps:6, rpe:6.0, tr:7.0, ds:3, dst:90},
      {mv:'P At',   mode:'T1.Mod',  cat:'S.Main', load:120, reps:6, rpe:6.0, tr:7.0, ds:3, dst:125},
      {mv:'P DL',   mode:'T1.Mod',  cat:'S.Main', load:120, reps:6, rpe:6.0, tr:7.0, ds:3, dst:120, dstMode:'T1.DL'},
      {mv:'P Keep', mode:'T1.Mod',  cat:'S.Main', load:120, reps:6, rpe:7.0, tr:7.0, ds:3, dst:120}
    ];
    var Pmk=function(sp,i,side){ return {row:200+i, cat:sp.cat, mv:sp.mv,
      mode:(side==='dst'&&sp.dstMode)?sp.dstMode:sp.mode,
      load:(side==='dst'?sp.dst:sp.load), reps:sp.reps, rpe:sp.rpe,
      targetRpe:sp.tr, doneSets:sp.ds, done:sp.ds>0, notes:''}; };
    var Pwk=function(list){ var o={}; o[Pday]={title:'P FIX',exercises:list}; return o; };
    state.weeks={'1':Pwk([]),'2':Pwk(Pspec.map(function(sp,i){ return Pmk(sp,i,'src'); })),
                 '3':Pwk(Pspec.map(function(sp,i){ return Pmk(sp,i,'dst'); }))};
    state.advAudit=[];
    var Padv=function(){ return nextWeekAdvice(2); };
    var Pcand=function(){ return Padv().filter(function(r){ return r.verdict==='up'||r.verdict==='down'; }); };
    var Prow=function(mv){ return Padv().filter(function(r){ return r.mv===mv; })[0]||null; };
    var Pex=function(mv){ return (state.weeks['3'][Pday].exercises||[]).filter(function(x){ return x.mv===mv; })[0]||null; };
    var Pload=function(mv){ var e=Pex(mv); return e?+e.load:null; };
    var PALL=JSON.stringify(state.weeks), PW1=JSON.stringify(state.weeks['1']), PW2=JSON.stringify(state.weeks['2']);
    var Pin=function(mv){ return (state.weeks['3'][Pday].exercises||[]).map(function(x){ return x.mv; }).indexOf(mv); };
    var Pwhy=function(list){ return list.map(function(x){ return x.why; }).join('|'); };

    T('P1 默认档是「只建议」：档位名单只有一份、认不出的值退回默认、下拉就是名单本身',
      ADV_TIER_DEFAULT==='suggest' && PREF_KEYS.indexOf('advAuto')>=0 && WORK_KEYS.indexOf('advAudit')>=0
      && state.advAuto==='suggest' && advTier()==='suggest' && advCanWrite()===false
      && ADV_TIERS.join(',')==='off,suggest,confirm,auto'
      && String(advTier).indexOf('ADV_TIER_DEFAULT')>=0 && String(setAdvTier).indexOf('ADV_TIERS.indexOf')>=0
      && (setAdvTier('nope'), state.advAuto==='suggest')
      && (fillAdviceTier(), document.getElementById('advTier').options.length===ADV_TIERS.length),
      '默认='+advTier()+' · 名单='+ADV_TIERS.join('/'));

    var Pa=advApply(Pcand(),'batch');
    T('P2 只建议档：批量一条都不写，每笔都带「只建议」的拒绝理由，state 与分片逐字节不动',
      Pcand().length===5 && Pa.applied===0 && Pa.refused.length===5 && Pa.id===null
      && Pwhy(Pa.refused).indexOf('只建议')>=0 && advAuditOf().length===0
      && JSON.stringify(state.weeks)===PALL && localStorage.getItem(LS_WORK)===PWORK,
      '候选 '+Pcand().length+' · 写 '+Pa.applied+' · 拒 '+Pa.refused.length);

    state.advAuto='confirm';
    var Pb=advApply(Pcand(),'batch');
    T('P3 确认后应用：只落下该落的两笔，重量等于契约步进后的建议值（上=契约下限步进、硬顶=回退量）',
      Pb.applied===2 && Pb.noop===1 && Pb.refused.length===2 && Pb.tier==='confirm'
      && Pload('P Up')===120+(+Par.step_up_kg.lower) && Pload('P Hard')===100-(+Par.regress_kg)
      && Pload('P At')===125 && Pload('P DL')===120 && Pload('P Jump')===90,
      'Up→'+Pload('P Up')+' · Hard→'+Pload('P Hard')+' · 拒 '+Pb.refused.length+' · 到位 '+Pb.noop);

    T('P4 只改下周：W1 与 W2 逐字节不动，审计里 dstW 永远是 srcW+1，拒绝的两笔各说清是哪道闸',
      JSON.stringify(state.weeks['1'])===PW1 && JSON.stringify(state.weeks['2'])===PW2
      && advAuditOf()[0].dstW===advAuditOf()[0].srcW+1 && advAuditOf()[0].dstW===3
      && Pwhy(Pb.refused).indexOf('超单次上限')>=0 && Pwhy(Pb.refused).indexOf('减载')>=0,
      '周对 W'+advAuditOf()[0].srcW+'→W'+advAuditOf()[0].dstW+' · '+Pwhy(Pb.refused).slice(0,40));

    T('P5 审计字段齐：批次的周对 / 档位 / 种类 / 时间 + 每笔的日·行·动作·类别·模式·字段·前后值·依据，一个都不缺',
      (function(){ var b=advAuditOf()[0]; if(!b) return false;
        var bk=['id','ts','srcW','dstW','tier','kind','items','undone','undoneTs'];
        if(!bk.every(function(k){ return b[k]!==undefined; })) return false;
        if(b.items.length!==2 || b.tier!=='confirm' || b.kind!=='batch') return false;
        if(String(b.ts).length!==19 || b.ts.indexOf('-')<0 || b.ts.indexOf(':')<0) return false;
        return b.items.every(function(it){
          return ['day','seq','mv','cat','mode','field','before','after','delta','verdict','rule']
            .every(function(k){ return it[k]!==undefined && it[k]!==null && it[k]!==''; })
            && it.field==='load' && +it.after===+(+it.before+it.delta)
            && String(it.rule).length>0 && advRowAt(b.dstW,it.day,it.seq)!==null; });
      })(),
      (function(){ var b=advAuditOf()[0]; return b?('批 '+b.id+' · '+b.items.length+' 笔 · '+b.ts):'无批次'; })());

    var Pundo=advUndo(advAuditOf()[0].id);
    T('P6 撤销逐字节还原：下周退回写回前的整张表，批次标成已撤销并留撤销时间',
      Pundo.ok && Pundo.restored===2 && !Pundo.refused.length
      && JSON.stringify(state.weeks)===PALL && Pload('P Up')===120 && Pload('P Hard')===100
      && advAuditOf()[0].undone===true && String(advAuditOf()[0].undoneTs).length===19,
      '还原 '+Pundo.restored+' · 周表退回原文='+(JSON.stringify(state.weeks)===PALL));

    var Pc=advApply(Pcand(),'batch');
    var Pe1=Pex('P Up'); Pe1.load=111;
    var Pundo2=advUndo(Pc.id);
    T('P7 撤销不吃手改：那一格已被人改成别的重量就拒绝还原，其余照旧退回，批次不算撤销完成',
      Pc.applied===2 && Pundo2.restored===1 && Pundo2.refused.length===1
      && Pwhy(Pundo2.refused).indexOf('手改')>=0 && Pload('P Up')===111 && Pload('P Hard')===100
      && advAuditOf()[0].undone===false,
      'restored='+Pundo2.restored+' refused='+Pundo2.refused.length+' · P Up='+Pload('P Up'));
    Pe1.load=120;

    var PcapKg=Par.cap_kg, PcapPct=Par.cap_pct;
    PLAN_SCHEMA.autoreg.cap_kg=100; PLAN_SCHEMA.autoreg.cap_pct=1;
    var PjumpOpen=advGuard(Prow('P Jump'));
    PLAN_SCHEMA.autoreg.cap_kg=PcapKg; PLAN_SCHEMA.autoreg.cap_pct=PcapPct;
    var PjumpShut=advGuard(Prow('P Jump'));
    T('P8 幅度上限来自契约：把 cap_kg / cap_pct 抬开，越界行立刻可写；改回去又拒绝（护栏里没有手抄的数）',
      PjumpOpen.code==='apply' && PjumpShut.code==='refuse'
      && String(PjumpShut.why).indexOf('超单次上限')>=0
      && String(advGuard).indexOf('ar.cap_kg')>=0 && String(advGuard).indexOf('ar.cap_pct')>=0,
      '放开='+PjumpOpen.code+' · 收回='+PjumpShut.code+' · 上限='+PjumpShut.why.slice(0,30));

    var Psuf=Par.skip_mode_suffix;
    PLAN_SCHEMA.autoreg.skip_mode_suffix=['.Test'];
    var PdlOpen=advGuard(Prow('P DL'));
    PLAN_SCHEMA.autoreg.skip_mode_suffix=Psuf;
    var PdlShut=advGuard(Prow('P DL'));
    T('P9 减载 / 测试周拒绝写入，认的后缀同样只来自契约：从名单里去掉 .DL，那一行才允许落笔',
      PdlOpen.code==='apply' && PdlShut.code==='refuse'
      && String(PdlShut.why).indexOf('减载')>=0 && String(advHasSuffix).indexOf('skip_mode_suffix')>=0,
      '去 .DL='+PdlOpen.code+' · 复原='+PdlShut.code);

    var Pbefore10=Prow('P Up');
    Pe1=Pex('P Up'); var Pmv=Pe1.mv; Pe1.mv='P Renamed';
    var Pstale=advGuard(Pbefore10); Pe1.mv=Pmv;
    var Plist=state.weeks['3'][Pday].exercises, Pcut=Plist[0];
    Plist.splice(0,1); var Pgone=advGuard(Pbefore10); Plist.splice(0,0,Pcut);
    T('P10 建议那一帧之后处方又变了就不落笔：下周那行换了动作 / 被删掉，各自拒绝且不写任何格',
      Pstale.code==='refuse' && String(Pstale.why).indexOf('换成别的动作')>=0
      && Pgone.code==='refuse' && String(Pgone.why).indexOf('找不到')>=0
      && Pload('P Up')===120 && JSON.stringify(state.weeks)===PALL,
      '换名='+Pstale.code+' · 删行='+Pgone.code);

    state.advAuto='auto';
    var PautoSnap=JSON.stringify(state.weeks['3']);
    var PautoN=advAuditOf().length;
    openAdviceSheet();
    T('P11 自动档只预览不落笔：打开不写、审计不增、下周重量不动，批量仍需二次确认',
      Pload('P Up')===120 && advAuditOf().length===PautoN
      && JSON.stringify(state.weeks['3'])===PautoSnap && advTier()==='auto'
      && document.querySelectorAll('#advBody tbody tr').length>0,
      '审计='+advAuditOf().length+' · W3 快照不变='+(JSON.stringify(state.weeks['3'])===PautoSnap));

    state.advAuto='off'; openAdviceSheet();
    var PoffBody=String(document.getElementById('advBody').textContent||'');
    var PoffSnap=JSON.stringify(state.weeks);
    openAdviceSheet();
    T('P12 关闭档：不渲染表格也不写，批量按钮禁、撤销按钮留给已落的那批，说明行给出切换指引',
      document.querySelectorAll('#advBody tbody tr').length===0 && PoffBody.indexOf('关闭')>=0
      && document.getElementById('advApplyAll').disabled===true
      && advGuard(Prow('P Up')).code==='refuse' && advAuditOf().length>0
      && JSON.stringify(state.weeks)===PoffSnap
      && document.getElementById('advUndoLast').disabled===false,
      '关闭档说明='+PoffBody.slice(0,24));

    state.advAuto='confirm';
    Pex('P Up').load=120; Pex('P Hard').load=100;
    state.advAudit=[]; openAdviceSheet();
    var Pbtns=document.querySelectorAll('#advBody .adv-mini').length;
    var Pi13=Pin('P Up');
    advApplyRow(Pi13);
    T('P13 逐项应用只动点的那一行：只有过完四道闸的行才配按钮（夹具里两行），写回记成 kind=row 的单笔批次，别行原样',
      Pbtns===2 && Pi13>=0 && Pload('P Up')===120+(+Par.step_up_kg.lower)
      && Pload('P Hard')===100 && Pload('P At')===125
      && advAuditOf().length===1 && advAuditOf()[0].kind==='row' && advAuditOf()[0].items.length===1,
      '按钮 '+Pbtns+' 个 · 本批 '+advAuditOf()[0].items.length+' 笔 · Up='+Pload('P Up'));

    var PkeepSnap=JSON.stringify(state.weeks['3']);
    advApplyAll();
    T('P14 批量要两次点击：第一次只把按钮变成「再点一次确认」，一个字节都不写；第二次才落笔',
      String(document.getElementById('advApplyAll').textContent).indexOf('再点一次')>=0
      && advAuditOf().length===1 && JSON.stringify(state.weeks['3'])===PkeepSnap,
      '按钮文案='+String(document.getElementById('advApplyAll').textContent));
    advApplyAll();
    T('P15 第二次点击才真落笔：批次记成 kind=batch，写回量与逐行判定的建议值一致',
      advAuditOf().length===2 && advAuditOf()[0].kind==='batch'
      && Pload('P Hard')===100-(+Par.regress_kg) && Pload('P DL')===120 && Pload('P Jump')===90,
      '批次 '+advAuditOf().map(function(b){ return b.kind+':'+b.items.length; }).join(','));
    var PnoNew=advAuditOf().length;
    advApplyAll(); advApplyAll();
    T('P16 已到位的行不再写第二遍：连续点批量只新增「零笔」判定，审计不掺水',
      advAuditOf().length===PnoNew && Pload('P Up')===120+(+Par.step_up_kg.lower),
      '批次仍 '+advAuditOf().length+' 条 · 再点两次');

    T('P17 审计台账有界：条数不超过 ADV_AUDIT_MAX，裁剪走同一个常量',
      advAuditOf().length<=ADV_AUDIT_MAX && String(advApply).indexOf('ADV_AUDIT_MAX')>=0
      && String(advApply).indexOf('state.advAudit=')>=0,
      advAuditOf().length+'/'+ADV_AUDIT_MAX);

    state.lang='en'; applyChrome(); openAdviceSheet();
    var PstatEn=String(document.getElementById('advStat').textContent||'');
    var PaudEn=String(document.getElementById('advAudit').textContent||'');
    var PbtnEn=String(document.getElementById('advApplyAll').textContent||'');
    state.lang=PLANG; applyChrome(); openAdviceSheet();
    var PaudZh=String(document.getElementById('advAudit').textContent||'');
    T('P18 写回层的文案双语齐：档位名 / 汇总条 / 审计行 / 按钮在英文态零汉字，切回中文态全是汉字',
      PbtnEn.length>0 && !HAN.test(PbtnEn+PaudEn+PstatEn)
      && PaudEn.indexOf('LIVE')>=0 && PaudZh.indexOf('生效中')>=0 && HAN.test(PaudZh)
      && advTierName('off')==='关闭' && advTierName('auto')==='自动应用'
      && HAN.test(String(document.getElementById('advApplyAll').textContent)),
      'en 按钮='+PbtnEn+' · zh 审计='+PaudZh.slice(0,18));

    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(PBAK).forEach(function(k){ state[k]=PBAK[k]; });
    state.lang=PLANG; state.advAuto=PTIER;
    if(PPREF===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS, PPREF);
    if(PWORK===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, PWORK);
    applyChrome(); renderAll();
    T('P19 出段还原：写回夹具改过的处方、档位与审计全部退回进段前（文本快照对得上）',
      JSON.stringify(state)===PSNAP && localStorage.getItem(LS_PREFS)===PPREF
      && localStorage.getItem(LS_WORK)===PWORK && advTier()===PTIER && state.advAuto==='suggest'
      && PLAN_SCHEMA.autoreg.cap_kg===PcapKg && PLAN_SCHEMA.autoreg.cap_pct===PcapPct
      && PLAN_SCHEMA.autoreg.skip_mode_suffix.join(',')===Psuf.join(','),
      '长度 '+JSON.stringify(state).length+'/'+PSNAP.length+' · 档位 '+advTier());

    /* ===== Y. 记录流反馈与动效卫生：接线、焦点链、只碰非几何属性、减动兜底 ===== */
    SECT='Y';
    var Ycss=(function(){ var st=document.querySelector('style'); return String(st?st.textContent:''); })();
    var YsrcOf=function(n){ var f=window[n]; return String(typeof f==='function'?f:('(no fn '+n+')')); };
    /* 取选择器后面那一个声明块；字符类一律写全，不靠反斜杠（模板串会吞掉 \d \w \s） */
    var Yblock=function(sel){ var i=Ycss.indexOf(sel); if(i<0) return '';
      i=Ycss.indexOf('{',i); if(i<0) return ''; var j=Ycss.indexOf('}',i); return j<0?'':Ycss.slice(i+1,j); };
    var Ykf=function(nm){ var i=Ycss.indexOf('@keyframes '+nm); if(i<0) return '';
      var o=Ycss.indexOf('{',i),dep=0,k=o;
      while(k<Ycss.length){ var c=Ycss.charAt(k); if(c==='{')dep++; else if(c==='}'){dep--; if(dep===0)break;} k++; }
      return Ycss.slice(o+1,k); };
    var Ygeo=['width','height','margin','padding','top:','left:','right:','bottom:','scale('];
    var Yhit=function(s){ return Ygeo.filter(function(w){ return s.indexOf(w)>=0; }); };
    var Yrec=['toggleDone','bumpSet','quickLoad','saveEditor'];
    var YnoFlash=Yrec.filter(function(n){ return YsrcOf(n).indexOf('flashCard(')<0; });
    T('Y1 四个落账入口都把刚改的那张卡闪一下（反馈函数不留「有定义没人调」）',
      YnoFlash.length===0, YnoFlash.join(',')||'4/4 已接线');
    var Yping=Yrec.filter(function(n){ return YsrcOf(n).indexOf('pingDayComplete(')>=0; });
    T('Y2 「本日全部完成」只由勾满驱动：勾选/推满组数/编辑器保存会报，快速调重量不报',
      Yping.join(',')==='toggleDone,bumpSet,saveEditor',
      '报=[' + Yping.join(',') + '] quickLoad 里含 ping=' + (YsrcOf('quickLoad').indexOf('pingDayComplete')>=0));
    var YidsInSrc=(function(){ var s=YsrcOf('edChain'),out=[],i=0;
      while(true){ i=s.indexOf("'ed",i); if(i<0) break; var j=i+1;
        while(j<s.length && new RegExp('[A-Za-z0-9_]').test(s.charAt(j))) j++;
        if(s.charAt(j)!=="'") break; out.push(s.slice(i+1,j)); i=j; }
      return out; })();
    T('Y3 编辑器焦点链的字段顺序在源码里就是 载荷→次数→RPE→笔记，末位直接落 saveEditor',
      YidsInSrc.join(',')==='edLoad,edReps,edRpe,edNotes' && YsrcOf('edChain').indexOf('saveEditor(')>=0,
      YidsInSrc.join('→'));
    var Yhints=['edLoad','edReps','edRpe','edNotes'].map(function(id){
      var e=document.getElementById(id); return e?String(e.getAttribute('enterkeyhint')||''):''; });
    T('Y4 四个字段的软键盘动作键齐：三个 next、笔记 done',
      Yhints.join(',')==='next,next,next,done', Yhints.join('/'));
    var YnoPd='(未跑)',Yfocus='(未跑)';
    /* 输入框藏在收起的面板里时 focus() 是无效的（activeElement 根本不停在字段上），
       所以先把编辑器真的打开再验「非 Enter 不动作」。 */
    (function(){ var e=document.getElementById('edReps'); if(!e) return;
      openEditor(0);
      var k=null; try{ k=new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}); }catch(x){ return; }
      e.focus(); e.dispatchEvent(k);
      YnoPd=k.defaultPrevented?'prevented':'noPd';
      var a=document.activeElement; Yfocus=a?String(a.id||a.tagName):'';
      closeSheet('edSheet'); if(a&&a.blur)a.blur(); })();
    T('Y5 非 Enter 键不动作：不拦截默认行为、焦点仍停在原字段（链子不能被方向键误触）',
      YnoPd==='noPd' && Yfocus==='edReps', YnoPd+' / 焦点=' + Yfocus);
    var Yclose=YsrcOf('closeSheet');
    T('Y6 关面板时交还焦点：读 activeElement、确认焦点在面板内才 blur（不留挂焦点的隐藏输入）',
      Yclose.indexOf('activeElement')>=0 && Yclose.indexOf('.blur(')>=0 && Yclose.indexOf('contains(')>=0,
      '三点命中 / 长度 ' + Yclose.length);
    var Yjust=Yblock('.ex.just');
    T('Y7 卡闪规则只挂一条动画、不写几何属性（uiv 量的是矩形，动效改矩形就是自毁判据）',
      Yjust.indexOf('card-just')>=0 && Yjust.indexOf('animation')>=0 && Yhit(Yjust).length===0,
      Yhit(Yjust).join('/') || ('规则体 ' + Yjust.trim().slice(0,48)));
    var YkfNames=['scrim-in','panel-in','drawer-in','card-just'];
    var YkfBody=YkfNames.map(function(n){ return Ykf(n); });
    var YkfBad=[];
    YkfBody.forEach(function(b,i){ if(!b){ YkfBad.push(YkfNames[i]+'(缺)'); return; }
      var bad=Yhit(b); if(bad.length) YkfBad.push(YkfNames[i]+'含'+bad.join('/')); });
    var YkfAll=YkfBody.join('');
    T('Y8 四条 keyframes 都在，且只碰 opacity / transform / box-shadow（入场与闪烁都不改布局）',
      YkfBad.length===0 && YkfAll.indexOf('opacity')>=0 && YkfAll.indexOf('transform')>=0
      && YkfAll.indexOf('box-shadow')>=0, YkfBad.join(' | ')||'4 条 · 无几何属性');
    var YrmBlock=Yblock('@media (prefers-reduced-motion');
    var YrmCount=Ycss.split('@media (prefers-reduced-motion').length-1;
    T('Y9 减动偏好兜底只写一处，且同时压掉 animation-duration 与 transition-duration',
      YrmCount===1 && YrmBlock.indexOf('animation-duration')>=0
      && YrmBlock.indexOf('transition-duration')>=0 && YrmBlock.indexOf('!important')>=0,
      YrmCount + ' 处 · 块长 ' + YrmBlock.length);
    var Yempty=null,YemptyToast=null,Yflag=null;
    (function(){ var Yday=day(); if(!Yday) return;
      var Yex=Yday.exercises||[]; var t=document.getElementById('toast');
      t.classList.remove('on'); t.textContent='';
      Yday.exercises=[];
      Yempty=pingDayComplete(); YemptyToast=t.classList.contains('on'); Yflag=_dayPinged;
      Yday.exercises=Yex; })();
    T('Y10 空账本不许报「完成」：当天没有动作时 pingDayComplete 返回 false 且不弹 toast',
      Yempty===false && YemptyToast===false && Yflag===false,
      '返回=' + Yempty + ' toast=' + YemptyToast + ' 闸门=' + Yflag);

    /* ===== F15. ✅ 满组开关：勾选即满组、取消归零、AMRAP 同口径，且绝不改写 reps/RPE/备注 ===== */
    SECT='F15';
    var F15r=(function(){
      var d=day();
      if(!d||!d.exercises||!d.exercises.length) return {skip:'空账本，跳过'};
      var ex=d.exercises[0];
      /* save() 是 120ms 防抖，同步断言块里根本不落盘 ⇒ 只备内存：本条动作会被 toggleDone 碰的字段
         + e1RM 账本 + 防抖句柄 + 完成闸门；跑完 stopTimer 收尾、逐字段还原、重渲，主屏与账本回到进段前。 */
      var bk={done:ex.done,doneSets:ex.doneSets,reps:ex.reps,rpe:ex.rpe,targetRpe:ex.targetRpe,notes:ex.notes,mode:ex.mode};
      var e1bk=state.e1rmLog?JSON.parse(JSON.stringify(state.e1rmLog)):null;
      var pingBk=_dayPinged;
      if(_saveTimer){ clearTimeout(_saveTimer); _saveTimer=null; }
      var total=setsOf(ex.mode);
      ex.done=false; ex.doneSets=0;                 /* 归零起点，好验「勾上=满组」 */
      toggleDone(0);                                 /* 勾上 */
      var on={done:ex.done,doneSets:ex.doneSets};
      var onKeep=(ex.reps===bk.reps&&ex.rpe===bk.rpe&&ex.targetRpe===bk.targetRpe&&ex.notes===bk.notes);
      toggleDone(0);                                 /* 取消 */
      var off={done:ex.done,doneSets:ex.doneSets};
      var offKeep=(ex.reps===bk.reps&&ex.rpe===bk.rpe&&ex.targetRpe===bk.targetRpe&&ex.notes===bk.notes);
      stopTimer();
      ex.done=bk.done; ex.doneSets=bk.doneSets; ex.reps=bk.reps; ex.rpe=bk.rpe;
      ex.targetRpe=bk.targetRpe; ex.notes=bk.notes; ex.mode=bk.mode;
      if(e1bk===null) delete state.e1rmLog; else state.e1rmLog=e1bk;
      _dayPinged=pingBk;
      if(_saveTimer){ clearTimeout(_saveTimer); _saveTimer=null; }
      try{ renderExercises(); renderTelemetry(); }catch(e){}
      return {total:total,on:on,off:off,onKeep:onKeep,offKeep:offKeep};
    })();
    T('F15a 点 ✅ 直接满组、取消归零（0→total→0，不保留半截组数）',
      !F15r.skip && F15r.total>0 && F15r.on.done===true && F15r.on.doneSets===F15r.total
      && F15r.off.done===false && F15r.off.doneSets===0,
      F15r.skip||('total='+F15r.total+' 勾上='+F15r.on.doneSets+'(done='+F15r.on.done+') 取消='+F15r.off.doneSets+'(done='+F15r.off.done+')'));
    T('F15b 勾选/取消都不改写 reps / RPE / 目标RPE / 备注（执行实况只归用户手填）',
      !F15r.skip && F15r.onKeep===true && F15r.offKeep===true,
      F15r.skip||('勾上后四字段原样='+F15r.onKeep+' 取消后原样='+F15r.offKeep));
    var F15src=YsrcOf('toggleDone');
    T('F15c 满组数取自 setsOf(e.mode)：与卡片 SET N/total、bumpSet 同源，AMRAP 也走这一条，无写死组数',
      F15src.indexOf('setsOf(e.mode)')>=0 && F15src.indexOf('e.doneSets=e.done?total:0')>=0,
      'setsOf命中='+(F15src.indexOf('setsOf(e.mode)')>=0)+' 满组赋值命中='+(F15src.indexOf('e.doneSets=e.done?total:0')>=0));

    /* ===== T. 环境配置 hub：配片库存 / 六类本地计算器 / 地点网格 ===== */
    SECT='T';
    var Tbak=clone(state), Tsnap=JSON.stringify(state);
    var Tpr0=localStorage.getItem(LS_PREFS), Twk0=localStorage.getItem(LS_WORK);
    T('T1 计算器六类名单齐、键不重、每个字段都在字段表里',
      LC_TYPES.length===6 && (function(){ var seen={}, bad=[];
        LC_TYPES.forEach(function(t){ if(seen[t.k]) bad.push('重复 '+t.k); seen[t.k]=1;
          t.f.forEach(function(f){ if(!LC_FIELDS[f]) bad.push(t.k+'.'+f+' 无字段定义'); }); });
        return bad.length===0 && ['stack','loaded','bw','bwadd','bwassist','manual']
          .every(function(k){ return !!seen[k]; }); })(),
      LC_TYPES.map(function(t){ return t.k; }).join(','));
    openEditor(0);
    T('T2 每开一行计算器都回到默认：类型是插片、逐档输入只有一排（参数从不跨行留着）',
      _lcType==='stack' && Array.isArray(_lcVal.pins) && _lcVal.pins.length===1,
      _lcType+' / pins=' + JSON.stringify(_lcVal.pins));
    /* 公式逐类验：值故意给成字符串，顺带证明输入解析走的是同一条路 */
    var lcSet=function(k,v){ _lcType=k; _lcVal=v; };
    lcSet('stack',{stacks:'2',plateKg:'2.5',pins:['5','7'],base:'10'});
    T('T3 插片 = 基数 + Σ(每栈插销档 × 每片重量)', lcTotal()===40, lcTotal()+'（10 + (5+7)×2.5）');
    lcSet('loaded',{arms:'3',armKg:['10','5','2.5'],base:'20'});
    T('T4 挂片 = 基数 + Σ各杆片重', lcTotal()===37.5, lcTotal()+'（20 + 10+5+2.5）');
    lcSet('bw',{bw:'80',coef:'0.7'});
    T('T5 自重 = 体重 × 杠杆系数', lcTotal()===56, lcTotal());
    lcSet('bwadd',{bw:'80',coef:'0.7',add:'10'});
    T('T6 自重加重 = 体重 × 系数 + 加重', lcTotal()===66, lcTotal());
    lcSet('bwassist',{bw:'80',coef:'0.7',assist:'30'});
    var Tassist=lcTotal();
    lcSet('bwassist',{bw:'80',coef:'0.7',assist:'99'});
    T('T7 自重辅助 = max(0, 体重 × 系数 − 辅助)：卸过头夹到 0 不出负数',
      Tassist===26 && lcTotal()===0, Tassist+' / 超额时 ' + lcTotal());
    lcSet('manual',{manual:'47.5',memo:'只写备注不写重量'});
    T('T8 特殊器械 = 手动总重，备注不参与计算', lcTotal()===47.5, lcTotal());
    var Tpre=JSON.stringify(state), TprA=localStorage.getItem(LS_PREFS), TwkA=localStorage.getItem(LS_WORK);
    fillLoadFromCalc();
    T('T9 点「填入载荷」只动 #edLoad 那一格：账本与两处分片一字未改，不保存就不落账',
      String(document.getElementById('edLoad').value)==='47.5' && JSON.stringify(state)===Tpre
      && localStorage.getItem(LS_PREFS)===TprA && localStorage.getItem(LS_WORK)===TwkA,
      'edLoad=' + document.getElementById('edLoad').value
      + ' 账本变动=' + (JSON.stringify(state)!==Tpre)
      + ' 分片变动=' + (localStorage.getItem(LS_PREFS)!==TprA || localStorage.getItem(LS_WORK)!==TwkA));
    /* ===== F13 + F14（器械 UI 止血）：横杆只属于杠铃 / 「低于空杆重量」不外泄 / 计算器按 kind 折叠 =====
       编辑器此刻是开着的（openEditor(0) 在 T2），setGearKind 直接驱动当前这条动作的器械口径；
       改到的 gear/load 由段末 state=Tbak 兜底还原，防抖句柄在本块尾清掉，不留悬空落盘。 */
    var pvBar=document.getElementById('edPlateBar');
    var lcalcBox=document.querySelector('.lcalc');
    var sleeveByKind={}, noteLeak=[];
    ['barbell','plate','stack','dumbbell','bw','special'].forEach(function(k){
      setGearKind(k);
      sleeveByKind[k]=pvBar.classList.contains('no-sleeve');
      var gvk=gearViewOf(day().exercises[editIdx]);
      var wjoin=(gvk.warnings||[]).join('|')+'|'+document.getElementById('edPlateTxt').textContent;
      if(k!=='barbell' && (wjoin.indexOf('低于空杆')>=0 || wjoin.indexOf('Below bar weight')>=0)) noteLeak.push(k);
    });
    T('T9a F13 横向杠铃杆只属于杠铃：杠铃不带 no-sleeve，其余五类全带（哑铃/自重不再画出那根灰杆）',
      sleeveByKind.barbell===false
      && ['plate','stack','dumbbell','bw','special'].every(function(k){ return sleeveByKind[k]===true; }),
      JSON.stringify(sleeveByKind));
    T('T9b F13 「低于空杆重量」只可能出现在杠铃：五类非杠铃的 warnings 与载荷文案都不含它',
      noteLeak.length===0, noteLeak.join(',')||'无泄漏');
    T('T9c F13 杠铃空载仍如实报「低于空杆重量」（这条警告没被一刀切删掉，只是不再串到非杠铃）',
      platesPerSide(10,false).note.indexOf('低于空杆重量')>=0, platesPerSide(10,false).note);
    var T9fold={};
    ['barbell','plate','stack','dumbbell','bw','special'].forEach(function(k){
      setGearKind(k); T9fold[k]=lcalcBox.classList.contains('collapsed');
    });
    T('T9d F14 计算器默认收起，且不随器械 kind 自动展开（六类都折叠，唯一出处是用户偏好）',
      ['barbell','plate','stack','dumbbell','bw','special'].every(function(k){ return T9fold[k]===true; })
      && state.lcOpen!==true,
      ['barbell','plate','stack','dumbbell','bw','special'].map(function(k){ return k+':'+(T9fold[k]?'折叠':'展开'); }).join(' '));
    setGearKind('stack');
    var T9eBody=getComputedStyle(document.getElementById('lcBody')).display;
    T('T9e F14 切到插片仍保持收起（折叠钮 aria-expanded=false + 输入区 display:none）',
      lcalcBox.classList.contains('collapsed')
      && document.getElementById('lcTogBtn').getAttribute('aria-expanded')==='false'
      && T9eBody==='none',
      'collapsed='+lcalcBox.classList.contains('collapsed')+' aria='+document.getElementById('lcTogBtn').getAttribute('aria-expanded')+' lcBody='+T9eBody);
    lcToggle();
    var T9fExpand=prefsOf().lcOpen;
    T('T9f F14 手动展开落地并把状态写进 prefs（aria-expanded=true + 输入区可见 + lcOpen=true）',
      !lcalcBox.classList.contains('collapsed')
      && document.getElementById('lcTogBtn').getAttribute('aria-expanded')==='true'
      && getComputedStyle(document.getElementById('lcBody')).display!=='none'
      && state.lcOpen===true && T9fExpand===true,
      'collapsed='+lcalcBox.classList.contains('collapsed')+' prefs.lcOpen='+T9fExpand);
    lcToggle();
    var T9gFolded=lcalcBox.classList.contains('collapsed'), T9gSt=state.lcOpen, T9gPr=prefsOf().lcOpen;
    lcToggle();
    T('T9g F14 折叠钮成对可逆：展开→收起写回 false，再点一下回到展开（状态与 prefs 同步翻）',
      T9gFolded===true && T9gSt===false && T9gPr===false
      && !lcalcBox.classList.contains('collapsed') && prefsOf().lcOpen===true
      && document.getElementById('lcTogBtn').getAttribute('aria-expanded')==='true',
      '首点折叠='+T9gFolded+' 折叠态='+T9gSt+' 再点展开='+(!lcalcBox.classList.contains('collapsed')));
    setGearKind('barbell');   /* 归回杠铃口径，剩下交段末 state=Tbak 兜底 */
    if(_saveTimer){ clearTimeout(_saveTimer); _saveTimer=null; }
    closeSheet('edSheet');
    /* 库存：95kg 在 20kg 杆上是单侧 37.5 —— 全套配得平，只留 15/10/5 就配不平，必须如实报余量。
       库存归场地（v7）：夹具改的是「当前场地的那份 inventory」，不再是全局 plateCfg。 */
    var TpkFull=platesPerSide(95,false);
    venueInv().plates={15:null,10:null,5:null};
    var TpkCut=platesPerSide(95,false);
    T('T10 配片库存生效：同一重量换了片组，且余量与「最小片」提示跟着在场的片走',
      TpkFull.exact===true && TpkFull.plates.map(function(p){return p.kg;}).join(',')==='25,10,2.5'
      && TpkCut.plates.map(function(p){return p.kg;}).join(',')==='15,15,5'
      && TpkCut.remainder===2.5 && TpkCut.exact===false
      && TpkCut.note.indexOf('2.5kg 无法配平')>=0 && TpkCut.note.indexOf('最小片 5kg')>=0,
      '全套=' + TpkFull.plates.map(function(p){return p.kg;}).join(',')
      + ' / 只留 15·10·5=' + TpkCut.plates.map(function(p){return p.kg;}).join(',')
      + ' 余 ' + TpkCut.remainder + ' [' + TpkCut.note + ']');
    venueInv().plates={};
    T('T11 一件不留是合法状态（只剩杆），不是「回到全套」',
      platesPerSide(95,false).plates.length===0 && plateStock().length===0
      && Object.keys(venueInv().plates).length===0, plateStock().length);
    state.venues=DEFAULT_VENUES(); state.activeVenueId=GEAR_SCHEMA.venues.id_legacy;
    togglePlateKg(25);
    var Toff=plateStock(), ToffKeys=Object.keys(venueInv().plates).length;
    togglePlateKg(25);
    var Ton=plateStock();
    T('T12 库存开关成对可逆：点掉 25kg 少一片、再点回来回全套，键数跟着增减（不在场就没有那个键）',
      Toff.length===PLATE_KGS.length-1 && Toff.indexOf(25)<0 && ToffKeys===PLATE_KGS.length-1
      && Ton.length===PLATE_KGS.length && Object.keys(venueInv().plates).length===PLATE_KGS.length,
      Toff.length + ' → ' + Ton.length + '/' + PLATE_KGS.length + ' keys=' + ToffKeys);
    /* 地点：写在账本里的一格，但交换文件与契约都没有这一列 */
    var TlocW=+state.week, TlocD=dayIds()[0];
    var Tok=setDayLoc(TlocW,TlocD,'铁馆 A 区');
    T('T13 地点落在 weeks[w][d].loc 上：写进去读得回来，主表那行也亮起来',
      Tok===true && dayLoc(TlocW,TlocD)==='铁馆 A 区'
      && document.getElementById('locLine').classList.contains('on')
      && txt('locLine').indexOf('铁馆 A 区')>=0, txt('locLine'));
    var Tcsv=exportUnifiedCsv();
    var Tx=(function(){ try{ return JSON.stringify(xStateToPlanDict(state)); }catch(e){ return 'THREW '+e.message; } })();
    T('T14 地点不随计划导出：CSV 26 列表头一字未动、六表工作簿里搜不到这个地名',
      CSV_COLS.length===26 && Tcsv.split('\\r\\n')[0].indexOf('loc')<0
      && Tcsv.indexOf('铁馆 A 区')<0 && Tx.indexOf('铁馆 A 区')<0,
      '列数=' + CSV_COLS.length + ' CSV 命中=' + (Tcsv.indexOf('铁馆 A 区')>=0) + ' 工作簿命中=' + (Tx.indexOf('铁馆 A 区')>=0));
    setDayLoc(TlocW,TlocD,'   ');
    T('T15 清空地点是把键删掉，不是留一个空字符串（账本不长胖）',
      dayLoc(TlocW,TlocD)==='' && !xHas(state.weeks[String(TlocW)][TlocD],'loc'),
      JSON.stringify(state.weeks[String(TlocW)][TlocD].loc));
    setDayLoc(TlocW,TlocD,'0123456789012345678901234567890123456789');
    T('T16 地名按 LOC_MAX_LEN 截断：输入框 maxlength 之外还有一道，账本里不会塞进超长串',
      dayLoc(TlocW,TlocD).length===LOC_MAX_LEN, dayLoc(TlocW,TlocD).length);
    setDayLoc(TlocW,TlocD,'');
    openEnvSheet();
    var TdayN=dayIds().length;
    var Tw0=+document.getElementById('envLocWeek').value;
    var Tcells=document.querySelectorAll('#envLocGrid .loc-cell').length;
    var Tw1=activeWeekNums().filter(function(w){ return w!==Tw0; })[0];
    setDayLoc(Tw1,TlocD,'另一周的地名');
    document.getElementById('envLocWeek').value=String(Tw1);
    renderEnvLoc();
    var Tattr=Array.prototype.map.call(document.querySelectorAll('#envLocGrid .loc-in'),function(i){ return i.getAttribute('data-locw'); });
    var Tval=Array.prototype.map.call(document.querySelectorAll('#envLocGrid .loc-in'),function(i){ return i.value; });
    T('T17 地点网格按周切换：列数就是训练日数，切周后每格认的周号跟着换、填进去的地名读得回来',
      Tcells===TdayN && document.querySelectorAll('#envLocGrid .loc-cell').length===TdayN
      && Tattr.length===TdayN && Tattr.every(function(a){ return a===String(Tw1); })
      && Tval[0]==='另一周的地名'
      && document.querySelectorAll('#envLocWeek option').length===activeWeekNums().length,
      Tcells + ' 格 / ' + TdayN + ' 日 / 切到 W' + Tw1 + ' 后格上周号=' + Tattr.join(',') + ' 首格值=' + Tval[0]);
    var Tchips=document.querySelectorAll('#envPlates .ps-chip').length;
    T('T18 库存芯片一个片重一枚，且与片表同源（不手抄 11）',
      Tchips===PLATES.length && Tchips===PLATE_KGS.length, Tchips + '/' + PLATES.length);
    closeSheet('envSheet');
    setLang('en'); applyChrome(); openEnvSheet(); openEditor(0);
    var TenIds=['lcTitleLbl','lcFillBtn','lcDisc','setPlateT','setPlateS','setLocT','setLocS','envNote'];
    var TenBad=TenIds.filter(function(id){ var v=txt(id); return !v || HAN.test(v); });
    /* 动态那批（六类名称 + 当前类型的字段名）判的是渲染出来的 DOM，不是名单里的中文项 */
    var TenDyn=Array.prototype.map.call(document.querySelectorAll('#lcType option'),function(o){ return o.textContent; })
      .concat(Array.prototype.map.call(document.querySelectorAll('#lcBody .lc-fld label'),function(l){ return l.textContent; }));
    var TenHan=TenDyn.filter(function(s){ return HAN.test(s); });
    T('T19 双语：环境 hub 静态标签 + 计算器渲染出的六类名与字段名，在英文态零汉字且非空',
      TenBad.length===0 && TenHan.length===0 && TenDyn.length===6+4
      && TenDyn.every(function(s){ return String(s).trim().length>0; }),
      '静态缺/脏=' + (TenBad.join(',')||'无') + ' 动态条数=' + TenDyn.length + ' 含汉字=' + (TenHan.join(',')||'无'));
    closeSheet('edSheet'); closeSheet('envSheet'); setLang('zh'); applyChrome();
    state=Tbak;
    if(Tpr0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,Tpr0);
    if(Twk0===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK,Twk0);
    T('T20 出段还原：本段改的库存 / 地点 / 载荷都没留下痕迹，两处分片回到进段前',
      JSON.stringify(state)===Tsnap && localStorage.getItem(LS_PREFS)===Tpr0 && localStorage.getItem(LS_WORK)===Twk0,
      'state 还原=' + (JSON.stringify(state)===Tsnap));

    /* ===== Q. 阈值回测校准（v0.27） =====
       契约里那九个数字第一次有了「拿自己的账判自己」的工具，所以这一段判的全是
       工具自身的口径与纪律，不是「命中率好不好看」——数字好看与否要由用户的账说话。
         Q1 参数字典按契约现读（不手抄键名）
         Q2 候选网格不越各自的物理边界
         Q3 覆盖只在 fn 期间生效，fn 抛错也要还原
         Q4 答案卷钉死在契约默认：扫到的阈值能改判「建议」，不能改判「答案」
         Q5 样本不够只说「太薄」，绝不给百分比
         Q6/Q7 合成账本跑得出数，且同输入必同输出
         Q8 整条链只读：state、两分片、两个导出面逐字节不动
         Q9/Q10 有账画表、无账画空态，两条分支都得渲染得出来
         Q11 双语不漏汉字进英文态
       夹具只在段内挂着，出段整份还原（和 O / T 段一样的规矩）。 */
    SECT='CA';
    var QBAK=clone(state), QSNAP=JSON.stringify(state);
    var Qpr0=localStorage.getItem(LS_PREFS), Qwk0=localStorage.getItem(LS_WORK);
    var Qar=PLAN_SCHEMA.autoreg||{};
    var Qday=dayIds()[0];
    /* 参数字典的唯一出处应当是契约：这里独立地再数一遍，两边对不上就是有人手抄了 */
    var Qwant=[];
    Object.keys(Qar).forEach(function(k){
      var v=Qar[k];
      if(typeof v==='number') Qwant.push(k);
      else if(v&&typeof v==='object'&&!Array.isArray(v)){
        Object.keys(v).forEach(function(k2){ if(typeof v[k2]==='number') Qwant.push(k+'.'+k2); });
      }
    });
    var Qgot=calibParamKeys();
    var Qgk=Qgot.map(function(p){ return p.key; });
    var Qmiss=Qwant.filter(function(k){ return Qgk.indexOf(k)<0; });
    var Qextra=Qgk.filter(function(k){ return Qwant.indexOf(k)<0; });
    var QwrongVal=Qgot.filter(function(p){
      var key=String(p.key), i=key.indexOf('.');
      var src=i<0?Qar[key]:(Qar[key.slice(0,i)]||{})[key.slice(i+1)];
      return +src!==p.val;
    }).map(function(p){ return p.key+'='+p.val; });
    /* calibOverride 是「只换一个键、其余原样」的构造器：叶子名自己带点的
       clean_reps.T3.Mod 是最容易写错的一个（整串 split('.') 会造出 'T3' 这种假键）。
       所以每个键都真换一次，读回来、并确认键的形状没被改、契约本体没被就地写脏。 */
    var QarSrc=JSON.stringify(PLAN_SCHEMA.autoreg);
    var Qrt=[], Qmutate=[];
    Qgot.forEach(function(p){
      var key=String(p.key), i=key.indexOf('.');
      var head=i<0?null:key.slice(0,i), tail=i<0?key:key.slice(i+1);
      var nv=Math.round((+p.val+0.25)*1000)/1000;
      var ov=calibOverride(key,nv);
      var leaf=i<0?ov[key]:((ov[head]||{})[tail]);
      if(+leaf!==nv) Qrt.push(key+' 写回读到 '+(leaf===undefined?'(键不见了)':leaf));
      if(JSON.stringify(Object.keys(ov).sort())!==JSON.stringify(Object.keys(Qar).sort()))
        Qmutate.push(key+' 把顶层键形状改了');
      if(i>=0 && JSON.stringify(Object.keys(ov[head]||{}).sort())
        !==JSON.stringify(Object.keys(Qar[head]||{}).sort()))
        Qmutate.push(key+' 在 '+head+' 里造了新键');
    });
    T('CA1 参数字典按契约 autoreg 现读（'+Qwant.length+' 个数字叶）：不漏、不多抄、值不跑偏，且每个键（含 clean_reps.T3.Mod 这种带点的）单独覆盖都能原样写回、不碰兄弟、不动契约本体',
      Qwant.length>0 && Qmiss.length===0 && Qextra.length===0 && QwrongVal.length===0
      && Qgk.length===Qwant.length && Qrt.length===0 && Qmutate.length===0
      && JSON.stringify(PLAN_SCHEMA.autoreg)===QarSrc,
      '契约 '+Qwant.length+' / 字典 '+Qgk.length+' 漏='+(Qmiss.join(',')||'无')
      +' 多='+(Qextra.join(',')||'无')+' 值偏='+(QwrongVal.join(',')||'无')
      +' 写回='+(Qrt.join(',')||'全通')+' 误伤='+(Qmutate.join(',')||'无')
      +' 契约被改='+(JSON.stringify(PLAN_SCHEMA.autoreg)!==QarSrc));

    var QcandBad=[], QcandN=0;
    Qgot.forEach(function(p){
      var cs=calibCand(p.key,p.val); QcandN+=cs.length;
      cs.forEach(function(v){
        if(!(v>0)) QcandBad.push(p.key+'='+v+' 非正');
        if(v===p.val) QcandBad.push(p.key+'='+v+' 与默认同');
        if(cs.indexOf(v)!==cs.lastIndexOf(v)) QcandBad.push(p.key+'='+v+' 重复');
        if(/completion|_pct$/.test(p.key)&&v>1) QcandBad.push(p.key+'='+v+' 比例过 100%');
        if(/completion|_pct$/.test(p.key)&&Math.abs(v*100-Math.round(v*100))>0.000000001)
          QcandBad.push(p.key+'='+v+' 不是整百分位');
        if(/rpe/.test(p.key)&&v>10) QcandBad.push(p.key+'='+v+' RPE 过 10');
        if(/kg$/.test(p.key)&&Math.abs(v/0.25-Math.round(v/0.25))>0.000000001)
          QcandBad.push(p.key+'='+v+' 装不出这一档');
      });
    });
    T('CA2 候选网格全落在各自的物理边界内（比例≤1 / RPE≤10 / 重量按 0.25 装配档），不重复不取默认（共 '+QcandN+' 个候选）',
      QcandN>0 && QcandBad.length===0, QcandBad.join(' ; ')||('全部 '+QcandN+' 个合法'));

    var Qgap=+Qar.rpe_gap;
    var Qin=withAutoreg({rpe_gap:Qgap+3},function(){ return autoregOf().rpe_gap; });
    var Qout=autoregOf().rpe_gap;
    var Qthrew='', Qafter=Qgap+1;
    try{ withAutoreg({rpe_gap:Qgap+5},function(){ throw new Error('qthrow'); }); }
    catch(e){ Qthrew=String(e&&e.message); Qafter=autoregOf().rpe_gap; }
    T('CA3 阈值覆盖只在 fn 动态期间生效：进去换了、出来还原、fn 抛错也照样还原（finally 不是装饰）',
      Qin===Qgap+3 && Qout===Qgap && Qthrew==='qthrow' && Qafter===Qgap,
      '期间='+Qin+' 段后='+Qout+' 抛错后='+Qafter+'（默认 '+Qgap+'）');

    /* 夹具不新造周表：只在内置模板的第 2、3 周上「把账记了」。
       周数、动作、处方全是真的，唯一假的是完成率与实 RPE；相邻两周都留下记录，
       才凑得出「这一行当时会怎么建议 + 下一周实际练成什么样」这一对。 */
    var Qrec=function(wn){
      var wk=state.weeks[String(wn)], n=0;
      if(!wk) return 0;
      Object.keys(wk).forEach(function(d){
        ((wk[d]||{}).exercises||[]).forEach(function(e,i){
          var pr=prescriptionOf(e), sets=(+pr.sets||1), reps=(+pr.reps||1);
          var tr=(+e.targetRpe||7);
          e.doneSets=(i%3===2)?Math.max(1,Math.floor(sets/2)):sets;
          e.done=e.doneSets>=sets;
          e.reps=(i%3===0)?reps:Math.max(1,reps-1);
          e.targetRpe=tr;
          e.rpe=(i%4===0)?Math.max(1,tr-1):((i%4===1)?tr:((i%4===2)?tr+0.8:+Qar.rpe_hard_stop+0.3));
          n++;
        });
      });
      return n;
    };
    var Qrows2=Qrec(2), Qrows3=Qrec(3);
    var QFIX=JSON.stringify(state);
    var Qpairs=adviceSrcWeekOptions();

    var Qbase=calibRun(null);
    var Qsum=Qbase.up+Qbase.keep+Qbase.down+Qbase.skip;
    var Qkinds=[Qbase.up>0,Qbase.keep>0,Qbase.down>0].filter(function(x){ return x; }).length;
    T('CA6 内置模板记满两周就能跑出一版可评分的基线（'+Qbase.graded+' 行 ≥ 门槛 '+CALIB_MIN_N+' 行）：分类账平、命中率在 0–100 之内、判词不止一种',
      Qpairs.length>=1 && Qrows2>0 && Qrows3>0 && Qbase.n>0 && Qsum===Qbase.n
      && Qbase.graded+Qbase.na===Qbase.n-Qbase.skip
      && Qbase.n>=Qrows2 && Qbase.graded>=CALIB_MIN_N
      && Qbase.rate>=0 && Qbase.rate<=100 && Qkinds>=2,
      '对 '+Qpairs.length+' / 行 '+Qbase.n+'（W2 共 '+Qrows2+'）/ 评分 '+Qbase.graded+' / 未评 '+Qbase.na
      +' / 上 '+Qbase.up+' 保 '+Qbase.keep+' 下 '+Qbase.down+' 跳 '+Qbase.skip
      +' / 命中 '+Qbase.hit+' = '+Qbase.rate+'%');

    var Qsw=calibSweep();
    var Qs1=JSON.stringify(Qsw), Qs2=JSON.stringify(calibSweep());
    /* 打平不是改进：结论列只准报真的赢过默认值的候选，否则「试 X：+0 个百分点」
       就是把噪声包装成建议。thin 也必须与「每个候选都不够样本」严格等价。 */
    var Qtie=Qsw.rows.filter(function(r){ return r.best&&!(r.best.d>0); })
      .map(function(r){ return r.key+' 报了 d='+r.best.d; });
    var QthinBad=Qsw.rows.filter(function(r){
      return r.thin!==r.cands.every(function(c){ return c.n<CALIB_MIN_N; });
    }).map(function(r){ return r.key; });
    T('CA7 同一本账连扫两遍逐字节相同（扫描里不许掺随机数/时间戳/迭代顺序），且结论只报真的赢过默认值的候选、thin 标记与候选样本数自洽',
      Qs1===Qs2 && Qs1.length>200 && Qtie.length===0 && QthinBad.length===0,
      '两次长度 '+Qs1.length+'/'+Qs2.length+' 相同='+(Qs1===Qs2)
      +' 打平当改进='+(Qtie.join(',')||'无')+' thin 不自洽='+(QthinBad.join(',')||'无'));

    /* 把硬顶压到 0、缺口抹成 0：所有记了 RPE 的行都会被判「超顶→下调」，建议分布必然剧变。
       其中 rpe_gap 是判卷里 adviceStruggle() 会读的键——如果判卷忘了套 withAutoreg(null)，
       它就会跟着这套假阈值走，勉强/干净的计数当场变形；崩/干净按契约硬顶判，不该动。
       两半合起来（分布剧变 + 答案不动）才不是一句空话。 */
    var QovStrict=calibOverride('rpe_hard_stop',0);
    var QovRun=clone(QovStrict); QovRun.rpe_gap=0;
    var Qov=calibRun(QovRun);
    var QkeySame=Qov.fail===Qbase.fail && Qov.ok===Qbase.ok && Qov.hard===Qbase.hard && Qov.graded===Qbase.graded;
    var QmovesDiff=(Qov.up!==Qbase.up)||(Qov.keep!==Qbase.keep)||(Qov.down!==Qbase.down);
    /* 同一行、同一份真实账，只把硬顶压到 0：判卷若读 autoregOf() 就会当场改口
       （8.5 < 契约硬顶 9.5 → 从「没崩」变「崩」）；实现里它读 PLAN_SCHEMA 原值，所以口径不动。 */
    var Qgx={verdict:'keep',rpe:+Qar.rpe_hard_stop-1};
    var QgRow=(state.weeks['3'][Qday].exercises)[0];
    var Qnaive=withAutoreg(QovStrict,function(){ return calibGrade(Qgx,QgRow); });
    var Qplain=calibGrade(Qgx,QgRow);
    /* 嵌套也要算得对：外层即便套着一套假阈值，calibRun 内部的判卷仍按契约默认，
       所以这趟「被假阈值包着的基线」必须和裸基线逐字节相同。少了那层 withAutoreg(null) 就露馅。 */
    var Qnested=withAutoreg(QovRun,function(){ return calibRun(null); });
    T('CA4 答案卷钉死在契约默认：把 RPE 硬顶压到 0、缺口抹成 0 会改掉「当时会怎么建议」（上/保/下 分布剧变），但改不掉「下周到底算不算崩」（崩/勉强/干净三档计数一字不动），而且整套回测被套在假阈值里跑也仍是同一版基线',
      QmovesDiff && QkeySame && Qov.down>Qbase.down && Qov.hard===Qbase.hard
      && JSON.stringify(Qnaive)===JSON.stringify(Qplain)
      && JSON.stringify(Qnested)===JSON.stringify(Qbase),
      '建议分布 基线上'+Qbase.up+'/保'+Qbase.keep+'/下'+Qbase.down+' vs 压顶后'
      +Qov.up+'/'+Qov.keep+'/'+Qov.down+' · 答案 崩'+Qbase.fail+'/勉强'+Qbase.hard+'/干净'+Qbase.ok
      +' vs 崩'+Qov.fail+'/勉强'+Qov.hard+'/干净'+Qov.ok
      +' · 判卷被覆盖污染='+(JSON.stringify(Qnaive)!==JSON.stringify(Qplain))
      +'（该行按契约硬顶判='+JSON.stringify(Qplain)+'）'
      +' · 嵌套跑与裸基线相同='+(JSON.stringify(Qnested)===JSON.stringify(Qbase)));

    var Qthin=calibVerdict({graded:CALIB_MIN_N-1,hit:0,rate:0,fail:0,hard:0,ok:0});
    var Qenough=calibVerdict({graded:CALIB_MIN_N,hit:2,rate:25,fail:1,hard:1,ok:6});
    T('CA5 门槛本身就是个「至少要看几行账」的数（≥2），样本不够只报「账本还太薄」，绝不端出一个唬人的命中率；刚好够数才给统计量',
      CALIB_MIN_N>=2 && Qthin.indexOf('太薄')>=0 && Qthin.indexOf('%')<0
      && Qenough.indexOf('太薄')<0 && Qenough.indexOf('25%')>=0 && Qenough.indexOf(String(CALIB_MIN_N))>=0,
      '门槛='+CALIB_MIN_N+' 薄：'+Qthin+' ｜ 够：'+Qenough);

    var QcsvA=exportUnifiedCsv(), QplanA=JSON.stringify(xStateToPlanDict());
    var Qrep=calibSweep();
    openCalibSheet();
    var Qrows=Qrep.rows.length;
    var Qtxt=document.getElementById('calibBody').textContent;
    var Qstat=document.getElementById('calibStat').textContent;
    var QbodyHtml=document.getElementById('calibBody').innerHTML;
    closeSheet('calibSheet');
    var QcsvB=exportUnifiedCsv(), QplanB=JSON.stringify(xStateToPlanDict());
    T('CA8 整条回测链只读：扫一遍 + 开面板 + 渲染之后，state、两分片、CSV 与计划导出逐字节不动（回测不动手，是纪律不是口号）',
      JSON.stringify(state)===QFIX && localStorage.getItem(LS_PREFS)===Qpr0
      && localStorage.getItem(LS_WORK)===Qwk0 && QcsvA===QcsvB && QplanA===QplanB,
      'state 不变='+(JSON.stringify(state)===QFIX)+' prefs='+(localStorage.getItem(LS_PREFS)===Qpr0)
      +' work='+(localStorage.getItem(LS_WORK)===Qwk0)+' csv='+(QcsvA===QcsvB)+' plan='+(QplanA===QplanB));

    var QnTab=document.querySelectorAll('#calibBody table.calib-table').length;
    var QnBody=document.querySelectorAll('#calibBody tbody tr').length;
    var QnTh=document.querySelectorAll('#calibBody thead th').length;
    var QnCand=document.querySelectorAll('#calibBody .cal-cand').length;
    var Qbad=['NaN','Infinity','undefined','null'].filter(function(s){ return Qtxt.indexOf(s)>=0; });
    T('CA9 有账时画得出表：一张表、每参数一行（'+QnBody+'/'+Qrows+'）、四列表头、候选格 '+QnCand+' 个、汇总行有数、正文里没有 NaN / Infinity / undefined',
      QnTab===1 && QnBody===Qrows && QnTh===4 && QnCand>0 && Qbad.length===0
      && Qstat.length>0 && Qstat.indexOf('%')>=0 && QbodyHtml.indexOf('calib-table')>=0,
      '表 '+QnTab+' 行 '+QnBody+'/'+Qrows+' 列 '+QnTh+' 候选格 '+QnCand+' 脏词='+(Qbad.join(',')||'无')+' 汇总='+Qstat);

    var QkeepWeeks=state.weeks;
    state.weeks={};
    openCalibSheet();
    var QnoPair=adviceSrcWeekOptions().length;
    var QemptyN=document.querySelectorAll('#calibBody .log-empty').length;
    var QemptyTxt=document.getElementById('calibBody').textContent.trim();
    var QemptyStat=document.getElementById('calibStat').textContent.trim();
    var QstillTable=document.querySelectorAll('#calibBody table').length;
    closeSheet('calibSheet');
    state.weeks=QkeepWeeks;
    T('CA10 凑不出相邻周时不画半张空表，改画空态并说清缺什么（回到有账的周表后仍可继续渲染）',
      QnoPair===0 && QemptyN===1 && QstillTable===0
      && QemptyTxt.length>8 && QemptyStat.length>8 && /相邻周/.test(QemptyTxt)
      && adviceSrcWeekOptions().length>=1,
      '周对 '+QnoPair+' 空态块 '+QemptyN+' 表 '+QstillTable+' 正文='+QemptyTxt.slice(0,40)
      +' 汇总='+QemptyStat.slice(0,30));

    setLang('en'); applyChrome(); openCalibSheet();
    var QenIds=['calibTitle','calibCloseBtn','chartCalibT','chartCalibS','chartCalibGo'];
    var QenBad=QenIds.filter(function(id){ var v=txt(id); return !v||HAN.test(v); });
    var QenHead=Array.prototype.map.call(document.querySelectorAll('#calibBody thead th'),function(t){ return t.textContent.trim(); });
    var QenHan=QenHead.filter(function(s){ return HAN.test(s); });
    var QenNote=Array.prototype.map.call(document.querySelectorAll('#calibBody .frm-note'),function(p){ return p.textContent; })
      .filter(function(s){ return HAN.test(s); });
    closeSheet('calibSheet'); setLang('zh'); applyChrome();
    T('CA11 英文态零汉字不漏：面板五个静态串 + 渲染出的表头与口径注（'+QenHead.length+' 列表头）都过 L()',
      QenBad.length===0 && QenHead.length===4 && QenHan.length===0 && QenNote.length===0,
      '静态缺/脏='+(QenBad.join(',')||'无')+' 表头='+QenHead.join('|')+' 汉字='+(QenHan.join(',')||'无')
      +' 注='+(QenNote.length||'无'));

    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(QBAK).forEach(function(k){ state[k]=QBAK[k]; });
    state.lang='zh'; applyChrome();
    if(Qpr0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,Qpr0);
    if(Qwk0===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK,Qwk0);
    applyChrome(); renderAll();
    T('CA12 出段还原：两周账目与语言没把共享对象改脏，两分片回到进段前，本段开的 calibSheet 收干净了',
      JSON.stringify(state)===QSNAP && localStorage.getItem(LS_PREFS)===Qpr0
      && localStorage.getItem(LS_WORK)===Qwk0
      && adviceWeekList().length>=3 && !document.querySelector('#calibSheet.on'),
      '长度 '+JSON.stringify(state).length+'/'+QSNAP.length+' 周数 '+adviceWeekList().length
      +' state 相同='+(JSON.stringify(state)===QSNAP)
      +' prefs='+(localStorage.getItem(LS_PREFS)===Qpr0)+' work='+(localStorage.getItem(LS_WORK)===Qwk0)
      +' calibSheet 还开着='+!!document.querySelector('#calibSheet.on'));

    SECT='BD'; /* ===== BD. v0.28 存档读取闸门：磁盘有账却读不回 → 停在只读，绝不拿空账本覆盖 ===== */
    var Qsrc=document.documentElement.outerHTML;
    T('BD1 闸门接线在位：boot 真调了探针并标 read 原因，两个 helper 都是函数',
      typeof unreadableSlices==='function' && typeof sliceProbe==='function'
      && Qsrc.indexOf('unreadableSlices(sliceProbe(')>=0
      && Qsrc.indexOf("markBootFatal('read'")>=0,
      'helper='+(typeof sliceProbe)+'/'+(typeof unreadableSlices)
      +' 调用点='+(Qsrc.indexOf('unreadableSlices(sliceProbe(')>=0)
      +' markBootFatal(read)='+(Qsrc.indexOf("markBootFatal('read'")>=0));

    T('BD2 没有桥就没有探针：浏览器里闸门永不触发（真机专属的兜底不能反过来把浏览器变砖）',
      !window.AndroidBridge && sliceProbe()===null && unreadableSlices(null,{workout:false,prefs:false}).length===0,
      'AndroidBridge='+(typeof window.AndroidBridge)+' probe='+String(sliceProbe()));

    var Qmtx={'roast_workout.json':812,'roast_prefs.json':-1,'roast_lib_diff.json':0,
              'roast_plan_archive.json':44,'roast_state.json':17};
    T('BD3 只点真正读不回的名字：有字节且没拿到才列，文件不在(-1)、空文件(0)、已读回的一律放过',
      unreadableSlices(Qmtx,{workout:false,prefs:false,lib:false,archive:true,legacy:false})
        .join()==='workout,legacy',
      '列出的='+unreadableSlices(Qmtx,{workout:false,prefs:false,lib:false,archive:true,legacy:false}).join(','));

    var QbPrev=window.AndroidBridge, QerrPrev=window.__lastStoreError;
    window.AndroidBridge={storeProbe:function(){return '这不是 JSON';}};
    var Qjunk=sliceProbe();
    window.AndroidBridge={storeProbe:function(){return '[1,2]';}};
    var Qarr=sliceProbe();
    window.AndroidBridge={};
    var QnoMethod=sliceProbe();
    window.AndroidBridge={storeProbe:function(){return '{"roast_workout.json":5}';}};
    var QokProbe=sliceProbe();
    delete window.AndroidBridge;
    T('BD4 探针自己坏了就当没有：坏 JSON / 数组 / 桥没这方法都回 null，绝不半个数字就下结论',
      Qjunk===null && Qarr===null && QnoMethod===null
      && !!QokProbe && +QokProbe['roast_workout.json']===5,
      '坏串='+String(Qjunk)+' 数组='+String(Qarr)+' 无方法='+String(QnoMethod)+' 好的='+JSON.stringify(QokProbe));

    var QwBak=localStorage.getItem(LS_WORK);
    localStorage.removeItem(LS_WORK);
    window.AndroidBridge={storeProbe:function(){return '{"roast_workout.json":812}';},
                          loadWorkout:function(){throw new Error('BD 注入的读故障');}};
    window.__lastStoreError='';
    var Qrtxt=readSlice('workout');
    var Qrerr=String(window.__lastStoreError||'');
    var Qrlist=unreadableSlices(sliceProbe(),{workout:!!Qrtxt});
    delete window.AndroidBridge;
    if(QwBak===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, QwBak);
    window.__lastStoreError=QerrPrev;
    T('BD5 读侧也有痕：桥抛错写进 __lastStoreError（与写侧对称），磁盘报字节 → 名单点到 workout',
      Qrtxt===null && Qrerr.indexOf('read-bridge:workout')===0 && Qrlist.join()==='workout',
      '文本='+String(Qrtxt)+' 错='+(Qrerr||'（空）')+' 名单='+Qrlist.join(','));

    var Qst0=JSON.stringify(state), Qpr0=localStorage.getItem(LS_PREFS),
        Qlk0=localStorage.getItem(LS), Qlib0=localStorage.getItem(LS_LIB),
        Qro0=READONLY, Qbf0=bootFatal;
    localStorage.removeItem(LS_WORK);
    window.AndroidBridge={storeProbe:function(){return '{"roast_workout.json":812,"roast_state.json":-1}';},
                          loadWorkout:function(){throw new Error('BD 注入的读故障');},
                          loadPrefs:function(){return '';}, loadLibDiff:function(){return '';},
                          loadStore:function(){return '';}};
    var QbootThrew='';
    try{ boot(); }catch(e){ QbootThrew=(e&&e.message)||String(e); }
    var Qbox=document.getElementById('bootFail');
    var QboxTxt=Qbox?Qbox.innerText:'';
    var QwAfter=localStorage.getItem(LS_WORK);
    var QroAfter=READONLY, QbfAfter=bootFatal;
    if(Qbox) Qbox.remove();
    delete window.AndroidBridge;
    if(QwBak===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, QwBak);
    T('BD6 boot 撞上「磁盘有账、手里是空」：停在只读并亮阻断层，四分片一字未动、state 没被换成空账本',
      !QbootThrew && QroAfter===true && !!QbfAfter && QbfAfter.reason==='read'
      && !!Qbox && QboxTxt.indexOf('原生读取失败')>=0 && QboxTxt.indexOf('roast_workout.json')>=0
      && QwAfter===null && localStorage.getItem(LS_PREFS)===Qpr0
      && localStorage.getItem(LS_LIB)===Qlib0 && localStorage.getItem(LS)===Qlk0
      && JSON.stringify(state)===Qst0,
      '抛错='+(QbootThrew||'无')+' READONLY='+QroAfter+' reason='+(QbfAfter&&QbfAfter.reason)
      +' 阻断层='+!!Qbox+' workout 仍空='+(QwAfter===null)+' state 不变='+(JSON.stringify(state)===Qst0));
    /* 兜底复原：万一上面某步没走到，这里把闭锁、原文与渲染都拉回来 */
    if(QwBak===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK, QwBak);
    delete window.AndroidBridge;
    READONLY=Qro0; bootFatal=Qbf0; window.__lastStoreError=QerrPrev;
    applyTheme(); applyChrome(); renderAll();

    T('BD7 原因标签不裸奔：五个 reason 都有人话，read 那条不能显示成键名',
      ['schema','migrate','parse','read','unknown'].every(function(k){
        return String(BF_REASON_LABEL[k]||'').length>1; }),
      Object.keys(BF_REASON_LABEL).map(function(k){ return k+'='+BF_REASON_LABEL[k]; }).join(' / '));

    /* ===== LD. v0.28 逻辑债：导入键分区 / 归档缺账可见 / 基准重算 / e1RM 读数 / 遥测沿用与整份拒绝 /
       jts 落盘 / 手抄兜底 / CSV 未知行记账 / 计数现算 / 档位取色单源 ===== */
    SECT='LD';
    var LDak=clone(state), LDsnap=JSON.stringify(state);
    var LDp0=localStorage.getItem(LS_PREFS), LDw0=localStorage.getItem(LS_WORK),
        LDl0=localStorage.getItem(LS_LIB), LDa0=localStorage.getItem(LS_ARCHIVE);
    var LDsrc=document.documentElement.outerHTML;
    var LDtt=function(){ return String(txt('toast')||''); };
    var LDdays=dayIds();
    closeAllSheets();   /* 前面段落可能留着一层面板；本段的「出去时收干净」只判自己开的那些 */

    var LDkeep=IMPORT_KEEP_KEYS.slice(), LDown=PLAN_OWNED_KEYS.slice();
    var LDovl=LDkeep.filter(function(k){ return LDown.indexOf(k)>=0; });
    var LDtop=Object.keys(state).filter(function(k){ return k!=='lib'; });
    var LDgap=LDtop.filter(function(k){ return LDkeep.indexOf(k)<0 && LDown.indexOf(k)<0; });
    T('LD1 导入的键分区自洽（保住 '+LDkeep.length+' 键 / 整份换新 '+LDown.length+' 键）：两份名单不重叠，且并起来盖得住 state 的每个顶层键——少归一类，导入那一刻那个键就静默回落到种子默认',
      LDkeep.length>0 && LDown.length>0 && LDovl.length===0 && LDgap.length===0,
      '重叠='+(LDovl.join(',')||'无')+' 未归类='+(LDgap.join(',')||'无')+' 顶层='+LDtop.join(','));

    var LDerr='', LDbad=null, LDgood=null, LDrefused=null;
    try{
      var LDict=xStateToPlanDict(state);
      var LDapBak=archivePush;
      window.archivePush=function(){ throw new Error('LD 注入：归档盘写不进'); };
      LDbad=adoptImportedPlan(LDict,true);
      window.archivePush=function(){ return {ok:false, reason:'too_big', bytes:999999}; };
      LDrefused=adoptImportedPlan(LDict,true);
      window.archivePush=LDapBak;
      LDgood=adoptImportedPlan(LDict,true);
    }catch(e){ LDerr=(e&&e.message)||String(e); }
    var LDnBad=LDbad?archMissNote(LDbad.archErr):'';
    var LDnRef=LDrefused?archMissNote(LDrefused.archErr):'';
    var LDnGood=LDgood?archMissNote(LDgood.archErr):'';
    var LDsites=(LDsrc.match(/archMissNote[(]/g)||[]).length;
    T('LD2 「这次没存下旧计划」看得见：归档抛错与归档拒收（ok:false）都进 archErr 并在回执里点名人话理由，成功路径不多嘴；三处导入/取回回执的中英文案都挂了这句（'+LDsites+' 个调用点）',
      !LDerr && !!LDbad && LDbad.archived===null && String(LDbad.archErr).indexOf('LD 注入')>=0
      && LDnBad.indexOf('旧计划未能存进归档')>=0 && LDnBad.indexOf('回退不可用')>=0
      && !!LDrefused && LDrefused.archErr.indexOf('归档体积上限')>=0 && LDnRef.indexOf('归档体积上限')>=0
      && !!LDgood && LDgood.archErr==='' && LDnGood==='' && !!LDgood.archived && LDgood.archived.ok===true
      && LDsites===7,
      '抛错='+(LDerr||'无')+' 异常态='+String(LDbad&&LDbad.archErr).slice(0,20)
      +' 拒收态='+String(LDrefused&&LDrefused.archErr).slice(0,24)
      +' 注(坏)='+LDnBad.slice(0,34)+' 注(好)="'+LDnGood+'" 调用点='+LDsites+'/7');

    var LDstep=(PLAN_SCHEMA.conflict_policy||{}).round_step_kg;
    var LDmidSnap='', LDbpSnap='', LDzBad=[], LDzLoad=null, LDz0=null, LDz1=null;
    var LDsqCell=null, LDbpCell=null;
    var LDfindMain=function(letter){
      var ws=Object.keys(state.weeks).map(Number).sort(function(a,b){ return a-b; });
      for(var i=0;i<ws.length;i++){
        var w=String(ws[i]), dk=Object.keys(state.weeks[w]);
        for(var j=0;j<dk.length;j++){
          var ex=(state.weeks[w][dk[j]]&&state.weeks[w][dk[j]].exercises)||[];
          for(var k=0;k<ex.length;k++){ if(anchorOf(ex[k].cat)===letter) return {w:w,d:dk[j],i:k}; }
        }
      }
      return null;
    };
    var LDpBak=clone(state.profile);
    var LDsyncInputs=function(){
      var p=state.profile;
      document.getElementById('pSq').value=String(p.sq);
      document.getElementById('pBp').value=String(p.bp);
      document.getElementById('pDl').value=String(p.dl);
      document.getElementById('pOhp').value=String(p.ohp);
      document.getElementById('pBw').value=String(p.bw);
    };
    state=JSON.parse(LDsnap); LDak=clone(state);   /* 归档段改了 state，先取回干净底版再定位格子 */
    LDsqCell=LDfindMain('sq'); LDbpCell=LDfindMain('bp');
    if(LDsqCell && LDbpCell && isFinite(+LDstep)){
      LDmidSnap=JSON.stringify(state);
      state.profile.sq=100; state.profile.bp=100; LDsyncInputs();
      document.getElementById('pSq').value='120';
      LDz0=state.weeks[LDsqCell.w][LDsqCell.d].exercises[LDsqCell.i].load;
      LDbpSnap=state.weeks[LDbpCell.w][LDbpCell.d].exercises[LDbpCell.i].load;
      saveProfile(true);
      LDz1=state.weeks[LDsqCell.w][LDsqCell.d].exercises[LDsqCell.i].load;
      var LDwant=mround((+LDz0)*1.2, LDstep);
      if(+LDz1!==+LDwant) LDzBad.push('SQ 主项按 1.2× 应为 '+LDwant+'，实得 '+LDz1);
      if(+state.weeks[LDbpCell.w][LDbpCell.d].exercises[LDbpCell.i].load!==+LDbpSnap)
        LDzBad.push('BP 基准未变却跟着缩放了');
      if(+state.profile.sq!==120) LDzBad.push('基准没落进档案（'+state.profile.sq+'）');
      /* 旧基准为 0：按比例缩放 = 除以 0，Infinity 乘进每一行后 mround 归零，保存一次抹平全计划 */
      state=JSON.parse(LDmidSnap);
      state.profile.sq=0; state.profile.bp=0; LDsyncInputs();
      document.getElementById('pSq').value='120';
      LDzLoad=state.weeks[LDsqCell.w][LDsqCell.d].exercises[LDsqCell.i].load;
      saveProfile(true);
      var LDzAfter=state.weeks[LDsqCell.w][LDsqCell.d].exercises[LDsqCell.i].load;
      if(!isFinite(+LDzAfter)) LDzBad.push('基准为 0 时主项重量变成 '+LDzAfter);
      if(+LDzAfter!==+LDzLoad) LDzBad.push('基准为 0 时主项被从 '+LDzLoad+' 改成了 '+LDzAfter);
      if(+state.profile.sq!==120) LDzBad.push('基准为 0 但新基准没写进档案');
    } else LDzBad.push('前置不满足：缺 SQ/BP 主项或契约没有 round_step_kg');
    var LDtoSrc=String(saveProfile);
    T('LD3 改基准重算主项：正基准按 nOld→nNew 的比例缩放并 round 到契约 round_step_kg（不手抄步进），未变的项不动；旧基准为 0（没填）时比例不成立按 1 处理，绝不再拿 100/0 的 Infinity 把重量抹成 0（'+LDstep+'kg 档）',
      LDzBad.length===0 && LDtoSrc.indexOf('PLAN_SCHEMA.conflict_policy')>=0
      && LDtoSrc.indexOf('round_step_kg')>=0,
      LDzBad.join(' ; ')||('底 '+LDz0+' → 期望 '+mround((+LDz0)*1.2,LDstep)+' 实 '+LDz1+'；零基准 '+LDzLoad+' → '+LDzAfter));

    var LDeBad=[];
    state=JSON.parse(LDsnap);
    state.e1rmLog=[{lift:'sq',week:12,e1rm:120,day:'A',mv:'Squat',load:110,reps:3,rpe:8},
                   {lift:'sq',week:3,e1rm:110,day:'A',mv:'Squat',load:100,reps:5,rpe:8},
                   {lift:'sq',e1rm:777,day:'A',mv:'Squat',load:90,reps:1,rpe:9}];
    var LDord=e1ByWeek('sq').map(function(r){ return +r.week||0; });
    if(!LDord.every(function(v,i){ return i===0||LDord[i-1]<=v; })) LDeBad.push('未按周号升序：'+LDord.join(','));
    var LDlastE=e1ByWeek('sq')[e1ByWeek('sq').length-1];
    if(!LDlastE||+LDlastE.e1rm!==120) LDeBad.push('「最新一条」取到的是 '+(LDlastE&&LDlastE.e1rm)+'（缺周号的那条排到了最后）');
    renderE1Trend('sq');
    var LDeHtml=String(document.getElementById('e1List').innerHTML);
    if(LDeHtml.indexOf('W—')<0) LDeBad.push('缺周号的记录没有画成 W—，列表里是 '+LDeHtml.slice(0,24));
    if(/NaN|undefined/.test(LDeHtml)) LDeBad.push('列表里漏出 NaN/undefined');
    var LDusableBad=[[undefined],[null],[{}],[{e1rm:0}],[{e1rm:-5}],[{e1rm:'x'}],[{e1rm:'NaN'}]]
      .filter(function(a){ return e1Usable(a[0]); }).map(function(a){ return JSON.stringify(a[0]); });
    if(!e1Usable({e1rm:120})) LDeBad.push('正数被判为不可用');
    if(LDusableBad.length) LDeBad.push('判过了这些：'+LDusableBad.join(','));
    var LDsqBefore=state.profile.sq;
    state.e1rmLog=[{lift:'sq',week:5,e1rm:0,day:'A',mv:'Squat',load:0,reps:0,rpe:10}];
    renderE1Trend('sq'); applyLatestE1();
    if(+state.profile.sq!==+LDsqBefore) LDeBad.push('e1RM=0 仍被写进档案：'+state.profile.sq);
    if(LDtt().indexOf('没有可用的 e1RM')<0) LDeBad.push('拒绝时没给人话（toast="'+LDtt()+'"）');
    state.e1rmLog=[{lift:'sq',week:5,e1rm:131.5,day:'A',mv:'Squat',load:120,reps:5,rpe:8}];
    renderE1Trend('sq'); applyLatestE1();
    if(+state.profile.sq!==131.5) LDeBad.push('可用时没写进档案（'+state.profile.sq+'）');
    state.profile.sq=LDsqBefore;
    closeSheet('profSheet');
    T('LD4 e1RM 读数拿得稳：缺周号（CSV 导入的 E1RM_LOG 行）按 0 周排序不再抢「最新」，列表画 W— 不漏 NaN；只有正且有限的 e1RM 才进档案，抹零的那条被拦下并说明「档案未改动」',
      LDeBad.length===0, LDeBad.join(' ; ')||('顺序 '+LDord.join('<')+' 最新 '+LDlastE.e1rm+' 拒绝态与写入态都如期'));

    var LDcBad=[];
    state=JSON.parse(LDsnap);
    state.week='1'; state.day=LDdays[0];
    var LDc1=JSON.stringify(day());
    copyPrevTele();
    if(JSON.stringify(day())!==LDc1) LDcBad.push('第一周仍在动格子');
    if(LDtt().indexOf('第一周')<0) LDcBad.push('第一周没说明（"'+LDtt()+'"）');
    var LDpw=state.weeks['2'];
    if(!LDpw) LDcBad.push('这份计划没有第 2 周，沿用链的其余分支验不了');
    if(LDpw){
      state.week='3';
      delete LDpw[state.day];
      copyPrevTele();
      if(LDtt().indexOf('上周同日还没有记录')<0) LDcBad.push('缺同日没说明（"'+LDtt()+'"）');
      LDpw[state.day]={title:'',bio:{},post:{},exercises:[]};
      var LDbefore=JSON.stringify(day());
      copyPrevTele();
      if(LDtt().indexOf('没有已启用的遥测值')<0) LDcBad.push('上周整周空着却说沿用了（"'+LDtt()+'"）');
      if(JSON.stringify(day())!==LDbefore) LDcBad.push('空值分支却动了本周格子');
      var LDprevBio=LDpw[state.day].bio||{};
      LDprevBio.sleep=7.5; LDpw[state.day].bio=LDprevBio;
      copyPrevTele();
      if(+day().bio.sleep!==7.5) LDcBad.push('沿用没落到内存（'+(day().bio&&day().bio.sleep)+'）');
      if(LDtt().indexOf('已沿用上周同日')<0) LDcBad.push('成功时没说沿用几项（"'+LDtt()+'"）');
      flushSave();
      var LDcDisk=JSON.parse(localStorage.getItem(LS_WORK)||'{}');
      var LDcDiskV=((LDcDisk.weeks||{})['3']||{})[state.day];
      LDcDiskV=LDcDiskV&&LDcDiskV.bio&&LDcDiskV.bio.sleep;
      if(+LDcDiskV!==7.5) LDcBad.push('沿用只改了内存没落盘（盘上='+String(LDcDiskV)+'）');
      closeSheet('teleSheet');
    }
    T('LD5 沿用上周遥测：第一周 / 上周缺同日 / 上周整周没值三种都只说明不动格子（旧写法写成 Math.max(1,w-1)，W1 的「上周」就是自己，于是把刚填的格子原样抄回自己还弹一句「已沿用」），真沿用时写进内存并落盘、报出项数',
      LDcBad.length===0, LDcBad.join(' ; ')||('W1 拦住 / 缺同日拦住 / 空值拦住 / 7.5 已落盘'));

    var LDcap=planCapacity(), LDcav=PLAN_SCHEMA.capacity||{};
    var LDcapSrc=String(planCapacity);
    var LDhasFallback=new RegExp('[|][|][0-9]').test(LDcapSrc.replace(/[ ]/g,''));
    T('LD6 容量四键只从契约现读：max '+LDcap.maxWeeks+' 周 / '+LDcap.maxBlocks+' Block 与 capacity 逐项相等且都是 >=1 的整数，函数体内没有「||52」这类第二份手抄（S28 已保证契约四键合格，兜底数字永远轮不到上场，留着它就不会跟着契约改）',
      +LDcap.minWeeks===+LDcav.min_weeks && +LDcap.maxWeeks===+LDcav.max_weeks
      && +LDcap.minBlocks===+LDcav.min_blocks && +LDcap.maxBlocks===+LDcav.max_blocks
      && [LDcap.minWeeks,LDcap.maxWeeks,LDcap.minBlocks,LDcap.maxBlocks].every(function(v){
        return isFinite(v)&&v>=1&&Math.floor(v)===+v; })
      && !LDhasFallback,
      '取到 '+JSON.stringify(LDcap)+' 契约 '+[LDcav.min_weeks,LDcav.max_weeks,LDcav.min_blocks,LDcav.max_blocks].join('/')
      +' 手抄兜底='+LDhasFallback);

    var LDwBak=clone(state.profile), LDbwBad=[];
    [0,'',null,'abc',undefined].forEach(function(v){
      state.profile=clone(LDwBak); state.profile.bw=v;
      if(+strengthMult()!==1) LDbwBad.push('bw='+JSON.stringify(v)+' 乘数='+strengthMult());
      var line=String(profileCoefLine());
      if(line.indexOf('体重未填')<0) LDbwBad.push('bw='+JSON.stringify(v)+' 没写「体重未填」');
      if(line.indexOf('85.0kg')>=0) LDbwBad.push('bw='+JSON.stringify(v)+' 编出了 85kg：'+line.slice(0,40));
    });
    state.profile=clone(LDwBak);
    state.profile.bw=100; state.profile.sq=100; state.profile.bp=100; state.profile.dl=200;
    var LDmExpected=Number((Math.max(0.82,Math.min(1.10,1.10-0.035*(4-3.5)))
      * Math.max(0.92,Math.min(1.05,1.0+0.0025*(75-100)))).toFixed(2));
    if(+strengthMult()!==LDmExpected) LDbwBad.push('bw=100/SBD=400 应为 '+LDmExpected+'，实得 '+strengthMult());
    var LDbwLine=String(profileCoefLine());
    if(LDbwLine.indexOf('100.0kg')<0) LDbwBad.push('填了体重却没照实显示：'+LDbwLine.slice(0,40));
    state.profile=LDwBak;
    T('LD7 体重没填就不替用户编：bw 为 0/空/非数时强度乘数恒等于 1（旧写法 +p.bw||75 会拿 75kg 算，档案行还硬写 85kg），填了才参与计算并照实显示',
      LDbwBad.length===0, LDbwBad.join(' ; ')||('五种空值都返回 1.00；bw100/SBD400 → '+LDmExpected));

    var LDjBad=[];
    state=JSON.parse(LDsnap);
    var LDjk=jtsKey();
    setJts('LDk',3.5); flushSave();
    var LDjd=JSON.parse(localStorage.getItem(LS_WORK)||'{}');
    if(!LDjd.jts||!LDjd.jts[LDjk]||+LDjd.jts[LDjk].LDk!==3.5) LDjBad.push('setJts 后盘上没有 '+LDjk+'.LDk');
    clearJts(); flushSave();
    var LDjd2=JSON.parse(localStorage.getItem(LS_WORK)||'{}');
    if(LDjd2.jts&&LDjd2.jts[LDjk]) LDjBad.push('clearJts 后盘上仍留着 '+LDjk);
    if(String(setJts).indexOf('save()')<0 || String(clearJts).indexOf('save()')<0)
      LDjBad.push('两个入口之一不再自己排盘');
    T('LD8 JTS 填完就落盘：setJts / clearJts 各自都排一次盘（旧写法只动内存，等别的动作顺手把它带出去，中途重开就是「填过又没了」，清空也一样会复活）',
      LDjBad.length===0, LDjBad.join(' ; ')||('写入 '+LDjk+'.LDk=3.5 已在盘上，清空后不在'));

    var LDtBad=[];
    state=JSON.parse(LDsnap);
    /* 遥测面板这一段本来就是测「面板怎么读写格子」，所以先按用户「已经打开」的样子进门；
       默认关闭那条腿由 TM3 单独测，不在这里混。 */
    state.teleOn=true;
    state.day=LDdays[0]; state.week='3';
    openTeleSheet();
    var LDfA=TELE_FIELDS.filter(function(f){ return f.type==='num'&&f.k!=='bw'; })[0];
    var LDfB=TELE_FIELDS.filter(function(f){ return f.type==='num'&&f.k!=='bw'&&f!==LDfA; })[1];
    document.getElementById('tf_'+LDfA.k).value='5';
    var LDeB=document.getElementById('tf_'+LDfB.k);
    LDeB.setAttribute('type','text'); LDeB.value='abc';
    var LDtSnap=JSON.stringify(day());
    saveTele();
    if(JSON.stringify(day())!==LDtSnap) LDtBad.push('有一格非数却仍然半份落账');
    if(LDtt().indexOf('本次未保存')<0 || LDtt().indexOf(LDfB.lbl[0])<0)
      LDtBad.push('拒绝时没点名是哪几格（"'+LDtt()+'"）');
    LDeB.setAttribute('type','number'); LDeB.value='6';
    saveTele();
    if(+teleVal(day(),LDfA)!==5 || +teleVal(day(),LDfB)!==6)
      LDtBad.push('修好后没写进去（'+teleVal(day(),LDfA)+'/'+teleVal(day(),LDfB)+'）');
    /* 关掉的格子：元素照旧渲染（.off），但不读也不写 —— 原先会把 null 写进 state，等于「隐藏这一格」顺手抹掉历史值。
       先给这一格写一个真值：不预置历史值，「抹掉」和「本来就空」在断言里长得一样（F10 注入时曾经绿过）。 */
    var LDfC=TELE_FIELDS.filter(function(f){ return f.type==='num'&&f.k!=='bw'&&f!==LDfA&&f!==LDfB; })[0];
    document.getElementById('tf_'+LDfC.k).value='7.7';
    saveTele();
    var LDcPrev=teleVal(day(),LDfC);
    if(String(LDcPrev)!=='7.7') LDtBad.push('停用的格先写不进历史值（'+String(LDcPrev)+'）');
    toggleTeleField(LDfC.k); renderTeleFields();
    document.getElementById('tf_'+LDfC.k).value='';
    document.getElementById('tf_'+LDfA.k).value='9';
    saveTele();
    if(teleVal(day(),LDfC)!==LDcPrev) LDtBad.push('停用的格子被写成了 '+String(teleVal(day(),LDfC)));
    if(+teleVal(day(),LDfA)!==9) LDtBad.push('启用格没保存');
    toggleTeleField(LDfC.k);
    closeSheet('teleSheet');
    T('LD9 遥测整份拒绝 + 停用不碰：任一数字格落进非数就整份不保存并点名是哪几格（旧写法先写的格子已经落账，半份遥测比没有更难查），关掉的格子不读不写（旧写法把 null 写进去＝顺手抹掉历史值）',
      LDtBad.length===0, LDtBad.join(' ; ')||('非数拒绝 '+LDfA.k+'/'+LDfB.k+'；停用 '+LDfC.k+' 保值'));

    var LDmk=function(o){
      var b={}; CSV_COLS.forEach(function(c){ b[c]=''; });
      Object.keys(o).forEach(function(k){ b[k]=o[k]; });
      return CSV_COLS.map(function(c){ return String(b[c]); }).join(',');
    };
    var LDcsvHead=CSV_HEAD;
    var LDst=JSON.parse(LDsnap);
    state=LDst;
    var LDcsvText=[LDcsvHead,
      LDmk({schema_ver:'1',record_type:'TELEMETRY',week:String(planCapacity().maxWeeks),day:'Z',sleep_h:'7'}),
      LDmk({schema_ver:'1',record_type:'EXERCISE',week:'1',day:'Q',row_idx:'1',movement:'Squat',load_kg:'100'}),
      LDmk({schema_ver:'1',record_type:'ARMOR',week:'1',category:'Recovery',movement:'LD不存在的辅助动作',aux_week_mask:'10'})
    ].join('\\n');
    var LDgppBefore=(state.gpp||[]).length;
    var LDir=importUnifiedCsv(LDcsvText);
    var LDiBad=[];
    /* v0.44/F25：陌生辅助动作不再静默跳过，而是落成 custom:true 的 GPP 定义；
       所以只有「未知周 / 未知日」两条真错各计一条 skipped，陌生动作那条进菜单。 */
    if(LDir.stats.skipped!==2) LDiBad.push('skipped='+LDir.stats.skipped+'（应 2）');
    if(LDir.errors.length!==2) LDiBad.push('errors='+LDir.errors.length+'（应 2）');
    var LDiAll=String(LDir.errors.join(' | '));
    if(/undefined|Cannot read|TypeError/.test(LDiAll)) LDiBad.push('回执里漏出 JS  internals：'+LDiAll.slice(0,50));
    if((LDiAll.match(/不在当前结构里/g)||[]).length<2) LDiBad.push('未知周/日没有点名「不在当前结构里」');
    var LDcustom=(state.gpp||[]).filter(function(g){ return g.item==='LD不存在的辅助动作' && g.custom===true; });
    if(LDcustom.length!==1) LDiBad.push('陌生辅助动作没落成 custom:true 的 GPP 定义（命中 '+LDcustom.length+' 条）');
    if((state.gpp||[]).length!==LDgppBefore+1) LDiBad.push('GPP 菜单没有恰好 +1（'+LDgppBefore+'→'+(state.gpp||[]).length+'）');
    if(state.weeks[String(planCapacity().maxWeeks)]!==undefined)
      LDiBad.push('导入凭空造出了第 '+planCapacity().maxWeeks+' 周');
    if(!state.weeks['1']) LDiBad.push('导入把已有周弄没了');
    state=JSON.parse(LDsnap);
    T('LD10 CSV 里对不上的行分两类记账：未知周 / 未知日各计一条 skipped 并点名「不在当前结构里」（旧写法对未知周直接 return，无声消失，回执还说「完成」；取格子还会先抛 TypeError，用户看到一句 JS internals）；陌生辅助动作不静默跳过，落成 custom:true 的 GPP 定义（F25/C6）',
      LDiBad.length===0, LDiBad.join(' ; ')||('2 条真错点名 + 陌生动作进菜单 '+LDiAll.slice(0,60)));

    var LDsc=stratCounts(), LDSL=SEED.strategyLib||{};
    var LDsBad=[];
    if(LDsc.n!==(LDSL.items||[]).length) LDsBad.push('策略条数 '+LDsc.n+'!='+((LDSL.items||[]).length));
    if(LDsc.m!==(LDSL.matrix||[]).length) LDsBad.push('矩阵行数 '+LDsc.m+'!='+((LDSL.matrix||[]).length));
    if(LDsc.aux!==(LDSL.auxActs||[]).length) LDsBad.push('辅助数 '+LDsc.aux+'!='+((LDSL.auxActs||[]).length));
    if(LDsc.cols!==STRAT_COLS.length) LDsBad.push('列数与 STRAT_COLS 不一致');
    applyChrome();
    openSettings();
    var LDsSub=String(txt('setStratLibS')||''), LDtabL=String(txt('stratTabList')||'');
    closeSheet('setSheet');
    if(LDsSub.indexOf(LDsc.n+' 条策略')<0 || LDsSub.indexOf(LDsc.m+'×'+LDsc.cols)<0
       || LDsSub.indexOf(LDsc.aux+' 辅助动作')<0)
      LDsBad.push('设置页副标题不是现算的数：'+LDsSub.slice(0,40));
    if(LDtabL.indexOf('('+LDsc.n+')')<0) LDsBad.push('列表页签没带现算条数：'+LDtabL);
    openStratLibSheet(); setStratView('matrix');
    var LDths=document.querySelectorAll('#stratMatrix thead th');
    var LDtabM=String(txt('stratTabMatrix')||'');
    setStratView('list'); closeSheet('stratLibSheet');
    if(LDths.length!==LDsc.cols+2) LDsBad.push('矩阵表头 '+(LDths?LDths.length:'无')+' 列，应为 '+(LDsc.cols+2));
    if(LDtabM.indexOf('('+LDsc.m+'×'+LDsc.cols+')')<0) LDsBad.push('矩阵页签没带现算规模：'+LDtabM);
    if(Object.keys(I18N_NODES).indexOf('setStratLibS')>=0) LDsBad.push('现算文案还挂在静态名单里（会被 applyChrome 覆盖成第二份口径）');
    T('LD11 策略库的数从种子现算：条数 / 矩阵规模 / 辅助数 / 列数都取 stratCounts()，设置页副标题、两页签文案与矩阵表头同口径（原先 27、27×5、209 抄在文案里，种子一改文案就说瞎话）',
      LDsBad.length===0, LDsBad.join(' ; ')||(LDsc.n+' 条 / '+LDsc.m+'×'+LDsc.cols+' 矩阵 / '+LDsc.aux+' 辅助'));

    var LDtk=Object.keys(TIER_TOKEN), LDtc=Object.keys(TIER_CLASS);
    var LDmissTok=LDtc.filter(function(k){ return !TIER_TOKEN[k]; });
    var LDnoVal=LDtk.filter(function(k){
      return String(getComputedStyle(document.documentElement).getPropertyValue(TIER_TOKEN[k])).trim()===''; });
    var LDsrcTimer=String(startTimer)+String(tierColor);
    T('LD12 档位取色单源：tierColor() 只发 var(--tX)，TIER_TOKEN 的键域覆盖 TIER_CLASS 且令牌在当前主题里都有值，HUD 圆点不再手抄十六进制（第三份色值：换到纸底主题时圆点仍是暗色盘的红，且没人看守）',
      LDmissTok.length===0 && LDnoVal.length===0
      && tierColor('T1')==='var(--t1)' && tierColor('T2')==='var(--t2)' && tierColor('T3')==='var(--t3)'
      && tierColor('什么也不是')==='var(--t3)'
      && LDsrcTimer.indexOf('#E53935')<0 && LDsrcTimer.indexOf('#1E88E5')<0 && LDsrcTimer.indexOf('#43A047')<0,
      '令牌表='+LDtk.join(',')+' 缺键='+(LDmissTok.join(',')||'无')
      +' 缺值='+(LDnoVal.join(',')||'无')+' T1='+tierColor('T1')+' 兜底='+tierColor('什么也不是'));

    /* ---------- LD14 就绪五档只有一份（逻辑债 #14） ---------- */
    var LDrBad=[];
    [[100,0],[95,0],[90,0],[89.9,1],[75,1],[74.9,2],[60,2],[59.9,3],[45,3],[44.9,4],[0,4]].forEach(function(c){
      if(readyIndexFromScore(c[0])!==c[1]) LDrBad.push(c[0]+'→'+readyIndexFromScore(c[0])+'（应 '+c[1]+'）');
    });
    if(readyIndexFromScore('不是数')!==4) LDrBad.push('非数没落到最低档：'+readyIndexFromScore('不是数'));
    [100,95,88,80,72,65,55,50,40,0].forEach(function(x){
      if(jtsToReady(x)!==READY[readyIndexFromScore(x)]) LDrBad.push('jtsToReady('+x+') 与阈值表分家');
    });
    var LDrJts0=state.jts; state.jts={};
    READY.forEach(function(r){
      var d0={readiness:r.zh,bio:{},post:{}};
      if(matchReadyPct(d0)!==r.pct) LDrBad.push(r.zh+' 的 pct='+matchReadyPct(d0)+'（应 '+r.pct+'）');
      if(matchReadyIndex(d0)!==READY.indexOf(r)) LDrBad.push(r.zh+' 认不出自己那一档');
    });
    var LDrPct=READY.map(function(r){ return r.pct; });
    for(var LDi=1; LDi<LDrPct.length; LDi++) if(LDrPct[LDi]>=LDrPct[LDi-1]) LDrBad.push('pct 不递减：'+LDrPct.join('/'));
    if(matchReadyPct({readiness:'没这种写法',bio:{},post:{}})!==READY[1].pct) LDrBad.push('认不出的写法没落到默认档');
    if(READY_COLOR.length!==READY.length) LDrBad.push('圆点色数与档数不等：'+READY_COLOR.length);
    if(/100,90,80,70,55/.test(String(matchReadyPct))) LDrBad.push('matchReadyPct 里还有第二份百分比表');
    var LDrToReadySrc=String(jtsToReady);
    if(LDrToReadySrc.indexOf('readyIndexFromScore')<0) LDrBad.push('jtsToReady 不再委托 readyIndexFromScore（阈值要单源）');
    if(/(>=|<=|>|<)\s*[0-9]/.test(LDrToReadySrc)) LDrBad.push('jtsToReady 里写着阈值比较（分数→档位应只走 readyIndexFromScore）：'+(LDrToReadySrc.match(/[^{}]*>=?[^;,}]*/)||[''])[0].trim());
    if(/9[05]|80|6[05]|4[05]/.test(LDrToReadySrc.replace(/READY\[[0-9]\]/g,''))) LDrBad.push('jtsToReady 里藏着档位数字：'+LDrToReadySrc);
    state.jts=LDrJts0;
    T('LD14 就绪五档只有一份：分数→档位与档位→计量值/色都从 READY / READY_AT 取，jtsToReady 与状态匹配同档，'
      + 'matchReadyPct 不再手抄五个数（旧写法改一档要记四处，漏一处的症状是「圆点说轻度疲劳、周容量按 90% 算」）',
      LDrBad.length===0, LDrBad.join(' ; ')||(READY.length+' 档 pct='+LDrPct.join('/')+' 阈值='+READY_AT.join('/')));

    /* ---------- LD15 默认值与字母表只有一份（逻辑债 #16 / #17） ---------- */
    var LDdBad=[];
    if(proto('LD没有这个模式')!==PROTO_FALLBACK) LDdBad.push('proto() 的兜底不再是 PROTO_FALLBACK 那一份');
    if(setsOf('LD没有这个模式')!==PROTO_FALLBACK.sets) LDdBad.push('setsOf 的兜底与 PROTO_FALLBACK 不等');
    if(setsOf('Custom')!==PROTO_FALLBACK.sets) LDdBad.push('Custom（sets=0）没走兜底：'+setsOf('Custom'));
    var LDtf=defaultTimerCfg(); LDtf.T1=999;
    if(defaultTimerCfg().T1!==300) LDdBad.push('defaultTimerCfg() 返回的是共享对象（改一次全污染）');
    if(defaultTimerCfg().T3!==75 || defaultTimerCfg().sound!==true) LDdBad.push('计时默认值漂移：'+JSON.stringify(defaultTimerCfg()));
    var LDtc=LDsrc.split('defaultTimerCfg(').length-1-1;   /* 减掉定义那一处，剩下的才是读点 */
    if(LDtc<2) LDdBad.push('读 defaultTimerCfg() 的地方少于 2 处（建档/迁移还在手抄）：'+LDtc);
    var LDtl=LDsrc.split('{T1:300').length-1;
    if(LDtl>1) LDdBad.push('还有第二份计时默认值字面量（'+LDtl+' 处）');
    if(DAY_LETTERS.length!==6) LDdBad.push('训练日字母表长度 '+DAY_LETTERS.length);
    if(DEFAULT_DAY_IDS.join('')!=='ABCD') LDdBad.push('四天兜底不是字母表前四项：'+DEFAULT_DAY_IDS.join(''));
    var LDst0=state.structure; state.structure={dayDefs:[]};
    if(dayIds().join('')!==DEFAULT_DAY_IDS.join('')) LDdBad.push('没有结构时 dayIds() 不取兜底名单');
    state.structure=LDst0;
    if(String(saveStructure).indexOf('DAY_LETTERS')<0) LDdBad.push('结构编辑器的天数上限不再跟着字母表走（写回了裸 6）');
    var LDal=LDsrc.split("'A','B','C'").length-1;
    if(LDal>1) LDdBad.push('字母表被抄了第二份（'+LDal+' 处）');
    if(window.THEME_IDS.indexOf(window.DEFAULT_THEME)<0) LDdBad.push('默认主题不在注册表里：'+window.DEFAULT_THEME);
    var LDlg0=state.lang; state.lang=window.DEFAULT_LANG;
    if(L('LD中','LDEN')!=='LD中') LDdBad.push('默认语言不是 L() 的中文分支：'+window.DEFAULT_LANG);
    state.lang=LDlg0;
    if(LDsrc.indexOf("||'dark'")>=0 || LDsrc.indexOf("||'zh'")>=0) LDdBad.push('还有手抄的语言/主题兜底');
    T('LD15 默认值与名单只有一份：模式兜底走 PROTO_FALLBACK、计时默认走 defaultTimerCfg()、训练日字母走 DAY_LETTERS、'
      + '出厂语言/主题走 window.DEFAULT_*（以前这四样各抄 2~7 处，改一处就出现「同版本不同机器默认不一样」）',
      LDdBad.length===0, LDdBad.join(' ; ')||('兜底组数='+PROTO_FALLBACK.sets+' 字母表='+DAY_LETTERS.join('')+' 默认='+window.DEFAULT_THEME+'/'+window.DEFAULT_LANG));

    /* ---------- TD1 计时档钮与设置副标题的时长是算出来的（v0.29 UI 债） ----------
       期望串写死在这里，不拿 fmtDur 去验 fmtDur（那等于什么都没说）。
       这一族坏法叫「文案抄了一份默认值」：改了 defaultTimerCfg 或老存档带着别的秒数时，
       按钮上那三个数还是出厂的 5m/2.5m/75s —— 点了却是别的时长，用户只会觉得计时器不准。 */
    var TDl0=state.lang, TDt0={T1:state.timerCfg.T1,T2:state.timerCfg.T2,T3:state.timerCfg.T3};
    var TDbad=[], TDrows=[];
    function TDpaint(o){
      state.timerCfg.T1=o.T1; state.timerCfg.T2=o.T2; state.timerCfg.T3=o.T3; state.lang=o.lang;
      applyChrome();
      var chips=['T1','T2','T3'].map(function(t){
        var b=document.getElementById('chip'+t); return b?b.textContent:'(缺#chip'+t+')'; }).join('/');
      var s=document.getElementById('setTimerS');
      return {chips:chips,sub:s?s.textContent:'(缺#setTimerS)'};
    }
    var TDa=TDpaint({T1:300,T2:150,T3:75,lang:'zh'});
    var TDb=TDpaint({T1:420,T2:90,T3:30,lang:'zh'});
    var TDc=TDpaint({T1:420,T2:90,T3:30,lang:'en'});
    if(TDa.chips!=='T1·5m/T2·2.5m/T3·75s') TDbad.push('出厂秒数下档钮是「'+TDa.chips+'」');
    if(TDa.sub!=='T1 5分钟 · T2 2.5分钟 · T3 75秒 · 到点蜂鸣与震动') TDbad.push('中文副标题是「'+TDa.sub+'」');
    if(TDb.chips!=='T1·7m/T2·90s/T3·30s') TDbad.push('改成 420/90/30 后档钮还是「'+TDb.chips+'」');
    if(TDb.sub!=='T1 7分钟 · T2 90秒 · T3 30秒 · 到点蜂鸣与震动') TDbad.push('中文副标题没跟着改：「'+TDb.sub+'」');
    if(TDc.chips!=='T1·7m/T2·90s/T3·30s') TDbad.push('英文态档钮是「'+TDc.chips+'」');
    if(TDc.sub!=='T1 7m · T2 90s · T3 30s · beep & haptics') TDbad.push('英文副标题是「'+TDc.sub+'」');
    state.timerCfg.T1=TDt0.T1; state.timerCfg.T2=TDt0.T2; state.timerCfg.T3=TDt0.T3;
    state.lang=TDl0; var TDz=TDpaint({T1:TDt0.T1,T2:TDt0.T2,T3:TDt0.T3,lang:TDl0});
    /* 本条自己改过 state.timerCfg / state.lang：留脏会让后面几段的判据基线漂移，所以自查还原 */
    if(state.timerCfg.T1!==TDt0.T1||state.timerCfg.T2!==TDt0.T2||state.timerCfg.T3!==TDt0.T3
       ||state.lang!==TDl0) TDbad.push('TD1 没把 timerCfg/lang 还原干净');
    T('TD1 计时档钮与设置副标题从 state.timerCfg 现算：出厂 300/150/75 与改成 420/90/30 各写各的数，'
      + '中英两态都跟着（文案里那份抄本已删）',
      TDbad.length===0, TDbad.join(' ; ')||('出厂='+TDa.chips+' / 改后='+TDb.chips+' / 还原='+TDz.chips));

    /* ---------- LD16 切语言不留中文（逻辑债 #21） ---------- */
    var LDi2Bad=[];
    var LDiIds=['pAgeNote','barLbl','snapHeadLbl'];
    LDiIds.forEach(function(id){
      var pair=I18N_NODES[id];
      if(!pair || pair.length!==2 || !String(pair[0]||'') || !String(pair[1]||'')) LDi2Bad.push(id+' 没登记两条非空词');
    });
    var LDlcw=window.LANG_CACHED_SELECTS||[];
    if(!LDlcw.length) LDi2Bad.push('取不到 window.LANG_CACHED_SELECTS（重刷名单没了出处）');
    setLang('en'); applyChrome();
    LDiIds.forEach(function(id){
      var el=document.getElementById(id);
      var t=el?String(el.textContent):'(无节点)';
      if(HAN.test(t)) LDi2Bad.push(id+' 切英文仍是中文：'+t.slice(0,18));
    });
    /* 筛选下拉只填一次（dataset.filled 省一次重建），所以切语言必须重刷 —— 先把它们做旧成中文 */
    ['stratTier','progLibFam'].forEach(function(id){
      var el=document.getElementById(id);
      if(el && el.options[0]){ el.dataset.filled='1'; el.options[0].textContent='Tier · 全部'; }
    });
    setLang('zh'); setLang('en');
    var LDsel=document.getElementById('stratTier');
    if(!LDsel || !LDsel.options[0]) LDi2Bad.push('没有 #stratTier 首项（判据无从下手）');
    else if(String(LDsel.options[0].textContent)!=='TIER · ALL') LDi2Bad.push('切语言后筛选首项仍是：'+String(LDsel.options[0].textContent));
    LDlcw.forEach(function(id){
      var e2=document.getElementById(id);
      if(e2 && e2.options[0] && HAN.test(String(e2.options[0].textContent))) LDi2Bad.push(id+' 首项仍是中文：'+String(e2.options[0].textContent).slice(0,18));
    });
    setLang('zh'); applyChrome();
    LDiIds.forEach(function(id){
      var el=document.getElementById(id);
      if(!I18N_NODES[id]) return;   /* 没登记的上面已经记过账：这里再取 [0] 会让整段抛错 */
      if(el && String(el.textContent)!==String(I18N_NODES[id][0])) LDi2Bad.push(id+' 切回中文没复原词对：'+String(el.textContent).slice(0,18));
    });
    if(String(setLang).indexOf('refreshLangSelects')<0) LDi2Bad.push('setLang 不再调用 refreshLangSelects()');
    T('LD16 切语言不留中文：静态漏网三格登记进 I18N_NODES，「填一次就缓存」的筛选下拉由 setLang 统一重刷'
      + '（旧写法是切了英文只有那几格还是中文，而 S25 只查「登记了却挂不上」这个方向，反方向没有任何东西会红）',
      LDi2Bad.length===0, LDi2Bad.join(' ; ')||('登记 '+LDiIds.join('/')+' + 重刷 '+LDlcw.length+' 个下拉'));

    /* ---------- LD17 写盘失败离桥也要出声（逻辑债 #9） ---------- */
    var LDwBad=[];
    var LDwe0=window.__lastWriteError, LDse0=_storeErrShown;
    window.__lastWriteError=''; _storeErrShown=false;
    var LDsp=Storage.prototype, LDspOld=LDsp.setItem;
    LDsp.setItem=function(k,v){ if(k===LS_PREFS) throw new Error('LD配额满了'); return LDspOld.call(this,k,v); };
    writeSlice('prefs','{"ld":1}');
    LDsp.setItem=LDspOld;
    if(!window.__lastWriteError) LDwBad.push('写失败没有记进 __lastWriteError');
    if(!writeError()) LDwBad.push('离桥环境读不到写失败（那条早退又回来了）');
    writeSlice('prefs','{"ld":2}');
    if(window.__lastWriteError!=='') LDwBad.push('一笔成功后没有解除闭锁：'+window.__lastWriteError);
    if(String(watchStoreError).replace(/[ ]/g,'').indexOf('if(!window.AndroidBridge')>=0) LDwBad.push('watchStoreError 仍对离桥环境早退');
    if(String(writeSlice).indexOf('__lastStoreError')<0) LDwBad.push('写侧不再留总痕（与 BD5 的读侧不对称）');
    window.__lastWriteError=LDwe0; _storeErrShown=LDse0;
    T('LD17 写盘失败两侧都出得了声：桥外 localStorage 抛错也记 __lastWriteError、writeError() 读得到、'
      + '写成功一笔就解除闭锁（旧写法开头就 if(!AndroidBridge) return，浏览器里丢数据全程无声）',
      LDwBad.length===0, LDwBad.join(' ; ')||('离桥痕可读 + 成功解锁'));

    /* ---------- LD18 导出失败要说得出原因（逻辑债 #10） ---------- */
    var LDx2Bad=[];
    var LDeuOld=exportUnifiedCsv;
    try{ toast(''); }catch(x){}
    exportUnifiedCsv=function(){ throw new Error('LD导出炸了'); };
    doExportCsv();
    exportUnifiedCsv=LDeuOld;
    var LDtx2=LDtt();
    if(LDtx2.indexOf('导出失败')<0) LDx2Bad.push('失败没有说「导出失败」：'+LDtx2);
    if(LDtx2.indexOf('LD导出炸了')<0) LDx2Bad.push('原因被吞了，回执只剩四个字：'+LDtx2);
    if(String(doExportCsv).indexOf('String(e')<0) LDx2Bad.push('doExportCsv 不再带 e');
    T('LD18 导出失败的回执带上真实原因（与计划/JSON/日志那三条导出出口同一口径；旧写法只说「导出失败」，'
      + '现场排障时用户和开发者都只能猜是 Blob、桥还是序列化炸的）',
      LDx2Bad.length===0, LDx2Bad.join(' ; ')||('回执='+LDtx2.slice(0,40)));

    /* ---------- LD19 对比周读数不产 NaN（逻辑债 #27） ---------- */
    var LDaBad=[];
    var LDgeOld=document.getElementById;
    [['',0],['3',3],['abc',0],['-2',0],['0',0],['12',12]].forEach(function(p){
      document.getElementById=function(id){ return id==='advWeek'?{value:p[0]}:LDgeOld(id); };
      var got=advCurWeek();
      document.getElementById=LDgeOld;
      if(got!==p[1]) LDaBad.push("'"+p[0]+"'→"+String(got)+'（应 '+p[1]+'）');
      if(typeof got!=='number' || !isFinite(got)) LDaBad.push("'"+p[0]+"' 出来不是有限数："+String(got));
    });
    document.getElementById=LDgeOld;
    T('LD19 下周建议的对比周读数永远是有限非负整数：缺值 / 非数 / 负数一律当「没选周」0，'
      + '不再把 NaN 传进档位判定与表头（NaN 一路往下走就是「面板空白但没有任何一句为什么」）',
      LDaBad.length===0, LDaBad.join(' ; ')||('六种取值全部收敛'));

    /* 出段还原：state、四个分片、归档缓存都拉回进段前，后面的重载轮看不到 LD 段痕迹 */
    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(LDak).forEach(function(k){ state[k]=LDak[k]; });
    flushSave();
    if(LDp0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,LDp0);
    if(LDw0===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK,LDw0);
    if(LDl0===null) localStorage.removeItem(LS_LIB); else localStorage.setItem(LS_LIB,LDl0);
    if(LDa0===null) localStorage.removeItem(LS_ARCHIVE); else localStorage.setItem(LS_ARCHIVE,LDa0);
    _archiveCache=null;
    applyChrome(); renderAll();
    T('LD13 出段还原：账本与四个分片（含第四分片的归档）回到进段前，本段开的面板都收干净、语言仍是中文',
      JSON.stringify(state)===LDsnap && localStorage.getItem(LS_PREFS)===LDp0
      && localStorage.getItem(LS_WORK)===LDw0 && localStorage.getItem(LS_LIB)===LDl0
      && localStorage.getItem(LS_ARCHIVE)===LDa0 && state.lang==='zh'
      && !document.querySelector('.sheet.on'),
      'state 同='+(JSON.stringify(state)===LDsnap)
      +' 分片同='+(localStorage.getItem(LS_WORK)===LDw0)+','+(localStorage.getItem(LS_ARCHIVE)===LDa0)
      +' 仍开着='+String(Array.prototype.map.call(document.querySelectorAll('.sheet.on'),function(s){return s.id;}).join(',')));

    /* ===== B. 动作选择链（v0.29 UI 债第三批）：mv-btn → 逐层下钻 → pickAct 落账 =====
       这条链的按钮全是 renderBrowse / actRow 用字符串拼出来的，全站只有它藏在 JS 拼串里；
       层级 0→1→2、crumb、返回钮、搜索命中、两种模式的分流共用同一段生成代码。
       静态侧 S36 逐个核对 231 处内联事件的函数名在不在，这一段核对**点下去之后**：
       账改没改、三个标签跟没跟、盘落没落（少了那句 save() 只红这一层）、
       manage 与 pick 串没串、editIdx 失效时会不会越界写、加练那条腿进的是不是选择态。 */
    var BSnap=JSON.stringify(state), BP0=localStorage.getItem(LS_PREFS),
        BW0=localStorage.getItem(LS_WORK), BL0=localStorage.getItem(LS_LIB);
    var Bex=(day().exercises||[]);
    var Bt=null, BtP=null;
    state.lib.cats.forEach(function(c){
      (c.acts||[]).forEach(function(a){
        if(!a || !a.en) return;
        if(!Bt) Bt={c:c,a:a};
        /* 预填那条腿要求「区间下限不是 1」——否则把 reps 摆成 1 再预填，
           期望值与起点相同，断言恒真（AGENTS §7 第 4 条：探针自己失效比没探针更坏）。 */
        if(!BtP){
          var mm=String(a.reps||'').match(/([0-9]+)[^0-9]+([0-9]+)/);
          if(mm && Number(mm[1])>1) BtP={c:c,a:a,lo:Number(mm[1])};
        }
      });
    });
    closeAllSheets();
    var Bbad1=[];
    if(Bex.length<1) Bbad1.push('当天没有动作行（判据无从下手）');
    if(!Bt) Bbad1.push('动作库里没有任何带 en 名的动作');
    T('B0 选择链的两个前提在位：当天至少一行动作、库里至少一个可点动作（缺一个下面六条就无从跑起）',
      Bbad1.length===0, Bbad1.join(' ; ')||(Bex.length+' 行 / 库 '+libTotal()+' 动作'));

    if(Bt && Bex.length>=1){
      /* ---------- B1 选择态：两层都该在（这是全站唯一合法的父子同屏） ---------- */
      var Bbad2=[];
      openEditor(0);
      var Bi0=editIdx, Bmv0=day().exercises[0].mv, Bcat0=day().exercises[0].cat;
      openBrowse('pick');
      var Bttl1=String(document.getElementById('brTitle').textContent||'').trim();
      var Bn0=document.querySelectorAll('#brBody .br-row').length;
      if(BR.mode!=='pick') Bbad2.push('BR.mode='+BR.mode+'（编辑器那颗钮该进选择态）');
      if(BR.level!==0) Bbad2.push('进来停在层级 '+BR.level);
      if(!document.getElementById('brSheet').classList.contains('on')) Bbad2.push('动作面板没开');
      if(!document.getElementById('edSheet').classList.contains('on')) Bbad2.push('编辑器让位了（选择器是它的子层，两层都该在）');
      if(Bttl1!==String(L('选择动作','PICK MOVEMENT'))) Bbad2.push('标题不是选择态：'+Bttl1);
      if(Bn0!==state.lib.domains.length) Bbad2.push('层级 0 行数 '+Bn0+' ≠ 功能域数 '+state.lib.domains.length);
      if(!document.getElementById('brBack').classList.contains('off')) Bbad2.push('层级 0 的返回钮没置灰（点了会跳空层）');
      T('B1 mv-btn 进的是选择态：BR.mode/层级 0/标题三样对得上，且编辑器与选择器两层同屏（唯一的合法父子）',
        Bbad2.length===0, Bbad2.join(' ; ')||('层级 0 '+Bn0+' 行 = 功能域数'));

      /* ---------- B2 逐层下钻：行数、meta、crumb 三段都跟着数据走 ---------- */
      var Bbad3=[];
      brGo(1, Bt.c.domain);
      var Bd=domOf(Bt.c.domain);
      var Bcats=state.lib.cats.filter(function(c){ return c.domain===Bt.c.domain; });
      var Bn1=document.querySelectorAll('#brBody .br-row').length;
      var Bcr1=document.querySelectorAll('#brCrumb button').length;
      if(BR.level!==1 || BR.dom!==Bt.c.domain) Bbad3.push('brGo(1) 没落到功能域层：'+BR.level+'/'+String(BR.dom));
      if(Bn1!==Bcats.length) Bbad3.push('层级 1 行数 '+Bn1+' ≠ 该域分类数 '+Bcats.length);
      if(Bcr1!==2) Bbad3.push('层级 1 的 crumb 有 '+Bcr1+' 段（应为 功能域 › 该域）');
      brGo(2, Bt.c.domain, Bt.c.cat);
      var Bn2=document.querySelectorAll('#brBody .br-row').length;
      var Bcr2=document.querySelectorAll('#brCrumb button').length;
      var Bmeta=String(document.getElementById('brMeta').textContent||'');
      var Bcur=document.querySelectorAll('#brCrumb button.cur').length;
      if(BR.level!==2 || BR.cat!==Bt.c.cat) Bbad3.push('brGo(2) 没落到动作层：'+BR.level+'/'+String(BR.cat));
      if(Bn2!==Bt.c.acts.length) Bbad3.push('层级 2 行数 '+Bn2+' ≠ 该分类动作数 '+Bt.c.acts.length);
      if(Bmeta.indexOf(String(Bt.c.acts.length))<0) Bbad3.push('meta 没报动作数：'+Bmeta);
      if(Bcr2!==3) Bbad3.push('层级 2 的 crumb 有 '+Bcr2+' 段（应为 域 › 分类 › 当前）');
      if(Bcur!==1) Bbad3.push('crumb 里当前段应当恰好 1 个，实为 '+Bcur);
      if(document.getElementById('brBack').classList.contains('off')) Bbad3.push('下钻后返回钮还置灰');
      T('B2 功能域 → 分类 → 动作逐层下钻：每层行数等于该层数据、crumb 段数与高亮跟着层级、meta 报动作数',
        Bbad3.length===0, Bbad3.join(' ; ')||(String(Bd?(state.lang==='en'?Bd.en:Bd.zh):Bt.c.domain)+' → '+Bt.c.acts.length+' 动作'));

      /* ---------- B3 pickAct：账、三个标签、落盘、次数预填一次改掉四样 ---------- */
      var Bbad4=[];
      var BsaveN=0, BsaveOld=save;
      save=function(x){ BsaveN++; return BsaveOld(x); };
      pickAct(Bt.c.cat, Bt.a.en);
      save=BsaveOld;
      var Be=day().exercises[0];
      var Bname=String(document.getElementById('edMvName').textContent||'').trim();
      var Bti=String(document.getElementById('edTitle').textContent||'').trim();
      var Bpth=String(document.getElementById('edMvPath').textContent||'').trim();
      if(Be.mv!==Bt.a.en || Be.cat!==Bt.c.cat) Bbad4.push('账本没落：mv='+String(Be.mv)+' cat='+String(Be.cat));
      if(BsaveN<1) Bbad4.push('pickAct 没调 save()（改了内存不落盘，杀进程即静默丢）');
      if(Bname!==String(mvLabel(Bt.a.en))) Bbad4.push('动作名标签没跟：'+Bname);
      if(Bti!==String(mvLabel(Bt.a.en))) Bbad4.push('面板标题没跟：'+Bti);
      if(Bpth.indexOf(String(catLabel(Bt.c)))<0) Bbad4.push('路径标签没跟：'+Bpth);
      if(document.getElementById('brSheet').classList.contains('on')) Bbad4.push('选完动作选择器没收');
      if(!document.getElementById('edSheet').classList.contains('on')) Bbad4.push('选完把编辑器一起收了（回不去改载荷）');
      flushSave();
      if(String(localStorage.getItem(LS_WORK)||'').indexOf(Bt.a.en)<0) Bbad4.push('落盘的账本里没有新动作名');
      /* 次数预填：只有「没填过」（空 / 1）才动它，填过的次数不许被选动作覆盖 */
      if(!BtP) Bbad4.push('库里找不到区间下限大于 1 的动作（预填腿无从验起）');
      var Brn=0, BsaveOld2=save;
      save=function(x){ Brn++; return BsaveOld2(x); };
      day().exercises[0].reps=6;
      if(BtP) pickAct(BtP.c.cat, BtP.a.en);
      if(BtP && Be.reps!==6) Bbad4.push('已填过的次数被预填覆盖：6 → '+Be.reps);
      day().exercises[0].reps=1;
      if(BtP) pickAct(BtP.c.cat, BtP.a.en);
      if(BtP && Be.reps!==BtP.lo) Bbad4.push('reps=1 时没按区间下限预填：'+Be.reps+'（'+BtP.a.reps+' 的下限是 '+BtP.lo+'）');
      save=BsaveOld2;
      if(BtP && Brn<2) Bbad4.push('两次预填测试只落盘 '+Brn+' 次');
      T('B3 pickAct 四样一起改对：账本 mv/cat、三个标签、当日分片里真读得到；次数只在空 / 1 时按区间下限预填，填过的不覆盖',
        Bbad4.length===0, Bbad4.join(' ; ')||(Bt.a.en+' / 落盘 save() '+BsaveN+' 次 / '+BtP.a.reps+' 预填 '+BtP.lo+'、已填的 6 未动'));

      /* ---------- B4 管理态同一条腿走的是编辑，不动账 ---------- */
      var Bbad5=[];
      var BmvKeep=day().exercises[0].mv;
      openBrowse('manage');
      if(BR.mode!=='manage') Bbad5.push('openBrowse(manage) 后 BR.mode='+BR.mode);
      var Bn3=document.querySelectorAll('#brBody .br-row').length;
      if(Bn3!==state.lib.domains.length+1) Bbad5.push('管理态层级 0 行数 '+Bn3+'（功能域 '+state.lib.domains.length+' + 新增分类 1）');
      pickAct(Bt.c.cat, Bt.a.en);
      if(day().exercises[0].mv!==BmvKeep) Bbad5.push('管理态点动作行竟然改了账');
      if(!document.getElementById('actSheet').classList.contains('on')) Bbad5.push('管理态没转到动作编辑面板');
      if(String(document.getElementById('actEn').value||'')!==Bt.a.en) Bbad5.push('动作编辑表单装的不是被点的那个动作：'+String(document.getElementById('actEn').value));
      T('B4 同一条 pickAct 在 manage 态转到动作编辑（表单装的正是那一个）、不改账本（模式分流串了就是「改库按钮写进行情」）',
        Bbad5.length===0, Bbad5.join(' ; ')||('管理态 '+Bn3+' 行（含新增分类）/ 账未动'));
      closeAllSheets();

      /* ---------- B5 搜索：命中数、空态、退回先清词 ---------- */
      var Bbad6=[];
      /* 换一个动作来验：B3 已经落过一次账，再点同一个就变成恒真断言。 */
      var Bt2=null;
      state.lib.cats.forEach(function(c){
        (c.acts||[]).forEach(function(a){ if(!Bt2 && a && a.en && a.en!==Bt.a.en) Bt2={c:c,a:a}; });
      });
      if(!Bt2) Bbad6.push('库里凑不出第二个动作（搜索腿无从验证）');
      var Bq=Bt2?String(Bt2.a.en||'').slice(0,4).toLowerCase():'';
      closeAllSheets(); openEditor(0); openBrowse('pick');
      brSearch(Bq);
      var Bh1=document.querySelectorAll('#brBody .br-row').length;
      var BhN=brSearchHits().length;
      if(BR.q!==Bq) Bbad6.push('BR.q='+BR.q);
      if(BhN<1) Bbad6.push('用刚选过的动作名前缀「'+Bq+'」搜不到任何命中');
      if(Bh1!==BhN) Bbad6.push('命中 '+BhN+' 条但面板画了 '+Bh1+' 行');
      if(String(document.getElementById('brCrumb').textContent||'').indexOf(L('搜索','Search'))<0) Bbad6.push('crumb 没切到搜索态');
      if(Bt2) pickAct(Bt2.c.cat, Bt2.a.en);
      if(Bt2 && day().exercises[0].mv!==Bt2.a.en) Bbad6.push('搜索命中的行选不进（走的是另一条腿）');
      openBrowse('pick');
      brSearch('zzz 不可能存在的动作名 zzz');
      var Bempty=document.querySelector('#brBody .br-empty');
      if(!Bempty) Bbad6.push('零命中没有空态（只剩一片白，用户以为卡住）');
      brUp();
      if(BR.q!=='') Bbad6.push('搜索态按返回没先清掉关键词：'+BR.q);
      brSearch('');
      T('B5 搜索腿：命中数=行数、crumb 进搜索态、命中行与下钻行走同一条 pickAct（换个动作才验得出）、零命中有空态、返回先清词',
        Bbad6.length===0, Bbad6.join(' ; ')||('「'+Bq+'」命中 '+BhN+' 条'));

      /* ---------- B6 brUp 逐层回退 + B7 editIdx 失效保护 ---------- */
      var Bbad7=[], Bbad8=[];
      /* BR.dom / BR.cat 在回退后留着旧值 —— 这是现状：renderBrowse 只在 level>=1 / >=2
         时才读它们，所以层级一降下去就没人再看。这里断言的是**看得见的东西**：
         层级、行号、crumb 段数、到顶置灰，而不是去补一次清空。 */
      brGo(2, Bt.c.domain, Bt.c.cat);
      brUp();
      var Br1=document.querySelectorAll('#brBody .br-row').length;
      var Bc7=document.querySelectorAll('#brCrumb button').length;
      if(BR.level!==1) Bbad7.push('层级 2 退回后停在 '+BR.level);
      if(Br1!==Bcats.length) Bbad7.push('退回分类层画了 '+Br1+' 行（该 '+Bcats.length+'）');
      if(Bc7!==2) Bbad7.push('退回分类层 crumb 有 '+Bc7+' 段');
      brUp();
      var Br0=document.querySelectorAll('#brBody .br-row').length;
      var Bc8=document.querySelectorAll('#brCrumb button').length;
      if(BR.level!==0) Bbad7.push('层级 1 退回后停在 '+BR.level);
      if(Br0!==state.lib.domains.length) Bbad7.push('退回顶层画了 '+Br0+' 行（该 '+state.lib.domains.length+'）');
      if(Bc8!==1) Bbad7.push('顶层 crumb 有 '+Bc8+' 段');
      if(!document.getElementById('brBack').classList.contains('off')) Bbad7.push('回到层级 0 返回钮没重新置灰');
      brGo(1, Bt.c.domain); brGo(2, Bt.c.domain, Bt.c.cat);
      brUp(); brUp();
      if(BR.level!==0) Bbad7.push('连着退两次没回到顶层：'+BR.level);
      T('B6 brUp 逐层回退：每一退都换回上一层的行数与 crumb 段数、到顶重新置灰（停在空层就是白屏）',
        Bbad7.length===0, Bbad7.join(' ; ')||('分类层 '+Br1+' 行 → 顶层 '+Br0+' 行'));
      var BmvBefore=day().exercises[0].mv;
      openBrowse('pick');
      editIdx=-1;
      pickAct(Bt.c.cat, 'Uiv Probe Movement');
      editIdx=Bi0;
      if(day().exercises[0].mv!==BmvBefore) Bbad8.push('没有编辑行时 pickAct 竟然写进了 0 行');
      if(document.getElementById('brSheet').classList.contains('on')) Bbad8.push('越界防护那条腿没收起选择器');
      T('B7 editIdx 失效（面板还开着但行已被删）时 pickAct 只收面板、不越界写第 0 行',
        Bbad8.length===0, Bbad8.join(' ; ')||('未写入，mv 仍是 '+BmvBefore));
      closeAllSheets();

      /* ---------- B8 加练那条腿：新行 mv 空 → 进选择态 → 选完标签从「未关联」变成路径 ---------- */
      var Bbad9=[];
      var BnBefore=day().exercises.length;
      addExercise();
      if(day().exercises.length!==BnBefore+1) Bbad9.push('加练没追加一行');
      if(BR.mode!=='pick') Bbad9.push('加练后没进选择态：'+BR.mode);
      if(!document.getElementById('brSheet').classList.contains('on')) Bbad9.push('加练后选择器没开');
      if(String(document.getElementById('edMvPath').textContent||'').indexOf(L('未关联分类','No category'))<0) Bbad9.push('空 mv 的新行没有「未关联分类」提示');
      pickAct(Bt.c.cat, Bt.a.en);
      var Bnew=day().exercises[day().exercises.length-1];
      if(Bnew.mv!==Bt.a.en) Bbad9.push('给新行选动作没落账');
      if(String(document.getElementById('edMvPath').textContent||'').indexOf(String(catLabel(Bt.c)))<0) Bbad9.push('新行选完路径没跟：'+String(document.getElementById('edMvPath').textContent));
      T('B8 加练直接进选择态：空 mv 的新行先显示「未关联分类」，选完当场变成 域 › 分类',
        Bbad9.length===0, Bbad9.join(' ; ')||(BnBefore+' → '+day().exercises.length+' 行'));
      closeAllSheets();
    }

    /* 出段还原：本段真改了当日账（选了动作、加了一行），不留痕给后面的重载轮与总数闸门 */
    (function(){ var o=JSON.parse(BSnap); Object.keys(state).forEach(function(k){ delete state[k]; }); Object.keys(o).forEach(function(k){ state[k]=o[k]; }); })();
    flushSave();
    if(BP0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,BP0);
    if(BW0===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK,BW0);
    if(BL0===null) localStorage.removeItem(LS_LIB); else localStorage.setItem(LS_LIB,BL0);
    editIdx=-1;
    applyChrome(); renderAll(); closeAllSheets();
    T('B9 出段还原：选择链改过的账与三个分片回到进段前，面板收干净、语言仍是中文',
      JSON.stringify(state)===BSnap && localStorage.getItem(LS_PREFS)===BP0
      && localStorage.getItem(LS_WORK)===BW0 && localStorage.getItem(LS_LIB)===BL0
      && state.lang==='zh' && !document.querySelector('.sheet.on') && editIdx===-1,
      'state 同='+(JSON.stringify(state)===BSnap)
      +' 分片同='+(localStorage.getItem(LS_WORK)===BW0)+','+(localStorage.getItem(LS_LIB)===BL0));

    /* ===== TM. 会员徽记 + 状态监控总开关（默认关） =====
       这一段的立场：teleOn 只收「入口」，一格已存的遥测值都不碰，也不改任何判定。
       所以每条腿都成对看——外观变没变 + state / prefs 分片有没有被顺手改写。 */
    SECT='TM';
    var TMs0=JSON.stringify(state), TMp0=localStorage.getItem(LS_PREFS);
    /* 钉一个一定能开面板的落点：前面几段把 day/week 留在什么状态不保证，
       openTeleSheet 里 wk()[day] 取不到格子会抛——那一刻 Z0 接管，本段其余断言一起消失，
       红的是「驱动器没跑完」而不是「闸门没了」，反向验证就白做。 */
    state.day='A'; state.week='1';
    var TMstar=String.fromCharCode(0x2726)+'Pro';
    var TMb=document.querySelector('.brand-line .pro-mark');
    T('TM1 右上角是一颗会员徽记：文本 ✦Pro、与 h1 平级挂在 .brand-line 下（挤进标题里就会被四档宽度的裁切检查抓没）、徽记自身不带版本号、旧写法那个裸 em 已经不在',
      !!TMb && TMb.textContent===TMstar
      && TMb.parentNode.className.indexOf('brand-line')>=0 && !!TMb.parentNode.querySelector('h1')
      && TMb.textContent.indexOf('v'+EXP)<0 && !document.querySelector('.brand-line h1 em'),
      TMb?(TMb.textContent+' / 父='+TMb.parentNode.className):'无 .pro-mark');

    var TMpod=document.getElementById('teleBrief');
    renderTelemetry();
    /* 旧存档那条腿单独点一下：删掉这个键 = 「这份账里从来没写过开关」。
       回填判据从 ===true 翻成 !==false 的话，这一句就把每一个老用户的面板偷偷打开，
       而「默认关闭」正是这一版的承诺——新建账走的是 fresh 分支，看不出这件事，所以必须现点。 */
    delete state.teleOn;
    ensureShape();
    var TMe1=teleOn();
    T('TM2 状态监控默认关（两条路都要关着）：新建账 teleOn() 为假；旧存档缺这个键时 ensureShape 回填成「关」而不是「开」。外观侧首页 STATUS 舱带上 .hidden（舱还在 DOM 里，只是点不进去），设置页那颗开关写着 OFF',
      teleOn()===false && TMe1===false && !!TMpod && TMpod.classList.contains('hidden')
      && TMpod.classList.contains('status-pod')
      && String(txt('teleOnBtn')||'').indexOf('OFF')>=0,
      '新建账='+teleOn()+' 旧存档回填='+TMe1+' 舱class='+(TMpod?TMpod.className:'无')+' 钮='+(txt('teleOnBtn')||'无'));

    /* 关着的时候，入口不止首页一颗舱钮：脚本直呼 openTeleSheet() 也不该进得去。
       这条腿一半的重量在「一个字节都没动」——闸门如果只是藏了面板，state 会照原样。 */
    var TMgBad=[];
    var TMg0=JSON.stringify(state);
    closeAllSheets();
    openTeleSheet();
    if(document.querySelector('#teleSheet.on')) TMgBad.push('关着还能把面板打开');
    if(String(txt('toast')||'').indexOf('我的档案')<0) TMgBad.push('拒绝时没指路（"'+txt('toast')+'"）');
    if(JSON.stringify(state)!==TMg0) TMgBad.push('被拒的一次点击仍然改了账');
    if(document.getElementById('teleBrief').classList.contains('on')) TMgBad.push('舱钮自己亮了');
    T('TM3 开关关掉后 openTeleSheet() 拒绝进入：面板没开、回执说得出去哪打开（人话，不是 undefined）、账本一个字节都没变',
      TMgBad.length===0, TMgBad.join(' ; ')||('拒收 '+String(txt('toast')).slice(0,24)));

    /* 真 DOM 点击：这是全站唯一入口，点了没接线的话上面两条腿照样全绿。 */
    var TMcBad=[];
    var TMbtn=document.getElementById('teleOnBtn');
    openSettings();
    if(!TMbtn) TMcBad.push('开关按钮不在设置页');
    else{
      TMbtn.click();
      if(teleOn()!==true) TMcBad.push('点下去没开');
      if((localStorage.getItem(LS_PREFS)||'').indexOf('"teleOn":true')<0) TMcBad.push('开了但没落进 prefs 分片（重开就丢）');
      if(document.getElementById('teleBrief').classList.contains('hidden')) TMcBad.push('开了舱还藏着');
      if(String(txt('teleOnBtn')||'').indexOf('ON')<0||String(txt('teleOnBtn')||'').indexOf('OFF')>=0)
        TMcBad.push('按钮文案没跟着翻（"'+txt('teleOnBtn')+'"）');
      closeAllSheets();
      openTeleSheet();
      if(!document.querySelector('#teleSheet.on')) TMcBad.push('开了还是进不去面板——闸门变成死锁');
      closeAllSheets();
      TMbtn.click();
      if(teleOn()!==false) TMcBad.push('第二下没关回去');
      if((localStorage.getItem(LS_PREFS)||'').indexOf('"teleOn":true')>=0) TMcBad.push('关回去但盘上仍留着 true');
    }
    T('TM4 设置页那颗开关真接在线上：点一下开（落进 prefs 分片、舱恢复可点、面板进得去）、再点一下关回去，文案跟着翻',
      TMcBad.length===0, TMcBad.join(' ; ')||('开→落盘→进面板→关 全程走真 click'));

    /* 体重趋势：关掉状态监控之后唯一活着的那一行。三件事分开钉——
       数对不对（首末两週 + 净变化）、只读（不许改账）、位置对不对（在运动员页，不在遥测面板里）。 */
    var TMbBad=[];
    var TMwk3=Object.keys(state.weeks).filter(function(k){ return /^[0-9]+$/.test(k); })
                    .sort(function(a,b){ return +a-+b; }).slice(0,3);
    var TMpad=function(w){ return 'W'+('0'+w).slice(-2); };
    /* 先把**所有**周的体重抹干净再摆三个点：只盖住前三周的话端点仍落在别人身上，
       「▼0.6」「持平」「不足两周」三种写法永远只能对上最后那一种。 */
    var TMwipeAll=function(){ Object.keys(state.weeks).forEach(function(w){
      var a=(state.weeks[w]||{}).A||{}; if(a.bio) delete a.bio.bw; delete a.bw; }); };
    var TMput=function(i,v){ var o=state.weeks[TMwk3[i]]; if(!o) o=state.weeks[TMwk3[i]]={};
      if(!o.A) o.A={}; if(!o.A.bio) o.A.bio={}; o.A.bio.bw=v; };
    var TMdrop=function(i){ var o=(state.weeks[TMwk3[i]]||{}).A||{};
      if(o.bio) delete o.bio.bw; delete o.bw; };
    TMwipeAll(); TMput(0,80.0); TMput(1,79.6); TMput(2,79.4);
    var TMr0=JSON.stringify(state);
    renderBwHint();
    var TMh=String(txt('bwHint')||'');
    if(TMh.indexOf(TMpad(TMwk3[0]))<0 || TMh.indexOf('80.0')<0 || TMh.indexOf('79.4')<0)
      TMbBad.push('首末两点没照实写：'+TMh.slice(0,60));
    if(TMh.indexOf('▼0.6')<0) TMbBad.push('净变化没算成下降 0.6：'+TMh.slice(0,60));
    if(TMh.indexOf('3 '+L('记','LOG'))<0) TMbBad.push('被抹掉的周仍算了进来：'+TMh.slice(0,60));
    if(JSON.stringify(state)!==TMr0) TMbBad.push('这一行是只读提示，但它动了账');
    TMput(2,80.0);
    renderBwHint();
    if(String(txt('bwHint')||'').indexOf('持平')<0) TMbBad.push('首末相等时没写「持平」：'+txt('bwHint'));
    TMdrop(1); TMdrop(2);
    renderBwHint();
    if(String(txt('bwHint')||'').indexOf('记录不足两周')<0) TMbBad.push('只剩一条时没说实话：'+txt('bwHint'));
    var TMbx=document.getElementById('bwHint');
    if(!TMbx || !TMbx.closest('#profSheet')) TMbBad.push('这一行不在运动员页上（宿主='+(TMbx?(TMbx.closest('.sheet')||{}).id:'无')+'）');
    if(!!document.querySelector('#teleSheet #bwHint')) TMbBad.push('这一行被塞进遥测面板里了：关掉就看不见');
    T('TM5 关掉状态监控后唯一留下的体重趋势一行：只取有值的两个端点周算净变化（▼0.6 / 持平 / 不足两周三种写法都对）、挂在运动员页而非遥测面板、纯只读不动一格账',
      TMbBad.length===0, TMbBad.join(' ; ')||('三态齐 '+TMh.slice(0,40)));

    /* 出段还原：本段真点过开关、也往 weeks 里塞过假体重，不留痕给后面的重载轮与总数闸门。 */
    closeAllSheets();
    Object.keys(state).forEach(function(k){ delete state[k]; });
    Object.keys(JSON.parse(TMs0)).forEach(function(k){ state[k]=JSON.parse(TMs0)[k]; });
    if(TMp0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,TMp0);
    applyChrome(); renderAll(); closeAllSheets();
    T('TM6 出段还原：徽记与开关这两段改过的账、prefs 分片回到进段前，面板收干净、开关仍是默认的关',
      JSON.stringify(state)===TMs0 && localStorage.getItem(LS_PREFS)===TMp0
      && teleOn()===false && state.lang==='zh' && !document.querySelector('.sheet.on'),
      'state 同='+(JSON.stringify(state)===TMs0)+' 分片同='+(localStorage.getItem(LS_PREFS)===TMp0));

    SECT='EQ'; /* ===== EQ. 装备库 / 场地库 / 赛前检查（词表现读契约 + 双名单落盘） ===== */
    var EQs0=JSON.stringify(state), EQp0=localStorage.getItem(LS_PREFS);
    var EQkit0=JSON.stringify(state.gearKit);
    /* 旧存档回填那条腿：删键再 ensureShape，缺 gearKit 补空数组、缺 machines 的场地各补一份，别的一律不动。 */
    delete state.gearKit;
    Object.keys(state.venues).forEach(function(k){ delete state.venues[k].machines; });
    ensureShape();
    T('EQ1 旧存档回填：gearKit 缺补空数组、每台场地的 machines 缺补空数组（SCHEMA_STAMP 不动，只补键）',
      Array.isArray(state.gearKit)&&state.gearKit.length===0
      && Object.keys(state.venues).every(function(k){ return Array.isArray(state.venues[k].machines); }),
      typeof state.gearKit+' / machines齐='+(state.venues[venueIdOf(state.activeVenueId)]||{}).machines);
    openKitSheet();
    T('EQ2 三舱接线：开页即装备舱可见，另两舱收起；分段器三枚按钮与契约成色五档不同源但同页共存',
      document.getElementById('kitSheet').classList.contains('on')
      && document.getElementById('kitGearPane').style.display!=='none'
      && document.getElementById('kitVenuePane').style.display==='none'
      && document.getElementById('kitCheckPane').style.display==='none'
      && document.querySelectorAll('#kitTabSeg button').length===3,
      document.querySelectorAll('#kitTabSeg button').length+' 枚舱钮');
    gearNew();
    var EQkindSel=document.getElementById('kfKind');
    T('EQ3 表单词表全从注入契约现读：类型下拉 = equipment.kinds（13）、成色胶囊 = wear_levels（5 枚、class 走 WEAR_CHIP 单源）、状态 = statuses（4）',
      EQkindSel.options.length===GEAR_SCHEMA.equipment.kinds.length && EQkindSel.options.length===13
      && document.querySelectorAll('#kitGearPane button.wk').length===GEAR_SCHEMA.equipment.wear_levels.length
      && ['wk-fn','wk-mw','wk-ft','wk-ww','wk-bs'].join(',')===Array.prototype.map.call(document.querySelectorAll('#kitGearPane button.wk'),function(b){ return b.className.split(' ')[1]; }).join(',')
      && document.getElementById('kfStatus').options.length===4,
      '类型 '+EQkindSel.options.length+' / 成色 '+document.querySelectorAll('#kitGearPane button.wk').length);
    /* 金标准第一例：多威/WL51201C/深蹲鞋/42/坡差 18mm/PU鞋面 + EVA中底 + 橡胶大底/崭新出厂 */
    EQkindSel.value='shoes'; kitKindChange();
    document.getElementById('kfBrand').value='多威';
    document.getElementById('kfName').value='WL51201C';
    document.getElementById('kfSize').value='42';
    kitPickWear('fn');
    document.getElementById('kfSpec').value='18';
    document.getElementById('kfMaterial').value='PU鞋面 + EVA中底 + 橡胶大底';
    gearSave();
    var EQit=(state.gearKit||[])[0]||{};
    T('EQ4 金标准入册且落进 prefs 片：类型 shoes、spec 现算「坡差 18mm」、成色 fn、材质原样不解析；gearKit 随 savePrefsOnly 进 prefs 分片（不是账本分片）',
      (state.gearKit||[]).length===1 && EQit.kind==='shoes' && EQit.brand==='多威' && EQit.name==='WL51201C'
      && EQit.spec==='坡差 18mm' && EQit.wear==='fn' && EQit.material==='PU鞋面 + EVA中底 + 橡胶大底'
      && ((JSON.parse(localStorage.getItem(LS_PREFS)||'{}').gearKit)||[]).length===1
      && JSON.parse(localStorage.getItem(LS_WORK||'roast.exdark.apk.workout')||'{}').gearKit===undefined,
      EQit.spec+' / '+EQit.wear);
    /* 第二例：腰带 厚度 12mm —— 换 kind 后规格输入仍是数值腿、标签换成契约 spec_keys 的那一行 */
    gearNew();
    document.getElementById('kfKind').value='belt'; kitKindChange();
    document.getElementById('kfBrand').value='劳拉之星';
    document.getElementById('kfName').value='行者0803';
    document.getElementById('kfSize').value='M';
    document.getElementById('kfSpec').value='12';
    document.getElementById('kfMaterial').value='二层软牛皮 + 再生革 + 再生革 + 皮胚 + 二层软牛皮';
    gearSave();
    var EQbelt=(state.gearKit||[])[1]||{};
    T('EQ5 换类型换规格腿：kind=belt 时 spec 由数值现算「厚度 12mm」（spec_keys 单源），材质串原样入库、+ 号连接不被解析',
      EQbelt.kind==='belt' && EQbelt.spec==='厚度 12mm'
      && EQbelt.material.indexOf('皮胚')>=0 && (state.gearKit||[]).length===2,
      EQbelt.spec);
    setKitTab('gear');
    var EQrow=document.querySelector('#kitGearPane .kit-row b');
    T('EQ6 列表行：显示名 = 类型 + 型号（鞋 WL51201C），成色胶囊带色 class 在行上',
      !!EQrow && EQrow.textContent.indexOf('WL51201C')>=0
      && !!document.querySelector('#kitGearPane .kit-row span.wk.wk-fn'),
      EQrow?EQrow.textContent.slice(0,30):'无行');
    var EQbid=EQbelt.id;
    gearDel(EQbid);
    var EQarmed=document.getElementById('kd_'+EQbid);
    var EQstill=(state.gearKit||[]).length;
    if(EQarmed) EQarmed.click();
    T('EQ7 删除两步制：第一次点只把按钮变成「再点确认」，一个字节不删；第二次才真删',
      EQarmed && EQarmed.dataset.armed==='1' && EQstill===2 && (state.gearKit||[]).length===1
      && (state.gearKit||[])[0].id!==EQbid,
      '第一步后 '+(state.gearKit||[]).length+' 件');
    /* 场地库腿：建 30 字名被裁到契约上限、改名改型、设为当前后库存立刻是新建场地那份、器械一行一台进出、删除两步 */
    var EQmax=GEAR_SCHEMA.venues.name_max_len;
    setKitTab('venue');
    document.getElementById('kvName').value='铁'.repeat(EQmax+2);
    venueNew();
    var EQvKeys=Object.keys(state.venues);
    var EQvid=EQvKeys.filter(function(k){ return k!==GEAR_SCHEMA.venues.id_legacy; })[0];
    T('EQ8 场地建档：名字裁到契约上限、machines 起步空数组、inventory 是新的一份 DEFAULT_INVENTORY（不动 legacy 的）',
      !!EQvid && state.venues[EQvid].name.length===EQmax
      && Array.isArray(state.venues[EQvid].machines) && state.venues[EQvid].machines.length===0
      && state.activeVenueId!==EQvid,
      EQvid?state.venues[EQvid].name.length:'没建上');
    venueToggle(EQvid);
    document.getElementById('kvr_'+EQvid).value='铁馆';
    document.getElementById('kvk_'+EQvid).value='gym';
    venueApplyRename(EQvid);
    venueSetActive(EQvid);
    document.getElementById('kmName_'+EQvid).value='深蹲架';
    document.getElementById('kmKind_'+EQvid).value=GEAR_KINDS[0];
    document.getElementById('kmQty_'+EQvid).value='2';
    machAdd(EQvid);
    var EQv=state.venues[EQvid];
    T('EQ9 场地编辑全链路：改名改型生效、设为当前后 venueInv 切到新场地、器械挂 machines 数组（name/kind/qty）且随 prefs 落盘',
      EQv.name==='铁馆' && EQv.kind==='gym' && venueIdOf(state.activeVenueId)===EQvid
      && EQv.machines.length===1 && EQv.machines[0].name==='深蹲架' && EQv.machines[0].qty===2
      && (((JSON.parse(localStorage.getItem(LS_PREFS)||'{}').venues)||{})[EQvid]||{}).machines.length===1,
      EQv.name+' / '+EQv.kind+' / m'+EQv.machines.length);
    /* 把鞋标成比赛再进检查舱：检查页列的必须是 status=race 的那件。 */
    gearEdit((state.gearKit||[])[0].id);
    document.getElementById('kfStatus').value='race';
    gearSave();
    var EQsnap=JSON.stringify(state);
    var EQp=localStorage.getItem(LS_PREFS);
    setKitTab('check');
    var EQcTxt=(document.getElementById('kitCheckPane').textContent||'');
    T('EQ10 赛前检查纯只读：切舱一个字节不写；race 装备（鞋 WL51201C）在列，页面自带「App 不查规则表、不给结论」的口径',
      JSON.stringify(state)===EQsnap && localStorage.getItem(LS_PREFS)===EQp
      && EQcTxt.indexOf('不查规则表')>=0 && EQcTxt.indexOf('WL51201C')>=0,
      '只读='+(JSON.stringify(state)===EQsnap)+' 文案='+EQcTxt.slice(0,18));
    gearEdit((state.gearKit||[])[0].id);
    var EQph=document.getElementById('kfPhoto');
    var EQphOk=false, EQphErr='';
    try{ kitPhotoPick(); kitPhotoDone('stale-key'); kitPhotoDone(kitPhotoKey()); EQphOk=true; }catch(e){ EQphErr=e.message; }
    T('EQ13 照片位：表单里是 1:1 缩略位（无桥=虚线占位、没有 img），pick/del/done 的无桥路径全不炸',
      !!EQph && EQph.className.indexOf('kf-photo')===0
      && EQph.querySelector('.kf-photo-ph')!=null && EQph.querySelector('img')==null
      && EQphOk===true,
      EQph?('占位='+(EQph.querySelector('.kf-photo-ph')!=null)+' 试跑='+EQphOk+(EQphErr?(' err='+EQphErr):'')):'照片位没渲染');
    gearCancel();
    venueDel(EQvid);
    var EQvd=document.getElementById('vd_'+EQvid);
    var EQvAlive=!!state.venues[EQvid];
    if(EQvd) EQvd.click();
    T('EQ11 场地删除两步制 + 回落：第一次点只武装不删；第二次才删，且 activeVenueId 指回 legacy，legacy 永远删不丢（删空兜底重建）',
      EQvd && EQvd.dataset.armed==='1' && EQvAlive && !state.venues[EQvid]
      && !!state.venues[GEAR_SCHEMA.venues.id_legacy] && venueIdOf(state.activeVenueId)===GEAR_SCHEMA.venues.id_legacy,
      Object.keys(state.venues).join(','));
    closeSheet('kitSheet');
    var EQr0=JSON.parse(EQs0);
    Object.keys(state).forEach(function(k){ if(!(k in EQr0)) delete state[k]; });
    Object.keys(EQr0).forEach(function(k){ delete state[k]; state[k]=EQr0[k]; });
    if(EQp0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,EQp0);
    T('EQ12 出段还原：装备库整段改过的账与 prefs 分片回到进段前，gearKit 回到原来的空册子，面板收干净',
      JSON.stringify(state)===EQs0 && localStorage.getItem(LS_PREFS)===EQp0
      && JSON.stringify(state.gearKit)===EQkit0 && !document.querySelector('.sheet.on'),
      'state 同='+(JSON.stringify(state)===EQs0)+' 分片同='+(localStorage.getItem(LS_PREFS)===EQp0));

    SECT='HX'; /* ===== HX. 主页打气与日历引擎 + 哑铃/自重器械视觉（F16/F17/F13）===== */
    /* 夹具全走「今日回推」：startDate=今天−4 天 ⇒ planPos 今天必落 week1 且 wd=今天序号，
       任何真实日期下都成立。段末把 state 与四路分片逐字节还原，账本一字不带走。 */
    var HXs0=JSON.stringify(state);
    var HXp0=localStorage.getItem(LS_PREFS),HXw0=localStorage.getItem(LS_WORK);
    var HXl0=localStorage.getItem(LS_LIB),HXa0=localStorage.getItem(LS_ARCHIVE);
    var HXbak=localStorage.getItem('roast.exdark.apk.struct_bak');
    var HXwk0=state.weeks, HXeLog0=state.e1rmLog, HXeLogR0=JSON.stringify(state.e1rmLog), HXstr0=state.structure;
    var HXnow=new Date(), HXwd=(HXnow.getDay()+6)%7;
    var HXst=new Date(HXnow); HXst.setDate(HXst.getDate()-4);
    var pad2=function(n){ return ('0'+n).slice(-2); };
    var isoDay=function(d){ return d.getFullYear()+'-'+pad2(d.getMonth()+1)+'-'+pad2(d.getDate()); };
    var HXdef=function(id,zh,en,off){ return {id:id,label:'DAY '+id,titleZh:zh,titleEn:en,weekdayOffset:off,focusTags:[],constraints:{}}; };
    function HXmk(a,b,c,tw){
      state.structure=Object.assign({},HXstr0,{startDate:isoDay(HXst),dayDefs:[
        HXdef('A','甲日','HXDAYA',a),HXdef('B','乙日','HXDAYB',b),HXdef('C','丙日','HXDAYC',c)]});
      if(tw) state.structure.totalWeeks=tw;
    }
    state.lang='zh'; state.nick=''; HXmk(HXwd,HXwd,(HXwd+2)%7);
    var HXpp=planPos(new Date(HXnow)), HXpp2=planPos(new Date(HXst.getTime()+6*86400000));
    T('HX1 planPos 全由日期派生：startDate=今天−4 ⇒ 今天 week1 且 wd=今天 Mon–Sun 序号；起点+6 天（明天）落 week1 且 wd+1',
      HXpp.ok===true&&HXpp.week===1&&HXpp.wd===HXwd&&HXpp2.ok===true&&HXpp2.week===1&&HXpp2.wd===(HXwd+2)%7,
      'week='+HXpp.week+' wd='+HXpp.wd+' 明天='+HXpp2.week+'/'+HXpp2.wd);
    var HXds=daysOnWd(HXwd);
    T('HX2 daysOnWd 同日多课按 dayDefs 顺序返回；sessionCode 沿用 B{块序}W{周}D{日} 现有口径（不新造编号）',
      HXds.length===2&&HXds[0].def.id==='A'&&HXds[1].def.id==='B'
      &&sessionCode(1,'A')==='B1W1DA'&&sessionCode(1,'C')==='B1W1DC',
      HXds.map(function(o){return o.def.id;}).join(',')+' / '+sessionCode(1,'A'));
    var HXhs=function(){ return document.getElementById('hdrSub').textContent; };
    renderHeader();
    T('HX3 今日有课：计划并进顶栏 hdrSub「课码 日名 +N」，首页问候卡已整块退役',
      HXhs()==='B1W1DA 甲日 +1'
      &&document.querySelectorAll('#hdrSub .gc-code').length===1
      &&!document.getElementById('greetCard'), JSON.stringify(HXhs()));
    saveNick('  铁蛋  ');
    var HXn4=state.nick, HXpr4=prefsOf().nick, HXdr4=localStorage.getItem(LS_PREFS);
    saveNick('一二三四五六七八九十1234567890一二三四五六七八九十');
    var HXclip=state.nick.length;
    saveNick('');
    /* 无桥环境磁盘只读（READONLY 止血设计）：落盘腿只在可写时才比对，取数口径腿走 prefsOf()。 */
    T('HX4 昵称只进 prefs 片（trim 后 24 字符截断）；saveNick 的取数只落 prefs 片（prefsOf 含 nick、workout 片一个字节不动）',
      HXn4==='铁蛋'&&HXclip===24
      &&HXpr4==='铁蛋'&&!('nick' in workoutOf())&&localStorage.getItem(LS_WORK)===HXw0
      &&(READONLY||HXdr4.indexOf('铁蛋')>=0),
      'nick='+JSON.stringify(HXn4)+' prefsOf含='+(HXpr4==='铁蛋')+' 盘='+(READONLY?'只读跳过':(HXdr4.indexOf('铁蛋')>=0?'已写':'没写'))+' work同='+(localStorage.getItem(LS_WORK)===HXw0));
    HXmk((HXwd+1)%7,(HXwd+1)%7,(HXwd+2)%7); renderHeader();
    T('HX5 休息日顶栏指到下一次：星期名走 WD_ZH×契约 weekday_labels 同序号配对，课码同句',
      HXhs()==='休息 · 下次 '+WD_ZH[(HXwd+1)%7]+' B1W1DA', JSON.stringify(HXhs()));
    HXmk((HXwd+3)%7,(HXwd+3)%7,(HXwd+3)%7,1); renderHeader();
    T('HX6 计划内排无可排：固定句「休息 · 计划内无更多课」（nextSession 扫到周界外收 null）',
      HXhs()==='休息 · 计划内无更多课', JSON.stringify(HXhs()));
    var HXfut=new Date(HXnow); HXfut.setDate(HXfut.getDate()+3);
    state.structure.startDate=isoDay(HXfut); renderHeader();
    var HXb1=HXhs();
    state.structure.startDate=isoDay(new Date(HXst.getTime()-6*86400000)); renderHeader();
    var HXb2=HXhs();
    state.structure.startDate='2026-13-45'; renderHeader();
    var HXb3=HXhs();
    T('HX7 计划外三句各有分工：未开始「起 …」/ 已结束「起 …」/ 坏日期「无效」兜底，绝不静默空白',
      HXb1.indexOf('未开始')>=0 && HXb2.indexOf('已结束')>=0 && HXb3.indexOf('无效')>=0,
      JSON.stringify([HXb1,HXb2,HXb3]));
    HXmk(HXwd,HXwd,(HXwd+2)%7); state.lang='en'; renderHeader();
    var HXe10=HXhs();
    state.lang='zh';
    T('HX10 顶栏随语言整句切换：英文课名上屏，不中英混排',
      HXe10==='B1W1DA HXDAYA +1',
      JSON.stringify([HXe10]));
    T('HX11 「最近一次训练」整块退役：函数不存在、DOM 无卡片/网格/空态、模板无该模块样式与文案',
      typeof recentTraining==='undefined'
      &&!document.getElementById('recentCard')
      &&document.documentElement.innerHTML.indexOf('recentTraining')<0
      &&document.documentElement.innerHTML.indexOf('recentGrid')<0
      &&document.documentElement.innerHTML.indexOf('recentEmpty')<0
      &&document.documentElement.innerHTML.indexOf('.recent-grid')<0,
      'fn='+(typeof recentTraining));
    var HXlcBak=state.lcOpen;
    openEditor(0);
    var HXbox=document.querySelector('.lcalc');
    var HXl1=!!HXbox&&HXbox.classList.contains('collapsed')&&state.lcOpen!==true;
    lcToggle();
    var HXl2=!!HXbox&&!HXbox.classList.contains('collapsed')&&state.lcOpen===true
      &&prefsOf().lcOpen===true&&getComputedStyle(document.getElementById('lcBody')).display!=='none';
    lcToggle();
    var HXl3=!!HXbox&&HXbox.classList.contains('collapsed')&&state.lcOpen===false&&prefsOf().lcOpen===false;
    lcToggle();
    var HXl4=!!HXbox&&!HXbox.classList.contains('collapsed')&&state.lcOpen===true;
    T('HX12 配重计算器默认收起、展开/收起成对可逆，且状态写进 prefs（下次打开沿用）',
      HXl1&&HXl2&&HXl3&&HXl4,
      '默认折='+HXl1+' 展='+HXl2+' 收='+HXl3+' 再展='+HXl4);
    state.lcOpen=HXlcBak;
    state.weeks=HXwk0; state.e1rmLog=HXeLog0; state.structure=HXstr0;
    var HXidx0=-1, HXe0=null, HXsets0=0;
    for(var HXi=0; HXi<day().exercises.length; HXi++){
      var HXc0=day().exercises[HXi];
      if(setsOf(HXc0.mode)>0 && (+HXc0.reps||0)>0 && !anchorOf(HXc0.cat)){ HXidx0=HXi; HXe0=HXc0; HXsets0=setsOf(HXc0.mode); break; }
    }
    var HXpv=document.getElementById('edPlateBar');
    var HXdbOK=false, HXbwOK=false, HXtd=null, HXobjA=null, HXobjB=null, HXbw0=0;
    if(HXidx0>=0){
      openEditor(HXidx0);
      HXbw0=day().bw;
      setGearKind('dumbbell');
      setGearField({sides:2,incrementKg:2.5});
      HXe0.load=15; refreshConsole();
      var HXn2=document.querySelectorAll('#edPlateBar .db-cell').length;
      var HXb2=!!HXpv.querySelector('.geg-badge');
      var HXs2=HXpv.textContent.indexOf('双手总重 '+fmtStep(30)+'kg')>=0;
      setGearSides(1);
      var HXn1=document.querySelectorAll('#edPlateBar .db-cell').length;
      var HXb1=!!HXpv.querySelector('.geg-badge');
      var HXs1=HXpv.textContent.indexOf('单边总重 '+fmtStep(15)+'kg')>=0;
      setGearSides(2);
      /* 双手只画一枚哑铃 + ×2 徽标，不再并排重复第二枚；单手时徽标消失。 */
      HXdbOK=HXn2===1&&HXb2&&HXs2&&HXn1===1&&!HXb1&&HXs1&&gearOf(HXe0).sides===2
        &&!HXpv.querySelector('.pv-sleeve')&&HXpv.className.indexOf('no-sleeve')>=0;
      setGearKind('bw');
      day().bw=100;
      HXe0.load=15; refreshConsole();
      var HXp1=HXpv.textContent.indexOf('加重 +'+fmtStep(15)+'kg')>=0
        &&HXpv.textContent.indexOf('净 '+fmtStep(115)+'kg')>=0&&!!HXpv.querySelector('.bw-fig.is-plus svg');
      HXe0.load=-10; refreshConsole();
      var HXp2b=HXpv.textContent.indexOf('辅助 −'+fmtStep(10)+'kg')>=0&&!!HXpv.querySelector('.bw-fig.is-assist');
      HXe0.load=0; refreshConsole();
      var HXp3=HXpv.textContent.indexOf('自重')>=0&&HXpv.textContent.indexOf('净 '+fmtStep(100)+'kg')>=0;
      HXbwOK=HXp1&&HXp2b&&HXp3&&!HXpv.querySelector('.pv-sleeve')&&HXpv.className.indexOf('no-sleeve')>=0;
      HXtd=JSON.stringify(HXe0);
      var HXeSnap={done:HXe0.done,ds:HXe0.doneSets};
      toggleDone(HXidx0);
      var HXtdA=HXe0.done===true&&HXe0.doneSets===HXsets0;
      toggleDone(HXidx0);
      /* 勾回原位：✅ 只该动 done/doneSets——把这两格按快照放回（含 done 原本无键的情况），
         其余字段必须一字未动，逐字节比对才作数。 */
      if(HXeSnap.done===undefined) delete HXe0.done; else HXe0.done=HXeSnap.done;
      if(HXeSnap.ds===undefined) delete HXe0.doneSets; else HXe0.doneSets=HXeSnap.ds;
      HXobjA=JSON.stringify(HXe0);
      HXobjB=JSON.stringify(state.e1rmLog);
    }
    T('HX13 哑铃只画一枚 + ×N 徽标（单手无徽标）并分列单边/总重、自重人形三态（加重/辅助/自重）带净负荷——两类都不是杠铃杆；✅ 勾满组再勾归零逐字节还原、e1RM 台账零写入',
      HXidx0>=0&&HXdbOK&&HXbwOK&&HXtdA&&HXtd===HXobjA&&HXobjB===HXeLogR0,
      'idx='+HXidx0+' 哑铃='+HXdbOK+' 自重='+HXbwOK+' 勾选还原='+(HXtd===HXobjA));
    var HXr15=JSON.parse(HXs0);
    Object.keys(state).forEach(function(k){ if(!(k in HXr15)) delete state[k]; });
    Object.keys(HXr15).forEach(function(k){ delete state[k]; state[k]=HXr15[k]; });
    if(HXp0===null) localStorage.removeItem(LS_PREFS); else localStorage.setItem(LS_PREFS,HXp0);
    if(HXw0===null) localStorage.removeItem(LS_WORK); else localStorage.setItem(LS_WORK,HXw0);
    if(HXl0===null) localStorage.removeItem(LS_LIB); else localStorage.setItem(LS_LIB,HXl0);
    if(HXa0===null) localStorage.removeItem(LS_ARCHIVE); else localStorage.setItem(LS_ARCHIVE,HXa0);
    if(HXbak===null) localStorage.removeItem('roast.exdark.apk.struct_bak'); else localStorage.setItem('roast.exdark.apk.struct_bak',HXbak);
    editIdx=-1; stopTimer(); closeSheet('edSheet'); renderHeader();
    T('HX14 出段还原：state 与四路分片逐字节回进段前、struct_bak 原位、面板收干净；顶栏在真实计划下仍渲染不空白',
      JSON.stringify(state)===HXs0&&localStorage.getItem(LS_WORK)===HXw0&&localStorage.getItem(LS_PREFS)===HXp0
      &&localStorage.getItem(LS_LIB)===HXl0&&localStorage.getItem(LS_ARCHIVE)===HXa0
      &&localStorage.getItem('roast.exdark.apk.struct_bak')===HXbak
      &&!document.querySelector('.sheet.on')
      &&document.getElementById('hdrSub').textContent.length>0,
      'state 同='+(JSON.stringify(state)===HXs0));

    SECT='HP'; /* ===== HP. 六边形能力记录（HPR 单源与评分） ===== */
    var HPs0=JSON.stringify(state);   /* 进段快照：HP 全程只喂纯读函数、不 save，出段逐字节回位 */
    var HPax=HPR_AXES.map(function(a){return a.id;}).join(',');
    var HPlab=HPR_AXES.map(function(a){return a.zh;}).join(',');
    var HPtwoChar=HPR_AXES.every(function(a){return /^[\u4e00-\u9fa5]{2}$/.test(a.zh);});
    T('HP1 六轴单源：HPR_AXES 恰好六项、id 顺序 力量/耐力/稳定/爆发/精神/灵活、中文标签一律两字',
      HPR_AXES.length===6 && HPax==='strength,endurance,stability,power,mind,mobility'
      && HPlab==='力量,耐力,稳定,爆发,精神,灵活' && HPtwoChar && typeof currentGl==='function',
      '六轴='+HPax+' 标签='+HPlab);
    var HPnb=hprNormalize(null);
    var HPcov={}, HPsub={cardio:0,interval:0};
    HPnb.items.forEach(function(it){ HPcov[it.axis]=1; if(it.sub) HPsub[it.sub]++; });
    T('HP2 内置种子：六轴全覆盖且默认有东西可填（22 项）、耐力含 3 条稳态 + 3 条间歇',
      HPnb.items.length===22 && Object.keys(HPcov).length===6
      && HPsub.cardio===3 && HPsub.interval===3,
      '项数='+HPnb.items.length+' 覆盖轴='+Object.keys(HPcov).length+' 稳态/间歇='+HPsub.cardio+'/'+HPsub.interval);
    var HPc=[
      hprComplete({type:'reps',dir:'higher',target:30,tries:[{v:15}]}),
      hprComplete({type:'reps',dir:'higher',target:30,tries:[{v:30}]}),
      hprComplete({type:'time',dir:'lower',target:1200,tries:[{v:600}]}),
      hprComplete({type:'time',dir:'lower',target:1200,tries:[{v:1800}]}),
      hprComplete({type:'binary',dir:'none',target:null,tries:[]}),
      hprComplete({type:'binary',dir:'none',target:null,achievedDate:'2026-01-01'}),
      hprComplete({type:'linked',dir:'none',target:null,tries:[{v:50}]}),
      hprComplete({type:'reps',dir:'higher',target:30,tries:[]}),
      hprComplete({type:'reps',dir:'higher',target:0,tries:[{v:5}]}),
      hprComplete(null)
    ];
    T('HP3 完成度单一算法：越高/越低按比例夹紧、达标与达成记 100、联动与无目标记 null、空尝试记 0、缺项记 null',
      HPc[0]===50 && HPc[1]===100 && HPc[2]===100 && HPc[3]===67 && HPc[4]===0 && HPc[5]===100
      && HPc[6]===null && HPc[7]===0 && HPc[8]===null && HPc[9]===null, HPc.join('/'));
    state.profile={sq:100,bp:60,dl:150,bw:80,gender:'M',equip:'classic'};
    var HPgl=Math.max(0,Math.min(100,Math.round(currentGl())));
    T('HP4 力量轴现读 GL：强度轴分等于现算 IPF GL 夹紧、绝不存死数',
      hprAxisScore('strength')===HPgl && HPgl>0, 'GL轴='+hprAxisScore('strength'));
    state.profile.sq=150;
    var HPgl2=Math.max(0,Math.min(100,Math.round(currentGl())));
    T('HP5 currentGl 随档案现算：改深蹲重量后力量轴分随之改变（不是缓存死值）',
      hprAxisScore('strength')===HPgl2 && HPgl2!==HPgl, '旧='+HPgl+' 新='+HPgl2);
    state.hpr={items:[{id:'hpc1',axis:'stability',type:'reps',dir:'higher',target:10,tries:[{v:10}]},
                      {id:'hpc2',axis:'stability',type:'reps',dir:'higher',target:10,tries:[{v:5}]}]};
    T('HP6 轴分取均值：同轴两项完成度 (100+50)/2=75 落在稳定轴',
      hprAxisScore('stability')===75, '稳定轴='+hprAxisScore('stability'));
    T('HP7 空轴不打分：灵活轴无内置也无自定义项时轴分为 null（雷达该角落在圆心不硬凑 0）',
      hprAxisScore('mobility')===null, '灵活轴='+hprAxisScore('mobility'));
    var HPpts=hprRadarPoints();
    /* 正六边形几何按 7 项重算过一版后回到 6：顶点数、60° 步进与半径都必须与轴分同源，不许写死坐标表。 */
    var HPgeom=HPpts.every(function(p,i){
      var f=(p.score==null?0:p.score/100), ang=(-90+i*60)*Math.PI/180;
      return Math.abs(p.x-(100+62*f*Math.cos(ang)))<0.75 && Math.abs(p.y-(100+62*f*Math.sin(ang)))<0.75;
    });
    var HPptOK=HPpts.length===6 && HPR_AXES.length===6 && HPgeom
      && HPpts.every(function(p){return typeof p.x==='number' && typeof p.y==='number';})
      && HPpts.filter(function(p){return p.id==='mobility';})[0].score===null;
    T('HP8 雷达几何：六顶点按 60° 均分、半径 = 62×轴分、空轴 score 为 null',
      HPptOK, '顶点数='+HPpts.length+' 轴数='+HPR_AXES.length);
    /* v0.54 数据视角 / 图形态：纯函数，不改 state。 */
    T('HP10 标准水平锚点：固定尺上夹紧到 0–100、越快越好与越多越好都算对、缺值记 null',
      hprAnchorScore(2100,2100,1080,true)===0 && hprAnchorScore(1080,2100,1080,true)===100
      && hprAnchorScore(3000,2100,1080,true)===0 && hprAnchorScore(15,0,30,false)===50
      && hprAnchorScore(40,40,85,false)===0 && hprAnchorScore(null,0,30,false)===null
      && hprLevelOf({type:'reps',dir:'higher',anchor:[0,30],tries:[{v:15},{v:24}]})===80,
      '5K30='+hprAnchorScore(1080,2100,1080,true)+' 引体24='+hprLevelOf({type:'reps',dir:'higher',anchor:[0,30],tries:[{v:15},{v:24}]}));
    var HPml=hprChartModel('level'), HPmg=hprChartModel('goal');
    var HPokv=HPml.axes.length===6 && HPml.axes.every(function(a){return a.score==null||(typeof a.score==='number'&&a.score>=0&&a.score<=100);});
    T('HP11 视角切换：level 走固定锚点（无锚点轴记 null）、goal 力量轴仍等于现算 GL',
      HPokv && HPml.axes.filter(function(a){return a.id==='mobility';})[0].score===null
      && HPmg.axes.filter(function(a){return a.id==='strength';})[0].score===hprAxisScore('strength')
      && HPmg.axes.filter(function(a){return a.id==='stability';})[0].score===hprAxisScore('stability'),
      'level缺失='+HPml.missing+' goal稳定='+HPmg.axes.filter(function(a){return a.id==='stability';})[0].score);
    var HPbar=hprBarHtml(HPmg), HPrg=hprRingHtml(HPmg), HPrd=hprRadarSvg('goal');
    T('HP12 形态切换只换画法：条形/环形各六行且不含 svg，雷达仍是唯一 200×200 SVG',
      (HPbar.split('hpr-brow').length-1)===6 && (HPrg.split('hpr-ringcell').length-1)===6
      && HPbar.indexOf('<svg')<0 && HPrg.indexOf('<svg')<0
      && HPrd.indexOf('viewBox="0 0 200 200"')>=0 && HPrd.indexOf('<polygon')>=0,
      '条形='+(HPbar.split('hpr-brow').length-1)+' 环形='+(HPrg.split('hpr-ringcell').length-1));
    var HPbad=hprNormalize({items:[],chart:'pie',view:'??'}), HPgood=hprNormalize({items:[],chart:'ring',view:'level'});
    T('HP13 视图偏好归一：chart/view 只认名单内值、脏值退回 radar/goal、items 原样保留',
      HPbad.chart==='radar' && HPbad.view==='goal' && HPbad.items.length===0
      && HPgood.chart==='ring' && HPgood.view==='level' && HPgood.items.length===0,
      '脏='+HPbad.chart+'/'+HPbad.view+' 好='+HPgood.chart+'/'+HPgood.view);
    var HPlg=hprNormalize({items:[{id:'lg1',axis:'control',type:'reps',dir:'higher',target:10,tries:[]},
                                  {id:'lg2',axis:'ball',type:'binary',dir:'none',target:null,tries:[]},
                                  {id:'lg3',axis:'flex',type:'time',dir:'higher',target:10,tries:[]},
                                  {id:'lg4',axis:'endurance',sub:'cardio',type:'time',dir:'higher',target:10,tries:[]},
                                  {id:'lg5',axis:'endurance',sub:'bogus',type:'time',dir:'higher',target:10,tries:[]}]});
    T('HP14 旧轴读时归位：control→稳定、ball→爆发、flex→灵活；耐力轴只留 cardio/interval 两个子组',
      HPlg.items[0].axis==='stability' && HPlg.items[1].axis==='power' && HPlg.items[2].axis==='mobility'
      && HPlg.items[3].sub==='cardio' && HPlg.items[4].sub===undefined,
      HPlg.items.map(function(it){return it.axis+'/'+(it.sub||'-');}).join(' '));
    state.hpr={items:[
      {id:'he1',axis:'endurance',sub:'cardio',type:'reps',dir:'higher',target:10,tries:[{v:10}]},
      {id:'he2',axis:'endurance',sub:'interval',type:'reps',dir:'higher',target:10,tries:[{v:5}]},
      {id:'he3',axis:'endurance',sub:'cardio',type:'reps',dir:'higher',target:10,tries:[{v:0}]}]};
    T('HP15 耐力只画一根轴：稳态与间歇条目合并取均值 (100+50+0)/3=50，两子组不再各占一根',
      hprAxisScore('endurance')===50
      && hprRadarPoints().filter(function(p){return p.id==='endurance';}).length===1,
      '耐力轴='+hprAxisScore('endurance'));
    var HPr15=JSON.parse(HPs0);
    Object.keys(state).forEach(function(k){ if(!(k in HPr15)) delete state[k]; });
    Object.keys(HPr15).forEach(function(k){ delete state[k]; state[k]=HPr15[k]; });
    T('HP9 出段还原：state 逐字节回进段前、四路分片零写入（HPR 读函数不落地）',
      JSON.stringify(state)===HPs0, 'state 同='+(JSON.stringify(state)===HPs0));
    /* v0.54 伤病台账：判定与影子目标都是纯读，默认绝不写计划。 */
    var HLs0=JSON.stringify(state);
    var HLn=healthNormalize(null);
    var HLv=healthNormalize({items:[{id:'a',part:'wrist',tier:'t2'},{part:'nope',tier:'t2'},{part:'knee',tier:'zzz'}]});
    T('HL1 台账归一：缺键得空清单、未知部位/档位整项丢弃、合法项按部位预设补三举百分比',
      HLn.items.length===0 && HLv.items.length===1 && HLv.items[0].part==='wrist'
      && HLv.items[0].lifts.sq===2.5 && HLv.items[0].lifts.bp===5 && HLv.items[0].lifts.dl===2.5,
      '空='+HLn.items.length+' 合法='+HLv.items.length);
    state.health=healthNormalize({items:[
      {id:'w1',part:'wrist',tier:'t2',start:hprToday(),lifts:{sq:2.5,bp:5,dl:2.5}},
      {id:'s1',part:'shoulder',tier:'t3',start:hprToday(),lifts:{sq:0,bp:7.5,dl:0}}]});
    T('HL2 多项取最重不叠加：BP 5%+7.5% 记 7.5%（不是 12.5%），factor 0.925、别的举不受牵连',
      injuryPct('bp')===7.5 && Math.abs(injuryFactor('bp')-0.925)<1e-9
      && injuryPct('sq')===2.5 && injuryPct('dl')===2.5,
      'BP='+injuryPct('bp')+' SQ='+injuryPct('sq')+' DL='+injuryPct('dl'));
    T('HL3 恢复期四档：t2=84 天、t1 从 2026-01-01 到 01-22、手填结束日优先',
      healthDays({tier:'t2'})===84 && healthEndDate({start:'2026-01-01',tier:'t1'})==='2026-01-22'
      && healthEndDate({start:'2026-01-01',tier:'t1',endOverride:'2026-03-01'})==='2026-03-01',
      't2天='+healthDays({tier:'t2'})+' t1止='+healthEndDate({start:'2026-01-01',tier:'t1'}));
    var HLe={cat:'B.Bench',load:100,mv:'Bench',gear:{kind:'barbell'}}, HLsh=injuryShadowOf(HLe);
    T('HL4 影子目标只算不写：S/B/D 识别正确、BP −7.5% 降到 ≤92.5、原载荷与 e.load 不被改动',
      injuryLiftOf('S.Squat')==='sq' && injuryLiftOf('B.Bench')==='bp' && injuryLiftOf('D.Deadlift')==='dl'
      && injuryLiftOf('Curl')===null && !!HLsh && HLsh.pct===7.5 && HLsh.before===100
      && HLsh.after<=92.5 && HLsh.after>=90 && HLe.load===100,
      '影子='+(HLsh?HLsh.after:'null')+' 原='+HLe.load);
    var HLr=JSON.parse(HLs0);
    Object.keys(state).forEach(function(k){ if(!(k in HLr)) delete state[k]; });
    Object.keys(HLr).forEach(function(k){ delete state[k]; state[k]=HLr[k]; });

    /* 本条自身也算一项，故判断时先排除自己（EXP_N 含本条）。 */
    }catch(ZERR){
      T('Z0 断言块在 '+SECT+' 段中途抛错（其后断言未执行）', false,
        ZERR.name+': '+String(ZERR.message).slice(0,90));
    }
    T('Z1 断言总数无漂移（无静默删除 / 无整段被跳过）', (P+F)+1===EXP_N, '实到 '+((P+F)+1)+' 应 '+EXP_N);
    o.push('');
    o.push('== v3v 汇总: '+P+' PASS / '+F+' FAIL （共 '+(P+F)+' 项）==');
    return o.join('\\n');})()`;

  const r = await send(ws, id, 'Runtime.evaluate', { expression: expr, returnByValue: true });
  /* 求值失败必须算失败：以前 r.result.value 为 undefined 时只打印一段 JSON 就 exit 0。 */
  const mainOut = (r && r.result && typeof r.result.value === 'string')
    ? r.result.value
    : ('FAIL  主断言块求值失败  [' + JSON.stringify((r && (r.exceptionDetails || r.result)) || {})
        .slice(0, 300) + ']');

  /* ===== G. 启动阻断层：需要重载页面，跑在主断言之后的独立几轮 ===== */
  const ev = async (expression) => {
    const x = await send(ws, id, 'Runtime.evaluate', { expression, returnByValue: true });
    return x && x.result ? x.result.value : undefined;
  };
  const waitBootFatal = async () => {
    for (let i = 0; i < 25; i++) {
      if (await ev('(function(){try{return !!(bootFatal)}catch(e){return false}})()')) return true;
      await new Promise(x => setTimeout(x, 200));
    }
    return false;
  };
  const gLines = [];
  const gT = async (name, cond, detail) => {
    const c = await ev('(function(){try{return (' + cond + ')?1:0}catch(e){return -1}})()');
    const d = detail === undefined ? undefined
      : await ev('(function(){try{return String(' + detail + ').slice(0,64)}catch(e){return "ERR"}})()');
    gLines.push((c === 1 ? 'PASS  ' : 'FAIL  ') + name + (d !== undefined ? '  [' + d + ']' : ''));
  };

  // R · 第 1 轮：把当轮真实 state 伪装成「版本号不认识」的存档
  // 先置空 state：pagehide 时 flushSave 会 bail，否则重载瞬间真实存档会把中毒文本盖掉。
  const poison1 = await ev(`(function(){
    try{
      state=null;
      var p=JSON.parse(JSON.stringify(JSON.parse(localStorage.getItem(LS_WORK))));
      p.schemaVer=999; p.sentinel='__G_SENT__';
      var t=JSON.stringify(p);
      localStorage.setItem(LS_WORK, t);
      localStorage.setItem(LS_PREFS,'{"theme":"dark","sentinel":"__G_PREFS__"}');
      return 'ok len='+t.length+' readback='+(localStorage.getItem(LS_WORK)||'').length;
    }catch(e){ return 'ERR '+e.name+':'+e.message; }
  })()`);
  await send(ws, id, 'Page.reload');
  const fatal1 = await waitBootFatal();
  if (!fatal1) gLines.push('FAIL  R0 中毒存档重载后未进入阻断态  [poison=' + poison1 + ' | ' + await ev(
    `(function(){var w=localStorage.getItem(LS_WORK)||'';return 'workoutLen='+w.length+' head='+w.slice(0,34)+' bootFatal='+(typeof bootFatal)+' READONLY='+READONLY+' stateVer='+(state&&state.schemaVer)})()`) + ']');
  await gT('R1 不识别的 schemaVer → READONLY，且不生成默认 state',
    'READONLY===true && state===null && !!bootFatal');
  await gT('R2 bootFatal 记录了原因与存档来源',
    "bootFatal && bootFatal.reason==='schema' && String(bootFatal.src).indexOf(LS_WORK)>=0",
    'bootFatal && bootFatal.reason+" / "+bootFatal.src');
  await gT('R3 阻断层已渲染（标题 + 处置按钮 ≥3）',
    "!!document.getElementById('bootFail') && document.querySelectorAll('#bootFail button').length>=3",
    "document.querySelectorAll('#bootFail button').length");
  await gT('R4 磁盘原文未被空账本覆盖（哨兵与版本仍在）',
    "(function(){var q=JSON.parse(localStorage.getItem(LS_WORK));return q.sentinel==='__G_SENT__'&&q.schemaVer===999})()");
  await gT('R5 阻断态下 save()/writeSlice() 三分片一律不写盘',
    `(function(){var a=localStorage.getItem(LS_WORK),b=localStorage.getItem(LS_PREFS),c=localStorage.getItem(LS_LIB);
      save(true); writeSlice('workout','{"zzz":1}'); writeSlice('prefs','{}'); writeSlice('lib','{}');
      return localStorage.getItem(LS_WORK)===a && localStorage.getItem(LS_PREFS)===b && localStorage.getItem(LS_LIB)===c})()`);

  // R · 第 2 轮：schemaVer 合法但迁移途中抛错（e1rmLog 含 null）→ 应走 migrate 分支并可只读浏览
  await ev(`(function(){
    state=null;
    var p={schemaVer:5,lang:'zh',theme:'dark',week:1,day:'A',sentinel:'__G_SENT2__',
      profile:JSON.parse(JSON.stringify(SEED.profile)),structure:JSON.parse(JSON.stringify(SEED.structure)),
      weeks:JSON.parse(JSON.stringify(SEED.weeks)),e1rmLog:[null]};
    localStorage.setItem(LS_WORK, JSON.stringify(p)); return 1;})()`);
  await send(ws, id, 'Page.reload');
  const fatal2 = await waitBootFatal();
  if (!fatal2) gLines.push('FAIL  R6 迁移抛错未进入阻断态');
  await gT('R6 迁移抛错 → 阻断且把异常文本带出来',
    "bootFatal && bootFatal.reason==='migrate' && String(bootFatal.text).length>10",
    'bootFatal && String(bootFatal.text)');
  await gT('R7 parsed 里有 weeks → 提供「只读浏览」出口',
    "bootFatal && !!bootFatal.parsed && !!bootFatal.parsed.weeks && /只读浏览/.test(document.getElementById('bootFail').innerText)");
  await ev('enterSafeMode()');
  await gT('R8 只读浏览可渲染，但写盘仍被拦（磁盘原文不变）',
    `(function(){var a=localStorage.getItem(LS_WORK); save(true);
      var q=JSON.parse(a);
      return !document.getElementById('bootFail') && !!state && !!state.weeks && q.e1rmLog[0]===null && q.sentinel==='__G_SENT2__'})()`);

  // R · 第 3 轮：清空存档后必须回到「正常首装」，不能误判成阻断
  await ev(`(function(){[LS_WORK,LS_PREFS,LS_LIB,LS].forEach(function(k){localStorage.removeItem(k)});return 1})()`);
  await send(ws, id, 'Page.reload');
  await waitReady();
  await gT('R9 无存档时正常首装并允许落盘',
    `(function(){var q=JSON.parse(localStorage.getItem(LS_WORK)||'null');
      return READONLY===false && !bootFatal && !!state && !!q && q.schemaVer===SCHEMA_STAMP
        && !document.getElementById('bootFail')})()`);

  // S · 迁移闸门：v5 存档开机迁移一次；已盖章的存档开机绝不重跑（否则会盖掉自定义 rx）
  const hArchive = (stamp) => `(function(){
      state=null;
      var p={schemaVer:${stamp},lang:'zh',theme:'dark',week:1,day:'A',
        profile:JSON.parse(JSON.stringify(SEED.profile)),
        structure:JSON.parse(JSON.stringify(SEED.structure)),
        weeks:JSON.parse(JSON.stringify(SEED.weeks)),
        e1rmLog:[],aux:[],jts:{}};
      p.weeks['1'].A.exercises=[{mode:'SS',cat:'S.Main',load:100,reps:3,rx:'8×2 自定义',done:false,rpe:0,targetRpe:7}];
      localStorage.setItem(LS_WORK, JSON.stringify(p)); return 1;})()`;
  await ev(hArchive(5));
  await send(ws, id, 'Page.reload');
  await waitReady();
  await gT('S1 v5 存档冷启动迁移一次（旧模式键换新键并盖章）',
    "state.weeks['1'].A.exercises[0].mode==='T1.3x3' && state.schemaVer===SCHEMA_STAMP",
    "state.weeks['1'].A.exercises[0].mode+' / stamp='+state.schemaVer");
  await gT('S2 迁移不覆盖用户自定义 rx',
    "state.weeks['1'].A.exercises[0].rx==='8×2 自定义'",
    "state.weeks['1'].A.exercises[0].rx");
  /* 盖章版必须用页面当前的 SCHEMA_STAMP：写死数字的话，每升一版这条就变成「旧存档该迁移」，
     而它真正要守的是「同一版不该重跑」——数字一漂，闸门看起来坏了，其实测的是别的事。 */
  await ev(hArchive('SCHEMA_STAMP'));
  await send(ws, id, 'Page.reload');
  await waitReady();
  await gT('S3 已盖章存档不再重跑迁移（闸门生效）',
    "state.weeks['1'].A.exercises[0].mode==='SS' && state.weeks['1'].A.exercises[0].rx==='8×2 自定义' && state.schemaVer===SCHEMA_STAMP",
    "state.weeks['1'].A.exercises[0].mode");

  /* 主断言一轮 + R/S 重载轮次，统一按行首计数；旧的汇总行剔除后重算，避免自增。 */
  const allLines = mainOut.split('\n')
    .filter(x => x.trim() && x.indexOf('== v3v 汇总') !== 0)
    .concat(gLines);
  const nP = allLines.filter(x => x.indexOf('PASS') === 0).length;
  const nF = allLines.filter(x => x.indexOf('FAIL') === 0).length;
  console.log(allLines.join('\n') + '\n\n== v3v 汇总: ' + nP + ' PASS / ' + nF + ' FAIL （共 ' + (nP + nF) + ' 项）==');
  const failed = nF > 0;
  await tmpclean.close(chrome, profDir);
  process.exit(failed ? 1 : 0);
})().catch(async e => {
  console.error(e);
  await tmpclean.close(chrome, profDir);
  process.exit(1);
});
