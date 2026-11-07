# RPL 命名规范 v1

> 目标：让任何人只看文件名就知道「是什么、哪一年、谁做的、什么语言、什么版本」，并且跨平台可检索。
> 决策：**中文目录 + 英文文件名 + 双语元数据**。

---

## 1. 目录命名

格式：`NN_中文名`

- `NN` 两位数，按阅读顺序排列；新增目录插在合适的序号段，不重排已有编号。
- 中文名用简短名词，不使用空格、括号、书名号。
- 子目录同样用 `NN_中文名`，最多三层。

当前目录：

```
data/
├── 00_索引/
├── 02_参考资料/
│   ├── 01_规则与协会/
│   ├── 02_研究与综述/
│   ├── 03_计划与方法/
│   │   ├── 01_方法论与手册/
│   │   └── 02_具体计划与模板/
│   ├── 04_技术与教练/
│   ├── 05_营养与恢复/
│   ├── 06_书籍与预览/
│   └── 07_数据集与工具/
├── 03_规范/
├── 04_生成物/
└── 05_归档/
```

> 说明：`01_工作簿/` 暂不建立；三个权威 xlsx 仍在 `data/` 根目录，因为 `gen_seed.py` 使用固定路径。下一轮改代码后再迁入 `01_工作簿/`。

---

## 2. 文件命名

### 2.1 研究/规则类

推荐格式：

```
YYYY_Author_ShortTitle_JournalOrOrg_Language[_Version].ext
```

示例：

- `2025_Silverthorne_Applied_Sport_Science_of_Powerlifting_SportsMed_EN.html`
- `2024_Tung_Injuries_in_Weightlifting_and_Powerlifting_BMJSEM_EN.html`
- `2020_Tapering_and_Peaking_Maximal_Strength_SportsMedOpen_EN.pdf`
- `IPF_Technical_Rules_Book_2026_v3_EN.pdf`
- `USPF_Technical_Rules_2025_EN.pdf`

规则：

- 年份用四位；有 DOI/期刊时把期刊缩写放进去。
- 作者只写第一作者或机构；不要写全作者列表。
- 标题用英文，CamelCase 或下划线分隔；不要空格。
- 版本 `v1` / `v2` / `v3` 放倒数第二段。

### 2.2 计划/模板类

推荐格式：

```
Family_ProgramName_Level_Weeks[_Version].ext
```

示例：

- `TSA_Beginner_Program.xlsx`
- `Sheiko_Intermediate_Medium_Load.xlsx`
- `Wendler_531_for_Beginners.xlsx`
- `Juggernaut_Method_Base_Template.xlsx`
- `RTS_16Week_4Day_Accumulation_Tracker.xlsx`

规则：

- `Family` 是体系名（TSA/Sheiko/Wendler/Juggernaut/RTS/nSuns/GZCL/SBS）。
- `Level` 用 `Beginner` / `Intermediate` / `Advanced` / `All`.
- `Weeks` 用 `8Week` / `12Week` / `16Week`；不定长省略。
- 追踪表用 `Tracker` 结尾。

### 2.3 书籍/预览类

```
Author_BookTitle_ZH|EN[_Preview].ext
```

示例：

- `JTS_A_Thoughtful_Pursuit_of_Strength_Preview_EN.pdf`
- `Israetel_Scientific_Principles_of_Strength_Training_ZH.pdf`
- `Rippetoe_Starting_Strength_Basic_Barbell_Training_ZH.pdf`

### 2.4 索引/生成物

```
NN_名称.csv|json|md|sha256
```

示例：

- `refs_manifest.json`
- `refs_index.csv`
- `checksums.sha256`
- `01_文件迁移表.csv`
- `04_数据质量报告.md`

---

## 3. 语言后缀

| 后缀 | 含义 |
|---|---|
| `_EN` | 英文 |
| `_ZH` | 简体中文 |
| `_ZH-TW` | 繁体中文 |
| `_EN-ZH` | 英中对照/双语 |
| 无后缀 | 语言未知或混合 |

---

## 4. 稳定 ID

未来跨表连接一律用 ID，不用名字。

| 实体 | ID 格式 | 示例 | 当前状态 |
|---|---|---|---|
| 参考资料 | `RPL-REF-0001` | `RPL-REF-0001` | 已生成于 `refs_manifest.json` |
| 动作 | `EX-0001` | `EX-0001` | 规划中；当前动作库无 ID |
| 分类 | `CAT-S.Main` | `CAT-S.Main` | 沿用现有分类名 |
| 做组模式 | `MODE-T1.3x3` | `MODE-T1.3x3` | 规划中；当前用 `proto` 键 |
| 周期块 | `BLK-B1` | `BLK-B1` | 规划中 |
| 训练日 | `DAY-A` | `DAY-A` | 规划中 |
| 计划家族 | `FAM-01` | `FAM-01` | 已在计划库第 17 列 |
| 计划条目 | 沿用 `GZCL-001` | `GZCL-001` | 现有 ID 可用 |
| 策略 | `STR-01` | `STR-01` | 已在策略库第 10 列 |
| 辅助动作 | `AUX-001` | `AUX-001` | 已在辅助库第 15 列 |
| 矩阵行 | `MAT-01` | `MAT-01` | 已在矩阵第 8 列 |

规则：

- ID 一旦分配，永不复用；删除/合并只改状态，不回收 ID。
- ID 只含 ASCII 大写字母、数字、连字符、点号。
- 人的名字、中文名、别名放 `alias` 字段，不参与连接。

---

## 5. 禁止项

- 文件名含空格、中文括号、书名号、全角标点。
- 同名不同内容直接覆盖；必须先比 `sha256`。
- 用 `最终版`、`最新`、`修改版` 这类无版本语义的词。
- 用日期代替版本：`2026-11-02` 只放在元数据 `last_verified`，不放进文件名。
- 在 `04_生成物/` 里手改文件。

---

## 6. 历史例外（已清零）

三个工作簿在 v0.15 已完成规范化，不再有例外：

| 现名 | 说明 |
|---|---|
| `01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx` | 权威源；`v{项目版本}` 与 `build.gradle` 的 `versionName` 对齐 |
| `01_工作簿/RPL_Program_Library_v0.15.xlsx` | 计划参考库；库自身内容版本记在 `00_META.library_version` |
| `01_工作簿/RPL_Set_Strategy_v0.15.xlsx` | 组策略参考库；同上 |

> 发版时若要同步版本串，改 `build.gradle` 后同步这三个文件名 + `gen_seed.py` / `validate_data.py` 的路径常量；或改用「文件名不带版本、版本只记 `00_META.app_compat`」的方案。
