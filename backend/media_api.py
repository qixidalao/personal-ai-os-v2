"""AIOS media delivery API.

Images are copied into managed storage and transferred out-of-band. LLM/SSE messages only
carry a tiny JSON descriptor; raw bytes are fetched once through this HTTP endpoint.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from tools.media import MEDIA_DIR, get_media_record

router = APIRouter(prefix="/api/v1/media", tags=["media"])


@router.get("/{media_id}", name="get_media")
async def get_media(media_id: str):
    record = get_media_record(media_id)
    if not record:
        raise HTTPException(status_code=404, detail="图片不存在")
    path = Path(record["path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件已丢失")
    media_type = record.get("mime") or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        path,
        media_type=media_type,
        filename=record.get("name") or path.name,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("")
async def media_status():
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    return {"ok": True, "transport": "url", "directory": str(MEDIA_DIR.resolve())}
