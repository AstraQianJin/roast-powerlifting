# data/ 入口

**这里只有一个索引：[`00_索引/DATA_MAP.md`](00_索引/DATA_MAP.md)。** 谁是权威源、谁消费哪张表的哪些列、什么能改、什么进 git，全部在那份里写一次；本文件只留「跑什么命令」。

> 原有的 `ENTRY.json` / `NAMING_CONVENTION.md` / `REFERENCE_INDEX.md` / `DATA_STRUCTURE_v1.md` / 主工作簿 META 已收进 DATA_MAP，原件移入 `05_归档/03_过期索引/` 留档（不删）。

---

## 三条命令

| 命令 | 回答什么 |
|---|---|
| `python data/03_规范/tools/validate_data.py` | 数据层健康度（工作簿结构 + manifest + sha256；项数以脚本汇总行为准，别抄） |
| `cd mobile && python tools/gen_seed.py` | 改完 xlsx，种子能否正常产出、行数对得上 |
| `cd mobile && python tools/gate.py --static` | 这条链还可信吗（项目级红线；全量门禁去掉 `--static`） |

---

## 目录一句话

`01_工作簿/` 三个 xlsx 是唯一被代码消费的东西 → `03_规范/` 数据层契约与独立校验脚本 → `04_生成物/` 脚本产物（禁止手改） → `05_归档/` 只增不删 → `00_索引/` 只剩 DATA_MAP。
`data/` 里**没有参考书了**（v0.31）：原先的 `02_参考资料/` 整体搬到仓库根的 `ref/`、全部不入仓，理由与取法在 DATA_MAP §1。

明细与取法命令在 DATA_MAP，不在这儿重述。

---

## 五条红线（改任何东西前先想）

1. **禁止用 `openpyxl` 保存主工作簿** —— 公式缓存会被清空，`gen_seed.py` 读到的负荷变 0。
2. **禁止重排 `gen_seed.py` 消费范围内的列** —— 它按列号硬编码读；范围唯一出处是 `mobile/tools/gen_seed.py` 与 `mobile/tools/wkbook.py`。
3. **禁止手改 `04_生成物/`** —— 改源后重跑生成脚本。
4. **禁止删除任何 `.xlsx`** —— 归档只增不删。
5. **付费/版权内容只建元数据** —— 不分发全文。

项目级红线（版本单源、不手改生成物、协议不可破、断言必须能红等）在 [`../AGENTS.md`](../AGENTS.md) §2 与 [`../mobile/README.md`](../mobile/README.md) §5。
