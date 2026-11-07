# -*- coding: utf-8 -*-
"""B5 注入闸门的反向验证：证明 build_html.py 的三道新守卫真的会拦，而不是摆设。

    python tools/_sabotage_b5.py inject
    python tools/gate.py --static          # 期望 S4 变红
    python tools/build_html.py --no-refresh  # 期望 seed 闸门 / 占位符断言变红
    python tools/_sabotage_b5.py revert    # 逐字节还原

三处故障各打在一个承诺上：
  F1 模板删掉 PLAN_SCHEMA 占位符  → check_template 必须拒绝（S4 红 / build 中止）
  F2 seed.json 顶层键名被改       → 注入前的契约校验必须拒绝（build 中止）
  F3 build_html 不再替换占位符    → render() 的占位符断言必须拒绝（build 中止 / S5 红）

还原靠注入前写下的原文副本（_sabotage_b5.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_b5.json")
TPL = os.path.join(HERE, "template.html")
SEED = os.path.join(HERE, "seed.json")
BUILD = os.path.join(HERE, "build_html.py")

SEED_LINE = "const SEED = /*__SEED__*/null;\nconst PLAN_SCHEMA = /*__PLAN_SCHEMA__*/null;"

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, SEED_LINE, "const SEED = /*__SEED__*/null;",
     "F1 模板缺 PLAN_SCHEMA 占位符 → check_template / gate S4 红"),
    (SEED, '"profile": {', '"profil": {',
     "F2 seed 顶层键被改 → 注入前的契约校验红"),
    (BUILD, '.replace(SCHEMA_MARKER, schema_payload)',
     '.replace("__NEVER_MATCHS__", schema_payload)  # 故障：占位符不再被替换',
     "F3 占位符没被替换 → render() 断言红"),
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
        # 故障文本按该文件自己的换行符落地，别让一次注入顺手改了整文件的 EOL
        rep = new.replace("\n", "\r\n") if "\r\n" in src else new
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
