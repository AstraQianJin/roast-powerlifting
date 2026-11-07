# -*- coding: utf-8 -*-
"""v0.28 逻辑债（静默丢失 / 无声跳过）与 v0.29 UI 债（色板单源 / 令牌可达 / 分段器段数单源 /
计时时长单源 / 内联事件接线）的反向验证：证明 S32·S33·S34·S35·S36 与 v3v 的 LD 段·W5·TD1、
uiv 的 X3c·X3d·X4c·B 段真的会红。

    python tools/_sabotage_n2.py inject          # 四十五处一起注
    python tools/_sabotage_n2.py inject 12       # 只注第 12 处（核对它只红自己那条腿）
    python tools/_sabotage_n2.py inject 16 17 18 # 按组注：组内各条的红项或断言不同、或理由文本不同
    python tools/build_html.py                   # 全部靶都在模板里，不重建则 S5 先红
    python tools/gate.py --static && node tools/v3v.js        # 期望见下表
    node tools/uiv.js                            # F12 红在 X4b，F37/F38 红在 X3d，F40 红在 X1+X3c，F42 红在 X4c，F43/F44 红在 B 段，F45 红在 N 段
    node tools/xlsxv.js                          # 只有 F32 会红这里（六表对账的名单现取）
    python tools/_sabotage_n2.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static && node tools/v3v.js  # 回到全绿

这一家守的是同一类坏法：**不抛错、不报错、界面看不出来，只在真机上少一次数据**。
v0.28 把这类洞逐个补成「拒收要说人话 / 脏输入整批不存 / 守卫先落盘」，
而这类补丁最容易被后人"顺手简化"回去 —— 简化完所有功能测试照旧全绿，因为
「第一周点沿用」和「填了个字母点保存」在回归里根本不会被点到。所以每条都要有
一个反向验证靶，且 S32（静态形状）与 LD 段（真行为）两侧都要能红。

前半批十五处故障各打在一个承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 IMPORT_KEEP_KEYS 丢掉 'e1rmLog'
     → LD1 红（顶层键没被任何一侧认领）。S32 全绿：静态腿只认 archErr/ok!==true 那几处形状，
       名单少一个键是行为问题 —— 两侧不重复也不互补，缺一个视角就漏一类坏法
  F2 归档拒收不再写 archErr（archivePush 返回 {ok:false} 时回执空白）
     → LD2 红（拒收理由与人话都丢）。这条对着红线 4 的姊妹面：导入成功了但回退没存上，
       用户看到"已导入"就再也想不起"这一份不能回退"
  F3 saveProfile 的比例函数回到裸除法（分母 0 不再兜底）
     → LD3 红（0 kg 深蹲算出 Infinity，主项载荷被抹成 0）。S32 全绿：静态腿认的是
       round_step_kg 这个「步进从契约取」的形状，与兜底逻辑无关 —— 行为与形状各管一面
  F4 e1ByWeek 排序回到裸减法（week 缺失时是 NaN）
     → LD4 红 + S32 红（NaN 记录抢到最新，海报/建议都跟着错）
  F5 copyPrevTele 的第一周拒收被拆（!(wn>1) 变成 wn<0）
     → LD5 红 + S32 红（W1 点"沿用"把本周抄成本周，还弹一句"已沿用"）
  F6 planCapacity 手抄 ||52 兜底
     → LD6 红 + S32 红（契约改小时模板不听，S28 的判据被绕过）
  F7 strengthMult 体重兜底回到 75
     → 只有 LD7 红（S32 的 BW>0 形状还在）。恒定的假体重不会报错，只会让所有系数悄悄偏
  F8 clearJts 删掉 save()（只改内存）
     → LD8 红 + S32 红（"清空"看着生效、重开 App 又回来了）
  F9 saveTele 的脏输入闸门改成 if(false)
     → LD9 红 + S32 红（abc 被静默存成 null，toast 还说"已保存"）
  F10 saveTele 不再跳过被关掉的字段
     → LD9 红 + S32 红（隐藏一格等于抹掉这一格历史值 = 数据不可破）
  F11 策略面板按钮上的计数被拿掉
     → 只有 LD11 红（S32 认 stratCounts() 调用点，调用还在）。计数是唯一能看出
       「面板读的是真数据还是写死的样例」的线索
  F12 startTimer 圆点回到写死十六进制
     → LD12 红 + S32 红 + uiv X4b 红（三个视角同判：换主题时圆点不跟着变）
  F13 TIER_TOKEN 少一个 RTS 键
     → LD12 红（键域覆盖）+ S32 红（同一件事的静态侧）
  F14 copyPrevTele 的落盘被拆（save(true) 删除）
     → 只有 S32 红：LD5 自己会 flushSave()，所以内存对、行为对、就是"这一次没落盘"，
       纯行为断言看不见这一层 —— 这条就是专门钉住「静态腿不是装饰」的靶
  F15 importUnifiedCsv 的 EXERCISE 分支回到裸下标（先抛 TypeError 再被吞）
     → LD10 红 + S32 红（回执里出现原始 TypeError、且这一行被静默计入 skipped）

后半批十七处（#14 就绪五档 / #16 默认值 / #17 出厂名单 / #21 切语言 / #9 写盘出声 /
#10 失败带因 / #27 脏输入读数）打的都是同一族坏法：**抄第二份默认值**。这类改动不留报错，
只让「同版本的不同机器」各有各的默认，或者改一处另一处不跟着改：

  F16 jtsToReady 回到手写四档阈值   → LD14 红 + S32 红（HUD 与周容量从此各认各的档）
  F17 matchReadyPct 抄回五个百分比   → LD14 红 + S32 红（档位改名后计量值悄悄退回 90%）
  F18 阈值表内联回 readyIndexFromScore → 只有 S32 红：逐点行为与 READY_AT 完全等价，
       LD14 的边界矩阵照绿 —— 这一张专钉「静态腿不是行为腿的副本」
  F19 proto() 兜底抄第二份字面量     → LD15 红 + S32 红
  F20 建档手抄计时默认值            → LD15 红 + S32 红（迁移/建档两份各调各的）
  F21 四天兜底写回裸字母            → LD15 红 + S32 红（字母表加长时这里不跟着长）
  F22 出厂主题回到 ||'dark'         → LD15 红 + S19 红
  F23 setLang 不再重刷筛选下拉       → LD16 红 + S32 红（切英文后筛选器仍中文）
  F24 静态中文格从登记表删掉         → LD16 红 + S25 红（S25 的反向腿）
  F25 重刷名单少一个下拉            → 只有 LD16 红（S32 只认函数形状，名单少一项是行为问题）
  F26 写侧不记 __lastWriteError     → LD17 红 + S32 红
  F27 那条离桥早退回来              → LD17 红 + S32 红（浏览器里配额炸了全程无声）
  F28 读侧只认桥                   → LD17 红 + S32 红（writeError() 桥外恒空）
  F29 导出失败吞掉原因              → LD18 红 + S32 红
  F30 对比周回到裸读数              → LD19 红 + S32 红（NaN 进档位判定，面板空白无解释）
  F31 处方兜底抄第三份              → 只有 S32 红：proto() 永不返回假值，`||{sets:3,…}`
       在行为上等价到任何断言都看不出差别，但那三份数字一旦被改就只改了一半 —— 手抄本身是病
  F32 本机键误列进 PLAN_OWNED_KEYS   → xlsxv 的 W0（名单互补腿）+ 四条 W1 逐格对账红，
       v3v 的 LD1 同时红（键分区自洽）；S 侧全绿属预期 —— 对账名单现取页面，
       加一把本机键不必改门禁，也就不会留下第二份手抄
  F33 按下态引用不存在的令牌          → 只有 S33 红：整条声明被浏览器丢掉，界面上只是「没反应」
  F34 档位色号抄回 CSS 规则            → 只有 S33 红：令牌值与接线都没变，静态腿盯的是位置不是行为
  F35 档位色号写进 JS 内联样式         → 只有 S33 红（<style> 之外那条腿）
  F36 拆掉一个令牌的接线               → 只有 S33 红：声明还在、没人引用，下个主题照抄就是死值
  F37 亮底主题的 --t1-ink 抄暗色那份    → 只有 uiv X3d 红（纸底对比 1.76:1，静态层量不出来）
  F38 亮底主题的 --gold 抄暗色那份      → 只有 uiv X3d 红（白字压亮金 2.2:1）
  F39 分段器宽度抄回三段实测值          → 只有 S34 红：两段/三段在几何上都自洽，行为侧看不出差别
  F40 segThumb 把格位写成 i+1          → 只有 uiv X1 + X3c 红 + v3v W5 红（S34 认形状：段数与两个属性都还在）
  F41 时长抄本请回 i18n 表            → 只有 S35 红：派生写随后覆盖它，界面一个字都不变
  F42 fmtDur 的秒/分界限改坏          → 只有 v3v TD1 + uiv X4c 红（形状腿认不出哪个界限对，只有对写死的期望串才看得见）
  F43 搜索框 oninput 的引用名改错      → S36 红 + uiv B 段搜索腿红 + uiv K3 红（v3v 全绿属预期：它直呼 brSearch()，
       看不见 markup 里那份引用死了 —— 用户在这头打字，那头一个字符都不筛，还不报错）
  F44 mv-btn 的模式抄成 'manage'      → S36 红 + uiv B 段真点腿红（v3v 全绿属预期：它自己传 'pick'；
       点进去变管理态，选完动作不回编辑器，整条选择链对用户不可达）
  F45 补周数截回出厂那 8 周            → 只有 uiv N1 + N2 红（S 侧与 v3v 全绿属预期：出厂种子就 8 周，
       这条分支只在结构被撑到契约上限时才走；用户拉到 52 周时第 9 周之后没账本，还不报错）

已知边界：F12 的 uiv X4b 只在真浏览器里量得到（getComputedStyle），无头静态层永远绿；
F1/F2/F3/F7/F11/F25 六条刻意只红 v3v 一侧、F14/F18/F31 刻意只红 S32 一侧、
F32 红在 xlsxv 与 v3v LD1 而 S 侧全绿、F33~F36 只红 S33 而 F37/F38 只红 uiv X3d、
F39 只红 S34 而 F40 只红 uiv X1 + X3c 与 v3v W5、
F41 只红 S35 而 F42 只红 v3v TD1 + uiv X4c、
F43/F44 红 S36 + uiv B 段而 v3v 全绿、F45 只红 uiv N1 + N2，
用来证明这几层判据不是互相抄的，而是各看得见另几层看不见的那一类坏法。
S33 与 X3d 的分工尤其清楚：静态层管「色号抄在规则里 / 令牌名写错 / 接线断了」，
行为层管「这个色号在这个主题底下读不读得出来」—— 后者只有真算过亮度比才知道。
S34 与 X3c 是同一件事的两面：静态层管「段数还有没有第二个出处」（抄死的档数特例回来了、
但当前几段恰好都自洽，像素量不出来），行为层管「滑块这会儿压在哪一格」（形状都对但算错了）。
S35 与 TD1 / X4c 同构：静态层管「文案里还有没有第二个数」（抄本被派生写盖住时只有静态看得见），
行为层管「按钮上那个数、点下去的倒计时、state.timerCfg 三方对不对得上」（界限算错只有对写死的期望串才红）。
S36 与 uiv B 段是同一条选择链的两面：静态层全站扫「拼串里那个函数名还认不认得」（名字改错不报错、
界面也不崩，只有逐个核对调用名才看得见），行为层真点那颗钮「下钻到不到得了动作、选完回不回编辑器」；
v3v 直呼 openBrowse('pick')/brSearch()，所以这两处故障在它那一侧必然全绿 —— 这正是它该绿的证据。
N 段管的是另一类：**跑在出厂模板尺寸上永远走不到的分支**。S28 钉住「上限只有一个出处」，
v3v 钉住「8 周这份账算得对」，只有把结构真撑到 52 周 × 16 Block × 6 日，才看得见补周、
时间轴与每张面板在上限那一头还站不站得住 —— 那三层的判据谁也替不了谁。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_n2.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "'e1rmLog','advAuto','advAudit','gearProfile','migrateBackup','migrateReport','gearKit','teleOn','lcOpen','nick'];",
     "'e1rmLog','advAudit','gearProfile','migrateBackup','migrateReport','gearKit','teleOn','lcOpen','nick'];",
     "F1 认领名单少一个键 → LD1 红（S32 全绿属预期）"),
    (TPL, "archErr=L(pair[0],pair[1]);",
     "archErr='';",
     "F2 归档拒收不说理由 → LD2 红（回执空白 = 用户不知道这一份不能回退）"),
    (TPL, "const scale=function(n,d){ const r=(+d>0&&+n>0)?(+n)/(+d):1; return isFinite(r)?r:1; };",
     "const scale=function(n,d){ return (+n)/(+d); };",
     "F3 比例守卫连分母带兜底一起拆 → LD3 红（0 kg 深蹲把全链抹成 Infinity/0）"),
    (TPL, "(+a.week||0)-(+b.week||0)",
     "a.week-b.week",
     "F4 排序回到裸减法 → LD4 红 + S32 红（缺 week 的记录抢到最新）"),
    (TPL, "if(!(wn>1)){",
     "if(wn<0){",
     "F5 第一周的拒收被拆 → LD5 红 + S32 红（把刚填的格子当成上周抄回自己）"),
    (TPL, "maxWeeks:+c.max_weeks,",
     "maxWeeks:+c.max_weeks||52,",
     "F6 容量手抄兜底 → LD6 红 + S32 红（契约改小模板不听）"),
    (TPL, "const BW=+p.bw||0;",
     "const BW=+p.bw||75;",
     "F7 体重兜底 75 → 只有 LD7 红（S32 的 BW>0 形状还在）"),
    (TPL, "  if(state.jts){ delete state.jts[jtsKey()]; }\n  save();",
     "  if(state.jts){ delete state.jts[jtsKey()]; }",
     "F8 清空不落盘 → LD8 红 + S32 红（重开 App 又回来了）"),
    (TPL, "  if(bad.length){",
     "  if(false){",
     "F9 脏输入闸门被拆 → LD9 红 + S32 红（abc 静默变 null，toast 说成功）"),
    (TPL, "    /* 关掉的字段一律不碰：原先会把 null 写进去，等于「隐藏这一格」顺手抹掉历史值（数据不可破）。 */\n    if(!teleFieldOn(f.k)) return;",
     "    /* 故障：关掉的字段也写回 */",
     "F10 隐藏一格等于抹掉一格 → LD9 红 + S32 红"),
    (TPL, "stL.textContent=L('策略列表 ('+sc.n+')','STRATEGY LIST ('+sc.n+')');",
     "stL.textContent=L('策略列表','STRATEGY LIST');",
     "F11 按钮计数被拿掉 → 只有 LD11 红（S32 只认调用点在不在）"),
    (TPL, "const col=tierColor(tier);",
     "const col=tier==='T1'?'#E53935':tier==='T2'?'#1E88E5':'#43A047';",
     "F12 圆点写死十六进制 → LD12 红 + S32 红 + uiv X4b 红（三视角同判）"),
    (TPL, "RTS:'--rts',",
     "",
     "F13 取色表少一个键 → LD12 红（键域覆盖）+ S32 红（同一判据的静态侧）"),
    (TPL, "  /* 改的是 state 里的遥测格子，必须落盘：原来只改内存不 save，重开 App 就没了 */\n  save(true);",
     "  /* 故障：只改内存不落盘 */",
     "F14 沿用不落盘 → 只有 S32 红（LD5 自己 flushSave，行为侧看不见）"),
    (TPL, "const dd=wx&&wx[o.day];\n        if(!dd) throw new Error(L('W'+wkNum+' '+o.day+' 不在当前结构里','W'+wkNum+' '+o.day+' not in this structure'));",
     "const dd=state.weeks[String(wkNum)][o.day];",
     "F15 导入的未知日回到裸下标 + 不再拒收 → LD10 红 + S32 红"),
    # ---- 后半批（#14 / #16 / #17 / #21 / #9 / #10 / #27）：默认值与「只准一份」那一族 ----
    (TPL, "function jtsToReady(score){ return READY[readyIndexFromScore(score)]||READY[1]; }",
     "function jtsToReady(score){ return score>=95?READY[0]:score>=80?READY[1]:score>=65?READY[2]:score>=50?READY[3]:READY[4]; }",
     "F16 分数→档位在手抄第二份阈值 → LD14 红 + S32 红（改 READY_AT 时 HUD 与周容量分家）"),
    (TPL, "function matchReadyPct(d){ const i=matchReadyIndex(d); return (READY[i]||READY[1]).pct; }",
     "function matchReadyPct(d){ const p=[100,90,80,70,55]; const s=String((d&&d.readiness)||''); for(let i=0;i<READY.length;i++) if(s.indexOf(READY[i].zh)>=0) return p[i]; return p[1]; }",
     "F17 就绪百分比抄回五个数 → LD14 红 + S32 红（档位改名后计量值悄悄退回 90%）"),
    (TPL, "  for(let i=0;i<READY_AT.length;i++) if(s>=READY_AT[i]) return i;",
     "  if(s>=95)return 0; if(s>=80)return 1; if(s>=65)return 2; if(s>=50)return 3; return 4;",
     "F18 阈值表被内联回函数体 → 只有 S32 红（READY_AT 腿 + 手抄计数；行为逐点等价，"
     "LD14 边界矩阵照绿 —— 这条钉住「静态腿不是装饰」的第二张靶）"),
    (TPL, "function proto(mode){ return (SEED.proto&&SEED.proto[mode]) || PROTO_FALLBACK; }",
     "function proto(mode){ return (SEED.proto&&SEED.proto[mode]) || {tier:'Other',sets:3,reps:10,rx:'3×10'}; }",
     "F19 模式兜底抄第二份 → LD15 红（身份不等）+ S32 红（缺 PROTO_FALLBACK）"),
    (TPL, "timerCfg:pref.timerCfg||defaultTimerCfg(),",
     "timerCfg:pref.timerCfg||{T1:300,T2:150,T3:75,sound:true},",
     "F20 建档手抄计时默认值 → LD15 红 + S32 红（字面量出现两次；迁移与建档从此各调各的）"),
    (TPL, "const DEFAULT_DAY_IDS=DAY_LETTERS.slice(0,4);",
     "const DEFAULT_DAY_IDS=['A','B','C','D'];",
     "F21 四天兜底写回裸字母 → LD15 红 + S32 红（字母表加到 G 时这里不会跟着长）"),
    (TPL, "state.lang=s.lang||window.DEFAULT_LANG; state.theme=s.theme||window.DEFAULT_THEME;",
     "state.lang=s.lang||window.DEFAULT_LANG; state.theme=s.theme||'dark';",
     "F22 出厂主题回到 ||'dark' → LD15 红 + S19 红（默认值不再是单源，改一处只改一半机器）"),
    (TPL, "  /* 筛选下拉的文案是按第一次填充时的语言生成的，切语言必须重刷（#21 的另一半） */\n  refreshLangSelects();",
     "  /* 故障：下拉文案按第一次填充的语言缓存，切语言不重刷 */",
     "F23 setLang 不再重刷筛选下拉 → LD16 红 + S32 红（切英文后筛选器仍是中文）"),
    (TPL, "  pAgeNote:['JTS 周容量按年龄 / 性别 / 相对力量 / 营养周期折算 Total_Multiplier。',\n            'JTS weekly volume scales Total_Multiplier by age / sex / relative strength / nutrition block.'],",
     "  /* 故障：这一格没登记 */",
     "F24 静态中文格从登记表里删掉 → LD16 红 + S25 红（反向腿：带中文的节点要么登记要么脚本会写）"),
    (TPL, "window.LANG_CACHED_SELECTS=['stratTier','stratCat','progLibFam','progLibGoal','progLibAuto'];",
     "window.LANG_CACHED_SELECTS=['stratCat','progLibFam','progLibGoal','progLibAuto'];",
     "F25 重刷名单少一个下拉 → 只有 LD16 红（S32 认的是函数形状，名单少一项是行为问题）"),
    (TPL, "  if(err){ window.__lastStoreError=err; window.__lastWriteError=err; }",
     "  if(err){ window.__lastStoreError=err; }",
     "F26 写侧不留本次错误痕 → LD17 红 + S32 红（桥外丢数据全程无声）"),
    (TPL, "function watchStoreError(){\n  setTimeout(function(){",
     "function watchStoreError(){\n  if(!window.AndroidBridge||!AndroidBridge.lastStoreError) return;\n  setTimeout(function(){",
     "F27 那条离桥早退回来 → LD17 红 + S32 红（浏览器里配额炸了没人说）"),
    (TPL, "  return String(window.__lastWriteError||'');",
     "  return '';",
     "F28 读侧只认桥 → LD17 红 + S32 红（writeError() 在桥外恒空，等于又闭嘴了）"),
    (TPL, "  }catch(e){ toast(L('导出失败：','Export failed: ')+String(e&&e.message||e)); }",
     "  }catch(e){ toast(L('导出失败','Export failed')); }",
     "F29 导出失败吞掉原因 → LD18 红 + S32 红（现场只剩四个字，谁也不知道炸在哪一层）"),
    (TPL, "function advCurWeek(){ const el=document.getElementById('advWeek'); const n=parseInt(String((el&&el.value)||''),10); return n>0?n:0; }",
     "function advCurWeek(){ const el=document.getElementById('advWeek'); return +(el&&el.value||0); }",
     "F30 对比周回到裸读数 → LD19 红 + S32 红（'abc' 变 NaN 传进档位判定，面板空白且无解释）"),
    (TPL, "  const pr=proto(mode);",
     "  const pr=proto(mode)||{sets:3,reps:10,rx:'3×10'};",
     "F31 处方兜底抄第三份 → 只有 S32 红（proto() 永不返回假值，这句在行为上等价到"
     "任何测试都看不出差别，但它就是那份「将来谁去改 3×10」的手抄本）"),
    (TPL, "const PLAN_OWNED_KEYS=['schemaVer','profile','structure','weeks','gpp','levelSnap'];",
     "const PLAN_OWNED_KEYS=['schemaVer','profile','structure','weeks','gpp','levelSnap','jts','e1rmLog','advAuto','advAudit','day','week'];",
     "F32 本机键被误列进「计划本体」名单 → D8 的 W0 红（两份名单本该互补，重叠即"
     "「导入一次抹掉一次本机账」）+ W1 逐格对账红；名单现取自页面，所以加键不用改门禁"),
    # ---- v0.29 第一批（档位色板 + 令牌可达）：S33 与 uiv X3d 各看得见一面 ----
    (TPL, ".rec-step button:active{background:var(--gold);color:var(--on-gold)}",
     ".rec-step button:active{background:var(--actives);color:var(--on-gold)}",
     "F33 按下态引用了不存在的令牌 → 只有 S33 红（浏览器把整条声明丢掉，"
     "表现是「按了没反应」，不报错也不塌版 —— 这就是当初 --active / --fg 静默躺了十几版的样子）"),
    (TPL, ".tbtn.t2{background:var(--t2-soft);border-color:var(--t2-line);color:var(--t2-ink)}",
     ".tbtn.t2{background:var(--t2-soft);border-color:var(--t2-line);color:#9CCBFF}",
     "F34 色号抄回规则里 → 只有 S33 红（令牌值没变，X3d 量的是令牌，看不见规则里的这份抄本；"
     "换主题时它不跟着变 —— 症状是纸底上档位按钮还是暗色那套浅蓝）"),
    (TPL, "+(sc.amrap?'<span style=\"color:var(--t1-ink)\">AMRAP</span>':'')",
     "+(sc.amrap?'<span style=\"color:#FF9C98\">AMRAP</span>':'')",
     "F35 内联色写死在 JS 字符串里 → 只有 S33 红（同 F34，但这条在 <style> 之外，"
     "靠「JS 无档位色号」那条腿才抓得到）"),
    (TPL, ".badge.dl{background:linear-gradient(135deg,var(--dl),var(--dl-deep))}",
     ".badge.dl{background:linear-gradient(135deg,var(--dl),var(--dl))}",
     "F36 令牌接线被拆掉 → 只有 S33 红（--dl-deep 变成没人引用的死值，"
     "下一个主题照着令牌块抄就等于抄一份不会生效的色）"),
    (TPL, "  --t1-ink:#B3261E; --t2-ink:#0D47A1; --t3-ink:#1B5E20;",
     "  --t1-ink:#FF9C98; --t2-ink:#0D47A1; --t3-ink:#1B5E20;",
     "F37 亮底主题把暗色那份浅蓝文字抄进令牌块 → 只有 uiv X3d 红（S33 全绿属预期："
     "色号在令牌块里、接线也在，静态层看不出「这个值在纸底上只有 1.76:1」）"),
    (TPL, "  --gold:#8A5F0B; --gold-soft:rgba(138,95,11,.09);",
     "  --gold:#E0A83A; --gold-soft:rgba(138,95,11,.09);",
     "F38 亮底主题把强调金抄成暗色那份 → 只有 uiv X3d 红（白字压亮金只有 2.2:1，"
     "「按下微按钮时字看不清」；令牌值与接线都在，静态层无从下手）"),
    # ---- v0.29 第二批（分段器段数单源）：S34 与 uiv X3c / v3v W5 各看得见一面 ----
    (TPL, ".seg-pill{--seg-n:2;--seg-i:0;position:relative;display:flex;flex:none;"
          "width:calc(8px + var(--seg-n)*68px);",
     ".seg-pill{--seg-n:2;--seg-i:0;position:relative;display:flex;flex:none;width:212px;",
     "F39 分段器宽度抄回三段那个实测值 → 只有 S34 红（两段 212 / 三段 212 在几何上都自洽，"
     "滑块照旧压在该档按钮上，行为层量不出差别 —— 但「144px 的两段宽」这条设计值就这么静默丢了，"
     "第四段来了谁也不知道该多宽）"),
    (TPL, "el.style.setProperty('--seg-i',String(i>=0&&i<n?i:0));",
     "el.style.setProperty('--seg-i',String(i+1));",
     "F40 格位写成 i+1 → 只有 uiv X1+X3c 红 + v3v W5 红（S34 全绿属预期：段数还是现量的按钮数、"
     "两个属性都还在写，静态腿认的是形状；滑块 off 一格只有量像素才看得见，"
     "超出的那一格还会把面板顶出横向溢出，连 X1 的裁切检测一起红）"),
    # ---- v0.29 第二批（计时时长单源）：S35 与 v3v TD1 / uiv X4c 各看得见一面 ----
    (TPL, "  setTimerT:['计时提示音','Rest Timer Sound'],",
     "  setTimerT:['计时提示音','Rest Timer Sound'],setTimerS:['T1 5分钟 · T2 2.5分钟 ·"
     " T3 75秒 · 到点蜂鸣与震动','T1 5m · T2 2.5m · T3 75s · beep & haptics'],",
     "F41 把时长抄本请回 i18n 表 → 只有 S35 红（applyChrome 的通用循环先写它、"
     "paintTimerChips 随后覆盖，界面上一个字都不会变 —— 行为侧完全看不出这份抄本回来了，"
     "但它就是说瞎话的那一句：哪天派生写被拆掉，文案立刻退回出厂的三个数）"),
    (TPL, "  if(s<120) return s+'s';",
     "  if(s<60) return s+'s';",
     "F42 fmtDur 的秒/分界限改坏（75s 算成 1.3m）→ 只有 v3v TD1 + uiv X4c 红"
     "（S35 全绿属预期：函数、调用点、档钮接线形状全对，静态层认不出哪个界限才是对的；"
     "只有拿写死的期望串去对文案和倒计时才看得见）"),
    # ---- v0.29 第三批（动作选择链的接线）：S36 与 uiv B 段各看得见一面 ----
    (TPL, 'oninput="brSearch(this.value)"',
     'oninput="brSearchX(this.value)"',
     "F43 把搜索框 oninput 里的引用名改错 → S36 红 + uiv B 段搜索腿红（v3v 全绿属预期：它直呼 "
     "brSearch()，看不见 markup 里这份接线已经死了；用户打字列表纹丝不动，不报错也不崩）"),
    (TPL, "mv-btn\" onclick=\"openBrowse('pick')\"",
     "mv-btn\" onclick=\"openBrowse('manage')\"",
     "F44 把 mv-btn 的模式抄成 'manage' → S36 红 + uiv B 段真点腿红（v3v 全绿属预期：它自己传 'pick'；"
     "用户从编辑器点那颗钮进的是管理态，选完动作不回编辑器改载荷）"),
    # ---- v0.29 第四批（撑到契约上限才走到的那条路径）：只有 uiv N 段看得见 ----
    (TPL, "  const total=+state.structure.totalWeeks||0;",
     "  const total=Math.min(8,+state.structure.totalWeeks||0);",
     "F45 把补周数截回出厂模板那 8 周 → 只有 uiv N1 + N2 红（S 侧与 v3v 全绿属预期：出厂种子就 8 周，"
     "任何跑在默认结构上的断言都碰不到这条分支；契约写着上限 52 周，用户把计划拉到 52 周时 "
     "第 9 周之后根本没有账本周片，主屏翻到 W26 是空的，还不报错）"),
]

EXPECT = {
    1: "只有 LD1 红（S32 全绿属预期）",
    2: "只有 LD2 红",
    3: "只有 LD3 红（S32 全绿属预期）",
    4: "LD4 红 + S32 红",
    5: "LD5 红 + S32 红",
    6: "LD6 红 + S32 红",
    7: "只有 LD7 红（S32 全绿属预期）",
    8: "LD8 红 + S32 红",
    9: "LD9 红 + S32 红",
    10: "LD9 红 + S32 红",
    11: "只有 LD11 红（S32 全绿属预期）",
    12: "LD12 红 + S32 红 + uiv X4b 红",
    13: "LD12 红 + S32 红",
    14: "只有 S32 红（LD5 全绿属预期）",
    15: "LD10 红 + S32 红",
    16: "LD14 红 + S32 红",
    17: "LD14 红 + S32 红",
    18: "只有 S32 红（LD14 全绿属预期）",
    19: "LD15 红 + S32 红",
    20: "LD15 红 + S32 红",
    21: "LD15 红 + S32 红",
    22: "LD15 红 + S19 红",
    23: "LD16 红 + S32 红",
    24: "LD16 红 + S25 红",
    25: "只有 LD16 红（S32 全绿属预期）",
    26: "LD17 红 + S32 红",
    27: "LD17 红 + S32 红",
    28: "LD17 红 + S32 红",
    29: "LD18 红 + S32 红",
    30: "LD19 红 + S32 红",
    31: "只有 S32 红（行为逐点等价，LD 段看不见）",
    32: "xlsxv W0 + W1 红 + v3v LD1 红（S 侧全绿属预期）",
    33: "只有 S33 红（引用了没声明的令牌）",
    34: "只有 S33 红（色号抄在令牌块外）",
    35: "只有 S33 红（JS 里出现档位色号）",
    36: "只有 S33 红（令牌声明了没人引用）",
    37: "只有 uiv X3d 红（S33 全绿属预期）",
    38: "只有 uiv X3d 红（S33 全绿属预期）",
    39: "只有 S34 红（两段/三段几何都自洽，行为层量不出来）",
    40: "uiv X1 + X3c 红 + v3v W5 红（S34 全绿属预期）",
    41: "只有 S35 红（抄本被派生写覆盖，行为一个字不变）",
    42: "v3v TD1 红 + uiv X4c 红（S35 全绿属预期）",
    43: "S36 红 + uiv B 段搜索腿红 + uiv K3 红（v3v 全绿属预期：它直呼 brSearch()，看不见 markup 里的引用）",
    44: "S36 红 + uiv B 段真点腿红（v3v 全绿属预期：它自己传 'pick'）",
    45: "uiv N1 + N2 红（S 侧与 v3v 全绿属预期：出厂种子只有 8 周，碰不到这条分支）",
}


def read(p):
    # newline=''：逐字节读写，还原时不会把 CRLF 文件悄悄改成 LF
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """定位故障目标串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject(pick=None):
    # pick：None=全注 / 整数=单注 / 整数列表=按组注（一组故障的期望红项必须互不重叠，
    #       或红项理由文本各不相同，否则「这组一起红」证明不了其中每一条有牙）
    if isinstance(pick, (list, tuple, set)):
        faults = [FAULTS[i - 1] for i in sorted(int(x) for x in pick)]
    else:
        faults = FAULTS if pick is None else [FAULTS[int(pick) - 1]]
    # 先逐条验靶再动手：任何一条打空都不写盘，杜绝「已改一半、未写台账」的半注入残留
    original, planned = {}, []
    for path, old, new, why in faults:
        src = original.get(path, read(path))
        original[path] = src
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
        planned.append((path, hit, new, why))
    pending = dict(original)
    for path, hit, new, why in planned:
        pending[path] = pending[path].replace(hit, new, 1)
        print("注入: %s" % why)
    for path in original:
        write(path, pending[path])
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(original, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(original)))


def revert():
    if not os.path.exists(LEDGER):
        sys.exit("没有台账 %s，拒绝猜测原文" % LEDGER)
    with io.open(LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    for path, original in ledger.items():
        write(path, original)
        print("还原: %s" % path)
    os.remove(LEDGER)
    print("台账已清除")


def _run(pick):
    if isinstance(pick, list):
        for i in pick:
            if not 1 <= i <= len(FAULTS):
                sys.exit("故障编号只允许 1..%d（收到 %d）" % (len(FAULTS), i))
    elif pick is not None and not 1 <= pick <= len(FAULTS):
        sys.exit("故障编号只允许 1..%d（收到 %d）" % (len(FAULTS), pick))
    inject(pick)
    if isinstance(pick, list):
        print("期望：%s" % " | ".join("%s" % EXPECT[i] for i in pick))
    else:
        print("期望：%s" % (EXPECT[pick] if pick else "见文档表"))


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        _run([int(a) for a in args[1:]] or None)
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
