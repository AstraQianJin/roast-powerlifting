# -*- coding: utf-8 -*-
"""v0.19（回归加固：i18n 挂载点可达 S25）的反向验证：证明 S25 那四条腿真的会拦。

    python tools/_sabotage_m9.py inject          # 四处一起注
    python tools/_sabotage_m9.py inject 2        # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                   # 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static                # 期望见下表
    python tools/_sabotage_m9.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

四处故障各打在一条承诺上（「红在哪」是单注那一处 + 重建 实测出来的）：

  F1 登记表里的 id 打错一个字母（setLangT → setLangTx，DOM 节点不动）
     → S25 红「登记的 id 在模板没有挂载点」。这条对着本版立这条守卫的原因：
       applyI18n 写的是 if(el)，节点找不到就**静默跳过**——不报错、不掉格，
       切到英文只有那一格还是中文。S14 只点名 14 个接线节点，这张全表没人管
  F2 一项只写一条词（addTxt 的英文那条删掉）
     → S25 红「不是两条词形态」。少一条的表现是切英文时 textContent 被写成
       undefined ——页面上真会出现「undefined」这个词，但没有任何断言量它
  F3 同一个 id 登记两次（bwCardLbl 抄两行，第二条词不同）
     → S25 红「登记了两次」。JS 对象字面量重复键不报错，后一条静默盖掉前一条，
       于是「改了第一行」的人看到的是没改的那行，还以为自己改错了地方
  F4 登记表本身改名（I18N_NODES 的声明那行）
     → S25 红「取不到登记表」：这条腿的意义就是「取不到被检对象一律 FAIL」，
       绝不因为表没了就当成「没有需要翻译的节点」而放行。
       注意动态侧一起红：applyI18n 里的 Object.keys 引用跟着断（v3v 的 Z0/Z1），
       所以 F4 是四组里唯一「静态 + 动态都该红」的那组

台账 _sabotage_m9.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

两种流程的实测数（v0.19，静态项数以 gate 自己的输出为准）：
  · `inject N` → **不重建**直接 `gate.py --static` = **23 PASS / 3 FAIL**：
    S5（模板改了成品没跟上，预期连带）+ S25（目标腿）+ S26（①那条腿看见台账，
    「台账在 = 不许发版」——这条连带是**正确行为**，不是判据漂了）
  · `inject N` → `build_html.py` → `--static` = **24 / 2**：S25 + S26（S5 被重建救回）
  四组单注在两种流程下都只红 S25 这一条目标腿，报错信息各自不同（F1「没有这个挂载点」/
  F2「不是「两条词」形态」/ F3「登记了两次」/ F4「取不到 I18N_NODES 登记表」）。
  合注（四处一起）只看得见 F4 那条：登记表没了，其余三条腿无从下手 —— 这是
  「取不到被检对象一律 FAIL」那条腿该赢的顺序，不是漏检。

已知边界（记下来，别当成已经防住）：S25 的反向腿只认模板里字面量 id="…"，
认不出 JS 拼出来的挂载点（`'<b id="'+k+'T">'` 这种）。真出现这种节点时往 gate.py 的
exempt 集合加那一个 id，**不要**把这条腿改成「查不到就当通过」。

v0.37（节点⑮ 组策略默认绑定）在本家续了三条腿（F5–F7，全打 S41）：
  F5 族绑到库里不存在的 idx ——「绑空=静默不绑」正是这条守卫立的原因：
     stratOf 认不出时返回 null，stratBoundId 的消费点全部判空跳过，页面上
     只是「那枚徽章没了」，没有任何报错；
  F6 兜底常量改名 ——「取不到被检对象一律 FAIL」的 S41 版；引用它的读取口
     当场 ReferenceError，v3v 整块红属预期（同 F4 的规矩）；
  F7 处方权威偷读策略绑定 ——prescriptionOf 里多一次 stratBoundId 调用。
     绑定是展示/选择层的默认，rx 文本是做组重量的唯一出处（ROADMAP §5），
     谁把两者接起来谁就在改处方语义，这条腿保证那不是一个安静的改动。
  实测：三组单注（sabr run m9 5/6/7）都是只红 S41、无意外红、还原逐字节、复跑回绿。

v0.38（周训练总结升级：三小项计数 + SBD.UpperBack 级功能标注 + 强调配色）在本家续了三条腿：
  F8 四族配色映射 SBD_CHIP 改名 —— 贴片颜色只从这张表出货，改名的直接表现是
     渲染口 ReferenceError（v3v 的 Z0/Z1 跟着红，同 F4 的规矩）；S42 的
     「配色表恰好一份」按「取不到被检对象一律 FAIL」拦住；
  F9 暗色主题那枚 --sbd-s 改名 —— 令牌是三块主题块各一份的配对家规，少一份的表现是
     默认主题下贴片静默掉色（CSS var 回落初值，不报错、不掉格）；S42 数声明份数，
     连带 S19（主题令牌对齐守卫）一起红——两块都在数同一组令牌，属正当连带；
  F10 .pc-x 类规则改名 —— JS 映射还发 pc-x，CSS 侧规则没了：贴片全走无底色默认。
     S42 的「映射类在 CSS 有规则」腿拦住；S22 实测不红（它管的是配重条那一族 class，
     pc-* 不在它名单里）——这条腿由 S42 自包，别指望 S22。
  实测（sabr run m9 8/9/10 --with fast）：F8 实到 S42 + Z0/Z1，F9 实到 S42 + S19，
  F10 实到只 S42；三组都无意外红、还原逐字节、复跑回绿。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m9.json")
TPL = os.path.join(HERE, "template.html")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "setLangT:['语言','Language'],",
     "setLangTx:['语言','Language'],",
     "F1 登记表的 id 打错 → S25 红（模板没有这个挂载点，applyI18n 静默跳过）"),
    (TPL, "addTxt:['添加训练动作','ADD MOVEMENT'],",
     "addTxt:['添加训练动作'],",
     "F2 少一条词 → S25 红（切英文时 textContent 会被写成 undefined）"),
    (TPL, "bwCardLbl:['体重','BW'],",
     "bwCardLbl:['体重','BW'],\n  bwCardLbl:['体重','Bodyweight'],",
     "F3 同一个 id 登记两次 → S25 红（后一条静默盖掉前一条）"),
    (TPL, "const I18N_NODES = {",
     "const I18N_NODEZ = {",
     "F4 登记表改名 → S25 红（取不到被检对象一律 FAIL；v3v 的 Z0/Z1 同红属预期）"),
    (TPL, "const STRAT_FAMILY_DEFAULT={GZCLP:7,RTS:4,TOP:2,CLASSIC:1};",
     "const STRAT_FAMILY_DEFAULT={GZCLP:99,RTS:4,TOP:2,CLASSIC:1};",
     "F5 族绑到库里不存在的 idx → S41 红（stratOf 判空=静默不绑，绑定表说谎）"),
    (TPL, "const STRAT_FALLBACK_IDX=1;",
     "const STRAT_FALLBACK_IDZ=1;",
     "F6 兜底常量改名 → S41 红（取不到被检对象一律 FAIL；引用它的腿当场抛错属预期）"),
    (TPL, "  const raw=String((e&&e.rx)||'').replace(/\\s+/g,' ').trim();\n  const parsed=parseRx(raw);",
     "  const raw=String((e&&e.rx)||'').replace(/\\s+/g,' ').trim();\n  stratBoundId({mode:mode,strategyId:''});\n  const parsed=parseRx(raw);",
     "F7 处方权威偷读策略绑定 → S41 红（绑定只许待在展示层，rx 解析被污染）"),
    (TPL, "const SBD_CHIP={S:'pc-s',B:'pc-b',D:'pc-d',X:'pc-x'};",
     "const SBD_CHIY={S:'pc-s',B:'pc-b',D:'pc-d',X:'pc-x'};",
     "F8 四族配色映射改名 → S42 红 + v3v Z0 Z1 同红（崩溃连带，取不到被检对象一律 FAIL）"),
    (TPL, "--sbd-s:#E07A5F;",
     "--sbd-sq:#E07A5F;",
     "F9 暗色那枚 SBD 令牌改名 → S42 红 + S19 红（三块只剩两份声明，令牌配对家规一起红；默认主题下贴片静默掉色）"),
    (TPL, ".pc-x{color:var(--sbd-x);background:var(--sbd-x-soft)}",
     ".pcq-x{color:var(--sbd-x);background:var(--sbd-x-soft)}",
     "F10 其它族类规则改名 → S42 红（JS 映射还发 pc-x，CSS 没有这条规则，贴片静默走无底色默认）"),
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
        sys.exit(__doc__)
