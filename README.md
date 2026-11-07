# Roast PowerLifting

力量举（SBD）周期化训练记录系统：**Android 离线 App（主线 · 唯一事实源）**，其余目录围着它转。

| | 项目 | 角色 | 文档 |
|---|---|---|---|
| ★ | `mobile/` | 唯一主线交付物：离线 App（单文件 HTML + 纯 Java WebView 壳） | [`mobile/README.md`](mobile/README.md) |
| | `data/` | 权威数据库，同时是主项目的种子输入源 | 见下 §数据 |
| | `release/` | 发版记录（`RELEASE_NOTES.md`）；APK 二进制只上传 GitHub Releases | [`release/RELEASE_NOTES.md`](release/RELEASE_NOTES.md) |
| | `archive/desktop/` | 已归档的 PC 端项目（Excel ⇄ Web HUD），**不入仓、不进依赖图、不参与门禁** | 归档目录内自带 `README.md` |

**现行版本：`v0.70`（versionCode 57）** — 本版只做一件事：让 App 里显示的计划与计划文件逐字对上。处方解析不再「认不出就静默换一套」（非空原文解析失败会显式标出、原文照留），`Workouts` 的 `sets` 列真正驱动组数，App 默认种子改用新工作簿 `data/01_工作簿/RPL_ExDark_v0.70_Plan_2026-11-09.xlsx`（旧工作簿原样保留）。不随本版变的：CSV 26 列、`data/*.xlsx` 权威源、既有契约与 `SCHEMA_STAMP`。逐版变更看 `CHANGELOG.md`，门禁项数以 `gate.py` 实际输出为准（本文不抄数字）。

> 文档以**子 README 为准**。本文件只做索引，冲突时以 `mobile/README.md` 为准。

---

## 目录结构

```
Roast PowerLifting/
├── mobile/          ★ 主项目：Android Gradle 工程 + tools/ 生成链 + docs/
├── data/              权威工作簿 + 两份只读参考库（01_工作簿/）；谁进仓、边界、改名规矩见 data/00_索引/DATA_MAP.md
├── ref/               参考书库（人与 Agent 的读物，数百 MB）：不入仓、App 运行时不读，只做 seed `canon` 的出处对账
├── release/           发版记录 RELEASE_NOTES.md；成品 APK 不入仓，只在 GitHub Releases（v0.21 起命名 `RPL_ExDark_v{X.XX}_Pro.apk`）
└── archive/           不入仓的本机留档：release/（轮出的历史 APK）、snapshots/（发版前快照）、legacy/（一次性工具与失效文档）、desktop/（v0.13 起整体归档的 PC 端项目）
```

## 下载与版本谱系

安装包只在大版本节点发布到 GitHub Releases：<https://github.com/AstraQianJin/roast-powerlifting/releases>，
站点 `http://49.233.196.202/Jhin/roast/` 保留镜像入口。APK 二进制不入仓库，GitHub 附件与页面公布值逐字节一致。

| 版本 | 定位 | 要点 |
|---|---|---|
| v0.70 | 下一个大版本节点 | 尚未出包 |
| v0.61 | 预览版 | 设置改为独立页、首页移除打气模块 |
| v0.60 | 内测基线（首个 GitHub Release） | 首页配重条只图形、零文字 |

逐版细节见 `CHANGELOG.md` 与 `release/RELEASE_NOTES.md`；远端只在大版本节点推送。

## 许可证

本仓库未附开源许可证文件。代码、文档与界面设计的版权归作者所有（All rights reserved），
未经许可不得再分发或商用。若后续改为开源许可，以仓库根新增的 `LICENSE` 文件为准。

## 快速上手

```bash
# 1) 构建 APK（一条命令：静态守卫 → 注入版本与种子 → --offline 构建 → 规范命名 → 发版全量门禁 → 校验）
cd mobile && python tools/pack.py

# 2) 构建链守卫：静态红线 + 全量回归（套件清单与各套断言数以 gate.py 的 DYNAMIC 输出为准），一个退出码
python tools/gate.py            # --static 只查红线；--quick 只留 v3v/v2v（跳过其余各套）

# 2b) 单项回归（排障时单独跑；gate 已包含）
node tools/v3v.js && node tools/v2v.js && node tools/check_hud.js
```

PC 端项目（Excel ⇄ Web HUD）已于 v0.13 整体归档在 `archive/desktop/`：不入仓、不进依赖图、不参与门禁，主线不提供也不支持那条路径。

App 界面是单文件 HTML，由模板生成；**不要手改生成物**：

```bash
cd mobile/tools
python gen_seed.py      # xlsx → seed.json
python build_html.py    # seed.json + 版本号 → app/src/main/assets/index.html
```

## 数据

**这一层的唯一索引是 `data/00_索引/DATA_MAP.md`**（什么进仓、谁是权威、哪层能改、改名怎么跟着走）。本节只留指路，表数、条数一类数字都去 DATA_MAP 与门禁输出查，别在这儿抄第二份。

- 权威工作簿：`data/01_工作簿/` 里 `gen_seed.py` 引用的那一份（路径与文件名以 `mobile/tools/gen_seed.py` 为准）
- 只读参考资产：同目录下的计划库与策略库两份工作簿，由 `gen_seed.py` 抽入 `seed.json` 的 `programLib` / `strategyLib`；各自读哪几列、哪些列禁止动，看 `DATA_MAP.md` §3
- 版本号唯一来源：`mobile/app/build.gradle` 的 `versionName` / `versionCode`；其余位置只跟随
- 数据流向：Excel →（`gen_seed.py`）→ `seed.json` →（`build_html.py`）→ `index.html` → APK；
  手机端只写本机四路分片（`roast_prefs.json` / `roast_workout.json` / `roast_lib_diff.json` / `roast_plan_archive.json`，最后一份是被替换掉的旧计划六表原文），**不回写 Excel**；CSV 回灌端点在已归档的 PC 端项目里（`archive/desktop/`），主线不提供该路径
- 历史文档与一次性工具在 `archive/legacy/`（**只移动、不删除**，缘由见该目录 `README.md`）；发版前快照在 `archive/snapshots/`。`archive/` 整体不入仓。

## 红线摘要

删任何 xlsx、改 `applicationId`、手改 `mobile/app/src/main/assets/index.html`、改 CSV 26 列协议 —— 一律不做。**git 是唯一历史机制**（v0.07 起；`archive/snapshots/*.zip` 降为发版留档）。完整清单见 `mobile/README.md` §5。
