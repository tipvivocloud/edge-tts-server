"""
=============================================================================
BACKEND EDGE-TTS API CHO PHÂN HỆ HSK 4 (RENDER.COM FASTAPI SERVER)
=============================================================================
"""
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts
import base64

app = FastAPI(
    title="HSK 4 Edge-TTS Karaoke API",
    description="Dịch vụ chuyển văn bản tiếng Trung thành giọng đọc Edge-TTS với mốc thời gian Karaoke",
    version="2.0.0"
)

# Cấu hình CORS để web frontend gọi API mà không bị chặn
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint kiểm tra trạng thái hoạt động của server (dùng cho UptimeRobot)"""
    return {
        "status": "online",
        "service": "HSK4 Edge-TTS Engine",
        "default_voice": "zh-CN-YunyangNeural"
    }


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """
    Endpoint phát âm thanh trực tiếp (.mp3)
    - text: Nội dung chữ Hán cần đọc
    - voice: Mã giọng đọc (mặc định: Nam phát thanh Yunyang)
    - rate: Tốc độ đọc (vd: -25%, -15%, -5%, +0%, +15%, +25%)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung chữ Hán không được để trống")

    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
        audio_bytes = b""

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]

        if not audio_bytes:
            raise HTTPException(status_code=500, detail="Không thể tạo dữ liệu âm thanh")

        return Response(content=audio_bytes, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tts-karaoke")
async def tts_with_karaoke(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "-5%"
):
    """
    Endpoint trả về âm thanh Base64 kèm mốc thời gian từng chữ (WordBoundary)
    """
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung chữ Hán không được để trống")

    try:
        communicate = edge_tts.Communicate(text=text.strip(), voice=voice, rate=rate)
        audio_bytes = b""
        boundaries = []

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                # Đổi từ ticks sang giây (1 giây = 10.000.000 ticks)
                boundaries.append({
                    "text": chunk["data"]["text"],
                    "start": chunk["data"]["offset"] / 10_000_000,
                    "duration": chunk["data"]["duration"] / 10_000_000
                })

        return {
            "status": "success",
            "audio_base64": base64.b64encode(audio_bytes).decode("utf-8"),
            "boundaries": boundaries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
