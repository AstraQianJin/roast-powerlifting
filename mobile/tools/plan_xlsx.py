# -*- coding: utf-8 -*-
"""RPL-Plan-v3 计划交换契约的 Python 侧实现（.xlsx / CSV 目录 ↔ App state）。

契约的**唯一事实源**是 `schema/RPL-Plan-v3.json`（决策 D7）：本模块只读它，
内部不出现第二份列序、枚举表或范围字面量。列一律按「角色名 → 契约真实列名」
寻址（`role_columns`），state 字段名一律取自契约的 `keys`，所以契约改列名不必
改代码，代码也不会和契约悄悄分叉。

v3 在 v2 的七表基础上把 Armor 附表换成 GPP（7 个 day-columns 收成单列 done_mask，
新增度量类型/目标值/实际值等列），并新增 Level 水平快照附表。旧计划（Profile!schema_ver
命中契约 `legacy_compat.entries[].plan_schema_vers`）按对应旧表序读写：v1 六表、v2 七表
（都含 Armor 不含 GPP/Level），导入侧把 Armor 行迁进 GPP state（见 sheets.GPP.legacy_armor）；
命中 v3 或没写 schema_ver → 八表全流程；任一清单都不命中 → 整份拒收，绝不静默降级——
分派只发生在 `_effective_order` 这一个函数里。读文件时扫「现行序 ∪ legacy 序」的全部表名，
所以旧档里的 Armor 表也会被读进 plan（`book_to_plan` / `read_plan_csvs`）。

行几何来自 `wkbook.DAYS`（A–D，与 `gen_seed.py` 同源），装载时和契约的
`row_idx.first` 逐值对账：任一方改坐标都会在这里立刻报错，而不是导出一份
行号错位、写回周表时盖错格的计划。

依赖：`openpyxl` + `wkbook`。**不 import `rxlib`**（决策 D8）——交换一份现成
计划不需要动作库推导逻辑，契约层与生成层保持解耦。

CLI（在 `mobile/` 目录下运行）：
    python tools/plan_xlsx.py validate plan.xlsx
    python tools/plan_xlsx.py validate --seed tools/seed.json
    python tools/plan_xlsx.py build   --in plan/ --out plan.xlsx
    python tools/plan_xlsx.py export  --seed tools/seed.json --out out.xlsx
    python tools/plan_xlsx.py roundtrip out.xlsx --out rt.xlsx
"""

from __future__ import annotations

import argparse
import copy
import csv
import datetime
import json
import math
import os
import re
import sys

_TOOLS = os.path.dirname(os.path.abspath(__file__))
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)

import openpyxl  # noqa: E402
import wkbook  # noqa: E402

SCHEMA_PATH = os.path.join(_TOOLS, "schema", "RPL-Plan-v3.json")
EXCHANGE_SCHEMA_PATH = os.path.join(_TOOLS, "schema", "RPL-Exchange-v3.json")
GEAR_SCHEMA_PATH = os.path.join(_TOOLS, "schema", "RPL-Gear-v1.json")
SEED_PATH = os.path.join(_TOOLS, "seed.json")
TEMPLATE_PATH = os.path.join(_TOOLS, "template.html")

# Profile 字段名：周起点与日级体重从这里取，装载时用 _require_profile_fields 断言存在。
_PROFILE_KEYS = ("start_date", "bw_kg")
_DERIVE_RE = re.compile(r"^mround\(\s*(\w+)\s*\*\s*([\d.]+)\s*,\s*([\d.]+)\s*\)$")

_SCHEMA_CACHE = {}


# ---------------------------------------------------------------- 契约装载


def load_schema(path=None):
    p = os.path.abspath(path or SCHEMA_PATH)
    if p not in _SCHEMA_CACHE:
        with open(p, encoding="utf-8") as fh:
            _SCHEMA_CACHE[p] = json.load(fh)
    return _SCHEMA_CACHE[p]


def _seed_keys(sch, field):
    """契约 seed 段的名单（顶层键单源）。取不到一律抛 —— 名单没了还继续校，
    等于把「契约缺键」伪装成「种子没问题」。"""
    block = sch.get("seed")
    if not isinstance(block, dict) or not isinstance(block.get(field), list) or not block[field]:
        raise ValueError("契约缺少 seed.%s（种子顶层键名单的唯一出处）" % field)
    return list(block[field])


def seed_required_keys(sch=None):
    return _seed_keys(sch or load_schema(), "required_keys")


def seed_invariant_keys(sch=None):
    return _seed_keys(sch or load_schema(), "invariant_keys")


def load_exchange_schema(path=None):
    """JSON 交换载体契约（schema/RPL-Exchange-v3.json）；与计划契约同规则缓存。"""
    p = os.path.abspath(path or EXCHANGE_SCHEMA_PATH)
    if p not in _SCHEMA_CACHE:
        with open(p, encoding="utf-8") as fh:
            _SCHEMA_CACHE[p] = json.load(fh)
    return _SCHEMA_CACHE[p]


def load_gear_schema(path=None):
    """器械词表契约（schema/RPL-Gear-v1.json）：Gear 表 kind/source 值域的唯一出处。
    契约的 Gear 段用 gear_vocab 引用它而不是手抄枚举（红线 3），这里按引用解析。"""
    p = os.path.abspath(path or GEAR_SCHEMA_PATH)
    if p not in _SCHEMA_CACHE:
        with open(p, encoding="utf-8") as fh:
            _SCHEMA_CACHE[p] = json.load(fh)
    return _SCHEMA_CACHE[p]


def _legacy_entries(sch):
    """契约 legacy_compat.entries[]（每条含 plan_schema_vers + sheet_order）。"""
    return (sch.get("legacy_compat") or {}).get("entries", []) or []


def _legacy_schema_vers(sch):
    """全部 legacy plan_schema_vers 扁平清单（往返比对判定「旧版即升级」用）。"""
    out = []
    for e in _legacy_entries(sch):
        for v in e.get("plan_schema_vers", []):
            if v not in out:
                out.append(v)
    return out


def _profile_ver(plan, sch):
    """plan 内 Profile!schema_ver 的原始文本（没有 → None）。"""
    cols = _cols(sch, "Profile")
    for row in plan.get("Profile") or []:
        if _text(row.get(cols[0])) == "schema_ver":
            return _text(row.get(cols[1]))
    return None


def _effective_order(plan, sch):
    """按 plan 内 Profile!schema_ver 分派出效的表序（v1/v2/v3 路由的唯一落点）。

    命中某条 legacy entry 的 plan_schema_vers → 返回该 entry 的旧表序（含 Armor 不含 GPP/Level）；
    命中本契约 schema_ver 或没写（AI 最简输入允许）→ 本契约 sheet_order；
    写了但任一清单都不命中 → 返回 None，调用方整份拒收，不静默降级。
    """
    ver = _profile_ver(plan, sch)
    if ver:
        for e in _legacy_entries(sch):
            if ver in e.get("plan_schema_vers", []):
                return list(e["sheet_order"])
    if ver in (None, "", sch["schema_ver"]):
        return list(sch["sheet_order"])
    return None


def _all_readable_sheets(sch):
    """读文件时要扫描的全部表名（现行序 ∪ 各 legacy 序），用于 book_to_plan / read_plan_csvs
    把旧档里的 Armor 也读进 plan（否则只按现行 sheet_order 扫会漏掉它，静默丢数据）。"""
    names = list(sch["sheet_order"])
    for e in _legacy_entries(sch):
        for n in e.get("sheet_order", []):
            if n not in names:
                names.append(n)
    return names


def _armor_legacy_spec(sch):
    """旧 Armor 表的机读列形（唯一出处 = sheets.GPP.legacy_armor.spec）。"""
    return _spec(sch, "GPP")["legacy_armor"]["spec"]


def _sheet_columns(sch, name):
    """某表的列序：现行表取 sheets[name].columns，legacy-only 的 Armor 取 legacy_armor.spec。"""
    if name in sch["sheets"]:
        return _cols(sch, name)
    if name == "Armor":
        return _armor_legacy_spec(sch)["columns"]
    raise KeyError("契约里没有表 '%s' 的列定义" % name)


def build_envelope(state, exported_at=None, exc=None, ver="dev"):
    """state → JSON 计划信封。键序/版本号/字段名全部取自交换契约，与前端 planEnvelope 同口径。"""
    exc = exc or load_exchange_schema()
    env_spec = exc["plan_envelope"]
    src = {
        "format": env_spec["format"],
        env_spec["schema_version_field"]: env_spec["current"],
        "exportedAt": exported_at or datetime.datetime.now().replace(microsecond=0).isoformat(),
        "app": {"name": env_spec["app_name"], "version": ver},
        "plan": state_to_plan_dict(state),
    }
    env = {}
    for k in env_spec["key_order"]:
        if k not in src:
            raise ValueError("交换契约 key_order 含未实现的键 %s" % k)
        env[k] = src[k]
    return env


def validate_envelope(env, exc=None, sch=None, strict_constraints=False):
    """信封结构 + plan 载荷双层校验；未知 schemaVersion 整份拒收，绝不静默降级。"""
    exc = exc or load_exchange_schema()
    sch = sch or load_schema()
    env_spec = exc["plan_envelope"]
    res = _res()

    def bad(reason):
        res["errors"].append("Envelope: %s" % reason)

    if not isinstance(env, dict):
        bad("信封必须是 JSON 对象")
        res["ok"] = False
        return res
    for k in env_spec["required_keys"]:
        if k not in env:
            bad("缺必带键 %s" % k)
    vf = env_spec["schema_version_field"]
    if env.get("format") != env_spec["format"]:
        bad("format=%r，只认 %r" % (env.get("format"), env_spec["format"]))
    if env.get(vf) not in env_spec["accepted"]:
        bad("%s=%r 不在接受清单 %s" % (vf, env.get(vf), env_spec["accepted"]))
    app = env.get("app")
    if not isinstance(app, dict) or any(k not in app for k in env_spec["app_keys"]):
        bad("app 必须是含 %s 的对象" % "/".join(env_spec["app_keys"]))
    keys = list(env.keys())
    want = [k for k in env_spec["key_order"] if k in env]
    if keys[:len(want)] != want:
        bad("头部键序应为 %s，实际 %s" % (want, keys[:len(want)]))
    plan = env.get("plan")
    if not isinstance(plan, dict):
        bad("plan 载荷必须是计划字典对象（表名与列名按契约）")
    else:
        sub = validate_plan_dict(plan, strict_constraints=strict_constraints, sch=sch)
        res["errors"].extend(sub["errors"])
        res["warnings"].extend(sub["warnings"])
    res["ok"] = not res["errors"]
    return res


def envelope_to_text(env):
    """信封 → 导出文本（indent=1，与前端 exportPlanJSONText 逐字节同形）。"""
    return json.dumps(env, ensure_ascii=False, indent=1)


# ---------------------------------------------------------------- JSONL 训练日志（只导不入）
#
# 日志由前端 unifiedRecords() 构建、logJsonlText() 序列化；Python 侧只做**独立校验**，
# 不重建记录逻辑（重建即第二份事实源，必漂移）。列名从 template.html 的 CSV_COLS 正则抽取
# （与 gate.py S6 同一口径），再与契约 log_jsonl.record_keys_frozen 逐列对账：
# 对不上就是协议被就地改了，一律抛错，不给静默降级留口子。

_CSV_COLS_CACHE = {}


def csv_cols_from_template(path=None, exc=None):
    """抽取并校验冻结的 26 列列名：模板实现 == 契约权威，且恰为 26 列。"""
    key = path or TEMPLATE_PATH
    cols = _CSV_COLS_CACHE.get(key)
    if cols is None:
        with open(key, encoding="utf-8") as f:
            src = f.read()
        m = re.search(r"const CSV_COLS='([^']+)'", src)
        if not m:
            raise ValueError("template.html 里解析不到 CSV_COLS 常量：%s" % key)
        cols = m.group(1).split(",")
        if len(cols) != 26:
            raise ValueError("CSV_COLS 应为 26 列，实际 %d 列" % len(cols))
        _CSV_COLS_CACHE[key] = cols
    # 契约每次都重读：缓存只省解析，不许把「契约被改了」糊过去
    frozen = (exc or load_exchange_schema())["log_jsonl"].get("record_keys_frozen")
    if not frozen:
        raise ValueError("交换契约 log_jsonl 缺 record_keys_frozen 清单（26 列协议失去权威出处）")
    if cols != frozen:
        i = next((k for k in range(max(len(cols), len(frozen)))
                  if (cols[k] if k < len(cols) else None) != (frozen[k] if k < len(frozen) else None)), 0)
        raise ValueError("CSV_COLS 与契约 record_keys_frozen 第 %d 列分叉：模板 %r ≠ 契约 %r"
                         "（改名/换序属于协议变更，要走 RPL-Log-v2）"
                         % (i + 1, cols[i] if i < len(cols) else None,
                            frozen[i] if i < len(frozen) else None))
    return cols


def validate_log_jsonl(text, exc=None, cols=None):
    """JSONL 日志结构校验：META 头记录 + 每行恰好 26 个 CSV_COLS 键。

    只校验、不重建：记录内容由前端 unifiedRecords 负责，这里确认 AI 拿到的文件
    自描述、版本可识别、每行键集与冻结的 CSV 协议一致。任一不过 → ok=False。
    """
    exc = exc or load_exchange_schema()
    spec = exc["log_jsonl"]
    hdr = spec["header_record"]
    cols = cols or csv_cols_from_template()
    colset = set(cols)
    res = _res()

    def bad(reason):
        res["errors"].append("LogJSONL: %s" % reason)

    lines = [ln for ln in str(text).splitlines() if ln.strip() != ""]
    if not lines:
        bad("空文件，至少要有 META 头记录")
        res["ok"] = False
        return res
    try:
        meta = json.loads(lines[0])
    except ValueError as e:
        bad("首行 META 不是合法 JSON：%s" % e)
        res["ok"] = False
        return res
    if not isinstance(meta, dict):
        bad("META 头记录必须是 JSON 对象")
        res["ok"] = False
        return res
    if meta.get(hdr["type_key"]) != hdr["type_value"]:
        bad("首行 %s 应为 %r，实际 %r" % (hdr["type_key"], hdr["type_value"], meta.get(hdr["type_key"])))
    for k in hdr["required_keys"]:
        if k not in meta:
            bad("META 头缺必带键 %s" % k)
    if meta.get("schema_ver") != spec["current"]:
        bad("META schema_ver=%r，只认 %r" % (meta.get("schema_ver"), spec["current"]))
    proto_field = hdr.get("schema_ver_value_field")
    if proto_field:
        if meta.get(proto_field) not in hdr.get("csv_protocol_accepted", []):
            bad("META %s=%r 不在接受清单 %s" % (proto_field, meta.get(proto_field),
                                                hdr.get("csv_protocol_accepted")))
    for i, ln in enumerate(lines[1:], start=2):
        try:
            rec = json.loads(ln)
        except ValueError as e:
            bad("第 %d 行不是合法 JSON：%s" % (i, e))
            continue
        if not isinstance(rec, dict):
            bad("第 %d 行记录必须是 JSON 对象" % i)
            continue
        keys = set(rec.keys())
        if keys != colset:
            missing = sorted(colset - keys)
            extra = sorted(keys - colset)
            detail = []
            if missing:
                detail.append("缺 %s" % "/".join(missing))
            if extra:
                detail.append("多 %s" % "/".join(extra))
            bad("第 %d 行键集与 CSV_COLS 不符（%s）" % (i, "，".join(detail)))
    res["ok"] = not res["errors"]
    return res


def row_first_map(sch=None):
    """{day_id: 该日首条动作行号}，`wkbook.DAYS` 与契约 `row_idx.first` 对账后的结果。"""
    sch = sch or load_schema()
    declared = dict(sch["row_idx"]["first"])
    for d in wkbook.DAYS:
        if d["id"] not in declared:
            raise ValueError("wkbook.DAYS 有训练日 %s，契约 row_idx.first 没有" % d["id"])
        if declared[d["id"]] != d["first"]:
            raise ValueError("row_idx 坐标分叉：wkbook.DAYS[%s].first=%s，契约=%s"
                             % (d["id"], d["first"], declared[d["id"]]))
    return declared


def _spec(sch, sheet):
    return sch["sheets"][sheet]


def _cols(sch, sheet):
    return _spec(sch, sheet)["columns"]


def _role(sch, sheet, name):
    return _spec(sch, sheet)["role_columns"][name]


# ---------------------------------------------------------------- 值解析


def _empty(v):
    return v is None or (isinstance(v, str) and v.strip() == "")


def _text(v):
    return "" if v is None else str(v).strip()


# float() 认的 ASCII 语法（千分位逗号由 _float_str 先去掉）：可带符号、整数或小数只缺一段、
# 数字间单个下划线、e 记数；外加 inf / infinity / nan 三个字面量。与 App 的 xPyFloatStr 同源。
_PY_NUM_RE = re.compile(
    r"^[+-]?(?:[0-9]+(?:_[0-9]+)*(?:\.(?:[0-9]+(?:_[0-9]+)*)?)?|\.[0-9]+(?:_[0-9]+)*)"
    r"(?:[eE][+-]?[0-9]+)?$")
_PY_SPECIAL_RE = re.compile(r"^[+-]?(?:inf(?:inity)?|nan)$", re.I)


def _float_str(s):
    """按 ASCII 语法解析 float()；不可解析 → None。

    为什么不用裸 `float()`：Python 认全角数字「１２」、也认阿拉伯-印度数字「٣」，而 JS 的
    `\\d` 只认 ASCII —— 同一串「算不算数字」在两边会给回不同答案，而「应为数字」是契约判定，
    只能有一种答案。这里显式写出 float() 认的 ASCII 语法（App 里 `xPyFloatStr` 逐字镜像），
    非 ASCII 数字串归不可解析，让必填 / 区间检查去报契约错误。
    """
    t = s.replace(",", "")
    if t == "":
        return None
    try:
        if _PY_SPECIAL_RE.match(t):
            return float(t)
        if _PY_NUM_RE.match(t):
            return float(t)
    except ValueError:
        return None
    return None


def _num(v):
    """数字；空 / 不可解析 → None；`75%` → 0.75（契约允许百分比写法）；bool 不当作数字。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = _text(v)
    if s == "":
        return None
    if s.endswith("%"):
        n = _float_str(s[:-1].strip())
        return None if n is None else n / 100.0
    return _float_str(s)


def _int(v):
    n = _num(v)
    # 手改的格子里写 "1e400" 时 _num 给回 inf，而 round(inf) / int(inf) 直接 OverflowError ——
    # 校验器不该被一份表判死，非有限值归成「不是整数」，让区间检查去报契约错误。
    # App 侧 xInt 同判定，两边必须逐字一致。
    if n is None or not math.isfinite(n) or abs(n - round(n)) > 1e-9:
        return None
    return int(round(n))


_TRUE = ("true", "1", "yes", "y", "on", "√", "是", "开")
_FALSE = ("false", "0", "no", "n", "off", "×", "否", "关", "")


def _as_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return int(v) != 0 if math.isfinite(v) else None
    s = _text(v).lower()
    if s in _TRUE:
        return True
    if s in _FALSE:
        return False
    return None


def mround(value, step):
    """等价于 JS `Math.round(v/s)*s`（半进位；Python 的 round 是银行家舍入，不能用）。"""
    s = float(step)
    x = _num(value) or 0.0
    # 格子里写 "inf" 时 math.floor(inf) 直接 OverflowError。非有限值就近不到任何 step 倍数，
    # 与 App 的 mround 同规则归 0，让区间检查去报契约错误。
    if not math.isfinite(x):
        return 0.0
    # 同理，1e308 ÷ 0.25 这种「商本身溢出」的量级也就近不到任何倍数：两边一起归 0。
    q = x / s
    if not math.isfinite(q):
        return 0.0
    return round(math.floor(q + 0.5) * s, 6)


def _date_str(v):
    if isinstance(v, datetime.datetime):
        return v.date().isoformat()
    if isinstance(v, datetime.date):
        return v.isoformat()
    return msg_val(v)


def msg_val(v):
    """错误串里「值」的唯一写法，与 `_cell_key` 同一套归一化。

    为 C4a 服务：App 内那份 JS 校验器要**逐字**复现这里的所有串。JS 的 number 没有
    int/float 之分（`24.0` 与 `24` 同为 24），Python 的 `str(24.0)` 却带 `.0`；布尔同理
    （`str(True)`='True' 而 JS='true'）。所以凡是往错误串里塞格子值或契约里的数，
    一律走这个函数，两边都按「整数值不带小数点、非整定到 6 位、布尔写 TRUE/FALSE」呈现。
    """
    return _cell_key(v)


def f1(x):
    """一位小数、半进位（`floor(x*10+0.5)/10`）。

    不能用 `%.1f`：Python 的格式化是银行家舍入（5.25→5.2），JS 的 `toFixed(1)` 是半进位
    （5.25→5.3），而 5.25 这种整除 4 的偏差在 2.5kg 步长下天天出现。两边写同一个算式才可比。
    """
    return math.floor(float(x) * 10 + 0.5) / 10


def err(sch, sheet, row, column, reason):
    """唯一错误串格式 `[{sheet}!Row{row}.{column}] {reason}`；表级错误的行号用契约占位符。"""
    label = sch["error_row_for_sheet_level"] if row in (None, "") else row
    return sch["error_format"].format(sheet=sheet, row=label, column=column, reason=reason)


def get_path(obj, path):
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def set_path(obj, path, value):
    parts = path.split(".")
    cur = obj
    for part in parts[:-1]:
        if not isinstance(cur.get(part), dict):
            cur[part] = {}
        cur = cur[part]
    cur[parts[-1]] = value


def load_default_seed():
    if not os.path.exists(SEED_PATH):
        return None
    with open(SEED_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _anchor_profile_fields(sch):
    """{cat: Profile 字段名}：契约 `anchors` 的 profile 叶名 ↔ `anchor: true` 字段。"""
    by_leaf = {}
    for name, fs in _spec(sch, "Profile")["fields"].items():
        if fs.get("anchor"):
            by_leaf[fs["path"].split(".")[-1]] = name
    return {cat: by_leaf[leaf] for cat, leaf in sch["anchors"].items()
            if isinstance(leaf, str) and leaf in by_leaf}


def _anchor_state_leaves(sch):
    """{cat: state.profile 叶名}：`_anchor_profile_fields` 给的是契约字段名，读 state 要换成叶名。"""
    fields = _spec(sch, "Profile")["fields"]
    return {cat: fields[fld]["path"].split(".")[-1] for cat, fld in _anchor_profile_fields(sch).items()}


# ---------------------------------------------------------------- state → plan


def state_to_plan_dict(state, sch=None):
    """App state / seed.json → 标准计划字典（Profile 为 field|value 行，其余为列行）。

    出哪些表按契约 sheet_order 动态派发：导出端永远是现行版本（v2 带 Gear），
    表名在这里只出现一次（sheet_order）+ 一次派发查表，不再手抄六键。"""
    sch = sch or load_schema()
    builders = {
        "Profile": _profile_from_state,
        "Blocks": _blocks_from_state,
        "Days": _days_from_state,
        "Workouts": _workouts_from_state,
        "Telemetry": _telemetry_from_state,
        "GPP": _gpp_from_state,
        "Gear": _gear_from_state,
        "Level": _level_from_state,
    }
    return {name: builders[name](state, sch) for name in sch["sheet_order"]}


def _profile_from_state(state, sch):
    cols = _cols(sch, "Profile")
    rows = []
    for field, fs in _spec(sch, "Profile")["fields"].items():
        if fs.get("enum_ref") == "accepted_schema_vers":
            value = sch["schema_ver"]
        elif "path" in fs:
            value = get_path(state, fs["path"])
        else:
            value = None
        if _empty(value) and "default" in fs:
            value = fs["default"]  # 导出即自足：state 缺省项写出契约默认值，往返不必再推一次
        rows.append({cols[0]: field, cols[1]: value, cols[2]: fs.get("desc", "")})
    return rows


def _blocks_from_state(state, sch):
    spec = _spec(sch, "Blocks")
    return [{col: b.get(key, "") for col, key in spec["keys"].items()}
            for b in (get_path(state, spec["path"]) or [])]


def _days_from_state(state, sch):
    spec = _spec(sch, "Days")
    tag_sep = spec["list_columns"][_role(sch, "Days", "tags")]
    rows = []
    for d in (get_path(state, spec["path"]) or []):
        row = {}
        for col, key in spec["keys"].items():
            v = d.get(key, spec["defaults"].get(col, ""))
            row[col] = tag_sep.join(v) if isinstance(v, list) else v
        cons = d.get("constraints") or {}
        for col in spec["bools"]:
            row[col] = bool(cons.get(spec["constraint_keys"][col], False))
        rows.append(row)
    return rows


def _week_keys(state):
    """导出用的周键（升序），跳过 D4 冻结的 `structure.inactiveWeeks`。"""
    inactive = {str(x) for x in ((state.get("structure") or {}).get("inactiveWeeks") or [])}
    return [k for k in sorted(state.get("weeks") or {}, key=lambda k: _int(k) if _int(k) is not None else 0)
            if k not in inactive]


def _day_ids_of_week(state, wk):
    defs = (state.get("structure") or {}).get("dayDefs") or []
    ids = [d.get("id") for d in defs if d.get("id")] or sorted(k for k in wk if k != "gppDays")
    return [i for i in ids if i in wk]


def _workouts_from_state(state, sch):
    spec = _spec(sch, "Workouts")
    rc, prog = spec["role_columns"], spec["prog_rules"]
    proto = state.get("proto") or {}
    leaves = _anchor_state_leaves(sch)
    profile = state.get("profile") or {}
    first = row_first_map(sch)
    dec = sch["conflict_policy"]["pct_decimals"]
    rows = []
    for wk_key in _week_keys(state):
        wk = state["weeks"][wk_key]
        for day_id in _day_ids_of_week(state, wk):
            exs = (wk.get(day_id) or {}).get("exercises") or []
            for seq, ex in enumerate(exs, start=1):
                cat, mode = _text(ex.get("cat")), _text(ex.get("mode"))
                p = proto.get(mode) or {}
                load = ex.get("load", "")
                row = {
                    rc["week"]: _int(wk_key),
                    rc["day"]: day_id,
                    rc["seq"]: seq,
                    rc["row"]: ex.get("row", first.get(day_id, 0) + seq - 1),
                    rc["tier"]: p.get("tier", ""),
                    rc["mode"]: mode,
                    rc["category"]: cat,
                    rc["movement"]: _text(ex.get("mv")),
                    rc["pct"]: "",
                    rc["load"]: load,
                    rc["sets"]: p.get("sets", ""),
                    rc["reps"]: ex.get("reps", ""),
                    rc["rx"]: _text(ex.get("rx")),
                    rc["target_rpe"]: ex.get("targetRpe", ""),
                    rc["prog_rule"]: prog.get(mode, prog.get("_default", "")),
                    rc["actual_reps"]: ex.get("actualReps", ""),
                    rc["actual_rpe"]: ex.get("rpe", ""),
                    rc["done_sets"]: ex.get("doneSets", ""),
                    rc["done"]: bool(ex.get("done", False)),
                    rc["notes"]: _text(ex.get("notes")),
                }
                anchor = _num(profile.get(leaves[cat])) if cat in leaves else None
                load_n = _num(load)
                if anchor and load_n is not None:
                    row[rc["pct"]] = round(load_n / anchor, dec)
                rows.append(row)
    return rows


def _telemetry_from_state(state, sch):
    spec = _spec(sch, "Telemetry")
    rc = spec["role_columns"]
    rows = []
    for wk_key in _week_keys(state):
        wk = state["weeks"][wk_key]
        for day_id in _day_ids_of_week(state, wk):
            day = wk.get(day_id) or {}
            row = {rc["week"]: _int(wk_key), rc["day"]: day_id}
            for col, key in spec["keys"].items():
                group, leaf = key.split(".")
                v = (day.get(group) or {}).get(leaf)
                if v is None and group == spec.get("bio_group", "bio"):
                    v = day.get(leaf)  # 兼容日级 readiness / bw（App 历史字段）
                row[col] = "" if v is None else v
            payload = [v for c, v in row.items() if c not in (rc["week"], rc["day"])]
            if any(not _empty(v) for v in payload):
                rows.append(row)
    return rows


def _gpp_cell(v):
    """GPP/Level 单元格输出：None→空串，字符串去空白，数字/布尔原样（保住 xlsx 数值类型，
    免得 25 被写成 '25' 而往返比对判为不一致）。"""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    return v


def _gpp_from_state(state, sch):
    """state.gpp（菜单定义）+ weeks[w].gppDays（逐周打卡）→ GPP 行。

    定义列逐周重复写出（每周 N 行 = N 个菜单项）；done_mask 是 7 位 '1'/'0' 串
    （周一到周日），沿用 Armor 的 7 日掩码语义但收成单列（契约 GPP.done_mask）。"""
    spec = _spec(sch, "GPP")
    rc = spec["role_columns"]
    week_col, item_col = rc["week"], rc["item"]
    mask_col = spec["done_mask"]["column"]
    mask_len = spec["done_mask"]["len"]
    keys = spec["keys"]
    def_cols = list(spec["definition_columns"])
    weekly_cols = [c for c in spec["weekly_columns"] if c != mask_col]
    defs = state.get("gpp") or []
    rows = []
    for wk_key in _week_keys(state):
        gpp_days = (state["weeks"][wk_key] or {}).get("gppDays") or []
        for idx, d in enumerate(defs):
            row = {week_col: _int(wk_key), item_col: idx}
            for col in def_cols:
                row[col] = _gpp_cell(d.get(keys[col]))
            wk_row = gpp_days[idx] if idx < len(gpp_days) else {}
            done = wk_row.get("done") or []
            row[mask_col] = "".join("1" if (i < len(done) and done[i]) else "0" for i in range(mask_len))
            for col in weekly_cols:
                row[col] = _gpp_cell(wk_row.get(keys[col]))
            rows.append(row)
    return rows


def _level_from_state(state, sch):
    """state.levelSnap → Level 行（按 date 升序；同 date 由写入侧保证唯一，见契约 write_rule）。"""
    spec = _spec(sch, "Level")
    keys = spec["keys"]
    rows = []
    for s in sorted(state.get("levelSnap") or [], key=lambda x: _text(x.get(keys["date"]))):
        rows.append({col: _gpp_cell(s.get(keys[col])) for col in spec["columns"]})
    return rows


# ---------------------------------------------------------------- Gear 附表（v2 新增，可选）


def _gear_canonical_json(gear):
    """ex.gear → 落表文本：sort_keys + 无空格，键全 ASCII，与前端 xGearCanonical 逐字节同形。

    规范化是逐字节对账的前提：同一配置两次导出、Python 与 App 引擎各自序列化，
    结果必须一字符不差（xlsxv 盯着）。
    """
    return json.dumps(gear, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _gear_from_state(state, sch):
    """逐动作器械配置 → Gear 行。只带 e.gear 的动作才占一行；kind/source 是人读冗余列。"""
    rc = _spec(sch, "Gear")["role_columns"]
    rows = []
    for wk_key in _week_keys(state):
        wk = state["weeks"][wk_key]
        for day_id in _day_ids_of_week(state, wk):
            for ex in (wk.get(day_id) or {}).get("exercises") or []:
                gear = ex.get("gear")
                if not isinstance(gear, dict) or not gear:
                    continue
                rows.append({
                    rc["week"]: _int(wk_key),
                    rc["day"]: day_id,
                    rc["row"]: ex.get("row", ""),
                    rc["kind"]: _text(gear.get("kind")),
                    rc["source"]: _text(ex.get("gearSource")) or "plan",
                    rc["gear_json"]: _gear_canonical_json(gear),
                })
    return rows


# ---------------------------------------------------------------- 行号


def _rows_of(plan, sheet):
    """列行表 → [(契约行号, row)]；行号取 `__row__`（读取时写入），否则按表头占第 1 行推算。"""
    data = plan.get(sheet)
    if data is None:
        return None
    return [(int(row.get("__row__", i + 2)), row) for i, row in enumerate(data)]


# ---------------------------------------------------------------- 校验


def _res():
    return {"ok": False, "errors": [], "warnings": []}


def _check_value(sch, sheet, row_no, name, spec, value, res, required):
    """按 spec（type / range / enum / enum_ref / pattern）校验单个值，返回归一化值；出错返回 None。"""
    if _empty(value):
        if required:
            res["errors"].append(err(sch, sheet, row_no, name, "缺少必填值"))
        return None
    t = spec.get("type")
    if t == "date":
        s = _date_str(value)
        if not re.match(spec["pattern"], s):
            res["errors"].append(err(sch, sheet, row_no, name, "日期需匹配 %s，实为 '%s'" % (spec["pattern"], s)))
            return None
        return s
    if "enum_ref" in spec:  # schema_ver：type=str 但受控于 accepted_schema_vers，必须先按枚举判
        allowed = sch[spec["enum_ref"]]
        s = msg_val(value)
        if s not in allowed:
            res["errors"].append(err(sch, sheet, row_no, name, "契约版本应为 %s，实为 '%s'" % ("/".join(allowed), s)))
            return None
        return s
    if t == "bool":
        b = _as_bool(value)
        if b is None:
            res["errors"].append(err(sch, sheet, row_no, name, "布尔值应为 TRUE/FALSE，实为 '%s'" % msg_val(value)))
        return b
    if t == "enum":
        # 归一化后按文本比：20 / 20.0 / "20" / " 20 " 视为同一个取值。
        # Excel 的数值格本来就只有 double，`<v>20</v>` 与 `<v>20.0</v>` 的区别属于读法噪声；
        # 更关键的是 JS 的 number 分不出整数与浮点，不归一化就没法与 App 内校验逐条对齐。
        hit = msg_val(value)
        for a in spec["enum"]:
            if msg_val(a) == hit or _text(a).lower() == hit.lower():
                return a
        res["errors"].append(err(sch, sheet, row_no, name, "取值应为 %s，实为 '%s'"
                                 % ("/".join(msg_val(a) for a in spec["enum"]), hit)))
        return None
    if t in ("str", None):
        return msg_val(value)
    n = _num(value)
    if n is None:
        res["errors"].append(err(sch, sheet, row_no, name, "应为数字，实为 '%s'" % msg_val(value)))
        return None
    if t == "int" and _int(value) is None:
        res["errors"].append(err(sch, sheet, row_no, name, "应为整数，实为 %s" % msg_val(value)))
        return None
    if "range" in spec:
        lo, hi = spec["range"]
        if not (lo <= n <= hi):
            res["errors"].append(err(sch, sheet, row_no, name, "越界 [%s, %s]，实为 %s"
                                     % (msg_val(lo), msg_val(hi), msg_val(value))))
            return None
    return _int(value) if t == "int" else n


def _check_columns(sch, sheet, row_no, row, res):
    """列行的 required / enums / ranges / bools 通用检查（Blocks、Days、Telemetry、Workouts 共用）。"""
    spec = _spec(sch, sheet)
    for col in spec.get("required", []):
        if _empty(row.get(col)):
            res["errors"].append(err(sch, sheet, row_no, col, "缺少必填列的值"))
    for col, allowed in (spec.get("enums") or {}).items():
        if col not in row or col.endswith("_free_text"):
            continue
        v = msg_val(row.get(col))
        if v and v not in allowed:
            res["errors"].append(err(sch, sheet, row_no, col, "取值应为 %s，实为 '%s'"
                                     % ("/".join(msg_val(a) for a in allowed), msg_val(row.get(col)))))
    for col, bounds in (spec.get("ranges") or {}).items():
        if col not in row or _empty(row.get(col)):
            continue
        _check_value(sch, sheet, row_no, col, {"type": "num", "range": list(bounds)}, row.get(col), res, False)
    for col in spec.get("bools", []):
        if col in row and not _empty(row.get(col)) and _as_bool(row.get(col)) is None:
            res["errors"].append(err(sch, sheet, row_no, col, "布尔值应为 TRUE/FALSE，实为 '%s'" % msg_val(row.get(col))))


def validate_plan_dict(plan, proto=None, strict_constraints=False, sch=None, lib=None):
    """全量契约校验，返回 `{"ok","errors","warnings"}`。

    `proto` / `lib` 缺省时取 `tools/seed.json`（契约 `mode_source`、`category_source`
    指向的就是它）；两边都拿不到时跳过 mode / category 成员检查。
    `strict_constraints=False`：训练日安全约束违规只进 warnings；True 时升级为 error。
    """
    sch = sch or load_schema()
    res = _res()
    if proto is None or lib is None:
        seed = load_default_seed() or {}
        proto = proto if proto is not None else seed.get("proto")
        lib = lib if lib is not None else seed.get("lib")

    order = _effective_order(plan, sch)
    if order is None:
        res["errors"].append(err(sch, "Profile", "", "schema_ver",
                                 "契约版本 %r 既不在现行清单也不在 legacy 清单，整份拒收"
                                 % (_text(_profile_ver_probe(plan, sch)))))
        res["ok"] = False
        return res

    for name in order:
        if name in plan:
            continue
        if name in sch["core_sheets"]:
            res["errors"].append(err(sch, name, "", _cols(sch, name)[0], "缺少核心工作表 '%s'" % name))
        else:
            res["warnings"].append(err(sch, name, "", "sheet", "可选工作表缺失，导入时按默认值初始化"))

    profile_values = _validate_profile(sch, plan, res)
    total_weeks = _validate_blocks(sch, plan, profile_values, res, proto)
    day_ids, day_defs = _validate_days(sch, plan, res)
    _validate_workouts(sch, plan, profile_values, res, proto, lib, day_ids, day_defs, total_weeks, strict_constraints)
    _validate_telemetry(sch, plan, res, day_ids, total_weeks)
    _validate_gpp(sch, plan, res, total_weeks)
    _validate_armor_legacy(sch, plan, res, total_weeks)
    _validate_level(sch, plan, res)
    _validate_gear(sch, plan, res, day_ids, total_weeks)
    res["ok"] = not res["errors"]
    return res


def _profile_ver_probe(plan, sch):
    """Profile!schema_ver 原始值（错误串展示用；判定本身在 _effective_order）。"""
    cols = _cols(sch, "Profile")
    for row in plan.get("Profile") or []:
        if _text(row.get(cols[0])) == "schema_ver":
            return row.get(cols[1])
    return None


def _validate_gear(sch, plan, res, day_ids, total_weeks):
    """Gear 表：列值域按器械词表（gear_vocab 引用，不手抄枚举）+ 锚必须命中 Workouts 行。

    gear_json 必须能解析成对象——装载只认它，kind/source 只是人读冗余。
    旧版（legacy 序）没有 Gear：表缺席连 warning 都不发，v1 文件逐字节照旧可导入。"""
    name = "Gear"
    if name not in (plan or {}):
        return
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    gear_sch = load_gear_schema()
    kind_col, src_col, json_col = rc["kind"], rc["source"], rc["gear_json"]
    allowed_kind = [k.get("id") for k in gear_sch.get("kinds", [])]
    allowed_src = list(gear_sch.get("gear_source", []))
    anchors = set()
    wr = _spec(sch, "Workouts")["role_columns"]
    first = row_first_map(sch)
    for _r, wrow in _rows_of(plan, "Workouts") or []:
        wkw, wdy, wseq = _int(wrow.get(wr["week"])), _text(wrow.get(wr["day"])), _int(wrow.get(wr["seq"]))
        wri = _int(wrow.get(wr["row"]))
        if wri is None and wseq is not None and wdy in first:
            wri = first[wdy] + wseq - 1  # 与 _apply_workouts 同一派生式：AI 不填 row_idx 也能对上锚
        anchors.add((wkw, wdy, wri))
    seen = set()
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        wk = _check_week_day(sch, name, row, res, rc, day_ids, total_weeks)
        did = _text(row.get(rc["day"]))
        ri = _int(row.get(rc["row"]))
        key = (wk, did, ri)
        if key in seen:
            res["errors"].append(err(sch, name, r, rc["row"], "重复的 (%s, %s, %s)=(%s, %s, %s)"
                                     % (spec["unique"][0], spec["unique"][1], spec["unique"][2],
                                        msg_val(wk), did, msg_val(ri))))
        else:
            seen.add(key)
        if ri is None or key not in anchors:
            res["errors"].append(err(sch, name, r, rc["row"],
                                     "锚 (week=%s, day=%s, row_idx=%s) 在 Workouts 里不存在"
                                     % (msg_val(wk), did, msg_val(ri))))
        kind = msg_val(row.get(kind_col))
        if kind and kind not in allowed_kind:
            res["errors"].append(err(sch, name, r, kind_col, "kind '%s' 不在器械词表 %s"
                                     % (kind, "/".join(msg_val(k) for k in allowed_kind))))
        src = msg_val(row.get(src_col))
        if src and src not in allowed_src:
            res["errors"].append(err(sch, name, r, src_col, "source '%s' 不在词表 %s"
                                     % (src, "/".join(msg_val(s) for s in allowed_src))))
        if _empty(row.get(json_col)):
            continue  # 空配置 = 这行没写器械，装载不建 ex.gear（契约 Gear.note）
        try:
            obj = json.loads(row.get(json_col))
        except (ValueError, TypeError):
            res["errors"].append(err(sch, name, r, json_col, "gear_json 不是合法 JSON"))
            continue
        if not isinstance(obj, dict):
            res["errors"].append(err(sch, name, r, json_col, "gear_json 应为对象，实为 %s" % type(obj).__name__))


def _profile_map(plan, sch, res):
    """Profile 行 → {字段名: (行号, 值)}；表头行与未知字段在这里处理。"""
    data = plan.get("Profile")
    if data is None:
        return None
    cols = _cols(sch, "Profile")
    known = _spec(sch, "Profile")["fields"]
    out = {}
    for i, row in enumerate(data):
        r = int(row.get("__row__", i + 2))
        fname = msg_val(row.get(cols[0]))
        if fname in ("", cols[0]):  # 空行 / 误留在数据里的表头行
            continue
        if fname not in known:
            res["warnings"].append(err(sch, "Profile", r, cols[0], "未知字段 '%s'，导入时忽略" % fname))
            continue
        out[fname] = (r, row.get(cols[1]))
    return out


def _validate_profile(sch, plan, res):
    values = {}
    prof = _profile_map(plan, sch, res)
    if prof is None:
        return values
    for name, fs in _spec(sch, "Profile")["fields"].items():
        row_no, raw = prof.get(name, ("", None))
        got = _check_value(sch, "Profile", row_no, name, fs, raw, res, bool(fs.get("required")))
        if got is None and "default" in fs:
            got = fs["default"]
        if got is not None:
            values[name] = got
    return values


def _validate_blocks(sch, plan, profile_values, res, proto):
    name = "Blocks"
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return None
    total, seen = 0, set()
    mode_cols = [rc["work_mode"], rc["deload_mode"]]
    w_col, d_col = rc["work_weeks"], rc["deload_weeks"]
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        bid = msg_val(row.get(rc["block"]))
        if bid:
            if not re.match(spec["row_rules"]["block_id"]["pattern"], bid):
                res["errors"].append(err(sch, name, r, rc["block"], "block_id 应形如 %s，实为 '%s'"
                                         % (spec["row_rules"]["block_id"]["pattern"], bid)))
            if bid in seen:
                res["errors"].append(err(sch, name, r, rc["block"], "block_id '%s' 重复" % bid))
            seen.add(bid)
        for col in (w_col, d_col):
            raw = row.get(col)
            if _empty(raw):
                continue
            if _int(raw) is None:
                res["errors"].append(err(sch, name, r, col, "应为整数周数，实为 '%s'" % msg_val(raw)))
            else:
                total += _int(raw)
        for col in mode_cols:
            v = msg_val(row.get(col))
            if v and proto is not None and v not in proto:
                res["errors"].append(err(sch, name, r, col, "模式 '%s' 不在 proto 中" % v))
    if not rows:
        res["errors"].append(err(sch, name, "", rc["block"], "Blocks 表没有周期块"))
        return None
    lo, hi = spec["row_rules"]["total_weeks"]["range"]
    if not (lo <= total <= hi):
        res["errors"].append(err(sch, name, "", rc["work_weeks"], "周期块周数合计 %d 越界 [%s, %s]"
                                 % (total, msg_val(lo), msg_val(hi))))
    pw = profile_values.get("plan_weeks")
    if pw is not None and pw != total:
        res["errors"].append(err(sch, "Profile", "", "plan_weeks", "plan_weeks=%s 与 Blocks 周数之和 %d 不符"
                                 % (msg_val(pw), total)))
    return total


def _day_def(sch, plan_row):
    """Days 列行 → state dayDef（字段名全部取自契约 `keys` / `constraint_keys`）。

    文本一律走 `msg_val`（=`_cell_key` 的归一化）而不是 `_text`：数值格写成 `21.0` 还是
    `21` 是读法噪声，JS 的 number 本来就分不出这两者，归一化之后两边才能得到同一个 id。
    """
    spec = _spec(sch, "Days")
    rc = spec["role_columns"]
    tag_sep = spec["list_columns"][rc["tags"]]
    d = {}
    for col, key in spec["keys"].items():
        raw = plan_row.get(col, spec["defaults"].get(col, ""))
        if col == rc["tags"]:
            d[key] = [t.strip() for t in msg_val(raw).split(tag_sep) if t.strip()]
        elif col == rc["weekday"]:
            d[key] = _int(raw) or 0
        else:
            d[key] = msg_val(raw)
    d["constraints"] = {spec["constraint_keys"][col]: bool(_as_bool(plan_row.get(col, False)))
                        for col in spec["bools"]}
    return d


def _day_field(sch, role):
    """Days 的 role 列名 → state 字段名（契约 `keys` 的值），如 day → `id`、tags → `focusTags`。"""
    col = _role(sch, "Days", role)
    return _spec(sch, "Days")["keys"][col]


def _validate_days(sch, plan, res):
    name = "Days"
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return [], []
    day_ids, defs, seen = [], [], set()
    enum_tags = spec["enums"]["focus_tag"]
    id_field, tags_field = _day_field(sch, "day"), _day_field(sch, "tags")
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        d = _day_def(sch, row)
        did = d.get(id_field)
        if did not in spec["enums"]["day_id"]:
            res["errors"].append(err(sch, name, r, rc["day"], "day_id 应为 %s，实为 '%s'"
                                     % ("/".join(spec["enums"]["day_id"]), did)))
        elif did in seen:
            res["errors"].append(err(sch, name, r, rc["day"], "day_id '%s' 重复" % did))
        else:
            seen.add(did)
            day_ids.append(did)
        for t in d.get(tags_field, []):
            if t not in enum_tags:
                res["errors"].append(err(sch, name, r, rc["tags"], "未知标签 '%s'，应为 %s" % (t, "/".join(enum_tags))))
        for col in spec["bools"]:
            if _as_bool(row.get(col, False)) is None:
                res["errors"].append(err(sch, name, r, col, "布尔值应为 TRUE/FALSE，实为 '%s'" % msg_val(row.get(col))))
        d["__row__"] = r
        defs.append(d)
    if len(rows) > spec["max_rows"]:
        res["errors"].append(err(sch, name, "", rc["day"], "训练日行数 %d 超过上限 %d" % (len(rows), spec["max_rows"])))
    if not day_ids:
        res["errors"].append(err(sch, name, "", rc["day"], "Days 表没有有效训练日"))
    return day_ids, defs


def _pred_hit(pred, cat, tier, mode, target_rpe):
    if "cat_in" in pred and cat not in pred["cat_in"]:
        return False
    if "cat_prefix" in pred and not any(cat.startswith(p) for p in pred["cat_prefix"]):
        return False
    if "cat_suffix" in pred and not cat.endswith(pred["cat_suffix"]):
        return False
    if "tier_in" in pred and tier not in pred["tier_in"]:
        return False
    if "mode_any" in pred and not any(
        mode.startswith(p[:-1]) if p.endswith(".*") else mode == p for p in pred["mode_any"]
    ):
        return False
    if "target_rpe_gt" in pred and not (target_rpe is not None and target_rpe > pred["target_rpe_gt"]):
        return False
    return True


def _rule_hit(rule, cat, tier, mode, target_rpe):
    return any(_pred_hit(p, cat, tier, mode, target_rpe) for p in rule["any_of"])


def _validate_workouts(sch, plan, profile_values, res, proto, lib, day_ids, day_defs, total_weeks, strict):
    name = "Workouts"
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    if not rows:
        res["errors"].append(err(sch, name, "", rc["movement"], "Workouts 表没有任何动作行"))
        return
    first = row_first_map(sch)
    anchors = _anchor_profile_fields(sch)
    cp = sch["conflict_policy"]
    cats = {c["cat"] for c in (lib or {}).get("categories", [])}
    acts = {a["en"] for a in (lib or {}).get("acts", [])}
    id_field, tags_field = _day_field(sch, "day"), _day_field(sch, "tags")
    flags = {d[id_field]: d["constraints"] for d in day_defs}
    tags = {d[id_field]: d.get(tags_field, []) for d in day_defs}
    uniq, seqs = {}, {}
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        wk = _int(row.get(rc["week"]))
        if wk is None or wk < 1:
            res["errors"].append(err(sch, name, r, rc["week"], "week 应为 ≥1 的整数，实为 '%s'" % msg_val(row.get(rc["week"]))))
        elif total_weeks and wk > total_weeks:
            res["errors"].append(err(sch, name, r, rc["week"], "week=%d 超出 Blocks 合计周数 %d" % (wk, total_weeks)))
        did = msg_val(row.get(rc["day"]))
        if did and day_ids and did not in day_ids:
            res["errors"].append(err(sch, name, r, rc["day"], "day '%s' 未在 Days 表定义" % did))
        seq = _int(row.get(rc["seq"]))
        if seq is not None and seq < 1:
            res["errors"].append(err(sch, name, r, rc["seq"], "seq 应为 1-based 整数，实为 '%s'" % msg_val(row.get(rc["seq"]))))
        mode = msg_val(row.get(rc["mode"]))
        cat = msg_val(row.get(rc["category"]))
        mv = msg_val(row.get(rc["movement"]))
        tier_decl = msg_val(row.get(rc["tier"]))
        p = (proto or {}).get(mode) or {}
        tier = p.get("tier") or tier_decl
        if mode and proto is not None and mode not in proto:
            res["errors"].append(err(sch, name, r, rc["mode"], "mode '%s' 不在 proto（%d 个模式）中" % (mode, len(proto))))
        elif tier_decl and p and tier_decl != p["tier"]:
            res["warnings"].append(err(sch, name, r, rc["tier"],
                                        "tier='%s' 与 proto 推导的 '%s' 不符，导入时以 proto 为准" % (tier_decl, p["tier"])))
        if cat and cats and cat not in cats:
            res["errors"].append(err(sch, name, r, rc["category"],
                                     "category '%s' 不在 lib.categories（%d 组）中" % (cat, len(cats))))
        if mv and acts and mv not in acts:
            res["warnings"].append(err(sch, name, r, rc["movement"],
                                        "movement '%s' 不在动作库（%d 个不重复动作名）中，请核对拼写" % (mv, len(acts))))
        pct, load = _num(row.get(rc["pct"])), _num(row.get(rc["load"]))
        anchor_field = anchors.get(cat)
        if anchor_field:
            if pct is None and load is None:
                res["errors"].append(err(sch, name, r, rc["pct"], "主项动作必须给 %s 或 %s" % (rc["pct"], rc["load"])))
            anchor = profile_values.get(anchor_field)
            if pct is not None and anchor:
                expect = mround(float(anchor) * pct, cp["round_step_kg"])
                if load is not None and abs(load - expect) > cp["tolerance_kg"]:
                    res["warnings"].append(err(sch, name, r, rc["load"],
                        "%s=%s 与 %s 推导值 %s 偏差 %skg > %skg：%s 为权威，导入时覆写"
                        % (rc["load"], msg_val(load), rc["pct"], msg_val(expect),
                           msg_val(f1(abs(load - expect))), msg_val(cp["tolerance_kg"]), rc["pct"])))
        ri = _int(row.get(rc["row"])) if not _empty(row.get(rc["row"])) else None
        if not _empty(row.get(rc["row"])) and ri is None:
            res["errors"].append(err(sch, name, r, rc["row"], "row_idx 应为整数，实为 '%s'" % msg_val(row.get(rc["row"]))))
        elif ri is not None and seq is not None and did in first:
            expect = first[did] + seq - 1
            if ri != expect:
                res["warnings"].append(err(sch, name, r, rc["row"],
                                            "row_idx=%d 与 first[%s]+seq-1=%d 不符，导入时按原值保留" % (ri, did, expect)))
        if not _empty(row.get(rc["actual_reps"])):
            res["warnings"].append(err(sch, name, r, rc["actual_reps"],
                                        "%s 不参与导入（App 无该字段），处方次数看 %s" % (rc["actual_reps"], rc["reps"])))
        key = tuple(row.get(c) for c in spec["unique"])
        if all(not _empty(v) for v in key):
            if key in uniq:
                res["errors"].append(err(sch, name, r, spec["unique"][-1], "重复的 (%s)=(%s)"
                                         % (", ".join(spec["unique"]), ", ".join(msg_val(v) for v in key))))
            else:
                uniq[key] = r
        if wk is not None and did and seq is not None:
            bucket = seqs.setdefault((wk, did), set())
            if seq in bucket:
                res["errors"].append(err(sch, name, r, rc["seq"], "(week=%d, day=%s) 内 seq=%d 重复" % (wk, did, seq)))
            bucket.add(seq)
        tr = _num(row.get(rc["target_rpe"]))
        for rule in sch["constraint_rules"]:
            on = bool(flags.get(did, {}).get(rule["when"]))
            if not on and rule.get("also_when_tag"):
                on = rule["also_when_tag"] in tags.get(did, [])
            if on and _rule_hit(rule, cat, tier, mode, tr):
                msg = "%s（该日启用了 %s）" % (rule["why"], rule["when"])
                (res["errors"] if strict else res["warnings"]).append(err(sch, name, r, rc["mode"], msg))


def _check_week_day(sch, name, row, res, rc, day_ids, total_weeks):
    wk = _int(row.get(rc["week"]))
    if wk is None or wk < 1 or (total_weeks and wk > total_weeks):
        res["errors"].append(err(sch, name, "", rc["week"], "week='%s' 不在 1..%s"
                                 % (msg_val(row.get(rc["week"])), msg_val(total_weeks))))
    if "day" in rc:
        did = msg_val(row.get(rc["day"]))
        if did and day_ids and did not in day_ids:
            res["errors"].append(err(sch, name, "", rc["day"], "day '%s' 未在 Days 表定义" % did))
    return wk


def _validate_telemetry(sch, plan, res, day_ids, total_weeks):
    name = "Telemetry"
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    seen = set()
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        wk = _check_week_day(sch, name, row, res, rc, day_ids, total_weeks)
        key = (wk, msg_val(row.get(rc["day"])))
        if key in seen:
            res["errors"].append(err(sch, name, r, spec["unique"][-1], "重复的 (%s, %s)=(%s, %s)"
                                     % (spec["unique"][0], spec["unique"][1], msg_val(wk), key[1])))
        seen.add(key)


def _validate_gpp(sch, plan, res, total_weeks):
    """GPP 表（v3 现行）：required/enums/ranges 走通用列检，另加 done_mask 格式、
    定义列一致性、(week,item_idx) 唯一。缺席即返回（可选表）。"""
    name = "GPP"
    if name not in (plan or {}):
        return
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    mask_col = spec["done_mask"]["column"]
    mask_len = spec["done_mask"]["len"]
    def_cols = list(spec["definition_columns"])
    defs, seen = {}, set()
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        wk = _int(row.get(rc["week"]))
        if wk is None or wk < 1 or (total_weeks and wk > total_weeks):
            res["errors"].append(err(sch, name, r, rc["week"], "week='%s' 不在 1..%s"
                                     % (msg_val(row.get(rc["week"])), msg_val(total_weeks))))
        mask = row.get(mask_col)
        if not _empty(mask):
            s = _text(mask)
            if len(s) != mask_len or any(ch not in "01" for ch in s):
                res["errors"].append(err(sch, name, r, mask_col, "done_mask 应为 %d 位 0/1 串（周一到周日），实为 '%s'"
                                         % (mask_len, s)))
        idx = _int(row.get(rc["item"]))
        if idx is None or idx < 0:
            res["errors"].append(err(sch, name, r, rc["item"], "item_idx 应为 0-based 整数，实为 '%s'"
                                     % msg_val(row.get(rc["item"]))))
            continue
        definition = tuple(msg_val(row.get(c)) for c in def_cols)
        if idx not in defs:
            defs[idx] = definition
        elif defs[idx] != definition:
            res["errors"].append(err(sch, name, r, rc["item_name"], "item_idx=%d 定义不一致：'%s' vs '%s'"
                                     % (idx, defs[idx][1], definition[1])))
        key = (wk, idx)
        if key in seen:
            res["errors"].append(err(sch, name, r, spec["unique"][-1], "重复的 (%s, %s)=(%s, %s)"
                                     % (spec["unique"][0], spec["unique"][1], msg_val(wk), msg_val(idx))))
        seen.add(key)


def _validate_armor_legacy(sch, plan, res, total_weeks):
    """旧 Armor 表（legacy_compat.entries 命中的 v1/v2 档）：按 legacy_armor.spec 校验。
    sch['sheets'] 里没有 Armor，所以不走 _check_columns，直接用旧 spec 的列形。"""
    name = "Armor"
    if name not in (plan or {}):
        return
    spec = _armor_legacy_spec(sch)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    day_cols = spec["day_columns"]
    defs, seen = {}, set()
    for r, row in rows:
        for col in spec["required"]:
            if _empty(row.get(col)):
                res["errors"].append(err(sch, name, r, col, "缺少必填列的值"))
        for col in day_cols:
            if col in row and not _empty(row.get(col)) and _as_bool(row.get(col)) is None:
                res["errors"].append(err(sch, name, r, col, "布尔值应为 TRUE/FALSE，实为 '%s'" % msg_val(row.get(col))))
        wk = _int(row.get(rc["week"]))
        if wk is None or wk < 1 or (total_weeks and wk > total_weeks):
            res["errors"].append(err(sch, name, r, rc["week"], "week='%s' 不在 1..%s"
                                     % (msg_val(row.get(rc["week"])), msg_val(total_weeks))))
        idx = _int(row.get(rc["item"]))
        if idx is None or idx < 0:
            res["errors"].append(err(sch, name, r, rc["item"], "item_idx 应为 0-based 整数，实为 '%s'"
                                     % msg_val(row.get(rc["item"]))))
            continue
        definition = tuple(msg_val(row.get(c)) for c in (rc["domain"], rc["item_name"], rc["target"], rc["intensity"]))
        if idx not in defs:
            defs[idx] = definition
        elif defs[idx] != definition:
            res["errors"].append(err(sch, name, r, rc["item_name"], "item_idx=%d 定义不一致：'%s' vs '%s'"
                                     % (idx, defs[idx][1], definition[1])))
        key = (wk, idx)
        if key in seen:
            res["errors"].append(err(sch, name, r, spec["unique"][-1], "重复的 (%s, %s)=(%s, %s)"
                                     % (spec["unique"][0], spec["unique"][1], msg_val(wk), msg_val(idx))))
        seen.add(key)


def _validate_level(sch, plan, res):
    """Level 表（可选）：date 必填且匹配 YYYY-MM-DD，数值列走 ranges，rank_stars 为整数。
    同 date 多行按 write_rule.same_day = 后行覆盖前行（导入不报错，只 warning）。"""
    name = "Level"
    if name not in (plan or {}):
        return
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    rows = _rows_of(plan, name)
    if rows is None:
        return
    date_col = rc["date"]
    pattern = spec["date_pattern"]
    int_cols = set(spec.get("ints", []))
    seen = {}
    for r, row in rows:
        _check_columns(sch, name, r, row, res)
        for col in int_cols:
            if not _empty(row.get(col)) and _int(row.get(col)) is None:
                res["errors"].append(err(sch, name, r, col, "应为整数，实为 '%s'" % msg_val(row.get(col))))
        d = _text(row.get(date_col))
        if not d:
            continue
        if not re.match(pattern, d):
            res["errors"].append(err(sch, name, r, date_col, "date 需匹配 %s，实为 '%s'" % (pattern, d)))
        elif d in seen:
            res["warnings"].append(err(sch, name, r, date_col,
                                       "date '%s' 与第 %d 行重复，导入时后行覆盖前行" % (d, seen[d])))
        seen[d] = r


def validate_seed_schema(seed, sch=None):
    """校验 seed.json / App state 的顶层不变量（Step 2.1 第 5 项）。
    顶层键名单取自契约的 seed.invariant_keys —— 导入后的 App state 不带 payload 三键
    （source / programLib / strategyLib 是种子独有的只读资产），所以这里校的是「不变量所需的那几个」；
    齐全性（required_keys）由 gate 的 S9/S24 与 gen_seed 的自检负责。"""
    sch = sch or load_schema()
    res = _res()
    for key in seed_invariant_keys(sch):
        if key not in seed:
            res["errors"].append(err(sch, "seed", "", key, "缺少顶层键 '%s'" % key))
    if res["errors"]:
        return res
    st = seed["structure"]
    lo, hi = _spec(sch, "Workouts")["ranges"]["target_rpe"]
    total = sum(b.get("workWeeks", 0) + b.get("deloadWeeks", 0) for b in st.get("blocks", []))
    if st.get("totalWeeks") != total:
        res["errors"].append(err(sch, "seed", "", "totalWeeks",
                                 "structure.totalWeeks=%s 与 blocks 周数之和 %d 不符" % (st.get("totalWeeks"), total)))
    if len(seed["weeks"]) != total:
        res["errors"].append(err(sch, "seed", "", "weeks", "weeks 数 %d 与 blocks 周数之和 %d 不符" % (len(seed["weeks"]), total)))
    if not st.get("dayDefs"):
        res["errors"].append(err(sch, "seed", "", "dayDefs", "structure.dayDefs 为空"))
    n_ex = 0
    for wk_key, wk in (seed["weeks"] or {}).items():
        for d in [x.get("id") for x in st.get("dayDefs", [])]:
            day = wk.get(d)
            if day is None:
                res["errors"].append(err(sch, "seed", wk_key, d, "周 %s 缺训练日 %s" % (wk_key, d)))
                continue
            for i, e in enumerate(day.get("exercises") or [], start=1):
                n_ex += 1
                if _empty(e.get("mv")):
                    res["errors"].append(err(sch, "seed", "%s/%s" % (wk_key, d), "movement", "第 %d 个动作名为空" % i))
                tr = e.get("targetRpe")
                if tr is None or not (lo <= float(tr) <= hi):
                    res["errors"].append(err(sch, "seed", "%s/%s" % (wk_key, d), "target_rpe",
                                              "targetRpe=%s 越界 [%s, %s]" % (tr, lo, hi)))
    lib = seed["lib"]
    dom = {x["id"] for x in lib.get("domains", [])}
    cats = {c["cat"] for c in lib.get("categories", [])}
    if not dom:
        res["errors"].append(err(sch, "seed", "", "domains", "lib.domains 为空"))
    for c in lib.get("categories", []):
        if c.get("domain") not in dom:
            res["errors"].append(err(sch, "seed", c.get("cat", "?"), "domain", "分组的 domain 不在 lib.domains 中"))
    for a in lib.get("acts", []):
        if a.get("cat") not in cats:
            res["errors"].append(err(sch, "seed", a.get("en", "?"), "category", "动作的 cat 不在 lib.categories 中"))
    if not seed.get("gpp"):
        res["errors"].append(err(sch, "seed", "", "gpp", "GPP 菜单定义为空"))
    res["ok"] = not res["errors"]
    res["stats"] = {"weeks": len(seed.get("weeks") or {}), "exercises": n_ex,
                    "domains": len(dom), "categories": len(cats), "acts": len(lib.get("acts", []))}
    return res


# ---------------------------------------------------------------- plan → state


def plan_dict_to_state(plan, base_seed=None, strict_constraints=False, sch=None):
    """校验通过的计划字典 → 完整 App state。校验失败直接抛 `ValueError`（带全部错误行）。"""
    sch = sch or load_schema()
    base = base_seed if (isinstance(base_seed, dict) and "proto" in base_seed) else load_default_seed()
    res = validate_plan_dict(plan, proto=(base or {}).get("proto"), lib=(base or {}).get("lib"),
                             strict_constraints=strict_constraints, sch=sch)
    if not res["ok"]:
        raise ValueError("计划不符合 %s 契约：\n  %s" % (sch["schema_ver"], "\n  ".join(res["errors"])))
    return _load_plan_state(plan, base, sch)


def _load_plan_state(plan, base_seed=None, sch=None):
    """装载本体：**不过契约闸门**，与 JS 侧 xPlanDictToState 里 validate 之后的段落一一对应。
    闸门留给 plan_dict_to_state 与 App 的 importPlanFromXlsxBytes；对账要拿非法计划
    （edge 样本）撞 D4 冻结与缺列兜底，走的正是这条无闸门路径。"""
    sch = sch or load_schema()
    _require_profile_fields(sch)
    if _effective_order(plan, sch) is None:
        raise ValueError("契约版本 %r 既不在现行清单也不在 legacy 清单，整份拒收（不静默降级）"
                         % _text(_profile_ver_probe(plan, sch)))
    base = base_seed if (isinstance(base_seed, dict) and "proto" in base_seed) else load_default_seed()
    if base is None:
        raise ValueError("找不到 tools/seed.json：契约的 proto / lib 与装甲默认值无处可取")
    state = copy.deepcopy(base)
    profile_values = _validate_profile(sch, plan, _res())
    _apply_profile(sch, profile_values, state)
    blocks = _blocks_to_state(sch, plan)
    day_defs = _days_to_state(sch, plan)
    total = sum(b[k] for b in blocks for k in _week_count_fields(sch))
    _apply_on_missing(sch, profile_values, state, total)
    gpp_defs = _gpp_defs_from_plan(sch, plan) or copy.deepcopy(base.get("gpp") or [])
    state["gpp"] = gpp_defs
    state["levelSnap"] = _level_from_plan(sch, plan)
    state["structure"] = {
        "version": sch["state_defaults_on_import"]["structure.version"],
        "startDate": profile_values.get(_PROFILE_KEYS[0]),
        "totalWeeks": total,
        "daysPerWeek": len(day_defs),
        "blocks": blocks,
        "dayDefs": day_defs,
        "recSetsOverride": copy.deepcopy((base.get("structure") or {}).get("recSetsOverride")
                                         or _default_rec_sets(sch)),
    }
    state["weeks"] = _blank_weeks(sch, total, day_defs, profile_values, gpp_defs)
    _apply_workouts(sch, plan, state, base.get("proto"), total)
    _apply_gear(sch, plan, state)
    _apply_gpp(sch, plan, state)
    _apply_telemetry(sch, plan, state)
    _freeze_extra_weeks(state, base.get("weeks") or {})
    return state


def _default_rec_sets(sch):
    """state.structure.recSetsOverride 的骨架：键与 Profile 的三项主项锚点同名。"""
    anchors = set(_anchor_profile_fields(sch).values())
    leaves = [_spec(sch, "Profile")["fields"][a]["path"].split(".")[-1] for a in anchors]
    return {leaf: None for leaf in sorted(leaves)}


def _apply_profile(sch, values, state):
    fields = _spec(sch, "Profile")["fields"]
    leaf = {name: fs["path"].split(".")[-1] for name, fs in fields.items() if "path" in fs}
    for name, fs in fields.items():
        if "path" not in fs:
            continue
        v = values[name] if name in values else fs.get("default")
        if v is not None:
            set_path(state, fs["path"], v)  # 契约无默认值且未提供 → 保留 base state 现值，不写 None
    profile = state.get("profile") or {}
    for name, fs in fields.items():
        if "path" not in fs or name in values:
            continue
        src_name = fs.get("default_from")
        if src_name is not None:
            src = values.get(src_name, profile.get(leaf.get(src_name)))
            if src is not None:
                set_path(state, fs["path"], src)
            continue
        m = _DERIVE_RE.match(fs.get("derive", ""))
        if m:
            src = values.get(m.group(1), profile.get(leaf.get(m.group(1))))
            if src is not None:
                set_path(state, fs["path"], mround(float(src) * float(m.group(2)), m.group(3)))


def _apply_on_missing(sch, values, state, total):
    """契约里声明了 `on_missing` 的 Profile 字段：本次没写就按当次计划算。

    `plan_weeks` 必须有这条：留着上一份计划的周数，再导出时会与本次 Blocks
    之和对不上，`cross` 检查立刻把自己判成 error —— 自己产出的文件过不了自己的契约。
    """
    fields = _spec(sch, "Profile")["fields"]
    for name, fs in fields.items():
        if fs.get("on_missing") == "total_weeks" and name not in values and "path" in fs:
            set_path(state, fs["path"], total)


def _require_profile_fields(sch):
    """契约里若改掉这两个 Profile 字段名，装载就报错，而不是静默产出错日期/错体重的计划。"""
    fields = _spec(sch, "Profile")["fields"]
    for name in _PROFILE_KEYS:
        if name not in fields:
            raise ValueError("契约 Profile 缺字段 '%s'（plan_xlsx 依赖它推导周起点与日级体重）" % name)
    return fields


def _block_prefix(spec):
    """从契约的 `^B\\d+$` 取出编号前缀（字母段），导入时按行序重编为 B1..Bn。"""
    m = re.match(r"^\^?([A-Za-z]+)", spec["row_rules"]["block_id"]["pattern"])
    if not m:
        raise ValueError("契约 row_rules.block_id.pattern 无法解析编号前缀：%s"
                         % spec["row_rules"]["block_id"]["pattern"])
    return m.group(1)


def _blocks_to_state(sch, plan):
    spec = _spec(sch, "Blocks")
    rc = spec["role_columns"]
    ints = set(_week_count_fields(sch))
    floats = {spec["keys"][c] for c in spec["ranges"] if c not in (rc["work_weeks"], rc["deload_weeks"])}
    prefix = _block_prefix(spec)
    block_field = spec["keys"][rc["block"]]
    out = []
    for i, (_r, row) in enumerate(_rows_of(plan, "Blocks") or [], start=1):
        b = {}
        for col, key in spec["keys"].items():
            raw = row.get(col)
            if _empty(raw):
                raw = spec["defaults"].get(col, "")
            if key in ints:
                b[key] = _int(raw) or 0
            elif key in floats:
                b[key] = _num(raw)
            else:
                b[key] = _text(raw)
        b[block_field] = "%s%d" % (prefix, i)
        out.append(b)
    return out


def _week_count_fields(sch):
    """Blocks 的两个周数列 → state 字段名（求和周数、判断块跨度都靠它们）。"""
    spec = _spec(sch, "Blocks")
    return [spec["keys"][spec["role_columns"][k]] for k in ("work_weeks", "deload_weeks")]


def _days_to_state(sch, plan):
    out = []
    for _r, row in _rows_of(plan, "Days") or []:
        d = _day_def(sch, row)
        d.pop("__row__", None)
        out.append(d)
    return out


def _week_rpe_map(sch, blocks, total):
    """{周: 基准 RPE}：块内训练周取 baseRpe，减载周取 deloadRpe（给缺 target_rpe 的行兜底）。"""
    spec = _spec(sch, "Blocks")
    keys = spec["keys"]
    w_f, dl_f = _week_count_fields(sch)
    base_f, dl_rpe_f = keys[spec["role_columns"]["base_rpe"]], keys[spec["role_columns"]["deload_rpe"]]
    dl_default = spec["defaults"].get(spec["role_columns"]["deload_rpe"])
    out, w = {}, 1
    for b in blocks:
        for _ in range(b[w_f]):
            if w <= total:
                out[w] = b[base_f]
            w += 1
        for _ in range(b[dl_f]):
            if w <= total:
                out[w] = b.get(dl_rpe_f, dl_default)
            w += 1
    return out


def _blank_gpp_day(mask_len):
    """单个 GPP 菜单项的空白周打卡（契约 state_defaults_on_import.gppDays）。"""
    return {"done": [False] * mask_len, "actualValue": "", "actualUnit": "", "actualRpe": None, "note": ""}


def _blank_weeks(sch, total, day_defs, profile_values, gpp_defs):
    days_spec = _spec(sch, "Days")
    labels = days_spec["weekday_labels"]
    mask_len = _spec(sch, "GPP")["done_mask"]["len"]
    id_f, wd_f = _day_field(sch, "day"), _day_field(sch, "weekday")
    en_f, zh_f = _day_field(sch, "title_en"), _day_field(sch, "title_zh")
    weeks = {}
    for w in range(1, total + 1):
        wk = {}
        for d in day_defs:
            wk[d[id_f]] = {
                "title": d.get(en_f) or d.get(zh_f) or "",
                "readiness": "",
                "bw": profile_values.get(_PROFILE_KEYS[1]),
                "bio": {"day": labels[d[wd_f] % len(labels)]},
                "post": {},
                "exercises": [],
            }
        wk["gppDays"] = [_blank_gpp_day(mask_len) for _ in gpp_defs]
        weeks[str(w)] = wk
    return weeks


def _apply_workouts(sch, plan, state, proto, total):
    spec = _spec(sch, "Workouts")
    rc = spec["role_columns"]
    fields = _spec(sch, "Profile")["fields"]
    first = row_first_map(sch)
    anchors = _anchor_profile_fields(sch)
    cp = sch["conflict_policy"]
    rpe_by_week = _week_rpe_map(sch, state["structure"]["blocks"], total)
    base_rpe_default = _spec(sch, "Blocks")["defaults"][_role(sch, "Blocks", "base_rpe")]
    groups = {}
    for _r, row in _rows_of(plan, "Workouts") or []:
        wk, did = _int(row.get(rc["week"])), _text(row.get(rc["day"]))
        if wk is None or did not in (state["weeks"].get(str(wk)) or {}):
            continue
        groups.setdefault((wk, did), []).append(row)
    for (wk, did), rows in groups.items():
        rows.sort(key=lambda x: (_int(x.get(rc["seq"])) or 0, _int(x.get(rc["row"])) or 0))
        exs = state["weeks"][str(wk)][did]["exercises"]
        for seq, row in enumerate(rows, start=1):
            mode, cat = _text(row.get(rc["mode"])), _text(row.get(rc["category"]))
            p = (proto or {}).get(mode) or {}
            ri = _int(row.get(rc["row"]))
            ex = {
                "row": ri if ri is not None else first.get(did, 0) + seq - 1,
                "mode": mode,
                "cat": cat,
                "mv": _text(row.get(rc["movement"])),
                "notes": _text(row.get(rc["notes"])),
                "done": bool(_as_bool(row.get(rc["done"]))),
            }
            reps, tr = _num(row.get(rc["reps"])), _num(row.get(rc["target_rpe"]))
            ex["reps"] = reps if reps is not None else p.get("reps", 0)
            ex["rx"] = _text(row.get(rc["rx"])) or p.get("rx", "")
            ex["targetRpe"] = tr if tr is not None else rpe_by_week.get(wk, base_rpe_default)
            ar = _num(row.get(rc["actual_rpe"]))
            if ar is not None:
                ex["rpe"] = ar
            ds = _int(row.get(rc["done_sets"]))
            if ds is not None:
                ex["doneSets"] = ds
            pct, load = _num(row.get(rc["pct"])), _num(row.get(rc["load"]))
            field = anchors.get(cat)
            if field and pct is not None:
                anchor = _num(get_path(state, fields[field]["path"]))
                if anchor:
                    load = mround(anchor * pct, cp["round_step_kg"])  # 决策 D10：%1RM 权威，覆写 load_kg
            ex["load"] = load if load is not None else 0
            exs.append(ex)


def _apply_gear(sch, plan, state):
    """Gear 行按 (week, day, row_idx) 锚合并进 ex：ex['gear']=json.loads(gear_json)。

    只在表存在且行命中锚时写；装载只读 gear_json，kind/source 是人读冗余列
    （source=local 才落 gearSource 字段，plan 是缺省态、不写脏键）。"""
    name = "Gear"
    if name not in (plan or {}):
        return
    spec = _spec(sch, name)
    rc = spec["role_columns"]
    defaults = spec.get("defaults") or {}
    wr = _spec(sch, "Workouts")["role_columns"]
    by_key = {}
    for wk_key in _week_keys(state):
        wk = state["weeks"][wk_key]
        for day_id in _day_ids_of_week(state, wk):
            for ex in (wk.get(day_id) or {}).get("exercises") or []:
                by_key[(_int(wk_key), day_id, _int(ex.get("row")))] = ex
    for _r, row in _rows_of(plan, name) or []:
        key = (_int(row.get(rc["week"])), _text(row.get(rc["day"])), _int(row.get(rc["row"])))
        ex = by_key.get(key)
        if ex is None:
            continue  # 锚不命中由 _validate_gear 报 error；无闸门路径（D8 对账）在这里静默跳过
        src = _text(row.get(rc["source"])) or defaults.get("source", "plan")
        raw = row.get(rc["gear_json"])
        if _empty(raw):
            continue
        try:
            gear = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(gear, dict) and gear:
            ex["gear"] = gear
            if src == "local":
                ex["gearSource"] = "local"


def _norm_gpp_def(d):
    """把一个来源各异的字典规整成 state.gpp 的规范定义形状（缺的数值列留空串，不缺类型）。"""
    d = d or {}
    def _nv(k):
        v = d.get(k)
        return v if v not in (None, "") else ""
    out = {
        "domain": _text(d.get("domain")),
        "item": _text(d.get("item")),
        "metricType": _text(d.get("metricType")),
        "targetValue": _nv("targetValue"),
        "targetUnit": _text(d.get("targetUnit")),
        "rx": _text(d.get("rx")),
        "intensity": _text(d.get("intensity")),
        "loadKg": _nv("loadKg"),
        "targetRpe": _nv("targetRpe"),
    }
    if d.get("custom"):
        out["custom"] = True
    return out


def _gpp_defs_from_plan(sch, plan):
    """GPP 菜单定义：现行 GPP 表优先，其次旧 Armor 表（迁移），都没有 → None（用种子默认）。"""
    if "GPP" in (plan or {}):
        return _gpp_defs_from_gpp_sheet(sch, plan)
    if "Armor" in (plan or {}):
        return _gpp_defs_from_armor_sheet(sch, plan)
    return None


def _gpp_defs_from_gpp_sheet(sch, plan):
    spec = _spec(sch, "GPP")
    rc, keys = spec["role_columns"], spec["keys"]
    item_col = rc["item"]
    def_cols = list(spec["definition_columns"])
    numeric = set(spec.get("ranges", {}))
    defs = {}
    for _r, row in _rows_of(plan, "GPP") or []:
        idx = _int(row.get(item_col))
        if idx is None or idx in defs:
            continue
        d = {}
        for col in def_cols:
            raw = row.get(col)
            d[keys[col]] = _num(raw) if col in numeric else _text(raw)
        defs[idx] = _norm_gpp_def(d)
    return [defs[i] for i in sorted(defs)]


def _gpp_defs_from_armor_sheet(sch, plan):
    """旧 Armor 定义 → GPP 定义：domain/item 原样，target→rx，intensity→intensity，
    新增的数值列（metric_type/target_value/target_unit/load_kg/target_rpe）留空。"""
    spec = _armor_legacy_spec(sch)
    rc, keys = spec["role_columns"], spec["keys"]
    item_col = rc["item"]
    defs = {}
    for _r, row in _rows_of(plan, "Armor") or []:
        idx = _int(row.get(item_col))
        if idx is None or idx in defs:
            continue
        d = {keys[col]: _text(row.get(col)) for col in keys if col != item_col}
        defs[idx] = _norm_gpp_def(d)
    return [defs[i] for i in sorted(defs)]


def _apply_gpp(sch, plan, state):
    """逐周打卡写回 weeks[w].gppDays：现行 GPP 表（done_mask + actual_*）或旧 Armor 表（7 日列）。"""
    if "GPP" in (plan or {}):
        _apply_gpp_sheet(sch, plan, state)
    elif "Armor" in (plan or {}):
        _apply_armor_sheet(sch, plan, state)


def _apply_gpp_sheet(sch, plan, state):
    spec = _spec(sch, "GPP")
    rc, keys = spec["role_columns"], spec["keys"]
    mask_col = spec["done_mask"]["column"]
    mask_len = spec["done_mask"]["len"]
    numeric = set(spec.get("ranges", {}))
    weekly_cols = [c for c in spec["weekly_columns"] if c != mask_col]
    for _r, row in _rows_of(plan, "GPP") or []:
        wk, idx = _int(row.get(rc["week"])), _int(row.get(rc["item"]))
        wkobj = state["weeks"].get(str(wk)) if wk is not None else None
        if wkobj is None or idx is None or idx >= len(wkobj.get("gppDays") or []):
            continue
        cell = wkobj["gppDays"][idx]
        mask = _text(row.get(mask_col))
        for i in range(mask_len):
            cell["done"][i] = (i < len(mask) and mask[i] == "1")
        for col in weekly_cols:
            raw = row.get(col)
            if _empty(raw):
                continue
            cell[keys[col]] = _num(raw) if col in numeric else _text(raw)


def _apply_armor_sheet(sch, plan, state):
    spec = _armor_legacy_spec(sch)
    rc = spec["role_columns"]
    day_cols = spec["day_columns"]
    for _r, row in _rows_of(plan, "Armor") or []:
        wk, idx = _int(row.get(rc["week"])), _int(row.get(rc["item"]))
        wkobj = state["weeks"].get(str(wk)) if wk is not None else None
        if wkobj is None or idx is None or idx >= len(wkobj.get("gppDays") or []):
            continue
        done = wkobj["gppDays"][idx]["done"]
        for i, col in enumerate(day_cols):
            if i < len(done):
                done[i] = bool(_as_bool(row.get(col)))


def _level_from_plan(sch, plan):
    """Level 表 → state.levelSnap（按 date 升序；同 date 后行覆盖前行，见契约 write_rule）。"""
    if "Level" not in (plan or {}):
        return []
    spec = _spec(sch, "Level")
    rc, keys = spec["role_columns"], spec["keys"]
    numeric = set(spec.get("ranges", {}))
    int_cols = set(spec.get("ints", []))
    date_col = rc["date"]
    by_date = {}
    for _r, row in _rows_of(plan, "Level") or []:
        d = _text(row.get(date_col))
        if not d:
            continue
        snap = {}
        for col in spec["columns"]:
            key, raw = keys[col], row.get(col)
            if col == date_col:
                snap[key] = d
            elif _empty(raw):
                snap[key] = None if (col in numeric or col in int_cols) else ""
            elif col in int_cols:
                snap[key] = _int(raw)
            elif col in numeric:
                snap[key] = _num(raw)
            else:
                snap[key] = _text(raw)
        by_date[d] = snap
    return [by_date[d] for d in sorted(by_date)]


def _apply_telemetry(sch, plan, state):
    spec = _spec(sch, "Telemetry")
    rc = spec["role_columns"]
    numeric = set(spec.get("ranges", {}))
    mirror = set(spec.get("mirror_day_level", []))
    for _r, row in _rows_of(plan, "Telemetry") or []:
        wk, did = _int(row.get(rc["week"])), _text(row.get(rc["day"]))
        day = (state["weeks"].get(str(wk)) or {}).get(did)
        if day is None:
            continue
        for col, key in spec["keys"].items():
            raw = row.get(col)
            if _empty(raw):
                continue
            group, leaf = key.split(".")
            v = _num(raw) if col in numeric else _text(raw)
            day.setdefault(group, {})[leaf] = v
            if leaf in mirror:
                day[leaf] = v


def _freeze_extra_weeks(state, old_weeks):
    """决策 D4：超出新计划周数的既有周键不删除，登记 `structure.inactiveWeeks` 冻结保留。"""
    total = state["structure"]["totalWeeks"]
    inactive = set(state["structure"].get("inactiveWeeks") or [])
    for key, wk in (old_weeks or {}).items():
        n = _int(key)
        if n is None or n <= total:
            continue
        state["weeks"].setdefault(str(n), copy.deepcopy(wk))
        inactive.add(n)
    state["structure"]["inactiveWeeks"] = sorted(inactive)


# ---------------------------------------------------------------- xlsx / CSV I/O


def _cell_out(v, as_csv=False):
    if v is None:
        return ""
    if isinstance(v, bool):
        # CSV 没有布尔类型：写成 Excel 认的 TRUE/FALSE，读回后与布尔单元格同值；工作簿保持真布尔。
        return ("TRUE" if v else "FALSE") if as_csv else v
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _cell_key(v):
    """比对用归一化：空串 / None 同值，bool 写成 TRUE/FALSE，整数值浮点写成整数。"""
    if v is None or (isinstance(v, str) and v.strip() == ""):
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(round(v, 6))
    return _text(v)


def plan_to_book(plan, out_path, sch=None):
    """计划字典 → .xlsx：出效表全写（可选表无数据时只留表头；legacy 序不含 Gear）。"""
    sch = sch or load_schema()
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name in (_effective_order(plan, sch) or sch["sheet_order"]):
        cols = _sheet_columns(sch, name)
        ws = wb.create_sheet(name)
        ws.append(list(cols))
        for row in plan.get(name) or []:
            ws.append([_cell_out(row.get(c)) for c in cols])
    wb.save(out_path)
    return out_path


def _sheet_raw(ws):
    raw = []
    for row in ws.iter_rows(values_only=True):
        cells = list(row)
        if all(_empty(c) for c in cells):
            continue
        raw.append(cells)
    return raw


def _profile_rows_from_raw(raw, sch):
    """Profile 原始二维表 → field|value 行；自动识别 `field|value|description` 与横向两行两种排布。"""
    cols = _cols(sch, "Profile")
    if not raw:
        return []
    vertical = _text(raw[0][0]) == cols[0]
    if vertical:
        rows = []
        for i, cells in enumerate(raw[1:], start=2):
            rows.append({cols[0]: (cells[0] if len(cells) > 0 else ""),
                         cols[1]: (cells[1] if len(cells) > 1 else ""),
                         cols[2]: (cells[2] if len(cells) > 2 else ""),
                         "__row__": i})
        return rows
    names = [_text(c) for c in raw[0]]
    vals = raw[1] if len(raw) > 1 else []
    return [{cols[0]: n, cols[1]: (vals[i] if i < len(vals) else ""), cols[2]: "", "__row__": 1}
            for i, n in enumerate(names) if n]


def _column_rows_from_raw(sch, name, raw, res_errors, cols=None):
    """列布局原始二维表 → 行字典（带 `__row__`）；表头与契约列序不符时记 error，仍按位置解析。
    `cols` 缺省按 `_sheet_columns` 解析（现行表取 sheets[name]，legacy-only 的 Armor 取 legacy_armor.spec）。"""
    cols = list(cols if cols is not None else _sheet_columns(sch, name))
    header = [_text(c) for c in raw[0]]
    if header[: len(cols)] != list(cols) or len(header) != len(cols):
        for j in range(max(len(cols), len(header))):
            want = cols[j] if j < len(cols) else "（多余列）"
            got = header[j] if j < len(header) else "（缺失）"
            if want != got:
                res_errors.append(err(sch, name, 1, cols[j] if j < len(cols) else "_extra",
                                       "表头第 %d 列应为 '%s'，实为 '%s'" % (j + 1, want, got)))
    rows = []
    for i, cells in enumerate(raw[1:], start=2):
        row = {cols[j]: (cells[j] if j < len(cells) else "") for j in range(len(cols))}
        row["__row__"] = i
        rows.append(row)
    return rows


def book_to_plan(xlsx_path, sch=None):
    """.xlsx → (计划字典, 表头错误列表)。扫现行序 ∪ legacy 序的全部表名，
    所以旧档里的 Armor 表也会被读进 plan（只按现行 sheet_order 扫会漏它，静默丢数据）。"""
    sch = sch or load_schema()
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    plan, errors = {}, []
    for name in _all_readable_sheets(sch):
        if name not in wb.sheetnames:
            continue
        raw = _sheet_raw(wb[name])
        if not raw:
            plan[name] = []
            continue
        plan[name] = (_profile_rows_from_raw(raw, sch) if name == "Profile"
                      else _column_rows_from_raw(sch, name, raw, errors))
    wb.close()
    return plan, errors


def plan_book_to_state(xlsx_path, base_seed=None, strict_constraints=False, sch=None):
    """.xlsx → App state；表头或契约校验不过直接抛 `ValueError`。"""
    sch = sch or load_schema()
    plan, errors = book_to_plan(xlsx_path, sch)
    if errors:
        raise ValueError("工作簿表头与 %s 契约不符：\n  %s" % (sch["schema_ver"], "\n".join(errors)))
    return plan_dict_to_state(plan, base_seed=base_seed, strict_constraints=strict_constraints, sch=sch)


def state_to_plan_book(state_or_seed, out_path, sch=None):
    """state / seed → 工作簿；`out_path` 以 `.xlsx` 结尾写工作簿，否则当成存放 CSV 家族的目录。"""
    sch = sch or load_schema()
    plan = state_to_plan_dict(state_or_seed, sch)
    if str(out_path).lower().endswith(".xlsx"):
        return plan_to_book(plan, out_path, sch)
    return write_plan_csvs(plan, out_path, sch)


def write_plan_csvs(plan, out_dir, sch=None):
    """计划字典 → 目录下的 CSV 家族（`Profile.csv` … 列序与契约一致，UTF-8 BOM 便于 Excel）。"""
    sch = sch or load_schema()
    os.makedirs(out_dir, exist_ok=True)
    for name in (_effective_order(plan, sch) or sch["sheet_order"]):
        cols = _sheet_columns(sch, name)
        with open(os.path.join(out_dir, "%s.csv" % name), "w", encoding="utf-8-sig", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for row in plan.get(name) or []:
                w.writerow([_cell_out(row.get(c), as_csv=True) for c in cols])
    return out_dir


def _csv_profile_probe_plan(in_dir, sch):
    """只读 Profile.csv 拼一份探针 plan，供 _effective_order 判版本（读目录前的先窥）。"""
    path = os.path.join(in_dir, "Profile.csv")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig", newline="") as fh:
        raw = [r for r in csv.reader(fh) if any(not _empty(c) for c in r)]
    if not raw:
        return {}
    return {"Profile": _profile_rows_from_raw(raw, sch)}


def _csv_sheet_order(in_dir, sch):
    return _effective_order(_csv_profile_probe_plan(in_dir, sch), sch) or sch["sheet_order"]


def read_plan_csvs(in_dir, sch=None):
    """目录下的 CSV 家族 → (计划字典, 表头错误列表)；CSV 第 n 行即工作簿第 n 行。"""
    sch = sch or load_schema()
    plan, errors = {}, []
    for name in _csv_sheet_order(in_dir, sch):
        path = os.path.join(in_dir, "%s.csv" % name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8-sig", newline="") as fh:
            raw = [r for r in csv.reader(fh) if any(not _empty(c) for c in r)]
        if not raw:
            plan[name] = []
            continue
        plan[name] = (_profile_rows_from_raw(raw, sch) if name == "Profile"
                      else _column_rows_from_raw(sch, name, raw, errors))
    return plan, errors


def read_plan_any(path, sch=None):
    """按路径形态分派：目录 → CSV 家族；`.xlsx` → 工作簿。返回 (plan, errors)。"""
    sch = sch or load_schema()
    return read_plan_csvs(path, sch) if os.path.isdir(path) else book_to_plan(path, sch)


# ---------------------------------------------------------------- 往返一致性


def _load_overwrite_ok(sch, name, row_a, row_b, pvals):
    """契约 D10 的往返豁免：pct_1rm 在场时 load_kg 被 mround(anchor×pct) 覆写，B 侧不同值不算丢数据。

    B 与契约算出的覆写值一致时返回该值，否则 None（该格仍按 A 的原值逐格比）。
    """
    cp = sch["conflict_policy"]
    if cp["pct_1rm_vs_load_kg"] != "authoritative_pct_warning_only":
        return None
    rc = _spec(sch, name)["role_columns"]
    field = _anchor_profile_fields(sch).get(_text(row_a.get(rc["category"])))
    pct, load_col = _num(row_a.get(rc["pct"])), rc["load"]
    anchor = _num(pvals.get(field)) if field else None
    if pct is None or not anchor:
        return None
    expect = mround(anchor * pct, cp["round_step_kg"])
    return expect if _cell_key(expect) == _cell_key(row_b.get(load_col)) else None


def _keyed_map(rows, cols):
    """按契约 unique 列把行编成字典；任一行键不全或有重复键 → None（退回行序对齐，不猜）。"""
    if not cols:
        return None
    out = {}
    for row in rows:
        key = tuple(_cell_key(row.get(c)) for c in cols)
        if any(x == "" for x in key) or key in out:
            return None
        out[key] = row
    return out


def _derived_only(sch, name):
    """纯导出派生列（`on` 以 export 开头且没有 keep_on_import）。

    这些列在 A 侧是**输入**（AI 写的 pct / tier / sets），在 B 侧是**计算值**
    （pct 由 load 反推、tier/sets 由 proto 查表），逐格相等从来不是契约的承诺；
    派生得对不对由 validate / 专用断言管，往返比对只管真正落进 state 的那些列。
    """
    dc = _spec(sch, name).get("derived_columns") or {}
    return {c for c, v in dc.items() if str(v.get("on", "")).startswith("export") and not v.get("keep_on_import")}


def diff_plan_cells(a, b, sch=None):
    """两份计划的逐格比对：`{"cells_a","cells_b","diffs":[...]}`（cells 为已填充单元格数）。

    语义是**回归检测**：a 里每个已填的**非派生**格都必须在 b 中原样出现；b 可以比 a 多 ——
    导入按契约补齐 Profile 默认值，那是补全，不是改动。要卡「完全等值」请再比
    `cells_a == cells_b`（两份导出产物天然相等）。

    行对齐用契约 `unique` 列，所以 AI 手写的行序和导出的行序不同也不算差异；
    Profile 是 field→value 字典，一律按字段名对齐，且只比 value（description 是给人看的）。
    """
    sch = sch or load_schema()
    diffs = []
    cells_a = cells_b = 0
    pvals = _validate_profile(sch, a, _res())
    for name in (_effective_order(a, sch) or sch["sheet_order"]):
        if name not in sch["sheets"]:
            continue  # legacy-only 表（Armor）：v2→v3 是升级路径，不做逐格往返比对（由迁移断言覆盖）
        cols = _cols(sch, name)
        rcol = _spec(sch, name).get("role_columns") or {}
        load_col = rcol.get("load") if "pct" in rcol and "category" in rcol else None
        ra, rb = a.get(name) or [], b.get(name) or []
        cells_a += sum(1 for row in ra for c in cols if _cell_key(row.get(c)) != "")
        cells_b += sum(1 for row in rb for c in cols if _cell_key(row.get(c)) != "")
        if _spec(sch, name).get("layout") == "field_value":
            key_col, val_col = cols[0], cols[1]
            by_field = {}
            for row in rb:
                by_field.setdefault(_text(row.get(key_col)), row)
            for i, row in enumerate(ra):
                field = _text(row.get(key_col))
                want = _cell_key(row.get(val_col))
                if field == "" or want == "":
                    continue
                if field == "schema_ver" and want in _legacy_schema_vers(sch):
                    continue  # 旧版载入即升级为现行导出，是承诺不是回归
                other = by_field.get(field)
                if other is None:
                    diffs.append(err(sch, name, row.get("__row__") or i + 2, key_col,
                                     "往返后字段 '%s' 丢失" % field))
                elif _cell_key(other.get(val_col)) != want:
                    diffs.append(err(sch, name, row.get("__row__") or i + 2, val_col,
                                     "往返不一致：原值 '%s'，再导出 '%s'" % (want, _cell_key(other.get(val_col)))))
            continue
        ucols = _spec(sch, name).get("unique") or []
        skip = _derived_only(sch, name)
        ka, kb = _keyed_map(ra, ucols), _keyed_map(rb, ucols)
        if ka and kb:
            compare = []
            for key, row_a in ka.items():
                row_b = kb.get(key)
                if row_b is None:
                    diffs.append(err(sch, name, row_a.get("__row__") or "", ucols[0],
                                     "往返后行 (%s)=(%s) 丢失" % (", ".join(ucols), ", ".join(key))))
                    continue
                compare.append((row_b, row_a))
        else:
            if len(ra) > len(rb):
                diffs.append(err(sch, name, len(rb) + 2, cols[0],
                                 "行数不一致：原 %d 行，再导出 %d 行" % (len(ra), len(rb))))
            compare = [(rb[i], ra[i]) for i in range(min(len(ra), len(rb)))]
        for row_b, row_a in compare:
            for col in cols:
                if col in skip:
                    continue
                va = _cell_key(row_a.get(col))
                if va == "":
                    continue
                vb = _cell_key(row_b.get(col))
                if va != vb:
                    if load_col == col and _load_overwrite_ok(sch, name, row_a, row_b, pvals) is not None:
                        continue  # 决策 D10：pct_1rm 权威，load 被契约算出的值覆写是承诺，不是丢失
                    diffs.append(err(sch, name, row_a.get("__row__") or "", col,
                                     "往返不一致：原值 '%s'，再导出 '%s'" % (va, vb)))
    return {"cells_a": cells_a, "cells_b": cells_b, "diffs": diffs}


def roundtrip_plan(plan, base_seed=None, strict_constraints=False, sch=None):
    """plan → state → plan：往返一致性内核（不落盘，测试可直接调用）。"""
    sch = sch or load_schema()
    state = plan_dict_to_state(plan, base_seed=base_seed, strict_constraints=strict_constraints, sch=sch)
    again = state_to_plan_dict(state, sch)
    return state, again, diff_plan_cells(plan, again, sch)


def roundtrip_book(xlsx_path, out_path=None, base_seed=None, strict_constraints=False, sch=None):
    """.xlsx → state → .xlsx，逐格比对；返回 (比对结果, 第二份产物路径)。"""
    sch = sch or load_schema()
    plan, errors = book_to_plan(xlsx_path, sch)
    if errors:
        raise ValueError("\n".join(errors))
    state, again, diff = roundtrip_plan(plan, base_seed=base_seed,
                                       strict_constraints=strict_constraints, sch=sch)
    out = out_path or (os.path.splitext(xlsx_path)[0] + ".rt.xlsx")
    plan_to_book(again, out, sch)
    return {"state": state, "diff": diff}, out


# ---------------------------------------------------------------- CLI


def _report(res, label):
    for e in res["errors"]:
        print("ERROR   %s" % e)
    for w in res["warnings"]:
        print("warning %s" % w)
    print("%s：%d error / %d warning" % (label, len(res["errors"]), len(res["warnings"])))
    return 0 if res["ok"] else 1


def main(argv=None):
    # 与 tools/pyout.py 同效，但必须内联：T4.5 断言本文件的依赖面只有
    # openpyxl + wkbook + 标准库，多一个本地 import 就会红。
    # stdout 默认跟随控制台代码页，非中文机器上 print 中文会直接 UnicodeEncodeError。
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="RPL-Plan-v3 计划交换（契约见 schema/RPL-Plan-v3.json，legacy v1 六表 / v2 七表照旧可导入）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="校验交换工作簿 / CSV 目录 / seed.json")
    v.add_argument("path", nargs="?", help=".xlsx 或含 CSV 家族的目录")
    v.add_argument("--seed", dest="seed", nargs="?", const=SEED_PATH, help="改校验 seed.json 顶层不变量")
    v.add_argument("--strict-constraints", action="store_true")

    b = sub.add_parser("build", help="校验 + 补齐派生列，产出一份规范工作簿")
    b.add_argument("--in", dest="src", required=True, help=".xlsx 或 CSV 目录")
    b.add_argument("--out", dest="out", required=True, help=".xlsx 或 CSV 目录")
    b.add_argument("--state-out", dest="state_out", help="同时导出转换后的 state JSON")
    b.add_argument("--strict-constraints", action="store_true")

    e = sub.add_parser("export", help="seed.json / state JSON → 计划工作簿")
    e.add_argument("--seed", dest="seed", default=SEED_PATH)
    e.add_argument("--out", dest="out", required=True)

    j = sub.add_parser("json", help="state/seed JSON ⇄ JSON 计划信封（交换唯一权威载体）")
    j.add_argument("--state", dest="state", help="state JSON；缺省用 --seed")
    j.add_argument("--seed", dest="seed", default=SEED_PATH)
    j.add_argument("--out", dest="out", help="信封写出路径（导出模式必填）")
    j.add_argument("--ver", dest="ver", default="dev", help="app.version 字段值")
    j.add_argument("--check", dest="check", help="校验既有信封文件而不导出")

    lj = sub.add_parser("logjsonl", help="校验 JSONL 训练日志（只导不入，Python 侧仅独立校验）")
    lj.add_argument("--check", dest="check", required=True, help="待校验的 .jsonl 文件")

    r = sub.add_parser("roundtrip", help="工作簿 → state → 工作簿，逐格比对")
    r.add_argument("path", help="待往返的 .xlsx（通常是 export 的产物）")
    r.add_argument("--out", dest="out", help="第二份产物路径，默认 <input>.rt.xlsx")
    r.add_argument("--strict-constraints", action="store_true")

    a = ap.parse_args(argv)
    sch = load_schema()

    if a.cmd == "validate":
        if a.seed:
            with open(a.seed, encoding="utf-8") as fh:
                return _report(validate_seed_schema(json.load(fh), sch), "seed 结构校验 %s" % os.path.basename(a.seed))
        if not a.path:
            ap.error("validate 需要 PATH 或 --seed")
        plan, errors = read_plan_any(a.path, sch)
        res = validate_plan_dict(plan, strict_constraints=a.strict_constraints, sch=sch)
        res["errors"] = errors + res["errors"]
        res["ok"] = not res["errors"]
        return _report(res, "契约校验 %s" % os.path.basename(a.path))

    if a.cmd == "export":
        with open(a.seed, encoding="utf-8") as fh:
            state = json.load(fh)
        res = validate_seed_schema(state, sch)
        if not res["ok"]:
            return _report(res, "seed 结构校验")
        print("已写出 %s" % state_to_plan_book(state, a.out, sch))
        return 0

    if a.cmd == "json":
        exc = load_exchange_schema()
        if a.check:
            with open(a.check, encoding="utf-8") as fh:
                env = json.load(fh)
            res = validate_envelope(env, exc=exc, sch=sch)
            return _report(res, "信封校验 %s" % os.path.basename(a.check))
        if not a.out:
            ap.error("json 导出需要 --out（或用 --check 校验既有信封）")
        with open(a.state or a.seed, encoding="utf-8") as fh:
            state = json.load(fh)
        if not a.state:  # seed 入口才查种子不变量；state JSON 的合法性由信封自检的载荷校验兜住
            res = validate_seed_schema(state, sch)
            if not res["ok"]:
                return _report(res, "seed 结构校验")
        env = build_envelope(state, ver=a.ver, exc=exc)
        res2 = validate_envelope(env, exc=exc, sch=sch)
        if not res2["ok"]:
            return _report(res2, "信封自检")
        with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(envelope_to_text(env))
        print("已写出信封 %s（%s=%s · %d 张表）" % (
            a.out, exc["plan_envelope"]["schema_version_field"],
            env[exc["plan_envelope"]["schema_version_field"]], len(env["plan"])))
        return 0

    if a.cmd == "logjsonl":
        with open(a.check, encoding="utf-8") as fh:
            text = fh.read()
        res = validate_log_jsonl(text, exc=load_exchange_schema())
        return _report(res, "JSONL 日志校验 %s" % os.path.basename(a.check))

    if a.cmd == "build":
        plan, errors = read_plan_any(a.src, sch)
        for e in errors:
            print("ERROR   %s" % e)
        try:
            state = plan_dict_to_state(plan, strict_constraints=a.strict_constraints, sch=sch)
        except ValueError as exc:
            print(exc)
            return 1
        out = state_to_plan_book(state, a.out, sch)
        res = validate_plan_dict(state_to_plan_dict(state, sch), proto=state.get("proto"),
                                 lib=state.get("lib"), strict_constraints=a.strict_constraints, sch=sch)
        print("已写出 %s（%d 周 / %d 动作行）" % (out, state["structure"]["totalWeeks"], len(plan.get("Workouts") or [])))
        if a.state_out:
            with open(a.state_out, "w", encoding="utf-8") as fh:
                json.dump(state, fh, ensure_ascii=False, indent=1)
            print("state 已写出 %s" % a.state_out)
        return _report(res, "补齐后再校验")

    if a.cmd == "roundtrip":
        try:
            info, out = roundtrip_book(a.path, a.out, strict_constraints=a.strict_constraints, sch=sch)
        except ValueError as exc:
            print(exc)
            return 1
        diff = info["diff"]
        for d in diff["diffs"][:40]:
            print("DIFF    %s" % d)
        print("往返比对：原 %d 格 / 再导出 %d 格 / 差异 %d 格，第二份产物 %s"
              % (diff["cells_a"], diff["cells_b"], len(diff["diffs"]), out))
        return 0 if not diff["diffs"] else 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
