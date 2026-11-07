# -*- coding: utf-8 -*-
"""一条命令出成品 APK：守卫 → 注入 → 构建 → 校验 → 门禁 → 按规范命名。

    python tools/pack.py                # release（默认）
    python tools/pack.py --debug        # debug 包，只构建不改 release/
    python tools/pack.py --no-build     # 跳过 Gradle，只重新注入 + 复制已有产物
    python tools/pack.py --skip-inject  # 跳过 build_html.py（确认产物已最新时）
    python tools/pack.py --skip-gate    # 跳过发版门禁（全量回归），仅限排查用

做的事：
1. gate.py --static：红线静态守卫（包名 / 权限 / 版本单源 / 成品未被手改 / CSV 两端同源 …）
2. 跑一次 build_html.py（版本号来自 app/build.gradle，模板只写 {{VER}}）
3. ./gradlew --offline assembleRelease
4. 校验 APK 内 assets/index.html 与仓库产物逐字节一致，打印 md5 与大小
5. gate.py 全量门禁（静态 + 全量回归）；不过就不写 release/
"""
import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
APK = os.path.dirname(HERE)                    # .../mobile
ROOT = os.path.dirname(APK)                    # .../Roast PowerLifting
sys.path.insert(0, HERE)

import build_html  # noqa: E402
import pyout  # noqa: E402

JBR = "C:/Program Files/Android/Android Studio/jbr"


def md5(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def java_home():
    """Gradle 要 JDK 17；没设就用 Android Studio 自带 jbr。"""
    cur = os.environ.get("JAVA_HOME")
    if cur and os.path.isdir(cur):
        return cur, False
    if os.path.isdir(JBR):
        return JBR, True
    return None, False


def gradle_cmd():
    return os.path.join(APK, "gradlew.bat" if os.name == "nt" else "gradlew")


def run_gate(args_flag, label):
    """gate.py 是子进程跑：它的退出码就是裁决，别在这儿复刻它的判定逻辑。"""
    cmd = [sys.executable, os.path.join(HERE, "gate.py")] + args_flag
    r = subprocess.run(cmd, cwd=APK)
    if r.returncode != 0:
        raise SystemExit("%s 未通过（exit %d）—— 修好再打包；确要绕过用 --skip-gate 并说明理由" % (label, r.returncode))


def main():
    pyout.use_utf8_stdout()
    ap = argparse.ArgumentParser(description="打包 RPL_ExDark APK")
    ap.add_argument("--debug", action="store_true", help="构建 debug 包（不改 release/）")
    ap.add_argument("--no-build", action="store_true", help="跳过 Gradle，只注入 + 复制")
    ap.add_argument("--skip-inject", action="store_true", help="跳过 build_html.py")
    ap.add_argument("--skip-gate", action="store_true", help="跳过发版门禁（全量回归），仅限排查")
    args = ap.parse_args()

    ver, code = build_html.read_version()
    variant = "debug" if args.debug else "release"

    print("[1/5] 静态守卫 gate.py --static ...", flush=True)
    run_gate(["--static"], "静态守卫")

    if not args.skip_inject:
        print("[2/5] 注入版本与种子 ...", flush=True)
        build_html.main()
    else:
        print("[2/5] 跳过注入（--skip-inject）", flush=True)

    if not args.no_build:
        jh, auto = java_home()
        if not jh:
            raise SystemExit(
                "找不到 JDK 17：请设置 JAVA_HOME，或安装 Android Studio（预期路径 %s）" % JBR)
        env = dict(os.environ, JAVA_HOME=jh)
        print("[3/5] Gradle assemble%s（--offline，JAVA_HOME=%s%s）..." % (
            variant.capitalize(), jh, " 自动探测" if auto else ""), flush=True)

        r = subprocess.run([gradle_cmd(), "--offline", "assemble" + variant.capitalize()],
                           cwd=APK, env=env)
        if r.returncode != 0:
            raise SystemExit("Gradle 构建失败（exit %d）" % r.returncode)
    else:
        print("[3/5] 跳过构建（--no-build）", flush=True)

    src = os.path.join(APK, "app", "build", "outputs", "apk", variant, "app-%s.apk" % variant)
    if not os.path.exists(src):
        raise SystemExit("找不到构建产物：%s" % src)

    inner = zipfile.ZipFile(src).read("assets/index.html")
    repo = open(os.path.join(APK, "app", "src", "main", "assets", "index.html"), "rb").read()
    if inner != repo:
        raise SystemExit("APK 内 assets/index.html 与仓库产物不一致，先重跑 build_html.py")

    if args.debug:
        print("[4/5] debug 包不写 release/，产物：%s" % src, flush=True)
        print("[5/5] debug 包不跑发版门禁", flush=True)
        dst = src
    else:
        # 门禁放在写 release/ 之前：一旦全绿，落盘的 APK 就是刚验过的那一份
        if args.skip_gate:
            print("[4/5] 跳过发版门禁（--skip-gate）", flush=True)
        else:
            print("[4/5] 发版门禁 gate.py（静态 + 全量回归）...", flush=True)
            run_gate([], "发版门禁")
        dst = os.path.join(ROOT, "release", "RPL_ExDark_v%s_Pro.apk" % ver)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        print("[5/5] 已写入 %s" % dst, flush=True)

    print("      内嵌 index.html == 仓库产物（md5 %s）" % hashlib.md5(inner).hexdigest())
    print("      versionName=%s  versionCode=%d  大小 %.1f KB  md5 %s" % (
        ver, code, os.path.getsize(dst) / 1024.0, md5(dst)))


if __name__ == "__main__":
    main()
