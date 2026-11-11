"""Conservative 2x general photo enhancement using local Real-ESRGAN."""
# 中文：使用本地 Real-ESRGAN 进行保守的 2 倍通用照片增强。
from __future__ import annotations
import os, subprocess, tempfile
from pathlib import Path
from tools import ToolRegistry
from tools.media import MEDIA_DIR, send_image
DEFAULT_PYTHON = os.getenv("HHS_REALESRGAN_PYTHON", "")
DEFAULT_REPO = os.getenv("HHS_REALESRGAN_REPO", "")
DEFAULT_MODEL = os.getenv("HHS_REALESRGAN_MODEL", "")
_RUNNER = r"""
import cv2, sys, torch
repo, source, destination, model_path, amount = sys.argv[1:]
sys.path.insert(0, repo)
from basicsr.archs.rrdbnet_arch import RRDBNet
from basicsr.utils.realesrgan_utils import RealESRGANer
img=cv2.imread(source,cv2.IMREAD_COLOR)
if img is None: raise ValueError("无法读取图片")
h,w=img.shape[:2]
if w*h>10_000_000: raise ValueError("图片像素超过1000万限制")
net=RRDBNet(num_in_ch=3,num_out_ch=3,num_feat=64,num_block=23,num_grow_ch=32,scale=2)
up=RealESRGANer(scale=2,model_path=model_path,model=net,tile=256,tile_pad=10,pre_pad=0,half=False,device=torch.device("cpu"))
with torch.no_grad(): restored,_=up.enhance(img,outscale=2)
base=cv2.resize(img,(w*2,h*2),interpolation=cv2.INTER_LANCZOS4)
result=cv2.addWeighted(base,1.0-float(amount),restored,float(amount),0)
if not cv2.imwrite(destination,result,[cv2.IMWRITE_JPEG_QUALITY,94]): raise RuntimeError("无法保存修复图片")
"""
def enhancement_available() -> bool:
    return bool(DEFAULT_PYTHON and DEFAULT_REPO and DEFAULT_MODEL and
                Path(DEFAULT_PYTHON).is_file() and Path(DEFAULT_MODEL).is_file())


def enhance_image_file(source: str | Path, blend_strength: float=0.3) -> Path:
    source=Path(source).expanduser().resolve()
    if not source.is_file(): raise FileNotFoundError(f"图片不存在: {source}")
    if not 0.1<=float(blend_strength)<=0.65: raise ValueError("blend_strength 必须在 0.1 到 0.65 之间")
    python=Path(os.getenv("HHS_REALESRGAN_PYTHON",DEFAULT_PYTHON)); repo=Path(os.getenv("HHS_REALESRGAN_REPO",DEFAULT_REPO)); model=Path(os.getenv("HHS_REALESRGAN_MODEL",DEFAULT_MODEL))
    if not python.is_file() or not model.is_file(): raise RuntimeError("Real-ESRGAN 本地运行环境或模型文件不存在")
    MEDIA_DIR.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix="enhanced-",suffix=".jpg",dir=MEDIA_DIR); os.close(fd); output=Path(name)
    try:
        def winpath(path): return subprocess.run(["wslpath","-w",str(path)],check=True,capture_output=True,text=True,timeout=10).stdout.strip()
        args=[str(python),"-c",_RUNNER,winpath(repo),winpath(source),winpath(output),winpath(model),str(float(blend_strength))]
        proc=subprocess.run(args,capture_output=True,text=True,timeout=300)
        if proc.returncode: raise RuntimeError("Real-ESRGAN 处理失败: "+(proc.stderr or proc.stdout).strip()[-1500:])
        if not output.is_file() or not output.stat().st_size: raise RuntimeError("Real-ESRGAN 没有生成输出文件")
        return output
    except Exception: output.unlink(missing_ok=True); raise
@ToolRegistry.register("restore_image","对本地照片进行保守的通用清晰化和2倍放大，不做人脸重建；传入本机图片路径，可选融合强度0.1-0.65（默认0.3）。","media")
                                                                                                                                                                                                   # 中文：媒体
def restore_image(path: str,blend_strength: float=0.3)->dict:
    if not enhancement_available():
        raise RuntimeError("图片增强功能未安装或未配置；请在实例管理员的部署环境中安装 Real-ESRGAN 模型后启用")
    result=enhance_image_file(path,blend_strength)
    try: return send_image(str(result),caption="照片清晰化（Real-ESRGAN x2）")
    finally: result.unlink(missing_ok=True)
