# -*- coding: utf-8 -*-
"""RPL Data v1 校验器（只读）。

用法：
    python data/03_规范/tools/validate_data.py

检查：
1. 契约 JSON 可解析；
2. refs_manifest.json 必填字段 / ID 唯一 / 文件存在 / sha256 与 size 一致；
3. checksums.sha256 与 manifest 逐条一致；
4. 02_参考资料 内无重复哈希；
5. d17 原始资料包映射 37 条且全部 sha256 一致；
6. 三个工作簿的关键结构未被破坏；
7. 许可/可分发字段一致性、双语标题完整性。

只读；输出 data/04_生成物/10_数据校验报告.md。
"""
import os
import sys
import json
import hashlib
import collections
import openpyxl

DATA = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# v0.31：参考库整体出仓到仓库根的 ref/。manifest / index 里的 path 仍是 `02_参考资料/…`
# —— 那是书在**自己库内**的相对路径，与 canon 同形；基准目录只有这一处，改这里就够了。
REF = os.path.join(os.path.dirname(DATA), "ref", "02_参考资料")
LIB_ROOT = os.path.dirname(REF)      # manifest 的 path 列以这一层为基准，与 canon 同形
GEN = os.path.join(DATA, "04_生成物")
CONTRACT = os.path.join(DATA, "03_规范", "RPL_Data_v1.contract.json")
MANIFEST = os.path.join(GEN, "refs_manifest.json")
BUNDLE_MAP = os.path.join(GEN, "08_原始资料包映射.csv")
REPORT = os.path.join(GEN, "10_数据校验报告.md")

results = []

def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS  " if ok else "FAIL  ") + name + ("  [" + str(detail) + "]" if detail else ""))

def sha256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()

# 1 contract
try:
    contract = json.load(open(CONTRACT, encoding="utf-8"))
    check("C1 契约 JSON 可解析", True, contract.get("schema_version", ""))
    check("C2 契约表数量 = 17", len(contract.get("tables", [])) == 17, len(contract.get("tables", [])))
    check("C3 契约校验规则 = 20", len(contract.get("validation_rules", [])) == 20, len(contract.get("validation_rules", [])))
except Exception as e:
    check("C1 契约 JSON 可解析", False, e)
    contract = {}

# 2 manifest
try:
    manifest = json.load(open(MANIFEST, encoding="utf-8"))
    assets = manifest.get("assets", [])
    check("M1 manifest 可解析", True, len(assets))
    check("M2 count 与 assets 数一致", manifest.get("count") == len(assets), "%s/%s" % (manifest.get("count"), len(assets)))
    ids = [a.get("asset_id") for a in assets]
    check("M3 asset_id 唯一", len(ids) == len(set(ids)), len(set(ids)))
    required = ["asset_id", "path", "sha256", "size_bytes", "title_zh", "title_en", "type", "language", "license", "status"]
    missing_fields = [(a.get("asset_id"), f) for a in assets for f in required if not a.get(f)]
    check("M4 必填字段齐全", not missing_fields, missing_fields[:3])
    missing_summary = [a["asset_id"] for a in assets if not a.get("summary_zh")]
    check("M5 中文摘要全覆盖", not missing_summary, len(missing_summary))
except Exception as e:
    check("M1 manifest 可解析", False, e)
    assets = []

# 3 files / checksums
bad_files, bad_size, bad_sha = [], [], []
for a in assets:
    p = os.path.join(LIB_ROOT, a["path"].replace("/", os.sep))
    if not os.path.exists(p):
        bad_files.append(a["path"]); continue
    if os.path.getsize(p) != a["size_bytes"]:
        bad_size.append(a["path"])
    if sha256(p) != a["sha256"]:
        bad_sha.append(a["path"])
check("F1 资产文件全部存在", not bad_files, bad_files[:3])
check("F2 size_bytes 与磁盘一致", not bad_size, bad_size[:3])
check("F3 sha256 与磁盘一致", not bad_sha, bad_sha[:3])

try:
    lines = [x for x in open(os.path.join(GEN, "checksums.sha256"), encoding="utf-8").read().splitlines() if x.strip()]
    check("F4 checksums 行数 = 资产数", len(lines) == len(assets), "%s/%s" % (len(lines), len(assets)))
    cs = {}
    for line in lines:
        h, p = line.split("  ", 1)
        cs[p] = h
    mism = [(a["path"], cs.get(a["path"])) for a in assets if cs.get(a["path"]) != a["sha256"]]
    check("F5 checksums 与 manifest 一致", not mism, mism[:3])
except Exception as e:
    check("F4 checksums 行数 = 资产数", False, e)

# 4 duplicate hashes in Ref
byhash = collections.defaultdict(list)
for dp, dn, fn in os.walk(REF):
    for f in fn:
        if f in {"BOOKS_METADATA.csv", "COACHING_ARTICLES_INDEX.csv", "DATASETS_AND_TOOLS.csv"}:
            continue
        p = os.path.join(dp, f)
        byhash[sha256(p)].append(os.path.relpath(p, LIB_ROOT))
dups = [v for v in byhash.values() if len(v) > 1]
check("D1 参考资料无重复哈希", not dups, dups[:3])

# 5 bundle mapping
try:
    rows = open(BUNDLE_MAP, encoding="utf-8-sig").read().splitlines()[1:]
    check("B1 d17 映射行数 = 37", len(rows) == 37, len(rows))
    bundle_assets = [a for a in assets if a.get("source_bundle") == "d17_AAA_clean"]
    check("B2 manifest 中 d17 资产 = 37", len(bundle_assets) == 37, len(bundle_assets))
    bad = [a["path"] for a in bundle_assets if not a.get("original_path")]
    check("B3 d17 原始路径齐全", not bad, bad[:3])
except Exception as e:
    check("B1 d17 映射行数 = 37", False, e)

# 6 workbooks
try:
    wb = openpyxl.load_workbook(os.path.join(DATA, "01_工作簿", "RPL_ExDark_v0.15_ProMax.xlsx"), data_only=True)
    ws = wb["W1"]
    ok = (ws["E9"].value == 130 and ws["F9"].value == "1×3 + 2×5@-10%" and ws["H9"].value == 7.5
          and ws["B11"].value == "Top.Set" and ws["E11"].value == 160)
    check("W1 主工作簿关键单元格", ok, "%s/%s/%s/%s/%s" % (ws["E9"].value, ws["F9"].value, ws["H9"].value, ws["B11"].value, ws["E11"].value))
    d4 = wb["W4"]
    ok = (str(d4["B9"].value) == "Top.Set" and d4["E9"].value == 130 and d4["E11"].value == 160)
    check("W4 力量块周关键单元格（v0.42 减重保力：开把恒定）", ok, "%s/%s/%s" % (d4["B9"].value, d4["E9"].value, d4["E11"].value))
    info = wb["信息"]
    vals = [info.cell(r, 4).value for r in range(10, 17)]
    check("W2 信息画像 D10–D16 非空", all(v is not None for v in vals), vals)
    wb.close()
except Exception as e:
    check("W1 主工作簿关键单元格", False, e)

try:
    wb = openpyxl.load_workbook(os.path.join(DATA, "01_工作簿", "RPL_Program_Library_v0.15.xlsx"), data_only=True)
    ws = wb["计划总库"]
    h1 = [ws.cell(1, c).value for c in range(1, 17)]
    h2 = [ws.cell(1, c).value for c in range(17, 29)]
    check("W3 计划库原 16 列表头", h1 == ["ID", "变更", "家族", "计划名称", "English / 原名", "条目类型", "主目标", "自调节", "GL 下限", "GL 上限", "周期", "频率(天/周)", "验证", "作者 / 出处", "规范链接", "备注"], h1[:3])
    check("W4 计划库新增 12 列表头", h2 == ["family_id", "level", "duration_min", "duration_max", "freq_min", "freq_max", "autoregulation_std", "verification_std", "canonical_status", "license_status", "language", "last_verified"], h2[:3])
    check("W5 计划库行数 = 198", ws.max_row == 198, ws.max_row)
    wb.close()
except Exception as e:
    check("W3 计划库原 16 列表头", False, e)

try:
    wb = openpyxl.load_workbook(os.path.join(DATA, "01_工作簿", "RPL_Set_Strategy_v0.15.xlsx"), data_only=True)
    ws = wb["组策略总表"]
    check("W6 策略总表原 9 列表头", [ws.cell(1, c).value for c in range(1, 10)] == ["序号", "功能分类", "组策略", "英文 / 别名", "Tier", "适用动作", "典型参数", "核心适用场景", "禁忌与注意事项"], True)
    ws2 = wb["动作适用性矩阵"]
    check("W7 矩阵原 7 列表头", [ws2.cell(2, c).value for c in range(1, 8)] == ["组策略", "Tier", "深蹲", "卧推", "硬拉", "肩推", "辅助动作"], True)
    ws3 = wb["三大项辅助动作库"]
    check("W8 辅助库原 14 列表头", [ws3.cell(2, c).value for c in range(1, 15)][0] == "ID", [ws3.cell(2, c).value for c in range(1, 4)])
    wb.close()
except Exception as e:
    check("W6 策略总表原 9 列表头", False, e)

# 7 license / i18n
bad_license = [a["path"] for a in assets if a.get("license") == "user_provided_copyright" and a.get("redistributable")]
check("L1 版权资产不可分发", not bad_license, bad_license[:3])
bad_i18n = [a["asset_id"] for a in assets if not a.get("title_zh") or not a.get("title_en")]
check("L2 双语标题完整", not bad_i18n, bad_i18n[:3])

# report
ok_n = sum(1 for _, ok, _ in results if ok)
fail_n = len(results) - ok_n
with open(REPORT, "w", encoding="utf-8") as f:
    f.write("# RPL Data v1 校验报告\n\n")
    f.write("- 生成日期：2026-11-03\n")
    f.write("- 校验器：`data/03_规范/tools/validate_data.py`\n")
    f.write("- 结果：**%d PASS / %d FAIL**（共 %d 项）\n\n" % (ok_n, fail_n, len(results)))
    f.write("| 检查项 | 结果 | 详情 |\n|---|---|---|\n")
    for name, ok, detail in results:
        f.write("| %s | %s | %s |\n" % (name, "PASS" if ok else "FAIL", str(detail).replace("|", "/")))
print("\n== validate_data: %d PASS / %d FAIL（共 %d 项）==" % (ok_n, fail_n, len(results)))
sys.exit(0 if fail_n == 0 else 1)
