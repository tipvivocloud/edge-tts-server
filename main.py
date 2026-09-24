from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import edge_tts

app = FastAPI()

# Mở toàn bộ quyền CORS để trang web của bạn gọi được âm thanh
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "Edge-TTS Service is running"}

@app.get("/tts")
async def text_to_speech(text: str, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "-5%"):
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Thiếu nội dung text")
    try:
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        return Response(content=audio_data, media_type="audio/mpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
