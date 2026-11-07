# -*- coding: utf-8 -*-
"""v0.24（自动调节判据单源 S29）的反向验证：证明 S29 那四条腿真的会拦，而不是摆设。

    python tools/_sabotage_u1.py inject          # 七处一起注
    python tools/_sabotage_u1.py inject 3        # 只注第 3 处（核对它只红自己那条腿）
    python tools/build_html.py                   # 契约与模板都要重建，否则 S5 先红
    python tools/gate.py --static                # 期望见下表
    python tools/_sabotage_u1.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

S29 管的是 ROADMAP §2.6 那一串判据数字（完成率下限、RPE 硬顶、RPE 缺口、上/下肢与 T3 步进、
回退量、单次幅度上限、T3 干净次数）。它们有三类读者：模板的 nextWeekAdvice()（真算建议）、
契约 Workouts.prog_rules（xlsx prog_rule 列里给用户看的人话）、设置页 advNote（口径说明）。
七处故障各打在一条承诺上（「红在哪」是单注那一处 + 重建后 `gate.py --static` 实测出来的）：
F1–F5 打 S29 判据单源；F6 打 D6 自重进自动加重（v3v O11b 的旁路，非 S29）；
F7 打 e1RM 口径分界线（v3v X5「定义必被用」与 X5b 的窄路径判据，非 S29）：

  F1 契约 min_completion 从 0.8 改成 0（数值键失效）
     → S29 红 ①「autoreg.min_completion 不是正数」。这一条腿是「判据段自己得是个能用的数」：
       0 会让 rate 闸门恒不触发（完成率 < 0 永远为假），建议开始给没跑满组的人加重
  F2 契约 clean_reps 的 T3.Mod 改成 T2.Mod（阈值挂错档）
     → S29 红 ②「是 T2 档，不是 T3」+ 连带红 ③「T2.Mod 的 prog_rules 里找不到 18」。
       这条防的是「阈值挂在没人执行的档上」：T3 的干净次数是 AMRAP 追 18/25 次那条规矩，
       挪到 T2 就等于 T3 的闸门悄悄消失、T2 多一条没人读的数
  F3 契约 prog_rules["T3.Def"] 里那句人话的 25 改成 24（文字与数字分叉）
     → S29 红 ③。这是这一家最值钱的一条：代码按 25 判、工作簿那列写 24，
       用户照着 xlsx 的 prog_rule 练，永远不知道自己为什么不加重量 —— 两边都不报错
  F4 模板引擎把 `+ar.min_completion` 换成手抄的 0.8
     → S29 红 ④「引擎代码里手抄了判据 min_completion=0.8」。契约随后改成 0.75 时建议不变，
       这就是「第二份数字」长大的样子；剥注释后才扫，所以注释里写人话不算违规
  F5 模板 nextWeekAdvice 改名（引擎定位锚点失效）
     → S29 直接 FAIL「定位不到下周建议引擎」。取不到被检对象一律判红，绝不因为
       「扫不到手抄数字」就当成 ④ 通过。动态侧一起红属预期（v3v 的 O 段全踩这个函数）

台账 _sabotage_u1.json 存的是注入前每个文件的整份原文，revert 逐字节放回。
两个文件（契约 JSON + 模板）都在靶子里，所以每一组都要 `build_html.py` 再跑门禁：
不重建的话 S5 会先红（成品与模板+契约脱节），那是正确行为，但会把 S29 的报错埋掉。

实测（静态项数以 gate 自己的输出为准）：
  · F1–F3（改契约那三处）单注 + 重建 + `--static` = S26 + S29。
    v0.36 起靶子从 RPL-Plan-v1.json 重指到现行契约 RPL-Plan-v2.json：S29 读的本来就是
    build_html.PLAN_SCHEMA 所指文件，重指前腿打在被冻结的存档上会**静默失效**（红的是 S39，
    不是 S29 —— 驱动器会判「期望的腿没红」）。S39 现在只盯 v1/v2 里那两份 v1 契约，
    改 v2 不碰它。S26 红是「台账在就不许发版」那条腿在现场看见了这个注入，属正确连带（sabr 会自动摘掉纯残留噪音）。
  · F4（模板手抄）单注 `--static` 只红 S29 ④；F5 的 why 点了 v3v，静态层判 SKIP，
    要在 fast 层才核它的动态腿 —— 实测 F5 改名引擎后 v3v 侧红在 A0 / Z0 / Z1（函子名单
    缺项 + 段内抛错被 try 兜住 → O 段没有逐条红），静态侧红 S29 + S30，
    不是早期文档写的「O 段全红」；这是该条期望的既有说法，未随 S39 一起校准，留待下轮重述。
  · `revert` → `build_html.py` → `--static` 回全绿，tools/ 下无 `_sabotage_u1.json` 残留。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_u1.json")
TPL = os.path.join(HERE, "template.html")
SCH = os.path.join(HERE, "schema", "RPL-Plan-v2.json")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (SCH, '"min_completion": 0.8,', '"min_completion": 0,',
     "F1 契约 min_completion 从 0.8 改成 0（数值键失效）→ S29 红 ①：完成率闸门恒不触发（v0.36 起注在现行契约；连带 S40）"),
    (SCH, '"clean_reps": {"T3.Mod": 18, "T3.Def": 25},',
     '"clean_reps": {"T2.Mod": 18, "T3.Def": 25},',
     "F2 契约 clean_reps 的 T3.Mod 改成 T2.Mod（阈值挂错档）→ S29 红 ②③：换档让判据两侧对不上（连带 S40）"),
    (SCH, '"T3.Def": "3×15+：末组 25 次干净次数达标再 +Load",',
     '"T3.Def": "3×15+：末组 24 次干净次数达标再 +Load",',
     "F3 契约 prog_rules[T3.Def] 那句人话的 25 改成 24（文字与数字分叉）→ S29 红 ③：prog_rules 里找不到 25（连带 S40）"),
    (TPL, "if(r.rate<+ar.min_completion){", "if(r.rate<0.8){",
     "F4 引擎手抄判据 → S29 红 ④（代码里出现 0.8，契约改了它不变）"),
    (TPL, "function nextWeekAdvice(srcW){", "function nextWeekAdviceV2(srcW){",
     "F5 引擎定位不到 → S29 一律 FAIL（取不到被检对象不放行；v3v O 段同红属预期）"),
    # F6：D6 自重进自动加重的绝对档位旁路被关进死分支 → 自重行塌回 ±5% 夹取（v3v O11b 的 witness）
    (TPL, "if(r.kind==='bw'){", "if(r.kind==='bw' && false){",
     "F6 自重旁路失效 → v3v O1 / O11b / O14 红（外载 25kg 被 ±5% 夹成保持，加重计数与表格随之塌）"),
    # F7：e1RM 口径分界判据被短路 → 合法迁移报告也不发 fx-mig（v3v X5「定义必被用」+ X5b 同红）
    (TPL, "var migOk=!!mr&&!mr.fresh&&mr.atWeek!=null&&",
     "var migOk=!!mr&&!mr.fresh&&false&&mr.atWeek!=null&&",
     "F7 分界判据短路 → v3v X5 / X5b 红（fx-mig 定义了却没人发，非首建报告也不画分界线）"),
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
