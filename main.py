"""
=============================================================================
BACKEND EDGE-TTS FASTAPI (ĐỒNG BỘ MỐC THỜI GIAN CHÍNH XÁC TỪNG TỪ)
=============================================================================
"""
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import base64

app = FastAPI(
    title="HSK 4 Edge-TTS Smart Sync API",
    version="2.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "online", "service": "HSK 4 Edge-TTS Word-Sync Engine"}


# Endpoint 1: Trả về MP3 trực tiếp (nghe thử hoặc tải nhanh)
@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")
    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 🌟 Endpoint 2: Trả về MP3 + Mốc thời gian chính xác từng từ từ Edge-TTS
@app.get("/tts-sync")
async def tts_sync(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")
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
                # 1 giây = 10.000.000 ticks
                boundaries.append({
                    "text": word_text,
                    "start": offset / 10_000_000,
                    "duration": duration / 10_000_000
                })

        return {
            "status": "success",
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
            "boundaries": boundaries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
