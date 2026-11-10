"""远端 SSH/SFTP 连接。

密码每次运行时向使用者询问，不写入任何文件、不进入命令行历史。
host / port / user 可以用参数或环境变量提供，缺省时交互询问。

    from remote_client import connect_from_args
    conn = connect_from_args(args)
"""

from __future__ import annotations

import getpass
import os
import sys
import time

try:
    import paramiko
except ImportError:  # pragma: no cover - 只在缺依赖时触发
    paramiko = None

DEFAULT_HOST = ""
DEFAULT_PORT = "22"
DEFAULT_USER = "root"


class RemoteError(RuntimeError):
    pass


class Connection:
    def __init__(self, host: str, port: int, user: str, password: str):
        self.host = host
        self.port = port
        self.user = user
        self._password = password
        self._client = None

    # ---------------------------------------------------------------- 生命周期

    def open(self) -> "Connection":
        if paramiko is None:
            raise RemoteError("缺少 paramiko，先执行: pip install paramiko")
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f"连接 {self.user}@{self.host}:{self.port} ...", flush=True)
        try:
            client.connect(
                self.host,
                port=self.port,
                username=self.user,
                password=self._password,
                timeout=30,
                banner_timeout=60,
                auth_timeout=60,
                allow_agent=False,
                look_for_keys=False,
            )
        except Exception as exc:  # paramiko 的异常类型较多，统一转成可读信息
            raise RemoteError(f"SSH 连接失败: {exc}") from exc
        client.get_transport().set_keepalive(20)
        self._client = client
        print("已连接", flush=True)
        return self

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "Connection":
        return self.open()

    def __exit__(self, *_exc) -> None:
        self.close()

    # ---------------------------------------------------------------- 命令

    def run(self, cmd: str, timeout: int = 900, quiet: bool = False) -> int:
        if self._client is None:
            raise RemoteError("连接还没打开")
        if not quiet:
            print(f"[remote] $ {cmd}", flush=True)
        stdin, stdout, stderr = self._client.exec_command(cmd, timeout=timeout, get_pty=True)
        channel = stdout.channel
        while True:
            if channel.recv_ready():
                chunk = channel.recv(8192)
                if chunk and not quiet:
                    sys.stdout.write(chunk.decode("utf-8", "replace"))
                    sys.stdout.flush()
            elif channel.exit_status_ready():
                # 退出前把剩余缓冲读完
                while channel.recv_ready():
                    chunk = channel.recv(8192)
                    if chunk and not quiet:
                        sys.stdout.write(chunk.decode("utf-8", "replace"))
                        sys.stdout.flush()
                break
            else:
                time.sleep(0.1)
        code = channel.recv_exit_status()
        if not quiet:
            print(f"[remote] exit={code}", flush=True)
        return code

    def check(self, cmd: str, timeout: int = 900) -> None:
        code = self.run(cmd, timeout)
        if code != 0:
            raise RemoteError(f"远端命令失败（exit={code}）: {cmd}")

    # ---------------------------------------------------------------- 传输

    def put(self, local: str, remote: str) -> None:
        if self._client is None:
            raise RemoteError("连接还没打开")
        print(f"[put] {local} -> {remote}", flush=True)
        with self._client.open_sftp() as sftp:
            sftp.put(local, remote)

    def get(self, remote: str, local: str) -> None:
        if self._client is None:
            raise RemoteError("连接还没打开")
        print(f"[get] {remote} -> {local}", flush=True)
        with self._client.open_sftp() as sftp:
            sftp.get(remote, local, max_concurrent_prefetch_requests=8)

    def exists(self, remote: str) -> bool:
        if self._client is None:
            raise RemoteError("连接还没打开")
        try:
            with self._client.open_sftp() as sftp:
                sftp.stat(remote)
            return True
        except OSError:
            return False


def ask_connection(args) -> Connection:
    """地址不预设：参数 > 环境变量 > 交互询问。密码每次询问，不落盘。"""
    host = getattr(args, "host", "") or os.environ.get("REMOTE_HOST") or input("远端 host> ").strip()
    if not host:
        raise RemoteError("没有 host")

    port_text = str(getattr(args, "port", "") or os.environ.get("REMOTE_PORT") or "")
    if not port_text:
        port_text = input(f"远端 port [{DEFAULT_PORT}]> ").strip() or DEFAULT_PORT
    try:
        port = int(port_text)
    except ValueError as exc:
        raise RemoteError(f"端口不是数字: {port_text}") from exc

    user = (
        getattr(args, "user", "")
        or os.environ.get("REMOTE_USER")
        or input(f"远端 user [{DEFAULT_USER}]> ").strip()
        or DEFAULT_USER
    )

    password = getattr(args, "password", "") or os.environ.get("REMOTE_PASSWORD")
    if not password:
        password = getpass.getpass(f"{user}@{host}:{port} 密码（本次使用，不保存）: ")
    if not password:
        raise RemoteError("没有密码")

    return Connection(host, port, user, password)


def connect_from_args(args) -> Connection:
    return ask_connection(args).open()
