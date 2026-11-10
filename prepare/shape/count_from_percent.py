"""按 Judge 显示的误差百分比，枚举相容的失败元素个数。

Judge 显示两位小数。若显示值来自 k/N，则只有少数整数 k 相容。

    python count_from_percent.py --percent 0.78 --max-n 1024
    python count_from_percent.py --percent 0.15 --max-n 4096 --n 131072
"""

from __future__ import annotations

import argparse


def consistent(shown: float, total: int) -> list[int]:
    low, high = shown - 0.005, shown + 0.005
    return [k for k in range(0, total + 1) if low <= round(k / total * 100, 10) < high]


def main() -> int:
    parser = argparse.ArgumentParser(description="误差百分比 -> 失败元素个数")
    parser.add_argument("--percent", type=float, required=True, help="Judge 显示的百分比，例如 0.78")
    parser.add_argument("--max-n", type=int, default=1024, help="枚举的元素总数上限")
    parser.add_argument("--n", type=int, default=0, help="直接验证某个元素总数")
    args = parser.parse_args()

    if args.n:
        counts = consistent(args.percent, args.n)
        single = "（恰好 1 个元素）" if counts == [1] else ""
        print(f"N={args.n}: {counts}{single}")
        return 0

    found = []
    for total in range(1, args.max_n + 1):
        counts = consistent(args.percent, total)
        if counts == [1]:
            found.append(total)
    if found:
        print(f"{args.percent}% 恰好等于 1 个元素的 N（<= {args.max_n}）:")
        print("  " + ", ".join(str(value) for value in found))
    else:
        print(f"{args.percent}% 在 N <= {args.max_n} 内没有「恰好 1 个元素」的解")

    print("\n再看几个常见 N：")
    for total in (64, 128, 256, 512, 1024):
        if total <= args.max_n:
            print(f"  N={total:6d}  k in {consistent(args.percent, total)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
