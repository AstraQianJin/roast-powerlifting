# -*- coding: utf-8 -*-
"""设置独立页返回栈：证明 E13 / E15 / E16 不是恒真。

    python tools/sabr.py run s3 1 --with fast
    或人肉：
    python tools/_sabotage_s3.py inject
    python tools/_sabotage_s3.py revert      # 逐字节还原

一处故障落在 template.html（v3v 直接读生成物，--with fast 会在注入后重建再跑）：
  F1 系统返回键从「只关最上层」改成「一次关光所有面板」
     → E13 红（返回子页直接掉回首页，设置页也没了）
     → E14 红（后续「再返回才回首页」建立在设置页仍开着的前提上）
     → E15 红（经典计划库返回不落在动作与计划库）
     → E16 红（第二次返回没有设置页可回）

还原靠注入前写下的原文副本（_sabotage_s3.json），不依赖 git。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_s3.json")
TPL = os.path.join(HERE, "template.html")

FAULTS = [
    (TPL, "    closeSheet(open.id); return true;",
     "    closeAllSheets(); return true;",
     "F1 返回键一次关光所有面板 → v3v E13 红 + E14 红 + E15 红 + E16 红（返回栈塌成一层）"),
]

EXPECT = {
    1: "F1 返回键一次关光所有面板 → E13 红 + E14 红 + E15 红 + E16 红",
}


def read(p):
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject(pick=None):
    idxs = range(1, len(FAULTS) + 1) if pick is None else [pick]
    ledger = {}
    for k in idxs:
        path, old, new, why = FAULTS[k - 1]
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        rep = new.replace("\n", "\r\n") if ("\r\n" in src and "\n" in new) else new
        ledger.setdefault(path, read(path))
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
        inject(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif mode == "revert":
        revert()
    else:
        print(__doc__)
