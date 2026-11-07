# 阶段编排统一方向 · RPL-Phase-v1（草案）

**状态**：方向文档，不是规范。§9 的七个问题裁决完才动代码；裁决后另写 `RPL-Phase-v1` 契约与规范。
**一句话**：把「计划 / 做组模式 / 进阶规则 / 每阶段怎么排」从**四套各说各话的词汇表**收敛成**一个可执行的 Phase 对象**，让同一份编排在 Python、App、文档三处得到同一个数。

---

## 1 · 现状：四套词汇表，三条断链

下面是数出来的，不是印象。基线是 v0.08（`tools/seed.json` + `tools/template.html` + `tools/schema/RPL-Plan-v1.json`）。

| 词汇表 | 有几项 | 定义在哪 | 谁真的消费它 |
|---|---|---|---|
| `cycleType` 周期类型 | 5（Hyper/Strength/Transmute/Peak/Custom） | `gen_seed.py:45 BLOCK_PRESETS`、模板 `:3983 CYCLE_PRESETS` | 结构编辑器显示、`MODE_BY_CYCLE` 反推一个 workMode；模板内 15 处引用，**没有一处参与重量或组数计算**（组数推荐走 JTS 容量带，`cycleType` 只是随结果一起返回、用于显示与着色） |
| `proto` 做组模式 | 24 | 种子（源自 24 表工作簿） | 显示 `rx`/`sets`/`reps`/`tier`；字段并集只有这四个 |
| `prog_rules` 进阶规则 | 16 键（15 具名 + `_default`） | **只在契约 JSON 里**（`Workouts.prog_rules`） | Python 校验读它做提示；模板内出现 **0 次** |
| `strategyLib` 做组策略 | 27 条 + 27×5 适用性矩阵 + 209 辅助动作 | 种子（`组策略体系-v2.xlsx`） | 设置页只读浏览，**与 24 个 mode 没有任何引用关系** |
| `programLib` 经典计划 | 197 条 + 6 维规范 | 种子（`训练计划库-v2.xlsx`） | 只读浏览，与执行层零耦合 |
| `WEEK_TAG` 周标签 | 14 键 | 模板 `:1785` 硬编码 | 周胶囊着色 |
| `phase` 分期名 | 4（Accum/Intens/Peak/Deload） | 模板 `:3648` 由 `cycleType` 三元式现推 | **只有装甲推荐**（`computeArmorRecommendations`）读它 |
| `volMult` 容量系数 | 5（age/sex/strength/recovery/nutrition） | 模板 `:3421` | 乘成 MV/MEV/MAV/MRV 的缩放 —— **不含任何阶段输入** |

**四条断链（这是要修的东西）**：

1. **RPE 阶梯只活在一次性的种子生成里。** 每周目标 RPE 的真值是 24 表工作簿 G 列，`gen_seed.py:285-303` 把它读出来**回填**成 `blocks[].baseRpe`，`rpeStep` 则来自 `BLOCK_PRESETS` 里手写的常量。也就是说：`structure.blocks` 里的 `baseRpe / rpeStep / deloadRpe` 是**结果**，不是**输入**。模板里这三个字段各出现 **1 次**——就是 `:4139` 那个新建块的默认值对象，**没有任何代码消费它们**。用户在设置页改了块的 `baseRpe`，重量、RPE、显示统统不动。
2. **tier→RPE 的阶梯只有一份实现，且在 Python 侧。** `gen_seed.py:149 target_rpe_for()`：T1 取基准、T2 基准 −0.5、T3 基准 −1.0，下限 5.0。App 里同名的 `tierOf()`（`:2493`）**只用来选组间休息计时器**（T1/T2/T3），不参与 RPE。所以「改了 tier 会怎样」在两端答案不同。
3. **进阶规则是给人读的句子。** `"AMRAP>=8:+2.5kg|5-7:+0kg|<5:->T1.Def"` 存在契约里，没有任何解析器；24 个 mode 中 **9 个连这句都没有**（`Custom`、`RTS.1/2/3`、`T2.Vol`、`T2.Def`、`T2.Tr`、`T3.Def`、`T3.Tr`），`WEEK_TAG` 也漏了 **13 个**。漏掉的模式在周胶囊上落到未定义分支，进阶行为等于「按处方执行」。
4. **容量带不看阶段。** `volMult()`（`:3421`）= 年龄 × 性别 × 力量 × 恢复 × 营养 五个系数，乘到 `VOL_LANDMARKS` 上得到 MV/MEV/MAV/MRV —— **一个与周期相关的输入都没有**。同一个人状态不变时，B1 肌肥大期和 B4 冲刺期拿到的建议组数区间**完全相同**；「这个阶段该多练还是少练」只体现在种子的死值里，不体现在推荐里。这是「每阶段该如何安排」最直接的缺口。

**净效果**：这 16 周计划里每一格的重量与 RPE，是**一次性烘焙进种子的死值**。App 知道 `baseRpe`、知道 `prog_rules`（通过注入的 `PLAN_SCHEMA`）、知道 `proto`，但**没有任何一条路径把它们算成下一周该做什么**。所谓「统一」，就是让这条路径存在且只有一条。

---

## 2 · 根因（三句话）

- 项目从「把一张 Excel 忠实搬到手机上」起步，**展示层先于计算层**长出来：种子是权威，App 是镜子。
- 后来加的每一套词汇表都各自找地方落地（预设表在 `gen_seed`、标签在模板、规则在契约），**没有引入过一层「编排语义」**，所以谁也不引用谁。
- 24 表工作簿是**唯一权威源**这条红线，客观上把「编排规则」留在了 Excel 单元格里，代码只能事后读取，不能事前生成。

---

## 3 · 目标模型：一个 Phase 对象

一个 Phase = 一个周期块内**行为一致**的一段。它把四件事钉在一起：**用什么模式做组、按什么规则进阶、这一阶段辅助与装甲怎么配比、什么时候结束**。

```jsonc
// RPL-Phase-v1 · 一个 phase 的完整形状（示例：B1 肌肥大适应期的第 2 周）
{
  "phase_id": "P-HYPER-BASE",
  "cycle_type": "Hyper",              // 沿用 5 值枚举，但它不再是「只有名字」
  "title": { "zh": "肌肥大适应期", "en": "HYPERTROPHY" },

  "span":   { "work_weeks": 3, "deload_weeks": 1 },
  "ramp": {                          // ← 取代「工作簿 G 列是 RPE 真值」
    "base_rpe": 7.0, "step": 0.25, "cap": 9.0,
    "deload_rpe": 6.0,
    "tier_offsets": { "T1": 0.0, "T2": -0.5, "T3": -1.0, "RTS": -0.5, "TOP": +0.5 },
    "floor": 5.0
  },
  "modes": {                         // ← 取代 MODE_BY_CYCLE 的四行硬编码
    "main": "T1.Mod", "deload": "T1.DL",
    "by_tier": { "T1": "T1.Mod", "T2": "T2.Mod", "T3": "T3.Mod" }
  },
  "progression": {                   // ← 取代给人读的句子，见 §5
    "T1.Mod": { "on": "amrap", "ge": 8, "then": { "load_kg": +2.5 } },
    "T2.Mod": { "on": "amrap", "ge": 10, "then": { "load_kg": +2.5 }, "else": { "hold": true } }
  },
  "volume": {                        // ← 把 strategyLib 从「资料」升成「引用」
    "strategy": "恒重组",             // strategyLib items 的 zh，必须能反查
    "sets_by_tier": { "T1": 3, "T2": 4, "T3": 4 },
    "landmark_mult": 1.15,           // ← 补断链 4：本阶段对 MV..MRV 的整体缩放，进 volMult 的乘积
    "week_curve": [1.0, 1.05, 1.10, 0.6]   // 相对容量，末位是减载周
  },
  "aux_mix": {                       // ← 辅助与装甲的阶段配比（现在只有固定 10 项）
    "domains": { "SBD": 2, "Hyper": 3, "Power": 1 },
    "armor": { "CARDIO RESPIRATORY": 2, "MOBILITY COORDINATION": 3,
               "PARASYMPATHETIC": 2, "HYPERTROPHY GAP-FILL": 3 }
  },
  "exit": {                          // ← 阶段出口判据：现在完全没有
    "any": [
      { "metric": "amrap_fail_streak", "ge": 2 },
      { "metric": "readiness", "lt": 0.7 },
      { "metric": "weeks_in_phase", "ge": 3 }
    ]
  },
  "label": { "tag": "B1 · HYPERTROPHY", "color": "#34D399" }   // ← 取代 WEEK_TAG 硬编码
}
```

**关键取舍**：`phase` 是**输入**，种子是**输出**。24 表工作簿继续当动作库与周表骨架的权威源（红线不动），但**「这一周该做什么组、多重、什么 RPE」由 phase 推导**，工作簿里对应的格降级为「人工覆盖值」——有覆盖用覆盖，没覆盖用推导。这样既守住「不删 `../data/*.xlsx`」，又让规则第一次真正拥有代码路径。

---

## 4 · 三份事实源怎么分工（不合并，划界）

| 事实源 | 管什么 | 不管什么 |
|---|---|---|
| `../../data/01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx`（24 表） | 动作库、周表骨架与行坐标、人工覆盖值 | 编排语义 |
| `tools/schema/RPL-Plan-v1.json` | **交换格式**：六表列名、枚举、区间、错误格式、往返保真 | 怎么算重量 |
| `tools/schema/RPL-Phase-v1.json`（拟新增） | **编排语义**：phase 档案、ramp、progression、配比、出口判据 | 文件格式 |

三者**互不重复**：Plan 说「字段长什么样」，Phase 说「这一阶段怎么做」，工作簿说「这个人实际排了什么」。
Phase JSON 与 Plan JSON 一样，由 `build_html.py` 注入成品（`const PHASE_SCHEMA`），Python 侧由 `plan_xlsx.py` 与新的 `phase.py` 共读——**同一份，三处消费**（决策 D7 的延续）。

---

## 5 · 进阶规则要变成能解析的东西

现状 16 条字符串的语法其实已经收敛成一种模式：`<条件>:<动作>|<条件>:<动作>|…`。方向是**把它形式化，而不是发明新语言**：

```
rule     := clause ( "|" clause )*
clause   := cond ":" action
cond     := "AMRAP" (">="|"<="|">"|"<"|==) INT | "全对完成" | "单组测试" | "否则"
action   := ("+"|"-"|":±") NUM "kg" | "+0kg" | "->" MODE_ID | "- >" NUM "RPE" | "hold"
```

- 落库形态用 JSON（`{"on":"amrap","ge":8,"then":{"load_kg":2.5}}`），**人类可读串由 JSON 反向渲染**，不再手写；现有 16 条串作为迁移输入，逐条转成结构后**逐字节回渲**比对，防翻译走样。
- 解释器**只写两份且必须同结果**：`tools/phase.py`（Python，产种子）与成品内 JS（App 算下一周）。两者由 gate 的一致性断言钉住（§10）。
- 覆盖缺口必须补齐：9 个无规则模式（`RTS.*` 三条本就是「按 RPE 自调节」的另一族，需要 `on:"rpe"` 条件；`T2/T3.Def/Tr/Vol` 是固定容量，`{"hold":true}`；`Custom` 显式 `_default`）。
- 歧义清单（转结构时必须逐条裁决）：`<5:->T1.Def` 的「切换到 T1.Def」是**下一周生效**还是**当场生效**；`- >0.5RPE` 是降目标 RPE 还是降实际 RPE 记录；`全对完成` 对 AMRAP 组如何定义。

---

## 6 · 覆盖矩阵补齐（可机械检查的部分）

| 缺口 | 数量 | 补法 |
|---|---|---|
| `proto` 无 `prog_rules` | 9 / 24 | 由所属 phase 的 `progression` 提供；phase 未覆盖则 `_default` 且 gate 报 warning |
| `proto` 无 `WEEK_TAG` | 13 / 24 | 标签改由 `phase.label.tag` 派生，`WEEK_TAG` 常量删除 |
| `cycleType` 无 `MODE_BY_CYCLE` 之外的映射 | 5 → 每 phase 一组 `modes.by_tier` | `MODE_BY_CYCLE` 删除 |
| `baseRpe/rpeStep/deloadRpe` 无人消费 | 3 字段 × 4 块 | 变成 `phase.ramp` 的输入并被真正计算 |
| `volMult` 不看阶段 | 5 系数 | `phase.volume.landmark_mult` 作为第 6 个乘子接入（默认 1.0，不写就不改变现有行为） |
| `strategyLib` 与 mode 零引用 | 27 条 | `phase.volume.strategy` 建立外键；矩阵 `27×5` 用于校验「该阶段该 lift 能不能用这策略」 |

---

## 7 · 落地顺序（建议作为 Phase D，排在 v0.09 之后）

**为什么不塞进 v0.09（Phase C）**：C 是**纯旁路**——六表读写不进运行时算路，出问题最多是导入失败，不会改任何人看到的重量。D 一上来就**改数据语义**（种子从「权威」变「产物」），两者混在一个版本里，回归红的时候分不清是引擎错还是编排错。v0.10 是全量逻辑 + UI 测试发版，也不该带语义变更。

| 步 | 做什么 | 可验证边界 |
|---|---|---|
| PD1 | `tools/schema/RPL-Phase-v1.json` + `tools/phase.py`（解析器 + 求值器），**离线**，不碰 App | 16 条旧串 → 结构 → 回渲逐字节一致；24 mode 全覆盖 |
| PD2 | `gen_seed.py` 改吃 phase：`target_rpe_for`、RPE 阶梯、模式选择全部由 `phase.py` 提供；工作簿对应格降级为覆盖值 | 新旧种子**逐格 diff 必须为空**（纯重构证明），非空即说明语义漂移 |
| PD3 | 成品注入 `const PHASE_SCHEMA`，App 内实现同一个求值器 | gate 新增「三端一致」断言（§10） |
| PD4 | 「下一周该练什么」在 App 内可算（先只读展示，不改写存档） | v3v 新增 N 段行为断言 |
| PD5 | 结构编辑器把 `baseRpe/rpeStep` 变成**真输入**，改完立刻反映到处方 | 用户可感知，需 UI 全量测试 → 归 v0.11 |

---

## 8 · 明确不做

- **不做自动排课 AI**：phase 是人写的档案，App 只按档案算，不发明档案。
- **不把 `programLib` 197 条计划可执行化**：它是参考库，保持只读；要引用就显式写成 phase 档案，不做「点一下就换成 GZCLP」。
- **不把 `strategyLib` 变成硬约束**：`taboo` 字段继续是文字提示，最多进 warning。
- **不动 24 表权威源、不动六表契约的列序**：D 只新增事实源，不改既有格式。
- **不在 v0.10 之前动 UI**。

---

## 9 · 需要你裁决的七件事

1. **RPE 真值归属**：工作簿 G 列降级为「覆盖值」、`phase.ramp` 升为输入——接受吗？（不接受则 §3 的模型不成立）
2. **phase 粒度**：一个 block 一个 phase（当前 4 块 4 phase），还是 block 内可再分（如 Peak 期内部「冲刺 2 周 + 测验 1 周」）？
3. **进阶生效时机**：AMRAP 未达标 → 切 `T1.Def`，是**当场这组**生效，还是**下周**生效？（§5 歧义 1）
4. **`RTS.*` 三条**：并入统一 DSL（加 `on:"rpe"` 条件），还是承认它是另一族、单独写规则？
5. **`tier→RPE` 偏移表**：`T1 0 / T2 −0.5 / T3 −1.0` 现在是 `gen_seed.py` 的硬编码，进 phase 后允许按 phase 覆写吗？
6. **出口判据（`exit`）**：v0.11 只做「提示该减载了」，还是允许自动进入下一 phase？后者会改用户账本，风险等级不同。
7. **版本号**：PD1–PD3 是 v0.11，还是把 v0.10 的全量测试之后顺延？（当前排期：0.09 = C，0.10 = 全量逻辑 + UI 测试）

---

## 10 · 怎么证明「真的统一了」

新增 gate 两套（接在 D8 `xlsxv.js` 之后）：

- **D9 覆盖完备**：24 个 `proto` 模式，每个都能查到 `phase`、`progression`、`label` 三项，缺任一即 FAIL（今天的实测是 9 / 13 / 13 缺）。
- **D10 三端一致**：同一份种子 + 同一组输入（周次、tier、AMRAP 结果、RPE），
  `tools/phase.py` 的推导值 == `gen_seed.py` 烘进种子的值 == 成品内 JS 的推导值，
  **逐格相等**；不等就把两边算出的数一起打出来。这条断言是 §7（PD1–PD5）每一步的验收闸门，也是防止「Python 改了 JS 忘改」的唯一机制。
- 反向验证照旧：`_sabotage_d*.py` 注入「改 tier 偏移只改一处」「删某个 phase 的 progression」等故障，确认 D9/D10 会红。

---

## 附 · 本文引用的位置（便于核对）

- `mobile/tools/gen_seed.py:45` `BLOCK_PRESETS`（cycleType → workMode + rpeStep 的硬编码表）
- `mobile/tools/gen_seed.py:149` `target_rpe_for()`（tier→RPE 偏移，唯一实现）
- `mobile/tools/gen_seed.py:285-303` 从工作簿 G 列回填 `baseRpe` / `deloadRpe`
- `mobile/tools/template.html:1785` `WEEK_TAG`（14 键硬编码）· `:2493` `tierOf()` · `:3648` `phase` 三元式
- `mobile/tools/template.html:3983` `CYCLE_PRESETS` · `:3987` `MODE_BY_CYCLE` · `:4139` 新建块默认值（`baseRpe/rpeStep/deloadRpe` 在模板里唯一的出现处）
- `mobile/tools/schema/RPL-Plan-v1.json` → `sheets.Workouts.prog_rules`（16 键）
- `mobile/tools/seed.json` → `proto` 24 / `lib.categories` 33 / `strategyLib.items` 27 / `programLib.items` 197
