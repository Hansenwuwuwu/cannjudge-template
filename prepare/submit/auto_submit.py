"""一条命令走完：提交 → 等 180 秒 → 读结果 → 落盘。

默认提交仓库根目录的 code/。Cookie 每次都建议重新取，详见 prepare/credentials/GET_COOKIE.md。

    python prepare/submit/auto_submit.py
    python prepare/submit/auto_submit.py --dry-run
    python prepare/submit/auto_submit.py --wait 180 --label c8_split32
    python prepare/submit/auto_submit.py --read-only 6a1b2c3d
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cannjudge_api as api  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CODE = REPO / "code"
RESULTS = Path(__file__).resolve().parent / "results"
RECEIPT = RESULTS / "last_submission.json"
LOG = RESULTS / "JUDGE_LOG.md"
WAIT_SECONDS = 180
POLL_INTERVAL = 3
MAX_POLLS = 100


def log_header(count: int) -> str:
    columns = " | ".join(f"c{index}" for index in range(1, count + 1))
    dividers = " | ".join("---" for _ in range(count))
    return (
        "# 提交记录\n\n"
        "由 `auto_submit.py` 自动追加。时间为本机时间，用时单位 µs。\n\n"
        f"| 时间 | 标签 | 结果 | {columns} | 合计 | 编号 |\n"
        f"| --- | --- | --- | {dividers} | --- | --- |\n"
    )


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def default_label(code_dir: Path) -> str:
    if code_dir.name == "code":
        parent = code_dir.parent.name
        if parent in {REPO.name, "cannjudge-template"}:
            return "baseline"
        return parent
    return code_dir.name


def cell_time(point: dict) -> str:
    if not api.is_pass(point):
        return point.get("status") or "—"
    value = point.get("time_us")
    if isinstance(value, (int, float)) and value > 0:
        return f"{value:.2f}"
    return "—"


def write_log(label: str, submission_id: str, points: list[dict], status: str) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    if not LOG.is_file():
        LOG.write_text(log_header(len(points) or 9), encoding="utf-8")
    passed = sum(1 for point in points if api.is_pass(point))
    cells = [cell_time(point) for point in points] or ["—"]
    times = [point["time_us"] for point in points if api.is_pass(point) and isinstance(point.get("time_us"), (int, float)) and point["time_us"] > 0]
    total = f"{sum(times):.2f}" if times else "—"
    result = f"{passed}/{len(points)}" if points else (status or "无结果")
    row = "| " + " | ".join(
        [time.strftime("%Y-%m-%d %H:%M"), label, result, *cells, total, submission_id[:8]]
    ) + " |\n"
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(row)


def save_result(label: str, submission: dict, submission_id: str, page: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    points = api.points_from_submission(submission)
    payload = {
        "label": label,
        "submission_id": submission_id,
        "page": page,
        "status": str(submission.get("status") or ""),
        "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "points": points,
        "submission": submission,
    }
    path = RESULTS / f"judge_{label}_{time.strftime('%Y%m%d_%H%M%S')}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_log(label, submission_id, points, payload["status"])
    return path


def poll_until_done(client: api.Client, submission_id: str, interval: int, max_polls: int) -> dict:
    api.log(f"开始轮询，每 {interval} 秒一次，最多 {max_polls} 次")
    errors = 0
    last_status = ""
    for index in range(1, max_polls + 1):
        time.sleep(interval)
        try:
            submission = client.get(f"/api/submissions/{submission_id}")
        except api.ApiError as exc:
            errors += 1
            if errors >= 5:
                api.log(f"连续 5 次查询失败，停止轮询。提交已发出，可稍后重跑 --read-only。原因: {exc}")
                return {}
            api.log(f"查询失败（{errors}/5）: {exc}")
            continue
        errors = 0
        status = str(submission.get("status") or "").strip()
        if status and status != last_status:
            last_status = status
            api.log(f"状态变化: {status}")
        if status and not api.IN_PROGRESS.search(status):
            return submission
        if index % 10 == 0:
            api.log(f"仍在评测（{index * interval}s，状态 = {status or '?'}）")
    api.log(f"轮询 {max_polls} 次仍未出结果，请稍后用 --read-only 再读。")
    return {}


def confirm_owner(client: api.Client, user_id: str, submission_id: str) -> bool:
    """确认这个编号仍是账号里最新的一条，防止把别的提交结果记成这次。"""
    if not user_id:
        api.log("没有 userId，跳过归属核对")
        return True
    try:
        newest = api.newest_submission_id(client, user_id)
    except api.ApiError as exc:
        api.log(f"归属核对失败（{exc}），继续记录")
        return True
    if newest and newest != submission_id:
        api.log(f"账号里最新一条是 {newest[:8]}，不是本次 {submission_id[:8]}，不写入记录")
        return False
    return True


def read_and_save(client: api.Client, label: str, submission_id: str, page: str = "") -> int:
    submission = client.get(f"/api/submissions/{submission_id}")
    status = str(submission.get("status") or "").strip()
    api.log(f"submission {submission_id}  状态 {status or '未知'}")
    if not status or api.IN_PROGRESS.search(status):
        api.log("评测还没结束，本次不落盘。")
        return 2
    api.print_finished(submission)
    path = save_result(label, submission, submission_id, page)
    print(f"\n已写入 {path}")
    print(f"已追加 {LOG}")
    return 0


def parse_args():
    parser = argparse.ArgumentParser(description="提交 code/ 到 CANNJudge，等 180 秒后读结果")
    parser.add_argument("code_dir", nargs="?", default=str(DEFAULT_CODE), help="含 op_host/op_kernel 的目录，默认 code/")
    parser.add_argument("--dry-run", action="store_true", help="只核对要上传的文件，不 POST")
    parser.add_argument("--read-only", default="", metavar="ID", help="不提交，只读取指定 submission id")
    parser.add_argument("--label", default="", help="记录用的版本名，默认取目录名")
    parser.add_argument("--wait", type=int, default=WAIT_SECONDS, help="提交后先等多少秒再读，默认 180")
    parser.add_argument("--poll-interval", type=int, default=POLL_INTERVAL)
    parser.add_argument("--max-polls", type=int, default=MAX_POLLS)
    parser.add_argument("--cookie", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--contest", default=api.DEFAULT_CONTEST)
    parser.add_argument("--problem", default=api.DEFAULT_PROBLEM)
    parser.add_argument("--group", default="")
    parser.add_argument("--extra-file", action="append", default=[], help="额外上传 code_dir 下的文件，可重复")
    parser.add_argument("--yes", action="store_true", help="非交互：直接用已保存的 Cookie，不询问")
    return parser.parse_args()


def main() -> int:
    configure_stdio()
    args = parse_args()
    code_dir = Path(args.code_dir).resolve()
    label = args.label or default_label(code_dir)

    cookie, user_id = api.resolve_credentials(
        args.cookie, args.user_id, interactive=not args.yes
    )

    if cookie and not api.cookie_is_well_formed(cookie):
        print("Cookie 格式不对。需要 name=value; name2=value2，不要只留裸令牌。", file=sys.stderr)
        return 1

    if args.read_only:
        if not cookie:
            print(api.cookie_help(), file=sys.stderr)
            return 1
        try:
            return read_and_save(api.Client(cookie), label, args.read_only.strip())
        except api.ApiError as exc:
            print(f"\n出错: {exc}", file=sys.stderr)
            return 1

    if not cookie:
        print(api.cookie_help(), file=sys.stderr)
        return 1

    client = api.Client(cookie)
    try:
        resolved = api.resolve_problem(client, args.contest, args.problem, args.group)
        template_files = api.load_template(client, resolved["problem_id"])
        editable = [item for item in template_files if item["editable"]]
        api.log("模板可编辑文件(" + str(len(editable)) + "): " + ", ".join(item["path"] for item in editable))
        payload = api.build_payload(
            code_dir, template_files, resolved["problem_id"], user_id, extra_files=args.extra_file
        )
    except api.ApiError as exc:
        print(f"\n出错: {exc}", file=sys.stderr)
        if exc.status in (401, 403):
            print("Cookie 可能已过期，请重新获取。", file=sys.stderr)
        return 1

    files = [
        {"path": item["path"], "chars": len(item["content"]), "sha256": api.sha256_text(item["content"])}
        for item in payload["files"]
    ]

    if args.dry_run:
        api.report_dry_run(code_dir, template_files, payload, resolved)
        return 0

    try:
        result = api.submit_once(client, payload)
    except api.ApiError as exc:
        print(f"\n出错: {exc}", file=sys.stderr)
        if exc.status in (401, 403):
            print("Cookie 可能已过期，请重新获取。", file=sys.stderr)
        return 1

    submission_id = str((result.get("data") or {}).get("submissionId") or result.get("submissionId") or "").strip()
    if not submission_id:
        print("提交返回里没有 submissionId: " + json.dumps(result, ensure_ascii=False)[:300], file=sys.stderr)
        return 1

    page = api.result_page(resolved, submission_id)
    api.log(f"提交成功，submissionId: {submission_id}")
    print(f"结果页: {page}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    receipt = {
        "submission_id": submission_id,
        "label": label,
        "code_dir": str(code_dir),
        "page": page,
        "contest": resolved["contest_name"],
        "problem": resolved["problem_name"],
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "files": files,
    }
    RECEIPT.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    wait_seconds = max(0, args.wait)
    if wait_seconds:
        api.log(f"等待 {wait_seconds} 秒后开始读结果（评测通常在 1-3 分钟）")
        time.sleep(wait_seconds)

    try:
        submission = poll_until_done(client, submission_id, max(1, args.poll_interval), max(1, args.max_polls))
    except api.ApiError as exc:
        print(f"\n读结果出错: {exc}", file=sys.stderr)
        return 1

    if not submission:
        print("\n这次没有读到最终结果。稍后可执行：")
        print(f"  python prepare/submit/auto_submit.py --read-only {submission_id}")
        return 2

    if not confirm_owner(client, user_id, submission_id):
        return 2

    api.print_finished(submission)
    path = save_result(label, submission, submission_id, page)
    print(f"\n已写入 {path}")
    print(f"已追加 {LOG}")
    print("\n提醒: Cookie 会过期，下次提交前按 prepare/credentials/GET_COOKIE.md 重新获取。")

    status = str(submission.get("status") or "")
    return 0 if status.lower() in {"accepted", "pass"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
