"""AIOS media delivery API.

Images are copied into managed storage and transferred out-of-band. LLM/SSE messages only
carry a tiny JSON descriptor; raw bytes are fetched once through this HTTP endpoint.
"""
# 中文：AIOS 媒体交付 API。 图像会复制到托管存储，并通过带外方式传输。LLM/SSE 消息仅携带微型 JSON 描述符；原始字节通过此 HTTP 端点获取一次。
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response
from fastapi import UploadFile, File
import base64
import tempfile
import uuid
import io

from tools.media import MEDIA_DIR, MAX_IMAGE_BYTES, get_media_record, send_image, save_user_media, read_user_media
from backend.ownership import identity

router = APIRouter(prefix="/api/v1/media", tags=["media"])
                                                 # 中文：媒体


@router.get("/{media_id}", name="get_media")
async def get_media(media_id: str, request: Request):
    user_id, role = identity(request)
    record = get_media_record(media_id, user_id=user_id, role=role)
    if not record:
        raise HTTPException(status_code=404, detail="媒体不存在")
    try:
        content = await read_user_media(user_id, role, record)
    except Exception:
        raise HTTPException(status_code=404, detail="媒体文件不存在或远程存储不可用")
    media_type = record.get("mime") or mimetypes.guess_type(record.get("name") or "")[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type, headers={"Cache-Control":"private, no-store"})

@router.get("")
async def media_status():
    return {"ok": True, "transport": "configured-storage"}

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
async def upload_image(request: Request, file: UploadFile = File(...)):
    """Chat 图片上传：落盘存储 + 返回可展示的 media URL 与给视觉模型的 data URL。

    之前只返回 data URL(base64)：用户发的图无法回显，且几 MB base64 会直接写进会话历史。
    普通用户按账号存储策略保存：默认账号空间，选择远程后写入用户自己的远程服务器；
    图片字节只在请求期间临时用于模型输入，不共享给其他账号。
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
    user_id, role = identity(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        record = await save_user_media(user_id, role, file.filename or "upload", mime, content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"保存媒体失败：{exc}") from exc

    return {
        "media_id": record.get("media_id", ""),
        "url": record.get("url", ""),
        "data_url": f"data:{mime};base64,{base64.b64encode(content).decode()}",
        "type": mime,
        "size": len(content),
        "name": record.get("name") or file.filename or "",
        "persistent": True,
        "storage": record.get("storage", "local"),
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
