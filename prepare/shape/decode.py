"""把 Judge 的用时按一份编码表解码。

编码表是 JSON，三种 kind：

  table   —— 离散档位，最近邻匹配
  linear  —— t = base + step × value
  bands   —— 区间匹配

    python decode.py --spec specs/table.example.json --times "59.9 180 240"
    python decode.py --spec specs/linear.example.json --times "33 36 39" --json

spec 里的数值是你要测的量对应的档位，换题目只换 spec。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_TOLERANCE_MS = 2.0


def to_ms(text: str) -> float:
    value = text.strip().lower().replace("μ", "µ")
    if value.endswith("ms"):
        return float(value[:-2])
    if value.endswith("µs") or value.endswith("us"):
        return float(value[:-2]) / 1000.0
    if value.endswith("s"):
        return float(value[:-1]) * 1000.0
    return float(value)


def split_times(text: str) -> list[float]:
    return [to_ms(part) for part in text.replace(",", " ").split()]


def near(value: float, target: float, tolerance: float) -> bool:
    return abs(value - target) <= tolerance


def decode_table(spec: dict, milliseconds: float) -> object:
    entries = spec.get("entries") or []
    if not entries:
        return None
    tolerance = float(spec.get("tolerance_ms", DEFAULT_TOLERANCE_MS))
    best = min(entries, key=lambda entry: abs(float(entry["time_ms"]) - milliseconds))
    if near(milliseconds, float(best["time_ms"]), tolerance):
        return best["value"]
    fallback = spec.get("fallback")
    if fallback and near(milliseconds, float(fallback["time_ms"]), tolerance):
        return fallback.get("label", "fallback")
    return None


def decode_linear(spec: dict, milliseconds: float) -> object:
    try:
        base = float(spec["base_ms"])
        step = float(spec["step_ms"])
        offset = float(spec.get("offset", 0))
        minimum = float(spec.get("min_value", 0))
        maximum = float(spec.get("max_value", 1e18))
    except KeyError as exc:
        raise SystemExit(f"linear spec 缺少字段: {exc}") from exc
    if step == 0:
        raise SystemExit("linear spec 的 step_ms 不能为 0")

    value = round((milliseconds - base) / step) + offset
    if not (minimum <= value <= maximum):
        return None
    tolerance = float(spec.get("tolerance_ms", DEFAULT_TOLERANCE_MS))
    if not near(milliseconds, base + step * (value - offset), tolerance):
        return None
    return int(value) if float(value).is_integer() else value


def decode_bands(spec: dict, milliseconds: float) -> object:
    no_spin_below = float(spec.get("no_spin_below_ms", 1.0))
    if milliseconds < no_spin_below:
        return spec.get("no_spin_label", "空转没有执行")
    for band in spec.get("bands") or []:
        if float(band["lo_ms"]) <= milliseconds <= float(band["hi_ms"]):
            return band["label"]
    return None


DECODERS = {
    "table": decode_table,
    "linear": decode_linear,
    "bands": decode_bands,
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Judge 用时 -> 测量值")
    parser.add_argument("--spec", required=True, help="编码表 JSON")
    parser.add_argument("--times", required=True, help='九点用时，空格分隔，例如 "59.9 180 240"')
    parser.add_argument("--json", action="store_true", help="输出 JSON 数组")
    args = parser.parse_args()

    path = Path(args.spec).resolve()
    if not path.is_file():
        print(f"找不到 spec: {path}", file=sys.stderr)
        return 1
    spec = json.loads(path.read_text(encoding="utf-8"))
    kind = str(spec.get("kind", "")).strip()
    decoder = DECODERS.get(kind)
    if decoder is None:
        print(f"spec.kind 只能是 table / linear / bands，当前是 {kind!r}", file=sys.stderr)
        return 1

    rows = []
    for index, milliseconds in enumerate(split_times(args.times), 1):
        value = decoder(spec, milliseconds)
        rows.append(
            {
                "point": index,
                "time_ms": milliseconds,
                "value": value,
                "resolved": value is not None,
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    for row in rows:
        shown = row["value"] if row["resolved"] else "?（没有落在任何档位）"
        print(f"点 {row['point']}  {row['time_ms']:g}ms -> {shown}")

    unresolved = sum(1 for row in rows if not row["resolved"])
    if unresolved:
        print(f"\n{unresolved}/{len(rows)} 个点没有解出来，先检查档位和正控制点。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
