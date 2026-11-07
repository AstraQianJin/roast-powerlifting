# -*- coding: utf-8 -*-
"""v0.39（阶段独立 UI + nature→Extra Dark 改名）的反向验证：证明 S43 那几条腿真的有牙。

    python tools/_sabotage_m10.py inject        # 五处一起注
    python tools/_sabotage_m10.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static               # 期望见下表
    python tools/_sabotage_m10.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

五处故障各打在一个承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 阶段行偷偷回到行网格（第二个出口）
     → S43 红「行网格里还留着阶段行」+ v3v P11 P12 同红。这条对着本版立守卫的原因：
       阶段有两个出口时两处迟早算出两个数，用户在条里看到的和行里看到的不是同一件事
  F2 阶段条外壳挂载点改名（ga-phase → ga-phasex）
     → S43 红「发射点不是恰好一处」+ S22 红（发出去的 class 没有规则）+ v3v P12 红
       （那条数外壳个数，就为这一类「肉眼看不出来、页面也不报错」的漂准备的）
  F3 旧对外名回到 i18n 表（zh 咖啡纸感 / en Extra Dark → 纸墨 / Paper Ink）
     → S43 红「nature 槽位不是 zh=咖啡纸感 / en=Extra Dark」+ 旧名残留；v3v E8 同红（zh 态按钮文案）
  F4 内部 id 跟着改名（THEME_IDS 里 nature → extradark）
     → 这是**红线**：改名只许改对外名字，存量存档里的 state.theme='nature' 一迁移就断链。
       S43 红「内部 id 被改了」+ S19 红（注册表与令牌块/按钮对齐）+ S23 红（m4 家那颗
       同串的靶当场找不到 —— 两家盯同一个承诺，这条连带是对的）+ 动态 W 段一起红
       （W1 W2 W3 W4 W5 W9：那张注册表就是它们的数据源，文案按 id 取，取不到是空格）
  F5 无 Peak 角标的 CSS 规则改名（.ga-peak → .ga-peakx）
     → S43 红「缺 CSS 规则」+ S22 红：JS 还发 ga-peak，CSS 没这条规则，表现是那一枚角标
       静默走默认样式（不报错、不掉格）。S22 的名单是「模板里发出的 class ↔ 样式表规则」
       双向核对，ga-* 也在里面 —— v0.38 那批 pc-* 之所以归 S42 自包，是因为那批名字带
       令牌配对的家规（三块主题各一份），不是 S22 管不着这一族

台账 _sabotage_m10.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

跑法（驱动器会把「注入 → 重建 → 各套回归 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m10 1 2 3 4 5 --with fast
静态项数以 gate.py 自己的输出为准，这里不抄数字。实测：F1/F2/F3/F5 各红自己那条目标腿
加就近的连带（P11 P12 / S22 / E8 / S22），F4 是五组里唯一「静态三条腿 + 动态 W 段六腿」
一起红的——内部 id 一动，注册表的每个读者都跟着抖，这正是它被写成红线的原因。
五组的还原都是逐字节相同、复跑回绿。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m10.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "{zh:'周期', en:'CYCLE', v:weeks+' '+L('周','wk')},",
     "{zh:'阶段', en:'PHASE', v:phases.length+' blocks'},\n    "
     "{zh:'周期', en:'CYCLE', v:weeks+' '+L('周','wk')},",
     "F1 阶段行回到行网格 → S43 红（阶段有第二个出口）+ v3v P11 P12 同红（数据腿与 DOM 腿都抓到那一行）"),
    (TPL, '<div class="ga-phase">',
     '<div class="ga-phasex">',
     "F2 阶段条外壳挂载点改名 → S43 红（发射点不唯一）+ S22 红（发出去的 class 没有 CSS 规则）+ v3v P12 红（外壳个数不是 1）"),
    (TPL, "thNatureT:['咖啡纸感','Extra Dark'],",
     "thNatureT:['纸墨','Paper Ink'],",
     "F3 旧对外名回到 i18n 表 → S43 红（不是 zh=咖啡纸感 / en=Extra Dark + 旧名残留）+ v3v E8 红（zh 态按钮文案）"),
    (TPL, "window.THEME_IDS=['dark','light','nature'];",
     "window.THEME_IDS=['dark','light','extradark'];",
     "F4 内部 id 跟着改名 → S43 红（id 不再是 nature，存量存档断链）+ S19 红（映射键/令牌块/按钮对不上）+ S23 红（m4 家那颗同串的靶没了）+ v3v W1 W2 W3 W4 W5 W9 同红（注册表是它们的数据源）"),
    (TPL, ".ga-peak{",
     ".ga-peakx{",
     "F5 无 Peak 角标的 CSS 规则改名 → S43 红（缺 CSS 规则）+ S22 红（JS 还发 ga-peak，发出的 class 没规则，静默走默认样式）"),
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
