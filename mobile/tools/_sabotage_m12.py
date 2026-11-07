# -*- coding: utf-8 -*-
"""v0.41（装备库 + 场地库 UI）的反向验证：证明 S45 那几条腿真的有牙。

    python tools/_sabotage_m12.py inject        # 五处一起注
    python tools/_sabotage_m12.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static               # 期望见下表
    python tools/_sabotage_m12.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

这一族的五个故障都是**静默型**的：页面不报错、点数不变、别的守卫大多不响。
「红在哪」是单注那一处 + 重建后实测出来的：

  F1 PREF_KEYS 里的 gearKit 改名成 gearKitX（名单还是 11 把钥匙，但那把键漂了）
     → S45 红（gearKit 没登记进 prefs 片名单）+ v3v M10 红（键位名单钉这把键在）
       + v3v EQ4 红（装备存了但 prefs 分片里没有它）+ S23 红（m11 家首条与本条同串，
       注入态里它那把靶当场找不到 —— 两家盯同一行的不同承诺，属正确连带）
       症状就是「今天记的装备，杀掉进程重开全没了」——台账页照常、保存照常，只有落盘没了
  F2 ensureShape 的 gearKit 回填整行删掉（gearSave 里还有一处防御，页面看起来一切正常）
     → S45 红（回填/防御不是恰好两处）+ v3v EQ1 红（旧存档删键后再 ensureShape 就没有这个键）
       少这一行不炸任何现存路径，但「旧存档进来就有空册子」的承诺没了，
       读 gearKit 的分支要各自依赖防御位 —— 防御位哪天被当冗余删掉就是静默数据丢失
  F3 WEAR_CHIP 的 bs 档漂成 wk-bad（页面上还是五枚胶囊，最后一枚从此没色）
     → S45 红（WEAR_CHIP 与契约 wear_levels 不是一对一）+ v3v EQ3 红（胶囊 class 序与契约对不上）
       + S22 红（wk-bad 是「JS 发射、CSS 无规则」的死类名 —— 恰好是那条守卫要抓的形状）
       契约与常量表分家是渐进的：今天漂一档，明天就没人知道页面上该有几档
  F4 closeAllSheets 的名单里漏掉 kitSheet（别的 panel 返回键都收得掉，就这层收不掉）
     → S45 红（收口字面量缺位）。这一族的见证腿按 fast 层判定：S45 稳定、单独成立。
       开 ui 层跑时实测还会连带 uiv A0 红（名单双向对账）与 uiv S 段红（返回键后 .sheet.on 还在），
       外加各段「出段收起」腿（B/L12/M7/M10/N2/N4）跟着碎 —— 但泄漏到哪几条腿是竞态相关的：
       三轮实测里 R3 两轮红一轮绿。连带集合不稳定就不许写进判定（写进去就是下一版的随机 FAIL），
       所以这条只在 fast 层收证据，ui 层的观察记在这里。
  F5 dark 主题令牌块里删掉 --wk-bs 一条（另外两套主题还在，只在暗底战痕累累没色）
     → S45 红（成色色标不是三套主题各定义一次）+ S19 红（令牌键集与其余块不齐 ——
       主题单源守卫盯的就是「一套多一条 / 一套少一条」，这条连带是对的）
       三套主题少一套是「换主题才看得见」的缺陷，回归只在默认主题跑就永远漏过

台账 _sabotage_m12.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

跑法（驱动器把「注入 → 重建 → 各套回归 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m12 1 2 3 4 5 --with fast
F4 的 ui 层连带（双向对账与各段出段收起）实测存在但泄漏集合竞态相关，不写进判定，只按 fast 层收证据。
静态项数以 gate.py 自己的输出为准，这里不抄数字。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m12.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "'advAuto','gearKit','teleOn','lcOpen','nick'];",
     "'advAuto','gearKitX','teleOn','lcOpen','nick'];",
     "F1 prefs 名单里的 gearKit 键名漂了 → S45 红（不在 prefs 片名单）+ v3v M10 红（键位名单）+ v3v EQ4 红（分片里没有装备台账）+ S23 红（m11 家首条与本条同串，属正确连带）"),
    (TPL, "if(!Array.isArray(state.gearKit)) state.gearKit=[];\n  if(!state.gearDefaults",
     "if(!state.gearDefaults",
     "F2 ensureShape 的 gearKit 回填整行删掉 → S45 红（回填/防御不是恰好两处）+ v3v EQ1 红（旧存档删键后 ensureShape 不再补回）"),
    (TPL, "const WEAR_CHIP={fn:'wk-fn',mw:'wk-mw',ft:'wk-ft',ww:'wk-ww',bs:'wk-bs'};",
     "const WEAR_CHIP={fn:'wk-fn',mw:'wk-mw',ft:'wk-ft',ww:'wk-ww',bs:'wk-bad'};",
     "F3 WEAR_CHIP 的 bs 档漂成没色的 class → S45 红（与契约 wear_levels 不是一对一）+ v3v EQ3 红（胶囊 class 序与契约对不上）"),
    (TPL, "'figsSheet','envSheet','kitSheet','sciSheet'",
     "'figsSheet','envSheet','sciSheet'",
     "F4 closeAllSheets 名单漏掉 kitSheet → S45 红（收口字面量缺位）+ uiv A0 红（名单双向对账）+ uiv S 段红（返回键收不掉这一层）"),
    (TPL, "--wk-fn:#43A047; --wk-mw:#1E88E5; --wk-ft:#FFB300; --wk-ww:#FB8C00; --wk-bs:#E53935;",
     "--wk-fn:#43A047; --wk-mw:#1E88E5; --wk-ft:#FFB300; --wk-ww:#FB8C00;",
     "F5 dark 主题删一条成色色标 → S45 红（色标不是三套主题各定义一次）"),
]


EXPECT = {
    1: "S45 红（gearKit 不在 prefs 片名单）+ v3v M10 红（键位名单钉这把键）+ v3v EQ4 红（装备没进 prefs 分片）"
       "+ S23 红（m11 家的首条与本条同串，注入态里它那把靶当场找不到 —— 两家盯同一行的不同承诺，这条连带是对的）",
    2: "S45 红（回填/防御不是恰好两处）+ v3v EQ1 红（旧存档删键后 ensureShape 不再补回 gearKit）",
    3: "S45 红（WEAR_CHIP 与契约 wear_levels 不是一对一）+ v3v EQ3 红（成色胶囊的 class 序与契约对不上）"
       "+ S22 红（wk-bad 是 JS 发射、CSS 无规则的死类名，恰好是那条守卫要抓的形状）",
    4: "S45 红（kitSheet 的返回键收口字面量缺位）。ui 层的连带（名单双向对账与各段出段收起）实测存在"
       "但泄漏到哪几条腿是竞态相关的（三轮里两红一绿），不稳定就不写进判定，详见 docstring",
    5: "S45 红（--wk-bs 色标不是三套主题各定义一次）+ S19 红（主题令牌键集与其余块不齐，属正确连带）",
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
