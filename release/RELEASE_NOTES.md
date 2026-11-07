# ExDark Pro · v0.70

**发布日期**：2026-11-07
**前序版本**：v0.60（versionCode 56 → 57）
**成品**：`release/RPL_ExDark_v0.70_Pro.apk`（versionName 0.70 / versionCode 57；1077.8 KB；md5 `98e39cccd0aa9d5c66eaeb8ed5890182`；内嵌 `index.html` md5 `e41fdc283f60c709788eb3cb3ae2c006`）
**签名**：固定 release keystore（`CN=RPL ExDark Pro, OU=Internal Beta`），SHA-256 `E4:23:E5:24:CC:95:82:7D:43:CC:A6:05:56:2D:CE:4E:B3:C2:88:45:29:48:3E:A9:B6:64:D5:EA:27:1E:2F:C9`；keystore 与口令在仓库外 `~/.rpl-keys`，**本版起签名不再随机器变**（v0.60 及更早是 debug 签名，升级本版需先卸载旧包，装前用 `pm uninstall -k` 保留账本数据）

> **本版内容**：计划正确性。处方解析覆盖计划里的真实写法，认不出的非空原文显式标出并保留原文，不再静默换成 `proto` 处方；`Workouts` 的 `sets` 列真正驱动组数（导入、卡片、组数切换、导出同一条链）；App 默认种子改用新工作簿 `RPL_ExDark_v0.70_Plan_2026-11-09.xlsx`（旧工作簿原样保留）。顺带修复：底部日卡的日名变长后把按钮撑出屏幕（周五/周六/GPP 点不到），改为 `minmax(0,1fr)` + 单行省略，360dp 下五个日卡全在屏内。CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

---

## [v0.60] — 2026-11-07

**发布日期**：2026-11-07
**前序版本**：v0.59（versionCode 55 → 56）
**成品**：`release/RPL_ExDark_v0.60_Pro.apk`（versionName 0.60 / versionCode 56；1048.5 KB；md5 `1807c13dd858ec53a1d5fb31ea88b49b`；内嵌 `index.html` md5 `cd8c9ad529d84dcb9c71893a1b46ba10`）

> **本版内容**：首页配重条改为「只图形、零文字」——条内的重量串、器械名、片数、`+N`、空杆文案与配平警告全部移除，只留片、杆、器械形状与状态色，从信息层消掉 320dp 窄屏的裁字问题；重量读数仍在左侧载荷格、明细点开编辑器。去字后图形补位：空杆画空心片轮廓、超 10 片画三个点、挂片柱按 posts 逐根画、哑铃双边用手柄旁双线、插片 `pin=0` 仍画梯框与销位、特殊类按 count 画单元方块，配不平只给琥珀状态色。器械种类 / 片重 / 每边片数仍走 `gearOf` → `stepKgOf` → `solveLoad` 同一条链。CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

---

# ExDark Pro · v0.59

**发布日期**：2026-11-07
**前序版本**：v0.58（versionCode 53 → 55）
**成品**：`release/RPL_ExDark_v0.59_Pro.apk`（versionName 0.59 / versionCode 55；1048.0 KB；md5 `6e12c7ba67144c841e754cc3e879663e`；内嵌 `index.html` md5 `710f3c06fad5b03700b318f1bd277c4c`）

> **本版内容**：① **修复 v0.58 滚动失效（回归）**——`html,body` 的 `overflow-x:hidden` 会让 body 变成吞掉拖动手势的滚动容器，整页划不动；改为 `overflow-x:clip;overflow-y:visible`，并给 `gate.py` 加静态闸门（根规则退回 `hidden` 直接红）。② **修复 GPP 排版溢出**——六轴数值标移出六边形外圈、处方行窄屏可换行、雷达窄屏铺满卡片宽度，361dp 与 320dp 实测零横向溢出。③ **移除「打气」模块**——设置项、存储键、文案、海报换句与断言一并删除。CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

**发布验证**：`python tools/pack.py` 退出码 0；静态门禁与全量门禁均 0 FAIL；`v3v` 470 PASS / 0 FAIL。**真机验证**（MEP-AN00 / 1264×2736 @560dpi = 361dp × 781dp）：同一手势下旧规则 `scrollTop=0`（复现卡死）、新规则 `scrollTop=2184`；GPP 内容区 313.14px、最宽处方行 289.71px、最大右缘差 −0.86px（零溢出）。320dp 档只在无头 Chrome 与模拟器 WebView 的 DOM 实测里验证（零溢出），**真机未验 320dp**。

---

# ExDark Pro · v0.58

**发布日期**：2026-11-07
**前序版本**：v0.54（versionCode 49 → 53）
**成品**：`release/RPL_ExDark_v0.58_Pro.apk`（versionName 0.58 / versionCode 53；1048.9 KB；md5 `9c5b0d29f56ae3e28aa5fdea36f6989c`；内嵌 `index.html` md5 `a3bdf06c6a6c073c33a0b4af6b5cffd8`）

> **本版内容**：① GPP 六轴改为力量/耐力/稳定/爆发/精神/灵活（耐力在图上合并为一轴，数据层保留稳态有氧与间歇两个子组，旧轴读时归位）；② 首页配重按器械形状语言重做（六类各有 glyph，`gearKindGuess` 先读中文动作名，插片与龙门架靠滑轮区分，哑铃头粗柄细 + `×2` 徽标；挂片柱带顶/底座、插片堆常显壳体与销位手柄、特殊器械按壶铃/药球/战绳/弹力带给简化轮廓、自重加重画腰带+负重片）；③ 配重计算器默认收起并记住上次状态，同时纠正 `LC_TYPES` 里 `stack`/`loaded` 的中英文标签错位（插片=SELECTORIZED、挂片=PLATE-LOADED）；④ 删除「最近一次训练」模块；⑤ 今日计划并入左上 `ExDark` 顶栏，窄屏不挤；⑥ 红屏防御性修复（`themes.xml` 增加 `android:colorEdgeEffect=@color/window_bg`、`html,body` 关 overscroll、`.panel` 关回弹、去掉 `body::before` 的 fixed+translateZ 红色合成层，改画在 body 背景上）——未真机证实成因，为低风险防御。CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

**发布验证**：`python tools/pack.py` 退出码 0；静态 51 PASS / 0 FAIL、全量门禁 61 PASS / 0 FAIL；`v3v` 473 PASS / 0 FAIL、`gearv` 69 PASS / 0 FAIL、`uiv` 251 PASS / 0 FAIL、`xlsxv` 171 PASS / 0 FAIL。APK 由 `pack.py` 写入 `release/` 并校验内嵌 `index.html` 与仓库产物字节一致。

---

# ExDark Pro · v0.54

**发布日期**：2026-11-06
**前序版本**：v0.50（versionCode 45 → 49）
**成品**：`release/RPL_ExDark_v0.54_Pro.apk`（versionName 0.54 / versionCode 49；1045.4 KB；md5 `40e919ddef1498f24f529fef8d021224`；内嵌 `index.html` md5 `049efcafb1bbe11b7aa616f1efeb3232`）

> **本版内容**：① HPR 增图表形态（雷达/条形/环形）与数据视角（目标完成度 ↔ 固定锚点标准水平），条形/环形只走 HTML+CSS，全模板仍只有雷达一份 `viewBox`；② 伤病台账（预设部位 + 4 档恢复期 + 三举可手改百分比，多项取最重不叠加），默认只给影子目标、不自动改计划，一键写回只经 `advWriteLoad` + `advAudit`；③ 非杠铃四项：自重 lever 入口、哑铃库存与步进、插片实配主数字与销位、热身 0kg 首档。CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

**发布验证**：`python tools/pack.py` 退出码 0；静态 51 PASS / 0 FAIL、全量 61 PASS / 0 FAIL；`v3v` 472 PASS / 0 FAIL。APK 已由 `pack.py` 写入 `release/` 并校验内嵌 `index.html` 与仓库产物字节一致。

---

# ExDark Pro · v0.50

**发布日期**：**发版节点**（v0.44–v0.49 逐版 bump+commit 不出 APK，本版 `pack.py` 把这条弧一并发布）
**前序版本**：v0.49（versionCode 44 → 45）
**成品**：`release/RPL_ExDark_v0.50_Pro.apk`（versionCode 45 · 大小 1037.4 KB · md5 `d594bb191330e406a9e98c5192362a76`；内嵌 `index.html` md5 `ba65d0c56ce7bbc3a9e89082def3435a` == 仓库产物）

> **发版收口（无新功能代码）**。本版把 v0.44–v0.49 六版内容打包为这条弧的首个 APK，并收口版本指针（`versionCode` 44→45 / `versionName` 0.49→0.50，唯一出处 `build.gradle`，四处人读指针同步）、清空注入台账、跑全链门禁。**打包内容汇总**：① v0.44 计划契约 v3 + 迁移闸门（旧存档带闸门恢复，不再静默落空账本）；② v0.45 GPP 引擎（目录/菜单来自 `RPL-GPP-v1.json`）+ JTS 六维重构（睡眠/压力/疲劳/酸痛/动力/精力，READY_AT 只在契约，CRS 退役、旧答 `migrateStateV8` 迁移留备份）；③ v0.46 运动员水平页（全量表 + 条状段位徽章 + `LevelSnapshot`）；④ v0.47 主页日历引擎（`planPos` 派生周/日/块、休息日指下一课）+ 当日打气句与昵称（只落 prefs、`saveNick` 一处 24 钳）+ 器械视觉（哑铃双格 / 自重人形 SVG / 无袖套）；⑤ v0.48 日/周分享图（`posterTextBlocks` 一份文字 DOM+canvas 两消费、短标签来自 `RPL-Share-v1.json` 的 `catShort` 唯一读口、e1RM 与首页同口径 `anchorDoneE1rm`、PNG 经 `exportDoc('image/png', 裸 base64)` 落盘）；⑥ v0.49 设置页六段重组（18 行一行不减）+ 六边形能力记录 HPR（`state.hpr` 单键、六轴单源、力量轴经 `currentGl()` 实时派生 GL 绝不存死数、雷达 SVG 落 AUX；进 `WORK_KEYS + IMPORT_KEEP_KEYS`，不动 CSV 26 列 / 契约 / `SCHEMA_STAMP`）。CSV 26 列列序、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP` 一字未动。

**发布验证**：`python tools/pack.py` 全链通过——`python tools/gate.py` **61 PASS / 0 FAIL**（静态守卫 51/0 + 动态 10 套：v3v 464 / v2v 47 / check_hud 四档 / 六表契约 147 / plan_xlsx 往返 4231 格差异 0 / xlsxv 171 / logicv 58 / uiv 251 / sabr selftest / gearv 67）；APK 内嵌 `index.html` 与仓库产物逐字节一致。真机验收未跑（分享图出图 / 系统文件选择器落 PNG / HPR 雷达实际渲染 / 换计划保全 / 中英双语重渲随本版出包后点验，见 D19 与 ROADMAP §12）。逐版明细见 `CHANGELOG.md` [v0.44]–[v0.49]。

---

# ExDark Pro · v0.49

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.48（versionCode 43 → 44）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **设置页六段重组 + 六边形能力记录 HPR**。设置页由平铺长单重排为「我的档案 / 我的水平 / 教练与计划 / 器械装备 / 数据报告 / 软件与高级」六段：18 行入口一行不减，只加分段头与换序，分段头双语进 i18n 名单、`v3v` E 段逐段钉住 id 序列，`_sabotage_m15.py` 换序靶随新结构改指同段相邻 `setAdvT↔setSciT`。**六边形能力记录**进 GPP 页：跨领域个人最佳收进 `state.hpr` 一个键，六轴单源 `HPR_AXES`（耐久/力量/控制/心智/球类/柔韧），完成度只在 `hprComplete`、轴分只在 `hprAxisScore`、**力量轴经 `currentGl()` 实时从 IPF GL 派生、绝不存死数**，雷达 SVG 落 AUX 看板双语且窄屏不溢出；内置 7 项对齐例举（5km/半马/引体 30/无辅助倒立 60s/冥想 2h/GL/扣篮）、柔韧轴默认自定义、自定义可增删。`state.hpr` 进 `WORK_KEYS + IMPORT_KEEP_KEYS`（本机账本、换计划不丢），**不进 CSV 26 列、不加第九表、不动契约 v3**；经 `ensureShape` 键种落地、不动 `SCHEMA_STAMP`。新守卫 **S51**（六轴单源/存储归属不越界/评分出口单源/力量轴现读/内置 7 项 flex 空/雷达落 AUX+成品同段），静态 50→**51**、全量 60→**61**；新家族 `_sabotage_m20.py` 六组（各红 S51 一腿）；v3v 新增 HP1–HP9（EXP_N 440→**452**，报告 452→**464**），M10 账本键数随 hpr 由 14→15。CSV 26 列、`data/*.xlsx`、既有契约与 `SCHEMA_STAMP` 一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **61 PASS / 0 FAIL**（静态守卫 51/0，含 v3v 464 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4231 格差异 0）。反向验证：`sabr run m20 1 2 3 4 5 6`「期望腿 S51 真红 / 无意外红 / 逐字节还原 / 复跑回绿」全绿；设置段 `_sabotage_m15.py` 换序靶重定后随全量门禁复看。真机验收未跑（HPR 雷达实际渲染 / 自定义增删 / 换计划保全 / 分享图出图等统一等 v0.50 出包后验，见 D19 与 ROADMAP）。逐版明细见 `CHANGELOG.md` [v0.49]。

---

# ExDark Pro · v0.48

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.47（versionCode 42 → 43）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **日/周分享图**。把一次训练排成一张可保存的竖版 PNG：**日卡**逐行处方（主项/变式每行带徽章 + 组次/RPE + 功能短标签贴片，配件按功能类别聚合），顶部印 SBD 三项总计与 Δ、总容量、最高 e1RM、体重；**周卡**本周六项 1RM（深蹲/卧推/硬拉/站推/引体附加/双杠附加）+ 三小项/功能标注贴片 + 逐日吨位与完成小结，周图不画体重格（`postBwBox` 在 week 态隐藏，id 保留供 S25/成品同段核对）。**文字只有一个出处**：`posterTextBlocks` 出货纯字符串，DOM 预览与 `buildPosterCanvas` 各自消费同一份，canvas 只从 `posterPaintPlan` 取字（画布配色经 `cssVar` 唯一令牌读口取主题，字面量仅「读不到令牌时」兜底，不是第二份主题）。**功能短标签**唯一来自新契约 `RPL-Share-v1.json`（`share_ver` + 33 条 `short_labels`），`build_html` 注入时与 seed `lib.categories` 类别全集**双向相等**、缺一即中止，模板里只 `catShort` 一处读口、零手抄，日图不再印原始类别码（如 `S.Main`→「深蹲主项」）。**e1RM 同口径**：周卡「最高 e1RM」与首页「最近记录」改用同一把 `anchorDoneE1rm`（锚项完成组实际最优），杜绝第二份公式。**保存 PNG** 走 `AndroidBridge.exportDoc(name,'image/png',裸 base64)`——剥 `data:image/png;base64,` 前缀只写一行，文件名 `RPL_ExDark_v{{VER}}_share_{day|week}.png`（版本位仍取 `{{VER}}` 单源），不经 ACTION_SEND，本机无 Canvas 时提示改用预览截屏。**页脚**取当日打气句可点轮换（关打气则回落品牌串）、署名走 `nickName()`（≤24 钳位仍只在 `saveNick` 一行），切语言即时重渲分享图。新守卫 **S50**（六类腿：SHARE 契约注入且成品指纹带 `share=` 位 / catShort 唯一短标签读口零手抄 / posterTextBlocks 一份两消费（DOM+canvas）且 paintPlan 只喂 canvas / anchorDoneE1rm 海报与首页同口径各调一次 / 裸 base64 剥前缀 + 桥 image/png + 文件名版本位各一份 / 周图关 BW + 卡面 14 面 id + 保存·换句控制接线 / 成品同段），静态守卫 49→**50**、全量门禁 59→**60**；v3v 441→**452**（新增 PX1–PX11，EXP_N 429→440；N9d/N9e 补「零原始类别码」），`build_html.py` 指纹增至八源（新 `share=` 位），`_sabotage_m1.py` F4 靶串随指纹格式重定。**同时修订反向验证**：`_sabotage_m1.py` F2（就地删 `RPL-Exchange-v2.json` 的 `key_order`）期望从「S40」改指 **S39**——v0.31 起「契约不可就地改、与 HEAD 哈希失联」由 S39 拦，S40 只比 v3 对 v2 的超集键、不含 key_order，原描述滞后于守卫拆分。新家族 `_sabotage_m19.py` 五组（F1 文案单源被拆 / F2 剥前缀失效 / F3 周图 BW 三目反接 / F4 海报 e1RM 改口 / F5 catShort 读口掏空，各红 S50 一腿）。CSV 26 列列序、`data/*.xlsx` 权威源、既有三份契约一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **60 PASS / 0 FAIL**（静态守卫 50/0，含 v3v 452 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4231 格差异 0）。反向验证：`sabr run m19 1 2 3 4 5` 全族合注「期望腿 S50 真红 / 无意外红 / 逐字节还原 / 复跑回绿」；`sabr run m1 1 2 3 4` 重跑「期望 S4/S5/S15/S17/S39 / 实到同 / 无意外红 / 还原 / 回绿」（F2 改指 S39 后与实到齐）。真机验收未跑（分享图出图 / 系统文件选择器落 PNG / 页脚换句 / 双语重渲需上机点，统一等 v0.50 出包后验，见 ROADMAP §12）。逐版明细见 `CHANGELOG.md` [v0.48]。

---

# ExDark Pro · v0.47

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.46（versionCode 41 → 42）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **主页打气 + 日历引擎 + 器械视觉**。首页「今日是哪一课」横幅改由 `planPos` 从 startDate 与自然日差派生（周 / 星期 / 块一并算出），不再读 `state.week`；off-plan 三态改口（未开始 / 已结束 / 日期无效），休息日指路「下一次是 周三 B1W1DA 甲日」。课码统一 `B{块}W{周}D{日字母}`，以金底 mono 贴片（`.gc-code`）落在横幅与最近记录卡上。**每日打气**：12 句按日期轮转（dayNo = 年\*372+月\*31+日，刻意避开 epoch 毫秒时区错位），昵称可改（≤24 字符，trim+截断只写 `saveNick` 一行）；打气开关与昵称都只进 prefs 分片（`SCHEMA_STAMP` 不动、训练账本一字不动、不进 CSV 26 列）。**最近完成课**卡：ΣdoneSets>0 的（周, 日）按周降序 × 星期偏移降序取第一个，组数 = ΣdoneSets，e1RM 只取锚项（S/B/D Main）最优，日期优先取 e1rmLog 同课记录的字典序最大者、缺记录回退计划派生日；无完成课时隐藏网格、单行居中空态（响应用户「好丑好割裂」的整页重排，改走 HUD 设计语言：细左标尺线打气句 + 2×2 mono 数字格）。**器械视觉**：哑铃卡单边显重 + 双格 `×2=总重`；自重卡画人形 SVG、加重 / 辅助 / 自重三态切换（净负荷 = 体重×力臂 + 带符号外载）；非杠铃形态一律关掉套管轴（`no-sleeve` 双向切）。模板里手抄的英文星期回退名单删净，单源走契约 `Days.weekday_labels` + `WD_ZH`。新守卫 **S49**（六腿：星期名单双源零出现且 `weekday_labels` 只两处读口 / nick·cheerOn 双名单登记与 24 钳位各一份 / 横幅 14 把函数与 dayNo 公式各恰好一份 / 两张卡 13 面 id 齐 / 哑铃·自重四函数两分支与 no-sleeve 在位 / 成品同段），静态守卫 48→**49**、全量门禁 58→**59**；反向验证新家族 `_sabotage_m18.py` 五组（F1 钳位改数 / F2 手抄星期名单复活 / F3 横幅退回旧口径 / F4 哑铃分支被吞 / F5 dayNo 换 epoch 毫秒）。v3v 426→**441**（新增 HX1–HX15）。CSV 26 列列序、`data/*.xlsx` 权威源、两份契约一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **59 PASS / 0 FAIL**（静态守卫 49/0，含 v3v 441 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4231 格差异 0）。反向验证：`sabr run m18 1 2 3 4 5` 五条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」（F1 原靶 PREF_KEYS 行与 w1/m11/m12 三家靶串同行、注入必连带 S23 判腐，改打独立的 saveNick 钳位行后只红 S49；nick 登记腿由 v3v HX4 动态兜底）。主页两张卡以 393px 无头截图三屏核看（亮空态 / 亮填充 / 暗 off-plan），CONSOLE 无报错。真机验收未跑（按裁决累积进 ROADMAP §12：v0.47 涉「横幅 off-plan 三态文案 / 打气与昵称跨重启记忆 / 哑铃·自重卡 320–412 排布 / 最近完成课日期口径 / 勾选还原」需上机点，统一等 v0.50 出包后验）。逐版明细见 `CHANGELOG.md` [v0.47]。

---

# ExDark Pro · v0.46

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.45（versionCode 40 → 41）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **运动员水平页**。档案页「1RM / Bio」两档 Tab 制退役，收为 **17 行单页全量表**：性别 / 年龄 / 身高 / 当前体重 / 目标体重 / 装备 / 营养 / S·B·D 1RM（各带目标格）/ OHP 1RM / 引体附加 / 双杠附加 / GL / DOTS / Wilks / 段位，变化量贴片（▲▼）仍挂行名后。左侧圆形 medal 换成**条状段位徽章**：GL 值、段位、星级、距下一星同屏一行，边框色跟段位色。三小项（OHP / 引体 / 双杠，D17）首次全量进 Profile / CSV / 六表 / JSON 四条链路——附加重量按契约 `range [0,200]`，负数在 `saveProfile` 钳位行夹 0（钳位只写一份）；三小项**不触发** S/B/D 处方重算（`anchorOf` 三锚单源，Lv2 逐字节钉）。**LevelSnapshot**：保存只在跟踪值变化时落当天一行、同日覆盖最后一行且**保留备注**；快照表可编辑，合计 / GL / DOTS / Wilks / 段位当场按系数重算；快照走六表 Level 页（契约 `sheets.Level` 19 列），不占 CSV 26 列协议，三小项随 CSV PROFILE notes 往返零差。旧档缺三小项按 0、段位不缺算（Lv3）。新守卫 **S48**（水平页六腿单源：17 行几何与三小项输入各一面 / CSV 携带与钳位各恰好一份 / `SNAP_TRACK` 对齐契约 `Level.keys` 值域 / medal·Tab·旧系数卡 CSS 退役零残留 / 成品同段），静态守卫 47→**48**、全量门禁 57→**58**；反向验证新家族 `_sabotage_m17.py` 五组（F1 行几何 / F2 CSV 携带 / F3 钳位 / F4 键漂移 / F5 退役残留）。CSV 26 列列序、`data/*.xlsx` 权威源一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **58 PASS / 0 FAIL**（静态守卫 48/0，含 v3v 426 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4231 格差异 0）。反向验证：`sabr run m17 1 2 3 4 5` 五条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」。真机验收未跑（无设备，按裁决累积进 ROADMAP §12：v0.46 涉「水平全量表 320/360/393 宽不横向溢出 / 段位条可读 / 快照编辑手感」需上机点，统一等 v0.50 出包后验）。逐版明细见 `CHANGELOG.md` [v0.46]。

---

# ExDark Pro · v0.45

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.44（versionCode 39 → 40）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **GPP 引擎 + JTS 六维重构**。AUX 页从「恢复装甲」重建为 **GPP · 一般身体准备**：内置目录与每周菜单 8 行由契约 `RPL-GPP-v1.json` 单源，逐项可记时间 / 距离 / 组数 / 负重 / RPE，不强制完成率（显示「本周已做 X 项」与恢复影响），自定义项含旧 Wall Handstand / Gripper 原名保留、导出导入往返零丢项。JTS 按研究结论重做**六维**（睡眠 / 压力 / 疲劳 / 酸痛 / 动力 / 精力，1–7 分制，权重与正/反向极性进 `RPL-JTS-v1.json`），R = 已填维加权均值、档位分数线 `[90,75,60,45]` 只在契约一处；旧五维答案走 `migrateStateV8` 扩展段迁移（drive+willingness→动力均值、health→疲劳反向并打近似标记、energy 留空重采），原始答案存迁移备份可撤销。**恢复乘数唯一式** `recMult = clamp(recBase + B_gpp − F_gpp)`（D14）驱动建议组数，**CRS 退役**、界面直显 R 与 REC%。JTS / GPP 页单人纵向布局、320px 无重叠。新守卫 **S47**（目录单源六腿：上限 / 夹紧读口各一份零手抄、种子 gpp 对齐契约菜单序与枚举、菜单覆盖项不重复落自定义、JTS 数字零手抄、退役形态零残留、成品契约载荷与三解析函数各一份），静态守卫 46→**47**、全量门禁 56→**57**；反向验证新家族 `_sabotage_m16.py` 四组。`gen_seed.py` GPP 出厂段重写为与 App `gppCanonDefs` 恒等。CSV 26 列列序、`data/*.xlsx` 权威源一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **57 PASS / 0 FAIL**（静态守卫 47/0，含 v3v 418 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4231 格差异 0）。反向验证：`sabr run m16 1 4` 与 `sabr run m16 2 3 --build build_html.py` 四条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」（F2/F3 打在种子上，须 build-only 链——默认链先跑 gen_seed 会把故障重生成掉，已写进家族 docstring）；旧家族复验 `_sabotage_l1.py 3`（JTS 数值强制摘除 → logicv J1/J2/J8 红）、`_sabotage_n2.py` F16（分数→档位手抄 → S32 + LD14 红）还原后回绿。真机验收未跑（无设备，按裁决累积进 ROADMAP §12：v0.45 涉「GPP 页无重叠 / JTS 六维问卷 / GPP 记录后恢复数字变化 / 旧档迁移不丢答案」需上机点，统一等 v0.50 出包后验）。逐版明细见 `CHANGELOG.md` [v0.45]。

---

# ExDark Pro · v0.44

**发布日期**：**未发版节点**（v0.44–v0.49 逐版 bump+commit 但不出 APK，仅 v0.50 跑 `pack.py` 打包；本版内容随 v0.50 一并发布）
**前序版本**：v0.43（versionCode 38 → 39）
**成品**：无独立 APK（未发版节点）——最新成品仍是 `release/RPL_ExDark_v0.43_Pro.apk`（md5 `50768db406af6094e5cbff48e60db0bd`）

> **契约 v3 + 存档 v8 迁移 + 低风险 UI 止血**。计划工作簿从七表扩到**八表**：新增 `GPP`（16 列，接替旧 `Armor`，承载 R2 四域恢复目录）与 `Level`（19 列，运动员水平快照），`Profile` 补引体/双杠负重两锚点；CSV 仍 v2、**26 列列序冻结**，v1/v2 旧工作簿与旧信封照旧能导入（`legacy_compat.entries[]` 两条逐字节兼容，认不出的版本整单拒收给人话），升级即导出到 v3。存档 `SCHEMA_STAMP` 7→**8**，`migrateStateV8` 串 V7：`aux→gpp`、`auxDays→gppDays` 打卡格逐位保留、锚点补 0、`levelSnap` 补 `[]`、Day A–D 标题升级 F2 名（id/label 不动、用户自定义名保留），带迁移台账 / 撤销 / 失败回滚不丢档。暗色自然主题中文名定版「**咖啡纸感**」（英文仍 `Extra Dark`、内部 id 仍 `nature`，存量存档不迁移）并修分段控件窄屏溢出；迁移报告 / 撤销下沉「软件与高级 → 高级」；`set-go` 防换行；✅ 勾选即满组、取消归零（AMRAP 同满组）；本地计算器默认折叠（仅挂片 / 插片 / 特殊展开）；非杠铃不画横向杠铃杆、移除「低于空杆重量」错字。新契约 `RPL-Plan-v3.json`/`RPL-Exchange-v3.json`（v2 严格超集），两份 v1 契约转冻结存档；守卫 **S39** 改盯 v8 闸门、**S40** 改核 v3 超集、**S43** 补改名腿——静态守卫仍 **46** 项无净增。反向验证新家族 `_sabotage_m14.py`（UI 止血五组）+ `_sabotage_m15.py`（v8 迁移 V8a–V8h + 设置下沉 E4/E5，十组）。v3v 400→**418** / uiv 244→**251** / xlsxv 167→**171** / 契约 144→**147**（logicv 58 / gearv 67 / v2v 47 未变）。CSV 26 列列序、`data/*.xlsx` 权威源一字未动。

**发布验证**：本版不出 APK，验证停在门禁层。`python tools/gate.py` **56 PASS / 0 FAIL**（静态守卫 46/0，含 v3v 418 / gearv 67 / uiv 251 / logicv 58 / 契约 147 / xlsxv 171 / v2v 47 / plan_xlsx 往返 4119 格差异 0）。反向验证：`sabr run m15 1 2 3 4 5 6 7 8 9 10 --with fast` 十条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」（F01 的 LD1 连带为正确连带，已写进 docstring 不入期望腿）；`sabr run m14 1 2 3 4 5 --with fast` 五条同判据 PASS。真机验收未跑（无设备，按裁决累积进 ROADMAP §12：v0.44 涉「v8 迁移在 `pm clear` 前后各一次 / 契约 v3 八表导入导出 / 计算器折叠 / ✅ 满组 / 咖啡纸感主题」需上机点，统一等 v0.50 出包后验）。逐版明细见 `CHANGELOG.md` [v0.44]。

---

# ExDark Pro · v0.43

**发布日期**：2026-11-05
**前序版本**：v0.42（versionCode 37 → 38）
**成品**：`release/RPL_ExDark_v0.43_Pro.apk`（983.2 KB / md5 `50768db406af6094e5cbff48e60db0bd`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `b2e806ccd596e94c4588b4c27108c060`；构建指纹 `v=0.43.38 tpl=3f71c683 seed=7647bbb0 sch=24737e91 exc=cbbbcd3e gear=f7f77a18`）

> **装备照片上传**。装备表单顶部多了一格 **1:1 缩略位**：没图是虚线占位（「📷 无图 · 点选上传」），点一下走系统相册/拍照选择器，选完回来即时刷新；有图右上角 ✕ 删图，删装备同步清图。图片经三个新 Java 桥方法（`gearPickPhoto`/`gearPhotoData`/`gearDelPhoto`）落**应用私有目录**——**大三限**：源文件 >10MB 拒收、最长边压到 512px、JPEG 成品 >200KB 逐级降质量（80→60→40）。照片**不进任何 JSON 分片与导入导出**（prefs 仍 11 键、`SCHEMA_STAMP` 不动、CSV 26 列与 Plan/Exchange 契约一字未动），卸载随 App 消失。新守卫 **S46** 钉「缩略位·七函数·三桥调用·渲染钩子各恰好一份 / 占位与图态两分支齐 / 旧「照片延到下版」零残留 / Java 三桥各一面且回调 / 大小三限在位 / 成品同段」；反向验证新家族 `_sabotage_m13.py` 五组（F1 桥名漂移 / F2 占位死类名 / F3 渲染钩子废 / F4 回调缺位 / F5 读口大小闸恒假）。v3v 399→**400**（EQ13 照片位腿），静态守卫 45→**46**、全量门禁 55→**56**。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 46/0 → 注入 v0.43.38 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **56 PASS / 0 FAIL**，含 v3v 400 / gearv 67 / uiv 244 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47）。反向验证：`sabr run m13 1 2 3 4 5 --with fast` 五条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」（F2 的 v3v EQ13 连带为正确连带，已写进期望腿）。真机验收未跑（无设备，按裁决累积进 ROADMAP §12 真机清单：v0.43 涉「系统选择器真调起与选图回落 / 选完缩略位即时刷新 / 删图与删装备清图 / 大图拒收与压缩后清晰度 / 杀进程重开照片还在」需上机点）。

---

# ExDark Pro · v0.42

**发布日期**：2026-11-05
**前序版本**：v0.41（versionCode 36 → 37）
**成品**：`release/RPL_ExDark_v0.42_Pro.apk`（980.7 KB / md5 `b91366c3a1616f8340f03def0dc6cc81`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `e30518dbf638a80216bb41206da1ad39`；构建指纹 `v=0.42.37 tpl=0bbe63f7 seed=7647bbb0 sch=24737e91 exc=cbbbcd3e gear=f7f77a18`）

> **八周减重保力计划 + D9 负重引体**。工作簿周期全面改写为 B1 Hyper 3w / B2 Strength 3w / B3 Peak 2w（共 8 周），BW 从 87.5→82.5，开把 S/B/D 恒定 130/90/160 不变——减重不降力。W8 含 Top.Test 1x1 测验日。动作库新增 D.Lats「Weighted Pull-Up 负重引体向上」共 260 动作 / 33 分组；计划三天 B/C/D 均编排了它，逐周加重至 W8 回自体重。profile 目标 1RM 140/100/170、计划日期 2026-11-09~2027-01-04。`gen_seed.py` 正常生成 3 块 8 周 200 条处方种子；`rxlib.py __main__` 探针修复；回归断言 v3v/v2v 适配新结构（L1/P11/P12/Q6/V02-07/迁移夹具）；validate_data 关键格期望更新到 v0.42 锚点。模板 UI、CSV 26 列、Plan/Exchange 契约、`SCHEMA_STAMP` 零改动。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 45/0 → 注入 v0.42.37 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **55 PASS / 0 FAIL**，含 v3v 399 / gearv 67 / uiv 244 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。真机验收未跑（无设备，累积进 ROADMAP §12 真机清单）。逐版明细见 `CHANGELOG.md` [v0.42]。

---

# ExDark Pro · v0.41

**发布日期**：2026-11-05
**前序版本**：v0.40（versionCode 35 → 36）
**成品**：`release/RPL_ExDark_v0.41_Pro.apk`（980.4 KB / md5 `4a08fbbf93d0a85b781fb5053bee68fa`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `44dfdd4efacbf57af6ebb5f463da225e`；构建指纹 `v=0.41.36 tpl=0bbe63f7 seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=f7f77a18`）

> **装备库 + 场地库 UI（无照片版）**。设置页「场地 · 库存」之后新增**「装备 · 场地库」**，打开是三舱一张板：**装备库**给每件装备建档——13 类词表（契约现读，模板零手抄）、品牌/产品线/型号/尺码/关键规格/材质构成/来源/用途/价格/数量/竞技评价/状态/备注与合规；深蹲鞋·腰带·套膝三类有硬规格的，规格输入自动换成带单位数字腿（坡差 mm / 厚度 mm）。**成色按 CS2 五档**点选：崭新出厂 / 略有磨损 / 久经沙场 / 破损不堪 / 战痕累累，绿蓝黄橙红胶囊、三套主题各自配色，只存档位 id、不存浮动值伪精确。**场地库**管健身房/居家/操场：新建（名字裁到契约上限）、改名改型、设为当前、**在场器械一行一台**进出、删除两步确认且 legacy 删丢兜底重建；杆重·赛扣·在场的片仍在「场地 · 库存」改——改的永远是当前场地。**赛前检查舱纯只读**：列「比赛」状态装备与合规确认位、各场地器械清单，页面自带口径「App 不查规则表、不给结论」。`gearKit` 进 prefs 分片（10→11 键）与导入保护名单、**不进 `WORK_KEYS`**；旧存档 `ensureShape` 补 `gearKit=[]` 与每台场地的 `machines=[]`，`SCHEMA_STAMP` 不动（仍 7）。Gear 契约本版字段终审扩表（fields 补 size/material/wear、`spec_keys` 数值腿、`wear_levels` 五档、`machines_*` 形状）——词表附表扩展，六表协议与求解引擎零触碰。照片（应用私有文件 + 两个 Java 桥方法）整体留给下一版。新守卫 **S45** 钉「gearKit 双名单各登记一次 / 回填+防御计数恰好 2+1 / kitSheet·入口·收口·文案各一份 / `WEAR_CHIP` 对齐契约 `wear_levels`（档位现读不手抄）/ 成色色标三套主题各定义一次 / 成品同段」；新家族 `_sabotage_m12.py` 五组反向腿（F1 prefs 键名漂移→S45+M10+EQ4+S23、F2 回填整行删→S45+EQ1、F3 WEAR_CHIP 死类名→S45+EQ3+S22、F4 收口漏 kitSheet→S45、F5 主题缺色标→S45+S19）。CSV 26 列、Plan/Exchange 契约、`data/*.xlsx` 一字未动。逐版明细见 `CHANGELOG.md` [v0.41]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 45/0 → 注入 v0.41.36 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **55 PASS / 0 FAIL**，含 v3v 399 / gearv 67 / uiv 244 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：`sabr run m12 1 2 3 4 5 --with fast` 五条均「期望腿真红 / 无意外红 / 逐字节还原 / 复跑回绿」；F4 的 ui 层连带实测存在但泄漏集合竞态相关，按 docstring 只收 fast 层证据。`_sabotage_m11/n2/w1` 三家 F1 靶串随 PREF_KEYS 追加同步重指并复跑 PASS。真机验收未跑（无设备，按裁决累积进 ROADMAP §12 真机清单：v0.41 涉「kitSheet 三舱真点与四档宽度 / 成色胶囊三主题配色 / 装备两步删除 / 场地切换后库存跟当前场地 / prefs 落盘跨进程记忆」需上机点）。

---

# ExDark Pro · v0.40

**发布日期**：2026-11-05
**前序版本**：v0.39（versionCode 34 → 35）
**成品**：`release/RPL_ExDark_v0.40_Pro.apk`（972.4 KB / md5 `f0a58b429efda97df394479f20962c80`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `e1eb1039333c00723f3cf7d462c589a2`；构建指纹 `v=0.40.35 tpl=79460dcc seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=55b1d173`）

> **会员徽记 + 每日状态监控默认关闭**。首页右上角那颗 Pro 升成 `✦Pro` 菱形星标徽记：挂在标题旁、与 `h1` 平级，徽记自身不带版本号，四档屏宽（含 320px）不裁不挤。每日状态监控出厂即关：设置 · 运动员配置新增「每日状态监控」开关（默认 OFF），关掉后首页 STATUS 舱钮藏起、直呼面板入口被拒并用人话指路，开关状态进 prefs 分片跨重开记忆、导入计划不覆盖；老存档缺这个键回填成「关」。体重趋势搬到运动员页作唯一留场行（净变化 `▼` / `持平` / `记录不足两周` 三态，纯只读不写账）。`teleOn` 只进 prefs 分片（9→10 键）与导入保护名单，不进 `WORK_KEYS`。新守卫 **S44** 钉「两名单各登记一次 / 读口·回填·闸门·藏舱·按钮·文案各一份 / `bwSeries` 读者恰 2 / 徽记 markup 唯一 + `.pro-mark` 两规则在位 / 旧写法 `<em>Pro</em>`·`ProMax` 零残留 / 成品同段」；新家族 `_sabotage_m11.py` 五组反向腿（F1 prefs 键名漂移→S44+M10+TM4、F2 旧存档回填弹开→S44+TM2、F3 闸门恒假→S44+TM3、F4 徽记退回裸 em+ProMax→S44+A5+N2+TM1、F5 体重趋势第二份口径→S44+TM5）。CSV 26 列、两份契约、`SCHEMA_STAMP`（仍 7）、`data/*.xlsx` 一字未动——`teleOn` 是 UI 闸门不是数据协议。逐版明细见 `CHANGELOG.md` [v0.40]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 44/0 → 注入 v0.40.35 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **54 PASS / 0 FAIL**，含 v3v 387 / gearv 67 / uiv 237 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：`sabr run m11 1 2 3 4 5 --with fast` 五条均「期望腿真红（F1→S44+M10+TM4+S23、F2→S44+TM2+TM3/TM4 真连带、F3→S44+TM3、F4→S44+A5+N2+TM1、F5→S44+TM5）/ 无意外红 / 逐字节还原 / 复跑回绿」。真机验收未跑（无设备，按裁决累积进 ROADMAP §12 真机清单：v0.40 涉「徽记四档宽度不裁不挤且不带版本号 / 开关点开的真全序（落盘→舱现→进面板→关回）与跨进程记忆 / 旧存档升级回填成关 / 体重趋势行只读且不受开关影响」需上机点）。

---

# ExDark Pro · v0.39

**发布日期**：2026-11-05
**前序版本**：v0.38（versionCode 33 → 34）
**成品**：`release/RPL_ExDark_v0.39_Pro.apk`（970.8 KB / md5 `770644f43b74549ce57f52ff0a37fbab`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `8a61755a3a126c8e626a9b48ec6847e7`；构建指纹 `v=0.39.34 tpl=90ae2b4c seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=55b1d173`）

> **咖啡纸感配色改名 Extra Dark + 周期「阶段」独立成条**。设置页那颗按钮现在写 `☕ Extra Dark`（副标题与顶栏字形同步，字形 ❦ → ☕），**内部 id 仍是 `nature`**——这是一次纯对外改名，存量存档里的 `state.theme` 一个字节都不迁移，老用户升级后不会跳回暗色。周期目标评估的「阶段」从两列数字网格里搬出来，自己占一条横排：每个周期块一枚胶囊（块名 + `工作周+减载周`），块间 `→` 相连，周期里没有 Peak/Test 块时条尾挂金色角标 `无 Peak/Test`；四块周期也读得动。这块 UI **纯只读**：读 `structure.blocks`，不写账本、不进任何重量公式。新守卫 **S43** 钉「阶段只有一个出口 / 四个 class 各有 CSS 规则 / `THEME_IDS` 里 `nature` 必须还在 / 旧名零残留 / 成品同段」；新家族 `_sabotage_m10.py` 五组反向腿（含 F4「内部 id 被改」这一发就撞红 S43+S19+S23 与动态 W 段六腿）。CSV 26 列、两份契约、`SCHEMA_STAMP`（仍 7）、`data/*.xlsx` 一字未动——无新存储字段、不涉及迁移。逐版明细见 `CHANGELOG.md` [v0.39]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 43/0 → 注入 v0.39.34 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **53 PASS / 0 FAIL**，含 v3v 381 / gearv 67 / uiv 237 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：`sabr run m10 1 2 3 4 5 --with fast` 五条均「期望腿真红（F1→S43+P11/P12、F2→S43+S22+P12、F3→S43+E8、F4→S43+S19+S23+W1–W5/W9、F5→S43+S22）/ 无意外红 / 逐字节还原 / 复跑回绿」；`_sabotage_m4.py` 的 F4 靶串随改名重指后复跑 `sabr run m4 4 --with fast` 同样 PASS（S19+S25+S43+E8/W9）。`sabr.py selftest` 12/0。真机验收未跑（无设备，按裁决累积进 ROADMAP §12 真机清单：v0.39 涉「Extra Dark 按钮与副标题文案 / 顶栏 ☕ 字形与循环顺序 / 旧存档 theme 不跳回暗色（`pm clear` 前后各一次）/ 阶段胶囊在两块的种子与四块夹具下的排布与 320px 不溢出 / 评估条纯只读」需上机点）。

---

# ExDark Pro · v0.38

**发布日期**：2026-11-05
**前序版本**：v0.37（versionCode 32 → 33）
**成品**：`release/RPL_ExDark_v0.38_Pro.apk`（970.3 KB / md5 `64ed4a0e86ccf07838202a1ebdba26eb`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `d3059adff3f7d69a10c3867c76273224`；构建指纹 `v=0.38.33 tpl=57fbf97c seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=55b1d173`）

> **周训练总结升级 + SBD 强调配色**（承接 v0.37 策略绑定）。周海报的「模式分布」换成练什么的账：**三小项计数**（深蹲/卧推/硬拉 + 其它，按动作数与组数）+ **功能标注**（按动作库类别码逐码列 occurrences，粒度停在库码如 `SBD.UpperBack ×3`，不做第二份映射名单）+ 全周合计；日海报每行挂族色贴片。归类与配色各恰好一份（`sbdFamilyOfCat` / `SBD_CHIP`），贴片颜色取自 8 枚 `--sbd-*` 令牌 × 暗/亮/自然三块主题配对，`.pc-*` 只引用 `var()`。新守卫 **S42** 钉单源/令牌份数/海报接线/成品同段；`_sabotage_m9.py` 加 F8–F10 反向腿。CSV 26 列、两份契约、`SCHEMA_STAMP`（仍 7）、`data/*.xlsx` 一字未动——无新存储字段、不涉及迁移。逐版明细见 `CHANGELOG.md` [v0.38]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 42/0 → 注入 v0.38.33 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **52 PASS / 0 FAIL**，含 v3v 377 / gearv 67 / uiv 237 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：`sabr run m9 8 9 10 --with fast` 三条均「期望腿真红（F8→S42+Z0/Z1、F9→S42+S19、F10→S42）/ 无意外红 / 逐字节还原 / 复跑回绿」；`sabr.py selftest` 12/0。真机验收未跑（无设备，按裁决累积进末尾真机清单：v0.38 涉「周海报三小项/功能标注/合计行可读性 / 日卡贴片在亮色与自然主题下的辨识度 / 贴片文本不截断」需上机点）。

---

# ExDark Pro · v0.37

**发布日期**：2026-11-05
**前序版本**：v0.36（versionCode 31 → 32）
**成品**：`release/RPL_ExDark_v0.37_Pro.apk`（968.8 KB / md5 `a68d628b7d98bfd318700ec5fff907ed`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `8dbf9c00473d248eb649c718491106fd`；构建指纹 `v=0.37.32 tpl=c03eadd4 seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=55b1d173`）

> **组策略默认绑定 + 智能训练引擎门面（D13）**（承接 v0.36 契约体系）。每张动作卡按训练族自动绑一条默认组策略——GZCLP 数数族→AMRAP 组、RTS→RPE 封顶组、TOP→顶重组、CLASSIC→恒重组，认不出走兜底（恒重组）；首页卡片与周导出行显示策略名，自动绑挂 `·`、手动选过的挂 `🎯`，一眼分清「引擎给的」还是「你定的」。编辑器策略下拉按当前模式族预置自动值，手动改选即存显式选择覆盖自动。绑定是**纯展示层**：`stratBoundId(e)` 只在读时算，绝不写回存档、`prescriptionOf` 不读取它（处方权威仍是 ROADMAP §5：`rx` 文本唯一）。新守卫 **S41** 钉这条单源：族表可解析、族键落在真实 proto 枚举、默认 idx 真在 `strategyLib`（绑到缺号=静默不绑、表会说谎）、兜底在库、四段接线在位、`prescriptionOf` 函数体不含 `strat`、产物同段；`_sabotage_m9.py` 加 F5–F7 反向腿。D13 门面：「Re.Plus / 下周建议」面板更名**智能训练引擎**（标题/设置行/双语词对同步），批量应用/撤销工具条挪到建议表下方——先看结论再动手；底层 `advice*` 函数与 `autoreg` 阈值一字不动。CSV 26 列、两份契约、`SCHEMA_STAMP`（仍 7）、`data/*.xlsx` 一字未动——无新存储字段、不涉及迁移。逐版明细见 `CHANGELOG.md` [v0.37]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 41/0 → 注入 v0.37.32 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **51 PASS / 0 FAIL**，含 v3v 372 / gearv 67 / uiv 237 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：`sabr run m9 5 6 7` 三条均「期望腿真红（S41）/ 无意外红 / 逐字节还原 / 复跑回绿」；`sabr.py selftest` 12/0。真机验收未跑（无设备，按裁决累积进末尾真机清单：v0.37 涉「首页策略徽章 `·` 自动 vs `🎯` 显式 / 编辑器下拉预置自动值 / 智能训练引擎标题与徽标双语切换 / 批量工具条挪到建议表下方后的点按」需上机点）。

---

# ExDark Pro · v0.36

**发布日期**：2026-11-05
**前序版本**：v0.34（versionCode 30 → 31；v0.35 为未发版节点，内容随本版一并打包）
**成品**：`release/RPL_ExDark_v0.36_Pro.apk`（968.1 KB / md5 `309683da0ac60cb0c3a913ef068408df`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `6eb318354535144b317bce0310884a6c`；构建指纹 `v=0.36.31 tpl=136cadaa seed=1b4ed614 sch=24737e91 exc=cbbbcd3e gear=55b1d173`）

> **计划交换升 v2：器械配置进交换契约**（承接 v0.31–v0.35 配重引擎六类全真）。`.xlsx` 计划工作簿在六表之后多出第七张 `Gear` 附表，逐条记录每个动作的器械配置（周 / 日 / 行锚 + `gear_json`）；JSON 信封同样携带 `plan.Gear`——换设备、发给教练，配重形态不再丢。v1 世代的六表工作簿与 v1 信封**照旧能导入**：版本路由只有一个落点（JS `xEffectiveOrder` / Python `_effective_order`），`Profile!schema_ver` 是 v1 名单就按六表读、字段全缺按七表读、**认不出的版本串整单拒收并给人话**，绝不静默降级或凭空造表。导入 v1 后重新导出自动落到 v2（信封 `current="RPL-Plan-v2"`、`accepted` 同列 v1/v2）= 升级即导出。往返零格差扩到带器械的计划：canonical（含 Gear）导出→读回逐格对账 5634 格差异 0；`Gear` 缺必填列值、`row_idx` 锚不存在等坏行，App 内引擎与 Python 侧报同样的错。新契约 `RPL-Plan-v2.json` 是 v1 的严格超集，新守卫 **S40** 把分叉白名单钉死（含生成链双指针必须指 v2、`plan_payload_contract` 指 v2）；两份 v1 契约转为冻结存档（S39 盯哈希）。本版同时收进 v0.35 两节点：⑪插片双栈独立插销 + gcd 步长 + 竖向配重堆，⑫特殊器械卡 + 六 chip 收口 + `equip→kind` 推断的设置页展示与单条修正 + 日程→场地引用。CSV 26 列、存档 `SCHEMA_STAMP`（仍 7）、`data/*.xlsx` 一字未动。逐版明细见 `CHANGELOG.md` [v0.35] [v0.36]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 40/0 → 注入 v0.36.31 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **50 PASS / 0 FAIL**，含 v3v 365 / gearv 67 / uiv 237 / logicv 58 / 契约 144 / xlsxv 167 / v2v 47 / 往返 0 差）。反向验证：新增 S40 后契约编辑类 sabotage 家族（a6 / m1 / m2 / m3 / m8 / u1）全部重指 v2 文件并合注 PASS；m3 加 F4（legacy_compat 与 v1 分叉 → S40 红）/ F5（accepted 丢 v1 世代 → S40 红）；`sabr.py selftest` 12/0。真机验收未跑（无设备，累积进末尾真机清单：v2 导出带 `Gear` 附表 / 旧 v1 工作簿与 v1 信封导入 / 升级重导出 / 往返逐格核对需上机点）。

---

# ExDark Pro · v0.34

**发布日期**：2026-11-05
**前序版本**：v0.33（versionCode 29 → 30）
**成品**：`release/RPL_ExDark_v0.34_Pro.apk`（960.3 KB / md5 `7c02d9771da5d403888f69c479224f54`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `f09dbd4f690f991dd364a410dbd95bfc`；构建指纹 `v=0.34.30 tpl=3d9e9ca9 seed=1b4ed614 sch=8e06170b exc=468758ef gear=55b1d173`）

> **挂片位器械 UI + 首页前四形态收口**（承接 v0.31 配重引擎、v0.32 处方权威化、v0.33 器械三态）。挂片类（plate-loaded）在编辑器不再是光一行字：新增 `posts` 位选择（1/2/4/6/8，取自器械词表 `RPL-Gear-v1` 的 `loaded.posts_options`，模板不抄第二份名单）、史密斯开关、下限 0 的基数输入；配重台把均衡装载画成网格——`posts` 个挂片位每位一叠同配方片（均衡 = 左右同重）、标 `#位 每位净重`、配不平给「每位余 Xkg」，挂片位不是横杠所以关掉杠铃那根套管轴（`no-sleeve` 双向切）。史密斯的命门是语义：`variant:smith` 时基数是机头自重、求解绝不叠加 20kg 奥杆，切过去给一条 toast 讲清、不静默。首页 `gear-strip` 让挂片卡从纯文字升级成可数形态（一位片叠 + `×N 位`），与杠铃逐侧片条 / 哑铃单边 `×2=总重` / 插片插销读数并列成「前四形态各有形状」。挂片求解（`solveLoad` 的 `plate` 分支、步长 `posts × min_plate`）早在 v0.31 节点③就实现，本版纯接 UI 与可视化、不动引擎算术。`gearv.js`（D12）`50 → 56`（新增 `G8` 六条挂片位断言，全部真点编辑器与首页、出段还原快照由 `G0.2` 复核零副作用），`_sabotage_g1.py` 加 `F15`（posts 枚举把关失效 → `G8.4` 红）/ `F16`（首页挂片不画片叠 → `G8.6` 红）。CSV 26 列、两份 v1 契约、`SCHEMA_STAMP`（仍 6）一字未动——无新存储字段、不涉及迁移。逐版明细见 `CHANGELOG.md` [v0.34]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 39/0 → 注入 v0.34.30 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **49 PASS / 0 FAIL**，含 v3v 365 / gearv 56 / uiv 237 / logicv 58 / contract 118 / xlsxv 146 / v2v 47 / 往返 0 差）。反向验证（作者注入、本席复跑对账）：`sabr run g1 15 16 --with gear` 两条均「期望腿真红 / 无意外红 / 还原逐字节 / 复跑回绿」（`F15` → `G8.4`、`F16` → `G8.6`）。真机验收未跑（无设备，按裁决累积进末尾真机清单：v0.34 涉「挂片位配置行 / 均衡装载网格 / 史密斯切开关与基数 toast / 首页挂片卡片叠」需上机点）。

---

# ExDark Pro · v0.33

**发布日期**：2026-11-05
**前序版本**：v0.32（versionCode 28 → 29）
**成品**：`release/RPL_ExDark_v0.33_Pro.apk`（958.1 KB / md5 `547ffef688f9f2f7094f86400a1433e6`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `42e0c82f58717a854b67746d2158842f`；构建指纹 `BUILD_FP v=0.33.29 tpl=dcaa01f3 seed=1b4ed614 sch=8e06170b exc=468758ef gear=55b1d173`）

> **器械显示三态 + 自重进自动加重**（承接 v0.32 处方权威化、v0.31 配重引擎）。哑铃按单边显重、双手动作灰字补 `×2=总重`；自重类主数字改「净负荷」并显 加重 / 辅助 / 自重 三态（`e.load` 是带符号外载）；下周自动加重不再跳过自重——进步改带符号外载、走档位绝对步长、不受杠铃 ±5% 夹取（单次幅度仍受 `cap_kg`，写回只走 `advWriteLoad`、闸门按净外载重夹）；e1RM 趋势图在非首建 v7 迁移报告下于换算发生的那周画一条口径分界点线，左侧历史点为旧口径。`v3v.js`（D1）扩 `O11b`（自重进自动加重）与 `X5b`（分界线六态窄路径），`gearv.js`（D12）哑铃显示 `G7.2`。反向验证：`_sabotage_u1.py` 加 `F6` / `F7`、`_sabotage_g1.py` 加 `F14`，并把改契约三处 `F1–F3` 的期望补上 v0.31 的 S39 冻结哈希腿、`F3` 补上 `G7.2`。CSV 26 列与两份 v1 契约一字未动。逐版明细见 `CHANGELOG.md` [v0.33]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 39/0 → 注入 v0.33.29 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **49 PASS / 0 FAIL**，含 v3v 365 / gearv 50 / uiv 237 / contract 118 / xlsxv 146 / logicv 58 / v2v 47 / 往返 0 差）。反向验证（作者注入、本席复跑对账）：`sabr run g1 1..14 --with gear` 全「期望腿真红 / 无意外红 / 还原逐字节 / 复跑回绿」（`F3` 现列 G1+G7.2、`F14` 自重主数字塌回 → G7）；`sabr run u1 1..7`：`F1–F3` 现列 S29+S39（改契约触发冻结哈希）、`F4` 只红 S29、`F5` 静态层 SKIP（其动态腿见脚本 docstring，未随 S39 校准）、`F6` 自重旁路失效 → O1/O11b/O14、`F7` 分界判据短路 → X5/X5b。真机验收未跑（无设备，按裁决累积进末尾真机清单：v0.33 涉「哑铃单边显重 / 自重净负荷三态 / 自重进自动加重的建议文案 / e1RM 分界线」需上机点）。

---

# ExDark Pro · v0.32

**发布日期**：2026-11-05
**前序版本**：v0.31（versionCode 27 → 28）
**成品**：`release/RPL_ExDark_v0.32_Pro.apk`（956.9 KB / md5 `4f992009560fdfda1394ff117f9e7d45`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `83ed7984b3239bba5a7a86b80b9e6283`；构建指纹 `BUILD_FP v=0.32.28 tpl=d463e376 seed=1b4ed614 sch=8e06170b exc=468758ef gear=55b1d173`）

> **处方权威化 + 杠铃配重态收口**（承接 v0.31 配重引擎地基）。`e.rx` 成为唯一处方源：`1×3 + 2×5@-10%` 解析成「顶组 `1×3` + 回落 `2×5@0.90`」两组、`3×5+` 末组 AMRAP、`5×5` 恒重，解析失败才回落模式原型并标注。首页不再把 Top.Set 误显成 `3×3`，编辑器配重台逐组给重量（回落 = `mround(顶组 ×(1−降幅), 步长)`，降幅取 `@-X%`、Top 缺省 10），回落与顶组同重时提示；保存不再覆盖可解析的权威 `rx`；海报 / 落账组结构改取 `Σsets`。两端银色滚花赛扣 CSS 组件上线、配重行单行不折行；杠铃单侧字样 / 余数「最近可达」/ 库存数量勾选延续 0.31。`gearv.js`（D12）40 → 48 条（G6 处方解析 8 条含运行时种子真行自证），`_sabotage_g1.py` 加第 13 条注入（rx 解析失效 → G6 必红）。CSV 26 列与两份 v1 契约一字未动。逐版明细见 `CHANGELOG.md` [v0.32]。

**发布验证**：`python tools/pack.py` exit 0（静态守卫 → 注入 → `assembleRelease` → 内嵌产物逐字节比对 → 全量门禁 **49 PASS / 0 FAIL**，含 gearv 48 条）。反向验证：`python tools/sabr.py run g1 1..13 --with gear` **13 条注入全部「期望的腿真红 / 无意外红 / 还原逐字节相同 / 复跑回绿」**（F13 rx 权威解析失效 → G6 塌回单组，命中）。真机验收①未跑（无设备，按上面裁决累积进末尾真机清单，v0.32 涉视觉组件「两端滚花赛扣 / 配重行不折行 / TopSet 逐组重量」需上机点）。

---

# ExDark Pro · v0.30

**发布日期**：2026-11-04
**前序版本**：v0.22（versionCode 25 → 26）
**成品**：`release/RPL_ExDark_v0.30_Pro.apk`（936.5 KB / md5 `2cba85515e8e90feea8e38a0b1a799c0`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `5107ad164b9ddc4b6fefd4922f110de2`；构建指纹 `BUILD_FP v=0.30.26 tpl=3e1719aa seed=1b4ed614 sch=8e06170b exc=468758ef`）

> **v0.23–v0.30 七个开发轮次的首次正式发版**（中间轮次逐轮过门禁但未单独出成品，故本文从 v0.22 直接接上 v0.30）。六件事：① **计划引擎按谱系分组**——补齐 `T1.Mod.2/3`、`T2.Mod.3`、`T2.Def.2/3`、`T3.Power`、`T3.Tech`，周期循环改由 `planWeeks` 驱动、Block 类型取自工作簿 `周期` 表，推进规则拆成可读的四条；② **下周建议从只读走到可落笔**——只改下周、幅度上限 ±5% / ±5kg、减载周与越界拒绝、留审计、撤销逐字节还原，自动化四档（关闭 / 只建议 / 确认后应用 / 自动应用）；③ **科研图表 hub 与阈值回测校准**——图版 / e1RM 趋势 / 分类容量 / 训练日志，校准页只给建议与依据，不静默改计划；④ **环境配置 hub 与六类配重本地计算器**（插片 / 挂片 / 自重 / 自重加重 / 自重辅助 / 特殊器械），只把结果写进当次负荷，CSV 26 列协议未动；⑤ **逻辑债与 UI 债收口**——原生「读挂了」不再静默落到空账本（停在只读并亮阻断层，五个原因都有人话标签），令牌可达、分段器段数、计时时长、内联事件调用名四处改单源或清零死按钮，静态守卫新增 S28–S36；⑥ **开发便利**——新增反向验证驱动器 `mobile/tools/sabr.py`（一条命令跑完「清台账 → 注 → 建 → 跑 → 对账 → 还原 → 建 → 复跑」，四件事缺一件判 FAIL），门禁新增 D11 盯这台驱动器自己的判定出口自检。逐版明细见 `CHANGELOG.md` [v0.30] 与 `mobile/README.md` §3.4 / §3.5。

## 发布验证

`python tools/pack.py`（exit 0，五步全过：静态守卫 → 注入 → Gradle assembleRelease → 内嵌产物逐字节比对 → 发版门禁）：

```
python tools/gate.py --static → 36 PASS / 0 FAIL
python tools/gate.py（发版门禁，静态 36 + 动态 9）→ 45 PASS / 0 FAIL / exit 0
node tools/v3v.js          → 363 PASS / 0 FAIL
node tools/v2v.js          → 47 PASS / 0 FAIL
node tools/uiv.js          → 237 PASS / 0 FAIL
node tools/xlsxv.js        → 146 PASS / 0 FAIL
node tools/logicv.js       → 58 PASS / 0 FAIL
python tools/test_plan_xlsx.py → 118 PASS / 0 FAIL（六表契约 T1–T8）
plan_xlsx 导出往返         → 4582 格 → 4582 格 / 差异 0 / error 0
python tools/sabr.py selftest → 判定出口 12 条 / 0 FAIL
```

本版新增守卫的反向验证实跑记录（`python tools/sabr.py`，四件事缺一件即判 FAIL：台账空 / 期望腿红 / 还原逐字节 / 复跑回绿）：

```
run w1 1 3 6            → 3 PASS（S30 / S29+S30 / S30）
run r1 1 2 3 4          → 4 PASS（四处版本指针各红 S26，且 detail 里报的是指针漂移而不是台账残留）
run n1 1 5              → 2 PASS（S31 两侧各一条）
run n1 3 --with fast    → 1 PASS（S31 + v3v BD6、BD7）
run n2 33               → 1 PASS（S33）
run n2 22 24 --with fast→ 2 PASS（LD15+S19 / LD16+S25）
run u1 1                → 1 PASS（S29）
run b4 1 --with plan    → 全族合注 1 PASS（T1、T2、T3、T6）
selftest --live         → 假期望（S34）确实被判 FAIL
```

驱动器自身的反向验证（D11 不是摆设，两种削法都实测过）：把 `judge()` 的待测腿核对削掉、或把 `s26_corroborated()` 削成恒真，`gate.py --quick` 都只报 `FAIL D11`（detail `2 FAIL`），其余项照旧绿；改回即逐字节复原。

## 真机状态

- **未验**：本版按「只在最终版做真机验收」的既定安排出成品，装机首屏、设置页三组 IA、导入导出 E2E 真点、键盘遮挡均**未**在真机上点过。要在真机上判定这些，需要先 `adb devices` 确认设备在线，再走 `pm clear` → 安装 → 首屏 → 导入导出 E2E → 截图归档。


---

# ExDark Pro · v0.22

**发布日期**：2026-11-03
**前序版本**：v0.21（versionCode 24 → 25）
**成品**：`release/RPL_ExDark_v0.22_Pro.apk`（901.7 KB / md5 `5e23fda6cf8feb7f84c44db2d90c6e00`；内嵌 `assets/index.html` 与仓库产物逐字节一致，md5 `1fbd6f7346df9eb2634afe8b16acb8ed`）

> v0.22 收口设置信息架构与数据读数：设置页重排为运动员 / 教练员 / 软件三组，新增环境、科学训练数据、计划导入导出三个 hub；修复组策略库无法滚动、首页顶栏截断、动作页控件不等高；JTS 页直接显示评估输入；动作页改为「组策略 + 目标疲劳度」双框；新增周期目标评估卡与分类周容量表，并修正周容量未乘组数的问题。

## 发布验证

```
python tools/gate.py --static → 27 PASS / 0 FAIL
python tools/gate.py → 35 PASS / 0 FAIL / exit 0（静态 27 + 动态 8）
node tools/v3v.js → 232 PASS / 0 FAIL
node tools/v2v.js → 47 PASS / 0 FAIL
node tools/uiv.js → 147 PASS / 0 FAIL
node tools/xlsxv.js → 145 PASS / 0 FAIL
node tools/logicv.js → 58 PASS / 0 FAIL
python tools/test_plan_xlsx.py → 117 PASS / 0 FAIL（六表契约 T1–T8）
plan_xlsx 导出往返 → 9052 格 → 9052 格 / 差异 0 / error 0
```

## 真机状态（emulator-5554 / 1080x2400 / 420dpi）

- 已验：`install -r` 升级成功，`dumpsys package` 回读 `versionCode=25 / versionName=0.22`；WebView 实际渲染正常；系统保存面板（`ACTION_CREATE_DOCUMENT`）被真实唤起 —— 这条是 §7「无头全绿不等于真机能用」点到的原生层
- 已验：旧存档无 `schemaVer` 时**不静默落到空账本**，停在只读并给出导出/复制/重试三条出口（§2 红线 4 在真机成立）
- **未验**：首屏正常态、设置页三组 IA、导入导出 E2E 真点、版本徽章目视。模拟器上留有一份无 `schemaVer` 的旧测试账本（84766 字符，已导出留档），要跑干净首屏必须 `pm clear`，本次按用户决定**不执行**，故 v0.22 记为「成品已出、真机首屏未验收」

---

# ExDark Pro · v0.21

**发布日期**：2026-11-03
**前序版本**：v0.20（versionCode 23 → 24）
**成品**：`release/RPL_ExDark_v0.21_Pro.apk`（896.8 KB，md5 `7e883f1fdc349fe379dfd1db94183f64`，内嵌 index.html md5 `7cc949aea887769e658cd6125b85b336`，`BUILD_FP v=0.21.24 tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=468758ef`）

> **小修小补**的一版，不加功能。三件事：① **产品标签统一为 Pro**——`ProMax` 退役，新成品一律 `RPL_ExDark_v{X.XX}_Pro.apk`，交换契约里的产品名与界面文案同步（`v3v.js` 的 A5 / N2 盯着「可见文案无 ProMax」）；② **启动图标**换成杠铃一侧 1 枚大红片 + 1 枚大蓝片（25 + 20kg，传统竞赛配片），片上不标数字，`gen_icon.py` 是唯一出处；③ **仓库形状瘦身并钉成守卫**——参考书只留 seed 真引用的 18 本（磁盘仍 96 本，其余本机留档）、`release/` 只跟踪最近 3 版成品、`data/00_索引/` 六份文档收成一份 `DATA_MAP.md`，并新增 **S27 仓库形状**（五条腿全读 git）与配套反向验证 `_sabotage_t1.py`。明细见 `CHANGELOG.md` [v0.21] 与 `mobile/README.md` §3.4 / §3.5 / §8。

## 发布验证

```
python tools/gate.py --static → 27 PASS / 0 FAIL（新增的一条是 S27 仓库形状，报 OK（顶层 7 项 / APK 2 版 / canon 18 条全部对齐 / 孤儿 0）；S23 平静态核对 106 处靶串 / 22 个脚本，新脚本 _sabotage_t1.py 的那 1 处一起进核）
python tools/gate.py          → 35 PASS / 0 FAIL（静态 27 + 动态 8：v3v 225/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 126/0）——**八套回归的条数与 v0.20 逐项相同**，这是「前端代码一行没动」的证据
python tools/build_html.py    → 成品 759.1 KB，BUILD_FP v=0.21.24 tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=468758ef；四项里只有 `exc` 变了（b3f24f0d → 468758ef），因为本版只改交换契约里的产品名 `app_name`（→ `RPL ExDark Pro`）——tpl / seed / sch 三项与 v0.20 逐字相同 = 模板、种子、六表契约都没动
python tools/pack.py          → 静态守卫 27/0 → 注入 v0.21/code 24 → assembleRelease → 发版门禁 35/0 → 写 release/RPL_ExDark_v0.21_Pro.apk（896.8 KB / md5 7e883f1f…，内嵌 index.html md5 7cc949ae… == 仓库产物，逐字节一致）
反向验证 _sabotage_t1.py      五组单注实测（每组后跑 --static，再 revert）：F2 造孤儿 **26/1 只红 S27 ③** · F3 复制 APK 顶过 3 版 **26/1 只红 ②** · F4 根目录加跟踪项 **26/1 只红 ①** · F5 `git add -f` 一本非 canon 书 **26/1 只红 ④** · F1 注释掉一条 `!` 重纳入 **25/2**（S27 ⑤ + S26 的「残留台账」——F1 是文本故障必须走台账，台账在就红，属正确连带）；合注（五处一起）**25/2**，detail 把五条腿的漂移一起报出来
复原核对                      revert 后 `--static` 回 **27 PASS / 0 FAIL**、`tools/` 无 `_sabotage_t1*.json` 残留、探针文件（孤儿 / 顶层条目 / 两份 extra APK）全部删净、`git status --porcelain` 行数复原到注入前的同一数值（索引没被探针污染）
图标核对                      `gen_icon.py` 重新生成 5 个密度 × 2 种形状 = 10 个 png；APK 里 10 个 `res/*.png` 与仓库这 10 个按「尺寸 + 调色板」逐一对上（AGP 会重压缩 PNG，所以字节 md5 不同属预期，不看 md5 看像素）；@xxxhdpi 数到红片 `#e2202e` 2698 px、蓝片 `#1a5fb4` 1891 px——红比蓝大，正是 25kg + 20kg 的一侧配片，片面无数字
真机验收                      本版改动**全是用户可见的**，装机请先点这四样：① 桌面 / 抽屉图标（一侧 1 枚大红片 + 1 枚大蓝片，无文字）；② 设置·关于页品牌串 `ExDark Pro`、版本徽章读 `v0.21`；③ 导出 JSON 交换信封里的 `app_name` 是 `RPL ExDark Pro`，导入旧文件仍能过契约闸门；④ 界面任何处都不出现 `ProMax`（v3v 的 A5 / N2 守着）。数据面本版零改动，账本与存档不需要 `pm clear`，但仍建议按老规矩先清一次再看首屏
```

---

# ExDark Pro · v0.20

**发布日期**：2026-11-03
**前序版本**：v0.19（versionCode 22 → 23）
**成品**：`release/RPL_ExDark_v0.20_ProMax.apk`（904.6 KB，md5 `7019c9c2a40915d2c90d2586484785d5`，内嵌 index.html md5 `60423dc91e9010552910e9cb67e36129`，`BUILD_FP v=0.20.23 tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=b3f24f0d`）

> **界面、功能、代码零改动**的一版，做的是**终验**：把 v0.11~v0.19 攒下的 21 家反向验证脚本逐组重新打一遍，确认每一家仍然咬得动自己的目标那条腿。「守卫还在、断言还在」不等于「注入还咬得动」——v0.17 就抓到过两家早已打空的反向验证，所以这件事只能每隔若干版重新做一次，而且必须在发版链的最后一次做。复跑抓到两处失真并已改掉：① `_sabotage_m4.py` 的 docstring 里那组「合注会红在哪些检查」记的是 S25/S26 上线之前测的数，实测已变；② 我自己差点把复跑跑成**静默空转**——注入家族有两种命令行形态（13 家 `inject [N]` / 8 家位置组号），对后一种发 `inject` 会 exit 1 打用法，而用法被重定向进 `/dev/null` 之后看起来就像「这一家已经不会红了」，其实是根本没打进靶子。这条坑现在写在 `mobile/README.md` §3.4 的通用跑法下面。明细见 `CHANGELOG.md` [v0.20] 与 `mobile/README.md` §3.4 / §8。

## 发布验证

```
python tools/gate.py --static → 26 PASS / 0 FAIL（判据数字与 v0.19 逐项相同，这是「模板/种子/契约/回归一套没动」的证据）
python tools/gate.py          → 34 PASS / 0 FAIL（静态 26 + 动态 8：v3v 225/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 126/0）
python tools/pack.py          → 静态守卫 26/0 → 注入 v0.20/code 23（成品 759.1 KB，BUILD_FP 除 v 一项外与 v0.19 逐字相同）→ assembleRelease → 发版门禁 34/0 → 写入 release/（内嵌 index.html md5 与仓库产物逐字节相同）
终验复跑（台账 13 家，注入态 --static 的红集，逐家实测）  a6 = S2/S3/S5/S7/S13/S23/S26（19/7）· b5 = S4/S5/S9/S24/S26（21/5）· m1 = S4/S5/S15/S17/S26 · m2 = S5/S14/S16/S17/S26 · m3 = S5/S7/S8/S17/S18/S26（20/6）· m4 = S5/S19/S21/S25/S26（F1 单注 22/4 = S5/S19/S21/S26，F4 单注 22/4 = S5/S19/S25/S26）· m5 = S5/S20/S21/S22/S26 · m6 = S5/S21/S26（23/3）· m7 = S5/S21/S22/S23/S26 · m8 = S5/S24/S26（23/3）· m9 = S5/S25/S26（23/3）· r1 与 b4 = 只红 S26（25/1）
终验复跑（positional 8 家，组 1）  a5/c1/c2/c3/c4/l1 = S5 + S23（24/2）· c5 = S5 + S14 + S23（23/3）· c6 = S16 + S26（24/2，靶在 Java，所以没有 S5 连带）——静态红不到前端逻辑的那几家逐家跑自己的回归：a5 → v3v 的 B3/B4/B7/J6/M13/N10 · c5 → v3v 223/3（A0/V3/Z1）· c2 → v3v 223/2（Q1/Q4）· c3 → v3v 224/1（U6）· c4 → xlsxv 144/1（W1d）· l1 → logicv 54/4（N7/P10/F3/F4）· c1 → xlsxv 23/2（Z0 + Z1「实到 24 应 145」，X4 段中途抛 BadZipFile 后其后断言不执行，这条同时是 Z1 漂移检测有效性的证据）· b4 → 契约 T 段六条红，还原回 117/0
复原核对  每一家跑完都 revert / build_html.py 复原并复跑 --static；终验结束时 26 PASS / 0 FAIL、tools/ 无 _sabotage_*.json 台账残留（S26 会在发版链第 1 步替你确认这件事）
为什么这一版值得单独发  反向验证是本仓唯一的「测试本身有效」证据。它自己也会腐：靶串被上游改写、命令行形态记错、输出被吞——三种腐法都不报错。这轮复跑花的是时间，买到的是「后面这十套守卫和八套回归现在还是真的」
真机验收        v0.11~v0.20 十个版本的自主推进到此结束，按既定决策交机主一次性人工体验。本版零代码改动，装机时顺带点这些历版累积项：版本号徽章读 0.20 / 三主题切换（含 Nature 纸底输入框）/ 图版学术配色与导出 / 面板入场动效与闪卡高亮 / 打完一组后的「本日全部完成」提示与短震 / 导入 CSV·xlsx·JSON 后各面板照常 / 设置·关于页品牌串为 `ExDark Pro`、版本行读 `v0.20`，界面任何处都不出现 `ProMax`（由 `v3v.js` A5/N2 守着）
```

---

# ExDark Pro · v0.19

**发布日期**：2026-11-03
**前序版本**：v0.18（versionCode 21 → 22）
**成品**：`release/RPL_ExDark_v0.19_ProMax.apk`（904.6 KB，md5 `23d1ce6acd8e7e011bd4ba0fc7e39721`，内嵌 index.html md5 `73cda2afa6af39a8613359ffe18d4557`，`BUILD_FP v=0.19.22 tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=b3f24f0d`）

> **界面与功能零改动**的一版（模板一行代码没动，成品只有版本号那一处变化）。用户可见的差异只有一句：以后发版时「装了新 APK 却读到上一版说明」「切语言后某一格永远不翻译」这两件事会被工具当场拦下，而不是等人事后发现。做的是两类**历版全靠人记得**的错：① 新增 **S25 i18n 挂载点可达**——翻译登记表里登记的每个节点 id 必须真在页面里存在、每项恰好两条词、不许重复登记；原先 `applyI18n` 写的是 `if(el)`，节点没了就静默跳过，切到 English 只有那一格还是中文，不报错也不掉格。② 新增 **S26 发版预检**——`tools/` 里残留任何注入台账（= 源码此刻就是故障原文）直接拦下发版，且根 README / `mobile/README.md` §1 / `CHANGELOG.md` 头条 / 本文头条四处版本号必须跟 `build.gradle` 相等；v0.17 就犯过后者：APK 出了、CHANGELOG 写了，只有本文头条还停在上一版，当时没有任何检查会红。③ **S23 补掉最后一个盲区**：故障表是运行时现算的那个家族现在要自己交出靶串（`--s23-dump`）才能被核对，取不出即 FAIL，「动态构造未能核对」那一栏从此消失。明细见 `CHANGELOG.md` [v0.19] 与 `mobile/README.md` §3.4 / §3.5 / §5 第 13 条 / §8。

## 发布验证

```
python tools/gate.py --static → 26 PASS / 0 FAIL（S25 报「154 项登记 / 挂载点全部在位 / 词对完整」；S26 报版本与 code 加「指针 4 处齐」；S23 报「核对 105 处靶串 / 21 个脚本；动态现算核对 _sabotage_m3.py（3 处）」——v0.18 那版这里还是「94 处 / 19 个脚本 + 动态构造未能核对」）
python tools/gate.py          → 34 PASS / 0 FAIL（静态 26 + 动态 8：v3v 225/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 126/0）——八套回归的条数与结论一套没动，这正是「本版没碰前端」的证据
python tools/pack.py          → 静态守卫 26/0 → 注入 v0.19/code 22（成品 759.1 KB，BUILD_FP 除 v 一项外与 v0.18 逐字相同：tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=b3f24f0d）→ assembleRelease → 发版门禁 34/0 → 写入 release/（内嵌 index.html md5 与仓库产物逐字节相同）
反向验证（新）  _sabotage_m9.py 四组（S25）：F1 登记表 id 打错 / F2 少一条词 / F3 同一个 id 登记两次 / F4 登记表改名 —— 单注都只红 S25 这一条目标腿，四条报错信息各不相同；不重建直接跑会另红 S5（模板改了成品没跟上）与 S26（台账在 = 不许发版），两条连带都是正确行为。合注只看得见 F4 那条：登记表没了，其余三条腿无从下手
              _sabotage_r1.py 五组（S26）：F1 根 README 身份行退回上一版 / F2 CHANGELOG 头条写成还没发的版本 / F3 本文头条落后一版（v0.17 真实犯过的错）/ F4 §1 身份卡只改 versionName 不改 versionCode / F5 造一份假台账 —— 五组单注各自只红 S26 一条（文档不是被检产物，所以这里没有 S5 连带）；revert 逐字节放回四处原文并删探针，复原后无台账残留
              S23 的新腿不能做成故障表的一行：脚本自己的台账一在旁边，S23 就跳过它。实测做法是手工删掉 _sabotage_m3.py 的 --s23-dump 分派 → 只红 S23（「退出码 1（现算不出靶串）」），放回即全绿
              新守卫上线当版就抓到两件事  ① S23 用 --s23-dump 核对这一家时发现 _sabotage_r1.py 自己的靶串抄死了 v0.18 —— gradle 一 bump 四处全找不到，改成从 build.gradle 现读后「脚本已腐」这条腿当场消失；② S26 在 pack 第 1 步拦下「根 README 身份行还停在 v0.18」，改完才放行。这两件都是这一版要拦的那类错，只是在同一版本里第一次落到作者自己身上
为什么这两条守卫值钱  S25 拦的是「静默不翻译」：无头回归量几何与文本，量不到「这一格该换成英文却还是中文」；S26 拦的是发版那一刻的时间差——四处指针各写各的时候，读说明的人和装 APK 的人对不上号，而产物本身完全正常，所以门禁全绿
真机验收        按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）；本版零 UI 零原生改动，列入统一体验时的点验清单：切 English 后设置页/各面板标题是否处处都翻（S25 新守的那张表）、导入旧版 CSV / xlsx / JSON 后各面板照常
```

---

# ExDark Pro · v0.18

**发布日期**：2026-11-03
**前序版本**：v0.17（versionCode 20 → 21；v0.17 那期未单独成文，明细见 `CHANGELOG.md` [v0.17]）
**成品**：`release/RPL_ExDark_v0.18_ProMax.apk`（904.6 KB，md5 `c138e98a237ba1032472b9afd077b1b8`，内嵌 index.html md5 `915a65d5f63edb39420aa4c8fd8092b6`，`BUILD_FP v=0.18.21 tpl=79b268cc seed=b88b0483 sch=4a3e5ae8 exc=b3f24f0d`）

> **界面与功能零改动**的一版，用户可见的差异只有一句：以后往种子里加一个键，不会再出现「改了三处里的两处、开屏才炸」。做的是两笔内部债：① `seed.json` 的顶层键名单原先手抄在 `gate.py` / `plan_xlsx.py` / `gen_seed.py` 三处，现在只写在契约 `schema/RPL-Plan-v1.json` 的新 `seed` 段里，四个读者都从它取，`gen_seed.py` 落盘前还会自检「产出的键与名单齐不齐」，不齐就**拒绝写文件**；② 文档分层——注入家族那份上百行的逐组命令清单是各脚本 docstring 的第二份手抄，现在本文只留「通用跑法 + 全家名单 + 四条跨切规矩」，逐组详情交还给脚本自己。新增守卫 **S24（种子顶层键名单单源）**，静态守卫 23→24 项。明细见 `CHANGELOG.md` [v0.18] 与 `mobile/README.md` §3.4 / §3.5 / §4 / §8。

## 发布验证

```
python tools/gate.py --static → 24 PASS / 0 FAIL（S24 报「名单 9 键 / 不变量 6 键 / 读者 4 处 / 产物键序 profile,structure,proto…」；S23 报「核对 94 处靶串 / 19 个脚本」）
python tools/gate.py          → 32 PASS / 0 FAIL（静态 24 + 动态 8：v3v 225/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 126/0）
python tools/pack.py          → 静态守卫 24/0 → 注入 v0.18/code 21（成品 759.1 KB，BUILD_FP 的 sch 摘要随契约新增 seed 段变为 4a3e5ae8）→ assembleRelease → 发版门禁 32/0 → 写入 release/（内嵌 index.html md5 与仓库产物逐字节相同）
反向验证（新）  _sabotage_m8.py 四组单注实测：F1 gate 自己复活一份手抄名单 / F2 plan_xlsx 退回手抄六键 / F4 gen_seed 的自检改成手抄名单 —— 三组各 23 PASS / 1 FAIL（只红 S24）；F3 契约名单改得比产物少一键 → 22/2（S24 + S5，契约进 BUILD_FP 指纹属预期连带），且注入态下再跑 gen_seed.py 确实拒落盘并报「seed 顶层键与契约名单不符：多 strategyLib」。revert + build_html.py 后回到 24/0，无台账残留
为什么这条守卫值钱  模板按名引用一个不存在的顶层键，静态与回归都是绿的（它们读的是已经生成好的产物），失败要等到用户开屏那一刻变成「undefined is not a function」。名单只留一份 + 生产者落盘前自检，把这个故障从「开屏炸」前移到「构建时拒写」
真机验收        按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）；本版零 UI 零原生改动，列入统一体验时的点验清单：导入旧版 CSV / xlsx / JSON 后各面板照常、种子缺失时的报错文案是否可读（这条走的是新加的闸门）
```

---

# ExDark Pro · v0.16

**发布日期**：2026-11-03
**前序版本**：v0.15（versionCode 18 → 19）
**成品**：`release/RPL_ExDark_v0.16_ProMax.apk`（904.8 KB，md5 `9fec4b7e5bbae3fb438d192395cd7bc9`，内嵌 index.html md5 `d35edb739d28161ec7ccc3bf2f8f8bbc`，`BUILD_FP v=0.16.19 tpl=614c1aab seed=b88b0483 sch=1be0e825 exc=b3f24f0d`）

> 本版是**手感上的改动**：面板不再「啪」地一下出现（底栏抽屉上滑、中段面板缩放落位、遮罩淡入），打完一组/勾完一个动作/快速载入后**刚改的那张卡会亮一圈再退**，当天所有动作打完弹一次「✓ 本日全部完成」并短震，编辑器里 Enter 一路从载荷走到备注、在备注按 Enter 直接保存收面板；系统的「减少动效」开关现在真的能一处关掉全站动效。**关闭不做动画**（连点不等待）。底层做的是「动效时长只写一处」：6 个 `--dur-*` / `--ease-*` 令牌替掉原先散在 13 处规则里的 `.1s`/`.15s`/`.2s`/`.3s`，没引用的 `--ease-pop` 删掉。明细见 `CHANGELOG.md` [v0.16] 与 `mobile/README.md` §3.5 / §6 / §8。

## 发布验证

```
python tools/gate.py --static → 21 PASS / 0 FAIL（S21 报「6 个 --dur-*/--ease-* 令牌 / 17 条 transition·animation 声明 / 6 条 @keyframes」）
python tools/gate.py          → 29 PASS / 0 FAIL（静态 21 + 动态 8：v3v 225/0（Z1 实到 213 应 213）· v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 126/0）
python tools/pack.py          → 静态守卫 21/0 → 注入 v0.16/code 19（成品 761.2 KB / 8289 行，模板 8288 行，BUILD_FP v=0.16.19 tpl=614c1aab seed=b88b0483 sch=1be0e825 exc=b3f24f0d）→ assembleRelease → 发版门禁 29/0 → 写入 release/（内嵌 index.html md5 与仓库产物逐字节相同）
反向验证（新）  _sabotage_m6.py 六组（本轮复跑实测）：F1 入场时长写死 .3s / F2 令牌改名而引用不动 / F3 删掉减动兜底 / F4 兜底复制成两处 / F5 动画名打错 —— 前五组 inject N → build_html.py → --static 均为 20 PASS / 1 FAIL（只红 S21，详情逐条报出写死时长、双向令牌差集、缺兜底、兜底 2 处、panel-in 无定义 + panel-inx 没人引用）；F6 只改成品**且不重建**为 19/2（S21 + S5，S5 精确指出第 35,144 字符起 `.5s var(--ease` ≠ `var(--dur-base`）；revert + 重建后 21/0、成品 md5 与注入前逐字节相同（d35edb73…）、台账文件消失
S21/M 段的必要性 动效不像颜色有最终态可查：无头回归量的是动画落地后的矩形，写死一处时长在 S21 之前不红任何一套断言，只让手感静默散开。动效的可断言面因此定成非几何三项（令牌落地 / 面板取到的 animationName+duration / 闪卡期间宽度恒定）+ 时序（完成提示第一次弹、重复不弹、撤销后再弹）
新增回归面      v3v 新增 Y 段 10 条（EXP_N 203→213）：四入口都闪卡、焦点链顺序、链上 id 与 DOM 双向对账、关着的面板里 input 拿不到焦点（证明量的是可达性不是恒真）、空账本不报「完成」；uiv 新增 M 段 10 条（116→126），M 段是全量遍历里唯一真动账本的段，段首取样、段末逐字节回装，所以 K1/K2 的零副作用对账照旧成立
目视核对        25 张 docs/shots（新增 25-daycomplete：六格全勾 + 100% + 完成提示 + 计时条 + 绿色高亮环），CONSOLE 无报错、AUDIT over 为空（small 命中一个 6px 的 <i>，本版 diff 未动过任何字号）
```

**真机验收**：按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）。本版零原生层改动（`enterkeyhints` 与 `haptic` 走的是既有桥与既有 WebView 行为），列入机主统一真机体验时的点验清单：入场动画在真 WebView 上顺不顺、震动是否真到、系统「减少动效」开与关两档的观感、备注按 Enter 的软键盘行为（这一类只有真机点得到）、软键盘弹起时焦点链会不会被顶掉。

---

# ExDark Pro · v0.15

**发布日期**：2026-11-03
**前序版本**：v0.14（versionCode 17 → 18）
**成品**：`release/RPL_ExDark_v0.15_ProMax.apk`（902.4 KB，md5 `76e28785ea6f03099ffcc77ae754db37`，内嵌 index.html md5 `8b2cf5d9567775e37ab2fb03659709a5`，`BUILD_FP v=0.15.18 tpl=68a12594 seed=b88b0483 sch=1be0e825 exc=b3f24f0d`）

> 本版是**看得见的改动**：设置页新增「数据图版（学术风）」，把账本画成四张能读的信——**Fig.1 主项 e1RM 趋势**（三条线，缺周就断节，不插值骗人）、**Fig.2 周训练量堆叠**（看加载周与减量周）、**Fig.3 主项 RPE 箱线图**（Tukey：Q1/中位/Q3 + 1.5×IQR 须 + 空心圈离群）、**Fig.4 依从性热图**（周×星期，「没安排」与「安排了没做」两种底纹）。每张卡自带 `n=`、画法口径与双语说明；三档主题各有一套图色；无数据出逐图空态。图版**只读**：不写盘、不新增存储键。本版同时吸收了 `data/` 的分区与改名（工作簿迁到 `data/01_工作簿/`，旧原件留备份、没有删），计划库因此多了「出处」一条，卡片只显示文件名、完整路径放在提示里。明细见 `CHANGELOG.md` [v0.15] 与 `mobile/README.md` §3.5 / §8。

## 发布验证

```
python tools/gate.py --static → 20 PASS / 0 FAIL（S20 报「22 个 .fx-* 类 / 9 个 --fig-* 令牌」）
python tools/gate.py          → 28 PASS / 0 FAIL（静态 20 + 动态 8：v3v 215/0（Z1 实到 203 应 203）· v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 116/0）
python tools/pack.py          → 静态守卫 20/0 → 注入 v0.15/code 18（成品 755.9 KB / 8206 行，模板 8205 行，BUILD_FP v=0.15.18 tpl=68a12594 seed=b88b0483 sch=1be0e825 exc=b3f24f0d）→ assembleRelease → 发版门禁 28/0 → 写入 release/（902.4 KB，内嵌 index.html md5 与仓库产物逐字节相同）
反向验证（新）  _sabotage_m5.py 六组：改模板的五组走 inject N → build_html.py → --static，各自**只红 S20**（19 PASS / 1 FAIL）；改生成物那组（成品里 .fx-med 指错令牌）**不许先重建**，否则被覆盖，实测 18/2（S20 + S5）；六处合注 + 重建 19/1（区域标记改名让「取不到被检对象」这条腿先红）；revert + 重建后成品 md5 与注入前逐字节相同（8b2cf5d9…）
X7b 的必要性    把辅助项图例键 'ohp' 改成 'oohp'：S20 全绿（拼接后的类名静态查不动），只有 v3v X7b 报「无定义键 oohp」
反向验证（旧）  _sabotage_m4 四组逐条隔离各 18 PASS / 2 FAIL（S19 + S5）· _sabotage_a6 五处合注 15/5（S2/S3/S5/S7/S13）· _sabotage_m3 单组各只红 S18 / S8、三处合注 15/5，各自 revert 回 20/0 —— 加了 S20 之后老断言没变钝
本轮修的工具缺陷 _sabotage_m3.py 的 F2 原先抄死种子工作簿名（改名后静默失效数月），改为从 gen_seed.py 现读；inject 改为先逐条验靶再动手，杜绝「已改盘、未写台账」的半注入残留
数据侧吸收      data/ 分区（00_索引 / 01_工作簿 / 02_参考资料 / 03_规范 / 04_生成物 / 05_归档）与工作簿改名在本版内一并收口，旧原件留在 data/05_归档/04_工作簿备份/（**没有删**）；种子 seed= 由 992462be 变到 b88b0483，schema 摘要由 11de312f 变到 1be0e825
数据变更撞出的 UI 缺陷 计划库新增出处字段后，出处胶囊把面板横向顶宽 31~123px（四档宽度全红，uiv P 段几何判据抓的）→ 改为只显示文件名 + title 留全路径 + max-width/省略号兜底；修完 uiv 116/0、gate 28/0
目视核对        24 张 docs/shots（新增 5 张：图版暗色 / 亮色 / 纸墨 + 滚动到 Fig.4 + 计划库在出处路径下的排布），三主题下折线与箱体均可读，CONSOLE 无报错、AUDIT 无横向溢出
重包说明        pack.py 全链通过两次：首包之后 data/ 侧并发改动落进同一条链（成品比 APK 新 2 秒），按机主「立即接管、把 data 收成 v0.15 的一部分」的指示重跑生成链与打包，最终内嵌产物与仓库产物 md5 一致
```

**真机验收**：按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）。本版零原生层改动（只在 Web 层新增面板与 SVG），列入机主统一真机体验时的点验清单：图版面入口/滚动/关闭收口、纸墨档下四张图的对比度、横屏与窄屏不溢出。

---

# ExDark Pro · v0.14

**发布日期**：2026-11-03
**前序版本**：v0.13（versionCode 16 → 17）
**成品**：`release/RPL_ExDark_v0.14_ProMax.apk`（892.2 KB，md5 `f6d50c179d0d8b28e2e3113d4ffecf8f`，内嵌 index.html md5 `7ac1667641eda1e4da679fb68e14c20a`，`BUILD_FP v=0.14.17 tpl=447d0f00 seed=6103cd29 sch=8f85b78c exc=b3f24f0d`）

> 本版是**看得见的改动**：新增第三套主题 **「❦ 纸墨」（Nature，低饱和学术风）**——暖纸底 + 墨色正文，设置页「外观」从两宫格变三宫格（☾ 暗色 / ☀ 亮色 / ❦ 纸墨），状态栏与首屏跟随主题、无闪。两套旧主题的颜色取值**逐字节未动**，看起来和 v0.13 一样。底层做的是「别再靠人记住有几处要改」：主题名单、明暗归类、每档底色只写一处，加第四套主题**只需补一份颜色令牌块，不必新增 CSS 规则、不必改判断分支**。明细见 `CHANGELOG.md` [v0.14] 与 `mobile/README.md` §3.5 / §8。

## 发布验证

```
python tools/gate.py --static → 19 PASS / 0 FAIL
python tools/gate.py          → 27 PASS / 0 FAIL（静态 19 + 动态 8：v3v 194/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 109/0）
python tools/pack.py          → 静态守卫 19/0 → 注入 v0.14/code 17 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 27/0 → 写入 release/
反向验证（新）  _sabotage_m4.py 四组逐条隔离，各 17 PASS / 2 FAIL（S19 + S5）：F1 亮底规则写回 [data-theme=light]、F2 Nature 令牌块少一键、F3 注册表多一个没落地的主题名、F4 主题按钮文案 span 改名；
               动态侧把故障 build 进成品后 F1→W4（三档 data-mode 开关全部失效）· F2→W3 · F3→W1+W2+W3+W5+W9 与 uiv X3+X3c · F4→W9；revert 后重建的成品 md5 与注入前逐字节相同
反向验证（旧）  _sabotage_a6 14/5 · _sabotage_m3 单组各 18/1 · 三处合注 14/5，各自 revert 回 19/0 —— 加了 S19 之后，老断言没变钝
S19 的必要性    注入前的实测里，「CSS 里多写一条 [data-theme=light] 规则」不会让任何一套静态或动态回归变红，只会静默表现为第三个主题颜色不对
目视核对        19 张 docs/shots（含 Nature 主屏 / 设置三宫格滑块在第 3 位 / 浏览抽屉 / 切回暗色），CONSOLE 无报错、AUDIT 无横向溢出
```

**真机验收**：按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）。本版触碰原生层的只有一处只读调用（`setChrome` 报状态栏颜色，`MainActivity.java` 零改动），列入机主统一真机体验时的点验清单：三档主题各切一次看状态栏、纸墨档下走一遍导入/导出、加载失败阻断层在纸底档的观感。

---

# ExDark Pro · v0.13

**发布日期**：2026-11-03
**前序版本**：v0.12（versionCode 15 → 16）
**成品**：`release/RPL_ExDark_v0.13_ProMax.apk`（889.6 KB，md5 `596124c633ea08a5aab2c8c8234dee18`，内嵌 index.html md5 `da4db226849bb093f008d6cedbc12a2e`，`BUILD_FP v=0.13.16 tpl=3eb46fbc seed=6103cd29 sch=8f85b78c exc=b3f24f0d`）

> **本版零功能、零 UI**——App 里能看到的唯一变化是「关于」的徽章变成 `v0.13 ProMax`。改的是这套系统靠什么不自欺：① PC 端项目（Excel ⇄ Web HUD）整体退役到 `archive/desktop/`，不入仓、不进依赖图、不再参与门禁（`data/*.xlsx` 权威源一张没删）；② 训练日志 **26 列协议的唯一出处**从「三端各存一份、改名靠人记」改成契约文件里的 `log_jsonl.record_keys_frozen`，单独改名或换序当场报**第几列**；③ 门禁新增 **S18 归档边界**——主线脚本的字面量里出现指向归档项目的路径就 FAIL，专防「只在本机绿」那种检查。明细见 `CHANGELOG.md` [v0.13] 与 `mobile/README.md` §3.5 / §8。

## 发布验证

```
python tools/gate.py --static → 18 PASS / 0 FAIL
python tools/gate.py          → 26 PASS / 0 FAIL（静态 18 + 动态 8：v3v 182/0 · v2v 47/0 · check_hud 320/360/390/412 · 契约 117/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 106/0）
python tools/pack.py          → 静态守卫 18/0 → 注入 v0.13/code 16 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 26/0 → 写入 release/（5/5 全过）
反向验证（新）  _sabotage_m3.py inject 1 → 只红 S18（17/1）；inject 2 → 只红 S8（17/1）；inject 3 → 红 S5/S7/S17（15/3）；三处合注 → 13/5；revert 后回 18/0、台账文件消失、git status 无幽灵改动
反向验证（旧）  _sabotage_a6 13/5 · _sabotage_m1 14/4 · _sabotage_m2 14/4，各自 revert 回 18/0 —— 退役两套之后，老断言没变钝
覆盖面得失      退役 D4/D5 = 失去 PC 端服务层 18 + 37 项（HUD 渲染 / 备份回写 / CSV 导入端点）；S7 与 S8 的第三端由 server.py 换成**发货成品**，主线三端（契约 / 模板 / 成品）逐列全等，覆盖面净增
归档两套仍可本机跑（archive/desktop/tests/ 实测 18/0 与 37/0），只是不再进主线判定
```

**真机验收**：按既定决策不逐版真机（v0.11~v0.20 连续推进，全部完成后由机主一次性人工体验）。本版无 UI 与原生层改动，真机点验清单与 v0.12 相同。

---

# ExDark Pro · v0.12

**发布日期**：2026-11-03
**前序版本**：v0.11（versionCode 14 → 15）
**成品**：`release/RPL_ExDark_v0.12_ProMax.apk`（889.3 KB，md5 `aa5cda8475eb2d02a768ab2fd2c491bd`，内嵌 index.html md5 `8df8a7f2af048eb6fa6bb2a5408812b7`，`BUILD_FP v=0.12.15 tpl=3eb46fbc seed=6103cd29 sch=8f85b78c exc=292e1ca3`）

> v0.12 把 v0.11 的「只导」补成**闭环**：JSON 计划可导可入——导入先过信封校验（键序 / 版本清单 / 载荷六表契约），通过后**整份替换并归档旧计划**，未知 `schemaVersion` 整份拒收且账本不动；新增**训练日志 JSONL**（首行 `META` 头 + 每行一条 26 列记录，**只导不入**），与 CSV 共读同一份 `unifiedRecords()`，两路不可能各自漂移（CSV 产物逐字节未变）。`plan_xlsx.py` 增 `logjsonl --check`（列名用正则从模板取，Python 侧只校验不复建）；原生 `chooserMimes()` 补 `.json → application/json`。明细见 `CHANGELOG.md` [v0.12] 与 `mobile/docs/JSON交换载体规范_RPL_Exchange_v1.md` §2–§3。

## 发布验证

```
python tools/gate.py   → 27 PASS / 0 FAIL（静态 17 + 动态 10：v3v 182/0 · v2v 47/0 · check_hud 320/360/390/412 · desktop 18/0 + 37/0 · 契约 114/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 145/0 · logicv 58/0 · uiv 106/0）
python tools/pack.py   → 静态守卫 17/0 → 注入 v0.12/code 15 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 27/0 → 写入 release/
python tools/_sabotage_m2.py inject → S14/S16/S17 变红（accept 去掉 .json / 选择器不映射 .json / 契约缺 import_policy），revert 后回到 17/0
跨语言互检          → xlsxv Y5（前端信封 → plan_xlsx.py json --check）+ Y9（前端 JSONL → plan_xlsx.py logjsonl --check）均 0 error
闭环演示（真产物）  → 导出 plan.json 253.9 KB / log.jsonl 627 行 → Python 读信封 6 表 0 error、读日志 626 条记录 → 改一格 target_rpe 7→7.5 后仍过契约 → App 导入 ok=true 且旧计划归档 → 未知版本 blocked=true 且账本逐字节不变 → 还原一致
```

**真机验收**：按既定决策不逐版真机。本版新增点全部复用已验收的 SAF 文档链（JSON 导入走 `<input accept>` + `FileReader`，日志导出走 `exportDoc`，与 xlsx 同一条落盘→选择器→流拷贝路径），`.json` 在选择器里可选、JSONL 导出落地两项列入机主统一真机体验时的点验清单。

---

# ExDark Pro · v0.11

**发布日期**：2026-11-03
**前序版本**：v0.10（versionCode 13 → 14）
**成品**：`release/RPL_ExDark_v0.11_ProMax.apk`（887.8 KB，md5 `de111998a290d34d307977818fa74047`，内嵌 index.html md5 `d3e9d227c5f33ce789ad9f45937cb855`，`BUILD_FP v=0.11.14 tpl=384a8ef4 seed=6103cd29 sch=8f85b78c exc=292e1ca3`）

> v0.11 是 **JSON 交换格式重构主线的第一版**：JSON 成为计划交换的唯一权威载体，xlsx/CSV 降级为视图/导出。新增交换载体契约 `tools/schema/RPL-Exchange-v1.json`（信封键序 / 接受版本 / 文件名模板 / MIME 的唯一出处，前端读注入的 `EXCHANGE_SCHEMA`，Python 读同一份文件）；设置页新增「JSON 计划（AI 交换）」导出（导出前契约自检、同时间戳逐字节确定）；原生新增通用文档桥 `exportDoc`；`plan_xlsx.py` 新增信封构建/校验与 CLI `json` 子命令（未知 `schemaVersion` 整份拒收）。本版只导不入，JSON 导入与日志 JSONL 落 v0.12。明细见 `CHANGELOG.md` [v0.11] 与 `mobile/docs/JSON交换载体规范_RPL_Exchange_v1.md`。

## 发布验证

```
python tools/gate.py   → 27 PASS / 0 FAIL（静态 17 + 动态 10：v3v 182/0 · v2v 47/0 · check_hud 320/360/390/412 · desktop 18/0 + 37/0 · 契约 102/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 138/0 · logicv 58/0 · uiv 106/0）
python tools/pack.py   → 静态守卫 17/0 → 注入 v0.11/code 14 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 27/0 → 写入 release/
python tools/_sabotage_m1.py inject → S4/S5/S15/S17 变红（模板缺占位符 / 契约缺 key_order / exportDoc 改名 / 指纹缺 exc=），revert 后回到 17/0
跨语言互检          → xlsxv Y5：前端页面产出的信封文本喂给 plan_xlsx.py json --check → 0 error / 0 warning
```

**真机验收**：按既定决策不逐版真机；`exportDoc` 走系统 `CREATE_DOCUMENT`（与已验收的 xlsx 导出同链），列入机主统一真机体验时的点验项。

---

# ExDark Pro · v0.10

**发布日期**：2026-11-03
**前序版本**：v0.09（versionCode 12 → 13）
**成品**：`release/RPL_ExDark_v0.10_ProMax.apk`（885.4 KB，md5 `f5861bb3b581c315df144902eab9a9c2`，内嵌 index.html md5 `44109930e1c4c58c650dd23f38df0924`，`BUILD_FP v=0.10.13 tpl=b56ffb11 seed=6103cd29 sch=8f85b78c`）

> v0.10 是**全量逻辑 + UI 测试发版**（按 v0.08 时的既定规划，保留版本号、不参与功能迭代）：App 行为与 v0.09 逐项相同，唯一可见变化是版本徽章。这一版交付的是两套会自己变红的回归——`logicv.js`（58 项，App 内全部纯逻辑函数对照独立参照系）与 `uiv.js`（106 项，14 面板 × 四档宽度几何遍历 + 零副作用对账）——以及它们首跑抓出并修掉的三处真实缺陷（JTS 字符串拼接失真、CSV 引号换行劈记录、mround 商溢出）。明细见 `CHANGELOG.md` [v0.10] 与 `mobile/README.md` §8。

## 发布验证

```
python tools/gate.py   → 26 PASS / 0 FAIL（静态 16 + 动态 10：v3v 182/0 · v2v 47/0 · check_hud 320/360/390/412 · desktop 18/0 + 37/0 · 契约 83/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 132/0 · logicv 58/0 · uiv 106/0）
python tools/pack.py   → 静态守卫 16/0 → 注入 v0.10/code 13 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 26/0 → 写入 release/
python tools/_sabotage_l1.py 1..7 → 七组故障各自变红（N7 / 只 N7 / J1+J2 / E1 / S3+S4 / C3+C5 / 只 A4），revert 后成品逐字节还原
```

**真机验收**：按本轮推进决策，v0.10~v0.19 不逐版真机；全部版本完成后由机主统一人工真机体验（v0.11~v0.20 涉及文件选择器/MIME 的改动点在 `docs` 遗留清单中逐个标注「待真机」）。

---

# ExDark Pro · v0.09

**发布日期**：2026-11-02
**前序版本**：v0.08（versionCode 11 → 12）
**成品**：`release/RPL_ExDark_v0.09_ProMax.apk`（883.1 KB，md5 `d44ed6df4f861aee243fe46007cc8d22`，内嵌 index.html md5 `c80659d0caf39dbabd35965dd2de5b23`）— 已在 API 37 模拟器 `pm clear` 后实装验收，见 §四

> Phase C 是**能用**的一版：v0.08 定的六表契约这次接到了界面上——设置页可以导出/导入 `.xlsx` 计划工作簿，被替换掉的旧计划进第四存储分片并可在「计划归档」里取回 / 删除 / 清空。验收过程中抓出一个只在真机上存在的缺陷（系统文件选择器把 `.xlsx` 整行置灰，导入永远选不出文件），已修复并新增守卫 S16 守住它。

## 一 · 用户可感知

| 场景 | v0.08 | v0.09 |
|---|---|---|
| 计划怎么进出这台设备 | 只有 PC 端命令行（`tools/plan_xlsx.py`） | 设置页「计划工作簿（六表）」导出 / 导入两钮：导出走 SAF 落到用户选的位置，导入经契约闸门后整份装载 |
| 导入一份不合规的计划 | 不存在这条路径 | **整份拒收**，`planErrBox` 逐条回显 `[Sheet!Row3.column] 原因`，账本与当前计划一字不动 |
| 换了新计划，旧计划去哪 | App 里无处可放（只有 `inactiveWeeks` 冻结名单） | 装载前自动进「计划归档」（新→旧顶替，上限 8 条 / 单片 512 KB / 单份 320 KB），面板可**取回 / 删除 / 清空** |
| 取回一条归档 | — | 与文件导入同一条链（`adoptImportedPlan`），落点与存档当场原文逐字节相同（`xlsxv` W3 断言）；取回前复检契约，非法档拦下 |
| 界面 | 与 v0.07 逐像素相同 | 只多设置页两行入口 + 归档面板；其余与 v0.08 相同 |
| 版本徽章 / 成品指纹 | `v0.08`，`BUILD_FP v=0.08.11 tpl=eff5aa4d …` | `v0.09 · 2026-11-02`，`BUILD_FP v=0.09.12 tpl=88524fef seed=6103cd29 sch=8f85b78c` |

## 二 · 工程机制

Phase C 六步，每步都带自己的反向验证（「守卫真的会红」）：

- **C1 App 内 xlsx 引擎**（模板 +582 行）：`planFromXlsxBytes` / `xlsxBytesFromPlan` 做 xlsx 字节 ⇄ 六表字典，列序、键名、错误格式全部取自成品里的 `const PLAN_SCHEMA`（段内不许出现第二份列名）。读侧逐点对齐 `plan_xlsx.book_to_plan`（空行剔除、缺 `r` 顺延、`t="str"/"b"/"d"`、内建 numFmtId 14 与自定义 numFmt、注释里的假标签、富文本分段、绝对/相对 rel Target），写侧 Stored + 固定 1980-01-01 时间戳使同一份计划两次导出逐字节相同。跨工具对账**真抓出两个缺陷**：zip 中央目录尺寸把 EOCD 自己的 12 字节算进去（openpyxl 报 `BadZipFile`，App 自读却正常）、表头错误串少一个「列」字
- **C2 结构写入唯一入口**：`applyStructure(raw)` 是成品里 `state.structure` 的唯一赋值点（`totalWeeks` 只从 ΣBlocks 求、`daysPerWeek` 只从 `len(dayDefs)` 求、`version` 只从契约取），五个入口全部改走它；D4 落到 App：`recomputeInactive()` 登记 `inactiveWeeks`、`activeWeekKeys()` 让导出只写未冻结的周，否则「导出→导入」会把已缩短的计划又撑回 16 周。删掉三处硬编码 16
- **C3 第四存储分片 `roast_plan_archive.json`**：JS 侧 `LS_BY_KIND`/`BRIDGE_LOAD`/`BRIDGE_SAVE` 三张映射表 + Java 侧 `loadPlanArchive()`/`savePlanArchive()`，仍走 tmp→rename 原子写与 `lastStoreError` 可见路径；`archiveItemOk` 六表少一张就整份拒收；归档**不进 `state`、不进 `WORK_KEYS`**，读坏只降级成「空归档 + 可见告警」，绝不回写覆盖磁盘原文，`READONLY` 态一律不写
- **C4 契约校验与换算落到 App 侧**：`validatePlanDict`（判定逐条对齐 `plan_xlsx`，59 用例）+ `xStateToPlanDict` / `xPlanDictToState`；导入链固定为「读字节 → 契约闸门 → 旧计划进第四分片 → 种子底版装载 → 偏好保留 → 一次写盘」；`plan_xlsx.py` 拆出无闸门的 `_load_plan_state` 供对账用非法样本撞 D4 冻结 / 缺列兜底
- **C5 UI 接线**：设置页两钮 + `planXlsxFile` 隐藏选择 + `planErrBox` 回显（i18n 九键）、`adoptImportedPlan` 共用装载段、`archSheet` 归档面板与 `closeAllSheets` 收口、Java 桥 `exportPlanXlsx`（`REQ_EXPORT_XLSX=1003`，复用 `CREATE_DOCUMENT` 流拷贝链）
- **C6 守卫与发版**：`gate.py` 静态 13 → **16**（S14 UI 接线成对 / S15 直呼 `AndroidBridge` 桥名对 Java 点名 / S16 选择器按 `<input accept>` 推导 MIME），`v3v.js` 新增 Q/U/V 三段（`EXP_N` 162 → **170**，全量 **182**；V 段全走真 DOM click），`xlsxv.js` 37 → **132** 项；`_sabotage_c1…c6` 六套反向故障
- **本次唯一功能面修复（只在原生层）**：`onShowFileChooser` 过去把 SAF 的 MIME 过滤写死成三份 CSV 类型，DocumentsUI 于是把不在 `EXTRA_MIME_TYPES` 里的扩展名一律标 `enabled=false` —— `.xlsx` 在手机上整行是灰的，永远选不出来（ENTER 只会激活变暗的下一行，所以表象是「导入后报找不到 zip 目录结尾」）。改为 `chooserMimes(params)` 从 `params.getAcceptTypes()` 推导（`.csv` → 三种 text MIME、`.xlsx` → spreadsheetml、空则 `*/*`）。**为什么回归抓不到**：浏览器里 `input.click()` 不经过系统选择器，`xlsxv` 又是直接喂字节 —— 这层过滤只有真机点得到，所以补 S16 静态点名；`_sabotage_c6.py` 三组（写死 `text/*` / 删 xlsx 映射 / 不读 accept）各自只红 S16

## 三 · 兼容性红线（逐条核过）

- ✅ `applicationId` / `namespace` = `com.roast.exdark`（守卫 S1）；权限仍只有 `VIBRATE`，无 `INTERNET`，`usesCleartextTraffic=false`（S2）
- ✅ CSV 26 列名称与列序不变，与 `desktop/server.py` 逐列相同（S7）；SEED 源工作簿 `data/RPL_ExDark_v0.03_ProMax.xlsx` 未改名、未被写过（S8 + 契约 T4）
- ✅ 存档向后兼容 `schemaVer ∈ {3,4,5,6}`、`SCHEMA_STAMP=6`（S10）；**四路分片是新增文件**，覆盖安装 v0.08 无需迁移，旧装升级后训练记录原样可读
- ✅ 归档不参与账本 CSV 导出、不被清账本带走（S12：`WORK_KEYS` 不许混进 `planArchive`，归档只走 `writeSlice('archive')`）
- ✅ 六表契约仍是单一事实源，App 内换算引擎不写第二份列名（`xlsxv` X7 按出现位置严查）
- ✅ 体积：成品 600.1 → **691.9 KB**（+91.8 KB，主要是引擎 + 换算 + 归档面板）；APK 852.4 → **883.1 KB**（+30.7 KB）

## 四 · 发布验证

```
python tools/gate.py            → 24 PASS / 0 FAIL（静态 16 + 动态 8：v3v 182/0 · v2v 47/0 · check_hud 320/360/390/412 · desktop 18/0 + 37/0 · 契约 83/0 · 往返 9052 格→9052 格 / 差异 0 / error 0 · xlsxv 132/0）
python tools/pack.py            → 静态守卫 16/0 → 注入 v0.09/code 12 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 24/0 → 写入 release/
python tools/plan_xlsx.py validate <手机导出的工作簿>   → 0 error / 0 warning（手机写的 xlsx 被 Python 侧原样读回）
python tools/_sabotage_c4.py 1..5 && node tools/xlsxv.js / node tools/v3v.js   → 五组分别红 W1d / W1+W1e / W1s（连带 W2/W2b）/ V3 / W0
python tools/_sabotage_c5.py 1..5 && python tools/gate.py --static && node tools/v3v.js   → 五组分别红 S14+A0/V3 / S14+V7 / 只有 V5（onclick 死代码，静态看不见）/ S14+V1 / 只有 S15（桥名漂移，v3v 全绿）
python tools/_sabotage_c6.py 1..3 && python tools/gate.py --static   → 三组各 15 PASS / 1 FAIL，只红 S16（Java 侧改动不在 S5 逐字节比对内，无连带红）
python tools/_sabotage_a6.py inject && python tools/gate.py --static  → 11 PASS / 5 FAIL（S2/S3/S5/S7/S13）→ revert 后 16/0，git status 无幽灵改动
```

**真机验收**（`Medium_Phone_API_37.0` 模拟器，API 37 / 1080×2400 @420dpi；release 包 `debuggable=false`，CDP 连不上，全程真实 tap + 截图）：

```
adb shell pm clear com.roast.exdark → adb install -r RPL_ExDark_v0.09_ProMax.apk → Success
versionCode=12  versionName=0.09
首屏 W1 · DAY A 六动作卡 + 配片条 + SET 胶囊 + DAY A–D / ARMOR dock 全渲染，无重叠无裁切
设置页「计划工作簿（六表）」两钮与「计划归档」入口在位；归档面板空态文案、✕ 与系统 BACK 键均正确收口
导出 → SAF 命名后落盘 456,968 B → 拉回仓库 `plan_xlsx.py validate` = 0 error / 0 warning
导入 → 修复前「找不到 zip 目录结尾（不是 xlsx？）」，根因是选择器把 .xlsx 灰掉；修复后可选，装载成功
归档 → 装载后自动生成条目（14:27 / 14:29 两条可见）；取回按顶替语义落位（14:30 + 14:29），当前计划随之切换且首页渲染一致
导出 CSV 的选择器回归照旧（.csv 仍可选，未因新增 xlsx 过滤而回退）
logcat：全程 0 条 REXJS / JS 异常
```

**升级安装**：直接 `install -r` 覆盖 v0.08 即可（新增的归档分片是独立文件，旧存档无需迁移）。要干净验收先 `adb shell pm clear com.roast.exdark`——注意这会清掉训练记录。

## 五 · 下一版

- **v0.10**：**全量逻辑测试 + 全量 UI 测试发版**（保留版本号，不参与功能迭代；含首帧时序、各面板在 320–412px 的排布、导入导出与归档的真机重复路径）
- **v0.11**：Phase D —— 阶段编排统一（方向稿见 `mobile/docs/阶段编排统一方向_RPL_Phase_v1.md`，§9 七件待裁决事项需先定）

---

# ExDark Pro · v0.08

**发布日期**：2026-11-02
**前序版本**：v0.07（versionCode 10 → 11）
**成品**：`release/RPL_ExDark_v0.08_ProMax.apk`（852.4 KB，md5 `4901c4da6c565c40f24be786704d735d`，内嵌 index.html md5 `3cc3d8b8dd10c81e8b01d14ec862d4f5`）— 已在 API 37 模拟器 `pm clear` 后实装验收，见 §四

> **零功能、零 UI**。Phase B 做的是「计划交换契约」：训练计划长什么样被定成一份机器可读的 JSON，Python 侧读写引擎、构建闸门、App 里的常量三处共读它。用户可见的唯一变化是版本号 `v0.08`；导入/导出入口在 v0.09（Phase C）接上。

## 一 · 用户可感知

| 场景 | v0.07 | v0.08 |
|---|---|---|
| App 界面 | 与 v0.06 同 | **与 v0.07 逐像素相同**（模板只多一行 `const PLAN_SCHEMA`） |
| 版本徽章 / 关于页 | `v0.07` | `v0.08 · 2026-11-02` |
| 「手上这份 APK 是哪一版模板 + 哪一版种子 + 哪一版契约」 | 靠回忆和文件时间 | 成品尾部 `<!-- BUILD_FP v=0.08.11 tpl=eff5aa4d seed=6103cd29 sch=8f85b78c-->`，三段哈希各自定位，改哪段变哪段 |
| 拿外部 AI 排一份计划再导进来 | 无规范可依，格式全靠猜 | `mobile/docs/计划交换规范_RPL_Plan_XLSX.md` §13 提示词模板 + §14 实测跑通的最小样例，可直接粘给任何 AI 产出合规六表 |
| 种子过期（改了 24 表工作簿忘了重跑） | `build_html.py` 照旧注入旧种子 | 注入前自动重跑 `gen_seed.py`（`--no-refresh` 下改为直接报错），且种子必须先过六表契约才允许进成品 |

## 二 · 工程机制

- **契约单一事实源 `tools/schema/RPL-Plan-v1.json`（决策 D7）**：六表（`Profile` 3 列长表 / 24 字段、`Blocks` 11、`Days` 10、`Workouts` 20 含 7 个派生列、`Telemetry` 14 可选、`Armor` 13 可选）的列名、受控枚举、区间、唯一键、错误格式 `[{sheet}!Row{row}.{column}] {reason}`、`row_idx` 几何（A9…F69，派生式 `first = 9 + 12*(n-1)`，A–D 与 `wkbook.DAYS` 逐值对账）、`conflict_policy`、4 条 `constraint_rules`、`state_defaults_on_import` 全在这一份里；Python 校验、`gate.py`、成品 `const PLAN_SCHEMA` 三处共读，不再各写一遍
- **交换层引擎 `tools/plan_xlsx.py`（1552 行）**：`.xlsx` ⇄ 六份 CSV ⇄ App state；子命令 `validate / build / export / roundtrip`；几何取自 `wkbook.py`、不 import `rxlib`（D8）；**不碰 `data/*.xlsx` 那 24 张权威源表**（规范 §0 硬边界 1，由 T4 断言源表 sha256 与 `data/` 目录不变）
- **冲突裁决（D10）**：`pct_1rm` 为权威，`load_kg = mround(anchor × pct, 2.5)` 无条件覆写；两者同时给出且偏差 > 5 kg 只进 warnings，仅两者都缺才 error
- **计划替换语义（D4）**：超出本次计划周数的既有周键**不删除**，登记到 `structure.inactiveWeeks` —— 归档 + 冻结
- **规范文档（620 行）**：逐列规格、受控枚举（24 训练模式 / 33 动作类别 / A–F 日 / 8 精力标签）、派生列与 `prog_rules`、`%` 与千分位写法、error/warning 分级、CLI；§13 是可直接粘贴的 AI 提示词模板（11 条硬规则 + 自检清单 + 验收命令），§14 是实测样例，附录 A 收录 240 个动作名按 33 组
- **契约测试 83 项 / 7 组**（`test_plan_xlsx.py`）：T1 全量 16 周逐格往返 · T2 最小四表 + `%1RM` 换算 · T3 坏输入电池（每条须恰好 1 个 error 且定位到 `[sheet!Row.列]`）· T3b 训练日安全约束 · T4 权威源表只读 · T5 六日 A–F + 几何对账 · T6 归档 + 冻结
- **`build_html.py` 从注入脚本变成闸门（144 → 244 行）**：种子陈旧自动重跑 → 契约不过不注入 → 注入 `const PLAN_SCHEMA` → 追加 `BUILD_FP` → 写盘后逐字节 / 无占位符 / 指纹恰好一条三条断言
- **守卫扩到七套**：`gate.py` 新增 D6（契约 83 项）与 D7（`seed → 工作簿 → state → 再工作簿` 逐格零差异，进程内跑）；S5 的失败详情由「差 0 字符」改成 **BUILD_FP 差异 + 首个不同字符偏移 + 该处上下文**——旧文案在长度相等时等于没报
- **反向故障注入**：`_sabotage_b4.py` 五处（含专打 `plan_weeks` 补齐的第 5 处）、`_sabotage_b5.py` 三处（删占位符 / 截断种子键名 / 替换目标写错），逐条验证新闸门真的会红，`revert` 后工作树逐字节还原
- **修掉一个真实缺陷**：`Profile.plan_weeks` 未填时沿用上一份计划的周数，导致 `build` 的产物被自家契约判 error（`plan_weeks=16 与 Blocks 周数之和 3 不符`）。契约补 `on_missing: "total_weeks"` + `_apply_on_missing()`，由 T2.17 / T2.18 守住

## 三 · 兼容性红线（逐条核过）

- ✅ `applicationId` / `namespace` = `com.roast.exdark`（守卫 S1）
- ✅ 权限仍只有 `VIBRATE`，无 `INTERNET`，`usesCleartextTraffic=false`（守卫 S2）
- ✅ CSV 26 列名称与列序不变，与 `desktop/server.py` 逐列相同（守卫 S7）
- ✅ SEED 源工作簿 `data/RPL_ExDark_v0.03_ProMax.xlsx` 未改名、未被写过（守卫 S8 + 契约测试 T4）
- ✅ 存档向后兼容 `schemaVer ∈ {3,4,5,6}`；`SCHEMA_STAMP=6` 严格大于白名单（守卫 S10）
- ✅ 六表交换层是**旁路**：不进 App 运行时逻辑，Phase C 才接上导入入口
- ✅ 体积：成品 586.4 → **600.1 KB**（+13.7 KB，其中契约 JSON 占 13.6 KB）；APK 848.0 → **852.4 KB**（+4.4 KB）

## 四 · 发布验证

```
python tools/gate.py            → 17 PASS / 0 FAIL（静态 10 + 动态 7：v3v 152/0 · v2v 47/0 · check_hud 320/360/390/412 · desktop 18/0 + 37/0 · 契约 83/0 · 往返 9052 格→9052 格 / 差异 0 / error 0）
python tools/plan_xlsx.py validate --seed            → 0 error / 0 warning
python tools/pack.py            → 静态守卫 → 注入 v0.08/code 11 → assembleRelease → 内嵌 index.html md5 一致 → 发版门禁 17/0 → 写入 release/
python tools/_sabotage_b4.py inject && python tools/test_plan_xlsx.py   → 五处故障逐条变红
python tools/_sabotage_b5.py inject && python tools/build_html.py       → 三处分别触发 S4/S5 红、契约闸门中止、marker 未替换中止
python tools/_sabotage_b5.py revert                  → git status 仅剩本次真实改动
```

**真机验收**（`Medium_Phone_API_37.0` 模拟器，API 37 / 1080×2400）：

```
adb shell pm clear com.roast.exdark     → Success（清掉 v0.06/code 9 的存档，验证首次安装路径）
adb install -r RPL_ExDark_v0.08_ProMax.apk → Success
versionCode=11  versionName=0.08
首屏：W1（11/02–11/08）· B1 肌肥大适应期 · DAY A 重型三项 100% · 六动作卡（高杠深蹲 92.5 / 中握卧推 57.5 /
      传统硬拉 87.5 / 挂片跪姿单腿弯举 15 …）+ 配片条 + SET 胶囊，W1–W9 周胶囊与 DAY A–D / ARMOR dock 全渲染，
      无重叠、无裁切
设置页：「关于 ExDark Pro · v0.08 · 纯本地离线运行 · 无联网权限」；关于弹窗 `v0.08 · 2026-11-02` + 六枚胶囊
logcat：无 JS 异常
```

> 注：release 包 `debuggable=false`，CDP 无法直连；契约与注入链的行为验证靠 `gate.py` 的 D6/D7 与两套 `_sabotage_b*`。
> 首帧时序（`swiftshader_indirect` 软渲染，真机会更快）：`am start` 后 t+2s 仅启动图、t+4s 只渲染到日头卡（动作卡与 dock 未到）、**t+6s 完整且此后稳定** —— 这是 WebView 首帧渐进，不是回归；全量 UI 时序测试留给 v0.10。

**升级安装**：直接 `install -r` 覆盖 v0.07 即可（存档无需迁移）。要干净验收先 `adb shell pm clear com.roast.exdark`——注意这会清掉训练记录。

## 五 · 下一版

- **v0.09**：Phase C —— App 内六表读写引擎（用成品里的 `const PLAN_SCHEMA`）、计划归档第四分片、设置页导入/导出入口、v3v N1–N12 行为断言
- **v0.10**：**全量逻辑 + UI 测试发版**（保留版本号，不参与功能迭代）

---

# ExDark Pro · v0.07

**发布日期**：2026-11-02
**前序版本**：v0.06（versionCode 9 → 10）
**成品**：`release/RPL_ExDark_v0.07_ProMax.apk`（848.0 KB，md5 `e53da2e1b22166850212b2ebabb600aa`，内嵌 index.html md5 `8550b35394f70550983e5edcc1a5e612`）— 已在 API 37 模拟器 `pm clear` 后实装验收，见 §四

> **零功能、零 UI**。这一版只修两件事：**数据不再静默丢**、**「全绿」不再等于「没坏」**，并把 README 里的红线变成会失败的检查。用户可见的唯一变化是版本徽章 `v0.07 · ProMax` 与「存档恢复失败」阻断层。

## 一 · 用户可感知

| 场景 | v0.06 | v0.07 |
|---|---|---|
| 存档读得出但装不回（文件损坏 / JSON 截断） | 静默落到默认空账本，训练记录被空账本覆盖 | 进入 `READONLY` 阻断层：导出原文 / 复制 / 重试 / 只读浏览，**任何写盘入口一律拒绝**，绝不拿空账本覆盖真实记录 |
| 原生写盘失败（磁盘满 / 权限） | 无声 | `AndroidBridge.lastStoreError()` 可见；写后 260ms 复查，失败回队重试 ≤3 次；POSIX 先改名再 `.bak` 兜底，不留半文件 |
| CSV 导入的自定义处方 | **每次冷启动**被迁移逻辑覆盖回处方值 | `SCHEMA_STAMP = 6` 闸门：迁移只在未盖章时跑一次，`migrateStateV6` 不再回写 `e.rx` |
| 旧字段 `v` 的存档 | 每次启动重迁移 | 读取兼容，迁移一次后盖章 |

## 二 · 工程机制

- **`tools/gate.py` 构建链守卫**：S1~S10 静态红线（`applicationId`、Manifest 无网络权限、`versionName` 纯版本号、模板无硬编码版本、**成品 == 重生成**、无残留 token、**CSV 26 列名称与列序两端逐列相同**、工作簿名三处同源、`seed.json` 键形状、`SCHEMA_STAMP` 严格大于旧 `sv` 白名单）+ D1~D5 五套回归，一条命令一个退出码；取不到被检对象一律算 FAIL
- **`tools/pack.py` 变成发版门禁**：第 1 步静态守卫 → 注入 → `assembleRelease` → APK 内嵌与仓库产物逐字节比对 → **写 `release/` 之前跑全量门禁**；`--skip-gate` 只为排查留，绕过须在 `mobile/README.md` §8 写理由
- **回归自身可证伪**：`v2v.js` 去掉无条件 `exit(0)`；新增 `A0`（API 点名，改名即红）、`Z0`（分段中断仍报结果）、`Z1`（断言总数闸门）；排掉 12 条「空集合恒真 / 缺节点即通过」的假绿断言；规模 v3v 137 → **152**、v2v 45 → **47**
- **反向故障注入**：`tools/_sabotage_a5.py`（4 组 9 处前端故障 → 逐条变红）、`tools/_sabotage_a6.py`（4 处红线故障 → S2/S3/S5/S7 变红且 `pack.py` 中止；台账逐字节还原，EOL 不变）
- **版本单源再收紧一档**：`v3v.js` 的 `EXP` 从 `app/build.gradle` 直读，发版只改 gradle 一处；`build_html.py` 修掉每轮必报的假 WARN，并对未替换 token 直接报错退出
- **瘦身（只移动，不删除）**：`shot2.js`、`jtsdiag.js`、`desktop/tools/fix_workbook_v0_01.py` + `w1_formula_diff.csv`、根 `docs/三系统使用说明.md` 移入 `archive/legacy/`，每件的理由与替代记在 `archive/legacy/README.md`

## 三 · 兼容性红线（逐条核过）

- ✅ `applicationId` / `namespace` = `com.roast.exdark`（守卫 S1）
- ✅ 权限仍只有 `VIBRATE`，无 `INTERNET`，`usesCleartextTraffic=false`（守卫 S2）
- ✅ CSV 26 列名称与列序不变，与 `desktop/server.py` 逐列相同（守卫 S7）
- ✅ SEED 源工作簿 `data/RPL_ExDark_v0.03_ProMax.xlsx` 未改名（守卫 S8）
- ✅ 存档向后兼容 `schemaVer ∈ {3,4,5,6}` 与旧字段 `v`；`SCHEMA_STAMP=6` 严格大于白名单（守卫 S10）
- ✅ 训练数据、周表坐标、动作库三级结构未动

## 四 · 发布验证

```
python tools/gate.py            → 15 PASS / 0 FAIL（v3v 152/0 · v2v 47/0 · check_hud 320/360/390/412 全 OK · desktop 18/0 + 37/0）
python tools/pack.py            → 静态守卫 → 注入 v0.07/code 10 → assembleRelease 13s → 内嵌 md5 一致 → 发版门禁 → 写入 release/
python tools/_sabotage_a6.py inject && python tools/gate.py --static   → S2/S3/S5/S7 FAIL，pack.py 第 1 步中止
python tools/_sabotage_a6.py revert                                   → git status 无残留
```

**真机验收**（`Medium_Phone_API_37.0` 模拟器，API 37 / 1080×2400）：

```
adb shell pm clear com.roast.exdark     → Success（清掉 v0.06 存档，验证首次安装路径）
adb install -r RPL_ExDark_v0.07_ProMax.apk → Success
versionCode=10  versionName=0.07
首屏：W1（11/02–11/08）· B1 肌肥大适应期 · DAY A 重型三项 · 6 动作卡片 + 配片预览 + SET 胶囊，
      DAY A–D / ARMOR 五格 dock 全渲染，无重叠、无裁切
设置页 → 关于：徽章 `v0.07 · ProMax`，数据链行「种子 RPL_ExDark_v0.03_ProMax.xlsx · 存档 schema v6」
```

> 注：release 包 `debuggable=false`，CDP 无法直连，A2 阻断路径（读得出却装不回）与 A3 盖章在真机上不可注入；这两条由 `v3v.js` 无头回归的 R1–R9 / S1–S3 轮次覆盖。

**升级安装**：直接 `install -r` 覆盖 v0.06 即可（存档会被一次性迁移并盖章）。要干净验收先 `adb shell pm clear com.roast.exdark`——注意这会清掉训练记录。

## 五 · 下一版

- **v0.08**：Phase B（按计划推进功能层）
- **v0.09**：Phase C
- **v0.10**：**全量逻辑 + UI 测试发版**（保留版本号，不参与功能迭代）

---

# ExDark Pro · v0.06

**发布日期**：2026-11-02
**前序版本**：v0.05（versionCode 8 → 9）
**成品**：`release/RPL_ExDark_v0.06_ProMax.apk`（843.8 KB，内嵌 index.html md5 `b80bce8bc95a2f13fab8d220f1f08a6c`）

> 本轮按 Master Execution Prompt 全量执行 P0→P3：底层科学模型与两套资料库先落地，再做存储迁移与顶层视觉。文末 9 项待裁决开关缺失，一律采用正文推荐默认；其中 C2 要求 `jtsCalc` 同时返回线性 `raw` 与非线性 `crs/recMult`，v2v 45 项因此继续全绿。

---

## 一 · 科学引擎（P0）

### 1. GZCLP 模式枚举
旧 `SS / SL / T1.Def / T1.S2 / T2.S2 / T1.S3 / T2.S3` 统一迁移到标准命名：`T1.3x3 / T1.5x5 / T1.Def.1 / T1.Def.2 / T1.Def.3`，并新增 `T1.6x6`。模式选择器固定分组顺序（Top* → Mod → Def.1–3 → 3×3 → 5×5 → 6×6），T2/T3 首项固定为 `T2.Mod` / `T3.Mod`。

### 2. JTS 周级五模块
- `M_sleep = (max(sleep,1)/6)^0.45`
- `M_stress = 1 − 0.035 × max(0, stress − 4)`
- `M_readiness = 1 + 0.03 × (0.30×酸痛归一 + 0.25×健康 + 0.25×动力 + 0.20×意愿 − 5.5)`
- `B_armor = min(0.08, 副交感/灵活性打卡项-天 × 0.012)`
- `REC = clamp(M_sleep×M_stress×M_readiness + B_armor, 0.55, 1.25)`；`CRS = round(REC×82)`
- `Total_Multiplier = AGE × SEX × STR × REC × NUTR`（年龄 1.06/1.04/1.00/0.94/0.88；营养 减脂 0.88 / 增肌 1.06）

### 3. 跨模态有氧干扰
`D_lower = LISS×0.6 + HIIT×1.1 + max(0, 步数天数−5)×0.15`，上肢取 25%。MRV/MAV/MEV/MV 分别按 `D×1.0 / 0.8 / 0.5 / 0.3` 扣减，并强制 `MV < MEV < MAV < MRV`。

### 4. SRU 与五档状态
单组权重 `1 + 0.12×(RPE−7)`（RPE<5 记 0）；动作系数 硬拉/低杠深蹲 1.15、卧推/高杠/变式/T1 1.00、T2/T3 0.75；ARMOR 薄弱链打卡每次 +1.5 SRU。状态徽章改为 `低于 MV / 低于 MEV / 最佳适应区间 / 功能性超量 / 超载预警 · 建议降维器械`。SRU 只用于徽章，`setsOf()` 与卡片组数完全不动。

### 5. ARMOR 实时处方决策树
睡眠≤6 或压力≥7 → 呼吸与睡眠置顶并改写说明；深蹲/硬拉计划组数 ≥95% MRV 或酸痛≥7 → 插入「器械降维替代（高 SFR · 省 25% 神经疲劳）」；有氧扣减 ≥2.0 组时在免责声明里动态追加提示。

### 6. IPF GL 段位
青铜 0–45（9/星）、白银 45–60、黄金 60–75、钻石 75–90（3/星）、王者 90+（2/星），`calcGlRank` 输出星级、下一星差额与主题色；边界 44.99/45.00/89.99/90.00/98.00 全部断言。

---

## 二 · 数据资产与存储（P0/P1）

- `训练计划库-v2.xlsx` → 197 条计划 + 30 条字段规范；设置页计划库改为 197 卡可搜索、五维筛选、★ 收藏（`state.favProgs` 持久化），**无应用按钮**。
- `组策略体系-v2.xlsx` → 27 条策略 + 27×5 适用性矩阵 + 209 辅助动作；新增只读参考库（列表 / 矩阵双视图 + 按策略自动关联适配动作）。
- 动作可挂 `e.strategyId`（做组策略标签，不改组数），编辑器新增下拉与「查阅策略库」。
- 存档：`PREF_KEYS` 6 项、`profile.height/nutr` 新增；`migrateStateV6` 四路迁移（动作模式 / e1RM 账本 / 结构块预设 / JTS 日级键→周级键），boot 与 CSV 导入同步调用。

---

## 三 · 视觉与交互（P2）

- 顶栏：三段深烘色阶 `#brandIcon`、花体 `ExDark`（暗色 `#D49A6A` / 亮色 `#6E3B16`），去掉版本胶囊与 ☰，图标即设置入口；`ProMax` 全局收敛为 `Pro`。
- Poster：材质改 `--card-a/card-b/oled` 令牌；新增日卡/周卡切换，周卡吨位 = 各日吨位之和，空日不产生 `0/0` 行；`.p-list` 超出 260px 内部滚动。
- 动作页：赛扣零文字；2.5kg 改 `#181C22`（HSL 亮度 11.4%），≤1.25kg 五档中性灰（饱和度 3.1–5.8%）；计划组数标签 10.5px；模式徽章改用展示名。
- Profile：新增 GL 段位主视觉（勋章 + 星级 + 距下一星差额）与 1RM / 档案 / 趋势三 Tab；档案收纳性别/装备/年龄/身高/体重/营养；「无装」单行等高。
- 启动器图标：去咖啡豆与裂纹，改为对称纯杠铃，与顶栏徽标零引用。

---

## 四 · 验证

| 套件 | 结果 |
|---|---|
| `v3v.js` | **137 PASS / 0 FAIL** |
| `v2v.js` | 45 PASS / 0 FAIL |
| `check_hud.js` | 320/360/390/412 四档 gap=8px、3 按钮、花体零裁切 |
| `desktop/test_backend.py` | 18 PASS / 0 FAIL |
| `desktop/test_v0_01_features.py` | 37 PASS / 0 FAIL |
| Gradle | `--offline assembleRelease` BUILD SUCCESSFUL |
| APK | versionName 0.06 / versionCode 9；内嵌 index.html 与仓库产物逐字节一致 |

---

# ExDark Pro · v0.05

**发布日期**：2026-11-02
**前序版本**：v0.04（versionCode 7 → 8）

> 按 `roast_powerlifting.md` 第四章三项决策执行：JTS 周组数**只展示与推荐、不做同步**；计划页与 Profile 两处趋势图**同款 STATUS 仪表**；本轮**全量四阶段**落地。v0.05 不是小修小补，而是把 16 项痛点一次性收口。

---

## 一 · 交互与观感

### 1. 设置页语言 / 主题切换器
旧版 `.seg.mini` 只有 9px 字号、6px 内边距，热区小、选中态靠一层浅底，切换常被误触。现改为 **Tactile Segmented Pill**：
- 34px 高、142px 宽，整块可点；`--safe` 之外的金属渐层 + 内阴影 + 滑块位移（`translateX(100%)`）
- 深/亮色各有一套材质，选中文字走 `--ink`，不再靠红框强调
- 同值切换短路（`setLang` / `setTheme` 开头 `return`），不再触发二次整页重绘

### 2. 品牌识别
- 顶栏 `RPL` 文字块 → **深烘焙咖啡豆 + 杠铃** 内嵌 SVG（`#brandIcon`，48×48 视图）
- 顶栏品牌名统一 **ExDark Pro**；About / 设置页关于 / 页脚 / 文档标题 / 启动器 `app_name` 全部同源
- `tools/gen_icon.py` 重写为与 `#brandIcon` 同坐标同色的绘制（豆 -16° 旋转、杆 / 套筒 / 金牌同尺寸），mdpi–xxxhdpi 方形与圆形图标全部重出

### 3. 计划页与 Profile 趋势图
两处统一为 **STATUS 面板**（`.status-panel`）：16 周单元格矩阵、`current` 描边、`hi` 金色峰值、页脚 `SPAN` + LED，右侧固定 `ExDark Pro` 落款。BW 与 e1RM 各一份，替换原折线图。
顶栏 `📊` 升级为 **STATUS 仪表舱**（LED + `STATUS` + 副标）：未录遥测时为琥珀待机 `LOG`，已录则亮绿并显示 `8.0h` / `Rx`；BW 面板另加 16 周面积轨与当前周十字准星。

### 3.1 JTS 推荐口径（不联动）
周容量地标始终是**每周总组数**；单次推荐 = 周 MAV ÷ **本周该主项实际出现次数**。结构页每行现在同时显示 `本周主项 N 次 / 单次推荐 X 组 / 单次区间 A–B`，并在顶部列出 `年龄 · 性别 · 体重 · SBD/BW → 容量乘数`。**不提供同步按钮，卡片组数不会被自动改写。**

---

## 二 · 训练逻辑

### 4. JTS 周容量模型（对齐 `信息!D14:G25`）
- `VOL_MULT = M_age × M_sex × M_str × M_rec`
  - 年龄 `<25→1.05 / 25–34→1.00 / 35–44→0.92 / ≥45→0.84`
  - 性别 `女→1.12`；相对力量 `SBD/BW >5.5→0.90 / 4.5–5.5→0.95 / <4.5→1.00`
  - 恢复 `0.85–1.20`（6 维评分折算 + 营养：盈余 +0.10 / 减脂 −0.08，clamp）
- 周地标：深蹲 `6/9/14/19`、卧推 `8/12/18/24`、硬拉 `4/7/11/15`、上背核心 `8/12/18/24`，全部 `round(base × VOL_MULT)`
- 新增 **周容量审计**（计划组数 vs MV/MEV/MAV/MRV 区间）与 **单日推荐**（周地标 ÷ 本周该动作分布天数）
- Profile 新增**年龄**输入；`saveProfile` 写入 `state.profile.age`
- **恢复总分保持纯 6 维**：移除 v0.04 的 `+3 / −2 / −5` 年龄加分，年龄只进 `VOL_MULT`，避免与科学模型重复计算
- **只展示与推荐，不改训练日卡片组数**（`.rec-note` 明示）

### 5. 做组处方 HUD
`prescriptionOf(mode)` 统一翻译为「模式徽章 + 核心组次 + 退阶重量」：
- `AMRAP`（协议带 `+` 或 reps ≥ 12）/ `TOP+BACKOFF`（Top.Single = `1×1 + 1×4`，退阶 −10%）/ `AUTOREG`（RTS）/ `DELOAD`（`.DL`）/ 其余 `STRAIGHT SETS`
- 动作卡片与编辑器预览共用同一函数；删除重复的 `rx` 文本节点，`protoTag` 不再叠字
- 编辑器 `.tgt-row` 上方新增 `.rx-preview` 实时预览（切模式 / 改次数 / 改重量即时刷新）

### 6. 配片与杆重
- 片种 11 档（25 → 0.25kg），视觉宽度 `cw` 严格单调；**5kg = 4px，2.5kg = 2.5px（1.6 倍）**，2.5kg 及以下只画片体不排文字
- 杆重 7 档 `10/15/20/25/30/35/40kg`，设置页与编辑器双入口；`barKg()` 校验 `BAR_OPTIONS`
- `edPlateLbl` 与 `warmups()` 全部去写死，热身自适应（含自重动作）

### 7. SET 胶囊与 e1RM 账本
- 动作卡片 SET 区改为一体式胶囊 `[ − | SET 2/3 ⏱ | + ]`，满组点亮，点击 `⏱` 开休息计时
- `bumpSet` 每次变更都同步 `logT1MainE1rm`：满组写账、撤销满组自动清账，修掉「卡片显示完成但 e1RM 曲线没有记录」的幽灵账本
- 误触可 `−` 撤销；撤销不计入休息计时

---

## 三 · ARMOR 与国际化

### 8. ARMOR 与训练日 UI 解耦
- AUX 日隐藏 `.tele`，不渲染每日状态卡；`openTeleSheet / saveTele / copyPrevTele / saveJts` 在 AUX 日直接返回，**不读写 `wk().A`**
- 新增 **ARMOR 专属看板**（`#armorBoard`）：全周准备度均值、装甲达成率、最低关节分 + 四域进度条
- 10 项打卡数据（`AUX_I18N`）与 4 域全部双语；`row.intensity` 补渲染

### 9. 国际化清扫
16+ 处漏译全部补齐：设置开关 `开/关`、训练结构周期名与减载标记、Profile Δ 对比、CSV 报错、JTS 维度名与反向标记、AUX 全量字段、STATUS 面板标题与页脚。

---

## 四 · 工程与回归

- 存储层：`save()` 120ms 防抖 + `flushSave()`（`pagehide` / `visibilitychange`）+ 关键事务 `save(true)`；Android `StoreBridge` 改为单线程 latest-wins 原子写
- **三路分片**：`roast_prefs.json`（语言/主题/杆重/赛扣/计时/字段开关，<500 B）· `roast_lib_diff.json`（仅自定义动作增量，259 个标准动作永不入库）· `roast_workout.json`（profile/structure/weeks/jts/e1rmLog/aux）；旧 `roast_state.json` 首次启动自动迁移，切后台 `onPause` 强制刷盘
- **desktop/ 降级**：Excel ⇄ Web 同步链标记为「可选 · 冻结」，APK 为唯一事实源；代码与 xlsx 原样保留可回退
- 主题切换删除全页 `transition`（`body.theme-anim`），避免整页重绘顿挫
- 桌面端同步：11 档片与 `cw` 单调宽度、同源 SVG logo、`ExDark Pro` 标题
- 仓库清理：`desktop/backups`、`tests/_backups`、`_book.xlsx`、`__pycache__`、`mobile/app/build`、`mobile/.gradle`、过程截图 27 张；`.gitignore` 补 `.screenshots/`、`.workbuddy/`
- 回归：`v3v.js` 断言同步（新增 M1–M13：杆重 7 档 / 片宽 1.67 倍 / 处方徽章 / e1RM 账本 / ARMOR 解耦 / 分段器 / 三路分片 / STATUS 舱），版本常量 `EXP=0.05`

---
---

# RPL ExDark ProMax · v0.04

**发布日期**：2026-11-02
**前序版本**：v0.03
**回归测试**：171+ 项全绿 · 0 FAIL · 零破坏性变更

> 这是一次**修复集**版本。v0.03 能跑、能存、能计，但界面有几块是"看起来有 UI 但其实没 CSS"，ARMOR 处方页里中英混杂，配片微片宽度明显不够，SET 点错了只能等三击满格。v0.04 先把这些实打实的 bug 和体验断点修干净，再顺便把架构层的渲染路径和国际化白名单做了收束。

---

## 🎯 五大核心修复

### 1. 配片微片终于能看清了 · #146 / #2968

1.25~0.25kg 的微片（红/蓝/银金之外最小的四档）之前用 `.pv-chip small` 渲染，但 CSS 只定义了 `.pv-chip.micro` —— class 名对不上，导致宽度撑满和大片一样。修完：
- class 名统一用 `.micro`（PLATES 数据里早就有 `micro: true` 标志）
- 重量数字从裸文本改成 `<span>` 绝对定位到片顶 10px 处
- 微片造型是窄金属条 + 顶部微标，不再撑宽

### 2. SET 点错了怎么办？现在有撤销 · #2814

之前 `bumpSet(i)` 只能递增，点错后必须硬点三下填满再退。现在：
- `bumpSet(i, -1)` 递减；doneSets 从 1 退到 0 时自动 `done=false`
- 卡片 SET 按钮前新增红色 − 按钮（仅 doneSets>0 时显示，不会误触）
- 递减**不触发**休息计时器（只有完成正向才开始倒计时）

### 3. 杆重终于能配了 · #1814 / #2974

之前 `BAR_KG = 20` 硬写在常量里（IPF 标准）。现在：
- `barKg()` 读 `state.plateCfg.barKg`，可支持 10 / 15 / 20 / 25 / 30 / 35 / 40kg
- 配片余量提示 `≤25 / ≤20` 改为动态
- sleeve 标签从 `20KG` 改为实时 `XXKG`
- ⚠️ **UI 入口待加**：本次只做了逻辑层 + 存档迁移，settings sheet 里暂未暴露下拉框

### 4. 结构页"恢复驱动建议组数"终于有 UI 了 · DOM 存在 100% 但 CSS 为 0

之前 `#stRecSetsBox` 容器里能渲染 DOM（`.rec-head / .rec-meta / .rec-row / .rec-step`），但 grep 发现这些 class 一个 CSS 定义都没有。现在补齐全套 15 行样式：
- 灰底卡片容器 + 标题 + 区间说明
- 深蹲 / 卧推 / 硬拉三行，每行左边科学区间 + 模型推荐，右边 − 当前值 + 重置
- 人工覆盖值金色高亮

### 5. ARMOR 处方页不再中英混杂 · #2446

之前 `renderArmorRx()` 里 `rx-cost` 标签、head 标题、disclaimer 全是硬编码中文 `'负成本' / '高负荷' / '离线智能处方'`。现在：
- 全部替换成 `L()` 双语
- `ARMOR_CATALOG.why` 拆成 `whyZh / whyEn`
- FUEL / STATUS 下拉选项也拆成 `{v, zh, en}` 三字段
- JTS 口径说明也加了英文

---

## 🏗️ 架构层收束（v0.04 真正的"地基修补"）

| 改进 | 改动 | 收益 |
|---|---|---|
| **语言切换从全量变局部** | `setLang()` 不再调 `renderAll()`，只重渲染 header/telemetry/exercises/dock + 已打开的 sheet | 减少不必要的 DOM 重建，理论上 ≤100ms |
| **主题切换删冗余** | `setTheme()` 不再调 `renderSettings()`，只切 `data-theme` + 同步 toggle 开关 | 去掉 220ms `theme-anim` 期间一次多余渲染 |
| **ARMOR 视觉解耦** | dock AUX 按钮新增 `.aux` class，选中态青绿色渐变 (#00897B→#004D40)，与 DAY 主项红色渐变明显区分 | 一眼看出"这是 ARMOR 不是 DAY" |

## 📦 构建 & 回归

```
python tools/build_html.py     →  成功 · 372.8 KB
node tools/v3v.js             →  71 / 71 PASS
node tools/v2v.js             →  45 / 45 PASS
node tools/check_hud.js       →  4 / 4 PASS (320 / 360 / 390 / 412px)
python tests/test_backend.py  →  18 / 18 PASS
python tests/test_v0_01_...   →  37 / 37 PASS
```

## 🛡️ 零破坏性变更声明

- ✅ `schema_ver = 5` 不变，无迁移链新增
- ✅ CSV 26 列头不变
- ✅ `applicationId` / `namespace` 不变
- ✅ SEED 源文件 `RPL_ExDark_v0.03_ProMax.xlsx` 不变
- ✅ 旧存档向前兼容（`state.plateCfg` 缺 `barKg` 时默认 20）

## ⚠️ 发布前需要手动更新

以下步骤由发布负责人在打包 v0.04 APK 前执行：

```bash
# 1. 更新版本号（build.gradle 禁止硬编码 template 版本）
# mobile/app/build.gradle 里 versionName='0.04', versionCode=7

# 2. 更新 v3v.js 里的手动同步常量
# mobile/tools/v3v.js L80: const EXP='0.04'

# 3. 重新生成 seed（如果 xlsx 改了；本次 xlsx 未动，可跳过）
# python tools/gen_seed.py

# 4. 构建
cd mobile && python tools/pack.py
# → release/RPL_ExDark_v0.04_ProMax.apk

# 5. 安装前务必清旧存档
# adb shell pm clear com.roast.exdark
```

## 🗺️ 已知限制（明确列入 backlog，不阻塞本次发布）

| 条目 | 原因 | 预计版本 |
|---|---|---|
| 杆重配置无 UI 入口 | 只做了逻辑层 + 存档迁移 | v0.05 |
| JTS 周量 MEV/MRV | 本次只做了 confidence + 年龄修正，真正的周汇总 + 三大项区间联动需要更完整的 volume 模型 | v0.05+ |
| About / Poster / e1RM 未补深色系截图 | 本次没有改视觉表现，沿用 v0.03 截图 | — |
| header RPL 文本未换 app 图标 | 图标已升级为咖啡豆+杠铃，但 header 仍是纯文字 `<div class="logo">RPL</div>` | v0.04.1 / v0.05 |

## 🙏 致谢

v0.04 的 16+ 处修改全部来自同一个需求背景：**"UI 有，但体验断点太多；逻辑对，但不够专业；国际化白名单不完整"**。这个版本先把"地基"和"看得见的 bug"修掉，后续再做真正的 feature 升级。

---

**签名**：钱进 · AI 辅助构建 · 2026-11-02
**许可**：纯本地离线运行 · 零联网权限 · 零第三方依赖
