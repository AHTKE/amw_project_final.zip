import os
import re
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from telethon import TelegramClient
import uvicorn
import dotenv

dotenv.load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "38232640"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "f55e14c6c0cda4b39b17a0509ab919bb")

app = FastAPI(title="AMW LMS Streaming Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = TelegramClient("amw_new_session", API_ID, API_HASH)

@app.on_event("startup")
async def startup_event():
    await client.connect()
    if not await client.is_user_authorized():
        print("🛑 [AMW Code] Authorization required.")

@app.on_event("shutdown")
async def shutdown_event():
    await client.disconnect()

# --- التعديل الأساسي هنا (Streaming Generator) ---
async def stream_generator(message, start_byte, chunk_size):
    """
    يقوم ببث الفيديو كقطع صغيرة مباشرة من تليجرام للمتصفح 
    دون تحميله كاملاً في ذاكرة الخادم.
    """
    async for chunk in client.iter_download(
        message.media.document, 
        offset=start_byte, 
        chunk_size=chunk_size
    ):
        yield chunk

@app.get("/stream")
async def stream_video(channel_id: int, message_id: int, range: str = Header(None)):
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Userbot not authorized.")

    try:
        # تصحيح معرف القناة
        str_channel = str(channel_id)
        entity_id = int(f"-100{str_channel}") if not str_channel.startswith("-100") else channel_id

        message = await client.get_messages(entity_id, ids=message_id)

        if not message or not message.media or not hasattr(message.media, 'document'):
            raise HTTPException(status_code=404, detail="Video not found.")

        document = message.media.document
        file_size = document.size
        mime_type = document.mime_type or "video/mp4"

        start_byte = 0
        end_byte = file_size - 1
        default_chunk_size = 1024 * 1024  # 1MB

        if range:
            match = re.search(r"bytes=(\d+)-(\d*)", range)
            if match:
                start_byte = int(match.group(1))
                if match.group(2):
                    end_byte = int(match.group(2))

        content_length = end_byte - start_byte + 1

        headers = {
            "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": mime_type,
            "Cache-Control": "no-cache",
        }

        # استخدام الـ StreamingResponse المحدث
        return StreamingResponse(
            stream_generator(message, start_byte, default_chunk_size),
            status_code=206 if range else 200,
            headers=headers,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
        
