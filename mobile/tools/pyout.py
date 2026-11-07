# -*- coding: utf-8 -*-
"""构建链脚本的 stdout 编码守卫：把中文输出与机器控制台代码页解耦。

Python 的 stdout 默认跟随控制台代码页。中文 Windows 是 cp936，恰好装得下汉字，
所以本地一切正常；换成英文 Windows（cp1252 / cp437）后，`print` 到中文路径或中文
结果串会直接抛 UnicodeEncodeError —— 于是 `gen_seed.py` / `build_html.py` 在换机后
**第一步就崩**，而崩的原因与代码无关。同理，被 node 侧脚本管道读取的输出若跟着代码页
走，接收方按 UTF-8 解码就成了乱码比对（D8 曾因这个误判 946 处格差）。

用法：在每个入口 `main()` 的第一行调用 `use_utf8_stdout()`。
例外：`plan_xlsx.py` 内联同样的 reconfigure 而不 import 本模块 —— 它的依赖面被
`test_plan_xlsx.py` 的 T4.5 钉死为「openpyxl + wkbook + 标准库」，多一个本地
import 就会红。
"""
import sys


def use_utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # 非 CPython / 已被重定向的流：不因此中断构建链
