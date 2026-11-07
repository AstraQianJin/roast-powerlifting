# RPL-Plan-v1 计划交换规范

> **谁该读这份文档**：要把训练计划喂进 App 的人（含外部 AI），以及要改 `plan_xlsx.py` / 契约 JSON 的人。
> **机器可读的契约**：[mobile/tools/schema/RPL-Plan-v1.json](../tools/schema/RPL-Plan-v1.json) —— 那份 JSON 才是事实源，本文是它的解释与使用手册。两者不一致时以 JSON 为准，并**立刻**回来改本文。

---

## 0. 边界：这份契约管什么、不管什么

| | 说明 |
|---|---|
| **管** | 「交换工作簿」——六张表：`Profile / Blocks / Days / Workouts / Telemetry / Armor`。外部工具（AI、Excel、脚本）用它描述一个完整周期。 |
| **不管** | 权威源表 `../../data/01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx`（24 张表）。交换契约**不读也不写**它（硬边界 1）。想改动作库、分组、`proto` 参数，那是源表 + `gen_seed.py` 的事，与本契约无关。 |
| **不管** | App 的运行时状态结构（`state.weeks` 的具体形状）。契约只规定「导入后写进哪些点分路径」，字段名在 `keys` 里。 |
| **不做** | 网络传输、加解密、版本协商以外的兼容承诺。`schema_ver` 只接受 `accepted_schema_vers` 里列的值。 |

一句话：**六表进，一个完整 App state 出**；出不了 state 的一律算 error，不放行。

---

## 1. 单一事实源（决策 D7）

同一份 JSON 被三方消费，任何一侧都不许再写第二遍列序 / 枚举 / 范围：

```
tools/schema/RPL-Plan-v1.json
   ├── Python：plan_xlsx.py 启动时 load_schema() 直读                （已落地）
   ├── 前端：build_html.py 注入成 `const PLAN_SCHEMA`                （已落地，Phase C 的 App 内读写引擎用它）
   └── 校验：gate.py 的静态守卫（取不到被检对象一律算 FAIL）           （已落地）
```

注入这一步还带了三道闸门（[mobile/tools/build_html.py](../tools/build_html.py)）：`ensure_fresh_seed()`（权威工作簿比 `seed.json` 新就重跑 `gen_seed.py`，别把旧数据打进 APK）、注入前用本契约校验 seed（不过就不产成品）、成品尾部 `<!-- BUILD_FP v=… tpl=… seed=… sch=… -->`（三份输入的 sha256 摘要，改动落在哪一份一眼可见，且**不含时间戳**，可逐字节复现）。反向验证见 [_sabotage_b5.py](../tools/_sabotage_b5.py)：模板缺占位符、seed 顶层键被改、占位符没被替换 —— 三处各自都能把构建拦下来。

代码里**没有**列名数组、没有枚举表、没有范围常量。`plan_xlsx.py` 通过两个间接层拿列：

- `role_columns`：角色 → 真实列名（例：`rc["pct"]` → `"pct_1rm"`）。改列名只动契约。
- `keys`：真实列名 → state 字段名（例：`{"load_kg": "load"}`）。

因此**契约里改名 = 全线改名**；本文与 JSON 里的列名一律从 JSON 抄，不手写。

---

## 2. 两种载体形态

| 形态 | 读 | 写 | 说明 |
|---|---|---|---|
| `.xlsx` 工作簿 | `book_to_plan()` | `plan_to_book()` | 六张表，表名 = `sheet_order`，第 1 行表头 |
| CSV 目录 | `read_plan_csvs()` | `write_plan_csvs()` | 目录下固定六份 `<表名>.csv`（`Profile.csv` …）；UTF-8 **带 BOM**（Excel 双击不乱码），`newline=""` |

- 入口统一是 `read_plan_any(path)` / `state_to_plan_book(state, out)`：**目录 → CSV，`.xlsx` 后缀 → 工作簿**，靠路径形态分派，不需要开关。
- 两种形态**行号语义一致**：CSV 第 n 行 = 工作簿第 n 行，所以错误信息里的 `Row{n}` 对两边都成立。
- 空行两边都忽略（xlsx 全空行、CSV 全空字段行都跳过）。
- 布尔格：`.xlsx` 里写真布尔；CSV 里写 `TRUE` / `FALSE` 字符串（CSV 无布尔类型，`csv.writer` 会把 Python `False` 写成 `False`，那会破坏往返比对 —— 所以导出时归一化）。
- 表头必须与契约**逐列等值且列数相同**。多一列、少一列、顺序换了，都是 error（`表头第 %d 列应为 'x'，实为 'y'`），但仍按位置尽力解析以便一次报出更多问题。

### ⚠ App 侧 CSV 解析与本契约的已知差异

App 内的 CSV 读取器 [mobile/tools/template.html:5221](../tools/template.html#L5221) 是 `text.split(/\r?\n/)` **先按行切开**再逐行做引号状态机；而写侧 `csvEscape`（同文件 :5210）遇到含换行的值会加引号。后果：

- **引号包住的换行会被拆成两行**，半条记录当垃圾丢掉；空行同样被丢。
- 所以：`notes` / `directive` / `rx_text` 这类自由文本里**不要放换行**。本工具（Python）用标准 `csv` 模块，能正确读写带引号的换行，但那份文件喂给 App 就会坏 —— 契约按 App 的下限要求：**单元格内禁止 CR/LF**。
- 跨工具搬运优先用 `.xlsx`；只在给人看、或喂给只能读 CSV 的工具时才用 CSV 目录。

> 注：这说的是**交换契约**的六表 CSV。App 自己的「训练日志 26 列」（`CSV_COLS`）是**另一套协议**：列名与列序自 v0.07 冻结，v0.13 起由 [RPL-Exchange-v1.json](../tools/schema/RPL-Exchange-v1.json) 的 `log_jsonl.record_keys_frozen` 单点定义，gate S7 拿「契约 / 模板 / 成品」三方逐列对账。改名或换序属于协议变更，要走 `RPL-Log-v2`，不许就地改那份清单。

---

## 3. 六表逐列规格

列序即契约，照抄即可（来源：JSON 的 `columns`）。

### 3.1 `Profile`（必填，`field,value,description`）

纵向「字段-值」两列排布；`description` 只给人看，导入忽略。也接受**横向两行**排布（第 1 行字段名、第 2 行值）——`_profile_rows_from_raw` 自动识别。

24 个字段。**必填 8 个**：`schema_ver`、`start_date`、`gender`、`age`、`bw_kg`、`sq_1rm`、`bp_1rm`、`dl_1rm`。

| 字段 | 类型 | 范围 / 枚举 | 默认 | 落点（state 路径） |
|---|---|---|---|---|
| `schema_ver` | str | `RPL-Plan-v1` / `1` / `v1` | — | — |
| `start_date` | date | `^\d{4}-\d{2}-\d{2}$` | — | `profile.startDate` |
| `plan_weeks` | int | 1–52 | `on_missing: total_weeks` | `profile.planWeeks`（填了必须 = Blocks 周数之和；未填按本次之和补齐） |
| `gender` | enum | `M` / `F` | — | `profile.gender` |
| `age` | int | 10–100 | 24 | `profile.age` |
| `height_cm` | num | 100–250 | 175 | `profile.height` |
| `bw_kg` | num | 30–250 | — | `profile.bw` |
| `init_bw_kg` | num | 30–250 | `= bw_kg` | `profile.initBw` |
| `target_bw_kg` | num | 0–250 | 0 | `profile.targetBw` |
| `equip` | enum | `classic` / `equipped` | `classic` | `profile.equip` |
| `recovery` | str | 自由文本 | `Normal / Balanced` | `profile.recovery` |
| `sq_1rm` / `bp_1rm` / `dl_1rm` | num | 0–600 | — | `profile.sq` / `.bp` / `.dl`（**锚点**） |
| `ohp_1rm` | num | 0–600 | `mround(bp_1rm×0.72, 2.5)` | `profile.ohp` |
| `init_sq` / `init_bp` / `init_dl` | num | 0–600 | `= 对应 *_1rm` | `profile.initSq/.initBp/.initDl` |
| `target_sq` / `target_bp` / `target_dl` | num | 0–600 | 0 | `profile.targetSq/.targetBp/.targetDl` |
| `bar_kg` | enum | 10/15/20/25/30/35/40 | 20 | `plateCfg.barKg` |
| `collars` | bool | TRUE/FALSE | FALSE | `plateCfg.collars` |
| `motto` | str | 自由文本 | `""` | `profile.motto` |

规则细节：

- `default_from` 的字段（`init_bw_kg`、`init_sq/bp/dl`）没给时取来源字段的**行值**，来源也没有时取 base state 现值。
- `derive` 只支持 `mround(<字段> * <系数>, <步长>)` 一种式子（当前只有 `ohp_1rm`）。
- 未知字段名 → **warning**（`未知字段 'xxx'，导入时忽略`），不算错，方便你先写备注字段。
- 锚点三兄弟（`sq/bp/dl_1rm`）同时是 `anchors` 的来源：`S.Main`→`sq_1rm`，`B.Main`→`bp_1rm`，`D.Main`→`dl_1rm`。

### 3.2 `Blocks`（必填）

`block_id,cycle_type,name_zh,name_en,work_weeks,deload_weeks,work_mode,deload_mode,base_rpe,rpe_step,deload_rpe`

- 必填列：`cycle_type`、`name_zh`、`work_weeks`。
- `cycle_type` ∈ `Hyper` / `Strength` / `Transmute` / `Peak` / `Custom`。
- 范围：`work_weeks` 1–24、`deload_weeks` 0–4、`base_rpe`/`deload_rpe` 5.0–10.0、`rpe_step` 0.0–1.0。
- 默认：`deload_weeks`=0、`deload_mode`=`T1.DL`、`base_rpe`=7.0、`rpe_step`=0.25、`deload_rpe`=6.0、`name_en`=`""`。
- `block_id` 必须形如 `^B\d+$` 且**不许重复**（error）；但导入时**一律按行序重编为 B1..Bn**，所以留空、写 `B99` 都不影响结果，只影响可读性。
- `work_mode` / `deload_mode` 可空；给了就必须是 `proto` 里的模式名，否则 error（`模式 'x' 不在 proto 中`）。
- 至少 1 个块；周数合计 = Σ(`work_weeks`+`deload_weeks`)，必须落在 1–52；`Profile.plan_weeks` 若填了必须严格等于它。

### 3.3 `Days`（必填，最多 6 行）

`day_id,label,title_zh,title_en,weekday_offset,focus_tags,forbid_heavy_sbd,forbid_t1_main,upper_only,deload_cap`

- 必填列：`day_id`、`title_zh`。
- `day_id` ∈ `A B C D E F`，唯一、至少 1 行、最多 6 行。**日键只有这六个**，别的写法（`a`、`Day1`）是 error。
- `weekday_offset` 0–6，对应 `weekday_labels` = `Mon Tue Wed Thu Fri Sat Sun`，导入时回填到 `weeks[w][d].bio.day`（就是 App 遥测头显示的星期标签）。
- `focus_tags` 逗号分隔，白名单 8 个（白名单外的标签是 error）：
  `tag_sbd_heavy` `tag_sq_quad` `tag_bp_upper` `tag_dl_post` `tag_vari_weak` `tag_hyper_acc` `tag_power_gpp` `tag_deload_rec`
- 四个开关列是布尔（`TRUE`/`FALSE`，CSV 里仅此两值；xlsx 里也可用真布尔）：见 §8。

### 3.4 `Workouts`（必填）

`week,day,seq,row_idx,tier,mode,category,movement,pct_1rm,load_kg,sets,reps,rx_text,target_rpe,prog_rule,actual_reps,actual_rpe,done_sets,done,notes`

- 必填列：`week`、`day`、`movement`。
- 一行 = 一个动作。同一 `(week, day)` 的行按 `seq` 排序后成为该日的动作列表。
- `week` 必须是 ≥1 且不大于 Blocks 周数合计；`day` 必须在 `Days` 里定义过。
- `seq` 可留空（留空由导入侧按排序结果补），给了就必须 ≥1 且在同 `(week,day)` 内唯一。
- `mode` 必须 ∈ `proto`（24 个，见 §4.1）；`category` 必须 ∈ `lib.categories`（33 组，见 §4.2）。
- `movement`：**不校验存在性**（拼错只 warning，见 §10），因为动作库会长。想安全就用附录 A 的原名。
- `tier`、`sets`、`prog_rule`、`pct_1rm`、`actual_reps` 通常是**导出时算出来的**，AI 手写时可留空（见 §5）。
- `pct_1rm` / `load_kg`：见 §6。
- `done` 布尔；`done_sets` 0–20；`actual_rpe` 1–10（App 里的历史 RPE）；`target_rpe` 5–10，留空按周兜底（见 §9）。
- `unique` = `(week, day, row_idx)`：三列都非空时若重复 → error。`row_idx` 留空不触发该检查。

### 3.5 `Telemetry`（可选，14 列）

`week,day,readiness,bw_kg,directive,sleep_h,rhr_bpm,hrv_ms,fuel_strategy,exec_status,duration_min,water_l,session_rpe,joint_pain`

- `(week, day)` 唯一，`week`/`day` 合法性同上；`readiness` 是自由文本（`readiness_free_text: true`，不参与枚举检查）。
- 范围：`bw_kg` 30–250、`sleep_h` 0–16、`rhr_bpm` 20–120、`hrv_ms` 0–300、`duration_min` 0–600、`water_l` 0–20、`session_rpe` 1–10、`joint_pain` 0–10。
- 枚举：`fuel_strategy` ∈ `cut`/`maintain`/`bulk`；`exec_status` ∈ `green`/`amber`/`red`。
- **列的数值/文本属性完全由它是否出现在 `ranges` 里决定**，代码里没有字段名白名单（`numeric_from: "ranges"`）。
- `mirror_day_level: ["readiness","bw"]`：这两个值除了写进 `bio.*`，还同时回写日级同名字段（App 历史字段，CSV 导入也是这么干的）。
- 整表缺失 = 只有 warning，导入时生成空遥测结构（**仍逐日生成**，星期标签照 `weekday_labels` 填）。

### 3.6 `Armor`（可选，13 列）

`week,item_idx,domain,item,target,intensity,mon,tue,wed,thu,fri,sat,sun`

- 恢复装甲（辅助训练）的**周 × 星期打勾表**。`item_idx` 是 **0-based**，指向 `state.aux` 下标。
- 定义列（`domain` / `item` / `target` / `intensity`）逐周重复写出；导入时以**最小 `item_idx` 那一行**的定义重建 `state.aux`，其余行若与之一致就忽略，不一致 → error（`item_idx=%d 定义不一致`）。
- `mon..sun` 七列是布尔（`day_columns`），打勾即该装甲项在周几执行；落进 `weeks[w].auxDays`。
- 整表缺失 → warning + 回落 seed 里的 10 项默认定义。

---

## 4. 受控枚举（从 `tools/seed.json` 现值抄，共 24 模式 / 33 分组）

### 4.1 `mode`（24 个，`proto` 键）

```
Top.Single  Top.Set  Top.Test
T1.Mod  T1.3x3  T1.5x5  T1.6x6  T1.Def.1  T1.Def.2  T1.Def.3  T1.DL
T2.Mod  T2.Vol  T2.Def  T2.Tr  T2.DL
T3.Mod  T3.Def  T3.Tr  T3.DL
RTS.1  RTS.2  RTS.3
Custom
```
对应档位 `tier`：`TOP / T1 / T2 / T3 / RTS / Other`（由 `proto[mode].tier` 决定，不要自己填）。

### 4.2 `category`（33 组，`lib.categories`）

```
S.Main  B.Main  D.Main
S.Vari.Start  S.Vari.Mid  S.Vari.End  S.Vari.Balance
B.Vari.Start  B.Vari.Mid  B.Vari.End  B.Vari.Control
D.Vari.Start  D.Vari.Mid  D.Vari.End  D.Vari.Power
S.Core  S.Quads  B.Pecs  B.Delts  B.Triceps  B.Rotator
D.Lats  D.LowerBack  D.GluteHam  D.Forearms
SBD.UpperBack  SBD.Power  SBD.Sled
S.Calves  S.GluteMed  Hyper.Biceps  Hyper.LatDelts  Unmapped
```

### 4.3 其余

| 列 | 取值 |
|---|---|
| `Days.day_id` | `A` `B` `C` `D` `E` `F` |
| `Days.focus_tags` | 8 个 `tag_*`（§3.3） |
| `Blocks.cycle_type` | `Hyper` `Strength` `Transmute` `Peak` `Custom` |
| `Telemetry.fuel_strategy` | `cut` `maintain` `bulk` |
| `Telemetry.exec_status` | `green` `amber` `red` |
| `Profile.bar_kg` | 10 15 20 25 30 35 40 |
| 布尔 | `TRUE` / `FALSE` |

---

## 5. 派生列（`Workouts.derived_columns`）

| 列 | 何时算 | 公式 / 来源 | 导入时 |
|---|---|---|---|
| `seq` | 导出 | 该 `(week,day)` 内 1-based 序号 | 仅用于排序，不单独落字段 |
| `row_idx` | **双向** | `row_idx.first[day] + seq - 1` | **保留原值**（`keep_on_import`）：它关联 App 的 e1RM 历史 |
| `tier` | 导出 | `proto[mode].tier` | 忽略（与 proto 不符只 warning） |
| `sets` | 导出 | `proto[mode].sets` | 不填则用 proto 值 |
| `pct_1rm` | 导出（**权威**） | `round(load_kg / anchor_1rm, 4)`，仅当 `category` 命中 `anchors` 且锚点 > 0 | 见 §6 |
| `prog_rule` | 导出 | `prog_rules[mode]`，查不到用 `_default` | 忽略（App 无对应字段） |
| `actual_reps` | 导出（空串） | — | 忽略 + warning（处方次数看 `reps`） |

「`on` 以 `export` 开头且没有 `keep_on_import`」= **纯派生列**，往返比对不比它们（AI 手写的 `tier`/`sets` 与算出来的本来就可能不同，比了只会制造噪音）。派生得对不对由专用断言管（见 §12）。

`prog_rules` 表（16 条，含 `_default`）在契约里，导出时按 `mode` 查：

```
Top.Single  AMRAP>=1:+2.5kg|<1:->0.5RPE        Top.Set  AMRAP>=3:+2.5kg|<3:->0.5RPE
Top.Test    单组测试：记录即更新 1RM 估计        T1.Mod   AMRAP>=8:+2.5kg|5-7:+0kg|<5:->T1.Def
T1.3x3      全对完成:+2.5kg|否则:+0kg           T1.5x5   AMRAP>=5:+2.5kg|<5:->T1.Def
T1.Def.1/2/3 固定 5×3+ / 6×2+ / 10×1+，不加重量  T1.6x6   AMRAP>=6:+2.5kg|<6:->T1.DL
T1.DL/T2.DL/T3.DL 减载周不进阶                  T2.Mod   AMRAP>=10:+2.5kg|<10:+0kg
T3.Mod      AMRAP>=15:+1.25kg|<15:+0kg          _default 无进阶规则：按处方执行
```

---

## 6. 冲突策略 D10：`pct_1rm` 权威

契约 `conflict_policy`：

```json
{"pct_1rm_vs_load_kg": "authoritative_pct_warning_only",
 "tolerance_kg": 5.0, "round_step_kg": 2.5, "pct_decimals": 4}
```

- **`pct_1rm` 在场就是它说了算**：`load_kg = mround(anchor_1rm × pct_1rm, 2.5)`，无条件覆写 AI 写的 `load_kg`。
- 两者都给了且 `|load − 推导值| > 5kg` → **warning**（不是 error），内容含推导值与实际偏差；导入照样按 `pct` 覆写。
- 两者**都缺**且 `category` 是 `.Main` 主项 → **error**：`[Workouts!Row12.pct_1rm] 主项动作必须给 pct_1rm 或 load_kg`。
- 非主项（`category` 不在 `anchors` 里）不受这套约束：`load_kg` 直接当绝对负荷用，`pct_1rm` 只是导出的展示值。
- `mround` 与 JS `Math.round(v/s)*s` **逐值一致**（半进位），Python 侧实现是 `round(math.floor(x/2.5 + 0.5) * 2.5, 6)`。**别用 Python 内建 `round`**，那是银行家舍入，答案不同。

写法：`pct_1rm` 支持小数（`0.70`）与百分比串（`"70%"` → `0.70`），见 §7。

---

## 7. 数字与百分号写法

`_num()` 是唯一入口，规则：

- 空 / 不可解析 → `None`；Python 布尔不当数字（`TRUE` 不会变成 1）。
- 千分位逗号会被去掉（`"1,200"` → 1200）。
- **以 `%` 结尾时除以 100**：`"70%"` ≡ `0.70`，`"82.5%"` ≡ `0.825`。`pct_1rm` 和 `target_rpe`（不带 %）都能走这个入口，但只有 `pct_1rm` 该用百分号写法。
- 其余范围校验按契约 `ranges` 逐列判定，越界就是 error（`越界 [a, b]，实为 x`）。

---

## 8. 训练日安全约束（`constraint_rules`）

`Days` 的四个布尔开关（或标签）在日级生效，命中的 `Workouts` 行会被记违规：

| 开关（`when`） | 触发条件 | 也当开关用的标签 | 判违规的行 |
|---|---|---|---|
| `forbidHeavySbd` | 真 | — | `category ∈ S./B./D..Main` 且 `tier=T1`；或 `mode` ∈ `Top.*` / `T1.3x3` / `T1.5x5` / `T1.6x6` / `SS` / `SL` |
| `forbidT1Main` | 真 | — | `category` 以 `.Main` 结尾 |
| `upperOnly` | 真 | — | `category` 以 `S.`/`D.` 开头且 `tier ∈ T1/T2` |
| `deloadCap` | 真 | `tag_deload_rec` | `mode` ∈ 上表的重负荷集合；或 `target_rpe > 7` |

- 违规文案取自契约的 `why`，例如 `[Workouts!Row18.mode] 违反 [禁止 Heavy SBD]：该日禁主项池 T1/重负荷（该日启用了 forbidHeavySbd）`。
- **默认只进 warnings**；`--strict-constraints` 升级为 errors。也就是说：宽松模式让你先看，严格模式让你不能发。
- `mode` 匹配支持 `前缀.*` 通配（`Top.*` 命中 `Top.Single`/`Top.Set`/`Top.Test`）。

---

## 9. 导入时的补齐与冻结

**结构默认**（`state_defaults_on_import`）：

| state 路径 | 来源 |
|---|---|
| `structure.daysPerWeek` | `len(Days)` |
| `structure.totalWeeks` | Σ Blocks 周数 |
| `structure.version` | 3 |
| `weeks` | 生成 `1..totalWeeks` 的空日结构（日键 = `Days.day_id` 顺序），每日含 `title/readiness/bw/bio.day/post/exercises` 与 `auxDays` 全 False 掩码 |
| `structure.inactiveWeeks` | 见下 |

**行级兜底**（AI 留空时的答案）：

- `reps` ← `proto[mode].reps`；`rx_text` ← `proto[mode].rx`。
- `target_rpe` ← **按周**：训练周用所在块的 `base_rpe`，减载周用 `deload_rpe`；块信息也缺时用 `base_rpe` 默认 7.0。
- `row_idx` ← `first[day] + seq − 1`；`seq` 由排序结果重写。
- `load_kg` ← `pct_1rm` 覆写（§6）；两者都缺（非主项）则 0。
- `Blocks.block_id` ← 按行序重编 `B1..Bn`。
- `profile.planWeeks` ← 本次 Blocks 之和（契约里这条写作 `plan_weeks.on_missing: "total_weeks"`）。**必须有**：留成上一份计划的周数，再导出的文件会撞上自己的 `cross` 检查，自产文件过不了自产契约。
- `Armor` 缺表 ← 回落 base seed 的 10 项定义；`Telemetry` 缺表 ← 空遥测结构（星期标签仍填）。
- `Profile` 未给的字段：有 `default` 用默认，有 `default_from` 用来源，有 `derive` 用推导式，都没有则**保留 base state 现值**（不写 `None`）。

**D4 归档 + 冻结**：新计划比 base seed 短（比如 16 周 → 12 周）时，第 13–16 周的数据**不删除**：原样留在 `state["weeks"]`，周号登记进 `structure.inactiveWeeks`（升序整数数组）。再导出工作簿时**只写 1..totalWeeks**，所以交换文件看不到冻结周，App 里的历史还在。要恢复更长周期，只需在新计划里把周数写回去。

---

## 10. 错误格式与分级

格式取自契约：

```
[{sheet}!Row{row}.{column}] {reason}
```

- 表级/结构级问题没有具体行 → `row` 位置写成契约 `error_row_for_sheet_level` 指定的 `-`（例：`[Days!Row-.day_id] Days 表没有有效训练日`）。
- CSV 目录形态下 `Row{n}` 与 xlsx 的 `n` 同义，可直接对照。

**error（挡住导入）** —— 一律 `plan_dict_to_state()` 抛 `ValueError` 并把全部错误逐行列出：

| 类 | 例子 |
|---|---|
| 缺核心表 | `缺少核心工作表 'Days'` |
| 表头不符 | `表头第 4 列应为 'row_idx'，实为 'row'` |
| 必填缺值 / 类型 / 越界 / 枚举非法 | `缺少必填值`、`应为数字，实为 'abc'`、`越界 [30, 250]，实为 9`、`取值应为 M/F，实为 'X'` |
| 布尔写法 | `布尔值应为 TRUE/FALSE，实为 'yes'` |
| 引用完整性 | `day 'G' 未在 Days 表定义`、`week=17 超出 Blocks 合计周数 16`、`mode 'T1.9x9' 不在 proto（24 个模式）中`、`category 'S.Foo' 不在 lib.categories（33 组）中` |
| 唯一性 | `重复的 (week, day, row_idx)=(1, A, 9)`、`(week=1, day=A) 内 seq=3 重复`、`day_id 'A' 重复`、`block_id 'B2' 重复` |
| 周期数学 | `周期块周数合计 60 越界 [1, 52]`、`plan_weeks=10 与 Blocks 周数之和 12 不符`、`训练日行数 8 超过上限 6` |
| 主项缺负荷 | `主项动作必须给 pct_1rm 或 load_kg` |
| 装甲定义分叉 | `item_idx=3 定义不一致：'X' vs 'Y'` |
| `validate --seed` 顶层不变量 | `缺少顶层键 'proto'`、`weeks 数 15 与 blocks 周数之和 16 不符`、`周 3/B 缺训练日 A`、`动作的 cat 不在 lib.categories 中` |

**warning（放行，但要说出来）**：

| 类 | 文案要点 |
|---|---|
| 可选表缺失 | `可选工作表缺失，导入时按默认值初始化` |
| `Profile` 未知字段 | `未知字段 'xxx'，导入时忽略` |
| `movement` 不在库 | `movement '...' 不在动作库（240 个不重复动作名）中，请核对拼写` —— **不是 error**：动作库会长，拼错也能练，只是没法一键复用 |
| `tier` 与 proto 不符 | 导入以 proto 为准 |
| `row_idx` 与公式不符 | 导入按原值保留（因为它连着历史 e1RM） |
| `pct` / `load` 打架 > 5kg | `pct_1rm` 为权威，导入时覆写（D10） |
| `actual_reps` 有值 | 不参与导入，处方次数看 `reps` |
| 约束违规（默认） | 见 §8；`--strict-constraints` 变 error |

---

## 11. 命令行

```bash
cd mobile/tools
python plan_xlsx.py validate <PATH>            # .xlsx 或含六份 CSV 的目录
python plan_xlsx.py validate --seed            # 改校验 seed.json 的顶层不变量
python plan_xlsx.py validate <PATH> --strict-constraints
python plan_xlsx.py build --in <PATH> --out <OUT> [--state-out <json>]
python plan_xlsx.py export [--seed <json>] --out <OUT>
python plan_xlsx.py roundtrip <IN.xlsx> [--out <OUT.xlsx>]
```

- `PATH` / `--in` / `--out` 都接受「`.xlsx`」或「目录（六份 CSV）」两种形态。
- `validate`：只读不写，打印全部 `ERROR` / `warning` 与计数；有 error → 退出码 1。
- `build`：校验 → 补齐派生列 → 写一份**规范**工作簿（可直接喂 App），`--state-out` 顺带导出转换后的 state JSON。写完对产物**再校验一遍**并报告，所以「0 error / 0 warning」是对产出自我的结论，不是对输入的。
- `export`：从 `seed.json`（或任意 state JSON）导出六表工作簿 —— 给 AI 当**参考答案**用。先 `validate --seed`，不过就不写。
- `roundtrip`：`工作簿 → state → 工作簿`，逐格比对。语义是**回归检测**：A 里每个已填的**非派生**格必须在 B 中原样出现；B 比 A 多（补默认值）算补全、不算改动；行数减少报 error；D10 的 `load_kg` 覆写豁免（与算出的覆写值一致才豁免）。退出码 = 有无差异。

Python 侧 API（`build --state-out` 之外想程序化时用）：

```python
import plan_xlsx as px
sch = px.load_schema()
plan, hdr_errors = px.read_plan_any("in.xlsx", sch)          # 目录 → CSV，文件 → xlsx
res = px.validate_plan_dict(plan, strict_constraints=False, sch=sch)
state = px.plan_dict_to_state(plan, base_seed=None, sch=sch)  # 校验不过抛 ValueError
out = px.state_to_plan_book(state, "out.xlsx", sch)           # 传目录则写六份 CSV
info, out2 = px.roundtrip_book("out.xlsx", sch=sch)           # info["diff"]["diffs"]
```

---

## 12. 怎么证明这套规范不是摆设

- 回归：[mobile/tools/test_plan_xlsx.py](../tools/test_plan_xlsx.py) —— **83 项断言 / 7 组**，全部从契约读列名，不写死。
  - **T1** 权威导出与往返：seed → 六表 0 error / 0 warning；9052 格往返零差异；`pct_1rm = round(load/anchor, 4)` 且不留空。
  - **T2** AI 最简输入（只有四张核心表）：可选表按契约数量报 warning、`"70%"` → 95.0、proto 兜底 `reps`/`rx`、D10 覆写 130→115、按周 RPE 兜底、`row_idx` 补齐、`ohp = mround(95×0.72) = 67.5`、`block_id` 重编号、空遥测仍逐日生成、`plan_weeks` 未填也按本次 Blocks 算且**再导出的工作簿自校验 0 error**（T2.17/2.18 —— 少这条，`build` 会被自己的产物判 error）。
  - **T3/T3b** 坏输入电池 23 条（每条都要「变红且只有它该变红」）+ 约束宽松 2 warning / 严格 2 error。
  - **T4** 硬边界：权威源表 sha256 前后不变；依赖面里不许出现 `rxlib`。
  - **T5** A–F 六日几何与 `row_first_map` 分叉必抛。
  - **T6** 12 周新计划替换 16 周基线 → `inactiveWeeks=[13,14,15,16]`、旧周数据仍在、再导出只写 1–12、幂等。
- 反向验证：[mobile/tools/_sabotage_b4.py](../tools/_sabotage_b4.py) 往 `plan_xlsx.py` 注 5 处红线故障（删 `mround` 的 `+0.5`、导出 `pct_1rm` 置空、核心表缺失降级成 warning、少建一周结构、`plan_weeks` 不补齐），跑 `test_plan_xlsx.py` 合并注入时 6 项变红（`pct` 那处会让 T2 组提前抛错，所以 `plan_weeks` 那处单点注入时恰好只红 T2.17/T2.18），再逐字节还原。**能红才算有人在守。**
- 构建链：`python gate.py --static`（S1–S13）与 B6 之后加入的 plan_xlsx 动态项。
- **App 内的第二实现**（C1）：`template.html` 里的一段零依赖 xlsx 引擎（`planFromXlsxBytes` / `xlsxBytesFromPlan`），列序、键名与错误串全部取自成品里的 `const PLAN_SCHEMA`，读侧对齐 `book_to_plan`、写侧对齐 `plan_to_book`。它的正确性不靠「看着能跑」，靠逐格对账：
  - [mobile/tools/xlsx_parity.py](../tools/xlsx_parity.py) 现造三份 fixture 与期望值 —— `app.xlsx`（App 导出形态）、`hand.xlsx`（表序打乱 / 契约外的表 / Profile 横排 / 中间空行 / 多余列 / 真布尔 / 日期格）、`odd.xlsx`（手写 XML：富文本分段、`xml:space`、`&#45;`、藏在注释里的假标签、缺 `r` 的行列、`t="str"`/`"b"`/公式无缓存值、自定义 numFmt 与内建 numFmtId 14 各一条）。
  - [mobile/tools/xlsxv.js](../tools/xlsxv.js)（gate 的 **D8**）把同一批字节喂给成品：**读** 11132 / 11132 / 29 格与 `plan_xlsx` 逐格相同、表头错误串逐字相同；**写** 由 openpyxl 原样读回（canonical 9052 非空格、edge 25 格）且契约判定与 openpyxl 写的同一份计划逐条相同（edge 故意不合法，两边都报同样的 14 条 error）；同一份计划两次导出**逐字节相同**；四类坏输入必须抛错而不是静默给半份计划。
  - 反向验证：`python tools/_sabotage_c1.py 1|2|3` 三处故障（zip 中央目录尺寸 +12 / 去掉内建日期格式 14 / 有格无值的整行不剔除）各自都能把 D8 判红，`build_html.py` 复原。
- **App 侧的 §9 补齐与 D4 冻结**（C2）：成品里的结构写入收成一个入口 `applyStructure(raw)` —— `totalWeeks` 只从 ΣBlocks 求、`daysPerWeek` 只从 `len(dayDefs)` 求、`version` 只从契约的 `state_defaults_on_import["structure.version"]` 取，三处派生不再有第二份；超出新周数的既有周按 D4 登记 `structure.inactiveWeeks`（数据不删），CSV 导出只写未冻结的周，与 `plan_xlsx._active_week_keys` 同口径。开机恢复、只读浏览、设置页保存、CSV 的 `STRUCTURE` 行四个入口全部改走这个函数，`gate.py` 的 **S11** 保证它只有一个赋值点。行为由 `v3v.js` 的 **Q 段（11 项）**守住：缩期→冻结登记、冻结周逐字节未删、导出最大周、周轨胶囊数、延长回来自动解冻、`ensureWeeks` 的参照周只取未冻结周、CSV 导入不抹掉 `recSetsOverride`。反向验证 `python tools/_sabotage_c2.py 1..6`：六组故障分别打红 Q1 / Q4 / Q2 / Q6 与 S11（第 5、6 组改的是生成物，S5「成品 == 重生成」同时变红属预期连带）。
- **D4 的存储侧**（C3）：光登记 `inactiveWeeks` 只保住「这台设备上那套 state 里的周数据没被删」；从外部工作簿换进来的整份计划被顶掉时，它的**六表原文**在 App 里没有落点，于是「换错了改回来」只能求用户重发文件。第四分片 `roast_plan_archive.json` 补这个洞：`archivePush(plan, meta)` 收六表齐全的字典（表名仍取自 `PLAN_SCHEMA.sheet_order`），新→旧环形保留，单份 >320 KB 拒收、条数 >8 与整片 >512 KB 从最旧淘汰，全部上限由测量定 —— 一份 16 周计划的字典 211,435 字节、同期账本分片 92,214 字节。三条硬约束：不进 `state`、不进 `WORK_KEYS`（因此不参与 CSV 导出、不被清账本带走）、只走与其余三片同一条 `writeSlice` 原子路径（`READONLY` 阻断态一律不写，读侧坏文本只告警且**绝不回写覆盖磁盘原文**）。行为由 `v3v.js` 的 **U 段（11 项）**守住：U1 空分片不落地 / U2 从盘重读逐字节相同 / U3 归档不参与账本 / U4 单份超限拒绝且不改盘 / U5 六表少一张拒收 / U6 条数淘汰 / U7 字节淘汰且不越线 / U8 坏分片降级+告警+原文不动 / U9 阻断态不写 / U10 显式删除后从盘重读消失 / U11 清空回报份数。反向验证 `python tools/_sabotage_c3.py 1..8` 分别打红 U6 / U7 / U4(+U5) / U5 / U8 / U9 / `M10`+S12 / **只有 S12**（第 8 组把 `savePlanArchive` 拼错一个字母：JS 静默回落到 localStorage，`v3v` 实测 174 全绿 —— 跨语言漂移只有 S12 看得见，这正是它存在的全部理由）。C4 的 `importPlanFromXlsxBytes` 在替换前调用 `archivePush`、`restoreLastArchivedPlan` 从这份归档回到 `applyStructure`。

---

## 13. AI 提示词模板（可直接整段粘贴）

把下面这段连同你的动作清单一起发给任意 AI。**它已经内嵌了硬约束，不需要再附本文件。**

````text
你要为一个力量举周期训练 App 生成训练计划文件。严格遵守下面的契约，只输出规定的表，不要任何解释性散文、不要 Markdown 表格、不要代码块以外的文字。

## 输出形态
输出 4 个 CSV 文件的内容，每个文件前用一行 `===文件名===` 开头（例如 `===Profile.csv===`）。
分隔符是英文逗号；字段里若含逗号或引号，用双引号包裹并把内部引号翻倍；字段内**禁止换行**。
第 1 行必须是表头，逐列与下面给出的列名序列完全一致，顺序不得改动、不得增删列。

## 1) Profile.csv —— 列：field,value,description
每行一个字段。必须包含（顺序不限，但缺一个就报错）：
schema_ver=RPL-Plan-v1
start_date=YYYY-MM-DD
gender=M 或 F
age=10..100 的整数
bw_kg=30..250
sq_1rm=0..600   （深蹲当前 1RM，S.* 主项的百分比基准）
bp_1rm=0..600   （卧推当前 1RM，B.* 主项的百分比基准）
dl_1rm=0..600   （硬拉当前 1RM，D.* 主项的百分比基准）
可选字段（不给就用默认）：plan_weeks、height_cm(175)、init_bw_kg(=bw_kg)、target_bw_kg(0)、
equip(classic|equipped)、recovery、ohp_1rm(自动=mround(bp_1rm*0.72,2.5))、init_sq/init_bp/init_dl(=对应1rm)、
target_sq/target_bp/target_dl(0)、bar_kg(10|15|20|25|30|35|40，默认20)、collars(TRUE|FALSE，默认FALSE)、motto。
不要发明新字段名（未知的会被忽略并警告）。

## 2) Blocks.csv —— 列：block_id,cycle_type,name_zh,name_en,work_weeks,deload_weeks,work_mode,deload_mode,base_rpe,rpe_step,deload_rpe
一行一个周期块，按时间顺序。
- block_id：B1、B2……（会被按行序重编，可留空）
- cycle_type 只能是：Hyper / Strength / Transmute / Peak / Custom
- name_zh 必填（中文块名）；name_en 可空
- work_weeks 1..24 必填；deload_weeks 0..4（默认 0）
- work_mode / deload_mode 必须取自下面的 mode 白名单，可留空（减载默认 T1.DL）
- base_rpe / deload_rpe 5.0..10.0（默认 7.0 / 6.0）；rpe_step 0..1（默认 0.25）
所有块的 (work_weeks + deload_weeks) 之和 = 总周数 N，必须 1..52，且与 Profile.plan_weeks（若填了）严格相等。

## 3) Days.csv —— 列：day_id,label,title_zh,title_en,weekday_offset,focus_tags,forbid_heavy_sbd,forbid_t1_main,upper_only,deload_cap
- day_id 只能是 A B C D E F 且不重复，最多 6 行
- weekday_offset：0=Mon 1=Tue 2=Wed 3=Thu 4=Fri 5=Sat 6=Sun
- focus_tags 逗号分隔，只能用：tag_sbd_heavy / tag_sq_quad / tag_bp_upper / tag_dl_post / tag_vari_weak / tag_hyper_acc / tag_power_gpp / tag_deload_rec
- 最后四列是布尔：TRUE 或 FALSE（不是 yes/no/1/0）
- 减载日必须 forbid_heavy_sbd=TRUE 或打 tag_deload_rec，且当天不得出现 Top.* / T1.3x3 / T1.5x5 / T1.6x6 / SS / SL，target_rpe 不得 > 7

## 4) Workouts.csv —— 列：week,day,seq,row_idx,tier,mode,category,movement,pct_1rm,load_kg,sets,reps,rx_text,target_rpe,prog_rule,actual_reps,actual_rpe,done_sets,done,notes
一行一个动作。建议只填 week, day, seq, mode, category, movement, pct_1rm（或 load_kg）, reps, target_rpe, notes，
其余（row_idx/tier/sets/prog_rule/actual_reps/actual_rpe/done_sets/done）留空，由 App 补齐。
- week 1..N 整数；day 必须在 Days.csv 里；同一 (week,day) 内 seq 从 1 递增且不重复
- mode 白名单（24 个，必须逐字一致）：
  Top.Single Top.Set Top.Test
  T1.Mod T1.3x3 T1.5x5 T1.6x6 T1.Def.1 T1.Def.2 T1.Def.3 T1.DL
  T2.Mod T2.Vol T2.Def T2.Tr T2.DL
  T3.Mod T3.Def T3.Tr T3.DL
  RTS.1 RTS.2 RTS.3 Custom
- category 白名单（33 个，必须逐字一致，含大小写与点号）：
  S.Main B.Main D.Main
  S.Vari.Start S.Vari.Mid S.Vari.End S.Vari.Balance
  B.Vari.Start B.Vari.Mid B.Vari.End B.Vari.Control
  D.Vari.Start D.Vari.Mid D.Vari.End D.Vari.Power
  S.Core S.Quads B.Pecs B.Delts B.Triceps B.Rotator
  D.Lats D.LowerBack D.GluteHam D.Forearms
  SBD.UpperBack SBD.Power SBD.Sled
  S.Calves S.GluteMed Hyper.Biceps Hyper.LatDelts Unmapped
- movement：优先用 App 动作库的英文原名（例：Low-bar Squat / Conventional Deadlift / Mid-grip Bench /
  Spoto Bench / Pendlay Row / Nordic Curl / Hanging Leg Raise / Cable Pushdown / Seated Leg Press）。
  写库里没有的名字只会得到拼写警告，不会报错，但请尽量准确。
- pct_1rm：**首选强度写法**，0..1.5 的小数，也可写 "70%"。对 category 为 S.Main / B.Main / D.Main 的行，
  必须给 pct_1rm 或 load_kg 之一（都不给 = 报错）。
- load_kg：0..600。规则：**pct_1rm 优先**，App 会用 mround(对应主项1rm × pct_1rm, 2.5) 覆写 load_kg；
  两者都给且偏差 > 5kg 只会警告。想让重量落在 2.5 的整数倍上，就只给 pct_1rm。
- sets / reps / target_rpe：sets 0..20、reps 0..100、target_rpe 5..10。留空时 reps 取 mode 的默认次数、
  target_rpe 按所在周取该块的 base_rpe（减载周取 deload_rpe）。
- done 布尔；notes 自由文本（禁止换行）。

## 硬规则（违反会报错或被覆写）
1) 列名与列序逐字照抄，不许增删列、不许改顺序、不许翻译列名。
2) **每行的字段个数必须等于该表表头的列数**（Workouts 恒为 20）。空列写成连续逗号，行尾的空字段一个都不能省 —— 少一个逗号，后面的值整体左移，报出来的是「应为数字」而不是「你漏了一列」。
3) 布尔只写 TRUE / FALSE。
4) 数字用小数点；`70%` 等价 0.70；重量步长 2.5kg。
5) `Profile.csv` 每行 3 个字段（`field,value,description`），没有备注也要以逗号结尾。
6) 不要输出 `Telemetry.csv` / `Armor.csv`：它们是可选表，不填即空遥测 + 默认装甲定义。
7) 每个训练日至少 1 个动作；`.Main` 主项行的强度必须明确（pct_1rm 或 load_kg）。
8) 减载周：mode 用 T1.DL / T2.DL / T3.DL，或让该日 forbid_heavy_sbd=TRUE，target_rpe ≤ 7，禁 Top.*/3x3/5x5/6x6。
9) 主项次数分配：Top.* 与 T1.3x3/T1.5x5/T1.6x6 是重负荷（1–6 次）；T2.* 是 8–12；T3.* 是 15–20；
   辅助/肌肥大用 T2.Mod、T3.Mod、Hyper.*、S.Core/D.Lats 等分组。
10) 动作数量：每个训练日 6–12 行为宜；一日 1 个主项（`.Main` 或 `Top.*`）+ 变化项 + 辅助 + 孤立。
11) 周结构：先高容量（Hyper），再力量（Strength），赛前用 Transmute/Peak；最后一周或每 4 周插一个减载周。

## 自检清单（输出前逐条核对）
- [ ] 4 个文件的表头与本提示词逐字一致
- [ ] 每行字段数 = 该表表头列数（Workouts 20、Blocks 11、Days 10、Profile 3）
- [ ] Workouts 里每个 day 值都在 Days.csv 出现；每个 week 在 1..N
- [ ] 每个 (week,day) 的 seq 从 1 连续不重复
- [ ] 所有 mode / category / cycle_type / focus_tag 都在白名单里（大小写、点号、连字符）
- [ ] 所有 `.Main` 行有 pct_1rm 或 load_kg；无重复 (week,day,row_idx)（若留空 row_idx 则不触发）
- [ ] Profile 8 个必填字段齐全；plan_weeks（若填）= Blocks 周数之和
- [ ] 减载日没有 Top.*/T1.3x3/T1.5x5/T1.6x6，且 target_rpe ≤ 7

## 现在的任务
周期长度：{N} 周。训练日：{列出 A/B/... 各日主题}。
运动员数据：性别 {M/F}、年龄 { }、体重 {kg}、深蹲 1RM {kg}、卧推 1RM {kg}、硬拉 1RM {kg}。
动作安排（按日给出，格式「动作名 | 分组模式 | 强度%1RM 或 负荷kg | 次数 | 备注」）：
{在这里贴上你的动作清单}
只输出 4 个 CSV 文件内容，不要多余文字。
````

投喂给你的 AI 之前，**先用工具验一遍**：把四份 CSV 存进一个目录（文件名必须叫 `Profile.csv`、`Blocks.csv`、`Days.csv`、`Workouts.csv`），跑

```bash
cd mobile/tools
python plan_xlsx.py build --in <那个目录> --out plan_ok.xlsx --state-out plan_state.json
python plan_xlsx.py roundtrip plan_ok.xlsx
```

`build` 报 `0 error / 0 warning`、`roundtrip` 报「差异 0 格」，才把 `plan_ok.xlsx` 交给 App。

---

## 14. 最小可用样例（本文示例已实测跑通）

四张核心表、3 周、A/B 两日，`Profile` 只给必填 8 项。存成目录里的 `Profile.csv` / `Blocks.csv` / `Days.csv` / `Workouts.csv`：

```csv
# Profile.csv
field,value,description
schema_ver,RPL-Plan-v1,
start_date,2026-01-05,
gender,M,
age,24,
bw_kg,82.5,
sq_1rm,140,
bp_1rm,95,
dl_1rm,170,
```

```csv
# Blocks.csv  —— 2 个训练周 + 1 个减载周 = 3 周
block_id,cycle_type,name_zh,name_en,work_weeks,deload_weeks,work_mode,deload_mode,base_rpe,rpe_step,deload_rpe
B1,Strength,力量,,2,1,,,7.5,0.25,6.5
```

```csv
# Days.csv
day_id,label,title_zh,title_en,weekday_offset,focus_tags,forbid_heavy_sbd,forbid_t1_main,upper_only,deload_cap
A,Mon,蹲重日,Squat Heavy,0,tag_sbd_heavy,FALSE,FALSE,FALSE,FALSE
B,Thu,推重日,Press Heavy,3,tag_bp_upper,FALSE,FALSE,FALSE,FALSE
```

```csv
# Workouts.csv —— 每行必须凑满 20 个字段，末尾连续逗号不能省
week,day,seq,row_idx,tier,mode,category,movement,pct_1rm,load_kg,sets,reps,rx_text,target_rpe,prog_rule,actual_reps,actual_rpe,done_sets,done,notes
1,A,1,,,T1.Mod,S.Main,Low-bar Squat,85%,,,,,,,,,,,
1,A,2,,,T2.Mod,S.Quads,Hack Squat,,60,,10,,,,,,,,
1,B,1,,,Top.Set,B.Main,Mid-grip Bench,75%,,,,,,,,,,,
3,B,1,,,T1.DL,B.Main,Mid-grip Bench,50%,,,,,,,,,,,减载
```

> 少写一个逗号，`notes` 就滑进 `actual_reps`，报的是「应为数字，实为 '减载'」而不是「你漏了一列」。

`python plan_xlsx.py build --in <目录> --out plan.xlsx --state-out plan.json` 实测：`3 周 / 4 动作行`、`0 error / 0 warning`；`roundtrip` `572 格 / 572 格 / 差异 0 格`。state 里的关键观测：

| 观测 | 值 | 来源 |
|---|---|---|
| `structure.totalWeeks` / `profile.planWeeks` / `daysPerWeek` | 3 / 3 / 2 | Blocks 之和；`plan_weeks` 未填也按本次算（§9） |
| 周1 A 行1：`load` / `row` / `targetRpe` / `rx` | 120.0 / 9 / 7.5 / `3×5+` | `mround(140×0.85, 2.5)`；`first[A]+seq−1`；块 `base_rpe`；`proto` 兜底 |
| 周1 A 行2：`load` / `reps` | 60.0 / 10.0 | 非主项：`load_kg` 就是绝对负荷 |
| 周1 B：`load` / `row` | 72.5 / 21 | `mround(95×0.75, 2.5)`；`first[B]` |
| 周3 B：`targetRpe` / `load` / `notes` | 6.5 / 47.5 / `减载` | 减载周取 `deload_rpe`；`mround(95×0.50, 2.5)` |
| `bio.day` A / B | `Mon` / `Thu` | `weekday_offset` → `weekday_labels` |
| `profile.ohp` | 67.5 | `mround(95×0.72, 2.5)` |
| `aux` | seed 的 10 项 | `Armor` 缺表回落 |
| `structure.inactiveWeeks` | `[4..16]` | base seed 是 16 周、本次 3 周 → **D4 冻结**：旧周数据留在 state，不进交换文件 |


---

## 附录 A · App 动作库原名（240 个不重复名 / 259 条分类映射）

> 从 [tools/seed.json](../tools/seed.json) 的 `lib.acts` 现值导出，按 `category` 分组；`\|` 是同一分组内的名字分隔符（有些原名里本身就含 `/`）。
> 少数动作名横跨两个分组，所以「259 条映射、240 个不重复名」。

| category | 数量 | 动作名（`\|` 分隔） |
|---|---|---|
| `S.Main` | 2 | High-bar Squat \| Low-bar Squat |
| `S.Vari.Start` | 6 | Anderson Squat \| Box Squat \| Cyclist Squat \| Paused Squat \| Tempo Squat \| Zercher Squat |
| `S.Vari.Mid` | 5 | Front Squat \| Kang Squat \| Narrow-stance Squat \| Pause Above Parallel Squat \| Pin Squat |
| `S.Vari.End` | 9 | Banded Squat \| Cossack Squat \| Hatfield Squat \| Leverage Squat (V-Squat) \| Low-bar Squat \| Pendulum Squat \| Skater Squat \| Squat & Calf Raise Machine \| Wide-stance Squat |
| `S.Vari.Balance` | 5 | Belt Squat \| Cambered-Bar Squat \| Overhead Squat \| Safety-Bar Squat \| Zombie Squat |
| `B.Main` | 2 | Mid-grip Bench \| Ultra-Wide-grip Bench |
| `B.Vari.Start` | 6 | Dead Bench \| Fat Bar Bench Press \| Long Paused Bench \| Panatta Multi-Grip Flat Press \| Tempo Bench \| Wide-grip Bench |
| `B.Vari.Mid` | 5 | Cambered Bar Bench Press \| Floor Press \| Incline Bench Press \| Pin Bench \| Spoto Bench |
| `B.Vari.End` | 6 | Board Press \| Close-Grip Floor Press \| Narrow-Grip Bench \| Plate-Loaded Decline Press \| Slingshot Bench \| Ultra-Wide-grip Bench |
| `B.Vari.Control` | 6 | Band-Resisted Bench Press \| Cluster Bench \| Feet-Up Bench \| Larsen Press \| Neutral-Grip DB / Machine Press \| Touch&Go Bench |
| `D.Main` | 3 | Conventional Deadlift \| Sumo Deadlift \| Semi-Sumo Deadlift |
| `D.Vari.Start` | 6 | Deficit Deadlift \| Dumbbell Deadlift \| Halting Deadlift \| Kettlebell Deadlift \| Snatch-Grip Deadlift \| Trap-Bar / Leverage Squat Pull |
| `D.Vari.Mid` | 6 | Narrow Sumo Deadlift \| Paused Deadlift \| Romanian Deadlift \| Snatch-Grip Block Pull \| Semi-Sumo Deadlift \| Tempo Deadlift |
| `D.Vari.End` | 6 | Banded / Reverse-Band Deadlift \| Block Pull \| Deadlift-Bar Pull (Whip Bar) \| Dumbbell Rack Pull \| Good Morning \| Rack Pull |
| `D.Vari.Power` | 5 | Box Deadlift (Vert Pull) \| Cluster Deadlift \| Kettlebell Swing \| Power Clean \| Sumo Deadlift |
| `SBD.UpperBack` | 15 | Bent-Over Barbell Row \| Chest-Supported Row (Elbows Out) \| Face Pull \| Hoist ROC-IT Mid Row \| Inward Converging Seated Row \| Iso-Lateral Plate-Loaded Row \| Kelso / Barbell Shrug \| Meadows Row \| One-Arm Dumbbell Row \| Pendlay Row \| Seal Row \| Seated Row \| Single-Arm Cable Row \| Smith Machine Shrug \| T-Bar Row |
| `S.Core` | 14 | Ab Wheel Rollout \| Bird Dog \| Cable Crunch \| Cable Woodchop / Lift \| Dead Bug \| Decline Bench Sit-Up / Crunch \| Dragon Flag \| GHD Sit-Up \| Leverage Ab Crunch Machine \| Machine / Hanging Leg Raise \| Pallof Press \| Side Plank \| Suitcase Carry \| Weighted Plank |
| `D.Lats` | 13 | Chin-Up \| Iso-Lateral Front Lat Row \| Meadows Row \| Plate-Loaded High Row \| Plate-Loaded Vertical Pulldown \| Pull-Up \| Pull-up (Standing Assisted) \| Rope Lat Prayer \| Scissor Converging Pulldown \| Straight-Arm Pulldown \| Technogym Vertical Traction \| Towel-Grip Pull-Up \| Wide / Neutral Lat Pulldown |
| `D.GluteHam` | 15 | 45-Degree Back Extension \| Barbell Hip Thrust \| Booty Builder Split Deadlift \| Cable Glute Kickback \| Cable Pull-Through \| Glute-Ham Raise / Nordic Curl \| Kettlebell / DB Swing \| Kneeling Single-Leg Curl \| Machine Hip Thrust (Glute Drive) \| Natural Leg Curl \| Romanian Deadlift \| Seated Leg Curl \| Single-Leg RDL \| Standing Single-Leg Curl \| Stiff-Leg Deadlift |
| `S.Quads` | 14 | Belt Squat \| Copenhagen Plank \| Dumbbell Bulgarian Split Squat \| Hack Squat \| Heels-Elevated Goblet Squat \| Leg Extension \| Leg Press \| Leverage Squat (V-Squat) \| Machine Hip Adduction \| Seated Leg Press \| Single-Leg Leg Press \| Smith Machine Squat (Feet Forward) \| Smith Reverse Lunge \| Walking Lunge / Step-Up |
| `B.Pecs` | 15 | Cable Fly (Low-to-High / Mid) \| Dip (Standing Assisted) \| Dumbbell Bench Press \| Dumbbell Squeeze Press \| Incline Bench Press \| Incline Cable Fly \| Incline Dumbbell Press \| Machine Chest Press \| Nautilus Leverage Press \| Panatta Multi-Grip Flat Press \| Pec Deck \| Plate-Loaded Decline Press \| Plate-Loaded Incline Press \| Rotary Converging Chest Press \| Weighted Dip |
| `B.Delts` | 9 | Bradford Press \| Cable Y-Raise \| Landmine / Arnold Press \| OHP \| Pin-Loaded Machine Shoulder Press \| Plate-Loaded Shoulder Press \| Seated Barbell / Smith OHP \| Seated DB Shoulder Press \| Z-Press |
| `B.Triceps` | 13 | Cable Pushdown \| Close-Grip Floor Press \| Cross-Body Dual Cable Extension \| JM Press (Barbell / Smith) \| Machine Triceps Dip / Extension \| Overhead Cable Extension \| Plate-Loaded Overhead Triceps Extension \| Rolling DB / Tate Press \| Rolling Triceps Extension \| Skull Crusher \| Smith Close-Grip Bench \| Tate Press \| Weighted Dip |
| `D.LowerBack` | 12 | 45-Degree Back Extension \| Back Extension (GHD) \| Good Morning \| Good Morning from Pins \| Jefferson Curl \| Machine Back Extension \| Plate-Loaded Roman Chair Extension \| Reverse Hyper \| Seated Good Morning \| Snatch-Grip RDL \| Suitcase Deadlift \| Zercher Good Morning |
| `D.Forearms` | 10 | Barbell Static Hold \| Deadlift Hold \| Farmer's Carry \| Fat Bar Hold \| Plate Pinch \| Reverse Wrist Curl \| Suitcase Carry \| Thick-Bar Hold \| Towel-Grip Pull-Up \| Wrist Curl |
| `Hyper.Biceps` | 11 | Bayesian Cable Curl \| Chin-Up \| Cross-Body Hammer Curl \| EZ-Bar / Barbell Curl \| Hammer Curl \| Incline DB Curl \| Leverage / Machine Bicep Curl \| Preacher Curl \| Reverse Curl \| Spider Curl \| Zottman Curl |
| `Hyper.LatDelts` | 9 | Behind-the-Back / Leaning Cable Raise \| Bent-Over Reverse Fly \| Cable Lateral Raise \| Lu Raise \| Multi / Seated Machine Lateral Raise \| Reverse Pec Deck \| Seated DB Lateral Raise \| Standing DB Lateral Raise \| Standing Machine Lateral Raise |
| `B.Rotator` | 8 | Band External Rotation \| Cable External Rotation \| Face Pull \| Full Can Raise \| Overhead Band Pull-Apart \| Prone Y-T-W Raise \| Side-Lying External Rotation \| Sleeper Stretch |
| `S.GluteMed` | 8 | Band Lateral Walk \| Clamshell \| Hip Airplane \| Lateral Step-Down \| Machine Hip Abduction \| Monster Walk \| Side-Lying Hip Abduction \| Standing Cable Hip Abduction |
| `S.Calves` | 3 | Seated Calf Raise \| Single-Leg Calf Raise \| Standing Calf Raise |
| `SBD.Power` | 7 | Box Jump \| Broad Jump \| Jump Squat \| Med Ball Slam \| Plyo Push-Up \| Rotational Med Ball Throw \| Vertical Jump |
| `SBD.Sled` | 4 | Prowler Sprint \| Sled Drag \| Sled Pull \| Sled Push |
| `Unmapped` | 1 | Unmapped |

## 附录 B · 装甲（Armor）10 项定义域

`state.aux` 的 4 个 `domain`（`CARDIO RESPIRATORY` 3 项、`MOBILITY COORDINATION` 2 项、`PARASYMPATHETIC` 2 项、`HYPERTROPHY GAP-FILL` 3 项），共 10 项、`item_idx` 0–9。缺 `Armor` 表时导入原样回落这 10 项，**多数计划不必写这张表**；要改打勾节奏时才写。

## 附录 C · `row_idx` 几何（与 `wkbook.py` 对账）

`row_idx.first`：`A=9, B=21, C=33, D=45, E=57, F=69`，通式 `first(day_id) + (seq − 1)`，等价 `9 + 12*(n−1)`。
A–D 与 `mobile/tools/wkbook.py::DAYS` 的 `first` 逐值一致（对账来源在契约 `row_idx.source` 里写着）；E/F 是契约新造（`wkbook` 只有 A–D 几何）。**任何代码里都不得再写第二遍**；`row_first_map()` 检测到与 `wkbook` 分叉直接抛 `ValueError`（见 T5.2）。
`row_idx` 是 App 用来关联 e1RM 历史的键，所以它是唯一「双向」列（导出算、导入也保留原值）。
