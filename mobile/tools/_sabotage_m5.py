# -*- coding: utf-8 -*-
"""v0.15（图版配色单源）的反向验证：证明 S20 那五条腿真的会拦。

    python tools/_sabotage_m5.py inject          # 六处一起注
    python tools/_sabotage_m5.py inject 3        # 只注第 3 处（看它只红自己那条腿）
    python tools/gate.py --static                # 期望 S20 变红（详情见下表）
    python tools/_sabotage_m5.py revert          # 逐字节还原
    python tools/gate.py --static                # 期望回到全绿

六处故障各打在 S20 的一个承诺上：

  F1 图版样式区里写死一个色值（.fx-grid 的 stroke 改成 #666666）
     → S20 红「区域有色值字面量」。这条不红的话，换主题时那条线永远灰在纸底上
  F2 类名引用了没声明的令牌（--fig-axis 手抄成 --fig-axix）
     → S20 红「引用了 :root 没声明的令牌」。CSS 变量写错不报错，只会回落到继承色，
       轴刻度文字在暗底上恰好还能读 —— 切到纸底才变成看不见
  F3 FIG_LN 表里的类名多打一个字母（fx-sq → fx-sqx）
     → S20 红「JS 发了没有定义的类名」+「定义了但没人发」，双向都拦住
  F4 类名改回字符串拼接（circle 的 FIG_FN[k] 拼回 'fx-f'+k）
     → S20 红「把类名拼出来了」。拼出来的名字在源码里不存在，静态查不动，
       所以这条腿盯的是「单源写法」本身，不是某个具体名字
  F5 手改成品（只动 assets/index.html 的一条 .fx-* 规则）
     → S20 红「成品与模板不一致」，S5 同时红 —— 这正是产物段比对的职责
  F6 区域标记改名（FIGS-CSS-END → FIGS-CSS-END2）
     → S20 直接 FAIL：取不到被检对象一律判失败，绝不因为「找不到就跑不出结论」而放行

注入目标只在 template.html / assets/index.html 里改字符串，台账（_sabotage_m5.json）
存的是注入前的整份原文，revert 逐字节放回。

静态查不动的那半由动态兜（v0.15 实测）：图例键名不在 S20 射程里——键是数据拼出来的，
静态看不见拼后的串。把 figVolume 的 'ohp' 抄成 'oohp'，S20 全绿而 v3v 的 X7b 报
「无定义键 oohp」。X 段 21 条自己造账本（不依赖前段残留）：X4/X5 双向钉 fx 系类名、
X6 钉只读、X7b 用 getComputedStyle 现读图例键名与色块、X12 逐主题算 WCAG ≥4.5:1。
`revert` + `build_html.py` 后成品与注入前逐字节相同（md5 前缀 `8b2cf5d9`）。

**不要在注入态跑 build_html.py / pack.py**：那会把故障原文固化成最新构建，
revert 之后成品反而和模板脱节。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m5.json")
TPL = os.path.join(HERE, "template.html")
ASSET = os.path.normpath(os.path.join(HERE, "..", "app", "src", "main", "assets", "index.html"))

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, ".fx-grid{stroke:var(--fig-grid)}",
     ".fx-grid{stroke:#666666}",
     "F1 图版样式区写死色值 → S20 红（区域有色值字面量）"),
    (TPL, ".fx-tk{font-family:var(--mono);font-size:7px;fill:var(--fig-axis)}",
     ".fx-tk{font-family:var(--mono);font-size:7px;fill:var(--fig-axix)}",
     "F2 手抄错的令牌名 → S20 红（引用了 :root 没声明的令牌）"),
    (TPL, "var FIG_LN={sq:'fx-sq',bp:'fx-bp',dl:'fx-dl'};",
     "var FIG_LN={sq:'fx-sqx',bp:'fx-bp',dl:'fx-dl'};",
     "F3 类名表里多打一个字母 → S20 红（发的没定义 + 定义的没人发）"),
    (TPL, "'<circle class=\"'+FIG_FN[k]+'\"",
     "'<circle class=\"fx-f'+k+'\"'",
     "F4 类名改回拼接 → S20 红（拼接护栏：单源写法被破）"),
    (ASSET, ".fx-med{stroke:var(--fig-ink)}",
     ".fx-med{stroke:var(--fig-bp)}",
     "F5 只改成品 → S20 红（产物段与模板不同）+ S5 红"),
    (TPL, "/*==FIGS-CSS-END==*/",
     "/*==FIGS-CSS-END2==*/",
     "F6 区域标记改名 → S20 FAIL（取不到被检对象一律判失败）"),
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
    ledger = {}
    faults = FAULTS if pick is None else [FAULTS[pick - 1]]
    for path, old, new, why in faults:
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
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
