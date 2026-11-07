# -*- coding: utf-8 -*-
"""v0.21（仓库形状 S27）的反向验证：证明 S27 那几条腿真的会红，而不是摆设。
v0.31 换了边界（参考库整库出仓），六条故障按新边界重排，F6 是这一版新加的一条。

    python tools/_sabotage_t1.py inject          # 六处一起注
    python tools/_sabotage_t1.py inject 3        # 只注第 3 处（核对它只红自己那条腿）
    python tools/gate.py --static                # 期望见下表（只红 S27，其余不动）
    python tools/_sabotage_t1.py revert          # 逐字节还原文本 + 清掉现场与索引
    python tools/gate.py --static                # 期望回到全绿

形状说明（§3.4 跨切规矩第 5 条）：这一家是「文本 + 现场」混合，和 `_sabotage_r1.py` 同形。
只有 F1 是文本故障（改 `.gitignore` 里整库出仓那一行 ignore），所以 `--s23-dump` 只报那一条靶串；
F2–F6 改的是**仓库状态**（造文件 / 动索引 / 挪书），没有靶串可对，S23 无事可核。
现场用**固定探针路径**表达、revert 按同一路径清，**不写 `_sabotage_*.json` 台账**——
写了就会连带红 S26 的「注入态残留台账」那条腿（那是 r1 F5 故意要验的东西，不是这里要的）。

  F1 `.gitignore` 里 `ref/`（整库出仓那一行）被注释掉 → S27 红 ①「未跟踪顶层条目没被 ignore」，
     连带 ③ 报孤儿。这条对着 v0.31 的新坏法：库回到忽略区之外，下一次 `git add -A`
     就把 482MB 拖进仓——而历史刚被剔过一次，拖回来就是第二次付代价
  F2 在 `data/` 里造一份既不跟踪也不 ignore 的文件 → S27 红 ③「孤儿」。
     孤儿是「下一次 git add -A 顺手拖进仓」的入口；v0.21 瘦身就是被这堆东西压垮的
  F3 往 `release/` 复制旧 APK 并 `git add`，把跟踪版数顶过 3 → S27 红 ②。
     这条腿防的是仓库重新长胖：历史 APK 每个 ~900 KB，不轮出就等于让 .git 背版本博物馆
  F4 在仓库根造一个顶层条目并跟踪 → S27 红 ①「顶层多出未登记条目」。
     顶层是人的第一视线，多一个没人认领的目录/文件就是下一个「这东西谁写的、还能删吗」
  F5 强制 `git add -f` 一本 **canon 书**进索引 → S27 红 ④「参考库又入仓 N 个文件」，
     ①「顶层多出未登记条目：ref」同刻一起报。同一个坏法的两个观测面，不是判据漂：
     ① 看的是顶层名单里多了一个没人认领的目录，④ 看的是这个目录里具体哪些文件被跟踪了。
     v0.21 的 F5 注的是「入仓但 seed 不引用」，方向反了：现在仓里不该有任何 ref/ 文件，
     `-f` 绕过 ignore 拖进来的第一个就是它
  F6 把一本 canon 书临时挪出库 → S27 红 ④「磁盘 ref/ 上找不到」。
     断链是静默的：canon 字符串照样躺在 seed 里、App 照样显示那行出处，只有逐条对账才知道书没了

实测记录见 `mobile/README.md` §3.5（本轮 v0.31 重排后的实跑数字在那里，别抄这份文档里的旧数）。

S23 怎么核这一家：`FAULTS` 是模块级字面量，S23 直接 AST 解析出那 1 处靶串并核对它在
`.gitignore` 中恰好命中一次；`--s23-dump` 存在是为了将来把靶串改成现算时接口不用换。
注入态下台账在场，S23 按老规矩跳过这一家。

已知边界：S27 只核对**仓库形状**（顶层名单、release 版数、孤儿、库在仓外、canon 逐条有书），
它不知道「这一本该不该被 seed 引用」——那是 DATA_MAP §1 与人的判断。另外这几条腿全依赖 git
可读：拿不到 `git ls-files` 一律 FAIL，不静默放行。
"""
import io
import glob
import json
import os
import shutil
import subprocess
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(HERE)))
LEDGER = os.path.join(HERE, "_sabotage_t1.json")

GITIGNORE = os.path.join(ROOT, ".gitignore")
# 靶串取「参考库整库出仓」那一行 ignore：唯一命中，注释掉它只影响 S27 ① 这一条腿
CANON_LINE = "ref/"

ORPHAN = os.path.join(ROOT, "data", "_sabotage_t1_orphan.md")
TOPFILE = os.path.join(ROOT, "_sabotage_t1_top.md")
EXTRA_GLOB = os.path.join(ROOT, "release", "_sabotage_t1_extra_*.apk")
# 探针书取一本**被 seed 引用**的 canon 书：v0.31 起仓里不该有 ref/ 任何文件，
# 所以「能不能 -f 塞一本进索引」本身就是这条腿要防的坏法（旧版是「塞一本 seed 没引用的」）
PROBE_BOOK = ("ref/02_参考资料/03_计划与方法/02_具体计划与模板/"
              "Wendler_531_Spreadsheet.xlsx")
# F6 的靶子：临时把一本 canon 书挪走 → S27 红 ④「磁盘 ref/ 上找不到」。
# 断链是静默的：canon 字符串照样在 seed 里、界面照样显示出处，只有对账才知道书没了
MISSING_BOOK = ("ref/02_参考资料/02_研究与综述/"
                "Westside_Conjugate_Method_Users_Guide_EN.pdf")
MISSING_STASH = os.path.join(ROOT, ".sabotage-stash", "t1_missing.bin")

FAULTS = [
    (GITIGNORE, CANON_LINE, "# S27 探针：整库出仓那一行被注释掉了 → 参考库不再是忽略区\n"
     "# " + CANON_LINE,
     "F1 `.gitignore` 的 `ref/` 被注释掉 → S27 红 ①（未跟踪顶层条目没被 ignore）+ ③（孤儿）"),
]

APK_CAP = 3      # S27 ② 的阈值：release/ 只跟踪最近这么多版


def _run(*args):
    return subprocess.run(["git", "-C", ROOT] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _tracked_apks():
    out = _run("ls-files", "-z", "--", "release").stdout
    return [p.decode("utf-8") for p in out.split(b"\0") if p.endswith(b".apk")]


def _tracked(rel):
    return rel in [p.decode("utf-8") for p in
                   _run("ls-files", "-z").stdout.split(b"\0") if p]


def read(p):
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def s23_dump():
    print(json.dumps([[p, old] for p, old, _new, _why in FAULTS], ensure_ascii=False))


def inject_text(pick=None):
    """F1：走台账，存**注入前全文**，revert 逐字节放回（照 _sabotage_r1 的形状）。"""
    faults = FAULTS if pick is None else [FAULTS[pick - 1]]
    original = {}
    for path, old, _new, why in faults:
        src = original[path] if path in original else read(path)
        original[path] = src
        if src.count(old) != 1:
            sys.exit("靶串在 %s 里出现 %d 次（应为 1），拒绝盲改：%r" % (path, src.count(old), old[:60]))
    pending = dict(original)
    for path, old, new, why in faults:
        pending[path] = pending[path].replace(old, new, 1)
        print("注入: %s" % why)
    for path, src in pending.items():
        write(path, src)
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(original, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(original)))


def _guard_free(path):
    if os.path.exists(path):
        sys.exit("探针路径已存在（%s）：先 revert 或人工确认它不是你的在作文件" % path)


def inject_state(which):
    """F2–F5：动仓库状态，全部用固定探针路径，revert 按同一路径清。"""
    if which == 2:                                   # 孤儿：既不跟踪也不 ignore
        _guard_free(ORPHAN)
        write(ORPHAN, "S27 ③ 的探针文件，revert 会删。\n")
        print("注入: F2 造孤儿 data/_sabotage_t1_orphan.md → S27 红 ③")
    elif which == 3:                                 # release/ 跟踪版数顶过阈值
        apks = _tracked_apks()
        if not apks:
            sys.exit("release/ 里一个跟踪的 APK 都没有，F3 无法把版数顶过 %d" % APK_CAP)
        need = max(1, APK_CAP + 1 - len(apks))
        src = sorted(apks)[-1]
        for n in range(1, need + 1):
            dst = os.path.join(ROOT, "release", "_sabotage_t1_extra_%d.apk" % n)
            _guard_free(dst)
            shutil.copyfile(os.path.join(ROOT, src), dst)
            _run("add", "--", dst[len(ROOT) + 1:].replace(os.sep, "/"))
        print("注入: F3 复制 %d 份 APK 进 release/ 并跟踪（现共 %d 版）→ S27 红 ②"
              % (need, len(apks) + need))
    elif which == 4:                                 # 顶层未登记条目
        _guard_free(TOPFILE)
        write(TOPFILE, "S27 ① 的探针条目，revert 会删。\n")
        _run("add", "--", "_sabotage_t1_top.md")
        print("注入: F4 在仓库根加顶层条目并跟踪 → S27 红 ①")
    elif which == 5:                                 # 参考库回到仓里
        book = os.path.join(ROOT, PROBE_BOOK)
        if not os.path.isfile(book):
            sys.exit("F5 的探针书不在磁盘上（%s）：换一本同样被 seed 引用的书" % PROBE_BOOK)
        if _tracked(PROBE_BOOK):
            sys.exit("F5 的探针书已被跟踪（%s）：库怎么又进仓了？先 revert" % PROBE_BOOK)
        _run("add", "-f", "--", PROBE_BOOK)
        print("注入: F5 强制把一本 canon 书加回索引 → S27 红 ④「参考库又入仓」")
    elif which == 6:                                 # canon 出处断链
        src = os.path.join(ROOT, MISSING_BOOK)
        if not os.path.isfile(src):
            sys.exit("F6 的靶子书不在原位（%s）：它被挪过还是改名了？先人工确认" % MISSING_BOOK)
        _guard_free(MISSING_STASH)
        if not os.path.isdir(os.path.dirname(MISSING_STASH)):
            os.makedirs(os.path.dirname(MISSING_STASH))   # 暂存位是被 ignore 的库外目录
        shutil.move(src, MISSING_STASH)
        print("注入: F6 把一本 canon 书临时挪出库 → S27 红 ④「磁盘 ref/ 上找不到」")


def revert():
    done = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            ledger = json.load(f)
        for path, original in ledger.items():
            write(path, original)          # 逐字节放回，不做二次 replace
        os.remove(LEDGER)
        done.append(".gitignore 原文按台账放回")
    for path in (ORPHAN, TOPFILE):
        if os.path.exists(path):
            rel = path[len(ROOT) + 1:].replace(os.sep, "/")
            _run("rm", "--cached", "-q", "--ignore-unmatch", "--", rel)
            os.remove(path)
            done.append("删除 " + os.path.basename(path))
    for path in glob.glob(EXTRA_GLOB):
        rel = path[len(ROOT) + 1:].replace(os.sep, "/")
        _run("rm", "--cached", "-q", "--ignore-unmatch", "--", rel)
        os.remove(path)
        done.append("移出索引并删除 " + os.path.basename(path))
    if _tracked(PROBE_BOOK):
        _run("rm", "--cached", "-q", "--ignore-unmatch", "--", PROBE_BOOK)
        done.append("把探针书移出索引（文件留在磁盘 ref/，仍是忽略区）")
    if os.path.exists(MISSING_STASH):
        dst = os.path.join(ROOT, MISSING_BOOK)
        if os.path.exists(dst):
            sys.exit("F6 的靶子书已经回到原位（%s），暂存件不知道该覆盖谁，人工确认后再删" % MISSING_BOOK)
        shutil.move(MISSING_STASH, dst)
        try:
            os.rmdir(os.path.dirname(MISSING_STASH))   # 空了就收回，不留一个空 ignore 目录
        except OSError:
            pass
        done.append("把 F6 挪走的书放回 ref/ 原位")
    if not done:
        sys.exit("没有台账也没有现场可清，拒绝猜测仓库状态")
    print("复原: " + " / ".join(done))


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        pick = int(args[1]) if len(args) > 1 else None
        if pick is None:
            inject_text()
            for which in (2, 3, 4, 5, 6):
                inject_state(which)
        elif pick == 1:
            inject_text(1)
        elif 2 <= pick <= 6:
            inject_state(pick)
        else:
            sys.exit("故障编号只允许 1..6")
    elif mode == "revert":
        revert()
    elif mode == "--s23-dump":
        s23_dump()
    else:
        sys.exit(__doc__)
