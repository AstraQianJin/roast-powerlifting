# -*- coding: utf-8 -*-
"""M1 JSON 交换载体（v0.11）的反向验证：证明新守卫真的会拦，而不是摆设。

    python tools/_sabotage_m1.py inject
    python tools/gate.py --static            # 期望 S4 / S5 / S15 / S17 / S39 变红
    python tools/_sabotage_m1.py revert      # 逐字节还原
    python tools/gate.py --static            # 期望回到全绿

四处故障各打在一个承诺上：
  F1 模板删掉 EXCHANGE_SCHEMA 占位符   → check_template 拒绝（gate S4 红 / build 中止；成品与模板脱节连带 S5 红，注入腿连带 S17 红）
  F2 契约文件就地删 key_order          → 合同不可就地改，与 git HEAD 哈希失联（gate S39 红；修订注：原写 S40，v0.31 起就地改契约由 S39 拦，S40 只比 v3 对 v2 的超集键、不含 key_order）
  F3 Java 侧 exportDoc 改名            → 桥方法点名对不上（gate S15 红）
  F4 build_html 指纹不再写 exc= 摘要   → 成品指纹与契约文件失联（重建后 gate S17 红）

还原靠注入前写下的原文副本（_sabotage_m1.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, "_sabotage_m1.json")
TPL = os.path.join(HERE, "template.html")
EXC = os.path.join(HERE, "schema", "RPL-Exchange-v2.json")
BUILD = os.path.join(HERE, "build_html.py")
JAVA = os.path.join(APK, "app", "src", "main", "java", "com", "roast", "exdark", "MainActivity.java")

MARKER_LINE = "const EXCHANGE_SCHEMA = /*__EXCHANGE_SCHEMA__*/null;\n"
KEY_ORDER_LINE = '    "key_order": ["format", "schemaVersion", "exportedAt", "app", "plan"],\n'
FP_OLD = ('sch=%s exc=%s gear=%s gpp=%s jts=%s share=%s-->" % (\n'
          '        FP_PREFIX, ver, code, d(tpl_src), d(seed_src), d(schema_src), d(exchange_src),\n'
          '        d(gear_src), d(gpp_src), d(jts_src), d(share_src))')
FP_NEW = ('sch=%s gear=%s gpp=%s jts=%s share=%s-->" % (\n'
          '        FP_PREFIX, ver, code, d(tpl_src), d(seed_src), d(schema_src),\n'
          '        d(gear_src), d(gpp_src), d(jts_src), d(share_src))')

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, MARKER_LINE, "",
     "F1 模板缺 EXCHANGE_SCHEMA 占位符 → gate S4 红 / build_html 中止（连带 S5）"),
    (EXC, KEY_ORDER_LINE, "",
     "F2 契约就地缺 key_order → 合同不可就地改、与 HEAD 哈希失联 gate S39 红"),
    (JAVA, "public void exportDoc(final String filename",
     "public void exportDocRenamed(final String filename",
     "F3 Java 侧 exportDoc 改名 → gate S15 红"),
    (BUILD, FP_OLD, FP_NEW,
     "F4 指纹不再写 exc= → 重建后 gate S17 红"),
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
