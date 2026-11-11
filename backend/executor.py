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
DEFAULT_TIMEOUT = 60
MAX_TIMEOUT = 300
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",
    "metadata",
    "instance-data",
    "169.254.169.254",
}


def _user_dir(user_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", user_id or "unknown")
    path = EXEC_ROOT / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def _config_path(user_id: str) -> Path:
    return _user_dir(user_id) / "executor.json"


def _key_path(user_id: str) -> Path:
    return _user_dir(user_id) / "ssh" / "id_ed25519"


def _known_hosts_path(user_id: str) -> Path:
    return _user_dir(user_id) / "ssh" / "known_hosts"


def default_config(role: str) -> dict[str, Any]:
    if role == "owner":
        return {
            "mode": "local",
            "ssh": {"host": "", "port": 22, "user": "aios", "image": "aios-runner:latest", "host_key": ""},
            "limits": {"timeout": DEFAULT_TIMEOUT, "memory": "512m", "cpus": "1"},
        }
    return {
        "mode": "disabled",
        "ssh": {"host": "", "port": 22, "user": "aios", "image": "aios-runner:latest", "host_key": ""},
        "limits": {"timeout": DEFAULT_TIMEOUT, "memory": "512m", "cpus": "1"},
    }


def load_config(user_id: str, role: str) -> dict[str, Any]:
    path = _config_path(user_id)
    cfg = default_config(role)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if isinstance(data, dict):
            cfg.update({k: v for k, v in data.items() if k in ("mode", "ssh", "limits", "updated_at")})
    return cfg


def save_config(user_id: str, cfg: dict[str, Any]) -> None:
    path = _config_path(user_id)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    host_key = str((cfg.get("ssh") or {}).get("host_key") or "").strip()
    kh = _known_hosts_path(user_id)
    kh.parent.mkdir(parents=True, exist_ok=True)
    kh.write_text(host_key + ("\n" if host_key else ""), encoding="utf-8")
    try:
        os.chmod(kh, 0o600)
    except OSError:
        pass


def ensure_keypair(user_id: str) -> str:
    key = _key_path(user_id)
    key.parent.mkdir(parents=True, exist_ok=True)
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
    """校验远程目标；member 必须是公网地址；owner 允许本机/内网。"""
    host = (host or "").strip()
    if not host:
        raise ValueError("请填写远程服务器地址")
    if len(host) > 253 or any(c in host for c in " /\\\t\r\n"):
        raise ValueError("服务器地址格式不正确")
    hostname = host.strip("[]").lower()
    if role != "owner":
        if hostname in BLOCKED_HOSTNAMES:
            raise ValueError("该地址不允许（本机/元数据地址）")
        try:
            literal = ipaddress.ip_address(hostname)
        except ValueError:
            literal = None
        if literal is not None and not _is_public_ip(str(literal)):
            raise ValueError("普通账号只能使用公网服务器地址")
    try:
        infos = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise ValueError(f"无法解析服务器地址: {exc}") from exc
    addresses = {item[4][0] for item in infos}
    if role != "owner":
        for ip in addresses:
            if not _is_public_ip(ip):
                raise ValueError("普通账号只能使用公网服务器地址")
    return hostname


def _ssh_args(user_id: str, cfg: dict[str, Any]) -> list[str]:
    ssh = cfg.get("ssh") or {}
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
        "-o", "ConnectTimeout=8",
        "-o", "ServerAliveInterval=15",
        f"{ssh.get('user') or 'aios'}@{ssh.get('host')}",
    ]


async def _ssh_exec(user_id: str, cfg: dict[str, Any], remote_cmd: str, timeout: int) -> dict[str, Any]:
    args = _ssh_args(user_id, cfg) + [remote_cmd]
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
    )
    result["mode"] = "ssh"
    return result


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
        f"--tmpfs /workspace:rw,size=512m,nosuid,nodev "
        f"--workdir /workspace "
        f"{shlex.quote(image)} sh -lc {shlex.quote(command)}"
    )
    result = await _ssh_exec(user_id, cfg, docker_cmd, timeout=ttl + 10)
    result["mode"] = "ssh"
    return result
