# -*- coding: utf-8 -*-
"""B4 契约回归的反向验证：证明 `test_plan_xlsx.py` 真的会红，而不是恒过。

    python tools/_sabotage_b4.py inject    # 注入 5 处故障（原件存到 _sabotage_b4.json）
    python tools/test_plan_xlsx.py         # 期望 T1/T2/T3/T6 各自变红
    python tools/_sabotage_b4.py revert    # 逐字节还原

每处故障都打在一个具体的承诺上：`mround` 的半进位、导出的 pct_1rm、
核心表缺失必须是 error、D4 的「冻结而不是删除」、以及 `plan_weeks` 的 `on_missing`
补齐。还原靠注入前的原文副本，不依赖 git，也不会把别的改动一起带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_b4.json")
MODULE = os.path.join(HERE, "plan_xlsx.py")

# (原文片段, 故障片段, 应该红在哪)
FAULTS = [
    ('return round(math.floor(q + 0.5) * s, 6)',
     'return round(math.floor(q) * s, 6)',
     "mround 不再半进位 → T2.3/T2.5/T2.10/T2.16 红"),
    ('row[rc["pct"]] = round(load_n / anchor, dec)',
     'row[rc["pct"]] = ""',
     "导出的 pct_1rm 丢失 → T1.11 红"),
    ('res["errors"].append(err(sch, name, "", _cols(sch, name)[0], "缺少核心工作表 \'%s\'" % name))',
     'res["warnings"].append(err(sch, name, "", _cols(sch, name)[0], "缺少核心工作表 \'%s\'" % name))',
     "核心表缺失被降级成 warning → T3.01 红"),
    ('state["weeks"].setdefault(str(n), copy.deepcopy(wk))',
     'continue  # 故障：超出的周被丢掉而不是冻结',
     "D4 归档+冻结失效 → T6.3/T6.4/T6.5 红"),
    ('    _apply_on_missing(sch, profile_values, state, total)',
     '    pass  # 故障：plan_weeks 沿用上一份计划的值',
     "plan_weeks 不补齐 → T2.17/T2.18 红（build 会被自己的产物判 error）"),
]


def read(p):
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """定位故障串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject():
    src = read(MODULE)
    hit_any = False
    for old, new, why in FAULTS:
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if not hit_any:
            with io.open(LEDGER, "w", encoding="utf-8") as f:
                json.dump({MODULE: src}, f, ensure_ascii=False)
            hit_any = True
        rep = new if "\r\n" not in hit else new.replace("\n", "\r\n")
        src = src.replace(hit, rep, 1)
        print("注入: %s" % why)
    write(MODULE, src)
    print("原件已存 %s；跑完 test_plan_xlsx.py 记得 revert" % LEDGER)


def revert():
    if not os.path.exists(LEDGER):
        sys.exit("没有台账 %s，拒绝猜测原文" % LEDGER)
    with io.open(LEDGER, encoding="utf-8") as f:
        ledger = json.load(f)
    for path, original in ledger.items():
        write(path, original)
        print("还原: %s" % path)
    os.remove(LEDGER)
    print("台账已清除")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "inject":
        inject()
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
