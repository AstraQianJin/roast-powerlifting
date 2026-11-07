# -*- coding: utf-8 -*-
"""C4b 反向验证：往**成品** index.html 的六表换算与导入链路里注入已知故障，证明 xlsxv/v3v 真的会红。

用法：python tools/_sabotage_c4.py <组号>   （跑完 python tools/build_html.py 复原）
  1 = %1RM 覆写 load_kg 失效（决策 D10 丢掉）   → node tools/xlsxv.js 的 W1d 第二条红（实测 1 红）
                                              （W1d 就是为这组补的：对账 fixture 全是自洽账本，
                                                load≡pct×锚点，删掉覆写四段对账无感）
  2 = 导入路径的 D4 冻结不登记                 → xlsxv 五条红（实测）：W1 三例 state 全等 + W1e 两条
  3 = 契约闸门不再拦（strict 档放行）          → xlsxv W1s 红（连带 W2/W2b）
                                              拒收是双层闸：读字节层 planFromXlsxFileBytes 与装载层
                                              xPlanDictToState 各拦一次，只拆一层另一层兜住（实测：
                                              单独短路装载层 132 条全绿）——所以这组是两个注入点
  4 = 装载前不再自动归档当前计划               → 只有 node tools/v3v.js 的 V3 红（xlsxv 不断言自动归档）
  5 = 换算回六表时 %1RM 列不再写               → xlsxv W0 红（实测 1 红，11132 格里 96 格掉 pct）

第 1–5 组改的都是生成物，S5「成品 == 重生成」必然同时变红 —— 那是预期内的连带。
只改生成物 app/src/main/assets/index.html，绝不改 template.html。
"""
import io
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "index.html")

# 每组 = 若干对 (旧串, 新串)；每对必须在成品里恰好命中一次。
MUT = [
    [("if(anchor) load=mround(anchor*pct,cp.round_step_kg);",
      "if(false&&anchor) load=mround(anchor*pct,cp.round_step_kg);")],
    [("stateObj.structure.inactiveWeeks=Object.keys(inactive).map(Number).sort(function(a,b){return a-b;});",
      "stateObj.structure.inactiveWeeks=[];")],
    [("if(msgs.length) throw new Error(msgs.join('\\n'));",
      "if(false&&msgs.length) throw new Error(msgs.join('\\n'));"),
     # 目标串停在字符串字面量之前：整句抄写曾因不可见字符错位，最小前缀改动就够把闸门短路。
     ("if(!res.ok) throw new Error(sch.schema_ver",
      "if(false&&!res.ok) throw new Error(sch.schema_ver")],
    [("archived=archivePush(cur,{source:'app', label:(state.structure&&state.structure.startDate)||'',\n"
      "      totalWeeks:(state.structure&&state.structure.totalWeeks)||0});",
      "archived=null;")],
    [("if(anchor&&loadN!==null) row[rc.pct]=xRoundPct(loadN/anchor,dec);",
      "if(false&&anchor&&loadN!==null) row[rc.pct]=xRoundPct(loadN/anchor,dec);")],
]
EXPECT = {
    "1": "node tools/xlsxv.js → W1d 第二条红（冲突行落定 load 仍是表内哨兵，覆写没跑）",
    "2": "node tools/xlsxv.js → W1 三例 state 全等 + W1e 两条红",
    "3": "node tools/xlsxv.js → W1s 红（连带 W2/W2b）",
    "4": "node tools/v3v.js → V3 红（xlsxv 全绿：它不断言自动归档）",
    "5": "node tools/xlsxv.js → W0 红（96 格 pct 掉空）",
}

GROUP = sys.argv[1] if len(sys.argv) > 1 else ""
if GROUP not in [str(i + 1) for i in range(len(MUT))]:
    sys.exit(__doc__)

# newline=''：逐字节读写，注入不会顺手把整文件的换行符改掉
src = io.open(P, encoding="utf-8", newline="").read()
for old, new in MUT[int(GROUP) - 1]:
    hit = old if old in src else old.replace("\n", "\r\n")
    if src.count(hit) != 1:
        sys.exit("故障组 %s 的目标串命中 %d 次（期望 1 次）：%r" % (GROUP, src.count(hit), old[:60]))
    rep = new.replace("\n", "\r\n") if "\r\n" in hit else new
    src = src.replace(hit, rep, 1)
io.open(P, "w", encoding="utf-8", newline="").write(src)
print("MUT%s injected → 期望 %s" % (GROUP, EXPECT[GROUP]))
