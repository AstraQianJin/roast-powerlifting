# -*- coding: utf-8 -*-
"""反向验证驱动器（v0.30 开发便利）：把 AGENTS.md §2 第 6 条那条仪式压成一条命令。

以前核对「这条断言真有牙」要人肉跑六步：清台账 → inject N → build_html → 跑三套回归
→ 逐条比对期望 → revert → 再 build → 复跑确认回绿。任何一步忘了都出假结论
（最常见的是带故障提交了，或还原后忘了重建，S5 下一版才红）。这一条把它固化：

    python tools/sabr.py list n2               # 这一家有几处靶、各自期望红在哪
    python tools/sabr.py run n2 45 --with ui   # 注 → 建 → 跑 → 对账 → 还原 → 建 → 复跑
    python tools/sabr.py run n2 33 34 35 36    # 按组（默认只跑静态层，秒级）
    python tools/sabr.py run n2 43 --with all  # 静态 + v3v + uiv + xlsxv + logicv + v2v
    python tools/sabr.py run b4 --with plan    # inject() 不收参数那几家：不给靶号，整族合注取期望并集
    python tools/sabr.py check                 # 不带注入：只看台账是否干净、家还认不认得
    python tools/sabr.py selftest              # 秒级：查这台驱动器自己的判定会不会红
    python tools/sabr.py selftest --live       # 再加一轮真注入：故意报错期望，它必须判 FAIL

--with 的档位：static（默认，秒级）/ fast（+v3v）/ ui（+uiv）/ all（全六套）。

selftest 那一段不是可选的润色：gate 的 D11 就盯着它（秒级、不注入，连 --quick 也不跳过）。
这台驱动器是「断言必须能红」的执行器，它一旦把「期望的腿没红」判成 PASS，之后每一版引用的
「已反向验证」都不作数 —— 而其余门禁照旧全绿，不会有任何别的报错替我们发现。

四件事缺一件就判 FAIL，不许悄悄放行：
  ① 注入前台账必须是空的（带台账再注入 = 把半套原文存进台账，之后还原不可信）
  ② 注入态里期望的那几条腿真变红（这是「有牙」的唯一证据；恒真断言等于没有断言）
  ③ 还原后被改过的文件逐字节回到注入前（自己算哈希，不信 revert 的口头回执）
  ④ 还原 + 重建后回归回到全绿（红着没收干净 = 这一轮做的任何事都不可信）

期望从各家的 EXPECT 表里读，不另抄一份：EXPECT 是自由文本，这里只提两类令牌——
形如 S33 / LD14 / X3c / TD1 / N1 的断言号，以及「uiv / v3v / xlsxv」这套名。
文本里点到某一套而 --with 没开那套，本条判 SKIP 并说明缺哪一层（不判 PASS，
因为「没跑」和「跑了没红」是两件事）。这一家没有 EXPECT 表时退到最弱的合格线：
注入态至少红一条 + 还原后全绿，并把实到的红项全列出来交人过一眼。
反过来，EXPECT 里只写腿名不写套件名的（F22「LD15 红 + S19 红」这种老写法），静态层
取不到那条腿，会判 FAIL 并把实到全列出来 —— 那不是断言没牙，是开的层不够，换 --with fast 重跑即可。

不要在注入态跑 pack.py：这一族命令全程不碰发版链，还原走 revert + 重建，收尾必回绿。
"""
import glob
import hashlib
import inspect
import importlib.util
import io
import json
import os
import re
import subprocess
import sys

import pyout

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TOOLS = HERE

# --with 的档位：每档 = 跑哪几套。静态层最便宜，默认只跑它。
PRESETS = {
    "static": ["static"],
    "fast":   ["static", "v3v"],
    "ui":     ["static", "v3v", "uiv"],
    "plan":   ["static", "contract"],
    "gear":   ["static", "gearv"],
    "all":    ["static", "v3v", "uiv", "xlsxv", "logicv", "v2v", "contract", "gearv"],
}


def node(name):
    return [os.environ.get("NODE", "node"), os.path.join(TOOLS, name)]


SUITES = {
    "static": ([sys.executable, os.path.join(TOOLS, "gate.py"), "--static"], "gate --static"),
    "v3v":    (node("v3v.js"), "v3v.js"),
    "uiv":    (node("uiv.js"), "uiv.js"),
    "xlsxv":  (node("xlsxv.js"), "xlsxv.js"),
    "logicv": (node("logicv.js"), "logicv.js"),
    "v2v":    (node("v2v.js"), "v2v.js"),
    # D12（v0.31）：配重引擎专属回归，_sabotage_g1.py 的 F1–F9 witness 全落在这里
    "gearv":  (node("gearv.js"), "gearv.js"),
    # 六表契约那套是 Python 的（gate 的 D6），b4 那一家反向验证的腿全在这里
    "contract": ([sys.executable, os.path.join(TOOLS, "test_plan_xlsx.py")], "test_plan_xlsx.py"),
}


def sh(cmd, tag):
    """跑一套，回 (返回码, 实到的红项号列表, 原始输出尾部)。取不到红项不报错，交给调用方判。"""
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=3600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, [], "%s 起不来：%s" % (tag, e)
    out = (p.stdout or "") + (p.stderr or "")
    reds = [m.group(1) for m in re.finditer(r"(?m)^FAIL\s+(\S+)", out)]
    return p.returncode, reds, out


def heard(out):
    """套件有没有真的开口说话。每套回归结尾都是「== X 汇总: N PASS / M FAIL …==」；
    取不到这行就是探针哑了（崩在半路 / 输出被吞），此时它的「绿」不作数。"""
    return bool(re.search(r"\d+ PASS /", out))


def fail_details(out):
    """红项号 → 它行尾 [ ... ] 里的原因原文。取不到 detail 的项不进表（调用方按「没证据」办）。"""
    found = {}
    for m in re.finditer(r"(?m)^FAIL\s+(\S+).*?\[([^\]]*)\]", out):
        found[m.group(1)] = m.group(2)
    return found


RESIDUE = r"注入态残留台账（[^）]*）：[^/]*"


def s26_corroborated(detail):
    """S26 这次红，是不是「版本指针漂移」那条腿红的，而不是台账残留。
    S26 有两条腿：①注入态有 _sabotage_*.json 残留 ②四处指针跟 gradle 不等。
    ①是这台驱动器自己留下的痕迹（任何一家、任何一注都红），拿它当 r1 那四条「指针腿有牙」
    的证据等于恒真断言（红线 6）；所以 detail 里除了①还剩别的东西才许算实到，
    detail 为空同样按「没证据」判。"""
    return bool(re.sub(RESIDUE, "", detail or "").strip(" /"))


def digest(path):
    if not os.path.exists(path):
        return "缺失"
    h = hashlib.sha1()
    with io.open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()[:16]


def load_family(fam):
    """按文件名加载某一家反向验证脚本，取出 inject / revert / FAULTS(或 MUT) / EXPECT。"""
    p = os.path.join(TOOLS, "_sabotage_%s.py" % fam)
    if not os.path.exists(p):
        raise SystemExit("找不到 %s（可选的家见 tools/_sabotage_*.py）" % p)
    spec = importlib.util.spec_from_file_location("sab_%s" % fam, p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    faults = getattr(mod, "FAULTS", None) or getattr(mod, "MUT", None) or getattr(mod, "GROUPS", None)
    if faults is None:
        raise SystemExit("%s 里没有 FAULTS / MUT / GROUPS，驱动器读不出靶串" % fam)
    return {
        "path": p, "mod": mod, "faults": faults,
        "inject": getattr(mod, "inject", None),
        "revert": getattr(mod, "revert", None),
        "expect": getattr(mod, "EXPECT", None),
    }


def touched_files(faults, idx):
    """这一条靶会动哪些文件（逐字节比对就盯这几个）。元组第一/二位里取路径样字符串。"""
    out = set()
    try:
        item = faults[idx - 1]
    except (IndexError, TypeError):
        return out
    for cell in (item if isinstance(item, (list, tuple)) else [item]):
        if isinstance(cell, str) and (cell.endswith((".py", ".html", ".json", ".js", ".java"))):
            p = cell if os.path.isabs(cell) else os.path.join(ROOT, cell)
            if os.path.exists(p):
                out.add(os.path.normpath(p))
    if not out:
        out.add(os.path.normpath(os.path.join(TOOLS, "template.html")))
    return out


def expect_of(fam_info, idx, why):
    """把期望文本切成 (断言号集合, 点到的套件名集合)。没有 EXPECT 就退回 why 里的说法。

    两段过滤是必要的，不是修饰：
      · 「S34 全绿属预期」这种句子提到断言号，说的是它不该红 —— 不收进期望，
        否则一条正常靶会被判成「期望的腿没红」。
      · 「uiv B 段」写的是段名不是断言号，实到的红项号正是 B / N 这样的裸字母，
        所以单独把「X 段」收进来。
    """
    exp = fam_info.get("expect") or {}
    txt = ""
    if isinstance(exp, dict):
        txt = exp.get(idx, "") or ""
    if not txt and isinstance(why, str):
        txt = why
    # 「什么坏了 → 该红在哪」这类写法里，箭头**前面**是故障描述，不是期望。
    # 不切开就会把描述里的名字当成断言号：b4 的 F04 写「D4 归档+冻结失效 → T6.3 红」，
    # 整句扫会多收一个 D4（那是契约里的决策号，任何套件都不会以它表态），合注判定就永远差一条。
    if "→" in txt:
        txt = txt.rsplit("→", 1)[1]
    ids = set()
    own = ("F%d" % idx, "F%02d" % idx)
    for m in re.finditer(r"[A-Z]{1,4}[0-9]+(?:[a-z])?", txt):
        tok = m.group(0)
        tail = txt[m.end():m.end() + 6]
        if "全绿" in tail or "属预期" in tail:
            continue
        if tok in own and m.start() < 8:
            # 开头那个 F3 是这一条靶自己的编号（「F3 上限手抄 → S30 红」），不是期望红在哪条腿。
            # 不摘掉它，实到永远少一项，每条靶都会被误判成「期望的腿没红」。
            continue
        if re.match(r"^(V[0-9]|S[0-9]{3}|W[0-9]{3}|P[0-9]{3}|V[0-9]{2})", tok):
            continue        # 版本号 / 320px 那类宽度串 / 周名，不是断言号
        ids.add(tok)
    for m in re.finditer(r"(?<![A-Za-z0-9])([A-Z])(?= 段)", txt):
        tail = txt[m.end():m.end() + 6]
        if "全绿" not in tail:
            ids.add(m.group(1))
    suites = {s for s in ("uiv", "v3v", "xlsxv", "logicv", "v2v", "contract", "gearv") if re.search(r"\b%s\b" % s, txt)}
    return ids, suites, txt


def ledgers():
    return [os.path.basename(p) for p in
            glob.glob(os.path.join(TOOLS, "_sabotage_*.json"))]


def rebuild(chain):
    """重建：默认 gen_seed（幂等，实测同哈希）+ build_html，覆盖两家靶的落点。"""
    for script in chain:
        p = subprocess.run([sys.executable, os.path.join(TOOLS, script)],
                           cwd=ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
        if p.returncode != 0:
            return False, "%s 非 0 退出：%s" % (script, (p.stderr or p.stdout)[-200:])
    return True, "OK"


def inject_shape(fn):
    """这一家的 inject 收什么形状：list / int / 只认全注（0 个必填参数）。
    按签名判而不是先试再吞 TypeError —— 试错法在「函数已经改了一半磁盘才抛 TypeError」时
    会留下半注入状态（m5 那一家的第 3 条就是这么留下的），所以宁可观形状。
    带默认值的形参也算数：这十几家写作 `inject(pick=None)`，「不给 = 全注、给了 = 单点」，
    只数必填形参会把它们全认成「只认全注」，于是单点跑法悄悄退化成整族合注。"""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return "unknown"
    pos = [q for q in sig.parameters.values()
           if q.kind in (q.POSITIONAL_ONLY, q.POSITIONAL_OR_KEYWORD)]
    if not pos:
        return "all"
    p0 = pos[0].name.lower()
    return "list" if p0 in ("idxs", "ids", "picked", "groups", "sel") else "int"


def call_inject(info, idx):
    """返回实际注入的形状：单点（list/int）回该靶号；这一家只会「全注」时回 "all"。"""
    fn = info["inject"]
    if fn is None:
        raise SystemExit("这一家没有 inject()，驱动器不猜它怎么注入")
    shape = inject_shape(fn)
    if shape == "unknown":
        raise SystemExit("读不出 inject 的参数形状，不硬猜（交回人按它自己的 docstring 跑）")
    try:
        if shape == "all":
            fn()
            return "all"
        arg = [idx] if shape == "list" else idx
        fn(arg)
        return idx
    except SystemExit as e:
        raise SystemExit("注入第 %d 处失败：%s" % (idx, e))


def run(fam, idxs, with_key, chain, expect_override=None):
    """跑一轮完整仪式。expect_override 只给 selftest 用：故意报错期望，
    验证这台驱动器自己会判 FAIL —— 判据本身不能是恒真的。"""
    info = load_family(fam)
    suites = PRESETS.get(with_key)
    if suites is None:
        suites = [x.strip() for x in with_key.split(",") if x.strip()]
    for s in suites:
        if s not in SUITES:
            raise SystemExit("不认识的套件名：%s（可选 %s）" % (s, "、".join(sorted(SUITES))))
    bad = ledgers()
    if bad:
        raise SystemExit("注入前台账不干净：%s —— 先跑对应家的 revert，别在残留态上做反向验证" % "、".join(bad))
    n = len(info["faults"])
    # 有几家的 inject() 不收参数（b4 / b5 / m1 / r1…）：一注就是全族一起注。
    # 这时按单条靶的期望对账必然看到「别处的腿也红了」，所以改成整族合注一条判定、
    # 期望取全族并集。硬把它当单点跑 = 每条都报意外红，那是驱动器在骗人而不是靶有问题。
    forced_all = info["inject"] is not None and inject_shape(info["inject"]) == "all"
    if forced_all:
        print("%s 家的 inject 只认「全注」→ 整族合注 %d 处，期望取全族并集" % (fam, n))
        idxs = [0]
    elif not idxs:
        raise SystemExit("没收到靶号：%s 家有 %d 处单点靶，给 1..%d（不带编号只适用于「只认全注」那几家）" % (fam, n, n))
    for i in idxs:
        if not forced_all and not 1 <= i <= n:
            raise SystemExit("%s 家只有 %d 处靶（收到 %d）" % (fam, n, i))
    print("== sabr：家 %s / 靶 %s / 层 %s ==" % (fam, ",".join(str(i) for i in idxs), "+".join(suites)))
    results, hard = [], 0
    for idx in idxs:
        why = ""
        try:
            why = fault_why(info["faults"][idx - 1])
        except (IndexError, TypeError):
            pass
        if forced_all:
            exp_ids, exp_suites = set(), set()
            for k in range(1, n + 1):
                e_id, e_su, _ = expect_of(info, k, fault_why(info["faults"][k - 1]))
                exp_ids |= e_id
                exp_suites |= e_su
            exp_txt = "全族 %d 处合注（这一家不支持单点注入，期望取并集）" % n
        else:
            exp_ids, exp_suites, exp_txt = expect_of(info, idx, why)
        if expect_override:
            exp_ids, exp_txt = {expect_override}, "（selftest 故意报的期望，不是 EXPECT 表里的）"
        missing_layers = {s for s in exp_suites if s not in suites}
        watch = (set().union(*[touched_files(info["faults"], k) for k in range(1, n + 1)])
                 if forced_all else touched_files(info["faults"], idx))
        before = {p: digest(p) for p in watch}
        ok, why_run = rebuild(chain)
        if not ok:
            print("  %s：基线重建就失败（%s），这一条不做注入" % (label(idx, forced_all), why_run))
            hard += 1
            results.append((idx, "FAIL", "基线重建失败"))
            continue
        rc0, base_reds, out0 = sh(SUITES["static"][0], "gate --static")
        if not heard(out0):
            print("  %s：静态层没吐出汇总行（探针哑了），这一条不做注入" % label(idx, forced_all))
            hard += 1
            results.append((idx, "FAIL", "静态层无输出"))
            continue
        if rc0 != 0 or base_reds:
            print("  %s：注入前静态层不绿（%s）→ 先修基线，本轮不判定" % (label(idx, forced_all), base_reds[:4]))
            hard += 1
            results.append((idx, "FAIL", "基线不绿"))
            continue
        got = call_inject(info, idx)
        if forced_all and got != "all":
            raise SystemExit("认成「全注」的形状却按单点注入了 → 停下：并集期望不能对一个单点结果")
        ok, why_run = rebuild(chain)
        observed, by_suite, details, inject_err = set(), {}, {}, None
        for s in suites:
            rc, reds, out = sh(SUITES[s][0], SUITES[s][1])
            if rc is None:
                inject_err = SUITES[s][1] + " 起不来"
                break
            if not heard(out):
                # 读不到汇总行 = 探针自己哑了。哑掉的绿不算绿，宁可直接判死，
                # 也别让它参加「实到 / 意外红」的比对（那会把驱动器骗成「期望的腿没红」）。
                inject_err = "%s 没吐出汇总行（输出取不到，判定不作数）" % SUITES[s][1]
                break
            by_suite[s] = reds
            observed |= set(reds)
            for k, v in fail_details(out).items():
                details.setdefault(k, v)
        if inject_err:
            info["revert"]()
            rebuild(chain)
            print("  %s：FAIL —— %s" % (label(idx, forced_all), inject_err))
            hard += 1
            results.append((idx, "FAIL", inject_err))
            continue
        # S26 的「台账残留」那条腿在任何一家注入态都红，那是驱动器自己留下的痕迹，不是靶的证据。
        # 只有当它的 detail 里除残留外还报了版本指针漂移，S26 才留在实到里；
        # 否则摘掉 —— 对期望 S26 的 r1 一家，摘掉就是「指针腿没红」= FAIL；
        # 对改模板那几家，摘掉是免掉一条必现的噪音，不该混进「意外红」淹没真信号。
        if "S26" in observed and not s26_corroborated(details.get("S26", "")):
            observed.discard("S26")
            by_suite = {k: [x for x in v if x != "S26"] for k, v in by_suite.items()}
        # 「uiv B 段」这类期望写的是段名，实到的红项号是 B3、B5 …… 所以单字母令牌按前缀配对；
        # 其余（S33 / LD14 / X3c）按全等或「T-」子编号配对。
        def spoke(t, obs):
            """期望令牌 ↔ 实到红项号。三种形状都要认，但不许认过头：
              · 「B 段」这类单字母段名 → 只认后面纯数字的（B3 算，BD1 不算 —— 那是另一段）
              · 「T2」对「T2.17」、「S19」对「S19」→ 只认 . _ - 分隔的子编号（N10 不能顶 N1）
              · 其余按全等
            """
            if t in obs:
                return True
            if len(t) == 1:
                return any(re.fullmatch(r"[0-9]+", o[len(t):]) for o in obs if o.startswith(t))
            pat = re.compile(r"^%s(?:[._-][0-9a-z]+)?$" % re.escape(t))
            return any(pat.match(o) for o in obs)

        hit = sorted(t for t in exp_ids if spoke(t, observed))
        miss = sorted(exp_ids - set(hit))
        extra = sorted(o for o in observed if not any(spoke(t, {o}) for t in exp_ids))
        info["revert"]()
        after = {p: digest(p) for p in watch}
        restored = all(before[p] == after[p] for p in before)
        ok, why_run = rebuild(chain)
        rc2, reds2, out2 = sh(SUITES["static"][0], "gate --static")
        green = (rc2 == 0 and not reds2 and heard(out2)) and ok
        verdict, note = judge(exp_ids, hit, miss, extra, observed,
                              restored, green, missing_layers, bool(info.get("expect")))
        print("  %-8s %s —— %s\n           期望原文：%s" % (label(idx, forced_all), verdict, note, (exp_txt or why)[:110]))
        results.append((idx, verdict, note))
        if verdict == "FAIL":
            hard += 1
    print("== sabr 汇总：%d PASS / %d SKIP / %d FAIL（共 %d 条）==" % (
        sum(1 for r in results if r[1] == "PASS"),
        sum(1 for r in results if r[1] == "SKIP"), hard, len(results)))
    return 1 if hard else 0


def label(idx, forced_all=False):
    return "全族合注" if forced_all else "F%02d" % idx


def list_family(fam):
    info = load_family(fam)
    print("%s：%d 处靶" % (fam, len(info["faults"])))
    for i in range(1, len(info["faults"]) + 1):
        exp = (info.get("expect") or {}).get(i, "") if isinstance(info.get("expect"), dict) else ""
        why = ""
        try:
            why = fault_why(info["faults"][i - 1])
        except (IndexError, TypeError):
            pass
        print("  F%02d  %s" % (i, (exp or why)[:150]))


def fault_why(item):
    """故障表里那句人话（期望红在哪）。各家形状不一：4 格的（n2 / w1）第三格就是它，
    3 格的（b4）最后一格才是。按位取会在 3 格形状上退化成 str(item)，
    于是期望原文变成整个元组的 repr —— 读起来像坏了，其实是被检文本压根不是人话。"""
    if isinstance(item, (list, tuple)):
        cells = [c for c in item if isinstance(c, str)]
        # 末格是说明，前面几格是靶文件与原文/替换串（各家都这个顺序）。
        # 取「最长那一格」会选中代码原文：b4 的 F03 实测就是这样，列出来全是 `res["warnings"]…`。
        for c in reversed(cells):
            if not c.endswith((".py", ".html", ".json", ".js", ".java")):
                return c
        return " / ".join(cells)
    return str(item)


def judge(exp_ids, hit, miss, extra, observed, restored, green,
          missing_layers, has_expect):
    """这一条靶算不算过。判定单独成函数，是为了能被 selftest 直接喂假数据检查（见下）。"""
    if missing_layers:
        return "SKIP", "期望还点了 %s，但 --with 没开那层，本条只核对了静态那部分" % "、".join(sorted(missing_layers))
    if exp_ids:
        v = "PASS" if (hit and not miss and not extra and restored and green) else "FAIL"
        return v, ("期望 %s / 实到 %s / 意外红 %s / 还原 %s / 复跑回绿 %s" % (
            "、".join(sorted(exp_ids)) or "无",
            "、".join(hit) or "无", "、".join(extra[:6]) or "无",
            "逐字节相同" if restored else "未还原",
            "是" if green else "否"))
    v = "PASS" if (observed and restored and green) else "FAIL"
    return v, ("这家没 EXPECT 表 → 只按「注入态至少红一条 + 还原后回绿」判；实到 %s / 还原 %s / 复跑回绿 %s" % (
        "、".join(sorted(observed)[:6]) or "无", "逐字节相同" if restored else "未还原",
        "是" if green else "否"))


def selftest(live_expect=None):
    """这台驱动器自己的判定也必须能红。

    第一段（秒级）：喂假数据把 judge 的每个出口钉一次。凡是「本该 FAIL 却判成 PASS」的，
    说明这台机器在骗人，它之后给出的每一句「反向验证通过」都不作数。
    第二段（--live，多花一轮注入）：真注 n2 的 F33（只会红 S33），却把期望报成
    S34 —— 注定对不上，驱动器必须判 FAIL 并非 0 退出。它若「通过」，说明它根本没在
    比对待测项，只是在复述套件退出码。
    """
    E, O = {"S33"}, {"S33"}
    cases = [
        ("期望腿真红 → PASS", (E, ["S33"], [], [], O, True, True, set(), True), "PASS"),
        ("期望的腿没红（恒真断言的样子） → FAIL", (E, [], ["S33"], [], set(), True, True, set(), True), "FAIL"),
        ("注出期望之外的红（见证故事不对） → FAIL", (E, ["S33"], [], ["S05"], O | {"S05"}, True, True, set(), True), "FAIL"),
        ("还原后文件漂移 → FAIL", (E, ["S33"], [], [], O, False, True, set(), True), "FAIL"),
        ("还原复跑仍红着 → FAIL", (E, ["S33"], [], [], O, True, False, set(), True), "FAIL"),
        ("期望点了没开的层 → SKIP（不冒充 PASS）", (E, ["S33"], [], [], O, True, True, {"uiv"}, True), "SKIP"),
        ("这家没 EXPECT，注入态一条都没红 → FAIL", (set(), [], [], [], set(), True, True, set(), False), "FAIL"),
        ("这家没 EXPECT，注入态红了 → PASS", (set(), [], [], [], O, True, True, set(), False), "PASS"),
    ]
    bad = 0
    print("== sabr selftest：判定出口自检 ==")
    for name, args, want in cases:
        got = judge(*args)[0]
        ok = got == want
        bad += 0 if ok else 1
        print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "（实到 %s）" % got))
    total = len(cases)
    # S26 的两条腿必须分得开。喂 gate 自己的原话形状：只有台账残留那种detail
    # 一旦算实到，r1 那四条「指针腿有牙」的结论就变成恒真 —— 证据其实是这台驱动器留下的痕迹。
    probes = [
        ("detail 只有台账残留 → 不算实到",
         "注入态残留台账（先 revert 再发版）：_sabotage_r1.json", False),
        ("残留 + 指针漂移都在（注入态的真实 detail） → 算实到",
         "注入态残留台账（先 revert 再发版）：_sabotage_r1.json / 根 README 身份行 写的是 v0.00/code 0，gradle 是 vX/code N", True),
        ("只有指针漂移（人肉 inject 时的 detail） → 算实到",
         "CHANGELOG 头条 写的是 v0.00/code —，gradle 是 vX/code N", True),
        ("detail 取不到 → 不算实到（没证据不等于没问题）", "", False),
    ]
    print("-- S26 双腿拆分 --")
    for name, det, want in probes:
        got = s26_corroborated(det)
        ok = got == want
        bad += 0 if ok else 1
        print("  %s  %s%s" % ("PASS" if ok else "FAIL", name, "" if ok else "（实到 %s）" % got))
    total += len(probes)
    print("-- 判定出口 %d 条 / %d FAIL --" % (total, bad))
    if bad:
        return bad
    if not live_expect:
        print("（未跑 live 注入自检：加 --live 会真注一条、故意报错期望，验这台机器会拒绝）")
        return 0
    print("== sabr selftest --live：注 n2 F33、期望故意写成 %s，必须判 FAIL ==" % live_expect)
    hard = run("n2", [33], "static", ["gen_seed.py", "build_html.py"], expect_override=live_expect)
    if hard == 0:
        print("FAIL  L1 假期望被驱动器判成通过 —— 这台驱动器没有牙，它的「PASS」不能采信")
        return 1
    print("PASS  L1 假期望确实被判红（驱动器会拒绝对不上账的那次运行）")
    return 0


def main(argv):
    # 读子进程输出必须钉死 UTF-8：跟随码页时这台机器会把子进程的中文吐成乱码字节，
    # reds 正则一条都匹配不上 → 「实到 无」→ 明明真有牙的靶被判成期望的腿没红。
    pyout.use_utf8_stdout()
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "check":
        bad = ledgers()
        if bad:
            print("台账残留：%s" % "、".join(bad))
            return 1
        fams = sorted(os.path.basename(p)[len("_sabotage_"):-3]
                      for p in glob.glob(os.path.join(TOOLS, "_sabotage_*.py")))
        ok_fam, unreadable = [], []
        for f in fams:
            # 这一族脚本里有几家 import 期就自己读 sys.argv 并 sys.exit(__doc__)。
            # 驱动器不迎合它：那类家留给人按它自己的文档跑，硬凑参数等于替它动手注入。
            try:
                info = load_family(f)
                if info["inject"] is None or info["revert"] is None:
                    unreadable.append("%s（没有 inject/revert 这对入口）" % f)
                else:
                    ok_fam.append(f)
            except BaseException as e:
                unreadable.append("%s（import 期即 %s：%s）" % (f, type(e).__name__, str(e)[:44]))
        print("家 %d 个：可驱动 %d 个（%s）" % (len(fams), len(ok_fam), "、".join(ok_fam)))
        if unreadable:
            print("读不出 %d 个（驱动器不碰，按各家自己的文档人肉跑）：" % len(unreadable))
            for line in unreadable:
                print("  " + line)
        return 0
    if cmd == "list":
        if len(argv) < 2:
            raise SystemExit("list 后面要跟家名，例：python tools/sabr.py list n2")
        list_family(argv[1])
        return 0
    if cmd == "run":
        if len(argv) < 2:
            raise SystemExit("run 后面要行家名，例：python tools/sabr.py run n2 45 --with ui")
        fam = argv[1]
        idxs = [int(x) for x in argv[2:] if re.match(r"^[0-9]+$", x)]
        with_key = "static"
        chain = ["gen_seed.py", "build_html.py"]
        for j, a in enumerate(argv):
            if a == "--with" and j + 1 < len(argv):
                with_key = argv[j + 1]
            if a == "--build" and j + 1 < len(argv):
                chain = [x.strip() for x in argv[j + 1].split(",") if x.strip()]
        return run(fam, idxs, with_key, chain)
    if cmd == "selftest":
        return 1 if selftest("S34" if "--live" in argv else None) else 0
    raise SystemExit("没这个子命令：%s（见 --help）" % cmd)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
