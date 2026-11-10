"""前期准备自检：环境、目录、网络、题目模板、凭证状态。

    python prepare/check_env.py
    python prepare/check_env.py --contest gcc_2026_mfg --problem spmmsum

不提交任何东西，也不会修改 code/。缺什么会直接打印下一步该做什么。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "submit"))
import cannjudge_api as api  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
CODE = REPO / "code"
RESULTS = REPO / "prepare" / "submit" / "results"


def mark(ok: bool, text: str) -> bool:
    print(f"  [{'OK' if ok else '缺'}] {text}")
    return ok


def check_python() -> bool:
    version = sys.version_info
    return mark(version >= (3, 8), f"Python {version.major}.{version.minor}.{version.micro}（需要 >= 3.8）")


def check_dirs() -> bool:
    ok = True
    for path, label in (
        (REPO / "code", "code/ 目录"),
        (REPO / "cases", "cases/ 目录"),
        (REPO / "optimize" / "versions", "optimize/versions/ 目录"),
        (REPO / "prepare" / "credentials", "prepare/credentials/ 目录"),
        (REPO / "prepare" / "remote", "prepare/remote/ 目录"),
        (REPO / "prepare" / "submit", "prepare/submit/ 目录"),
        (RESULTS, "results/ 目录"),
    ):
        ok = mark(path.is_dir(), f"{label}: {path}") and ok
    if CODE.is_dir():
        real = [p for p in CODE.rglob("*") if p.is_file() and p.name != ".gitkeep"]
        if real:
            print(f"  [OK] code/ 里有 {len(real)} 个文件")
        else:
            print("  [空] code/ 还是空的，先把比赛题目的空工程放进来")
    return ok


def check_problem(contest: str, problem: str, group: str) -> bool:
    client = api.Client("")
    try:
        resolved = api.resolve_problem(client, contest, problem, group)
        template_files = api.load_template(client, resolved["problem_id"])
    except api.ApiError as exc:
        if "网络请求失败" in str(exc):
            mark(False, f"访问 {api.SITE} 失败: {exc}")
        else:
            mark(False, f"解析题目失败: {exc}")
            print("       如果是 401/403，先按 prepare/credentials/GET_COOKIE.md 配好 Cookie 再跑。")
        return False
    editable = [item for item in template_files if item["editable"]]
    print(f"  [OK] 题目 {resolved['problem_name']}，模板 {len(template_files)} 个文件，其中可编辑 {len(editable)} 个")
    for item in template_files:
        local = CODE.joinpath(*item["path"].split("/"))
        state = "本地有" if local.is_file() else ("模板可编辑，本地缺" if item["editable"] else "服务器模板")
        print(f"       {item['path']:<40} {state}")
    missing = [item["path"] for item in editable if not CODE.joinpath(*item["path"].split("/")).is_file()]
    if missing:
        print("  [缺] code/ 缺少模板要求的文件，提交会失败：")
        for path in missing:
            print(f"       {path}")
        print("       把比赛网站下载的空工程整体放进 code/，保持相同的相对路径。")
        return False
    if editable:
        print("  [OK] code/ 已覆盖模板要求的全部可编辑文件")
    return True


def check_credentials() -> bool:
    cookie = api.read_secret_line(api.COOKIE_FILE)
    user_id = api.read_secret_line(api.USER_ID_FILE)
    if cookie:
        state = "格式正确" if api.cookie_is_well_formed(cookie) else "格式可疑，建议重新取"
        print(f"  [有] Cookie 存档（{state}）。Cookie 会过期，提交前建议重新取。")
    else:
        print("  [无] 还没有 Cookie。按 prepare/credentials/GET_COOKIE.md 获取。")
    mark(bool(user_id), f"userId 存档: {api.USER_ID_FILE if user_id else '没有'}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="CANNJudge 前期准备自检")
    parser.add_argument("--contest", default=api.DEFAULT_CONTEST)
    parser.add_argument("--problem", default=api.DEFAULT_PROBLEM)
    parser.add_argument("--group", default="")
    args = parser.parse_args()

    print("== Python ==")
    ok = check_python()
    print("\n== 目录 ==")
    ok = check_dirs() and ok
    print("\n== 网络与题目 ==")
    ok = check_problem(args.contest, args.problem, args.group) and ok
    print("\n== 凭证 ==")
    check_credentials()

    print("\n" + ("全部通过，可以开始改代码并提交。" if ok else "有未通过项，按上面的提示补齐。"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
