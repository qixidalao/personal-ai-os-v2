"""Execution boundary data models."""
# 中文：执行边界数据模型。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field


class ExecRequest(BaseModel):
    """A single sandboxed execution request."""
    # 中文：单个沙箱执行请求。

    tool: str
    argv: list[str] = Field(default_factory=list)
    python_code: str | None = None
    shell_command: str | None = None
    cwd: str | None = None
    timeout_s: int = 30
    max_output_bytes: int = 64 * 1024
    network: bool = False
    run_id: str | None = None
    tool_call_id: str | None = None
    stdin: str | None = None


class ExecResult(BaseModel):
    status: str = "failed"  # succeeded | failed | timeout | denied  ｜ succeeded | failed | timeout | denied
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    truncated: bool = False
    duration_ms: int = 0
    sandbox: str = "none"
    error: str | None = None


@dataclass
class ExecutionPolicy:
    """Policy resolved from settings.json `execution` section."""
    # 中文：从 settings.json 的 `execution` 部分解析策略。

    enabled: bool = True
    allowed_roots: list[str] = field(default_factory=list)
    allow_shell: bool = True
    allow_python: bool = True
    allow_network: bool = False
    default_timeout: int = 30
    max_timeout: int = 300
    max_output_bytes: int = 64 * 1024
    max_concurrent: int = 2
    sandbox: str = "auto"  # auto | bwrap | none  ｜ auto | bwrap | none

    def clamp_timeout(self, value: int | None) -> int:
        try:
            value = int(value) if value is not None else self.default_timeout
        except (TypeError, ValueError):
            value = self.default_timeout
        return max(1, min(value, self.max_timeout))

    def clamp_output(self, value: int | None) -> int:
        try:
            value = int(value) if value is not None else self.max_output_bytes
        except (TypeError, ValueError):
            value = self.max_output_bytes
        return max(1024, min(value, 2 * 1024 * 1024))


def result_to_dict(result: ExecResult) -> dict[str, Any]:
    return result.model_dump()
