"""BYO executor: per-user remote SSH execution (never local for non-owner).

Design:
- owner: default local (existing tools/sandbox); may also configure SSH.
- member: only SSH to their own public server; no config => "normal permissions" (no execution).
- The AIOS host NEVER runs member commands locally, even if member enters 127.0.0.1.
- SSH transport only needs a public IP + SSH port; no domain / TLS / extra inbound ports.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import os
import re
import shlex
import socket
from pathlib import Path
from typing import Any

EXEC_ROOT = Path("storage/users")
MAX_OUTPUT = 200_000
MAX_REMOTE_FILE_BYTES = 12 * 1024 * 1024
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
}


def _user_dir(user_id: str, *, create: bool = False) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", user_id or "unknown")
    path = EXEC_ROOT / safe
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path(user_id: str, *, create: bool = False) -> Path:
    directory = _user_dir(user_id, create=create)
    return directory / "executor.json"


def _key_path(user_id: str, *, create: bool = False) -> Path:
    base = _user_dir(user_id, create=create) / "ssh"
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base / "id_ed25519"


def _known_hosts_path(user_id: str, *, create: bool = False) -> Path:
    base = _user_dir(user_id, create=create) / "ssh"
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base / "known_hosts"


def default_config(role: str) -> dict[str, Any]:
    base = {
        "ssh": {"host": "", "port": 22, "user": "aios", "image": "aios-runner:latest", "host_key": ""},
        "limits": {"timeout": DEFAULT_TIMEOUT, "memory": "512m", "cpus": "1"},
        "storage": {"mode": "local", "path": "~/aios-data"},
    }
    return {"mode": "local" if role == "owner" else "disabled", **base}


def load_config(user_id: str, role: str) -> dict[str, Any]:
    path = _config_path(user_id)
    cfg = default_config(role)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in ("mode", "ssh", "limits", "storage", "updated_at")})
    return cfg


def save_config(user_id: str, cfg: dict[str, Any]) -> None:
    path = _config_path(user_id, create=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    host_key = str((cfg.get("ssh") or {}).get("host_key") or "").strip()
    kh = _known_hosts_path(user_id, create=True)
    kh.write_text(host_key + ("\n" if host_key else ""), encoding="utf-8")
    try:
        os.chmod(kh, 0o600)
    except OSError:
        pass


def ensure_keypair(user_id: str) -> str:
    key = _key_path(user_id, create=True)
    if not key.exists():
        import subprocess

        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-C", f"aios-{user_id}", "-f", str(key)],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            os.chmod(key, 0o600)
        except OSError:
            pass
    return (key.with_suffix(".pub")).read_text(encoding="utf-8").strip()


def public_keys(user_id: str) -> dict[str, str]:
    ensure_keypair(user_id)
    return {"public_key": ( _key_path(user_id).with_suffix(".pub") ).read_text(encoding="utf-8").strip()}


def _is_public_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def validate_target(host: str, role: str, port: int = 22) -> str:
    """Validate the SSH target. Members may use public addresses only."""
    host = (host or "").strip()
    if not host:
        raise ValueError("请填写远程服务器地址")
    if len(host) > 253 or any(c in host for c in " /\\\t\r\n"):
        raise ValueError("服务器地址格式不正确")
    hostname = host.strip("[]").lower()
    if role != "owner" and hostname in BLOCKED_HOSTNAMES:
        raise ValueError("该地址不允许（本机/元数据地址）")
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = {str(literal)}
    else:
        try:
            infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
        except OSError as exc:
            raise ValueError(f"无法解析服务器地址: {exc}") from exc
        addresses = {item[4][0] for item in infos}
    if not addresses:
        raise ValueError("服务器地址未解析到 IP")
    if role != "owner" and any(not _is_public_ip(ip) for ip in addresses):
        raise ValueError("普通账号只能使用公网服务器地址")
    # Pin the validated address for the SSH process. Passing the hostname would trigger
    # another DNS lookup after validation and permit DNS rebinding to private networks.
    return sorted(addresses)[0] if role != "owner" and literal is None else hostname


def _ssh_args(user_id: str, cfg: dict[str, Any], role: str = "member") -> list[str]:
    ssh = cfg.get("ssh") or {}
    original_host = str(ssh.get("host") or "").strip().lower().strip("[]")
    host = validate_target(original_host, role, int(ssh.get("port") or 22))
    key = _key_path(user_id)
    if not key.exists():
        raise ValueError("SSH 密钥未生成，请先调用 /api/v1/executor/ssh-key")
    kh = _known_hosts_path(user_id)
    if not kh.exists() or not kh.read_text(encoding="utf-8").strip():
        raise ValueError("未配置服务器主机指纹（host_key），请先填写")
    return [
        "ssh",
        "-i", str(key),
        "-p", str(int(ssh.get("port") or 22)),
        "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=yes",
        "-o", f"UserKnownHostsFile={_known_hosts_path(user_id)}",
        *(["-o", f"HostKeyAlias={original_host}"] if original_host != host else []),
        "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=15",
        f"{ssh.get('user') or 'aios'}@{host}",
    ]


async def _ssh_exec(user_id: str, cfg: dict[str, Any], remote_cmd: str, timeout: int, role: str = "member") -> dict[str, Any]:
    args = _ssh_args(user_id, cfg, role) + [remote_cmd]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"ok": False, "exit_code": -1, "stdout": "", "stderr": f"执行超时（{timeout}s）"}
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode if proc.returncode is not None else -1,
        "stdout": stdout.decode("utf-8", "replace")[:MAX_OUTPUT],
        "stderr": stderr.decode("utf-8", "replace")[:MAX_OUTPUT],
    }


async def test_connection(user_id: str, role: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config(user_id, role)
    if (cfg.get("mode") or "disabled") != "ssh":
        return {"ok": False, "error": "未配置远程执行服务器", "mode": cfg.get("mode")}
    ssh = cfg.get("ssh") or {}
    validate_target(str(ssh.get("host") or ""), role, int(ssh.get("port") or 22))
    result = await _ssh_exec(
        user_id, cfg,
        "uname -s; docker --version 2>/dev/null || podman --version 2>/dev/null; echo AIOS_OK",
        timeout=min(int((cfg.get("limits") or {}).get("timeout") or DEFAULT_TIMEOUT), MAX_TIMEOUT),
        role=role,
    )
    result["mode"] = "ssh"
    return result


async def remote_storage_mode(user_id: str, role: str) -> tuple[str, str]:
    cfg = load_config(user_id, role)
    storage = cfg.get("storage") or {}
    mode = str(storage.get("mode") or "local")
    path = str(storage.get("path") or "~/aios-data")
    if role != "owner" and mode == "remote" and (cfg.get("mode") or "disabled") == "ssh":
        return "remote", path
    return "local", path


async def _ssh_binary(user_id: str, cfg: dict[str, Any], remote_cmd: str, payload: bytes | None, timeout: int, role: str = "member") -> tuple[int, bytes, bytes]:
    args = _ssh_args(user_id, cfg, role) + [remote_cmd]
    proc = await asyncio.create_subprocess_exec(
        *args, stdin=asyncio.subprocess.PIPE if payload is not None else asyncio.subprocess.DEVNULL,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(payload), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill(); await proc.wait()
        raise TimeoutError(f"SSH 文件传输超时（{timeout}s）")
    return int(proc.returncode or 0), stdout, stderr


async def remote_write_bytes(user_id: str, role: str, relative_path: str, content: bytes, timeout: int = 60) -> dict[str, Any]:
    mode, root = await remote_storage_mode(user_id, role)
    if mode != "remote":
        raise PermissionError("用户未启用远程存储")
    if len(content) > MAX_REMOTE_FILE_BYTES:
        raise ValueError(f"远程单文件上限为 {MAX_REMOTE_FILE_BYTES // (1024*1024)}MB")
    safe = "/".join(part for part in relative_path.split("/") if part not in ("", ".", ".."))
    if not safe:
        raise ValueError("远程存储路径为空")
    target = root.rstrip("/") + "/" + safe
    parent = target.rsplit("/", 1)[0] if "/" in safe else root
    command = f"mkdir -p {shlex.quote(parent)} && cat > {shlex.quote(target)}"
    code, stdout, stderr = await _ssh_binary(user_id, load_config(user_id, role), command, content, timeout, role=role)
    return {"ok": code == 0, "exit_code": code, "stdout": stdout.decode("utf-8", "replace")[:MAX_OUTPUT], "stderr": stderr.decode("utf-8", "replace")[:MAX_OUTPUT]}


async def remote_read_bytes(user_id: str, role: str, relative_path: str, timeout: int = 60) -> bytes:
    mode, root = await remote_storage_mode(user_id, role)
    if mode != "remote":
        raise PermissionError("用户未启用远程存储")
    safe = "/".join(part for part in relative_path.split("/") if part not in ("", ".", ".."))
    if not safe:
        raise ValueError("远程存储路径为空")
    target = root.rstrip("/") + "/" + safe
    code, stdout, stderr = await _ssh_binary(user_id, load_config(user_id, role), f"cat -- {shlex.quote(target)}", None, timeout, role=role)
    if code != 0:
        raise FileNotFoundError(stderr.decode("utf-8", "replace")[:MAX_OUTPUT] or "远程文件不存在")
    if len(stdout) > MAX_REMOTE_FILE_BYTES:
        raise ValueError(f"远程文件超过读取上限 {MAX_REMOTE_FILE_BYTES // (1024*1024)}MB")
    return stdout


async def run_remote(user_id: str, role: str, command: str, timeout: int | None = None) -> dict[str, Any]:
    cfg = load_config(user_id, role)
    if (cfg.get("mode") or "disabled") != "ssh":
        raise PermissionError("当前账号未配置远程执行器，无代码执行权限")
    ssh = cfg.get("ssh") or {}
    validate_target(str(ssh.get("host") or ""), role, int(ssh.get("port") or 22))
    limits = cfg.get("limits") or {}
    ttl = max(1, min(int(timeout or limits.get("timeout") or DEFAULT_TIMEOUT), MAX_TIMEOUT))
    image = str(ssh.get("image") or "aios-runner:latest")
    memory = str(limits.get("memory") or "512m")
    cpus = str(limits.get("cpus") or "1")
    docker_cmd = (
        f"timeout {ttl} docker run --rm --network none "
        f"--memory {shlex.quote(memory)} --cpus {shlex.quote(cpus)} "
        f"--pids-limit 256 --read-only "
        f"--tmpfs /tmp:rw,size=64m,nosuid,nodev "
        f"--tmpfs /workspace:rw,size=512m,nosuid,nodev,uid=10001,gid=10001 "
        f"--workdir /workspace "
        f"{shlex.quote(image)} sh -lc {shlex.quote(command)}"
    )
    result = await _ssh_exec(user_id, cfg, docker_cmd, timeout=ttl + 10, role=role)
    result["mode"] = "ssh"
    return result
