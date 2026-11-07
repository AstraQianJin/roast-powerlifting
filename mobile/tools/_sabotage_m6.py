# -*- coding: utf-8 -*-
"""v0.16（动效时长单源）的反向验证：证明 S21 那五条腿真的会拦。

    python tools/_sabotage_m6.py inject          # 六处一起注（成品会被前五项盖掉，只看总数）
    python tools/_sabotage_m6.py inject 2        # 只注第 2 处（看它只红自己那条腿）
    python tools/build_html.py                   # F1–F5 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static                # 期望 S21 变红（详情见下表）
    python tools/_sabotage_m6.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

六处故障各打在 S21 的一个承诺上：

  F1 面板入场时长写死（scrim-in 的 var(--dur-base) 改成 .3s）
     → S21 红「声明里写死时长」。动效不像颜色那样有最终态可查：它只改变中间帧，
       而无头回归量的就是中间帧落地之后的矩形 —— 写死一处没人会红，只会「手感散了」
  F2 缓动令牌改名（--ease-out → --ease-out2，引用点不动）
     → S21 双向都红：CSS 引用了 :root 没声明的令牌 + 声明了没人引用。
       CSS 变量名写错不报错，动画只是回落成默认 ease，肉眼几乎看不出来
  F3 删掉 prefers-reduced-motion 兜底块
     → S21 红「缺兜底块」。这条是令牌化的真正收益：一处开关能关掉全站动效
  F4 兜底块复制成两处
     → S21 红「兜底写了 2 处，只允许一处」。散落第二份的那一刻起，
       新增规则就只会被其中一份盖住，迟早漏
  F5 @keyframes 名字打错（panel-in → panel-inx）
     → S21 红「animation 引用了没有定义的名字」+「定义了没人引用」。
       动画名对不上不抛错，面板只是直接显示出来 —— 没有任何断言会因为「不动」而变红
  F6 只改成品（assets/index.html 里把 drawer-in 的时长抄成 .5s）
     → S21 红「成品 <style> 段与模板不同」，S5 同时红 —— 产物同段这条腿的职责。
       这一处**不许先重建**，重建会把故障固化成最新构建

注入目标只在 template.html / assets/index.html 里改字符串，台账（_sabotage_m6.json）
存的是注入前的整份原文，revert 逐字节放回。

逐条隔离实测（v0.16 首跑，当时静态项数比现在少，只核「红在哪条」）：改模板的 F1–F5
按 `inject N → build_html → --static` 各**只红 S21**一条；F6 改成品，**不许先重建**，
不重建时红 S21 + S5 两条，一重建就被覆盖。`revert` + 重建后成品与注入前逐字节相同
（md5 前缀 `a6cdfbe7`）。动效这一族的动态侧为什么不够看：uiv 量的是动画落地后的矩形，
中间帧写死或丢了兜底都不会让它红，所以 S21 是这一族唯一的信号。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m6.json")
TPL = os.path.join(HERE, "template.html")
ASSET = os.path.normpath(os.path.join(HERE, "..", "app", "src", "main", "assets", "index.html"))

RM_BLOCK = ("@media (prefers-reduced-motion:reduce){\n"
            "  *,*::before,*::after{animation-duration:.001ms!important;"
            "transition-duration:.001ms!important}\n}\n")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, ".sheet.on{animation:scrim-in var(--dur-base) linear}",
     ".sheet.on{animation:scrim-in .3s linear}",
     "F1 入场时长写死 → S21 红（声明里有字面时长，改走 --dur-* 令牌）"),
    (TPL, "--ease-out:cubic-bezier(.2,.8,.2,1);",
     "--ease-out2:cubic-bezier(.2,.8,.2,1);",
     "F2 令牌改名引用点不动 → S21 红（引用没声明 + 声明没人引用，双向）"),
    (TPL, RM_BLOCK, "",
     "F3 删掉减动兜底 → S21 红（兜底块取不到）"),
    (TPL, RM_BLOCK, RM_BLOCK + RM_BLOCK,
     "F4 兜底复制成两处 → S21 红（只允许一处开关）"),
    (TPL, "@keyframes panel-in{",
     "@keyframes panel-inx{",
     "F5 动画名打错 → S21 红（引用的没定义 + 定义的没人引用）"),
    (ASSET, ".sheet.down.on .panel{animation:drawer-in var(--dur-base) var(--ease-out)}",
     ".sheet.down.on .panel{animation:drawer-in .5s var(--ease-out)}",
     "F6 只改成品 → S21 红（产物 style 段与模板不同）+ S5 红"),
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
    planned = []
    for path, old, new, why in faults:
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
        planned.append((path, src, hit, new, why))
    ledger = {}
    for path, src, hit, new, why in planned:
        ledger.setdefault(path, src)
        write(path, src.replace(hit, new, 1))
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
