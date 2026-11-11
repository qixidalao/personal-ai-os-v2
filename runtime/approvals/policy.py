"""Three-tier permission policy with deny patterns + session grants (P2)."""
# 中文：三级权限策略，包含拒绝模式和会话授权（P2）。
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_FILE = PROJECT_ROOT / "storage" / "settings.json"

DEFAULT_CONFIRM_TOOLS = ["shell_exec", "python_exec", "write_file", "delete_file"]
HIGH_RISK_TOOLS = {"shell_exec", "python_exec"}
DEFAULT_DENY_PATTERNS = [
    r"rm\s+-rf\s+/(?:\s|$)",
    r"rm\s+-rf\s+~(?:\s|$)",
    r":\s*\(\s*\)\s*\{",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r"\bchmod\s+-R\s+777\s+/",
    r">\s*/dev/sd",
]
PATTERN_TOOLS = {"shell_exec", "python_exec"}


@dataclass
class ApprovalDecision:
    kind: str  # allow | confirm | deny  ｜ allow | confirm | deny
    risk: str  # low | medium | high  ｜ low | medium | high
    reason: str = ""

    def to_dict(self) -> dict:
        return {"kind": self.kind, "risk": self.risk, "reason": self.reason}


def _load_settings() -> dict:
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _exec_cfg(settings: dict | None) -> dict:
    settings = settings if settings is not None else _load_settings()
    cfg = settings.get("execution") if isinstance(settings, dict) else None
    return cfg if isinstance(cfg, dict) else {}


def classify_risk(tool: str) -> str:
    if tool in HIGH_RISK_TOOLS:
        return "high"
    if tool in ("write_file", "delete_file"):
        return "medium"
    return "low"


def matched_deny_pattern(tool: str, args: dict | None, settings: dict | None = None) -> str | None:
    """Return the matched deny pattern for shell/python inputs, else None."""
    # 中文：返回 shell/python 输入匹配的拒绝模式，否则返回 None。
    if tool not in PATTERN_TOOLS:
        return None
    cfg = _exec_cfg(settings)
    patterns = cfg.get("denyPatterns")
    patterns = [str(p) for p in patterns] if isinstance(patterns, list) else DEFAULT_DENY_PATTERNS
    text = ""
    if isinstance(args, dict):
        text = str(args.get("command") or args.get("code") or "")
    if not text:
        return None
    for pattern in patterns:
        try:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return pattern
        except re.error:
            continue
    return None


def decide(tool: str, args: dict | None = None, settings: dict | None = None,
           session_id: str | None = None) -> ApprovalDecision:
    cfg = _exec_cfg(settings)
    mode = str(cfg.get("approvalMode", "confirm") or "confirm").lower()
    confirm_tools = cfg.get("confirmTools")
    confirm_tools = [str(x) for x in confirm_tools] if isinstance(confirm_tools, list) else DEFAULT_CONFIRM_TOOLS
    deny_tools = cfg.get("denyTools")
    deny_tools = {str(x) for x in deny_tools} if isinstance(deny_tools, list) else set()

    risk = classify_risk(tool)
    if tool in deny_tools:
        return ApprovalDecision("deny", risk, f"工具 {tool} 在 execution.denyTools 中")

    pattern = matched_deny_pattern(tool, args, settings)
    if pattern:
        return ApprovalDecision("deny", risk, f"参数命中高风险规则：{pattern}")

    if session_id and mode != "auto":
        try:
            from runtime.approvals.store import get_approval_store
            if get_approval_store().has_grant(session_id, tool):
                return ApprovalDecision("allow", risk, "本会话已授权该工具")
        except Exception:
            pass

    if mode == "auto":
        return ApprovalDecision("allow", risk)
    if tool in confirm_tools:
        return ApprovalDecision("confirm", risk)
    return ApprovalDecision("allow", risk)


def approval_timeout(settings: dict | None = None) -> int:
    cfg = _exec_cfg(settings)
    try:
        return max(5, int(cfg.get("approvalTimeoutSeconds", 120)))
    except (TypeError, ValueError):
        return 120
