# -*- coding: utf-8 -*-
"""C1 反向验证：往**成品** index.html 的工作簿引擎里注入已知故障，证明 `xlsxv.js` 真的会红。

用法：python tools/_sabotage_c1.py <组号>
  1 = zip 的中央目录尺寸写成 cdSize+12 → openpyxl 打不开 App 写的包（X4 段中断，连带 Z0/Z1）
  2 = 内建日期格式表去掉 numFmtId 14   → 同一格 Python 得日期、App 得序列号（读 hand + X3.11 红）
  3 = 「有格无值」的整行不再剔除        → App 多吐一行空记录（读 odd 的格数与行数都红）

跑完 `python tools/build_html.py` 重生成成品即复原。只改生成物，绝不改 template.html。
"""
import io
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

P = os.path.join(os.path.dirname(__file__), "..", "app", "src", "main", "assets", "index.html")

MUT = [
    ("u32(cdSize); u32(dirStart); u16(0);",
     "u32(cdSize+12); u32(dirStart); u16(0);"),
    ("const XL_BUILTIN_DATE=[[14,22],",
     "const XL_BUILTIN_DATE=[[15,22],"),
    ("if(empty) continue;",
     "if(false) continue;"),
]

GROUP = sys.argv[1] if len(sys.argv) > 1 else ""
if GROUP not in ("1", "2", "3"):
    sys.exit(__doc__)
old, new = MUT[int(GROUP) - 1]

src = io.open(P, encoding="utf-8", newline="").read()
if src.count(old) < 1:
    sys.exit("故障组 %s 的目标串没找到：%r" % (GROUP, old[:60]))
io.open(P, "w", encoding="utf-8", newline="").write(src.replace(old, new, 1))
print("MUT%s injected → 跑 node tools/xlsxv.js 期望变红" % GROUP)
