"""
=============================================================================
BACKEND FASTAPI - EDGE-TTS SERVER WITH PINYIN-AWARE CACHE DISAMBIGUATION
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
    title="HSK Official TTS Engine (Bounded Storage & Pinyin Aware)",
    version="3.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_DIR = Path("./tts_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def get_cache_key(voice: str, rate: str, text: str, pinyin: str = "") -> str:
    """
    Tạo mã băm duy nhất có kèm Pinyin để phân biệt chính xác các từ đa âm (多音字)
    Ví dụ: 还 (hái) != 还 (huán)
    """
    raw_str = f"{voice.strip()}|{rate.strip()}|{text.strip()}|{pinyin.strip().lower()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


@app.get("/")
async def root():
    cache_count = len(list(CACHE_DIR.glob("*.json"))) + len(list(CACHE_DIR.glob("*.mp3")))
    return {
        "status": "online",
        "service": "HSK Official Bounded Audio Engine",
        "cached_variants": cache_count
    }


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "+0%",
    pinyin: str = ""
):
    """Endpoint phát MP3 cho từ vựng và bài đọc HSK chuẩn"""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, text, pinyin)
    cache_file = CACHE_DIR / f"{cache_key}.mp3"

    if cache_file.exists():
        try:
            return Response(content=cache_file.read_bytes(), media_type="audio/mpeg")
        except Exception:
            pass

    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
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
    rate: str = "+0%",
    pinyin: str = ""
):
    """Endpoint gộp luồng Base64 + Mốc thời gian WordBoundary cho Reading & Listening"""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, text, pinyin)
    cache_file = CACHE_DIR / f"{cache_key}_sync.json"

    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
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
