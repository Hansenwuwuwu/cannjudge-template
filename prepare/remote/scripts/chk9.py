"""九点数值比对。参考实现是 SwiGLU，换题目改 reference()。

用法（远端）: python3 chk9.py <root>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

TOLERANCE = 2e-3


def reference(x, w1, b1, w2, b2):
    z1 = x @ w1.T + b1
    z2 = x @ w2.T + b2
    return (z1 / (1 + np.exp(-z1)) * z2).reshape(-1)


def check(root) -> int:
    root = Path(root)
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    failures = 0
    for case in config["cases"]:
        name = case["name"]
        shape = case["shape"]
        dim = shape[-1]
        rows = 1
        for value in shape[:-1]:
            rows *= value

        folder = root / "inputs" / name
        output = Path(f"/tmp/out_{name}") / "output_f16.bin"
        if not output.exists():
            print("%-6s MISSING OUTPUT" % name)
            failures += 1
            continue

        got = np.fromfile(output, dtype="<f2").astype(np.float64).reshape(-1)
        x = np.fromfile(folder / "input_x.bin", dtype="<f2").astype(np.float64).reshape(rows, dim)
        w1 = np.fromfile(folder / "weight_1.bin", dtype="<f2").astype(np.float64).reshape(dim, dim)
        b1 = np.fromfile(folder / "bias_1.bin", dtype="<f2").astype(np.float64)
        w2 = np.fromfile(folder / "weight_2.bin", dtype="<f2").astype(np.float64).reshape(dim, dim)
        b2 = np.fromfile(folder / "bias_2.bin", dtype="<f2").astype(np.float64)

        expect = reference(x, w1, b1, w2, b2)
        if got.size != expect.size:
            print("%-6s LEN got=%d ref=%d" % (name, got.size, expect.size))
            failures += 1
            continue
        diff = np.abs(got - expect)
        bad = int((diff > TOLERANCE).sum())
        print("%-6s maxdiff=%.6f bad=%d" % (name, diff.max(), bad))
        if bad:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(check(sys.argv[1]))
