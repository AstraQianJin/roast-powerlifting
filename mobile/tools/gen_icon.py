# -*- coding: utf-8 -*-
"""Generate ExDark Pro launcher icons.

纯杠铃图标：48×48 坐标系内对称的深色底 IPF 力量举杠铃，一侧一片 25kg 红片 + 一片
20kg 蓝片（不标数字）= 45kg/侧，两侧 90kg 加 20kg 杠铃 = 110kg 的竞赛配置。
与首页顶栏的三段烘焙色阶品牌徽标（brandIcon）完全解耦、互不引用：
两者都源自 IPF 杠铃母题，但一个用于启动器、一个用于顶栏，改一处不影响另一处。
"""
import os
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.join(os.path.dirname(HERE), "app", "src", "main", "res")
DENS = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}

U = 48.0                             # 设计坐标系边长

BG          = (11, 14, 22, 255)       # 深色底（--deep #0B0E16）
SHAFT       = (214, 222, 234, 255)     # 滚花钢杆 #D6DEEA
SLEEVE      = (154, 166, 182, 255)     # 内侧轴套挡圈 #9AA6B6
RED_PLATE   = (226, 32, 46, 255)       # 25kg 红片（IPF 竞赛片色）
BLUE_PLATE  = (26, 95, 180, 255)       # 20kg 蓝片（IPF 竞赛片色）
# 一侧一片红一片蓝 = 45kg，两侧 90kg + 20kg 杠铃 = 110kg，片上不标数字


def make(size, round_icon=False):
    k = size * 8
    u = k / U
    img = Image.new("RGBA", (k, k), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1. 底：圆角方形 / 圆形
    if round_icon:
        d.ellipse([0, 0, k - 1, k - 1], fill=BG)
    else:
        d.rounded_rectangle([0, 0, k - 1, k - 1], radius=int(k * 0.225), fill=BG)

    # 2. 柔和的冷钢径向辉光（只为立体感；暖棕底会把红蓝片衬脏，故走中性冷色）
    cx = cy = k / 2.0
    for i in range(20, 0, -1):
        t = (20 - i) / 20.0 * 0.20
        col = (int(BG[0] * (1 - t) + 150 * t), int(BG[1] * (1 - t) + 170 * t),
               int(BG[2] * (1 - t) + 200 * t), 255)
        r = int(k * (0.26 + i * 0.009))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)

    # 3. 贯穿滚花钢杆（垂直居中 y = 24u）
    d.rounded_rectangle([3.5 * u, 22.4 * u, 44.5 * u, 25.6 * u],
                        radius=max(1, int(1.2 * u)), fill=SHAFT)

    # 4. 内侧轴套挡圈（左右对称）
    for x in (10.5 * u, 35.5 * u):
        d.rounded_rectangle([x, 17 * u, x + 2.0 * u, 31 * u],
                            radius=max(1, int(0.6 * u)), fill=SLEEVE)

    # 5. 内侧 25kg 红片（左右对称 · 直径最大）
    for x in (6.6 * u, 38.2 * u):
        d.rounded_rectangle([x, 11.5 * u, x + 3.4 * u, 36.5 * u],
                            radius=max(1, int(1.3 * u)), fill=RED_PLATE)

    # 6. 外侧 20kg 蓝片（左右对称 · 比红片小一号）
    for x in (3.6 * u, 42.0 * u):
        d.rounded_rectangle([x, 14 * u, x + 2.8 * u, 34 * u],
                            radius=max(1, int(1.1 * u)), fill=BLUE_PLATE)

    # 圆形图标裁切（避免辉光溢到圆外）
    if round_icon:
        mask = Image.new("L", (k, k), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, k - 1, k - 1], fill=255)
        img.putalpha(Image.composite(img.getchannel("A"), Image.new("L", (k, k), 0), mask))

    return img.resize((size, size), Image.LANCZOS)


def main():
    for dens, size in DENS.items():
        out = os.path.join(RES, "mipmap-" + dens)
        os.makedirs(out, exist_ok=True)
        make(size, False).save(os.path.join(out, "ic_launcher.png"))
        make(size, True).save(os.path.join(out, "ic_launcher_round.png"))
        print("  %-8s %dpx  (pure barbell)" % (dens, size))
    print("icons written to", RES)


if __name__ == "__main__":
    main()
