# -*- coding: utf-8 -*-
"""M2 JSON 导入闭环 + JSONL 日志（v0.12）的反向验证：证明新守卫真的会拦，而不是摆设。

    python tools/_sabotage_m2.py inject
    python tools/gate.py --static            # 期望 S14 / S16 / S17 变红
    python tools/_sabotage_m2.py revert      # 逐字节还原
    python tools/gate.py --static            # 期望回到全绿

三处故障各打在一个承诺上：
  F1 Java 选择器不再把 .json 映射成 MIME   → JSON 计划在系统选择器里灰掉（gate S16 红）
  F2 契约文件删掉 log_jsonl.import_policy  → 日志契约缺键，前端直读会运行时抛错（gate S17 红）
  F3 模板 planJsonFile 的 accept 去掉 .json → 导入接线不成对（gate S14 红）

还原靠注入前写下的原文副本（_sabotage_m2.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, "_sabotage_m2.json")
TPL = os.path.join(HERE, "template.html")
EXC = os.path.join(HERE, "schema", "RPL-Exchange-v2.json")
JAVA = os.path.join(APK, "app", "src", "main", "java", "com", "roast", "exdark", "MainActivity.java")

IMPORT_POLICY_LINE = '    "import_policy": "禁止：App 不提供 RPL-Log 导入通道；日志是历史事实的单向视图。",\n'

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (JAVA, 't.equals(".json")', 't.equals(".jsonx")',
     "F1 选择器不再映射 .json → gate S16 红"),
    (EXC, IMPORT_POLICY_LINE, "",
     "F2 契约缺 log_jsonl.import_policy → gate S17 红（连带 S40）"),
    (TPL, 'accept=".json,application/json"', 'accept="application/json"',
     "F3 planJsonFile 的 accept 去掉 .json → gate S14 红"),
]


def read(p):
    # newline=''：逐字节读写，还原时不会把 CRLF 文件悄悄改成 LF
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """定位故障串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject():
    ledger = {}
    for path, old, new, why in FAULTS:
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        rep = new.replace("\n", "\r\n") if ("\r\n" in src and "\n" in new) else new
        ledger.setdefault(path, src)
        write(path, src.replace(hit, rep, 1))
        print("注入: %s" % why)
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(ledger)))


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


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "inject":
        inject()
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
