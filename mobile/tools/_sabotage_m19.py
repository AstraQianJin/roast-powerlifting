# -*- coding: utf-8 -*-
"""v0.48 日/周分享图（poster）反向验证：证明新守卫 S50 真的会拦，而不是摆设。

    python tools/_sabotage_m19.py inject
    python tools/gate.py --static            # 期望 S50 变红
    python tools/_sabotage_m19.py revert      # 逐字节还原
    python tools/gate.py --static            # 期望回到全绿

五处故障各打在一个承诺上，全落在 template.html（成品不重建，静态腿即红）：
  F1 posterTextBlocks 定义改名        → 文案单源被拆（S50「posterTextBlocks 定义」红；v3v PX2/PX3 崩）
  F2 裸 base64 剥前缀改成整串         → 桥收到带 data: 前缀的串（S50「裸 base64 剥前缀」红；v3v PX6 红）
  F3 周图关 BW 三目反接               → 周图露体重格 / 日图被关（S50「周图关 BW 格」红；v3v PX10 红）
  F4 海报 topE1rm 另点名一把函数      → 与首页最近记录不同口径（S50「海报 topE1rm 调用」红；v3v PX7–PX9 崩）
  F5 catShort 契约读口被掏空          → 短标签回落「其它」第二份（S50「契约短标签读口」红；v3v PX1 红）

还原靠注入前写下的原文副本（_sabotage_m19.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m19.json")
TPL = os.path.join(HERE, "template.html")

DEF_TEXT = "function posterTextBlocks("
B64_OLD = "url.slice(url.indexOf(',')+1)"
BW_OLD = "document.getElementById('postBwBox').style.display=isWeek?'none':''"
BW_NEW = "document.getElementById('postBwBox').style.display=isWeek?'':''"
E1RM_OLD = "anchorDoneE1rm(d.exercises)"
E1RM_NEW = "anchorDoneE1rmTop(d.exercises)"
PORT_OLD = "(SHARE_SCHEMA&&SHARE_SCHEMA.short_labels)||{}"

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, DEF_TEXT, "function posterTextBlocksX(",
     "F1 posterTextBlocks 定义改名 → gate S50 红（文案单源被拆）"),
    (TPL, B64_OLD, "url.slice(0)",
     "F2 裸 base64 剥前缀改成整串 → gate S50 红（桥收到带 data: 前缀的串）"),
    (TPL, BW_OLD, BW_NEW,
     "F3 周图关 BW 三目反接 → gate S50 红（周图露体重格 / 日图被关）"),
    (TPL, E1RM_OLD, E1RM_NEW,
     "F4 海报 topE1rm 另点名一把函数 → gate S50 红（与首页最近记录不同口径）"),
    (TPL, PORT_OLD, "{}",
     "F5 catShort 契约读口被掏空 → gate S50 红（短标签回落第二份）"),
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
