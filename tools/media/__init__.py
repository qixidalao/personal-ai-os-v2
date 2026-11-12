"""Structured image delivery tool for Web clients."""
# 中文：面向 Web 客户端的结构化图像传输工具。
from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from tools import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_ROOT = PROJECT_ROOT / "storage" / "media"
MEDIA_DIR = MEDIA_ROOT  # legacy/owner media root
INDEX_FILE = MEDIA_DIR / "index.json"
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _scope_paths(user_id: str = "") -> tuple[Path, Path]:
    if not user_id or user_id == "user_owner":
        return MEDIA_ROOT, INDEX_FILE
    safe_id = "".join(c for c in user_id if c.isalnum() or c in "_.-")
    directory = PROJECT_ROOT / "storage" / "users" / safe_id / "media"
    return directory, directory / "index.json"
ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}


def _read_index(index_file: Path | None = None) -> dict[str, dict[str, Any]]:
    target = index_file or INDEX_FILE
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_index(index: dict[str, dict[str, Any]], index_file: Path | None = None) -> None:
    target = index_file or INDEX_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(".tmp")
    temp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(target)


def get_media_record(media_id: str, user_id: str = "", role: str = "member") -> dict[str, Any] | None:
    if not media_id or any(ch not in "0123456789abcdef" for ch in media_id.lower()):
        return None
    if role == "owner":
        value = _read_index().get(media_id)
        if isinstance(value, dict): return value
    directory, index_file = _scope_paths(user_id)
    value = _read_index(index_file).get(media_id)
    return value if isinstance(value, dict) else None


async def save_user_media(user_id: str, role: str, filename: str, mime: str, content: bytes) -> dict[str, Any]:
    """Save media per selected account storage policy, then persist its owner index."""
    from backend.executor import remote_storage_mode, remote_write_bytes
    mode, _ = await remote_storage_mode(user_id, role)
    digest = hashlib.sha256(content).hexdigest()[:24]
    suffix = mimetypes.guess_extension(mime) or Path(filename).suffix or ".bin"
    safe_name = Path(filename or "upload").name[:120]
    directory, index_file = _scope_paths(user_id)
    if mode == "remote":
        relative = f"media/{digest}{suffix}"
        result = await remote_write_bytes(user_id, role, relative, content)
        if not result.get("ok"):
            raise RuntimeError(result.get("stderr") or "远程媒体保存失败")
        record = {"kind":"aios.image", "media_id":digest, "name":safe_name, "mime":mime,
                  "size":len(content), "owner_user_id":user_id, "storage":"remote",
                  "remote_path":relative, "url":f"/api/v1/media/{digest}"}
    else:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{digest}{suffix}"
        if not target.exists(): target.write_bytes(content)
        record = {"kind":"aios.image", "media_id":digest, "name":safe_name, "mime":mime,
                  "size":len(content), "owner_user_id":user_id, "storage":"local",
                  "path":str(target.resolve()), "url":f"/api/v1/media/{digest}"}
    index = _read_index(index_file)
    index[digest] = record
    _write_index(index, index_file)
    return record


async def read_user_media(user_id: str, role: str, record: dict[str, Any]) -> bytes:
    if record.get("storage") == "remote":
        from backend.executor import remote_read_bytes
        return await remote_read_bytes(user_id, role, str(record.get("remote_path") or ""))
    path = Path(str(record.get("path") or ""))
    if not path.is_file():
        raise FileNotFoundError("媒体文件不存在")
    return path.read_bytes()


def is_media_descriptor(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == "aios.image" and bool(value.get("media_id"))


@ToolRegistry.register(
    "send_image",
    "把已生成或已有的本地图片真正发送到当前对话。必须传图片文件路径；禁止读取或输出 base64。",
    "media",
    # 中文：媒体
)
def send_image(path: str, caption: str = "", user_id: str = "user_owner") -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"图片不存在: {source}")
    size = source.stat().st_size
    if size <= 0 or size > MAX_IMAGE_BYTES:
        raise ValueError(f"图片大小必须在 1B 到 {MAX_IMAGE_BYTES // 1024 // 1024}MB 之间")
    mime = mimetypes.guess_type(source.name)[0] or ""
    if mime not in ALLOWED_MIME:
        raise ValueError(f"不支持的图片格式: {mime or source.suffix or 'unknown'}")

    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:24]
    suffix = mimetypes.guess_extension(mime) or source.suffix.lower()
    directory, index_file = _scope_paths(user_id)
    target = directory / f"{digest}{suffix}"
    directory.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)

    record = {
        "kind": "aios.image",
        "media_id": digest,
        "name": source.name,
        "mime": mime,
        "size": size,
        "path": str(target.resolve()),
        "owner_user_id": user_id,
        "url": f"/api/v1/media/{digest}",
        "caption": str(caption or "").strip()[:500],
    }
    index = _read_index(index_file)
    index[digest] = record
    _write_index(index, index_file)
    # Small structured result only. Image bytes never enter the LLM context or SSE text stream.  ｜ 仅返回少量结构化结果。图像字节不会进入 LLM 上下文或 SSE 文本流。
    return record
