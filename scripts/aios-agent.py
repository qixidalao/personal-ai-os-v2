"""AIOS outbound local-device agent (Windows/macOS/Linux).

Run `python aios_agent.py pair --server URL --code 123456`, then `python aios_agent.py run`.
The agent initiates HTTPS polling; AIOS never connects to the device's localhost/LAN address.
Jobs require local interactive approval unless --auto-approve is explicitly set.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import subprocess
import sys
import threading
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path.home() / ".config" / "aios-agent" / "device.json"
MAX_OUTPUT = 200_000


def _request(url: str, token: str = "", body: dict | None = None, timeout: int = 25):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read()
            ctype = response.headers.get("Content-Type", "")
            if "json" in ctype:
                return json.loads(raw or b"{}")
            return raw
    except urllib.error.HTTPError as exc:
        msg = exc.read(2048).decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code}: {msg}") from exc


def pair(server: str, code: str, name: str = "此设备") -> dict:
    base = server.rstrip("/")
    if not base.startswith("https://") and not base.startswith("http://127.0.0.1") and not base.startswith("http://localhost"):
        raise ValueError("远程 AIOS 地址必须使用 HTTPS；本机测试可用 http://127.0.0.1")
    result = _request(base + "/api/v1/devices/pair", body={
        "pairing_code": code,
        "name": name,
        "platform": f"{platform.system()} {platform.release()}",
    })
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"server": base, **result}, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG, 0o600)
    except OSError:
        pass
    return result


def _run_bounded(argv: list[str], timeout: int, cwd: str) -> dict:
    proc = subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd,
        creationflags=(subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0),
        start_new_session=(os.name != "nt"),
    )
    outputs = {"stdout": bytearray(), "stderr": bytearray()}

    def drain(stream, key):
        while True:
            chunk = stream.read(8192)
            if not chunk:
                break
            outputs[key].extend(chunk)
            excess = len(outputs[key]) - MAX_OUTPUT
            if excess > 0:
                del outputs[key][:excess]

    readers = [threading.Thread(target=drain, args=(proc.stdout, "stdout"), daemon=True),
               threading.Thread(target=drain, args=(proc.stderr, "stderr"), daemon=True)]
    for reader in readers: reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True, timeout=5)
        else:
            import signal
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
        proc.wait()
        for reader in readers: reader.join(timeout=2)
        return {"exit_code":124,"stdout":outputs["stdout"].decode("utf-8","replace"),"stderr":"任务超时"}
    for reader in readers: reader.join(timeout=2)
    return {"exit_code":int(code),"stdout":outputs["stdout"].decode("utf-8","replace"),"stderr":outputs["stderr"].decode("utf-8","replace")}


def _execute(job: dict, auto_approve: bool = False) -> dict:
    kind = job.get("kind")
    command = str(job.get("command") or "")
    timeout = min(max(int(job.get("timeout") or 60), 1), 300)
    if not command:
        return {"exit_code": 2, "stdout": "", "stderr": "empty command"}
    if not auto_approve:
        answer = input(f"AIOS 请求在本机执行 {kind} 任务（最长 {timeout}s）。批准？[y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            return {"exit_code": 126, "stdout": "", "stderr": "用户拒绝本机任务"}
    if kind == "python":
        fd, path = tempfile.mkstemp(prefix="aios-agent-", suffix=".py")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(command)
            result = _run_bounded([sys.executable, path], timeout, str(Path.home()))
        finally:
            Path(path).unlink(missing_ok=True)
    elif kind == "shell":
        argv = (["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command]
                if os.name == "nt" else ["/bin/sh", "-lc", command])
        result = _run_bounded(argv, timeout, str(Path.home()))
    else:
        return {"exit_code": 2, "stdout": "", "stderr": f"unsupported task kind: {kind}"}
    return result


def run(auto_approve: bool = False, poll_wait: int = 20):
    if not CONFIG.exists():
        raise RuntimeError("设备未配对。先运行：python aios_agent.py pair --server https://AIOS地址 --code 配对码")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    server, token = cfg["server"].rstrip("/"), cfg["device_token"]
    print(f"已连接 AIOS：{cfg.get('name','此设备')}。按 Ctrl+C 退出。")
    while True:
        job_data = _request(f"{server}/api/v1/devices/agent/jobs/next?wait={poll_wait}", token=token, timeout=poll_wait + 10)
        job = job_data.get("job")
        if not job:
            continue
        job_id = job["job_id"]
        try:
            expires_at = float(job.get("expires_at") or 0)
            if expires_at and time.time() >= expires_at:
                result = {"exit_code": 124, "stdout": "", "stderr": "任务已过期，未在本机执行"}
            else:
                result = _execute(job, auto_approve=auto_approve)
        except subprocess.TimeoutExpired as exc:
            result = {"exit_code": 124, "stdout": str(exc.stdout or "")[-MAX_OUTPUT:], "stderr": "任务超时"}
        except Exception as exc:
            result = {"exit_code": 1, "stdout": "", "stderr": str(exc)[:MAX_OUTPUT]}
        _request(f"{server}/api/v1/devices/agent/jobs/{job_id}/result", token=token, body=result)


def main():
    parser = argparse.ArgumentParser(description="AIOS local device executor agent")
    sub = parser.add_subparsers(dest="command", required=True)
    pair_cmd = sub.add_parser("pair", help="pair this device with an AIOS account")
    pair_cmd.add_argument("--server", required=True)
    pair_cmd.add_argument("--code", required=True)
    pair_cmd.add_argument("--name", default=platform.node() or "此设备")
    run_cmd = sub.add_parser("run", help="connect and receive jobs")
    run_cmd.add_argument("--auto-approve", action="store_true", help="skip per-job local confirmation; use only on a trusted device")
    run_cmd.add_argument("--poll-wait", type=int, default=20)
    args = parser.parse_args()
    if args.command == "pair":
        result = pair(args.server, args.code, args.name)
        print(f"已配对设备：{result['device_id']}。设备令牌仅保存在本机配置中。")
    else:
        run(args.auto_approve, args.poll_wait)


if __name__ == "__main__":
    main()
