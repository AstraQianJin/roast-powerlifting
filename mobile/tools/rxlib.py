#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rxlib.py — R.ExDark「动作库」的读取 / 全量重建 / 命名区域同步。

归属与依赖方向
--------------
本文件归**主项目**（mobile/tools/）所有，是「动作库三级结构」的唯一实现。
- gen_seed.py 同目录直接 import（种子生成不再跨项目）
自 v0.13 起 PC 端项目整体归档，本文件只有主项目内的读者；改完跑 `gate.py` 全量即可。

设计约束
--------
1. 动作库没有条件格式与数据验证，但它有 10 列各自的样式、行高、合并标题。
   重建时保留 <sheetData> 之外的一切字节，只重排 <sheetData>。
2. 斑马纹不是按全局序号，而是「每组起始套 + 组内交替」。
   起始套从原表学习，不猜。
3. 视觉家族由分类前缀决定（S./B./D./其余），对应 4 套 GROUP 行配色。
4. 33 个 lib_* 命名区域是静态区间 `动作库!$C$a:$C$b`，
   任何行数变化都必须重算，否则 W1–W16 的级联下拉全部错位。
"""
from __future__ import annotations

import os
import re
import zipfile
from collections import Counter
from datetime import datetime

import openpyxl

LIB = "动作库"
HEAD_ROWS = (1, 2, 3)
NCOL = 10
COLS = "ABCDEFGHIJ"
AUTO_F = ('IF(COUNTIF(INDIRECT("W"&CUR_WEEK&"!$D$9:$D$51"),'
          '$C{row})>0,"ACTIVE","No")')


# --------------------------------------------------------------------------- #
# 基础工具
# --------------------------------------------------------------------------- #
def col_index(col: str) -> int:
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch) - 64)
    return n


def xesc(t: str) -> str:
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def family_of(cat: str) -> str:
    """视觉家族：决定 GROUP 行与动作行的配色模板。"""
    if cat.startswith("S."):
        return "S"
    if cat.startswith("B."):
        return "B"
    if cat.startswith("D."):
        return "D"
    return "X"          # SBD.* / Hyper.* / Unmapped


def sheet_part(z: zipfile.ZipFile, name: str):
    """workbook.xml r:id -> rels Target，返回 zip 内路径。"""
    wbx = z.read("xl/workbook.xml").decode("utf-8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    rid = None
    for tag in re.findall(r"<sheet\b[^>]*/>", wbx):
        if 'name="%s"' % name in tag:
            m = re.search(r'r:id="([^"]+)"', tag)
            if m:
                rid = m.group(1)
            break
    if not rid:
        return None
    for tag in re.findall(r"<Relationship\b[^>]*/>", rels):
        if 'Id="%s"' % rid in tag:
            tgt = re.search(r'Target="([^"]+)"', tag).group(1)
            return tgt.lstrip("/") if tgt.startswith("/") else "xl/" + tgt
    return None


# --------------------------------------------------------------------------- #
# 读取逻辑模型
# --------------------------------------------------------------------------- #
def read_groups(path) -> list[dict]:
    """从工作簿读取动作库的完整逻辑模型（分组 + 动作 + 元信息）。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    try:
        ws = wb[LIB]
        groups, cur = [], None
        for r in range(4, ws.max_row + 1):
            en = ws.cell(r, 3).value
            if en is None:
                continue
            en = str(en).strip()
            if not en:
                continue
            cat = str(ws.cell(r, 2).value or "").strip()
            if en.startswith("—"):
                cur = {
                    "cat": cat,
                    "family": family_of(cat),
                    "tier": str(ws.cell(r, 1).value or "").strip(),
                    "cn": str(ws.cell(r, 4).value or "").strip(),
                    "cues": str(ws.cell(r, 7).value or "").strip(),
                    "label": str(ws.cell(r, 9).value or "").strip(),
                    "src_row": r,
                    "acts": [],
                }
                groups.append(cur)
            elif cur is not None:
                if cat and cat != cur["cat"]:
                    # 没有 GROUP 标题的孤儿分类（Unmapped）
                    cur = {"cat": cat, "family": family_of(cat), "tier": "", "cn": "",
                           "cues": "", "label": "", "src_row": None, "acts": [],
                           "orphan": True}
                    groups.append(cur)
                cur["acts"].append({
                    "tier": str(ws.cell(r, 1).value or "").strip(),
                    "cat": cat or cur["cat"],
                    "en": en,
                    "cn": str(ws.cell(r, 4).value or "").strip(),
                    "equip": str(ws.cell(r, 5).value or "").strip(),
                    "reps": str(ws.cell(r, 6).value or "").strip(),
                    "cues": str(ws.cell(r, 7).value or "").strip(),
                    "role": str(ws.cell(r, 8).value or "").strip(),
                    "muscle": str(ws.cell(r, 10).value or "").strip(),
                    "src_row": r,
                })
        return groups
    finally:
        wb.close()


# --------------------------------------------------------------------------- #
# 学习样式模板
# --------------------------------------------------------------------------- #
def _row_styles(xml: str) -> dict[int, dict[str, str]]:
    out = {}
    for m in re.finditer(r'<row\b[^>]*\br="(\d+)"[^>]*>(.*?)</row>', xml, re.S):
        r, body, cell = int(m.group(1)), m.group(2), {}
        for cm in re.finditer(r"<c\b([^>]*?)(?:/>|>)", body):
            a = cm.group(1)
            ref = re.search(r'r="([A-Z]+)\d+"', a)
            s = re.search(r'\bs="(\d+)"', a)
            if ref:
                cell[ref.group(1)] = s.group(1) if s else None
        out[r] = cell
    return out


def learn_templates(path, groups: list[dict]) -> dict:
    """
    返回 {
      ("group", family)      -> [s]*10,
      ("act", family, 0|1)   -> [s]*10   两个斑马套
      "__start__": {cat: 0|1}
    }
    斑马套用 C 列的 s 值作判别键（填充色一定体现在这里），
    不靠 i%2 猜——各组的起始套本来就不同。
    """
    z = zipfile.ZipFile(path)
    part = sheet_part(z, LIB)
    xml = z.read(part).decode("utf-8")
    styles = _row_styles(xml)
    z.close()

    g_cnt = {}
    by_fam_c = {}          # family -> { C列s : Counter(sig) }
    sig_of = {}            # (family, src_row) -> sig

    for g in groups:
        sig = tuple(styles.get(g["src_row"], {}).get(c) for c in COLS)
        if not g.get("orphan"):
            g_cnt.setdefault(g["family"], Counter())[sig] += 1
        for a in g["acts"]:
            s2 = tuple(styles.get(a["src_row"], {}).get(c) for c in COLS)
            sig_of[a["src_row"]] = s2
            by_fam_c.setdefault(g["family"], {}).setdefault(s2[2], Counter())[s2] += 1

    tpl = {}
    order = {}             # family -> [C列s 的 top1, top2]
    for fam, m in by_fam_c.items():
        tops = sorted(m.items(), key=lambda kv: -sum(kv[1].values()))
        order[fam] = [t[0] for t in tops] + [tops[0][0]] * 2
        for zi in (0, 1):
            rows = []
            for sig, cnt in m[order[fam][zi]].items():
                rows += [sig] * cnt
            # 逐列取众数：原表 E/G/J 列有手工粘贴留下的底色漂移，整行取模会被带偏
            tpl[("act", fam, zi)] = [
                Counter(s[k] for s in rows).most_common(1)[0][0] for k in range(NCOL)
            ]
    for fam, ctr in g_cnt.items():
        tpl[("group", fam)] = list(ctr.most_common(1)[0][0])

    start = {}
    for g in groups:
        for a in g["acts"]:
            a["_sig"] = list(sig_of.get(a["src_row"], [None] * NCOL))
        if not g["acts"]:
            start[g["cat"]] = 0
            continue
        c_s = sig_of.get(g["acts"][0]["src_row"], (None,) * 10)[2]
        start[g["cat"]] = 0 if c_s == order[g["family"]][0] else 1
    tpl["__start__"] = start
    return tpl



# --------------------------------------------------------------------------- #
# 渲染 <sheetData>
# --------------------------------------------------------------------------- #
def _cell(ref: str, s, value=None, formula=None, cache="No") -> str:
    sa = f' s="{s}"' if s else ""
    if formula is not None:
        return f'<c r="{ref}"{sa} t="str"><f ca="1">{xesc(formula)}</f><v>{xesc(cache)}</v></c>'
    if value is None or value == "":
        return f'<c r="{ref}"{sa}/>'
    return (f'<c r="{ref}"{sa} t="inlineStr"><is><t xml:space="preserve">'
            f'{xesc(str(value))}</t></is></c>')


def render_sheet(xml: str, groups: list[dict], tpl: dict) -> tuple[str, dict]:
    """重建 sheetData，返回 (新 xml, {分类: (首行, 末行)})。"""
    start = tpl.get("__start__", {})
    # 标题行（1-3）原样保留，它们有合并单元格与独立样式
    head = re.findall(r'<row\b[^>]*\br="[123]"[^>]*>.*?</row>', xml, re.S)
    out = list(head)
    row = HEAD_ROWS[-1] + 1          # 从第 4 行开始
    ranges = {}

    for g in groups:
        fam = g["family"]
        # GROUP 行（孤儿分类没有标题行）
        if not g.get("orphan"):
            gs = tpl.get(("group", fam))
            vals = [g["tier"] or fam, g["cat"], f'— {len(g["acts"])} 个动作 —',
                    g["cn"], "Group", "All", g["cues"], "GROUP", g.get("label") or "No", "group"]
            cells = [_cell(f"{c}{row}", gs[i] if gs else None, vals[i])
                     for i, c in enumerate(COLS)]
            out.append(f'<row r="{row}" ht="48" customHeight="1" spans="1:10">'
                       + "".join(cells) + "</row>")
            row += 1

        z0 = start.get(g["cat"], 0)
        first = row
        for i, a in enumerate(g["acts"]):
            # 有原样式的行原封不动；新增行才套模板（避免把原表的手工底色“矫正”掉）
            s = a.get("_sig") or tpl[("act", fam, (z0 + i) % 2)]
            if len(s) < NCOL:
                s = (list(s) + [None] * NCOL)[:NCOL]
            cells = [
                _cell(f"A{row}", s[0], a["tier"]),
                _cell(f"B{row}", s[1], a["cat"]),
                _cell(f"C{row}", s[2], a["en"]),
                _cell(f"D{row}", s[3], a["cn"]),
                _cell(f"E{row}", s[4], a["equip"]),
                _cell(f"F{row}", s[5], a["reps"]),
                _cell(f"G{row}", s[6], a["cues"]),
                _cell(f"H{row}", s[7], a["role"]),
                _cell(f"I{row}", s[8], None, formula=AUTO_F.replace("{row}", str(row)), cache="No"),
                _cell(f"J{row}", s[9], a["muscle"]),
            ]
            out.append(f'<row r="{row}" ht="48" customHeight="1" spans="1:10">'
                       + "".join(cells) + "</row>")
            row += 1
        ranges[g["cat"]] = (first, row - 1)

    i = xml.find("<sheetData>")
    j = xml.find("</sheetData>")
    if i < 0 or j < 0:
        raise ValueError("动作库缺少 sheetData")
    body = "<sheetData>" + "".join(out) + "</sheetData>"
    new = xml[:i] + body + xml[j + len("</sheetData>"):]
    new = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:J{row - 1}"/>', new, count=1)
    return new, ranges


# --------------------------------------------------------------------------- #
# 命名区域
# --------------------------------------------------------------------------- #
def lib_name(cat: str) -> str:
    return "lib_" + re.sub(r"[^0-9A-Za-z]+", "_", cat).strip("_")


def rebuild_defined_names(wbxml: str, ranges: dict) -> tuple[str, list[str]]:
    """把所有 lib_* 的区间改到新行号，返回 (新 xml, 变更说明)。"""
    changes = []
    for cat, (a, b) in ranges.items():
        nm = lib_name(cat)
        pat = re.compile(r'(<definedName name="%s"[^>]*>)[^<]*(</definedName>)' % re.escape(nm))
        m = pat.search(wbxml)
        if not m:
            changes.append(f"缺失 {nm}")
            continue
        old = m.group(0)
        new = f'{m.group(1)}动作库!$C${a}:$C${b}{m.group(2)}'
        if old != new:
            changes.append(f"{nm}: {re.search(r'>([^<]*)<', old).group(1)} -> 动作库!$C${a}:$C${b}")
            wbxml = wbxml.replace(old, new, 1)
    return wbxml, changes


def set_full_calc(wbxml: str) -> str:
    if "fullCalcOnLoad" in wbxml:
        return re.sub(r'fullCalcOnLoad="[^"]*"', 'fullCalcOnLoad="1"', wbxml, count=1)
    if "<calcPr" in wbxml:
        return re.sub(r"<calcPr\b([^>]*?)/>", r'<calcPr\1 fullCalcOnLoad="1"/>', wbxml, count=1)
    return wbxml.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')


def patch_dependents(xml: str, last_row: int) -> str:
    """「映射」表 F 列的 SUMPRODUCT 写死了 动作库!$B$4:$B$290，必须跟着改。"""
    xml = re.sub(r"(动作库!\$B\$4:\$B\$)\d+", lambda m: m.group(1) + str(last_row), xml)
    return re.sub(r"(动作库!\$C\$4:\$C\$)\d+", lambda m: m.group(1) + str(last_row), xml)


def patch_lib_none(wbxml: str, row: int) -> str:
    """lib_none 是「无动作」哨兵，指向 Unmapped 行。"""
    pat = re.compile(r'(<definedName name="lib_none"[^>]*>)[^<]*(</definedName>)')
    return pat.sub(lambda m: f"{m.group(1)}动作库!$C${row}{m.group(2)}", wbxml, count=1)


# --------------------------------------------------------------------------- #
# 写回
# --------------------------------------------------------------------------- #
def write_library(src, dst, groups: list[dict], tpl: dict | None = None) -> dict:
    if tpl is None:
        tpl = learn_templates(src, read_groups(src))
    z = zipfile.ZipFile(src)
    part = sheet_part(z, LIB)
    map_part = sheet_part(z, "映射")
    xml = z.read(part).decode("utf-8")
    new_xml, ranges = render_sheet(xml, groups, tpl)
    last_row = max(b for _, b in ranges.values())
    map_xml = patch_dependents(z.read(map_part).decode("utf-8"), last_row)

    wbx = z.read("xl/workbook.xml").decode("utf-8")
    new_wbx, changes = rebuild_defined_names(set_full_calc(wbx), ranges)
    unmapped = ranges.get("Unmapped")
    if unmapped:
        new_wbx = patch_lib_none(new_wbx, unmapped[1])

    tmp = str(dst) + ".part"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zo:
        for it in z.infolist():
            if it.filename == part:
                data = new_xml.encode("utf-8")
            elif it.filename == map_part:
                data = map_xml.encode("utf-8")
            elif it.filename == "xl/workbook.xml":
                data = new_wbx.encode("utf-8")
            else:
                data = z.read(it.filename)
            zo.writestr(it, data)
    z.close()
    os.replace(tmp, dst)          # 原子替换：src == dst 也安全
    return {"ranges": ranges, "nameChanges": changes, "lastRow": last_row,
            "actions": sum(len(g["acts"]) for g in groups), "groups": len(groups)}


# --------------------------------------------------------------------------- #
# 动作库 → 三级选择（功能域 / 子分类 / 动作）的对外载荷
# server.py 与 mobile/tools/gen_seed.py 共用，保证 PC 与 APK 的动作库完全同源
# --------------------------------------------------------------------------- #
DOMAINS = [
    ("T1.Main",   "主项池",       "Main Lifts",
     lambda c: c.endswith(".Main")),
    ("Variation", "主项变式",     "Competition Variations",
     lambda c: ".Vari." in c),
    ("SBD",       "SBD 专项辅助", "SBD Specifics",
     lambda c: c.startswith("SBD.") and c not in ("SBD.Power", "SBD.Sled")),
    ("Power",     "爆发与体能",   "Power & Conditioning",
     lambda c: c in ("SBD.Power", "SBD.Sled")),
    ("Hyper",     "增肌孤立",     "Hypertrophy Isolation",
     lambda c: c.startswith("Hyper.")),
    ("Accessory", "部位辅助",     "Body-Part Accessory", lambda c: True),
]
DOMAIN_ORDER = {d[0]: i for i, d in enumerate(DOMAINS)}


def domain_of(cat: str) -> str:
    for did, _zh, _en, test in DOMAINS:
        if test(cat):
            return did
    return "Accessory"


def cat_weight(cat: str) -> int:
    """同域内按 深蹲 → 卧推 → 硬拉 → SBD → 增肌 排序，而不是按字母。"""
    head = cat.split(".")[0]
    return {"S": 0, "B": 1, "D": 2, "SBD": 3, "Hyper": 4}.get(head, 5)


def read_focus(path) -> dict:
    """「映射」表 D/E 列：分类的英文 / 中文聚焦名。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    out = {}
    try:
        if "映射" not in wb.sheetnames:
            return out
        wm = wb["映射"]
        for r in range(4, wm.max_row + 1):
            cat = wm.cell(r, 1).value
            if cat:
                out[str(cat).strip()] = {
                    "en": str(wm.cell(r, 4).value or "").strip(),
                    "zh": str(wm.cell(r, 5).value or "").strip(),
                }
    finally:
        wb.close()
    return out


def library_payload(path) -> dict:
    """返回 {categories, acts, domains, meta}，供 PC / APK 前端渲染三级选择器。"""
    groups = read_groups(path)
    focus = read_focus(path)

    cats, acts = [], []
    for g in groups:
        f = focus.get(g["cat"], {})
        dom = domain_of(g["cat"])
        cats.append({
            "cat": g["cat"], "domain": dom,
            "zh": g["cn"] or g["cat"],
            "en": f.get("en") or g["cat"],
            "focusZh": f.get("zh", ""),
            "count": len(g["acts"]),
            "tiers": sorted({a["tier"] for a in g["acts"] if a["tier"]}),
        })
        for a in g["acts"]:
            acts.append({
                "cat": g["cat"], "domain": dom, "tier": a["tier"],
                "en": a["en"], "cn": a["cn"], "equip": a["equip"],
                "reps": a["reps"], "cues": a["cues"],
                "role": a["role"], "muscle": a["muscle"],
            })

    cats.sort(key=lambda c: (DOMAIN_ORDER[c["domain"]], cat_weight(c["cat"]), c["cat"]))
    doms = []
    for did, zh, en, _t in DOMAINS:
        sub = [c for c in cats if c["domain"] == did]
        if sub:
            doms.append({"id": did, "zh": zh, "en": en,
                         "count": sum(c["count"] for c in sub),
                         "cats": [c["cat"] for c in sub]})

    name = os.path.basename(str(path))
    return {
        "categories": cats, "acts": acts, "domains": doms,
        "meta": {"file": name, "groups": len(groups), "acts": len(acts),
                 "mtime": datetime.fromtimestamp(os.stat(path).st_mtime)
                          .isoformat(timespec="seconds")},
    }


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "../../data/01_工作簿/RPL_ExDark_v0.70_Plan_2026-11-09.xlsx"
    gs = read_groups(p)
    tp = learn_templates(p, gs)
    print("分组:", len(gs), "动作:", sum(len(g["acts"]) for g in gs))
    print("组套模板:", sum(1 for k in tp if isinstance(k, tuple) and k[0] == "group"), "个 family")
    print("斑马套模板:", sum(1 for k in tp if isinstance(k, tuple) and k[0] == "act"), "套")
    print("起始套:", tp["__start__"])
