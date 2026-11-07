# -*- coding: utf-8 -*-
"""实练 RPE 不凭空写 + 关闭编辑器不静默丢 + 徽章账本同源：证明 RP1–RP5 / DS1–DS5 / BS1–BS3 真的会拦。

    python tools/sabr.py run s2 1 2 3 4 5 6 7 8 9 10 --with fast
    或人肉：
    python tools/_sabotage_s2.py inject
    python tools/_sabotage_s2.py revert      # 逐字节还原

十处故障全落在 template.html（v3v 直接读生成物，--with fast 会在注入后重建再跑）：
  F1 打开编辑器把计划目标 RPE 预填进实练格 → RP1 红（值非空、预览不再写「未记录」）
  F2 账本在空 RPE 时拿 targetRpe 兜底     → RP2 红（rpe 不再为 null、估值改口）
  F3 逐组写入忽略用户填的值、统一写 8      → RP3 红（末组 / 卡片 / 账本读不到 9）
  F4 e1RM 在无 RPE 时补默认 8             → RP4 红（无 RPE 公式被悄悄换成有 RPE 公式）
  F5 拆掉 closeSheet 的未保存闸门          → DS2/DS3/DS5 红（改动静默丢）
  F6 「放弃」不绕过闸门                    → DS4 红（面板关不掉）
  F7 「保存离开」只收条不落账              → DS5 红
  F8 徽章退回吃卡片 reps                   → BS1/BS2 红（徽章与账本不同值）
  F9 无逐组记录时丢掉旧单值 RPE            → BS3 红
  F10 CSV 导入空 actual_rpe 补 10           → RP5 红（空值被冒充成已记录）

还原靠注入前写下的原文副本（_sabotage_s2.json），不依赖 git，也不会把别的改动带回去。
"""
import io
import json
import os
import sys
import pyout  # noqa: E402
pyout.use_utf8_stdout()

HERE = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(HERE, "_sabotage_s2.json")
TPL = os.path.join(HERE, "template.html")

FAULTS = [
    (TPL, "_rpeEl.value=(_rv==null||_rv==='')?'':String(_rv);",
     "_rpeEl.value=(_rv==null)?String(e.targetRpe||8):String(_rv);",
     "F1 编辑器预填计划目标 RPE → v3v RP1 红 + RP2 红（预填值被当成用户填写保存）"),
    (TPL, "const lastRpe=(rawRpe!=null&&+rawRpe>=5&&+rawRpe<=10)?+rawRpe:null;",
     "const lastRpe=(rawRpe!=null&&+rawRpe>=5&&+rawRpe<=10)?+rawRpe:(+ex.targetRpe||10);",
     "F2 账本空 RPE 拿 targetRpe 兜底 → v3v RP2 红"),
    (TPL, "if(_lastSet) _lastSet.rpe=_rpe;",
     "if(_lastSet) _lastSet.rpe=(_rpe==null?null:8);",
     "F3 逐组 RPE 写死 8 → v3v RP3 红"),
    (TPL, "const rir=e.rpe==null?0:Math.max(0,Math.min(5,10-e.rpe));",
     "const rir=e.rpe==null?Math.max(0,Math.min(5,10-8)):Math.max(0,Math.min(5,10-e.rpe));",
     "F4 e1RM 无 RPE 补默认 8 → v3v RP4 红 + RP2 红（估值跟着改口）"),
    (TPL, "  if(id==='edSheet' && el.classList.contains('on') && !edLeaveOK\n      && editIdx>=0 && editorDirty()){",
     "  if(false){",
     "F5 拆掉未保存闸门 → v3v DS2/DS3/DS5 红（改动静默丢）"),
    (TPL, "  edLeaveOK=true; hideEdLeave(); closeSheet('edSheet'); edLeaveOK=false; haptic(20);",
     "  hideEdLeave(); closeSheet('edSheet'); haptic(20);",
     "F6 「放弃」不绕过闸门 → v3v DS4 红（面板关不掉）"),
    (TPL, "function edLeaveSave(){ saveEditor(false); }",
     "function edLeaveSave(){ hideEdLeave(); }",
     "F7 「保存离开」只收条不落账 → v3v DS5 红"),
    (TPL, "    const e1=e1rmOfExercise(e);",
     "    const e1=e1rm(gv.effectiveKg,e.reps,recordedRpeOf(e));",
     "F8 徽章退回吃卡片 reps → v3v BS1/BS2 红（徽章与账本不同值）"),
    (TPL, "    rpe:recordedRpeOf(e)\n  };",
     "    rpe:(lastSetOf(e)?recordedRpeOf(e):null)\n  };",
     "F9 无逐组记录时丢掉旧单值 RPE → v3v BS3 红"),
    (TPL, "rpe:(rpe>0?rpe:null),rpeAssumed:!(rpe>0)",
     "rpe:(rpe>0?rpe:10),rpeAssumed:false",
     "F10 CSV 导入空 actual_rpe 补 10 → v3v RP5 红"),
]

EXPECT = {
    1: "F1 预填目标 RPE → RP1 红 + RP2 红",
    2: "F2 账本拿 targetRpe 兜底 → RP2 红",
    3: "F3 逐组 RPE 写死 8 → RP3 红",
    4: "F4 e1RM 补默认 8 → RP4 红 + RP2 红",
    5: "F5 拆掉未保存闸门 → DS2 红 + DS3 红 + DS5 红",
    6: "F6 「放弃」不绕过闸门 → DS4 红",
    7: "F7 「保存离开」不落账 → DS5 红",
    8: "F8 徽章退回吃卡片 reps → BS1 红 + BS2 红",
    9: "F9 无逐组记录时丢掉旧单值 RPE → BS3 红",
    10: "F10 CSV 导入空 actual_rpe 补 10 → RP5 红",
}


def read(p):
    # newline=''：逐字节读写，还原时不会把 CRLF 文件悄悄改成 LF
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


def inject(pick=None):
    idxs = range(1, len(FAULTS) + 1) if pick is None else [pick]
    ledger = {}
    for k in idxs:
        path, old, new, why = FAULTS[k - 1]
        src = read(path)
        hit = find(src, old)
        if hit is None:
            sys.exit("故障目标串没找到（%s）：%r" % (why, old[:60]))
        rep = new.replace("\n", "\r\n") if ("\r\n" in src and "\n" in new) else new
        ledger.setdefault(path, read(path))
        write(path, src.replace(hit, rep, 1))
        print("注入: %s" % why)
    with io.open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False)
    print("原件已存 %s（%d 个文件）" % (LEDGER, len(ledger)))


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
        inject(int(sys.argv[2]) if len(sys.argv) > 2 else None)
    elif mode == "revert":
        revert()
    else:
        sys.exit(__doc__)
