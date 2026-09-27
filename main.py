"""
=============================================================================
BACKEND FASTAPI - EDGE-TTS WITH SERVER-SIDE CACHE & WORDBOUNDARY SYNC
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
    title="HSK TTS & Passive Listening Engine (Server Cache Enabled)",
    version="3.1.0"
)

# Mở CORS để Web Frontend gọi API không bị chặn
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
    """Tạo mã băm SHA-256 định danh duy nhất cho từng biến thể âm thanh"""
    raw_str = f"{voice.strip()}|{rate.strip()}|{text.strip()}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


@app.get("/")
async def root():
    """Kiểm tra trạng thái server (dùng cho UptimeRobot giữ server thức 24/7)"""
    cache_count = len(list(CACHE_DIR.glob("*.json"))) + len(list(CACHE_DIR.glob("*.mp3")))
    return {
        "status": "online",
        "service": "HSK Edge-TTS Server-Side Caching Engine",
        "cached_variants": cache_count
    }


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """Endpoint phát trực tiếp MP3 (Có Cache trên Server)"""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, text)
    cache_file = CACHE_DIR / f"{cache_key}.mp3"

    # 1. Kiểm tra cache trên server: Nếu có -> Trả về ngay lập tức (< 5ms)
    if cache_file.exists():
        try:
            audio_bytes = cache_file.read_bytes()
            return Response(content=audio_bytes, media_type="audio/mpeg")
        except Exception:
            pass

    # 2. Nếu chưa có: Tạo mới bằng Edge-TTS
    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Lỗi tạo file âm thanh")

        # 3. Lưu vào Cache Server cho những người dùng sau tải lại
        try:
            cache_file.write_bytes(audio_bytes)
        except Exception as write_err:
            print(f"[Cache Write Error]: {write_err}")

        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tts-sync")
async def tts_sync(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """
    Endpoint gộp luồng: Âm thanh Base64 + Mốc WordBoundary (Có Cache trên Server)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, text)
    cache_file = CACHE_DIR / f"{cache_key}_sync.json"

    # 1. Kiểm tra cache trên server: Nếu có -> Trả JSON ngay tức thì
    if cache_file.exists():
        try:
            cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
            return cached_data
        except Exception:
            pass

    # 2. Nếu chưa có: Tạo mới bằng Edge-TTS
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
                # Đổi từ ticks sang giây (1 giây = 10.000.000 ticks)
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

        # 3. Lưu vào Cache Server
        try:
            cache_file.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except Exception as write_err:
            print(f"[Cache Write Error]: {write_err}")

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
