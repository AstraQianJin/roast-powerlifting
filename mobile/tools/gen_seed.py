# -*- coding: utf-8 -*-
"""Extract the real R.ExDark workbook into seed.json for the standalone APK.

Re-run after editing the workbook:
    python gen_seed.py

T01 升级：完整 profile（init*/target*/age/gender/recovery/startDate/planWeeks）
+ structure（version 2 的 blocks / dayDefs）+ 每动作 targetRpe
+ 每日 bio/post 全字段 + 每周独立 auxDays。
"""
import json
import os
import sys

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))  # .../Roast Powerlifting
XLSX = os.path.join(ROOT, "data", "01_工作簿/RPL_ExDark_v0.15_ProMax.xlsx")
PROG_XLSX = os.path.join(ROOT, "data", "01_工作簿/RPL_Program_Library_v0.15.xlsx")
STRAT_XLSX = os.path.join(ROOT, "data", "01_工作簿/RPL_Set_Strategy_v0.15.xlsx")
OUT = os.path.join(HERE, "seed.json")
SCHEMA = os.path.join(HERE, "schema", "RPL-Plan-v3.json")


def check_seed_shape(seed):
    """种子顶层键名单的唯一出处 = 契约里的 seed.required_keys（红线 3）。
    产出的键与名单不齐就不落盘：少一个键是开屏炸（模板按名引用），
    多一个键是让下一个人以为可以往产物里随手塞东西。"""
    with open(SCHEMA, encoding="utf-8") as f:
        req = json.load(f)["seed"]["required_keys"]
    miss = [k for k in req if k not in seed]
    extra = [k for k in seed if k not in req]
    if miss or extra:
        raise SystemExit("seed 顶层键与契约 %s 名单不符：缺 %s / 多 %s（名单见 schema/RPL-Plan-v3.json 的 seed.required_keys）"
                         % (os.path.basename(SCHEMA), miss or "无", extra or "无"))

# 旧模式 → 标准键（v0.06 起不再双写旧 key）。
# v0.23 起只保留 Classic S&C 两条：`T1.Def / T1.S2 / T1.S3` 不再折叠成 `T1.Def.1/2/3`——
# 折叠让三个 Default 阶段在种子里塌成一个 tier，前端拿不到阶段，也无法按 §2.2 显示 Def 1/2/3。
# 折叠的历史方向（T2.S2/T2.S3 → T1.Def.2/3）本就写错了（T2 的键落到 T1 上），一并删除。
MODE_MIGRATION_MAP = {
    "SS": "T1.3x3",
    "SL": "T1.5x5",
}

# 协议表 A 列 FAMILY 的显示串 → 种子里的家族令牌（徽章用它，不用显示串）
FAMILY_TOKENS = {
    "TOP PEAK": "TOP",
    "CLASSIC S&C": "CLASSIC",
    "GZCLP T1": "GZCLP",
    "GZCLP T2": "GZCLP",
    "GZCLP T3": "GZCLP",
    "RTS AUTO": "RTS",
    "DELOAD": "DELOAD",
    "CUSTOM": "CUSTOM",
    "APP": "APP",
}


def mode_branch_stage(mode):
    """从规范键本身推出 (repBranch, stage)——键名即分支，见 ROADMAP §2.2 的 T1/T2/T3 表。

    不另开一份「模式 → 分支」表：那会变成第二个真相源，改了组次却忘了改这里。
    """
    tail = mode.split(".", 1)[1] if "." in mode else mode
    parts = tail.split(".")
    stem = parts[0]
    explicit_stage = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    # 分支词面与阶段不同名的几条：T1 的 Default 用 S2/S3，T2 的 Mod 2 叫 Vol
    alias = {"S2": ("Def", 2), "S3": ("Def", 3), "Vol": ("Mod", 2)}
    if stem in alias:
        branch, stage = alias[stem]
    elif stem in ("Mod", "Def", "Tr"):
        branch = stem
        stage = explicit_stage or 1
    else:
        return "", 0
    return branch, stage


# 动作库三级结构的唯一实现就在本目录；PC 侧反向 import 这里（主项目零外部代码依赖）
sys.path.insert(0, HERE)
import rxlib  # noqa: E402
import pyout  # noqa: E402

# 周表骨架坐标（标题行 / bio 行 / 动作行区间 / AUX 区）由 wkbook.py 单点定义，
# 本文件是它唯一的读者；坐标改动只改 wkbook.py，不在此处抄第二份。
from wkbook import DAY_BLOCKS, AUX_FIRST  # noqa: E402

# 周期类型预设的唯一出处 = 契约的 cycle_presets.items。
# v0.23 前这里是一张按 Block 下标取的四元组表：块一多、一换序就取错档，且与模板里
# 手抄的 CYCLE_PRESETS / MODE_BY_CYCLE 构成第二份真相源（红线 3）。
_CONTRACT = json.load(open(SCHEMA, encoding="utf-8"))
CYCLE_PRESETS = _CONTRACT["cycle_presets"]["items"]
BLOCK_DEFAULTS = _CONTRACT["sheets"]["Blocks"]["defaults"]
DELOAD_MODE_DEFAULT = BLOCK_DEFAULTS["deload_mode"]

# GPP 目录契约：种子 gpp 定义的唯一形状来源（与 App gppCanonDefs / plan_xlsx._norm_gpp_def
# 同口径，v0.45 红线 3「多处单源」的 GPP 一侧）。菜单行 + legacy 自定义项由 gen_seed 组装。
_GPP_CATALOG = json.load(open(os.path.join(HERE, "schema", "RPL-GPP-v1.json"), encoding="utf-8"))
_GPP_MASK_LEN = _CONTRACT["sheets"]["GPP"]["done_mask"]["len"]


def _gpp_cellv(v):
    return v if v not in (None, "") else ""


def _gpp_def(domain, it, custom=False):
    """目录条目 → 种子 gpp 定义：9 个契约列 + custom 旗标，字段序与 App/Python 两侧同构。"""
    d = {"domain": str(domain or ""),
         "item": str(it.get("name_en") or ""),
         "metricType": str(it.get("metric_type") or ""),
         "targetValue": _gpp_cellv(it.get("target_value")),
         "targetUnit": str(it.get("target_unit") or ""),
         "rx": str(it.get("target_text") or ""),
         "intensity": str(it.get("intensity") or ""),
         "loadKg": _gpp_cellv(it.get("load_kg_hint")),
         "targetRpe": _gpp_cellv(it.get("target_rpe"))}
    if custom:
        d["custom"] = True
    return d


def match_cycle_preset(phase_text):
    """按 `周期` C 列 PHASE 的文本关键词认周期类型；认不出就是 Custom，不猜。"""
    t = str(phase_text or "").lower()
    for c in CYCLE_PRESETS:
        if any(k and k in t for k in c["phase_match"]):
            return c
    return [c for c in CYCLE_PRESETS if c["id"] == "Custom"][0]


DAY_DEFS = [
    {"id": "A", "label": "DAY A", "titleZh": "模拟赛日", "titleEn": "Mock Day",
     "weekdayOffset": 0, "focusTags": ["tag_sbd_heavy", "tag_sq_quad"],
     "constraints": {"forbidHeavySbd": False, "forbidT1Main": False,
                     "upperOnly": False, "deloadCap": False}},
    {"id": "B", "label": "DAY B", "titleZh": "卧推日", "titleEn": "Bench Day",
     "weekdayOffset": 2, "focusTags": ["tag_bp_upper", "tag_hyper_acc"],
     "constraints": {"forbidHeavySbd": False, "forbidT1Main": False,
                     "upperOnly": False, "deloadCap": False}},
    {"id": "C", "label": "DAY C", "titleZh": "硬拉深蹲日", "titleEn": "Deadlift+Squat Day",
     "weekdayOffset": 4, "focusTags": ["tag_dl_post", "tag_sq_quad"],
     "constraints": {"forbidHeavySbd": False, "forbidT1Main": False,
                     "upperOnly": False, "deloadCap": False}},
    {"id": "D", "label": "DAY D", "titleZh": "变式日", "titleEn": "Variation Day",
     "weekdayOffset": 5, "focusTags": ["tag_vari_weak", "tag_hyper_acc", "tag_power_gpp"],
     "constraints": {"forbidHeavySbd": True, "forbidT1Main": True,
                     "upperOnly": False, "deloadCap": False}},
]

# F2 日标题迁移：权威工作簿是 v0.15 历史快照，各 W 表标题格里写的还是退役前的旧内置名
# （且工作簿含数据校验扩展 + 公式缓存值，openpyxl 重存会丢这两样，所以不改工作簿）。
# 读出来若命中旧内置名就升级为 DAY_DEFS 的 F2 名（新名单一出处 = DAY_DEFS.titleEn，不在此再抄）；
# 自定义标题（不在这张旧名表里）原样保留 —— 与 App 存档迁移 migrateStateV8 同一哲学。
_OLD_DAY_TITLE = {"A": "HEAVY SBD", "B": "BENCH FOCUS", "C": "DL + SQUAT", "D": "TECHNIQUE / VARIATION"}
_DAY_TITLE_MIGRATION = {_OLD_DAY_TITLE[d["id"]]: d["titleEn"] for d in DAY_DEFS if d["id"] in _OLD_DAY_TITLE}

V03_DOMAINS = [
    {"id": "T1.Main", "zh": "主项池", "en": "Main Lifts"},
    {"id": "Variation", "zh": "主项变式", "en": "Competition Variations"},
    {"id": "SBD", "zh": "专项辅助", "en": "SBD Specifics"},
    {"id": "Hyper", "zh": "协调增肌", "en": "Hypertrophy & Coordination"},
    {"id": "Power", "zh": "爆发体能", "en": "Power & Conditioning"},
]
SBD_SPECIFIC_CATS = {
    "SBD.UpperBack", "S.Core", "S.Quads", "B.Delts", "B.Triceps",
    "D.GluteHam", "D.Lats", "D.LowerBack", "D.Forearms",
}
POWER_CATS = {"SBD.Power", "SBD.Sled"}
HYPER_CATS = {"B.Pecs", "S.Calves", "S.GluteMed", "B.Rotator", "Unmapped"}


def domain_of_cat(cat, old_domain):
    cat = (cat or "").strip()
    if cat.endswith(".Main"):
        return "T1.Main"
    if ".Vari." in cat:
        return "Variation"
    if cat in POWER_CATS or old_domain == "Power":
        return "Power"
    if cat in SBD_SPECIFIC_CATS:
        return "SBD"
    if cat.startswith("Hyper.") or cat in HYPER_CATS:
        return "Hyper"
    if old_domain in {"T1.Main", "Variation", "SBD", "Hyper", "Power"}:
        return old_domain
    if cat.startswith(("S.", "B.", "D.", "SBD.")):
        return "SBD"
    return "Hyper"


def library_v03():
    lib = rxlib.library_payload(XLSX)
    lib["domains"] = [dict(d) for d in V03_DOMAINS]
    for cat in lib["categories"]:
        cat["domain"] = domain_of_cat(cat.get("cat"), cat.get("domain"))
    for act in lib["acts"]:
        act["domain"] = domain_of_cat(act.get("cat"), act.get("domain"))
        if act.get("en") == "Cossack Squat" and "萨克" in (act.get("cn") or ""):
            act["cn"] = "哥萨克深蹲"
        if act.get("en") == "Machine Triceps Dip / Extension" and (act.get("cn") or "").startswith("插片"):
            act["cn"] = "插片坐姿三头推压 / 臂屈伸机"
    dom_ord = {d["id"]: i for i, d in enumerate(V03_DOMAINS)}
    head_ord = {"S": 0, "B": 1, "D": 2, "SBD": 3, "Hyper": 4}
    lib["categories"].sort(key=lambda c: (
        dom_ord.get(c.get("domain"), 9),
        head_ord.get((c.get("cat") or "").split(".")[0], 5),
        c.get("cat") or "",
    ))
    return lib


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip())
    except Exception:
        return None


def mround2_5(x):
    return round(x / 2.5) * 2.5


def tier_of(mode):
    m = (mode or "").strip()
    if (m.startswith("T1") or m.startswith("Top")
            or m in ("SL", "SS", "T1.3x3", "T1.5x5", "T1.6x6") or m.startswith("RTS")):
        return "T1"
    if m.startswith("T2"):
        return "T2"
    return "T3"


def target_rpe_for(mode, base):
    t = tier_of(mode)
    if t == "T1":
        return base
    if t == "T2":
        return max(5.0, base - 0.5)
    return max(5.0, base - 1.0)


def _s(v):
    return "" if v is None else str(v).strip()


def program_lib():
    """RPL_Program_Library_v0.15.xlsx → {items:197, specs:30 条规范（按字段分组）}"""
    if not os.path.exists(PROG_XLSX):
        sys.exit("missing workbook: " + PROG_XLSX)
    wb = openpyxl.load_workbook(PROG_XLSX, data_only=True)

    ws = wb["计划总库"]
    items = []
    for r in range(2, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, 17)]
        if not any(v not in (None, "") for v in vals):
            continue
        items.append({
            "id": _s(vals[0]), "chg": _s(vals[1]), "fam": _s(vals[2]),
            "zh": _s(vals[3]), "en": _s(vals[4]), "type": _s(vals[5]),
            "goal": _s(vals[6]), "auto": _s(vals[7]),
            "glMin": num(vals[8]), "glMax": num(vals[9]),
            "dur": _s(vals[10]), "freq": _s(vals[11]), "ver": _s(vals[12]),
            "auth": _s(vals[13]), "canon": _s(vals[14]), "note": _s(vals[15]),
        })

    specs = {}
    ws2 = wb["字段规范与口径"]
    for r in range(2, ws2.max_row + 1):
        field = _s(ws2.cell(r, 1).value)
        if not field:
            continue
        specs.setdefault(field, []).append({
            "v": _s(ws2.cell(r, 2).value),
            "def": _s(ws2.cell(r, 3).value),
            "rule": _s(ws2.cell(r, 4).value),
        })
    wb.close()
    return {"items": items, "specs": specs, "source": os.path.basename(PROG_XLSX)}


def strategy_lib():
    """RPL_Set_Strategy_v0.15.xlsx → {items:27, matrix:27×5, auxActs:209}"""
    if not os.path.exists(STRAT_XLSX):
        sys.exit("missing workbook: " + STRAT_XLSX)
    wb = openpyxl.load_workbook(STRAT_XLSX, data_only=True)

    ws = wb["组策略总表"]
    items = []
    for r in range(2, ws.max_row + 1):
        vals = [ws.cell(r, c).value for c in range(1, 13)]
        if not any(v not in (None, "") for v in vals):
            continue
        idx = num(vals[0])
        # J/K/L = strategy_id / tier_std / mode_hint。mode_hint 是逗号分隔的模式键，
        # 前端按「等于或作为前缀分支」匹配（T1.Mod.2 命中 T1.Mod），所以这里就拆成数组。
        hint = _s(vals[11])
        items.append({
            "idx": int(idx) if idx is not None else len(items) + 1,
            "cat": _s(vals[1]), "zh": _s(vals[2]), "en": _s(vals[3]),
            "tier": _s(vals[4]), "lifts": _s(vals[5]), "params": _s(vals[6]),
            "scene": _s(vals[7]), "taboo": _s(vals[8]),
            "strategyId": _s(vals[9]), "tierStd": _s(vals[10]),
            "modeHint": [h.strip() for h in hint.split(",") if h.strip()],
        })

    ws2 = wb["动作适用性矩阵"]
    matrix = []
    for r in range(3, ws2.max_row + 1):
        vals = [ws2.cell(r, c).value for c in range(1, 8)]
        if not any(v not in (None, "") for v in vals):
            continue
        matrix.append({
            "zh": _s(vals[0]), "tier": _s(vals[1]),
            "sq": _s(vals[2]), "bp": _s(vals[3]), "dl": _s(vals[4]),
            "ohp": _s(vals[5]), "acc": _s(vals[6]),
        })

    ws3 = wb["三大项辅助动作库"]
    aux = []
    for r in range(3, ws3.max_row + 1):
        vals = [ws3.cell(r, c).value for c in range(1, 14)]
        if not any(v not in (None, "") for v in vals):
            continue
        aux.append({
            "id": _s(vals[0]), "lift": _s(vals[1]), "cat": _s(vals[2]),
            "sub": _s(vals[3]), "zh": _s(vals[4]), "en": _s(vals[5]),
            "tier": _s(vals[6]), "strats": _s(vals[7]), "rx": _s(vals[8]),
            "fat": _s(vals[9]), "src": _s(vals[10]), "use": _s(vals[11]),
            "note": _s(vals[12]),
        })
    wb.close()
    return {"items": items, "matrix": matrix, "auxActs": aux,
            "source": os.path.basename(STRAT_XLSX)}


def main():
    pyout.use_utf8_stdout()
    if not os.path.exists(XLSX):
        sys.exit("missing workbook: " + XLSX)

    wb = openpyxl.load_workbook(XLSX, data_only=True)

    info = wb["信息"]
    sq = num(info["D11"].value) or 135.0
    bp = num(info["D12"].value) or 95.0
    dl = num(info["D13"].value) or 165.0
    bw = num(info["D10"].value) or 85.0
    gender_raw = str(info["H14"].value or "Male").strip()
    start = info["D16"].value
    startDate = start.strftime("%Y-%m-%d") if hasattr(start, "strftime") else str(start or "2026-11-02")[:10]
    planWeeks = int(num(info["E16"].value) or 16)
    cap = _CONTRACT["capacity"]
    if not (cap["min_weeks"] <= planWeeks <= cap["max_weeks"]):
        raise SystemExit("信息!E16 的总周数 %d 超出契约容量 %s–%s（上限唯一出处 = RPL-Plan-v3.json 的 capacity）"
                         % (planWeeks, cap["min_weeks"], cap["max_weeks"]))

    profile = {
        "sq": sq, "bp": bp, "dl": dl,
        "ohp": mround2_5(bp * 0.72),
        "bw": bw,
        "initSq": sq, "initBp": bp, "initDl": dl, "initBw": bw,
        "targetSq": num(info["E11"].value) or 0.0,
        "targetBp": num(info["E12"].value) or 0.0,
        "targetDl": num(info["E13"].value) or 0.0,
        "targetBw": num(info["E10"].value) or 0.0,
        "age": int(num(info["D14"].value) or 24),
        "gender": "F" if gender_raw.lower().startswith("f") else "M",
        "equip": "classic",
        "recovery": str(info["H15"].value or "Normal / Balanced").strip(),
        "startDate": startDate,
        "planWeeks": planWeeks,
        "motto": str(info["H6"].value or "").strip(),
        # 三小项之二（F3/C2）：负重引体 / 负重双杠的最大附加负重。v0.15 权威表没有这两格，
        # 出厂默认 0（用户尚未记录）；契约 Profile 的 pullup_added_kg / dip_added_kg 同默认。
        "pullupAddedKg": 0.0,
        "dipAddedKg": 0.0,
    }

    # ---- structure（version 3，含训练日标签与建议组数人工覆盖）----
    # 周期表按 planWeeks（信息!E16）行数读，不再写死 16 行：软件容量是 0–52 周，
    # 表里行数不足就是数据缺，让它炸在这里，不要静默补成 16 周。
    period = wb["周期"]
    rpe_by_week = {}   # week -> base RPE（周期第 6 行起，每周一行）
    block_rows = {}    # block_id -> [ {week, type, phase, rpe} ]
    for i in range(planWeeks):
        r = 6 + i
        w = i + 1
        if period.cell(r, 1).value in (None, ""):
            raise SystemExit("周期表只到第 %d 行，覆盖不到 planWeeks=%d（信息!E16 说计划有 %d 周）——补表，不要静默造第 %d 周的数据"
                             % (r - 1, planWeeks, planWeeks, w))
        if period.cell(r, 2).value in (None, ""):
            raise SystemExit("周期表 B%d 的 BLOCK 是空的：块归属只能由表说；旧写法按下标猜 i//4+1，在 3+1 以外的节律上必错" % r)
        bid = str(period.cell(r, 2).value).strip()
        # D 列是 TYPE（Accum / Intens / Deload / Peak / Taper / Test），C 列 PHASE 才是块名
        block_type = str(period.cell(r, 4).value or "Accum").strip()
        phase_text = str(period.cell(r, 3).value or "").strip()
        rpe = num(period.cell(r, 7).value) or BLOCK_DEFAULTS["base_rpe"]
        rpe_by_week[w] = rpe
        block_rows.setdefault(bid, []).append({"week": w, "type": block_type, "phase": phase_text, "rpe": rpe})

    blocks = []
    for bi, bid in enumerate(sorted(block_rows, key=lambda b: int(b[1:]) if b[1:].isdigit() else 0)):
        rows = block_rows[bid]
        work = [r for r in rows if r["type"].lower() != "deload"]
        deload = [r for r in rows if r["type"].lower() == "deload"]
        preset = match_cycle_preset(work[0]["phase"] if work else rows[0]["phase"])
        cycleType, nameZh, nameEn, workMode, rpeStep = (
            preset["id"], preset["zh"], preset["en"], preset["work_mode"], preset["rpe_step"])
        baseRpe = work[0]["rpe"] if work else BLOCK_DEFAULTS["base_rpe"]
        deloadRpe = deload[0]["rpe"] if deload else BLOCK_DEFAULTS["deload_rpe"]
        blocks.append({
            "id": "B%d" % (bi + 1),
            "cycleType": cycleType,
            "nameZh": nameZh,
            "nameEn": nameEn,
            "workWeeks": len(work),
            "deloadWeeks": len(deload),
            "workMode": workMode,
            "deloadMode": DELOAD_MODE_DEFAULT,
            "baseRpe": baseRpe,
            "rpeStep": rpeStep,
            "deloadRpe": deloadRpe,
        })

    structure = {
        "version": 3,
        "startDate": startDate,
        "totalWeeks": planWeeks,
        "daysPerWeek": len(DAY_DEFS),
        "blocks": blocks,
        "dayDefs": DAY_DEFS,
        "recSetsOverride": {"sq": None, "bp": None, "dl": None},
    }

    # ---- weeks（含 targetRpe + bio/post + gppDays）----
    weeks = {}
    for w in range(1, planWeeks + 1):
        ws = wb["W%d" % w]
        base_rpe = rpe_by_week.get(w, BLOCK_DEFAULTS["base_rpe"])
        days = {}
        for did, fallback_title, title_row, bio_row, ex_start, ex_end in DAY_BLOCKS:
            raw_title = str(ws["A%d" % title_row].value or fallback_title)
            title = raw_title.replace("\n", " · ").strip()
            if "·" in title:
                title = title.split("·", 1)[1].strip()
            title = _DAY_TITLE_MIGRATION.get(title, title)  # F2：旧内置名升级为现行名

            exercises = []
            for r in range(ex_start, ex_end + 1):
                mv = ws["D%d" % r].value
                if mv is None or str(mv).strip() == "":
                    continue
                mode = str(ws["B%d" % r].value or "Custom").strip()
                mode = MODE_MIGRATION_MAP.get(mode, mode)
                trpe = target_rpe_for(mode, base_rpe)
                exercises.append({
                    "row": r,
                    "mode": mode,
                    "cat": str(ws["C%d" % r].value or "").strip(),
                    "mv": str(mv).strip(),
                    "load": num(ws["E%d" % r].value) or 0.0,
                    "rx": str(ws["F%d" % r].value or "").strip(),
                    "reps": num(ws["G%d" % r].value) or 0,
                    "targetRpe": trpe,
                    "rpe": num(ws["H%d" % r].value) or trpe,
                    "notes": str(ws["I%d" % r].value or "").strip(),
                })

            # V02-06：遥测初始一律置空 —— bio/post 不再携带 xlsx 的参考数值，
            # 只保留结构性字段（day/readiness/directive）；数值由用户在 TELEMETRY 面板录入
            days[did] = {
                "title": title,
                "readiness": str(ws["C%d" % bio_row].value or "Good / Normal (90%)"),
                "bw": num(ws["E%d" % bio_row].value) or bw,
                "bio": {
                    "day": str(ws["B%d" % bio_row].value or "").strip(),
                    "readiness": str(ws["C%d" % bio_row].value or "").strip(),
                    "directive": str(ws["I%d" % bio_row].value or "").strip(),
                },
                "post": {},
                "exercises": exercises,
            }

        # 每周独立 gppDays（每项 = {done:[7 bool], actualValue, actualUnit, actualRpe, note}）
        # 种子出厂恒为空白卡：行序在 gpp 定义段组装完后对齐到规范行数（菜单 8 行 + 自定义）。
        days["gppDays"] = [{"done": [False] * _GPP_MASK_LEN, "actualValue": "",
                            "actualUnit": "", "actualRpe": None, "note": ""}]
        weeks[str(w)] = days

    # ---- protocol ----
    # 表体从第 6 行起、到 MODE 列第一个空格为止——行数是内容不是坐标，
    # 所以不写死 range(6, 29)：往表里加一行就少读一行的那种错，静态守卫看不见。
    proto = {}
    proto_ws = wb["协议"]
    r = 6
    while r < 200:
        raw_mode = proto_ws["B%d" % r].value
        if not raw_mode:
            break
        raw_mode = str(raw_mode).strip()
        raw_family = str(proto_ws["A%d" % r].value or "").strip()
        if raw_family not in FAMILY_TOKENS:
            raise SystemExit("协议表 A%d 的家族 %r 不在 FAMILY_TOKENS 里（新增家族请同时补令牌，别让它静默变成空徽章）" % (r, raw_family))
        mode = MODE_MIGRATION_MAP.get(raw_mode, raw_mode)
        if mode in proto:
            raise SystemExit("协议表 B%d 的键 %r 与上面某行重复（迁移别名撞键会让 tier 静默覆盖）" % (r, mode))
        branch, stage = mode_branch_stage(mode)
        proto[mode] = {
            "tier": str(proto_ws["D%d" % r].value or "Other").strip(),
            "sets": int(num(proto_ws["E%d" % r].value) or 0),
            "reps": int(num(proto_ws["F%d" % r].value) or 0),
            "rx": str(proto_ws["C%d" % r].value or "").strip(),
            "family": FAMILY_TOKENS[raw_family],
            "repBranch": branch,
            "stage": stage,
        }
        r += 1
    # 只有组次、没有工作簿行的应用内模式（工作簿是权威源，这条是例外，写明来源）
    proto["T1.6x6"] = {"tier": "T1", "sets": 6, "reps": 6, "rx": "6×6",
                       "family": "GZCLP", "repBranch": "", "stage": 0}

    # ---- GPP 菜单定义（item defs，不含 days；按周打卡在 weeks[w].gppDays）----
    # v0.45 起 GPP 目录契约（schema/RPL-GPP-v1.json）是唯一权威：种子直接出厂「菜单 8 行 +
    # legacy_map.seed_aux_rows 里 new_ids 为空的旧条目落自定义」的规范形状，与 App 侧
    # gppCanonDefs 逐字段同形（ensureShape 对种子恒为恒等变换）。旧 AUX 区解析已退役：
    # 目标文本/RPE 来自目录条目，不再抄工作簿。数值列（targetValue/targetUnit/intensity）
    # 出厂留空，由用户在 GPP 引擎里补。与 plan_xlsx 的 _norm_gpp_def 同口径，
    # 保证「种子导出 → 再导入」往返稳定。
    gpp_menu = _GPP_CATALOG["weekly_menu"]
    gpp_items = {it["id"]: it for it in _GPP_CATALOG["items"]}
    menu_covered = set()
    gpp = []
    for r in gpp_menu:
        ids = r.get("item_ids") or []
        if not ids:
            raise SystemExit("GPP 契约菜单行 %s 没有 item_ids（目录与代码约定不一致）" % r.get("row"))
        it = gpp_items.get(ids[0])
        if not it:
            raise SystemExit("GPP 契约菜单行 %s 指向目录外条目 %r" % (r.get("row"), ids[0]))
        menu_covered.update(i for i in ids if i in gpp_items)
        gpp.append(_gpp_def(it.get("domain") or r.get("domain"), it))
    aux_ws = wb["W1"]
    gpp_seen = set()
    for e in _GPP_CATALOG.get("legacy_map", {}).get("seed_aux_rows", []):
        nids = [i for i in (e.get("new_ids") or []) if i in gpp_items]
        name = str(e.get("old_item") or "").strip()
        if nids and nids[0] in menu_covered:
            continue  # 菜单行已覆盖（App 侧 gppCanonDefs 的 gppMenuRowIndex 判据同口径）
        if not name or name in gpp_seen:
            continue  # 与 App 侧 seen[key] 去重同口径；落自定义的条目 item 一律用契约旧名
        gpp_seen.add(name)
        # 目录富化（与 App 同口径）：new_ids 认到的目录条目补 metric_type/target_rpe/
        # load_kg_hint/domain，rx 仍以旧 AUX 原文优先、目录文本兜底。
        cat = gpp_items.get(nids[0]) if nids else None
        r0 = (AUX_FIRST + e["old_row"]) if e.get("old_row") is not None else None
        raw = str(aux_ws["E%d" % r0].value or "").strip() if r0 is not None else ""
        src = {"domain": (cat or {}).get("domain") or e.get("new_domain") or "custom",
               "name_en": name,
               "metric_type": (cat or {}).get("metric_type"),
               "target_text": raw or (cat or {}).get("target_text"),
               "load_kg_hint": (cat or {}).get("load_kg_hint"),
               "target_rpe": (cat or {}).get("target_rpe")}
        gpp.append(_gpp_def(src["domain"], src, custom=True))

    # 打卡行数与规范定义对齐（空白卡，done 全 0；历史数据由前端迁移闸门按 legacy_map 搬家）。
    for wk in weeks.values():
        gd = wk["gppDays"]
        while len(gd) < len(gpp):
            gd.append({"done": [False] * _GPP_MASK_LEN, "actualValue": "",
                       "actualUnit": "", "actualRpe": None, "note": ""})
        del gd[len(gpp):]

    plib = program_lib()
    slib = strategy_lib()

    seed = {"profile": profile, "structure": structure, "proto": proto,
            "weeks": weeks, "gpp": gpp,
            "lib": library_v03(), "source": os.path.relpath(XLSX, os.path.join(ROOT, "data")).replace(os.sep, "/"),
            "programLib": plib, "strategyLib": slib}
    check_seed_shape(seed)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(seed, f, ensure_ascii=False, indent=1)
    wb.close()

    n_ex = sum(len(d["exercises"]) for wk in weeks.values() for d in wk.values() if isinstance(d, dict) and "exercises" in d)
    print("seed -> %s" % OUT)
    print("profile: ohp=%.1f age=%d gender=%s targetSq=%.1f targetDl=%.1f" % (
        profile["ohp"], profile["age"], profile["gender"], profile["targetSq"], profile["targetDl"]))
    print("structure: %d blocks  totalWeeks=%d  startDate=%s" % (len(blocks), planWeeks, startDate))
    print("weeks: %d | exercises: %d | gpp defs: %d" % (planWeeks, n_ex, len(gpp)))
    print("library: %d 域 / %d 分类 / %d 动作" % (
        len(seed["lib"]["domains"]), len(seed["lib"]["categories"]), len(seed["lib"]["acts"])))
    print("programLib: %d 计划 / %d 规范字段 | strategyLib: %d 策略 / %d 矩阵 / %d 辅助动作" % (
        len(plib["items"]), len(plib["specs"]),
        len(slib["items"]), len(slib["matrix"]), len(slib["auxActs"])))


if __name__ == "__main__":
    main()
