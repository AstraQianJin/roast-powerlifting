# -*- coding: utf-8 -*-
"""v0.13（desktop 归档 + gate 调整）的反向验证：证明这三条新承诺真的会拦，而不是摆设。

    python tools/_sabotage_m3.py inject          # 三处一起注
    python tools/_sabotage_m3.py inject 2        # 只注第 2 处（证明它只打红自己那条）
    python tools/gate.py --static            # 期望每条各自变红（见下表）
    python tools/_sabotage_m3.py revert      # 逐字节还原
    python tools/gate.py --static            # 期望回到全绿（静态项数以 gate 实际输出为准，别抄数字）
    python tools/_sabotage_m3.py --s23-dump # 只打印现算出的靶串（gate 的 S23 用它核对动态家族）

三处故障各打在一个承诺上（判定只写「红在哪条」，PASS/FAIL 的数字随静态项数变，以 gate 实际输出为准）：

  F1 活动脚本里出现指向已归档项目的路径字面量 → gate S18 红（归档边界）
     只红 S18，详情直接把命中的字面量报出来
  F2 `gen_seed.py` 的权威工作簿名与另两处对不上 → gate S8 红（三处同源）
     只红 S8，详情列出三处各自的值。这一处的靶子（工作簿名）**从 gen_seed.py 现读**，
     不写在故障表里：名字随种子链变（v0.03 → v0.14 已变过一轮），抄死的版本会让 F2
     找不到目标串而静默失效。
  F3 契约的 record_keys_frozen 清单读不到 → gate S17 红，**连带 S7 与 S5**。
     三条都该红，不是判定钝：26 列协议的权威出处就是这个键，
     S7 拿它当比对基准（报「契约清单 0 列」）、S17 查它在不在；S5 红是因为契约内容变了
     → `exc` 摘要跟着变，成品自然对不上。复原走 `revert`，不要跑 `build_html.py`
     （那会把故障原文注入成品，把契约的坏状态固化成「最新构建」）。

F1/F2 是 S18/S8 首次上闸，历史上没有对应故障可注入，所以这两组是本版本新增的牙。

v0.36（Plan/Exchange v2）新增两腿，见证 S40 的「v2 是 v1 七表超集」判定：
  F4 v2 Plan 契约的 legacy_compat.sheet_order_legacy 少一表 → gate S40 红
     （连带盯 sch= 摘要的腿也红：契约文件字节变了，成品指纹自然对不上）
  F5 v2 信封 accepted 丢了 v1 世代 → gate S40 红（双版本接受是 Y14/Y15 的地基）
     （连带 S5/S17 的 exc= 指纹腿红，理由同 F3）

v0.19 起，本脚本是三处靶串**现算**的这一家，S23 静态读不出来，改由 `--s23-dump` 让它自己
交出来核对（此前它是唯一被 detail 里点名「未能核对」的脚本 —— 靶子漂了要等下次 inject 打空
才发现，而那一刻不在守卫里）。这条新腿的反向验证**不能**做成故障表的一行：脚本自己的台账一在
旁边，S23 就跳过本脚本。实测做法是手工删掉 `--s23-dump` 分派再跑 `gate.py --static` →
只红 S23（`--s23-dump 退出码 1（现算不出靶串）`），放回后回到全绿。

注入前先逐条验靶（存在且只命中一次），任一条不合格就一处都不改 —— 否则会出现「前几处
已落盘、台账却没写」的半注入状态，此时 `revert` 无从还原。

还原靠注入前写下的原文副本（_sabotage_m3.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import re
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m3.json")
PYOUT = os.path.join(HERE, "pyout.py")
GEN = os.path.join(HERE, "gen_seed.py")
EXC = os.path.join(HERE, "schema", "RPL-Exchange-v2.json")
PLAN2 = os.path.join(HERE, "schema", "RPL-Plan-v2.json")


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


def _authoritative_xlsx():
    """F2 的靶子从 `gen_seed.py` 现读，不抄工作簿名。

    这个名字随种子链变（v0.03 → v0.14 已经变过一轮），抄死在故障表里的话，改名后
    目标串找不到，F2 就再也打不红 S8 —— 反向验证静默失效，比没有更糟。
    """
    src = read(GEN)
    hit = re.search(r'XLSX = os\.path\.join\(ROOT, "data", "([^"]+\.xlsx)"\)', src)
    if hit is None:
        sys.exit("F2 取不到 gen_seed.py 的 XLSX 文件名（靶子漂了，先修这个脚本）")
    return hit.group(1)


def build_faults():
    name = _authoritative_xlsx()
    stale = name[:-5] + "_stale.xlsx"
    return [
        (PYOUT, "import sys",
         'import sys\nARCHIVED_LEGACY = "../desktop/tests/test_backend.py"  # 归档边界故障',
         "F1 活动脚本按路径引用已归档项目 → gate S18 红"),
        (GEN, '"%s"' % name, '"%s"' % stale,
         "F2 gen_seed 的工作簿名与 rxlib/成品分叉 → gate S8 红"),
        (EXC, '"record_keys_frozen": [', '"record_keys_frozen_old": [',
         "F3 契约 26 列清单失去权威出处 → gate S17 红（连带 S7、S40；sabr 注入后重建，指纹腿被吸收故不点名）"),
        (PLAN2, '"sheet_order_legacy": ["Profile", "Blocks", "Days", "Workouts", "Telemetry", "Armor"]',
         '"sheet_order_legacy": ["Profile", "Blocks", "Days", "Workouts", "Telemetry"]',
         "F4 legacy_compat 与 v1 sheet_order 分叉 → gate S40 红"),
        (EXC, '"accepted": ["RPL-Plan-v1", "RPL-Plan-v2"]',
         '"accepted": ["RPL-Plan-v2"]',
         "F5 信封 accepted 丢了 v1 世代 → gate S40 红"),
    ]


FAULTS = build_faults()


def inject(pick=None):
    faults = FAULTS if pick is None else [FAULTS[pick - 1]]
    # 先全部验靶，再动手写：中途退出的话，前面几处已经改了磁盘而台账还没落地，
    # 那时 revert 会说「没有台账」，故障就永久留在工作区里（实测踩过）。
    pending = []
    for path, old, new, why in faults:
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
        pending.append((path, src, hit, new, why))
    ledger = {}
    for path, src, hit, new, why in pending:
        ledger.setdefault(path, src)
        rep = new.replace("\n", "\r\n") if ("\r\n" in src and "\n" in new) else new
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


def s23_dump():
    """把现算出来的靶串交给 gate 的 S23 核对：每行 [靶文件, 原文片段]。

    F2 的靶子是从 `gen_seed.py` 现读的，S23 静态解析不出来（v0.18 及之前它只能如实写
    「未能核对」）。有了这条，动态家族也纳进「在位且唯一」的核对：改了脚本却忘了
    `--s23-dump`、或它现算不出靶串，S23 当场红 —— 不用等下次 `inject` 打空才发现。
    只读，不写盘、不建台账。
    """
    print(json.dumps([[p, old] for p, old, _new, _why in FAULTS], ensure_ascii=False))


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
    elif mode == "--s23-dump":
        s23_dump()
    else:
        sys.exit(__doc__)
