# -*- coding: utf-8 -*-
"""C3 反向验证：往**成品** index.html 的归档分片里注入已知故障，证明 U 段与 S12 真的会红。

用法：python tools/_sabotage_c3.py <组号>   （跑完 python tools/build_html.py 复原）
  1 = 条数上限不再淘汰                    → node tools/v3v.js 的 U6 红
  2 = 字节上限不再淘汰                    → U7 红（分片文本实测越线）
  3 = 单份超限不再拒绝，照收              → U4 红（连带 U5：归档里多出那一份）
  4 = 六表不齐也收                      → U5 红（残缺归档被当成可用归档存下来）
  5 = 坏分片当场回写覆盖磁盘原文        → U8 红（磁盘上那句「这不是 JSON」没了）
  6 = 阻断态下归档照写                  → U9 红（READONLY 拦不住 push）
  7 = 归档被塞进 WORK_KEYS              → M10 红 + gate S12 红（成品：等于把归档当训练数据导出/清空）
  8 = 桥方法名与 Java 侧对不上          → 只有 gate S12 红（实测 v3v 174 全绿：浏览器里没有 AndroidBridge，
                                          这类两端漂移前端回归看不见，必须由守卫守）

第 1–8 组改的都是生成物，S5「成品 == 重生成」必然同时变红 —— 那是预期内的连带，看 U/S12 那几条。
只改生成物 app/src/main/assets/index.html，绝不改 template.html。
"""
import io
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "index.html")

MUT = [
    ("while(items.length>ARCHIVE_MAX_ITEMS) dropped.push(items.pop().id);",
     "while(false&&items.length>ARCHIVE_MAX_ITEMS) dropped.push(items.pop().id);"),
    ("while(items.length>1 && total>ARCHIVE_CAP_BYTES){ dropped.push(items.pop().id); total=archiveShardBytes(items); }",
     "while(false&&items.length>1 && total>ARCHIVE_CAP_BYTES){ dropped.push(items.pop().id); total=archiveShardBytes(items); }"),
    ("if(own>ARCHIVE_ENTRY_CAP) return {ok:false, reason:'too_big', bytes:own};",
     "if(false&&own>ARCHIVE_ENTRY_CAP) return {ok:false, reason:'too_big', bytes:own};"),
    ("for(let k=0;k<order.length;k++){ if(!Array.isArray(plan[order[k]])) return null; }\n"
     "  let rows=0;\n"
     "  for(let k=0;k<order.length;k++) rows+=plan[order[k]].length;",
     "for(let k=0;k<order.length-1;k++){ if(!Array.isArray(plan[order[k]])) return null; }\n"
     "  let rows=0;\n"
     "  for(let k=0;k<order.length-1;k++) rows+=plan[order[k]].length;"),
    ("shard.warn='归档分片无法识别，已按空归档处理（磁盘原文未改写）'; return shard;",
     "shard.warn='归档分片无法识别，已按空归档处理（磁盘原文未改写）'; writePlanArchive(); return shard;"),
    ("if(READONLY) return {ok:false, reason:'readonly'};",
     "if(false&&READONLY) return {ok:false, reason:'readonly'};"),
    ("const WORK_KEYS=['schemaVer','week','day','profile','structure','weeks','jts','e1rmLog','gpp','levelSnap','advAudit',",
     "const WORK_KEYS=['schemaVer','week','day','profile','structure','weeks','jts','e1rmLog','gpp','levelSnap','advAudit','planArchive',"),
    ("archive:'savePlanArchive'", "archive:'savePlanArch'"),
]
EXPECT = {
    "1": "node tools/v3v.js → U6 红",
    "2": "node tools/v3v.js → U7 红",
    "3": "node tools/v3v.js → U4 红（连带 U5）",
    "4": "node tools/v3v.js → U5 红",
    "5": "node tools/v3v.js → U8 红",
    "6": "node tools/v3v.js → U9 红",
    "7": "node tools/v3v.js → M10 红 + python tools/gate.py --static 的 S12 红（成品）",
    "8": "python tools/gate.py --static → S12 红（v3v 全绿：浏览器里没有 AndroidBridge）",
}

GROUP = sys.argv[1] if len(sys.argv) > 1 else ""
if GROUP not in [str(i + 1) for i in range(len(MUT))]:
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
