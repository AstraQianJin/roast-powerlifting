# -*- coding: utf-8 -*-
"""Enrich the two reference library xlsx files for human + Agent readability.

Safe-only changes in gen_seed consumption OUTSIDE columns.
Main workbook (RPL_ExDark) is NEVER touched here — formula cache risk.

Run from project root: python data/03_规范/tools/enrich_workbooks.py
"""
import os, sys
from copy import copy
import openpyxl
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.comments import Comment

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # .../data/
PLIB = os.path.join(ROOT, "01_工作簿", "RPL_Program_Library_v0.15.xlsx")
SLIB = os.path.join(ROOT, "01_工作簿", "RPL_Set_Strategy_v0.15.xlsx")

# === Visual styles ===
RED_FILL = PatternFill(start_color="FFD6D6", end_color="FFD6D6", fill_type="solid")
BLUE_FILL = PatternFill(start_color="D6E4FF", end_color="D6E4FF", fill_type="solid")
GREY_FILL = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
HEADER_FONT = Font(bold=True)
THIN = Side(border_style="thin", color="CCCCCC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

# ============================================================
# 1. RPL_Program_Library_v0.15.xlsx
# ============================================================

PROGRAM_COLS = [
    # (col_num, col_name, def_zh, type, allowed_values, gen_seed_consumes, editable, notes)
    (1,  "ID",          "计划稳定 ID（如 GZCL-001）",         "string",  "FAM-xxx 或自定义", "是 A-P(1-16)", "否（主键）",     "gen_seed.py cols 1-16 原范围"),
    (2,  "变更",        "相对于母计划的变更标记",               "string",  "沿用 / 新增 / 重写 / 合并", "是", "是", "用于标识正式改版 vs 社区变体"),
    (3,  "家族",        "所属计划家族（GZCL / Sheiko / JTS...）", "string", "自由文本", "是", "是", "跨表关联 family_id 的来源"),
    (4,  "计划名称",    "中文/英文混合显示名",                   "string",  "自由文本", "是", "是", "App 内显示用"),
    (5,  "English / 原名", "英文官方名或原名",                   "string",  "自由文本", "是", "是", "双语对照表"),
    (6,  "条目类型",    "方法论 / 计划 / 变体",                 "enum",    "方法论/计划/变体", "是", "是", "字段规范与口径 sheet 已定义取值"),
    (7,  "主目标",      "入门教学 / 力量 / 肥大 / 力量+肥大",    "string",  "自由文本", "是", "是", "用于 level 推断"),
    (8,  "自调节",      "框架内置 / 部分 / 无",                 "string",  "自由文本", "是", "是", "原计划的 auto-regulation 程度"),
    (9,  "GL 下限",     "Gym Ladder 百分位下限",                "number",  "0–100", "是", "是", "原 16 列范围"),
    (10, "GL 上限",     "Gym Ladder 百分位上限",                "number",  "0–100", "是", "是", "原 16 列范围"),
    (11, "周期",        "计划周期描述（持续 / N 周）",           "string",  "自由文本", "是", "是", "原 16 列范围"),
    (12, "频率(天/周)", "每周训练天数范围",                      "string",  "如 3 / 3–6", "是", "是", "原 16 列范围"),
    (13, "验证",        "已验证 / 部分验证 / 未验证",            "string",  "自由文本", "是", "是", "原 16 列范围；canonical_status 列会标准化"),
    (14, "作者 / 出处", "原作者 / 来源",                          "string",  "自由文本", "是", "是", "原 16 列范围"),
    (15, "规范链接",    "canonical URL / 官方文档",              "string",  "自由文本", "是", "是", "原 16 列范围"),
    (16, "备注",        "自由文本说明",                          "string",  "自由文本", "是", "是", "原 16 列范围"),
    # --- 派生列（gen_seed 忽略，17-28）---
    (17, "family_id",             "家族稳定 ID（FAM-xx）",       "string", "FAM-01...", "否", "否（派生）", "原 16 列范围外，gen_seed 不读"),
    (18, "level",                 "难度等级",                    "enum",   "beginner/intermediate/advanced/unknown", "否", "是（推断+人工复核）", "由主目标/备注关键词推断"),
    (19, "duration_min",          "最短周期（周）",              "number", "整数周", "否", "是", "原 16 列范围外"),
    (20, "duration_max",          "最长周期（周）",              "number", "整数周", "否", "是", "原 16 列范围外"),
    (21, "freq_min",              "最低频率（天/周）",           "number", "1–7", "否", "是", "原 16 列范围外"),
    (22, "freq_max",              "最高频率（天/周）",           "number", "1–7", "否", "是", "原 16 列范围外"),
    (23, "autoregulation_std",    "自调节标准化值",              "enum",   "built_in/partial/none/missing", "否", "是", "原 16 列范围外"),
    (24, "verification_std",      "验证状态标准化值",            "enum",   "verified/partial/unverified/missing", "否", "是", "原 16 列范围外"),
    (25, "canonical_status",      "canonical 资源状态",          "enum",   "available/missing/paid_only/link_only", "否", "是", "原 16 列范围外"),
    (26, "license_status",        "许可状态",                    "enum",   "free_public/OA/paid/user_provided/missing", "否", "是", "原 16 列范围外"),
    (27, "language",              "可用语言",                    "enum",   "zh/en/zh+en/missing", "否", "是", "原 16 列范围外"),
    (28, "last_verified",         "最后验证日期",                "date",   "YYYY-MM-DD", "否", "是", "原 16 列范围外"),
]


def enrich_program_library():
    wb = openpyxl.load_workbook(PLIB)

    # --- 99_数据字典：逐列定义 ---
    if "99_数据字典" not in wb.sheetnames:
        ws_dict = wb.create_sheet("99_数据字典")
    else:
        del wb["99_数据字典"]
        ws_dict = wb.create_sheet("99_数据字典")

    # 扩展表头
    dict_headers = ["sheet", "col_letter", "col_num", "col_name",
                    "definition_zh", "type", "allowed_values",
                    "gen_seed_consumes", "editable", "notes"]
    ws_dict.append(dict_headers)
    for h in dict_headers:
        cell = ws_dict.cell(row=1, column=dict_headers.index(h)+1)
        cell.font = HEADER_FONT
        cell.fill = GREY_FILL
        cell.border = BORDER

    for sheet_name, col_defs, header_row in [
        ("计划总库", PROGRAM_COLS, 1),
        ("字段规范与口径", [
            (1, "字段",   "字段中文名", "string", "自由文本", "是 2-4 列", "否（主键）", "gen_seed.py 184-193 读取"),
            (2, "取值",   "字段取值枚举", "string", "自由文本", "是", "是",   ""),
            (3, "定义",   "字段定义",   "string", "自由文本", "是", "是",   ""),
            (4, "使用规则", "使用约束", "string", "自由文本", "是", "是",   ""),
        ], 1),
    ]:
        for d in col_defs:
            row = [sheet_name, openpyxl.utils.get_column_letter(d[0]), d[0]] + list(d[1:])
            ws_dict.append(row)

    # 设置列宽
    col_widths = [14, 10, 8, 18, 30, 12, 25, 18, 10, 40]
    for i, w in enumerate(col_widths, 1):
        ws_dict.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # --- 00_META：扩充 ---
    ws_meta = wb["00_META"]
    # 找到现有最后一行，追加三个新 section
    existing_max_row = ws_meta.max_row

    # Section 1: 表格契约
    sections = [
        ("", "", "", ""),
        ("=== SECTION: gen_seed 读取契约 ===", "", "", ""),
        ("table_sheet", "col_range", "row_range", "consumer"),
        ("计划总库", "A-P (1-16)", "2-N", "gen_seed.py:171-181 range(1,17)"),
        ("字段规范与口径", "A-D (1-4)", "2-N", "gen_seed.py:184-193"),
        ("", "", "", ""),
        ("=== SECTION: 表间关系 ===", "", "", ""),
        ("from_table", "from_col", "to_table", "to_col"),
        ("计划总库", "family_id (col 17)", "RPL_Set_Strategy_v0.15.xlsx", "(无直接关联)"),
        ("组策略总表", "strategy_id (col 10)", "三大项辅助动作库", "适配组策略 (col 8, 自由文本)"),
        ("", "", "", ""),
        ("=== SECTION: 已知限制 ===", "", "", ""),
        ("限制项", "说明", "影响范围", "优先级"),
        ("family_id 全空", "所有条目的 family_id 尚未填入，跨表关联暂不可用", "所有", "P1"),
        ("exercise_id 全空", "组策略库的 exercise_id (aux_id.exercise_id) 全空，未建立与主工作簿动作库关联", "三大项辅助动作库", "P1"),
        ("gen_seed 按列号读", "不能重排前 16 列；不能在前 16 列中间插入新列", "计划总库", "硬约束"),
    ]
    for row_data in sections:
        existing_max_row += 1
        for ci, val in enumerate(row_data, 1):
            cell = ws_meta.cell(row=existing_max_row, column=ci, value=val)
            if val and val.startswith("==="):
                cell.font = Font(bold=True, color="CC3300", size=11)

    # --- 视觉标记：计划总库 ---
    ws_plan = wb["计划总库"]
    for c in range(1, 17):  # A-P = gen_seed 消费
        cell = ws_plan.cell(row=1, column=c)
        cell.fill = RED_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment(
                f"⚠ gen_seed.py 按列号读取此列 (range 1-16)\n请勿重排或在此范围内插入新列。",
                "data-admin"
            )
    for c in range(17, 29):  # Q-AB = 派生列
        cell = ws_plan.cell(row=1, column=c)
        cell.fill = BLUE_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment(
                "派生列 / 规范化补充。gen_seed 忽略。可自由编辑。",
                "data-admin"
            )

    # 保存
    wb.save(PLIB)
    print(f"✓ {os.path.basename(PLIB)} enriched")


# ============================================================
# 2. RPL_Set_Strategy_v0.15.xlsx
# ============================================================

STRAT_TABLE_COLS = [
    (1,  "序号",   "行号，无语义",              "number",  "整数", "是 A-I(1-9)", "否（行号）",     "gen_seed.py cols 1-9"),
    (2,  "功能分类", "基础结构 / 进阶结构 / 疲劳管理", "string", "自由文本", "是", "是", ""),
    (3,  "组策略",   "策略中文名",               "string",  "自由文本", "是", "是", ""),
    (4,  "英文 / 别名", "策略英文名或别名",         "string", "自由文本", "是", "是", ""),
    (5,  "Tier",    "S+/S/A/B/C 评级",           "string",  "S+/S/A/B/C", "是", "是", "原 Tier 列；tier_std 是标准化副本"),
    (6,  "适用动作", "适用的主项列表",             "string",  "自由文本", "是", "是", "自由文本枚举，机器不可靠"),
    (7,  "典型参数", "典型组×次×强度范围",         "string",  "自由文本", "是", "是", ""),
    (8,  "核心适用场景", "典型使用时机",             "string", "自由文本", "是", "是", ""),
    (9,  "禁忌与注意事项", "禁忌和风险",             "string", "自由文本", "是", "是", ""),
    # 派生列（gen_seed 忽略）
    (10, "strategy_id", "策略稳定 ID（STR-01...）", "string", "STR-xx", "否", "否（派生）", "gen_seed 不读"),
    (11, "tier_std",  "Tier 标准化副本",           "enum",    "S+/S/A/B/C", "否", "否（派生）", "与 Tier 同值，用于机器解析"),
    (12, "mode_hint", "关联 mode 提示",            "string",  "自由文本", "否", "是", "当前全空，预留"),
]

MATRIX_COLS = [
    # 注意：动作适用性矩阵 row 1 是标题行，row 2 才是表头
    (1,  "组策略",     "策略中文名（关联 组策略总表.组策略）", "string", "自由文本", "是 A-G(1-7)", "否（主键关联）", "gen_seed.py cols 1-7, row 2"),
    (2,  "Tier",       "策略 Tier",                         "string", "S+/S/A/B/C", "是", "是", ""),
    (3,  "深蹲",       "适用性：推荐 / 限量 / 不适用",          "string", "推荐/限量/不适用", "是", "是", "自由文本，机器解析时需枚举化"),
    (4,  "卧推",       "同上",                               "string", "同上", "是", "是", ""),
    (5,  "硬拉",       "同上",                               "string", "同上", "是", "是", ""),
    (6,  "肩推",       "同上",                               "string", "同上", "是", "是", ""),
    (7,  "辅助动作",   "同上",                               "string", "同上", "是", "是", ""),
    # 派生列
    (8,  "matrix_id",  "矩阵行稳定 ID（MAT-01...）",           "string", "MAT-xx", "否", "否（派生）", "gen_seed 不读"),
    (9,  "condition_note", "特殊适用条件",                    "string", "自由文本", "否", "是", "gen_seed 不读"),
]

AUX_COLS = [
    # 注意：三大项辅助动作库 row 1 是标题行，row 2 才是表头
    (1,  "ID",        "辅助动作行号（SQ-V-01...）",           "string", "自由文本", "是 A-M(1-13)", "否", "gen_seed.py cols 1-13, row 2"),
    (2,  "主项 Lift", "所属主项（SQ/BP/DL）",                  "enum",   "SQ/BP/DL", "是", "是", ""),
    (3,  "类别 Category", "类别（Main Variation/分段/辅助）", "string", "自由文本", "是", "是", ""),
    (4,  "子类 Subclass", "子类",                              "string", "自由文本", "是", "是", ""),
    (5,  "中文名称 Name", "中文名",                              "string", "自由文本", "是", "是", ""),
    (6,  "英文名 Name (EN)", "英文名",                          "string", "自由文本", "是", "是", ""),
    (7,  "常见定位 Tier", "T1/T2/T3 定位",                       "enum",   "T1/T2/T3", "是", "是", ""),
    (8,  "适配组策略 Set Strategy", "适配的组策略（自由文本）",   "string", "自由文本", "是", "是", "自由文本，未与 strategy_id 关联"),
    (9,  "典型组×次 Sets × Reps", "推荐组次范围",                "string", "自由文本", "是", "是", ""),
    (10, "疲劳成本 Fatigue", "High/Medium/Low",                  "string", "High/Medium/Low", "是", "是", ""),
    (11, "依据 Source",  "依据来源（IPF/SBS/RTS...）",            "string", "自由文本", "是", "是", ""),
    (12, "训练指向 / 用途 (CN)", "训练目标描述",                 "string", "自由文本", "是", "是", ""),
    (13, "备注 Notes (CN)", "其他说明",                           "string", "自由文本", "是", "是", ""),
    # 派生列
    (14, "规范链接 Canonical", "canonical URL",                    "string", "自由文本", "否", "是", "gen_seed 不读"),
    (15, "aux_id",      "辅助动作稳定 ID（AUX-001...）",         "string", "AUX-NNN", "否", "否（派生）", "gen_seed 不读"),
    (16, "exercise_id", "与主工作簿动作库的关联 ID",               "string", "预留", "否", "待填", "当前全空，P1 填主工作簿 EX-xxx"),
    (17, "canonical_status", "canonical 状态",                     "string", "missing/available", "否", "是", "gen_seed 不读"),
]


def enrich_strategy_library():
    wb = openpyxl.load_workbook(SLIB)

    # --- 99_数据字典 ---
    if "99_数据字典" not in wb.sheetnames:
        ws_dict = wb.create_sheet("99_数据字典")
    else:
        del wb["99_数据字典"]
        ws_dict = wb.create_sheet("99_数据字典")

    dict_headers = ["sheet", "header_row", "col_letter", "col_num", "col_name",
                    "definition_zh", "type", "allowed_values",
                    "gen_seed_consumes", "editable", "notes"]
    ws_dict.append(dict_headers)
    for h in dict_headers:
        cell = ws_dict.cell(row=1, column=dict_headers.index(h)+1)
        cell.font = HEADER_FONT
        cell.fill = GREY_FILL
        cell.border = BORDER

    for sheet_name, col_defs, header_row in [
        ("组策略总表",       STRAT_TABLE_COLS, 1),
        ("动作适用性矩阵",    MATRIX_COLS,      2),
        ("三大项辅助动作库",  AUX_COLS,         2),
    ]:
        for d in col_defs:
            row = [sheet_name, header_row, openpyxl.utils.get_column_letter(d[0]), d[0]] + list(d[1:])
            ws_dict.append(row)

    col_widths = [16, 10, 10, 8, 20, 34, 12, 28, 18, 10, 42]
    for i, w in enumerate(col_widths, 1):
        ws_dict.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

    # --- 00_META：扩充 ---
    ws_meta = wb["00_META"]
    existing_max_row = ws_meta.max_row

    sections = [
        ("", "", "", ""),
        ("=== SECTION: gen_seed 读取契约 ===", "", "", ""),
        ("table_sheet", "col_range", "row_range", "consumer"),
        ("组策略总表",     "A-I (1-9)", "2-N",   "gen_seed.py:204-216 range(1,10)"),
        ("动作适用性矩阵", "A-G (1-7)", "3-N",   "gen_seed.py:219-228 range(1,8) row3+"),
        ("三大项辅助动作库", "A-M (1-13)", "3-N", "gen_seed.py:231-242 range(1,14) row3+"),
        ("", "", "", ""),
        ("=== SECTION: 表头位置（重要！） ===", "", "", ""),
        ("sheet", "表头在 row", "数据在 row", "原因"),
        ("组策略总表",     "row 1", "row 2+",  "gen_seed 用 range(2, max_row+1)"),
        ("动作适用性矩阵", "row 2", "row 3+",  "row 1 是大标题，gen_seed 用 range(3, max_row+1)"),
        ("三大项辅助动作库", "row 2", "row 3+", "row 1 是大标题，gen_seed 用 range(3, max_row+1)"),
        ("", "", "", ""),
        ("=== SECTION: 表间关系 ===", "", "", ""),
        ("from_table", "from_col", "to_table", "to_col"),
        ("组策略总表",    "组策略 (col 3)",       "动作适用性矩阵",   "组策略 (col 1)"),
        ("组策略总表",    "strategy_id (col 10)", "三大项辅助动作库", "适配组策略 (col 8, 自由文本)"),
        ("三大项辅助动作库", "主项 Lift (col 2)",  "(无)",             "主项枚举，不跨表"),
        ("", "", "", ""),
        ("=== SECTION: 已知限制 ===", "", "", ""),
        ("限制项", "说明", "影响范围", "优先级"),
        ("mode_hint 全空", "组策略的 mode 关联未建立", "组策略总表", "P1"),
        ("exercise_id 全空", "aux 动作与主工作簿动作库未关联", "三大项辅助动作库", "P1"),
        ("gen_seed 按列号读", "三张表都不能重排 gen_seed 消费范围", "全部", "硬约束"),
        ("自由文本适用性", "动作适用性矩阵是自由文本，不是枚举", "机器解析", "P2：枚举化"),
    ]
    for row_data in sections:
        existing_max_row += 1
        for ci, val in enumerate(row_data, 1):
            cell = ws_meta.cell(row=existing_max_row, column=ci, value=val)
            if val and val.startswith("==="):
                cell.font = Font(bold=True, color="CC3300", size=11)

    # --- 视觉标记 ---
    # 组策略总表 (row 1)
    ws = wb["组策略总表"]
    for c in range(1, 10):
        cell = ws.cell(row=1, column=c)
        cell.fill = RED_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment(
                f"⚠ gen_seed.py 按列号读取此列 (range 1-9)\n请勿重排或在此范围内插入新列。",
                "data-admin"
            )
    for c in range(10, 13):
        cell = ws.cell(row=1, column=c)
        cell.fill = BLUE_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment("派生列 / 规范化补充。gen_seed 忽略。可自由编辑。", "data-admin")

    # 动作适用性矩阵 (row 2 = 表头)
    ws = wb["动作适用性矩阵"]
    for c in range(1, 8):
        cell = ws.cell(row=2, column=c)
        cell.fill = RED_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment(
                "⚠ gen_seed.py 按列号读取此列 (range 1-7, row 2 表头)\n请勿重排或在此范围内插入新列。",
                "data-admin"
            )
    for c in range(8, 10):
        cell = ws.cell(row=2, column=c)
        cell.fill = BLUE_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment("派生列 / 规范化补充。gen_seed 忽略。可自由编辑。", "data-admin")

    # 三大项辅助动作库 (row 2 = 表头)
    ws = wb["三大项辅助动作库"]
    for c in range(1, 14):
        cell = ws.cell(row=2, column=c)
        cell.fill = RED_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment(
                "⚠ gen_seed.py 按列号读取此列 (range 1-13, row 2 表头)\n请勿重排或在此范围内插入新列。",
                "data-admin"
            )
    for c in range(14, 18):
        cell = ws.cell(row=2, column=c)
        cell.fill = BLUE_FILL
        cell.border = BORDER
        if not cell.comment:
            cell.comment = Comment("派生列 / 规范化补充。gen_seed 忽略。可自由编辑。", "data-admin")

    wb.save(SLIB)
    print(f"✓ {os.path.basename(SLIB)} enriched")


if __name__ == "__main__":
    enrich_program_library()
    enrich_strategy_library()
    print("\n全部完成。验证：python mobile/tools/gen_seed.py 应正常产出且 seed.json 与之前零格差。")
