# -*- coding: utf-8 -*-
"""v0.47（主页打气/日历引擎/器械视觉，gate S49）的反向验证。

    python tools/_sabotage_m18.py inject        # 五处一起注
    python tools/_sabotage_m18.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则成品腿先红
    python tools/gate.py --static               # 期望见下表（只红 S49，其余 48 条不动）
    python tools/_sabotage_m18.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

跑法（驱动器把「注入 → 重建 → 静态对账 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m18 1 5
  （五处全打在模板上，默认重建链 gen_seed → build_html 即可。）

这一族守的是 v0.47 五件**没有别处兜底**的新承诺：

  A. 昵称截断钳位单源（S49 B 腿）。24 字符钳位只许写在 saveNick 一行；改数当天
     不会炸，昵称超长被悄悄吞或界面与落盘分家那天才错。PREF_KEYS 登记那条腿与
     w1/m11/m12 三家的靶串同行重叠，改它必连带 S23，所以由 v3v HX4 动态兜底
     （prefsOf().nick 往返 + work 片零出现），本家族不注它。
  B. 星期名单单源（S49 A 腿）。回退英文名单一旦复活，契约缺值时页面说英文、
     WD_ZH 说中文，两套名字在同一天并存 —— 只有这一条能当场响。
  C. 横幅必须走日历引擎（S49 C 腿调用位）。planPos 的 off-plan 判定只经
     todaySessions 一个入口；调用位被换回 state.week 旧口径，横幅当天照常绿，
     换周口径分家那天才错。
  D. 器械分支完整（S49 E 腿）。哑铃分支是四形态里唯一靠一条 else-if 连着的；
     条件被改名的瞬间不炸，之后所有 dumbbell 记录画成杠铃。
  E. 根滚动容器不许退回 overflow-x:hidden（S49 B2 腿）。html/body 一旦用 hidden，
     真机上整页拖动会被那个「不可滚」的容器吞掉（v0.58 真机回归的原症状）；
     这条只能靠静态闸门当场响。

五处故障各打在一个承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 saveNick 钳位 24 改 12
     → S49 红（B 腿：昵称 24 字符截断钳位不是恰好一份）。
       症状：入库钳位悄悄改数，nickName 的 24 截断与落盘口径分家
  F2 星期名单回退手抄英文版复活
     → S49 红（A 腿：模板出现 ['Mon','Tue' 第二份名单）。
       症状：契约缺 weekday_labels 时结构页下拉说英文，与 WD_ZH 中文永久分家
  F3 横幅调用位退回 state.week 旧口径（renderHeader 里的 todaySessions 不再被调用）
     → S49 红（C 腿：const p=todaySessions(); 不是恰好一份）。
       症状：off-plan/结束周照常显示「今天是…」，planPos 的新口径白改
  F4 哑铃分支条件漂名（isDumb → isDumbX）
     → S49 红（E 腿：哑铃渲染分支不是恰好一条）。
       症状：dumbbell 记录整体落到杠铃套管渲染，双手/单边总重读数全错
  F5 根规则退回 overflow-x:hidden
     → S49 红（B2 腿：html/body 根规则用了 overflow-x:hidden）。
       症状：真机上拖动被 body 的不可滚容器吞掉，整页划不动
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m18.json")
TPL = os.path.join(HERE, "template.html")

# F1（B 腿）：saveNick 入库钳位改数 —— 24 只许这一行（nickName 的 slice(0,24) 无 trim 前缀，不同串）
_F1_OLD = "state.nick=String(v!=null?v:(state.nick||'')).trim().slice(0,24);"
_F1_NEW = "state.nick=String(v!=null?v:(state.nick||'')).trim().slice(0,12);"

# F2（A 腿）：回退分支把英文星期名单手抄回来
_F2_OLD = "const wlabels=(PLAN_SCHEMA.sheets&&PLAN_SCHEMA.sheets.Days.weekday_labels)||[];"
_F2_NEW = ("const wlabels=(PLAN_SCHEMA.sheets&&PLAN_SCHEMA.sheets.Days.weekday_labels)"
           "||['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];")

# F3（C 腿）：横幅调用位被换回 state.week 旧口径
_F3_OLD = "const p=todaySessions();"
_F3_NEW = "const p={ok:true,week:state.week,wd:0,list:daysOnWd(0)};"

# F4（E 腿）：哑铃分支条件漂名，else-if 链被吞
_F4_OLD = "}else if(isDumb){"
_F4_NEW = "}else if(isDumbX){"

# F5（B2 腿）：根规则退回 overflow-x:hidden（真机会吞掉整页滚动）
_F5_OLD = "overflow-x:clip;overflow-y:visible;overscroll-behavior:none"
_F5_NEW = "overflow-x:hidden;overflow-y:visible;overscroll-behavior:none"

FAULTS = [
    (TPL, _F1_OLD, _F1_NEW, "F1 saveNick 钳位改数 → S49 B 腿红"),
    (TPL, _F2_OLD, _F2_NEW, "F2 手抄英文星期名单复活 → S49 A 腿红"),
    (TPL, _F3_OLD, _F3_NEW, "F3 横幅退回 state.week 旧口径 → S49 C 腿红"),
    (TPL, _F4_OLD, _F4_NEW, "F4 哑铃分支条件漂名 → S49 E 腿红"),
    (TPL, _F5_OLD, _F5_NEW, "F5 根规则退回 overflow-x:hidden → S49 B2 腿红"),
]

EXPECT = {
    1: "F1 昵称钳位改数 → S49 红",
    2: "F2 星期名单双源复活 → S49 红",
    3: "F3 横幅调用位漂移 → S49 红",
    4: "F4 哑铃分支被吞 → S49 红",
    5: "F5 根规则退回 overflow-x:hidden → S49 红",
}


def read(p):
    # newline=''：逐字节读写，还原时不会把 LF 文件悄悄改成 CRLF
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
