import os
import re
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

import dotenv
import uvicorn
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from telethon import TelegramClient
from telethon.sessions import StringSession

dotenv.load_dotenv()

API_ID = int(os.getenv("TELEGRAM_API_ID", "38232640"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "").strip()
SESSION_FILE = os.getenv("TELEGRAM_SESSION_FILE", "amw_new_session.session").strip()

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_SESSION_BASE = Path("/tmp/amw_new_session")
RUNTIME_SESSION_FILE = RUNTIME_SESSION_BASE.with_suffix(".session")
BUNDLED_SESSION_FILE = BASE_DIR / SESSION_FILE


def build_session_source():
    """
    Prefer StringSession on Vercel.
    If not available, copy the bundled SQLite session file into /tmp so Telethon can read/write safely.
    """
    if SESSION_STRING:
        return StringSession(SESSION_STRING)

    if BUNDLED_SESSION_FILE.exists():
        try:
            RUNTIME_SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
            if not RUNTIME_SESSION_FILE.exists():
                shutil.copy2(BUNDLED_SESSION_FILE, RUNTIME_SESSION_FILE)
        except Exception:
            # If copying fails, Telethon will still try the bundled file path.
            pass
        return str(RUNTIME_SESSION_BASE)

    return str(RUNTIME_SESSION_BASE)


client = TelegramClient(build_session_source(), API_ID, API_HASH)

app = FastAPI(title="AMW LMS Streaming Proxy")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "HEAD", "OPTIONS"],
    allow_headers=["*"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await client.connect()
    yield
    await client.disconnect()


app.router.lifespan_context = lifespan


async def stream_generator(message, start_byte: int, end_byte: int | None, chunk_size: int):
    """
    Stream only the requested byte range directly from Telegram.
    No full-file buffering in memory.
    """
    current = start_byte
    async for chunk in client.iter_download(
        message.media.document,
        offset=start_byte,
        chunk_size=chunk_size,
    ):
        if end_byte is not None:
            remaining = end_byte - current + 1
            if remaining <= 0:
                break

            if len(chunk) > remaining:
                yield chunk[:remaining]
                break

        yield chunk
        current += len(chunk)

        if end_byte is not None and current > end_byte:
            break


def normalize_entity_id(channel_id: int) -> int:
    s = str(channel_id).strip()
    if s.startswith("-100"):
        return int(s)
    if s.startswith("100"):
        return int(f"-{s}")
    return int(f"-100{s}")


def parse_range_header(range_header: str | None, file_size: int):
    if not range_header:
        return 0, file_size - 1, False

    match = re.search(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        return 0, file_size - 1, False

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    if start < 0 or start >= file_size:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    end = min(end, file_size - 1)
    if end < start:
        raise HTTPException(status_code=416, detail="Requested Range Not Satisfiable")

    return start, end, True


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.get("/stream")
async def stream_video(channel_id: int, message_id: int, range: str = Header(default=None)):
    if not API_HASH:
        raise HTTPException(status_code=500, detail="TELEGRAM_API_HASH is missing")

    if not await client.is_user_authorized():
        raise HTTPException(
            status_code=401,
            detail="Telegram session is not authorized. Provide TELEGRAM_SESSION or include the session file.",
        )

    try:
        entity_id = normalize_entity_id(channel_id)
        message = await client.get_messages(entity_id, ids=message_id)

        if not message or not getattr(message, "media", None) or not hasattr(message.media, "document"):
            raise HTTPException(status_code=404, detail="Video not found")

        document = message.media.document
        file_size = int(document.size or 0)
        if file_size <= 0:
            raise HTTPException(status_code=404, detail="Invalid media file")

        mime_type = document.mime_type or "video/mp4"
        start_byte, end_byte, is_partial = parse_range_header(range, file_size)
        content_length = end_byte - start_byte + 1

        headers = {
            "Accept-Ranges": "bytes",
            "Content-Type": mime_type,
            "Content-Length": str(content_length),
            "Content-Disposition": "inline",
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "Vary": "Range",
        }

        if is_partial:
            headers["Content-Range"] = f"bytes {start_byte}-{end_byte}/{file_size}"

        return StreamingResponse(
            stream_generator(message, start_byte, end_byte, 256 * 1024),
            status_code=206 if is_partial else 200,
            headers=headers,
            media_type=mime_type,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
