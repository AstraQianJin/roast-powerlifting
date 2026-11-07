# -*- coding: utf-8 -*-
"""W1..W16 周表骨架坐标 —— **唯一来源**。

`gen_seed.py`（抽种子）是它唯一的读者，任何行号调整只改本文件。
（曾经还有 PC 端白名单写回一处读它；自 v0.13 那个项目整体归档，不再进依赖图。）

坐标含义（都指每周表 `W{n}` 内部的行号）：

| 字段 | 含义 |
|---|---|
| `title` | 训练日标题行（A 列，形如 `A · HEAVY SBD`） |
| `bio`   | 训前遥测行（B/C/E/F/G/H/I 列） |
| `post`  | 训后遥测行（恒为 `bio + 2`） |
| `first`…`last` | 该日动作行区间 |
| AUX     | 「恢复装甲」打卡区：55–64 行 × I…O 列 |

改动本文件后必须：`python tools/gen_seed.py` → `build_html.py` → 两端回归。
"""

# 四个训练日，顺序即 W 表内的排列顺序（A/B/C/D）
DAYS = [
    {"id": "A", "fallback": "HEAVY SBD",            "title": 4,  "bio": 5,  "post": 7,  "first": 9,  "last": 14},
    {"id": "B", "fallback": "BENCH FOCUS",          "title": 16, "bio": 17, "post": 19, "first": 21, "last": 26},
    {"id": "C", "fallback": "DL + SQUAT",           "title": 28, "bio": 29, "post": 31, "first": 33, "last": 38},
    {"id": "D", "fallback": "TECHNIQUE / VARIATION","title": 40, "bio": 41, "post": 43, "first": 45, "last": 51},
]

AUX_FIRST, AUX_LAST = 55, 64
AUX_COLS = ["I", "J", "K", "L", "M", "N", "O"]
AUX_ROWS = range(AUX_FIRST, AUX_LAST + 1)

# 兼容两种历史调用形态（元组解包 / 字典取值），避免改动调用方逻辑
DAY_BLOCKS = [(d["id"], d["fallback"], d["title"], d["bio"], d["first"], d["last"]) for d in DAYS]
BLOCKS = [{k: d[k] for k in ("id", "title", "bio", "post", "first", "last")} for d in DAYS]

assert all(d["post"] == d["bio"] + 2 for d in DAYS), "post 行必须等于 bio + 2"
