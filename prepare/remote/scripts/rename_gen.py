"""把上传的四个文件改名成独立算子，再写进 source/。

名字从 config.json 读，换题目只改配置。
用法（远端）: python3 rename_gen.py <root> <updir>
"""

from __future__ import annotations

import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
up = pathlib.Path(sys.argv[2])
config = json.loads((root / "config.json").read_text(encoding="utf-8"))

OP = config["op_name"]
AUDIT = config["audit_name"]
CLASS = config["class_name"]
AUDIT_CLASS = config["audit_class"]

src = root / "source"
pairs = [
    ("host.cpp", f"op_host/{AUDIT}.cpp"),
    ("kernel.cpp", f"op_kernel/{AUDIT}.cpp"),
    ("tiling.h", f"op_kernel/{AUDIT}_tiling.h"),
    ("key.h", f"op_kernel/tiling_key_{AUDIT}.h"),
]


def rename_text(text: str) -> str:
    text = text.lstrip("\ufeff")
    return text.replace(OP, AUDIT).replace(CLASS, AUDIT_CLASS)


for src_name, dst_rel in pairs:
    text = (up / src_name).read_text(encoding="utf-8-sig")
    out = rename_text(text)
    dst = src / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(out, encoding="utf-8")
    print("wrote", dst_rel, len(out), "chars")

# 评测机是 910B4：20 AIC / 40 AIV。远端整机核数更多，这里按 Judge 口径截断。
host_path = src / f"op_host/{AUDIT}.cpp"
text = host_path.read_text(encoding="utf-8")
old = """    const uint32_t aicCoreNum = platform.GetCoreNumAic();
    const uint32_t aivCoreNum = platform.GetCoreNumAiv();"""
new = """    // 仅在远端验证时模拟 Judge 的 910B4（20 AIC / 40 AIV）。
    const uint32_t aicCoreNumHw = platform.GetCoreNumAic();
    const uint32_t aivCoreNumHw = platform.GetCoreNumAiv();
    const uint32_t aicCoreNum = aicCoreNumHw > 20u ? 20u : aicCoreNumHw;
    const uint32_t aivCoreNum = aivCoreNumHw > 40u ? 40u : aivCoreNumHw;"""
if old in text:
    text = text.replace(old, new, 1)
    host_path.write_text(text, encoding="utf-8")
    print("patched host for 20/40")
else:
    print("warn: 没找到 GetCoreNumAic/GetCoreNumAiv 连续两行，跳过 20/40 patch")

print("host_opdef_ok", f"class {AUDIT_CLASS} : public OpDef" in host_path.read_text(encoding="utf-8"))
print("kernel_entry_ok", f"void {AUDIT}(" in (src / f"op_kernel/{AUDIT}.cpp").read_text(encoding="utf-8"))
