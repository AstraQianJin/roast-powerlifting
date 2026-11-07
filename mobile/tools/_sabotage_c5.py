# -*- coding: utf-8 -*-
"""C5 反向验证：往**成品** index.html 的 UI 接线里注入已知故障，证明 gate S14/S15 与 v3v V 段真的会红。

用法：python tools/_sabotage_c5.py <组号>   （跑完 python tools/build_html.py 复原）
  1 = 取回函数被改名                        → gate S14 红（成品）+ node tools/v3v.js 的 A0 与 V3 红
  2 = archSheet 从 closeAllSheets 名单掉队  → gate S14 红 + v3v V7 红（返回键关不掉归档面板）
  3 = 清空按钮的 onclick 指向死代码         → 只有 v3v V5 红（实测 gate S14 全绿：
                                              静态扫只点名「函数定义在不在」，onclick 写错什么看不见）
  4 = 文件框 accept 不再收 .xlsx            → gate S14 红 + v3v V1 红
  5 = 直呼 AndroidBridge 的方法名漂移       → 只有 gate S15 红（前端回归里没有 AndroidBridge，
                                              真机上 typeof 守卫静默走浏览器兜底，点了没反应）
  6 = 存档原文导出退回 exportCsv 通道       → 只有 v3v K7 红（S15 抓不到：方法名合法，
                                              错的是 MIME 选择——text/csv 会让保存面板补成 .txt.csv）

第 1–6 组改的都是生成物，S5「成品 == 重生成」必然同时变红 —— 那是预期内的连带，看 S14/S15/V 段那几条。
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
    [("function restoreArchiveItem(id){",
      "function restoreArchiveItemGone(id){")],
    [("'stratLibSheet','archSheet','figsSheet','envSheet'",
      "'stratLibSheet','figsSheet'].forEach")],
    [('id="archClearBtn" onclick="clearArchiveSheet()"',
      'id="archClearBtn" onclick="void(0)"')],
    [('accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"',
      'accept=".csv,text/csv"')],
    [("AndroidBridge.exportPlanXlsx(name,btoa(bin));",
      "AndroidBridge.exportPlanXlsxRenamed(name,btoa(bin));")],
    [("AndroidBridge.exportDoc('exdark_store_backup.txt','text/plain',btoa(bin));",
      "AndroidBridge.exportCsv('exdark_store_backup.txt', f.raw);")],
]
EXPECT = {
    "1": "gate S14 红（成品）+ v3v A0/V3 红",
    "2": "gate S14 红 + v3v V7 红",
    "3": "v3v V5 红（gate S14 全绿：静态盲区，只有真点能抓）",
    "4": "gate S14 红 + v3v V1 红",
    "5": "gate --static S15 红（v3v 全绿）",
    "6": "v3v K7 红（gate S15 全绿：exportCsv 在 Java 确有声明，错的是通道选择不是方法名）",
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
