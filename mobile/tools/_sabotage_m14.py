# -*- coding: utf-8 -*-
"""v0.44（器械 UI 止血 F13/F14/F15）的反向验证：证明这一版新加的 v3v 腿真的有牙。

    python tools/_sabotage_m14.py inject        # 七处一起注
    python tools/_sabotage_m14.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    node tools/v3v.js                           # 期望见下表（只红那一条腿，其余不动）
    node tools/gearv.js                         # F6/F7 红在 G11
    python tools/_sabotage_m14.py revert        # 逐字节还原
    python tools/build_html.py && node tools/v3v.js   # 期望回到全绿

跑法（驱动器把「注入 → 重建 → 各套回归 → 对账 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m14 1 2 3 4 5 6 7 --with fast

这一族守的是同一类坏法：**v0.44 把三处「界面看得见的错」补成了承诺，而这类补丁最容易被
后人"顺手简化"回去** —— 简化完功能测试照旧全绿，因为「哑铃画了根灰杆」「计算器永远展开」
「勾完成只勾一半组数」在回归里根本不会被点到。所以每条新腿都要有一个反向验证靶，
且打的都是**这一版新写的那行代码**（不是去改 platesPerSide 那种既有核心算学，免得连带红一片）。

七处故障各打在一个新承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 toggleDone 里的满组同步 `e.doneSets=e.done?total:0;` 整行拆掉
     → v3v F15a 红（勾上后 doneSets 不再等于 total，停在 0）+ F15c 红（源码里那句赋值没了）。
       F15b 仍绿：拆的是组数同步，没碰 reps/RPE/备注 —— 这正是 F15b 要守的「勾选不改写手填」
       症状：点 ✅ 只把 done 翻成 true，卡片 SET 还停在 0/3，"完成"了却看着像没做
  F2 横杆判定 `!isBar` 退回旧的三分支 `isPlate||isStack||isSpecial`
     → v3v T9a 红（哑铃 / 自重不再带 no-sleeve，::before 又画出那根 20kg 灰杆）。
       这条对着 F13 的原话「非杠铃不画横向杠铃杆」：旧三分支漏了 dumbbell 和 bw 两类
       症状：哑铃、自重动作的配重条左边凭空长出一根杠铃套管轴
  F3 lcApplyFold 的默认判定 `const collapsed=state.lcOpen!==true;` 漂成恒假 `=false`
     → v3v T9d 红（六类器械一进编辑器就摊开，默认收起失守）
       症状：配重计算器不再默认收起，编辑页永远被输入区占着
  F4 lcToggle 的 `state.lcOpen=expanded;` 漂成 `=true`
     → v3v T9g 红（想收起却被写回展开：折叠钮不可逆，越点越开）
       症状：用户手动收起计算器后又被弹开，收起动作没法生效
  F5 lcToggle 里的 `savePrefsOnly();` 被拆掉
     → v3v T9f 红（展开状态只在内存里，prefs 分片没落 lcOpen）
       症状：这次展开过，下次打开编辑器又回到收起，等于没记住
  F6 gearKindGuess 里的 `gearKindZh(...)` 调用被拆
     → gearv G11.1 红（中文动作名不再定向，插片/挂片/坐姿器械全兜回 barbell）
       症状：首页又一次满屏杠铃片——Hammer Select 画成挂片、坐姿器械画成杠铃
  F7 挂片 glyph 的 `<i class="geg-post"></i>` 被拿掉
     → gearv G11.2 红（挂片只剩片条，没有挂片柱，六类形状语言少一角）

没有单独设靶的三条新腿，牙来自别处，不是摆设：
  · T9b/T9c 是**回归锁**：platesPerSide 本就是杠铃专属（solveLoad 只在 isBar 时调它），
    "低于空杆重量"根本串不到非杠铃。T9c 钉住「杠铃空载仍如实报这条警告」——
    谁要为了 T9b 一刀切删掉这条警告，T9c 立刻红。它们的牙是彼此，不是再去动核心算学。
  · T9e（切到插片仍保持收起）是 T9d 的 converse，同由 lcApplyFold 驱动：它独立的坏法
    只有「lcApplyFold 被 kind 分支绕过」，正是 F3 守的那行。
  · F15b（勾选不改写 reps/RPE/备注）是锁：它的坏法是"额外加一句改写"，不是"简化掉一句"，
    没有对应的自然回归靶；F15a/F15c 红时它仍绿，已证明拆满组同步不会顺手动到那四格。

台账 _sabotage_m14.json 存的是注入前每个文件的整份原文，revert 逐字节放回。
**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m14.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "e.doneSets=e.done?total:0;",
     "/* m14-F1 探针：满组同步被拆 */",
     "F1 toggleDone 满组同步整行拆掉 → v3v F15a 红（doneSets 停在 0）+ F15c 红（源码赋值缺位）"),
    (TPL, "pvBar.classList.toggle('no-sleeve', !isBar);",
     "pvBar.classList.toggle('no-sleeve', isPlate||isStack||isSpecial);",
     "F2 横杆判定退回旧三分支 → v3v T9a 红（哑铃/自重又画出灰杆）"),
    (TPL, "const collapsed=state.lcOpen!==true;",
     "const collapsed=false;",
     "F3 计算器默认折叠恒假 → v3v T9d 红（默认就摊开）"),
    (TPL, "state.lcOpen=card.classList.contains('collapsed');",
     "state.lcOpen=true;",
     "F4 折叠钮收起时也把状态写回 true → v3v T9g 红（收起后又被展开）"),
    (TPL, "  state.lcOpen=card.classList.contains('collapsed');\n  savePrefsOnly();",
     "  state.lcOpen=card.classList.contains('collapsed');",
     "F5 展开状态不写 prefs → v3v T9f 红（换页/重开后不记得展开过）"),
    (TPL, "  const zk=gearKindZh(zh||String(mv||''));\n  if(zk) return zk;\n",
     "",
     "F6 中文动作名定向被拆 → gearv G11.1 红（插片/挂片/坐姿器械全兜回 barbell）"),
    (TPL, "data-gz=\"horn\" data-side=",
     "data-side=",
     "F7 挂片轴的 horn 钩子被拆 → gearv G11.2 红（首页挂片不再画轴）"),
]


EXPECT = {
    1: "F1 满组同步被拆 → v3v F15a 红 + F15c 红",
    2: "F2 横杆判定退回旧三分支 → v3v T9a 红",
    3: "F3 计算器默认折叠恒假 → v3v T9d 红",
    4: "F4 收起仍写 lcOpen=true → v3v T9g 红",
    5: "F5 展开状态不写 prefs → v3v T9f 红",
    6: "F6 中文动作名定向被拆 → gearv G11.1 红",
    7: "F7 挂片 glyph 竖柱被拆 → gearv G11.2 红",
}


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
