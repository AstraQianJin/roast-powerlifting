# -*- coding: utf-8 -*-
"""v0.44（存档 v8 迁移 V8a–V8h + 设置页 F20 下沉 E4/E5）的反向验证。

    python tools/_sabotage_m15.py inject        # 十处一起注
    python tools/_sabotage_m15.py inject 3      # 只注第 3 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    node tools/v3v.js                           # 期望见下表（只红那一条腿，其余不动）
    python tools/_sabotage_m15.py revert        # 逐字节还原
    python tools/build_html.py && node tools/v3v.js   # 期望回到全绿

跑法（驱动器把「注入 → 重建 → 各套回归 → 对账 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m15 1 2 3 4 5 6 7 8 9 10 --with fast

这一族守的是 v0.44 两块**没有别处兜底**的新承诺：

  A. 存档 v8 迁移（migrateStateV8 / v8GppDef / v8GppDay / v8RenameDayTitles / v8RestoreTitles）。
     迁移是「一次性、就地变形、失败要能回滚」的代码，平时跑不到、出错也不响 —— 正是红线 6
     「断言必须能红」最容易被绕过的地方。V8a–V8h 八条腿钉住八个变形步骤，这里给每条腿一个靶。
  B. 设置页结构承诺：v0.44 是 F20 下沉（迁移报告搬进「高级」子页），v0.49 又按 F19 把三段
     重组成六段（我的档案 / 我的水平 / 教练与计划 / 器械装备 / 数据报告 / 软件与高级）。
     E2–E8 钉的是主表六个分组各自的**行序与行数**；F9/F10 各打在其中相邻两行上做整块换序。

十处故障各打在一个新承诺上（「红在哪」是单注那一处 + 重建后实测出来的）。
除 F1 外每处都只红自己那条腿（F1 另带一条**正确连带** LD1，见下）：迁移靶打的是
migrateStateV8 内部语句（S39 只核对闸门行、V7 串联、V7 的 fresh/else 块，都不在这些语句上）；
设置靶用的是**整块换序**而非改 id —— 改 id 会同时踩 S25 的双向 i18n 可达（登记表↔挂载点），
换序不动任何 id，S25 与 E1（18 行）全绿。
（修订注：原 F9→E5「软件组」、F10→E4「教练组」，v0.49 六段重组后按段名与段序就地重定为
 F9→E8「软件与高级」、F10→E5「教练与计划」——换序靶随段落搬家，不是削弱覆盖，见 D22。）

  F1 `delete s.aux;` 整句拆掉
     → v3v V8a 红（迁移后 state.aux 仍在，`v8fake.aux===undefined` 不成立）。
       V8b/V8f 仍绿：s.gpp 在 delete 之前已派生、bk.aux 在 delete 之前已 clone。
       **正确连带 LD1 红**：aux 没删 = state 多出一个既不在 IMPORT_KEEP_KEYS、也不在
       「整份换新」名单里的顶层键，LD1「导入键分区自洽、并起来盖得住 state 每个顶层键」
       本就该报这条漏网键（与 m13 F2 的 EQ13 连带同理）。这条连带写进 docstring 留档，
       但**不写进 EXPECT** —— sabr 的 expect_of 把 `V8a` 当版本号滤掉（`^(V[0-9])`），
       本族 V8 腿一律走「至少红一条 + 还原回绿」的弱判据；若把 LD1 塞进 EXPECT 反而会让
       sabr 切到严格判据、再把自己滤掉的 V8a 当成「意外红」误判 FAIL。
       症状：旧 Armor 定义迁完还挂在账本上，WORK_KEYS 序列化会把它一起写回，双份真相
  F2 v8GppDef 的 rx 回落 `((d.target!=null)?String(d.target):'')` 拆掉
     → v3v V8b 红（旧 Armor 的 target 文本不再落进 rx，v8gpp[0].rx 变空串）。
       症状：老账本里「负重引体 target=20」迁完 rx 空白，目标处方凭空消失
  F3 `wk.auxDays.map(v8GppDay)` 漂成 `.map(blankGppDay)`
     → v3v V8c 红（打卡位不再逐位保留，done 全 false）。
       症状：用户历史 GPP 打卡记录迁完全被清零，「本周已做」归零
  F4 profile 锚点默认 `pullupAddedKg=0` 漂成 `=5`
     → v3v V8d 红（旧账本引体负重锚点不再从 0 起记）。
       症状：没填过引体负重的人迁移后凭空多出 5kg，Level 附表锚点失真
  F5 V8_DAY_TITLE_ZH 的 `'重型三项':F2_DAY_NAMES[0].zh` 漂成恒等 `'重型三项':'重型三项'`
     → v3v V8e 红（Day A 旧内置名不再升级成 F2「模拟赛日」）。
       V8f 仍绿：moved 照样 push（命中恒等映射也算改名），bk.titles.length 仍是 3
       V8g 仍绿：撤销时恒等映射照样把 F2 名换回旧名
       症状：升级后 Day A 还叫旧名「重型三项」，F2 日名落地漏一天
  F6 `rep.titlesRenamed=bk.titles.length;` 漂成 `=0;`
     → v3v V8f 红（迁移台账不再如实记改名条数）。
       V8h 仍绿：fresh 路径本就跳过改名，titlesRenamed 恒 0，与这条无关
       症状：迁移报告谎报「没改过日名」，用户对着台账查不到自己那三天去哪了
  F7 v8RestoreTitles 的 `d.titleZh=t.titleZh;` 漂成空操作 `d.titleZh=d.titleZh;`
     → v3v V8g 红（撤销迁移不再把 F2 名放回旧内置名）。
       症状：用户点「撤销迁移」后日名纹丝不动，撤销等于没撤
  F8 `if(!fresh){` 漂成 `if(true){`
     → v3v V8h 红（首建账本也去改名，titlesRenamed 不再是 0、日名不再是旧默认名）。
       V8a–V8g 仍绿：非 fresh 路径 `!fresh` 与 `true` 等价，行为不变
       症状：全新安装（本来就是 F2 名）被当旧档再"迁"一遍，台账记下莫须有的改名
  F9 软件与高级组「界面语言」行与「主题切换」行整块换序
     → v3v E8 红（软件与高级组 id 序列 slice(13) 不再逐位吻合 …,setLangT,setThemeT,…）。
       E1（18 行）/E2–E7/E9/E10/S25 全绿：只换位、不增删行、不改任何 id、不碰 {{VER}}
       （为什么不打「关于↔高级」那一对：关于行副标题带 {{VER}}，S23 探靶会把它换成版本号，
        而模板源里是字面 {{VER}}，带进靶串会探空 —— 换序靶必须避开它。）
       症状：六段重组后「软件与高级」组的行序承诺失守，E8 钉的精确 id 序列漂位
  F10 教练与计划组 setAdvT 行与 setSciT 行整块换序
     → v3v E5 红（教练与计划组 slice(5,9) 顺序不再是 …,setAdvT,setSciT）。
       E1/E2/E3/E4/E6–E10/S25 全绿：同理只换位
       症状：教练与计划组行序被打乱，E5 钉的「计划配置·评估·智能引擎·科学引擎」四行结构失守

台账 _sabotage_m15.json 存的是注入前每个文件的整份原文，revert 逐字节放回。
**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m15.json")
TPL = os.path.join(HERE, "template.html")

# 设置页整块换序用的两段原文（LF 行尾，与 template.html 一致；id 一律不动，避开 S25 双向可达）
# 我的训练组「训练计划 / 自动调整重量」两行换序（这两行相邻，换序只红 E4，不动别处）。
_ADV_SCI = """      <div class="set-row">
        <div class="sl"><b id="setStructT">训练计划</b><i id="setStructS">周期长度、训练日与建议组数</i></div>
        <button class="set-go" id="setStructGo" onclick="openStructSheet()">›</button>
      </div>
      <div class="set-row">
        <div class="sl"><b id="setAdvT">自动调整重量</b><i id="setAdvS">按完成率与体感预览下周重量，确认后才应用</i></div>
        <button class="set-go" id="setAdvGo" onclick="openAdviceSheet()">›</button>
      </div>"""
_SCI_ADV = """      <div class="set-row">
        <div class="sl"><b id="setAdvT">自动调整重量</b><i id="setAdvS">按完成率与体感预览下周重量，确认后才应用</i></div>
        <button class="set-go" id="setAdvGo" onclick="openAdviceSheet()">›</button>
      </div>
      <div class="set-row">
        <div class="sl"><b id="setStructT">训练计划</b><i id="setStructS">周期长度、训练日与建议组数</i></div>
        <button class="set-go" id="setStructGo" onclick="openStructSheet()">›</button>
      </div>"""
# 外观组「主题 / 语言」两枚 compact 行整块换序（不含 {{VER}}：S23 探靶会把 {{VER}} 换成版本号，
# 而模板源里是字面 {{VER}}，带它进靶串会探空 —— 故换序靶避开关于行）。
_THEME_LANG = """      <div class="set-row compact">
        <div class="sl"><b id="setThemeT">主题</b><i id="setThemeS">暗色、亮色与咖啡纸感</i></div>
        <div class="seg-pill" id="themeSeg">
          <span class="thumb"></span>
          <button id="thDark" onclick="setTheme('dark')">☾ <span id="thDarkT">暗色</span></button>
          <button id="thLight" onclick="setTheme('light')">☀ <span id="thLightT">亮色</span></button>
          <button id="thNature" onclick="setTheme('nature')">☕ <span id="thNatureT">咖啡纸感</span></button>
        </div>
      </div>
      <div class="set-row compact">
        <div class="sl"><b id="setLangT">语言</b><i id="setLangS">界面与动作名称</i></div>
        <div class="seg-pill" id="langSeg">
          <span class="thumb"></span>
          <button id="langZh" onclick="setLang('zh')">中文</button>
          <button id="langEn" onclick="setLang('en')">EN</button>
        </div>
      </div>"""
_LANG_THEME = """      <div class="set-row compact">
        <div class="sl"><b id="setLangT">语言</b><i id="setLangS">界面与动作名称</i></div>
        <div class="seg-pill" id="langSeg">
          <span class="thumb"></span>
          <button id="langZh" onclick="setLang('zh')">中文</button>
          <button id="langEn" onclick="setLang('en')">EN</button>
        </div>
      </div>
      <div class="set-row compact">
        <div class="sl"><b id="setThemeT">主题</b><i id="setThemeS">暗色、亮色与咖啡纸感</i></div>
        <div class="seg-pill" id="themeSeg">
          <span class="thumb"></span>
          <button id="thDark" onclick="setTheme('dark')">☾ <span id="thDarkT">暗色</span></button>
          <button id="thLight" onclick="setTheme('light')">☀ <span id="thLightT">亮色</span></button>
          <button id="thNature" onclick="setTheme('nature')">☕ <span id="thNatureT">咖啡纸感</span></button>
        </div>
      </div>"""

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "delete s.aux;",
     "/* m15-F1 探针：aux 键未删 */",
     "F1 迁移后不删 state.aux → v3v V8a 红（旧 Armor 定义仍挂在账本上）"),
    (TPL, "rx:(d.rx!=null&&d.rx!=='')?String(d.rx):((d.target!=null)?String(d.target):'')",
     "rx:(d.rx!=null&&d.rx!=='')?String(d.rx):''",
     "F2 v8GppDef 丢掉 target→rx 回落 → v3v V8b 红（旧 target 文本迁完变空）"),
    (TPL, "wk.gppDays=wk.auxDays.map(v8GppDay);",
     "wk.gppDays=wk.auxDays.map(blankGppDay);",
     "F3 打卡迁移用空白格取代逐位保留 → v3v V8c 红（done 位全清零）"),
    (TPL, "if(s.profile.pullupAddedKg==null) s.profile.pullupAddedKg=0;",
     "if(s.profile.pullupAddedKg==null) s.profile.pullupAddedKg=5;",
     "F4 引体负重锚点默认漂成 5 → v3v V8d 红（旧账本不再从 0 起记）"),
    (TPL, "'重型三项':F2_DAY_NAMES[0].zh",
     "'重型三项':'重型三项'",
     "F5 日名映射恒等 → v3v V8e 红（Day A 旧名不升级成 F2 名）"),
    (TPL, "rep.titlesRenamed=bk.titles.length;",
     "rep.titlesRenamed=0;",
     "F6 迁移台账改名条数归零 → v3v V8f 红（谎报没改过日名）"),
    (TPL, "if(t.titleZh!==undefined&&d.titleZh===V8_DAY_TITLE_ZH[t.titleZh]) d.titleZh=t.titleZh;",
     "if(t.titleZh!==undefined&&d.titleZh===V8_DAY_TITLE_ZH[t.titleZh]) d.titleZh=d.titleZh;",
     "F7 撤销日名成空操作 → v3v V8g 红（撤销迁移不再放回旧内置名）"),
    (TPL, "if(!fresh){",
     "if(true){",
     "F8 fresh 首建也去改名 → v3v V8h 红（titlesRenamed 不再 0、日名不再旧默认）"),
    (TPL, _THEME_LANG,
     _LANG_THEME,
     "F9 外观组主题行与语言行整块换序 → v3v E6 红（外观组 id 序列不再逐位吻合）"),
    (TPL, _ADV_SCI,
     _SCI_ADV,
     "F10 我的训练组计划行与自动调整行整块换序 → v3v E4 红（我的训练组行序被打乱）"),
]


EXPECT = {
    1: "F1 aux 键未删 → v3v V8a 红",
    2: "F2 rx 丢 target 回落 → v3v V8b 红",
    3: "F3 gppDays 用空白格 → v3v V8c 红",
    4: "F4 引体锚点默认漂成五 → v3v V8d 红",
    5: "F5 日名映射恒等 → v3v V8e 红",
    6: "F6 改名条数归零 → v3v V8f 红",
    7: "F7 撤销日名成空操作 → v3v V8g 红",
    8: "F8 fresh 也改名 → v3v V8h 红",
    9: "F9 软件与高级组语言主题行换序 → v3v E8 红",
    10: "F10 教练与计划组行序打乱 → v3v E5 红",
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
