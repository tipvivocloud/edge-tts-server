"""
=============================================================================
BACKEND FASTAPI - EDGE-TTS BATCH & REAL-TIME WORDBOUNDARY SYNC
=============================================================================
"""
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import base64

app = FastAPI(
    title="HSK TTS & Passive Listening Engine",
    version="3.0.0"
)

# Mở CORS để Web Frontend gọi API không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Kiểm tra trạng thái server (dùng cho UptimeRobot giữ server thức 24/7)"""
    return {"status": "online", "service": "HSK Edge-TTS Batch Sync Engine"}


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """Endpoint phát trực tiếp MP3"""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")
    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
        audio_bytes = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Lỗi tạo file âm thanh")
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
    Endpoint gộp luồng: Trả về âm thanh Base64 + Mốc thời gian (WordBoundary)
    để Frontend cắt lát từng câu trong RAM mà không cần gọi nhiều request.
    """
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
                # Đổi từ ticks sang giây (1 giây = 10.000.000 ticks)
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
