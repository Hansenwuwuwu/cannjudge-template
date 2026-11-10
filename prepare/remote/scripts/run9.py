"""跑九点：按 config.json 的 cases 调 runner，再交给 chk9 比对。

用法（远端）: python3 run9.py <root>
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chk9  # noqa: E402

REPEAT = "3"
PREFILL = "3"
TIMEOUT = 180


def main() -> int:
    root = Path(sys.argv[1])
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    runner = root / "build_runner" / "current_audit_runner"
    library = root / "build" / "libcust_opapi.so"
    entry = config["aclnn_entry"]

    if not runner.is_file():
        print(f"缺少 runner: {runner}")
        return 2
    if not library.is_file():
        print(f"缺少算子库: {library}")
        return 2

    for case in config["cases"]:
        name = case["name"]
        shape = ",".join(str(value) for value in case["shape"])
        outdir = Path(f"/tmp/out_{name}")
        subprocess.run(["rm", "-rf", str(outdir)], check=False)
        outdir.mkdir(parents=True, exist_ok=True)
        command = [
            str(runner),
            str(root / "inputs" / name),
            str(outdir),
            shape,
            str(library),
            entry,
            REPEAT,
            PREFILL,
        ]
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=TIMEOUT)
            lines = [
                line
                for line in (proc.stdout + proc.stderr).splitlines()
                if "R27_RUN_OK" in line or "R27_RUN_ERROR" in line or "wrong input" in line
            ]
            result = lines[-1] if lines else "NO_RESULT"
        except subprocess.TimeoutExpired:
            result = f"TIMEOUT {TIMEOUT}s"
        print(f"=== {name} -> {result}")

    print("=== numbers")
    return chk9.check(root)


if __name__ == "__main__":
    raise SystemExit(main())
