# 03_规范 · 数据契约

本目录存放 RPL 数据层的**机器可读契约**，不是实现代码。

| 文件 | 作用 | 状态 |
|---|---|---|
| `RPL_Data_v1.contract.json` | 表、字段、枚举、引用与校验规则草案 | draft |
| `tools/validate_data.py` | 只读数据校验器；输出 `04_生成物/10_数据校验报告.md` | v1 |
| `README.md` | 本说明 | — |

## 怎么用

1. **新增表/字段**：先改 `RPL_Data_v1.contract.json`，再改生成器与校验器。
2. **校验器**（下一轮）：读取 contract，逐条执行 `validation_rules`；错误分级 error/warning。
3. **生成器**（下一轮）：`gen_seed.py` 从旧工作簿抽取 → 规范表 → `seed.json`；纯重构时用新旧 seed 逐格 diff = 0 作为闸门。
4. **前端**：`build_html.py` 可把 contract 的枚举/字段子集注入 `PLAN_SCHEMA` / `PHASE_SCHEMA`，避免三处手写。

## 当前状态

- 契约是**方向性草案**，字段已覆盖现有数据与 Phase v1 的核心语义。
- 尚未与 `mobile/tools/schema/RPL-Plan-v1.json` 合并；两者边界：本契约管**数据层**，Plan 契约管**六表交换格式**。
- 旧工作簿的固定坐标、公式缓存与 `gen_seed.py` 兼容问题，见 [DATA_MAP.md](../00_索引/DATA_MAP.md) §3。
