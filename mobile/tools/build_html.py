# -*- coding: utf-8 -*-
"""Inject version + seed.json + 计划交换契约 into template.html -> app/src/main/assets/index.html

单一事实源
----------
- 版本号只认 app/build.gradle 的 versionName / versionCode。模板内写 {{VER}}，由本脚本注入；
  模板里若出现裸版本号即报错拦下（防止换版漏改）。
- 计划契约只认 tools/schema/RPL-Plan-v3.json（v1/v2 冻结留档，见其 legacy_compat 段），注入成
  `const PLAN_SCHEMA`；前端不许再写第二份列序。
- JSON 交换载体只认 tools/schema/RPL-Exchange-v3.json，注入成 `const EXCHANGE_SCHEMA`；
  信封键序、文件名模板、MIME 均以它为唯一出处，模板与 Python 侧不许硬编码第二份。
- 器械词表只认 tools/schema/RPL-Gear-v1.json，注入成 `const GEAR_SCHEMA`；六类 kind、杆重/赛扣/
  挂片位/插片档枚举、步长公式与步进按钮形状都以它为出处（它不是交换契约，不进信封 accepted）。

新鲜度与闸门（只在这一步做，render() 保持纯函数供 gate.py 比对）
--------------------------------------------------------------
- `ensure_fresh_seed()`：权威工作簿比 seed.json 新就重跑 gen_seed.py，别把旧数据打进 APK。
- `check_seed_gates()`：注入前用 plan_xlsx 的契约校验过一遍 seed，不过就不产成品。
- 成品尾部写 `<!-- BUILD_FP ... -->`：模板/种子/两份契约/器械词表五份输入的摘要，改了哪一份一眼可见。

    python build_html.py                 # 需要时自动重跑 gen_seed.py
    python build_html.py --no-refresh    # 只检测陈旧，不改 seed.json
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)                      # .../mobile
ROOT = os.path.dirname(APK)                      # .../Roast PowerLifting
GRADLE = os.path.join(APK, "app", "build.gradle")
TPL = os.path.join(HERE, "template.html")
SEED = os.path.join(HERE, "seed.json")
PLAN_SCHEMA = os.path.join(HERE, "schema", "RPL-Plan-v3.json")
EXCHANGE_SCHEMA = os.path.join(HERE, "schema", "RPL-Exchange-v3.json")
GEAR_SCHEMA = os.path.join(HERE, "schema", "RPL-Gear-v1.json")
GPP_SCHEMA = os.path.join(HERE, "schema", "RPL-GPP-v1.json")
JTS_SCHEMA = os.path.join(HERE, "schema", "RPL-JTS-v1.json")
SHARE_SCHEMA = os.path.join(HERE, "schema", "RPL-Share-v1.json")
OUT = os.path.join(APK, "app", "src", "main", "assets", "index.html")

sys.path.insert(0, HERE)
import pyout  # noqa: E402

VER_TOKEN = "{{VER}}"
SEED_MARKER = "/*__SEED__*/null"
SCHEMA_MARKER = "/*__PLAN_SCHEMA__*/null"
EXCHANGE_MARKER = "/*__EXCHANGE_SCHEMA__*/null"
GEAR_MARKER = "/*__GEAR_SCHEMA__*/null"
GPP_MARKER = "/*__GPP_SCHEMA__*/null"
JTS_MARKER = "/*__JTS_SCHEMA__*/null"
SHARE_MARKER = "/*__SHARE_SCHEMA__*/null"
FP_PREFIX = "<!-- BUILD_FP "


def read_version():
    """从 build.gradle 读版本；versionName 必须是纯版本号（如 0.03）。"""
    with open(GRADLE, encoding="utf-8") as f:
        src = f.read()
    m_name = re.search(r"versionName\s*=\s*'([^']*)'", src)
    m_code = re.search(r"versionCode\s*=\s*(\d+)", src)
    if not m_name or not m_code:
        raise SystemExit("build.gradle 缺 versionName / versionCode")
    ver = m_name.group(1).strip()
    if not re.fullmatch(r"\d+\.\d{1,2}", ver):
        raise SystemExit(
            "versionName 必须是纯版本号（如 0.03），实际为 %r。\n"
            "产品标签（Pro）是显示串，不进 versionName。" % ver)
    return ver, int(m_code.group(1))


GEN_SEED = os.path.join(HERE, "gen_seed.py")


def workbook_name():
    """gen_seed.py 里 `XLSX = os.path.join(ROOT, "data", "<name>")` 的文件名。
    用文本抽取而不是 import：gen_seed 依赖 openpyxl，注入这一步不该需要它。"""
    try:
        with open(GEN_SEED, encoding="utf-8") as f:
            m = re.search(r'^XLSX\s*=\s*os\.path\.join\(ROOT,\s*"data",\s*"([^"]+)"\)',
                          f.read(), re.M)
    except OSError:
        return ""
    return m.group(1) if m else ""


def workbook_path():
    name = workbook_name()
    return os.path.join(ROOT, "data", name) if name else ""


def read_text(path, what):
    try:
        with io.open(path, encoding="utf-8") as f:
            return f.read()
    except OSError as e:
        raise SystemExit("%s 读不到（%s）：%s" % (what, path, e))


def plan_schema_text():
    """契约 JSON → 注入用的紧凑文本；缺关键键直接中止，别让半成品契约进成品。"""
    sch = json.loads(read_text(PLAN_SCHEMA, "契约 JSON"))
    missing = [k for k in ("schema_ver", "sheet_order", "sheets", "conflict_policy", "legacy_compat")
               if k not in sch]
    if missing:
        raise SystemExit("契约 %s 缺键 %s，注入中止" % (PLAN_SCHEMA, ",".join(missing)))
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def exchange_schema_text():
    """交换载体契约 JSON → 注入用的紧凑文本；键不全直接中止（半成品契约比没有更糟）。"""
    sch = json.loads(read_text(EXCHANGE_SCHEMA, "交换契约 JSON"))
    missing = [k for k in ("exchange_ver", "notes", "plan_envelope", "log_jsonl") if k not in sch]
    if missing:
        raise SystemExit("交换契约 %s 缺键 %s，注入中止" % (EXCHANGE_SCHEMA, ",".join(missing)))
    env = sch.get("plan_envelope") or {}
    missing = [k for k in ("format", "schema_version_field", "current", "accepted",
                           "key_order", "app_name", "file_name", "mime") if k not in env]
    if missing:
        raise SystemExit("交换契约 plan_envelope 缺键 %s，注入中止" % ",".join(missing))
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def gear_schema_text():
    """器械词表 JSON → 注入用的紧凑文本。它不是交换契约，但同样「半成品比没有更糟」：
       少任何一节枚举（六类 kind / 场地形状 / 步长公式 / equip 映射），模板里的派生常量
       就会静默退回 undefined，配重引擎按「没有库存」算步长。"""
    sch = json.loads(read_text(GEAR_SCHEMA, "器械词表 JSON"))
    missing = [k for k in ("gear_ver", "kinds", "bar", "collar", "plates", "dumbbell",
                           "loaded", "stack", "bodyweight", "special", "backoff",
                           "step_rule", "step_buttons", "venues", "equipment",
                           "equip_map", "defaults") if k not in sch]
    if missing:
        raise SystemExit("器械词表 %s 缺键 %s，注入中止" % (GEAR_SCHEMA, ",".join(missing)))
    ids = [k.get("id") for k in sch["kinds"]]
    if len(ids) != 6 or len(set(ids)) != 6 or not all(ids):
        raise SystemExit("器械词表 kinds 必须恰好 6 类且 id 唯一，实为 %s" % ids)
    for rule in ("barbell", "plate", "dumbbell", "stack", "bw", "special"):
        if not sch["step_rule"].get(rule):
            raise SystemExit("器械词表 step_rule 缺 %s 的公式" % rule)
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def js_safe(payload):
    """JSON 里的 `</` 会终结所在的 <script> 块，注入前一律转义。"""
    return payload.replace("</", "<\\/")


def gpp_schema_text():
    """GPP 目录词表 JSON → 注入用的紧凑文本。它不是交换契约（不进信封 accepted），但同样
       「半成品比没有更糟」：缺 34 项之一、域枚举不齐、恢复通道上限缺失，前端 GPP 页与
       恢复乘数就会静默退回 undefined。数值单源在此，前端不许写第二份。"""
    sch = json.loads(read_text(GPP_SCHEMA, "GPP 词表 JSON"))
    missing = [k for k in ("gpp_ver", "domain_enum", "metric_type_enum", "target_unit_enum",
                           "items", "weekly_menu", "recovery", "legacy_map") if k not in sch]
    if missing:
        raise SystemExit("GPP 词表 %s 缺键 %s，注入中止" % (GPP_SCHEMA, ",".join(missing)))
    items = sch["items"]
    ids = [it.get("id") for it in items]
    if len(ids) != 34 or len(set(ids)) != 34 or not all(ids):
        raise SystemExit("GPP 词表 items 必须恰好 34 项且 id 唯一，实为 %d 项" % len(ids))
    dom = set(sch["domain_enum"])
    for it in items:
        if it.get("domain") not in dom:
            raise SystemExit("GPP 条目 %s 的 domain %r 不在枚举内" % (it.get("id"), it.get("domain")))
    rec = sch["recovery"]
    if rec.get("b_gpp", {}).get("cap") is None or rec.get("f_gpp", {}).get("cap") is None:
        raise SystemExit("GPP 词表 recovery 缺 b_gpp/f_gpp 上限")
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def jts_schema_text():
    """JTS 六维问卷词表 JSON → 注入用的紧凑文本。问题/权重/评分区间/档位分数线/恢复乘数公式
       单源在此。缺任一节，六维 UI 与恢复乘数就会静默退回 undefined 或按旧五档算。"""
    sch = json.loads(read_text(JTS_SCHEMA, "JTS 词表 JSON"))
    missing = [k for k in ("jts_ver", "scale", "items", "item_order", "flags",
                           "scoring", "readiness", "recMult", "migration") if k not in sch]
    if missing:
        raise SystemExit("JTS 词表 %s 缺键 %s，注入中止" % (JTS_SCHEMA, ",".join(missing)))
    items = sch["items"]
    ids = [it.get("id") for it in items]
    if len(ids) != 6 or len(set(ids)) != 6 or ids != sch["item_order"]:
        raise SystemExit("JTS 词表 items 必须恰好 6 维、id 唯一且与 item_order 同序，实为 %s" % ids)
    sc = sch["scale"]
    if not (sc.get("min") == 1 and sc.get("max") == 7 and sc.get("points") == 7):
        raise SystemExit("JTS 词表 scale 必须是 1–7 七点，实为 %s" % sc)
    if sch["readiness"].get("ready_at") != [90, 75, 60, 45]:
        raise SystemExit("JTS 词表 readiness.ready_at 必须是 [90,75,60,45]（单源，别处不许另写）")
    if "0.75" not in sch["recMult"]["rec_base"]["expr"]:
        raise SystemExit("JTS 词表 recMult.rec_base.expr 缺 0.75 基线")
    at = sch["migration"]["answer_table"]
    if sorted(int(k) for k in at) != list(range(11)):
        raise SystemExit("JTS 词表 migration.answer_table 必须覆盖旧 0–10 全档")
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def share_schema_text(seed):
    """分享图词表 JSON → 注入用紧凑文本。short_labels 键集必须与 seed lib.categories
       的 cat 全集双向相等：新类别没配短标签，注入中止（分享图会静默印 raw 类别码）。"""
    sch = json.loads(read_text(SHARE_SCHEMA, "分享图词表 JSON"))
    missing = [k for k in ("share_ver", "short_labels") if k not in sch]
    if missing:
        raise SystemExit("分享图词表 %s 缺键 %s，注入中止" % (SHARE_SCHEMA, ",".join(missing)))
    lab = sch["short_labels"]
    cats = [c.get("cat") for c in seed.get("lib", {}).get("categories", [])]
    if not cats:
        raise SystemExit("seed lib.categories 为空，无法校验分享图词表键集")
    ck, lk = set(cats), set(lab)
    if len(ck) != len(cats):
        raise SystemExit("seed lib.categories 有重复 cat，无法做键集对账")
    if lk - ck:
        raise SystemExit("分享图词表多出无类别的短标签：%s" % ",".join(sorted(lk - ck)))
    if ck - lk:
        raise SystemExit("分享图词表缺类别短标签：%s" % ",".join(sorted(ck - lk)))
    for k, v in lab.items():
        if not (str(v.get("zh", "")).strip() and str(v.get("en", "")).strip()):
            raise SystemExit("分享图短标签 %s 的 zh/en 必须都非空" % k)
    return js_safe(json.dumps(sch, ensure_ascii=False, separators=(",", ":")))


def fingerprint(tpl_src, seed_src, schema_src, exchange_src, gear_src, gpp_src, jts_src, share_src, ver, code):
    """八份输入的摘要：改动落在哪一份，尾注一眼可见（内容寻址，不含时间戳，可逐字节复现）。"""
    d = lambda s: hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]
    return "%sv=%s.%d tpl=%s seed=%s sch=%s exc=%s gear=%s gpp=%s jts=%s share=%s-->" % (
        FP_PREFIX, ver, code, d(tpl_src), d(seed_src), d(schema_src), d(exchange_src),
        d(gear_src), d(gpp_src), d(jts_src), d(share_src))


def check_template(html, ver):
    """模板侧守卫：标记齐全 + 无硬编码版本号。gate.py 与 main() 共用，别各写一份。"""
    for marker, what in ((SEED_MARKER, "seed"), (SCHEMA_MARKER, "plan schema"),
                         (EXCHANGE_MARKER, "exchange schema"), (GEAR_MARKER, "gear schema"),
                         (GPP_MARKER, "gpp schema"), (JTS_MARKER, "jts schema"),
                         (SHARE_MARKER, "share schema")):
        if marker not in html:
            raise SystemExit("%s marker missing in template (%s)" % (what, marker))
    if VER_TOKEN not in html:
        raise SystemExit("version token %s missing in template" % VER_TOKEN)

    # 硬编码版本号守卫：只认「产品前缀 + 版本」或「两位小数版本」，避免误伤 CSV schema_ver 的 v8.1
    hard = sorted(set(re.findall(r"RPL_ExDark_v\d+\.\d+", html))
                  | set(re.findall(r"v\d+\.\d{2}", html)))
    if hard:
        raise SystemExit("template 内仍有硬编码版本号 %s，请改写为 %s" % (hard, VER_TOKEN))


def render():
    """模板 + 种子 + 两份契约 + 器械词表 + GPP/JTS/分享图词表 + gradle 版本 → 成品文本（不写盘、不改 seed）。
    gate.py 用它做「成品是否由当前源码重生成」的逐字节比对，所以这里必须保持纯函数。"""
    ver, code = read_version()
    tpl_src = read_text(TPL, "模板")
    seed_src = read_text(SEED, "seed.json")
    schema_src = read_text(PLAN_SCHEMA, "契约 JSON")
    exchange_src = read_text(EXCHANGE_SCHEMA, "交换契约 JSON")
    gear_src = read_text(GEAR_SCHEMA, "器械词表 JSON")
    gpp_src = read_text(GPP_SCHEMA, "GPP 词表 JSON")
    jts_src = read_text(JTS_SCHEMA, "JTS 词表 JSON")
    share_src = read_text(SHARE_SCHEMA, "分享图词表 JSON")

    check_template(tpl_src, ver)
    seed = json.loads(seed_src)
    payload, schema_payload = js_safe(json.dumps(seed, ensure_ascii=False, separators=(",", ":"))), plan_schema_text()
    exchange_payload = exchange_schema_text()
    gear_payload = gear_schema_text()
    gpp_payload = gpp_schema_text()
    jts_payload = jts_schema_text()
    share_payload = share_schema_text(seed)

    html = (tpl_src.replace(VER_TOKEN, ver)
            .replace(SEED_MARKER, payload)
            .replace(SCHEMA_MARKER, schema_payload)
            .replace(EXCHANGE_MARKER, exchange_payload)
            .replace(GEAR_MARKER, gear_payload)
            .replace(GPP_MARKER, gpp_payload)
            .replace(JTS_MARKER, jts_payload)
            .replace(SHARE_MARKER, share_payload))

    if VER_TOKEN in html:
        raise SystemExit("unreplaced version token remains")
    for marker in (SEED_MARKER, SCHEMA_MARKER, EXCHANGE_MARKER, GEAR_MARKER, GPP_MARKER,
                   JTS_MARKER, SHARE_MARKER):
        if marker in html:
            raise SystemExit("marker 未被替换：%s" % marker)
    left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
    if left:
        raise SystemExit("成品仍有未替换 token %s" % left)

    html = "%s\n%s\n" % (html.rstrip(),
                         fingerprint(tpl_src, seed_src, schema_src, exchange_src, gear_src,
                                     gpp_src, jts_src, share_src, ver, code))
    if html.count(FP_PREFIX) != 1:
        raise SystemExit("BUILD_FP 尾注应恰好一条")
    return html, ver, code, seed


# ---------- 新鲜度与 seed 闸门（main() 专用） ----------

def stale_reason():
    """seed.json 是否落后于权威工作簿；拿不准一律算陈旧，不放行。"""
    wb = workbook_path()
    if not wb:
        return "gen_seed.py 里解析不到 XLSX 常量，无法判断新鲜度"
    if not os.path.exists(wb):
        return "权威工作簿不存在：%s" % wb
    if not os.path.exists(SEED):
        return "seed.json 不存在"
    if os.path.getmtime(wb) > os.path.getmtime(SEED):
        return "工作簿 %s 比 seed.json 新" % os.path.basename(wb)
    return ""


def ensure_fresh_seed(auto=True):
    why = stale_reason()
    if not why:
        return
    if not auto:
        raise SystemExit("seed.json 陈旧：%s。重跑 `python tools/gen_seed.py`，或去掉 --no-refresh。" % why)
    print("seed.json 陈旧：%s → 重跑 gen_seed.py" % why)
    r = subprocess.run([sys.executable, GEN_SEED], cwd=HERE, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "")
        raise SystemExit("gen_seed.py 退出码 %d，注入中止" % r.returncode)
    why = stale_reason()
    if why:
        raise SystemExit("重跑后仍然陈旧：%s" % why)


def check_seed_gates(seed):
    """注入前过一遍契约的 seed 不变量：键缺、周数与 blocks 不符、动作名为空 —— 现在拦住，
    比让用户在开屏时撞上「undefined is not a function」便宜得多。"""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import plan_xlsx
    except ImportError as e:
        raise SystemExit("契约校验器不可用（%s）：先 `pip install -r tools/requirements.txt`" % e)
    sch = plan_xlsx.load_schema()
    miss = [k for k in plan_xlsx.seed_required_keys(sch) if k not in seed]
    if miss:
        raise SystemExit("seed.json 缺契约要求的顶层键 %s（名单唯一出处：%s 的 seed.required_keys）"
                         % (miss, sch["schema_ver"]))
    res = plan_xlsx.validate_seed_schema(seed, sch)
    if not res["ok"]:
        raise SystemExit("seed.json 不过 %s 契约：\n  %s" % (sch["schema_ver"], "\n  ".join(res["errors"])))
    return len(res["warnings"]), sch["schema_ver"]


def main():
    pyout.use_utf8_stdout()
    ap = argparse.ArgumentParser(description="模板 + seed + 契约 → assets/index.html")
    ap.add_argument("--no-refresh", action="store_true", help="seed 陈旧时报错而不是自动重跑 gen_seed.py")
    args = ap.parse_args()

    ensure_fresh_seed(auto=not args.no_refresh)
    html, ver, code, seed = render()

    src = str(seed.get("source") or "")
    # 比对基准是「种子当前读的那份工作簿」，不是 app 版本：工作簿改名是破坏性操作，
    # 版本却在一路往上走 —— 旧判定每轮都报 WARN，等于训练大家忽略警告。
    want = workbook_name()
    if src and want and src != want:
        raise SystemExit(
            "seed.json source=%r 与 gen_seed.py 的工作簿 %r 不同步，先重跑 gen_seed.py" % (src, want))
    n_warn, sch_ver = check_seed_gates(seed)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(html)

    # 写后断言：磁盘上那份必须与刚算出来的逐字节相同，且三个注入点都在位。
    on_disk = read_text(OUT, "成品")
    if on_disk != html:
        raise SystemExit("成品写后校验失败：磁盘与重生成文本不一致（%d vs %d 字符）"
                         % (len(on_disk), len(html)))
    for probe in (SEED_MARKER, SCHEMA_MARKER, EXCHANGE_MARKER, GEAR_MARKER, GPP_MARKER, JTS_MARKER):
        if probe in on_disk:
            raise SystemExit("成品里仍留着占位符 %s" % probe)
    if FP_PREFIX not in on_disk:
        raise SystemExit("成品缺 BUILD_FP 尾注")

    print("built %s" % OUT)
    print("  version: v%s (versionCode %d)" % (ver, code))
    print("  size: %.1f KB" % (os.path.getsize(OUT) / 1024.0))
    n_ex = sum(len(d["exercises"]) for w in seed["weeks"].values()
               for d in w.values() if isinstance(d, dict) and "exercises" in d)
    print("  seed: %s | weeks %d | exercises %d | proto %d | 契约 schema_ver=%s" % (
        src, len(seed["weeks"]), n_ex, len(seed["proto"]), sch_ver))
    print("  seed 闸门：%d warning | %s" % (n_warn, on_disk.strip().rsplit("\n", 1)[-1].strip()))


if __name__ == "__main__":
    main()
