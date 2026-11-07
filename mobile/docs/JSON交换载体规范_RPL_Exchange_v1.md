# JSON 交换载体规范（RPL-Exchange-v1）

> v0.11 起，**JSON 是计划交换的唯一权威载体**：xlsx / CSV 降级为「视图 / 导出」，不再承载任何独占协议。
> 载体契约只有一份：[mobile/tools/schema/RPL-Exchange-v1.json](../tools/schema/RPL-Exchange-v1.json)。
> 前端读注入的 `const EXCHANGE_SCHEMA`，Python 读同一份文件（`plan_xlsx.load_exchange_schema()`）——
> 任何键名 / 键序 / 文件名模板 / MIME 的改动**只改这份 JSON**，两侧同时生效，不许硬编码第二份。

## 1 · 计划信封（plan envelope）

导出 = 单个自描述 JSON 文件，头部键序固定（AI / 人都能第一眼识别格式与版本）：

```json
{
 "format": "RPL-Plan",
 "schemaVersion": "RPL-Plan-v1",
 "exportedAt": "2026-11-03T01:36:25",
 "app": { "name": "RPL ExDark Pro", "version": "0.11" },
 "plan": { "Profile": [...], "Blocks": [...], "Days": [...], "Workouts": [...], "Telemetry": [...], "Armor": [...] }
}
```

- `plan` 载荷就是 [RPL-Plan-v1 六表契约](计划交换规范_RPL_Plan_XLSX.md)的字典形态——列名 / 枚举 / 约束仍以那份契约为准，本规范不复制第二份。
- `exportedAt` 仅用于人读溯源，不参与任何判定，导入侧忽略。
- 导出前自检：载荷过不了 `validatePlanDict` 就不产文件（宁可导不出，不可导出坏计划）。
- 确定性：同 `exportedAt` / `app.version` 两次导出逐字节相同，AI 侧可复算摘要。

### 版本演进规则

1. 载体升版必须**新增** schema 文件（不改旧文件），并在 `accepted` 列表登记。
2. 导入侧对未知 `schemaVersion` **整份拒收**，绝不静默降级。
3. 迁移说明写进本目录，`build_html.py` / `gate.py` 同步（指纹 `exc=` 摘要盯住「改了契约没重建」）。

## 2 · 训练日志 JSONL（v0.12 实现）

- 每行一条记录，行记录键 = CSV 26 列列名（与 `template.html` 的 `CSV_COLS` 同源，列序冻结）。
- 首行固定 `META` 头记录：`record_type=META` / `schema_ver=RPL-Log-v1` / `csv_protocol=v8.1` /
  `app_name` / `app_version` / `exportedAt`（必带键取自契约 `log_jsonl.header_record.required_keys`）。
- 记录内容由 `unifiedRecords()` 一处构建，CSV 导出与 JSONL 导出共读同一份，不各写一遍。
- **只导不入**：日志是历史事实的单向视图，App 不提供 RPL-Log 导入通道；Python 侧也只**独立校验**（`validate_log_jsonl`），不重建记录逻辑。

```jsonl
{"record_type":"META","schema_ver":"RPL-Log-v1","csv_protocol":"v8.1","app_name":"RPL ExDark Pro","app_version":"0.12","exportedAt":"2026-11-03T10:12:44"}
{"schema_ver":"1","record_type":"EXERCISE","week":1,"day":"A","row_idx":1,"movement":"High-bar Squat","load_kg":100,"target_rpe":7,"last_reps":5,"done":"1", ... 其余 CSV_COLS 键补 "" }
```

## 3 · 导出 → AI → 导入闭环（v0.12）

导入是**整份替换**，不是增量合并：

1. App 导出 `RPL_ExDark_v{VER}_plan.json`（信封）；AI 侧按 `format` / `schemaVersion` 自识别后改 `plan` 载荷。
2. 用户点设置页「JSON 计划（AI 交换）→ 导入」，选中 AI 改过的文件。
3. `onPlanJSONFile` → `importPlanFromJSONText`：`validateEnvelope`（必带键 / format / `schemaVersion` 在 `accepted` 内 / `app` 对象 / 头部键序）→ `validatePlanDict`（六表契约）→ **任一不过整份拒收，账本一个字都不动**。
4. 过闸后走 `adoptImportedPlan`：导入前的计划原文先进第四分片归档，再装载新计划（保偏好与动作库，视图位置收敛）。
5. 未知 `schemaVersion` 一律拒收并点名「不在接受清单」——绝不静默降级读旧格式。

闭环可逆：被替换掉的旧计划随时可从「计划归档」取回。

## 4 · 实现落点

| 侧 | 落点 |
|---|---|
| 注入 | `build_html.py`：`/*__EXCHANGE_SCHEMA__*/null` → `const EXCHANGE_SCHEMA`；`BUILD_FP` 尾注含 `exc=` 摘要 |
| 前端 | `template.html`：`planEnvelope()` / `exportPlanJSONText()` / `doExportPlanJSON()`；`validateEnvelope()` / `importPlanFromJSONText()` / `onPlanJSONFile()`（导入整份替换）；`unifiedRecords()` / `logMetaRecord()` / `logJsonlText()` / `doExportLogJSONL()`（设置页「JSON 计划」「训练日志（JSONL）」两行） |
| 原生 | `MainActivity.exportDoc(filename, mime, b64)`（REQ_EXPORT_DOC=1004，与 CSV/xlsx 共用落盘→SAF→流拷贝链）；`chooserMimes` 把 `.json` 映射成 `application/json`，否则系统选择器会灰掉 JSON 件 |
| Python | `plan_xlsx.py`：`build_envelope()` / `validate_envelope()` / `envelope_to_text()` + CLI `json`；`validate_log_jsonl()` / `csv_cols_from_template()` + CLI `logjsonl --check` |
| 守卫 | gate **S17**（契约键齐全含 `log_jsonl` / 注入成对 / `exc=` 指纹可复算）+ **S14**（JSON/JSONL 节点·处理函数·`accept=".json"` 接线成对）+ **S16**（`.json` MIME 映射在位）+ **S6**（成品含 `EXCHANGE_SCHEMA`）+ **S15**（`exportDoc` 桥名成对） |
| 回归 | `test_plan_xlsx.py` T7（信封往返 / 确定性 / 坏信封电池 / CLI）+ T8（JSONL 列名单源 / META 头 / 坏日志电池 / CLI）；`xlsxv.js` Y 段（注入单源 / 键序 / 载荷全等 / 前端产物过 Python 校验 ×2 / 导入闭环 / 篡改件拒收 / READONLY 拒导出） |
| 反向验证 | `_sabotage_m1.py`（打红 S4/S5、S17、S15、S17 指纹）；`_sabotage_m2.py`（打红 S16、S17、S14）——inject → gate 红 → revert → 全绿 |
