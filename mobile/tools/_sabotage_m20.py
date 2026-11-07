# -*- coding: utf-8 -*-
"""v0.49 六边形能力记录（HPR）反向验证：证明新守卫 S51 真的会拦，而不是摆设。

    python tools/sabr.py run m20 1 2 3 4 5 6 --with static   # 一条命令跑完六处
    或人肉：
    python tools/_sabotage_m20.py inject
    python tools/gate.py --static            # 期望 S51 变红
    python tools/_sabotage_m20.py revert      # 逐字节还原
    python tools/gate.py --static            # 期望回到全绿

六处故障各打在 S51 的一条承诺上，全落在 template.html（成品不重建，静态腿即红）：
  F1 HPR_AXES 抽掉柔韧轴      → 六轴单源失守（S51「不是恰好六轴」红）
  F2 hpr 从 WORK_KEYS 撤下登记 → 本机账本丢这一片（S51「没登记进 WORK_KEYS」+「出现 1 次」红）
  F3 hprAxisScore 定义改名    → 轴分单源出口被拆成两面（S51「不是恰好一面」红）
  F4 力量轴 GL 现读改成写死    → 系数漂成死数、换重量组不跟（S51「强度轴没经 currentGl 现读」红）
  F5 内置种子塞一条柔韧项      → 承诺的「内置 7 项 / flex 空」失守（S51「不是恰好 7 项」+「flex 有内置」红）
  F6 摘掉 hprBoard 看板 id     → 雷达落不进 AUX 看板、renderHpr 空转（S51「hprBoard 不是恰好一面」红）

还原靠注入前写下的原文副本（_sabotage_m20.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m20.json")
TPL = os.path.join(HERE, "template.html")

# 六轴里的灵活一行（整行，含前导逗号与换行，撤掉后 mind 成为末项，数组仍合法）
AXES_MOB_OLD = (",\n  {id:'mobility', zh:'灵活', en:'MOBILITY', shortZh:'灵活', shortEn:'MOB', "
                "bz:'拉伸 / 松解 / 平衡 / 瑜伽', be:'stretch / release / balance / yoga'}\n];")
AXES_MOB_NEW = "\n];"
# 耐力轴的三个间歇子组（连续三行）：把 sub 全改成 cardio，破坏「两个子组都有条目」
SUB_BLOCK_OLD = (
    "    {id:'hpr_itr',    axis:'endurance', sub:'interval',type:'reps', dir:'higher',target:10,   unit:'组', nameZh:'间歇跑 · 10 组', nameEn:'Interval Run · 10 sets', anchor:[0,20]},\n"
    "    {id:'hpr_frswim', axis:'endurance', sub:'interval',type:'reps', dir:'higher',target:1000, unit:'米', nameZh:'自由泳 · 1000 米', nameEn:'Freestyle · 1000m', anchor:[0,2000]},\n"
    "    {id:'hpr_ball',   axis:'endurance', sub:'interval',type:'time', dir:'higher',target:60,   unit:'分', nameZh:'篮球 · 60 分', nameEn:'Basketball · 60m', anchor:[0,120]}")
SUB_BLOCK_NEW = SUB_BLOCK_OLD.replace("sub:'interval'", "sub:'cardio'")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, AXES_MOB_OLD, AXES_MOB_NEW,
     "F1 HPR_AXES 抽掉灵活轴 → gate S51 红（六轴单源失守）"),
    (TPL, "'migrateBackup','migrateReport','hpr','health'];", "'migrateBackup','migrateReport','health'];",
     "F2 hpr 从 WORK_KEYS 撤下登记 → gate S51 红（本机账本丢这一片）"),
    (TPL, "function hprAxisScore(", "function hprAxisScoreX(",
     "F3 hprAxisScore 定义改名 → gate S51 红（轴分单源出口被拆）"),
    (TPL, "Math.max(0,Math.min(100,Math.round(currentGl())))", "Math.max(0,Math.min(100,50))",
     "F4 力量轴 GL 现读改成写死 → gate S51 红（系数漂成死数）"),
    (TPL, SUB_BLOCK_OLD, SUB_BLOCK_NEW,
     "F5 耐力轴三个间歇条目改成稳态 → gate S51 红（两个子组都有条目失守）"),
    (TPL, '<div id="hprBoard" class="hpr-board"></div>', '<div class="hpr-board"></div>',
     "F6 摘掉 hprBoard 看板 id → gate S51 红（雷达落不进 AUX 看板）"),
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
