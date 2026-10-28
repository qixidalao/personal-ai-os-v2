"""HTTP upload endpoint for local, conservative photo enhancement."""
from __future__ import annotations
import asyncio,tempfile
from pathlib import Path
from fastapi import APIRouter,File,HTTPException,UploadFile
from tools.media import MEDIA_DIR,MAX_IMAGE_BYTES,send_image
from tools.media.image_enhance import DEFAULT_MODEL,enhance_image_file
router=APIRouter(prefix="/api/v1/media",tags=["media"])
_slots=asyncio.Semaphore(1)
_SUPPORTED={"image/jpeg":".jpg","image/png":".png","image/webp":".webp","image/bmp":".bmp"}
@router.get("/enhance/status")
async def enhancement_status():
    return {"available":Path(DEFAULT_MODEL).is_file(),"model":"Real-ESRGAN x2plus","scale":2,"default_blend_strength":0.3,"face_reconstruction":False}
@router.post("/enhance")
async def enhance_upload(file:UploadFile=File(...),blend_strength:float=0.3):
    if file.content_type not in _SUPPORTED: raise HTTPException(status_code=415,detail="支持 JPG、PNG、WebP、BMP 图片")
    if not 0.1<=blend_strength<=0.65: raise HTTPException(status_code=422,detail="blend_strength 必须在 0.1 到 0.65 之间")
    if _slots.locked(): raise HTTPException(status_code=429,detail="图片修复任务正在运行，请稍后重试")
    MEDIA_DIR.mkdir(parents=True,exist_ok=True); tmp_name=None
    try:
        with tempfile.NamedTemporaryFile(prefix="upload-",suffix=_SUPPORTED[file.content_type],dir=MEDIA_DIR,delete=False) as tmp:
            tmp_name=tmp.name; total=0
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>MAX_IMAGE_BYTES: raise HTTPException(status_code=413,detail="图片不能超过20MB")
                tmp.write(chunk)
        async with _slots:
            output=await asyncio.to_thread(enhance_image_file,tmp_name,blend_strength)
            try: return send_image(str(output),caption="照片清晰化（Real-ESRGAN x2）")
            finally: output.unlink(missing_ok=True)
    except HTTPException: raise
    except Exception as exc: raise HTTPException(status_code=503,detail=str(exc)) from exc
    finally:
        await file.close()
        if tmp_name: Path(tmp_name).unlink(missing_ok=True)
