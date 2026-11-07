# RPL Data Map · `data/` 的唯一索引

> 只管 `data/` 这一层：谁是权威源、谁消费、什么能改、什么进 git。
> 项目级的红线与发版流程在 [`../../AGENTS.md`](../../AGENTS.md) §2 / [`../../mobile/README.md`](../../mobile/README.md) §5，这里不复制。
> 本目录原有的五份索引（`DATA_STRUCTURE_v1` / `NAMING_CONVENTION` / `REFERENCE_INDEX` / `ENTRY.json` / 主工作簿 META）已收进本文件，原件移入 `05_归档/03_过期索引/` 留档。
> **易变的数字一律写取法，不写值**——值抄进来那天就开始腐烂。

---

## 1. 目录职责与 git 边界

| 目录 | 职责 | 被代码消费 | 入仓策略 |
|---|---|---|---|
| `01_工作簿/` | 三个 xlsx：权威源 + 两份参考库 | **是**（`mobile/tools/gen_seed.py`） | 全部跟踪 |
| `00_索引/` | 本文件 | 否 | 跟踪（只此一份） |
| `03_规范/` | 数据层机器可读契约 + 校验脚本 | 否（`validate_data.py` 是独立探针） | 跟踪 |
| `04_生成物/` | manifest / 索引 CSV / checksums / 报告 | 否 | 跟踪，**禁止手改**（改源后重跑生成脚本） |
| `05_归档/` | 重复文件、旧索引、工作簿备份 | 否 | 旧索引与备份跟踪；`01_重复文件/` 不跟踪（本机留档，不删） |

**参考库不在 `data/` 里了（v0.31）**：原先的 `02_参考资料/` 整体搬到仓库根的 `ref/`，全部不入仓。
理由是它**从来不是种子链的输入**——`gen_seed.py` 只读 `01_工作簿/` 那三份表，书的唯一作用是
`programLib.canon` 的**出处对账**（人与 Agent 读得懂「这条规范出自哪本书」）。v0.21 的做法是
「96 本里只跟踪被引用的 18 本」，代价仍然没解决：仓背 53MB、git 历史背 481MB，而且那 18 本
在 App 运行时一次都不被读。**canon 字符串一个字符都没改**：它写的是书在自己库内的相对路径
（`02_参考资料/03_计划与方法/…`），库的基准目录从 `data/` 换成 `ref/` 之后它照样成立。

**出处名单的唯一出处仍然是数据本身，不是本文件**——名单 = `seed.json` 里 `programLib.items[*].canon`
中以 `02_参考资料/` 开头的那些路径（相对 `ref/`；其余 canon 是「→ 计划名」这种人读串，不对应文件）。取法与对账：

```bash
python - <<'PY'
import json, os, subprocess
d = json.load(open("mobile/tools/seed.json", encoding="utf-8"))
canon = {i["canon"] for i in d["programLib"]["items"]
         if isinstance(i.get("canon"), str) and i["canon"].startswith("02_")}
have = {c for c in canon if os.path.isfile(os.path.join("ref", c))}
out = subprocess.check_output(["git", "ls-files", "-z", "--", "ref"])
print("canon", len(canon), "磁盘有书", len(have), "断链", sorted(canon - have) or "-")
print("库里文件竟被跟踪", [p.decode() for p in out.split(b"\0") if p] or "-")
PY
```

`git ls-files` 默认会八进制转义非 ASCII 路径，**不带 `-z` 的对账一定假红**（S27 的判据照此写）。

两条硬约束（gate S27 盯，另盯「跟踪的 APK 不超过 3 版」与「孤儿为零」）：
canon 每条都要能在 `ref/` 下找到实体书（断链 = 出处失效）；`ref/` 下任何文件都不许被跟踪（库回来 = 重蹈 481MB）。

**换机 / 新 clone 必须单独搬库**：库不入仓，所以 `git clone` 出来的目录**没有 `ref/`**，
`gate.py --static` 会在 S27 的 ④ 上判红（报「参考库整个不在」）——这不是仓库坏了，是在提醒你补这一步：

```bash
cp -r <原机位>/Roast\ PowerLifting/ref <新仓>/ref     # 96 个文件 / 482MB
cd <新仓>/mobile && python tools/gate.py --static      # 补齐后回全绿
```

本机备份位在 `Desktop/RPL-backup/`（含恢复步骤与两个 bundle 的分工说明）；库的逐本 sha256 由
`data/04_生成物/refs_manifest.json` 记录，`validate_data.py` 会核对。

库内导读与评价入口：`ref/README.md`（`SOURCE_GUIDE.md` 为判断层文档，`ref/tools/ref_probe.py` 为库内只读探针——探针不是门禁）。

`data/` 下**既不跟踪也不 ignore** 的文件是孤儿（会被下一次 `git add -A` 悄悄拖进仓）；S27 判它为零。取法：

```bash
git ls-files --others --exclude-standard data | wc -l    # 期望 0
```

---

## 2. 事实所有权

| 事实 | 唯一主人 | 消费者 | 派生镜像（禁止回灌） |
|---|---|---|---|
| 运动员画像、1RM、目标、恢复、开始日期 | `01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx` → `信息` | `gen_seed.py`、App 设置页 | `总览`、`追踪`、`信息` 的日历时间线 |
| 周期块、阶段、T1/T2/TOP 百分比、RPE 基线 | 同上 → `周期`（`E`=T1%、`F`=T2%、`G`=RPE、`J`=TOP%，命名区域 `PERIOD_T1` / `PERIOD_T2` / `PERIOD_RPE` / `PERIOD_TOP`） | `gen_seed.py` | `信息` 的 W0–W16 时间线、`总览` |
| 内置 8 周 2 Block 模板处方（周/日/动作/负荷/组次） | 同上 → `W1`–`W8`（`W9`–`W16` 隐藏归档，仍在簿内，按「数据不可破」不删） | `gen_seed.py` | `Exe`、`总览` |
| 动作分类与动作组 | 同上 → `动作库` + `映射` | `gen_seed.py` → `seed.lib` | App 动作库页 |
| 做组模式与组次结构 | 同上 → `协议` | `gen_seed.py` → `seed.proto` | `W` 表的 `PROTOCOL` 列 |
| 装甲/恢复项定义与周打卡 | 同上 → `W1`–`W16` 的 AUX 区 | `gen_seed.py` → `seed.aux` | App 装甲页 |
| 经典计划与变体参考 | `01_工作簿/RPL_Program_Library_v0.15.xlsx` → `计划总库` | `gen_seed.py` → `seed.programLib` | App 计划库浏览页 |
| 组策略、适用性矩阵、辅助动作 | `01_工作簿/RPL_Set_Strategy_v0.15.xlsx` | `gen_seed.py` → `seed.strategyLib` | App 策略浏览页 |
| **读哪些单元格** | `mobile/tools/gen_seed.py` 的 range 调用 + `mobile/tools/wkbook.py`（W 行坐标单源） | — | 本文件不抄坐标，抄了就和代码分叉 |
| 资源主数据（全量、机器可读） | `04_生成物/refs_manifest.json` | 人读时导成表 | `04_生成物/refs_index.csv` |
| 交换契约（六表 / 日志 / 信封） | `mobile/tools/schema/RPL-Plan-v1.json`、`RPL-Exchange-v1.json` | App 成品 + Python 两侧共读 | 任何第二份列名手抄 |

> **文件名里的 `_ProMax` 是历史标签**：产品标签在 v0.21 退役为 `Pro`，但工作簿名是建库时的历史快照，不随 App 升版、也不跟着改名（`applicationId`、存档、侧载升级都认它）。看到 `_ProMax` 在这里不是漏改。

---

## 3. 三个工作簿的边界

### 3.1 权威源 `RPL_ExDark_v0.15_ProMax.xlsx`（24 表）

- 角色：**唯一权威源 + `gen_seed.py` 兼容源**，状态冻结（只读优先）。
- **禁止**：用 `openpyxl` 保存它。`W1–W16` 的 `LOAD` / `PROTOCOL` / `RPE` 是公式，`gen_seed.py` 以 `data_only=True` 读缓存值，openpyxl 一保存缓存就空 → 负荷读成 0、组次协议读成空。要写入就用 Excel/WPS 打开后保存，保存完确认公式仍有缓存值，再跑 `gen_seed.py`。
- **禁止**：在 `W1–W16` 插入行或列、改动 `信息` 的固定坐标区、删除任何工作表。改坐标属于代码变更，`gen_seed.py` / `wkbook.py` 同改并重跑种子 + 全量门禁。
- 元数据与数据字典在 `04_生成物/05_主工作簿数据字典.csv`（**不写在簿内**，理由同上）。
- 表归属：`信息` `周期` `W1–W16` `动作库` `映射` `协议` 是 input；`Exe` `总览` 是 derived，不进 seed；`追踪` 是 demo 数据，`gen_seed` 不读、且会把遥测置空。
- 已知问题（不修，除非机主点名；详情看 `04_生成物/04_数据质量报告.md`）：负荷与 1RM/百分比口径不一致、`总览`/`周期` 组数与处方组数不一致、`协议` 里仍有旧 mode 名（`SS` / `SL` / `T1.Def` / `T1.S2` / `T1.S3`，靠 `gen_seed.py` 的 `MODE_MIGRATION_MAP` 迁移）、动作库无稳定 ID 只能靠名字跨表连接。

### 3.2 `RPL_Program_Library_v0.15.xlsx`

- 角色：参考库，不是可执行计划。`gen_seed.py` 只读 `计划总库` 的前 16 列。
- 第 17 列之后是补的规范化字段（family / level / 时长与频率区间 / 自动调节与验证标准 / 许可状态 / 语言 / 校核日期）。
- **禁止**：改前 16 列顺序；把「别名/占位」条目当可执行计划。

### 3.3 `RPL_Set_Strategy_v0.15.xlsx`

- 角色：参考库。`gen_seed.py` 只读三张表的原始列；补的 ID / tier / 备注列在后面。
- **禁止**：改原列顺序；把自由文本的适用性矩阵当机器枚举。

---

## 4. 参考资料目录的规矩

`ref/02_参考资料/` 只增不改，分类固定为 `01_规则与协会` `02_研究与综述` `03_计划与方法/01_方法论与手册` `03_计划与方法/02_具体计划与模板` `04_技术与教练` `05_营养与恢复` `06_书籍与预览` `07_数据集与工具`。

命名：目录用 `NN_中文名`（新增插段，不重排旧编号）；文件用英文下划线名，形如 `<主题>_<年份>_<期刊或来源缩写>_<语言>.<ext>`——看名字就知道是什么、哪一年、什么语言。

版权：官方公开文件记 `license`；付费书/课程**只建元数据与官方链接，不放全文**。付费与下载不到的清单在 `04_生成物/06_无法下载与付费清单.csv`、`07_待补资源清单.csv`。

---

## 5. 生成物与归档

| 对象 | 怎么来 | 干什么用 |
|---|---|---|
| `refs_manifest.json` / `refs_index.csv` | 扫描 `ref/02_参考资料` + 元数据 | 资源主数据（机器读 / 人读） |
| `checksums.sha256` | 逐文件哈希 | 完整性校验 |
| `01_文件迁移表.csv` | 重组记录 | 旧路径 → 新路径可追溯 |
| `02_重复文件清单.csv` | 哈希去重 | `05_归档/01_重复文件/` 的账 |
| `04_数据质量报告.md` | 自动统计 | 交付时的体检结论 |
| `05_主工作簿数据字典.csv` | 自动统计 | 权威源的字段字典 |
| `05_归档/01_重复文件/` | 哈希重复副本 | 只归档不删；不跟踪 |
| `05_归档/02_旧索引/` `03_过期索引/` | 被取代的索引 | 历史可追溯 |
| `05_归档/04_工作簿备份/` | 改动前备份 | 回滚点 |

取法：`ls data/04_生成物/`（别在文档里抄文件名与条数，新增一份就变）。

---

## 6. 变更流程

1. **加一份参考资料** → 判分类 → 按 §4 命名 → 放入目录（同名先比哈希，别覆盖）→ 重跑 `04_生成物` 的 manifest / index / checksums。要让它进仓，就得让 seed 的 `canon` 指到它，否则只是本机文件。
2. **改一个计划条目** → 只改 `计划总库`；保持前 16 列顺序 → 确认 `gen_seed.py` 的列读取范围没变 → `cd mobile && python tools/gate.py`。
3. **改权威源** → 先备份进 `05_归档/04_工作簿备份/` → 用 Excel/WPS 改 → 重跑 `gen_seed.py` + `build_html.py` → 全量门禁。
4. **改文件名** → 属于破坏性操作：`gen_seed.py` 的 `XLSX`、`rxlib.py` 的 `__main__` 默认路径、引用该名的文档三处同改，再重跑种子与打包（gate S8 三端同源会当场抓出来）。改前先快照。
