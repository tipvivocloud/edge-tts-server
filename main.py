"""
=============================================================================
BACKEND FASTAPI - EDGE-TTS CLEAN PLAIN-TEXT SHARED AUDIO SERVER
=============================================================================
"""
import os
import json
import base64
import hashlib
from pathlib import Path
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts

app = FastAPI(
    title="HSK AI Clean Plain-Text TTS Engine",
    version="3.5.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Thư mục lưu trữ bộ nhớ đệm âm thanh trên Server
CACHE_DIR = Path("./tts_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_key(voice: str, rate: str, text: str) -> str:
    """Định danh file thuần bằng Chữ Hán và Giọng đọc"""
    raw_str = f"{voice.strip()}|{rate.strip()}|{text.strip()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


@app.get("/")
async def root():
    cache_count = len(list(CACHE_DIR.glob("*.json"))) + len(list(CACHE_DIR.glob("*.mp3")))
    return {
        "status": "online",
        "service": "HSK Edge-TTS Clean Plain-Text Engine",
        "cached_files": cache_count
    }


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "+0%"
):
    """Endpoint phát trực tiếp MP3 cho Game, SRS, Từ đơn"""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, clean_text)
    cache_file = CACHE_DIR / f"{cache_key}.mp3"

    if cache_file.exists():
        try:
            return Response(content=cache_file.read_bytes(), media_type="audio/mpeg")
        except Exception:
            pass

    try:
        communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Lỗi tạo file âm thanh")

        cache_file.write_bytes(audio_bytes)
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tts-sync")
async def tts_sync(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "+0%"
):
    """Endpoint kèm WordBoundary cho Reading & Listening"""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, clean_text)
    cache_file = CACHE_DIR / f"{cache_key}_sync.json"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        communicate = edge_tts.Communicate(text=clean_text, voice=voice, rate=rate)
        audio_bytes = b""
        boundaries = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                data = chunk.get("data", chunk)
                offset = data.get("offset", 0)
                duration = data.get("duration", 0)
                word_text = data.get("text", "")
                boundaries.append({
                    "text": word_text,
                    "start": offset / 10_000_000,
                    "duration": duration / 10_000_000
                })

        result = {
            "status": "success",
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
            "boundaries": boundaries
        }

        cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/tts")
@app.get("/tts-delete")
async def delete_tts_cache(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "+0%"
):
    """Xóa file cache khi người dùng sửa câu ví dụ"""
    clean_text = text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, clean_text)
    mp3_file = CACHE_DIR / f"{cache_key}.mp3"
    json_file = CACHE_DIR / f"{cache_key}_sync.json"

    deleted = []
    if mp3_file.exists():
        mp3_file.unlink(missing_ok=True)
        deleted.append(f"{cache_key}.mp3")
    if json_file.exists():
        json_file.unlink(missing_ok=True)
        deleted.append(f"{cache_key}_sync.json")

    return {"status": "success", "deleted": deleted}
