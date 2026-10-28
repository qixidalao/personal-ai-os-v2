"""Structured image delivery tool for Web and OneBot/QQNT."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import shutil
from pathlib import Path
from typing import Any

from tools import ToolRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MEDIA_DIR = PROJECT_ROOT / "storage" / "media"
INDEX_FILE = MEDIA_DIR / "index.json"
MAX_IMAGE_BYTES = 20 * 1024 * 1024
ALLOWED_MIME = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"}


def _read_index() -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_index(index: dict[str, dict[str, Any]]) -> None:
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    temp = INDEX_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(INDEX_FILE)


def get_media_record(media_id: str) -> dict[str, Any] | None:
    if not media_id or any(ch not in "0123456789abcdef" for ch in media_id.lower()):
        return None
    value = _read_index().get(media_id)
    return value if isinstance(value, dict) else None


def is_media_descriptor(value: Any) -> bool:
    return isinstance(value, dict) and value.get("kind") == "aios.image" and bool(value.get("media_id"))


@ToolRegistry.register(
    "send_image",
    "把已生成或已有的本地图片真正发送到当前对话。必须传图片文件路径；禁止读取或输出 base64。",
    "media",
)
def send_image(path: str, caption: str = "") -> dict[str, Any]:
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
    target = MEDIA_DIR / f"{digest}{suffix}"
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copyfile(source, target)

    record = {
        "kind": "aios.image",
        "media_id": digest,
        "name": source.name,
        "mime": mime,
        "size": size,
        "path": str(target.resolve()),
        "url": f"/api/v1/media/{digest}",
        "caption": str(caption or "").strip()[:500],
    }
    index = _read_index()
    index[digest] = record
    _write_index(index)
    # Small structured result only. Image bytes never enter the LLM context or SSE text stream.
    return record
