# -*- coding: utf-8 -*-
"""v0.10 反向验证：往**成品** index.html 的纯逻辑函数里注入已知故障，证明 logicv（gate 的 D9）真的会红。

用法：python tools/_sabotage_l1.py <组号>   → 跑 node tools/logicv.js（或 python tools/gate.py --dynamic）→
      python tools/build_html.py            （成品是生成物，复原就是重注入，不依赖 git）
  1 = mround 就近退回向下取整              → N7 红（实测连带 P10/F3/F4，四处同红都源自同一个函数）
  2 = 去掉 mround 商溢出的归零守卫          → N7 红（只有这一条：1e308÷0.25 这类值两侧不再同为 0）
  3 = JTS 丢掉数值强制（字符串照原样累加）  → J1 + J2 红 —— 这正是 v0.10 首跑抓出的那个真实缺陷
                                              （实测连带 J3/J5/J6/J8：脏值一路渗到组数与档位）
  4 = e1rm 的 >12 次软截断丢掉             → E1 红（连带 E2「13 次与 12 次同值」）
  5 = D4 冻结只克隆周、不登记 inactiveWeeks → S3 红（连带 S4；F 段随后撞契约交叉校验，
                                              由 Z0 报中断 + Z1 报实到 42 应 58 —— 闸门按设计生效）
  6 = csvParse 退回按物理行硬切            → C3 + C5 红（连带 C6：一条记录被劈成两半，
                                              后半截当成脏行导入 → 跳过 3 / schema_ver 无效）
  7 = archivePush 单条字节上限短路          → A4 红（只有这一条：507KB 条目被收下）

七组都只改生成物 `app/src/main/assets/index.html`，绝不改 `tools/template.html`；
S5「成品 == 重生成」必然同时变红 —— 那是预期内的连带，与 _sabotage_c4 同理。
"""
import io
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "index.html")

# 每组 = 若干对 (旧串, 新串)；每对必须在成品里恰好命中一次。
MUT = [
    [("return xRound6Py(Math.floor(q+0.5)*s);",
      "return xRound6Py(Math.floor(q)*s);")],
    [("if(!isFinite(q)) return 0;",
      "if(false&&!isFinite(q)) return 0;")],
    [("const v=jtsNum(sc[d.k]);",
      "const v=sc[d.k];")],
    [("const effReps=Math.min(12,reps);",
      "const effReps=reps;")],
    [("stateObj.structure.inactiveWeeks=Object.keys(inactive).map(Number).sort(function(a,b){return a-b;});",
      "stateObj.structure.inactiveWeeks=src.slice();")],
    [("const recs=csvRecords(text);",
      "const recs=text.split(/\\r?\\n/).filter(function(l){return l.trim()!=='';}).map(function(t,i){return {t:t,n:i+1};});")],
    [("if(own>ARCHIVE_ENTRY_CAP) return {ok:false, reason:'too_big', bytes:own};",
      "if(false&&own>ARCHIVE_ENTRY_CAP) return {ok:false, reason:'too_big', bytes:own};")],
]
EXPECT = {
    "1": "logicv → N7 红（连带 P10/F3/F4）",
    "2": "logicv → 只 N7 红",
    "3": "logicv → J1+J2 红（连带 J3/J5/J6/J8）",
    "4": "logicv → E1 红（连带 E2）",
    "5": "logicv → S3 红（连带 S4，F 段由 Z0/Z1 兜住）",
    "6": "logicv → C3+C5 红（连带 C6）",
    "7": "logicv → 只 A4 红",
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
