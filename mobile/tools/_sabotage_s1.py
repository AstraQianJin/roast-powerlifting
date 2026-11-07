# -*- coding: utf-8 -*-
"""逐组落库（A 口径：一组一点）反向验证：证明 SL1–SL5 真的会拦，而不是恒真。

    python tools/sabr.py run s1 1 2 3 4 --with fast
    或人肉：
    python tools/_sabotage_s1.py inject
    python tools/_sabotage_s1.py revert      # 逐字节还原

四处故障全落在 template.html（不重建时静态层看不出，v3v 直接读模板生成物，
所以 --with fast 会在注入后重建再跑）：
  F1 「+」落库时把 RPE 写成 8   → SL1 红（不代表这一组、凭空造 RPE）+ SL5 红（补齐后仍非全空）
  F2 导出取首组而不是末组       → SL4 红（actual_reps / actual_rpe 跟末组脱节）
  F3 编辑器逐组改次数写回卡片   → SL3 红（改的是 e.reps，不是该组）
  F4 「−」不撤末条              → SL2 红（组数不跟记录条数走）

还原靠注入前写下的原文副本（_sabotage_s1.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_s1.json")
TPL = os.path.join(HERE, "template.html")

FAULTS = [
    (TPL, "const rec={kg:kg, reps:(+e.reps||0), rpe:null, t:Date.now(), src:'achieved', basis:gearBasisStamp(e)};",
     "const rec={kg:kg, reps:(+e.reps||0), rpe:8, t:Date.now(), src:'achieved', basis:gearBasisStamp(e)};",
     "F1 「+」落库把 RPE 写成 8 → v3v SL1 红 + SL5 红"),
    (TPL, "const last=hasSL&&ex.setLog.length?ex.setLog[ex.setLog.length-1]:null;",
     "const last=hasSL&&ex.setLog.length?ex.setLog[0]:null;",
     "F2 导出取首组而不是末组 → v3v SL4 红"),
    (TPL, "else if(f==='reps') log[k].reps=(v==null?0:Math.max(0,Math.round(v)));",
     "else if(f==='reps') e.reps=(v==null?0:Math.max(0,Math.round(v)));",
     "F3 编辑器逐组改次数写回卡片 → v3v SL3 红（改的是 e.reps）+ SL4 红（导出跟着读到没改的末组）"),
    (TPL, "else if(d<0){ if(e.setLog.length) e.setLog.pop(); }",
     "else if(d<0){ /* F4 探针：− 不撤末条 */ }",
     "F4 「−」不撤末条 → v3v SL2 红"),
]

EXPECT = {
    1: "F1 RPE 兜底 8 → SL1 红 + SL5 红",
    2: "F2 导出取首组 → SL4 红",
    3: "F3 逐组改写到卡片 → SL3 红 + SL4 红",
    4: "F4 − 不撤末条 → SL2 红",
}


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
        sys.exit(__doc__)
