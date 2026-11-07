# -*- coding: utf-8 -*-
"""构建链守卫 —— 一条命令回答「这条链现在可信吗」。

    python tools/gate.py            # 静态 + 动态（出包前跑一次）
    python tools/gate.py --static   # 只静态（秒级，日常改完就跑）
    python tools/gate.py --dynamic  # 只动态（全量回归）
    python tools/gate.py --verbose  # 逐条打印 PASS（默认只打 FAIL）

默认把输出压到「FAIL 明细 + 汇总」，PASS 不刷屏；断言条数与判定逻辑不受影响。

为什么要有它：v0.06 之前的回归脚本无条件 exit(0)，「全绿」不代表什么都没坏。
静态部分守的是**红线**（改了就会坏、但没人拦的那些），动态部分就是 `DYNAMIC` 名单里那几套回归本身（名单即唯一出处）。
每条检查都必须能失败 —— 取不到被检对象一律算 FAIL，不放行。
"""
import argparse
import ast
import hashlib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)                       # .../mobile
ROOT = os.path.dirname(APK)                       # .../Roast PowerLifting
sys.path.insert(0, HERE)

import build_html  # noqa: E402
import pyout  # noqa: E402

GRADLE = os.path.join(APK, "app", "build.gradle")
MANIFEST = os.path.join(APK, "app", "src", "main", "AndroidManifest.xml")
JAVA = os.path.join(APK, "app", "src", "main", "java", "com", "roast", "exdark", "MainActivity.java")
RXLIB = os.path.join(HERE, "rxlib.py")
GEN_SEED = os.path.join(HERE, "gen_seed.py")
ASSET = build_html.OUT

EXPECTED_APP_ID = "com.roast.exdark"
CSV_N = 26

results = []


def seed_contract():
    """契约里的种子顶层键名单（v0.18 起的唯一出处）。取不到一律由调用方判 FAIL：
    「名单读不到」和「种子缺键」是两件事，但都不许放行。"""
    with io.open(build_html.PLAN_SCHEMA, encoding="utf-8") as f:
        block = json.load(f)["seed"]
    for field in ("required_keys", "invariant_keys"):
        if not isinstance(block.get(field), list) or not block[field]:
            raise ValueError("契约 seed.%s 缺失或为空（种子顶层键名单的唯一出处）" % field)
    return block


def _roster_literals(src, roster):
    """源码里「同时点名 ≥2 个种子键」的列表 / 元组字面量 —— 那就是第二份名单。"""
    hits = []
    for n in ast.walk(ast.parse(src)):
        if isinstance(n, (ast.List, ast.Tuple)):
            got = [e.value for e in n.elts
                   if isinstance(e, ast.Constant) and e.value in roster]
            if len(got) >= 2:
                hits.append((getattr(n, "lineno", 0), got))
    return hits


VERBOSE = False


def chk(cid, name, ok, detail=""):
    results.append((ok, cid, name, detail))
    if ok and not VERBOSE:                 # 默认只打 FAIL；--verbose 才逐条打 PASS
        return ok
    print("%s  %s %s%s" % ("PASS" if ok else "FAIL", cid, name,
                           ("  [" + str(detail).replace("\n", " ")[:220] + "]") if detail else ""))
    return ok


def read(path):
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def fingerprint_delta(a, b):
    """两份成品的 BUILD_FP 差异：只列出对不上的那几个 token。"""
    def toks(s):
        m = re.search(r"BUILD_FP ([^>]*)-->", s)
        return dict(t.split("=", 1) for t in m.group(1).split() if "=" in t) if m else {}
    ta, tb = toks(a), toks(b)
    d = ["%s %s≠%s" % (k, ta.get(k, "无"), tb.get(k, "无"))
         for k in sorted(set(ta) | set(tb)) if ta.get(k) != tb.get(k)]
    return "尾注 " + " / ".join(d) if d else "尾注一致"


def diff_summary(on_disk, rendered):
    """成品与重生成的定位信息。旧文案只报「差 N 字符」，长度相等时等于没报。"""
    n = min(len(on_disk), len(rendered))
    i = next((k for k in range(n) if on_disk[k] != rendered[k]), n)
    where = "第 %d 字符起不同" % i
    snip = lambda s: s[i:i + 14].replace("\n", "\\n") if i < len(s) else "<到结尾>"
    return "%s｜%s｜此处「%s」≠「%s」" % (
        fingerprint_delta(on_disk, rendered), where, snip(on_disk), snip(rendered))


# ---------- 静态 ----------

def style_span(src, what):
    """取 <style> 段与它的起始偏移（S33 的色板跨度、S34 的规则体都要用同一份取法）。"""
    i, j = src.find("<style>"), src.find("</style>")
    if i < 0 or j < i:
        raise ValueError("%s 里取不到 <style> 段" % what)
    return i, src[i:j]


def strip_css_comments(s):
    """去注释但保留长度无关的匹配位置：用等长空格替换，跨度索引才不会错位。"""
    out = []
    k = 0
    while True:
        a = s.find("/*", k)
        if a < 0:
            out.append(s[k:])
            break
        b = s.find("*/", a + 2)
        if b < 0:
            out.append(s[k:])
            break
        out.append(s[k:a])
        out.append(" " * (b + 2 - a))
        k = b + 2
    return "".join(out)


def css_rule(css, sel):
    """取某条 CSS 规则的声明体（按花括号配对）。取不到返回 None，让调用方判红。"""
    i = css.find(sel + "{")
    if i < 0:
        return None
    depth, k = 0, i + len(sel)
    while k < len(css):
        if css[k] == "{":
            depth += 1
        elif css[k] == "}":
            depth -= 1
            if depth == 0:
                return css[i + len(sel) + 1:k]
        k += 1
    return None


def js_fn_body(src, name):
    """按函数名取函数体（花括号配对）。取不到返回 None。"""
    i = src.find("function %s(" % name)
    if i < 0:
        return None
    j = src.find("{", i)
    if j < 0:
        return None
    depth, k = 0, j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                return src[j + 1:k]
        k += 1
    return None

def static_checks():
    # S1 包名：改了旧存档与侧载升级全部失联
    try:
        g = read(GRADLE)
        ids = re.findall(r"(?:namespace|applicationId)\s*=?\s*'([^']+)'", g)
        chk("S1", "gradle namespace/applicationId 未被改",
            len(ids) >= 2 and set(ids) == {EXPECTED_APP_ID}, ",".join(ids))
    except OSError as e:
        chk("S1", "gradle namespace/applicationId 未被改", False, e)

    # S2 权限：纯本地无联网是产品承诺，也是 About 面板里写给用户的话
    try:
        m = read(MANIFEST)
        bad = [p for p in ("android.permission.INTERNET", "android.permission.ACCESS_NETWORK_STATE")
               if p in m]
        chk("S2", "Manifest 无网络权限且禁明文流量",
            not bad and 'usesCleartextTraffic="false"' in m and 'allowBackup="false"' in m,
            ("多出权限: " + ",".join(bad)) if bad else "INTERNET 缺席=预期")
    except OSError as e:
        chk("S2", "Manifest 无网络权限且禁明文流量", False, e)

    # S3 版本单源：versionName 必须纯版本号
    try:
        ver, code = build_html.read_version()
        chk("S3", "versionName 为纯版本号 / versionCode 存在",
            bool(re.fullmatch(r"\d+\.\d{1,2}", ver)) and code > 0, "v%s / code %d" % (ver, code))
    except SystemExit as e:
        chk("S3", "versionName 为纯版本号 / versionCode 存在", False, e)

    # S4 模板侧守卫（标记齐全 + 无硬编码版本号）
    try:
        tpl = read(build_html.TPL)
        build_html.check_template(tpl, "")
        chk("S4", "模板含 {{VER}} 与 seed marker、无硬编码版本号", True)
    except SystemExit as e:
        chk("S4", "模板含 {{VER}} 与 seed marker、无硬编码版本号", False, e)

    # S5 成品保真：手改 assets/index.html 会被下一次注入无声覆盖 —— 这里当场拦
    try:
        rendered, _ver, _code, seed = build_html.render()
        on_disk = read(ASSET)
        chk("S5", "成品 == 模板+种子重生成（未被手改）",
            on_disk == rendered,
            "字节一致" if on_disk == rendered
            else "%s → 改模板后跑 build_html.py，别改成品" % diff_summary(on_disk, rendered))
    except SystemExit as e:
        chk("S5", "成品 == 模板+种子重生成（未被手改）", False, e)

    # S6 成品自身：无残留 token、关键常量在位
    try:
        asset = read(ASSET)
        left = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", asset)))
        need = ["SCHEMA_STAMP", "READONLY", "CSV_COLS", "AndroidBridge", "PLAN_SCHEMA",
                "EXCHANGE_SCHEMA", "BUILD_FP"]
        miss = [n for n in need if n not in asset]
        chk("S6", "成品无残留 token 且关键常量在位", not left and not miss,
            ("残留: " + ",".join(left)) if left else (("缺: " + ",".join(miss)) if miss else "OK"))
    except OSError as e:
        chk("S6", "成品无残留 token 且关键常量在位", False, e)

    # S7 CSV 26 列协议冻结：契约（权威）/ 模板（源）/ 成品（真正发货的那份）三处逐列全等。
    #     v0.13 起 desktop 归档，原来对账的另一端（server.py 的 CSV_HEADER）换成契约里的
    #     record_keys_frozen。端点少了一个，锁反而更硬：改名要同时动 JSON、模板，且成品必须重build。
    try:
        exc = json.loads(read(build_html.EXCHANGE_SCHEMA))
        frozen = exc.get("log_jsonl", {}).get("record_keys_frozen") or []
        pat = r"const CSV_COLS='([^']+)'"

        def cols_of(src):
            m = re.search(pat, src)
            return m.group(1).split(",") if m else []

        tpl_cols = cols_of(read(build_html.TPL))
        asset_cols = cols_of(read(ASSET))
        ref = frozen or ["(契约缺 record_keys_frozen)"]

        def first_diff(other):
            for i in range(max(len(ref), len(other))):
                x = ref[i] if i < len(ref) else None
                y = other[i] if i < len(other) else None
                if x != y:
                    return "#%d 契约 %r ≠ 本处 %r" % (i + 1, x, y)
            return None

        bad = []
        if len(frozen) != CSV_N:
            bad.append("契约清单 %d 列（应 %d）" % (len(frozen), CSV_N))
        if len(tpl_cols) != CSV_N:
            bad.append("模板 %d 列（应 %d）" % (len(tpl_cols), CSV_N))
        if len(asset_cols) != CSV_N:
            bad.append("成品 %d 列（应 %d）" % (len(asset_cols), CSV_N))
        if not bad:
            for tag, other in (("模板", tpl_cols), ("成品", asset_cols)):
                d = first_diff(other)
                if d:
                    bad.append("%s 与契约分叉：%s" % (tag, d))
        chk("S7", "CSV 列协议冻结：%d 列三处一致（契约 / 模板 / 成品）" % CSV_N, not bad,
            " | ".join(bad) or "契约==模板==成品，%d 列逐列对齐" % CSV_N)
    except (OSError, ValueError) as e:
        chk("S7", "CSV 列协议冻结：%d 列三处一致（契约 / 模板 / 成品）" % CSV_N, False, e)

    # S8 权威工作簿名同源（红线 9：改名属于破坏性操作，历史上真的各自为政过）
    #     v0.13 起 desktop 归档，第三端从 server.py 的 DEFAULT_XLSX 换成成品里注入的 seed.source
    #     —— 这一端更贴近发货物：数据源名字在 APK 里写错，用户看到的「来源」就跟着错。
    try:
        names = {
            "gen_seed.py": (re.search(r'^XLSX\s*=\s*os\.path\.join\(ROOT,\s*"data",\s*"([^"]+)"\)',
                                      read(GEN_SEED), re.M) or [None, "?"])[1],
            "rxlib.py": (re.search(r'"[^"]*data/([^"]+\.xlsx)"', read(RXLIB)) or [None, "?"])[1],
            "成品 seed.source": (re.search(r'"source":\s*"([^"]+\.xlsx)"', read(ASSET)) or [None, "?"])[1],
        }
        uniq = set(names.values())
        exists = os.path.exists(os.path.join(ROOT, "data", list(uniq)[0])) if len(uniq) == 1 else False
        chk("S8", "工作簿名三处同源且文件存在", len(uniq) == 1 and uniq != {"?"} and exists,
            json.dumps(names, ensure_ascii=False))
    except OSError as e:
        chk("S8", "工作簿名三处同源且文件存在", False, e)

    # S9 种子形状：键名被模板/CSV/e1RM 追踪按名引用，少一个就是开机炸。
    #     名单不写在这里（v0.18 起在契约的 seed.required_keys，见 S24）。
    try:
        with io.open(build_html.SEED, encoding="utf-8") as f:
            seed = json.load(f)
        req = seed_contract()["required_keys"]
        miss = [k for k in req if k not in seed]
        weeks = len(seed.get("weeks") or {})
        n_ex = sum(len(d["exercises"]) for w in (seed.get("weeks") or {}).values()
                   for d in w.values() if isinstance(d, dict) and "exercises" in d)
        chk("S9", "seed.json 键齐全 / 周数与动作行数非空",
            not miss and weeks > 0 and n_ex > 0,
            ("缺 " + ",".join(miss)) if miss else "weeks=%d exercises=%d" % (weeks, n_ex))
    except (OSError, ValueError) as e:
        chk("S9", "seed.json 键齐全 / 周数与动作行数非空", False, e)

    # S10 迁移链入口：SCHEMA_STAMP 必须高于历史所有被接受的 sv，否则闸门形同虚设
    try:
        asset = read(ASSET)
        m = re.search(r"const SCHEMA_STAMP=(\d+);", asset)
        acc = re.search(r"\(sv===SCHEMA_STAMP((?:\|\|sv===\d+)+)\)", asset)
        stamps = sorted(int(x) for x in re.findall(r"sv===(\d+)", acc.group(1))) if acc else []
        chk("S10", "迁移闸门：SCHEMA_STAMP 高于所有可接受的旧 sv",
            bool(m) and bool(stamps) and int(m.group(1)) > max(stamps),
            "STAMP=%s 接受=%s" % (m.group(1) if m else "?", stamps))
    except OSError as e:
        chk("S10", "迁移闸门：SCHEMA_STAMP 高于所有可接受的旧 sv", False, e)

    # S11 结构写入唯一入口（C2）：派生字段只允许 applyStructure 一处赋值，
    #     否则导入 / 迁移 / 设置页各写一份，用户改的周数会被下一次重算无声盖掉。
    try:
        tpl = read(build_html.TPL)
        asset = read(ASSET)
        n_tpl = len(re.findall(r"state\.structure\s*=(?!=)", tpl))
        n_asset = len(re.findall(r"state\.structure\s*=(?!=)", asset))
        inside = bool(re.search(r"function applyStructure\(raw\)\{.*?state\.structure=st;", tpl, re.S))
        stale = len(re.findall(r"version:2\b", tpl)) + len(re.findall(r"version:2\b", asset))
        chk("S11", "结构只在 applyStructure 一处写入 / 无过期 version:2 字面量",
            n_tpl == 1 and n_asset == 1 and inside and stale == 0,
            "模板 %d 处 / 成品 %d 处 / 在 applyStructure 内=%s / version:2 残留 %d"
            % (n_tpl, n_asset, inside, stale))
    except OSError as e:
        chk("S11", "结构只在 applyStructure 一处写入 / 无过期 version:2 字面量", False, e)

    # S12 四分片两端同源（C3）：JS 的 kind→桥方法映射逐个能在 Java 侧找到 @JavascriptInterface，
    #     归档只走 writeSlice，且不许混进账本键 —— 桥方法名对不上时 JS 会静默回落到
    #     localStorage，用户以为存住了、其实换了 WebView 数据目录就没了。
    #     模板和成品都扫：只查模板的话，成品被手改的那一份照样能装上手机。
    try:
        java = read(JAVA)
        declared = set(re.findall(r"@JavascriptInterface\s+public\s+\w+\s+(\w+)\s*\(", java))

        def shard_scan(tag, src):
            bad = []
            for mname in ("BRIDGE_LOAD", "BRIDGE_SAVE"):
                mm = re.search(mname + r"=\{([^}]*)\}", src)
                vals = re.findall(r":\s*'([^']+)'", mm.group(1)) if mm else []
                if len(vals) != 4:
                    bad.append("%s 只有 %d 个方法" % (mname, len(vals)))
                miss = [n for n in vals if n not in declared]
                if miss:
                    bad.append("%s 在 Java 侧无声明: %s" % (mname, ",".join(miss)))
            wk = re.search(r"const WORK_KEYS=\[([^\]]*)\]", src)
            keys = re.findall(r"'([^']+)'", wk.group(1)) if wk else []
            if "planArchive" in keys:
                bad.append("归档被塞进 WORK_KEYS（等于当训练数据导出/清空）")
            if len(re.findall(r"writeSlice\('archive'", src)) != 1:
                bad.append("writeSlice('archive') 不是恰好一处")
            bypass = len(re.findall(r"setItem\(LS_ARCHIVE", src))
            if bypass:
                bad.append("绕过 writeSlice 直写 localStorage %d 处" % bypass)
            return tag + ": " + ("OK" if not bad else " / ".join(bad))

        reports = [shard_scan("模板", read(build_html.TPL)), shard_scan("成品", read(ASSET))]
        ok = all(r.endswith("OK") for r in reports) and "roast_plan_archive.json" in java
        chk("S12", "四分片桥方法两端同源 / 归档只走 writeSlice 且不进 WORK_KEYS",
            ok, ("文件名 roast_plan_archive.json 在 Java=%s | " % ("是" if "roast_plan_archive.json" in java else "否"))
                + " | ".join(reports))
    except OSError as e:
        chk("S12", "四分片桥方法两端同源 / 归档只走 writeSlice 且不进 WORK_KEYS", False, e)

    # S13 无头回归回收 Chrome profile：每套脚本每次跑都新建一份一次性 --user-data-dir，
    #     旧写法是「spawn 参数里现拼一个 Date.now() 匿名路径 + 删失败就算了」——
    #     Chrome 没退出前 Windows 锁着目录，于是没人持有句柄、也没人删得掉，
    #     %TEMP% 里积下 200+ 份约 2.6 GB（xlsxv 那份连 fixture 一起 15~20 MB）。
    #     现在五套都走 tools/tmpclean.js：profile 路径必须是持有变量的模块级量，
    #     且每条 process.exit 之前都要 await 回收，否则崩掉的那条路照样漏。
    leaks = []
    headless = ("v3v.js", "v2v.js", "check_hud.js", "xlsxv.js", "logicv.js", "uiv.js", "gearv.js")
    for fn in headless:
        try:
            src = read(os.path.join(HERE, fn))
        except OSError as e:
            leaks.append("%s 读不到(%s)" % (fn, e.strerror or type(e).__name__))
            continue
        if "require('./tmpclean')" not in src:
            leaks.append(fn + " 未引用 tmpclean")
        udd = re.findall(r"--user-data-dir[^\n]*", src)
        if len(udd) != 1:
            leaks.append("%s 的 user-data-dir 有 %d 处" % (fn, len(udd)))
        elif "Date.now()" in udd[0]:
            leaks.append(fn + " 的 profile 是匿名一次性拼接（没人持有路径）")
        n_exit = len(re.findall(r"process\.exit\(", src))
        n_close = len(re.findall(r"tmpclean\.close\(", src))
        if n_close < n_exit:
            leaks.append("%s 退出 %d 处 / 回收 %d 处" % (fn, n_exit, n_close))
    chk("S13", "%d 套无头回归经 tmpclean 回收 Chrome profile" % len(headless), not leaks,
        "; ".join(leaks) if leaks else "/".join(f.split(".")[0] for f in headless) + " 每条退出路径都回收")

    # S14 C5 接线成对（计划工作簿 UI）：设置页两钮、归档面板、隐藏文件输入、契约错误框
    #     必须与处理函数**成对**出现 —— 单向漂移（onclick 指向被改名的函数、面板从
    #     closeAllSheets 掉队）都是浏览器里点了没反应的静默故障，无头对账链路
    #     （xlsxv 直接调 importPlanFromXlsxBytes）看不见，只有静态点名能拦。模板与成品都扫。
    try:
        tpl = read(build_html.TPL)
        asset = read(ASSET)

        def wiring_scan(tag, src):
            bad = []
            for nid in ("setPlanT", "planExpBtn", "planImpBtn", "planXlsxFile",
                        "setArchT", "archSheet", "archRows", "planErrBox",
                        "setJsonT", "jsonExpBtn", "jsonImpBtn", "planJsonFile",
                        "setLogT", "logExpBtn"):
                if 'id="%s"' % nid not in src:
                    bad.append("缺节点 #" + nid)
            for fn in ("doExportPlanXlsx", "onPlanXlsxFile", "openArchiveSheet",
                       "renderArchiveSheet", "restoreArchiveItem", "dropArchiveItem",
                       "clearArchiveSheet", "adoptImportedPlan",
                       "doExportPlanJSON", "onPlanJSONFile", "importPlanFromJSONText",
                       "validateEnvelope", "doExportLogJSONL", "logJsonlText"):
                if not re.search(r"function\s+%s\s*\(" % fn, src):
                    bad.append(fn + " 未定义")
            if not re.search(r"closeAllSheets[\s\S]{0,400}'archSheet'", src):
                bad.append("archSheet 未进 closeAllSheets（返回键会卡在归档面板）")
            if 'accept=".xlsx' not in src:
                bad.append("planXlsxFile 的 accept 不含 .xlsx")
            if 'accept=".json' not in src:
                bad.append("planJsonFile 的 accept 不含 .json（JSON 计划导入选不出文件）")
            return tag + ": " + ("OK" if not bad else " / ".join(bad))

        reports = [wiring_scan("模板", tpl), wiring_scan("成品", asset)]
        chk("S14", "计划工作簿 / JSON 信封 / JSONL 日志 UI 接线成对（节点 / 处理函数 / 面板收口）",
            all(r.endswith("OK") for r in reports), " | ".join(reports))
    except OSError as e:
        chk("S14", "计划工作簿 / JSON 信封 / JSONL 日志 UI 接线成对（节点 / 处理函数 / 面板收口）", False, e)

    # S15 桥方法直呼点名（补 S12 的盲区）：S12 只查四分片映射 BRIDGE_LOAD/BRIDGE_SAVE，
    #     成品里还有七个直接 AndroidBridge.xxx() 的调用点（两路导出、错误回读、
    #     insets、chrome）。Java 侧改名或漏 @JavascriptInterface 时，JS 的 typeof 守卫会
    #     静默走浏览器兜底路径，手机上表现为「导出没反应」，前端回归同样看不见。
    try:
        java = read(JAVA)
        declared = set(re.findall(r"@JavascriptInterface\s+public\s+\w+\s+(\w+)\s*\(", java))
        asset = read(ASSET)
        called = set(re.findall(r"AndroidBridge\.([A-Za-z_]\w*)", asset))
        miss = sorted(c for c in called if c not in declared)
        chk("S15", "直呼 AndroidBridge 的方法在 Java 侧都有声明",
            bool(called) and not miss,
            "直呼 %d 个: %s%s" % (len(called), ",".join(sorted(called)),
                                  (" / 未声明: " + ",".join(miss)) if miss else ""))
    except OSError as e:
        chk("S15", "直呼 AndroidBridge 的方法在 Java 侧都有声明", False, e)

    # S16 导入选择器的 MIME 过滤必须跟着 <input accept> 走（v0.09 真机验收抓出的缺陷）：
    #     onShowFileChooser 曾写死 text/* + 三份 CSV 类型，DocumentsUI 于是把 .xlsx 整行灰掉，
    #     计划工作簿导入在手机上永远选不出文件。这条系统级过滤前端与无头回归都碰不到，
    #     只有静态点名能拦 —— 浏览器里表现为「点了导入，选择器里没有 xlsx」。
    try:
        java = read(JAVA)
        body = re.search(r"public boolean onShowFileChooser[\s\S]*?\n            \}", java)
        helper = re.search(r"private static String\[\] chooserMimes\([\s\S]*?\n    \}", java)
        bad = []
        if not body:
            bad.append("找不到 onShowFileChooser")
        elif 'setType("text/*")' in body.group(0):
            bad.append("选择器仍写死 text/*")
        if not helper:
            bad.append("找不到 chooserMimes")
        else:
            if "getAcceptTypes" not in helper.group(0):
                bad.append("未从 accept 推导 MIME")
            # 只看这个函数体：导出侧本来就带同一个 xlsx MIME 字面量，全文件搜会永远为真
            if "spreadsheetml" not in helper.group(0):
                bad.append("缺 xlsx 的 MIME 映射")
            # v0.12 起 JSON 计划导入也走系统选择器：.json 不映射就会和当年 .xlsx 一样被灰掉
            if '".json"' not in helper.group(0) or "application/json" not in helper.group(0):
                bad.append("缺 .json 的 MIME 映射（JSON 计划导入会在选择器里灰掉）")
        chk("S16", "文件选择器按 accept 过滤（.xlsx/.json 在系统选择器里可选）",
            not bad, "OK" if not bad else " / ".join(bad))
    except OSError as e:
        chk("S16", "文件选择器按 accept 过滤（.xlsx/.json 在系统选择器里可选）", False, e)

    # S17 JSON 交换载体（v0.11 起唯一权威）：契约文件键齐全、注入成对、指纹可复算。
    #     信封键序/文件名/MIME 只有 build_html.EXCHANGE_SCHEMA 所指的契约文件一份（现为 RPL-Exchange-v2.json）；
    #     模板若绕过 EXCHANGE_SCHEMA
    #     硬编码第二份（比如直接写死 'RPL-Plan' 字面量当格式判定），或注入链漏掉 exc= 摘要，
    #     交换契约就悄悄分叉了 —— 导出文件 AI 侧解析失败时根本无从对账。三条各自能红：
    #     a) 契约文件缺键；b) 模板缺 marker / 成品残留 marker / 成品没注入成对象；
    #     c) 成品 BUILD_FP 的 exc= 与当前契约文件摘要不符（契约改了没重建）。
    try:
        exc_src = read(build_html.EXCHANGE_SCHEMA)
        exc = json.loads(exc_src)
        bad = []
        for k in ("exchange_ver", "notes", "plan_envelope", "log_jsonl"):
            if k not in exc:
                bad.append("契约缺键 " + k)
        env = exc.get("plan_envelope") or {}
        for k in ("format", "schema_version_field", "current", "accepted", "key_order",
                  "app_name", "file_name", "mime"):
            if k not in env:
                bad.append("plan_envelope 缺键 " + k)
        # v0.12 起前端 doExportLogJSONL / logMetaRecord 直读 log_jsonl 的这些键，缺一个就运行时抛错
        log = exc.get("log_jsonl") or {}
        for k in ("current", "header_record", "file_name", "mime", "import_policy",
                  "record_keys_frozen"):
            if k not in log:
                bad.append("log_jsonl 缺键 " + k)
        if len(log.get("record_keys_frozen") or []) != CSV_N:
            bad.append("log_jsonl.record_keys_frozen 不是 %d 列" % CSV_N)
        hdr = log.get("header_record") or {}
        for k in ("type_key", "type_value", "required_keys", "schema_ver_value_field",
                  "csv_protocol_accepted"):
            if k not in hdr:
                bad.append("log_jsonl.header_record 缺键 " + k)
        tpl = read(build_html.TPL)
        if build_html.EXCHANGE_MARKER not in tpl:
            bad.append("模板缺 EXCHANGE marker")
        prod = read(ASSET)
        if build_html.EXCHANGE_MARKER in prod:
            bad.append("成品残留 EXCHANGE marker（注入未替换）")
        if "const EXCHANGE_SCHEMA = {" not in prod:
            bad.append("成品未见注入后的 EXCHANGE_SCHEMA 对象")
        m = re.search(r"BUILD_FP [^>]*exc=([0-9a-f]{8})", prod)
        want = hashlib.sha256(exc_src.encode("utf-8")).hexdigest()[:8]
        if not m:
            bad.append("成品 BUILD_FP 缺 exc= 摘要")
        elif m.group(1) != want:
            bad.append("exc=%s 与当前契约文件摘要 %s 不符（改了契约没重建）" % (m.group(1), want))
        chk("S17", "JSON 交换载体契约单源且注入/指纹成对", not bad, "OK" if not bad else " / ".join(bad))
    except (OSError, ValueError) as e:
        chk("S17", "JSON 交换载体契约单源且注入/指纹成对", False, e)

    # S18 归档边界（v0.13 起 PC 端项目整体移入 archive/）：活动脚本不许再按路径引用它。
    #     archive/ 整体不入仓。一旦 tools/ 里的脚本还写着那个路径，就会出现
    #     「只在这台电脑上绿」的检查 —— 别人 clone 下来取不到被检对象，而本机留着旧副本照样 PASS。
    #     判据只看**字符串字面量**（注释与文档提名字不违规，字面量才真会被执行）；
    #     _sabotage_* 是反向验证夹具，故障文本本身就得含被注入的路径，按文件名排除。
    #     被检词分段拼出来，免得本检查的自己的正则字面量命中自己。
    try:
        token = "desk" + "top"
        scanned = [f for f in sorted(os.listdir(HERE))
                   if f.endswith((".py", ".js")) and not f.startswith("_sabotage_")]
        hits = []
        for fn in scanned:
            src = read(os.path.join(HERE, fn))
            for pair in re.findall(r"'([^'\n]{1,140})'|\"([^\"\n]{1,140})\"", src):
                for piece in pair:
                    if token in piece.lower():
                        hits.append("%s: %s" % (fn, piece.strip()[:60]))
                        break
        chk("S18", "活动脚本没有指向已归档项目的路径字面量（归档边界干净）", not hits,
            ("OK（扫 %d 个 tools 脚本）" % len(scanned)) if not hits else " / ".join(hits[:6]))
    except OSError as e:
        chk("S18", "活动脚本没有指向已归档项目的路径字面量（归档边界干净）", False, e)

    # S19 主题注册表单源（v0.14 起多主题）：名单只在头部那份注册表里写一次，
    #     每个主题一份令牌块、一个设置面板按钮，规则一律走 html[data-mode=] 门控。
    #     为什么盯这个：原先「当前是不是亮色」的判断散在 CSS 选择器和三处 JS 里，
    #     加第三个主题时漏掉任何一处都只会**静默**表现为「纸底上出现暗色文字」，
    #     没有任何一套回归会因为一个主题没被 paint 而变红。
    #     判据全部取不到就 FAIL：注册表缺失 / 令牌块缺失 / 按钮缺失都不算通过。
    try:
        tpl = read(build_html.TPL)

        def _ids(src, name):
            m = re.search(r"window\." + name + r"\s*=\s*\[([^\]]*)\]", src)
            return None if not m else re.findall(r"'([A-Za-z0-9_-]+)'", m.group(1))

        def _map(src, name):
            m = re.search(r"window\." + name + r"\s*=\s*\{([^}]*)\}", src)
            if not m:
                return None
            return dict(re.findall(r"'?([A-Za-z0-9_-]+)'?\s*:\s*'([^']*)'", m.group(1)))

        def _block(src, sel):
            i = src.find(sel + "{")
            if i < 0:
                return None
            j = src.find("\n}", i)
            return None if j < 0 else src[i + len(sel) + 1:j]

        def _keys(body):
            return re.findall(r"(--[a-z0-9-]+)\s*:", body)

        ids = _ids(tpl, "THEME_IDS")
        mode, bg, glyph = (_map(tpl, n) for n in ("THEME_MODE", "THEME_BG", "THEME_GLYPH"))
        bad = []
        if not ids:
            bad.append("模板缺 window.THEME_IDS 注册表")
        if ids and not (mode and bg and glyph):
            bad.append("THEME_MODE / THEME_BG / THEME_GLYPH 有缺失")
        if ids and len(ids) != len(set(ids)):
            bad.append("THEME_IDS 里有重名")
        for name, tbl in (("THEME_MODE", mode), ("THEME_BG", bg), ("THEME_GLYPH", glyph)):
            if tbl is not None and set(tbl) != set(ids or []):
                bad.append("%s 的键与 THEME_IDS 不一致（多/少：%s）"
                           % (name, "、".join(sorted(set(tbl) ^ set(ids or []))) or "无"))
        if mode:
            odd = sorted(v for v in mode.values() if v not in ("dark", "light"))
            if odd:
                bad.append("THEME_MODE 只能是 dark|light，出现 %s" % odd)
        # 每个主题都得有令牌块（暗色 = :root 默认值本身，不另开块）
        root_body = _block(tpl, ":root")
        root_keys = set(_keys(root_body or ""))
        ref_keys, ref_name = None, ""
        for tid in (ids or []):
            if tid == "dark":
                if root_body is None:
                    bad.append("缺 :root 默认令牌块")
                continue
            sel = 'html[data-theme="%s"]' % tid
            body = _block(tpl, sel)
            if body is None:
                bad.append("主题 %s 没有 %s 令牌块" % (tid, sel))
                continue
            ks = _keys(body)
            if len(ks) != len(set(ks)):
                bad.append("主题 %s 令牌块里有重复键" % tid)
            extra = sorted(set(ks) - root_keys)
            if extra:
                bad.append("主题 %s 定义了 :root 没有的令牌 %s" % (tid, extra))
            if ref_keys is None:
                ref_keys, ref_name = set(ks), tid
            elif set(ks) != ref_keys:
                bad.append("主题 %s 与 %s 的令牌键集不一致（差集 %s）"
                           % (tid, ref_name, sorted(ref_keys ^ set(ks))))
        # 规则门控：[data-theme=] 在 CSS 里只准当令牌块头，别的选择器一律走 [data-mode=]
        style = tpl[tpl.find("<style>"):tpl.find("</style>")] if "<style>" in tpl else ""
        heads = re.findall(r'\[data-theme="([A-Za-z0-9_-]+)"\]', style)
        want_heads = [t for t in (ids or []) if t != "dark"]
        if sorted(heads) != sorted(want_heads):
            bad.append("CSS 主题块清单与注册表不一致：块 %s vs 名单 %s" % (heads, want_heads))
        for m in re.finditer(r'html\[data-theme="([A-Za-z0-9_-]+)"\]([^\n{}]*?)\{', style):
            if m.group(2).strip():
                bad.append('规则写死在单一主题上（应改走 [data-mode=] 或抽成令牌）：'
                           'html[data-theme="%s"] %s' % (m.group(1), m.group(2).strip()[:40]))
        if style and "[data-mode=" not in style:
            bad.append("CSS 没有任何 [data-mode=] 门控规则（亮底规则写回了死选择器）")
        # 设置面板：一个主题一个按钮 + 一个文案 span，且注册表外没有第二份名单
        for tid in (ids or []):
            cap = tid[:1].upper() + tid[1:]
            for needle, label in (('id="th%s"' % cap, "按钮"), ('id="th%sT"' % cap, "文案 span"),
                                  ("setTheme('%s')" % tid, "点击接线")):
                if needle not in tpl:
                    bad.append("主题 %s 缺%s %s" % (tid, label, needle))
        if len(re.findall(r"window\.THEME_IDS\s*=", tpl)) != 1:
            bad.append("window.THEME_IDS 被赋值多次（注册表不再是唯一出处）")
        if "const THEME_IDS = window.THEME_IDS" not in tpl:
            bad.append("主脚本没有把注册表接过来（可能另抄了一份名单）")
        # 出厂默认值（v0.28 逻辑债 #17）：'dark'/'zh' 曾经各抄 7 / 4 处兜底，
        # 现在只有注册表旁边那两行是出处，别处一律读 window.DEFAULT_*。
        m_dt = re.search(r"window\.DEFAULT_THEME\s*=\s*'([^']+)'", tpl)
        m_dl = re.search(r"window\.DEFAULT_LANG\s*=\s*'([^']+)'", tpl)
        if not m_dt or not m_dl:
            bad.append("取不到 window.DEFAULT_THEME / window.DEFAULT_LANG（默认值不再是单源）")
        else:
            if ids and m_dt.group(1) not in ids:
                bad.append("默认主题 %s 不在 THEME_IDS 里（首屏会静默退回暗色）" % m_dt.group(1))
            for pat, label in ((r"\|\|\s*'dark'", "||'dark'"), (r"\|\|\s*'zh'", "||'zh'")):
                n = len(re.findall(pat, tpl))
                if n:
                    bad.append("还有 %d 处 %s 手抄兜底（该读 window.DEFAULT_*）" % (n, label))
        if len(re.findall(r"dataset\.mode\s*=", tpl)) < 3:
            bad.append("dataset.mode 写入点少于 3 处（无闪脚本 / applyTheme / 阻断层有一处没跟上）")
        html_tag = tpl[tpl.find("<html"):tpl.find(">", tpl.find("<html"))]
        if "data-theme=" not in html_tag or "data-mode=" not in html_tag:
            bad.append("<html> 起始标签缺 data-theme 或 data-mode")
        # 成品侧必须与模板同一份注册表（防手改产物）
        prod = read(ASSET)
        for name in ("THEME_IDS", "THEME_MODE", "THEME_BG", "THEME_GLYPH",
                     "DEFAULT_THEME", "DEFAULT_LANG"):
            a = re.search(r"window\." + name + r"\s*=\s*[^\n]*", tpl)
            b = re.search(r"window\." + name + r"\s*=\s*[^\n]*", prod)
            if not a or not b:
                bad.append("%s 在模板或成品里找不到" % name)
            elif a.group(0).strip() != b.group(0).strip():
                bad.append("%s 成品与模板不一致（改了模板没重建）" % name)
        chk("S19", "主题注册表单源：名单 / 令牌块 / 按钮 / mode 门控四处对齐",
            not bad, ("OK（%d 个主题 %s，令牌 %d 键）"
                      % (len(ids or []), "/".join(ids or []), len(ref_keys or [])))
            if not bad else " / ".join(bad[:6]))
    except (OSError, ValueError, AttributeError) as e:
        chk("S19", "主题注册表单源：名单 / 令牌块 / 按钮 / mode 门控四处对齐", False, e)

    # S20 图版配色单源（v0.15 起四张学术图）：SVG 的颜色只有两条路 ——
    #     CSS 区里的 .fx-* 类规则从 --fig-* 令牌取值，JS 区只发类名。
    #     为什么盯这个：类名写错 / 令牌漏声明 / 谁手抄了个 #FFF，都只会表现为
    #     「那条线画成默认黑」，切到纸底主题才看得出来 —— 没有一套回归会因为
    #     一个颜色丢失而变红。所以判据必须是结构性的，不能靠肉眼看图。
    #     区域标记取不到 / 取反了顺序 / 成品与模板脱节，一律 FAIL。
    try:
        tpl = read(build_html.TPL)
        prod = read(ASSET)
        bad = []

        def _s20_region(src, beg, end, what):
            if src.count(beg) != 1 or src.count(end) != 1:
                raise ValueError("%s 区标记不唯一（%s / %s 各应出现 1 次）" % (what, beg, end))
            i, j = src.find(beg), src.find(end)
            if i < 0 or j < i:
                raise ValueError("%s 区标记顺序不对" % what)
            body = src[i + len(beg):j]
            if len(body) < 200:
                raise ValueError("%s 区内容过短（不足 200 字，像是被截断）" % what)
            return body

        def _s20_uncmt(t):
            t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
            return re.sub(r"(?m)^\s*//.*$", "", t)

        def _s20_block(src, sel):
            i = src.find(sel + "{")
            if i < 0:
                return None
            j = src.find("\n}", i)
            return None if j < 0 else src[i + len(sel) + 1:j]

        css = _s20_region(tpl, "/*==FIGS-CSS-BEGIN==*/", "/*==FIGS-CSS-END==*/", "图版样式")
        js = _s20_region(tpl, "/*==FIGS-BEGIN==*/", "/*==FIGS-END==*/", "图版脚本")

        # 1) 区域内不得出现色值字面量（注释除外：注释里写「不许出现 #」不算违规）
        for name, body in (("图版样式", css), ("图版脚本", js)):
            lits = sorted(set(re.findall(r"#[0-9a-fA-F]{3,8}\b|\brgba?\s*\(|\bhsla?\s*\(",
                                          _s20_uncmt(body))))
            if lits:
                bad.append("%s区有色值字面量（只能走 --fig-* 令牌）：%s" % (name, "、".join(lits[:5])))

        # 2) --fig-* 令牌双向：用到的必须在 :root 声明，声明的必须有人用
        root_body = _s20_block(tpl, ":root")
        declared = set(re.findall(r"(--fig-[a-z0-9-]+)\s*:", root_body or ""))
        style = tpl[tpl.find("<style>"):tpl.find("</style>")] if "<style>" in tpl else ""
        refs_css = set(re.findall(r"var\((--fig-[a-z0-9-]+)\)", css))
        refs_all = set(re.findall(r"var\((--fig-[a-z0-9-]+)\)", style))
        if not declared:
            bad.append(":root 里没有 --fig-* 令牌块（图版配色无处取值）")
        orphan = sorted(refs_css - declared)
        if orphan:
            bad.append("图版样式引用了 :root 没声明的令牌：%s" % "、".join(orphan))
        dead = sorted(declared - refs_all)
        if dead:
            bad.append("声明了但全模板没人用的令牌：%s" % "、".join(dead))

        # 3) fx-* 类名双向：JS 发的必须都定义，定义的必须有人发
        defined = set(re.findall(r"\.(fx-[a-z0-9]+)[\s,{]", css))
        emitted = set()
        for attr in re.findall(r'class="([^"]*)"', _s20_uncmt(js)):
            emitted.update(t for t in attr.split() if t.startswith("fx-"))
        for tbl in ("FIG_LN", "FIG_FN"):
            m = re.search(r"var\s+" + tbl + r"\s*=\s*\{([^}]*)\}", _s20_uncmt(js))
            if not m:
                bad.append("图版脚本缺 %s 表（大项→类名只能写在这一处）" % tbl)
                continue
            vals = re.findall(r"([a-z]+)\s*:\s*'([^']*)'", m.group(1))
            for k, v in vals:
                if v.startswith("fx-"):
                    emitted.add(v)
                else:
                    bad.append("%s 表里 %s 的值不是类名：%r" % (tbl, k, v))
            if len(vals) < 3:
                bad.append("%s 表条目少于 3（深蹲/卧推/硬拉至少都在）" % tbl)
        concat = re.findall(r"['\"]fx-[a-z]*['\"]\s*\+", js)
        if concat:
            bad.append("图版脚本把类名拼出来了（改走 FIG_LN/FIG_FN 表，拼出来的类名静态查不动）：%s"
                       % "、".join(concat[:3]))
        miss = sorted(emitted - defined)
        if miss:
            bad.append("JS 发了没有定义的类名（只会表现为「没颜色」）：%s" % "、".join(miss))
        unused = sorted(defined - emitted)
        if unused:
            bad.append("定义了但没人发的类名（发不出去就是拼错或删了图）：%s" % "、".join(unused))

        # 4) 成品侧与模板同一段（防手改产物：区域是纯文本注入，没有任何加工理由不同）
        for beg, end, what in (("/*==FIGS-CSS-BEGIN==*/", "/*==FIGS-CSS-END==*/", "图版样式"),
                               ("/*==FIGS-BEGIN==*/", "/*==FIGS-END==*/", "图版脚本")):
            a = _s20_region(tpl, beg, end, what + "（模板）")
            b = _s20_region(prod, beg, end, what + "（成品）")
            if a != b:
                bad.append("%s区成品与模板不一致（改了模板没重建，或手改了产物）" % what)

        chk("S20", "图版配色单源：区域无色值 / 令牌双向 / 类名双向 / 产物同段",
            not bad,
            ("OK（%d 个 .fx-* 类 / %d 个 --fig-* 令牌）" % (len(defined), len(declared)))
            if not bad else " / ".join(bad[:6]))
    except (OSError, ValueError) as e:
        chk("S20", "图版配色单源：区域无色值 / 令牌双向 / 类名双向 / 产物同段", False, e)

    # S21 动效时长单源（v0.16 记录流与动效）：transition/animation 的时长与缓动只能取
    #     :root 里的 --dur-* / --ease-* 令牌，唯一例外是 prefers-reduced-motion 兜底块。
    #     为什么盯这个：原先 13 处把 .1s/.15s/.2s/.3s 手抄在各自规则里，「把面板入场调快一点」
    #     这种五分钟的活要满文件找；更糟的是漏改一处在任何断言里都看不出来——它不改变
    #     最终状态，只改变中间帧，而无头回归量的就是最终状态。收成令牌之后，
    #     prefers-reduced-motion 那条兜底才有意义：一处开关真的能关掉全站动效。
    #     拿不到 :root 令牌块 / 成品与模板的 style 段不同 / 兜底块缺失，一律 FAIL。
    try:
        tpl = read(build_html.TPL)
        prod = read(ASSET)
        bad = []

        def _s21_style(src, what):
            i, j = src.find("<style>"), src.find("</style>")
            if i < 0 or j < i:
                raise ValueError("%s 里取不到 <style> 段" % what)
            return src[i:j]

        def _s21_block(src, sel):
            """从标记（可能是 @media 前缀，后面还跟着条件）找到它自己的 {…} 整段。"""
            i = src.find(sel)
            if i < 0:
                return None, None
            o, depth, k = src.find("{", i), 0, src.find("{", i)
            if o < 0:
                return None, None
            while k < len(src):
                c = src[k]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            return src[o + 1:k], (o, k)

        def _s21_root(css):
            i = css.find(":root{")
            if i < 0:
                return None
            j = css.find("}", i)
            return None if j < 0 else css[i + len(":root{"):j]

        css = _s21_style(tpl, "模板")
        root_body = _s21_root(css)
        if root_body is None:
            raise ValueError("模板 :root 令牌块取不到（动效时长无处取值）")

        declared = set(re.findall(r"(--(?:dur|ease)-[a-z0-9-]+)\s*:", root_body))
        if not declared:
            raise ValueError(":root 里没有 --dur-*/--ease-* 令牌声明")
        refs = set(re.findall(r"var\((--(?:dur|ease)-[a-z0-9-]+)\)", css))
        for t in sorted(refs - declared):
            bad.append("CSS 引用了 :root 没声明的动效令牌：%s" % t)
        for t in sorted(declared - refs):
            bad.append("声明了但全样式没人引用的动效令牌：%s（要么用起来，要么删掉）" % t)

        # 兜底块整段先摘出来：它是唯一允许写字面时长（.001ms）的地方
        _, rm_span = _s21_block(css, "@media (prefers-reduced-motion")
        rm_count = css.count("@media (prefers-reduced-motion")
        if rm_span is None:
            bad.append("缺 prefers-reduced-motion 兜底块（令牌的真正收益就在这里）")
        elif rm_count != 1:
            bad.append("prefers-reduced-motion 兜底写了 %d 处，只允许一处（散落迟早漏一条）" % rm_count)

        decls = re.findall(r"(?m)[;{\s]((?:-\w+-)?(?:transition|animation)[a-z-]*)\s*:\s*([^;{}]*)", css)
        if not decls:
            raise ValueError("样式里一条 transition/animation 声明都没有，判据抓不到东西")
        lit = []
        names_ref = set()
        for m in re.finditer(r"(?m)([;{\s])((?:-\w+-)?(?:transition|animation)[a-z-]*)\s*:\s*([^;{}]*)", css):
            prop, val = m.group(2), m.group(3)
            in_rm = rm_span is not None and rm_span[0] <= m.start() <= rm_span[1]
            if in_rm:
                continue
            for hit in re.findall(r"[\d.]+\s*m?s\b", val):
                lit.append("%s:%s（写死 %s，改走 --dur-* 令牌）" % (prop, val.strip()[:40], hit))
            plain = re.sub(r"var\([^)]*\)", "", val)
            plain = re.sub(r"(?:cubic-bezier|steps|linear-gradient)\s*\([^)]*\)", "", plain)
            # 只有 animation / animation-name 的值里那串标识符才是动画名；
            # transition 的值里同名位置写的是「要过渡的属性」（background、color、transform…），
            # 把它当动画名查就会满屏假红。
            if re.fullmatch(r"(?:-\w+-)?animation(-name)?", prop):
                for tok in re.split(r"[,\s]+", plain):
                    if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", tok or ""):
                        names_ref.add(tok)
        if lit:
            bad.extend(lit[:6])
        if len(lit) > 6:
            bad.append("……另外 %d 处写死时长" % (len(lit) - 6))

        kf_def = re.findall(r"@keyframes\s+([A-Za-z0-9_-]+)", css)
        kf_set = set(kf_def)
        kw = {"linear", "ease", "ease-in", "ease-out", "ease-in-out", "infinite", "alternate",
              "reverse", "normal", "forwards", "backwards", "both", "none", "running", "paused",
              "initial", "inherit", "unset", "important"}
        called = {n for n in names_ref if n not in kw and not n.startswith("-")}
        for n in sorted(called - kf_set):
            bad.append("animation 引用了没有 @keyframes 定义的名字：%s（只会表现为「不动」）" % n)
        for n in sorted(kf_set - called):
            bad.append("定义了 @keyframes %s 但没人引用（删掉，或接线漏了）" % n)

        if rm_span is not None:
            rm_body = css[rm_span[0]:rm_span[1]]
            for need in ("animation-duration", "transition-duration", "!important"):
                if need not in rm_body:
                    bad.append("prefers-reduced-motion 兜底块里缺 %s" % need)

        # 产物同段：style 是纯文本注入，没有任何理由和模板不一致（手改产物的老路）
        if _s21_style(prod, "成品") != css:
            bad.append("成品 <style> 段与模板不同（改了模板没重建，或手改了产物）")

        chk("S21", "动效时长单源：令牌双向 / 声明无字面时长 / 减动兜底唯一 / keyframes 双向 / 产物同段",
            not bad,
            ("OK（%d 个 --dur-*/--ease-* 令牌 / %d 条 transition·animation 声明 / %d 条 @keyframes）"
             % (len(declared), len(decls), len(kf_def))) if not bad else " / ".join(bad[:6]))
    except (OSError, ValueError) as e:
        chk("S21", "动效时长单源：令牌双向 / 声明无字面时长 / 减动兜底唯一 / keyframes 双向 / 产物同段", False, e)

    # S22 类名可达（v0.17 清死代码）：样式表里定义的每一个类必须真有人发，模板里
    #     class="…" 字面量发出的每一个类必须真有规则。为什么盯这个：清理时扫出 14 个
    #     「只剩规则、没人发」的类（.chip-hud / .setcount / .rec-row / .pv-grip / .ps-flange …），
    #     都是历次改面板留在 CSS 里的空壳；同一次扫描还抓到 actRow 自己抄了一份
    #     档位→类名的内联映射（'RTS'→'rts'），而唯一的映射表给的是 'trts'——
    #     .tier-chip.rts 永远命不中，动作库里 RTS 档的徽章其实一直没上色。
    #     这类事不崩、不报错，只是「悄悄不对」，而无头回归量的是几何与文本，量不到颜色。
    #     拼接出来的类名（'ct-'+cycleType / 'on-'+i）静态查不动，所以判可达前先从模板
    #     里收集 `'xxx'-` 这类拼接前缀，同族一律算可达（拼错的代价由反向那条腿兜）。
    #     取不到 <style> 段 / 一个类名都扫不到，一律 FAIL。
    try:
        tpl = read(build_html.TPL)
        bad = []
        i0, j0 = tpl.find("<style>"), tpl.find("</style>")
        if i0 < 0 or j0 < i0:
            raise ValueError("模板里取不到 <style> 段")
        css = tpl[i0 + 7:j0]
        outside = tpl[:i0] + tpl[j0 + 9:]
        # 注释里点名的类不算「定义」：样式表写一句「不必再补 .three 式规则」就会把 .three
        # 当成一条死规则报红（本检查的判据是规则，不是散文）。等长替换，后续索引不会错位。
        defined = set(re.findall(r"\.([a-z][a-zA-Z0-9_-]*)", strip_css_comments(css)))
        if not defined:
            raise ValueError("样式表里一条类名都扫不到（判据已失效，不是「没有类」）")

        # 工具侧只认类上下文：选择器里的 .foo，或 class="… foo …"（裸词 foo 不算，
        # 否则 check_hud 里的变量 sr 会把死规则 .sr 救活）
        tools_txt = "\n".join(read(os.path.join(HERE, fn))
                              for fn in sorted(os.listdir(HERE))
                              if fn.endswith((".js", ".py")))
        ref_tools = set(re.findall(r"['\"][^'\"]*\.([a-z][a-zA-Z0-9_-]*)", tools_txt))
        for m in re.finditer(r'class\s*=\s*(["\'])(.*?)\1', tools_txt, re.S):
            ref_tools.update(m.group(2).split())

        prefixes = set(re.findall(r"['\"]([a-z][a-z0-9-]*)-['\"]\s*\+", outside))

        def _s22_reachable(c):
            if re.search(r"(?<![\w$.-])" + re.escape(c) + r"(?![\w$-])", outside):
                return True
            if c in ref_tools:
                return True
            return any(c.startswith(p + "-") for p in prefixes)

        dead = sorted(c for c in defined if not _s22_reachable(c))
        for c in dead[:6]:
            bad.append("样式表定义了 .%s 但全站没人发（删掉规则，或把 UI 接回去）" % c)
        if len(dead) > 6:
            bad.append("……另外 %d 个只剩规则的类名" % (len(dead) - 6))

        # 反向：class="…" 字面量发出的类名必须有规则。hooks 是故意的「只当挂载点、不带样式」
        # 容器类（DOM 里在、CSS 无规则）；要给它上色就补规则并把名字从这张表里删掉。
        hooks = {"day-sub", "jts-recsets", "pv-sleeve"}
        emitted = set()
        for m in re.finditer(r'class="([^"<>]*)"', outside):
            emitted.update(t for t in m.group(1).split()
                           if re.fullmatch(r"[a-z][a-zA-Z0-9_-]*", t))
        for c in sorted(emitted - defined - hooks)[:6]:
            bad.append('发出 class="%s" 但样式表没有这条规则（拼错，或规则被删）' % c)

        chk("S22", "类名可达：样式表定义的真有人发 / 发出的 class 真有规则（拼接前缀豁免）", not bad,
            ("OK（%d 个类名定义全部可达 / %d 个 class 字面量 token / 拼接前缀 %d 个：%s）"
             % (len(defined), len(emitted), len(prefixes), "、".join(sorted(prefixes)) or "无"))
            if not bad else " / ".join(bad[:6]))
    except (OSError, ValueError) as e:
        chk("S22", "类名可达：样式表定义的真有人发 / 发出的 class 真有规则（拼接前缀豁免）", False, e)

    # S23 反向验证家族不腐（v0.17 清死代码）：每个 _sabotage_*.py 的故障靶串，必须在它的
    #     靶文件里恰好命中一次。为什么盯这个：红线 6 说「任何全绿都要拿得出反向验证」，
    #     而靶串是手抄在产品源码里的字符串 —— 产品改了、脚本没跟着改，注入就打空，
    #     「期望变红」那条承诺就此失效，而且没人会红。本版清理真抓到两处：
    #     _sabotage_b4 F1 抄的是 mround 非有限值重构之前的式子，
    #     _sabotage_c5 G2 抄的是 figsSheet 加进 closeAllSheets 之前的名单。
    #     动态构造靶串的脚本（_sabotage_m3 从 gen_seed.py 现读种子名）静态读不出来，
    #     v0.19 起让它自己用 `--s23-dump` 把现算结果交出来一起核 —— 取不出就判 FAIL。
    #     （v0.18 及之前是「如实写进 detail、不核对」：靶子漂了只能等下次 inject 打空，
    #      而那一刻已经不在守卫里了。）
    try:
        bad = []
        injected = []
        mver = re.search(r"versionName\s*=\s*'([^']*)'", read(GRADLE))
        ver = mver.group(1) if mver else None

        def _s23_eval(node, env):
            """常量折叠：字面量 / 顶层大写名 / os.path.join|dirname|abspath|normpath / + 拼接。"""
            if isinstance(node, ast.Constant):
                return node.value if isinstance(node.value, str) else None
            if isinstance(node, ast.Name):
                if node.id == "__file__":
                    return os.path.join(HERE, "_x.py")
                return env.get(node.id)
            if isinstance(node, ast.Call):
                name = ast.unparse(node.func)
                args = [_s23_eval(a, env) for a in node.args]
                if any(a is None for a in args):
                    return None
                if name == "os.path.join":
                    return os.path.join(*args)
                if name == "os.path.dirname":
                    return os.path.dirname(args[0])
                if name == "os.path.abspath":
                    return os.path.abspath(args[0])
                if name == "os.path.normpath":
                    return os.path.normpath(args[0])
                return None
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
                a, b = _s23_eval(node.left, env), _s23_eval(node.right, env)
                return a + b if isinstance(a, str) and isinstance(b, str) else None
            return None

        def _s23_pairs(node, env, default):
            """从 FAULTS / MUT / GROUPS 里取出 (靶文件, 原文片段)；取不出的返回 None。"""
            out, undetermined = [], False
            els = ([v for v in node.values] if isinstance(node, ast.Dict) else node.elts)
            for el in els:
                groups = el.elts if isinstance(el, ast.List) else [el]
                for g in groups:
                    if not isinstance(g, ast.Tuple) or len(g.elts) < 2:
                        undetermined = True
                        continue
                    tgt = _s23_eval(g.elts[0], env)
                    if isinstance(tgt, str) and os.path.isfile(tgt):
                        old = _s23_eval(g.elts[1], env)
                    else:
                        tgt, old = default, _s23_eval(g.elts[0], env)
                    if old is None:
                        undetermined = True
                    else:
                        out.append((tgt, old))
            return (out, undetermined)

        def _s23_check(fn, pairs, texts):
            """逐处核对：靶串必须在靶文件里恰好命中一次。返回核对了几处。"""
            n_done = 0
            for tgt, old in pairs:
                probe = old.replace("{{VER}}", ver or "{{VER}}")
                if tgt not in texts:
                    texts[tgt] = read(tgt)
                n = max(texts[tgt].count(probe), texts[tgt].count(probe.replace("\n", "\r\n")))
                n_done += 1
                if n == 0:
                    bad.append("%s 的靶串在 %s 里找不到（脚本已腐，反向验证不成立）：%r"
                               % (fn, os.path.basename(tgt), probe[:52]))
                elif n > 1:
                    bad.append("%s 的靶串在 %s 里命中 %d 次（不唯一，会把不相干的地方一起改掉）：%r"
                               % (fn, os.path.basename(tgt), n, probe[:52]))
            return n_done

        def _s23_dump(path):
            """动态现算靶串的脚本：用它自己的 `--s23-dump` 取（只读，不落盘）。"""
            try:
                proc = subprocess.run([sys.executable, path, "--s23-dump"],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      timeout=60, cwd=HERE)
            except (OSError, subprocess.SubprocessError) as e:
                return None, "拉不起 %s --s23-dump：%s" % (os.path.basename(path), e)
            err = (proc.stderr or b"").decode("utf-8", "replace").strip().splitlines()
            if proc.returncode != 0:
                return None, "%s --s23-dump 退出码 %d（现算不出靶串）：%s" % (
                    os.path.basename(path), proc.returncode, err[-1] if err else "无 stderr")
            try:
                rows = json.loads((proc.stdout or b"").decode("utf-8", "replace"))
            except ValueError as e:
                return None, "%s --s23-dump 的输出不是 JSON：%s" % (os.path.basename(path), e)
            if not isinstance(rows, list) or not rows:
                return None, "%s --s23-dump 一个靶串都没给" % os.path.basename(path)
            pairs = []
            for row in rows:
                if not (isinstance(row, list) and len(row) == 2 and all(isinstance(x, str) for x in row)):
                    return None, "%s --s23-dump 给的不是 [文件, 靶串]：%r" % (os.path.basename(path), row)
                pairs.append((row[0], row[1]))
            return pairs, None

        checked = 0
        dyn_note = []
        for fn in sorted(f for f in os.listdir(HERE)
                         if f.startswith("_sabotage_") and f.endswith(".py")):
            body = io.open(os.path.join(HERE, fn), encoding="utf-8").read()
            if os.path.exists(os.path.join(HERE, fn[:-3] + ".json")):
                # 这个脚本此刻在**注入态**：它的台账（= 注入前原文还没放回）就在旁边。
                # 它写进产品源码的故障，必然让它自己的靶串对不上 —— 那是故障现场，不是腐。
                # 不豁免这一条，家族里每注一次 S23 就跟着红一次，「只红自己那条腿」就没法核。
                injected.append(fn)
                continue
            script = os.path.join(HERE, fn)
            tree = ast.parse(body)
            env, tables = {}, []
            for n in tree.body:
                if not (isinstance(n, ast.Assign) and len(n.targets) == 1
                        and isinstance(n.targets[0], ast.Name) and n.targets[0].id.isupper()):
                    continue
                nm = n.targets[0].id
                v = _s23_eval(n.value, env)
                if isinstance(v, str):
                    env[nm] = v
                elif isinstance(n.value, (ast.List, ast.Tuple, ast.Dict)) and nm not in ("EXPECT", "IDX"):
                    tables.append(n.value)
            if not tables:
                # 整个故障表是函数现算的（_sabotage_m3 从 gen_seed.py 读工作簿名）：让它自己交靶串
                pairs, why = _s23_dump(script)
                if pairs is None:
                    bad.append(why)
                    continue
                checked += _s23_check(fn, pairs, {})
                dyn_note.append("%s（%d 处）" % (fn, len(pairs)))
                continue
            default = None
            for k in ("P", "ASSET", "TPL", "MODULE", "JAVA", "EXC", "BUILD"):
                if isinstance(env.get(k), str) and os.path.isfile(env[k]):
                    default = env[k]
                    break
            for v in env.values():      # 只剩一个靶文件的脚本（如 b4 只有 MODULE）
                if v.endswith(".json"):  # 台账不是靶
                    continue
                if default is None and os.path.isfile(v):
                    default = v
            default = default or ASSET
            texts = {}
            static_pairs = []
            partial = False
            for tbl in tables:
                pairs, undetermined = _s23_pairs(tbl, env, default)
                if undetermined:
                    partial = True       # 表里混了现算的项：整张表改走 --s23-dump，别只核能读出来的
                static_pairs.extend(pairs)
            if partial:
                pairs, why = _s23_dump(script)
                if pairs is None:
                    bad.append(why)
                    continue
                checked += _s23_check(fn, pairs, texts)
                dyn_note.append("%s（%d 处）" % (fn, len(pairs)))
                continue
            checked += _s23_check(fn, static_pairs, texts)
        if checked == 0:
            raise ValueError("一个反向验证靶串都没核对到（判据已失效，不是「脚本都干净」）")

        chk("S23", "反向验证家族不腐：%d 处靶串在位且唯一" % checked, not bad,
            ("OK（核对 %d 处靶串 / %d 个脚本%s%s）"
             % (checked, len([f for f in os.listdir(HERE)
                              if f.startswith("_sabotage_") and f.endswith(".py")]),
                "；动态现算核对 " + "、".join(dyn_note) if dyn_note else "",
                "；注入态跳过（台账在）：" + "、".join(sorted(injected)) if injected else ""))
            if not bad else " / ".join(bad[:5]))
    except (OSError, ValueError, SyntaxError) as e:
        chk("S23", "反向验证家族不腐：靶串在位且唯一", False, e)

    # S24 种子键名单单源（v0.18 种子链 JSON 化）：seed.json 的顶层键名单只有契约那一份，
    #     四个读者（gen 自检 / build 闸门 / 契约校验 / 本守卫）全部从它取。
    #     为什么值得单独立一条：这份名单原先手抄在三处，加一个键要改三处，漏一处的表现是
    #     「seed 里多一个键没人管」或「模板按名引用时 undefined」——后者要到开屏才炸。
    try:
        block = seed_contract()
        req, inv = block["required_keys"], block["invariant_keys"]
        bad = []
        if len(set(req)) != len(req) or len(set(inv)) != len(inv):
            bad.append("契约名单里有重复键")
        if not set(inv) <= set(req):
            bad.append("invariant_keys 有不在 required_keys 里的键：%s" % sorted(set(inv) - set(req)))
        with io.open(build_html.SEED, encoding="utf-8") as f:
            got = list(json.load(f))
        if sorted(got) != sorted(req):
            bad.append("seed.json 顶层键与名单不等：多 %s / 少 %s"
                       % (sorted(set(got) - set(req)) or "无", sorted(set(req) - set(got)) or "无"))
        readers = {"gate.py": "seed_contract(",
                   "build_html.py": "seed_required_keys(",
                   "plan_xlsx.py": "seed_invariant_keys(",
                   "gen_seed.py": "check_seed_shape("}
        for fn in sorted(readers):
            src = read(os.path.join(HERE, fn))
            if readers[fn] not in src:
                bad.append("%s 没从契约取名单（找不到调用 %s）" % (fn, readers[fn]))
            for ln, names in _roster_literals(src, set(req)):
                bad.append("%s 第 %d 行手抄了一份种子名单：%s" % (fn, ln, "、".join(names)))
        chk("S24", "种子顶层键名单单源：契约一份 / 四处读者都从它取 / 产物键不多不少", not bad,
            ("OK（名单 %d 键 / 不变量 %d 键 / 读者 4 处 / 产物键序 %s）"
             % (len(req), len(inv), ",".join(got[:3]) + "…"))
            if not bad else " / ".join(bad[:5]))
    except (OSError, ValueError, SyntaxError) as e:
        chk("S24", "种子顶层键名单单源：契约 / 读者 / 产物三对齐", False, e)

    # S25 i18n 挂载点可达（v0.19 回归加固）：模板里那张 I18N_NODES 是「哪个节点用哪两个词」的
    #     唯一出处，applyI18n 遍历它、按 id 找节点、把 textContent 换成 L(zh,en)。
    #     关键是它写的是 `if(el)` —— 节点不存在时**静默跳过**：不报错、不掉格，切了语言也只有
    #     那一格还是中文。历次改设置页最容易踩的就是「节点改名了 / 删了，登记表没跟上」。
    #     S14 只点名计划 / JSON / 日志那 14 个接线节点，S19 只管主题按钮那三个 span，这张全表
    #     此前没人管。腿：① 取不到表或一项都解析不出 → FAIL；② 登记的 id 必须在模板里有
    #     id="…" 挂载点（JS 拼出来的挂载点静态算不出，真需要就往下面的 exempt 加一条，
    #     别放宽这条腿）；③ 每项必须是恰好两条非空词（少一条 = 切英文时 textContent 被写成
    #     undefined）；④ id 不许重复（重复 = 后一条静默盖掉前一条，改错地方还以为改对了）。
    try:
        tpl = read(build_html.TPL)
        m = re.search(r"I18N_NODES\s*=\s*\{", tpl)
        if not m:
            raise ValueError("模板里取不到 I18N_NODES 登记表（判据已失效，不是「没有可翻译节点」）")
        i0 = m.start()
        j0 = tpl.find("\n};", i0)
        if j0 < i0:
            raise ValueError("I18N_NODES 登记表取不到结尾（这张表的结构被动过，静态核对无从下手）")
        block = tpl[i0:j0]
        dom = set(re.findall(r'id="([^"]+)"', tpl))
        exempt = set()          # 挂载点由 JS 拼出来的 id：确认一条加一条，别整表放宽
        entries = re.findall(r"(?m)^\s*([A-Za-z][\w-]*)\s*:\s*\[([^\]]*)\]", block)
        if not entries:
            raise ValueError("I18N_NODES 里一项都解析不出（表形如 id:['中文','English']）")
        bad = []
        seen = set()
        for node_id, body in entries:
            if node_id in seen:
                bad.append("id %s 登记了两次（后一条会静默盖掉前一条）" % node_id)
            seen.add(node_id)
            words = [a or b for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", body)]
            if len(words) != 2:
                bad.append("id %s 不是「两条词」形态：解析出 %d 条" % (node_id, len(words)))
            elif not all(w.strip() for w in words):
                bad.append("id %s 有空词串" % node_id)
            if node_id not in dom and node_id not in exempt:
                bad.append("id %s 在登记表里但模板没有这个挂载点（applyI18n 会静默跳过它）" % node_id)
        # 反方向腿（v0.28 逻辑债 #21）：上面只管「登记了却挂不上」，没人管「静态中文没登记」。
        #     漏登记不会报错、不会掉格，只会切了英文后那一格永远是中文 —— 没有一套回归会红。
        #     判据：静态标记里带中文、又有 id 的节点，要么在登记表里，要么脚本真的会写它
        #     （渲染函数用 getElementById 取到再赋值，包括先存进变量的常见写法）。
        mark = re.sub(r"<script[^>]*>.*?</script>", "", tpl, flags=re.S)
        scripts = "".join(re.findall(r"<script[^>]*>(.*?)</script>", tpl, re.S))
        cjk = re.compile(u"[\u4e00-\u9fff]")
        leaks = []
        static_nodes = re.findall(r'<[^>]*\bid="([^"]+)"[^>]*>([^<]*)', mark)
        for node_id, text in static_nodes:
            if node_id in seen or not cjk.search(text):
                continue
            if not re.search(r"getElementById\(\s*['\"]%s['\"]\s*\)" % re.escape(node_id), scripts):
                leaks.append(node_id)
        if leaks:
            bad.append("%d 个静态中文节点既不登记也没人写：%s" % (len(leaks), "/".join(leaks[:8])))
        chk("S25", "i18n 双向可达：登记的 id 真在 DOM 里 / 每项两条非空词 / 无重复 / "
            "静态中文节点要么登记要么脚本会写",
            not bad, ("OK（%d 项登记 / 挂载点全部在位 / 词对完整 / 静态中文 %d 格全部有人管）"
                      % (len(entries), sum(1 for n, t in static_nodes if cjk.search(t))))
            if not bad else " / ".join(bad[:5]))
    except (OSError, ValueError) as e:
        chk("S25", "i18n 挂载点可达", False, e)

    # S26 发版预检（v0.19）：发版那一刻才会犯的两种错，提前到静态层拦。
    #     ① 注入态不许发版：tools/ 下还有 _sabotage_*.json 台账 = 有人（多半是上一个 Agent）
    #        注了故障没复原，而 pack 第 1 步跑的就是这套守卫——台账里的原文此刻正躺在源码里，
    #        发出去的 APK 就带着故障。S23 只会「跳过并点名」注入态的脚本，它不拦发版，拦的是这条。
    #     ② 版本指针四处齐：gradle 是唯一出处（红线 1），但根 README / 本目录 §1 / CHANGELOG 头条 /
    #        RELEASE_NOTES 头条各抄了一份版本串用于人读。v0.17 就漏了 RELEASE_NOTES，
    #        装机时对着的是 v0.18 的 APK、发版说明写的还是 v0.16 —— 这类漂移没人报错，只有人对得上才发现。
    #     取不到任何一处指针一律 FAIL（「找不到就当没这回事」正是这类检查最没用的写法）。
    try:
        ver, code = build_html.read_version()
        bad = []
        leftovers = sorted(fn for fn in os.listdir(HERE)
                           if fn.startswith("_sabotage_") and fn.endswith(".json"))
        if leftovers:
            bad.append("注入态残留台账（先 revert 再发版）：%s" % "、".join(leftovers))
        pointers = [
            (os.path.join(ROOT, "README.md"),
             r"现行版本：\`v([0-9.]+)\`（versionCode (\d+)）", "根 README 身份行"),
            (os.path.join(HERE, "..", "README.md"),
             r"\| 现行版本 \| \`v([0-9.]+)\`（\`versionName = '([0-9.]+)'\` / \`versionCode = (\d+)\`）",
             "mobile/README §1 身份卡"),
            (os.path.join(ROOT, "CHANGELOG.md"), r"^## \[v([0-9.]+)\]", "CHANGELOG 头条"),
            (os.path.join(ROOT, "release", "RELEASE_NOTES.md"),
             r"^# ExDark Pro · v([0-9.]+)", "RELEASE_NOTES 头条"),
        ]
        for path, pat, label in pointers:
            try:
                src = read(path)
            except OSError as e:
                bad.append("%s 读不到（%s）" % (label, e))
                continue
            m = re.search(pat, src, re.M)
            if not m:
                bad.append("%s 找不到版本指针（样式：%s）" % (label, pat))
                continue
            found = m.groups()
            if found[0] != ver or (len(found) > 1 and found[-1] != str(code)):
                bad.append("%s 写的是 v%s/code %s，gradle 是 v%s/code %d"
                           % (label, found[0], found[-1] if len(found) > 1 else "—", ver, code))
        chk("S26", "发版预检：无注入台账残留 / 四处版本指针都跟着 gradle", not bad,
            "OK（v%s / code %d，指针 4 处齐）" % (ver, code) if not bad else " / ".join(bad[:5]))
    except (OSError, ValueError, SystemExit) as e:
        chk("S26", "发版预检", False, e)

    # S27 仓库形状（v0.21 立，v0.31 换边界）：v0.21 那版是「96 本里只跟踪 seed 引用的 18 本」，
    #     v0.31 把整库移出仓（data/02_参考资料 → 顶层 ref/，全部不入仓）——那 18 本的唯一作用是
    #     **给出处对账**，App 运行时不读它（gen_seed 只读 data/01_工作簿 三份表），却让仓背 53MB、
    #     历史背 481MB。边界从「哪些书进仓」换成「参考库不进仓」，一样靠口头约定就会长回去。
    #     五条腿：① 顶层条目白名单（跟踪的 + 未跟踪的都要登记，未登记又没 ignore 的就是胖回去的路）
    #     ② release/ 跟踪的 APK ≤ 3 版 ③ data/ 与 release/ 无孤儿
    #     ④ 参考库不许在仓里，且 seed 的 canon 出处逐条能在磁盘 ref/ 上找到（断链就是数据缺陷）
    #     ⑤ canon 非空（空集说明溯源链断了，④ 会自动全过）。名单唯一出处是 seed，本文件不抄书目。
    #     git 取不到（没装 / 不在仓里 / seed 读不出）一律 FAIL：查不到不等于没事。
    try:
        def _git_z(sub, *rest):
            """git 对非 ASCII 路径默认八进制转义，**必须 -z**，否则整条腿假红（本机实测）。
            -z 紧跟子命令：放在 `--` 之后会被当成 pathspec 字面量。"""
            out = subprocess.check_output(["git", "-C", ROOT, sub, "-z"] + list(rest),
                                          stderr=subprocess.STDOUT, timeout=60)
            return [p.decode("utf-8") for p in out.split(b"\0") if p]

        shape_bad = []
        top = {p.split("/")[0] for p in _git_z("ls-files")}
        allowed_top = {".gitignore", "AGENTS.md", "CHANGELOG.md", "README.md",
                       "mobile", "data", "release"}
        stray = sorted(top - allowed_top)
        missing = sorted(allowed_top - top)
        if stray:
            shape_bad.append("① 顶层多出未登记条目：%s" % "、".join(stray))
        if missing:
            shape_bad.append("① 顶层应有条目不见了：%s（取数不对或误删）" % "、".join(missing))
        # 未跟踪的顶层条目只允许一种存在方式：被 ignore。参考库整库出仓靠的就是这条——
        # 哪天 .gitignore 里 `ref/` 那行被删，96 本书立刻以「未登记顶层条目」回来。
        others_top = {p.split("/")[0] for p in _git_z("ls-files", "--others", "--exclude-standard")
                      if not p.startswith(".")}
        for name in sorted(others_top - top):
            shape_bad.append("① 顶层未跟踪条目 `%s/` 没被 ignore（出仓边界破了）" % name)

        apks = sorted(p for p in _git_z("ls-files", "--", "release") if p.endswith(".apk"))
        if len(apks) > 3:
            shape_bad.append("② release/ 跟踪了 %d 版 APK，只留最近 3 版，其余移 archive/release/：%s"
                             % (len(apks), "、".join(os.path.basename(a) for a in apks)))

        orphans = _git_z("ls-files", "--others", "--exclude-standard", "--", "data", "release")
        if orphans:
            shape_bad.append("③ 既不跟踪也不 ignore 的孤儿 %d 个（下一次 git add -A 会把它们悄悄拖进仓）：%s"
                             % (len(orphans), "、".join(orphans[:4])))

        with io.open(build_html.SEED, encoding="utf-8") as f:
            pl = (json.load(f).get("programLib") or {}).get("items")
        if not isinstance(pl, list) or not pl:
            raise ValueError("读不到 seed 的 programLib.items —— canon 出处的唯一来源")
        canon = set()
        for it in pl:
            c = it.get("canon") if isinstance(it, dict) else None
            if isinstance(c, str) and c.startswith("02_"):
                canon.add(c)                       # 其余 canon 是「→ 计划名」人读串，不对应文件
        if not canon:
            raise ValueError("seed 里一条 canon 出处都没有，S27 无从对账")
        # ④ 方向和 v0.21 反了：书**不该**在仓里。仓里出现 ref/ = 有人把库又拉回去了；
        #    磁盘上找不到 = canon 指向空气（换机后出处对账全部失效）。
        inside = sorted(p for p in _git_z("ls-files") if p.split("/")[0] == "ref")
        if inside:
            shape_bad.append("④ 参考库又入仓了 %d 个文件（v0.31 起整库不入仓；App 运行时不读它，"
                             "要拉回来先回答「谁在运行时读它」）：%s"
                             % (len(inside), "、".join(inside[:3])))
        absent = sorted(c for c in canon
                        if not os.path.isfile(os.path.join(ROOT, "ref", c.replace("/", os.sep))))
        if absent:
            if not os.path.isdir(os.path.join(ROOT, "ref")):
                shape_bad.append("④ 参考库整个不在（顶层缺 `ref/`）：库不入仓，新 clone 必须先从本机副本或"
                                 "备份位拷回，命令见 data/00_索引/DATA_MAP.md §1；缺的 %d 本无从核对"
                                 % len(absent))
            else:
                shape_bad.append("④ canon 指向的书在磁盘 ref/ 上找不到：%s" % "、".join(absent[:4]))

        chk("S27", "仓库形状：顶层白名单（未跟踪条目须被 ignore）/ release ≤3 版 / 无孤儿 / 参考库不入仓且 canon 逐条在磁盘有书",
            not shape_bad,
            "OK（顶层 %d 项 / APK %d 版 / canon %d 条逐条有书 / 库在仓外）"
            % (len(top), len(apks), len(canon)) if not shape_bad else " / ".join(shape_bad[:5]))
    except (OSError, ValueError, SystemExit, subprocess.SubprocessError) as e:
        chk("S27", "仓库形状", False, e)

    # S28 容量与周期预设单源（v0.23 容量模型）：「有哪几种周期」「计划能开多大」这两件事
    #     在契约里各有两处读者 —— cycle_presets.items[*].id 是名单，sheets.Blocks.enums.cycle_type
    #     是导入校验用的同一份名单的第二抄；capacity 是 App 输入框上限，模板里 stBlocks 的 max="…"
    #     又是第三个抄。v0.23 之前这些数还散在模板的 CYCLE_PRESETS / MODE_BY_CYCLE 里手抄着。
    #     漂移的表现都很安静：枚举少一个 → 导入合法计划被拒；HTML 字面量大一个 → 用户能填进
    #     输入框、保存时被 JS 夹紧，看着像「按钮坏了」。四条腿：
    #     ① 两份周期名单集合相等且各自无重复、非空；
    #     ② capacity 四键是正整数、min ≤ max，且 Blocks.ranges.work_weeks 上限不超过总周数上限；
    #     ③ 契约给的 work_mode / deload_mode（含 Custom 兜底）全部在 seed.proto 里存在；
    #     ④ 模板真的从 PLAN_SCHEMA 取这两件事（读不到 .items / .capacity 就是又长出第二份），
    #        且 stBlocks 的 max="…" 字面量等于 capacity.max_blocks（JS 会动态覆写它，
    #        但首屏与「JS 挂了」的场景按这个字面量渲染，它就是给用户看的那个上限）。
    try:
        with io.open(build_html.PLAN_SCHEMA, encoding="utf-8") as f:
            sch = json.load(f)
        items = (sch.get("cycle_presets") or {}).get("items")
        if not isinstance(items, list) or not items:
            raise ValueError("契约 cycle_presets.items 缺失或为空（周期预设名单的唯一出处）")
        ids = [it.get("id") for it in items]
        enum_ids = ((sch.get("sheets") or {}).get("Blocks") or {}).get("enums", {})
        enums = enum_ids.get("cycle_type")
        if not isinstance(enums, list) or not enums:
            raise ValueError("契约 sheets.Blocks.enums.cycle_type 缺失（导入侧的周期名单）")
        bad = []
        if len(set(ids)) != len(ids) or len(set(enums)) != len(enums):
            bad.append("① 周期名单有重复项：presets %s / enums %s" % (ids, enums))
        elif set(ids) != set(enums):
            bad.append("① 周期名单两份不等：只在 cycle_presets %s / 只在 Blocks.enums %s"
                       % (sorted(set(ids) - set(enums)) or "无",
                          sorted(set(enums) - set(ids)) or "无"))

        cap = sch.get("capacity") or {}
        capv = {}
        for k in ("min_weeks", "max_weeks", "min_blocks", "max_blocks"):
            v = cap.get(k)
            if not isinstance(v, int) or isinstance(v, bool) or v < 1:
                bad.append("② capacity.%s 不是 ≥1 的整数：%r" % (k, v))
                v = None
            capv[k] = v
        if all(capv.get(k) for k in ("min_weeks", "max_weeks")) and capv["min_weeks"] > capv["max_weeks"]:
            bad.append("② capacity min_weeks > max_weeks")
        if all(capv.get(k) for k in ("min_blocks", "max_blocks")) and capv["min_blocks"] > capv["max_blocks"]:
            bad.append("② capacity min_blocks > max_blocks")
        blk = (sch.get("sheets") or {}).get("Blocks") or {}
        ww = (blk.get("ranges") or {}).get("work_weeks")
        if not (isinstance(ww, list) and len(ww) == 2):
            bad.append("② 取不到 Blocks.ranges.work_weeks")
        elif capv.get("max_weeks") and ww[1] > capv["max_weeks"]:
            bad.append("② 单 Block work_weeks 上限 %s 超过总周数上限 %s（这种 Block 永远存不进去）"
                       % (ww[1], capv["max_weeks"]))

        with io.open(build_html.SEED, encoding="utf-8") as f:
            proto = (json.load(f).get("proto") or {})
        if not proto:
            raise ValueError("读不到 seed.proto（模式键的唯一出处）")
        modes = set(proto)
        want = set([it.get("work_mode") for it in items]
                   + [it.get("deload_mode") for it in items if it.get("deload_mode")]
                   + [(blk.get("defaults") or {}).get("deload_mode")])
        missing = sorted(m for m in want if m and m not in modes)
        if missing:
            bad.append("③ 契约给的 work/deload 模式不在 seed.proto 里：%s" % "、".join(missing))

        tpl = read(build_html.TPL)
        if "PLAN_SCHEMA.cycle_presets.items" not in tpl:
            bad.append("④ 模板没从 PLAN_SCHEMA.cycle_presets.items 取周期名单（第二份名单长回来了）")
        if "PLAN_SCHEMA.capacity" not in tpl:
            bad.append("④ 模板没从 PLAN_SCHEMA.capacity 取容量上限")
        if "MODE_BY_CYCLE" in tpl:
            bad.append("④ 模板里还有 MODE_BY_CYCLE 手抄配对表")
        mb = re.search(r'id="stBlocks"[^>]*\bmax="(\d+)"', tpl)
        if not mb:
            bad.append("④ 模板里取不到 stBlocks 的 max 字面量")
        elif capv.get("max_blocks") and int(mb.group(1)) != capv["max_blocks"]:
            bad.append("④ stBlocks max=\"%s\" 与 capacity.max_blocks=%d 分叉"
                       % (mb.group(1), capv["max_blocks"]))

        chk("S28", "容量与周期预设单源：两份名单相等 / capacity 自洽 / 模式在 proto 里 / 模板从契约取且不手抄",
            not bad,
            "OK（周期 %d 种 / 容量 1–%d 周 · 1–%d Block / 模式覆盖 %d 键 / 模板读者在位）"
            % (len(ids), capv.get("max_weeks") or 0, capv.get("max_blocks") or 0, len(modes))
            if not bad else " / ".join(bad[:5]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S28", "容量与周期预设单源", False, e)


    # S29 自动调节判据单源（v0.24 下周建议）：ROADMAP §2.6 那一串数字（完成率下限、RPE 硬顶、
    #     RPE 缺口、上/下肢与 T3 步进、回退量、单次幅度上限、T3 干净次数）只准写在契约 autoreg 段。
    #     它有三类读者：模板的 nextWeekAdvice()（算建议）、Workouts.prog_rules（xlsx prog_rule 列
    #     里那两句人话）、设置页 advNote（给用户看的口径说明）。漂移的方式很安静：模板里手抄一个
    #     2.5，契约改了建议不变；prog_rules 的 18 改了，代码还按 25 判 —— 用户读到的规则和
    #     实际执行的规则从此是两套。四条腿：
    #     ① autoreg 十个键在位且类型对（数值 / 按上-下肢的字典 / 模式→次数 / 后缀名单）；
    #     ② clean_reps 的每个模式都真的存在且是 T3 档（阈值挂在不存在的模式上等于没挂）；
    #     ③ 每个 clean_reps 数字都出现在该模式的 prog_rules 人话里（文字与数字不许分叉）；
    #     ④ 模板确实读 PLAN_SCHEMA.autoreg，且建议引擎的代码行里没有第二个判据数字
    #        （注释允许写人话，代码不许带私货；先剥注释再扫，边界用「前后不是数字或小数点」）。
    try:
        with io.open(build_html.PLAN_SCHEMA, encoding="utf-8") as f:
            sch29 = json.load(f)
        ar = sch29.get("autoreg")
        if not isinstance(ar, dict):
            raise ValueError("契约缺 autoreg 段（自动调节判据的唯一出处）")
        bad29 = []
        nums = {}
        for k in ("min_completion", "rpe_hard_stop", "rpe_gap", "t3_step_kg",
                  "regress_kg", "cap_pct", "cap_kg"):
            v = ar.get(k)
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
                bad29.append("① autoreg.%s 不是正数：%r" % (k, v))
                continue  # 坏值不进扫描表：拿 0 去代码里找「手抄」会把每个 0 都认成赃物
            nums[k] = v
        st = ar.get("step_up_kg")
        if not isinstance(st, dict) or any(
                not isinstance(st.get(a), (int, float)) or isinstance(st.get(a), bool) or st.get(a) <= 0
                for a in ("lower", "upper")):
            bad29.append("① autoreg.step_up_kg 需要 lower/upper 两个正数：%r" % (st,))
        else:
            nums["step_lower"] = st["lower"]
            nums["step_upper"] = st["upper"]
        cr = ar.get("clean_reps")
        if not isinstance(cr, dict) or not cr:
            bad29.append("① autoreg.clean_reps 缺空（T3 干净次数阈值）")
            cr = {}
        sfx = ar.get("skip_mode_suffix")
        if not (isinstance(sfx, list) and sfx and all(isinstance(x, str) and x.startswith(".") for x in sfx)):
            bad29.append("① autoreg.skip_mode_suffix 需要非空的「.后缀」名单：%r" % (sfx,))

        with io.open(build_html.SEED, encoding="utf-8") as f:
            proto29 = (json.load(f).get("proto") or {})
        for m, n in cr.items():
            p = proto29.get(m)
            if not p:
                bad29.append("② clean_reps 挂在不存在的模式 %s 上" % m)
            elif p.get("tier") != "T3":
                bad29.append("② clean_reps.%s 是 %s 档，不是 T3（阈值挂错档）" % (m, p.get("tier")))
            elif not isinstance(n, int) or isinstance(n, bool) or n <= int(p.get("reps") or 0):
                bad29.append("② clean_reps.%s=%r 应大于该模式处方次数 %r（末组永远追不上）" % (m, n, p.get("reps")))

        rules = ((sch29.get("sheets") or {}).get("Workouts") or {}).get("prog_rules") or {}
        for m, n in cr.items():
            txt = rules.get(m)
            if not txt:
                bad29.append("③ %s 没有 prog_rules 人话，代码却有数字 %s" % (m, n))
            elif str(n) not in str(txt):
                bad29.append("③ prog_rules[%s] 里找不到 %s（人话与判据分叉：%s）" % (m, n, txt))

        tpl29 = read(build_html.TPL)
        if "PLAN_SCHEMA.autoreg" not in tpl29:
            bad29.append("④ 模板没从 PLAN_SCHEMA.autoreg 取判据（第二份数字长回来了）")
        a0 = tpl29.find("function nextWeekAdvice(")
        a1 = tpl29.find("/*==FIGS-END==*/", a0)
        if a0 < 0 or a1 < 0:
            raise ValueError("定位不到下周建议引擎（函数改名或 FIGS 收口注释没了）")
        eng = tpl29[a0:a1]
        eng = re.sub(r"/\*.*?\*/", " ", eng, flags=re.S)
        eng = re.sub(r"//[^\n]*", " ", eng)
        stolen = []
        for k, v in nums.items():
            sv = ("%g" % v)
            if re.search(r"(?<![0-9.])" + re.escape(sv) + r"(?![0-9.])", eng):
                stolen.append("%s=%s" % (k, sv))
        for x in [str(v) for v in cr.values() if isinstance(v, int) and not isinstance(v, bool) and v > 0]:
            if re.search(r"(?<![0-9.])" + re.escape(x) + r"(?![0-9.])", eng):
                stolen.append("clean_reps=" + x)
        if stolen:
            bad29.append("④ 引擎代码里手抄了判据：%s" % "、".join(stolen))
        if eng.count("ar.") < 8:
            bad29.append("④ 引擎里 ar.* 只有 %d 处，判据八成没走契约" % eng.count("ar."))

        chk("S29", "自动调节判据单源：autoreg 自洽 / clean_reps 挂对档 / prog_rules 人话含同一数字 / 引擎不手抄",
            not bad29,
            "OK（阈值 %d 键 / 步进 上 %s·下 %s·T3 %s / 干净次数 %s / 跳过后缀 %s / 引擎读契约）"
            % (len(nums), st.get("upper") if isinstance(st, dict) else "?",
               st.get("lower") if isinstance(st, dict) else "?",
               nums.get("t3_step_kg"),
               "、".join("%s:%s" % (m, n) for m, n in cr.items()) or "无",
               "/".join(sfx) if isinstance(sfx, list) else "?")
            if not bad29 else " / ".join(bad29[:5]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S29", "自动调节判据单源", False, e)

    # S30 写回护栏（下周建议可应用 + 撤销）：v0.24 的引擎只读，v0.25 在这一节第一次允许落笔改
    #     处方。风险跟 S29 不一样：S29 怕「判据漂移」，这里怕「写坏账本」——批量应用越界、撤销吃
    #     掉用户手改、档位说明写在 UI 而代码走另一套。漂移同样是安静的，而且这次会动数据，所以
    #     守的是「出口」而不是「数字」：
    #     ① 档位与键位单源：ADV_TIERS 名单、ADV_TIER_DEFAULT='suggest'（决策 3：默认只建议）各
    #        只准出现一次；advAuto 落 prefs 片、advAudit 落 work 片，两把钥匙不许串片；
    #        默认值与 ensureShape 的退回都从常量取，不许手抄 'suggest'。
    #     ② 唯一落笔出口：建议引擎那一节（nextWeekAdvice → FIGS 收口）里改重量的语句
    #        只准待在 advWriteLoad 体内，其余每处 `.load=` 都是第二个后门。
    #     ③ 写回侧不复造判据：跳档后缀走契约 skip_mode_suffix 且只读一次；幅度上限必须同时读
    #        cap_kg 与 cap_pct（少一个就变成「只按公斤封顶」，5% 那条规则从此不存在）。
    #     ④ 四档策略在闸门口径统一：advGuard 体内 off / suggest 各拒绝一次、confirm / auto
    #        不出现（能写的档位不需要被拒绝），别处再多写一次「off 不写」就是第二套口径。
    #     ⑤ 撤销安全：还原必须比对当前值与审计值（!==+it.after），批次只有全数还原才盖 undone，
    #        审计条数受 ADV_AUDIT_MAX 约束且只用 slice(0,ADV_AUDIT_MAX) 一处裁剪。
    #     ⑥ UI 在位：档位选择器 / 批量应用 / 撤销上一批 / 审计容器四个挂载点 + onchange/onclick
    #        接线齐全（挂在 DOM 上的文案若没有对应函数，S25 只管 id 存在，管不到写回路径）。
    #     ⑦ 产物同段：模板里那把唯一的笔与四个挂载点在成品里同样在位（防手改 index.html）。
    try:
        tpl30 = read(build_html.TPL)
        bad30 = []
        a0 = tpl30.find("function nextWeekAdvice(")
        a1 = tpl30.find("/*==FIGS-END==*/", a0)
        if a0 < 0 or a1 < 0:
            raise ValueError("定位不到下周建议引擎（函数改名或 FIGS 收口注释没了）")
        eng30 = re.sub(r"/\*.*?\*/", " ", tpl30[a0:a1], flags=re.S)
        eng30 = re.sub(r"//[^\n]*", " ", eng30)
        g0 = eng30.find("function advGuard(")
        g1 = eng30.find("function advCandidates(", g0)
        if g0 < 0 or g1 < 0:
            raise ValueError("定位不到写回闸门 advGuard（函数改名或尾巴注释没了）")
        guard = eng30[g0:g1]
        w0 = eng30.find("function advWriteLoad(")
        w1 = eng30.find("\n", w0)
        if w0 < 0:
            raise ValueError("定位不到唯一落笔出口 advWriteLoad")
        writer = eng30[w0:w1 if w1 > 0 else len(eng30)]

        # ① 档位与键位
        for t, why in [("const ADV_TIERS=['off','suggest','confirm','auto']",
                       "① ADV_TIERS 名单不是「off/suggest/confirm/auto」或被抄了两份"),
                      ("const ADV_TIER_DEFAULT='suggest'",
                       "① 默认档不在常量里写死成 suggest（决策 3：默认只建议）")]:
            if tpl30.count(t) != 1:
                bad30.append("%s（实到 %d 次）" % (why, tpl30.count(t)))
        pk = re.search(r"const PREF_KEYS=\[([^\]]*)\]", tpl30)
        wk = re.search(r"const WORK_KEYS=\[([^\]]*)\]", tpl30)
        if not pk or not wk:
            bad30.append("① 取不到 PREF_KEYS / WORK_KEYS 名单")
        else:
            pkeys, wkeys = pk.group(1), wk.group(1)
            if "'advAuto'" not in pkeys:
                bad30.append("① advAuto 不在 PREF_KEYS（档位没进 prefs 片）")
            if "'advAuto'" in wkeys:
                bad30.append("① advAuto 又出现在 WORK_KEYS（同一把钥匙两片都写）")
            if "'advAudit'" not in wkeys:
                bad30.append("① advAudit 不在 WORK_KEYS（写回审计不进账本，撤销活不过刷新）")
            if "'advAudit'" in pkeys:
                bad30.append("① advAudit 又出现在 PREF_KEYS（审计跟设置混片）")
        if tpl30.count("advAuto:ADV_TIER_DEFAULT") < 1:
            bad30.append("① 初始 state 的默认档没从常量取")
        if tpl30.count("ADV_TIERS.indexOf(state.advAuto)") < 1:
            bad30.append("① ensureShape 没按 ADV_TIERS 校验退回，脏档位能一路带进写回")

        # ② 唯一落笔出口
        backdoors = []
        for m in re.finditer(r"\.load\s*=[^=]", eng30):
            if not (w0 <= m.start() < w1):
                backdoors.append(eng30[max(0, m.start() - 40):m.start() + 30].replace("\n", " "))
        if backdoors:
            bad30.append("② 引擎里有 %d 处绕过 advWriteLoad 改重量：%s"
                         % (len(backdoors), " ‖ ".join(backdoors[:2])))
        if "ex.load=value" not in writer:
            bad30.append("② advWriteLoad 体内没有那唯一一笔（出口名存实亡）")
        if eng30.count("advWriteLoad(") < 3:
            bad30.append("② advWriteLoad 只被调 %d 次，写回/撤销八成没走出口"
                         % eng30.count("advWriteLoad("))

        # ③ 写回侧不复造判据
        if eng30.count("ar.skip_mode_suffix") != 1:
            bad30.append("③ skip_mode_suffix 在引擎里读了 %d 次（后缀名单该只从契约取一次）"
                         % eng30.count("ar.skip_mode_suffix"))
        if eng30.count("advHasSuffix(") < 2:
            bad30.append("③ advHasSuffix 定义/调用只 %d 处，建议侧或闸门侧漏了跳档判定"
                         % eng30.count("advHasSuffix("))
        for t in ("ar.cap_kg", "ar.cap_pct"):
            if guard.count(t) < 1:
                bad30.append("③ 闸门里没读 %s（幅度上限不再跟契约走）" % t)
        if re.search(r"Math\.min\(\s*[0-9]", guard):
            bad30.append("③ 闸门里的上限写成了字面量（cap 该来自 autoreg）")

        # ④ 四档策略口径
        for t, why in [("tier==='off'", "④ 闸门里 off 的拒绝口径不在/重复"),
                       ("tier==='suggest'", "④ 闸门里 suggest 的拒绝口径不在/重复")]:
            if guard.count(t) != 1:
                bad30.append("%s（实到 %d 次）" % (why, guard.count(t)))
        for t in ("tier==='confirm'", "tier==='auto'"):
            if t in guard:
                bad30.append("④ 闸门里出现了 %s：可写档位被单独特判，口径开始分叉" % t)

        # ⑤ 审计有界与撤销安全
        if tpl30.count("const ADV_AUDIT_MAX=") != 1:
            bad30.append("⑤ ADV_AUDIT_MAX 不在或有多份")
        if eng30.count("slice(0,ADV_AUDIT_MAX)") != 1:
            bad30.append("⑤ 审计裁剪点不是唯一一处（实到 %d）" % eng30.count("slice(0,ADV_AUDIT_MAX)"))
        if eng30.count("!==+it.after") != 1:
            bad30.append("⑤ 撤销没做「当前值必须等于审计值」的比对（手改会被覆盖）")
        if eng30.count("b.undone=true") != 1:
            bad30.append("⑤ 撤销盖章点不在或有多份")

        # ⑥ UI 在位
        ui30 = [('id="advTier"', "档位选择器"), ('onchange="setAdvTier', "档位接线"),
                ('id="advApplyAll"', "批量应用"), ('id="advUndoLast"', "撤销上一批"),
                ('id="advAudit"', "审计容器"), ('onclick="advApplyRow(', "行内应用"),
                ('id="advWeek"', "周选择"), ('onchange="onAdvWeekChange', "换周接线")]
        ui_hits = 0
        for t, why in ui30:
            if tpl30.count(t) < 1:
                bad30.append("⑥ 缺 %s（%s）" % (why, t))
            else:
                ui_hits += 1

        # ⑦ 产物同段
        try:
            prod30 = read(ASSET)
        except OSError:
            prod30 = None
        if prod30 is None:
            bad30.append("⑦ 读不到成品，无法核对模板与产物同段")
        else:
            for t in ("function advWriteLoad(ex,value){ ex.load=value; }",
                      'id="advTier"', 'id="advAudit"', "advAuto:ADV_TIER_DEFAULT"):
                if t not in prod30:
                    bad30.append("⑦ 成品里找不到「%s」（产物与模板脱节）" % t)

        m_tiers = re.search(r"const ADV_TIERS=\[([^\]]*)\]", tpl30)
        m_deflt = re.search(r"const ADV_TIER_DEFAULT='([^']*)'", tpl30)
        m_max = re.search(r"const ADV_AUDIT_MAX=(\d+)", tpl30)
        detail30 = "OK（档位 %d 档默认 %s / 出口 %d 处调用 / 闸门读 cap_kg+cap_pct+后缀 / 审计上限 %s / 挂载点 %d·%d 在位 / 成品同段）" % (
            len(re.findall(r"'[a-z]+'", m_tiers.group(1))) if m_tiers else 0,
            m_deflt.group(1) if m_deflt else "?",
            eng30.count("advWriteLoad("),
            m_max.group(1) if m_max else "?",
            ui_hits, len(ui30))

        chk("S30", "写回护栏：档位/键位单源 · 落笔只走 advWriteLoad · 闸门读契约 cap 与后缀 · "
                   "off/suggest 口径唯一 · 审计有界且撤销认手改 · UI 接线在位 · 产物同段",
            not bad30,
            detail30 if not bad30 else " / ".join(bad30[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S30", "写回护栏", False, e)

    # S31 分片文件名双侧同步（v0.28 读取闸门）：原生 readStore() 把「文件不在」和「读挂了」
    #     都压成空串，前端唯一的分辨办法是 storeProbe() 报的字节数。这条链的文件名两侧各写一遍
    #     （Java 的 F_* 常量 / 模板的 BRIDGE_FILE 映射），任何一侧改名或漏一个分片，
    #     probe["roast_workout.json"] 就取到 undefined → NaN>0 为假 → 闸门永不触发，
    #     「磁盘有账却读不回」重新退化成静默空账本覆盖（红线 4）。四段各自能红：
    #     ① Java 侧五个 F_*.json 常量集合与模板 BRIDGE_FILE 取值集合完全相等（多一个少一个都红）；
    #     ② boot 里闸门调用点在位：unreadableSlices(sliceProbe( 与 markBootFatal('read')；
    #     ③ BF_REASON_LABEL 给 read 留了人话标签（否则阻断层直接显示键名）；
    #     ④ 成品同段：以上三处若在成品里缺席，说明有人手改 index.html 或忘了 build_html。
    try:
        tpl31 = read(build_html.TPL)
        java31 = read(JAVA)
        asset31 = read(ASSET)
        bad31 = []
        names_java = set(re.findall(r'String\s+F_\w+\s*=\s*"([^"]+\.json)"', java31))
        m31 = re.search(r"const BRIDGE_FILE\s*=\s*\{([^}]*)\}", tpl31)
        if not m31:
            raise ValueError("定位不到模板里的 BRIDGE_FILE 映射（改名或删除都会让探针失去对象）")
        names_js = set(re.findall(r":\s*'([^']+\.json)'", m31.group(1)))
        if not names_java:
            bad31.append("Java 侧一个 F_*.json 常量都没找到")
        elif names_js != names_java:
            bad31.append("分片文件名两侧不等：Java 独有 %s / JS 独有 %s"
                         % ("/".join(sorted(names_java - names_js)) or "无",
                            "/".join(sorted(names_js - names_java)) or "无"))
        for tag, src in (("模板", tpl31), ("成品", asset31)):
            if "unreadableSlices(sliceProbe(" not in src:
                bad31.append("%s的 boot 里没有读取闸门调用点" % tag)
            if "markBootFatal('read'" not in src:
                bad31.append("%s闸门没有标成 read 原因" % tag)
            if not re.search(r"\bread\s*:\s*'[^']+'", src):
                bad31.append("%s的 BF_REASON_LABEL 缺 read 标签" % tag)
        chk("S31", "分片文件名双侧同步：Java 常量 == BRIDGE_FILE / 闸门调用点在位 / read 有人话标签 · 产物同段",
            not bad31,
            "分片 %d 个: %s" % (len(names_js), ",".join(sorted(names_js))) if not bad31
            else " / ".join(bad31[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S31", "分片文件名双侧同步", False, e)

    # S32 逻辑债闸门（v0.28）：这一版修的是「不抛错也能把数据抹掉 / 跳过」的那一类，
    #     它们的坏法在界面上看不出来，只在真机丢一次账。每一条都对应一处承诺性的代码形状：
    #     将来有人顺手把守卫删了、或改了模板忘了 build_html（成品停在旧形状），静态层先红。
    #     判据按「函数体里必须/必须不许出现什么」来写，不比对整段文本（那会一改动就红，
    #     逼人不改守卫改门禁）。⚠ 不许把「无 ||数字」这条套到 profileCoefLine：
    #     它的注释里写着旧代码 `+p.bw||85`，字符串匹配会误伤（v3v LD7 就是这么假红过一次）。
    try:
        tpl32 = read(build_html.TPL)
        asset32 = read(ASSET)
        bad32 = []

        def _body32(name, s):
            m = re.search(r"^function " + name + r"\(", s, re.M)
            if not m:
                return None
            e = re.search(r"^}", s[m.start():], re.M)
            if not e:
                return s[m.start():]
            return s[m.start():m.start() + e.end()]

        # (函数, 必须出现, 不许出现)
        LEGS32 = [
            ("adoptImportedPlan",
             ["archErr=", "IMPORT_KEEP_KEYS", "ok!==true"], []),
            ("saveTele",
             ["if(bad.length)", "teleFieldOn(f.k)"], []),
            ("copyPrevTele",
             ["wn>1", "save(true)"], []),
            ("setJts", ["save()"], []),
            ("clearJts", ["save()"], []),
            ("planCapacity", [], [r"re:[|][|][0-9]"]),
            ("strengthMult", ["BW>0"], []),
            ("applyLatestE1", ["e1Usable("], []),
            ("e1ByWeek", ["+a.week||0"], []),
            ("saveProfile", ["round_step_kg"], []),
            ("importUnifiedCsv",
             ["不在当前结构里", "custom:true"], ["state.weeks[String(wkNum)]["]),
            ("startTimer",
             ["tierColor("], ["#E53935", "#1E88E5", "#43A047"]),
            ("applyChrome", ["stratCounts("], []),
            # v0.28 后半批（#14 / #16 / #9 / #10 / #27）：同一类「抄第二份默认值」的债
            ("matchReadyPct",
             ["READY["], ["100,90,80,70,55"]),
            ("matchReadyIndex",
             ["readyIndexFromScore("], ["score>=95"]),
            ("jtsToReady", ["readyIndexFromScore("], ["score>=95"]),
            ("setsOf", ["PROTO_FALLBACK"], ["?p.sets:3"]),
            ("proto", ["PROTO_FALLBACK"], []),
            ("dayIds", ["DEFAULT_DAY_IDS"], ["['A','B','C','D']"]),
            ("writeSlice", ["__lastWriteError=err"], []),
            ("watchStoreError",
             ["writeError("], ["if(!window.AndroidBridge||!AndroidBridge.lastStoreError) return"]),
            ("doExportCsv", ["String(e"], []),
            ("advCurWeek", ["parseInt"], []),
            ("readyIndexFromScore", ["READY_AT"], []),
            ("writeError", ["__lastWriteError"], []),
            ("refreshLangSelects",
             ["LANG_CACHED_SELECTS", "fillStratSelects(", "fillProgSelects("], []),
            ("setLang", ["refreshLangSelects("], []),
        ]
        for tag, src in (("模板", tpl32), ("成品", asset32)):
            for fn, must, forb in LEGS32:
                b = _body32(fn, src)
                if b is None:
                    bad32.append("%s里没有 %s()（改名或删除都会让整条腿失去判据）" % (tag, fn))
                    continue
                flat = b.replace(" ", "")
                for t in must:
                    if t.replace(" ", "") not in flat:
                        bad32.append("%s的 %s() 缺承诺片段 %s" % (tag, fn, t))
                for t in forb:
                    if t.startswith("re:"):
                        if re.search(t[3:], flat):
                            bad32.append("%s的 %s() 还留着兜底数字（%s）" % (tag, fn, t[3:]))
                    elif t.replace(" ", "") in flat:
                        bad32.append("%s的 %s() 出现了禁止形状 %s" % (tag, fn, t))
        # 档位取色表覆盖 TIER_CLASS：少一个键，HUD 圆点就退回 --t3 而无人报错
        for tag, src in (("模板", tpl32), ("成品", asset32)):
            mtt = re.search(r"window\.TIER_TOKEN\s*=\s*\{([^}]*)\}", src)
            mtc = re.search(r"const\s+TIER_CLASS\s*=\s*\{([^}]*)\}", src)
            if not mtt:
                bad32.append("%s里没有 window.TIER_TOKEN（内联取色的唯一出处）" % tag)
            elif not mtc:
                bad32.append("%s里没有 TIER_CLASS（没有可比对的键域）" % tag)
            else:
                k_tok = set(re.findall(r"([A-Za-z0-9_]+)\s*:", mtt.group(1)))
                k_cls = set(re.findall(r"([A-Za-z0-9_]+)\s*:", mtc.group(1)))
                if not k_cls <= k_tok:
                    bad32.append("%s的 TIER_TOKEN 覆盖不到 TIER_CLASS：%s"
                                 % (tag, "/".join(sorted(k_cls - k_tok)) or "无"))
        # 「只准有一份字面量」这条盯的是抄第二份默认值的那一刻：多了红、少了也红
        for tag, src in (("模板", tpl32), ("成品", asset32)):
            for lit, want, what in (
                ("['A','B','C','D','E','F']", 1, "训练日字母表"),
                ("['A','B','C','D']", 0, "四天兜底的手抄"),
                ("{T1:300,T2:150,T3:75,sound:true}", 1, "计时默认值"),
                ("[100,90,80,70,55]", 0, "就绪百分比的手抄"),
                ("score>=95", 0, "分数→档位阈值的手抄"),
                ("{sets:3,reps:10,rx:'3×10'}", 0, "处方兜底的手抄"),
            ):
                got = src.count(lit)
                if got != want:
                    bad32.append("%s里 %s 出现 %d 次（应为 %d 次）" % (tag, what, got, want))
        n_lit = 6
        n_legs = (len(LEGS32) + n_lit) * 2 + 2
        chk("S32", "逻辑债闸门：静默丢失守卫在位（拒收有人话 / 脏输入拒存 / 取色走令牌 / "
            "容量不手抄 / 导入不凭空造周 / 默认值只一份）· 产物同段",
            not bad32,
            "%d 条腿（%d 函数 + %d 份字面量，各 ×2 份）齐"
            % (n_legs, len(LEGS32), n_lit) if not bad32 else " / ".join(bad32[:8]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S32", "逻辑债闸门：静默丢失守卫在位", False, e)

    # S33 令牌可达 + 档位色板不外溢（v0.29 的 UI 债第一批）：
    #     两条都是「坏了没有任何东西会红」的那类。
    #     ① CSS 里 var(--名字) 写错，浏览器把整条声明丢掉 —— 界面只是「那个状态没反应」，
    #        不报错、不塌版。本次清出三处：--active（按下态从未生效过）、--fg 两处
    #        （审计行与迷你钮的文字色一直是继承来的），还有一个 var(--warn,#F0C060)
    #        靠兜底字面量活着，令牌块从来没声明过 warn。
    #     ② 档位色（t1/t2/t3/rts/dl）与警示色的「浅底文字色 / 深端 / 反白」抄在规则里，
    #        令牌块换不动它：症状是换到纸底主题，徽标跟着变深了，按钮文字与 AMRAP
    #        提示还是暗色那套（在白底上等于看不见）。
    #     判据：色号在 <style> 里只准出现在令牌块内；JS 里一个都不准出现
    #     （#1A1200 例外 —— PLATES 那五行是杠铃片的物理配色，不跟主题走，属另一套承诺）。
    try:
        tpl33 = read(build_html.TPL)
        prod33 = read(ASSET)
        bad33 = []

        off33, css33 = style_span(tpl33, "模板")
        cssp = strip_css_comments(css33)
        # JS 段：style 之外的一切都算（本检查只管色号，不解析脚本边界）
        js33 = strip_css_comments(tpl33[:off33] + tpl33[off33 + len(css33):])
        js33 = re.sub(r"//[^\n]*", " ", js33)

        decl33 = set(re.findall(r"(--[A-Za-z0-9_-]+)\s*:", cssp))
        decl33 |= set(re.findall(r"setProperty\(\s*'(--[A-Za-z0-9_-]+)'", tpl33))
        refs33 = set(re.findall(r"var\(\s*(--[A-Za-z0-9_-]+)", cssp))
        if not decl33:
            bad33.append("样式里一个自定义属性声明都没抓到（判据抓不到东西）")
        for t in sorted(refs33 - decl33):
            bad33.append("CSS 引用了没有声明的令牌 %s（整条声明会被丢弃，界面表现为「没反应」）" % t)

        # 令牌块跨度：:root 与每个 html[data-theme=…]，都按花括号配对算出区间
        spans33 = []
        for m in re.finditer(r"(?m)^(:root|html\[data-theme=\"[a-z]+\"\])\s*\{", cssp):
            depth, k = 0, m.end() - 1
            while k < len(cssp):
                if cssp[k] == "{":
                    depth += 1
                elif cssp[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            spans33.append((m.end(), k))
        if not spans33:
            bad33.append("抓不到任何令牌块（:root / html[data-theme=…] 的形状变了）")

        PALS = ["#F0C060", "#FF9C98", "#9CCBFF", "#9BE4A5", "#1A1200"]
        for lit in PALS:
            for m in re.finditer(re.escape(lit), cssp, re.I):
                if not any(a <= m.start() < b for a, b in spans33):
                    bad33.append("%s 抄在令牌块外的规则里（主题换不动它）" % lit)
        for lit in [p for p in PALS if p != "#1A1200"]:
            if re.search(re.escape(lit), js33, re.I):
                bad33.append("%s 出现在 JS 里（内联色只能取令牌或注册表）" % lit)

        # 这次收口新给的令牌必须真有人用：只声明不引用 = 下一个主题照着抄一份死值
        CONSUMED = ["--t1-ink", "--t2-ink", "--t3-ink", "--t1-deep", "--t2-deep", "--t3-deep",
                    "--dl-deep", "--rts-deep", "--on-rts", "--on-gold", "--warn",
                    "--warn-soft", "--warn-line", "--t3-line", "--rts-line", "--on-accent"]
        for t in CONSUMED:
            if t not in decl33:
                bad33.append("令牌块里没有 %s（没有出处，引用它等于引用暗色那份）" % t)
            if cssp.count("var(%s" % t) == 0:
                bad33.append("%s 声明了但全样式没人引用（要么接线，要么删掉）" % t)

        if style_span(prod33, "成品")[1] != css33:
            bad33.append("成品 <style> 段与模板不同（改了模板没重建，或手改了产物）")

        chk("S33", "令牌可达 + 档位色板不外溢：CSS 引用的令牌都有声明 / 色号只在令牌块 / "
            "JS 无档位色号 / 本批令牌有人用 · 产物同段",
            not bad33,
            "%d 个声明 / %d 个引用 / 色板 %d 个色号只在 %d 个令牌块内"
            % (len(decl33), len(refs33), len(PALS), len(spans33))
            if not bad33 else " / ".join(bad33[:8]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S33", "令牌可达 + 档位色板不外溢", False, e)

    # S34 分段器段数单源（v0.29 的 UI 债第二批）：语言 / 主题两个开关原先把「有几段」抄了四份
    #     —— CSS 里两段一套数、三段另一套（.three 特例），thumb 宽按档数各算一次，
    #     markup 的 class 再点一次档，JS 的 on-k 类名枚举第四次。注册表加第四个主题那天，
    #     漏补特例的症状是滑块停在上一格、宽度还是三段宽，界面一声不吭；补了则是把抄本再抄一遍。
    #     判据：段数只有一个出处 = DOM 里真实的按钮数（segThumb 现量后写进 --seg-n / --seg-i），
    #     CSS 的尺寸与位移只吃这两个变量；样式里再出现 .seg-pill.<档数> 式特例即红，
    #     JS 里再出现 on-k 类名枚举即红，markup 里每个分段器都要被 segThumb 的调用点覆盖。
    #     与行为侧不重叠（各看得见另一层看不见的那一类坏法）：注入 F39 把宽度抄回三段那个
    #     实测值只红这里（两段/三段的滑块几何都自洽，量像素看不出），F40 把格位写成 i+1
    #     只红 uiv X1+X3c / v3v W5（形状腿照旧全绿，顶出面板的那一格只有真浏览器量得到）。
    try:
        tpl34 = read(build_html.TPL)
        prod34 = read(ASSET)
        bad34 = []
        css34 = strip_css_comments(style_span(tpl34, "模板")[1])

        pill = css_rule(css34, ".seg-pill")
        thumb = css_rule(css34, ".seg-pill .thumb")
        if pill is None or thumb is None:
            bad34.append("取不到 .seg-pill 或 .seg-pill .thumb 规则（选择器形状变了，判据抓不到东西）")

        def _decl(body, prop):
            m = re.search(r"(?:^|;)\s*%s\s*:\s*([^;]*)" % re.escape(prop), body or "")
            return m.group(1).strip() if m else None

        if pill is not None and thumb is not None:
            for tok in ("--seg-n", "--seg-i"):
                if not re.search(re.escape(tok) + r"\s*:", pill):
                    bad34.append(".seg-pill 规则里没有 %s 的默认值（变量没有出处时整条声明会被丢弃）" % tok)
            w1, w2, tf = _decl(pill, "width"), _decl(thumb, "width"), _decl(thumb, "transform")
            for nm, val in (("分段器宽度", w1), ("滑块宽度", w2)):
                if not val or "var(--seg-n)" not in val:
                    bad34.append("%s「%s」不是按 var(--seg-n) 算的（档数又写死了）" % (nm, val))
            if not tf or "var(--seg-i)" not in tf:
                bad34.append("滑块位移「%s」不是按 var(--seg-i) 算的（格位又写死了）" % tf)
            for sel in re.findall(r"\.seg-pill\.[A-Za-z0-9_-]+", css34):
                bad34.append("样式里回来了按档数/格位写死的特例 %s（新档位要回来补一条，补漏即静默错位）" % sel)

        fn34 = js_fn_body(tpl34, "segThumb")
        if fn34 is None:
            bad34.append("取不到 segThumb 函数体")
        else:
            if "querySelectorAll('button').length" not in fn34:
                bad34.append("segThumb 没从 DOM 的按钮数现量段数（段数没有唯一出处）")
            for tok in ("--seg-n", "--seg-i"):
                if "setProperty('%s'" % tok not in fn34:
                    bad34.append("segThumb 没写 %s（CSS 那边只能吃写死的档数）" % tok)
            for forb in ("classList.add('on-", "classList.remove('on-"):
                if forb in fn34:
                    bad34.append("segThumb 里还有类名枚举 %s（格位要靠属性而不是靠枚举第几档）" % forb)

        ids34 = set(re.findall(r'<div class="seg-pill"\s+id="([A-Za-z0-9_]+)"', tpl34))
        bare = re.findall(r'class="seg-pill\s+[^"]*"', tpl34)
        calls = set(re.findall(r"segThumb\(\s*'([A-Za-z0-9_]+)'", tpl34))
        if not ids34:
            bad34.append("markup 里抓不到任何分段器（class=\"seg-pill\" 的写法变了，判据抓不到东西）")
        if bare:
            bad34.append("分段器元素上还挂着别的 class（档数抄在 markup 里就是第二份出处）：%s" % bare[0])
        if not calls:
            bad34.append("抓不到 segThumb 的调用点")
        for miss in sorted(ids34 - calls):
            bad34.append("#%s 没有对应的 segThumb 调用（它的段数永远停在默认值）" % miss)
        for extra in sorted(calls - ids34):
            bad34.append("segThumb('%s') 点名的分段器在 markup 里不存在" % extra)

        if "setProperty('--seg-i'" not in prod34 or "querySelectorAll('button').length" not in prod34:
            bad34.append("成品里没有这份派生接线（改了模板没重建，或手改了产物）")

        chk("S34", "分段器段数单源：段数取自 DOM 按钮数 / 尺寸与位移只吃 --seg-n 与 --seg-i / "
            "CSS 无档数特例 / markup 与 segThumb 调用点一一对齐 · 产物同接线",
            not bad34,
            "%d 个分段器（%s）/ 调用点 %d 处 / CSS 特例 0 条"
            % (len(ids34), "/".join(sorted(ids34)), len(calls))
            if not bad34 else " / ".join(bad34[:8]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S34", "分段器段数单源", False, e)

    # S35 计时时长单源（v0.29 的 UI 债第二批）：HUD 三颗档钮与设置副标题原先把
    #     「5m / 2.5m / 75s」抄在文案里，而真正生效的是 defaultTimerCfg() 那三个秒数 ——
    #     默认值一改（或老存档带着别的秒数升上来），按钮写着 5 分钟、点下去是别的时长，
    #     用户只会觉得计时器不准；没有任何回归量过这两个数对不对得上。
    #     判据（形状侧）：① 模板与成品里不许再出现时长抄本（先等长去注释，散文里的
    #     名字不算抄本）；② 秒数只准出现在 defaultTimerCfg 那一处；③ 派生三件套
    #     fmtDur / fmtDurZh / paintTimerChips 在位，paintTimerChips 真的写三颗档钮与
    #     #setTimerS，且 applyChrome 调它（切语言/首帧/迁档都走这条）；④ 档钮的 onclick
    #     仍从 state.timerCfg 取秒数，不是裸数字；⑤ 成品同接线。
    #     行为侧（v3v TD1 真改 cfg 看文案跟不跟、uiv X4c 点下去三方对账）看得见算错的那一半：
    #     注入 F41 把抄本请回 i18n 表只红这里（抄本被派生写覆盖，行为一模一样），
    #     F42 把 fmtDur 的秒/分界限改坏只红 TD1+X4c（形状腿认不出哪个界限对）。
    try:
        tpl35 = read(build_html.TPL)
        prod35 = read(ASSET)
        bad35 = []
        bare35 = re.sub(r"(?m)//[^\n]*", " ", strip_css_comments(tpl35))

        COPY = ["5分钟", "2.5分钟", "75秒", "·5m", "·2.5m", "·75s"]
        for lit in COPY:
            if lit in bare35:
                bad35.append("模板里还有时长抄本「%s」（数字只准从 state.timerCfg 现算）" % lit)
            if lit in re.sub(r"(?m)//[^\n]*", " ", strip_css_comments(prod35)):
                bad35.append("成品里还有时长抄本「%s」" % lit)
        if bare35.count("{T1:300") != 1:
            bad35.append("秒数出现 %d 次（defaultTimerCfg 之外又抄了一份）" % bare35.count("{T1:300"))

        paint35 = js_fn_body(bare35, "paintTimerChips")
        if paint35 is None or js_fn_body(bare35, "fmtDur") is None or js_fn_body(bare35, "fmtDurZh") is None:
            bad35.append("取不到 fmtDur / fmtDurZh / paintTimerChips（时长换算又回文案里了）")
        else:
            if "getElementById('chip'+t)" not in paint35:
                bad35.append("paintTimerChips 没按 #chipT1/T2/T3 逐个写档钮")
            if "getElementById('setTimerS')" not in paint35:
                bad35.append("paintTimerChips 没写设置副标题 #setTimerS")
            for fn in ("fmtDur", "fmtDurZh"):
                if not re.search(r"\b%s\b" % fn, paint35):
                    bad35.append("paintTimerChips 没走 %s（时长换算又在这里拼了一份）" % fn)
        chrome35 = js_fn_body(bare35, "applyChrome")
        if chrome35 is None:
            bad35.append("取不到 applyChrome 函数体")
        elif "paintTimerChips()" not in chrome35:
            bad35.append("applyChrome 没调 paintTimerChips（首帧与切语言都不会刷档钮）")

        for t in ("T1", "T2", "T3"):
            if 'id="chip%s"' % t not in bare35:
                bad35.append("markup 里没有 #chip%s 这颗档钮" % t)
            if "startTimer(state.timerCfg.%s,'%s')" % (t, t) not in bare35:
                bad35.append("#chip%s 的 onclick 不从 state.timerCfg 取秒数" % t)
        for need in ("function paintTimerChips(", 'id="chipT1"'):
            if need not in prod35:
                bad35.append("成品里没有「%s」（改了模板没重建，或手改了产物）" % need)

        chk("S35", "计时时长单源：模板与成品无时长抄本 / 秒数只在 defaultTimerCfg / "
            "换算与刷新的三件套在位且 applyChrome 调用 / 档钮 onclick 从 state.timerCfg 取 · 产物同接线",
            not bad35,
            "抄本 0 处 / 秒数出处 1 处 / 档钮 3 颗（T1·T2·T3）都从 state.timerCfg 取数"
            if not bad35 else " / ".join(bad35[:8]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S35", "计时时长单源", False, e)

    # S36 内联事件里没有死按钮（v0.29 的 UI 债第三批）：全站两百多处 on*="…" 里，
    #     动作选择链（编辑器 mv-btn → openBrowse('pick') → brGo 逐层下钻 → pickAct 落账）
    #     是唯一「按钮藏在 JS 拼出来的字符串里」的入口。onclick 目标被改名、处理函数被删、
    #     模式参数抄错，浏览器里的表现都一样：点一下什么也没有 —— 不报错、不崩、
    #     界面看不出问题，用户只会以为这个 app 没做完。以前只有 S14 手工点名了
    #     导入导出那几条腿，剩下的内联站点没人核对过函数名。
    #     判据：① 扫模板与成品里每个 on*="…" 属性值（markup 与 JS 拼串同为双引号，一并抓到），
    #     取出「前面不是点/标识符字符、后面紧跟左括号」的调用名根，逐个必须能在**同一份源码**
    #     里找到 function / const / let / var / window. 的声明。先等长去注释：说明文字里
    #     提到的名字不算引用（S22 那条教训）。
    #     ② mv-btn 这条腿额外核对**模式字面量**是 'pick'。两套回归都直接调
    #     openBrowse('pick')，把 markup 里的模式改成 'manage' 时它们照旧全绿 ——
    #     只有静态侧认得出「用户点的那颗钮进的是管理态」。
    #     ③ 扫描完整性：一条属性都没抓到 = 属性写法变了 = 判据在空转，一律判红。
    #     反向验证：F43 把 oninput="brSearch(this.value)" 的引用改名（两套回归都直接调
    #     brSearch，看不见 markup 里的引用死了）；F44 把 mv-btn 的模式抄成 'manage'。
    try:
        tpl36 = read(build_html.TPL)
        prod36 = read(ASSET)
        bad36 = []
        # 平台全局：内联事件里合法可调、但不归本项目声明的那几个。逐个都要有理由，
        # 空着写等于给将来的误报埋雷 —— 新增前先想这条腿是不是真会写在 onclick 里。
        GLOBALS = {"alert", "confirm", "setTimeout", "clearTimeout",
                   "setInterval", "clearInterval", "encodeURIComponent",
                   "decodeURIComponent", "parseInt", "parseFloat", "isNaN", "isFinite"}
        KEYWORDS = {"if", "for", "while", "switch", "return", "typeof",
                    "function", "catch", "new", "do", "else"}

        def handler_scan(tag, src):
            bare = re.sub(r"(?m)//[^\n]*", " ", strip_css_comments(src))
            found = re.findall(r'\bon[a-z]+\s*=\s*"([^"]*)"', bare)
            if not found:
                return False, tag + ": 一条内联事件都没抓到（属性写法变了，这条判据在空转）"
            decl = set(re.findall(r"function\s+([A-Za-z_$][\w$]*)\s*\(", bare))
            decl |= set(re.findall(r"(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=", bare))
            decl |= set(re.findall(r"window\.([A-Za-z_$][\w$]*)\s*=", bare))
            dead, roots = {}, set()
            for val in found:
                for m in re.finditer(r"(?<![\w.$])([A-Za-z_$][\w$]*)\s*\(", val):
                    nm = m.group(1)
                    roots.add(nm)
                    if nm in decl or nm in KEYWORDS or nm in GLOBALS:
                        continue
                    dead[nm] = dead.get(nm, 0) + 1
            if dead:
                return False, (tag + ": " + " / ".join("%s（引 %d 处）" % (k, v)
                                                       for k, v in sorted(dead.items())))
            if 'mv-btn" onclick="openBrowse(\'pick\')' not in bare:
                return False, tag + ": mv-btn 的入口不是 openBrowse('pick')（用户点的那颗钮进的不是选择态）"
            return True, tag + ": %d 处内联事件 / %d 个调用名全在位" % (len(found), len(roots))

        reports = [handler_scan("模板", tpl36), handler_scan("成品", prod36)]
        chk("S36", "内联事件指向的函数全在位：站点级逐个核对调用名 / mv-btn 走 pick 模式 · "
            "模板与成品同扫（死按钮点了没反应，不报错也不崩）",
            all(r[0] for r in reports), " | ".join(r[1] for r in reports))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S36", "内联事件指向的函数全在位", False, e)

    # S37 器械名单单源（v0.31 节点③c）：六类 kind 只在 RPL-Gear-v1.json 里写一遍。
    #     加一类是改契约的事，模板里任何一份手抄名单都会让「六类全真」变成五类半 ——
    #     而 chip 少一颗、strip 少一条分支这种错，不抛错、也不被别的检查覆盖。
    try:
        tpl37 = read(os.path.join(HERE, "template.html"))
        prod37 = read(ASSET)
        gear37 = json.loads(read(build_html.GEAR_SCHEMA))
        kinds37 = [k.get("id") for k in gear37.get("kinds", [])]
        bad37 = []
        roster37 = "const GEAR_KINDS = GEAR_SCHEMA.kinds.map(function(k){ return k.id; });"
        if len(kinds37) != 6 or len(set(kinds37)) != 6:
            bad37.append("契约 kinds 不是 6 个唯一键：%s" % kinds37)
        if roster37 not in tpl37:
            bad37.append("GEAR_KINDS 未从契约派生")
        gs37 = re.search(r"function gearStripText\(gv\)\{(.*?)\n\}", tpl37, re.S)
        cases37 = []
        if not gs37:
            bad37.append("gearStripText 段取不到")
        else:
            cases37 = re.findall(r"case '([a-z]+)':", gs37.group(1))
            outside37 = [c for c in cases37 if c not in kinds37]
            if outside37:
                bad37.append("gearStripText 有契约外分支：%s" % ",".join(outside37))
            if len(cases37) < 4:
                bad37.append("gearStripText 分支少于 4（%d）" % len(cases37))
        gc37 = re.search(r"function renderGearChips\(\)\{(.*?)\n\}", tpl37, re.S)
        if not gc37:
            bad37.append("renderGearChips 段取不到")
        else:
            body37 = gc37.group(1)
            if "GEAR_SCHEMA.kinds.map" not in body37:
                bad37.append("renderGearChips 未从契约 kinds 长出来")
            lits37 = [k for k in kinds37 if ("'" + k + "'") in body37]
            if lits37:
                bad37.append("renderGearChips 手抄 kind 字面量：%s" % ",".join(lits37))
        bh37 = read(os.path.join(HERE, "build_html.py"))
        if build_html.GEAR_MARKER not in tpl37:
            bad37.append("模板缺 GEAR_SCHEMA 注入标记")
        if "GEAR_SCHEMA" not in bh37 or "gear=%s" not in bh37:
            bad37.append("build_html 缺 gear 指纹位（改契约必须让指纹变）")
        if roster37 not in prod37:
            bad37.append("成品与模板的名单派生段不一致")
        chk("S37", "器械名单单源：契约 kinds / GEAR_KINDS / strip 分支 / chips 四处对齐 · 注入与指纹成对 · 产物同段",
            not bad37,
            "OK（%d 类 / switch %d 分支 / chips 手抄 0）" % (len(kinds37), len(cases37))
            if not bad37 else " / ".join(bad37[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S37", "器械名单单源", False, e)

    # S38 Resolver 纪律（v0.31 节点③c）：配片只能被 Resolver 调，全局杆重/赛扣不许回到 UI 算式，
    #     步进按钮只报倍数、文案由 stepOf 现写。三处任一被"顺手简化"回去，六类器械就退化成
    #     「所有动作都按杠铃算」——而且不报错，只是哑铃重量和自重净负荷一起错。
    try:
        tpl38 = read(os.path.join(HERE, "template.html"))
        bad38 = []
        n38 = len(re.findall(r"platesPerSide\(", tpl38))
        if n38 != 3:
            bad38.append("platesPerSide 出现 %d 次（应 3：注释 / 定义 / Resolver 内 1 次调用）" % n38)
        if "const pk=platesPerSide(raw, g.collarOn, g.barKg, g.collarPairKg, inv);" not in tpl38:
            bad38.append("Resolver 内唯一调用点漂了")
        lines38 = tpl38.splitlines()
        # 现存合法调用点逐一列全：配片兜底、场地默认开关、热身数字路径、设置页、杆重下拉。
        allowed38 = {"platesPerSide", "toggleCollars", "warmups", "renderSettings",
                     "fillBarSelects", "barKg", "collarsOn"}
        owners38 = []
        for i38, l38 in enumerate(lines38):
            if not re.search(r"\bbarKg\(\)|\bcollarsOn\(\)", l38):
                continue
            owner38 = None
            for j38 in range(i38, -1, -1):
                m38 = re.match(r"function\s+([A-Za-z0-9_]+)\s*\(", lines38[j38])
                if m38:
                    owner38 = m38.group(1)
                    break
            owners38.append(owner38 or "?")
            if owner38 not in allowed38:
                bad38.append("第 %d 行全局 barKg()/collarsOn() 落在 %s（白名单外）" % (i38 + 1, owner38 or "?"))
        step38 = re.findall(r"id=\"edStep(?:M2|M1|P1|P2)\"[^>]*onclick=\"([^\"]+)\"", tpl38)
        if len(step38) != 4 or any(not re.fullmatch(r"stepLoad\(-?[12]\)", x) for x in step38):
            bad38.append("编辑器步进按钮不是 ±1/±2 倍数调用：%s" % step38)
        if re.search(r"stepLoad\([^)]*[0-9]+\.[0-9]", tpl38):
            bad38.append("stepLoad 调用里出现小数 kg 字面量")
        card38 = "onclick=\"quickLoad(event,'+i+',1)\">+'+fmtStep(stepOf(e))+'</button>'"
        if card38 not in tpl38:
            bad38.append("首页步进按钮文案不是 fmtStep(stepOf(e)) 现写")
        chk("S38", "Resolver 纪律：platesPerSide 只在 Resolver / 全局杆重·赛扣只在白名单 / 步进按钮无 kg 字面量",
            not bad38,
            "OK（platesPerSide %d 处 / 全局调用 %d 处全在白名单 / 步进 4 颗）" % (n38, len(owners38))
            if not bad38 else " / ".join(bad38[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S38", "Resolver 纪律", False, e)

    # S39 迁移与分片（v0.31 节点③c，v0.44 起闸门是 V8）：场地库存进 prefs 且导入时保留、
    #     不进账本分片；v8 迁移在一次性闸门内且内部串 V7（v7 换算仍只在 V7 的闸门内、
    #     首建不换算）；v1+v2 四份旧契约冻结（哈希对 git HEAD），v3 是现行版不入冻结名单。
    try:
        tpl39 = read(os.path.join(HERE, "template.html"))
        bad39 = []

        def keys39(nm):
            m39 = re.search(r"const %s=\[(.*?)\];" % nm, tpl39, re.S)
            return re.findall(r"'([A-Za-z0-9_]+)'", m39.group(1)) if m39 else None

        pref39, imp39, work39 = keys39("PREF_KEYS"), keys39("IMPORT_KEEP_KEYS"), keys39("WORK_KEYS")
        if not pref39 or not imp39 or work39 is None:
            bad39.append("三份键名单有一份取不到")
        else:
            for k39 in ("venues", "activeVenueId"):
                if k39 not in pref39:
                    bad39.append(k39 + " 不在 PREF_KEYS")
                if k39 not in imp39:
                    bad39.append(k39 + " 不在 IMPORT_KEEP_KEYS")
                if k39 in work39:
                    bad39.append(k39 + " 误入 WORK_KEYS")
        if "if(sv<SCHEMA_STAMP) migrateStateV8(state);" not in tpl39:
            bad39.append("migrateStateV8 不在 sv<SCHEMA_STAMP 闸门内")
        m39v8 = re.search(r"function migrateStateV8\(s, fresh\)\{(.*?)\n\}", tpl39, re.S)
        if not m39v8:
            bad39.append("migrateStateV8 函数体取不到")
        elif "migrateStateV7(s, fresh);" not in m39v8.group(1):
            bad39.append("migrateStateV8 没串 migrateStateV7（v7 旧档将跳过换算）")
        fr39 = re.search(r"if\(fresh\)\{(.*?)\}else\{(.*?)\n    \}", tpl39, re.S)
        if not fr39:
            bad39.append("fresh / else 结构取不到")
        else:
            if "v7ConvertLoads" in fr39.group(1):
                bad39.append("fresh 首建分支竟做换算")
            if "v7ConvertLoads(s, bk, rep);" not in fr39.group(2):
                bad39.append("非 fresh 分支缺 v7ConvertLoads")
        for rel39 in ("mobile/tools/schema/RPL-Plan-v1.json", "mobile/tools/schema/RPL-Exchange-v1.json",
                      "mobile/tools/schema/RPL-Plan-v2.json", "mobile/tools/schema/RPL-Exchange-v2.json"):
            p39 = os.path.join(ROOT, rel39)
            try:
                h39 = subprocess.run(["git", "hash-object", p39], cwd=ROOT,
                                     capture_output=True, text=True).stdout.strip()
                g39 = subprocess.run(["git", "rev-parse", "HEAD:" + rel39], cwd=ROOT,
                                     capture_output=True, text=True).stdout.strip()
                if not h39 or not g39 or h39 != g39:
                    bad39.append(rel39.split("/")[-1] + " 与 git HEAD 不一致（契约永不就地改）")
            except OSError as ee:
                bad39.append(rel39 + " 取不到 git 哈希：" + str(ee))
        chk("S39", "迁移与分片：venues 双登记且不入 WORK_KEYS / v8 闸门在位且串 v7、fresh 不换算 / 四份旧契约哈希 == HEAD",
            not bad39,
            "OK（prefs %d 键 / keep %d 键 / 冻结契约 4 份）" % (len(pref39 or []), len(imp39 or []))
            if not bad39 else " / ".join(bad39[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S39", "迁移与分片", False, e)

    # S40 Plan/Exchange v3 超集（v0.44 节点①，接替旧 v2 超集检查）：v3 只许是 v2 的
    #     「八表换代超集」——合法差异仅限：schema_ver / title / notes / accepted_schema_vers
    #     （前置 v3 + 补 '3'/'2' 短别名）/ sheet_order（Armor 原位换 GPP、末尾 +Level）/
    #     legacy_compat（v2 单条清单 → v3 entries[] 两条）/ seed（aux→gpp 改名）/
    #     state_defaults_on_import（+gppDays/levelSnap）/ sheets（-Armor，+GPP+Level，
    #     Profile 只加三小项两字段且 ohp_1rm 只许改 desc，Days 只许改 weekday_labels_note，
    #     Blocks/Workouts/Telemetry/Gear 逐字节等 v2）。
    #     另查：build_html 双指针必须落在 v3（改回 v2 也红）；legacy_compat.entries 两条
    #     分别与 v1/v2 的 accepted+sheet_order 逐字节等；GPP/Level/legacy_armor.spec 三张
    #     新形状自洽（列名不手抄，全部由契约自身部件拼出核对）；26 列台账冻结
    #     （record_keys_frozen 逐字节等 v2）；信封除版本四键外逐键等 v2、accepted 含三版本、
    #     csv_protocol_current='2' 且在 accepted 里。见证腿在 _sabotage_m3 F4/F5 与 v0.44 新注入。
    try:
        bad40 = []
        plan1p = os.path.join(HERE, "schema", "RPL-Plan-v1.json")
        plan2p = os.path.join(HERE, "schema", "RPL-Plan-v2.json")
        plan3p = os.path.join(HERE, "schema", "RPL-Plan-v3.json")
        exc2p = os.path.join(HERE, "schema", "RPL-Exchange-v2.json")
        exc3p = os.path.join(HERE, "schema", "RPL-Exchange-v3.json")
        for nm40, pth40 in (("RPL-Plan-v3", plan3p), ("RPL-Exchange-v3", exc3p)):
            if not os.path.isfile(pth40):
                bad40.append(nm40 + ".json 不在位")
        if os.path.basename(str(build_html.PLAN_SCHEMA)) != "RPL-Plan-v3.json":
            bad40.append("build_html.PLAN_SCHEMA 没指向 v3")
        if os.path.basename(str(build_html.EXCHANGE_SCHEMA)) != "RPL-Exchange-v3.json":
            bad40.append("build_html.EXCHANGE_SCHEMA 没指向 v3")
        if not bad40:
            p1 = json.loads(read(plan1p))
            p2 = json.loads(read(plan2p))
            p3 = json.loads(read(plan3p))
            e2 = json.loads(read(exc2p))
            e3 = json.loads(read(exc3p))
            jd = lambda o: json.dumps(o, sort_keys=True, ensure_ascii=False)
            if p3.get("schema_ver") != "RPL-Plan-v3":
                bad40.append("Plan v3 schema_ver=%r" % p3.get("schema_ver"))
            acc3 = p3.get("accepted_schema_vers") or []
            if not acc3 or acc3[0] != "RPL-Plan-v3":
                bad40.append("accepted_schema_vers 没把 v3 放首位")
            if not set(p2.get("accepted_schema_vers") or []) <= set(acc3):
                bad40.append("accepted_schema_vers 丢了 v2 世代的别名")
            if p3.get("sheet_order") != ["GPP" if s40 == "Armor" else s40
                                         for s40 in (p2.get("sheet_order") or [])] + ["Level"]:
                bad40.append("sheet_order 不是 v2 七表 Armor→GPP 原位换代 + 末尾 Level")
            allow40 = {"schema_ver", "title", "notes", "accepted_schema_vers", "sheet_order",
                       "legacy_compat", "seed", "state_defaults_on_import", "sheets"}
            for k40 in p2:
                if k40 in allow40:
                    continue
                if jd(p2[k40]) != jd(p3.get(k40)):
                    bad40.append("Plan v3 键 '%s' 与 v2 分叉（不在合法差异清单）" % k40)
            # seed：只许 aux→gpp 改名（note 允许改词）
            s2s, s3s = dict(p2.get("seed") or {}), dict(p3.get("seed") or {})
            for k40 in ("required_keys", "invariant_keys", "payload_keys", "generated_by"):
                want40 = ["gpp" if x40 == "aux" else x40 for x40 in (s2s.get(k40) or [])] \
                    if k40 != "generated_by" else s2s.get(k40)
                if s3s.get(k40) != want40:
                    bad40.append("seed.%s 不是 v2 名单的 aux→gpp 改名" % k40)
            # state_defaults：只许加 gppDays/levelSnap 两条
            d2s, d3s = p2.get("state_defaults_on_import") or {}, p3.get("state_defaults_on_import") or {}
            if set(d3s) - set(d2s) != {"gppDays", "levelSnap"}:
                bad40.append("state_defaults 新增键不是恰好 gppDays+levelSnap：%s" % sorted(set(d3s) - set(d2s)))
            for k40 in d2s:
                if jd(d2s[k40]) != jd(d3s.get(k40)):
                    bad40.append("state_defaults 键 '%s' 与 v2 分叉" % k40)
            # sheets：-Armor，+GPP+Level；四张共有表逐字节等；Profile/Days 白名单式放宽
            sh2, sh3 = p2.get("sheets") or {}, p3.get("sheets") or {}
            if set(sh3) - set(sh2) != {"GPP", "Level"} or set(sh2) - set(sh3) != {"Armor"}:
                bad40.append("表差集不是 -Armor/+GPP+Level：%s / %s"
                             % (sorted(set(sh3) - set(sh2)), sorted(set(sh2) - set(sh3))))
            for shn40 in sorted(set(sh2) & set(sh3)):
                if shn40 in ("Profile", "Days"):
                    continue
                if jd(sh2[shn40]) != jd(sh3[shn40]):
                    bad40.append("表 '%s' 与 v2 分叉" % shn40)
            pr2, pr3 = sh2.get("Profile") or {}, sh3.get("Profile") or {}
            for k40 in pr2:
                if k40 == "fields":
                    continue
                if jd(pr2[k40]) != jd(pr3.get(k40)):
                    bad40.append("Profile.%s 与 v2 分叉" % k40)
            f2, f3 = pr2.get("fields") or {}, pr3.get("fields") or {}
            if set(f3) - set(f2) != {"pullup_added_kg", "dip_added_kg"}:
                bad40.append("Profile 新增字段不是恰好三小项两个：%s" % sorted(set(f3) - set(f2)))
            for k40 in f2:
                a40, b40 = dict(f2[k40]), dict(f3.get(k40) or {})
                a40.pop("desc", None)
                b40.pop("desc", None)
                if jd(a40) != jd(b40):
                    bad40.append("Profile 字段 '%s' 除 desc 外与 v2 分叉" % k40)
            dy2, dy3 = sh2.get("Days") or {}, sh3.get("Days") or {}
            for k40 in dy2:
                if k40 == "weekday_labels_note":
                    continue
                if jd(dy2[k40]) != jd(dy3.get(k40)):
                    bad40.append("Days.%s 与 v2 分叉" % k40)
            # legacy_compat.entries：两条清单逐字节等 v1/v2 的人读事实源
            ents40 = ((p3.get("legacy_compat") or {}).get("entries")) or []
            if len(ents40) != 2:
                bad40.append("legacy_compat.entries 不是恰好 2 条")
            else:
                if ents40[0].get("plan_schema_vers") != p1.get("accepted_schema_vers") \
                        or ents40[0].get("sheet_order") != p1.get("sheet_order"):
                    bad40.append("entries[0] 与 v1 契约的 accepted/sheet_order 不等")
                if (ents40[1].get("plan_schema_vers") or [None])[0] != p2.get("schema_ver") \
                        or ents40[1].get("sheet_order") != p2.get("sheet_order"):
                    bad40.append("entries[1] 与 v2 契约的 schema_ver/sheet_order 不等")
                for en40 in ents40:
                    if "GPP" in (en40.get("sheet_order") or []):
                        bad40.append("legacy 表序里不该出现 GPP（旧档只有 Armor）")
            # GPP 表自洽（列名全部由契约部件拼核对，不手抄）
            g3 = sh3.get("GPP") or {}
            cols40 = g3.get("columns") or []
            dm40 = g3.get("done_mask") or {}
            if cols40[:2] + (g3.get("definition_columns") or []) + (g3.get("weekly_columns") or []) != cols40:
                bad40.append("GPP columns != week+item_idx+定义列+每周列 的顺序拼接")
            if set(g3.get("definition_columns") or []) & set(g3.get("weekly_columns") or []):
                bad40.append("GPP 定义列与每周列有交集")
            if dm40.get("column") not in cols40 or dm40.get("column") not in (g3.get("weekly_columns") or []):
                bad40.append("done_mask.column 不在 GPP 每周列里")
            if dm40.get("state_key") != "done" or dm40.get("len") != 7:
                bad40.append("done_mask 的 state_key/len 不是 done/7")
            for k40 in list(g3.get("required") or []) + list(g3.get("unique") or []) \
                    + list((g3.get("ranges") or {}).keys()) + list((g3.get("role_columns") or {}).values()):
                if k40 not in cols40:
                    bad40.append("GPP 的 %r 不在 columns 里" % k40)
            spec40 = ((g3.get("legacy_armor") or {}).get("spec")) or {}
            spc40 = spec40.get("columns") or []
            dayc40 = spec40.get("day_columns") or []
            if set(spc40) != {"week", "item_idx", "domain", "item", "target", "intensity"} | set(dayc40):
                bad40.append("legacy_armor.spec.columns 不是 6 固定列 + day_columns")
            if len(dayc40) != dm40.get("len"):
                bad40.append("legacy_armor day_columns 位数与 done_mask.len 不等")
            for k40 in list(spec40.get("required") or []) + list(spec40.get("unique") or []) \
                    + list((spec40.get("keys") or {}).keys()) + list((spec40.get("role_columns") or {}).values()):
                if k40 not in spc40:
                    bad40.append("legacy_armor.spec 的 %r 不在其 columns 里" % k40)
            # Level 表自洽
            lv3 = sh3.get("Level") or {}
            lvc40 = lv3.get("columns") or []
            if lv3.get("required") != ["date"] or lv3.get("unique") != ["date"]:
                bad40.append("Level 的 required/unique 不是 ['date']")
            if not lv3.get("date_pattern"):
                bad40.append("Level 缺 date_pattern")
            for k40 in list(lv3.get("ints") or []) + list((lv3.get("ranges") or {}).keys()) \
                    + list((lv3.get("keys") or {}).keys()) + list(lv3.get("required") or []):
                if k40 not in lvc40:
                    bad40.append("Level 的 %r 不在 columns 里" % k40)
            lvk40 = list((lv3.get("keys") or {}).values())
            if len(lvk40) != len(set(lvk40)):
                bad40.append("Level keys 的 state 键有重复")
            # Exchange v3：26 列冻结 + 信封 + CSV 协议登记
            if e3.get("exchange_ver") != "RPL-Exchange-v3":
                bad40.append("exchange_ver=%r" % e3.get("exchange_ver"))
            l2, l3 = e2.get("log_jsonl") or {}, e3.get("log_jsonl") or {}
            if jd(l3.get("record_keys_frozen")) != jd(l2.get("record_keys_frozen")):
                bad40.append("record_keys_frozen 与 v2 分叉（26 列台账协议冻结）")
            h2, h3 = l2.get("header_record") or {}, l3.get("header_record") or {}
            for k40 in ("type_key", "type_value", "required_keys", "schema_ver_value_field"):
                if jd(h2.get(k40)) != jd(h3.get(k40)):
                    bad40.append("header_record.%s 与 v2 分叉" % k40)
            if h3.get("csv_protocol_current") != "2":
                bad40.append("csv_protocol_current=%r（CSV v2 协议登记丢了）" % h3.get("csv_protocol_current"))
            if h3.get("csv_protocol_current") not in (h3.get("csv_protocol_accepted") or []):
                bad40.append("csv_protocol_current 不在 csv_protocol_accepted 里")
            if not set(h2.get("csv_protocol_accepted") or []) <= set(h3.get("csv_protocol_accepted") or []):
                bad40.append("csv_protocol_accepted 丢了 v2 世代（旧 META 头对不上）")
            gp40 = l3.get("gpp_record") or {}
            njk40 = gp40.get("notes_json_keys") or []
            if len(njk40) != len(set(njk40)) or not njk40:
                bad40.append("gpp_record.notes_json_keys 为空或有重复")
            for k40 in (gp40.get("mapping") or {}):
                if k40 not in (l3.get("record_keys_frozen") or []):
                    bad40.append("gpp_record.mapping 的列 %r 不在 26 列冻结清单里" % k40)
            v2e, v3e = e2.get("plan_envelope") or {}, e3.get("plan_envelope") or {}
            for k40 in v2e:
                if k40 in ("current", "accepted", "plan_payload_contract", "legacy_note"):
                    continue
                if jd(v2e[k40]) != jd(v3e.get(k40)):
                    bad40.append("plan_envelope 键 '%s' 与 v2 分叉（非版本差异）" % k40)
            if v3e.get("current") != p3.get("schema_ver"):
                bad40.append("信封 current 与 Plan 契约 schema_ver 不同步")
            if v3e.get("current") not in (v3e.get("accepted") or []):
                bad40.append("信封 accepted 不含 current")
            if not set(v2e.get("accepted") or []) <= set(v3e.get("accepted") or []):
                bad40.append("信封 accepted 丢了 v2 世代（老信封导不进）")
            if v3e.get("plan_payload_contract") != "schema/RPL-Plan-v3.json":
                bad40.append("plan_payload_contract 没指向 v3")
        chk("S40", "Plan/Exchange v3 超集：分叉白名单 / entries 逐字节等 v1+v2 / -Armor+GPP+Level / GPP·Level·legacy spec 自洽 / 26 列冻结 / 信封三版本 / csv_protocol_current=2 / 生成链指 v3",
            not bad40,
            "OK（v2 七表 → v3 八表 / 信封 accepted %d 版本 / legacy entries 2 条 / 分叉 0）"
            % len((e3.get("plan_envelope") or {}).get("accepted") or [])
            if not bad40 else " / ".join(bad40[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S40", "Plan/Exchange v3 超集", False, e)

    # ---------- S41 ----------
    # 组策略默认绑定（v0.37 节点⑮）单源：族→idx 名单只在模板里一份，兜底 idx 必须在库，
    # 绑定表的族键必须落在种子协议表真实 family 枚举上（绑个不存在的新族=静默永不生效），
    # 读取口与 auto 语义的接线在位，且 prescriptionOf 一个字都不读策略绑定（处方权威不动）。
    # 见证腿在 _sabotage_s1.py（F1 绑到库里没有的 idx → 本检查红）。
    try:
        tpl41 = read(os.path.join(HERE, "template.html"))
        bad41 = []

        def list41(nm41, pat41):
            m41 = re.search(pat41, tpl41, re.S)
            return m41.group(1) if m41 else None

        tb41 = list41("STRAT_FAMILY_DEFAULT", r"const STRAT_FAMILY_DEFAULT=\{(.*?)\};")
        fb41 = list41("STRAT_FALLBACK_IDX", r"const STRAT_FALLBACK_IDX\s*=\s*(\d+)")
        if tb41 is None or fb41 is None:
            bad41.append("绑定表或兜底常量取不到")
        else:
            pairs41 = re.findall(r"([A-Za-z_]+):\s*(\d+)", tb41)
            if not pairs41:
                bad41.append("绑定表解析出 0 条")
            with open(os.path.join(HERE, "seed.json"), encoding="utf-8") as f41:
                sd41 = json.load(f41)
            lib_idx41 = {str(i.get("idx")) for i in (sd41.get("strategyLib") or {}).get("items", [])}
            fam41 = {p.get("family") for p in (sd41.get("proto") or {}).values() if p.get("family")}
            for fam_name, idx_val in pairs41:
                if idx_val not in lib_idx41:
                    bad41.append("族 %s 绑到库里不存在的 idx=%s（stratOf 判空=静默不绑）" % (fam_name, idx_val))
                if fam_name not in fam41:
                    bad41.append("族 %s 不在协议表 family 枚举（绑定永不生效）" % fam_name)
            if fb41 not in lib_idx41:
                bad41.append("兜底 idx=%s 不在库里" % fb41)
        for sym41 in ("function stratBoundId(", "function strategySource(",
                      "stratBoundId({mode:", "strategySource(e)==='auto'"):
            if sym41 not in tpl41:
                bad41.append("接线缺席：" + sym41)
        m41p = re.search(r"function prescriptionOf\(e\)\{(.*?)\n\}", tpl41, re.S)
        if not m41p:
            bad41.append("prescriptionOf 取不到")
        elif re.search(r"[Ss]trat", m41p.group(1)):
            bad41.append("prescriptionOf 读到了策略绑定（处方权威被污染）")
        prod41 = read(ASSET)
        for sym41 in ("STRAT_FAMILY_DEFAULT", "stratBoundId", "strategySource"):
            if sym41 not in prod41:
                bad41.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym41)
        chk("S41", "组策略默认绑定单源：族表可解析 / 兜底在库 / 族键落在真实枚举 / 读取与 auto 接线在位 / 处方权威不碰绑定",
            not bad41,
            "OK（绑定 %d 族 / 兜底 idx=%s / 库 %d 行）" % (len(re.findall(r"([A-Za-z_]+):\s*(\d+)", tb41 or "")), fb41 or "?", len(lib_idx41 or {}))
            if not bad41 else " / ".join(bad41[:6]))
    except (OSError, ValueError, KeyError, TypeError) as e:
        chk("S41", "组策略默认绑定单源", False, e)

    # ---------- S42 ----------
    # 周训练总结的三小项归类与功能标注单源：归类函数与四族配色映射各只许一份；
    # --sbd-* 八枚令牌在三块主题令牌块各一份 —— 少一块的表现是那个主题下贴片
    # 静默掉色（CSS 变量回落初值，不报错）。贴片只从 sbdChipCls/posterCatAgg 出货，
    # renderPoster 里手抄类名或绕开聚合都算漂。见证腿在 _sabotage_m9.py（F8–F10）。
    try:
        tpl42 = read(os.path.join(HERE, "template.html"))
        bad42 = []
        if tpl42.count("function sbdFamilyOfCat(cat){") != 1:
            bad42.append("sbdFamilyOfCat 定义不是恰好一份")
        if tpl42.count("const SBD_CHIP={S:'pc-s',B:'pc-b',D:'pc-d',X:'pc-x'};") != 1:
            bad42.append("SBD_CHIP 四族配色映射不是恰好一份")
        for tok42 in ("--sbd-s", "--sbd-b", "--sbd-d", "--sbd-x",
                      "--sbd-s-soft", "--sbd-b-soft", "--sbd-d-soft", "--sbd-x-soft"):
            c42 = tpl42.count(tok42 + ":")
            if c42 != 3:
                bad42.append("%s 声明 %d 份（主题令牌块应三块各一）" % (tok42, c42))
        for cls42, tk42 in ((".pc-s{", "--sbd-s"), (".pc-b{", "--sbd-b"),
                            (".pc-d{", "--sbd-d"), (".pc-x{", "--sbd-x")):
            if cls42 not in tpl42 or ("var(%s)" % tk42) not in tpl42:
                bad42.append("缺 %s 规则或对 %s 的 var 引用" % (cls42, tk42))
        for sym42 in ("sbdChipCls(", "posterCatAgg(", "sbdFamilyOfCat(", "weekFam:wagg.fam"):
            if sym42 not in tpl42:
                bad42.append("接线缺席：" + sym42)
        prod42 = read(ASSET)
        for sym42 in ("sbdFamilyOfCat", "SBD_CHIP", "--sbd-s:", "posterCatAgg"):
            if sym42 not in prod42:
                bad42.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym42)
        chk("S42", "SBD 三小项标注单源：归类函数与配色映射各唯一 / 令牌三块计数一致 / "
            "海报接线在位 / 成品同段",
            not bad42,
            "OK（归类 1 / 配色表 1 / 令牌 8×3 块 / 接线 4 / 成品同段）"
            if not bad42 else " / ".join(bad42[:6]))
    except (OSError, ValueError) as e:
        chk("S42", "SBD 三小项标注单源", False, e)

    # ---------- S43 ----------
    # 阶段条（v0.39）单源 + Extra Dark 改名钉：阶段数据只从 auditCycleGoal 的
    # phases 出货、只在 renderGoalAudit 的独立条里消费一次（行网格里不再有「阶段」这一行）；
    # 发出的四个 class 必须各有 CSS 规则 —— 少一条的表现是贴片静默走默认样式，不报错。
    # 改名是**纯对外改名**：内部 id 仍是 nature（存量存档里的 state.theme='nature' 不迁移、
    # 不断链），旧对外名「纸墨」与旧字形「❦」零残留。v0.44/F21 起 zh 态对外名是「咖啡纸感」、
    # en 态保留「Extra Dark」（中文态显示英文名 + 分段器溢出是用户点名要修的）。
    # 见证腿在 _sabotage_m10.py（F1–F4）。
    try:
        tpl43 = read(os.path.join(HERE, "template.html"))
        bad43 = []
        if tpl43.count("phases:phases") != 1:
            bad43.append("phases 出口不是恰好一份")
        if tpl43.count("a.phases.map") != 1:
            bad43.append("phases 消费点不是恰好一处")
        if "{zh:'阶段'" in tpl43 or "en:'PHASE'" in tpl43:
            bad43.append("行网格里还留着阶段行（阶段有第二个出口）")
        for js43, css43 in (('<div class="ga-phase">', ".ga-phase{"),
                            ('<b class="ga-blk">', ".ga-blk{"),
                            ('<span class="ga-arrow">', ".ga-arrow{"),
                            ('<i class="ga-peak">', ".ga-peak{")):
            if tpl43.count(js43) != 1:
                bad43.append("发射点 %s 不是恰好一处" % js43)
            if css43 not in tpl43:
                bad43.append("缺 CSS 规则 " + css43)
        if "thNatureT:['咖啡纸感','Extra Dark']," not in tpl43:
            bad43.append("i18n 表里 nature 槽位不是 zh=咖啡纸感 / en=Extra Dark（F21：中文态不许再显示英文名）")
        if '<span id="thNatureT">咖啡纸感</span>' not in tpl43:
            bad43.append("markup 里 nature 按钮文案不是 咖啡纸感")
        if "window.THEME_IDS=['dark','light','nature'];" not in tpl43:
            bad43.append("内部 id 被改了（改名必须是纯对外，nature 要留在注册表里）")
        for old43 in ("纸墨", "❦"):
            if old43 in tpl43:
                bad43.append("旧名残留：" + old43)
        prod43 = read(ASSET)
        for sym43 in ("ga-phase", "phases:phases", "Extra Dark", "咖啡纸感"):
            if sym43 not in prod43:
                bad43.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym43)
        if "纸墨" in prod43:
            bad43.append("成品里还有旧名「纸墨」")
        chk("S43", "阶段条单源与 Extra Dark 改名：阶段只有一个出口 / 四个 class 各有 CSS 规则 / "
            "id 仍是 nature / 旧名零残留 / 成品同段",
            not bad43,
            "OK（出口 1 / 消费 1 / class×规则 4 对 / id=nature / 旧名 0 / 成品同段）"
            if not bad43 else " / ".join(bad43[:6]))
    except (OSError, ValueError) as e:
        chk("S43", "阶段条单源与 Extra Dark 改名", False, e)


    # ---------- S44 ----------
    # 会员徽记 + 状态监控总开关（teleOn）的接线钉。这组改动全部是「静默型」的：
    # 键位漏进 PREF_KEYS 不会报错，只是重开一次 App 就把用户打开的开关忘掉；
    # ensureShape 少一行回填不会报错，只是旧存档每次进来都重新判一次；
    # openTeleSheet 的闸门被删不会报错，只是关掉的面板又点得进去；
    # 徽记写回标题里不会报错，只是 320px 下 h1 被裁、check_hud 之后才红。
    # 所以每一处都按「恰好一份」来钉，多一份也算红（第二份口径迟早和第一份分家）。
    # 见证腿在 _sabotage_m11.py（F1–F5）。
    try:
        tpl44 = read(os.path.join(HERE, "template.html"))
        bad44 = []
        for pat44, what44 in (
                (r"const PREF_KEYS=\[[^\]]*'teleOn'[^\]]*\]", "teleOn 没登记进 prefs 片名单"),
                (r"const IMPORT_KEEP_KEYS=\[[^\]]*'teleOn'[^\]]*\]", "teleOn 没登记进导入保全名单")):
            if len(re.findall(pat44, tpl44)) != 1:
                bad44.append(what44)
        for lit44 in ("function teleOn(){ return state.teleOn===true; }",
                      "state.teleOn=(state.teleOn===true);",
                      "teleOn:pref.teleOn===true",
                      "if(!teleOn()){",
                      "brief.classList.toggle('hidden',!teleOn());",
                      'onclick="toggleTeleOn()"',
                      "setTeleT:", "setTeleS:",
                      "function bwSeries(){",
                      "renderBwHint();",
                      ".bw-hint{"):
            if tpl44.count(lit44) != 1:
                bad44.append("接线/回填缺位或重复：%s" % lit44)
        if tpl44.count("bwSeries();") != 2:
            bad44.append("bwSeries 的读者不是恰好两处（趋势行 + 遥测曲线）")
        if tpl44.count('<span class="pro-mark"><i>\u2726</i>Pro</span>') != 1:
            bad44.append("会员徽记 markup 不是恰好一颗")
        for css44 in (".pro-mark{", ".pro-mark i{"):
            if tpl44.count(css44) < 1:
                bad44.append("缺 CSS 规则 " + css44)
        for dead44 in ("<em>Pro</em>", ".brand-line h1 em", "ProMax"):
            if dead44 in tpl44:
                bad44.append("旧写法残留：" + dead44)
        prod44 = read(ASSET)
        for sym44 in ("pro-mark", "teleOn", "bwSeries", "setTeleT"):
            if sym44 not in prod44:
                bad44.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym44)
        chk("S44", "会员徽记与状态监控开关接线：两个名单各登记一次 / 读口·回填·闸门·藏舱·按钮·文案各一份 / "
            "体重趋势单源 / 徽记一颗且旧写法零残留 / 成品同段",
            not bad44,
            "OK（名单 2 / 接线 9 / 读者 2 / 徽记 1 / 旧写法 0 / 成品同段）"
            if not bad44 else " / ".join(bad44[:6]))
    except (OSError, ValueError) as e:
        chk("S44", "会员徽记与状态监控开关接线", False, e)


    # ---------- S45 ----------
    # 装备/场地库（gearKit + kitSheet）接线钉（v0.41）。这组改动同样是「静默型」的：
    # gearKit 漏登记只表现为「存了装备、杀掉进程重开就没了」；
    # ensureShape 少一处回填只表现为旧存档每次多判一次、gearSave 的防御成了唯一兜底；
    # WEAR_CHIP 与契约 wear_levels 漂移只表现为某档成色胶囊没色（页面照常、点数照常）；
    # closeAllSheets 漏 kitSheet 只表现为返回键收不掉这一层（别的面板都正常）；
    # 三套主题的 --wk-* 少一条只表现为那套主题下胶囊失色。
    # 所以每一处都按「恰好一份」来钉；成色档位表从 RPL-Gear-v1.json 现读，不手抄。
    # 见证腿在 _sabotage_m12.py（F1–F5）。
    try:
        tpl45 = read(os.path.join(HERE, "template.html"))
        gear45 = json.loads(read(build_html.GEAR_SCHEMA))
        bad45 = []
        for pat45, what45 in (
                (r"const PREF_KEYS=\[[^\]]*'gearKit'[^\]]*\]", "gearKit 没登记进 prefs 片名单"),
                (r"const IMPORT_KEEP_KEYS=\[[^\]]*'gearKit'[^\]]*\]", "gearKit 没登记进导入保全名单")):
            if len(re.findall(pat45, tpl45)) != 1:
                bad45.append(what45)
        # 回填与防御各在其位：一处是 ensureShape 的旧存档兜底，另一处是 gearSave 的入口防御
        if tpl45.count("if(!Array.isArray(state.gearKit)) state.gearKit=[];") != 2:
            bad45.append("gearKit 回填/防御不是恰好两处（ensureShape + gearSave）")
        if tpl45.count("if(v&&typeof v==='object'&&!Array.isArray(v.machines)) v.machines=[];") != 1:
            bad45.append("场地 machines 回填缺位或重复")
        if tpl45.count('id="kitSheet"') != 1:
            bad45.append("装备面板 markup 不是恰好一张")
        for lit45 in ("function openKitSheet(){ renderKit(); showSheet('kitSheet'); haptic(10); }",
                      "onclick=\"openKitSheet()\"",
                      "'figsSheet','envSheet','kitSheet','sciSheet'",
                      "setKitT:", "setKitS:", 'id="setKitGo"'):
            if tpl45.count(lit45) != 1:
                bad45.append("入口/返回键收口/i18n 缺位或重复：%s" % lit45)
        wear45 = [w["id"] for w in gear45["equipment"]["wear_levels"]]
        chip45 = "const WEAR_CHIP={" + ",".join("%s:'wk-%s'" % (w, w) for w in wear45) + "};"
        if tpl45.count(chip45) != 1:
            bad45.append("WEAR_CHIP 与契约 wear_levels 不是一对一（契约档位 %s）" % ",".join(wear45))
        for w45 in wear45:
            if tpl45.count("--wk-%s:" % w45) != 3:
                bad45.append("成色色标 --wk-%s 不是三套主题各定义一次" % w45)
        prod45 = read(ASSET)
        for sym45 in ("kitSheet", "WEAR_CHIP", "gearKit", "setKitT"):
            if sym45 not in prod45:
                bad45.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym45)
        chk("S45", "装备/场地库接线：gearKit 双名单各登记一次 / 回填与防御各两处比一 / kitSheet·入口·"
            "收口·文案各一份 / WEAR_CHIP 对齐契约 wear_levels / 三套主题色标齐 / 成品同段",
            not bad45,
            "OK（名单 2 / 防御 2+1 / 接线 6 / 契约 %d 档 × 主题 3 / 成品同段）" % len(wear45)
            if not bad45 else " / ".join(bad45[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S45", "装备/场地库接线", False, e)

    # ---------- S46 ----------
    # 装备照片（gearphoto）接线钉（v0.43）。静默型的病与 S45 同族：
    # 表单缩略位丢了只表现为「没地方放照片」；渲染钩子丢了只表现为「选完图回来缩略位不刷新」；
    # Java 三桥少一面只表现为「点了没反应」；大小上限漂了只表现为「占内存/拖慢读口」却不报错。
    # 每处按「恰好一份」钉；旧版「照片延到下版」的说明必须零残留。
    # 见证腿在 _sabotage_m13.py（F1–F5）。
    try:
        tpl46 = read(os.path.join(HERE, "template.html"))
        java46 = read(JAVA)
        bad46 = []
        # 模板面：缩略位 markup / 五个照片函数 / 桥调用 / 渲染钩子各恰好一份
        if tpl46.count('class="kf-photo" id="kfPhoto" onclick="kitPhotoPick()"') != 1:
            bad46.append("缩略位 markup 缺位或重复")
        for lit46, what46 in (
                ("function kitPhotoKey(){", "kitPhotoKey"),
                ("function kitPhotoData(", "kitPhotoData"),
                ("function renderKitPhoto(){", "renderKitPhoto"),
                ("function kitPhotoPick(){", "kitPhotoPick"),
                ("function kitPhotoDel(){", "kitPhotoDel"),
                ("function kitPhotoDone(", "kitPhotoDone"),
                ("function gearPhotoWipe(", "gearPhotoWipe")):
            if tpl46.count(lit46) != 1:
                bad46.append("照片函数缺位或重复：%s" % what46)
        for call46 in ("AndroidBridge.gearPickPhoto(key)", "AndroidBridge.gearPhotoData(key)",
                       "AndroidBridge.gearDelPhoto(key)", "if(kitForm) renderKitPhoto();"):
            if tpl46.count(call46) != 1:
                bad46.append("桥调用/渲染钩子缺位或重复：%s" % call46)
        # 占位与图态两分支都在（钉 JS 发射字面量；CSS 规则另有四类钉）；旧「照片延到下版」零残留
        if tpl46.count('class="kf-photo-ph"') != 1:
            bad46.append("占位分支发射缺位或重复")
        if tpl46.count('class="kf-photo-img"') != 1:
            bad46.append("图态分支发射缺位或重复")
        if "照片延到下版" in tpl46:
            bad46.append("旧版「照片延到下版」说明残留")
        # Java 面：三桥各有 @JavascriptInterface、选图回路回调 kitPhotoDone、三条大小限在位
        for m46 in ("gearPickPhoto", "gearPhotoData", "gearDelPhoto"):
            if len(re.findall(r"@JavascriptInterface\s+(?:public\s+\w+\s+)?%s\s*\(" % m46, java46)) != 1:
                bad46.append("Java 桥缺位或重复：%s" % m46)
        if java46.count("kitPhotoDone(") != 1:
            bad46.append("Java 选图回路没回调 kitPhotoDone（缩略位选完不刷新）")
        for cap46 in ("PHOTO_SRC_MAX_BYTES", "PHOTO_MAX_BYTES", "PHOTO_EDGE_MAX"):
            if len(re.findall(r"private static final (?:long|int) %s\s*=" % cap46, java46)) != 1:
                bad46.append("大小上限声明缺位或重复：%s" % cap46)
        if java46.count("f.length() > PHOTO_MAX_BYTES") != 1:
            bad46.append("读口大小闸缺位（超限文件会被当图读出）")
        # CSS 面：四个类都有规则（S22 兜死类名，这里钉「样式在」）
        for cls46 in (".kf-photo{", ".kf-photo-img{", ".kf-photo-ph{", ".kf-photo-x{"):
            if tpl46.count(cls46) != 1:
                bad46.append("CSS 规则缺位或重复：%s" % cls46)
        prod46 = read(ASSET)
        for sym46 in ("kfPhoto", "kitPhotoPick", "kitPhotoDone", "gearPickPhoto"):
            if sym46 not in prod46:
                bad46.append("成品缺 %s（忘跑 build_html 或手改成品）" % sym46)
        chk("S46", "装备照片接线：缩略位·七函数·三桥调用·渲染钩子各恰好一份 / 占位与图态两分支齐 / "
            "旧「照片延到下版」零残留 / Java 三桥各一面且回调 kitPhotoDone / 大小三限在位 / 成品同段",
            not bad46,
            "OK（模板 12 处 / Java 桥 3 + 回调 1 / 三限 / 成品同段）"
            if not bad46 else " / ".join(bad46[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S46", "装备照片接线", False, e)


    # ---------- S47 ----------
    # GPP / JTS 目录契约的单源钉（v0.45）。D8/xlsxv 已经逐格证明「App 侧和 Python 侧
    # 对同一份 seed 算出同一张表」；这一条盯的是「两边算的到底是不是同一份目录」：
    # 恢复通道上限、菜单域名、目录富化字段只要有一处被手抄成第二份真相，
    # 格差不会立刻出现，直到目录改数那天才在某一侧静默漂走。
    # 所以每条腿都按「契约读口恰好一份 + 手抄形态零出现」来钉；契约数字全部现读，不抄进本文件。
    # 见证腿在 _sabotage_m16.py（F1–F4）。
    try:
        tpl47 = read(os.path.join(HERE, "template.html"))
        s47 = os.path.join(HERE, "schema")
        gpp47 = json.loads(read(os.path.join(s47, "RPL-GPP-v1.json")))
        jts47 = json.loads(read(os.path.join(s47, "RPL-JTS-v1.json")))
        seed47 = json.loads(read(build_html.SEED))
        bad47 = []
        # 注入行（const X_SCHEMA = {...}）是契约载荷本身，不参与「手抄形态」扫描
        body47 = "\n".join(l for l in tpl47.split("\n")
                           if not re.match(r"const (GPP_SCHEMA|JTS_SCHEMA) = ", l))
        # A. 恢复通道：上限只许从契约读，读口恰好一份；写死上限的形态零出现
        if body47.count("+((GPP_RECOVERY.b_gpp||{}).cap), capF=+((GPP_RECOVERY.f_gpp||{}).cap)") != 1:
            bad47.append("GPP 恢复上限读口不是恰好一份")
        for capnum47 in (gpp47["recovery"]["b_gpp"]["cap"], gpp47["recovery"]["f_gpp"]["cap"]):
            for pat47 in (r"=\s*" + re.escape(str(capnum47)),
                          r"\(\s*" + re.escape(str(capnum47)) + r"[,)]"):
                if re.search(pat47, body47):
                    bad47.append("恢复上限 %s 被手抄成第二份（模板 %s）" % (capnum47, pat47))
        # B. 种子 GPP 定义 = 契约规范序：菜单行在前、域名/度量身在契约枚举里、item 非空
        menu47 = gpp47["weekly_menu"]
        dom_enum47 = set(gpp47["domain_enum"]) | {"custom"}
        mt_enum47 = set(gpp47["metric_type_enum"]) | {""}
        defs47 = seed47.get("gpp") or []
        if len(defs47) < len(menu47):
            bad47.append("seed.gpp 只有 %d 项，少于契约菜单 %d 行" % (len(defs47), len(menu47)))
        for i, r in enumerate(menu47):
            d = defs47[i] if i < len(defs47) else {}
            if d.get("domain") != r["domain"]:
                bad47.append("seed.gpp[%d].domain=%r ≠ 菜单行 %d 的 %r（种子不是规范序）"
                             % (i, d.get("domain"), r["row"], r["domain"]))
            if d.get("custom"):
                bad47.append("seed.gpp[%d] 是菜单行，却带 custom 旗标" % i)
        for d in defs47:
            if d.get("domain") not in dom_enum47:
                bad47.append("seed.gpp 域 %r 不在契约 domain_enum（旧 AUX 域没迁移）" % d.get("domain"))
            if d.get("metricType") not in mt_enum47:
                bad47.append("seed.gpp 度量 %r 不在契约 metric_type_enum" % d.get("metricType"))
            if not str(d.get("item") or "").strip():
                bad47.append("seed.gpp 出现空 item")
            if d.get("custom") and str(d.get("intensity") or "") != "":
                bad47.append("seed.gpp 自定义项 %r 的 intensity 不该有出厂值" % str(d.get("item"))[:24])
        # C. 目录富化单源：契约里 new_ids[0] 已被菜单覆盖的旧行，种子再落成自定义就是重复定义
        covered47 = set()
        for r in menu47:
            covered47.update(r.get("item_ids") or [])
            covered47.update(r.get("alt_item_ids") or [])
        custom_items47 = {d.get("item") for d in defs47 if d.get("custom")}
        for e in (gpp47.get("legacy_map") or {}).get("seed_aux_rows") or []:
            nids47 = e.get("new_ids") or []
            if nids47 and nids47[0] in covered47 and e.get("old_item") in custom_items47:
                bad47.append("旧行 %r 的目录条目已在菜单覆盖里，种子却把它落成自定义（重复定义，rec_bonus 双记）"
                             % str(e.get("old_item"))[:24])
        # D. JTS 契约读口恰好一份 + 手抄形态零出现
        #    （唯一允许的兜底字面是定义行 `(JTS_RECMULT.clamp||[0.55,1.25])`；
        #      消费处 lo/hi 的三元兜底数字若再出现第二处，就是手抄。）
        if body47.count("const JTS_REC_CLAMP=(JTS_RECMULT.clamp||[0.55,1.25]).slice();") != 1:
            bad47.append("recMult.clamp 定义行读口不是恰好一份")
        for pat47 in (r"ready_at\s*=\s*\[", r"=\s*\[90\s*,\s*75", r"=\s*\[0\.55",
                      r"=\s*1\.25", r"polarity\s*=\s*['\"]reverse"):
            if re.search(pat47, body47):
                bad47.append("JTS 契约数字被手抄成第二份（模板 %s）" % pat47)
        # E. 退役形态零残留：旧 AUX 域名、旧 Armor 菜单名、CRS 旁路、旧五维键
        for dead47 in ("CARDIO RESPIRATORY", "PARASYMPATHETIC", "HYPERTROPHY GAP-FILL",
                       "Aerobic LISS", "function jtsRef(",
                       "drive:", "willingness:"):
            if dead47 in body47:
                bad47.append("退役写法残留：" + dead47)
        if "CARDIO RESPIRATORY" in json.dumps(seed47, ensure_ascii=False):
            bad47.append("seed 里还带旧 AUX 域名（gen_seed 没按契约出厂）")
        # F. 成品接线：注入载荷与三枚解析函数在成品各一份（忘跑 build_html / 手改成品）
        prod47 = read(ASSET)
        if '"weekly_menu"' not in prod47 or '"readiness"' not in prod47:
            bad47.append("成品缺 GPP/JTS 契约载荷（忘跑 build_html？）")
        for sym47 in ("function gppResolveDef(", "function gppCanonDefs(", "function jtsCalcV6("):
            if prod47.count(sym47) != 1:
                bad47.append("成品里 %s 不是恰好一份" % sym47)
        chk("S47", "GPP/JTS 目录单源：恢复上限与夹紧读口各一份且零手抄 / 种子 gpp 对齐契约菜单序与枚举 / "
            "目录富化不缺腿 / JTS 数字零手抄 / 退役形态零残留 / 成品契约载荷与三解析函数各一份",
            not bad47,
            "OK（契约现读：菜单 %d 行 / 种子 %d 项 / 域名 %d 种 / 分数线 %s）" % (
                len(menu47), len(defs47), len(dom_enum47),
                ",".join(str(x) for x in jts47["readiness"]["ready_at"]))
            if not bad47 else " / ".join(bad47[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S47", "GPP/JTS 目录单源", False, e)

    # ---------- S48 ----------
    # 运动员水平页单源钉（v0.46）。这一页把「三小项 / 快照 / 段位」三件事第一次同时落在
    # 模板、CSV notes、契约 Level 表三个介质上；任何一处被手抄成第二份真相，当天不会有
    # 格差，改数那天才静默漂走。六条腿：行几何 / CSV 携带 / 夹单源 / 快照键 ↔ 契约 keys /
    # 退役形态零残留 / 成品同段。见证腿在 _sabotage_m17.py（F1–F5）。
    try:
        tpl48 = read(os.path.join(HERE, "template.html"))
        body48 = "\n".join(l for l in tpl48.split("\n")
                           if not re.match(r"const (PLAN_SCHEMA|GPP_SCHEMA|JTS_SCHEMA) = ", l))
        bad48 = []
        # A. 水平页几何：全量表恰好 17 行，三小项输入各一面（v0.46 执行清单的清单数）
        if body48.count('<div class="lvl-row">') != 17:
            bad48.append("lvl-row 不是恰好 17 行（现 %d）" % body48.count('<div class="lvl-row">'))
        for id48 in ('id="pOhp"', 'id="pPullup"', 'id="pDip"'):
            if body48.count(id48) != 1:
                bad48.append("%s 不是恰好一份" % id48)
        # B. CSV 携带单源：PROFILE notes 的三小项只许在定义行写一次
        if body48.count("pullupAddedKg:p.pullupAddedKg,dipAddedKg:p.dipAddedKg") != 1:
            bad48.append("CSV notes 三小项携带行不是恰好一份")
        if body48.count("sq:p.sq,bp:p.bp,dl:p.dl,ohp:p.ohp") != 1:
            bad48.append("CSV notes 主项+OHP 定义行不是恰好一份")
        # C. 附加重量夹单源：[0,200] 的非负下界只许写在 saveProfile 的钳位行上
        for cl48 in ("pullupAddedKg:Math.max(0,gval('pPullup',p.pullupAddedKg||0)),",
                     "dipAddedKg:Math.max(0,gval('pDip',p.dipAddedKg||0)),"):
            if body48.count(cl48) != 1:
                bad48.append("附加重量钳位行不是恰好一份：%s…" % cl48[:24])
        # D. 快照键 ↔ 契约 Level.keys：SNAP_TRACK 必须等于契约值域去掉 date/note
        p3_48 = json.loads(read(os.path.join(HERE, "schema", "RPL-Plan-v3.json")))
        keys48 = p3_48["sheets"]["Level"]["keys"]
        want48 = {v for k, v in keys48.items() if k not in ("date", "note")}
        m48 = re.search(r"const SNAP_TRACK=\[([^\]]*)\]", body48)
        if not m48:
            bad48.append("SNAP_TRACK 定义行没了")
        else:
            got48 = set(re.findall(r"'([^']+)'", m48.group(1)))
            if len(re.findall(r"'[^']+'", m48.group(1))) != len(got48):
                bad48.append("SNAP_TRACK 有重复键")
            if got48 != want48:
                bad48.append("SNAP_TRACK 与契约 Level.keys 值域不一致（多 %s / 缺 %s）" % (
                    sorted(got48 - want48) or "无", sorted(want48 - got48) or "无"))
        # E. 退役形态零残留：圆形 medal、Tab 制、旧系数/目标卡 CSS
        for dead48 in ("gl-medal", "glMedal", "gl-rank-hero", "profTab", "setProfTab",
                       ".goal-in", ".coef-grid", ".coef-cell", ".prof-grid"):
            if dead48 in body48:
                bad48.append("退役形态残留：" + dead48)
        # F. 成品同段：忘跑 build_html / 手改成品都会在这里先响
        prod48 = read(ASSET)
        prod48 = "\n".join(l for l in prod48.split("\n")
                           if not re.match(r"const (PLAN_SCHEMA|GPP_SCHEMA|JTS_SCHEMA) = ", l))
        if prod48.count('<div class="lvl-row">') != 17:
            bad48.append("成品 lvl-row 不是 17 行（模板与成品不同段？）")
        for sym48 in ("function writeLevelSnap(", "function levelSnapshotOf(",
                      "function renderLevelSnapTable(", "const SNAP_TRACK=["):
            if prod48.count(sym48) != 1:
                bad48.append("成品里 %s 不是恰好一份" % sym48)
        chk("S48", "运动员水平页单源：全量表 17 行与三小项输入各一面 / CSV notes 携带与钳位各恰好一份 / "
            "SNAP_TRACK 对齐契约 Level.keys / medal·Tab·旧卡 CSS 退役零残留 / 成品同段",
            not bad48,
            "OK（契约现读：Level %d 列 / 跟踪键 %d / 退役写法 9 项零残留）" % (
                len(p3_48["sheets"]["Level"]["columns"]), len(want48))
            if not bad48 else " / ".join(bad48[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S48", "运动员水平页单源", False, e)

    # ---------- S49 ----------
    # 主页打气 / 日历引擎 / 器械视觉接线钉（v0.47）。这一版把「今日是哪一课」第一次交给
    # planPos 派生，把昵称/打气第一次落 prefs 片，把哑铃/自重第一次画成非杠铃形态。
    # 病仍是静默族：星期名单被手抄第二份、横幅悄悄退回 state.week 旧口径、哑铃分支被 else
    # 吞掉、dayNo 公式被换成 epoch 毫秒——当天都不炸，换周/换月/换器械那天才错。
    # 见证腿在 _sabotage_m18.py（F1–F5）。
    try:
        tpl49 = read(os.path.join(HERE, "template.html"))
        body49 = "\n".join(l for l in tpl49.split("\n")
                           if not re.match(r"const (PLAN_SCHEMA|GPP_SCHEMA|JTS_SCHEMA) = ", l))
        bad49 = []
        # A. 星期单源：WD_ZH 一份七项不重复；模板里不许再出现手抄英文星期名单
        m49 = re.search(r"const WD_ZH=\[([^\]]*)\]", body49)
        if not m49:
            bad49.append("WD_ZH 定义行没了")
        else:
            wd49 = re.findall(r"'([^']+)'", m49.group(1))
            if len(wd49) != 7 or len(set(wd49)) != 7:
                bad49.append("WD_ZH 不是恰好 7 项不重复（现 %d/%d）" % (len(wd49), len(set(wd49))))
        if body49.count("['Mon','Tue'") != 0:
            bad49.append("模板里出现第二份手抄英文星期名单")
        if body49.count("Days.weekday_labels") != 2:
            bad49.append("weekday_labels 读口不是恰好两处（weekdayName + renderStructDays，现 %d）"
                         % body49.count("Days.weekday_labels"))
        # B. 昵称登记与钳位单源：双名单各恰好一份，截断 24 只写在 saveNick 一行
        for pat49, what49 in (
                (r"const PREF_KEYS=\[[^\]]*'nick'\]", "nick 没登记进 prefs 片名单"),
                (r"const IMPORT_KEEP_KEYS=\[[^\]]*'nick'\]", "nick 没登记进导入保全名单")):
            if len(re.findall(pat49, body49)) != 1:
                bad49.append(what49)
        if body49.count(".trim().slice(0,24)") != 1:
            bad49.append("昵称 24 字符截断钳位不是恰好一份")
        # B2. 根滚动回归闸门（v0.58 真机反馈「整页划不动」）：html/body 根规则不许用
        # overflow-x:hidden——它把 body 变成滚动容器，WebView 拖动手势被吞掉且不向根链传递。
        # 必须用 clip（不建滚动容器）。
        root49 = re.search(r"html,body\{([^}]*)\}", body49)
        if not root49:
            bad49.append("找不到 html,body 根规则")
        elif "overflow-x:hidden" in root49.group(1):
            bad49.append("html/body 根规则用了 overflow-x:hidden（真机会吞掉滚动链）")
        elif "overflow-x:clip" not in root49.group(1):
            bad49.append("html/body 根规则里没有 overflow-x:clip")
        # C. 横幅与日历引擎：每把函数恰好一份
        for sym49 in ("function planPos(", "function todaySessions(",
                      "function nextSession(", "function sessionCode(",
                      "function daysOnWd(", "function weekdayName(", "function dayOffset(",
                      "function saveNick(", "function nickName(",
                      "const p=todaySessions();", "const n=nextSession();",
                      "document.getElementById('hdrSub').innerHTML=planSub"):
            if body49.count(sym49) != 1:
                bad49.append("%s 不是恰好一份（现 %d）" % (sym49, body49.count(sym49)))
        # D. 主页卡片 DOM 几何：问候卡已退役（v0.70），顶栏与昵称入口各一面
        for id49 in ('id="hdrSub"', 'id="hdrGoal"', 'id="nickIn"'):
            if body49.count(id49) != 1:
                bad49.append("%s 不是恰好一面" % id49)
        if body49.count('id="greetCard"') != 0 or body49.count('id="greetTxt"') != 0:
            bad49.append("模板里还留着已删除的首页问候卡")
        if body49.count("function renderHomeCards(") != 0:
            bad49.append("模板里还留着已删除的 renderHomeCards")
        # E. 器械视觉接线：四函数各一份 / 容器一面 / 分支各一条 / 非杠铃套管轴必须被关掉
        for sym49 in ("function renderGearDumbBar(", "function renderGearBwBar(",
                      "function renderGearDumbCfg(", "function setGearSides("):
            if body49.count(sym49) != 1:
                bad49.append("%s 不是恰好一份" % sym49)
        if body49.count('id="gearDumbCfg"') != 1:
            bad49.append("gearDumbCfg 容器不是恰好一面")
        if body49.count("}else if(isDumb){") != 1 or body49.count("}else if(isBw){") != 1:
            bad49.append("哑铃/自重渲染分支不是各恰好一条")
        if body49.count("pvBar.classList.toggle('no-sleeve', !isBar)") != 1:
            bad49.append("非杠铃关套管轴那行不是恰好一份")
        for css49 in (".db-row", ".db-cell", ".bw-fig", ".bw-state", ".gc-code"):
            if css49 + "{" not in body49 and css49 + " " not in body49 and css49 + "," not in body49:
                bad49.append("CSS 缺 %s 规则" % css49)
        # F. 成品同段：忘跑 build_html / 手改成品都会在这里先响
        prod49 = read(ASSET)
        prod49 = "\n".join(l for l in prod49.split("\n")
                           if not re.match(r"const (PLAN_SCHEMA|GPP_SCHEMA|JTS_SCHEMA) = ", l))
        for sym49 in ("function planPos(", "function renderGearDumbBar(",
                      "function renderGearBwBar(", "}else if(isDumb){", "}else if(isBw){",
                      'id="hdrSub"'):
            if prod49.count(sym49) != 1:
                bad49.append("成品里 %s 不是恰好一份（模板与成品不同段？）" % sym49)
        if prod49.count('id="greetCard"') != 0 or prod49.count("function renderHomeCards(") != 0:
            bad49.append("成品里还留着已删除的首页问候卡")
        if prod49.count("['Mon','Tue'") != 0:
            bad49.append("成品里出现手抄英文星期名单")
        if prod49.count('id="recentCard"') != 0 or prod49.count("function recentTraining(") != 0:
            bad49.append("成品里还留着已删除的「最近一次训练」模块")
        chk("S49", "主页日历引擎与器械视觉接线：星期名单双源零出现且 weekday_labels 只两处读口 / "
            "nick 双名单登记与 24 截断各一份 + 根规则 overflow-x:clip（打气模块已删除） / "
            "今日计划并入顶栏 hdrSub 且引擎函数各恰好一份 / "
            "哑铃·自重四函数两分支与 no-sleeve 在位 / 成品同段",
            not bad49,
            "OK（WD_ZH 7 项 / 引擎函数 15 把 / 卡面 id 5 面 / 星期手抄名单 0 处 / 最近卡已删）"
            if not bad49 else " / ".join(bad49[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S49", "主页日历引擎与器械视觉接线", False, e)

    # ---------- S50 ----------
    # 日/周分享图（poster）接线钉（v0.48）。这一版把「功能短标签」第一次交给 SHARE_SCHEMA 契约、
    # 把「日/周出货文案」第一次收进 posterTextBlocks 单源、把「保存 PNG」第一次接
    # AndroidBridge.exportDoc 裸 base64。病仍是静默族：短标签被手抄第二份、DOM 预览与 canvas 各
    # 走各的文案、海报里把 e1RM 公式又抄一遍、base64 前缀没剥 / MIME 写错、周图忘关 BW 格——
    # 当天都不炸，换语言 / 换周 / 换机那天才错。见证腿在 _sabotage_m19.py（F1–F5）。
    try:
        tpl50 = read(os.path.join(HERE, "template.html"))
        body50 = "\n".join(l for l in tpl50.split("\n")
                           if not re.match(r"const (PLAN_SCHEMA|EXCHANGE_SCHEMA|GEAR_SCHEMA|"
                                           r"GPP_SCHEMA|JTS_SCHEMA|SHARE_SCHEMA) = ", l))
        bad50 = []
        # A. 契约 + 注入 + 指纹：RPL-Share-v1 单源；模板有占位、成品已注入且指纹带 share= 位
        share50 = json.loads(read(build_html.SHARE_SCHEMA))
        if share50.get("share_ver") != "RPL-Share-v1":
            bad50.append("契约 share_ver 不是 RPL-Share-v1（现 %r）" % share50.get("share_ver"))
        sl50 = share50.get("short_labels") or {}
        if not sl50:
            bad50.append("契约 short_labels 空")
        else:
            miss50 = [k for k, v in sl50.items()
                      if not (isinstance(v, dict) and str(v.get("zh", "")).strip() and str(v.get("en", "")).strip())]
            if miss50:
                bad50.append("short_labels 有条目缺 zh/en：%s" % ",".join(sorted(miss50)[:4]))
        if tpl50.count("const SHARE_SCHEMA = /*__SHARE_SCHEMA__*/null;") != 1:
            bad50.append("模板缺 SHARE_SCHEMA 占位（应恰好一处）")
        prod50 = read(ASSET)
        if prod50.count("__SHARE_SCHEMA__") != 0:
            bad50.append("成品仍有未替换的 SHARE_SCHEMA 占位")
        if prod50.count("const SHARE_SCHEMA = {") != 1:
            bad50.append("成品 SHARE_SCHEMA 注入载荷不是恰好一份")
        if len(re.findall(r"BUILD_FP[^>]*share=[0-9a-f]{8}", prod50)) != 1:
            bad50.append("成品 BUILD_FP 指纹缺 share= 摘要位")
        # B. 单源与双消费接线：短标签读口 / 文案出货 / e1RM 同口径 / PNG 出货 / 控制接线，各恰好其数
        for sym50, want50, what50 in (
                ("function catShort(", 1, "catShort 定义"),
                ("SHARE_SCHEMA.short_labels", 1, "契约短标签读口（只许 catShort）"),
                ("function posterTextBlocks(", 1, "posterTextBlocks 定义"),
                ("posterTextBlocks(data);", 2, "posterTextBlocks 消费点（DOM+canvas）"),
                ("function posterPaintPlan(", 1, "posterPaintPlan 定义"),
                ("posterPaintPlan(B);", 1, "posterPaintPlan 消费点（仅 canvas）"),
                ("function anchorDoneE1rm(", 1, "anchorDoneE1rm 定义"),
                ("anchorDoneE1rm(d.exercises)", 1, "海报 topE1rm 调用（同口径）"),
                ("anchorDoneE1rm(rec.exercises)", 0, "已退役的首页最近记录调用"),
                ("function deliverPosterPng(", 1, "deliverPosterPng 定义"),
                ("url.slice(url.indexOf(',')+1)", 1, "裸 base64 剥前缀"),
                ("AndroidBridge.exportDoc(name,'image/png',b64)", 1, "桥 image/png 出货"),
                ("function posterShareName(", 1, "posterShareName 定义"),
                ("RPL_ExDark_v{{VER}}_share_", 1, "分享图文件名版本位"),
                ("function buildPosterCanvas(", 1, "buildPosterCanvas 定义"),
                ("function renderPoster(", 1, "renderPoster 定义"),
                ("function posterIsAcc(", 1, "posterIsAcc 定义"),
                ("posterIsAcc(r.mode)", 1, "配件分组调用"),
                ("foot:L('EXDARK PRO · 力量举训练日志','EXDARK PRO · IRON LOG'),", 1, "海报品牌尾注单源"),
                ("document.getElementById('postBwBox').style.display=isWeek?'none':''", 1, "周图关 BW 格"),
                ("document.getElementById('postSheet').classList.contains('on')", 1, "setLang 重渲分享图")):
            if body50.count(sym50) != want50:
                bad50.append("%s 不是恰好 %d 份（现 %d）" % (what50, want50, body50.count(sym50)))
        # C. 卡面 DOM 与控制接线：14 面 id 各一面 + 保存唯一一处
        for id50 in ('id="postBwBox"', 'id="postTitle"', 'id="postTotal"', 'id="postDelta"',
                     'id="postDate"', 'id="postBw"', 'id="postTon"', 'id="postE1"',
                     'id="postFootTxt"', 'id="postList"', 'id="postSave"', 'id="postClose"',
                     'id="postModeDay"', 'id="postModeWeek"'):
            if body50.count(id50) != 1:
                bad50.append("%s 不是恰好一面" % id50)
        if body50.count('onclick="exportPosterPng()"') != 1:
            bad50.append("onclick=\"exportPosterPng()\" 不是恰好一处")
        # D. 成品同段：忘跑 build_html / 手改成品都会在这里先响（版本位避开：成品 {{VER}} 已替换）
        prod50b = "\n".join(l for l in prod50.split("\n")
                            if not re.match(r"const (PLAN_SCHEMA|EXCHANGE_SCHEMA|GEAR_SCHEMA|"
                                            r"GPP_SCHEMA|JTS_SCHEMA|SHARE_SCHEMA) = ", l))
        for sym50 in ("function posterTextBlocks(", "function posterPaintPlan(", "function deliverPosterPng(",
                      "function anchorDoneE1rm(", "function catShort(",
                      "url.slice(url.indexOf(',')+1)", "AndroidBridge.exportDoc(name,'image/png',b64)",
                      "document.getElementById('postBwBox').style.display=isWeek?'none':''"):
            if prod50b.count(sym50) != 1:
                bad50.append("成品里 %s 不是恰好一份（模板与成品不同段？）" % sym50)
        chk("S50", "日/周分享图接线：SHARE 契约注入且指纹带 share= 位 / catShort 唯一短标签读口零手抄 / "
            "posterTextBlocks 一份两消费（DOM+canvas）且 paintPlan 只喂 canvas / anchorDoneE1rm 只留海报一处消费（首页最近记录已退役） / "
            "裸 base64 剥前缀 + 桥 image/png + 文件名版本位各一份 / 周图关 BW + 卡面 14 面 id + 保存控制接线 / 成品同段",
            not bad50,
            "OK（契约 short_labels %d 项 / 文案消费 2 处 / 卡面 id 14 面）" % len(sl50)
            if not bad50 else " / ".join(bad50[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S50", "日/周分享图接线", False, e)

    # ---------- S51 ----------
    # 六边形能力记录（HPR）接线钉（v0.49，D18）。这一版把「跨领域个人最佳」第一次收进 state.hpr
    # 一个键：六轴单源（HPR_AXES，v0.58 重定义为 力量/耐力/稳定/爆发/精神/灵活）、内置种子覆盖全部
    # 六轴且耐力轴两个子组都有条目、完成度只在 hprComplete、轴分只在
    # hprAxisScore、力量轴经 currentGl 现读 IPF GL（绝不手存 GL 死数）、雷达 SVG 落在 AUX 看板。
    # 病仍是静默族：轴名单被手抄第二份、GL 被存成死数、夹紧写漏、hpr 漏进某份名单或误进契约——
    # 当天都不炸，换轴 / 换 GL / 导入计划那天才错。见证腿在 _sabotage_m20.py（F1–F6）。
    try:
        tpl51 = read(os.path.join(HERE, "template.html"))
        bad51 = []
        # A. 六轴单源 + 单位单源：id 集合恰好六轴
        if "const HPR_AXES=[" not in tpl51:
            bad51.append("缺 HPR_AXES 单源")
            ids51 = []
        else:
            a0 = tpl51.index("const HPR_AXES=[")
            ids51 = re.findall(r"\{id:'([a-z]+)',\s*zh:", tpl51[a0:tpl51.index("];", a0)])
            if set(ids51) != {"strength", "endurance", "stability", "power", "mind", "mobility"} or len(ids51) != 6:
                bad51.append("HPR_AXES 不是恰好六轴（现 %r）" % (ids51,))
        if tpl51.count("const HPR_UNITS=[") != 1:
            bad51.append("HPR_UNITS 单源丢了")
        # B. 存储归属：'hpr' 恰好落 WORK_KEYS 与 IMPORT_KEEP 两份，绝不进 PLAN_OWNED；也不是契约/CSV 列
        for nm51, reg51 in (("WORK_KEYS", r"const WORK_KEYS=\[[^\]]*\]"),
                            ("IMPORT_KEEP_KEYS", r"const IMPORT_KEEP_KEYS=\[[^\]]*\]")):
            mm51 = re.search(reg51, tpl51, re.S)
            if not mm51 or "'hpr'" not in mm51.group(0):
                bad51.append("'hpr' 没登记进 %s" % nm51)
        mo51 = re.search(r"const PLAN_OWNED_KEYS=\[[^\]]*\]", tpl51, re.S)
        if mo51 and "'hpr'" in mo51.group(0):
            bad51.append("hpr 误进 PLAN_OWNED（导入会被整片换掉）")
        if tpl51.count("'hpr'") != 2:
            bad51.append("模板里 'hpr' 出现 %d 次（应恰好 WORK+KEEP 两处）" % tpl51.count("'hpr'"))
        plan51 = json.loads(read(build_html.PLAN_SCHEMA))
        if "hpr" in json.dumps(plan51).lower():
            bad51.append("hpr 漏进六表契约（它不是 CSV 列）")
        # C. 单源出口各一面；力量轴现读 currentGl，绝不把 GL 存成死数
        for sym51 in ("function hprComplete(", "function hprAxisScore(", "function hprNormalize(",
                      "function hprRadarPoints(", "function currentGl(", "function hprBuiltin(",
                      "const HPR_AXIS_LEGACY="):
            if tpl51.count(sym51) != 1:
                bad51.append("%s 不是恰好一面" % sym51)
        if "control:'stability'" not in tpl51 or "flex:'mobility'" not in tpl51:
            bad51.append("HPR_AXIS_LEGACY 没把旧轴 control/flex 归位到新轴")
        if ("function hprAxisScore" in tpl51 and "function hprRadarPoints" in tpl51
                and "currentGl()" not in tpl51[tpl51.index("function hprAxisScore"):tpl51.index("function hprRadarPoints")]):
            bad51.append("hprAxisScore 强度轴没经 currentGl 现读")
        # D. 内置种子：六轴全覆盖，且耐力轴两个子组（稳态 / 间歇）都有默认条目
        if "function hprBuiltin" in tpl51 and "function hprNormalize" in tpl51:
            b0 = tpl51.index("function hprBuiltin")
            seg51 = tpl51[b0:tpl51.index("function hprNormalize", b0)]
            n_items = seg51.count("{id:'hpr_")
            seen_axes = set(re.findall(r"axis:'([a-z]+)'", seg51))
            want_axes = {"strength", "endurance", "stability", "power", "mind", "mobility"}
            if seen_axes != want_axes:
                bad51.append("hprBuiltin 没覆盖全部六轴（现 %r）" % (sorted(seen_axes),))
            if n_items != 22:
                bad51.append("hprBuiltin 不是恰好 22 项（现 %d）" % n_items)
            if seg51.count("sub:'cardio'") < 1 or seg51.count("sub:'interval'") < 1:
                bad51.append("耐力轴缺默认子组（cardio / interval 各至少一条）")
        else:
            n_items = -1
        # E. 雷达看板落在 AUX：hprBoard 一面 + 双语标题 + viewBox 六边形 + 360px 降档 + 每写一次统一重绘
        if tpl51.count('id="hprBoard"') != 1:
            bad51.append("hprBoard 看板不是恰好一面")
        if tpl51.count('<svg viewBox="0 0 200 200"') != 1:
            bad51.append("雷达六边形 viewBox 不是恰好一份")
        if tpl51.count("六边形能力记录") < 1:
            bad51.append("雷达看板缺双语标题")
        if "@media(max-width:360px){.hpr-radar" not in tpl51:
            bad51.append("雷达没有 360px 窄屏降档")
        if tpl51.count("renderHpr();") < 5:
            bad51.append("记录写入后没统一重绘（renderHpr 调用 < 5）")
        # F. 成品同段：忘跑 build_html / 手改成品都会在这先响
        prod51 = read(ASSET)
        for sym51 in ("const HPR_AXES=[", "function currentGl(", "function hprAxisScore(",
                      'id="hprBoard"', "renderHpr();"):
            if prod51.count(sym51) != tpl51.count(sym51):
                bad51.append("成品里 %s 与模板不同段" % sym51)
        chk("S51", "六边形能力记录接线：六轴 HPR_AXES 单源且 id 恰好六轴 / hpr 只在 WORK+IMPORT 双名单绝不进 PLAN_OWNED 与契约列 / "
            "hprComplete·hprAxisScore·hprNormalize·hprRadarPoints·currentGl·hprBuiltin 各一面 / "
            "力量轴经 currentGl 现读 GL 绝不存死数 / 内置覆盖六轴且耐力两子组都有条目 / 旧轴读时归位 / 雷达落 AUX 双语 + viewBox + 360px 降档 + 写后重绘 / 成品同段",
            not bad51,
            "OK（六轴 %s / 内置 %d 项 / 名单 2 处 / 成品同段）" % ("/".join(ids51), n_items)
            if not bad51 else " / ".join(bad51[:6]))
    except (OSError, ValueError, KeyError) as e:
        chk("S51", "六边形能力记录接线", False, e)


# ---------- 动态 ----------

def _plan_roundtrip():
    """seed → 六表工作簿 → state → 再工作簿，逐格必须零差异（在 gate 进程内跑，不落临时目录）。

    D6 管的是契约的**规则**；这条管的是**当前这份 seed** 走完全程不丢格 ——
    种子数据形状变了（新周、新动作、锚点缺值）只会在这里红。
    """
    import plan_xlsx as px
    sch = px.load_schema()
    seed = px.load_default_seed()
    if seed is None:
        return False, "读不到 tools/seed.json"
    plan = px.state_to_plan_dict(seed, sch)
    state, again, diff = px.roundtrip_plan(plan, base_seed=seed, sch=sch)
    errs = px.validate_plan_dict(again, proto=seed.get("proto"), lib=seed.get("lib"), sch=sch)["errors"]
    ok = not diff["diffs"] and not errs
    return ok, "%d 格 → %d 格 / 差异 %d / error %d" % (
        diff["cells_a"], diff["cells_b"], len(diff["diffs"]), len(errs))


DYNAMIC = [
    ("D1", "v3v.js（主回归）", ["node", os.path.join(HERE, "v3v.js")], APK),
    ("D2", "v2v.js（v0.02 判据）", ["node", os.path.join(HERE, "v2v.js")], APK),
    ("D3", "check_hud.js（四档宽度）", ["node", os.path.join(HERE, "check_hud.js")], APK),
    # D4 / D5 是 PC 端项目（desktop/tests/）的两套回归，v0.13 该项目整体归档后退役。
    # 编号保留不复用：历史文档与 _sabotage_* 里出现的 D4/D5 永远指同一件事。
    # 覆盖是真的少了一截，写清楚少在哪：那两套守的是「外科式改写权威 xlsx 的 zip 条目并保住
    # 条件格式/样式」与「PC 读侧公式·周期·CSV 解析」。前者是 desktop 独有的能力——主线从不写
    # Excel（数据单向：xlsx → seed → 成品），所以它不再属于任何会发货的代码路径；
    # 后者的同类不变量在主线由 D6（六表契约）+ D7（seed 往返零格差）+ D8（App 内引擎与 Python
    # 逐格对账）覆盖，CSV 26 列协议本身自 v0.13 起由 S7 三方冻结（契约 / 模板 / 成品）。
    ("D6", "test_plan_xlsx.py（六表契约 T1–T8）", [sys.executable, os.path.join(HERE, "test_plan_xlsx.py")], APK),
    ("D7", "plan_xlsx 导出 → 往返零格差", _plan_roundtrip, None),
    ("D8", "xlsxv.js（App 内工作簿引擎与 plan_xlsx 逐格对账）", ["node", os.path.join(HERE, "xlsxv.js")], APK),
    ("D9", "logicv.js（数值格式对账 + 八段逻辑回归）", ["node", os.path.join(HERE, "logicv.js")], APK),
    ("D10", "uiv.js（全量面板 × 四档宽度 UI 遍历 + 零副作用对账）", ["node", os.path.join(HERE, "uiv.js")], APK),
    # D11（v0.30）：反向验证驱动器自己的判定自检。它跑的是纯函数对假数据（judge 的每个出口
    #   + S26 双腿拆分的每条 detail），不注入、不建台账，所以秒级、连 --quick 也不跳过。
    #   为什么要有这一条：sabr.py 是「断言必须能红」的执行器，它一旦钝了（比如把「期望的腿没红」
    #   判成 PASS），后面每一版引用的「已反向验证」都是假的——而 gate 其余部分全绿也不会报错。
    #   反向验证（本轮实测，非设想）：把 judge() 的判定条件 `hit and not miss and not extra` 削成
    #   只剩 `restored and green`（= 只看还原与回绿，不再核对待测腿）→ `gate.py --quick` 报
    #   `FAIL D11`，detail 是 `[-- 判定出口 N 条 / 2 FAIL --]`（N 随出口数变，别抄进任何文档）；
    #   同样把 s26_corroborated() 削成恒真（= 拿台账残留当指针腿的证据）也报 2 FAIL、--quick 其余项照旧绿。
    #   两种削法改回即恢复（逐字节比对相同）。
    #   顺便记一条边界：只摘 `not miss` 或只把 `hit` 换成恒真这两种更小的削法，selftest 仍判 0 ——
    #   因为那两条出口彼此兜着（hit 为空 ⇔ 没红）。要削到「整条腿不看」才露馅，说明这两个出口不是凑数。
    ("D11", "sabr.py selftest（反向验证驱动器的判定出口自检）", [sys.executable, os.path.join(HERE, "sabr.py"), "selftest"], APK),
    # D12（v0.31 节点③b）：配重引擎专属回归。既有套件只从 UI / 杠铃口径间接路过 Resolver，
    #   六类 kind 的 effective/step/recipe/warnings、库存→步长、调用点改道这些分支没有一条
    #   断言直接盯着；反向验证 _sabotage_g1.py 的 witness 也落在这套上。
    ("D12", "gearv.js（配重引擎六类/步长/处方/调用点）", ["node", os.path.join(HERE, "gearv.js")], APK),
]


def _run_dynamic(cmd):
    """跑一条动态检查，返回 (ok, 摘要)。浏览器套件仍由 dynamic_checks 串行调度。"""
    if callable(cmd):                          # 进程内检查：返回 (ok, 摘要)
        try:
            return cmd()
        except Exception as e:
            return False, "%s: %s" % (type(e).__name__, e)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        tail = [l for l in out.splitlines() if l.strip()]
        summary = next((l for l in reversed(tail) if "汇总" in l or "passed" in l),
                       tail[-1] if tail else "无输出")
        return r.returncode == 0, summary
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "%s: %s" % (type(e).__name__, e)


# 只有不启 Chrome 的三套可以并行：D6 六表契约（Python）、D7 往返零格差（进程内）、
# D11 sabr 自检。浏览器套件共用 9890–9899 端口池，并发会撞端口造成假红，必须串行。
PARALLEL_IDS = ("D6", "D7", "D11")


def dynamic_checks(quick=False):
    skip = ("D3", "D6", "D7", "D8", "D9", "D10", "D12") if quick else ()
    pre = {}
    par = [e for e in DYNAMIC if e[0] in PARALLEL_IDS and e[0] not in skip]
    if par:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(par)) as pool:
            futs = {e[0]: pool.submit(_run_dynamic_in_cwd, e[2], e[3]) for e in par}
            for cid, fut in futs.items():
                pre[cid] = fut.result()
    for cid, name, cmd, cwd in DYNAMIC:
        if cid in skip:
            continue
        ok, detail = pre[cid] if cid in pre else _run_dynamic_in_cwd(cmd, cwd)
        chk(cid, name, ok, detail)


def _run_dynamic_in_cwd(cmd, cwd):
    """与 _run_dynamic 相同，但把 cwd 传进子进程（TYPE=APK 的套件依赖工作目录）。"""
    if callable(cmd):
        return _run_dynamic(cmd)
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=900)
        out = (r.stdout or "") + (r.stderr or "")
        tail = [l for l in out.splitlines() if l.strip()]
        summary = next((l for l in reversed(tail) if "汇总" in l or "passed" in l),
                       tail[-1] if tail else "无输出")
        return r.returncode == 0, summary
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "%s: %s" % (type(e).__name__, e)


def main():
    global VERBOSE
    ap = argparse.ArgumentParser(description="构建链守卫")
    ap.add_argument("--static", action="store_true", help="只跑静态检查")
    ap.add_argument("--dynamic", action="store_true", help="只跑全量回归")
    ap.add_argument("--quick", action="store_true", help="动态只跑 v3v + v2v")
    ap.add_argument("--verbose", action="store_true", help="逐条打印 PASS（默认只打 FAIL）")
    args = ap.parse_args()
    global VERBOSE
    VERBOSE = args.verbose
    pyout.use_utf8_stdout()

    if not args.dynamic:
        static_checks()
    if not args.static:
        dynamic_checks(quick=args.quick)

    n_fail = sum(1 for ok, *_ in results if not ok)
    print("\n== gate: %d PASS / %d FAIL （共 %d 项）==" % (len(results) - n_fail, n_fail, len(results)))
    if n_fail:
        print("未通过项：" + ", ".join(cid for ok, cid, *_ in results if not ok))
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
