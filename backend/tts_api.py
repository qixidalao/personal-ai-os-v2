"""Third-party TTS proxy + reference voice file upload (user-configured)."""
from __future__ import annotations

import base64
import mimetypes
import secrets
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from backend.executor import validate_target
from backend.ownership import identity

router = APIRouter(prefix="/api/v1/tts", tags=["tts"])
VOICE_DIR = Path("storage/tts_voices")
VOICE_DIR.mkdir(parents=True, exist_ok=True)
MAX_AUDIO = 15 * 1024 * 1024
ALLOWED_AUDIO = {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/aac"}


def _validate_endpoint(endpoint: str, role: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=422, detail="TTS 地址必须是 http/https")
    if not parsed.hostname:
        raise HTTPException(status_code=422, detail="TTS 地址缺少主机名")
    if role != "owner" and parsed.scheme != "https":
        raise HTTPException(status_code=422, detail="普通账号的 TTS 地址必须使用 https")
    try:
        validate_target(parsed.hostname, role, parsed.port or (443 if parsed.scheme == "https" else 80))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return endpoint


def _voice_file(voice_id: str) -> Path | None:
    if not voice_id or "/" in voice_id or ".." in voice_id:
        return None
    for p in VOICE_DIR.glob(f"{voice_id}.*"):
        return p
    return None


@router.post("/voice")
async def upload_voice(request: Request, file: UploadFile = File(...)):
    identity(request)  # 需要登录
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="空文件")
    if len(content) > MAX_AUDIO:
        raise HTTPException(status_code=400, detail="音频文件超过 15MB")
    mime = (file.content_type or mimetypes.guess_type(file.filename or "")[0] or "audio/mpeg").lower()
    if not mime.startswith("audio/") and mime not in ALLOWED_AUDIO:
        raise HTTPException(status_code=400, detail="只支持音频文件")
    ext = mimetypes.guess_extension(mime) or ".mp3"
    if ext == ".mpga":
        ext = ".mp3"
    voice_id = secrets.token_hex(8)
    path = VOICE_DIR / f"{voice_id}{ext}"
    path.write_bytes(content)
    return {"id": voice_id, "url": f"/api/v1/tts/voice/{voice_id}", "name": file.filename or path.name}


@router.get("/voice/{voice_id}")
async def get_voice(voice_id: str):
    path = _voice_file(voice_id)
    if not path:
        raise HTTPException(status_code=404, detail="音频不存在")
    mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
    return FileResponse(path, media_type=mime)


OPENAI_VOICES = [
    {"id": "alloy", "name": "Alloy"},
    {"id": "ash", "name": "Ash"},
    {"id": "ballad", "name": "Ballad"},
    {"id": "coral", "name": "Coral"},
    {"id": "echo", "name": "Echo"},
    {"id": "fable", "name": "Fable"},
    {"id": "nova", "name": "Nova"},
    {"id": "onyx", "name": "Onyx"},
    {"id": "sage", "name": "Sage"},
    {"id": "shimmer", "name": "Shimmer"},
    {"id": "verse", "name": "Verse"},
]


def _parse_voice_list(data) -> list[dict]:
    items = data
    if isinstance(data, dict):
        for key in ("voices", "data", "items", "results"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if isinstance(item, str):
            out.append({"id": item, "name": item})
        elif isinstance(item, dict):
            vid = item.get("id") or item.get("voice_id") or item.get("voice") or item.get("name")
            if vid:
                out.append({"id": str(vid), "name": str(item.get("name") or item.get("display_name") or vid)})
    return out


@router.get("/voices")
async def list_voices(request: Request, endpoint: str, api_key: str = "", model: str = ""):
    user_id, role = identity(request)
    base = endpoint.strip().rstrip("/")
    if not base:
        return JSONResponse({"detail": "endpoint 不能为空"}, status_code=422)
    # 用户可能填的是完整的 /audio/speech，取到根
    if base.endswith("/audio/speech"):
        base = base[: -len("/audio/speech")]
    try:
        _validate_endpoint(base, role)
    except HTTPException as exc:
        return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    candidates = [
        f"{base}/audio/voices",
        f"{base}/voices",
        f"{base}/tts/voices",
        f"{base}/audio/speech/voices",
    ]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=8.0), trust_env=False, follow_redirects=False) as client:
            for url in candidates:
                try:
                    resp = await client.get(url, headers=headers)
                except Exception:
                    continue
                if resp.status_code >= 400:
                    continue
                try:
                    parsed = _parse_voice_list(resp.json())
                except Exception:
                    continue
                if parsed:
                    return {"voices": parsed, "source": "remote", "endpoint": url}
    except Exception:
        pass
    host = (urlparse(base).hostname or "").lower()
    if any(k in host for k in ("openai.com", "azure.com", "microsoft")):
        return {"voices": OPENAI_VOICES, "source": "builtin", "endpoint": ""}
    return {"voices": [], "source": "none", "endpoint": ""}


@router.post("/synthesize")
async def synthesize(request: Request):
    user_id, role = identity(request)
    try:
        data = await request.json()
    except Exception:
        data = {}
    text = str(data.get("text") or "").strip()
    endpoint = str(data.get("endpoint") or "").strip()
    if not text:
        return JSONResponse({"detail": "text 不能为空"}, status_code=422)
    if len(text) > 5000:
        text = text[:5000]
    endpoint = _validate_endpoint(endpoint, role)
    api_key = str(data.get("api_key") or "")
    voice = str(data.get("voice") or "")
    model = str(data.get("model") or "")
    fmt = str(data.get("format") or "mp3")
    api_type = str(data.get("api_type") or "auto")
    extra = data.get("extra") if isinstance(data.get("extra"), dict) else {}
    reference_audio = str(data.get("reference_audio") or "")

    ref_payload: dict = {}
    if reference_audio.startswith("/api/v1/tts/voice/"):
        vid = reference_audio.rsplit("/", 1)[-1]
        path = _voice_file(vid)
        if path:
            raw = path.read_bytes()
            mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
            ref_payload = {
                "reference_audio_base64": base64.b64encode(raw).decode(),
                "reference_audio_mime": mime,
                "reference_audio_name": path.name,
            }
    elif reference_audio:
        ref_payload = {"reference_audio": reference_audio}

    timeout = httpx.Timeout(120.0, connect=10.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client:
            if api_type == "mimo":
                target = endpoint.rstrip("/")
                if not target.endswith("/chat/completions"):
                    target += "/chat/completions"
                instruction = str(data.get("instruction") or "").strip()
                messages = []
                if instruction:
                    messages.append({"role": "user", "content": instruction})
                messages.append({"role": "assistant", "content": text})
                audio: dict = {"format": fmt or "mp3"}
                if model == "mimo-v2.5-tts-voicedesign":
                    if not instruction:
                        return JSONResponse({"detail": "voicedesign 模型必须填写音色描述"}, status_code=422)
                elif model == "mimo-v2.5-tts-voiceclone":
                    ref = reference_audio
                    if not ref:
                        return JSONResponse({"detail": "voiceclone 模型必须上传参考音频"}, status_code=422)
                    if ref.startswith("/api/v1/tts/voice/"):
                        vid = ref.rsplit("/", 1)[-1]
                        path = _voice_file(vid)
                        if not path:
                            return JSONResponse({"detail": "参考音频不存在"}, status_code=422)
                        raw = path.read_bytes()
                        mime = mimetypes.guess_type(path.name)[0] or "audio/mpeg"
                        audio["voice"] = f"data:{mime};base64,{base64.b64encode(raw).decode()}"
                    else:
                        audio["voice"] = ref
                else:
                    audio["voice"] = voice or "mimo_default"
                payload = {"model": model, "messages": messages, "audio": audio, "stream": False}
                headers = {"api-key": api_key, "Content-Type": "application/json"}
                resp = await client.post(target, json=payload, headers=headers)
                if resp.status_code >= 400:
                    return JSONResponse({"detail": f"MiMo TTS 返回 {resp.status_code}: {resp.text[:300]}"}, status_code=502)
                try:
                    body = resp.json()
                    b64 = body["choices"][0]["message"]["audio"]["data"]
                except Exception:
                    return JSONResponse({"detail": "MiMo 返回中没有 audio.data（检查模型是否为 TTS 模型）"}, status_code=502)
                try:
                    audio_bytes = base64.b64decode(b64)
                except Exception:
                    return JSONResponse({"detail": "MiMo audio.data 不是合法 base64"}, status_code=502)
                mime = mimetypes.guess_type(f"a.{fmt or 'mp3'}")[0] or "audio/mpeg"
                return Response(content=audio_bytes, media_type=mime, headers={"Cache-Control": "no-store"})
            if api_type == "template" or (api_type == "auto" and "{text}" in endpoint):
                if "{text}" not in endpoint:
                    return JSONResponse({"detail": "自定义 URL 模板必须包含 {text}"}, status_code=422)
                url = endpoint.replace("{text}", quote(text))
                params = {}
                if voice:
                    params["voice"] = voice
                if model:
                    params["model"] = model
                if fmt:
                    params["format"] = fmt
                params.update({k: v for k, v in extra.items() if isinstance(v, (str, int, float))})
                if reference_audio:
                    params["reference_audio"] = reference_audio
                headers = {"Accept": f"audio/{fmt}"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.get(url, params=params, headers=headers)
            else:
                target = endpoint
                if api_type == "openai" and not target.rstrip("/").endswith("/audio/speech"):
                    target = target.rstrip("/") + "/audio/speech"
                payload = {"input": text}
                if model:
                    payload["model"] = model
                if voice:
                    payload["voice"] = voice
                if fmt:
                    payload["response_format"] = fmt
                payload.update(ref_payload)
                payload.update({k: v for k, v in extra.items() if isinstance(v, (str, int, float, bool, dict, list))})
                headers = {"Content-Type": "application/json", "Accept": f"audio/{fmt}"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                resp = await client.post(target, json=payload, headers=headers)
            if resp.status_code >= 400:
                detail = resp.text[:300]
                return JSONResponse({"detail": f"第三方 TTS 返回 {resp.status_code}: {detail}"}, status_code=502)
            content = resp.content
            if len(content) > 30 * 1024 * 1024:
                return JSONResponse({"detail": "TTS 音频超过 30MB"}, status_code=502)
            media = resp.headers.get("content-type") or f"audio/{fmt}"
            return Response(content=content, media_type=media, headers={"Cache-Control": "no-store"})
    except Exception as exc:  # noqa: BLE001
        return JSONResponse({"detail": f"TTS 请求失败: {exc}"}, status_code=502)
