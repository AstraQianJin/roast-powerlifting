# -*- coding: utf-8 -*-
"""`xlsxv.js` 的 Python 侧：造工作簿 fixture、导出逐格摘要、回读 App 写出的文件。

    python tools/xlsx_parity.py fixtures <目录>     # 写 fixture 与 expect.json
    python tools/xlsx_parity.py dump <xlsx>         # 单份工作簿 → 逐格摘要（stdout JSON）
    python tools/xlsx_parity.py cases               # 契约校验用例的 Python 侧判定一览
    python tools/xlsx_parity.py numfmt <cases.json> # 一批格子值 → 六个归一化函数的期望串（v0.10 逻辑对账）

为什么需要它：App 内那份读/写引擎是 `plan_xlsx.py` 的第二实现，逐格对账是唯一能证明
两边语义一致的手段。fixture 专挑两边最容易各写各的地方 —— 表序打乱、契约外的表、
Profile 横排、中间空行、多余列、共享字符串与富文本分段、XML 注释、缺 `r` 的格子、
行内字符串、只有公式没有缓存值、日期格式的数值格（内建与自定义 numFmt 各一条）。

列名与字段名一律取自契约，不写字面量；摘要的键用 `px._cell_key`，JS 侧同名同规则的是
`xCellKey`。页面侧语言固定 zh，所以表头对账的错误串也逐字比。
"""
from __future__ import annotations

import copy
import datetime
import io
import json
import math
import os
import sys
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import openpyxl  # noqa: E402
import plan_xlsx as px  # noqa: E402
import pyout  # noqa: E402

SCH = px.load_schema()
ORDER = SCH["sheet_order"]
COLS = {n: SCH["sheets"][n]["columns"] for n in ORDER}
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_DOC = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
EPOCH_1900 = datetime.date(1899, 12, 30)


# ---------------------------------------------------------------- 逐格摘要

def jsonable(v):
    """openpyxl 把日期格式的格子读成 datetime；契约里日期一律按 `date().isoformat()` 记账。"""
    if isinstance(v, (datetime.datetime, datetime.date)):
        return px._date_str(v)
    return v


def cells_of(plan, errors=()):
    """键 = `表|行序|__row__|列`：行序管顺序，`__row__` 管两边的行号推导是否一致。
    Profile 横排时所有行的 `__row__` 都是 1，只按 `__row__` 建键会互相覆盖。"""
    cells = {}
    for name in ORDER:
        for i, row in enumerate(plan.get(name) or []):
            for c in COLS[name]:
                if c in row:
                    cells["%s|%d|%s|%s" % (name, i, row.get("__row__"), c)] = px._cell_key(jsonable(row[c]))
    return {"cells": cells, "errors": list(errors),
            "rows": {n: len(plan.get(n) or []) for n in ORDER}}


def dump(path, with_val=False):
    plan, errors = px.book_to_plan(path, SCH)
    out = cells_of(plan, errors)
    if with_val:
        out["val"] = validate(plan)
    return out


def state_plan_cells(state_path):
    """C4b：state JSON（真文件路径）→ state_to_plan_dict 的逐格摘要 + 计划本体。

    App 里那份 xStateToPlanDict 必须给出逐格相同的字典；计划本体再喂给 xlsx_bytes，
    让「JS 换算 → Python 读回」与「JS 换算 → JS 写出 → Python 读回」共用同一份期望。"""
    with io.open(state_path, encoding="utf-8") as fh:
        st = json.load(fh)
    plan = px.state_to_plan_dict(st, SCH)
    return {"cells": cells_of(plan)["cells"], "plan": plan_jsonable(plan)}


def import_state_cells(xlsx_path):
    """C4b：工作簿 → plan_dict_to_state 的结果 state（去掉 lib/source，两边都按 App 语义换掉），
    连同这次装载的契约判定一起还给 node。"""
    plan, errors = px.book_to_plan(xlsx_path, SCH)
    if errors:
        raise AssertionError("fixture 工作簿表头对账就不过：%s" % errors)
    st = px._load_plan_state(plan, base_seed=px.load_default_seed(), sch=SCH)
    st.pop("lib", None)
    st.pop("source", None)
    res = px.validate_plan_dict(plan, proto=PROTO, lib=LIB, sch=SCH)
    return {"state": _json_state(st),
            "cells": cells_of(px.state_to_plan_dict(st, SCH))["cells"],
            "val": {"ok": res["ok"], "errors": res["errors"], "warnings": res["warnings"]}}


def _json_state(v):
    """datetime 是 plan_dict_to_state 不产出的类型，但为稳妥统一走 jsonable。"""
    if isinstance(v, dict):
        return {k: _json_state(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_json_state(x) for x in v]
    return jsonable(v)


def plan_jsonable(plan):
    return {n: [{c: jsonable(v) for c, v in row.items()} for row in plan.get(n) or []]
            for n in ORDER}


def sheet_col(name, role):
    """按契约 role 取列名，别在测试里写死列。"""
    return SCH["sheets"][name]["role_columns"][role]


def numeric_col(name):
    return sorted(SCH["sheets"][name].get("ranges", {}).keys())[0]


def bool_col(name):
    bs = SCH["sheets"][name].get("bools") or []
    return bs[0] if bs else None


def profile_field(type_name):
    fields = SCH["sheets"]["Profile"]["fields"]
    return [f for f, spec in fields.items() if spec.get("type") == type_name][0]


# ---------------------------------------------------------------- fixture 1：App 导出形态

def f_app(tmp):
    path = os.path.join(tmp, "app.xlsx")
    px.state_to_plan_book(px.load_default_seed(), path, SCH)
    return path, dump(path, True)


# ---------------------------------------------------------------- fixture 2：人手改过的形态

def f_hand(tmp):
    base = px.state_to_plan_dict(px.load_default_seed(), SCH)
    plan = {n: [dict(r) for r in (base.get(n) or [])] for n in ORDER}
    pct, done = sheet_col("Workouts", "pct"), bool_col("Workouts")
    for i, row in enumerate(plan["Workouts"][:6]):
        row[pct] = "75%" if i % 2 else "007"          # 数字样字符串必须原样回来
    if done:
        plan["Workouts"][0][done] = False             # 真布尔：格子类型是 b，不是 0
    wd, day_bool = sheet_col("Days", "day"), bool_col("Days")
    plan["Days"][0][wd] = 3.5                         # 整数列写小数
    if day_bool:
        plan["Days"][0][day_bool] = True

    path = os.path.join(tmp, "hand.xlsx")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    date_field, bool_field = profile_field("date"), profile_field("bool")
    for name in ["Workouts", "说明", "GPP", "Profile", "Blocks", "Days", "Telemetry", "Gear", "Level"]:
        ws = wb.create_sheet(name)
        if name == "说明":                             # 契约外的表：两边都要整体忽略
            ws.append(["这一列表不在契约里", "读侧必须整体忽略"])
            ws.cell(row=3, column=1, value="第 2 行整行空白，也要剔除")
            continue
        cols = COLS[name]
        if name == "Profile":                          # 横排两行：第 1 行字段名、第 2 行取值
            fields = list(SCH["sheets"]["Profile"]["fields"].keys())
            values = {r[cols[0]]: jsonable(r[cols[1]]) for r in plan["Profile"]}
            ws.append(fields)
            ws.append([values.get(f, "") for f in fields])
            c = ws.cell(row=2, column=fields.index(date_field) + 1)
            c.value = datetime.datetime(2026, 11, 2)   # 内建日期格式：openpyxl 回来的是 datetime
            c.number_format = "mm-dd-yy"               # 走 numFmtId 14，styles.xml 里没有 <numFmt> 可查
            if bool_field in fields:
                ws.cell(row=2, column=fields.index(bool_field) + 1).value = True
            continue
        ws.append(list(cols))
        if name == "Days":
            ws.cell(row=1, column=len(cols) + 1, value="extra_note")   # 多余列：表头对账必须报
        r = 2
        for row in plan[name]:
            if name == "Blocks" and r == 4:
                r += 1                                                # 中间留一整行空白
            for j, c in enumerate(cols):
                v = jsonable(row.get(c))
                if v is None or v == "":
                    continue
                ws.cell(row=r, column=j + 1, value=v)
            if name == "Days":
                ws.cell(row=r, column=len(cols) + 1, value="多余列第 %d 行" % r)
            r += 1
    wb.save(path)
    plan2, errors = px.book_to_plan(path, SCH)
    out = cells_of(plan2, errors)
    out["val"] = validate(plan2)
    return path, out


# ---------------------------------------------------------------- fixture 3：手写 XML 的边角形态

def _sheet_xml(rows, col_letter, col_max):
    """rows: [(行号或 None, [(列名或 None, 属性串, 内部 XML 或 None)])]。"""
    body = []
    for rn, cells in rows:
        inner = []
        for ref, cattr, val in cells:
            attrs = (" " + cattr if cattr else "") + (' r="%s"' % ref if ref else "")
            inner.append('<c%s/>' % attrs if val is None else '<c%s>%s</c>' % (attrs, val))
        body.append('<row%s>%s</row>' % (' r="%d"' % rn if rn else "", "".join(inner)))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="%s"><dimension ref="A1:%s1"/>'
            '<sheetViews><sheetView workbookViewId="0"/></sheetViews>'
            '<cols><col min="1" max="%d" width="12"/></cols>'
            '<sheetData>%s</sheetData>'
            '<rowBreaks count="1"><brk id="4" max="16383" man="1"/></rowBreaks>'
            '<conditionalFormatting sqref="A1"><cfRule type="cellIs" operator="equal"/></conditionalFormatting>'
            '</worksheet>') % (NS, col_letter, col_max, "".join(body))


def f_odd(tmp):
    path = os.path.join(tmp, "odd.xlsx")
    cp, cb = COLS["Profile"], COLS["Blocks"]
    serial = (datetime.date(2026, 11, 2) - EPOCH_1900).days
    sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<sst xmlns="%s" count="6" uniqueCount="6">'
           '<si><t>%s</t></si>'
           '<si><t>%s</t></si>'
           '<si><t>%s</t></si>'
           '<si><r><t>富</t></r><r><rPr><b/></rPr><t>文 &amp; 本</t></r></si>'
           '<si><t xml:space="preserve">  前后空格  </t></si>'
           '<si><t>2026-11&#45;02</t></si>'
           '</sst>') % (NS, cp[0], cp[1], cp[2])
    profile = _sheet_xml([
        (1, [("A1", 't="s"', '<v>0</v>'), ("B1", 't="s"', '<v>1</v>'), (None, 't="s"', '<v>2</v>')]),
        (2, [("A2", 't="s"', '<v>5</v>'), ("C2", 't="s"', '<v>4</v>')]),        # B2 缺格：要当空
        (4, [("A4", 't="s"', '<v>3</v>'),
             ("B4", 't="inlineStr"', '<is><t>注释<!-- <c r="Z9"/>"不算格子 --><!-- 另一段 --></t></is>')]),
        (None, [("A6", 't="s"', '<v>0</v>'), ("B6", 't="str"', '<v>+B4&amp;1</v>')]),
        (7, [("A7", 't="s"', '<v>1</v>'), ("B7", 't="n" s="1"', '<v>%d</v>' % serial)]),
        (8, [("A8", 't="s"', '<v>1</v>'), ("B8", 't="b"', '<v>0</v>')]),
        (9, [("A9", 't="s"', '<v>1</v>'), ("B9", 't="s"', '<f>SUM(A1:A8)</f>')]),
        (10, [("B10", '', None)]),                                          # 有格子但没值：openpyxl 给出 None，整行仍要剔除
        (None, []),                                                         # 空行：两边都要剔
    ], "C", 3)
    blocks = _sheet_xml([
        (1, [(None, 't="inlineStr"', '<is><t>%s</t></is>' % c) for c in cb]),
        (2, [("A2", 't="inlineStr"', '<is><t>B1</t></is>'),
             ("B2", 't="inlineStr"', '<is><t>Strength</t></is>'),
             ("C2", 't="inlineStr"', '<is><t>&lt;主项&gt;&quot;周&quot;</t></is>'),
             ("E2", '', '<v>4</v>'), ("I2", 's="0"', '<v>8</v>')]),
    ], "K", len(cb))
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="%s">'
              '<numFmts count="1"><numFmt numFmtId="164" formatCode="yyyy\\-mm\\-dd"/></numFmts>'
              '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
              '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders>'
              '<cellXfs count="2"><xf numFmtId="0" fontId="0"/><xf numFmtId="164" fontId="0"/></cellXfs>'
              '</styleSheet>') % NS
    # Target 一个写成绝对路径、一个写成相对路径：两种都得解析到同一个部件
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="%s">'
            '<Relationship Id="rId1" Type="%s/worksheet" Target="/xl/worksheets/sheet1.xml"/>'
            '<Relationship Target="worksheets/sheet2.xml" Type="%s/worksheet" Id="rId2"/>'
            '</Relationships>') % (REL_PKG, REL_DOC, REL_DOC)
    wbx = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
           '<sheet name="Blocks" sheetId="2" r:id="rId2"/>'
           '<sheet name="Profile" sheetId="1" r:id="rId1"/>'
           '</sheets><definedNames/><calcPr calcId="0"/></workbook>') % (NS, REL_DOC)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="%s">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
          '</Types>') % REL_PKG
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="%s"><Relationship Id="rId1" '
                 'Type="%s/officeDocument" Target="xl/workbook.xml"/></Relationships>') % (REL_PKG, REL_DOC)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", wbx)
        z.writestr("xl/_rels/workbook.xml.rels", rels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/sharedStrings.xml", sst)
        z.writestr("xl/worksheets/sheet1.xml", profile)
        z.writestr("xl/worksheets/sheet2.xml", blocks)
    return path, dump(path, True)


# ---------------------------------------------------------------- 契约校验对账（C4a）
#
# App 内的 validatePlanDict 是 validate_plan_dict 的第二实现。对账用的计划不取 seed
# 那份大计划（16 周 / 400 行动作 ≈ 1 MB，逐个用例发给页面太贵），而是按契约现造一份
# **最小合法计划**，再一个用例只坏一处：每个用例都必须在 Python 侧产生至少一条判定，
# 否则这里直接抛错 —— 白造的用例会养出一条永远不会红的断言。

RC = {n: SCH["sheets"][n].get("role_columns") or {} for n in ORDER}
CI = {n: {i: c for i, c in enumerate(COLS[n])} for n in ORDER}
_SEED = px.load_default_seed() or {}
PROTO = _SEED.get("proto") or {}
LIB = _SEED.get("lib") or {}
FIELDS = SCH["sheets"]["Profile"]["fields"]
ANCHOR_FLD = px._anchor_profile_fields(SCH)      # {cat: Profile 里的 1RM 字段名}
SHEETS = SCH["sheets"]

# 下面这些名字只是「契约里取哪一条」的指针，取值一律现取，不在测试里复制列名/字段名。
VER_FIELD = next(n for n, fs in FIELDS.items() if fs.get("enum_ref"))
WEEKS_FIELD = next(n for n, fs in FIELDS.items() if fs.get("on_missing") == "total_weeks")
ENUM_FIELD = next(n for n, fs in FIELDS.items() if fs.get("type") == "enum")
INT_FIELD = next(n for n, fs in FIELDS.items() if fs.get("type") == "int" and fs.get("required"))
NUM_FIELD = next(n for n, fs in FIELDS.items()
                 if fs.get("type") == "num" and fs.get("required") and fs["range"][0] > 0)
NUM_OPT_FIELD = next(n for n, fs in FIELDS.items() if fs.get("type") == "num" and not fs.get("required"))
BOOL_FIELD = next(n for n, fs in FIELDS.items() if fs.get("type") == "bool")
CATS = {c["cat"] for c in (LIB.get("categories") or [])}
ANCHOR_CAT = next(c for c in SCH["anchors"] if c in CATS)
MAIN_FLD = ANCHOR_FLD[ANCHOR_CAT]
MV0 = next(a["en"] for a in (LIB.get("acts") or []) if a.get("cat") == ANCHOR_CAT)
DOMAIN0 = next(c["domain"] for c in (LIB.get("categories") or []) if c["cat"] == ANCHOR_CAT)
MODE0 = next(m for m in PROTO if (PROTO[m] or {}).get("tier") == "T1")
MODE_DL = next(m for m in PROTO if m.endswith(".DL"))
TAG0 = SHEETS["Days"]["enums"]["focus_tag"][0]
DAY_IDS = SHEETS["Days"]["enums"]["day_id"]
FIRST = SCH["row_idx"]["first"]
_GEAR_VOCAB = px.load_gear_schema()
GEAR_KIND0 = _GEAR_VOCAB["kinds"][0]["id"]
# 器械配置样本：数值只放「JS/Python 序列化同形」的整数与真小数——
# Python 的 20.0 会写成 "20.0" 而 JS 是 "20"，gear_json 的逐字节对账扛不住整值浮点。
GEAR_SAMPLE = {"barKg": 20, "kind": GEAR_KIND0}
GEAR_SAMPLE_LOCAL = {"barKg": 12.5, "kind": GEAR_KIND0, "sides": 2}
LEGACY_ENTRIES = px._legacy_entries(SCH)
LEGACY_VER = LEGACY_ENTRIES[0]["plan_schema_vers"][0]
LEGACY_ORDER = LEGACY_ENTRIES[0]["sheet_order"]
GPP_SPEC = SCH["sheets"]["GPP"]
GPP_RC = GPP_SPEC["role_columns"]
GPP_MASK_COL = GPP_SPEC["done_mask"]["column"]
GPP_MASK_LEN = GPP_SPEC["done_mask"]["len"]


def srow(sheet, extra=None, **by_role):
    """一行：契约的全部列都补齐成空串，再按 role 名（或列下标）覆盖。测试里不写列名。"""
    r = {c: "" for c in COLS[sheet]}
    for k, v in by_role.items():
        assert k in RC[sheet], "%s 没有 role '%s'" % (sheet, k)
        r[RC[sheet][k]] = v
    for k, v in (extra or {}).items():
        assert k in COLS[sheet], "%s 没有列 %s" % (sheet, k)
        r[k] = v
    return r


def prow(field, value):
    c = COLS["Profile"]
    return {c[0]: field, c[1]: value, c[2]: ""}


def _ok_val(fs):
    """按契约类型给一个落在范围内的取值。"""
    t = fs.get("type")
    if t == "date":
        return "2026-11-02"
    if t == "enum":
        return fs["enum"][0]
    lo, hi = fs.get("range", [1, 100])
    return int((lo + hi) // 2) if t == "int" else float(lo + hi) / 2.0


def _mode(prefer=None):
    for m in ([prefer] if prefer else []) + list(PROTO):
        if m in PROTO:
            return m
    return ""


def _bound(sheet, col, which):
    """契约 ranges 的端点：which=0 下界、1 上界。"""
    return SHEETS[sheet]["ranges"][col][which]


def minimal_plan(weeks=2):
    """八表齐全、且**零判定**（0 error 且 0 warning）的最小计划：必填 Profile + 1 块 + 2 日 + 每周一动作 + 一行 GPP + 一行器械 + 一行水平快照。

    故意只到"够用"：45 个用例各坏一处，都要发给页面重算，计划越小对账越快。
    """
    prof = [prow(VER_FIELD, SCH["schema_ver"])]
    for name, fs in FIELDS.items():
        if name == VER_FIELD or not fs.get("required"):
            continue
        prof.append(prow(name, _ok_val(fs)))
    prof.append(prow(WEEKS_FIELD, weeks))
    anchor_kg = _ok_val(FIELDS[MAIN_FLD])
    pct = 0.75
    blocks = [srow("Blocks", block="B1", work_weeks=weeks, deload_weeks=0,
                   work_mode=_mode(MODE0), deload_mode=_mode(MODE_DL),
                   base_rpe=_bound("Blocks", "base_rpe", 0) + 1,
                   deload_rpe=_bound("Blocks", "deload_rpe", 0) + 1,
                   extra={COLS["Blocks"][1]: SHEETS["Blocks"]["enums"]["cycle_type"][0],
                          COLS["Blocks"][2]: "最小周期"})]
    days = [srow("Days", day=d, weekday=i, tags=TAG0,
                 extra={RC["Days"]["title_zh"]: "第%s日" % d}) for i, d in enumerate(DAY_IDS[:2])]
    workouts = [srow("Workouts", week=w, day=DAY_IDS[0], seq=1, row=FIRST[DAY_IDS[0]],
                     mode=_mode(MODE0), category=ANCHOR_CAT, movement=MV0, pct=pct,
                     load=px.mround(anchor_kg * pct, SCH["conflict_policy"]["round_step_kg"]),
                     sets=3, reps=5, target_rpe=8) for w in range(1, weeks + 1)]
    tel = []
    for w in range(1, weeks + 1):
        t = srow("Telemetry", week=w, day=DAY_IDS[0])
        for col, bounds in (SHEETS["Telemetry"].get("ranges") or {}).items():
            t[col] = (int((bounds[0] + bounds[1]) // 2)
                      if all(isinstance(b, int) for b in bounds) else float(sum(bounds)) / 2.0)
        for col, allowed in (SHEETS["Telemetry"].get("enums") or {}).items():
            if isinstance(allowed, list) and col in COLS["Telemetry"]:
                t[col] = allowed[0]
        tel.append(t)
    gpp = [srow("GPP", week=w, item=0, domain=DOMAIN0, item_name="髋屈肌",
                rx="活动度", intensity="轻", done_mask="1000000") for w in range(1, weeks + 1)]
    gear = [srow("Gear", week=1, day=DAY_IDS[0], row=FIRST[DAY_IDS[0]],
                 kind=GEAR_KIND0, source="plan",
                 gear_json=px._gear_canonical_json(GEAR_SAMPLE))]
    level = [srow("Level", date="2026-11-02")]
    return {"Profile": prof, "Blocks": blocks, "Days": days,
            "Workouts": workouts, "Telemetry": tel, "GPP": gpp, "Gear": gear, "Level": level}


def validate(plan, strict=False):
    r = px.validate_plan_dict(plan, proto=PROTO, lib=LIB, strict_constraints=strict, sch=SCH)
    return {"ok": r["ok"], "errors": r["errors"], "warnings": r["warnings"]}


# ---------------------------------------------------------------- 用例：每个只坏一处
#
# fn 直接改传入的深拷贝；第三列 True 表示按 strict 判（训练日安全约束违规升级为 error）。
# 有些坏法会连带撞出第二条判定（比如第 7 个训练日必然同时踩 day_id 重复），这不算问题 ——
# 对账比的是**整串判定逐条相同**，连带判定同样是两边要一致的内容。

def _set_prof(p, field, value):
    for row in p["Profile"]:
        if row[COLS["Profile"][0]] == field:
            row[COLS["Profile"][1]] = value
            return
    p["Profile"].append(prow(field, value))


def _wrow(p, i=0, **by_role):
    for k, v in by_role.items():
        assert k in RC["Workouts"], "Workouts 没有 role '%s'" % k
        p["Workouts"][i][RC["Workouts"][k]] = v


def _dup_last(p, sheet, **by_role):
    """复制该表最后一行（可覆盖几个 role 列）再追加回去。"""
    over = {RC[sheet][k]: v for k, v in by_role.items()}
    p[sheet].append(dict(p[sheet][-1], **over))


def _blocks_over_total(p):
    """把 Blocks 的周数之和推到契约上限之外：每块都取 work_weeks 的上界。"""
    hi = _bound("Blocks", "work_weeks", 1)
    for i in range(3):
        _dup_last(p, "Blocks", block="B%d" % (i + 2), work_weeks=hi)


CASES = [
    ("契约版本不认识", lambda p: _set_prof(p, VER_FIELD, SCH["schema_ver"] + "?"), False),
    ("日期形如不符", lambda p: _set_prof(p, profile_field("date"), "2026-11-2"), False),
    ("枚举取值非法", lambda p: _set_prof(p, ENUM_FIELD, "X"), False),
    ("数值越界", lambda p: _set_prof(p, NUM_FIELD, 9), False),
    ("数字列写了文本", lambda p: _set_prof(p, NUM_OPT_FIELD, "abc"), False),
    ("整数列写了小数", lambda p: _set_prof(p, INT_FIELD, 24.5), False),
    ("布尔列写了文本", lambda p: _set_prof(p, BOOL_FIELD, "maybe"), False),
    ("必填缺失", lambda p: _set_prof(p, MAIN_FLD, ""), False),
    ("未知 Profile 字段", lambda p: p["Profile"].append(prow("totally_unknown", 1)), False),
    ("Profile 整表是表头行", lambda p: p.__setitem__(
        "Profile", [{c: c for c in COLS["Profile"]}]), False),
    ("block_id 形如", lambda p: p["Blocks"][0].__setitem__(RC["Blocks"]["block"], "X1"), False),
    ("block_id 重复", lambda p: _dup_last(p, "Blocks"), False),
    ("块缺必填", lambda p: p["Blocks"][0].__setitem__(COLS["Blocks"][1], ""), False),
    ("块 RPE 越界", lambda p: p["Blocks"][0].__setitem__(RC["Blocks"]["base_rpe"],
                                                      _bound("Blocks", "base_rpe", 1) + 1), False),
    ("周数非整数", lambda p: p["Blocks"][0].__setitem__(RC["Blocks"]["work_weeks"], "2.5"), False),
    ("合计周数越界", _blocks_over_total, False),
    ("plan_weeks 与 Blocks 之和不符", lambda p: _set_prof(p, WEEKS_FIELD, _bound("Blocks", "work_weeks", 1)), False),
    ("块模式不在 proto", lambda p: p["Blocks"][0].__setitem__(RC["Blocks"]["work_mode"], "Nope"), False),
    ("day_id 非法", lambda p: p["Days"][0].__setitem__(RC["Days"]["day"], "Z"), False),
    ("day_id 重复", lambda p: _dup_last(p, "Days"), False),
    ("工作日缺标题", lambda p: p["Days"][0].__setitem__(RC["Days"]["title_zh"], ""), False),
    ("未知标签", lambda p: p["Days"][0].__setitem__(RC["Days"]["tags"], "tag_nope"), False),
    ("weekday 越界", lambda p: p["Days"][0].__setitem__(RC["Days"]["weekday"],
                                                    _bound("Days", "weekday_offset", 1) + 1), False),
    ("训练日超上限", lambda p: p["Days"].extend(
        [srow("Days", day=d, weekday=2, extra={RC["Days"]["title_zh"]: "第%s日" % d})
         for d in DAY_IDS[2:]] +
        [srow("Days", day=DAY_IDS[0], weekday=3, extra={RC["Days"]["title_zh"]: "多出的一个"})]), False),
    ("日约束布尔非法", lambda p: p["Days"][0].__setitem__(SHEETS["Days"]["bools"][0], "maybe"), False),
    ("必填列空", lambda p: _wrow(p, 0, movement=""), False),
    ("week 超出合计", lambda p: _wrow(p, 0, week=99), False),
    ("week 非整数", lambda p: _wrow(p, 0, week="x"), False),
    ("day 未定义", lambda p: _wrow(p, 0, day="Z"), False),
    ("seq 非 1-based", lambda p: _wrow(p, 0, seq=0), False),
    ("mode 不在 proto", lambda p: _wrow(p, 0, mode="Nope"), False),
    ("tier 与 proto 不符", lambda p: _wrow(p, 0, tier="T9"), False),
    ("category 不在 lib", lambda p: _wrow(p, 0, category="Nope"), False),
    ("movement 拼写不在库", lambda p: _wrow(p, 0, movement=MV0 + "（不存在）"), False),
    ("主项缺 pct 与 load", lambda p: _wrow(p, 0, pct="", load=""), False),
    ("load 与 pct 冲突", lambda p: _wrow(p, 0, load=_bound("Workouts", "load_kg", 1)), False),
    ("load 越界", lambda p: _wrow(p, 0, load=_bound("Workouts", "load_kg", 1) + 300), False),
    ("target_rpe 越界", lambda p: _wrow(p, 0, target_rpe=_bound("Workouts", "target_rpe", 1) + 2), False),
    ("row_idx 非整数", lambda p: _wrow(p, 0, row="abc"), False),
    ("row_idx 与公式不符", lambda p: _wrow(p, 0, row=99), False),
    ("actual_reps 不参与导入", lambda p: _wrow(p, 0, actual_reps=5), False),
    ("(week,day,row_idx) 重复", lambda p: p["Workouts"].append(dict(p["Workouts"][0])), False),
    ("同周同日 seq 重复", lambda p: _dup_last(p, "Workouts", row=FIRST[DAY_IDS[1]]), False),
    ("安全约束违规", lambda p: p["Days"][0].__setitem__(SHEETS["Days"]["bools"][0], True), False),
    ("安全约束违规（strict）", lambda p: p["Days"][0].__setitem__(SHEETS["Days"]["bools"][0], True), True),
    ("遥测 week 越界", lambda p: p["Telemetry"][0].__setitem__(RC["Telemetry"]["week"], 99), False),
    ("遥测数值越界", lambda p: p["Telemetry"][0].__setitem__(
        numeric_col("Telemetry"), _bound("Telemetry", numeric_col("Telemetry"), 1) + 500), False),
    ("遥测重复", lambda p: _dup_last(p, "Telemetry"), False),
    ("GPP item_idx 非 0-based", lambda p: p["GPP"][0].__setitem__(GPP_RC["item"], -1), False),
    ("GPP 定义不一致", lambda p: _dup_last(p, "GPP", item_name="另一项"), False),
    ("GPP 重复", lambda p: _dup_last(p, "GPP"), False),
    ("GPP done_mask 非法", lambda p: p["GPP"][0].__setitem__(GPP_MASK_COL, "2000000"), False),
    ("可选表缺失", lambda p: (p.pop("Telemetry"), p.pop("GPP")), False),
    ("核心表缺失", lambda p: p.pop("Days"), False),
    ("Profile 缺失", lambda p: p.pop("Profile"), False),
    ("动作表缺失", lambda p: p.pop("Workouts"), False),
    ("块表为空", lambda p: p.__setitem__("Blocks", []), False),
    ("动作表为空", lambda p: p.__setitem__("Workouts", []), False),
    ("Gear 缺失（可选表告警）", lambda p: p.pop("Gear"), False),
    ("Gear kind 不在词表", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["kind"], "nope_kind"), False),
    ("Gear source 不在词表", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["source"], "magic"), False),
    ("Gear gear_json 非法", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "{barKg:"), False),
    ("Gear gear_json 是数组", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "[1,2]"), False),
    ("Gear gear_json 是浮点", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "12.5"), False),
    ("Gear gear_json 是整数", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "5"), False),
    ("Gear gear_json 是文本", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], '"abc"'), False),
    ("Gear gear_json 是布尔", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "true"), False),
    ("Gear gear_json 是 null", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["gear_json"], "null"), False),
    ("Gear 锚不命中", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["row"], FIRST[DAY_IDS[0]] + 50), False),
    ("Gear 锚 row_idx 空", lambda p: p["Gear"][0].__setitem__(RC["Gear"]["row"], ""), False),
    ("Gear (week,day,row_idx) 重复", lambda p: _dup_last(p, "Gear"), False),
    ("Level date 形如不符", lambda p: p["Level"][0].__setitem__(RC["Level"]["date"], "2026-1-2"), False),
    ("Level rank_stars 非整数", lambda p: p["Level"][0].__setitem__(RC["Level"]["stars"], "3.5"), False),
    ("Level total_kg 越界", lambda p: p["Level"][0].__setitem__(RC["Level"]["total"], 5000), False),
    ("Level date 重复（后行覆盖，warning）", lambda p: _dup_last(p, "Level"), False),
    ("legacy 六表：Gear 既不要求也不解析",
     lambda p: (p.pop("Gear"), p.pop("GPP"), p.pop("Level"), _set_prof(p, VER_FIELD, LEGACY_VER)), False),
]
CASES = [(c[0], c[1], c[2] if len(c) > 2 else False) for c in CASES]


def v_cases():
    """最小计划 + 逐用例的 Python 侧判定；JS 侧要在页面上逐条复现。"""
    base = minimal_plan()
    b = validate(base)
    if b["errors"] or b["warnings"]:
        raise AssertionError("最小合法计划本身不过契约：%s / %s" % (b["errors"], b["warnings"]))
    out = [{"label": "基线：最小合法计划", "strict": False, "plan": base, **b}]
    for label, fn, strict in CASES:
        p = copy.deepcopy(base)
        fn(p)
        r = validate(p, strict)
        if not r["errors"] and not r["warnings"]:
            raise AssertionError("用例「%s」没有任何判定，是个白造的用例" % label)
        out.append({"label": label, "strict": strict, "plan": p, **r})
    return out


# ---------------------------------------------------------------- 导入链的合法载荷（C4b W1）
#
# importPlanFromXlsxBytes 的契约闸门会拒掉任何带 error 的计划，所以进 W1 循环的
# 必须全是 **Python 侧按该例 strict 档判过且 0 error** 的载荷；不合格的用例改在
# W1s（strict 档整份拒收）和 W2（非 strict 拒收）里专门撞闸门。
# 挑中的用例名在这里写死：将来 CASES 改名，这里当场 KeyError，而不是静默少一批用例。

IMPORT_LABELS = ["基线：最小合法计划", "可选表缺失", "安全约束违规"]


def gear_canonical_plan():
    """带器械的 canonical：往种子账本的两条动作注入 gear，再走 state_to_plan_dict 出七表。

    一条 source 留缺省（plan）、一条 local——都进 W1 链：JS 写的 xlsx 两侧各自装载后，
    换算回计划字典逐格对账，gear_json 的逐字节一致性（xGearCanonical=_gear_canonical_json）
    与锚合并（ex.gear / gearSource）就在这一腿里被盯住。样本值只放整数与真小数（见 GEAR_SAMPLE 注）。"""
    st = copy.deepcopy(_SEED)
    wk = st["weeks"]["1"]
    exs = wk["A"]["exercises"]
    exs[0]["gear"] = dict(GEAR_SAMPLE)
    exs[1]["gear"] = dict(GEAR_SAMPLE_LOCAL)
    exs[1]["gearSource"] = "local"
    return px.state_to_plan_dict(st, SCH)


def import_cases(canon_plan):
    cs = {c["label"]: c for c in v_cases()}
    out = []
    for lb in IMPORT_LABELS:
        c = cs[lb]
        r = validate(c["plan"], c["strict"])
        if r["errors"]:
            raise AssertionError("导入链用例「%s」在 %s 档带 error=%r，不能进 W1"
                                 % (lb, "strict" if c["strict"] else "非 strict", r["errors"]))
        out.append({"label": lb, "plan": plan_jsonable(c["plan"]),
                    "strict": c["strict"], "warnings": r["warnings"]})
    out.append({"label": "canonical 全量计划", "plan": canon_plan,
                "strict": False, "warnings": validate(canon_plan)["warnings"]})
    gplan = plan_jsonable(gear_canonical_plan())
    gv = validate(gplan)
    if gv["errors"]:
        raise AssertionError("带器械 canonical 在 Python 侧带 error=%r，不能进 W1" % gv["errors"])
    out.append({"label": "canonical 带器械", "plan": gplan, "strict": False, "warnings": gv["warnings"]})
    return out


# ---------------------------------------------------------------- 写侧要还回去的两份计划

def w_plans():
    canonical = px.state_to_plan_dict(px.load_default_seed(), SCH)
    cp = COLS["Profile"]
    bl = {r: sheet_col("Blocks", r) for r in ("block", "work_weeks", "base_rpe")}
    bl["cycle"] = SCH["sheets"]["Blocks"]["columns"][1]
    bl["zh"] = SCH["sheets"]["Blocks"]["columns"][2]
    wk = {r: sheet_col("Workouts", r) for r in ("week", "pct", "load", "rx", "sets", "notes")}
    edge = {n: [] for n in ORDER}
    edge["Profile"] = [
        {cp[0]: profile_field("str"), cp[1]: SCH["schema_ver"], cp[2]: "", "__row__": 2},
        {cp[0]: profile_field("date"), cp[1]: "2026-11-02", cp[2]: "带 & 与 \"引号\"", "__row__": 3},
        {cp[0]: profile_field("num"), cp[1]: 87.5, cp[2]: "", "__row__": 4},
        {cp[0]: profile_field("int"), cp[1]: 24, cp[2]: "", "__row__": 5},
        {cp[0]: profile_field("bool"), cp[1]: True, cp[2]: "", "__row__": 6},
    ]
    edge["Blocks"] = [{bl["block"]: "B1", bl["cycle"]: SCH["sheets"]["Blocks"]["enums"]["cycle_type"][1],
                       bl["zh"]: "带 <尖括号> 与 🙂 表情", bl["work_weeks"]: 4, bl["base_rpe"]: 8.25,
                       SCH["sheets"]["Blocks"]["columns"][-1]: "", "__row__": 2}]
    edge["Workouts"] = [
        {wk["week"]: 1, wk["pct"]: 0.0625, wk["load"]: -2.5, wk["rx"]: "  前后空格  ",
         wk["notes"]: "多行\n备注", "__row__": 2},
        {wk["week"]: 2, wk["pct"]: "75%", wk["sets"]: 0, "__row__": 3},
    ]
    if bool_col("Workouts"):
        edge["Workouts"][0][bool_col("Workouts")] = True
    return canonical, edge


def numfmt_expect(path):
    """v0.10 逻辑对账的 Python 侧参照：一批「格子值可能长什么样」→ 六个函数的归一化串。

    只还字符串，不还数值 —— 归一化全部走 `px._cell_key`，因为 App 里那份 `xCellKey`
    的定义就是「逐字复现这里」。浮点在两门语言里的字面量写法本来就不同（`24.0` vs `24`、
    1e21 的指数形式），先把两侧都压成同一个串才可比，否则测的是打印格式而不是语义。

    定义域 = 契约的列类型（str / num / int / bool / date / enum），数组与对象进不来，
    所以这里不收。非有限值（inf / nan）**只走能算的那几个函数**：Python 的
    `math.floor(inf)` 直接抛，而 App 拿到的是字符串 —— 两侧对同一份输入的可达结果不同，
    比的是「能算出来的那些是否一致」。
    """
    with io.open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    values, steps = payload["values"], payload.get("steps") or [2.5]
    out = {"cellkey": [], "num": [], "int": [], "bool": [], "datestr": [], "f1": [], "mround": {}}
    for v in values:
        out["cellkey"].append(px._cell_key(v))
        out["num"].append(px._cell_key(px._num(v)))
        out["int"].append(px._cell_key(px._int(v)))
        out["bool"].append(px._cell_key(px._as_bool(v)))
        out["datestr"].append(px._cell_key(px._date_str(v)))
        n = px._num(v)
        # f1 的定义式是 floor(x*10+0.5)/10：x 大到 x*10 溢出成 inf 时 Python 的 math.floor 直接抛，
        # JS 给回 Infinity。这种量级在契约里既不是重量也不是百分比（f1 只用于 GL / 百分比的展示），
        # 所以两侧都在 1e307 之外留空 —— 比的是「两边都能算出来的那些」。
        ok = isinstance(n, float) and math.isfinite(n) and abs(n) <= 1e307
        out["f1"].append(px._cell_key(px.f1(n)) if ok else "")
    for s in steps:
        key = px._cell_key(s)
        # mround 现在对非有限值归 0（见 plan_xlsx.mround），整批都能算，不需要挑定义域
        out["mround"][key] = [px._cell_key(px.mround(v, s)) for v in values]
    return out


def main(argv=None):
    pyout.use_utf8_stdout()
    args = argv or sys.argv[1:]
    if args and args[0] == "dump":
        # ensure_ascii=True：中文格写成 \uXXXX 出去，字节全是 ASCII。
        # 否则 stdout 跟着控制台代码页走（中文 Windows 是 cp936），node 按 UTF-8 解码就成了
        # 乱码比对，遇到 emoji 直接 UnicodeEncodeError —— 回归结果取决于机器语言，不可接受。
        print(json.dumps(dump(args[1]), ensure_ascii=True))
        return 0
    if args and args[0] == "stateplan":
        print(json.dumps(state_plan_cells(args[1]), ensure_ascii=True))
        return 0
    if args and args[0] == "importstate":
        print(json.dumps(import_state_cells(args[1]), ensure_ascii=True))
        return 0
    if args and args[0] == "numfmt":
        print(json.dumps(numfmt_expect(args[1]), ensure_ascii=True))
        return 0
    if args and args[0] == "cases":
        # 本地体检：只打每条用例的判定条数，红了先看这里，不用跑整条 Chrome 链。
        for c in v_cases():
            print("%-34s %s error=%d warning=%d" % (c["label"], "OK " if c["ok"] else "ERR",
                                                    len(c["errors"]), len(c["warnings"])))
        return 0
    if args and args[0] == "fixtures":
        tmp = args[1]
        if not os.path.isdir(tmp):
            os.makedirs(tmp)
        expects, fixtures = {}, []
        for fn in (f_app, f_hand, f_odd):
            path, exp = fn(tmp)
            fixtures.append(os.path.basename(path))
            expects[fixtures[-1]] = exp
        canonical, edge = w_plans()
        # 同一份计划再用 openpyxl 写一遍：App 写出的工作簿必须得到**一模一样**的契约校验结果，
        # 包括 edge 这种故意不合法的计划 —— 比「error 数为 0」更严，也不会误伤边角样本。
        py_written = {}
        for label, plan in (("canonical", canonical), ("edge", edge)):
            py_written[label] = "px_" + label + ".xlsx"
            px.plan_to_book(plan, os.path.join(tmp, py_written[label]), SCH)
        with io.open(os.path.join(tmp, "expect.json"), "w", encoding="utf-8", newline="") as fh:
            json.dump({"fixtures": fixtures, "expect": expects, "pyWritten": py_written,
                       "canonicalPlan": plan_jsonable(canonical),
                       "canonicalVal": validate(canonical),
                       "canonicalCells": cells_of(canonical)["cells"],
                       "edgePlan": edge,
                       "edgeVal": validate(edge),
                       "edgeCells": cells_of(edge)["cells"],
                       "importCases": import_cases(plan_jsonable(canonical)),
                       "statePlan": state_plan_cells(px.SEED_PATH),
                       "vCases": v_cases()}, fh, ensure_ascii=False)
        print("fixtures: " + ", ".join(fixtures))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
