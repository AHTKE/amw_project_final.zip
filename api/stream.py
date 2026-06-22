"""
AMW LMS Streaming Proxy — Vercel Serverless (Python)
Endpoint: GET /api/stream?channel_id=<int>&message_id=<int>

ENV REQUIRED (set in Vercel → Project → Settings → Environment Variables):
  TELEGRAM_API_ID         e.g. 12345678
  TELEGRAM_API_HASH       e.g. abc123...
  TELEGRAM_SESSION        StringSession (generate locally with generate_session.py)

NOTES:
  * Vercel filesystem is read-only (except /tmp). We MUST use StringSession,
    not the .session SQLite file.
  * Hobby plan max execution = 60s. Long videos may be cut. The browser will
    auto-reconnect with a new Range request for the next chunk, so playback
    usually still works.
"""

import os
import re
import asyncio
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = os.environ["TELEGRAM_SESSION"]

app = FastAPI(title="AMW LMS Streaming Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

_client: TelegramClient | None = None
_lock = asyncio.Lock()


async def get_client() -> TelegramClient:
    global _client
    async with _lock:
        if _client is None:
            c = TelegramClient(StringSession(SESSION), API_ID, API_HASH)
            await c.connect()
            if not await c.is_user_authorized():
                raise HTTPException(
                    status_code=401,
                    detail="Userbot not authorized. Regenerate TELEGRAM_SESSION.",
                )
            _client = c
        return _client


@app.get("/api/health")
async def health():
    try:
        c = await get_client()
        me = await c.get_me()
        return {"ok": True, "user": me.username or me.first_name}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


async def stream_generator(client, document, start_byte, file_size):
    # 512 KB chunks — small enough to stay well under memory limits
    chunk_size = 512 * 1024
    sent = 0
    target = file_size - start_byte
    async for chunk in client.iter_download(
        document, offset=start_byte, chunk_size=chunk_size, request_size=chunk_size
    ):
        if not chunk:
            break
        if sent + len(chunk) > target:
            chunk = chunk[: target - sent]
        yield chunk
        sent += len(chunk)
        if sent >= target:
            break


@app.get("/api/stream")
@app.get("/stream")
async def stream_video(
    channel_id: int, message_id: int, range: str | None = Header(None)
):
    client = await get_client()

    # Normalize channel id: accept 123456, 100123456, or -100123456
    s = str(channel_id)
    if s.startswith("-100"):
        entity_id = channel_id
    elif s.startswith("100"):
        entity_id = int(f"-{s}")
    else:
        entity_id = int(f"-100{s}")

    try:
        message = await client.get_messages(entity_id, ids=message_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"get_messages failed: {e}")

    if not message or not message.media or not hasattr(message.media, "document"):
        raise HTTPException(status_code=404, detail="Video not found.")

    document = message.media.document
    file_size = document.size
    mime_type = document.mime_type or "video/mp4"

    start_byte = 0
    end_byte = file_size - 1
    if range:
        m = re.search(r"bytes=(\d+)-(\d*)", range)
        if m:
            start_byte = int(m.group(1))
            if m.group(2):
                end_byte = min(int(m.group(2)), file_size - 1)

    # Cap per-request size to keep within Vercel's 60s limit (~25 MB safe range)
    MAX_CHUNK = 8 * 1024 * 1024  # 8 MB per HTTP response
    if end_byte - start_byte + 1 > MAX_CHUNK:
        end_byte = start_byte + MAX_CHUNK - 1

    content_length = end_byte - start_byte + 1
    headers = {
        "Content-Range": f"bytes {start_byte}-{end_byte}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
        "Cache-Control": "no-cache",
    }

    return StreamingResponse(
        stream_generator(client, document, start_byte, end_byte + 1),
        status_code=206 if range else 200,
        headers=headers,
    )
