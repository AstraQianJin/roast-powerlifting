# -*- coding: utf-8 -*-
"""v0.28（存档读取闸门 S31 + v3v BD 段）的反向验证：证明那几条腿真的会红，而不是摆设。

    python tools/_sabotage_n1.py inject          # 五处一起注
    python tools/_sabotage_n1.py inject 2        # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                   # 改模板必须重建，否则 S5 先红（改 Java 不必）
    python tools/gate.py --static && node tools/v3v.js     # 期望见下表
    python tools/_sabotage_n1.py revert          # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static && node tools/v3v.js  # 回到全绿

这一家守的是红线 4 里最阴的一种坏法：原生 readStore() 对「文件不在」和「读挂了」都回空串，
前端只看返回值就分不出来 —— 于是「磁盘上有真实训练记录、这一次没读回来」会走到默认账本分支，
再用 save(true) 把真实记录原子覆盖掉。v0.28 加的是 storeProbe()（报字节数）+ boot 闸门，
而这条链的两侧各有一份文件名（Java 的 F_* / 模板的 BRIDGE_FILE），漂哪一侧都会让闸门
**静默失效**（取到 undefined → NaN>0 为假 → 什么都不拦），所以必须反向钉住。

五处故障各打在一个承诺上（「红在哪」是单注那一处 + 该重建的重建后实测出来的）：

  F1 模板 BRIDGE_FILE 里 workout 的文件名多了一个字符
     → S31 红 ①「分片文件名两侧不等：JS 独有 roast_workoutx.json / Java 独有 roast_workout.json」。
       这条对着「换机改名」：探针查一个不存在的键，闸门永久沉默，而所有回归依旧全绿
  F2 boot 里闸门调用点被拆掉（unread 恒为空表）
     → S31 红 ②「模板/成品的 boot 里没有读取闸门调用点」+ v3v BD1 红；
       BD6 同红并且红得有意义：磁盘报 812 字节、手里是空，闸门没了就直接落默认分支，
       断言里那条「workout 分片仍为空」当场变红（= 真实数据被空账本覆盖的那一步）
  F3 BF_REASON_LABEL 删掉 read 那一项
     → S31 红 ③「缺 read 标签」+ v3v BD7、BD6 红；阻断层于是把内部键名「read」当人话显示，
       而 BD6 就是去读那块阻断层文案的（它断言「原生读取失败」这句人话在屏上），所以它跟着红是**正确连带**，
       不是判定漂了 —— v0.30 用 sabr.py 复跑时才把这条暴露出来（此前人肉只盯 BD7）
  F4 readSlice 的 catch 重新变成什么都不记（与写侧不对称）
     → 只有 v3v BD5 红（S31 全绿：静态腿不点名「读侧留痕」）。这条对着排查现场——
       真机上「为什么停在只读」全靠这句话，没有它就只能猜
  F5 Java 侧 F_WORK 常量改名（模拟原生侧单独动过）
     → 只有 S31 红 ①（Java 独有新名）。与 F1 是同一条腿的两侧：单侧改名红一次不算钉住，
       两侧都试才知道它到底有没有在比对

已知边界：BD6 只在「桥抛错 + 探针报字节 + localStorage 镜像也空」三者同时成立时才该红；
浏览器里没有 AndroidBridge，sliceProbe() 恒为 null，闸门永不触发（BD2 钉的就是这个）。

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_n1.json")
TPL = os.path.join(HERE, "template.html")
JAVA = os.path.join(HERE, "..", "app", "src", "main", "java",
                    "com", "roast", "exdark", "MainActivity.java")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "workout:'roast_workout.json',",
     "workout:'roast_workoutx.json',",
     "F1 JS 侧分片名漂移 → S31 红（探针查不到键，闸门静默失效）"),
    (TPL, "  const unread=unreadableSlices(sliceProbe(), got);",
     "  const unread=[];",
     "F2 拆掉 boot 闸门 → S31 红 + v3v BD1/BD6 红（空账本覆盖真实记录那一步被抓）"),
    (TPL, "read:'原生读取失败', ",
     "",
     "F3 删掉 read 原因标签 → S31 红 + v3v BD7、BD6 红（阻断层显示内部键名，BD6 读的就是那块文案）"),
    (TPL, "  }catch(e){ window.__lastStoreError='read-bridge:'+kind+':'+(e&&e.message?e.message:String(e)); }",
     "  }catch(e){}",
     "F4 读侧不再留痕 → 只有 v3v BD5 红（真机排障失去线索）"),
    (JAVA, 'F_WORK   = "roast_workout.json"',
     'F_WORK   = "roast_workout_v2.json"',
     "F5 Java 侧分片名漂移 → S31 红（同一条腿的另一侧）"),
]

EXPECT = {
    1: "S31 红 ①：分片文件名两侧不等（JS 独有）",
    2: "S31 红 ②：boot 里没有闸门调用点 / v3v BD1+BD6 红",
    3: "S31 红 ③：缺 read 标签 / v3v BD7 + BD6 红（BD6 断言阻断层里那句人话，正确连带）",
    4: "只有 v3v BD5 红（S31 全绿属预期）",
    5: "S31 红 ①：分片文件名两侧不等（Java 独有）",
}


def read(p):
    # newline=''：逐字节读写，还原时不会把 CRLF 文件悄悄改成 LF
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """定位故障目标串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject(pick=None):
    faults = FAULTS if pick is None else [FAULTS[pick - 1]]
    # 先逐条验靶再动手：任何一条打空都不写盘，杜绝「已改一半、未写台账」的半注入残留
    original, planned = {}, []
    for path, old, new, why in faults:
        src = original.get(path, read(path))
        original[path] = src
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        if src.count(hit) != 1:
            # 多处命中会把不相干的地方一起改掉，故障就不再「只打在一个承诺上」
            sys.exit("故障目标串在 %s 里出现 %d 次，拒绝盲改：%r" % (path, src.count(hit), old[:60]))
        planned.append((path, hit, new, why))
    pending = dict(original)
    for path, hit, new, why in planned:
        pending[path] = pending[path].replace(hit, new, 1)
        print("注入: %s" % why)
    for path in original:
        write(path, pending[path])
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(original, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(original)))


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
    args = sys.argv[1:]
    mode = args[0] if args else ""
    if mode == "inject":
        pick = int(args[1]) if len(args) > 1 else None
        if pick is not None and not 1 <= pick <= len(FAULTS):
            sys.exit("故障编号只允许 1..%d" % len(FAULTS))
        inject(pick)
        print("期望：%s" % (EXPECT[pick] if pick else "S31 的一条腿（见文档表）"))
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
