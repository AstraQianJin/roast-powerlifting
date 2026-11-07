# -*- coding: utf-8 -*-
"""v0.17（清死代码 + 两条新守卫 S22/S23）的反向验证：证明这六条腿真的会拦。

    python tools/_sabotage_m7.py inject          # 六处一起注
    python tools/_sabotage_m7.py inject 2        # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                   # F1/F2/F3 改模板，必须重建，否则 S5 先红
    python tools/gate.py --static                # 期望见下表
    python tools/_sabotage_m7.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到 23/0

一起注 + 重建 实测：21 PASS / 2 FAIL（S22 三条 + S23 两条）。
其中 F4 的红只有单注它、并且**不重建**时才看得见 —— 一重建，成品就和模板重新对齐，
它的活儿被 F1 的模板侧盖住了。这不是 F4 失效，是它的靶本来就在成品那一侧。

六处故障各打在一条承诺上（「红在哪」是单注那一处实测出来的）：

  F1 往样式表塞一条没人发的类规则
     → S22 红「定义了但全站没人发」。本版清掉的 14 个空壳类就是这一类：
       UI 早就改了，CSS 还留着，不崩不报错，只是再没人画它
  F2 把一处 class 字面量拼错（set-go → set-gox，只改这一个站点）
     → 只 S22 红「发出的 class 没有规则」。拼错的类不报错，那一块只是掉回继承样式，
       很容易被当成「设计本来就这样」。选出现 21 次的 set-go 而不是只有一处的类，
       是为了让改错的那一处仍然有其他站点撑腰 —— 不然前向腿会被连坐，看不出谁在报
  F3 把档位徽章的 CSS 选择器改名（映射表不动）
     → S22 红「样式表多出一个没人发的新名」。这条对着本版修掉的真实缺陷：
       actRow 手抄的第二份映射给的是 rts，而规则是 .tier-chip.trts，
       两边词汇不一致 → 动作库里 RTS 档的徽章一直没上色
     反方向（只改映射表的值）S22 量不到，见下面的「已知盲区」
  F4 只改成品（assets/index.html 的样式段加一条规则）
     → S5 红（成品 ≠ 模板+种子重生成）+ S21 的「产物同段」腿红；S22 绿，它只核对模板。
       这一处**不许先重建**，重建会把故障固化成最新构建
  F5 让一个反向验证脚本的靶串腐掉（_sabotage_b4 的 F1 抄回非有限值重构之前的式子）
     → S23 红「靶串在 plan_xlsx.py 里找不到」。这条就是本版抓到的真事：
       b4 的 F1 与 c5 的 G2 都腐了，注入打空、「期望变红」的承诺失效，且没人变红
  F6 让一个靶串变得不唯一（_sabotage_b4 的 F2 改成 plan_xlsx.py 里出现两次的 return 0.0）
     → S23 红「命中 2 次」。不唯一的靶会把不相干的地方一起改掉，故障就不再
       「只打在一个承诺上」——每个脚本自己拒注入的那条规矩，这里由门禁盯着

写这脚本的人得先守一条自己的规矩：**故障名在本脚本里不许带点写成选择器**。
S22 把工具侧「引号 + 点 + 名字」形式的选择器也算「有人发」；这里一旦把故障类名按选择器
写法抄进注释或字符串，自己注入的故障就被自己救活，F1/F3 会一直绿 —— 那是探针自己失效
（AGENTS.md §7 第 4 条），不是「没有死代码」。所以下面用拼接构造选择器，类名单独写、不带点。

台账 _sabotage_m7.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

已知盲区（记下来，别当成已经防住）：S22 的反向腿只读字面量 class="…"，读不到 JS
拼出来的类名，所以改 TIER_CLASS 的**值**不会让它红。本版把三份内联映射折叠成一张表
（tierClass / badgeClass 都从 TIER_CLASS 取），为的就是让这个盲区里最多只有一处可错。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。

豁免不再靠标记，改看**台账在不在**：`_sabotage_m7.json` 还在
就说明本脚本在注入态，此刻它自己的靶串当然对不上，那是故障现场、不是腐，于是跳过它并在
detail 里点名；台账一清（revert 之后），S23 又把本脚本的六处靶串一起核对，脚本不再特殊。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m7.json")
TPL = os.path.join(HERE, "template.html")
ASSET = os.path.normpath(os.path.join(HERE, "..", "app", "src", "main", "assets", "index.html"))
B4 = os.path.join(HERE, "_sabotage_b4.py")

FORM_MARK = "/* ---------- form ---------- */"
DEAD_NAME = "m7-dead-rule"
DEAD_RULE = "." + DEAD_NAME + "{color:#0F0}\n"

TIER_SEL = ".tier-chip."
TIER_OLD = "trts"
TIER_NEW = "trtsx"

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, FORM_MARK, DEAD_RULE + FORM_MARK,
     "F1 样式表加一条没人发的类规则 → S22 红（只剩规则、没人发）"),
    (TPL, 'class="set-go" id="sndBtn"', 'class="set-gox" id="sndBtn"',
     "F2 class 字面量拼错 → S22 红（发出的类没有规则）"),
    (TPL, TIER_SEL + TIER_OLD + "{", TIER_SEL + TIER_NEW + "{",
     "F3 徽章 CSS 选择器改名 → S22 红（映射表还在发旧名，样式表只认新名）"),
    (ASSET, FORM_MARK, DEAD_RULE + FORM_MARK,
     "F4 只改成品 → S5 + S21 产物同段红（S22 只看模板，绿）"),
    (B4, "return round(math.floor(q + 0.5) * s, 6)",
     "return round(math.floor(x / s + 0.5) * s, 6)",
     "F5 反向验证脚本的靶串腐掉 → S23 红（找不到靶，注入打空）"),
    (B4, 'row[rc["pct"]] = round(load_n / anchor, dec)',
     '        return 0.0',
     "F6 靶串不唯一 → S23 红（命中 2 次，会连坐改掉不相干的地方）"),
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
    # 同一文件的多处故障按顺序落在同一份演进文本上，后一处不被前一处的原文盖掉
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
