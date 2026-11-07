# -*- coding: utf-8 -*-
"""v0.18（种子链 JSON 化：顶层键名单收进契约）的反向验证：证明 S24 真的会拦。

    python tools/_sabotage_m8.py inject          # 四处一起注
    python tools/_sabotage_m8.py inject 2        # 只注第 2 处（核对它只红自己那条腿）
    python tools/gate.py --static                # 期望见下表
    python tools/_sabotage_m8.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

四处故障都打在同一个承诺上：**seed.json 的顶层键名单只有契约那一份，四个读者都从它取**。
这条名单原先手抄在 gate.py / plan_xlsx.py / gen_seed.py 三处，加一个键要改三处，
漏掉的那一处的表现是「模板按名引用时 undefined」—— 要到开屏才炸，静态什么都绿。

  F1 在 gate.py 里复活一份手抄名单（守卫自己抄了一份）
     → S24 红「第 N 行手抄了一份种子名单」。腿是 AST 扫列表/元组字面量：
       一个字面量里同时点名 ≥2 个种子键 = 第二份出处
  F2 让 plan_xlsx 的契约校验退回手抄那六键
     → S24 红同一条腿。这条最像「无害的重构」：函数还在、结果还对，
       只是名单不再是单源 —— 下一次加键时它会静默漏掉这个读者
  F3 把契约名单改得比产物少一键（required_keys 去掉 strategyLib）
     → S24 红「seed.json 顶层键与名单不等：多 ['strategyLib']」，
       另连带 S5（契约也进 BUILD_FP 指纹，成品当场不同步）
  F4 让 gen_seed 的落盘自检改成手抄名单
     → S24 红同一条腿。这条对着一个真实风险：gen_seed 是名单的**生产者**，
       它若不读契约，产物与契约就各说各话，而 check_seed_shape 那一步会被当成摆设

单注实测（v0.18 首跑，只核「红在哪条」）：F1 / F2 / F4 各只红 S24 一条；F3 红两条
（S24 + S5，后者是契约进指纹的连带）。F3 注入态下再跑一次 gen_seed 会**拒落盘**，
报「seed 顶层键与契约名单不符：多 strategyLib」——生产者与契约对不上时，坏种子进不了成品。

已知边界（别当成已经防住）：S24 核的是「名单只有一份 + 读者都从它取 + 产物与名单相等」，它不核**语义** —— 把 required_keys 改成一组名字全在但顺序错、或把 invariant_keys
缩成一个键，S24 只会报子集/相等那两条能看见的部分；不变量校验收窄了要由契约回归 T 段负责。

台账 _sabotage_m8.json 存的是注入前每个文件的整份原文，revert 逐字节放回。
S23 在平静态会把本脚本的四处靶串一起核对（要求各自命中一次）；注入态里台账还在，
S23 就跳过本脚本并在 detail 里点名 —— 那是故障现场，不是脚本腐了。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
F3 改的是契约，复原后必须重建（`build_html.py`）才能让成品跟指纹对上。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m8.json")
GATE = os.path.join(HERE, "gate.py")
PX = os.path.join(HERE, "plan_xlsx.py")
GEN = os.path.join(HERE, "gen_seed.py")
SCH = os.path.join(HERE, "schema", "RPL-Plan-v2.json")

ROSTER = '["profile", "structure", "proto", "weeks", "aux", "lib", "source", "programLib", "strategyLib"]'
ROSTER_SHORT = '["profile", "structure", "proto", "weeks", "aux", "lib", "source", "programLib"]'
INV_TUPLE = '("profile", "structure", "proto", "weeks", "aux", "lib")'

ANCHOR_GATE = "CSV_N = 26"
ANCHOR_PX = "for key in seed_invariant_keys(sch):"
ANCHOR_GEN = 'req = json.load(f)["seed"]["required_keys"]'

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (GATE, ANCHOR_GATE, ANCHOR_GATE + "\nSEED_KEYS = " + ROSTER,
     "F1 gate.py 里复活一份手抄名单 → S24 红（名单出现第二处出处）"),
    (PX, ANCHOR_PX, "for key in " + INV_TUPLE + ":",
     "F2 契约校验退回手抄六键 → S24 红（读者不再从契约取名单）"),
    (SCH, ROSTER, ROSTER_SHORT,
     "F3 契约名单比产物少一键 → S24 红（产物键与名单不等）+ S5 连带（契约进指纹）+ S40 连带（seed 除 note 外须逐键等 v1）"),
    (GEN, ANCHOR_GEN, "req = " + ROSTER,
     "F4 gen_seed 的落盘自检改成手抄 → S24 红（生产者与契约脱钩）"),
]


def read(p):
    # newline=''：逐字节读写，还原时不会把 CRLF 文件悄悄改成 LF
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """定位故障目标串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject(pick=None):
    faults = FAULTS if pick is None else [FAULTS[pick - 1]]
    # 先逐条验靶再动手：任何一条打空都不写盘，杜绝「已改一半、未写台账」的半注入残留
    original, planned = {}, []
    for path, old, new, why in faults:
        src = original.get(path) if path in original else read(path)
        original[path] = src
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
        planned.append((path, hit, new, why))
    pending = dict(original)
    for path, hit, new, why in planned:
        pending[path] = pending[path].replace(hit, new, 1)
        print("注入: %s" % why)
    for path in original:
        write(path, pending[path])
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(original, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(original)))


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
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        pick = int(args[1]) if len(args) > 1 else None
        if pick is not None and not 1 <= pick <= len(FAULTS):
            sys.exit("故障编号只允许 1..%d" % len(FAULTS))
        inject(pick)
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
