"""AIOS media delivery API.

Images are copied into managed storage and transferred out-of-band. LLM/SSE messages only
carry a tiny JSON descriptor; raw bytes are fetched once through this HTTP endpoint.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from fastapi import UploadFile, File
import base64
import uuid
import io

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

@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image and return a data URL for vision models."""
    content = await file.read()
    b64 = base64.b64encode(content).decode()
    mime = file.content_type or "image/jpeg"
    data_url = f"data:{mime};base64,{b64}"
    media_id = str(uuid.uuid4())[:12]
    return {
        "media_id": media_id,
        "url": data_url,
        "type": mime,
        "size": len(content),
    }

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and extract text content."""
    content_bytes = await file.read()
    text = ""
    filename = file.filename or "unknown"
    suffix = filename.split(".")[-1].lower() if "." in filename else ""
    
    try:
        if suffix == "pdf":
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(io.BytesIO(content_bytes))
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            except ImportError:
                text = "[PDF 解析需要 PyPDF2: pip install PyPDF2]"
        elif suffix in ["txt", "md", "py", "js", "ts", "vue", "json", "yaml", "yml", "csv", "html", "css", "sh", "bash"]:
            text = content_bytes.decode("utf-8", errors="replace")
        else:
            text = content_bytes.decode("utf-8", errors="replace")[:5000]
    except Exception as e:
        text = f"[文件读取失败: {e}]"
    
    return {
        "filename": filename,
        "type": suffix,
        "text": text[:10000],
        "size": len(content_bytes),
        "truncated": len(text) > 10000,
    }
