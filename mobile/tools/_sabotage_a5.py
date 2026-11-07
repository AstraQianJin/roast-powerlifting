# -*- coding: utf-8 -*-
"""A5 排雷用：对**成品** index.html 注入若干互相独立的故障，
证明 v3v 的断言真的会红（而不是恒绿）。跑完用 build_html.py 重生成即可复原。
只改 app/src/main/assets/index.html（生成物），绝不改 template.html。

用法：python tools/_sabotage_a5.py <组号>
  1 = MUT1~MUT5（v3v 内容级故障，互相独立，可同轮跑）
  2 = MUT6（改名 openProgLibSheet，验证 A0 点名 + Z0 段名 + Z1 漂移）
  3 = MUT7+MUT8（v2v 内容级故障）
  4 = MUT9（改名 openTeleSheet，验证 v2v 的 Z0/Z1）
  5 = MUT10~MUT15（v0.23 模式引擎/容量层：派生分组、迁移方向、标签覆盖、
      契约化约束、prog_rules、capacity、mode_hint、AMRAP 判据）
  6 = MUT17~MUT20（v0.24 T2/T3 完整分支：新键标签、种子组次、派生组序、契约阈值）
  7 = MUT21~MUT25（v0.24 下周建议只读引擎：零写盘、硬顶优先级、T3 干净次数、
      上/下肢轴向、阶段链派生顺序）
  8 = MUT26~MUT35（环境配置 hub + 六类本地计算器 + 地点网格：名单完整性、参数复位、
      辅助夹 0、填入不落盘、配平看库存、空库存≠全套、全套不占字节、
      清空删键、地名截断、网格跟周走）
  9 = MUT36~MUT38（同一批行为的 **uiv 真点面**：环境面板不渲染网格、换周不跟、
      芯片不按 PLATES 现读——v3v 的 T 段算得出对的结果，uiv 的 L 段才看得见控件）
  10 = MUT39~MUT47（v0.27 阈值回测校准：判卷跟着被测阈值走（实现侧 / 调用侧各一处）、
      样本门槛归零、候选越出物理边界、覆盖忘了还原、表头少一列、有账也画空态、
      打平当改进、比例候选不落整百分位）
点名单条：python tools/_sabotage_a5.py 7 22   （组号 + MUT 序号，可跟多个）
"""
import io, sys, os
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), '..', 'app', 'src', 'main', 'assets', 'index.html')
GROUP = sys.argv[1] if len(sys.argv) > 1 else '1'

MUT = [
    # 1) fmtLoad 给整数补 .0 —— 应打红 B3/B4 + B7
    ("const x=Math.round((+n||0)*100)/100; return String(x);",
     "const x=Math.round((+n||0)*100)/100; return (x%1===0?x+'.0':String(x));"),
    # 2) EN 设置页标签里掺一个汉字 —— 应打红 J6
    ("setLibT:['动作库与自定义动作','Exercise Library & Custom']",
     "setLibT:['动作库与自定义动作','Exercise Library 与 Custom']"),
    # 3) 周容量行少一条「单次区间」标注 —— 应打红 M13
    ("+L('单次区间 ','RANGE ')+r.min+'–'+r.max",
     "+L('区间 ','RANGE ')+r.min+'–'+r.max"),
    # 4) 赛扣视觉里塞进文字 —— 应打红 N10（v0.31 后首页 strip 走 gv.recipe.collars）
    ('if(gv.recipe.collars) chips+=\'<span class="pv-clamp"></span>\';',
     'if(gv.recipe.collars) chips+=\'<span class="pv-clamp">X</span>\';'),
    # 5) 派生分组丢掉 T3 —— 应打红 N13b/N13c/N15
    ("const MODE_GROUP_ORDER=['TOP','T1','T2','T3','RTS','DL','CUSTOM'];",
     "const MODE_GROUP_ORDER=['TOP','T1','T2','RTS','DL','CUSTOM'];"),
    # 6) 重命名 openProgLibSheet 定义 —— 应打红 F1 并连带 Z1（断言数掉了 7 条）
    ("function openProgLibSheet(){", "function openProgLibSheet_GONE(){"),
    # 7) 默认开赛扣 —— v2v 应打红「场地库存默认关赛扣」
    #    （库存归场地后，赛扣默认值只住在 DEFAULT_INVENTORY 一处；旧 DEFAULT_PLATE_CFG 已无读者）
    ("  return {bar_options:BAR_OPTIONS.slice(), bar_kg:BAR_KG, collar_on:false,",
     "  return {bar_options:BAR_OPTIONS.slice(), bar_kg:BAR_KG, collar_on:true,"),
    # 8) 徽章换类名 —— v2v 应打红「About 徽章渲染」
    ('<span class="about-badge">', '<span class="bdg">'),
    # 9) 重命名 openTeleSheet —— v2v 应在 V02-06 段中断并连带 Z0/Z1
    ("function openTeleSheet(){", "function openTeleSheet_GONE(){"),
    # 10) 迁移表退回旧方向（Def.2 不再落到 T1.S2）—— 应打红 N16a
    ("  'T1.Def.1':'T1.Def','T1.Def.2':'T1.S2','T1.Def.3':'T1.S3',\n", ""),
    # 11) 新键 MODE_LABEL 漏一条 —— 应打红 N15b
    ("'T1.Mod':'T1 · MOD 1','T1.Mod.2':'T1 · MOD 2',", "'T1.Mod':'T1 · MOD 1',"),
    # 12) 约束引擎退回不看契约（恒不违规）—— 应打红 N24a~N24e
    ("    if(on&&xRuleHit(rule,cat,tier,mode,candEx.targetRpe!=null?candEx.targetRpe:null))",
     "    if(false&&xRuleHit(rule,cat,tier,mode,candEx.targetRpe!=null?candEx.targetRpe:null))"),
    # 13) Block 上限退回手抄的 8 —— 应打红 N26b
    ("Math.max(cap.minBlocks,Math.min(cap.maxBlocks,+document.getElementById('stBlocks').value||cap.minBlocks))",
     "Math.max(1,Math.min(8,+document.getElementById('stBlocks').value||1))"),
    # 14) 16 周下限回来 —— 应打红 N26c
    ("function figTotalWeeks(){ return Math.max(1, +state.structure.totalWeeks||0); }",
     "function figTotalWeeks(){ return Math.max(16, +state.structure.totalWeeks||16); }"),
    # 15) modeHint 退化成裸前缀（T1.Modx 也会命中）—— 应打红 N27b
    ("return !!hint && (mode===hint || mode.indexOf(hint+'.')===0);",
     "return !!hint && mode.indexOf(hint)===0;"),
    # 16) AMRAP 判据不再看 rx 尾部的「+」—— 应打红 M6c（T2.5x5 被当成 AMRAP）
    ("}else if(/\\+$/.test(String(pr.rx||''))||reps>=12){", "}else if(true||reps>=12){"),
    # ---- 组 6：v0.24 T2/T3 完整分支（N28a~N28e 的 witness）----
    # 17) 新键 MODE_LABEL 漏一条 —— 应打红 N15b
    ("'T2.Mod':'T2 · MOD 1','T2.Vol':'T2 · MOD 2','T2.Mod.3':'T2 · MOD 3',",
     "'T2.Mod':'T2 · MOD 1','T2.Vol':'T2 · MOD 2',"),
    # 18) 种子把 T2.Def.2 的组数写错 —— 应打红 N28a（协议表与成品脱节）
    ('"T2.Def.2":{"tier":"T2","sets":3', '"T2.Def.2":{"tier":"T2","sets":4'),
    # 19) 派生组序的分支档退回 Def 在前 —— 应打红 N28b/N28c（连带 N14）
    ("MODE_BRANCH_ORDER = {Mod:0, Def:1, Tr:2, '':3};",
     "MODE_BRANCH_ORDER = {Def:0, Mod:1, Tr:2, '':3};"),
    # 20) 契约的 T3.Mod 阈值退回 15 —— 应打红 N28e（成品内嵌契约与判据分叉）
    ("AMRAP>=18:+1.25kg|<18:+0kg", "AMRAP>=15:+1.25kg|<15:+0kg"),
    # ---- 组 7：v0.24 下周建议只读引擎（O1~O17 的 witness）----
    # 21) 建议面板落盘 —— 应打红 O16（零写盘）并连带 O17（出段还原）
    ("function openAdviceSheet(){ fillAdviceWeek(); renderAdviceTable(); showSheet('adviceSheet'); haptic(10); }",
     "function openAdviceSheet(){ fillAdviceWeek(); renderAdviceTable(); showSheet('adviceSheet'); localStorage.setItem(LS_WORK,'sab'); haptic(10); }"),
    # 22) 硬顶判定被短路（RPE 9.6 不再直接回退）—— 应打红 O5（走的是两周分支，依据不是「超硬顶」）
    ("if(r.rpe>+ar.rpe_hard_stop){", "if(false&&r.rpe>+ar.rpe_hard_stop){"),
    # 23) T3 干净次数闸门被摘掉（17 次也算达标）—— 应打红 O4 并连带 O1（分支计数变了）
    ("const repsOk=r.lastReps>=r.tgtReps && (!clean || r.lastReps>=clean);",
     "const repsOk=r.lastReps>=r.tgtReps;"),
    # 24) 上/下肢轴向写反（深蹲按上肢 2.5 步进）—— 应打红 O2 并连带 O11（契约读数对不上）
    ("const ax=/^[SD]\\./.test(String(cat||''))?'lower':'upper';",
     "const ax=/^[SD]\\./.test(String(cat||''))?'upper':'lower';"),
    # 25) 阶段链按 stage 倒序（T1.Mod 的下一阶算不出来）—— 应打红 O6
    ("return (+SEED.proto[a].stage||0)-(+SEED.proto[b].stage||0);",
     "return (+SEED.proto[b].stage||0)-(+SEED.proto[a].stage||0);"),
    # ---- 组 8：环境配置 hub + 六类本地计算器 + 地点网格（T1~T20 的 witness）----
    # 26) 名单里少一类（特殊器械换了键）—— 应打红 T1
    ("  {k:'manual',  lbl:['特殊器械','MACHINE / MANUAL'], f:['manual','memo'],",
     "  {k:'manual_x', lbl:['特殊器械','MACHINE / MANUAL'], f:['manual','memo'],"),
    # 27) 打开配片计算器不再复位（参数跨次留着）—— 应打红 T2
    ("  lcReset();\n  showSheet('toolLoadSheet');", "  showSheet('toolLoadSheet');"),
    # 28) 辅助类不再夹 0（能算出负总重）—— 应打红 T7
    ("  if(t.k==='bwassist')return Math.max(0, g('bw')*g('coef')-g('assist'));",
     "  if(t.k==='bwassist')return g('bw')*g('coef')-g('assist');"),
    # 29) 计算器输入顺手写盘 —— 应打红 T9（只该算，不该碰分片）
    ("function readLoadCalc(){", "function readLoadCalc(){ savePrefsOnly();"),
    # 30) 配平无视库存、永远按全片表算 —— 应打红 T10（库存归场地后靶串换成 Resolver 那条腿）
    ("  const set=(invOverride&&typeof invOverride==='object')?stockPlates(invOverride):plateSet();",
     "  const set=PLATES;"),
    # 31) 空库存被当成「回到全套」—— 应打红 T11
    ("  if(!p || typeof p!=='object') return PLATE_KGS.slice();",
     "  if(!p || typeof p!=='object' || !Object.keys(p).length) return PLATE_KGS.slice();"),
    # 32) 关一片却仍把 11 个 kg 全写回场地 —— 应打红 T12
    ("  next.forEach(function(x){ map[x]=null; });",
     "  PLATE_KGS.forEach(function(x){ map[x]=null; });"),
    # 33) 清空地点留一个空字符串（账本长胖）—— 应打红 T15
    ("  if(s){ dd.loc=s; } else { delete dd.loc; }", "  dd.loc=s;"),
    # 34) 地名不再截断 —— 应打红 T16
    ("  const s=String(v==null?'':v).trim().slice(0,LOC_MAX_LEN);",
     "  const s=String(v==null?'':v).trim();"),
    # 35) 下拉换了周但网格不跟着换（每格还认旧周）—— 应打红 T17
    ("  if(sel.value!=='' && ws.indexOf(picked)>=0) _envLocWeek=picked;",
     "  if(false) _envLocWeek=picked;"),
    # 36) 打开环境面板不再渲染地点网格 —— 应打红 uiv L3/L4/L5（芯片在、格子一个都没有）
    ("  renderEnvLoc();\n}", "  /* no grid */\n}"),
    # 37) 每格认的是当前周而不是网格周 —— 应打红 uiv L4（换档后 data-locw 不跟）
    ('+\'data-locw="\'+_envLocWeek+\'"', '+\'data-locw="\'+state.week+\'"'),
    # 38) 库存芯片不再按 PLATES 现读（只画大片）—— 应打红 uiv L1/L3（芯片数与注册表脱钩）
    ("    box.innerHTML=PLATES.map(function(p){",
     "    box.innerHTML=PLATES.filter(function(p){return p.kg>=5;}).map(function(p){"),
    # 39) 判卷改读「当前被覆盖的阈值」—— 应打红 CA4（扫到什么阈值就用什么阈值判卷，命中率必然自证）
    ("  const ar=(PLAN_SCHEMA&&PLAN_SCHEMA.autoreg)||{};\n  const fail=",
     "  const ar=autoregOf();\n  const fail="),
    # 40) 判卷不再套 withAutoreg(null) —— 应打红 CA4（同上，但从调用侧漏掉而非实现侧写错）
    ("    const g=withAutoreg(null,function(){ return calibGrade(r,nx); });",
     "    const g=calibGrade(r,nx);"),
    # 41) 样本门槛归零 —— 应打红 CA5（三行账也敢报百分比）
    ("const CALIB_MIN_N=8;", "const CALIB_MIN_N=0;"),
    # 42) 候选不再夹 RPE 上限 —— 应打红 CA2（扫出 11.9 这种物理上不存在的 RPE）
    ("    if(/rpe/.test(key)) v=Math.min(10,Math.round(v*10)/10);",
     "    if(/rpe/.test(key)) v=Math.round(v*10)/10;"),
    # 43) finally 里不还原覆盖 —— 应打红 CA3（覆盖泄漏到面板之外，整本账从此按假阈值算）
    ("  try{ return fn(); } finally { _arOverride=prev; }",
     "  try{ return fn(); } finally { /* 忘了还原 */ }"),
    # 44) 回测表少画「结论」一列 —— 应打红 CA9/CA11 + uiv R1（表头列数与断言脱钩）
    ("    +'<th>'+esc(L('候选 → 命中率','CAND → HIT'))+'</th><th>'+esc(L('结论','VERDICT'))+'</th></tr></thead>';",
     "    +'<th>'+esc(L('候选 → 命中率','CAND → HIT'))+'</th></tr></thead>';"),
    # 45) 有账时空态判断失效（永远画空态）—— 应打红 CA9/CA10 + uiv R1/R2（表根本没渲染出来）
    ("  const rep=calibSweep(), st=rep.base;",
     "  const rep={base:calibRun(null),rows:[]};\n  box.innerHTML='<div class=\"log-empty\">x</div>'; return;\n  const st=rep.base;"),
    # 46) 打平也算改进（把噪声包装成建议）—— 应打红 CA7
    ("    const ok=cands.filter(function(c){ return c.n>=CALIB_MIN_N&&c.d>0; })",
     "    const ok=cands.filter(function(c){ return c.n>=CALIB_MIN_N; })"),
    # 47) 比例候选不落整百分位 —— 应打红 CA2（扫出 0.038 这种没人填得出的数）
    ("      v=Math.min(1,Math.round(v*100)/100);",
     "      v=Math.min(1,v);"),
]

IDX = {'1': [0, 1, 2, 3, 4], '2': [5], '3': [6, 7], '4': [8],
       '5': [9, 10, 11, 12, 13, 14, 15], '6': [16, 17, 18, 19],
       '7': [20, 21, 22, 23, 24],
       '8': [25, 26, 27, 28, 29, 30, 31, 32, 33, 34],
       '9': [35, 36, 37], '10': [38, 39, 40, 41, 42, 43, 44, 45, 46]}[GROUP]
# 可选第二、三个参数：点名到具体 MUT 序号（1 起），用于逐条确认「哪条断言为它红」。
if len(sys.argv) > 2:
    IDX = [int(x) - 1 for x in sys.argv[2:]]

src = io.open(P, encoding='utf-8').read()
for i in IDX:
    old, new = MUT[i]
    if src.count(old) < 1:
        sys.exit('MUT%d 目标串没找到：%r' % (i + 1, old[:60]))
    src = src.replace(old, new, 1)
    print('MUT%d injected' % (i + 1))

io.open(P, 'w', encoding='utf-8', newline='').write(src)
print('written: %s' % P)
