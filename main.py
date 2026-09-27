"""
=============================================================================
BACKEND FASTAPI - EDGE-TTS AUTO-SSML PHONEME & WORDBOUNDARY SERVER
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
    title="HSK AI TTS Engine with Auto-SSML Phoneme",
    version="3.4.0"
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

# Bảng chuyển đổi nguyên âm thanh điệu sang số SAPI của Microsoft
TONE_MAP = {
    'ā': ('a', 1), 'á': ('a', 2), 'ǎ': ('a', 3), 'à': ('a', 4),
    'ē': ('e', 1), 'é': ('e', 2), 'ě': ('e', 3), 'è': ('e', 4),
    'ī': ('i', 1), 'í': ('i', 2), 'ǐ': ('i', 3), 'ì': ('i', 4),
    'ō': ('o', 1), 'ó': ('o', 2), 'ǒ': ('o', 3), 'ò': ('o', 4),
    'ū': ('u', 1), 'ú': ('u', 2), 'ǔ': ('u', 3), 'ù': ('u', 4),
    'ǖ': ('v', 1), 'ǘ': ('v', 2), 'ǚ': ('v', 3), 'ǜ': ('v', 4), 'ü': ('v', 5),
}


def pinyin_to_sapi(py: str) -> str:
    """Chuyển Pinyin có dấu (hái, huán) sang định dạng SAPI (hai 2, huan 2)"""
    if not py:
        return ""
    raw = py.strip().split('/')[0].split(',')[0].strip().lower()
    tone = 5
    clean_chars = []
    for char in raw:
        if char in TONE_MAP:
            base_char, t = TONE_MAP[char]
            clean_chars.append(base_char)
            tone = t
        elif char.isdigit():
            tone = int(char)
        elif char.isalpha():
            clean_chars.append(char)
    syllable = "".join(clean_chars)
    if not syllable:
        return ""
    return f"{syllable} {tone}"


def build_ssml_payload(text: str, voice: str, rate: str, pinyin: str = "") -> str:
    """Nếu là từ đơn kèm Pinyin, tự động bọc thẻ SSML <phoneme> chuẩn Microsoft"""
    clean_text = text.strip()
    if len(clean_text) == 1 and pinyin.strip():
        sapi_ph = pinyin_to_sapi(pinyin)
        if sapi_ph:
            return (
                f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='zh-CN'>"
                f"<voice name='{voice}'>"
                f"<prosody rate='{rate}'>"
                f"<phoneme alphabet='sapi' ph='{sapi_ph}'>{clean_text}</phoneme>"
                f"</prosody>"
                f"</voice>"
                f"</speak>"
            )
    return clean_text


def get_cache_key(voice: str, rate: str, text: str, pinyin: str = "") -> str:
    """Tạo khóa cache: Phân biệt Pinyin cho từ đơn 1 chữ, băm thuần cho từ ghép và câu"""
    clean_text = text.strip()
    sapi_ph = pinyin_to_sapi(pinyin) if len(clean_text) == 1 and pinyin.strip() else ""
    raw_str = f"{voice.strip()}|{rate.strip()}|{clean_text}|{sapi_ph}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()


@app.get("/")
async def root():
    cache_count = len(list(CACHE_DIR.glob("*.json"))) + len(list(CACHE_DIR.glob("*.mp3")))
    return {
        "status": "online",
        "service": "HSK Edge-TTS Auto-SSML Engine",
        "cached_files": cache_count
    }


@app.get("/tts")
async def text_to_speech(
    text: str,
    voice: str = "zh-CN-YunyangNeural",
    rate: str = "+0%",
    pinyin: str = ""
):
    """Endpoint phát trực tiếp MP3 cho Game, SRS, Từ đơn"""
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
        payload = build_ssml_payload(text, voice, rate, pinyin)
        communicate = edge_tts.Communicate(text=payload, voice=voice, rate=rate)
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
    """Endpoint kèm WordBoundary cho Reading & Listening"""
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
        payload = build_ssml_payload(text, voice, rate, pinyin)
        communicate = edge_tts.Communicate(text=payload, voice=voice, rate=rate)
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
    rate: str = "+0%",
    pinyin: str = ""
):
    """Xóa file cache khi người dùng sửa câu ví dụ"""
    if not text or not text.strip():
        raise HTTPException(status_code=400, detail="Nội dung không được để trống")

    cache_key = get_cache_key(voice, rate, text, pinyin)
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
