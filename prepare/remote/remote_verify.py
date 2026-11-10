"""910B 远端验证：上传 → 编译 → 跑九点 → 可选 msprof。

    python prepare/remote/remote_verify.py upload
    python prepare/remote/remote_verify.py build
    python prepare/remote/remote_verify.py run9
    python prepare/remote/remote_verify.py all
    python prepare/remote/remote_verify.py prof --case case8 --shape 85,33 --launches 8
    python prepare/remote/remote_verify.py shell --cmd "npu-smi info"

题目信息全部来自 config.json，换题目只改它。
服务器地址不预设，用 --host / --port / REMOTE_HOST 提供，没有就交互询问。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import remote_client  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
DEFAULT_CODE = REPO / "code"
DEFAULT_CONFIG = HERE / "config.json"
DEFAULT_ASSETS = HERE / "assets.tar.gz"
SCRIPTS = HERE / "scripts"
DEFAULT_ROOT = "/tmp/cannverify"

REMOTE_SCRIPTS = (
    "rename_gen.py",
    "build_gen.sh",
    "best9_gen.sh",
    "chk9.py",
    "run9.py",
    "t173_prof.sh",
    "t93g_pipes.py",
)


def load_config(args) -> dict:
    path = Path(args.config).resolve()
    if not path.is_file():
        raise SystemExit(f"缺少 {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def check_local(args, config: dict) -> None:
    code = Path(args.code).resolve()
    assets = Path(args.assets).resolve()
    if not assets.is_file():
        raise SystemExit(f"缺少 {assets}")
    missing = [relative for relative in config["files"].values() if not (code / relative).is_file()]
    if missing:
        raise SystemExit("code/ 缺少文件: " + ", ".join(missing))


def do_upload(conn: remote_client.Connection, args, config: dict) -> None:
    root = args.root.rstrip("/")
    code = Path(args.code).resolve()
    assets = Path(args.assets).resolve()

    conn.check(f"mkdir -p {root}/up {root}/scripts")
    for remote_name, relative in config["files"].items():
        conn.put(str(code / relative), f"{root}/up/{remote_name}")
    conn.put(str(Path(args.config).resolve()), f"{root}/config.json")
    conn.put(str(assets), f"{root}/assets.tar.gz")
    for name in REMOTE_SCRIPTS:
        conn.put(str(SCRIPTS / name), f"{root}/scripts/{name}")

    conn.check(f"rm -rf {root}/source {root}/runner {root}/inputs")
    conn.check(f"tar -xzf {root}/assets.tar.gz -C {root}")
    conn.check(f"ls -la {root} {root}/up", timeout=60)


def do_build(conn: remote_client.Connection, args) -> None:
    root = args.root.rstrip("/")
    conn.check(f"bash {root}/scripts/build_gen.sh {root} {root}/up", timeout=1800)


def do_run9(conn: remote_client.Connection, args) -> None:
    root = args.root.rstrip("/")
    conn.check(f"bash {root}/scripts/best9_gen.sh {root}", timeout=1800)


def do_prof(conn: remote_client.Connection, args) -> None:
    root = args.root.rstrip("/")
    if not args.case or not args.shape:
        raise SystemExit("prof 需要 --case 和 --shape，例如 --case case8 --shape 85,33")
    conn.check(f"bash {root}/scripts/t173_prof.sh {root} {args.case} {args.shape} {args.launches}", timeout=1800)


def parse_args():
    parser = argparse.ArgumentParser(description="910B 远端验证")
    parser.add_argument("action", choices=("upload", "build", "run9", "all", "prof", "shell", "put", "get"))
    parser.add_argument("--root", default=DEFAULT_ROOT, help=f"远端工作目录，默认 {DEFAULT_ROOT}")
    parser.add_argument("--code", default=str(DEFAULT_CODE), help="本地代码目录，默认 code/")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="题目配置")
    parser.add_argument("--assets", default=str(DEFAULT_ASSETS))
    parser.add_argument("--case", default="", help="prof 用，例如 case8")
    parser.add_argument("--shape", default="", help="prof 用，例如 85,33")
    parser.add_argument("--launches", type=int, default=8)
    parser.add_argument("--cmd", default="", help="shell 用")
    parser.add_argument("--local", default="", help="put/get 用")
    parser.add_argument("--remote", default="", help="put/get 用")
    parser.add_argument("--host", default="")
    parser.add_argument("--port", default="")
    parser.add_argument("--user", default="")
    parser.add_argument("--password", default="", help="不推荐；省略则交互输入")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "shell" and not args.cmd:
        print("shell 需要 --cmd", file=sys.stderr)
        return 1
    if args.action in ("put", "get") and not (args.local and args.remote):
        print(f"{args.action} 需要 --local 和 --remote", file=sys.stderr)
        return 1

    config = {}
    if args.action in ("upload", "all"):
        try:
            config = load_config(args)
            check_local(args, config)
        except SystemExit as exc:
            print(exc, file=sys.stderr)
            return 1

    try:
        conn = remote_client.connect_from_args(args)
    except remote_client.RemoteError as exc:
        print(f"连接失败: {exc}", file=sys.stderr)
        return 1

    try:
        if args.action == "upload":
            do_upload(conn, args, config)
        elif args.action == "build":
            do_build(conn, args)
        elif args.action == "run9":
            do_run9(conn, args)
        elif args.action == "all":
            do_upload(conn, args, config)
            do_build(conn, args)
            do_run9(conn, args)
        elif args.action == "prof":
            do_prof(conn, args)
        elif args.action == "shell":
            return conn.run(args.cmd)
        elif args.action == "put":
            conn.put(args.local, args.remote)
        elif args.action == "get":
            conn.get(args.remote, args.local)
        return 0
    except remote_client.RemoteError as exc:
        print(f"\n失败: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
