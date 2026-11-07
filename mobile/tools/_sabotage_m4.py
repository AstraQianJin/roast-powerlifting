# -*- coding: utf-8 -*-
"""v0.14（主题注册表单源 + Nature 主题）的反向验证：证明 S19 那四条腿真的会拦。

    python tools/_sabotage_m4.py inject          # 四处一起注
    python tools/_sabotage_m4.py inject 2        # 只注第 2 处（看它只红自己那条腿）
    python tools/gate.py --static                # 期望 S19 变红（详情见下表）
    python tools/_sabotage_m4.py revert          # 逐字节还原
    python tools/gate.py --static                # 期望回到全绿（静态项数以 gate 实际输出为准，别抄数字）

四处故障各打在 S19 的一个承诺上：

  F1 亮底规则写回单一主题选择器（[data-mode=light] → [data-theme="light"]）
     → S19 红：既报「规则写死在单一主题上」，又报「CSS 主题块清单与注册表不一致」
  F2 Nature 令牌块少一个键（--surf-hi）→ S19 红：与参照主题的键集不一致
     这条最阴险：纸底上输入框会回落到暗色底，肉眼才看得见，任何断言都看不见
  F3 注册表多写一个没落地的主题名（THEME_IDS 加 'slate'）
     → S19 红：三张映射表的键、令牌块、按钮、span 一起缺
  F4 主题按钮的文案 span 改名（thNatureT → thNatureLabel）
     → S19 红：缺 span。i18n 表按 id 找节点，改名后英文切换会**静默**丢这一格

**S5 必然连带红**：四处都改 template.html，而成品没有重新生成 —— 这正是 S5 的职责，
不是 S19 判定钝化。复原一律走 `revert`，不要跑 `build_html.py`（那会把故障原文固化成最新构建）。

v0.19 起还连带两条，都是**正确行为**、不是判定漂了：合注 + 不重建 → `--static` 实测
`S5 + S19 + S21 + S25 + S26` 五条红（S21：F1 那条规则同段带动效声明；S25：F4 把
`thNatureT` 改名，i18n 表按 id 找节点，正是 19 行预告的那格静默丢失 —— 现在它有守卫了；
S26：台账在 = 不许发版）。只注 F4 时红的是 `S5 + S19 + S25 + S26`。

静态查得动、动态也查得动的对照组（v0.15 实测，跑法：inject N → build_html → 跑回归 →
revert → build_html）：F1 打红 v3v 的 W4（模式开关全失效）、F2 打红 W3、F3 打红
W1+W2+W3+W5+W9 与 uiv 的 X3+X3c、F4 打红 W9。`revert` + 重建后成品与注入前逐字节相同
（md5 前缀 `7ac16676`）。v0.39 起 F4 的动态腿加一条（v3v 的 E8 钉 nature 文案挂载点）、
静态腿加一条（S43 钉 markup 里那句 nature 对外名串，v0.44/F21 起 zh 态是「咖啡纸感」），单注 + 重建实测红
`S19 + S25 + S43 + v3v E8/W9`；合注到静态那层仍是文档上面记的那组。

还原靠注入前写下的原文副本（_sabotage_m4.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m4.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, 'html[data-mode="light"] .card{box-shadow:var(--card-shadow)}',
     'html[data-theme="light"] .card{box-shadow:var(--card-shadow)}',
     "F1 亮底规则写回单一主题选择器 → S19 红（块清单不一致 + 硬编码规则）"),
    (TPL, "  --surf-hi:#FFFDF8; --ink-strong:#241F17;",
     "  --ink-strong:#241F17;",
     "F2 Nature 令牌块少一个键 → S19 红（键集与参照主题不一致）"),
    (TPL, "window.THEME_IDS=['dark','light','nature'];",
     "window.THEME_IDS=['dark','light','nature','slate'];",
     "F3 注册表多一个没落地的主题名 → S19 红（映射键 / 令牌块 / 按钮全缺）"),
    (TPL, '<span id="thNatureT">咖啡纸感</span>',
     '<span id="thNatureLabel">咖啡纸感</span>',
     "F4 主题按钮文案 span 改名 → S19 红（缺 span）+ S25 红（登记表指向不存在的挂载点）"
     "+ S43 红（咖啡纸感 的 markup 串没落位）+ v3v E8 W9 同红（按钮文案取不到）"),
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
