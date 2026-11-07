# -*- coding: utf-8 -*-
"""v0.45（GPP/JTS 目录单源，gate S47）的反向验证。

    python tools/_sabotage_m16.py inject        # 四处一起注
    python tools/_sabotage_m16.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板/种子，必须重建，否则 S5 先红
    python tools/gate.py --static               # 期望见下表（只红 S47，其余 46 条不动）
    python tools/_sabotage_m16.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

跑法（驱动器把「注入 → 重建 → 静态对账 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m16 1 4
    python tools/sabr.py run m16 2 3 --build build_html.py
  （F2/F3 打在 seed.json 上：默认链先跑 gen_seed，会用工作簿把种子重生成一遍、
    故障还没见到门禁就被抹掉——所以这两条只许 build_html 重建。）

这一族守的是 v0.45 两块**没有别处兜底**的新承诺：

  A. 恢复通道数字单源（S47 A/D 腿）。上限/夹紧一旦被手抄成第二份，格差当天不出现，
     目录改数那天才在某一侧静默漂走 —— 正是「多处单源」红线里最难看见的那类。
  B. 种子 GPP 规范序 + 目录富化（S47 B/C 腿）。种子出厂形状与 App gppCanonDefs 的
     恒等关系是全链路对账（D8/xlsxv W0）的地基；地基歪了，第一响应该是 S47，
     而不是等到逐格对账长出几百格差异。

四处故障各打在一个承诺上（「红在哪」是单注那一处 + 重建后实测出来的）：

  F1 gppRecoveryOf 的上限读口换成写死 0.08/0.06
     → S47 红（A 腿：读口不是恰好一份 + 手抄形态出现）。
       症状：目录 b_gpp/f_gpp 改数后，恢复乘数继续吃旧上限，UI 公式行与引擎分家
  F2 seed.gpp[0].metricType 漂成契约外度量 'steps'
     → S47 红（B 腿：度量不在 metric_type_enum）。
       症状：种子与目录枚举脱钩，GPP 表导出带着非法度量过契约闸门再被导入侧拒收
  F3 HIIT 自定义定义整块换成旧名 Foam 的自定义定义
     → S47 红（C 腿：legacy_map 旧行 4 的 new_ids[0]=foam_roll 在菜单覆盖里，
       种子却把它的旧名落成自定义）。
       症状：同一动作两份定义（菜单一行 + 自定义一行），项天计数翻倍、rec_bonus 双记
  F4 模板注释里残留退役域名 'CARDIO RESPIRATORY'
     → S47 红（E 腿：退役写法残留）。
       症状：旧 AUX 域名单源在模板里复活，下一轮「按旧域对齐」的漂移代码有了寄生处
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m16.json")
TPL = os.path.join(HERE, "template.html")
SEED = os.path.join(HERE, "seed.json")

_F1_OLD = "const capB=+((GPP_RECOVERY.b_gpp||{}).cap), capF=+((GPP_RECOVERY.f_gpp||{}).cap);"
_F1_NEW = "const capB=0.08, capF=0.06; /* m16-F1 探针：上限手抄 */"

# F2/F3 打在 seed.json 上（indent=1 出厂格式，键缩进 3 空格）：串在文件里恰好一份
_F2_OLD = '   "metricType": "time",\n   "targetValue": "",\n   "targetUnit": "",\n   "rx": "30 min'
_F2_NEW = '   "metricType": "steps",\n   "targetValue": "",\n   "targetUnit": "",\n   "rx": "30 min'

_F3_OLD = ('   "domain": "aerobic",\n   "item": "Interval HIIT",\n   "metricType": "time",'
           '\n   "targetValue": "",\n   "targetUnit": "",\n   "rx": "12 min",\n   "intensity": "",'
           '\n   "loadKg": "",\n   "targetRpe": 7.5,\n   "custom": true')
_F3_NEW = ('   "domain": "mobility",\n   "item": "Foam Roll · Joint Mobility · Thoracic Rotation",'
           '\n   "metricType": "",\n   "targetValue": "",\n   "targetUnit": "",\n   "rx": "20 min",'
           '\n   "intensity": "",\n   "loadKg": "",\n   "targetRpe": "",\n   "custom": true')

_F4_OLD = "/* 恢复两通道（GPP 契约 recovery.b_gpp / f_gpp）：上限都从契约取，不写第二份 0.08 / 0.06。 */"
_F4_NEW = "/* m16-F4 探针：旧域 CARDIO RESPIRATORY 残留 */" + _F4_OLD

FAULTS = [
    (TPL, _F1_OLD, _F1_NEW, "F1 恢复上限读口手抄成 0.08/0.06 → S47 A 腿红"),
    (SEED, _F2_OLD, _F2_NEW, "F2 种子菜单项度量漂成契约外 'steps' → S47 B 腿红"),
    (SEED, _F3_OLD, _F3_NEW, "F3 菜单覆盖项退回自定义区 → S47 C 腿红"),
    (TPL, _F4_OLD, _F4_NEW, "F4 模板残留退役 AUX 域名 → S47 E 腿红"),
]

EXPECT = {
    1: "F1 上限手抄 → S47 红",
    2: "F2 度量漂移 → S47 红",
    3: "F3 菜单覆盖项落自定义 → S47 C 腿红",
    4: "F4 退役残留 → S47 红",
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
