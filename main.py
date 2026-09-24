"""
=============================================================================
BACKEND EDGE-TTS SIÊU NHẸ CHO HSK 4 (FASTAPI - RENDER.COM)
=============================================================================
"""
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts

app = FastAPI(title="HSK 4 TTS Engine")

# Mở quyền CORS để web frontend gọi API không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Dùng để kiểm tra server hoặc cắm UptimeRobot giữ server luôn thức"""
    return {"status": "online", "message": "HSK 4 TTS Engine is Ready"}


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """
    Endpoint phát âm thanh trực tiếp (audio/mpeg)
    - Nhận: text, voice, rate
    - Trả về: Dữ liệu nhị phân MP3 trực tiếp, không qua xử lý trung gian
    """
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
