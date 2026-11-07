# -*- coding: utf-8 -*-
"""`plan_xlsx.py` 的契约回归测试（B4）—— 一条命令回答「六表交换层还可信吗」。

    python tools/test_plan_xlsx.py            # 全跑
    python tools/test_plan_xlsx.py T3         # 只跑指定组（可多个，T3 含 T3b）
    python tools/test_plan_xlsx.py -v         # 详细模式：断言明细不截断

六组断言：
  T1 全量 16 周计划的逐格往返：state→plan→state→plan，与 .xlsx / CSV 目录两种落盘形态
  T2 最小四表（AI 最简输入面）+ `%1RM` 写法自动换算 + 导入默认值
  T3 坏输入电池：每处篡改恰好产生一条、格式精确的 error（另含设计上只 warning 的几类）
  T4 权威源表 `data/*.xlsx` 只读 —— 交换层写盘绝不越界（硬边界 1）
  T5 六日 A–F 计划（契约新造的那一面）+ `row_idx` 几何与 `wkbook` 对账
  T6 归档 + 冻结语义（决策 D4：`structure.inactiveWeeks`）

单元格数、行数、周数一律运行时算出，不写死；列名与字段名一律经契约的
`role_columns` / `keys` 寻址，所以契约改名不会让这里悄悄失效或假绿。
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import plan_xlsx as px  # noqa: E402
import pyout  # noqa: E402

SCH = px.load_schema()
COLS = {n: SCH["sheets"][n]["columns"] for n in SCH["sheet_order"]}
RC = {n: SCH["sheets"][n].get("role_columns", {}) for n in SCH["sheet_order"]}
UNIQ = {n: SCH["sheets"][n].get("unique", [None])[-1] for n in SCH["sheet_order"]}
OPTIONAL = [n for n in SCH["sheet_order"] if SCH["sheets"][n].get("optional")]
SEED = px.load_default_seed()
PROF = SCH["sheets"]["Profile"]["fields"]
CP = SCH["conflict_policy"]
FIRST = SCH["row_idx"]["first"]
LABELS = SCH["sheets"]["Days"]["weekday_labels"]
P = SEED["profile"] if SEED else {}
# v3 起现行附表是 GPP（单列 done_mask）+ Level；旧 Armor 表（v1/v2 档）只在 legacy_compat
# 命中时出现，其列形唯一出处是 sheets.GPP.legacy_armor.spec（产品代码不加载冻结的旧契约）。
GPP = SCH["sheets"]["GPP"]
GPP_RC = GPP["role_columns"]
GPP_MASK_COL = GPP["done_mask"]["column"]
GPP_MASK_LEN = GPP["done_mask"]["len"]
LEGACY_SPEC = px._armor_legacy_spec(SCH)
LEGACY_COLS = LEGACY_SPEC["columns"]
LRC = LEGACY_SPEC["role_columns"]
LEGACY_ENTRIES = px._legacy_entries(SCH)

results = []
VERBOSE = "-v" in sys.argv
GROUPS = [a for a in sys.argv[1:] if re.fullmatch(r"T[1-9]", a)]


def check(label, ok, detail=""):
    results.append((bool(ok), label, str(detail)))
    cap = 4000 if VERBOSE else 180
    line = "%s  %s" % ("PASS" if ok else "FAIL", label)
    if str(detail):
        line += "  [%s]" % str(detail).replace("\n", " ⏎ ")[:cap]
    print(line)
    return ok


def head(title):
    print("\n---- %s ----" % title)


# ---------------------------------------------------------------- 计划构造


def profile_rows(pairs):
    c = COLS["Profile"]
    return [{c[0]: field, c[1]: value, c[2]: PROF[field]["desc"], "__row__": i + 2}
            for i, (field, value) in enumerate(pairs)]


def sheet_rows(name, records):
    cols, rows = COLS[name], []
    for i, rec in enumerate(records):
        row = {c: rec.get(c, "") for c in cols}
        row["__row__"] = rec.get("__row__", i + 2)
        rows.append(row)
    return rows


def wrow(week, day, seq, mode, cat, mv, **kw):
    """Workouts 一行的原料：位置参数是必填项，其余用**角色名**（pct / load / target_rpe …）。"""
    r = RC["Workouts"]
    rec = {r["week"]: week, r["day"]: day, r["seq"]: seq,
           r["mode"]: mode, r["category"]: cat, r["movement"]: mv}
    for role, v in kw.items():
        rec[r[role]] = v
    return rec


def brow(block_id, cycle, zh, work, deload, **kw):
    r = RC["Blocks"]
    rec = {"block_id": block_id, "cycle_type": cycle, "name_zh": zh,
           r["work_weeks"]: work, r["deload_weeks"]: deload,
           r["work_mode"]: "T1.5x5", r["deload_mode"]: "T1.DL",
           r["base_rpe"]: 7.5, r["deload_rpe"]: 6.0}
    for role, v in kw.items():
        rec[r[role] if role in r else role] = v
    return rec


def gpp_row(week, idx, item="Aerobic LISS (Zone 2)", domain="CARDIO RESPIRATORY",
            rx="25-45 min", intensity="HR 125 · RPE 5.5", done_mask="0000000", **extra):
    """一行现行 GPP：定义列 + 单列 done_mask（7 位周一到周日）。"""
    rec = {c: "" for c in COLS["GPP"]}
    rec[GPP_RC["week"]] = week
    rec[GPP_RC["item"]] = idx
    rec[GPP_RC["domain"]] = domain
    rec[GPP_RC["item_name"]] = item
    rec[GPP_RC["rx"]] = rx
    rec[GPP_RC["intensity"]] = intensity
    rec[GPP_MASK_COL] = done_mask
    rec.update(extra)
    return rec


def armor_row(week, idx, item="Aerobic LISS (Zone 2)", domain="CARDIO RESPIRATORY",
              target="25-45 min", intensity="HR 125 · RPE 5.5", **days):
    """一行旧 Armor（legacy v1/v2 档）：定义列 + 7 个 day-columns（bool）。"""
    rec = {c: "" for c in LEGACY_COLS}
    rec[LRC["week"]] = week
    rec[LRC["item"]] = idx
    rec[LRC["domain"]] = domain
    rec[LRC["item_name"]] = item
    rec[LRC["target"]] = target
    rec[LRC["intensity"]] = intensity
    rec.update(days)
    return rec


def armor_rows(records):
    """legacy Armor 表行（带 __row__），因为 COLS 里没有 Armor（它不在 SCH['sheets']）。"""
    rows = []
    for i, rec in enumerate(records):
        row = {c: rec.get(c, "") for c in LEGACY_COLS}
        row["__row__"] = rec.get("__row__", i + 2)
        rows.append(row)
    return rows


def gpp_rows_to_armor(gpp_rows):
    """现行 GPP 行 → 旧 Armor 行（domain/item 原样，rx→target，done_mask→7 日 bool）。"""
    day_cols = LEGACY_SPEC["day_columns"]
    out = []
    for i, g in enumerate(gpp_rows):
        a = {c: "" for c in LEGACY_COLS}
        a[LRC["week"]] = g.get(GPP_RC["week"], "")
        a[LRC["item"]] = g.get(GPP_RC["item"], "")
        a[LRC["domain"]] = g.get(GPP_RC["domain"], "")
        a[LRC["item_name"]] = g.get(GPP_RC["item_name"], "")
        a[LRC["target"]] = g.get(GPP_RC["rx"], "")
        a[LRC["intensity"]] = g.get(GPP_RC["intensity"], "")
        mask = str(g.get(GPP_MASK_COL, "") or "")
        for j, dc in enumerate(day_cols):
            a[dc] = (j < len(mask) and mask[j] == "1")
        a["__row__"] = i + 2
        out.append(a)
    return out


def to_legacy(seed_plan_dict, ver, with_gear):
    """v3 种子计划 → 一份真正的 legacy 计划（Armor 表、无 GPP/Level；v1 再去掉 Gear）。"""
    lp = {k: [dict(r) for r in v] for k, v in seed_plan_dict.items()}
    armor = gpp_rows_to_armor(lp.pop("GPP", []))
    lp.pop("Level", None)
    if not with_gear:
        lp.pop("Gear", None)
    lp["Armor"] = armor
    set_field(lp, "schema_ver", ver)
    return lp


def minimal_plan():
    """AI 最简输入 = 四表；可选表全缺，靠导入默认值补齐。"""
    workouts = [
        wrow(1, "A", 1, "T1.5x5", "S.Main", "High-bar Squat", pct="70%"),
        wrow(1, "A", 2, "T2.Mod", "S.Core", "Ab Wheel Rollout", load=0.0, reps=12, target_rpe=7.0),
        wrow(2, "B", 1, "T1.5x5", "D.Main", "Conventional Deadlift", pct=0.7, load=130.0),
        wrow(3, "A", 1, "T1.DL", "B.Main", "Mid-grip Bench", pct=0.6),
    ]
    return {
        "Profile": profile_rows([
            ("schema_ver", SCH["schema_ver"]), ("start_date", P["startDate"]),
            ("gender", P["gender"]), ("age", P["age"]), ("bw_kg", P["bw"]),
            ("sq_1rm", P["sq"]), ("bp_1rm", P["bp"]), ("dl_1rm", P["dl"]),
        ]),
        "Blocks": sheet_rows("Blocks", [brow("B1", "Strength", "力量容量期", 2, 1)]),
        "Days": sheet_rows("Days", [{"day_id": "A", "title_zh": "深蹲日", "weekday_offset": 0},
                                    {"day_id": "B", "title_zh": "硬拉日", "weekday_offset": 1}]),
        "Workouts": sheet_rows("Workouts", workouts),
    }


def seed_plan():
    return px.state_to_plan_dict(SEED, SCH)


def val(plan, strict=False):
    return px.validate_plan_dict(plan, proto=SEED["proto"], lib=SEED["lib"],
                                 strict_constraints=strict, sch=SCH)


def set_field(plan, field, value):
    for row in plan["Profile"]:
        if row[pcol("Profile")] == field:
            row[COLS["Profile"][1]] = value
            return plan
    plan["Profile"].append({pcol("Profile"): field, COLS["Profile"][1]: value,
                            COLS["Profile"][2]: "", "__row__": len(plan["Profile"]) + 2})
    return plan


def pcol(name):
    return COLS[name][0]


def col(name, role):
    """列名：role 在契约 role_columns 里就按角色取，否则当字面列名（cycle_type 这类）。"""
    return RC[name][role] if role in RC[name] else role


def set_cell(plan, name, idx, role, value):
    plan[name][idx][col(name, role)] = value
    return plan


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def authoritative_xlsx():
    """权威源表路径取自 gen_seed.py（与 gate.py S8 同一手法），测试里不写第二遍文件名。"""
    with open(os.path.join(_HERE, "gen_seed.py"), encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r'^XLSX\s*=\s*os\.path\.join\(ROOT,\s*"data",\s*"([^"]+)"\)', src, re.M)
    if not m:
        raise AssertionError("gen_seed.py 里的权威源表常量找不到，T4 无从判定")
    return os.path.join(_ROOT, "data", m.group(1))


# ---------------------------------------------------------------- T1 全量往返


def t1(tmp):
    head("T1 全量 16 周计划：逐格往返")
    res = px.validate_seed_schema(SEED, SCH)
    check("T1.1 seed.json 顶层不变量", res["ok"],
          "%d error / %d warning %s" % (len(res["errors"]), len(res["warnings"]), res["errors"][:2]))

    plan = seed_plan()
    filled = sum(1 for n in SCH["sheet_order"] for row in plan[n] for c in COLS[n] if not px._empty(row.get(c)))
    check("T1.2 导出的计划非空", filled > 1000, "已填充单元格 %d 个" % filled)

    v = val(plan, strict=True)
    check("T1.3 全量计划自校验干净（含严格日约束）", v["ok"] and not v["warnings"],
          "%d error / %d warning %s" % (len(v["errors"]), len(v["warnings"]), (v["errors"] + v["warnings"])[:2]))

    _state, again, diff = px.roundtrip_plan(plan, base_seed=SEED, strict_constraints=True, sch=SCH)
    check("T1.4 state→plan→state→plan 零格差", not diff["diffs"],
          "原 %d 格 / 再导出 %d 格 / 差异 %d 格 %s" % (diff["cells_a"], diff["cells_b"], len(diff["diffs"]), diff["diffs"][:2]))
    check("T1.5 往返前后格数与手工计数相等", diff["cells_a"] == diff["cells_b"] == filled,
          "%s / %s / 手工 %s" % (diff["cells_a"], diff["cells_b"], filled))

    xlsx = os.path.join(tmp, "full.xlsx")
    px.state_to_plan_book(SEED, xlsx, SCH)
    info, _out = px.roundtrip_book(xlsx, os.path.join(tmp, "full.rt.xlsx"), base_seed=SEED, sch=SCH)
    d2 = info["diff"]
    check("T1.6 .xlsx 落盘往返零格差", not d2["diffs"],
          "读回 %d 格 / 再写 %d 格 / 差异 %d 格 %s" % (d2["cells_a"], d2["cells_b"], len(d2["diffs"]), d2["diffs"][:2]))

    csv_dir = os.path.join(tmp, "csv")
    px.state_to_plan_book(SEED, csv_dir, SCH)
    wrote = sorted(os.listdir(csv_dir))
    check("T1.7 CSV 目录形态 = 六份同名文件", wrote == sorted("%s.csv" % n for n in SCH["sheet_order"]), ",".join(wrote))
    cplan, cerr = px.read_plan_csvs(csv_dir, SCH)
    check("T1.8 CSV 表头与契约列序一致", not cerr, cerr[:2])
    dc = px.diff_plan_cells(plan, cplan, SCH)
    check("T1.9 CSV 读回与原计划零格差", not dc["diffs"], "差异 %d 格 %s" % (len(dc["diffs"]), dc["diffs"][:2]))
    v2 = val(cplan)
    check("T1.10 CSV 读回仍过契约", v2["ok"], v2["errors"][:2])

    rwc = RC["Workouts"]
    mrows = [r for r in plan["Workouts"] if r[rwc["category"]] in SCH["anchors"]]
    def want_pct(r):
        return round(float(r[rwc["load"]]) / P[SCH["anchors"][r[rwc["category"]]]], CP["pct_decimals"])
    empty = [r for r in mrows if px._empty(r[rwc["pct"]])]
    off = [r for r in mrows if not px._empty(r[rwc["pct"]]) and abs(float(r[rwc["pct"]]) - want_pct(r)) > 1e-9]
    check("T1.11 主项行导出 pct_1rm = round(load/anchor, %s) 且不留空" % CP["pct_decimals"],
          len(mrows) > 0 and not empty and not off,
          "主项行 %d / 空 pct %d / 偏离 %d；样例 %s" % (
              len(mrows), len(empty), len(off),
              [(r[rwc["week"]], r[rwc["day"]], r[rwc["load"]], r[rwc["pct"]]) for r in (empty + off)[:2]]))


# ---------------------------------------------------------------- T2 最小四表


def t2(tmp):
    head("T2 最小四表 + %1RM 自动换算")
    plan = minimal_plan()
    v = val(plan)
    check("T2.1 四表即可过契约", v["ok"], v["errors"][:3])
    init = [w for w in v["warnings"] if "可选工作表缺失" in w]
    check("T2.2 可选表缺失只 warning（数量 = 契约可选表数）",
          len(init) == len(OPTIONAL) and all(SCH["sheets"][n]["optional"] for n in OPTIONAL),
          "%d/%d warning: %s" % (len(init), len(OPTIONAL), [w.split("]")[0] + "]" for w in init]))

    state = px.plan_dict_to_state(plan, base_seed=SEED, sch=SCH)
    ex_a = state["weeks"]["1"]["A"]["exercises"][0]
    want_a = px.mround(P["sq"] * 0.70, CP["round_step_kg"])
    check("T2.3 '70%%' 写法被当作 0.70 换算（pct_decimals=%s）" % CP["pct_decimals"],
          abs(ex_a["load"] - want_a) < 1e-9, "load=%s，期望 mround(%s×0.70, %s)=%s" % (ex_a["load"], P["sq"], CP["round_step_kg"], want_a))
    proto = SEED["proto"]["T1.5x5"]
    check("T2.4 处方列由 proto 兜底", ex_a["reps"] == proto["reps"] and ex_a["rx"] == proto["rx"],
          "reps=%s rx=%s" % (ex_a["reps"], ex_a["rx"]))

    declared = plan["Workouts"][2][col("Workouts", "load")]
    ex_b = state["weeks"]["2"]["B"]["exercises"][0]
    want_b = px.mround(P["dl"] * 0.70, CP["round_step_kg"])
    check("T2.5 %1RM 权威：load_kg 被覆写（决策 D10）", declared == 130.0 and abs(ex_b["load"] - want_b) < 1e-9,
          "工作簿写 %s，导入得 %s（pct 推导值）" % (declared, ex_b["load"]))

    ex_w3 = state["weeks"]["3"]["A"]["exercises"][0]
    check("T2.6 缺 target_rpe 时按周取块 RPE（训练周 base / 减载周 deload）",
          ex_b["targetRpe"] == 7.5 and ex_w3["targetRpe"] == 6.0,
          "第2周=%s 第3周=%s" % (ex_b["targetRpe"], ex_w3["targetRpe"]))
    check("T2.7 row_idx 按 first[day]+seq-1 补齐",
          ex_a["row"] == FIRST["A"] and ex_b["row"] == FIRST["B"], "A=%s B=%s" % (ex_a["row"], ex_b["row"]))

    st = state["structure"]
    check("T2.8 结构默认值来自契约", st["totalWeeks"] == 3 and st["daysPerWeek"] == 2
          and st["version"] == SCH["state_defaults_on_import"]["structure.version"],
          "totalWeeks=%s daysPerWeek=%s version=%s" % (st["totalWeeks"], st["daysPerWeek"], st["version"]))
    check("T2.9 块编号重编为 B1..Bn", [b["id"] for b in st["blocks"]] == ["B1"], str([b["id"] for b in st["blocks"]]))
    check("T2.10 ohp 由 bp_1rm 推导", state["profile"]["ohp"] == px.mround(P["bp"] * 0.72, CP["round_step_kg"]),
          "ohp=%s" % state["profile"]["ohp"])
    check("T2.11 initBw / 杠铃配置补齐", state["profile"]["initBw"] == P["bw"]
          and state["plateCfg"]["barKg"] == PROF["bar_kg"]["default"]
          and state["plateCfg"]["collars"] is PROF["collars"]["default"],
          "initBw=%s plateCfg=%s" % (state["profile"]["initBw"], state["plateCfg"]))
    check("T2.12 GPP 菜单定义回落 base seed", len(state["gpp"]) == len(SEED["gpp"]), "gpp=%d 项" % len(state["gpp"]))
    wk1 = state["weeks"]["1"]
    check("T2.13 空遥测结构仍逐日生成，bio.day 取星期标签",
          all(d in wk1 for d in ("A", "B", "gppDays"))
          and [wk1["A"]["bio"]["day"], wk1["B"]["bio"]["day"]] == LABELS[:2],
          "bio.day A=%s B=%s" % (wk1["A"]["bio"]["day"], wk1["B"]["bio"]["day"]))
    _s, _again, diff = px.roundtrip_plan(plan, base_seed=SEED, sch=SCH)
    check("T2.14 手写最小计划：A 里每个已填的非派生格往返后原样保留", not diff["diffs"], diff["diffs"][:2])
    check("T2.15 往返由契约补齐派生列与默认值（B 多于 A 是补全，不是改动）",
          diff["cells_b"] > diff["cells_a"],
          "A %d 格 → B %d 格" % (diff["cells_a"], diff["cells_b"]))
    pct_back = _again["Workouts"][0][col("Workouts", "pct")]
    tol = 0.5 * CP["round_step_kg"] / P["sq"] + 1e-9
    check("T2.16 pct_1rm 是导出时的计算值：反推结果落在半个 round_step 内",
          abs(float(pct_back) - 0.70) <= tol,
          "写 0.7 → load %s → 反推 pct %s（容差 %.5f）" % (state["weeks"]["1"]["A"]["exercises"][0]["load"], pct_back, tol))
    check("T2.17 plan_weeks 未填时按本次 Blocks 之和算（on_missing，不沿用 base 的 %s）"
          % SEED["profile"].get("planWeeks"),
          PROF["plan_weeks"].get("on_missing") == "total_weeks" and state["profile"]["planWeeks"] == 3,
          "planWeeks=%s" % state["profile"]["planWeeks"])
    re_check = val(_again)
    check("T2.18 最小计划 → state → 再导出的工作簿自校验 0 error（build 的收尾检查）",
          re_check["ok"], re_check["errors"][:3])


# ---------------------------------------------------------------- T3 坏输入电池


def bad_cases():
    """(编号, 说明, 篡改函数, 期望 sheet, 期望列, 期望子串) —— 每条必须恰好 1 个 error。"""
    def drop_days(p):
        p.pop("Days")
        return p

    def work_weeks_half(p):
        set_cell(p, "Blocks", 0, "work_weeks", 2.5)
        p["Workouts"] = [r for r in p["Workouts"] if r[col("Workouts", "week")] == 1]
        return p

    def dup_day(p):
        p["Days"].append(dict(p["Days"][0], __row__=3))
        return p

    def dup_workout(p):
        p["Workouts"].append(dict(p["Workouts"][0], __row__=6))
        return p

    def dup_rowidx(p):
        set_cell(p, "Workouts", 0, "row", 9)
        set_cell(p, "Workouts", 1, "row", FIRST["A"])
        return p

    def tel_row(**kw):
        def f(p):
            p["Telemetry"] = sheet_rows("Telemetry", [kw])
            return p
        return f

    def dup_tel(p):
        a = {col("Telemetry", "week"): 1, col("Telemetry", "day"): "A"}
        p["Telemetry"] = sheet_rows("Telemetry", [a, dict(a, __row__=3)])
        return p

    def dup_gpp(p):
        p["GPP"] = sheet_rows("GPP", [gpp_row(1, 0), gpp_row(1, 0, __row__=3)])
        return p

    def conflict_gpp(p):
        p["GPP"] = sheet_rows("GPP", [gpp_row(1, 0), gpp_row(2, 0, item="换个名字的同一项", __row__=3)])
        return p

    return [
        ("T3.01", "缺核心表 Days", drop_days,
         "Days", pcol("Days"), "缺少核心工作表"),
        ("T3.02", "schema_ver 写成别的契约", lambda p: set_field(p, "schema_ver", "RPL-Plan-v0"),
         "Profile", "schema_ver", "既不在现行清单也不在 legacy 清单"),
        ("T3.03", "start_date 非 ISO 形状", lambda p: set_field(p, "start_date", "2026-11-2"),
         "Profile", "start_date", "日期需匹配"),
        ("T3.04", "bw_kg 越界", lambda p: set_field(p, "bw_kg", 850),
         "Profile", "bw_kg", "越界"),
        ("T3.05", "gender 非枚举", lambda p: set_field(p, "gender", "X"),
         "Profile", "gender", "取值应为"),
        ("T3.06", "plan_weeks 与 Blocks 之和不符", lambda p: set_field(p, "plan_weeks", 16),
         "Profile", "plan_weeks", "与 Blocks 周数之和"),
        ("T3.07", "cycle_type 非枚举", lambda p: set_cell(p, "Blocks", 0, "cycle_type", "Super"),
         "Blocks", "cycle_type", "取值应为"),
        ("T3.08", "work_weeks 非整数", work_weeks_half,
         "Blocks", col("Blocks", "work_weeks"), "应为整数周数"),
        ("T3.09", "day_id 重复", dup_day, "Days", pcol("Days"), "重复"),
        ("T3.10", "未知训练标签", lambda p: set_cell(p, "Days", 0, "tags", "tag_nope"),
         "Days", col("Days", "tags"), "未知标签"),
        ("T3.11", "week 超出计划周数", lambda p: set_cell(p, "Workouts", 0, "week", 9),
         "Workouts", col("Workouts", "week"), "超出 Blocks 合计周数"),
        ("T3.12", "day 未在 Days 表定义", lambda p: set_cell(p, "Workouts", 0, "day", "Z"),
         "Workouts", col("Workouts", "day"), "未在 Days 表定义"),
        ("T3.13", "mode 不在 proto", lambda p: set_cell(p, "Workouts", 0, "mode", "T9.Foo"),
         "Workouts", col("Workouts", "mode"), "不在 proto"),
        ("T3.14", "category 不在 lib.categories", lambda p: set_cell(p, "Workouts", 0, "category", "S.Nope"),
         "Workouts", col("Workouts", "category"), "不在 lib.categories"),
        ("T3.15", "target_rpe 越界", lambda p: set_cell(p, "Workouts", 1, "target_rpe", 12),
         "Workouts", col("Workouts", "target_rpe"), "越界"),
        ("T3.16", "主项 pct 与 load 同时缺", lambda p: set_cell(p, "Workouts", 0, "pct", ""),
         "Workouts", col("Workouts", "pct"), "主项动作必须给"),
        ("T3.17", "(week, day, row_idx) 重复", dup_rowidx, "Workouts", UNIQ["Workouts"], "重复的"),
        ("T3.18", "同一 (week, day) 内 seq 重复", dup_workout, "Workouts", col("Workouts", "seq"), "内 seq"),
        ("T3.19", "遥测 week 越界", tel_row(**{col("Telemetry", "week"): 8, col("Telemetry", "day"): "A"}),
         "Telemetry", col("Telemetry", "week"), "不在 1.."),
        ("T3.20", "fuel_strategy 非枚举",
         tel_row(**{col("Telemetry", "week"): 1, col("Telemetry", "day"): "A", "fuel_strategy": "pizza"}),
         "Telemetry", "fuel_strategy", "取值应为"),
        ("T3.21", "遥测 (week, day) 重复", dup_tel, "Telemetry", UNIQ["Telemetry"], "重复的"),
        ("T3.22", "GPP (week, item_idx) 重复", dup_gpp, "GPP", UNIQ["GPP"], "重复的"),
        ("T3.23", "同一 item_idx 定义冲突", conflict_gpp, "GPP", col("GPP", "item_name"), "定义不一致"),
    ]


def t3(tmp):
    head("T3 坏输入电池（每条须恰好 1 个 error，且 [sheet!Row行.列] 精确命中）")
    fmt = re.compile(r"^\[([A-Za-z]+)!Row(-|\d+)\.([A-Za-z0-9_]+)\] .+")
    n_ok = 0
    for cid, desc, mutate, want_sheet, want_col, want_sub in bad_cases():
        res = val(mutate(minimal_plan()))
        errs, warns = res["errors"], res["warnings"]
        hit = [e for e in errs if want_sub in e and want_col in e]
        m = fmt.match(hit[0]) if len(hit) == 1 else None
        ok = bool(len(errs) == 1 and m and m.group(1) == want_sheet and m.group(3) == want_col)
        check("%s %s" % (cid, desc), ok, (hit or errs or warns or ["无 error"])[:1])
        if not ok:
            print("      errors=%s ⏎ warnings=%s" % (errs[:3], warns[:2]))
        n_ok += 1 if ok else 0
    check("T3.24 全部 %d 条坏输入命中" % len(bad_cases()), n_ok == len(bad_cases()), "%d/%d" % (n_ok, len(bad_cases())))

    p = set_cell(minimal_plan(), "Workouts", 0, "movement", "High-bar Squt")
    r1 = val(p)
    typo = [w for w in r1["warnings"] if col("Workouts", "movement") in w]
    check("T3.25 动作名拼错 → warning 而非 error", r1["ok"] and len(typo) == 1, typo[:1] or r1["warnings"])

    big = [w for w in val(minimal_plan())["warnings"] if col("Workouts", "load") in w and "为权威" in w]
    check("T3.26 load 偏差 > %skg → warning 且声明以 pct 为准（D10）" % CP["tolerance_kg"],
          len(big) == 1, big[:1])

    exact = px.mround(P["dl"] * 0.70, CP["round_step_kg"]) + CP["tolerance_kg"]
    r3 = val(set_cell(minimal_plan(), "Workouts", 2, "load", exact))
    check("T3.27 偏差恰等于容差时不报（判据是 >，不是 >=）",
          not [w for w in r3["warnings"] if col("Workouts", "load") in w], r3["warnings"])


def t3b(tmp):
    head("T3b 训练日安全约束：宽松 warning / 严格 error")
    plan = minimal_plan()
    del plan["Workouts"][3]  # 第 3 天(A)那条 B.Main 也违规，会让计数变成 4
    plan["Days"] = sheet_rows("Days", [
        {"day_id": "A", "title_zh": "深蹲日", "weekday_offset": 0,
         "forbid_heavy_sbd": True, "forbid_t1_main": True},
        {"day_id": "B", "title_zh": "硬拉日", "weekday_offset": 1}])
    loose, strict = val(plan), val(plan, strict=True)
    hits = [w for w in loose["warnings"] if "违反" in w]
    errs = [e for e in strict["errors"] if "违反" in e]
    check("T3b.1 违约束的行在宽松模式只 warning", loose["ok"] and len(hits) == 2, hits[:2])
    check("T3b.2 --strict-constraints 把同样的违规升级为 error", not strict["ok"] and len(errs) == 2,
          "%d 条 %s" % (len(errs), errs[:2]))
    why = next(c["why"] for c in SCH["constraint_rules"] if c["when"] == "forbidHeavySbd")
    check("T3b.3 违规文案取自契约 constraint_rules", any(why in h for h in hits), why[:48])


# ---------------------------------------------------------------- T4 权威源表只读


def t4(tmp):
    head("T4 权威源表只读（硬边界 1）")
    path = authoritative_xlsx()
    data_dir = os.path.dirname(path)
    check("T4.1 权威源表存在且未被移动", os.path.exists(path), path)
    before, listing_before = sha256(path), sorted(os.listdir(data_dir))

    plan = seed_plan()
    px.plan_to_book(plan, os.path.join(tmp, "t4.xlsx"), SCH)
    px.book_to_plan(os.path.join(tmp, "t4.xlsx"), SCH)
    px.state_to_plan_book(SEED, os.path.join(tmp, "t4csv"), SCH)
    px.roundtrip_book(os.path.join(tmp, "t4.xlsx"), os.path.join(tmp, "t4.rt.xlsx"), base_seed=SEED, sch=SCH)

    check("T4.2 四种落盘操作后源表字节不变", sha256(path) == before, before[:16] + "…")
    check("T4.3 data/ 目录内容不变", sorted(os.listdir(data_dir)) == listing_before,
          "前 %d 项 / 后 %d 项" % (len(listing_before), len(os.listdir(data_dir))))
    src = open(os.path.join(_HERE, "plan_xlsx.py"), encoding="utf-8").read()
    mods = set(re.findall(r"^(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", src, re.M))
    check("T4.4 plan_xlsx 不 import rxlib、不引用 data/ 路径（D8 + 硬边界 1）",
          "rxlib" not in mods and '"data"' not in src and "openpyxl" in mods and "wkbook" in mods,
          "imports=%s" % ",".join(sorted(mods)))
    mod = [l.strip() for l in src.splitlines() if re.match(r"^\s*(import|from)\s", l)]
    check("T4.5 依赖面只有 openpyxl + wkbook + 标准库",
          all(re.match(r"^(import|from)\s+(argparse|copy|csv|datetime|json|math|os|re|sys|openpyxl|wkbook|__future__)\b", m)
              for m in mod), " | ".join(mod))


# ---------------------------------------------------------------- T5 六日 A–F


def six_day_plan():
    plan = minimal_plan()
    ids = SCH["sheets"]["Days"]["enums"]["day_id"]
    plan["Days"] = sheet_rows("Days", [{"day_id": d, "title_zh": "训练日 %s" % d, "weekday_offset": i}
                                       for i, d in enumerate(ids)])
    cats = ["S.Main", "B.Main", "D.Main", "S.Core", "B.Triceps", "D.GluteHam"]
    mvs = ["High-bar Squat", "Mid-grip Bench", "Conventional Deadlift",
           "Ab Wheel Rollout", "Tempo Squat", "Romanian Deadlift"]
    workouts = []
    for wk in (1, 2):
        for i, did in enumerate(ids):
            workouts.append(wrow(wk, did, 1, "T1.5x5" if i < 3 else "T2.Mod", cats[i], mvs[i], pct=0.7))
            workouts.append(wrow(wk, did, 2, "T3.Mod", cats[(i + 3) % 6], mvs[(i + 3) % 6], load=20.0))
    plan["Workouts"] = sheet_rows("Workouts", workouts)
    return plan


def t5(tmp):
    head("T5 六日 A–F（契约新造面）+ row_idx 几何对账")
    first = px.row_first_map(SCH)
    ids = SCH["sheets"]["Days"]["enums"]["day_id"]
    check("T5.1 row_idx.first 覆盖 A–F 且按 9+12(n-1) 等距",
          list(first) == ids and all(first[k] == FIRST["A"] + 12 * i for i, k in enumerate(ids)), str(first))
    try:
        forked = copy.deepcopy(SCH)
        forked["row_idx"]["first"]["A"] = FIRST["A"] + 1
        px.row_first_map(forked)
        check("T5.2 wkbook 与契约几何分叉时立刻报错", False, "改小坐标后 row_first_map 仍返回结果")
    except ValueError as exc:
        check("T5.2 wkbook 与契约几何分叉时立刻报错", "row_idx" in str(exc), str(exc)[:90])

    plan = six_day_plan()
    res = val(plan)
    check("T5.3 六日计划过契约", res["ok"], res["errors"][:3])
    state = px.plan_dict_to_state(plan, base_seed=SEED, sch=SCH)
    check("T5.4 daysPerWeek = Days 行数", state["structure"]["daysPerWeek"] == 6,
          "daysPerWeek=%s" % state["structure"]["daysPerWeek"])
    got = [state["weeks"]["1"][d]["bio"]["day"] for d in ids]
    check("T5.5 bio.day 按 weekday_offset 回填 Mon–Sat", got == LABELS[:6], str(got))
    rows = {d: state["weeks"]["1"][d]["exercises"][0]["row"] for d in ids}
    check("T5.6 六日首行行号 = first[day]", rows == {d: first[d] for d in ids}, str(rows))

    again = px.state_to_plan_dict(state, SCH)
    w = again["Workouts"]
    check("T5.7 再导出的 row_idx 与几何公式一致",
          all(r[col("Workouts", "row")] == first[r[col("Workouts", "day")]] + r[col("Workouts", "seq")] - 1 for r in w),
          "%d 行 / %d 日" % (len(w), len({r[col("Workouts", "day")] for r in w})))
    _s, _p, diff = px.roundtrip_plan(plan, base_seed=SEED, sch=SCH)
    check("T5.8 六日计划往返：非派生格零差异", not diff["diffs"],
          "%d 格 → %d 格，差异 %d %s" % (diff["cells_a"], diff["cells_b"], len(diff["diffs"]), diff["diffs"][:1]))
    xlsx = os.path.join(tmp, "six.xlsx")
    px.plan_to_book(again, xlsx, SCH)
    back, errs = px.book_to_plan(xlsx, SCH)
    check("T5.9 六日工作簿可原样读回", not errs and len(back["Workouts"]) == len(w),
          errs[:2] or "%d 行" % len(back["Workouts"]))


# ---------------------------------------------------------------- T6 归档 + 冻结


def t6(tmp):
    head("T6 归档 + 冻结（决策 D4：structure.inactiveWeeks）")
    plan = seed_plan()
    last_seed_week = max(int(k) for k in SEED["weeks"])
    blocks_keep = plan["Blocks"][:-1]          # 砍掉末段：留几块跟着种子的块数走，但必须真的缩短
    total = _sum_weeks(blocks_keep)
    check("T6.0 缩短用例真的缩短了（留 %d/%d 块 = %d 周 < 种子 %d 周）"
          % (len(blocks_keep), len(plan["Blocks"]), total, last_seed_week),
          0 < total < last_seed_week,
          "inactiveWeeks 为空时下面六条全会空转，所以先把「确实缩短了」钉住")
    short = dict(plan)
    short["Blocks"] = blocks_keep
    for sheet, role in (("Workouts", "week"), ("Telemetry", "week"), ("GPP", "week")):
        short[sheet] = [r for r in plan[sheet] if px._int(r[col(sheet, role)]) <= total]
    set_field(short, "plan_weeks", total)

    res = val(short)
    check("T6.1 缩短后的计划过契约（%d 周）" % total, res["ok"], res["errors"][:2])
    state = px.plan_dict_to_state(short, base_seed=SEED, sch=SCH)
    st, base_weeks = state["structure"], len(SEED["weeks"])
    check("T6.2 totalWeeks 取新计划周数、daysPerWeek 取 Days 行数",
          st["totalWeeks"] == total and st["daysPerWeek"] == len(plan["Days"]),
          "totalWeeks=%s daysPerWeek=%s" % (st["totalWeeks"], st["daysPerWeek"]))
    check("T6.3 超出的既有周键登记为冻结（不删除）",
          st.get("inactiveWeeks") == list(range(total + 1, base_weeks + 1)) and len(state["weeks"]) == base_weeks,
          "inactiveWeeks=%s，weeks 仍在 %d/%d 周" % (st.get("inactiveWeeks"), len(state["weeks"]), base_weeks))
    same = all(len(state["weeks"][str(w)][d]["exercises"]) == len(SEED["weeks"][str(w)][d]["exercises"])
               for w in range(total + 1, base_weeks + 1) for d in "ABCD")
    check("T6.4 冻结周的动作数据一字未删", same,
          "周 %d–%d 每日动作数 %s" % (total + 1, base_weeks,
                                      sorted({len(state["weeks"][str(w)]["A"]["exercises"]) for w in range(total + 1, base_weeks + 1)})))
    frozen_day = str(last_seed_week)
    check("T6.5 冻结周内容与基线同值（deepcopy 而非重算）",
          state["weeks"][frozen_day]["A"]["exercises"][0] == copy.deepcopy(SEED["weeks"][frozen_day]["A"]["exercises"][0]),
          "周 %s A 日首项 mv=%s row=%s" % (frozen_day, SEED["weeks"][frozen_day]["A"]["exercises"][0].get("mv"),
                                           SEED["weeks"][frozen_day]["A"]["exercises"][0].get("row")))
    re_out = px.state_to_plan_dict(state, SCH)
    active = [px._int(r[col("Workouts", "week")]) for r in re_out["Workouts"]]
    check("T6.6 再导出只写未冻结的周", max(active) == total and len(set(active)) == total,
          "最大周=%s，覆盖 %s 周，动作行 %s / 遥测行 %s / GPP 行 %s"
          % (max(active), len(set(active)), len(active), len(re_out["Telemetry"]), len(re_out["GPP"])))

    _s, again, diff = px.roundtrip_plan(short, base_seed=SEED, sch=SCH)
    check("T6.7 缩短计划也零格差往返", not diff["diffs"],
          "%d 格 → %d 格，差异 %d %s" % (diff["cells_a"], diff["cells_b"], len(diff["diffs"]), diff["diffs"][:1]))
    frozen_again = px.plan_dict_to_state(again, base_seed=SEED, sch=SCH)
    check("T6.8 冻结集在往返后仍成立（幂等）",
          frozen_again["structure"].get("inactiveWeeks") == st["inactiveWeeks"]
          and len(frozen_again["weeks"]) == base_weeks,
          "inactiveWeeks=%s weeks=%d" % (frozen_again["structure"].get("inactiveWeeks"), len(frozen_again["weeks"])))
    no_base = px.plan_dict_to_state(short, base_seed=None, sch=SCH)
    check("T6.9 无 base_seed 时回落 tools/seed.json",
          no_base["structure"].get("inactiveWeeks") == st["inactiveWeeks"] and len(no_base["gpp"]) == len(SEED["gpp"]),
          "inactiveWeeks=%s gpp=%d" % (no_base["structure"].get("inactiveWeeks"), len(no_base["gpp"])))
    out = os.path.join(tmp, "short.xlsx")
    px.plan_to_book(again, out, SCH)
    check("T6.10 缩短计划可落盘并原样读回", len(px.book_to_plan(out, SCH)[0]["Workouts"]) == len(short["Workouts"]),
          "%d 行 vs 期望 %d" % (len(px.book_to_plan(out, SCH)[0]["Workouts"]), len(short["Workouts"])))


def _sum_weeks(block_rows):
    """Blocks 行 → 合计周数（列名经 role_columns/keys 求逆得到，不写死）。"""
    spec = SCH["sheets"]["Blocks"]
    state_fields = set(px._week_count_fields(SCH))
    cols = [c for c, key in spec["keys"].items() if key in state_fields]
    return sum(px._int(r.get(c)) or 0 for r in block_rows for c in cols)


RUNNERS = [("T1", t1), ("T2", t2), ("T3", t3), ("T3b", t3b), ("T4", t4), ("T5", t5), ("T6", t6)]


# ---------------------------------------------------------------- T7 JSON 信封（交换唯一权威载体）
def t7(tmp):
    head("T7 JSON 计划信封：契约单源 / 往返同形 / 坏信封电池")
    exc = px.load_exchange_schema()
    spec = exc["plan_envelope"]
    vf = spec["schema_version_field"]

    env = px.build_envelope(SEED, exported_at="2026-01-01T00:00:00", ver="9.99", exc=exc)
    res = px.validate_envelope(env, exc=exc)
    check("T7.1 seed → 信封过校验（0 error）", res["ok"], "；".join(res["errors"][:3]))
    check("T7.2 头部键序 == 契约 key_order", list(env.keys())[:len(spec["key_order"])] == spec["key_order"],
          str(list(env.keys())))
    check("T7.3 信封自带契约版本（%s=%s）且载荷即六表字典" % (vf, spec["current"]),
          env.get(vf) == spec["current"] and set(env["plan"].keys()) >= set(SCH["sheet_order"]),
          "plan 表: %s" % sorted(env["plan"].keys()))

    txt = px.envelope_to_text(env)
    again = json.loads(txt)
    check("T7.4 文本往返：loads(envelope_to_text(env)) 与原信封全等且仍过校验",
          again == env and px.validate_envelope(again, exc=exc)["ok"])
    det = px.envelope_to_text(px.build_envelope(SEED, exported_at="2026-01-01T00:00:00",
                                                ver="9.99", exc=exc))
    check("T7.5 确定性：同 exportedAt/ver 两次构建逐字节相同（AI 侧可复算摘要）", det == txt)

    def env_err(e, want_frag, label):
        r = px.validate_envelope(e, exc=exc)
        ok = (not r["ok"]) and any(want_frag in x for x in r["errors"])
        check(label, ok, "；".join(r["errors"][:2]) if r["errors"] else "竟然通过")

    bad = dict(env); bad["format"] = "Something-Else"
    env_err(bad, "format", "T7.6 坏信封：format 不认识 → 整份拒收")
    bad = dict(env); bad[vf] = "RPL-Plan-v999"
    env_err(bad, "不在接受清单", "T7.7 坏信封：未知 schemaVersion → 拒收（绝不静默降级）")
    for k in spec["required_keys"]:
        bad = {kk: vv for kk, vv in env.items() if kk != k}
        env_err(bad, "缺必带键", "T7.8 坏信封：缺 %s → 拒收" % k)
    bad = dict(env); bad["app"] = {"name": "x"}
    env_err(bad, "app", "T7.9 坏信封：app 缺 version → 拒收")
    bad = dict(env); bad["plan"] = {"Workouts": []}
    env_err(bad, "", "T7.10 坏信封：plan 载荷缺表 → 载荷层校验拒收")
    r = px.validate_envelope(["not", "a", "dict"], exc=exc)
    check("T7.11 坏信封：非对象 → 拒收", not r["ok"], str(r["errors"][:1]))
    reorder = {k: env[k] for k in reversed(spec["key_order"])}
    reorder["plan"] = env["plan"]
    env_err(reorder, "键序", "T7.12 坏信封：头部键序被打乱 → 拒收")

    out = os.path.join(tmp, "envelope.json")
    rc = px.main(["json", "--out", out, "--ver", "9.99"])
    cli_ok = rc == 0 and os.path.exists(out)
    if cli_ok:
        with open(out, encoding="utf-8") as fh:
            cli_env = json.load(fh)
        cli_ok = px.validate_envelope(cli_env, exc=exc)["ok"] and cli_env["plan"] == env["plan"]
    check("T7.13 CLI `json` 子命令：导出 → 读回 → 过校验且载荷与直构相同", cli_ok, "rc=%s" % rc)
    rc2 = px.main(["json", "--check", out]) if cli_ok else 1
    check("T7.14 CLI `json --check`：校验既有信封，rc=0", rc2 == 0, "rc=%s" % rc2)
    tampered = os.path.join(tmp, "envelope_bad.json")
    with open(tampered, "w", encoding="utf-8") as fh:
        json.dump(dict(env, **{vf: "RPL-Plan-v0"}), fh, ensure_ascii=False)
    rc3 = px.main(["json", "--check", tampered])
    check("T7.15 CLI `json --check`：被篡改的信封 rc≠0（能红）", rc3 != 0, "rc=%s" % rc3)


RUNNERS.append(("T7", t7))


# ---------------------------------------------------------------- T8 JSONL 训练日志（只导不入）
def t8(tmp):
    head("T8 JSONL 训练日志：列名单源 / META 头 / 坏日志电池（Python 侧只校验不重建）")
    exc = px.load_exchange_schema()
    spec = exc["log_jsonl"]
    hdr = spec["header_record"]
    try:
        cols = px.csv_cols_from_template()
        cols_err = None
    except ValueError as e:
        cols, cols_err = [], str(e)
    check("T8.0 列名清单可解析（模板 26 列 + 契约逐列对账，任一不过则整套日志校验无主）",
          cols_err is None, cols_err or "%d 列在手" % len(cols))

    check("T8.1 CSV_COLS 单源取自 template.html：26 列、首列 schema_ver、末列 aux_week_mask（协议冻结）",
          len(cols) == 26 and cols[0] == "schema_ver" and cols[-1] == "aux_week_mask",
          "%d 列 / %s…%s" % (len(cols), cols[0], cols[-1]))

    frozen = spec.get("record_keys_frozen") or []
    check("T8.1b 契约 record_keys_frozen 是 26 列权威，且与模板逐列全等（v0.13 起 S7 的另一端）",
          len(frozen) == 26 and frozen == cols,
          "契约 %d 列 / %s" % (len(frozen), "全等" if frozen == cols else "分叉"))

    if len(frozen) == 26:
        forked = json.loads(json.dumps(exc))
        fl = forked["log_jsonl"]["record_keys_frozen"]
        fl[9], fl[10] = fl[10], fl[9]
        try:
            px.csv_cols_from_template(exc=forked)
            forked_ok, fork_msg = False, "竟然没抛"
        except ValueError as e:
            forked_ok, fork_msg = "分叉" in str(e), str(e)[:70]
    else:
        forked_ok, fork_msg = False, "契约清单不足 26 列，分叉演示无从做起"
    check("T8.1c 契约列序被就地改（不换版本号）→ csv_cols_from_template 抛错（协议不可静默漂移）",
          forked_ok, fork_msg)

    def meta_rec(**over):
        m = {hdr["type_key"]: hdr["type_value"], "schema_ver": spec["current"],
             hdr["schema_ver_value_field"]: hdr["csv_protocol_accepted"][0],
             "app_name": exc["plan_envelope"]["app_name"], "app_version": "9.99",
             "exportedAt": "2026-01-01T00:00:00"}
        m.update(over)
        return m

    def data_rec(**over):
        r = {c: "" for c in cols}
        r.update({"schema_ver": "1", "record_type": "EXERCISE", "movement": "Squat"})
        r.update(over)
        return r

    def jsonl(meta, recs):
        lines = [json.dumps(meta, ensure_ascii=False)]
        lines += [json.dumps(r, ensure_ascii=False) for r in recs]
        return "\n".join(lines) + "\n"

    good = jsonl(meta_rec(), [data_rec(), data_rec(record_type="TELEMETRY")])
    r = px.validate_log_jsonl(good, exc=exc, cols=cols)
    check("T8.2 合规 JSONL（META 头 + 两条 26 键记录）过校验（0 error）", r["ok"], "；".join(r["errors"][:3]))

    def log_err(text, want_frag, label):
        rr = px.validate_log_jsonl(text, exc=exc, cols=cols)
        ok = (not rr["ok"]) and any(want_frag in x for x in rr["errors"])
        check(label, ok, "；".join(rr["errors"][:2]) if rr["errors"] else "竟然通过")

    bad = dict(meta_rec()); bad.pop("app_version")
    log_err(jsonl(bad, [data_rec()]), "缺必带键", "T8.3 坏日志：META 缺 app_version → 拒收")
    log_err(jsonl(meta_rec(schema_ver="RPL-Log-v999"), [data_rec()]), "schema_ver",
            "T8.4 坏日志：META schema_ver 不认识 → 拒收")
    log_err(jsonl(meta_rec(**{hdr["schema_ver_value_field"]: "v0.0"}), [data_rec()]), "不在接受清单",
            "T8.5 坏日志：csv_protocol 不在接受清单 → 拒收")
    log_err(jsonl(meta_rec(**{hdr["type_key"]: "NOTMETA"}), [data_rec()]), hdr["type_key"],
            "T8.6 坏日志：首行 record_type 不是 META → 拒收")

    short = data_rec(); short.pop("movement")
    log_err(jsonl(meta_rec(), [short]), "键集与 CSV_COLS 不符",
            "T8.7 坏日志：数据记录缺一列（movement）→ 拒收")
    extra = data_rec(); extra["bogus_col"] = "x"
    log_err(jsonl(meta_rec(), [extra]), "键集与 CSV_COLS 不符",
            "T8.8 坏日志：数据记录多一列（bogus_col）→ 拒收")
    log_err("", "空文件", "T8.9 坏日志：空文件 → 拒收")
    log_err(json.dumps(meta_rec(), ensure_ascii=False) + "\n{not json}\n", "不是合法 JSON",
            "T8.10 坏日志：数据行不是合法 JSON → 拒收")

    good_path = os.path.join(tmp, "log.jsonl")
    with open(good_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(good)
    rc = px.main(["logjsonl", "--check", good_path])
    check("T8.11 CLI `logjsonl --check`：合规日志 rc=0", rc == 0, "rc=%s" % rc)
    bad_path = os.path.join(tmp, "log_bad.jsonl")
    with open(bad_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(jsonl(meta_rec(), [short]))
    rc2 = px.main(["logjsonl", "--check", bad_path])
    check("T8.12 CLI `logjsonl --check`：缺列日志 rc≠0（能红）", rc2 != 0, "rc=%s" % rc2)


RUNNERS.append(("T8", t8))


# ---------------------------------------------------------------- T9 Gear 附表 + v1/v2 路由


def gear_row(week, day, row_idx, gear, source="plan", kind=None):
    r = RC["Gear"]
    gj = "" if gear is None else px._gear_canonical_json(gear)
    return {r["week"]: week, r["day"]: day, r["row"]: row_idx,
            r["kind"]: kind if kind is not None else ("" if gear is None else gear.get("kind", "")),
            r["source"]: source, r["gear_json"]: gj}


def t9(tmp):
    head("T9 Gear 附表 + legacy v1/v2 路由（v0.44 契约 v3：八表，旧 Armor 档照旧可导并迁进 GPP）")

    seed_plan_dict = seed_plan()
    order3 = px._effective_order(seed_plan_dict, SCH)
    check("T9.0a 现行导出命中 v3 效序（八表）", order3 == SCH["sheet_order"], str(order3))
    V1_ORDER = LEGACY_ENTRIES[0]["sheet_order"]
    legacy = to_legacy(seed_plan_dict, "RPL-Plan-v1", with_gear=False)
    order1 = px._effective_order(legacy, SCH)
    check("T9.0b v1 legacy 命中旧六表序（Armor，无 Gear/GPP/Level）",
          order1 == V1_ORDER, str(order1))
    vl = val(legacy)
    check("T9.0c v1 legacy 计划过契约：无 error，且不因 Gear/GPP/Level 缺席发 warning",
          vl["ok"] and not [w for w in vl["warnings"] if any(x in w for x in ("Gear", "GPP", "Level"))],
          vl["warnings"][:3])
    st_legacy = px.plan_dict_to_state(legacy, base_seed=SEED, sch=SCH)
    back = px.state_to_plan_dict(st_legacy, SCH)
    check("T9.0d legacy 载入后导出升级为现行八表，schema_ver 写 v3",
          list(back.keys()) == SCH["sheet_order"]
          and [r[COLS["Profile"][1]] for r in back["Profile"]
               if r[pcol("Profile")] == "schema_ver"] == [SCH["schema_ver"]])
    check("T9.0d2 旧 Armor 表定义迁进 state.gpp（domain/item/rx 逐项保留）",
          len(st_legacy["gpp"]) == len(SEED["gpp"])
          and st_legacy["gpp"][0]["rx"] == SEED["gpp"][0]["rx"]
          and st_legacy["gpp"][0]["domain"] == SEED["gpp"][0]["domain"],
          "gpp=%d 项，首项 rx=%r" % (len(st_legacy["gpp"]), st_legacy["gpp"][0]["rx"]))
    dl = px.diff_plan_cells(legacy, back, SCH)
    check("T9.0e legacy→state→现行导出 零格差（Armor 表与版本升级行已豁免）", not dl["diffs"], dl["diffs"][:3])
    for e in LEGACY_ENTRIES:
        for alias in e["plan_schema_vers"][1:]:
            p2 = to_legacy(seed_plan_dict, alias, with_gear=("Gear" in e["sheet_order"]))
            check("T9.0f legacy 别名 %r 也按旧表序路由" % alias,
                  px._effective_order(p2, SCH) == e["sheet_order"])

    bad = {k: [dict(r) for r in v] for k, v in legacy.items()}
    set_field(bad, "schema_ver", "RPL-Plan-v9")
    vbad = val(bad)
    check("T9.1 未知 Profile!schema_ver → 契约拒收", (not vbad["ok"])
          and any("既不在现行清单也不在 legacy 清单" in e for e in vbad["errors"]), vbad["errors"][:2])
    try:
        px._load_plan_state(bad, SEED, SCH)
        check("T9.2 未知版本走无闸门装载也被拒（不静默降级）", False, "装载居然通过了")
    except ValueError as e:
        check("T9.2 未知版本走无闸门装载也被拒（不静默降级）", "既不在现行清单也不在 legacy 清单" in str(e))

    plan = minimal_plan()
    rwc = RC["Workouts"]
    rows_a = [r for r in plan["Workouts"] if r[rwc["day"]] == "A" and r[rwc["week"]] == 1]
    row1 = FIRST["A"] + int(rows_a[0][rwc["seq"]]) - 1
    row2 = FIRST["A"] + int(rows_a[1][rwc["seq"]]) - 1
    plan["Gear"] = sheet_rows("Gear", [
        gear_row(1, "A", row1, {"sides": 1, "barKg": 12.5, "kind": "dumbbell"}, source="local"),
        gear_row(1, "A", row2, {"kind": "barbell"}),
    ])
    v = val(plan)
    check("T9.3 带 Gear 的四+一表计划过契约", v["ok"], v["errors"][:3])
    st = px.plan_dict_to_state(plan, base_seed=SEED, sch=SCH)
    a1 = st["weeks"]["1"]["A"]["exercises"][0]
    a2 = st["weeks"]["1"]["A"]["exercises"][1]
    check("T9.4 锚 (week,day,row_idx) 命中：gear 合并进 ex，source=local 才落 gearSource",
          a1.get("gear") == {"barKg": 12.5, "kind": "dumbbell", "sides": 1}
          and a1.get("gearSource") == "local"
          and a2.get("gear") == {"kind": "barbell"} and "gearSource" not in a2,
          "a1=%s/%s a2=%s/%s" % (a1.get("gear"), a1.get("gearSource"), a2.get("gear"), a2.get("gearSource")))
    again = px.state_to_plan_dict(st, SCH)
    dg = px.diff_plan_cells(plan, again, SCH)
    gcols = COLS["Gear"]
    gstrip = lambda rows: [{c: r.get(c, "") for c in gcols} for r in rows]
    check("T9.5 state→plan 再导出：Gear 行按锚回写且逐字节不变（含键排序规范化）",
          gstrip(again.get("Gear") or []) == gstrip(plan.get("Gear") or []) and not dg["diffs"],
          "%s vs %s / diffs %s" % (gstrip(again.get("Gear") or []),
                                   gstrip(plan.get("Gear") or []), dg["diffs"][:2]))
    raw = plan["Gear"][0][col("Gear", "gear_json")]
    check("T9.6 gear_json 写出即 sort_keys 单行紧凑（跨端逐字节对账的前提）",
          raw == '{"barKg":12.5,"kind":"dumbbell","sides":1}', raw)

    def gear_case(mut, why, label):
        q = {k: [dict(r) for r in v] for k, v in plan.items()}
        mut(q)
        r = val(q)
        check(label, (not r["ok"]) and any(why in e for e in r["errors"]), r["errors"][:2])

    gear_case(lambda q: q["Gear"].append(gear_row(1, "A", 9999, {"kind": "barbell"})),
              "在 Workouts 里不存在", "T9.7 Gear 锚不命中 → error")
    gear_case(lambda q: q["Gear"][0].__setitem__(col("Gear", "gear_json"), "{oops"),
              "不是合法 JSON", "T9.8 gear_json 语法坏 → error")
    gear_case(lambda q: q["Gear"][0].__setitem__(col("Gear", "gear_json"), '[1,2]'),
              "应为对象", "T9.9 gear_json 非对象 → error")
    gear_case(lambda q: q["Gear"][0].__setitem__(col("Gear", "kind"), "unobtainium"),
              "不在器械词表", "T9.10 kind 不在词表 → error")
    gear_case(lambda q: q["Gear"][0].__setitem__(col("Gear", "source"), "garage"),
              "不在词表", "T9.11 source 不在词表 → error")
    gear_case(lambda q: q["Gear"].append(dict(q["Gear"][0], **{RC["Gear"]["source"]: "local"})),
              "重复的", "T9.12 同锚重复行 → error")

    x2 = os.path.join(tmp, "v2.xlsx")
    px.plan_to_book(again, x2, SCH)
    info, _out = px.roundtrip_book(x2, os.path.join(tmp, "v2.rt.xlsx"), base_seed=SEED, sch=SCH)
    check("T9.15 v3 八表工作簿落盘往返零格差", not info["diff"]["diffs"], info["diff"]["diffs"][:2])
    xl = os.path.join(tmp, "legacy.xlsx")
    px.plan_to_book(legacy, xl, SCH)
    lp, lerr = px.book_to_plan(xl, SCH)
    check("T9.16 legacy 工作簿按六表读回（无 Gear）且表头无错",
          "Gear" not in lp and not lerr, "%s / %s" % (sorted(lp.keys()), lerr[:2]))
    lst = px.plan_dict_to_state(lp, base_seed=SEED, sch=SCH)
    dlx = px.diff_plan_cells(lp, px.state_to_plan_dict(lst, SCH), SCH)
    check("T9.17 legacy xlsx 全链装载：再导出除版本升级行外零格差",
          not dlx["diffs"] and lst["structure"]["totalWeeks"] == len(SEED["weeks"]),
          "%s / totalWeeks=%s" % (dlx["diffs"][:2], lst["structure"]["totalWeeks"]))

    EXC = px.load_exchange_schema()
    env = px.build_envelope(st, ver="test")
    check("T9.18 信封导出现行 v3 载荷（八表，带 GPP/Gear/Level）",
          env[EXC["plan_envelope"]["schema_version_field"]] == SCH["schema_ver"]
          and list(env["plan"].keys()) == SCH["sheet_order"])
    check("T9.19 v3 信封过校验", px.validate_envelope(env, sch=SCH)["ok"])
    vf = EXC["plan_envelope"]["schema_version_field"]
    old_env = {k: ("RPL-Plan-v1" if k == vf else v) for k, v in env.items()}
    old_env["plan"] = legacy
    r_old = px.validate_envelope(old_env, sch=SCH)
    check("T9.20 v1 信封（六表 Armor 载荷）照收：装载只认 legacy_compat，不注入 v1 契约全文",
          r_old["ok"], r_old["errors"][:2])
    v9_env = {k: ("RPL-Plan-v9" if k == vf else v) for k, v in env.items()}
    check("T9.21 未知信封版本 → 整份拒收", not px.validate_envelope(v9_env, sch=SCH)["ok"])


RUNNERS.append(("T9", t9))


def main():
    pyout.use_utf8_stdout()
    if SEED is None:
        print("找不到 tools/seed.json，无法运行（契约的 proto / lib 与装甲默认值都取自它）")
        return 2
    todo = [r for r in RUNNERS if not GROUPS or any(r[0].startswith(g) for g in GROUPS)]
    tmp = tempfile.mkdtemp(prefix="rpl_plan_test_")
    print("契约 %s ｜ 基线 seed %d 周 / %d 动作 ｜ 临时产物目录 %s"
          % (SCH["schema_ver"], len(SEED["weeks"]), len(SEED["proto"]), tmp))
    try:
        for cid, fn in todo:
            try:
                fn(tmp)
            except Exception as exc:  # 断言之外的崩溃同样算失败，绝不静默放行
                check("%s 执行" % cid, False, "%s: %s" % (type(exc).__name__, exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    n_fail = sum(1 for ok, _l, _d in results if not ok)
    print("\n== test_plan_xlsx: %d PASS / %d FAIL（共 %d 项，%d 组）==" % (
        len(results) - n_fail, n_fail, len(results), len(todo)))
    for ok, label, detail in results:
        if not ok:
            print("   FAIL %s  %s" % (label, detail))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
