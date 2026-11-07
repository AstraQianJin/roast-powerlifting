# -*- coding: utf-8 -*-
"""C2 反向验证：往**成品** index.html 的结构闸门里注入已知故障，证明 Q 段与 S11 真的会红。

用法：python tools/_sabotage_c2.py <组号>   （跑完 python tools/build_html.py --no-refresh 复原）
  1 = 冻结集不再登记（写回空数组）      → node tools/v3v.js 的 Q1 红（连带 Q4：导出失去冻结清单）
  2 = 导出无视冻结周（回到全部周键）    → Q4 红
  3 = daysPerWeek 改回听 raw 里的值     → Q2 红（派生字段有了第二个来源）
  4 = ensureWeeks 参照周回到硬编码 16   → Q6 红（归档周被复制成新周处方）
  5 = 多一处 state.structure= 赋值      → python tools/gate.py --static 的 S11 红（成品 2 处）
  6 = 重新写死一个过期 version:2        → S11 红（version:2 残留 1）

第 5 / 6 组改的是生成物，S5「成品 == 重生成」必然同时变红 —— 那是预期内的连带，看 S11 那条。
只改生成物 app/src/main/assets/index.html，绝不改 template.html。
"""
import io
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "index.html")

MUT = [
    ("state.structure.inactiveWeeks=out.sort(function(a,b){return a-b;});",
     "state.structure.inactiveWeeks=[];"),
    ("  activeWeekKeys().map(Number).forEach(function(w){",
     "  Object.keys(state.weeks).map(Number).forEach(function(w){"),
    ("  st.daysPerWeek=(st.dayDefs||[]).length;",
     "  st.daysPerWeek=+raw.daysPerWeek||(st.dayDefs||[]).length;"),
    ("  for(let w=total;w>=1;w--){ if(!f[String(w)]&&state.weeks[String(w)]){ src=state.weeks[String(w)]; break; } }",
     "  for(let w=16;w>=1;w--){ if(state.weeks[String(w)]){ src=state.weeks[String(w)]; break; } }"),
    ("  try{localStorage.setItem('roast.exdark.apk.struct_bak',JSON.stringify(state));}catch(e){}",
     "  try{localStorage.setItem('roast.exdark.apk.struct_bak',JSON.stringify(state));}catch(e){}\n"
     "  state.structure=Object.assign({},state.structure,{totalWeeks:99});"),
    ("  st.version=structureVersion();",
     "  st.version=structureVersion(); st.draft={version:2};"),
]
EXPECT = {
    "1": "node tools/v3v.js → Q1 红（连带 Q4）",
    "2": "node tools/v3v.js → Q4 红",
    "3": "node tools/v3v.js → Q2 红",
    "4": "node tools/v3v.js → Q6 红",
    "5": "python tools/gate.py --static → S11 红（模板 1 处 / 成品 2 处）",
    "6": "python tools/gate.py --static → S11 红（version:2 残留 1）",
}

GROUP = sys.argv[1] if len(sys.argv) > 1 else ""
if GROUP not in ("1", "2", "3", "4", "5", "6"):
    sys.exit(__doc__)
old, new = MUT[int(GROUP) - 1]

# newline=''：逐字节读写，注入不会顺手把整文件的换行符改掉
src = io.open(P, encoding="utf-8", newline="").read()
hit = old if old in src else old.replace("\n", "\r\n")
if src.count(hit) != 1:
    sys.exit("故障组 %s 的目标串命中 %d 次（期望 1 次）：%r" % (GROUP, src.count(hit), old[:60]))
rep = new.replace("\n", "\r\n") if "\r\n" in hit else new
io.open(P, "w", encoding="utf-8", newline="").write(src.replace(hit, rep, 1))
print("MUT%s injected → 期望 %s" % (GROUP, EXPECT[GROUP]))
