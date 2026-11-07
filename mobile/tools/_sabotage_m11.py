# -*- coding: utf-8 -*-
"""v0.40（会员徽记 + 状态监控默认关闭）的反向验证：证明 S44 那几条腿真的有牙。

    python tools/_sabotage_m11.py inject        # 五处一起注
    python tools/_sabotage_m11.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static               # 期望见下表
    python tools/_sabotage_m11.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

这一族的五个故障都是**静默型**的：页面不报错、点数不变、别的守卫也不响。
「红在哪」是单注那一处 + 重建后实测出来的：

  F1 PREF_KEYS 里的 teleOn 改成 teleOnx（键名漂了，片还是那片）
     → S44 红「teleOn 没登记进 prefs 片名单」+ v3v M10 红（键位名单）+ v3v TM4 红（点开了但盘上没有）
       + S23 红（w1 家 F1 的靶与本条同一行，注入态里当场找不到 —— 两家盯同一行的不同承诺，属正确连带）
       症状是「今天打开的开关，杀掉进程重开又关上」——面板照常、开关照常，只有记忆没了
  F2 ensureShape 的回填判据从 ===true 翻成 !==false（默认从关变成开）
     → S44 红「接线/回填缺位或重复」+ v3v TM2 红（那条现点一次「旧存档缺这个键」）
       + v3v TM3/TM4 红（默认被弹成开之后，TM 段「关着」的前提连着碎 —— 实测真连带）
       这条最阴：新装的用户一切正常，只有**旧存档**的用户升级后开关自己弹回开启，
       而「默认关闭」正是这一版的承诺。新建账走的是 fresh 分支、看不出这件事，
       所以 TM2 里必须 `delete state.teleOn` 再 `ensureShape()`，把回填结果一起钉进去
  F3 openTeleSheet 头上的闸门条件改成恒假（if(false){ —— 关着也放行，闸门失效）
     → S44 红「if(!teleOn()){ 缺位」+ v3v TM3 红（关着还能把面板打开、回执也不再指路）
       关掉之后只剩藏舱钮一条腿，键盘/脚本仍直呼得进——「关」成了视觉提示而不是状态
       （TM 段开头先把 day/week 钉在 A·W1：面板取不到格子会抛，那一刻 Z0 接管、
        整段断言一起消失，红的是「驱动器没跑完」而不是「闸门没了」——第一轮实测真撞过）
  F4 徽记写回标题里、还退回旧标签（h1 内一个裸 em 包 ProMax）
     → S44 红（徽记 markup 不唯一 + ProMax 残留）+ v3v A5 红（可见文案里冒出退役标签）
       + v3v N2 红 + v3v TM1 红
       这一处**不红 S22**，而且是本工具既有的脾气：S22 把「工具侧点过名」也算可达，
       而 S44 自己的见证串就是 `".pro-mark{"` —— 这条规则的牙由 S44 的 markup 计数兜，不由 S22 兜
  F5 体重趋势不再从 bwSeries() 取数（改成现摆一个空对象）
     → S44 红「bwSeries 的读者不是恰好两处」+ v3v TM5 红（那一行永远说「记录不足两周」）
       表现是「明明记了三周体重，运动员页却说不足两周」——读的是第二份口径，不是没数据

台账 _sabotage_m11.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

跑法（驱动器把「注入 → 重建 → 各套回归 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m11 1 2 3 4 5 --with fast
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
LEDGER = os.path.join(HERE, "_sabotage_m11.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "'advAuto','gearKit','teleOn','lcOpen','nick'];",
     "'advAuto','gearKit','teleOnx','lcOpen','nick'];",
     "F1 prefs 名单里的键名漂了 → S44 红（teleOn 不在 PREF_KEYS）+ v3v TM4 红（开关点了不落盘）"),
    (TPL, "state.teleOn=(state.teleOn===true);",
     "state.teleOn=(state.teleOn!==false);",
     "F2 旧存档回填的默认从「关」翻成「开」 → S44 红（回填字面量不在）——老用户升级后开关自己弹开"),
    (TPL, "if(!teleOn()){",
     "if(false){",
     "F3 面板头上的闸门条件改成恒假 → S44 红（闸门调用点不在）+ v3v TM3 红（关着还进得去、回执不再指路）"),
    (TPL, '<h1><span class="ex-script">ExDark</span></h1><span class="pro-mark"><i>\u2726</i>Pro</span>',
     '<h1><span class="ex-script">ExDark</span><em>ProMax</em></h1>',
     "F4 徽记退回标题内的裸 em 还带退役标签 → S44 红（markup 不唯一 + ProMax 残留）+ v3v A5/N2/TM1 红（类名双向可达那条守卫不红属预期，见 EXPECT）"),
    (TPL, "  const vals=bwSeries();\n  const ks=Object.keys(vals)",
     "  const vals={};\n  const ks=Object.keys(vals)",
     "F5 体重趋势的第二份口径 → S44 红（bwSeries 读者不是两处）+ v3v TM5 红（那一行永远「记录不足两周」）"),
]


EXPECT = {
    1: "S44 红（teleOn 不在 prefs 名单）+ v3v M10 红 + v3v TM4 红 + S23 红（w1 家的首条与本条同串，"
       "注入态里它那把靶当场找不到 —— 两家盯同一行的不同承诺，这条连带是对的）",
    2: "S44 红（回填字面量不在）+ v3v TM2 红（旧存档缺键时被回填成「开」）+ v3v TM3 红 + v3v TM4 红"
       "（本条把默认弹成开，TM 段「关着」的前提连着碎 —— 后两条是真连带，不是误伤）",
    3: "S44 红（闸门调用点不在）+ v3v TM3 红（关着还进得去、回执不再指路）",
    4: "S44 红（徽记 markup 不唯一 + ProMax 残留）+ v3v A5 红 + v3v N2 红 + v3v TM1 红。"
       "类名双向可达那条守卫不红属预期：它把「工具侧点过名」也算可达，而本家守卫的见证串就是 "
       "`.pro-mark{` —— 这条规则的牙由 markup 计数兜，不由那条守卫兜",
    5: "S44 红（bwSeries 读者不唯一）+ v3v TM5 红（那一行永远「记录不足两周」）",
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
