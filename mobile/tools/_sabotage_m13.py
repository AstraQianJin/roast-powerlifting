# -*- coding: utf-8 -*-
"""v0.43（装备照片上传）的反向验证：证明 S46 那几条腿真的有牙。

    python tools/_sabotage_m13.py inject        # 五处一起注
    python tools/_sabotage_m13.py inject 2      # 只注第 2 处（核对它只红自己那条腿）
    python tools/build_html.py                  # 改的是模板，必须重建，否则 S5 先红
    python tools/gate.py --static               # 期望见下表
    python tools/_sabotage_m13.py revert        # 逐字节还原
    python tools/build_html.py && python tools/gate.py --static   # 期望回到全绿

这一族的五个故障都是**静默型**的：页面不报错、点数不变、别的守卫大多不响。
「红在哪」是单注那一处 + 重建后实测出来的：

  F1 模板里的桥调用 gearPickPhoto 漂成 gearPickPhotoX（S15 的双向对账把「JS 直呼」
     与「Java @JavascriptInterface」钉在一起，改名后 JS 那面成了没声明的孤呼）
     → S15 红（AndroidBridge 直呼的方法 Java 侧没声明）+ S46 红（桥调用字面量缺位）
       症状：点缩略位毫无反应——onActivityResult 的回路根本没机会发生
  F2 renderKitPhoto 的占位 class 漂成 kf-photo-phx（页面还是那个 96px 的框，里面从此空白）
     → S46 红（占位分支缺位：CSS 或 JS 发射）+ S22 红（kf-photo-phx 是 JS 发射、CSS 无规则的死类名
       ——恰好是那条守卫要抓的形状）
       症状：无图装备的缩略位是一个空框，用户不知道那里能点
  F3 renderKitGear 出口的渲染钩子 if(kitForm) renderKitPhoto(); 整行删掉
     （markup 里 #kfPhoto 永远是空 div——钩子是唯一往里填内容的地方）
     → S46 红（渲染钩子缺位）
       症状：表单打开缩略位永远空白，与 F2 的区别是连占位字样都没有
  F4 Java 选图回路里 evaluateJavascript("try{kitPhotoDone(...)...") 整行删掉
     （Java 侧其实落盘成功了，但 JS 不知道——缩略位要等下次重开表单才刷新）
     → S46 红（Java 回调缺位）
       症状：选完图回来缩略位不变，杀掉重开才看到图——静默得最典型的一条
  F5 Java 读口的大小闸 f.length() > PHOTO_MAX_BYTES 漂成恒假（超限文件会被整个 base64 出去）
     → S46 红（读口大小闸缺位）
       症状：正常操作看不出来，只有异常大的文件（或被外部塞进私有目录的文件）才会拖慢读口/占内存
       ——「限制上传大小」的承诺在读口这侧的最后一道闸

台账 _sabotage_m13.json 存的是注入前每个文件的整份原文，revert 逐字节放回。

跑法（驱动器把「注入 → 重建 → 各套回归 → 还原 → 复跑回绿」一次做完）：
    python tools/sabr.py run m13 1 2 3 4 5 --with fast

**不要在注入态跑 pack.py**：发版链会把故障写进 APK。复原只走 `revert`。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_m13.json")
TPL = os.path.join(HERE, "template.html")
JAVA = os.path.join(HERE, "..", "app", "src", "main", "java", "com", "roast", "exdark", "MainActivity.java")

# (文件, 原文片段, 故障片段, 应该红在哪)
FAULTS = [
    (TPL, "AndroidBridge.gearPickPhoto(key); return;",
     "AndroidBridge.gearPickPhotoX(key); return;",
     "F1 模板桥调用漂成没声明的名字 → S15 红（JS 直呼的方法 Java 侧没声明）+ S46 红（桥调用字面量缺位）"),
    (TPL, "'<span class=\"kf-photo-ph\">'", "'<span class=\"kf-photo-phx\">'",
     "F2 占位 class 漂成死类名 → S46 红（占位分支缺位）+ S22 红（JS 发射、CSS 无规则）+ v3v EQ13 红（缩略位占位断言，正确连带）"),
    (TPL, "if(kitForm) renderKitPhoto();", "if(kitForm) true;",
     "F3 渲染钩子整行废掉 → S46 红（渲染钩子缺位）；缩略位从此永远空白"),
    (JAVA, "webView.evaluateJavascript(\"try{kitPhotoDone('\" + key + \"')}catch(e){}\", null);",
     "",
     "F4 Java 选图回路不回调 kitPhotoDone → S46 红（Java 回调缺位）；落盘成功但缩略位不刷新"),
    (JAVA, "if (!f.exists() || f.length() == 0 || f.length() > PHOTO_MAX_BYTES) return \"\";",
     "if (!f.exists() || f.length() == 0 || f.length() >= 0) return \"\";",
     "F5 读口大小闸漂成恒假 → S46 红（读口大小闸缺位）；超限文件被整个 base64 出去"),
]


EXPECT = {
    1: "S15 红（gearPickPhotoX 在 Java 侧没声明）+ S46 红（桥调用字面量缺位）",
    2: "S46 红（占位分支缺位）+ S22 红（kf-photo-phx 是 JS 发射、CSS 无规则的死类名）"
       "+ v3v EQ13 红（EQ13 钉的就是占位分支在位，占位没了它必红——正确连带）",
    3: "S46 红（渲染钩子缺位）",
    4: "S46 红（Java 回调 kitPhotoDone 缺位）",
    5: "S46 红（读口大小闸缺位）",
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
        src = original.get(path) if path in original else read(path)
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
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
