# -*- coding: utf-8 -*-
"""v0.25（写回护栏 S30）的反向验证：证明 S30 那六条腿真的会拦，而不是摆设。

    python tools/_sabotage_w1.py inject          # 六处一起注
    python tools/_sabotage_w1.py inject 2        # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                   # 注的是模板，不重建 S5 先红
    python tools/gate.py --static                # 期望见下表
    python tools/_sabotage_w1.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

S30 管的是「这一节第一次允许落笔改处方」之后的事：v0.24 的引擎只算不写，判据漂移最多让建议
变笨；v0.25 有了应用/撤销，写错一笔就是改坏账本。所以它守的是**出口与口径**，不是数字：
档位与分片键位只有一个出处、改重量只有一支笔、闸门只从契约读上限与跳档后缀、四档的拒绝口径
只写在闸门里、撤销必须认用户的手改、UI 挂载点与产物段落都还在。

六处故障各打在一条承诺上（「红在哪」是单注那一处 + 重建后 `gate.py --static` 实测出来的）：

  F1 PREF_KEYS 的 'advAuto' 改名 → S30 红 ①「advAuto 不在 PREF_KEYS」
     档位是设置，落在 prefs 片；改名等于切了档不持久化，刷新就回到默认 ——
     用户以为开了「确认后应用」，下次打开其实还是「只建议」
  F2 撤销那笔改成 `e.load=it.before;`（绕过 advWriteLoad）
     → S30 红 ②「有 1 处绕过 advWriteLoad 改重量」。这支笔是全节唯一改处方的地方，
       绕开它以后想加「写入前统一校验」就得满文件找赋值
  F3 闸门上限改成字面量 `Math.min(5, Math.abs(before)*0.05)`
     → S30 红 ③「闸门里没读 ar.cap_kg/ar.cap_pct」+「上限写成字面量」，
       并**正确连带** S29 红 ④「引擎代码里手抄了判据 cap_kg=5、cap_pct=0.05」——
       同一件事两处都要拦，契约把上限改成 2.5kg 时建议与闸门会各走一套
  F4 删掉闸门里 `tier==='suggest'` 那一条拒绝
     → S30 红 ④「suggest 的拒绝口径实到 0 次」。这是最坏的一种静默：默认档从此能写盘，
       决策 3 的「不点应用就一个字节都不写」当场失效，而且界面上一切正常
  F5 撤销的手改比对改成 `if(false){`
     → S30 红 ⑤「撤销没做当前值与审计值的比对」。撤销会覆盖用户撤销前自己改的重量
  F6 档位 select 的 onchange 接线去掉
     → S30 红 ⑥「缺档位接线」。文案还在、点不动，用户以为换了档，其实档位永远停在默认

台账 _sabotage_w1.json 存的是注入前模板的整份原文，revert 逐字节放回。
只动模板一个文件，所以每一组都要 `build_html.py` 再跑门禁：不重建的话 S5 会先红
（成品与模板脱节），那是正确行为，但会把 S30 的报错埋掉。

实测（v0.25，静态项数以 gate 自己的输出为准）：
  · 六组单注 + 重建 + `--static` 一律 **28 PASS / 2 FAIL = S26 + S30**：S26 红是「台账在就不许
    发版」那条腿在现场看见了这个注入，属正确连带；S30 的 detail 各自报到自己要红的那条腿——
    F1「① advAuto 不在 PREF_KEYS（档位没进 prefs 片）」
    F2「② 引擎里有 1 处绕过 advWriteLoad 改重量」+「② advWriteLoad 只被调 2 次」（同一条腿的两个问法）
    F3 **27 PASS / 3 FAIL**：S30 红 ③（cap_kg/cap_pct 都没读 + 上限写成字面量），
       同时**正确连带 S29** 红 ④「手抄了判据：cap_pct=0.05、cap_kg=5、step_lower=5」
       —— 5 这个数既是写回上限也是上肢步进，两处守卫都该响，只有一处响才是漏检
    F4「④ 闸门里 suggest 的拒绝口径不在/重复（实到 0 次）」
    F5「⑤ 撤销没做「当前值必须等于审计值」的比对（手改会被覆盖）」
    F6「⑥ 缺 档位接线（onchange="setAdvTier"）」
  · `revert` → `build_html.py` → `--static` 回 **30 PASS / 0 FAIL**（S23 同步核到 139 处靶串 /
    24 个脚本），tools/ 下无 `_sabotage_w1.json` 残留。
  · 动态侧的预期连带（不改静态结论）：F1 红 v3v M10（键位断言）+ v3v P1（档位段入口同钉这把键）+
    S23（m11 首条与本条同串，注入态里它的靶当场找不到）、F2 红 v3v P6（撤销还原）、
    F4 红 v3v P2 + uiv U1（默认档零写盘）、F5 红 v3v P7（撤销拒绝手改）、
    F6 红 uiv U2（切档后行内按钮）。S30 的每一腿都有动态断言在后面兜，静态只是提前一步。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_w1.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "const PREF_KEYS=['lang','theme','timerCfg','plateCfg','venues','activeVenueId','teleFields','favProgs','advAuto','gearKit','teleOn','lcOpen','nick'];",
     "const PREF_KEYS=['lang','theme','timerCfg','plateCfg','venues','activeVenueId','teleFields','favProgs','advTier','gearKit','teleOn','lcOpen','nick'];",
     "F1 档位键改名 → S30 红 ①（advAuto 不在 PREF_KEYS，档位不再持久化）+ v3v M10 红（键位断言认这把键）"
     "+ v3v P1 红（档位段入口同样钉这把键在 prefs 名单）+ S23 红（m11 家的首条与本条同串，"
     "注入态里它那把靶当场找不到 —— 两家盯同一行的不同承诺，这条连带是对的）"),
    (TPL, "    advWriteLoad(e,it.before); restored++;",
     "    e.load=it.before; restored++;",
     "F2 撤销绕过出口 → S30 红 ②（引擎里出现第二个 .load= 赋值）"),
    (TPL, "  const lim=Math.min(+ar.cap_kg, Math.abs(before)*(+ar.cap_pct));",
     "  const lim=Math.min(5, Math.abs(before)*0.05);",
     "F3 上限手抄 → S30 红 ③，正确连带 S29 红 ④（判据从契约换成私货）"),
    (TPL, "  if(tier==='suggest') return advG(",
     "  if(false) return advG(",
     "F4 删掉默认档的拒绝 → S30 红 ④（suggest 口径不在，「只建议」开始写盘）"),
    (TPL, "    if(+e[it.field]!==+it.after){",
     "    if(false){",
     "F5 撤销不认手改 → S30 红 ⑤（比对点消失，撤销会覆盖用户自己的改动）"),
    (TPL, '<select id="advTier" onchange="setAdvTier(this.value)"></select>',
     '<select id="advTier"></select>',
     "F6 档位接线断线 → S30 红 ⑥（文案在、点不动，档位永远停在默认）"),
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
        print(__doc__)
