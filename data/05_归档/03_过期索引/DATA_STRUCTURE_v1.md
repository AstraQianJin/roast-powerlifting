# RPL Data 结构 v1 · 团队落地参考方案

> 版本：v1 · 2026-11-03（初稿 2026-11-02）
> 范围：`data/` 目录（本轮未修改 `mobile/`、`desktop/`、`release/`）
> 状态：数据层已重组；规范层为草案；代码接入作为下一阶段
> 配套：[DATA_MAP.md](./DATA_MAP.md) · [NAMING_CONVENTION.md](./NAMING_CONVENTION.md) · [REFERENCE_INDEX.md](./REFERENCE_INDEX.md) · [RPL_Data_v1.contract.json](../03_规范/RPL_Data_v1.contract.json)

---

## 0. 一页结论

这轮做了三件事：

1. **把 `data/Ref` 重组成 7 个分类目录**：重复文件归档、旧索引归档、文件名英文化、目录中文化。
2. **补了 33 份可分发资源**：4 份规则、17 份 OA 研究/综述、12 份免费计划模板；付费/版权内容只建元数据。
3. **建立了数据治理骨架**：`00_索引`（数据地图/命名/索引）、`03_规范`（数据契约草案）、`04_生成物`（manifest/checksums/迁移表/质量报告）、`05_归档`（重复/备份/过期）。

当前 `data/`：**139 个文件、573.1 MB**；其中 `02_参考资料` **96 个文件、481.6 MB**，机器清单 **93 条**（不含 3 份元数据 CSV）。d17 无水印纯净版资料包的 37 个文件与现有资产 sha256 完全一致，未重复导入。

**最重要的一条约束**：主工作簿 `01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx` 的 `W1–W16` 含公式，`gen_seed.py` 读的是公式缓存值；用 `openpyxl` 保存会清空缓存。因此**没有把元数据写进主工作簿**，而是放在 `00_索引/RPL_ExDark_v0.15_ProMax_META.md`。详见 §8.1。

---

## 1. 项目目的与 data 的角色

项目是**离线 Android 力量举（SBD）周期化训练记录系统**：Excel 是编辑/参考源，`gen_seed.py` 生成 `seed.json`，`build_html.py` 生成单文件 `index.html`，最终打进 APK。手机端只写本机四路分片，不回写 Excel。

因此 data 不只是「资料堆」，它要同时满足四种用途：

| 用途 | 需要的数据 | 当前承载 |
|---|---|---|
| 生成 App 的初始计划 | 画像、周期、16 周处方、动作库、协议、装甲 | 主工作簿 24 表 |
| App 内浏览/推荐 | 经典计划、组策略、辅助动作 | 两个参考库 xlsx |
| 团队学习/引用 | 规则、论文、模板、技术、营养、书籍 | `02_参考资料` |
| 可校验/可追溯 | ID、枚举、版本、哈希、许可、校验规则 | `03_规范` + `04_生成物` |

旧结构的问题不是「文件少」，而是**展示布局直接当数据源、同一事实多处重复、三套动作词汇互不连通、参考库没有稳定身份**。本方案先修底层，再谈扩展。

---

## 2. 本轮交付清单

### 2.1 目录重组

| 动作 | 结果 |
|---|---|
| `data/Ref` 拆分 | 按 7 个分类迁入 `02_参考资料` |
| 12 组字节完全相同的文件 | 每组保留 1 份，其余 12 份归档到 `05_归档/01_重复文件` |
| 旧索引/旧资源总览 | 归档到 `05_归档/02_旧索引` |
| 空目录 | 清理；`Ref` 已不存在 |
| 迁移记录 | `04_生成物/01_文件迁移表.csv`（76 行） |
| 重复记录 | `04_生成物/02_重复文件清单.csv`（24 行，含 canonical 标记） |

### 2.2 新增资源（33 份）

| 类别 | 数量 | 代表 |
|---|---|---|
| 规则与协会 | 4 | IPF 2026 v3、IPF 2026 变更说明、USPF 2025、CPU 2025 |
| 研究与综述 | 17 | 损伤、自动调节、减重、睡眠、蛋白质、深蹲/卧推/硬拉生物力学 |
| 免费计划模板 | 12 | TSA、Sheiko、Candito、5/3/1、Juggernaut、Bullmastiff、70s、GZCL P-Zero、Askold |

新增记录：`04_生成物/03_新增资源清单.csv`。
完整索引：`00_索引/REFERENCE_INDEX.md`；机器清单：`04_生成物/refs_manifest.json`。

### 2.3 参考库索引

| 文件 | 内容 |
|---|---|
| `02_参考资料/06_书籍与预览/BOOKS_METADATA.csv` | 20 本书：作者、年份、出版方、access_status、官方链接、本地文件 |
| `02_参考资料/04_技术与教练/COACHING_ARTICLES_INDEX.csv` | 15 条 JTS/RTS/SBS/BM/Calgary/Greg Nuckols/Lift Vault 文章/模板链接 |
| `02_参考资料/07_数据集与工具/DATASETS_AND_TOOLS.csv` | 12 条 OpenPowerlifting、Lift Vault、Boostcamp、IPF approved list 等 |

### 2.4 三个工作簿

| 工作簿 | 状态 | 本轮改动 |
|---|---|---|
| `01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx` | **未改动** | 仅备份；因公式缓存风险，不写 `00_META` |
| `01_工作簿/RPL_Program_Library_v0.15.xlsx` | 已优化 | 新增 `00_META`、`99_数据字典`，追加 12 个规范化辅助列 |
| `01_工作簿/RPL_Set_Strategy_v0.15.xlsx` | 已优化 | 新增 `00_META`、`99_数据字典`，追加 `strategy_id`/`matrix_id`/`aux_id` 等辅助列 |

备份：`05_归档/04_工作簿备份/*_pre_meta_2026-11-02.xlsx`。

---

## 3. 目标目录结构（当前已落地）

```
data/
├── 00_索引/
│   ├── DATA_STRUCTURE_v1.md          ← 本文件
│   ├── DATA_MAP.md                   ← 数据所有权矩阵
│   ├── NAMING_CONVENTION.md          ← 命名/ID 规范
│   ├── REFERENCE_INDEX.md            ← 参考资料人读索引
│   ├── ENTRY.json                    ← 机器可读目录契约
│   └── RPL_ExDark_v0.15_ProMax_META.md
├── 01_工作簿/
│   ├── RPL_ExDark_v0.15_ProMax.xlsx     ← 历史存档 + gen_seed 权威源
│   ├── RPL_Program_Library_v0.15.xlsx   ← 经典计划参考库（28 列）
│   └── RPL_Set_Strategy_v0.15.xlsx      ← 组策略参考库（3 sheet）
├── 02_参考资料/
│   ├── 01_规则与协会/                 (7)
│   ├── 02_研究与综述/                 (33)
│   ├── 03_计划与方法/
│   │   ├── 01_方法论与手册/           (8)
│   │   └── 02_具体计划与模板/         (31)
│   ├── 04_技术与教练/                 (10 + 1 索引)
│   ├── 05_营养与恢复/                 (1)
│   ├── 06_书籍与预览/                 (3 + 1 索引)
│   └── 07_数据集与工具/               (1 索引)
├── 03_规范/
│   ├── README.md
│   └── RPL_Data_v1.contract.json
├── 04_生成物/
│   ├── refs_manifest.json
│   ├── refs_index.csv
│   ├── checksums.sha256
│   ├── 01_文件迁移表.csv
│   ├── 02_重复文件清单.csv
│   ├── 03_新增资源清单.csv
│   ├── 04_数据质量报告.md
│   ├── 05_主工作簿数据字典.csv
│   ├── 06_无法下载与付费清单.csv
│   ├── 07_待补资源清单.csv
│   ├── 08_原始资料包映射.csv
│   └── 10_数据校验报告.md
├── 05_归档/
│   ├── 01_重复文件/
│   ├── 02_旧索引/
│   ├── 03_过期索引/
│   └── 04_工作簿备份/
└── README.md                          ← 一页入口（人读 + Agent 快速上手）
```

**三个工作簿为什么在 `01_工作簿/`**：让 `00→05` 编号连续，根目录只剩 `README.md`；`gen_seed.py` 的路径常量已同步为 `data/01_工作簿/<文件名>`，gate S8 仍能三处同源校验。

---

## 4. 命名与 ID（摘要）

完整规则见 [NAMING_CONVENTION.md](./NAMING_CONVENTION.md)。

- 目录：`NN_中文名`，如 `02_参考资料/02_研究与综述`。
- 文件：英文文件名，`YYYY_Author_Title_Journal_Language.ext` 或 `Family_Program_Level_Weeks.ext`。
- 语言后缀：`_EN` / `_ZH` / `_ZH-TW` / `_EN-ZH`。
- 稳定 ID：
  - 参考资料：`RPL-REF-0001`（已生成）
  - 动作：`EX-0001`（规划）
  - 模式：`MODE-T1.3x3`（规划）
  - 周期块：`BLK-B1`（规划）
  - 计划家族：`FAM-01`（已写入计划库第 17 列）
  - 策略：`STR-01`（已写入策略库第 10 列）
  - 辅助动作：`AUX-001`（已写入辅助库第 15 列）
  - 矩阵：`MAT-01`（已写入矩阵第 8 列）

**原则**：名字只用于显示；跨表连接一律用 ID；ID 永不复用。

---

## 5. 单一事实源与所有权

完整矩阵见 [DATA_MAP.md](./DATA_MAP.md)。

一句话版本：

- `信息` 只负责画像；`周期` 只负责块/阶段/RPE；`W1–W16` 只负责处方；`动作库/映射/协议` 只负责目录；`总览/追踪/Exe` 是派生，不回灌。
- `训练计划库` 是参考库，不自动执行；`组策略体系` 是参考库，当前与 `mode` 无引用。
- `02_参考资料` 只增不改；`04_生成物` 只由脚本生成；`05_归档` 只增不删。

---

## 6. 数据模型（契约草案）

完整字段见 [RPL_Data_v1.contract.json](../03_规范/RPL_Data_v1.contract.json)。核心表：

| 层 | 表 | 作用 | 关键字段 |
|---|---|---|---|
| L0 | `META` | 版本/来源/哈希/语言 | data_version、schema_version、source_hash |
| L1 | `ATHLETE_PROFILE` | 画像与 1RM 锚点 | sex、age、bw、sq/bp/dl 1RM、equip、bar_kg |
| L1 | `EXERCISE` | 动作主数据 | exercise_id、name_en/zh、equipment、pattern、fatigue、cues |
| L1 | `EXERCISE_ALIAS` | 别名/旧名/中英/拼写 | alias、exercise_id、language |
| L1 | `CATEGORY` | 分类树/多归属 | category_id、domain、parent、order |
| L1 | `MODE` | 做组模式 | sets、reps、last_reps、backoff、amrap、rpe_offset、progression_id |
| L1 | `PROGRESSION` | 可解析进阶规则 | condition、threshold、action、value、target_mode |
| L2 | `PHASE` | 周期块/阶段语义 | cycle_type、work/deload、base_rpe、rpe_step、tier_offsets、volume_strategy |
| L2 | `DAY` | 训练日模板 | day_id、weekday_offset、focus_tags、constraints |
| L2 | `PRESCRIPTION` | 唯一处方长表 | week、day、seq、exercise_id、mode_id、pct、load、sets、reps、target_rpe |
| L2 | `ARMOR` | 装甲项定义 | item_id、domain、target、intensity、default_days |
| L3 | `PROGRAM` | 计划参考库 | program_id、family_id、entity_type、level、duration、canonical_url、verification |
| L3 | `PROGRAM_REL` | 计划关系 | from/to、relation_type |
| L3 | `STRATEGY` | 组策略 | strategy_id、tier、applicable_lifts、params、mode_ids |
| L3 | `STRATEGY_MATRIX` | 适用性矩阵 | strategy_id、lift、verdict、condition |
| L3 | `AUX_EXERCISE` | 辅助动作库 | aux_id、exercise_id、lift、category、strategy_ids |
| L4 | `REF` | 参考资料 | asset_id、path、sha256、title、license、status |

**迁移映射**：

| 现有 | 目标 |
|---|---|
| `信息` | `ATHLETE_PROFILE` |
| `周期` + `BLOCK_PRESETS` | `PHASE` |
| `W1–W16` | `PRESCRIPTION`（长表） |
| `动作库` + `映射` | `EXERCISE` / `EXERCISE_ALIAS` / `CATEGORY` |
| `协议` | `MODE` + `PROGRESSION` |
| W 表 AUX 区 | `ARMOR` + `auxDays` |
| `训练计划库` | `PROGRAM` + `PROGRAM_REL` |
| `组策略体系` | `STRATEGY` + `STRATEGY_MATRIX` + `AUX_EXERCISE` |
| `02_参考资料` | `REF`（已生成） |

---

## 7. 参考资料体系

### 7.1 分类与数量

| 分类 | 文件数 | 说明 |
|---|---|---|
| 规则与协会 | 7 | IPF 2022/2024/2026、USPF 2025、CPU 2025 等 |
| 研究与综述 | 33 | OA 论文/系统综述、JTS 原理书、RTS 手册、Westside、Rippetoe |
| 计划与方法 | 39 | JTS 方法论、19 份具体计划/追踪表、12 份新模板 |
| 技术与教练 | 10 | SBS 三大项指南、JTS 诊断、RPE、变式详解 |
| 营养与恢复 | 1 | SBS 饮食设置指南 |
| 书籍与预览 | 3 | JTS 官方预览 |
| 数据集与工具 | 索引 | OpenPowerlifting、Lift Vault 等（链接为主） |

机器清单 `refs_manifest.json` 每条含：`asset_id / path / sha256 / size / title_zh / title_en / authors / year / type / language / license / redistributable / source_url / status / tags / summary_zh`。

### 7.2 许可策略

| 类型 | 处理 |
|---|---|
| 官方公开规则 | 下载全文；标 `official_public` |
| OA/CC 论文 | 下载全文（PDF 或 HTML）；标 `OA` / `CC BY` |
| 免费模板 | 下载 xlsx；标 `free_public`，`redistributable=false`（作者保留权利） |
| 付费书/课程 | 只建元数据 + 官方链接；不存全文 |
| 用户已有版权 PDF | 保留原文件；标 `user_provided_*`，不再分发 |
| 明确禁止复制 | 只建链接（如 WRPF） |

### 7.3 本轮无法下载/不应下载（详见 `04_生成物/06_无法下载与付费清单.csv`）

- **USPA 2025 规则 PDF**：官方站点下载多次超时/截断；保留 2024 全文 + 2025 链接。
- **USAPL 2026.2 规则**：页面为嵌入式 PDF 查看器，未取得直链。
- **WRPF 规则**：官方 PDF 明确禁止未授权复制。
- **Calgary Barbell 16/8 周模板**：Google Sheets 导出失败。
- **JTS 付费书**：Scientific Principles（完整版）、A Thoughtful Pursuit、Beginner's Guide、Juggernaut Method 2.0、JTS AI。
- **RTS Manual**：官方数字手册付费。
- **5/3/1 系列、Sheiko 书、Base Strength、Westside 书**：付费/已有版权文件，只建元数据。
- **OpenPowerlifting 全量 CSV**：体积大、更新频繁；只建链接，按需下载。

这些不是「遗漏」，是**有意为之的版权/稳定性边界**。需要全文时走官方购买或团队已有副本。

### 7.4 d17 无水印纯净版资料包（2026-11-03 核对）

来源：`C:\Users\Astra\Downloads\d17、AAA力量举资料计划（无水印纯净版）`

- 原始文件 **37 个、355.5 MB**，覆盖 JTS 模板/手册、RTS 手册/追踪表、SBS 三大项与旅程、Westside、计划致胜、531 魔改、动作变式、RPE 指南。
- 与 `data/02_参考资料` 现有资产 **37/37 sha256 完全一致**，**新增文件 0**；因此没有重复导入，也没有覆盖任何文件。
- 这 37 条资产已补：中文标题、中文摘要、`user_provided_copyright` / `user_provided_unknown` 许可、`source_bundle=d17_AAA_clean`、原始相对路径。
- 原路径 → Data 路径映射：`04_生成物/08_原始资料包映射.csv`。
- 结论：d17 包是现有资料的「干净来源备份」，不是新资料；它的价值在于**可追溯来源**和**补齐元数据**。

---

## 8. 三个工作簿的优化说明

### 8.1 主工作簿：为什么没有写 `00_META`

`W1–W16` 的 `LOAD` / `PROTOCOL` / `RPE` 是公式，`gen_seed.py` 用 `data_only=True` 读缓存值。`openpyxl` 保存会清空缓存，导致负荷变 0、协议为空。因此：

- **不修改主工作簿**；
- 元数据放 `00_索引/RPL_ExDark_v0.03_ProMax_META.md`；
- 数据字典放 `04_生成物/05_主工作簿数据字典.csv`；
- 备份放 `05_归档/04_工作簿备份/`。

如果未来必须写入：用 Excel/WPS 打开保存，或使用保留缓存值的工具；不要用 `openpyxl`。

### 8.2 训练计划库

新增：

- `00_META`：标题、角色、版本、`gen_seed` 读取列范围、已知问题、禁止项。
- `99_数据字典`：原 16 列 + 新增 12 列的字段定义。
- 第 17–28 列：`family_id`、`level`、`duration_min/max`、`freq_min/max`、`autoregulation_std`、`verification_std`、`canonical_status`、`license_status`、`language`、`last_verified`。

原 16 列不动；`gen_seed.py` 仍按列号读取。

### 8.3 组策略体系

新增：

- `00_META` / `99_数据字典`；
- `组策略总表` 第 10–12 列：`strategy_id`、`tier_std`、`mode_hint`；
- `动作适用性矩阵` 第 8–9 列：`matrix_id`、`condition_note`；
- `三大项辅助动作库` 第 15–17 列：`aux_id`、`exercise_id`、`canonical_status`。

原列顺序不动；`gen_seed.py` 仍按列号读取。

---

## 9. 校验与门禁

### 9.1 数据侧校验（本轮已落地基础版）

已落地 `03_规范/tools/validate_data.py`：只读检查契约、manifest、sha256、重复哈希、d17 映射、三个工作簿关键结构、许可与双语标题，输出 `04_生成物/10_数据校验报告.md`。本轮 **27 PASS / 0 FAIL**。

契约里另有 20 条语义规则（`RPL_Data_v1.contract.json → validation_rules`），将在规范表落地后接入。优先级最高的 10 条：

1. `PRESCRIPTION.exercise_id` 必须能在 `EXERCISE` 或 `EXERCISE_ALIAS` 找到。
2. `PRESCRIPTION.category_id/mode_id` 必须存在。
3. 主项 `load_kg = mround(anchor_1rm × pct_1rm, 2.5)`，偏差 ≤ 2.5kg；否则 `load_override=true`。
4. `week` 必须落在 `PHASE` 周数之和内；`(week, day, seq)` 唯一。
5. 每周/每日组数之和必须等于 `PHASE` 声明值。
6. 每个训练日恰好一个 `.Main` 主项（或显式 exception）。
7. 24 个 canonical mode 全覆盖；旧名必须映射到 canonical。
8. 每个 mode 有 progression 或显式 hold/test。
9. 每个 program/strategy 有 canonical 或明确 `unverified/missing`，不许编造。
10. 每条 REF 有 sha256、license、status；重复文件必须归档。

### 9.2 代码侧门禁（现有，保持不变）

```bash
cd mobile
python tools/gate.py --static
cd tools
node v3v.js
node v2v.js
node check_hud.js
python plan_xlsx.py validate --seed
```

**纯重构**追加一条：`旧 seed.json` vs `新 seed.json` 逐格 diff 必须为 0；非空即说明语义漂移。

### 9.3 本轮验收

- `refs_manifest.json` 可解析，93 条资产，sha256 全部可校验。
- `checksums.sha256` 与文件一一对应。
- `02_参考资料` 无字节完全相同的重复文件（重复已归档）。
- 三个工作簿可被 openpyxl 读取；主工作簿关键单元格 `W1 E9 = 92.5`、`F9 = 3×5+`、`H9 = 7` 未被破坏。
- 计划库/策略库原列顺序不变；新增列不与 `gen_seed.py` 读取范围冲突。

---

## 10. 分批落地计划

### P0 · 数据地基（本轮已完成）

- 目录重组、重复归档、命名规范、数据地图、参考资料索引、manifest/checksums。
- 三个工作簿：主工作簿保持原状；两个参考库加 META/字典/辅助列。
- 验收：§9.3。

### P1 · 规范层（下一轮，仍可只改 Data）

- 已落地 `03_规范/tools/validate_data.py`：27 项检查，覆盖契约、manifest、sha256、重复哈希、d17 映射、三个工作簿关键结构、许可与双语标题；本轮 **27 PASS / 0 FAIL**。
- 已补齐 `02_参考资料` 全部 93 条资产的中文摘要（缺失 0）；后续新增资源按同一模板补。
- 生成 `04_生成物/09_数据质量报告_v2.md`：按 ID、许可、语言、覆盖率统计。
- 建立 `04_生成物/07_待补资源清单.csv`：25 条 P1–P3 资源 backlog（规则/模板/研究/书籍/工具），按优先级逐条补。

### P2 · 语义层（需要改 `mobile/tools`，单独审批）

- `MODE` / `PROGRESSION` / `PHASE` 三表落地；`协议` 旧名在数据侧 canonical 化。
- `gen_seed.py` 改为「先读规范层，读不到回退旧表」；纯重构用 golden seed diff = 0。
- 解决负荷/百分比口径：以 `pct + anchor` 重算，旧绝对重量降级为 `load_override`。

### P3 · 处方层（需要改代码）

- `PRESCRIPTION` 长表成为唯一处方源；`W1–W16` 降级为视图。
- 校验组数、周数、每日主项、target RPE。
- 结构编辑器把 `baseRpe/rpeStep` 变成真输入。

### P4 · 展示/交互层（v0.10 之后）

- App 计划库/策略库从「只读浏览」升级为「可引用」。
- 参考资料只打包 manifest + 摘要，不打包 100MB PDF。
- 文档、截图、索引自动生成。

---

## 11. 维护 SOP

### 11.1 新增参考资料

1. 判定分类 → 按 [NAMING_CONVENTION.md](./NAMING_CONVENTION.md) 命名。
2. 先比 `sha256`；重复则归档，不覆盖。
3. 记录 `title_zh/title_en/authors/year/source_url/license`。
4. 重跑 manifest/checksums/index。
5. 若是付费/版权内容，只建元数据。

### 11.2 新增计划

1. 改 `01_工作簿/RPL_Program_Library_v0.15.xlsx` 的 `计划总库`；保留原 16 列顺序。
2. 补 `family_id/level/duration/freq/autoregulation/verification/canonical_status`。
3. 跑 `gen_seed.py` 前确认列读取范围；跑 `gate.py`。
4. 若是正式变体/别名，补 `PROGRAM_REL` 关系，不要只改 `条目类型`。

### 11.3 更新规则

1. 下载官方 PDF 或建链接元数据。
2. 记录版本、生效日期、语言、官方 URL。
3. 在 §7.3/`06_无法下载与付费清单.csv` 更新状态。
4. 若影响比赛合规，在 `REFERENCE_INDEX.md` 顶部加「规则变更」提示。

---

## 12. 风险与红线

### 12.1 高风险

- **主工作簿公式缓存**：任何 `openpyxl` 保存都会破坏 `gen_seed.py` 的读数；必须用 Excel/WPS 或保留缓存的工具。
- **固定坐标**：`W1–W16` 插入行/列会直接错位；`信息 D10–D16` 同理。
- **改名/移动 xlsx**：`gen_seed.py` 路径会断；本轮不改名。
- **付费内容**：不下载、不分发；只建元数据。

### 12.2 红线

- 不删任何 xlsx；`05_归档` 只增不删。
- 不改 `applicationId`；不手改 `index.html`；不改 App 日志 26 列 CSV。
- 不在 `04_生成物` 手改文件。
- 不用名字做跨表连接。
- 不把 100MB 级 PDF 打进 APK。

---

## 13. 附录

### A. 当前统计

| 指标 | 值 |
|---|---|
| `data/` 文件数 | 139 |
| `data/` 总大小 | 573.1 MB |
| `02_参考资料` 文件数 | 96 |
| `02_参考资料` 大小 | 481.6 MB |
| manifest 资产数 | 93 |
| 新增资源 | 33 |
| 重复文件归档 | 12 组 / 24 个副本 |
| 工作簿备份 | 3 |

### B. 参考资料类型/许可

- 类型：PDF 41、XLSX 27、HTML 13、DOCX 9、TXT 3。
- 许可：`user_provided_copyright` 27、`user_provided_unknown` 24、`OA` 20、`free_public` 12、`official_public` 7、`CC BY` 2、`metadata_only` 1。
- 93 条资产全部有中文摘要；d17 纯净版 37 条已建立原路径映射。

### C. 12 组重复文件（已归档）

1. IPF 2022 EN（两个文件名）
2. IPF 2024 ZH-TW（两个文件名）
3. USPA 2024 EN（两个文件名）
4. 12 周力量举计划（`02_` vs `04_`）
5. Barbell Medicine Powerbuilding I 样本（`02_` vs `04_`）
6. JTS Foundations（`02_训练手册` vs `02_训练科学原理`）
7. JTS Program Design Manual（`02_` vs `03_`）
8. PRS Beginner Guide（`02_` vs `04_`）
9. 2020 Squat vs Deadlift（`03_` vs `08_`）
10. JTS Thoughtful Pursuit Preview（`04_` vs `09_`）
11. JTS Beginner's Guide Preview（`04_` vs `09_`）
12. JTS Scientific Principles Preview（`04_` vs `09_`）

完整路径见 `04_生成物/02_重复文件清单.csv`。

### D. manifest 字段

```json
{
  "asset_id": "RPL-REF-0001",
  "path": "02_参考资料/01_规则与协会/IPF_Technical_Rules_Book_2026_v3_EN.pdf",
  "sha256": "...",
  "size_bytes": 7507335,
  "title_zh": "IPF 技术规则书 2026（2026-03-01 生效，v3）",
  "title_en": "IPF Technical Rule Book 2026 (Effective 01 March 2026, v3)",
  "authors": ["International Powerlifting Federation (IPF)"],
  "year": 2026,
  "type": "pdf",
  "language": "en",
  "license": "official_public",
  "redistributable": true,
  "source_url": "https://www.powerlifting.sport/rules/codes/info/technical-rules",
  "status": "source_checked",
  "tags": ["IPF", "rules", "competition"],
  "summary_zh": "..."
}
```

### E. 团队评审清单

- [ ] 三个 xlsx 的路径/列顺序是否保持不变（`gen_seed.py` 兼容）。
- [ ] 主工作簿 `W1 E9/F9/H9` 是否为 `92.5 / 3×5+ / 7`。
- [ ] `refs_manifest.json` 是否能被 JSON 解析，`checksums.sha256` 是否逐文件匹配。
- [ ] `02_参考资料` 是否还有字节重复文件。
- [ ] 付费/版权内容是否只保留元数据。
- [ ] 下一轮是否批准 P2 的 `gen_seed.py` 改动（需要改 `mobile/tools`）。
