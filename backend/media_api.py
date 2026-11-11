"""AIOS media delivery API.

Images are copied into managed storage and transferred out-of-band. LLM/SSE messages only
carry a tiny JSON descriptor; raw bytes are fetched once through this HTTP endpoint.
"""
# 中文：AIOS 媒体交付 API。 图像会复制到托管存储，并通过带外方式传输。LLM/SSE 消息仅携带微型 JSON 描述符；原始字节通过此 HTTP 端点获取一次。
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from fastapi import UploadFile, File
import base64
import tempfile
import uuid
import io

from tools.media import MEDIA_DIR, MAX_IMAGE_BYTES, get_media_record, send_image

router = APIRouter(prefix="/api/v1/media", tags=["media"])
                                                 # 中文：媒体


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

SUPPORTED_IMAGE_MIME = {
    "image/png": ".png", "image/jpeg": ".jpg", "image/jpg": ".jpg",
    "image/gif": ".gif", "image/webp": ".webp", "image/bmp": ".bmp",
}


def _normalize_image(content: bytes, mime: str) -> tuple[bytes, str]:
    """把浏览器/手机上传的图片统一成受支持的格式（HEIC 等借 Pillow 转 PNG）。"""
    if mime in SUPPORTED_IMAGE_MIME:
        return content, mime
    try:
        from PIL import Image  # type: ignore
        with Image.open(io.BytesIO(content)) as im:
            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"不支持的图片格式: {mime or 'unknown'} ({exc})")


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Chat 图片上传：落盘存储 + 返回可展示的 media URL 与给视觉模型的 data URL。

    之前只返回 data URL(base64)：用户发的图无法回显，且几 MB base64 会直接写进会话历史。
    现在图片统一进 storage/media（经 send_image 索引），历史里只存 /api/v1/media/<id>，
    只有真正请求模型时才转回 data URL。
    """
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="空文件")
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="图片超过 20MB 限制")
    mime = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/jpeg").lower()
    if not mime.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持上传图片")

    content, mime = _normalize_image(content, mime)

    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(prefix="chat-upload-", suffix=SUPPORTED_IMAGE_MIME.get(mime, ".png"),
                                         dir=MEDIA_DIR, delete=False) as tmp:
            tmp.write(content)
            temp_name = tmp.name
        record = send_image(temp_name, caption="")
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass

    return {
        "media_id": record.get("media_id", ""),
        "url": record.get("url", ""),
        "data_url": f"data:{mime};base64,{base64.b64encode(content).decode()}",
        "type": mime,
        "size": len(content),
        "name": record.get("name") or file.filename or "",
    }


@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file and extract text content."""
    # 中文：上传文件并提取文本内容。
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
