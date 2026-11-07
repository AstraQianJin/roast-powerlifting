# 跑步模块（RUN）实施说明书

> 交接对象：实现者（人或模型）
> 目标版本：v0.99 之前任意一版
> 本文是唯一施工依据；与本文冲突的旧讨论一律作废。

---

## 0 · 一句话任务

在训练日页（DAY A/B/C/D，不含 AUX）加一张独立的跑步打卡卡：**DAY B = 轻松跑，DAY D = 300m 间歇**，处方按 9 周周期变化，强度用心率区间和配速表达，**不使用 RPE**。数据存本机账本，不进 CSV 26 列、不改六表契约。

---

## 1 · 已确认的用户事实（不要再问）

| 项 | 值 |
|---|---|
| 体重 | 87.5 kg，目标 82.5 kg，减重期 |
| 跑龄 | 半马以上，但已停跑数月，目前只跑 5K + 间歇 |
| 现有跑量 | 每周 2 次，无其他跑步/球类 |
| 目标 | 心肺健康优先，稳定每周两次，不追成绩 |
| 设备 | 手环（光学心率），跑步机为主 |
| 时间 | 练后 30 分钟内完成 |
| 伤史（按严重度） | 髂胫束联动膝 > 小腿后侧 > 髋 > 足底/跟腱，均已恢复 |
| 5K 基准 | 27:00，平均心率 180 |
| 300m 间歇基准 | 3 次，平均 72s |

**关键约束**：三十秒到三分钟的短间歇里，光学心率滞后且容易被步频锁死。因此：

- **轻松跑**：心率是权威，配速只是结果。
- **300m 间歇**：配速是权威，心率只用于判断组间恢复是否足够。
- 任何地方都不出现 RPE 字段或 RPE 文案。

---

## 2 · 心率区间

`HRmax` 默认 **190**，存在 `state.run.hrMax`，用户可改。区间按 HRmax 百分比现算，不写死数字：

| 区间 | %HRmax | @190 | 用途 |
|---|---|---|---|
| Z1 恢复 | 50–60% | 95–114 | 冷身、组间走 |
| Z2 有氧 | 60–70% | 114–133 | 轻松跑主力 |
| Z3 节奏 | 70–80% | 133–152 | 轻松跑上沿、节奏段 |
| Z4 阈值 | 80–90% | 152–171 | 间歇后段 |
| Z5 极限 | 90–100% | 171–190 | 300m 末段、5K 自测 |

区间判定函数 `runZone(hr)` 返回 `'Z1'…'Z5'` 或 `''`（无心率）。

---

## 3 · 9 周处方（唯一单源表）

实现为模板里的 `const RUN_PLAN = [...]`，索引 `week-1`，越界夹到首/末项。**不许在别处再抄一份周次数字。**

| 周 | DAY B 轻松跑 | DAY D 间歇（走100m + 跑300m） |
|---|---|---|
| W1 | 20 min，HR 120–135 | 3 次，均 78s，组间走到 HR ≤140 |
| W2 | 25 min，HR 120–135 | 3 次，均 76s |
| W3 | 30 min，HR 125–140 | 4 次，均 76s |
| W4 | 30 min，最后 5 min HR 145–155 | 4 次，均 74s |
| W5 | 30 min，中段 10 min HR 145–155 | 5 次，均 72s |
| W6（减载） | 20 min，HR ≤135 | 3 次，均 78s |
| W7 | 30 min 轻松；**5K 自测可选** | 4 次，均 71s |
| W8（减量） | 25 min，HR 125–135 | 3 次，均 72s |
| W9（测试周） | 20 min，HR ≤130 或跳过 | 2 次，均 74s，只激活 |

数据结构建议：

```js
const RUN_PLAN=[
  { easy:{min:20,hrLow:120,hrHigh:135,tempo:''},          interval:{reps:3,sec:78} },
  { easy:{min:25,hrLow:120,hrHigh:135,tempo:''},          interval:{reps:3,sec:76} },
  { easy:{min:30,hrLow:125,hrHigh:140,tempo:''},          interval:{reps:4,sec:76} },
  { easy:{min:30,hrLow:125,hrHigh:140,tempo:'last5'},     interval:{reps:4,sec:74} },
  { easy:{min:30,hrLow:125,hrHigh:140,tempo:'mid10'},     interval:{reps:5,sec:72} },
  { easy:{min:20,hrLow:0,  hrHigh:135,tempo:''},          interval:{reps:3,sec:78} },
  { easy:{min:30,hrLow:125,hrHigh:140,tempo:''},          interval:{reps:4,sec:71} },
  { easy:{min:25,hrLow:125,hrHigh:135,tempo:''},          interval:{reps:3,sec:72} },
  { easy:{min:20,hrLow:0,  hrHigh:130,tempo:''},          interval:{reps:2,sec:74} }
];
```

`hrLow:0` 表示只设上限。

### 3.1 配套换算（实现时现算，不存死数）

- 300m 配速：`sec/300m` → 每公里秒数 = `sec/0.3`；跑步机速度 km/h = `300/sec*3.6`。
- 轻松跑：30 min 跑 5.0km = 10.0 km/h；6:20/km = 9.5 km/h。
- 目标秒数对应速度（写进 UI 提示）：78s→13.8、76s→14.2、74s→14.6、72s→15.0、71s→15.2 km/h。
- 跑步机坡度固定 **1%**，写进处方行。

### 3.2 每次结构（全部塞进 30 分钟）

热身走/慢跑 3–5 min → 主课 → 冷身 3–5 min。
间歇日组间恢复：走 100m 是下限，**心率回到 ≤140 才开下一组**；没回到就继续走。

### 3.3 5K 自测（可选）

W7 标注为「可选」。不写成绩目标，只记录用时、平均心率、最大心率，作为趋势点。用户不测就按 30 min 轻松跑执行。UI 上必须显示「可选」字样，不能默认强制。

---

## 4 · 伤史规避（写进处方的说明行）

| 部位 | 规避 |
|---|---|
| 髂胫束 / 膝外侧 | 步频保持 170–180；只跑 1% 坡度，不做下坡；臀中肌激活每周 2 次（现有 GPP 已有） |
| 小腿后侧 | 速度渐进，W1–W2 不上 15 km/h；提踵每周 2 次；热身不足不许跑快 |
| 髋 | 跑前髋屈肌动态拉伸 |
| 足底 / 跟腱 | 不连续两天跑；晨起足底痛 → 当周降一档；跑后小腿放松 |

**疼痛闸门**：跑中或次日晨起疼痛 >2/10，当周处方降一档并重复一周，不跨档加量。

---

## 5 · 数据模型

### 5.1 形状

```js
state.run = {
  v: 1,
  hrMax: 190,
  days: { B:'easy', D:'interval' },
  logs: {
    '3-B': { week:3, day:'B', type:'easy', at:'2026-11-25', done:true,
             distKm:4.9, durSec:1800, hrAvg:132, hrMax:141, note:'' },
    '3-D': { week:3, day:'D', type:'interval', at:'2026-11-28', done:true,
             reps:4, avgSec:76, hrAvg:168, hrRecover:138, note:'' }
  }
}
```

- 键 = `week-day`，一周最多一条。
- `v` 现在就写，给以后加「比赛日 / 跑量统计 / 配速趋势」留迁移位。
- `logs` 里**保留未知字段**，不要整条重建，避免以后加字段时丢数据。
- `at` 是本地日期 `YYYY-MM-DD`，由记录当天现算。

### 5.2 登记与规范化

1. `WORK_KEYS` 加 `'run'`（长度 16 → 17）。
2. `IMPORT_KEEP_KEYS` 加 `'run'`。
3. **不进** `PLAN_OWNED_KEYS`：换计划不许清跑步记录。
4. `ensureShape()` 末尾加 `state.run = runNormalize(state.run);`。
5. `runNormalize()` 规则：
   - `v` 非数字 → 1；`hrMax` 夹在 150–220，缺省 190；
   - `days` 只认 B/D 两个键，值只认 `'easy'/'interval'`，非法回落默认；
   - `logs` 只保留 `/^[1-9]\d?-[A-F]$/` 的键；字段做数值夹紧；`done` 转布尔；
   - 任何异常都返回可用空结构，**不许抛错阻断启动**。
6. **不改 `SCHEMA_STAMP`**：这是纯加法键，和 `health` / `hpr` 同一类。

### 5.3 明确不碰

- `data/*.xlsx`、`seed.json`、`schema/*.json`、`SCHEMA_STAMP`、CSV 26 列、`rxlib.py`、`wkbook.py`。
- 跑步记录**不导出到 CSV**，也不进六表契约。
- 跑步不进 GPP 菜单、不进 `state.gpp`。

---

## 6 · UI 规格

### 6.1 位置

[template.html](../../mobile/tools/template.html) 当前第 1794–1795 行：

```html
<section id="exList"></section>
<button class="add" onclick="addExercise()">…</button>
```

在这两者之后、`<section class="card hidden" id="auxSec">` 之前插入：

```html
<section class="card hidden" id="runSec"></section>
```

### 6.2 显示条件

- `state.day === 'AUX'` → 隐藏。
- 当前 day 不在 `state.run.days` 里 → 隐藏。
- 其余情况显示，并在 `renderAll()` 的非 AUX 分支调用 `renderRun()`；`setLang()` 的局部重渲染也要调用。

### 6.3 卡片结构

```
┌ RUN · 跑步 ───────────────── W3 · DAY D ┐
│ [间歇]  走100m + 跑300m × 4              │
│ 目标 均 76s（14.2 km/h）· 组间走到 HR≤140 │
│ 跑步机坡度 1% · 热身5min + 冷身5min       │
│                                           │
│ 完成次数   [−]  4  [+]                    │
│ 平均秒数   [ 76 ] s                       │
│ 平均心率   [ 168 ] bpm                    │
│ 恢复心率   [ 138 ] bpm                    │
│ 备注       [                    ]         │
│ 合计 1200m · 5:04 · 配速 4:13/km          │
│                                           │
│ [ ✓ 完成打卡 ]                            │
│ 最近   W2 3次·76s   W1 3次·78s            │
└───────────────────────────────────────────┘
```

轻松跑日字段：`用时（mm:ss）/ 距离 / 平均心率 / 最大心率 / 备注`，派生行显示 `平均配速` 与 `心率区间`。距离可由用时和配速估算并允许手改。

### 6.4 交互

- 所有数字输入 `inputmode="numeric"`；用时输入接受 `mm:ss` 或纯秒。
- 输入用 `onchange`/`onblur` 落盘，不逐键写盘；打卡按钮立即写并 `haptic`。
- 已打卡状态：字段只读 + 顶部显示小结 + 一个不显眼的「撤销打卡」。
- 撤销只把 `done` 置 false，不删记录。
- 历史条只显示同类型最近 4 条，按 week 降序；点击历史条不跳转（本期不做详情页）。

### 6.5 文案

- 全部走 `L('中文','English')`，不许出现只有中文的节点。
- 视觉复用现有 `card / badge / mono / gold / dim` 令牌。
- 不新增主题色、不加渐变、不加新动效时长（S21 会查）。
- 新增 CSS 类必须全部被模板真实使用（S22 会查）。

---

## 7 · 代码落点清单

| 位置 | 动作 |
|---|---|
| `template.html` CSS 区（GPP 样式附近） | 新增 `#runSec` 与 `.run-*` 样式 |
| `template.html` 主 DOM | `#exList` / `.add` 之后插入 `#runSec` |
| `template.html` 常量区（`GPP_SCHEMA` 附近） | 新增 `RUN_PLAN`、`RUN_TYPES` |
| `template.html` 工具函数区 | 新增 `runNormalize()`、`runPlanOf()`、`runZone()`、`fmtPace()`、`fmtClock()` |
| `template.html` 渲染区（GPP 模块附近） | 新增 `renderRun()`、`runSaveField()`、`runToggleDone()`、`runSetReps()` |
| `WORK_KEYS`（约 3178 行） | 加 `'run'` |
| `IMPORT_KEEP_KEYS`（约 3187 行） | 加 `'run'` |
| `ensureShape()`（约 3721 行） | 末尾加 `state.run=runNormalize(state.run);` |
| `renderAll()`（约 6334 行） | 非 AUX 分支调用 `renderRun()` |
| `setLang()`（约 6001 行） | 非 AUX 分支调用 `renderRun()` |

> 行号会随版本漂移；以符号名为准。

---

## 8 · 回归与门禁

### 8.1 必须同步的既有断言

`v3v.js` 的 M10（约 512–530 行）：

- `WORK_KEYS.length===16` → `17`
- 增加 `WORK_KEYS.indexOf('run')>=0 && PREF_KEYS.indexOf('run')<0`

### 8.2 新增断言（建议 8 条，SECT='RUN'）

| ID | 断言 |
|---|---|
| RUN1 | `runPlanOf(1/5/9/99)` 按周取值并正确夹紧，减载周次数下降 |
| RUN2 | 300m 换算：`reps×300m`、总工作秒数、配速、跑步机 km/h 全部正确 |
| RUN3 | `runZone()` 在 190 下五个边界值判定正确，空心率返回空 |
| RUN4 | 打卡写入 `state.run.logs['w-d']`，字段齐全，`done=true` |
| RUN5 | 撤销打卡只改 `done`，记录与字段不丢 |
| RUN6 | 重新渲染/读回后记录一致（只读快照逐字节） |
| RUN7 | 导入新计划后 `run` 仍在（`IMPORT_KEEP_KEYS` 生效） |
| RUN8 | CSV 导出仍是 26 列，且不含 run 列 |

`EXP_N` 按实际新增条数同步（当前 481）。

### 8.3 断言必须能红

新增断言至少做一次反向验证：临时改坏 `RUN_PLAN` 的取值或换算系数，确认对应用例变红，再改回。把这次验证写进提交说明。

### 8.4 门禁命令

```bash
cd mobile
python tools/build_html.py
python tools/gate.py --static
python tools/gate.py
```

全量门禁必须 0 FAIL。碰原生层（输入法、返回键、文件选择）时另做真机验证；本模块不涉及。

---

## 9 · 验收判据

1. `gate.py --static` 与 `gate.py` 全绿，退出码 0。
2. DAY B 显示轻松跑卡，DAY D 显示间歇卡，AUX 不显示。
3. 打卡后杀进程重开，记录仍在。
4. 导入 `mobile/plans/` 里的计划后，跑步记录不丢。
5. CSV 导出仍是 26 列。
6. 切中英文，卡片全部文案跟着变。
7. 360dp 宽屏不横向溢出。
8. 间歇日能算出「4 次 × 76s = 5:04，配速 4:13/km，14.2 km/h」。
9. 减载周 W6 的次数与时长确实下降，不是只改文案。

---

## 10 · 边界（违反即返工）

- 不许用 RPE、1RM 百分比、组数这些力量训练口径写跑步处方。
- 不许把跑步塞进 GPP 菜单或 `state.gpp`。
- 不许改 CSV 26 列、六表契约、`SCHEMA_STAMP`、`data/*.xlsx`。
- 不许引入第三方库或网络请求。
- 不许手改 `assets/index.html`；必须改模板后跑 `build_html.py`。
- 不许覆盖 `release/` 里已有的 APK；出包按下一版号走 `pack.py`。
- 不许跳门禁、不许改门禁判据来「变绿」。

---

## 附录 A · ref 库扩充任务书（给子智能体 A）

**目标**：在现有 `ref/` 的 7 个分类下补中长跑内容，不新建第 8 个顶层分类。

- 归入 `02_研究与综述 / 03_计划与方法 / 04_技术与教练 / 06_书籍与预览`。
- 只收公开可下载的指南与开放论文；受版权教材只登记书名、作者、版次、目录级要点与出处，不下载整本。
- 必须覆盖：5K–半马周期化、轻松跑/阈值/间歇的强度分配、心率与配速关系、跑步机训练等效性、跑者伤后回归、减重期与跑量相容性。
- 产出后更新 `ref/README.md` 与 `ref/SOURCE_GUIDE.md` 的中长跑索引。
- 不改 `seed.json` 的 `canon` 出处链；不跑门禁；`ref/` 不入仓。

## 附录 B · 身体约束分析任务书（给子智能体 B）

输入就是本文第 1 节。产出三件事：

1. 复跑风险清单（髂胫束→小腿→髋→足底/跟腱），每条给触发条件与规避动作。
2. 「练后 30 分钟、跑步机、每周两次」下的跑量上限与加量节奏。
3. `HRmax=190` 是否合理，以及两周后用哪些实测数据校准。

不允许直接给训练计划，不允许写代码。

## 附录 C · 交接开场提示（直接复制给实现者）

> 读 `tmp/run-design/RUN_MODULE_SPEC.md`，按第 5–9 节施工。只改 `mobile/tools/template.html` 与 `mobile/tools/v3v.js`；改完跑 `build_html.py` 和两级 gate；新增断言先证明能红。不要改 `data/`、`schema/`、CSV 列、`SCHEMA_STAMP`。完成后贴出门禁输出、改动文件清单和 3 条验收证据。
