# -*- coding: utf-8 -*-
"""A6 构建链守卫的反向验证：证明 gate.py 的静态检查真的会红，而不是恒过。

    python tools/_sabotage_a6.py inject    # 注入 10 处红线故障（原件存到 _sabotage_a6.json）
    python tools/gate.py --static          # 期望 S2/S3/S5/S7/S13/S28 变红
    python tools/_sabotage_a6.py revert    # 逐字节还原

还原靠的是注入前写下的原文副本，不依赖 git，也不会把别的改动一起带回去。
"""
import io
import json
import os
import re
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)
ROOT = os.path.dirname(APK)
LEDGER = os.path.join(HERE, "_sabotage_a6.json")

MANIFEST = os.path.join(APK, "app", "src", "main", "AndroidManifest.xml")
GRADLE = os.path.join(APK, "app", "build.gradle")
ASSET = os.path.join(APK, "app", "src", "main", "assets", "index.html")
CHECK_HUD = os.path.join(HERE, "check_hud.js")
SCHEMA = os.path.join(HERE, "schema", "RPL-Plan-v2.json")
TPL = os.path.join(HERE, "template.html")

# 每处故障对应一条静态守卫：加了 INTERNET 权限 / versionName 掺产品标签 /
# 手改生成物 / 成品 CSV 列序与契约分叉 / 回归脚本不回收 Chrome profile。
# {{VER}} 在注入时按 build.gradle 现值替换 —— 换版不必改本脚本。
FAULTS = [
    (MANIFEST, '<uses-permission android:name="android.permission.VIBRATE" />',
     '<uses-permission android:name="android.permission.VIBRATE" />\n    <uses-permission android:name="android.permission.INTERNET" />',
     "S2 多出 INTERNET 权限"),
    (GRADLE, "versionName = '{{VER}}'", "versionName = '{{VER}}-Pro'",
     "S3 版本串掺了标签（连带 S26：发版预检同读这一行；连带 S23：_sabotage_r1 从 gradle 现算靶子，掺标签后当场算不出）"),
    (ASSET, "const SCHEMA_STAMP=8;", "const SCHEMA_STAMP=8; // 手一下成品", "S5 成品被手改"),
    # v0.13：CSV 协议的对账端从 desktop/server.py 换成契约的 record_keys_frozen，
    # 故障也相应打在成品上——同一处改动同时该让 S5（成品≠重生成）和 S7（成品列序≠契约）变红。
    (ASSET, "movement,load_kg,rx_text,target_rpe", "movement,rx_text,load_kg,target_rpe",
     "S7 成品 CSV 列序与契约分叉（连带 S5）"),
    # 第 5 处是 S13 的历史形态：profile 路径现拼在 spawn 参数里，脚本没人持有它，
    # Chrome 退出前 Windows 又锁着目录 —— 删不掉，每次跑漏一份（实测积到 200+ 份 / 2.6 GB）。
    (CHECK_HUD, '`--user-data-dir=${profDir}`',
     "`--user-data-dir=${path.join(os.tmpdir(), 'hudchk-' + Date.now())}`",
     "S13 profile 退回匿名一次性拼接（不回收）"),
    # 第 6–10 处打在 v0.23 新守卫 S28 的四条腿上（容量/周期预设单源）。
    # 每条只断一条腿：名单分叉 / 容量自相矛盾 / 契约给的模式在种子里不存在 /
    # 模板不再从契约取名单 / 输入框上限与契约分叉。
    (SCHEMA, '"cycle_type": ["Hyper", "Strength", "Transmute", "Peak", "Custom"]',
     '"cycle_type": ["Hyper", "Strength", "Transmute", "Peak"]',
     "S28① Blocks 周期枚举与 cycle_presets 名单分叉（连带 S40）"),
    (SCHEMA, '"max_weeks": 52', '"max_weeks": 20',
     "S28② 总周数上限小于单 Block work_weeks 上限（24）（连带 S40）"),
    (SCHEMA, '"work_mode": "T1.Mod",', '"work_mode": "T1.ModX",',
     "S28③ 契约给的 work_mode 在 seed.proto 里不存在（连带 S40）"),
    (TPL, "&&PLAN_SCHEMA.cycle_presets.items)||[]", "&&PLAN_SCHEMA.cycle_presets)||[]",
     "S28④ 模板退回自己拼名单（不再读 cycle_presets.items）"),
    (TPL, 'min="1" max="16" inputmode="numeric"', 'min="1" max="8" inputmode="numeric"',
     "S28④ stBlocks 上限字面量与 capacity.max_blocks 分叉"),
]


def read(p):
    # newline='' 是关键：不做换行翻译，读到的原文与磁盘逐字节一致，
    # 还原时才不会把 CRLF 文件悄悄改成 LF（内容没错、但 git 会报幽灵改动）。
    with io.open(p, encoding="utf-8", newline="") as f:
        return f.read()


def write(p, s):
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


def find(src, old):
    """在原文里定位故障串，容忍 CRLF/LF 差异。"""
    if old in src:
        return old
    alt = old.replace("\n", "\r\n")
    return alt if alt in src else None


def inject():
    m = re.search(r"versionName\s*=\s*'([^']*)'", read(GRADLE))
    if not m:
        sys.exit("读不到 build.gradle 的 versionName，{{VER}} 无法替换")
    ver = m.group(1)
    ledger = {}
    for path, old, new, why in FAULTS:
        old = old.replace("{{VER}}", ver)
        new = new.replace("{{VER}}", ver)
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:50]))
        # 故障文本按该文件自己的换行符落地，别让一次注入顺手改了整文件的 EOL
        rep = new.replace("\n", "\r\n") if "\r\n" in src else new
        ledger.setdefault(path, src)          # 只留第一份原文，重复注入不会覆盖备份
        write(path, src.replace(hit, rep, 1))
        print("注入: %s" % why)
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）；跑完 gate.py 记得 revert" % (LEDGER, len(ledger)))


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
