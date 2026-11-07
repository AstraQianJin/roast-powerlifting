# -*- coding: utf-8 -*-
"""v0.19（发版预检 S26）的反向验证：证明 S26 那两条腿真的会拦，而不是摆设。

    python tools/_sabotage_r1.py inject          # 五处一起注
    python tools/_sabotage_r1.py inject 3        # 只注第 3 处（核对它只红自己那条腿）
    python tools/gate.py --static                # 期望见下表（S26 一条红，其余不动）
    python tools/_sabotage_r1.py revert          # 逐字节还原 + 删掉探针台账
    python tools/gate.py --static                # 期望回到全绿
    python tools/_sabotage_r1.py --s23-dump      # 只打印现算出的靶串（gate 的 S23 用它核对）

S26 拦的是**发版那一刻**才会犯的两种错，历版都靠人记得。四处指针故障都写成同一个哨兵版本
`v0.00` / code `0`：判据要的是「指针 ≠ gradle」，把上一版的号抄进脚本就等于又造一份手抄副本
（v0.19 实测：靶串写死 `v0.18` 后，gradle 一升到 `v0.19` 这四处全找不到，S23 当场报「脚本已腐」
—— 现算 + `--s23-dump` 才是这一家该有的形状）。

  F1 根 README 的身份行停在旧版本 → S26 红「根 README 身份行 写的是 v0.00/code 0，gradle 是 vX/…」。
     这条对着最常见的漏改：bump 了 gradle，正文那行忘了跟
  F2 CHANGELOG 头条不是正在发的版本
     → S26 红同一条腿。这条对着一个真实顺序错误：先写 CHANGELOG 再 bump gradle，
       或 bump 了 gradle 忘了发版，两处就对不上
  F3 RELEASE_NOTES 头条退回哨兵版本
     → S26 红。**这条对着 v0.17 真实犯过的错**：那版 pack 出了 APK、CHANGELOG 也写了，
       但 release/RELEASE_NOTES.md 的头条还停在 v0.16，装机的人对着新 APK 读旧说明。
       当时没有任何检查会红，只有人对齐日期才发现
  F4 本目录 §1 身份卡只改 versionName 不改 versionCode（两者不再同源）
     → S26 红「写的是 v当前/code 0」。这条腿盯的是「同一个事实的两半各改各的」——
       红线 1 说版本只有一个出处，指针行是给人读的副本，副本内部自己都要先一致
  F5 造一份假台账（tools/_sabotage_r1_probe.json）
     → S26 红「注入态残留台账」。这条腿不看内容只看文件在不在：台账在 = 有脚本
       inject 了没 revert = 源码里现在就是故障原文，此刻跑 pack 会把故障发出去

单注 F1–F4 时，本脚本自己的台账 _sabotage_r1.json 也在，所以 S26 的 detail 里会**同时**
出现「残留台账」和「版本指针漂移」两条——那是 ① 那条腿顺手在现场验到的，不是判据漂了；
只看版本指针那条就按 `inject N` 后读 detail 的第二段。

实测（v0.19，静态项数以 gate 自己的输出为准）：F1 / F2 / F3 / F4 / F5 五组单注都是
**25 PASS / 1 FAIL，只红 S26**——文档不是被检产物，所以这里**没有** S5 连带（对比
`_sabotage_m9.py` 改模板那一家：不重建时 S5 会一起红）。detail 逐条报出漂移值：
F1–F3 是「写的是 v0.00/code 0，gradle 是 v当前/code 当前」，F4 是「写的是 v当前/code 0」
（只有 code 那一半没跟上，正是这条腿要盯的形状），F5 只报台账文件名。合注（四处）同样是 25/1，
把四处漂移一起报出来（截到前五条）。`revert` 会把四处原文逐字节放回并删掉探针台账，
复原后 `--static` 回全绿、`tools/` 下无残留 json。

已知边界：S26 只核对四处**指针的写法与值**，它不知道「这一版到底该不该发」「CHANGELOG 写的内容
对不对」——那些是 §8 与 CHANGELOG 的表述问题，静态管不着。取不到指针样式一律 FAIL，
所以改了这三份文档里那几行的措辞，S26 会当场要求把正则一起改掉（这是故意的：
指针行不许悄悄换写法）。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_r1.json")
PROBE = os.path.join(HERE, "_sabotage_r1_probe.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(HERE)))

DOC_ROOT = os.path.join(ROOT, "README.md")
DOC_MOBILE = os.path.join(ROOT, "mobile", "README.md")
DOC_CHANGE = os.path.join(ROOT, "CHANGELOG.md")
DOC_NOTES = os.path.join(ROOT, "release", "RELEASE_NOTES.md")

# 靶串**从 build.gradle 现读**，不抄版本号：这四行写的就是当前版本，一旦 bump 就跟着变。
# 抄死的话，下一次发版后这些靶串全部找不到 —— S23 会当场报「脚本已腐」（v0.19 实测踩过：
# 靶子抄成 v0.18，gradle 一升到 v0.19 就找不到），而 `inject` 也会打空。
# 现算出来的家族必须支持 `--s23-dump`（见 §3.4 跨切规矩第 5 条），S23 靠它取靶串。
SENTINEL = "0.00"        # 一个绝不等于任何 gradle 值的哨兵：只要求「指针 ≠ gradle」


def _ver_code():
    sys.path.insert(0, HERE)
    import build_html
    return build_html.read_version()      # 读不到就抛，宁可红也不要用过期的靶串


def build_faults():
    ver, code = _ver_code()
    return [
        (DOC_ROOT, "现行版本：`v%s`（versionCode %d）" % (ver, code),
         "现行版本：`v%s`（versionCode 0）" % SENTINEL,
         "F1 根 README 身份行停在旧版本 → S26 红（指针与 gradle 不等）"),
        (DOC_CHANGE, "## [v%s]" % ver, "## [v%s]" % SENTINEL,
         "F2 CHANGELOG 头条不是正在发的版本 → S26 红"),
        (DOC_NOTES, "# ExDark Pro · v%s" % ver, "# ExDark Pro · v%s" % SENTINEL,
         "F3 RELEASE_NOTES 头条落后一版（v0.17 真实犯过的错）→ S26 红"),
        (DOC_MOBILE, "| 现行版本 | `v%s`（`versionName = '%s'` / `versionCode = %d`） |" % (ver, ver, code),
         "| 现行版本 | `v%s`（`versionName = '%s'` / `versionCode = 0`） |" % (ver, ver),
         "F4 身份卡只改 versionName 不改 code → S26 红（副本内部自己都不一致）"),
    ]


FAULTS = build_faults()


def s23_dump():
    """把现算出来的靶串交给 gate 的 S23 核对：每行 [靶文件, 原文片段]。只读，不落盘。"""
    print(json.dumps([[p, old] for p, old, _new, _why in FAULTS], ensure_ascii=False))


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
    if pick == len(FAULTS) + 1:
        # F5：不碰任何文档，只造一份台账样文件——「台账在 = 注入态」这条腿看的就是文件在不在
        with io.open(PROBE, "w", encoding="utf-8") as f:
            json.dump({"_probe": "S26 的 ① 腿用这份假台账验"}, f, ensure_ascii=False)
        print("注入: F5 造一份假台账 %s" % os.path.basename(PROBE))
        return
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
    done = False
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            ledger = json.load(f)
        for path, original in ledger.items():
            write(path, original)
            print("还原: %s" % path)
        os.remove(LEDGER)
        done = True
    if os.path.exists(PROBE):
        os.remove(PROBE)
        print("删除探针台账: %s" % os.path.basename(PROBE))
        done = True
    if not done:
        sys.exit("没有台账 %s 也没有探针 %s，拒绝猜测原文"
                 % (os.path.basename(LEDGER), os.path.basename(PROBE)))


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        pick = int(args[1]) if len(args) > 1 else None
        if pick is not None and not 1 <= pick <= len(FAULTS) + 1:
            sys.exit("故障编号只允许 1..%d" % (len(FAULTS) + 1))
        inject(pick)
    elif mode == "revert":
        revert()
    elif mode == "--s23-dump":
        s23_dump()
    else:
        sys.exit(__doc__)
