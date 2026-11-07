# -*- coding: utf-8 -*-
"""g1：配重引擎（v0.31 节点③c）的反向验证。

打在 template.html 上，由 sabr.py 驱动（注入 → gen_seed + build_html → 跑套件 → 逐条对账 →
还原 → 重建 → 复跑回绿）。每一条都必须有一个具体断言变红，否则那条断言就是恒真的。

    python tools/_sabotage_g1.py inject          # 十九处一起注
    python tools/_sabotage_g1.py inject 7        # 只注第 7 处
    python tools/_sabotage_g1.py revert          # 逐字节还原
    python tools/sabr.py run g1 1 2 3 --with gear

F1–F9 对着 gearv（D12）：六类 effective / 配方 / 步长 / 处方 / 调用点 / v7 迁移语义。
F10–F12 对着 v0.31 新增的三条静态守卫 S37 / S38 / S39 —— 守卫自身也要能被证明会红。
F13 对着 v0.32 节点⑥：e.rx 权威逐组解析（gearv G6），塌回 sets×reps 猜测时必须红。
F14 对着 v0.33 节点⑦⑧：自重载荷格主数字必须吃 effectiveKg（净负荷），顶回带符号外载原值时 gearv G7 必须红。
F15–F16 对着 v0.34 节点⑨⑩：挂片位 posts 枚举把关（G8.4）与首页前四形态的挂片片叠（G8.6），任一退化必须红。
F17–F19 对着 v0.35 节点⑪⑫：插片栈数枚举把关（G9.3）、特殊卡主数字吃 effectiveKg（G9.7）、manualKg 覆盖总重（G1.14+G9.7），任一退化必须红。
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_g1.json")
TPL = os.path.join(HERE, "template.html")

FAULTS = [
    # 1) 杠铃步长写死：0.25 片的 0.5kg 步长会变成 2.5 —— gearv G1 步长段红
    (TPL, "    case 'barbell': return mp? +(2*mp).toFixed(3) : +fb;",
     "    case 'barbell': return 2.5;",
     "F1 步长硬编码 2.5 → gearv G1 红（步长按库存派生失效）"),
    # 2) 赛扣重复计一次 —— 100kg 实配变成 105
    (TPL, "    achieved=+(g.barKg+(pk.collars?g.collarPairKg:0)+2*pk.plates.reduce(function(a,p){ return a+p.kg; },0)).toFixed(3);",
     "    achieved=+(g.barKg+(pk.collars?g.collarPairKg:0)+2*pk.plates.reduce(function(a,p){ return a+p.kg; },0)+g.collarPairKg).toFixed(3);",
     "F2 赛扣双计 → gearv G1 红（实配重量对不上目标）"),
    # 3) 哑铃按单边当总重
    (TPL, "    achieved=+(snap*g.sides).toFixed(3); effective=+(side*g.sides).toFixed(3);",
     "    achieved=+(snap*g.sides).toFixed(3); effective=+side.toFixed(3);",
     "F3 哑铃按 ×1 → gearv G1 红（effective 掉一半）+ G7.2 红（×2=48 后缀没了）"),
    # 4) 辅助超过体重时不再钳 0
    (TPL, "    effective=Math.max(0,net);",
     "    effective=net;",
     "F4 辅助净负荷出负 → gearv G1 红（钳 0 分支失效）"),
    # 5) Top 系处方退回 sets×reps 的猜测
    (TPL, "    rx='1×'+reps+' + '+(sets-1)+'×'+Math.max(1,reps-1); tag='TOP+BACKOFF'; backoff=0.10;",
     "    rx=sets+'×'+reps; tag='STRAIGHT SETS'; backoff=0;",
     "F5 顶组回落猜次数 → gearv G2 红（处方逐组串与标签都没了）"),
    # 6) 海报吨位把 e.load 当净负荷
    (TPL, "      const tonOne=bk.kg*(+e.reps||0)*setsOf(e.mode, e.sets);",
     "      const tonOne=(+e.load||0)*(+e.reps||0)*setsOf(e.mode, e.sets);",
     "F6 吨位退回 e.load → gearv G3 红（纯自重行吨位掉 0）"),
    # 7) 纯自重 load=0 也做净重→外载换算
    (TPL, "      if(old===0) return;                 // 计划原文就是 0：纯自重，不动",
     "      if(false) return;                     // 计划原文就是 0：纯自重，不动",
     "F7 纯自重被换算 → gearv G5 红（load 被改成负外载）"),
    # 8) 派生指标回写去掉 ≥0.005 门槛，无条件覆写
    (TPL, "    if(Math.abs(next-(+r.e1rm||0))<0.005){ r.effV=SCHEMA_STAMP; rep.deriveSame++; return; }",
     "    if(false){ r.effV=SCHEMA_STAMP; rep.deriveSame++; return; }",
     "F8 派生回写污染 → gearv G5 红（相同值也进备份、deriveSame 归零）"),
    # 9) BW 缺失时擅自按 0 折算
    (TPL, "      if(!(bw>0)){",
     "      if(false){",
     "F9 BW 缺失擅自换算 → gearv G5 红（gearPending 不猜的承诺失效）"),
    # 10) 六类 chip 改成手抄名单（S37 的 witness）
    (TPL, "  box.innerHTML=GEAR_SCHEMA.kinds.map(function(k){",
     "  box.innerHTML=[{id:'barbell',zh:'杠铃',en:'BARBELL'}].map(function(k){",
     "F10 chips 手抄名单 → S37 红 + gearv G3 红（六类只剩一类）"),
    # 11) 首页步进按钮写死 kg 字面量（S38 的 witness）
    (TPL, "+'+nextStepText(e,1)+'</button>'",
     "+2.5</button>'",
     "F11 步进按钮写死 2.5 → S38 红 + gearv G3 红（文案不再跟步长走）"),
    # 12) venues 掉出 IMPORT_KEEP_KEYS（S39 的 witness）
    (TPL, "const IMPORT_KEEP_KEYS=['lang','theme','plateCfg','venues','activeVenueId',",
     "const IMPORT_KEEP_KEYS=['lang','theme','plateCfg','activeVenueId',",
     "F12 venues 掉登记 → S39 红（导入会丢场地库存）"),
    # 13) §5 权威解析被摘掉：prescriptionOf 无视 e.rx，退回 sets×reps 猜测（节点⑥的 witness）
    (TPL, "  const parsed=parseRx(raw);",
     "  const parsed={parsed:false,trivial:true,groups:[],amrap:false,totalSets:0};",
     "F13 rx 权威解析失效 → gearv G6 红（逐组结构全塌回单组猜测）"),
    # 14) 自重载荷格塌回原值：主数字不吃 effectiveKg（节点⑦⑧的 witness）
    (TPL, "_num=fmtLoad(gv.effectiveKg);",
     "_num=fmtLoad(e.load);",
     "F14 自重主数字顶回带符号外载原值 → gearv G7 红（净负荷显示塌成 25/−30）"),
    # 15) setGearPosts 不再拒非法 posts：3 不在枚举也应被挡在门外（节点⑨的 witness）
    (TPL, "  if(POSTS_OPTIONS.indexOf(v)<0) return;",
     "  if(false) return;",
     "F15 挂片位 posts 失守 → gearv G8.4 红（非法 3 被写进 e.gear，契约枚举不再把关）"),
    # 16) 首页挂片卡退回纯文字：不画每位片叠，前四形态里挂片又跟 dumbbell/stack 挤成一行摘要（节点⑩的 witness）
    (TPL, "        chips+='<i class=\"pb\" style=\"background:'+p.c+';height:'+hh+'px;width:'+ww+'px\"></i>';",
     "        chips+='<i class=\"none\"></i>';",
     "F16 首页挂片不画片叠 → gearv G8.6 红（前四形态退化，pb 视觉没了）"),
    # 17) setGearStacks 不再拒非法栈数：3 不在 stacks_options 也应被挡在门外（节点⑪的 witness）
    (TPL, "  if(STACKS_OPTIONS.indexOf(v)<0) return;",
     "  if(false) return;",
     "F17 插片栈数枚举失守 → gearv G9.3 红（非法 3 被写进 e.gear，契约枚举不再把关）"),
    # 18) 特殊类载荷格塌回原值：主数字不吃 effectiveKg（节点⑫的 witness，与 F14 自重腿同型不同格）
    (TPL, "      _num=fmtLoad(+gv.effectiveKg);",
     "      _num=fmtLoad(e.load);",
     "F18 特殊主数字顶回 e.load 原值 → gearv G9.7 红（48/46 两张卡塌成 0）"),
    # 19) 特殊类 manualKg 覆盖被短路：实称总重不再顶掉标称 unit×count（节点⑫语义腿）
    (TPL, "    achieved=(g.manualKg!=null)?+g.manualKg:calc;",
     "    achieved=calc;",
     "F19 手填覆盖失效 → gearv G1.14 红（50 被算回 48）+ G9.7 红（手填 46 与手填字样没了）"),
]

EXPECT = {
    1: "→ gearv G1 红（步长段）",
    2: "→ gearv G1 红（achieved 段）",
    3: "→ gearv G1 红（dumbbell 段）+ G7.2 红（sides 强 1 后 ×2=48 后缀与总重一起没）",
    4: "→ gearv G1 红（辅助钳 0 段）",
    5: "→ gearv G2 红（Top 逐组串 / 标签）",
    6: "→ gearv G3 红（海报周吨位）",
    7: "→ gearv G5 红（纯自重不动）",
    8: "→ gearv G5 红（回写门槛）",
    9: "→ gearv G5 红（BW 缺失不猜）",
    10: "→ S37 红 + gearv G3 红（chips 手抄）",
    11: "→ S38 红 + gearv G3 红（按钮字面量）",
    12: "→ S39 红（venues 掉登记）",
    13: "→ gearv G6 红（rx 权威解析塌回单组）",
    14: "→ gearv G7 红（自重主数字塌回带符号外载原值）",
    15: "→ gearv G8.4 红（挂片位 posts 枚举把关失效）",
    16: "→ gearv G8.6 红（首页挂片 strip 不画每位片叠）",
    17: "→ gearv G9.3 红（栈数枚举把关失效，非法 3 被写进 e.gear）",
    18: "→ gearv G9.7 红（特殊卡主数字顶回 e.load 原值）",
    19: "→ gearv G1.14 红（手填覆盖被短路）+ G9.7 红（手填 46 腿没了）",
}


def read(p):
    # newline="" 保留原始换行：通用换行会把 CRLF 读成 LF，台账里的「原文」就与磁盘
    # 差了一层，revert 后逐字节比对必然判「未还原」（sabr 的第 ③ 条合格线）。
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
    if isinstance(pick, (list, tuple, set)):
        faults = [FAULTS[i - 1] for i in sorted(int(x) for x in pick)]
    else:
        faults = FAULTS if pick is None else [FAULTS[int(pick) - 1]]
    original, planned = {}, []
    for path, old, new, why in faults:
        src = original.get(path, read(path))
        original[path] = src
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r"
                     % (path, src.count(hit), old[:60]))
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


def _run(pick):
    if isinstance(pick, list):
        for i in pick:
            if not 1 <= i <= len(FAULTS):
                sys.exit("故障编号只允许 1..%d（收到 %d）" % (len(FAULTS), i))
    elif pick is not None and not 1 <= pick <= len(FAULTS):
        sys.exit("故障编号只允许 1..%d（收到 %d）" % (len(FAULTS), pick))
    inject(pick)
    if isinstance(pick, list):
        print("期望：%s" % " | ".join(EXPECT[i] for i in pick))
    else:
        print("期望：%s" % (EXPECT[pick] if pick else "见文档表"))


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        _run([int(a) for a in args[1:]] or None)
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
