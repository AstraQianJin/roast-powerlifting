# -*- coding: utf-8 -*-
"""C6 反向验证：把 v0.09 真机验收抓出的**选择器缺陷**注回 Java 侧，证明 gate 的 S16 真的会红。

用法：python tools/_sabotage_c6.py <组号>   → 跑 python tools/gate.py --static → 再
      python tools/_sabotage_c6.py revert   （还原靠注入前存下的原文台账，不依赖 git）
  1 = 选择器退回写死 text/*            → S16 报「选择器仍写死 text/*」
  2 = 删掉 .xlsx 的 MIME 映射          → S16 报「缺 xlsx 的 MIME 映射」
  3 = 不再从 accept 推导（读空数组）    → S16 报「未从 accept 推导 MIME」

三组都只改 `MainActivity.java`（不是生成物），所以 S5 不会连带变红 —— 这是本脚本与
_sabotage_c4/c5 的最大区别：那两套改成品，S5 必然同红属预期；这套只该红 S16 一条。

背景：v0.09 装机验收时，计划工作簿「导入」能拉起系统选择器，但 .xlsx 整行是灰的、
选不动 —— onShowFileChooser 把 MIME 过滤写死成三份 CSV 类型，DocumentsUI 于是把
不匹配的扩展名全部置灰。前端与无头回归（xlsxv 直接喂字节）都碰不到这层系统过滤。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
P = os.path.join(HERE, "..", "app", "src", "main", "java",
                 "com", "roast", "exdark", "MainActivity.java")
LEDGER = os.path.join(HERE, "_sabotage_c6.json")

XLSX_BRANCH = (
    "                } else if (t.equals(\".xlsx\")) {\n"
    "                    out.add(\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\");\n"
    "                }"
)

GROUPS = {
    "1": [("intent.setType(\"*/*\");", "intent.setType(\"text/*\");")],
    "2": [(XLSX_BRANCH, "                }")],
    "3": [("params == null ? null : params.getAcceptTypes()",
           "params == null ? null : new String[0]")],
}
EXPECT = {
    "1": "S16 红：选择器仍写死 text/*",
    "2": "S16 红：缺 xlsx 的 MIME 映射",
    "3": "S16 红：未从 accept 推导 MIME",
}


def read():
    # newline=''：逐字节读写，注入不会顺手把整文件的换行符改掉
    return io.open(P, encoding="utf-8", newline="").read()


def write(s):
    io.open(P, "w", encoding="utf-8", newline="").write(s)


MODE = sys.argv[1] if len(sys.argv) > 1 else ""

if MODE == "revert":
    if not os.path.exists(LEDGER):
        sys.exit("没有台账 %s，拒绝猜测原文" % LEDGER)
    write(json.load(io.open(LEDGER, encoding="utf-8"))[P])
    os.remove(LEDGER)
    print("已还原 MainActivity.java，台账清除")
elif MODE in GROUPS:
    src = read()
    for old, new in GROUPS[MODE]:
        hit = old if old in src else old.replace("\n", "\r\n")
        if src.count(hit) != 1:
            sys.exit("故障组 %s 的目标串命中 %d 次（期望 1 次）：%r"
                     % (MODE, src.count(hit), old[:60]))
        src = src.replace(hit, new.replace("\n", "\r\n") if "\r\n" in hit else new, 1)
    json.dump({P: read()}, io.open(LEDGER, "w", encoding="utf-8"))  # 台账存的是注入前原文
    write(src)
    print("MUT%s injected → 期望 %s" % (MODE, EXPECT[MODE]))
else:
    sys.exit(__doc__)
