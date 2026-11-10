"""CANNJudge HTTP API 客户端（只用标准库）。

流程对应 https://gitcode.com/luanchess/cannjudge-auto-submit 的 submit-api.js：
解析公开赛事与题目 → 取服务器模板 → 用本地 code/ 覆盖可编辑文件 →
POST /api/submissions/submit → GET /api/submissions/{id} 读结果。

Cookie 与 userId 属于登录凭证，只存放在仓库外的 %USERPROFILE%\\.cannjudge\\，
不进入版本库。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

SITE = "https://cannjudge.cn"
DEFAULT_CONTEST = ""
DEFAULT_PROBLEM = ""
CONTEST_CONFIG = Path(__file__).resolve().parents[1] / "contest.json"
SECRET_DIR = Path.home() / ".cannjudge"
COOKIE_FILE = SECRET_DIR / "cookie.txt"
USER_ID_FILE = SECRET_DIR / "user_id.txt"

RATE_LIMIT_MS = 5000
MAX_SUBMIT_ATTEMPTS = 5
IN_PROGRESS = re.compile(
    r"\b(wait(ing)?|running|queu(e|ed|ing)|pending|judg(ing)?|"
    r"process(ing)?|prepar(ing)?|in progress)\b|"
    r"compiling|排队|等待|运行中|评测中|编译中|处理中|执行中",
    re.IGNORECASE,
)


class ApiError(RuntimeError):
    def __init__(self, message: str, status: int | None = None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def slugify(value: str) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", value.lower()))


def token_matches(token: str, entity: dict) -> bool:
    want = str(token or "").strip().lower()
    if not want or not isinstance(entity, dict):
        return False
    keys = set()
    for field in ("name", "slug", "title", "token", "url_token", "path"):
        raw = entity.get(field)
        if raw is None:
            continue
        text = str(raw).strip()
        if not text:
            continue
        keys.add(text.lower())
        keys.add(slugify(text))
    return want in keys or slugify(want) in keys


class Client:
    def __init__(self, cookie: str = ""):
        self.cookie = cookie.strip()

    def request(self, method: str, path: str, body=None, origin: bool = False):
        # GET 遇到瞬时网络错误重试一次；POST 不重试，避免重复提交。
        attempts = 2 if method == "GET" else 1
        for attempt in range(1, attempts + 1):
            try:
                return self._request_once(method, path, body, origin)
            except ApiError as exc:
                if attempt < attempts and "网络请求失败" in str(exc):
                    log(f"网络抖动，1 秒后重试: {exc}")
                    time.sleep(1)
                    continue
                raise
        raise ApiError("请求未得到响应")

    def _request_once(self, method: str, path: str, body=None, origin: bool = False):
        headers = {"User-Agent": "cannjudge-template", "Accept": "application/json"}
        if self.cookie:
            headers["Cookie"] = self.cookie
        if origin:
            headers["Origin"] = SITE
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(SITE + path, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8", errors="replace")
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            status = exc.code
        except urllib.error.URLError as exc:
            raise ApiError(f"网络请求失败: {exc.reason}") from exc
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"message": raw}
        if status >= 400:
            message = (
                payload.get("message")
                or payload.get("msg")
                or payload.get("error")
                or payload.get("detail")
                or (payload.get("data") or {}).get("message")
                or (payload.get("data") or {}).get("msg")
                or f"HTTP {status}"
            )
            raise ApiError(str(message), status, payload)
        return payload

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, body: dict):
        return self.request("POST", path, body, origin=True)


def resolve_problem(client: Client, contest_token: str, problem_token: str, group_token: str = ""):
    log("解析题目 ID")
    if group_token:
        group = None
        try:
            group = client.get(f"/api/groups/name/{urllib.request.quote(group_token)}")
        except ApiError:
            group = None
        group_id = str((group or {}).get("_id") or (group or {}).get("id") or "")
        if not group_id:
            groups = client.get("/api/groups")
            if not isinstance(groups, list):
                raise ApiError("获取小组列表失败")
            matched = next((item for item in groups if token_matches(group_token, item)), None)
            group_id = str((matched or {}).get("_id") or (matched or {}).get("id") or "")
        if not group_id:
            raise ApiError(f"未找到小组 {group_token}")
        log(f"小组 {group_token}: {group_id}")
    else:
        group = client.get("/api/groups/public")
        group_id = str(group.get("_id") or group.get("id") or "")
        if not group_id:
            raise ApiError("获取公开小组失败")
        log(f"公开小组: {group_id}")

    contests = client.get(f"/api/contests/group/{group_id}")
    if not isinstance(contests, list):
        raise ApiError("获取赛事列表失败")
    contest = next((item for item in contests if token_matches(contest_token, item)), None)
    if not contest:
        names = ", ".join(str(item.get("name") or "") for item in contests[:12])
        raise ApiError(f"未找到赛事 {contest_token}。当前可见: {names}")
    contest_id = str(contest.get("_id") or contest.get("id") or "")
    log(f"赛事 {contest.get('name')}: {contest_id}")

    problems = client.get(f"/api/problems/contest/{contest_id}")
    if not isinstance(problems, list):
        raise ApiError("获取题目列表失败")
    problem = next((item for item in problems if token_matches(problem_token, item)), None)
    if not problem:
        names = ", ".join(str(item.get("name") or "") for item in problems)
        raise ApiError(f"未找到题目 {problem_token}。当前可见: {names}")
    problem_id = str(problem.get("_id") or problem.get("id") or "")
    log(f"题目 {problem.get('name')}: {problem_id}")
    return {
        "problem_id": problem_id,
        "contest_id": contest_id,
        "group_id": group_id,
        "problem_name": str(problem.get("name") or problem_token),
        "contest_name": str(contest.get("name") or contest_token),
    }


def load_template(client: Client, problem_id: str) -> list[dict]:
    payload = client.get(f"/api/problems/{problem_id}/template")
    data = payload.get("data") if isinstance(payload, dict) else None
    data = data if isinstance(data, dict) else payload if isinstance(payload, dict) else {}
    files = data.get("files") if isinstance(data.get("files"), list) else []
    if not files:
        # 老题目没有 files 数组，只有四个固定字段。
        files = [
            {"path": "tiling.h", "content": data.get("tiling_h") or "", "editable": True},
            {
                "path": "tiling_key.h",
                "content": data.get("tiling_key_h") or data.get("tiling_key_cpp") or "",
                "editable": True,
            },
            {"path": "host.cpp", "content": data.get("host_cpp") or "", "editable": True},
            {"path": "kernel.cpp", "content": data.get("kernel_cpp") or "", "editable": True},
        ]
    normalized = []
    for item in files:
        key = str(item.get("key") or item.get("path") or item.get("label") or "").strip()
        path = str(item.get("path") or item.get("key") or item.get("label") or "").strip()
        if not key:
            continue
        normalized.append(
            {
                "key": key,
                "path": path.replace("\\", "/"),
                "content": str(item.get("content") or ""),
                "editable": item.get("editable") is not False,
            }
        )
    return normalized


def read_local(code_dir: Path, relative: str) -> str:
    local = code_dir.joinpath(*relative.split("/"))
    text = local.read_text(encoding="utf-8-sig")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    return text


def legacy_payload(files: list[dict]) -> dict:
    def find(predicate) -> str:
        for item in files:
            file_path = str(item["path"]).replace("\\", "/")
            base = file_path.split("/")[-1]
            if predicate(file_path, base):
                return item["content"]
        return ""

    tiling = find(lambda _path, base: base == "tiling.h" or bool(re.search(r"_tiling\.h$", base, re.I)))
    tiling_key = find(
        lambda path, base: base == "tiling_key.h"
        or (path.startswith("op_kernel/") and bool(re.search(r"^tiling_key_|_tiling_key\.h$", base, re.I)))
    )
    host = find(
        lambda path, base: path.startswith("op_host/")
        and base != "CMakeLists.txt"
        and bool(re.search(r"\.(cc|cpp|cxx|h|hpp)$", base, re.I))
    ) or find(lambda _path, base: base == "host.cpp")
    kernel = find(
        lambda path, base: path.startswith("op_kernel/")
        and base != "CMakeLists.txt"
        and bool(re.search(r"\.(cc|cpp|cxx)$", base, re.I))
    ) or find(lambda _path, base: base == "kernel.cpp")
    return {
        "tiling_h": tiling,
        "tiling_key_h": tiling_key,
        "host_cpp": host,
        "kernel_cpp": kernel,
    }


def local_includes(text: str) -> list[str]:
    return re.findall(r'^\s*#include\s+"([^"]+)"', text, re.M)


def build_payload(
    code_dir: Path,
    template_files: list[dict],
    problem_id: str,
    user_id: str,
    *,
    extra_files: list[str] | None = None,
) -> dict:
    if not code_dir.is_dir():
        raise ApiError(f"找不到代码目录: {code_dir}")
    editable = [dict(item) for item in template_files if item["editable"]]
    missing = []
    for item in editable:
        local = code_dir.joinpath(*item["path"].split("/"))
        if not local.is_file():
            missing.append(item["path"])
            continue
        item["content"] = read_local(code_dir, item["path"])
    if missing:
        raise ApiError("本地缺少模板要求的文件: " + ", ".join(missing))

    known_paths = {item["path"] for item in template_files}
    extras = []
    for requested in extra_files or []:
        relative = str(requested).replace("\\", "/")
        pure = PurePosixPath(relative)
        raw_parts = relative.split("/")
        if (
            not relative
            or pure.is_absolute()
            or re.match(r"^[A-Za-z]:", relative)
            or any(part in {"", ".", ".."} for part in raw_parts)
        ):
            raise ApiError(f"非法的额外文件路径: {requested}")
        normalized = pure.as_posix()
        if normalized in known_paths:
            raise ApiError(f"额外文件与模板路径重复: {normalized}")
        local = (code_dir / Path(*pure.parts)).resolve()
        if not local.is_relative_to(code_dir.resolve()) or not local.is_file():
            raise ApiError(f"额外文件不存在或不在 code 目录内: {normalized}")
        known_paths.add(normalized)
        extras.append({"path": normalized, "content": read_local(code_dir, normalized)})

    merged = template_files_with_local(template_files, editable)
    payload = {
        "problemId": problem_id,
        "files": [
            *[{"path": item["path"], "content": item["content"]} for item in editable],
            *extras,
        ],
        **legacy_payload(merged),
    }
    if user_id:
        payload["userId"] = user_id
    return payload


def template_files_with_local(template_files: list[dict], editable: list[dict]) -> list[dict]:
    replaced = {item["path"]: item["content"] for item in editable}
    merged = []
    for item in template_files:
        copied = dict(item)
        if copied["path"] in replaced:
            copied["content"] = replaced[copied["path"]]
        merged.append(copied)
    return merged


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def warn_unsubmitted_headers(code_dir: Path, template_files: list[dict], extra_files: list[str] | None = None) -> None:
    """提示本地引用了接口不会上传的头文件，避免白跑一次评测。"""
    known = {item["path"] for item in template_files}
    known.update(str(path).replace("\\", "/") for path in extra_files or [])
    known_bases = {path.split("/")[-1] for path in known}
    local_files = {}
    for path in code_dir.rglob("*"):
        if path.is_file():
            local_files.setdefault(path.name, path.relative_to(code_dir).as_posix())
    for path in code_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".cpp", ".cc", ".cxx", ".h", ".hpp"}:
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError:
            continue
        for include in local_includes(text):
            name = include.replace("\\", "/").split("/")[-1]
            local_rel = local_files.get(name)
            if not local_rel or local_rel in known or name in known_bases:
                continue
            relative = path.relative_to(code_dir).as_posix()
            log(f"注意: {relative} 引用了 {include}，该头文件不在模板里，接口不会上传它")


def report_dry_run(code_dir: Path, template_files: list[dict], payload: dict, resolved: dict) -> None:
    print()
    print("========== 只核对，未提交 ==========")
    print(f"赛事: {resolved['contest_name']}  {resolved['contest_id']}")
    print(f"题目: {resolved['problem_name']}  {resolved['problem_id']}")
    print(f"代码: {code_dir}")
    print()
    local_by_path = {item["path"]: item["content"] for item in payload["files"]}
    template_paths = {item["path"] for item in template_files}
    for item in payload["files"]:
        if item["path"] not in template_paths:
            print(
                f"  附加上传 {item['path']}  {len(item['content'])} 字符  "
                f"sha256={sha256_text(item['content'])[:16]}"
            )
    for item in template_files:
        path = item["path"]
        local = code_dir.joinpath(*path.split("/"))
        if path in local_by_path:
            content = local_by_path[path]
            newline = "CRLF" if "\r\n" in content else "LF"
            state = "与模板相同" if content == item["content"] else "将覆盖模板"
            print(
                f"  上传 {path}  {len(content)} 字符  {newline}  "
                f"sha256={sha256_text(content)[:16]}  {state}"
            )
        elif local.is_file():
            print(f"  跳过 {path}  接口不上传，评测用服务器模板")
        else:
            print(f"  跳过 {path}  本地没有，评测用服务器模板")
    print()
    print(
        "兼容字段: "
        f"tiling_h={len(payload['tiling_h'])} 字符, "
        f"tiling_key_h={len(payload['tiling_key_h'])} 字符, "
        f"host_cpp={len(payload['host_cpp'])} 字符, "
        f"kernel_cpp={len(payload['kernel_cpp'])} 字符"
    )
    extra_paths = [item["path"] for item in payload["files"] if item["path"] not in template_paths]
    warn_unsubmitted_headers(code_dir, template_files, extra_paths)
    print("========== 核对结束，未向服务器提交 ==========")


def result_page(resolved: dict, submission_id: str) -> str:
    return (
        f"{SITE}/public/{resolved['contest_name']}/{resolved['problem_name']}"
        f"/submission/{submission_id}"
    )


def submit_once(client: Client, payload: dict) -> dict:
    last_error = None
    for attempt in range(1, MAX_SUBMIT_ATTEMPTS + 1):
        log(f"第 {attempt} 次提交")
        try:
            return client.post("/api/submissions/submit", payload)
        except ApiError as exc:
            last_error = exc
            limited = exc.status == 429 or bool(re.search(r"频繁|429|rate", str(exc), re.I))
            if not limited:
                if re.search(r"找不到用户|userId|请先登录", str(exc), re.I):
                    raise ApiError(
                        f"{exc}\n提交接口要求 userId。浏览器登录后按 prepare/credentials/GET_COOKIE.md 取值。"
                    ) from exc
                raise
            seconds = parse_rate_limit_seconds(str(exc))
            if seconds is not None and seconds * 1000 >= RATE_LIMIT_MS * 2:
                raise ApiError(f"触发限流，需要等待约 {seconds} 秒。这次没有继续重试。") from exc
            if attempt == MAX_SUBMIT_ATTEMPTS:
                raise
            wait_seconds = seconds + 1 if seconds is not None else RATE_LIMIT_MS / 1000
            log(f"触发限流（{exc}），等待 {wait_seconds:.0f} 秒后重试")
            time.sleep(wait_seconds)
    raise ApiError(f"提交未得到响应: {last_error}")


def parse_rate_limit_seconds(message: str):
    match = re.search(r"(\d+)\s*秒", str(message or ""))
    if not match:
        return None
    seconds = int(match.group(1))
    return seconds if seconds > 0 else None


def format_time(us) -> str:
    if not isinstance(us, (int, float)) or not (us == us) or us <= 0:
        return ""
    if us < 1000:
        return f"{us:.2f} µs"
    if us < 1_000_000:
        return f"{us / 1000:.3f} ms"
    return f"{us / 1_000_000:.3f} s"


def format_error_pct(precision) -> str:
    if not isinstance(precision, (int, float)) or not (precision == precision):
        return ""
    return f"{(1 - precision) * 100:.2f}%"


def is_pass(item: dict) -> bool:
    return bool(re.search(r"pass", str(item.get("testcase_status") or ""), re.I))


def points_from_submission(submission: dict) -> list[dict]:
    rows = submission.get("result") if isinstance(submission.get("result"), list) else []
    points = []
    for index, item in enumerate(rows, 1):
        time_us = item.get("time")
        best_us = item.get("best_time")
        points.append(
            {
                "point": index,
                "status": str(item.get("testcase_status") or ""),
                "error_percent": format_error_pct(item.get("precision_ratio")),
                "time_us": time_us if isinstance(time_us, (int, float)) and time_us == time_us else None,
                "best_time_us": best_us if isinstance(best_us, (int, float)) and best_us == best_us else None,
                "msg": str(item.get("msg") or "").strip(),
            }
        )
    return points


def print_finished(submission: dict) -> None:
    status = str(submission.get("status") or "").strip()
    rows = submission.get("result") if isinstance(submission.get("result"), list) else []
    passed = sum(1 for item in rows if is_pass(item))
    print()
    print(f"评测结束: 状态 = {status}，通过 {passed}/{len(rows)}")

    messages = []
    seen = set()
    for item in rows:
        message = item.get("msg")
        if isinstance(message, str) and message.strip() and message.strip() not in seen:
            seen.add(message.strip())
            messages.append(message.strip())
    if messages:
        print()
        print("编译/运行信息:")
        for index, message in enumerate(messages, 1):
            if len(messages) > 1:
                print(f"--- 报错 [{index}] ---")
            print(message)
        return

    eps = 1e-6

    def positive(value) -> bool:
        return isinstance(value, (int, float)) and value == value and value > 0

    for index, item in enumerate(rows, 1):
        meta = []
        error_pct = format_error_pct(item.get("precision_ratio"))
        used = format_time(item.get("time")) if positive(item.get("time")) else ""
        best = format_time(item.get("best_time")) if positive(item.get("best_time")) else ""
        if is_pass(item) and positive(item.get("time")) and positive(item.get("best_time")) and item["time"] <= item["best_time"] + eps:
            meta.append(f"用时 {used} ★本次最优")
        elif error_pct and used and best:
            meta.append(f"误差比例 {error_pct}，用时 {used}，最优 {best}")
        elif error_pct and used:
            meta.append(f"误差比例 {error_pct}，用时 {used}")
        elif used and best:
            meta.append(f"用时 {used}，最优 {best}")
        elif error_pct:
            meta.append(f"误差比例 {error_pct}")
        elif used:
            meta.append(f"用时 {used}")
        suffix = f"  [{meta[0]}]" if meta else ""
        print(f"  case {index}: {item.get('testcase_status') or '?'}{suffix}")

    times = [item["time"] for item in rows if is_pass(item) and positive(item.get("time"))]
    if times:
        print(f"\n用时合计: {format_time(sum(times))}，单 case 最长 {format_time(max(times))}")


# ---------------------------------------------------------------- 凭证处理


def read_secret_line(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            text = line.strip()
            if text and not text.startswith("#"):
                return text
    except OSError:
        return ""
    return ""


def write_secret_line(path: Path, value: str) -> None:
    SECRET_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(value.strip() + "\n", encoding="utf-8")


def cookie_is_well_formed(cookie: str) -> bool:
    return bool(re.fullmatch(r"[^;\s]+=[^;]+(?:\s*;\s*[^;\s]+=[^;]+)*", cookie.strip()))


def cookie_help() -> str:
    return (
        "没有可用的 Cookie，无法提交。登录 https://cannjudge.cn 后：\n"
        "  1. F12 → Network → 刷新页面 → 点一条 cannjudge.cn 请求\n"
        "  2. Request Headers 里复制整段 Cookie（不要用 document.cookie，HttpOnly 读不到）\n"
        "  3. 形如 name=value; name2=value2，不要带 Cookie: 前缀\n"
        "  4. user_id：F12 Console 执行 JSON.parse(localStorage.getItem('cannjudge_user'))._id\n"
        f"  Cookie 存在仓库外的 {COOKIE_FILE}，不要提交进 git。"
    )


def _saved_age(path: Path) -> str:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return "未知"
    if age < 3600:
        return f"{age / 60:.0f} 分钟前"
    return f"{age / 3600:.1f} 小时前"


def read_contest_config() -> dict:
    try:
        data = json.loads(CONTEST_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def resolve_targets(contest: str = "", problem: str = "") -> tuple[str, str]:
    """参数 > 环境变量 > prepare/contest.json。"""
    saved = read_contest_config()
    contest = contest or os.environ.get("CANNJUDGE_CONTEST", "") or str(saved.get("contest") or "")
    problem = problem or os.environ.get("CANNJUDGE_PROBLEM", "") or str(saved.get("problem") or "")
    return contest.strip(), problem.strip()


def resolve_credentials(
    cookie: str = "",
    user_id: str = "",
    *,
    interactive: bool = True,
) -> tuple[str, str]:
    """按 参数 → 环境变量 → 交互询问 的顺序取凭证。

    Cookie 会过期，所以即使磁盘上有存档也会先问一句是否复用，
    默认回车即要求重新粘贴。userId 不过期，可直接复用存档。
    """
    cookie = (cookie or os.environ.get("CANNJUDGE_COOKIE", "")).strip()
    user_id = (user_id or os.environ.get("CANNJUDGE_USER_ID", "")).strip()

    if not cookie:
        saved = read_secret_line(COOKIE_FILE)
        if saved:
            print(f"发现上次保存的 Cookie（{_saved_age(COOKIE_FILE)}）。Cookie 会过期，建议每次重新获取。")
            if interactive:
                answer = input("  直接回车 = 重新粘贴新的；输入 y = 复用上次的: ").strip().lower()
                if answer == "y":
                    cookie = saved
            else:
                cookie = saved

    if not cookie and interactive:
        print("粘贴新的 Cookie（整段请求头，形如 a=b; c=d）:")
        cookie = input("  Cookie> ").strip()
        if cookie:
            write_secret_line(COOKIE_FILE, cookie)
            print(f"  已保存到 {COOKIE_FILE}（仓库外）")

    if not user_id:
        saved = read_secret_line(USER_ID_FILE)
        if saved:
            user_id = saved
        elif interactive:
            print("账号 userId 还没保存过。F12 Console 执行：")
            print("  JSON.parse(localStorage.getItem('cannjudge_user'))._id")
            user_id = input("  userId> ").strip()
            if user_id:
                write_secret_line(USER_ID_FILE, user_id)
                print(f"  已保存到 {USER_ID_FILE}（仓库外）")

    return cookie, user_id


def get_submission(client: Client, submission_id: str) -> dict:
    return client.get(f"/api/submissions/{submission_id}")


def newest_submission_id(client: Client, user_id: str) -> str:
    items = client.get(f"/api/submissions/user/{user_id}")
    if not isinstance(items, list):
        return ""
    stamped = [item for item in items if isinstance(item, dict) and item.get("create_time")]
    if not stamped:
        return ""
    stamped.sort(key=lambda item: str(item.get("create_time")), reverse=True)
    return str(stamped[0].get("_id") or "")
