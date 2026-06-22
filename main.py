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

# غيرنا اسم الجلسة هنا لـ amw_new_session عشان يطلب الرقم فوراً
client = TelegramClient("amw_new_session", API_ID, API_HASH)

@app.on_event("startup")
async def startup_event():
    await client.connect()
    # لو مش متسجل، يطلب تسجيل الدخول فوراً في الترمنال
    if not await client.is_user_authorized():
        print("🛑 [AMW Code] Authorization required. Please log in below:")
        phone = input("Please enter your phone number (e.g. +2010...): ")
        await client.send_code_request(phone)
        code = input("Please enter the code you received on Telegram: ")
        try:
            await client.sign_in(phone, code)
        except Exception as e:
            if "Password" in str(e):
                password = input("Please enter your 2FA password: ")
                await client.sign_in(password=password)
    print("⚡ [AMW Code] Telethon Client Connected Successfully!")

@app.on_event("shutdown")
async def shutdown_event():
    await client.disconnect()

async def stream_generator(client, message, start_byte, chunk_size, file_size):
    current_byte = start_byte
    async for chunk in client.iter_download(
        message.media.document, 
        offset=start_byte, 
        chunk_size=chunk_size
    ):
        yield chunk
        current_byte += len(chunk)
        if current_byte >= file_size:
            break

@app.get("/stream")
async def stream_video(channel_id: int, message_id: int, range: str = Header(None)):
    if not await client.is_user_authorized():
        raise HTTPException(status_code=401, detail="Userbot not authorized.")

    try:
        str_channel = str(channel_id)
        if not str_channel.startswith("-100"):
            entity_id = int(f"-100{str_channel}") if not str_channel.startswith("100") else int(f"-{str_channel}")
        else:
            entity_id = channel_id

        message = await client.get_messages(entity_id, ids=message_id)

        if not message or not message.media or not hasattr(message.media, 'document'):
            raise HTTPException(status_code=404, detail="Video not found.")

        document = message.media.document
        file_size = document.size
        mime_type = document.mime_type or "video/mp4"

        start_byte = 0
        end_byte = file_size - 1
        default_chunk_size = 1024 * 1024

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

        return StreamingResponse(
            stream_generator(client, message, start_byte, default_chunk_size, file_size),
            status_code=206 if range else 200,
            headers=headers,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
