# -*- coding: utf-8 -*-
"""v0.46（运动员水平页单源，gate S48）的反向验证。

    python tools/_sabotage_m17.py inject        # 五处一起注
    python tools/_sabotage_m17.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则成品腿先红
    python tools/gate.py --static               # 期望见下表（只红 S48，其余 47 条不动）
    python tools/_sabotage_m17.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

跑法（驱动器把「注入 → 重建 → 静态对账 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m17 1 5
  （五处全打在模板上，默认重建链 gen_seed → build_html 即可。）

这一族守的是 v0.46 三件**没有别处兜底**的新承诺：

  A. 水平页几何与三小项输入（S48 A 腿）。17 行是全量可编辑表格的清单数，
     行被吞或复制都不会让任何计算出错 —— 只有这一条会在改页那天先响。
  B. CSV 携带 + 钳位单源（S48 B/C 腿）。三小项走 26 列 CSV 只经 PROFILE notes
     一条定义行；钳位只在 saveProfile 写一次。写第二份的人不会自知，
     改口径那天导出侧与 UI 侧才分家。
  C. 快照跟踪键 ↔ 契约 Level.keys（S48 D 腿）。SNAP_TRACK 是 App 与六表 Level 页
     之间唯一的桥面；漂移不会报错，只会让导出静默少列。

五处故障各打在一个承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 年龄行的 lvl-row 容器被拆（class 换成 data 属性）
     → S48 红（A 腿：lvl-row 不是恰好 17 行）。
       症状：这一行脱离表格网格，宽度收紧时它漂出列对齐，清单数与页面悄悄脱钩
  F2 PROFILE notes 丢掉 dipAddedKg 携带
     → S48 红（B 腿：三小项携带行不是恰好一份）。
       症状：双杠附加导不出、跨设备迁移静默归零，导入侧连报错都没有
  F3 引体附加钳位行去掉 Math.max 下界
     → S48 红（C 腿：钳位定义不是恰好一份）。
       症状：负数附加重新入库，与契约 range [0,200] 分家，六表校验开始拒收
  F4 SNAP_TRACK 两个键名漂成 App 外别名（pullupKg/dipKg）
     → S48 红（D 腿：跟踪键与契约 Level.keys 值域不一致）。
       症状：快照导出这两列拿不到值，Level 页永远空两格
  F5 退役 Tab 形态以注释名义在 openProfile 上方复活
     → S48 红（E 腿：profTab 退役写法残留）。
       症状：单页收口被文档性回滚，下一轮「按 Tab 改回去」的寄生代码有了落脚点
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m17.json")
TPL = os.path.join(HERE, "template.html")

# F1（A 腿）：年龄行脱离 lvl-row 容器，17 行数成 16
_F1_OLD = '<div class="lvl-row"><label id="pAgeLbl" for="pAge">'
_F1_NEW = '<div data-rig="1"><label id="pAgeLbl" for="pAge">'

# F2（B 腿）：CSV PROFILE notes 的双杠携带被从定义行里吃掉
_F2_OLD = "pullupAddedKg:p.pullupAddedKg,dipAddedKg:p.dipAddedKg"
_F2_NEW = "pullupAddedKg:p.pullupAddedKg"

# F3（C 腿）：引体附加钳位下界被拆
_F3_OLD = "pullupAddedKg:Math.max(0,gval('pPullup',p.pullupAddedKg||0)),"
_F3_NEW = "pullupAddedKg:gval('pPullup',p.pullupAddedKg||0),"

# F4（D 腿）：跟踪键漂成契约外别名（整行替换，行在文件里唯一）
_F4_OLD = ("const SNAP_TRACK=['bw','sq','bp','dl','ohp','pullupAddedKg','dipAddedKg',"
           "'total','gl','dots','wilks','rankId','rankStars','targetSq','targetBp','targetDl','targetBw'];")
_F4_NEW = ("const SNAP_TRACK=['bw','sq','bp','dl','ohp','pullupKg','dipKg',"
           "'total','gl','dots','wilks','rankId','rankStars','targetSq','targetBp','targetDl','targetBw'];")

# F5（E 腿）：退役 Tab 形态注释复活
_F5_OLD = "function setProfOpt(k, v, silent){"
_F5_NEW = "/* m17-F5 探针：profTab1rmBox 退役形态注释残留 */\nfunction setProfOpt(k, v, silent){"

FAULTS = [
    (TPL, _F1_OLD, _F1_NEW, "F1 年龄行脱离 lvl-row → S48 A 腿红"),
    (TPL, _F2_OLD, _F2_NEW, "F2 notes 丢双杠携带 → S48 B 腿红"),
    (TPL, _F3_OLD, _F3_NEW, "F3 引体钳位下界被拆 → S48 C 腿红"),
    (TPL, _F4_OLD, _F4_NEW, "F4 SNAP_TRACK 键漂出契约值域 → S48 D 腿红"),
    (TPL, _F5_OLD, _F5_NEW, "F5 退役 Tab 注释残留 → S48 E 腿红"),
]

EXPECT = {
    1: "F1 行几何被拆 → S48 红",
    2: "F2 CSV 携带缺失 → S48 红",
    3: "F3 钳位下界被拆 → S48 红",
    4: "F4 跟踪键漂移 → S48 红",
    5: "F5 退役形态残留 → S48 红",
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
